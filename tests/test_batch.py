from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import fitz
import pytest
from typer.testing import CliRunner

from ingestion.batch.executor import _preflight, execute_batch
from ingestion.batch.models import (
    BatchConfiguration,
    BatchDocumentStatus,
    BatchStage,
    OCRRoute,
    ParserRoute,
    SelectionMode,
)
from ingestion.batch.planner import build_batch_plan
from ingestion.batch.resume import should_execute
from ingestion.batch.router import ocr_route, parser_route
from ingestion.batch.state import initial_state, load_or_initialize_state, persist_state
from ingestion.batch.validation import inspect_existing_outputs
from ingestion.chunking.builder import build_chunk_collection
from ingestion.cli import app
from ingestion.datasets.builder import build_ai_ready_dataset
from ingestion.datasets.output import write_chunk_outputs, write_dataset_output
from ingestion.hashing import sha256_file
from ingestion.models import LibraryReport
from ingestion.normalization.models import BlockType, DocumentType, LocationType
from ingestion.scanner import inspect_library
from tests.test_chunking import block, document

runner = CliRunner()


def configuration(root: Path, **overrides: Any) -> BatchConfiguration:
    values: dict[str, Any] = {
        "input_root": root,
        "output_root": root.parent / "processed",
        "derived_output_root": root.parent / "derived",
        "reports_root": root.parent / "reports",
        "limit": 10,
    }
    values.update(overrides)
    return BatchConfiguration(**values)


def make_pdf(path: Path, *, text: str = "native text", image: bool = False) -> None:
    pdf = fitz.open()
    page = pdf.new_page()
    if text:
        page.insert_text((20, 30), text)
    if image:
        pixmap = fitz.Pixmap(fitz.csRGB, (0, 0, 4, 4), False)
        pixmap.clear_with(255)
        page.insert_image(fitz.Rect(40, 40, 80, 80), stream=pixmap.tobytes("png"))
    pdf.save(path)
    pdf.close()


def make_library(tmp_path: Path) -> Path:
    root = tmp_path / "library"
    root.mkdir()
    (root / "z.docx").write_bytes(b"docx")
    (root / "c.pptx").write_bytes(b"pptx")
    (root / "unsupported.txt").write_text("plain", encoding="utf-8")
    make_pdf(root / "a-native.pdf", text="native text")
    make_pdf(root / "b-mixed.pdf", text="small", image=True)
    make_pdf(root / "d-scanned.pdf", text="", image=True)
    return root


def make_complete_output(root: Path, output: Path, relative: str) -> str:
    source = root / relative
    digest = sha256_file(source)
    canonical = document([[block("b1", BlockType.PARAGRAPH, "grounded text", 0)]])
    canonical.document_id = digest
    canonical.sha256 = digest
    canonical.source_relative_path = relative
    canonical.source_filename = source.name
    canonical.source_extension = source.suffix
    canonical.metadata["extraction_quality"] = {"technical_suitability": "ready_for_chunking"}
    for page in canonical.pages:
        for item in page.blocks:
            item.source_reference.source_relative_path = relative
    directory = output / digest
    directory.mkdir(parents=True)
    canonical_path = directory / "document.json"
    canonical_path.write_text(canonical.model_dump_json(indent=2), encoding="utf-8")
    collection = build_chunk_collection(canonical)
    write_chunk_outputs(canonical_path, collection)
    dataset = build_ai_ready_dataset(canonical, collection)
    write_dataset_output(canonical_path, dataset)
    return digest


