from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz
import pytest
from typer.testing import CliRunner

from ingestion.chunking.builder import build_chunk_collection
from ingestion.cli import app
from ingestion.hashing import sha256_file
from ingestion.normalization.models import (
    AssetType,
    BlockType,
    DocumentType,
    LocationType,
    NormalizedAsset,
    NormalizedBlock,
    NormalizedDocument,
    NormalizedPage,
    ProcessingInformation,
    ProcessingReport,
    ProcessingStatus,
    SourceReference,
)
from ingestion.ocr.environment import check_ocr_environment
from ingestion.ocr.evaluator import evaluate_ocr
from ingestion.ocr.models import (
    OCRConfiguration,
    OCREligibility,
    OCREnvironmentReport,
    OCRQualityMetrics,
    OCRQualityOutcome,
)
from ingestion.ocr.parsing import parse_ocr_derivative, processing_variant_id
from ingestion.ocr.service import (
    OCRExecutionError,
    _quality_outcome,
    create_ocr_derivative,
    deterministic_derivative_id,
)
from ingestion.ocr.validation import validate_derivative_file
from ingestion.pipeline import ParseResult


def make_pdf(
    path: Path,
    *,
    text: str = "",
    image: bool = False,
    pages: int = 1,
    encryption: bool = False,
) -> None:
    document = fitz.open()
    for index in range(pages):
        page = document.new_page(width=300, height=400)
        page_text = text if index == 0 else ("x" * 200)
        if page_text:
            page.insert_textbox(fitz.Rect(20, 20, 280, 180), page_text, fontsize=8)
        if image and index == 0:
            pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), False)
            pixmap.clear_with(220)
            page.insert_image(fitz.Rect(20, 190, 280, 380), pixmap=pixmap)
    if encryption:
        document.save(
            path,
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner",
            user_pw="user",
        )
    else:
        document.save(path)
    document.close()


def ready_environment(languages: list[str]) -> OCREnvironmentReport:
    return OCREnvironmentReport(
        ready=True,
        ocrmypdf_version="16.13.0",
        tesseract_version="tesseract 5.5.0",
        qpdf_version="qpdf 12.3.2",
        ghostscript_version="10.06.0",
        installed_languages=["eng", "fra", "osd"],
        requested_languages=languages,
        derivative_output_writable=True,
        source_library_policy="read-only",
    )


def test_ocr_environment_missing_tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ingestion.ocr.environment._version", lambda _command: None)
    monkeypatch.setattr("ingestion.ocr.environment.installed_tesseract_languages", list)
    report = check_ocr_environment(["fra"], tmp_path)
    assert report.ready is False
    assert report.missing_tools == ["ocrmypdf", "tesseract", "qpdf", "ghostscript"]
    assert report.missing_languages == ["fra"]


