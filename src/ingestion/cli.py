"""Typer commands for local document inspection, parsing, OCR, and text-tree extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from ingestion.config import DoclingSettings
from ingestion.doctor import check_environment
from ingestion.library import docling_artifacts_path, get_year
from ingestion.logging import configure_logging
from ingestion.normalization.validation import validate_document_file, validation_summary
from ingestion.ocr.environment import check_ocr_environment
from ingestion.ocr.evaluator import evaluate_ocr
from ingestion.ocr.models import OCRConfiguration, OCRQualityOutcome
from ingestion.ocr.parsing import parse_ocr_derivative
from ingestion.ocr.service import OCRExecutionError, create_ocr_derivative
from ingestion.ocr.validation import validate_derivative_file
from ingestion.pipeline import (
    parse_document,
    parse_sample,
    select_representative_documents,
)
from ingestion.reports import write_reports
from ingestion.scanner import inspect_library as scan_library
from ingestion.scanner import inspect_path
from ingestion.text_tree.models import (
    SUPPORTED_TEXT_EXPORT_EXTENSIONS,
    ExportStatus,
    TextExportConfiguration,
)
from ingestion.text_tree.service import extract_text_tree

app = typer.Typer(help="Inspect and normalize a local document library without modifying it.")
console = Console()
error_console = Console(stderr=True)


def _ocr_languages(value: str) -> list[str]:
    languages = [item.strip().lower() for item in value.split("+") if item.strip()]
    if not languages:
        raise typer.BadParameter("Specify one or more language codes, for example fra+eng.")
    return languages


def _validate_output(input_root: Path, output: Path) -> None:
    resolved_input = input_root.resolve()
    resolved_output = output.resolve()
    if resolved_output == resolved_input or resolved_output.is_relative_to(resolved_input):
        raise typer.BadParameter(
            "output must not be inside the document library", param_hint="--output"
        )


@app.command("inspect-library")
def inspect_library_command(
    input_root: Annotated[
        Path, typer.Option("--input", help="Root directory scanned recursively.")
    ] = Path("pdfsrc"),
    output: Annotated[
        Path, typer.Option("--output", help="Directory where reports are written.")
    ] = Path("data/reports"),
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help="Inspect at most this many files.")
    ] = None,
) -> None:
    """Inspect a library recursively and write JSON and CSV reports."""
    configure_logging()
    _validate_output(input_root, output)
    try:
        report = scan_library(input_root, limit=limit)
    except (NotADirectoryError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--input") from exc
    paths = write_reports(report, output)
    console.print(
        f"Inspected [bold]{report.inspected_count}[/bold] of "
        f"[bold]{report.discovered_count}[/bold] discovered files."
    )
    for path in paths:
        console.print(path)


@app.command("inspect-document")
def inspect_document_command(
    document: Annotated[Path, typer.Argument(help="Document to inspect.")],
) -> None:
    """Inspect one document and emit its normalized JSON result."""
    configure_logging()
    if not document.is_file():
        raise typer.BadParameter("document does not exist or is not a file", param_hint="document")
    result = inspect_path(document, document.parent)
    console.print_json(json.dumps(result.model_dump(mode="json"), ensure_ascii=False))


def _source_root_for(document: Path) -> Path:
    library = Path("pdfsrc")
    try:
        document.resolve().relative_to(library.resolve())
    except ValueError:
        return document.parent
    return library


@app.command("parse-document")
def parse_document_command(
    document: Annotated[Path, typer.Argument(help="One PDF, PPTX, or DOCX source.")],
    output: Annotated[
        Path, typer.Option("--output", help="Root for content-addressed normalized output.")
    ] = Path("data/processed"),
    extract_assets: Annotated[
        bool, typer.Option("--extract-assets", help="Materialize supported embedded assets.")
    ] = False,
    render_previews: Annotated[
        bool, typer.Option("--render-previews", help="Render supported page previews.")
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Replace an existing successful result atomically.")
    ] = False,
    docling_artifacts_path: Annotated[
        Path | None,
        typer.Option(
            "--docling-artifacts-path",
            help="Local Docling model root; overrides DOCLING_ARTIFACTS_PATH for PDFs.",
        ),
    ] = None,
) -> None:
    """Parse and normalize exactly one supported source document."""
    configure_logging()
    source_root = _source_root_for(document)
    try:
        result = parse_document(
            document,
            source_root=source_root,
            output_root=output,
            extract_assets=extract_assets,
            render_previews=render_previews,
            force=force,
            docling_settings=DoclingSettings.from_sources(docling_artifacts_path),
        )
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as exc:
        error_console.print(f"[red]Parse failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"Normalized [bold]{result.document.source_relative_path}[/bold]")
    console.print(result.output_directory)


@app.command("check-environment")
def check_environment_command(
    docling_artifacts_path: Annotated[
        Path | None,
        typer.Option(
            "--docling-artifacts-path",
            help="Local Docling model root; overrides DOCLING_ARTIFACTS_PATH.",
        ),
    ] = None,
    output: Annotated[
        Path,
        typer.Option("--output", help="Prospective processed-output root to check."),
    ] = Path("data/processed"),
) -> None:
    """Check local PDF readiness without parsing or downloading."""
    settings = DoclingSettings.from_sources(docling_artifacts_path)
    report = check_environment(settings, output_root=output)
    for check in report.checks:
        marker = "OK" if check.ok else "FAIL"
        console.print(f"[{marker}] {check.name}: {check.detail}")
    for remediation in report.remediation:
        error_console.print(f"Remediation: {remediation}")
    if not report.ready:
        raise typer.Exit(code=1)


@app.command("check-ocr-environment")
def check_ocr_environment_command(
    languages: Annotated[
        str, typer.Option("--languages", help="Required Tesseract codes, e.g. fra+eng.")
    ],
    output: Annotated[
        Path, typer.Option("--output", help="Prospective derivative output root.")
    ] = Path("data/derived"),
) -> None:
    """Check local OCR tools and language packs without invoking OCR."""
    requested = _ocr_languages(languages)
    report = check_ocr_environment(requested, output)
    for name, value in (
        ("OCRmyPDF", report.ocrmypdf_version),
        ("Tesseract", report.tesseract_version),
        ("qpdf", report.qpdf_version),
        ("Ghostscript", report.ghostscript_version),
    ):
        console.print(f"{name}: {value or 'missing'}")
    console.print(f"installed_languages: {', '.join(report.installed_languages) or 'none'}")
    console.print(f"requested_languages: {', '.join(report.requested_languages)}")
    console.print(f"derivative_output_writable: {report.derivative_output_writable}")
    console.print(f"source_policy: {report.source_library_policy}")
    console.print(f"ocr_execution: {report.ocr_default_state}")
    if not report.ready:
        if report.missing_tools:
            error_console.print(f"Missing tools: {', '.join(report.missing_tools)}")
        if report.missing_languages:
            error_console.print(f"Missing languages: {', '.join(report.missing_languages)}")
        raise typer.Exit(code=1)


@app.command("evaluate-ocr")
def evaluate_ocr_command(
    document: Annotated[Path, typer.Argument(help="One source PDF to evaluate without OCR.")],
) -> None:
    """Evaluate deterministic OCR eligibility without creating output."""
    evaluation = evaluate_ocr(document, source_root=_source_root_for(document))
    for name, value in (
        ("eligibility", evaluation.eligibility.value),
        ("source_sha256", evaluation.source_sha256),
        ("source_relative_path", evaluation.source_relative_path),
        ("page_count", evaluation.page_count),
        ("total_extractable_characters", evaluation.total_extractable_characters),
        ("low_text_pages", evaluation.low_text_pages),
        ("image_heavy_pages", evaluation.image_heavy_pages),
        ("image_count", evaluation.image_count),
        ("reason", evaluation.reason),
        ("language_input_required", evaluation.language_input_required),
    ):
        console.print(f"{name}: {value}")


@app.command("create-ocr-derivative")
def create_ocr_derivative_command(
    document: Annotated[Path, typer.Argument(help="One original source PDF.")],
    languages: Annotated[
        str, typer.Option("--languages", help="Required Tesseract codes, e.g. fra+eng.")
    ],
    output: Annotated[Path, typer.Option("--output")] = Path("data/derived"),
    deskew: Annotated[bool, typer.Option("--deskew/--no-deskew")] = False,
    rotate_pages: Annotated[bool, typer.Option("--rotate-pages/--no-rotate-pages")] = False,
    clean: Annotated[bool, typer.Option("--clean/--no-clean")] = False,
    force_ocr: Annotated[bool, typer.Option("--force-ocr")] = False,
    skip_text: Annotated[bool, typer.Option("--skip-text/--no-skip-text")] = True,
    timeout_seconds: Annotated[int, typer.Option("--timeout-seconds", min=1)] = 300,
    jobs: Annotated[int, typer.Option("--jobs", min=1, max=4)] = 1,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Explicitly create and quality-check one local OCR PDF derivative."""
    try:
        configuration = OCRConfiguration(
            language_codes=_ocr_languages(languages),
            deskew=deskew,
            rotate_pages=rotate_pages,
            clean=clean,
            force_ocr=force_ocr,
            skip_text=skip_text,
            timeout_seconds=timeout_seconds,
            jobs=jobs,
        )
        result = create_ocr_derivative(
            document,
            configuration,
            output_root=output,
            source_root=_source_root_for(document),
            force=force,
        )
    except (FileExistsError, OCRExecutionError, OSError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]OCR derivative failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"derivative_id: {result.derivative.derivative_id}")
    console.print(f"quality: {result.derivative.validation_status.value}")
    console.print(f"output: {result.directory}")


