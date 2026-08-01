"""Retry and resume selection rules independent of document execution."""

from ingestion.batch.models import (
    BatchConfiguration,
    BatchDocumentStatus,
    DocumentBatchState,
    PlannedDocument,
)


def should_execute(
    planned: PlannedDocument,
    state: DocumentBatchState,
    configuration: BatchConfiguration,
) -> tuple[bool, str | None]:
    if planned.skip_reason == "unsupported_for_parsing":
        return False, "unsupported_for_parsing"
    if planned.skip_reason == "already_complete" and not configuration.force_rebuild:
        return False, "already_complete"
    if configuration.retry_failures:
        if state.status not in {BatchDocumentStatus.FAILED, BatchDocumentStatus.INTERRUPTED}:
            return False, "not_failed_or_interrupted"
        if state.retry_count >= configuration.maximum_retries:
            return False, "maximum_retry_count_reached"
        return True, None
    if state.status in {BatchDocumentStatus.FAILED, BatchDocumentStatus.INTERRUPTED}:
        return False, "explicit_retry_required"
    if (
        state.status
        in {
            BatchDocumentStatus.SUCCEEDED,
            BatchDocumentStatus.SUCCEEDED_WITH_WARNINGS,
        }
        and not configuration.force_rebuild
    ):
        return False, "already_complete"
    return True, None
