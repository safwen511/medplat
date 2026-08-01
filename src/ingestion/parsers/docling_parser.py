"""Docling source parser isolated behind the shared structured interface."""

from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import ConversionStatus
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from ingestion.config import (
    DoclingConfigurationError,
    DoclingErrorCategory,
    DoclingSettings,
)
from ingestion.parsers.base import ParsedSource, StructuredDocumentParser


class StructuredParsingError(RuntimeError):
    """Categorized failure converting a supported source."""

    def __init__(self, category: DoclingErrorCategory, message: str) -> None:
        self.category = category
        super().__init__(f"{category.value}: {message}")


class UnsupportedFormatError(ValueError):
    """Raised when no structured parser is registered for a format."""


class DoclingStructuredParser(StructuredDocumentParser):
    """Parse PDF, PPTX, and DOCX locally with lazy PDF model initialization."""

    def __init__(self, settings: DoclingSettings | None = None) -> None:
        self._settings = settings or DoclingSettings.from_sources()
        self._pdf_converter_instance: DocumentConverter | None = None
        self._office_converter_instance: DocumentConverter | None = None
        self._pdf_artifact_identifiers: tuple[str, ...] = ()

    @property
    def extensions(self) -> frozenset[str]:
        return frozenset({".pdf", ".pptx", ".docx"})

    @property
    def pdf_initialized(self) -> bool:
        """Expose initialization state for diagnostics and regression tests."""
        return self._pdf_converter_instance is not None

    def _office_converter(self) -> DocumentConverter:
        if self._office_converter_instance is None:
            self._office_converter_instance = DocumentConverter(
                allowed_formats=[InputFormat.PPTX, InputFormat.DOCX]
            )
        return self._office_converter_instance

    def _pdf_converter(self) -> DocumentConverter:
        if self._pdf_converter_instance is not None:
            return self._pdf_converter_instance
        inventory = self._settings.validate_pdf_artifacts()
        self._settings.enforce_local_only()
        pdf_options = PdfPipelineOptions(
            artifacts_path=inventory.root,
            do_ocr=False,
            enable_remote_services=False,
            allow_external_plugins=False,
            do_table_structure=True,
            force_backend_text=True,
            do_picture_classification=False,
            do_picture_description=False,
            do_chart_extraction=False,
            do_code_enrichment=False,
            do_formula_enrichment=False,
        )
        converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)},
        )
        try:
            converter.initialize_pipeline(InputFormat.PDF)
        except (DoclingConfigurationError, KeyboardInterrupt):
            raise
        except Exception as exc:
            raise StructuredParsingError(
                DoclingErrorCategory.MODEL_INITIALIZATION_FAILED,
                f"Could not initialize the configured local PDF models ({type(exc).__name__}).",
            ) from exc
        self._pdf_artifact_identifiers = inventory.artifact_identifiers
        self._pdf_converter_instance = converter
        return converter

    def parse(self, path: Path) -> ParsedSource:
        extension = path.suffix.lower()
        if extension == ".pdf":
            converter = self._pdf_converter()
            failure_category = DoclingErrorCategory.PDF_PARSE_FAILED
        elif extension in {".pptx", ".docx"}:
            converter = self._office_converter()
            failure_category = DoclingErrorCategory.SOURCE_PARSE_FAILED
        else:
            raise UnsupportedFormatError(
                f"Structured parsing is not supported for {extension or 'extensionless files'}"
            )
        try:
            result = converter.convert(path, raises_on_error=False)
        except (DoclingConfigurationError, StructuredParsingError, KeyboardInterrupt):
            raise
        except Exception as exc:
            label = "PDF" if extension == ".pdf" else "Office document"
            raise StructuredParsingError(
                failure_category,
                f"{label} conversion failed ({type(exc).__name__}).",
            ) from exc
        if result.status not in {ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS}:
            error_types = sorted({type(error).__name__ for error in result.errors})
            details = ", ".join(error_types) or f"status={result.status.value}"
            raise StructuredParsingError(failure_category, f"Docling conversion failed: {details}.")
        warnings: tuple[str, ...] = ()
        if result.status is ConversionStatus.PARTIAL_SUCCESS:
            warnings = ("Docling reported a partial conversion.",)
        docling_version = version("docling")
        provenance: dict[str, object] = {
            "docling_version": docling_version,
            "parser_backend": (
                "docling-standard-pdf+PyMuPDF" if extension == ".pdf" else "docling-office"
            ),
            "local_only": extension == ".pdf",
            "ocr_enabled": False,
            "table_structure_recognition_enabled": extension == ".pdf",
            "backend_text_forced": extension == ".pdf",
        }
        if extension == ".pdf":
            provenance["artifact_identifiers"] = list(self._pdf_artifact_identifiers)
        return ParsedSource(
            document=result.document,
            parser_name="docling",
            parser_version=docling_version,
            warnings=warnings,
            provenance=provenance,
        )


class UnsupportedStructuredParser(StructuredDocumentParser):
    """Clear rejection for current and legacy unsupported formats."""

    @property
    def extensions(self) -> frozenset[str]:
        return frozenset()

    def parse(self, path: Path) -> ParsedSource:
        extension = path.suffix.lower() or "extensionless files"
        raise UnsupportedFormatError(f"Structured parsing is not supported for {extension}")
