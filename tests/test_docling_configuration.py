from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from docling.datamodel.document import ConversionStatus
from typer.testing import CliRunner

from ingestion.cli import app
from ingestion.config import (
    DOCLING_ARTIFACTS_ENV,
    DoclingConfigurationError,
    DoclingErrorCategory,
    DoclingSettings,
)
from ingestion.doctor import check_environment
from ingestion.normalization.models import NormalizedDocument
from ingestion.normalization.validation import validate_document_file
from ingestion.parsers.base import ParsedSource, StructuredDocumentParser, StructuredParserRegistry
from ingestion.parsers.docling_parser import DoclingStructuredParser, StructuredParsingError
from ingestion.parsers.unsupported import UnsupportedParser
from ingestion.pipeline import parse_document
from ingestion.scanner import default_registry


def make_artifacts(root: Path) -> Path:
    layout = root / "docling-project--docling-layout-heron"
    table = (
        root / "docling-project--docling-models" / "model_artifacts" / "tableformer" / "accurate"
    )
    layout.mkdir(parents=True)
    table.mkdir(parents=True)
    for path in (
        layout / "config.json",
        layout / "preprocessor_config.json",
        layout / "model.safetensors",
        table / "tm_config.json",
        table / "tableformer_accurate.safetensors",
    ):
        path.write_bytes(b"fixture")
    return root


def assert_category(settings: DoclingSettings, category: DoclingErrorCategory) -> None:
    with pytest.raises(DoclingConfigurationError) as caught:
        settings.validate_pdf_artifacts()
    assert caught.value.category is category
    assert category.value in str(caught.value)


def test_artifact_environment_absent() -> None:
    settings = DoclingSettings.from_sources(environ={})
    assert_category(settings, DoclingErrorCategory.ARTIFACTS_NOT_CONFIGURED)


def test_artifact_path_missing(tmp_path: Path) -> None:
    settings = DoclingSettings.from_sources(environ={DOCLING_ARTIFACTS_ENV: str(tmp_path / "x")})
    assert_category(settings, DoclingErrorCategory.ARTIFACTS_PATH_MISSING)


def test_artifact_path_is_file(tmp_path: Path) -> None:
    path = tmp_path / "models"
    path.write_text("not a directory", encoding="utf-8")
    assert_category(
        DoclingSettings.from_sources(environ={DOCLING_ARTIFACTS_ENV: str(path)}),
        DoclingErrorCategory.ARTIFACTS_INVALID,
    )


def test_artifact_directory_malformed(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    assert_category(
        DoclingSettings.from_sources(environ={DOCLING_ARTIFACTS_ENV: str(root)}),
        DoclingErrorCategory.ARTIFACTS_INVALID,
    )


def test_required_model_missing(tmp_path: Path) -> None:
    root = tmp_path / "models"
    (root / "docling-project--docling-layout-heron").mkdir(parents=True)
    assert_category(
        DoclingSettings.from_sources(environ={DOCLING_ARTIFACTS_ENV: str(root)}),
        DoclingErrorCategory.REQUIRED_MODEL_MISSING,
    )


def test_valid_artifact_structure_cli_precedence_and_expansion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment_root = make_artifacts(tmp_path / "environment")
    override_root = make_artifacts(tmp_path / "override")
    settings = DoclingSettings.from_sources(
        override_root,
        environ={DOCLING_ARTIFACTS_ENV: str(environment_root)},
    )
    assert settings.validate_pdf_artifacts().root == override_root.resolve()

    fake_home = tmp_path / "home"
    expanded = make_artifacts(fake_home / "models")
    monkeypatch.setenv("HOME", str(fake_home))
    settings = DoclingSettings.from_sources(environ={DOCLING_ARTIFACTS_ENV: "~/models"})
    assert settings.artifacts_path == expanded.resolve()


def test_local_only_environment_is_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    settings = DoclingSettings(artifacts_path=make_artifacts(tmp_path / "models"))
    settings.enforce_local_only()
    assert settings.local_only is True
    assert settings.ocr_enabled is False
    assert settings.table_structure_enabled is True
    assert __import__("os").environ["HF_HUB_OFFLINE"] == "1"
    assert __import__("os").environ["HF_HUB_DISABLE_TELEMETRY"] == "1"
    assert __import__("os").environ["TRANSFORMERS_OFFLINE"] == "1"


class FakeConverter:
    instances: list[FakeConverter] = []
    initialization_error: Exception | None = None
    conversion_error: Exception | None = None

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args
        self.kwargs = kwargs
        self.initialized = False
        FakeConverter.instances.append(self)

    def initialize_pipeline(self, _format: object) -> None:
        if self.initialization_error is not None:
            raise self.initialization_error
        self.initialized = True

    def convert(self, _path: Path, *, raises_on_error: bool) -> Any:
        assert raises_on_error is False
        if self.conversion_error is not None:
            raise self.conversion_error
        return SimpleNamespace(
            status=ConversionStatus.SUCCESS,
            errors=[],
            document=SimpleNamespace(),
        )


def test_pdf_initialization_is_lazy_local_and_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    FakeConverter.instances.clear()
    FakeConverter.initialization_error = None
    FakeConverter.conversion_error = None
    monkeypatch.setattr("ingestion.parsers.docling_parser.DocumentConverter", FakeConverter)
    settings = DoclingSettings(artifacts_path=make_artifacts(tmp_path / "models"))
    parser = DoclingStructuredParser(settings)
    assert parser.pdf_initialized is False
    assert FakeConverter.instances == []

    first = parser.parse(tmp_path / "one.pdf")
    second = parser.parse(tmp_path / "two.pdf")

    assert parser.pdf_initialized is True
    assert len(FakeConverter.instances) == 1
    assert first.provenance is not None
    assert first.provenance["local_only"] is True
    assert first.provenance["ocr_enabled"] is False
    assert second.parser_name == "docling"
    options = FakeConverter.instances[0].kwargs["format_options"]
    pdf_pipeline = next(iter(options.values())).pipeline_options
    assert pdf_pipeline.artifacts_path == settings.artifacts_path
    assert pdf_pipeline.do_ocr is False
    assert pdf_pipeline.enable_remote_services is False
    assert pdf_pipeline.force_backend_text is True


def test_model_initialization_and_pdf_parse_errors_are_categorized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ingestion.parsers.docling_parser.DocumentConverter", FakeConverter)
    settings = DoclingSettings(artifacts_path=make_artifacts(tmp_path / "models"))
    FakeConverter.initialization_error = RuntimeError("model detail must not leak")
    parser = DoclingStructuredParser(settings)
    with pytest.raises(StructuredParsingError) as initialized:
        parser.parse(tmp_path / "one.pdf")
    assert initialized.value.category is DoclingErrorCategory.MODEL_INITIALIZATION_FAILED

    FakeConverter.initialization_error = None
    FakeConverter.conversion_error = RuntimeError("document content must not leak")
    parser = DoclingStructuredParser(settings)
    with pytest.raises(StructuredParsingError) as parsed:
        parser.parse(tmp_path / "one.pdf")
    assert parsed.value.category is DoclingErrorCategory.PDF_PARSE_FAILED
    FakeConverter.conversion_error = None


def test_cli_help_and_inspection_do_not_require_models(tmp_path: Path) -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["--help"], env={DOCLING_ARTIFACTS_ENV: ""}).exit_code == 0
    assert (
        runner.invoke(app, ["parse-document", "--help"], env={DOCLING_ARTIFACTS_ENV: ""}).exit_code
        == 0
    )
    text = tmp_path / "notes.txt"
    text.write_text("fixture", encoding="utf-8")
    inspected = runner.invoke(app, ["inspect-document", str(text)], env={DOCLING_ARTIFACTS_ENV: ""})
    assert inspected.exit_code == 0
    assert "unsupported_for_now" in inspected.stdout


