"""Atomic serialization for chunk collections and AI-ready datasets."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from ingestion.chunking.models import ChunkCollection, ChunkingReport
from ingestion.chunking.validation import (
    validate_chunk_collection_file,
    validate_chunks_jsonl,
)
from ingestion.datasets.models import AIReadyDataset
from ingestion.datasets.validation import validate_dataset_file


class DerivedOutputExistsError(FileExistsError):
    """Raised when validated downstream output is protected from overwrite."""


def write_chunk_outputs(
    canonical_path: Path,
    collection: ChunkCollection,
    *,
    force: bool = False,
) -> Path:
    """Write and validate all chunk artifacts before atomic finalization."""
    _ensure_safe_canonical_path(canonical_path)
    final = canonical_path.parent / "chunks"
    temporary = canonical_path.parent / f".chunks.{uuid4().hex}.tmp"
    backup = canonical_path.parent / f".chunks.{uuid4().hex}.backup"
    if final.exists() and not force:
        raise DerivedOutputExistsError("Chunk output already exists; use --force to replace it.")
    temporary.mkdir()
    try:
        chunks_json = temporary / "chunks.json"
        chunks_jsonl = temporary / "chunks.jsonl"
        chunks_markdown = temporary / "chunks.md"
        report_json = temporary / "chunking-report.json"
        chunks_json.write_text(collection.model_dump_json(indent=2) + "\n", encoding="utf-8")
        with chunks_jsonl.open("w", encoding="utf-8", newline="\n") as stream:
            for chunk in collection.chunks:
                stream.write(chunk.model_dump_json() + "\n")
        chunks_markdown.write_text(_chunks_markdown(collection), encoding="utf-8")
        output_paths = [
            str(final / "chunks.json"),
            str(final / "chunks.jsonl"),
            str(final / "chunks.md"),
            str(final / "chunking-report.json"),
        ]
        report = ChunkingReport(
            start_time=collection.generated_at,
            completion_time=collection.generated_at,
            status="partial_success" if collection.warnings else "success",
            configuration=collection.chunking_configuration,
            statistics=collection.processing_statistics,
            exclusions=collection.excluded_blocks,
            exact_duplicates=collection.exact_duplicates,
            unassociated_table_ids=collection.unassociated_table_ids,
            unassociated_asset_ids=collection.unassociated_asset_ids,
            warnings=collection.warnings,
            errors=collection.errors,
            output_paths=output_paths,
        )
        report_json.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        validated = validate_chunk_collection_file(chunks_json)
        jsonl_chunks = validate_chunks_jsonl(chunks_jsonl)
        ChunkingReport.model_validate_json(report_json.read_text(encoding="utf-8"))
        if [chunk.chunk_id for chunk in jsonl_chunks] != [
            chunk.chunk_id for chunk in validated.chunks
        ]:
            raise ValueError("JSON and JSONL chunk ordering differs.")
        _finalize_directory(temporary, final, backup)
        return final
    except Exception:
        _cleanup_or_restore(temporary, final, backup)
        raise


def write_dataset_output(
    canonical_path: Path,
    dataset: AIReadyDataset,
    *,
    force: bool = False,
) -> Path:
    """Write and validate the complete dataset through a sibling directory."""
    _ensure_safe_canonical_path(canonical_path)
    final = canonical_path.parent / "datasets"
    temporary = canonical_path.parent / f".datasets.{uuid4().hex}.tmp"
    backup = canonical_path.parent / f".datasets.{uuid4().hex}.backup"
    if final.exists() and not force:
        raise DerivedOutputExistsError("Dataset output already exists; use --force to replace it.")
    temporary.mkdir()
    try:
        path = temporary / "ai-ready-dataset.json"
        path.write_text(dataset.model_dump_json(indent=2) + "\n", encoding="utf-8")
        validate_dataset_file(path)
        _finalize_directory(temporary, final, backup)
        return final
    except Exception:
        _cleanup_or_restore(temporary, final, backup)
        raise


def _chunks_markdown(collection: ChunkCollection) -> str:
    lines = [f"# Chunks for {collection.document_title or collection.source_relative_path}", ""]
    for chunk in collection.chunks:
        location = _location_label(
            chunk.location_type.value,
            chunk.page_or_slide_start,
            chunk.page_or_slide_end,
        )
        lines.extend(
            [
                f"## {chunk.chunk_id}",
                "",
                f"- Type: `{chunk.chunk_type.value}`",
                f"- Section: {' > '.join(chunk.section_path) or '(none)'}",
                f"- Location: {location}",
                f"- Tables: {', '.join(chunk.table_ids) or '(none)'}",
                f"- Assets: {', '.join(chunk.asset_ids) or '(none)'}",
                f"- Warnings: {'; '.join(chunk.warnings) or '(none)'}",
                "",
                chunk.text,
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _location_label(location_type: str, start: int | None, end: int | None) -> str:
    if start is None:
        return location_type
    return f"{location_type} {start}" if start == end else f"{location_type}s {start}-{end}"


def _ensure_safe_canonical_path(canonical_path: Path) -> None:
    if canonical_path.name != "document.json":
        raise ValueError("Input must be a canonical document.json file.")
    source_root = Path("pdfsrc").resolve()
    resolved = canonical_path.resolve()
    if resolved == source_root or resolved.is_relative_to(source_root):
        raise ValueError("Derived output must never be written inside pdfsrc.")


def _finalize_directory(temporary: Path, final: Path, backup: Path) -> None:
    if final.exists():
        final.rename(backup)
    temporary.rename(final)
    if backup.exists():
        shutil.rmtree(backup)


def _cleanup_or_restore(temporary: Path, final: Path, backup: Path) -> None:
    if temporary.exists():
        shutil.rmtree(temporary)
    if backup.exists() and not final.exists():
        backup.rename(final)
