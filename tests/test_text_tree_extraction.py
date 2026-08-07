from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import fitz
import pytest
from pydantic import ValidationError

from ingestion.hashing import sha256_file
from ingestion.normalization.models import (
    BlockType,
    DocumentType,
    LocationType,
    NormalizedBlock,
    NormalizedDocument,
    NormalizedPage,
    NormalizedTable,
    NormalizedTableCell,
    ProcessingInformation,
    SourceReference,
)
from ingestion.text_tree.discovery import (
    plan_output_paths,
    safe_output_path,
    snapshot_source_tree,
)
from ingestion.text_tree.models import ExportStatus, TextExportConfiguration
from ingestion.text_tree.rendering import render_normalized_document
from ingestion.text_tree.service import extract_text_tree
from ingestion.text_tree.validation import parse_metadata_header, validate_text_export

FIXED_TIME = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


def _configuration(source: Path, root: Path, **changes: object) -> TextExportConfiguration:
    values: dict[str, object] = {
        "input_root": source,
        "output_root": root / "output",
        "report_output_root": root / "reports",
    }
    values.update(changes)
    return TextExportConfiguration(**values)


def _run(configuration: TextExportConfiguration):  # type: ignore[no-untyped-def]
    return extract_text_tree(configuration, now=lambda: FIXED_TIME, monotonic=lambda: 10.0)


def _reference(
    source: str, location: LocationType, number: int | None, block_id: str
) -> SourceReference:
    return SourceReference(
        source_relative_path=source,
        location_type=location,
        page_or_slide_number=number,
        block_id=block_id,
    )


def _block(
    source: str,
    location: LocationType,
    number: int | None,
    order: int,
    text: str | None,
    kind: BlockType = BlockType.PARAGRAPH,
    metadata: dict[str, object] | None = None,
) -> NormalizedBlock:
    block_id = f"block-{order:06d}"
    return NormalizedBlock(
        block_id=block_id,
        block_type=kind,
        text=text,
        page_or_slide_number=number,
        reading_order=order,
        source_reference=_reference(source, location, number, block_id),
        metadata=metadata or {},
    )


def _document(
    document_type: DocumentType,
    pages: list[NormalizedPage],
    *,
    tables: list[NormalizedTable] | None = None,
) -> NormalizedDocument:
    source = (
        "nested/course"
        + {
            DocumentType.PDF: ".pdf",
            DocumentType.POWERPOINT: ".pptx",
            DocumentType.WORD: ".docx",
        }[document_type]
    )
    return NormalizedDocument(
        document_id="a" * 64,
        sha256="a" * 64,
        source_relative_path=source,
        source_filename=Path(source).name,
        source_extension=Path(source).suffix,
        document_type=document_type,
        page_or_slide_count=None if document_type is DocumentType.WORD else len(pages),
        pages=pages,
        tables=tables or [],
        processing=ProcessingInformation(parser_name="synthetic"),
    )


def _blank_pdf(path: Path, pages: int = 1) -> None:
    document = fitz.open()
    for _ in range(pages):
        document.new_page()
    document.save(path)
    document.close()


def test_recursive_hierarchy_mirroring_utf8_and_duplicate_names(tmp_path: Path) -> None:
    source = tmp_path / "source"
    first = source / "Pôle A" / "Urologie"
    second = source / "Pôle B" / "طب"
    empty = source / "Pôle B" / "empty"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    empty.mkdir(parents=True)
    (first / "cours.txt").write_text("Français — cœur\nمرحبا", encoding="utf-8")
    (second / "cours.txt").write_text("نص عربي", encoding="utf-8")

    result = _run(_configuration(source, tmp_path))

    assert result.report.exported_count == 2
    assert (tmp_path / "output/Pôle A/Urologie/cours.txt").is_file()
    assert (tmp_path / "output/Pôle B/طب/cours.txt").is_file()
    assert (tmp_path / "output/Pôle B/empty").is_dir()
    value = (tmp_path / "output/Pôle A/Urologie/cours.txt").read_text(encoding="utf-8")
    assert "Français — cœur\nمرحبا" in value
    assert result.report.source_immutable


def test_pdf_page_order_rendering() -> None:
    source = "nested/course.pdf"
    pages = [
        NormalizedPage(
            number=1,
            location_type=LocationType.PAGE,
            blocks=[_block(source, LocationType.PAGE, 1, 1, "first page")],
        ),
        NormalizedPage(
            number=2,
            location_type=LocationType.PAGE,
            blocks=[_block(source, LocationType.PAGE, 2, 2, "second page")],
        ),
    ]

    rendered = render_normalized_document(_document(DocumentType.PDF, pages))

    assert rendered.page_or_slide_count == 2
    assert rendered.text.index("===== PAGE 1 =====") < rendered.text.index("first page")
    assert rendered.text.index("first page") < rendered.text.index("===== PAGE 2 =====")
    assert rendered.text.index("===== PAGE 2 =====") < rendered.text.index("second page")