def test_configuration_enforces_limits_jobs_and_ocr_languages(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    with pytest.raises(ValueError, match="only --jobs 1"):
        configuration(root, jobs=2)
    with pytest.raises(ValueError, match="--allow-full-library"):
        configuration(root, limit=None)
    with pytest.raises(ValueError, match="--allow-large-batch"):
        configuration(root, limit=11)
    with pytest.raises(ValueError, match="--ocr-languages"):
        configuration(root, ocr_enabled=True)


def test_planning_is_deterministic_and_ordered(tmp_path: Path) -> None:
    root = make_library(tmp_path)
    config = configuration(root, limit=3)
    first = build_batch_plan(config)
    second = build_batch_plan(config)
    assert first.batch_id == second.batch_id
    assert first.deterministic_document_order == second.deterministic_document_order
    assert first.deterministic_document_order == sorted(
        first.deterministic_document_order, key=str.casefold
    )
    assert [item.sequence_number for item in first.documents] == [1, 2, 3]


def test_representative_selection_is_deterministic(tmp_path: Path) -> None:
    root = make_library(tmp_path)
    plan = build_batch_plan(configuration(root, limit=6, selection=SelectionMode.REPRESENTATIVE))
    assert [item.extension for item in plan.documents] == [
        ".pdf",
        ".pdf",
        ".pptx",
        ".docx",
        ".pdf",
        ".txt",
    ]
    assert plan.documents[-1].parser_route is ParserRoute.UNSUPPORTED


def test_filters_and_maximum_size(tmp_path: Path) -> None:
    root = make_library(tmp_path)
    plan = build_batch_plan(
        configuration(
            root,
            include_extensions=["pdf"],
            exclude_patterns=["*mixed*"],
            maximum_source_file_size=100_000,
        )
    )
    assert all(item.extension == ".pdf" for item in plan.documents)
    assert all("mixed" not in item.source_relative_path for item in plan.documents)


def test_manifest_is_reused_and_stale_entry_is_reinspected(tmp_path: Path) -> None:
    root = make_library(tmp_path)
    report = inspect_library(root)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    current = build_batch_plan(configuration(root, manifest_path=manifest))
    assert not any("Stale manifest" in warning for warning in current.warnings)
    (root / "z.docx").write_bytes(b"changed")
    stale = build_batch_plan(configuration(root, manifest_path=manifest))
    assert any("Stale manifest entry" in warning for warning in stale.warnings)


def test_manifest_root_mismatch_falls_back_to_live_inspection(tmp_path: Path) -> None:
    root = make_library(tmp_path)
    report = inspect_library(root)
    payload = report.model_dump(mode="json")
    payload["input_root"] = str(tmp_path / "elsewhere")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    plan = build_batch_plan(configuration(root, manifest_path=manifest))
    assert any("does not match" in warning for warning in plan.warnings)


def test_existing_complete_output_is_validated_and_skipped(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    source = root / "lesson.pptx"
    source.write_bytes(b"pptx")
    config = configuration(root, output_root=tmp_path / "processed", limit=1)
    digest = make_complete_output(root, config.output_root, source.name)
    state = inspect_existing_outputs(
        output_root=config.output_root,
        source_sha256=digest,
        source_relative_path=source.name,
    )
    assert state.complete is True
    assert state.last_valid_stage is BatchStage.COMPLETE
    plan = build_batch_plan(config)
    assert plan.documents[0].skip_reason == "already_complete"


def test_partial_and_invalid_outputs_resume_from_nearest_valid_stage(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    source = root / "lesson.pptx"
    source.write_bytes(b"pptx")
    output = tmp_path / "processed"
    digest = make_complete_output(root, output, source.name)
    dataset = output / digest / "datasets" / "ai-ready-dataset.json"
    dataset.unlink()
    state = inspect_existing_outputs(
        output_root=output, source_sha256=digest, source_relative_path=source.name
    )
    assert state.last_valid_stage is BatchStage.CHUNKS_VALIDATED
    chunks = output / digest / "chunks" / "chunks.json"
    chunks.write_text("{}", encoding="utf-8")
    state = inspect_existing_outputs(
        output_root=output, source_sha256=digest, source_relative_path=source.name
    )
    assert state.last_valid_stage is BatchStage.CANONICAL_VALIDATED


@pytest.mark.parametrize(
    ("extension", "document_type", "location_type", "location"),
    [
        (".pptx", DocumentType.POWERPOINT, LocationType.SLIDE, 1),
        (".docx", DocumentType.WORD, LocationType.DOCUMENT, None),
    ],
)
def test_legacy_office_suitability_is_inferred_without_mutating_canonical(
    tmp_path: Path,
    extension: str,
    document_type: DocumentType,
    location_type: LocationType,
    location: int | None,
) -> None:
    root = tmp_path / "library"
    root.mkdir()
    source = root / f"lesson{extension}"
    source.write_bytes(b"office fixture")
    digest = sha256_file(source)
    relative = source.name
    canonical = document(
        [
            [
                block(
                    "b1",
                    BlockType.PARAGRAPH,
                    "grounded office text",
                    0,
                    location=location,
                    location_type=location_type,
                )
            ]
        ],
        document_type=document_type,
    )
    canonical.document_id = digest
    canonical.sha256 = digest
    canonical.source_relative_path = relative
    canonical.source_filename = source.name
    canonical.source_extension = extension
    canonical.metadata.pop("extraction_quality", None)
    canonical.processing.warnings = ["Legacy extraction warning."]
    for page in canonical.pages:
        for item in page.blocks:
            item.source_reference.source_relative_path = relative
    directory = tmp_path / "processed" / digest
    directory.mkdir(parents=True)
    canonical_path = directory / "document.json"
    canonical_path.write_text(canonical.model_dump_json(indent=2), encoding="utf-8")
    before = canonical_path.read_bytes()

    state = inspect_existing_outputs(
        output_root=tmp_path / "processed",
        source_sha256=digest,
        source_relative_path=relative,
        source_root=root,
    )

    assert state.last_valid_stage is BatchStage.CANONICAL_VALIDATED
    assert state.suitability == "ready_with_warnings"
    assert any("backward-compatible resume" in warning for warning in state.validation_warnings)
    assert canonical_path.read_bytes() == before


def test_provenance_mismatch_is_never_complete(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    source = root / "lesson.pptx"
    source.write_bytes(b"pptx")
    output = tmp_path / "processed"
    digest = make_complete_output(root, output, source.name)
    state = inspect_existing_outputs(
        output_root=output, source_sha256="f" * 64, source_relative_path=source.name
    )
    assert state.complete is False
    assert state.canonical_path is None
    assert digest != "f" * 64


def test_router_preserves_office_and_explicit_ocr_policy(tmp_path: Path) -> None:
    root = make_library(tmp_path)
    inspections = {item.relative_path: item for item in inspect_library(root).documents}
    assert parser_route(inspections["c.pptx"]) is ParserRoute.PPTX
    assert parser_route(inspections["z.docx"]) is ParserRoute.DOCX
    mixed = inspections["b-mixed.pdf"]
    assert ocr_route(mixed, configuration(root)).value == "disabled"
    assert (
        ocr_route(mixed, configuration(root, ocr_enabled=True, ocr_languages=["fra"]))
        is OCRRoute.SAFE_FIRST
    )
    assert (
        ocr_route(
            mixed,
            configuration(root, ocr_enabled=True, ocr_languages=["fra"], allow_force_ocr=True),
        )
        is OCRRoute.SAFE_THEN_FORCE_ALLOWED
    )


def test_dry_run_writes_nothing_and_does_not_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_library(tmp_path)
    plan = build_batch_plan(configuration(root, limit=2, dry_run=True))
    monkeypatch.setattr(
        "ingestion.batch.executor._preflight",
        lambda _plan: pytest.fail("dry run invoked preflight"),
    )
    report = execute_batch(plan)
    assert report.selected_count == 2
    assert not plan.configuration.reports_root.exists()
    assert not plan.configuration.output_root.exists()
    assert not plan.configuration.derived_output_root.exists()


def test_state_round_trip_and_retry_selection(tmp_path: Path) -> None:
    root = make_library(tmp_path)
    plan = build_batch_plan(configuration(root, limit=1))
    state = initial_state(plan)
    state.documents[0].status = BatchDocumentStatus.FAILED
    persist_state(plan, state)
    loaded = load_or_initialize_state(plan)
    assert loaded.documents[0].status is BatchDocumentStatus.FAILED
    execute, reason = should_execute(plan.documents[0], loaded.documents[0], plan.configuration)
    assert execute is False and reason == "explicit_retry_required"
    retry_config = plan.configuration.model_copy(update={"retry_failures": True})
    execute, reason = should_execute(plan.documents[0], loaded.documents[0], retry_config)
    assert execute is True and reason is None
    loaded.documents[0].retry_count = 1
    execute, reason = should_execute(plan.documents[0], loaded.documents[0], retry_config)
    assert execute is False and reason == "maximum_retry_count_reached"


def test_failure_isolation_and_stop_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_library(tmp_path)
    monkeypatch.setattr("ingestion.batch.executor._preflight", lambda _plan: None)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("concise fixture failure")

    monkeypatch.setattr("ingestion.batch.executor._execute_document", fail)
    continuing = build_batch_plan(configuration(root, limit=2, continue_on_error=True))
    report = execute_batch(continuing, persist=False)
    assert report.failed_count == 2
    stopping = build_batch_plan(configuration(root, limit=2, continue_on_error=False))
    report = execute_batch(stopping, persist=False)
    assert report.failed_count == 1
    assert report.skipped_count == 1
    assert [item.sequence_number for item in report.documents] == [1, 2]


def test_unsupported_is_reported_without_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "library"
    root.mkdir()
    (root / "legacy.doc").write_bytes(b"legacy")
    plan = build_batch_plan(configuration(root, limit=1, dry_run=True))
    report = execute_batch(plan)
    assert report.unsupported_count == 1
    assert report.documents[0].skipped_reason == "unsupported_for_parsing"


def test_source_library_is_not_written_during_plan_or_dry_run(tmp_path: Path) -> None:
    root = make_library(tmp_path)
    before = {
        path.relative_to(root): sha256_file(path) for path in root.rglob("*") if path.is_file()
    }
    plan = build_batch_plan(configuration(root, limit=6, dry_run=True))
    execute_batch(plan)
    after = {
        path.relative_to(root): sha256_file(path) for path in root.rglob("*") if path.is_file()
    }
    assert before == after


def test_cli_help_does_not_initialize_models_or_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ingestion.config.DoclingSettings.validate_pdf_artifacts",
        lambda _self: pytest.fail("help initialized PDF models"),
    )
    monkeypatch.setattr(
        "ingestion.ocr.environment.check_ocr_environment",
        lambda *_args, **_kwargs: pytest.fail("help checked OCR"),
    )
    assert runner.invoke(app, ["plan-library", "--help"]).exit_code == 0
    assert runner.invoke(app, ["process-library", "--help"]).exit_code == 0


def test_cli_rejects_parallel_jobs_and_dry_run_writes_nothing(tmp_path: Path) -> None:
    root = make_library(tmp_path)
    parallel = runner.invoke(
        app, ["process-library", "--input", str(root), "--limit", "2", "--jobs", "2"]
    )
    assert parallel.exit_code == 2
    assert "only --jobs 1" in parallel.output
    reports = tmp_path / "batch-reports"
    dry = runner.invoke(
        app,
        [
            "process-library",
            "--input",
            str(root),
            "--limit",
            "2",
            "--dry-run",
            "--reports-output",
            str(reports),
            "--output",
            str(tmp_path / "processed"),
            "--derived-output",
            str(tmp_path / "derived"),
        ],
    )
    assert dry.exit_code == 0
    assert not reports.exists()


def test_library_report_schema_rejects_invalid_manifest(tmp_path: Path) -> None:
    root = make_library(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    plan = build_batch_plan(configuration(root, manifest_path=manifest))
    assert any("Manifest invalid" in warning for warning in plan.warnings)
    assert LibraryReport.model_fields


def test_full_library_requires_explicit_authorization(tmp_path: Path) -> None:
    root = make_library(tmp_path)
    allowed = configuration(root, limit=None, allow_full_library=True)
    assert allowed.limit is None


def test_preflight_checks_pdf_models_and_ocr_only_for_relevant_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    office = tmp_path / "office"
    office.mkdir()
    (office / "lesson.pptx").write_bytes(b"pptx")
    office_plan = build_batch_plan(configuration(office, limit=1))
    monkeypatch.setattr(
        "ingestion.batch.executor.DoclingSettings.validate_pdf_artifacts",
        lambda _self: pytest.fail("Office-only plan checked PDF artifacts"),
    )
    monkeypatch.setattr(
        "ingestion.batch.executor.check_ocr_environment",
        lambda *_args: pytest.fail("OCR-disabled plan checked OCR tools"),
    )
    _preflight(office_plan)

    pdf_root = tmp_path / "pdfs"
    pdf_root.mkdir()
    make_pdf(pdf_root / "mixed.pdf", text="small", image=True)
    calls = {"pdf": 0, "ocr": 0}

    def pdf_check(_self: object) -> None:
        calls["pdf"] += 1

    def ocr_check(*_args: object) -> SimpleNamespace:
        calls["ocr"] += 1
        return SimpleNamespace(ready=True)

    monkeypatch.setattr(
        "ingestion.batch.executor.DoclingSettings.validate_pdf_artifacts", pdf_check
    )
    monkeypatch.setattr("ingestion.batch.executor.check_ocr_environment", ocr_check)
    pdf_plan = build_batch_plan(
        configuration(pdf_root, limit=1, ocr_enabled=True, ocr_languages=["fra"])
    )
    _preflight(pdf_plan)
    assert calls == {"pdf": 1, "ocr": 1}


def test_source_hash_change_is_isolated_as_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "library"
    root.mkdir()
    source = root / "lesson.pptx"
    source.write_bytes(b"before")
    plan = build_batch_plan(configuration(root, limit=1))
    source.write_bytes(b"after")
    monkeypatch.setattr("ingestion.batch.executor._preflight", lambda _plan: None)
    report = execute_batch(plan, persist=False)
    assert report.failed_count == 1
    assert "SHA-256 changed" in report.documents[0].errors[0]


def test_interrupted_state_requires_explicit_retry(tmp_path: Path) -> None:
    root = make_library(tmp_path)
    plan = build_batch_plan(configuration(root, limit=1))
    state = initial_state(plan).documents[0]
    state.status = BatchDocumentStatus.INTERRUPTED
    execute, reason = should_execute(plan.documents[0], state, plan.configuration)
    assert execute is False and reason == "explicit_retry_required"
    retry = plan.configuration.model_copy(update={"retry_failures": True})
    execute, reason = should_execute(plan.documents[0], state, retry)
    assert execute is True and reason is None


def test_valid_dataset_without_eligible_chunks_is_not_complete(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    source = root / "lesson.pptx"
    source.write_bytes(b"pptx")
    output = tmp_path / "processed"
    digest = make_complete_output(root, output, source.name)
    dataset_path = output / digest / "datasets" / "ai-ready-dataset.json"
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    for chunk in payload["chunks"]:
        chunk["eligible_for_generation"] = False
        chunk["generation_exclusion_reasons"] = ["fixture_exclusion"]
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")
    state = inspect_existing_outputs(
        output_root=output,
        source_sha256=digest,
        source_relative_path=source.name,
        source_root=root,
    )
    assert state.complete is False
    assert state.last_valid_stage is BatchStage.DATASET_VALIDATED
    assert any("eligible" in warning for warning in state.validation_warnings)


def test_ocr_canonical_with_missing_derivative_is_not_reused(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    source = root / "lesson.pdf"
    make_pdf(source)
    output = tmp_path / "processed"
    digest = sha256_file(source)
    canonical = document([[block("b1", BlockType.PARAGRAPH, "grounded", 0)]])
    canonical.document_id = digest
    canonical.sha256 = digest
    canonical.source_relative_path = source.name
    canonical.source_filename = source.name
    canonical.source_extension = ".pdf"
    canonical.metadata["derivative_provenance"] = {
        "quality_outcome": "accepted",
        "original_source_sha256": digest,
        "derivative_id": "d" * 64,
        "derivative_sha256": "e" * 64,
        "derivative_relative_path": str(tmp_path / "missing" / "document-ocr.pdf"),
    }
    variant = output / digest / "variants" / "variant"
    variant.mkdir(parents=True)
    (variant / "document.json").write_text(canonical.model_dump_json(), encoding="utf-8")
    state = inspect_existing_outputs(
        output_root=output,
        source_sha256=digest,
        source_relative_path=source.name,
        source_root=root,
    )
    assert state.complete is False
    assert state.canonical_path is None
    assert any(
        "derivative validation failed" in warning.lower() for warning in state.validation_warnings
    )
