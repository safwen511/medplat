"""Deterministic evidence-span resolution from retained dataset source references."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ingestion.generation.models import GenerationSource, ProviderEvidenceDraft
from ingestion.normalization.models import SourceReference


class EvidenceChunk(Protocol):
    chunk_id: str
    text: str
    source_references: list[SourceReference]


class EvidenceResolutionError(ValueError):
    """Provider evidence identifiers cannot resolve to one exact retained span."""

    def __init__(self, message: str, *, code: str, details: dict[str, object]) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


@dataclass(frozen=True)
class ResolvedEvidenceSpan:
    chunk_id: str
    source_reference_block_ids: list[str]
    quotation: str
    source_references: list[SourceReference]


def resolve_chunk_evidence_span(
    chunk: EvidenceChunk,
    block_ids: list[str],
) -> ResolvedEvidenceSpan:
    """Resolve ordered contiguous block IDs to an exact substring of retained chunk text."""
    details: dict[str, object] = {"chunk_id": chunk.chunk_id, "block_ids": block_ids}
    if not block_ids:
        raise EvidenceResolutionError(
            "Evidence span requires at least one source-reference block ID.",
            code="empty_evidence_block_ids",
            details=details,
        )
    if len(block_ids) != len(set(block_ids)):
        raise EvidenceResolutionError(
            "Evidence span contains duplicate source-reference block IDs.",
            code="duplicate_evidence_block_ids",
            details=details,
        )

    reference_indexes: dict[str, int] = {}
    for index, reference in enumerate(chunk.source_references):
        if reference.block_id is not None:
            reference_indexes[reference.block_id] = index
    unknown = [block_id for block_id in block_ids if block_id not in reference_indexes]
    if unknown:
        raise EvidenceResolutionError(
            "Evidence block ID is absent from the selected chunk.",
            code="unknown_evidence_block_ids",
            details={**details, "unknown_block_ids": unknown},
        )

    indexes = [reference_indexes[block_id] for block_id in block_ids]
    if indexes != sorted(indexes):
        raise EvidenceResolutionError(
            "Evidence block IDs do not preserve canonical source-reference order.",
            code="reordered_evidence_block_ids",
            details={**details, "reference_indexes": indexes},
        )
    expected_indexes = list(range(indexes[0], indexes[-1] + 1))
    if indexes != expected_indexes:
        raise EvidenceResolutionError(
            "Evidence block IDs are noncontiguous in canonical source-reference order.",
            code="noncontiguous_evidence_block_ids",
            details={**details, "reference_indexes": indexes},
        )

    references = [chunk.source_references[index] for index in indexes]
    excerpts = [reference.source_excerpt for reference in references]
    if any(not excerpt for excerpt in excerpts):
        raise EvidenceResolutionError(
            "Evidence source reference has no retained source excerpt.",
            code="missing_evidence_source_excerpt",
            details=details,
        )

    span_start: int | None = None
    span_end: int | None = None
    cursor = 0
    for excerpt in excerpts:
        assert excerpt is not None
        # Chunk construction may trim whitespace at structural block boundaries while
        # retaining the canonical excerpt verbatim in the source reference. Resolve
        # that boundary-only difference deterministically, then always slice the
        # quotation from the retained chunk text itself.
        retained_excerpt = excerpt.strip()
        start = chunk.text.find(retained_excerpt, cursor)
        if start < 0:
            raise EvidenceResolutionError(
                "Evidence source excerpt cannot be located exactly in retained chunk text.",
                code="evidence_span_unmaterializable",
                details={**details, "source_excerpt": excerpt},
            )
        if span_start is None:
            span_start = start
        span_end = start + len(retained_excerpt)
        cursor = span_end
    assert span_start is not None and span_end is not None
    return ResolvedEvidenceSpan(
        chunk_id=chunk.chunk_id,
        source_reference_block_ids=list(block_ids),
        quotation=chunk.text[span_start:span_end],
        source_references=references,
    )


def resolve_provider_evidence(
    source: GenerationSource,
    evidence: ProviderEvidenceDraft,
) -> ResolvedEvidenceSpan:
    """Resolve provider identifiers only against deterministic selected source chunks."""
    selected = {chunk.chunk_id: chunk for chunk in source.selected_chunks}
    if evidence.chunk_id in source.excluded_chunk_ids:
        raise EvidenceResolutionError(
            "Provider cited an excluded source chunk.",
            code="excluded_evidence_chunk",
            details={"chunk_id": evidence.chunk_id},
        )
    chunk = selected.get(evidence.chunk_id)
    if chunk is None:
        raise EvidenceResolutionError(
            "Provider cited a chunk outside the selected source set.",
            code="provider_cited_unselected_chunk",
            details={"chunk_id": evidence.chunk_id},
        )
    return resolve_chunk_evidence_span(chunk, evidence.source_reference_block_ids)
