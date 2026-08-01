"""Construct a self-contained AI-ready package from canonical chunks."""

from __future__ import annotations

from ingestion.chunking.models import ChunkCollection
from ingestion.datasets.models import AIReadyDataset
from ingestion.normalization.models import NormalizedDocument


def build_ai_ready_dataset(
    document: NormalizedDocument, collection: ChunkCollection
) -> AIReadyDataset:
    """Package canonical chunks without interpretation or generated content."""
    if collection.document_id != document.document_id:
        raise ValueError("Chunk collection does not belong to the canonical document.")
    if collection.source_sha256 != document.sha256:
        raise ValueError("Chunk collection source hash does not match the canonical document.")
    table_by_id = {table.table_id: table for table in collection.tables}
    asset_by_id = {asset.asset_id: asset for asset in collection.assets}
    return AIReadyDataset(
        document_id=document.document_id,
        source_sha256=document.sha256,
        source_relative_path=document.source_relative_path,
        document_type=document.document_type,
        document_title=document.title,
        language=document.language,
        generation_timestamp=collection.generated_at,
        chunking_configuration=collection.chunking_configuration,
        chunk_count=collection.chunk_count,
        chunks=collection.chunks,
        tables=collection.tables,
        assets=collection.assets,
        excluded_blocks=collection.excluded_blocks,
        exact_duplicates=collection.exact_duplicates,
        unassociated_tables=[
            table_by_id[table_id]
            for table_id in collection.unassociated_table_ids
            if table_id in table_by_id
        ],
        unassociated_assets=[
            asset_by_id[asset_id]
            for asset_id in collection.unassociated_asset_ids
            if asset_id in asset_by_id
        ],
        warnings=collection.warnings,
        errors=collection.errors,
        processing_statistics=collection.processing_statistics,
        provenance_metadata={
            "canonical_document_id": document.document_id,
            "canonical_source_relative_path": document.source_relative_path,
            "canonical_parser_name": document.processing.parser_name,
            "canonical_parser_version": document.processing.parser_version,
            "source_references_preserved": True,
            "generated_content_present": False,
        },
    )
