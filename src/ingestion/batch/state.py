"""Atomic persistence for resumable batch and per-document state."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ingestion.batch.models import (
    BatchDocumentStatus,
    BatchPlan,
    BatchState,
    DocumentBatchState,
)
from ingestion.output import write_json_atomic


def batch_directory(plan: BatchPlan) -> Path:
    return plan.configuration.reports_root / plan.batch_id


def initial_state(plan: BatchPlan) -> BatchState:
    return BatchState(
        batch_id=plan.batch_id,
        documents=[
            DocumentBatchState(
                sequence_number=item.sequence_number,
                source_relative_path=item.source_relative_path,
                source_sha256=item.sha256,
                status=(
                    BatchDocumentStatus.UNSUPPORTED
                    if item.skip_reason == "unsupported_for_parsing"
                    else BatchDocumentStatus.PLANNED
                ),
            )
            for item in plan.documents
        ],
    )


def load_or_initialize_state(plan: BatchPlan) -> BatchState:
    path = batch_directory(plan) / "batch-state.json"
    if not plan.configuration.resume or not path.is_file():
        return initial_state(plan)
    state = BatchState.model_validate_json(path.read_text(encoding="utf-8"))
    if state.batch_id != plan.batch_id:
        raise ValueError("Persisted batch state belongs to another deterministic plan.")
    expected = [
        (item.sequence_number, item.source_relative_path, item.sha256) for item in plan.documents
    ]
    actual = [
        (item.sequence_number, item.source_relative_path, item.source_sha256)
        for item in state.documents
    ]
    if actual != expected:
        raise ValueError("Persisted batch state does not match the current source plan.")
    return state


def persist_plan(plan: BatchPlan) -> Path:
    path = batch_directory(plan) / "batch-plan.json"
    write_json_atomic(path, plan.model_dump(mode="json"))
    return path


def persist_state(plan: BatchPlan, state: BatchState) -> Path:
    state.updated_at = datetime.now(timezone.utc)
    path = batch_directory(plan) / "batch-state.json"
    write_json_atomic(path, state.model_dump(mode="json"))
    return path


def persist_document_state(plan: BatchPlan, document: DocumentBatchState) -> Path:
    prefix = document.source_sha256[:12]
    path = batch_directory(plan) / "documents" / f"{document.sequence_number:04d}-{prefix}.json"
    write_json_atomic(path, document.model_dump(mode="json"))
    return path
