"""Deterministic selection of validated generation-eligible source chunks."""

from __future__ import annotations

from pathlib import Path

from ingestion.datasets.models import AIReadyDataset
from ingestion.generation.models import (
    GenerationConfiguration,
    GenerationSource,
    SourceChunkReference,
)
from ingestion.hashing import sha256_file

_TYPE_PRIORITY = {
    "paragraph_group": 0,
    "table_context": 1,
    "list": 2,
    "section": 3,
    "subsection": 4,
    "document_preamble": 5,
    "orphan_content": 6,
    "formula_context": 7,
    "figure_context": 8,
}


def select_generation_source(
    dataset: AIReadyDataset,
    dataset_path: Path,
    configuration: GenerationConfiguration,
) -> GenerationSource:
    """Select a minimal stable evidence set without mutating the dataset."""
    eligible = [chunk for chunk in dataset.chunks if chunk.eligible_for_generation]
    ineligible = [chunk for chunk in dataset.chunks if not chunk.eligible_for_generation]
    topic_terms = set(configuration.topic.casefold().split()) if configuration.topic else set()

    def rank(chunk: object) -> tuple[int, int, int, int, str]:
        from ingestion.chunking.models import DocumentChunk

        item = DocumentChunk.model_validate(chunk)
        metadata_text = " ".join(
            [item.section_title or "", *item.section_path, *item.parent_section_titles]
        ).casefold()
        match_count = sum(term in metadata_text for term in topic_terms)
        substantive = 0 if item.character_count >= 100 else 1
        return (
            -match_count,
            substantive,
            _TYPE_PRIORITY.get(item.chunk_type.value, 99),
            item.chunk_index,
            item.chunk_id,
        )

    ordered = sorted(eligible, key=rank)
    selected: list[SourceChunkReference] = []
    selected_ids: set[str] = set()
    seen_hashes: set[str] = set()
    selected_characters = 0
    selected_tokens = 0
    exclusion_reasons: dict[str, str] = {
        chunk.chunk_id: "ineligible:" + ",".join(chunk.generation_exclusion_reasons)
        for chunk in ineligible
    }
    for chunk in ordered:
        if chunk.normalized_text_hash in seen_hashes:
            exclusion_reasons[chunk.chunk_id] = "duplicate_normalized_text"
            continue
        if len(selected) >= configuration.count:
            exclusion_reasons[chunk.chunk_id] = "not_needed_for_requested_count"
            continue
        if (
            selected_characters + chunk.character_count > configuration.maximum_source_characters
            or selected_tokens + chunk.token_estimate > configuration.maximum_source_tokens
        ):
            exclusion_reasons[chunk.chunk_id] = "source_budget_exceeded"
            continue
        selected.append(
            SourceChunkReference(
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                chunk_type=chunk.chunk_type.value,
                text=chunk.text,
                normalized_text_hash=chunk.normalized_text_hash,
                character_count=chunk.character_count,
                token_estimate=chunk.token_estimate,
                source_references=chunk.source_references,
            )
        )
        selected_ids.add(chunk.chunk_id)
        seen_hashes.add(chunk.normalized_text_hash)
        selected_characters += chunk.character_count
        selected_tokens += chunk.token_estimate
    if len(selected) < configuration.count:
        raise ValueError(
            "Source budget and eligibility must permit at least one unique chunk "
            "per requested item."
        )
    for chunk in eligible:
        if chunk.chunk_id not in selected_ids and chunk.chunk_id not in exclusion_reasons:
            exclusion_reasons[chunk.chunk_id] = "not_selected"
    excluded_ids = sorted(exclusion_reasons)
    return GenerationSource(
        document_id=dataset.document_id,
        source_sha256=dataset.source_sha256,
        source_relative_path=dataset.source_relative_path,
        dataset_path=str(dataset_path),
        dataset_sha256=sha256_file(dataset_path),
        dataset_schema_version=dataset.dataset_schema_version,
        eligible_chunk_count=len(eligible),
        ineligible_chunk_count=len(ineligible),
        selected_chunks=selected,
        excluded_chunk_ids=excluded_ids,
        exclusion_reasons=dict(sorted(exclusion_reasons.items())),
        selected_character_count=selected_characters,
        selected_token_estimate=selected_tokens,
        prompt_character_estimate=0,
        prompt_token_estimate=0,
    )
