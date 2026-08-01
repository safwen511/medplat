from __future__ import annotations

import csv
import json
from hashlib import sha256
from pathlib import Path

import fitz

from ingestion.hashing import sha256_file
from ingestion.models import DocumentClassification
from ingestion.reports import duplicate_groups, write_reports
from ingestion.scanner import discover_documents, inspect_library, inspect_path


def make_text_pdf(path: Path, text: str = "Clinical teaching document") -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def test_recursive_discovery_preserves_relative_paths(tmp_path: Path) -> None:
    nested = tmp_path / "course" / "week-1"
    nested.mkdir(parents=True)
    (nested / "notes.txt").write_text("notes", encoding="utf-8")
    (tmp_path / "root.md").write_text("root", encoding="utf-8")

    paths = discover_documents(tmp_path)

    assert [path.relative_to(tmp_path).as_posix() for path in paths] == [
        "course/week-1/notes.txt",
        "root.md",
    ]


def test_sha256_file_matches_known_digest(tmp_path: Path) -> None:
    path = tmp_path / "large.bin"
    content = b"medplat" * 200_000
    path.write_bytes(content)

    assert sha256_file(path, chunk_size=17) == sha256(content).hexdigest()


def test_pdf_inspection_extracts_pdf_metrics(tmp_path: Path) -> None:
    path = tmp_path / "lesson.pdf"
    make_text_pdf(path, "Cardiology lesson")

    result = inspect_path(path, tmp_path)

    assert result.relative_path == "lesson.pdf"
    assert result.detected_type == "PDF"
    assert result.mime_type == "application/pdf"
    assert result.readable is True
    assert result.encrypted is False
    assert result.page_count == 1
    assert result.image_count == 0
    assert result.extractable_character_count is not None
    assert result.extractable_character_count >= len("Cardiology lesson")
    assert result.average_characters_per_page_or_slide == result.extractable_character_count
    assert result.classification is DocumentClassification.NATIVE_TEXT


def test_non_pdf_is_metadata_only_and_unsupported(tmp_path: Path) -> None:
    path = tmp_path / "slides.pptx"
    path.write_bytes(b"not actually a presentation")

    result = inspect_path(path, tmp_path)

    assert result.detected_type == "Microsoft PowerPoint"
    assert result.file_size == len(b"not actually a presentation")
    assert result.sha256 == sha256(b"not actually a presentation").hexdigest()
    assert result.classification is DocumentClassification.UNSUPPORTED_FOR_NOW
    assert result.page_count is None
    assert result.error is None


def test_damaged_pdf_does_not_stop_scan(tmp_path: Path) -> None:
    (tmp_path / "broken.pdf").write_bytes(b"not a pdf")
    (tmp_path / "notes.txt").write_text("still inspected", encoding="utf-8")

    report = inspect_library(tmp_path)

    assert report.inspected_count == 2
    by_name = {document.filename: document for document in report.documents}
    assert by_name["broken.pdf"].classification is DocumentClassification.UNREADABLE
    assert by_name["broken.pdf"].error is not None
    assert by_name["notes.txt"].classification is DocumentClassification.UNSUPPORTED_FOR_NOW


def test_report_generation_and_duplicate_detection(tmp_path: Path) -> None:
    library = tmp_path / "library"
    output = tmp_path / "reports"
    library.mkdir()
    (library / "a.txt").write_text("same", encoding="utf-8")
    (library / "b.txt").write_text("same", encoding="utf-8")
    make_text_pdf(library / "lesson.pdf")

    report = inspect_library(library)
    written = write_reports(report, output)

    assert len(written) == 5
    assert all(path.is_file() for path in written)
    manifest = json.loads((output / "library-manifest.json").read_text(encoding="utf-8"))
    assert manifest["discovered_count"] == 3
    assert len(manifest["documents"]) == 3
    with (output / "library-manifest.csv").open(encoding="utf-8", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 3
    groups = duplicate_groups(report)
    assert len(groups) == 1
    assert groups[0].relative_paths == ["a.txt", "b.txt"]
    duplicates = json.loads((output / "duplicate-files.json").read_text(encoding="utf-8"))
    assert duplicates[0]["relative_paths"] == ["a.txt", "b.txt"]
    unsupported = json.loads((output / "unsupported-files.json").read_text(encoding="utf-8"))
    assert {entry["filename"] for entry in unsupported} == {"a.txt", "b.txt"}


def test_limit_applies_after_recursive_discovery(tmp_path: Path) -> None:
    for name in ("c.txt", "a.txt", "b.txt"):
        (tmp_path / name).write_text(name, encoding="utf-8")

    report = inspect_library(tmp_path, limit=2)

    assert report.discovered_count == 3
    assert report.inspected_count == 2
    assert [document.filename for document in report.documents] == ["a.txt", "b.txt"]
