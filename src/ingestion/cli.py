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
from ingestion.courses.output import CourseOutputExistsError, write_course_artifacts
from ingestion.courses.service import (
    CourseError,
    build_course_catalog,
    build_course_qcm_plan,
    build_coverage_ledger,
    load_course_artifacts,
)
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
from ingestion.generation.config import generation_configuration
from ingestion.generation.export import export_question_bank
from ingestion.generation.models import (
    ContentType,
    GeneratedContentBatch,
    GenerationConfiguration,
    GenerationRequest,
    KnowledgeMode,
    ProviderKind,
    QCMType,
    ReviewStatus,
)
from ingestion.generation.providers.ollama import OllamaGenerationProvider
from ingestion.generation.review import review_content
from ingestion.generation.service import (
    GenerationError,
    GenerationFailure,
    build_generation_plan,
    generate_content,
)
from ingestion.generation.validation import validate_generated_content
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
from ingestion.preparation.models import LocationMarkerMode, PreparationConfiguration
from ingestion.preparation.service import prepare_course_text_tree
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


@app.command("build-course-catalog")
def build_course_catalog_command(
    dataset_json: Annotated[
        list[Path], typer.Argument(help="One or more explicit validated AI-ready datasets.")
    ],
    course_name: Annotated[str, typer.Option("--course-name")],
    course_root: Annotated[str | None, typer.Option("--course-root")] = None,
    output_root: Annotated[Path, typer.Option("--output-root")] = Path("data/courses"),
    generation_root: Annotated[Path, typer.Option("--generation-root")] = Path("data/generated"),
) -> None:
    """Build an immutable folder-aware course catalog and QCM coverage snapshot."""
    try:
        catalog, units = build_course_catalog(
            dataset_json,
            course_name=course_name,
            course_root=course_root,
        )
        ledger = build_coverage_ledger(units, generation_root=generation_root)
        output = write_course_artifacts(catalog, units, ledger, output_root=output_root)
        console.print(f"course_id: {catalog.course_id}")
        console.print(f"course_output: {output}")
        console.print(f"documents: {catalog.document_count}")
        console.print(f"knowledge_units: {catalog.knowledge_unit_count}")
        console.print(f"eligible_units: {catalog.eligible_unit_count}")
        console.print(f"excluded_units: {catalog.excluded_unit_count}")
        for status, count in sorted(ledger.status_counts.items(), key=lambda item: item[0].value):
            console.print(f"coverage_{status.value}: {count}")
    except (OSError, ValidationError, ValueError, CourseError, CourseOutputExistsError) as exc:
        error_console.print(f"[red]Course catalog construction failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("plan-course-qcm")
def plan_course_qcm_command(
    course_directory: Annotated[Path, typer.Argument(help="Finalized course artifact directory.")],
    count: Annotated[int, typer.Option("--count", min=1, max=100)] = 5,
    maximum_source_characters: Annotated[
        int, typer.Option("--max-source-characters", min=1)
    ] = 12000,
    maximum_source_tokens: Annotated[int, typer.Option("--max-source-tokens", min=1)] = 3000,
) -> None:
    """Plan QCM coverage from pending course units without writes or provider requests."""
    try:
        catalog, units, ledger = load_course_artifacts(course_directory)
        plan = build_course_qcm_plan(
            catalog,
            units,
            ledger,
            requested_count=count,
            maximum_source_characters=maximum_source_characters,
            maximum_source_tokens=maximum_source_tokens,
            proposed_plan_root=course_directory,
        )
        console.print(f"course_id: {catalog.course_id}")
        console.print(f"course_name: {catalog.course_name}")
        console.print(f"course_root: {catalog.course_root}")
        console.print(f"plan_id: {plan.plan_id}")
        console.print(f"requested_questions: {plan.requested_question_count}")
        console.print(f"planned_questions: {plan.planned_question_count}")
        console.print(f"eligible_units: {plan.eligible_unit_count}")
        console.print(f"pending_units: {plan.pending_unit_count}")
        console.print(f"already_attempted_units: {plan.already_attempted_unit_count}")
        console.print(f"excluded_units: {plan.excluded_unit_count}")
        console.print(f"selected_characters: {plan.selected_character_count}")
        console.print(f"selected_tokens: {plan.selected_token_estimate}")
        console.print(f"proposed_plan: {plan.proposed_plan_path}")
        for unit in plan.selected_units:
            console.print(f"selected_unit: {unit.unit_id}")
            console.print(f"  chunk_id: {unit.chunk_id}")
            console.print(f"  taxonomy: {' / '.join(unit.taxonomy_path)}")
            for reference in unit.source_references:
                console.print(
                    "  source_reference: "
                    + json.dumps(reference.model_dump(mode="json"), ensure_ascii=False)
                )
        console.print("provider_request: none")
        console.print("writes: none")
    except (OSError, ValidationError, ValueError, CourseError) as exc:
        error_console.print(f"[red]Course QCM planning failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc


def _generation_options(
    *,
    content_type: ContentType,
    qcm_type: QCMType,
    count: int,
    language: str,
    difficulty: str,
    knowledge_mode: KnowledgeMode,
    model: str | None,
    base_url: str | None,
    timeout: float | None,
    temperature: float | None,
    context_size: int | None,
    seed: int | None,
    maximum_output_tokens: int | None,
    retry_count: int | None,
    validation_retry_count: int | None,
    maximum_source_characters: int,
    maximum_source_tokens: int,
    topic: str | None,
) -> GenerationConfiguration:
    return generation_configuration(
        content_type=content_type,
        qcm_type=qcm_type,
        count=count,
        language=language,
        difficulty=difficulty,
        knowledge_mode=knowledge_mode,
        provider=ProviderKind.OLLAMA,
        model=model,
        base_url=base_url,
        timeout_seconds=timeout,
        temperature=temperature,
        context_size=context_size,
        seed=seed,
        maximum_output_tokens=maximum_output_tokens,
        retry_count=retry_count,
        validation_retry_count=validation_retry_count,
        maximum_source_characters=maximum_source_characters,
        maximum_source_tokens=maximum_source_tokens,
        topic=topic,
    )


def _show_generation_plan(plan: object) -> None:
    from ingestion.generation.service import GenerationPlan

    validated = plan if isinstance(plan, GenerationPlan) else None
    if validated is None:
        raise TypeError("Expected a generation plan.")
    request = validated.request
    console.print(f"generation_id: {request.generation_id}")
    console.print(f"dataset: {request.source.dataset_path}")
    console.print(f"content_type: {request.configuration.content_type.value}")
    console.print(f"requested_count: {request.configuration.count}")
    console.print(f"language: {request.configuration.language}")
    console.print(f"eligible_chunks: {request.source.eligible_chunk_count}")
    console.print(f"excluded_chunks: {request.source.ineligible_chunk_count}")
    console.print(f"selected_characters: {request.source.selected_character_count}")
    console.print(f"selected_tokens: {request.source.selected_token_estimate}")
    console.print(f"prompt_characters_estimate: {request.source.prompt_character_estimate}")
    console.print(f"prompt_tokens_estimate: {request.source.prompt_token_estimate}")
    console.print(f"model: {request.configuration.model}")
    console.print(f"endpoint: {request.configuration.base_url}")
    console.print(f"validation_retries: {request.configuration.validation_retry_count}")
    console.print(f"proposed_output: {validated.proposed_output_directory}")
    for chunk in request.source.selected_chunks:
        console.print(f"selected_chunk: {chunk.chunk_id}")
        for reference in chunk.source_references:
            console.print(
                "  source_reference: "
                + json.dumps(reference.model_dump(mode="json"), ensure_ascii=False)
            )


@app.command("plan-generation")
def plan_generation_command(
    dataset_json: Annotated[Path, typer.Argument(help="Explicit validated AI-ready dataset.")],
    content_type: Annotated[ContentType, typer.Option("--content-type")],
    count: Annotated[int, typer.Option("--count", min=1, max=100)],
    model: Annotated[str | None, typer.Option("--model")] = None,
    qcm_type: Annotated[QCMType, typer.Option("--qcm-type")] = QCMType.SINGLE_ANSWER,
    language: Annotated[str, typer.Option("--language")] = "fr",
    difficulty: Annotated[str, typer.Option("--difficulty")] = "mixed",
    knowledge_mode: Annotated[KnowledgeMode, typer.Option("--knowledge-mode")] = (
        KnowledgeMode.SOURCE_ONLY
    ),
    base_url: Annotated[str | None, typer.Option("--base-url")] = None,
    timeout: Annotated[float | None, typer.Option("--timeout", min=0.1)] = None,
    temperature: Annotated[float | None, typer.Option("--temperature", min=0, max=2)] = None,
    context_size: Annotated[int | None, typer.Option("--context-size", min=1)] = None,
    seed: Annotated[int | None, typer.Option("--seed")] = None,
    maximum_output_tokens: Annotated[int | None, typer.Option("--max-output-tokens", min=1)] = None,
    retry_count: Annotated[int | None, typer.Option("--retry-count", min=0, max=10)] = None,
    validation_retry_count: Annotated[
        int | None, typer.Option("--validation-retry-count", min=0, max=10)
    ] = None,
    maximum_source_characters: Annotated[
        int, typer.Option("--max-source-characters", min=1)
    ] = 12000,
    maximum_source_tokens: Annotated[int, typer.Option("--max-source-tokens", min=1)] = 3000,
    topic: Annotated[str | None, typer.Option("--topic")] = None,
) -> None:
    """Validate and display a read-only QCM plan without contacting Ollama."""
    try:
        configuration = _generation_options(
            content_type=content_type,
            qcm_type=qcm_type,
            count=count,
            language=language,
            difficulty=difficulty,
            knowledge_mode=knowledge_mode,
            model=model,
            base_url=base_url,
            timeout=timeout,
            temperature=temperature,
            context_size=context_size,
            seed=seed,
            maximum_output_tokens=maximum_output_tokens,
            retry_count=retry_count,
            validation_retry_count=validation_retry_count,
            maximum_source_characters=maximum_source_characters,
            maximum_source_tokens=maximum_source_tokens,
            topic=topic,
        )
        plan = build_generation_plan(dataset_json, configuration)
        _show_generation_plan(plan)
        console.print("provider_request: none")
        console.print("writes: none")
    except (OSError, ValidationError, ValueError, GenerationError) as exc:
        error_console.print(f"[red]Generation planning failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("generate-content")
def generate_content_command(
    dataset_json: Annotated[Path, typer.Argument(help="Explicit validated AI-ready dataset.")],
    content_type: Annotated[ContentType, typer.Option("--content-type")],
    count: Annotated[int, typer.Option("--count", min=1, max=100)],
    model: Annotated[str | None, typer.Option("--model")] = None,
    qcm_type: Annotated[QCMType, typer.Option("--qcm-type")] = QCMType.SINGLE_ANSWER,
    language: Annotated[str, typer.Option("--language")] = "fr",
    difficulty: Annotated[str, typer.Option("--difficulty")] = "mixed",
    knowledge_mode: Annotated[KnowledgeMode, typer.Option("--knowledge-mode")] = (
        KnowledgeMode.SOURCE_ONLY
    ),
    base_url: Annotated[str | None, typer.Option("--base-url")] = None,
    timeout: Annotated[float | None, typer.Option("--timeout", min=0.1)] = None,
    temperature: Annotated[float | None, typer.Option("--temperature", min=0, max=2)] = None,
    context_size: Annotated[int | None, typer.Option("--context-size", min=1)] = None,
    seed: Annotated[int | None, typer.Option("--seed")] = None,
    maximum_output_tokens: Annotated[int | None, typer.Option("--max-output-tokens", min=1)] = None,
    retry_count: Annotated[int | None, typer.Option("--retry-count", min=0, max=10)] = None,
    validation_retry_count: Annotated[
        int | None, typer.Option("--validation-retry-count", min=0, max=10)
    ] = None,
    maximum_source_characters: Annotated[
        int, typer.Option("--max-source-characters", min=1)
    ] = 12000,
    maximum_source_tokens: Annotated[int, typer.Option("--max-source-tokens", min=1)] = 3000,
    topic: Annotated[str | None, typer.Option("--topic")] = None,
    output_root: Annotated[Path, typer.Option("--output-root")] = Path("data/generated"),
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Generate local Ollama QCM drafts after a deterministic source plan."""
    try:
        configuration = _generation_options(
            content_type=content_type,
            qcm_type=qcm_type,
            count=count,
            language=language,
            difficulty=difficulty,
            knowledge_mode=knowledge_mode,
            model=model,
            base_url=base_url,
            timeout=timeout,
            temperature=temperature,
            context_size=context_size,
            seed=seed,
            maximum_output_tokens=maximum_output_tokens,
            retry_count=retry_count,
            validation_retry_count=validation_retry_count,
            maximum_source_characters=maximum_source_characters,
            maximum_source_tokens=maximum_source_tokens,
            topic=topic,
        )
        if dry_run:
            plan = build_generation_plan(dataset_json, configuration, output_root=output_root)
            _show_generation_plan(plan)
            console.print("provider_request: none")
            console.print("writes: none")
            return
        result = generate_content(
            dataset_json,
            configuration,
            OllamaGenerationProvider(),
            output_root=output_root,
        )
        console.print(f"generation_output: {result.output_directory}")
        console.print(f"validation_status: {result.validation_report.status.value}")
    except GenerationFailure as exc:
        error_console.print(f"[red]Content generation failed:[/red] {exc}")
        error_console.print(f"failed_attempt: {exc.failure_directory}")
        error_console.print("validation_issue_codes: " + (", ".join(exc.issue_codes) or "none"))
        raise typer.Exit(code=1) from exc
    except (OSError, ValidationError, ValueError, GenerationError) as exc:
        error_console.print(f"[red]Content generation failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("validate-generation")
def validate_generation_command(
    generation_directory: Annotated[Path, typer.Argument()],
) -> None:
    """Revalidate a generated batch against its explicitly recorded dataset."""
    try:
        request = GenerationRequest.model_validate_json(
            (generation_directory / "request.json").read_text(encoding="utf-8")
        )
        batch = GeneratedContentBatch.model_validate_json(
            (generation_directory / "generated-content.json").read_text(encoding="utf-8")
        )
        dataset_path = Path(request.source.dataset_path)
        expected_plan = build_generation_plan(dataset_path, request.configuration)
        if expected_plan.request.generation_id != request.generation_id:
            raise ValueError("Recorded generation request no longer matches its dataset.")
        if expected_plan.request.source != request.source:
            raise ValueError("Recorded source selection no longer matches its dataset.")
        if expected_plan.request.prompt_sha256 != request.prompt_sha256:
            raise ValueError("Recorded prompt identity no longer matches its source selection.")
        grounding, validation = validate_generated_content(batch, request, expected_plan.dataset)
        console.print(f"grounding_status: {grounding.status.value}")
        console.print(f"validation_status: {validation.status.value}")
        console.print(f"issues: {validation.issue_count}")
        if validation.status.value == "failed":
            raise typer.Exit(code=1)
    except (OSError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]Generation validation failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("review-content")
def review_content_command(
    generation_directory: Annotated[Path, typer.Argument()],
    decision: Annotated[ReviewStatus, typer.Option("--decision")],
    reviewer: Annotated[str, typer.Option("--reviewer")],
    notes: Annotated[str | None, typer.Option("--notes")] = None,
    question_id: Annotated[str | None, typer.Option("--question-id")] = None,
) -> None:
    """Record one explicit terminal human review decision atomically."""
    try:
        reviewed = review_content(
            generation_directory,
            decision=decision,
            reviewer=reviewer,
            notes=notes,
            question_id=question_id,
        )
        console.print(f"reviewed_generation: {reviewed.generation_id}")
    except (OSError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]Content review failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("export-question-bank")
def export_question_bank_command(
    generation_directories: Annotated[list[Path], typer.Argument()],
    output: Annotated[Path, typer.Option("--output")],
) -> None:
    """Export only human-accepted QCM questions to a protected JSON file."""
    try:
        count = export_question_bank(generation_directories, output)
        console.print(f"accepted_questions_exported: {count}")
        console.print(f"output: {output}")
    except (OSError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]Question-bank export failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc


def _text_tree_extensions(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return tuple(sorted(SUPPORTED_TEXT_EXPORT_EXTENSIONS))
    extensions: list[str] = []
    for value in values:
        extensions.extend(item.strip() for item in value.split(",") if item.strip())
    return tuple(extensions)


@app.command("extract-text-tree")
def extract_text_tree_command(
    input_root: Annotated[Path, typer.Option("--input")] = Path("yahyaouisalsa"),
    output: Annotated[Path, typer.Option("--output")] = Path("data/yahyaouisalsa-text"),
    report_output: Annotated[Path, typer.Option("--report-output")] = Path(
        "data/reports/yahyaouisalsa-text"
    ),
    docling_artifacts_path: Annotated[Path | None, typer.Option("--docling-artifacts-path")] = None,
    resume: Annotated[bool, typer.Option("--resume")] = False,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
    extensions: Annotated[list[str] | None, typer.Option("--extensions")] = None,
    jobs: Annotated[int, typer.Option("--jobs", min=1)] = 1,
) -> None:
    """Export a read-only source tree to validated mirrored UTF-8 text files."""
    try:
        configuration = TextExportConfiguration(
            input_root=input_root,
            output_root=output,
            report_output_root=report_output,
            docling_artifacts_path=docling_artifacts_path,
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


@app.command("prepare-course-text-tree")
def prepare_course_text_tree_command(
    input_root: Annotated[Path, typer.Option("--input")] = Path("data/yahyaouisalsa-text"),
    clean_output: Annotated[Path, typer.Option("--clean-output")] = Path(
        "data/yahyaouisalsa-clean"
    ),
    reconstructed_output: Annotated[Path, typer.Option("--reconstructed-output")] = Path(
        "data/yahyaouisalsa-reconstructed"
    ),
    report_output: Annotated[Path, typer.Option("--report-output")] = Path(
        "data/reports/yahyaouisalsa-preparation"
    ),
    selected_file: Annotated[Path | None, typer.Option("--file")] = None,
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    resume: Annotated[bool, typer.Option("--resume")] = False,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
    generator_model: Annotated[str, typer.Option("--generator-model")] = "gemma3:12b",
    reviewer_model: Annotated[str | None, typer.Option("--reviewer-model")] = "auto-medgemma-4b",
    disable_model_reconstruction: Annotated[
        bool, typer.Option("--disable-model-reconstruction")
    ] = False,
    disable_medgemma_review: Annotated[bool, typer.Option("--disable-medgemma-review")] = False,
    location_markers: Annotated[
        LocationMarkerMode, typer.Option("--location-markers")
    ] = LocationMarkerMode.COMPACT,
    context_budget: Annotated[int, typer.Option("--context-budget", min=4096, max=32768)] = 8192,
    temperature: Annotated[float, typer.Option("--temperature", min=0.0, max=2.0)] = 0.0,
    seed: Annotated[int, typer.Option("--seed")] = 42,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 300.0,
    max_retries: Annotated[int, typer.Option("--max-retries", min=0, max=10)] = 2,
    jobs: Annotated[int, typer.Option("--jobs", min=1)] = 1,
) -> None:
    """Clean and reconstruct mirrored course text without generating study material."""
    try:
        configuration = PreparationConfiguration(
            input_root=input_root,
            clean_output_root=clean_output,
            reconstructed_output_root=reconstructed_output,
            report_output_root=report_output,
            file=selected_file,
            limit=limit,
            dry_run=dry_run,
            resume=resume,
            overwrite=overwrite,
            generator_model=generator_model,
            reviewer_model=reviewer_model,
            disable_model_reconstruction=disable_model_reconstruction,
            disable_medgemma_review=disable_medgemma_review,
            location_markers=location_markers,
            context_budget=context_budget,
            temperature=temperature,
            seed=seed,
            timeout_seconds=timeout,
            maximum_retries=max_retries,
            jobs=jobs,
        )
        result = prepare_course_text_tree(configuration)
        report = result.report
        console.print(f"run_id: {report.run_id}")
        console.print(f"raw_text_files: {report.total_raw_text_files}")
        console.print(f"cleaned_files: {report.total_cleaned_files}")
        console.print(f"reconstructed_files: {report.total_reconstructed_files}")
        for status, count in sorted(report.readiness_counts.items()):
            console.print(f"readiness_{status}: {count}")
        for status, count in sorted(report.status_counts.items()):
            console.print(f"status_{status}: {count}")
        console.print(f"source_immutable: {str(report.source_immutable).lower()}")
        console.print("study_material_generated: false")
        if dry_run:
            console.print("writes: none")
            console.print("model_inference: false")
        else:
            console.print(f"clean_manifest: {clean_output / 'cleaning-manifest.json'}")
            console.print(
                f"reconstruction_manifest: {reconstructed_output / 'reconstruction-manifest.json'}"
            )
            console.print(f"reports: {result.report_directory}")
        if not report.source_immutable:
            raise typer.Exit(code=1)
    except (OSError, ValidationError, ValueError) as exc:
        error_console.print(f"[red]Course-text preparation failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc


if __name__ == "__main__":
    app()
