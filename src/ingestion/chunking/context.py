"""Source-grounded section and neighboring-context construction."""

from __future__ import annotations

from ingestion.chunking.models import DocumentChunk
from ingestion.chunking.sizing import short_leading_context, short_trailing_context
from ingestion.normalization.models import NormalizedSection


def section_titles(
    section_id: str | None, sections: dict[str, NormalizedSection]
) -> tuple[list[str], list[str]]:
    """Return root-to-leaf path and parent-only titles without inventing hierarchy."""
    if section_id is None:
        return [], []
    lineage: list[NormalizedSection] = []
    seen: set[str] = set()
    current = sections.get(section_id)
    while current is not None and current.section_id not in seen:
        seen.add(current.section_id)
        lineage.append(current)
        current = sections.get(current.parent_section_id) if current.parent_section_id else None
    titles = [section.title for section in reversed(lineage)]
    return titles, titles[:-1]


def apply_neighbor_context(chunks: list[DocumentChunk], maximum_per_side: int) -> None:
    """Attach short exact excerpts only across structurally related neighbors."""
    for index, chunk in enumerate(chunks):
        if index > 0:
            previous = chunks[index - 1]
            if _related(previous, chunk):
                chunk.preceding_context = short_trailing_context(previous.text, maximum_per_side)
        if index + 1 < len(chunks):
            following = chunks[index + 1]
            if _related(chunk, following):
                chunk.following_context = short_leading_context(following.text, maximum_per_side)


def _related(left: DocumentChunk, right: DocumentChunk) -> bool:
    if left.section_id is not None and left.section_id == right.section_id:
        return True
    if left.section_id is None and right.section_id is None:
        if left.location_type is not right.location_type:
            return False
        if left.location_type.value == "document":
            return True
        return left.page_or_slide_end == right.page_or_slide_start
    return False