@app.command("validate-derivative")
def validate_derivative_command(
    derivative_json: Annotated[Path, typer.Argument(help="Path to derivative.json.")],
) -> None:
    """Validate OCR files, hashes, page mapping, quality, and provenance."""
    try:
        derivative, report = validate_derivative_file(derivative_json)
    except (OSError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]Derivative validation failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"schema_version: {derivative.schema_version}")
    console.print(f"derivative_id: {derivative.derivative_id}")
    console.print(f"source_sha256: {derivative.source_sha256}")
    console.print(f"derivative_sha256: {derivative.derivative_sha256}")
    console.print(f"page_count: {derivative.page_count}")
    console.print(f"quality: {derivative.validation_status.value}")
    console.print(f"suitability: {report.suitability_status.value}")
    if derivative.validation_status not in {
        OCRQualityOutcome.ACCEPTED,
        OCRQualityOutcome.ACCEPTED_WITH_WARNINGS,
    }:
        raise typer.Exit(code=2)


@app.command("parse-ocr-derivative")
def parse_ocr_derivative_command(
    derivative_json: Annotated[Path, typer.Argument(help="Accepted derivative.json.")],
    output: Annotated[Path, typer.Option("--output")] = Path("data/processed"),
    docling_artifacts_path: Annotated[Path | None, typer.Option("--docling-artifacts-path")] = None,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Parse an accepted OCR derivative while retaining original source identity."""
    try:
        result = parse_ocr_derivative(
            derivative_json,
            output_root=output,
            docling_settings=DoclingSettings.from_sources(docling_artifacts_path),
            force=force,
        )
    except (FileExistsError, OSError, RuntimeError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]OCR derivative parse failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"document_id: {result.document.document_id}")
    console.print(f"output: {result.output_directory}")


@app.command("parse-sample")
def parse_sample_command(
    input_root: Annotated[
        Path,
        typer.Option("--input", help="Required source library root scanned recursively."),
    ],
    output: Annotated[
        Path, typer.Option("--output", help="Root for content-addressed normalized output.")
    ] = Path("data/processed"),
    limit: Annotated[
        int, typer.Option("--limit", min=1, help="Maximum representative documents.")
    ] = 3,
    allow_large_batch: Annotated[
        bool,
        typer.Option(
            "--allow-large-batch",
            help="Explicitly allow a limit greater than the safe default of 3.",
        ),
    ] = False,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Select and parse a small representative batch with failure isolation."""
    configure_logging()
    if limit > 3 and not allow_large_batch:
        error_console.print("[red]Limits greater than 3 require --allow-large-batch.[/red]")
        raise typer.Exit(code=2)
    _validate_output(input_root, output)
    try:
        selected = select_representative_documents(input_root, limit)
    except (NotADirectoryError, OSError, ValueError) as exc:
        error_console.print(f"[red]Selection failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print("Selected documents:")
    for path in selected:
        console.print(f"- {path.relative_to(input_root).as_posix()}")
    report = parse_sample(
        input_root=input_root,
        output_root=output,
        limit=limit,
        force=force,
        selected_paths=selected,
    )
    failed = sum(result.status.value == "failed" for result in report.results)
    console.print(f"Completed {len(report.results)} selected documents; {failed} failed.")
    if failed:
        raise typer.Exit(code=1)


@app.command("validate-output")
def validate_output_command(
    document_json: Annotated[Path, typer.Argument(help="Path to a canonical document.json file.")],
) -> None:
    """Validate canonical JSON and report navigation/content counts."""
    try:
        document = validate_document_file(document_json)
    except (OSError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]Validation failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    summary = validation_summary(document)
    for label, value in summary.items():
        console.print(f"{label}: {value}")


def _text_tree_extensions(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return tuple(sorted(SUPPORTED_TEXT_EXPORT_EXTENSIONS))
    extensions: list[str] = []
    for value in values:
        extensions.extend(item.strip() for item in value.split(",") if item.strip())
    return tuple(extensions)


@app.command("extract-text-tree")
def extract_text_tree_command(
    year: Annotated[str | None, typer.Option("--year", help="Year id from library.toml")] = None,
    input_root: Annotated[Path | None, typer.Option("--input")] = None,
    output: Annotated[Path | None, typer.Option("--output")] = None,
    report_output: Annotated[Path | None, typer.Option("--report-output")] = None,
    docling_artifacts: Annotated[Path | None, typer.Option("--docling-artifacts-path")] = None,
    resume: Annotated[bool, typer.Option("--resume")] = False,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
    extensions: Annotated[list[str] | None, typer.Option("--extensions")] = None,
    jobs: Annotated[int, typer.Option("--jobs", min=1)] = 1,
) -> None:
    """Export a read-only source tree to validated mirrored UTF-8 text files.

    With --year, paths default to library/<year> -> data/<year>/{text,reports/text-export,ocr}.
    """
    try:
        if year is not None:
            selected = get_year(year)
            input_root = input_root or selected.source
            output = output or selected.text
            report_output = report_output or selected.reports / "text-export"
            derived_root = selected.ocr
        elif input_root is None or output is None or report_output is None:
            raise typer.BadParameter("Pass --year, or all of --input, --output, --report-output.")
        else:
            derived_root = output.parent / "ocr"
        if docling_artifacts is None and DoclingSettings.from_sources().artifacts_path is None:
            docling_artifacts = docling_artifacts_path()
        configuration = TextExportConfiguration(
            input_root=input_root,
            output_root=output,
            report_output_root=report_output,
            docling_artifacts_path=docling_artifacts,
            derived_root=derived_root,
            resume=resume,
            overwrite=overwrite,
            dry_run=dry_run,
            limit=limit,
            extensions=_text_tree_extensions(extensions),
            jobs=jobs,
        )
        result = extract_text_tree(configuration)
        report = result.report
        console.print(f"run_id: {report.run_id}")
        console.print(f"discovered: {report.discovered_count}")
        console.print(f"supported: {report.supported_count}")
        console.print(f"planned: {report.planned_count}")
        console.print(f"exported: {report.exported_count}")
        console.print(f"exported_with_warnings: {report.exported_with_warnings_count}")
        console.print(f"skipped_current: {report.skipped_current_count}")
        console.print(f"requires_ocr: {report.requires_ocr_count}")
        console.print(f"unsupported: {report.unsupported_count}")
        console.print(f"empty: {report.empty_count}")
        console.print(f"failed: {report.failed_count}")
        console.print(f"proposed_text_outputs: {report.proposed_text_output_count}")
        console.print(f"collisions: {report.collision_count}")
        console.print(f"source_bytes: {report.total_source_bytes}")
        console.print(f"source_immutable: {str(report.source_immutable).lower()}")
        for entry in result.manifest.entries:
            if entry.export_status in {ExportStatus.REQUIRES_OCR, ExportStatus.UNSUPPORTED}:
                console.print(f"{entry.export_status.value}: {entry.source_relative_path}")
        for proposed, sources in result.collisions.items():
            console.print(f"collision: {proposed} <- {', '.join(sources)}")
        if dry_run:
            console.print("writes: none")
            console.print("docling_initialized: false")
        elif result.report_directory is not None:
            console.print(f"manifest: {configuration.output_root / 'export-manifest.json'}")
            console.print(f"reports: {result.report_directory}")
        if not report.source_immutable:
            raise typer.Exit(code=1)
    except (OSError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]Text-tree extraction failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc


if __name__ == "__main__":
    app()
