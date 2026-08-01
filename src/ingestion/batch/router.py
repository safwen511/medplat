"""Pure deterministic route selection for inspected documents."""

from ingestion.batch.models import BatchConfiguration, OCRRoute, ParserRoute
from ingestion.models import DocumentClassification, DocumentInspection


def parser_route(inspection: DocumentInspection) -> ParserRoute:
    return {
        ".pdf": ParserRoute.PDF,
        ".pptx": ParserRoute.PPTX,
        ".docx": ParserRoute.DOCX,
    }.get(inspection.extension, ParserRoute.UNSUPPORTED)


def ocr_route(inspection: DocumentInspection, configuration: BatchConfiguration) -> OCRRoute:
    if inspection.extension != ".pdf":
        return OCRRoute.NONE
    may_need_ocr = inspection.classification in {
        DocumentClassification.MIXED,
        DocumentClassification.LIKELY_SCANNED,
    }
    if not may_need_ocr:
        return OCRRoute.NONE
    if not configuration.ocr_enabled:
        return OCRRoute.DISABLED
    return (
        OCRRoute.SAFE_THEN_FORCE_ALLOWED if configuration.allow_force_ocr else OCRRoute.SAFE_FIRST
    )
