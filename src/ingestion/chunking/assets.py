"""Deterministic canonical table and asset association."""

from __future__ import annotations

from collections.abc import Iterable

from ingestion.chunking.models import DocumentChunk
from ingestion.chunking.sizing import normalize_text
from ingestion.normalization.models import (
    NormalizedAsset,
    NormalizedBlock,
    NormalizedDocument,
    NormalizedTable,
)


def associate_tables_and_assets(
    document: NormalizedDocument,
    chunks: list[DocumentChunk],
    block_by_id: dict[str, NormalizedBlock],
) -> tuple[list[str], list[str], list[str]]:
    """Associate objects only when canonical evidence selects one chunk."""
    warnings: list[str] = []
    chunk_by_block = {block_id: chunk for chunk in chunks for block_id in chunk.block_ids}
    associated_tables: set[str] = set()
    associated_assets: set[str] = set()

    for table in document.tables:
        chunk = _explicit_table_chunk(table, chunk_by_block)
        method = "explicit_block_reference"
        if chunk is None:
            chunk = _caption_chunk(table.caption, table.page_or_slide_number, chunks, block_by_id)
            method = "caption_relationship"
        if chunk is None:
            chunk = _only_chunk_at_location(table.page_or_slide_number, chunks)
            method = "unique_same_location"
        if chunk is not None:
            chunk.table_ids.append(table.table_id)
            _record_evidence(chunk, table.table_id, method)
            associated_tables.add(table.table_id)

    for asset in document.assets:
        chunk = _explicit_asset_chunk(asset.asset_id, chunks, block_by_id)
        method = "explicit_block_reference"
        if chunk is None:
            chunk = _caption_chunk(asset.caption, asset.source_page_or_slide, chunks, block_by_id)
            method = "caption_relationship"
        if chunk is None and asset.bounding_box is not None:
            chunk = _spatially_nearest_chunk(asset, chunks, block_by_id)
            method = "spatial_nearest"
        if chunk is None:
            chunk = _only_chunk_at_location(asset.source_page_or_slide, chunks)
            method = "unique_same_location"
        if chunk is not None:
            chunk.asset_ids.append(asset.asset_id)
            _record_evidence(chunk, asset.asset_id, method)
            associated_assets.add(asset.asset_id)

    unassociated_tables = sorted(
        table.table_id for table in document.tables if table.table_id not in associated_tables
    )
    unassociated_assets = sorted(
        asset.asset_id for asset in document.assets if asset.asset_id not in associated_assets
    )
    if unassociated_tables:
        warnings.append(f"{len(unassociated_tables)} table(s) lacked reliable chunk association.")
    if unassociated_assets:
        warnings.append(f"{len(unassociated_assets)} asset(s) lacked reliable chunk association.")
    return unassociated_tables, unassociated_assets, warnings


def _explicit_table_chunk(
    table: NormalizedTable, chunk_by_block: dict[str, DocumentChunk]
) -> DocumentChunk | None:
    block_id = table.source_reference.block_id
    return chunk_by_block.get(block_id) if block_id else None


def _explicit_asset_chunk(
    asset_id: str,
    chunks: list[DocumentChunk],
    block_by_id: dict[str, NormalizedBlock],
) -> DocumentChunk | None:
    matches = [
        chunk
        for chunk in chunks
        if any(
            block_by_id[block_id].metadata.get("asset_id") == asset_id
            for block_id in chunk.block_ids
        )
    ]
    return matches[0] if len(matches) == 1 else None


def _caption_chunk(
    caption: str | None,
    location: int | None,
    chunks: list[DocumentChunk],
    block_by_id: dict[str, NormalizedBlock],
) -> DocumentChunk | None:
    if not caption:
        return None
    target = normalize_text(caption)
    matches = [
        chunk
        for chunk in chunks
        if _contains_location(chunk, location)
        and any(
            normalize_text(block_by_id[block_id].text or "") == target
            for block_id in chunk.block_ids
        )
    ]
    return matches[0] if len(matches) == 1 else None


def _spatially_nearest_chunk(
    asset: NormalizedAsset,
    chunks: list[DocumentChunk],
    block_by_id: dict[str, NormalizedBlock],
) -> DocumentChunk | None:
    if asset.bounding_box is None:
        return None
    asset_center = (asset.bounding_box.top + asset.bounding_box.bottom) / 2
    scored: list[tuple[float, int, DocumentChunk]] = []
    for index, chunk in enumerate(chunks):
        if not _contains_location(chunk, asset.source_page_or_slide):
            continue
        distances = [
            abs(asset_center - (block.bounding_box.top + block.bounding_box.bottom) / 2)
            for block_id in chunk.block_ids
            for block in [block_by_id[block_id]]
            if block.bounding_box is not None
            and block.bounding_box.coordinate_origin == asset.bounding_box.coordinate_origin
        ]
        if distances:
            scored.append((min(distances), index, chunk))
    scored.sort(key=lambda value: (value[0], value[1]))
    if not scored or (len(scored) > 1 and scored[0][0] == scored[1][0]):
        return None
    return scored[0][2]


def _only_chunk_at_location(
    location: int | None, chunks: Iterable[DocumentChunk]
) -> DocumentChunk | None:
    if location is None:
        return None
    matches = [chunk for chunk in chunks if _contains_location(chunk, location)]
    return matches[0] if len(matches) == 1 else None


def _contains_location(chunk: DocumentChunk, location: int | None) -> bool:
    if location is None:
        return False
    start = chunk.page_or_slide_start
    end = chunk.page_or_slide_end
    return start is not None and end is not None and start <= location <= end


def _record_evidence(chunk: DocumentChunk, object_id: str, method: str) -> None:
    evidence = chunk.metadata.setdefault("association_evidence", {})
    if isinstance(evidence, dict):
        evidence[object_id] = method