def test_environment_doctor_exit_codes(tmp_path: Path) -> None:
    missing = check_environment(DoclingSettings.from_sources(environ={}), output_root=tmp_path)
    assert missing.ready is False
    valid = check_environment(
        DoclingSettings(artifacts_path=make_artifacts(tmp_path / "models")),
        output_root=tmp_path,
    )
    assert valid.ready is True

    runner = CliRunner()
    cli_missing = runner.invoke(app, ["check-environment"], env={DOCLING_ARTIFACTS_ENV: ""})
    assert cli_missing.exit_code == 1
    cli_valid = runner.invoke(
        app,
        ["check-environment", "--docling-artifacts-path", str(tmp_path / "models")],
        env={DOCLING_ARTIFACTS_ENV: ""},
    )
    assert cli_valid.exit_code == 0


def test_office_registration_and_inspection_registry_remain_model_independent() -> None:
    parser = DoclingStructuredParser(DoclingSettings.from_sources(environ={}))
    assert parser.extensions == frozenset({".pdf", ".pptx", ".docx"})
    assert parser.pdf_initialized is False
    assert default_registry().parser_for(".pptx").__class__ is UnsupportedParser
    assert default_registry().parser_for(".docx").__class__ is UnsupportedParser


class FailingPdfParser(StructuredDocumentParser):
    @property
    def extensions(self) -> frozenset[str]:
        return frozenset({".pdf"})

    def parse(self, path: Path) -> ParsedSource:
        del path
        raise DoclingConfigurationError(DoclingErrorCategory.ARTIFACTS_NOT_CONFIGURED, "fixture")


def test_pdf_failure_leaves_no_partial_output(tmp_path: Path) -> None:
    source_root = tmp_path / "library"
    source_root.mkdir()
    source = source_root / "fixture.pdf"
    source.write_bytes(b"fixture")
    output = tmp_path / "processed"
    registry = StructuredParserRegistry(FailingPdfParser())
    registry.register(FailingPdfParser())
    with pytest.raises(DoclingConfigurationError):
        parse_document(source, source_root=source_root, output_root=output, registry=registry)
    assert not output.exists()


def test_canonical_schema_and_existing_pptx_output_remain_compatible() -> None:
    assert NormalizedDocument.model_fields["schema_version"].default == "1.0.0"
    assert set(NormalizedDocument.model_fields) == {
        "schema_version",
        "document_id",
        "sha256",
        "source_relative_path",
        "source_filename",
        "source_extension",
        "source_mime_type",
        "title",
        "document_type",
        "language",
        "page_or_slide_count",
        "metadata",
        "sections",
        "pages",
        "tables",
        "assets",
        "processing",
    }
    existing = Path(
        "data/processed/"
        "a072483ee794dc62095a8578d7582c5311911a86d98668331bf27c393b4e20bd/"
        "document.json"
    )
    if existing.is_file():
        assert validate_document_file(existing).document_type.value == "powerpoint"


def test_processing_report_provenance_is_serializable() -> None:
    payload = ParsedSource(
        document=SimpleNamespace(),
        parser_name="fixture",
        parser_version="1",
        provenance={
            "local_only": True,
            "ocr_enabled": False,
            "artifact_identifiers": ["layout", "tableformer"],
        },
    )
    assert json.loads(json.dumps(payload.provenance))["local_only"] is True