def test_pptx_slide_title_content_and_notes_order() -> None:
    source = "nested/course.pptx"
    pages = [
        NormalizedPage(
            number=1,
            location_type=LocationType.SLIDE,
            blocks=[
                _block(source, LocationType.SLIDE, 1, 1, "Title one", BlockType.TITLE),
                _block(source, LocationType.SLIDE, 1, 2, "Body one"),
            ],
        ),
        NormalizedPage(
            number=2,
            location_type=LocationType.SLIDE,
            blocks=[
                _block(source, LocationType.SLIDE, 2, 3, "Title two", BlockType.TITLE),
                _block(source, LocationType.SLIDE, 2, 4, "Body two"),
            ],
        ),
    ]

    rendered = render_normalized_document(
        _document(DocumentType.POWERPOINT, pages), notes_by_slide={1: "Note one"}
    )

    assert rendered.text.index("===== SLIDE 1 =====") < rendered.text.index("Title one")
    assert rendered.text.index("Body one") < rendered.text.index("Note one")
    assert rendered.text.index("Note one") < rendered.text.index("===== SLIDE 2 =====")
    assert rendered.text.index("Title two") < rendered.text.index("Body two")


def test_docx_paragraph_list_and_table_order() -> None:
    source = "nested/course.docx"
    table = NormalizedTable(
        table_id="table-000001",
        row_count=2,
        column_count=2,
        cells=[
            NormalizedTableCell(row=0, column=0, text="A"),
            NormalizedTableCell(row=0, column=1, text="B"),
            NormalizedTableCell(row=1, column=0, text="1"),
            NormalizedTableCell(row=1, column=1, text="2"),
        ],
        source_reference=_reference(source, LocationType.DOCUMENT, None, "block-000003"),
    )
    page = NormalizedPage(
        number=None,
        location_type=LocationType.DOCUMENT,
        blocks=[
            _block(source, LocationType.DOCUMENT, None, 1, "Heading", BlockType.HEADING),
            _block(source, LocationType.DOCUMENT, None, 2, "Item", BlockType.LIST_ITEM),
            _block(
                source,
                LocationType.DOCUMENT,
                None,
                3,
                None,
                BlockType.TABLE,
                {"table_id": "table-000001"},
            ),
            _block(source, LocationType.DOCUMENT, None, 4, "Caption", BlockType.CAPTION),
        ],
    )

    rendered = render_normalized_document(_document(DocumentType.WORD, [page], tables=[table]))

    assert rendered.text.index("Heading") < rendered.text.index("- Item")
    assert rendered.text.index("- Item") < rendered.text.index("===== TABLE 1 =====")
    assert "A | B\n1 | 2" in rendered.text
    assert rendered.text.index("1 | 2") < rendered.text.index("Caption")


def test_same_folder_collision_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "course.pdf").write_bytes(b"pdf")
    (source / "course.pptx").write_bytes(b"pptx")

    plan = plan_output_paths(snapshot_source_tree(source).files)

    assert plan.output_by_source == {
        "course.pdf": "course__pdf.txt",
        "course.pptx": "course__pptx.txt",
    }
    assert plan.collisions == {"course.txt": ("course.pdf", "course.pptx")}


def test_unsupported_ppt_and_requires_ocr_are_reported_without_outputs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "legacy.ppt").write_bytes(b"legacy")
    _blank_pdf(source / "scan.pdf", pages=2)
    configuration = _configuration(source, tmp_path, dry_run=True)

    result = _run(configuration)

    statuses = {
        entry.source_relative_path: entry.export_status for entry in result.manifest.entries
    }
    assert statuses == {
        "legacy.ppt": ExportStatus.UNSUPPORTED,
        "scan.pdf": ExportStatus.REQUIRES_OCR,
    }
    assert result.report.requires_ocr_count == 1
    assert result.report.unsupported_count == 1
    assert result.report.proposed_text_output_count == 0
    assert not configuration.output_root.exists()
    assert not configuration.report_output_root.exists()


def test_empty_source_creates_no_text_output(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "empty.txt").write_bytes(b"")

    result = _run(_configuration(source, tmp_path))

    assert result.manifest.entries[0].export_status is ExportStatus.EMPTY
    assert not (tmp_path / "output/empty.txt").exists()
    assert (tmp_path / "output/export-manifest.json").is_file()


