"""Typer commands for local document inspection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from ingestion.batch.executor import execute_batch
from ingestion.batch.models import BatchConfiguration, SelectionMode
from ingestion.batch.planner import build_batch_plan
from ingestion.batch.state import persist_plan
from ingestion.chunking.builder import build_chunk_collection
from ingestion.chunking.models import ChunkingConfiguration
from ingestion.chunking.validation import (
    chunk_validation_summary,
    validate_chunk_collection_file,
)
from ingestion.config import DoclingSettings
from ingestion.datasets.builder import build_ai_ready_dataset
from ingestion.datasets.output import (
    write_chunk_outputs,
    write_dataset_output,
)
from ingestion.datasets.validation import (
    dataset_validation_summary,
    validate_dataset_file,
)
from ingestion.doctor import check_environment
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


def _batch_configuration(
    *,
    input_root: Path,
    output: Path,
    derived_output: Path,
    reports_output: Path,
    limit: int | None,
    jobs: int,
    resume: bool,
    retry_failures: bool,
    maximum_retries: int,
    dry_run: bool,
    force: bool,
    enable_ocr: bool,
    ocr_languages: str | None,
    allow_force_ocr: bool,
    manifest: Path | None,
    include_extension: list[str],
    exclude_pattern: list[str],
    max_file_size: int | None,
    continue_on_error: bool,
    allow_full_library: bool,
    allow_large_batch: bool,
    parser_timeout: int,
    ocr_timeout: int,
    selection: SelectionMode,
) -> BatchConfiguration:
    languages = _ocr_languages(ocr_languages) if ocr_languages is not None else []
    return BatchConfiguration(
        input_root=input_root,
        output_root=output,
        derived_output_root=derived_output,
        reports_root=reports_output,
        limit=limit,
        jobs=jobs,
        resume=resume,
        retry_failures=retry_failures,
        maximum_retries=maximum_retries,
        dry_run=dry_run,
        force_rebuild=force,
        ocr_enabled=enable_ocr,
        ocr_languages=languages,
        allow_force_ocr=allow_force_ocr,
        manifest_path=manifest,
        include_extensions=include_extension,
        exclude_patterns=exclude_pattern,
        maximum_source_file_size=max_file_size,
        continue_on_error=continue_on_error,
        allow_full_library=allow_full_library,
        allow_large_batch=allow_large_batch,
        parser_timeout_seconds=parser_timeout,
        ocr_timeout_seconds=ocr_timeout,
        selection=selection,
    )


def _print_batch_plan(plan: object) -> None:
    from ingestion.batch.models import BatchPlan

    validated = BatchPlan.model_validate(plan)
    console.print(f"batch_id: {validated.batch_id}")
    console.print(f"selected: {validated.selected_document_count}")
    console.print(f"source_bytes: {sum(item.file_size for item in validated.documents)}")
    for item in validated.documents:
        actions = ",".join(item.planned_actions)
        console.print(
            f"{item.sequence_number:02d} {item.source_relative_path} | "
            f"{item.extension or '(none)'} | {item.inspection_classification} | "
            f"route={item.parser_route.value} | ocr={item.ocr_route.value} | "
            f"skip={item.skip_reason or '-'} | actions={actions}"
        )


@app.command("plan-library")
def plan_library_command(
    input_root: Annotated[Path, typer.Option("--input")] = Path("pdfsrc"),
    output: Annotated[Path, typer.Option("--output")] = Path("data/processed"),
    derived_output: Annotated[Path, typer.Option("--derived-output")] = Path("data/derived"),
    reports_output: Annotated[Path, typer.Option("--reports-output")] = Path(
        "data/reports/batches"
    ),
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
    selection: Annotated[SelectionMode, typer.Option("--selection")] = SelectionMode.ORDERED,
    enable_ocr: Annotated[bool, typer.Option("--enable-ocr")] = False,
    ocr_languages: Annotated[str | None, typer.Option("--ocr-languages")] = None,
    allow_force_ocr: Annotated[bool, typer.Option("--allow-force-ocr")] = False,
    manifest: Annotated[Path | None, typer.Option("--manifest")] = None,
    include_extension: Annotated[list[str] | None, typer.Option("--include-extension")] = None,
    exclude_pattern: Annotated[list[str] | None, typer.Option("--exclude-pattern")] = None,
    max_file_size: Annotated[int | None, typer.Option("--max-file-size", min=1)] = None,
    allow_full_library: Annotated[bool, typer.Option("--allow-full-library")] = False,
    allow_large_batch: Annotated[bool, typer.Option("--allow-large-batch")] = False,
    parser_timeout: Annotated[int, typer.Option("--parser-timeout", min=1)] = 900,
    ocr_timeout: Annotated[int, typer.Option("--ocr-timeout", min=1)] = 300,
    write_plan: Annotated[bool, typer.Option("--write-plan")] = False,
) -> None:
    """Build a deterministic plan without parsing or invoking OCR."""
    try:
        configuration = _batch_configuration(
            input_root=input_root,
            output=output,
            derived_output=derived_output,
            reports_output=reports_output,
            limit=limit,
            jobs=1,
            resume=True,
            retry_failures=False,
            maximum_retries=1,
            dry_run=True,
            force=False,
            enable_ocr=enable_ocr,
            ocr_languages=ocr_languages,
            allow_force_ocr=allow_force_ocr,
            manifest=manifest,
            include_extension=include_extension or [],
            exclude_pattern=exclude_pattern or [],
            max_file_size=max_file_size,
            continue_on_error=True,
            allow_full_library=allow_full_library,
            allow_large_batch=allow_large_batch,
            parser_timeout=parser_timeout,
            ocr_timeout=ocr_timeout,
            selection=selection,
        )
        plan = build_batch_plan(configuration)
        _print_batch_plan(plan)
        if write_plan:
            console.print(f"plan_path: {persist_plan(plan)}")
    except (OSError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]Batch planning failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc


@app.command("process-library")
def process_library_command(
    input_root: Annotated[Path, typer.Option("--input")] = Path("pdfsrc"),
    output: Annotated[Path, typer.Option("--output")] = Path("data/processed"),
    derived_output: Annotated[Path, typer.Option("--derived-output")] = Path("data/derived"),
    reports_output: Annotated[Path, typer.Option("--reports-output")] = Path(
        "data/reports/batches"
    ),
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
    jobs: Annotated[int, typer.Option("--jobs", min=1)] = 1,
    resume: Annotated[bool, typer.Option("--resume/--no-resume")] = True,
    retry_failures: Annotated[bool, typer.Option("--retry-failures")] = False,
    maximum_retries: Annotated[int, typer.Option("--maximum-retries", min=0)] = 1,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    force: Annotated[bool, typer.Option("--force")] = False,
    enable_ocr: Annotated[bool, typer.Option("--enable-ocr")] = False,
    ocr_languages: Annotated[str | None, typer.Option("--ocr-languages")] = None,
    allow_force_ocr: Annotated[bool, typer.Option("--allow-force-ocr")] = False,
    manifest: Annotated[Path | None, typer.Option("--manifest")] = None,
    include_extension: Annotated[list[str] | None, typer.Option("--include-extension")] = None,
    exclude_pattern: Annotated[list[str] | None, typer.Option("--exclude-pattern")] = None,
    max_file_size: Annotated[int | None, typer.Option("--max-file-size", min=1)] = None,
    continue_on_error: Annotated[bool, typer.Option("--continue-on-error/--stop-on-error")] = True,
    allow_full_library: Annotated[bool, typer.Option("--allow-full-library")] = False,
    allow_large_batch: Annotated[bool, typer.Option("--allow-large-batch")] = False,
    parser_timeout: Annotated[int, typer.Option("--parser-timeout", min=1)] = 900,
    ocr_timeout: Annotated[int, typer.Option("--ocr-timeout", min=1)] = 300,
    selection: Annotated[SelectionMode, typer.Option("--selection")] = SelectionMode.ORDERED,
) -> None:
    """Execute or dry-run one controlled sequential batch."""
    try:
        configuration = _batch_configuration(
            input_root=input_root,
            output=output,
            derived_output=derived_output,
            reports_output=reports_output,
            limit=limit,
            jobs=jobs,
            resume=resume,
            retry_failures=retry_failures,
            maximum_retries=maximum_retries,
            dry_run=dry_run,
            force=force,
            enable_ocr=enable_ocr,
            ocr_languages=ocr_languages,
            allow_force_ocr=allow_force_ocr,
            manifest=manifest,
            include_extension=include_extension or [],
            exclude_pattern=exclude_pattern or [],
            max_file_size=max_file_size,
            continue_on_error=continue_on_error,
            allow_full_library=allow_full_library,
            allow_large_batch=allow_large_batch,
            parser_timeout=parser_timeout,
            ocr_timeout=ocr_timeout,
            selection=selection,
        )
        plan = build_batch_plan(configuration)
        _print_batch_plan(plan)
        report = execute_batch(plan, persist=not dry_run)
    except (OSError, RuntimeError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]Batch processing failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    console.print(
        f"complete={report.complete_count} warnings={report.complete_with_warnings_count} "
        f"requires_ocr={report.requires_ocr_count} unsupported={report.unsupported_count} "
        f"failed={report.failed_count}"
    )
    if report.failed_count:
        raise typer.Exit(code=1)


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


def _chunking_configuration(
    target_characters: int,
    soft_max_characters: int,
    hard_max_characters: int,
    minimum_characters: int,
) -> ChunkingConfiguration:
    return ChunkingConfiguration(
        target_characters=target_characters,
        soft_max_characters=soft_max_characters,
        hard_max_characters=hard_max_characters,
        minimum_characters=minimum_characters,
    )


@app.command("build-chunks")
def build_chunks_command(
    document_json: Annotated[Path, typer.Argument(help="Validated canonical document.json input.")],
    target_characters: Annotated[int, typer.Option("--target-characters", min=1)] = 4000,
    soft_max_characters: Annotated[int, typer.Option("--soft-max-characters", min=1)] = 6000,
    hard_max_characters: Annotated[int, typer.Option("--hard-max-characters", min=1)] = 10000,
    minimum_characters: Annotated[int, typer.Option("--minimum-characters", min=0)] = 250,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Build deterministic chunks from canonical JSON only."""
    try:
        document = validate_document_file(document_json)
        configuration = _chunking_configuration(
            target_characters,
            soft_max_characters,
            hard_max_characters,
            minimum_characters,
        )
        collection = build_chunk_collection(document, configuration)
        output = write_chunk_outputs(document_json, collection, force=force)
    except (OSError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]Chunk build failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"Built [bold]{collection.chunk_count}[/bold] chunks in {output}")
    console.print(f"Warnings: {len(collection.warnings)}")