def test_ocr_environment_missing_tesseract_language(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("ingestion.ocr.environment._version", lambda command: command[0] + " 1")
    monkeypatch.setattr("ingestion.ocr.environment.installed_tesseract_languages", lambda: ["eng"])
    report = check_ocr_environment(["fra"], tmp_path)
    assert report.ready is False
    assert report.missing_tools == []
    assert report.missing_languages == ["fra"]


def test_valid_ocr_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ingestion.ocr.environment._version", lambda command: command[0] + " 1")
    monkeypatch.setattr(
        "ingestion.ocr.environment.installed_tesseract_languages", lambda: ["eng", "fra"]
    )
    assert check_ocr_environment(["fra", "eng"], tmp_path).ready is True


def test_non_pdf_damaged_and_encrypted_rejection(tmp_path: Path) -> None:
    text = tmp_path / "notes.txt"
    text.write_text("notes", encoding="utf-8")
    assert evaluate_ocr(text, source_root=tmp_path).eligibility is OCREligibility.NOT_SUPPORTED
    damaged = tmp_path / "damaged.pdf"
    damaged.write_bytes(b"not pdf")
    assert evaluate_ocr(damaged, source_root=tmp_path).eligibility is OCREligibility.BLOCKED
    encrypted = tmp_path / "encrypted.pdf"
    make_pdf(encrypted, image=True, encryption=True)
    result = evaluate_ocr(encrypted, source_root=tmp_path)
    assert result.eligibility is OCREligibility.BLOCKED
    assert result.encrypted is True


def test_ocr_eligibility_not_needed_recommended_and_required(tmp_path: Path) -> None:
    native = tmp_path / "native.pdf"
    make_pdf(native, text="reliable " * 40)
    assert evaluate_ocr(native, source_root=tmp_path).eligibility is OCREligibility.NOT_NEEDED
    required = tmp_path / "required.pdf"
    make_pdf(required, text="tiny", image=True)
    required_result = evaluate_ocr(required, source_root=tmp_path)
    assert required_result.eligibility is OCREligibility.REQUIRED
    assert required_result.low_text_pages == [1]
    recommended = tmp_path / "recommended.pdf"
    make_pdf(recommended, text="tiny", image=True, pages=3)
    assert evaluate_ocr(recommended, source_root=tmp_path).eligibility is OCREligibility.RECOMMENDED


def test_explicit_and_multilingual_configuration() -> None:
    with pytest.raises(ValueError, match="At least one"):
        OCRConfiguration(language_codes=[])
    configuration = OCRConfiguration(language_codes=["fra", "eng"])
    assert configuration.language_codes == ["fra", "eng"]
    with pytest.raises(ValueError, match="mutually exclusive"):
        OCRConfiguration(language_codes=["fra"], force_ocr=True, skip_text=True)


def test_deterministic_derivative_and_variant_ids() -> None:
    configuration = OCRConfiguration(language_codes=["fra"])
    first = deterministic_derivative_id("a" * 64, configuration, "16.13.0")
    second = deterministic_derivative_id("a" * 64, configuration, "16.13.0")
    different = deterministic_derivative_id(
        "a" * 64, OCRConfiguration(language_codes=["fra", "eng"]), "16.13.0"
    )
    assert first == second
    assert first != different
    assert processing_variant_id(first) == processing_variant_id(first)


def fake_ocr_run(output_text: str | None):
    def run(
        command: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        del capture_output, text, timeout, check
        source = Path(command[-2])
        output = Path(command[-1])
        if output_text is None:
            shutil.copyfile(source, output)
        else:
            make_pdf(output, text=output_text, image=True)
        return subprocess.CompletedProcess(command, 0, stdout="completed", stderr="")

    return run


def create_fixture_derivative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    output_text: str | None,
) -> tuple[Path, Path, str]:
    library = tmp_path / "library"
    library.mkdir()
    source = library / "source.pdf"
    make_pdf(source, text="tiny", image=True)
    before = sha256_file(source)
    monkeypatch.setattr(
        "ingestion.ocr.service.check_ocr_environment",
        lambda languages, output: ready_environment(languages),
    )
    monkeypatch.setattr("ingestion.ocr.service.subprocess.run", fake_ocr_run(output_text))
    result = create_ocr_derivative(
        source,
        OCRConfiguration(language_codes=["fra"]),
        output_root=tmp_path / "derived",
        source_root=library,
    )
    return source, result.directory / "derivative.json", before


def test_derivative_is_atomic_isolated_and_preserves_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, metadata, before = create_fixture_derivative(
        tmp_path, monkeypatch, output_text="texte reconnu " * 30
    )
    derivative, report = validate_derivative_file(metadata, source_root=tmp_path / "library")
    assert sha256_file(source) == before == derivative.source_sha256
    assert derivative.derivative_id in metadata.parts
    assert not metadata.resolve().is_relative_to((tmp_path / "library").resolve())
    assert derivative.page_count == report.source_page_count == report.derivative_page_count == 1
    assert derivative.validation_status is OCRQualityOutcome.ACCEPTED
    assert report.derivative_text_character_count > report.source_text_character_count
    assert not list((tmp_path / "derived").rglob("*.tmp"))
    with pytest.raises(FileExistsError):
        create_ocr_derivative(
            source,
            OCRConfiguration(language_codes=["fra"]),
            output_root=tmp_path / "derived",
            source_root=tmp_path / "library",
        )


def test_no_material_improvement_and_degraded_quality() -> None:
    base = dict(
        source_text_characters_by_page=[100],
        derivative_text_characters_by_page=[100],
        low_text_pages_before=[1],
        low_text_pages_after=[1],
        image_heavy_pages=[1],
        percentage_improvement=0.0,
        page_count_equal=True,
        derivative_pdf_valid=True,
        physical_page_mapping_preserved=True,
    )
    no_gain = OCRQualityMetrics(
        source_text_character_count=100,
        derivative_text_character_count=110,
        **base,
    )
    assert _quality_outcome(no_gain) is OCRQualityOutcome.NO_MATERIAL_IMPROVEMENT
    degraded = OCRQualityMetrics(
        source_text_character_count=100,
        derivative_text_character_count=80,
        **base,
    )
    assert _quality_outcome(degraded) is OCRQualityOutcome.DEGRADED
    invalid = OCRQualityMetrics(
        source_text_character_count=100,
        derivative_text_character_count=200,
        **{**base, "page_count_equal": False},
    )
    assert _quality_outcome(invalid) is OCRQualityOutcome.INVALID


def test_derivative_hash_validation_detects_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, metadata, _ = create_fixture_derivative(
        tmp_path, monkeypatch, output_text="texte reconnu " * 30
    )
    (metadata.parent / "document-ocr.pdf").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        validate_derivative_file(metadata, source_root=tmp_path / "library")


def test_failed_ocr_cleans_temporary_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    library = tmp_path / "library"
    library.mkdir()
    source = library / "source.pdf"
    make_pdf(source, text="tiny", image=True)
    monkeypatch.setattr(
        "ingestion.ocr.service.check_ocr_environment",
        lambda languages, output: ready_environment(languages),
    )
    monkeypatch.setattr(
        "ingestion.ocr.service.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 2, "", "failure"),
    )
    with pytest.raises(OCRExecutionError):
        create_ocr_derivative(
            source,
            OCRConfiguration(language_codes=["fra"]),
            output_root=tmp_path / "derived",
            source_root=library,
        )
    assert not list((tmp_path / "derived").rglob("*.tmp"))
    assert not list((tmp_path / "derived").rglob("derivative.json"))


def canonical_document(*, derivative_quality: str | None = None) -> NormalizedDocument:
    source_path = "nested/source.pdf"
    text_reference = SourceReference(
        source_relative_path=source_path,
        location_type=LocationType.PAGE,
        page_or_slide_number=1,
        block_id="block-text",
    )
    figure_reference = SourceReference(
        source_relative_path=source_path,
        location_type=LocationType.PAGE,
        page_or_slide_number=2,
        block_id="block-figure",
    )
    metadata: dict[str, Any] = {}
    if derivative_quality is not None:
        metadata["derivative_provenance"] = {"quality_outcome": derivative_quality}
    return NormalizedDocument(
        document_id="a" * 64,
        sha256="a" * 64,
        source_relative_path=source_path,
        source_filename="source.pdf",
        source_extension=".pdf",
        source_mime_type="application/pdf",
        document_type=DocumentType.PDF,
        page_or_slide_count=2,
        metadata=metadata,
        pages=[
            NormalizedPage(
                number=1,
                location_type=LocationType.PAGE,
                blocks=[
                    NormalizedBlock(
                        block_id="block-text",
                        block_type=BlockType.PARAGRAPH,
                        text="Short meaningful title",
                        page_or_slide_number=1,
                        reading_order=0,
                        source_reference=text_reference,
                    ),
                ],
            ),
            NormalizedPage(
                number=2,
                location_type=LocationType.PAGE,
                blocks=[
                    NormalizedBlock(
                        block_id="block-figure",
                        block_type=BlockType.FIGURE,
                        page_or_slide_number=2,
                        reading_order=1,
                        source_reference=figure_reference,
                        metadata={"asset_id": "asset-1"},
                    )
                ],
                asset_references=["asset-1"],
            ),
        ],
        assets=[
            NormalizedAsset(
                asset_id="asset-1",
                asset_type=AssetType.FIGURE,
                source_page_or_slide=2,
            )
        ],
        processing=ProcessingInformation(parser_name="fixture", parser_version="1"),
    )


def test_chunk_gate_and_generation_eligibility() -> None:
    with pytest.raises(ValueError, match="Rejected OCR"):
        build_chunk_collection(canonical_document(derivative_quality="no_material_improvement"))
    collection = build_chunk_collection(canonical_document(derivative_quality="accepted"))
    meaningful = next(chunk for chunk in collection.chunks if chunk.normalized_text)
    empty = next(chunk for chunk in collection.chunks if not chunk.normalized_text)
    assert meaningful.eligible_for_generation is True
    assert meaningful.character_count < 250
    assert empty.eligible_for_generation is False
    assert "uncaptioned_asset_without_explanation" in empty.generation_exclusion_reasons
    assert collection.processing_statistics.eligible_for_generation == 1
    assert collection.processing_statistics.excluded_from_generation == 1


def test_parse_derivative_preserves_original_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, metadata, _ = create_fixture_derivative(
        tmp_path, monkeypatch, output_text="texte reconnu " * 30
    )

    def fake_parse(_path: Path, **kwargs: Any) -> ParseResult:
        document = canonical_document(derivative_quality="accepted")
        document.document_id = kwargs["source_sha256_override"]
        document.sha256 = kwargs["source_sha256_override"]
        document.source_relative_path = kwargs["source_relative_path_override"]
        document.source_filename = kwargs["source_identity_path"].name
        document.metadata.update(kwargs["additional_metadata"])
        for page in document.pages:
            for block in page.blocks:
                block.source_reference.source_relative_path = document.source_relative_path
        now = datetime.now(timezone.utc)
        report = ProcessingReport(
            parser_name="fixture",
            parser_version="1",
            start_time=now,
            completion_time=now,
            status=ProcessingStatus.SUCCESS,
        )
        output = tmp_path / "processed" / kwargs["output_relative_path"]
        output.mkdir(parents=True)
        return ParseResult(document=document, report=report, output_directory=output)

    monkeypatch.setattr("ingestion.ocr.parsing.parse_document", fake_parse)
    result = parse_ocr_derivative(
        metadata,
        source_root=tmp_path / "library",
        output_root=tmp_path / "processed",
    )
    assert result.document.document_id == sha256_file(source)
    assert result.document.source_relative_path == "source.pdf"
    assert result.document.metadata["derivative_provenance"]["derivative_sha256"]
    assert all(
        block.source_reference.source_relative_path == "source.pdf"
        for page in result.document.pages
        for block in page.blocks
    )


def test_cli_help_does_not_invoke_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    invoked = False

    def forbidden(*args: object, **kwargs: object) -> None:
        nonlocal invoked
        invoked = True
        raise AssertionError("OCR invoked during help")

    monkeypatch.setattr("ingestion.ocr.service.create_ocr_derivative", forbidden)
    runner = CliRunner()
    for command in (
        "check-ocr-environment",
        "evaluate-ocr",
        "create-ocr-derivative",
        "validate-derivative",
        "parse-ocr-derivative",
    ):
        assert runner.invoke(app, [command, "--help"]).exit_code == 0
    assert invoked is False