def test_txt_preserves_content_while_normalizing_line_endings(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "lines.txt").write_bytes("ligne  \r\nنهاية".encode())

    _run(_configuration(source, tmp_path))

    value = (tmp_path / "output/lines.txt").read_text(encoding="utf-8")
    assert value.endswith("===== SOURCE TEXT =====\n\nligne  \nنهاية")


def test_resume_validates_current_output_and_corruption_regenerates(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "lesson.txt").write_text("alpha", encoding="utf-8")
    _run(_configuration(source, tmp_path))
    output = tmp_path / "output/lesson.txt"
    initial_hash = sha256_file(output)

    resumed = _run(_configuration(source, tmp_path, resume=True))
    assert resumed.manifest.entries[0].export_status is ExportStatus.SKIPPED_CURRENT
    assert sha256_file(output) == initial_hash

    output.write_text("corrupt", encoding="utf-8")
    regenerated = _run(_configuration(source, tmp_path, resume=True))
    assert regenerated.manifest.entries[0].export_status is ExportStatus.EXPORTED
    assert "alpha" in output.read_text(encoding="utf-8")
    assert sha256_file(output) == initial_hash


def test_stale_source_regenerates_and_updates_identity(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    path = source / "lesson.txt"
    path.write_text("first", encoding="utf-8")
    first = _run(_configuration(source, tmp_path))
    first_identity = first.manifest.entries[0].export_identity
    path.write_text("second", encoding="utf-8")

    second = _run(_configuration(source, tmp_path, resume=True))

    assert second.manifest.entries[0].export_status is ExportStatus.EXPORTED
    assert second.manifest.entries[0].export_identity != first_identity
    assert "second" in (tmp_path / "output/lesson.txt").read_text(encoding="utf-8")


def test_dry_run_is_no_write_and_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "nested").mkdir(parents=True)
    (source / "nested/cours.txt").write_text("texte", encoding="utf-8")
    (source / "legacy.ppt").write_bytes(b"legacy")
    configuration = _configuration(source, tmp_path, dry_run=True)

    first = _run(configuration)
    second = _run(configuration)

    assert first.manifest.model_dump() == second.manifest.model_dump()
    assert first.report.model_dump() == second.report.model_dump()
    assert first.report.run_id == second.report.run_id
    assert not configuration.output_root.exists()
    assert not configuration.report_output_root.exists()


def test_atomic_validation_failure_preserves_existing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    path = source / "lesson.txt"
    path.write_text("stable", encoding="utf-8")
    configuration = _configuration(source, tmp_path)
    _run(configuration)
    output = tmp_path / "output/lesson.txt"
    original = output.read_bytes()

    def fail_validation(*args: object, **kwargs: object) -> str:
        raise ValueError("synthetic staged validation failure")

    monkeypatch.setattr("ingestion.text_tree.service.validate_text_export", fail_validation)
    result = _run(_configuration(source, tmp_path, overwrite=True))

    assert result.manifest.entries[0].export_status is ExportStatus.FAILED
    assert output.read_bytes() == original
    assert not list(output.parent.glob("*.staged"))


def test_output_validation_and_path_traversal_protection(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "lesson.txt").write_text("content", encoding="utf-8")
    result = _run(_configuration(source, tmp_path))
    entry = result.manifest.entries[0]
    output = tmp_path / "output/lesson.txt"

    header, body = parse_metadata_header(output.read_text(encoding="utf-8"))
    assert header["SOURCE_RELATIVE_PATH"] == "lesson.txt"
    assert body.startswith("===== SOURCE TEXT =====")
    assert entry.source_sha256 is not None
    assert (
        validate_text_export(
            output,
            output_root=tmp_path / "output",
            source_filename="lesson.txt",
            source_relative_path="lesson.txt",
            source_extension=".txt",
            source_sha256=entry.source_sha256,
            document_type="text",
            page_or_slide_count=None,
            expected_output_sha256=entry.output_sha256,
        )
        == entry.output_sha256
    )
    with pytest.raises(ValueError, match="stay below"):
        safe_output_path(tmp_path / "output", "../escape.txt")


def test_source_immutability_and_jobs_rejection(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    path = source / "lesson.txt"
    path.write_text("immutable", encoding="utf-8")
    before = sha256_file(path)

    result = _run(_configuration(source, tmp_path))

    assert result.report.source_immutable
    assert sha256_file(path) == before
    with pytest.raises(ValidationError, match="jobs must be 1"):
        _configuration(source, tmp_path, jobs=2)