@app.command("build-dataset")
def build_dataset_command(
    document_json: Annotated[Path, typer.Argument(help="Validated canonical document.json input.")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Build an AI-ready dataset without invoking parsers or models."""
    try:
        document = validate_document_file(document_json)
        chunks_path = document_json.parent / "chunks" / "chunks.json"
        if chunks_path.is_file():
            try:
                collection = validate_chunk_collection_file(chunks_path)
            except (OSError, ValidationError, ValueError):
                if not force:
                    raise
                collection = build_chunk_collection(document)
                write_chunk_outputs(document_json, collection, force=True)
        else:
            if chunks_path.parent.exists() and not force:
                raise ValueError(
                    "Existing chunk directory is incomplete; use --force to rebuild it."
                )
            collection = build_chunk_collection(document)
            write_chunk_outputs(document_json, collection, force=force)
        if collection.document_id != document.document_id:
            raise ValueError("Existing chunks belong to another canonical document.")
        dataset = build_ai_ready_dataset(document, collection)
        output = write_dataset_output(document_json, dataset, force=force)
    except (OSError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]Dataset build failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"Built dataset with [bold]{dataset.chunk_count}[/bold] chunks in {output}")


@app.command("validate-chunks")
def validate_chunks_command(
    chunks_json: Annotated[Path, typer.Argument(help="Path to chunks/chunks.json.")],
) -> None:
    """Validate a chunk collection and report structural coverage."""
    try:
        collection = validate_chunk_collection_file(chunks_json)
    except (OSError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]Chunk validation failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    for label, value in chunk_validation_summary(collection).items():
        console.print(f"{label}: {value}")


@app.command("inspect-chunk")
def inspect_chunk_command(
    chunks_json: Annotated[Path, typer.Argument(help="Path to chunks/chunks.json.")],
    chunk_id: Annotated[str, typer.Argument(help="Deterministic chunk ID to review.")],
) -> None:
    """Display one source-grounded chunk for manual quality review."""
    try:
        collection = validate_chunk_collection_file(chunks_json)
        chunk = next(value for value in collection.chunks if value.chunk_id == chunk_id)
    except StopIteration as exc:
        error_console.print(f"[red]Chunk not found:[/red] {chunk_id}")
        raise typer.Exit(code=1) from exc
    except (OSError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]Chunk inspection failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"chunk_id: {chunk.chunk_id}")
    console.print(f"chunk_type: {chunk.chunk_type.value}")
    console.print(f"document_title: {chunk.document_title}")
    console.print(f"section_path: {' > '.join(chunk.section_path) or None}")
    console.print(
        f"location: {chunk.location_type.value} "
        f"{chunk.page_or_slide_start}-{chunk.page_or_slide_end}"
    )
    console.print(f"preceding_context: {chunk.preceding_context}")
    console.print(f"following_context: {chunk.following_context}")
    console.print(f"block_ids: {', '.join(chunk.block_ids)}")
    console.print(f"table_ids: {', '.join(chunk.table_ids)}")
    console.print(f"asset_ids: {', '.join(chunk.asset_ids)}")
    console.print(f"warnings: {'; '.join(chunk.warnings)}")
    console.print(f"metadata: {json.dumps(chunk.metadata, ensure_ascii=False)}")
    console.print("source_references:")
    console.print_json(
        json.dumps(
            [reference.model_dump(mode="json") for reference in chunk.source_references],
            ensure_ascii=False,
        )
    )
    console.print("text:")
    console.print(chunk.text)


@app.command("validate-dataset")
def validate_dataset_command(
    dataset_json: Annotated[Path, typer.Argument(help="Path to datasets/ai-ready-dataset.json.")],
) -> None:
    """Validate an AI-ready dataset and report source-grounding counts."""
    try:
        dataset = validate_dataset_file(dataset_json)
    except (OSError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]Dataset validation failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    for label, value in dataset_validation_summary(dataset).items():
        console.print(f"{label}: {value}")


if __name__ == "__main__":
    app()
