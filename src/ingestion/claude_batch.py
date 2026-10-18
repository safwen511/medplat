"""Bounded, resumable Claude Message Batches runs with append-only audit records.

A run lives in one directory (data/<year>/runs/<stage>/<run_id>/):

- items.jsonl    planned items: stable custom_id plus the stage's own metadata (no request bodies;
                 the stage rebuilds each request at submit time, so large inputs are not duplicated)
- batches.jsonl  one record per submitted batch (id, model, custom_ids, submitted_at)
- results.jsonl  append-only raw results: message, stop reason, usage and estimated cost per item

Nothing here spends money except `submit`, which callers run only on the owner's explicit go.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ingestion.library import PROJECT_ROOT

# Standard first-party prices in USD per million tokens (input, output, cache read). Cache writes
# with the default 5-minute TTL cost 1.25x input. The Batches API halves every token price.
PRICES: dict[str, tuple[float, float, float]] = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
}
CACHE_WRITE_FACTOR = 1.25
BATCH_FACTOR = 0.5
# API limits: 100,000 requests or 256 MB per batch; stay well below the size limit.
MAX_BATCH_REQUESTS = 100_000
MAX_BATCH_BYTES = 200 * 1024 * 1024
MAX_ATTEMPTS = 2
CUSTOM_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
RETRYABLE = {"expired", "canceled", "errored_server", "refusal", "max_tokens"}


def custom_id(prefix: str, key: str) -> str:
    """Stable request id for an item: the prefix plus a digest of the item's identity."""
    value = f"{prefix}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[: 63 - len(prefix)]}"
    if not CUSTOM_ID.fullmatch(value):
        raise ValueError(f"Invalid custom_id {value!r}.")
    return value


def cost_usd(model: str, usage: dict[str, Any], *, batch: bool = True) -> float | None:
    """Estimated cost of one response from its usage block; None for an unpriced model."""
    if model not in PRICES:
        return None
    input_price, output_price, cache_read_price = PRICES[model]
    total = (
        (usage.get("input_tokens") or 0) * input_price
        + (usage.get("cache_creation_input_tokens") or 0) * input_price * CACHE_WRITE_FACTOR
        + (usage.get("cache_read_input_tokens") or 0) * cache_read_price
        + (usage.get("output_tokens") or 0) * output_price
    ) / 1_000_000
    return total * BATCH_FACTOR if batch else total


def estimate_usd(model: str, input_tokens: int, output_tokens: int, *, batch: bool = True) -> float:
    """Rough cost of a planned request, without caching."""
    usage = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    estimate = cost_usd(model, usage, batch=batch)
    if estimate is None:
        raise ValueError(f"No price for model {model!r}.")
    return estimate


def load_api_key(env_file: Path = PROJECT_ROOT / ".env") -> bool:
    """Load ANTHROPIC_API_KEY from the Git-ignored .env file if it is not already set.

    Returns whether a key is available. The key is never printed or logged.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.strip().partition("=")
            if separator and name.strip() == "ANTHROPIC_API_KEY" and value.strip():
                os.environ["ANTHROPIC_API_KEY"] = value.strip().strip("'\"")
                return True
    return False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if path.is_file():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def _append_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def outcome(record: dict[str, Any]) -> str:
    """succeeded, refusal, max_tokens, errored_server, errored_invalid, expired, or canceled."""
    kind = str(record["type"])
    if kind == "succeeded":
        stop = record.get("stop_reason")
        return "succeeded" if stop not in {"refusal", "max_tokens"} else str(stop)
    if kind == "errored":
        invalid = record.get("error_type") == "invalid_request_error"
        return "errored_invalid" if invalid else "errored_server"
    return kind


@dataclass
class BatchRun:
    root: Path

    @property
    def items_path(self) -> Path:
        return self.root / "items.jsonl"

    @property
    def batches_path(self) -> Path:
        return self.root / "batches.jsonl"

    @property
    def results_path(self) -> Path:
        return self.root / "results.jsonl"

    # Planning -------------------------------------------------------------------------------

    def plan(self, items: list[dict[str, Any]]) -> int:
        """Record planned items (each with a unique `custom_id`); returns how many were new."""
        self.root.mkdir(parents=True, exist_ok=True)
        ids = [item["custom_id"] for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Planned items must have unique custom_ids.")
        known = {item["custom_id"] for item in self.items()}
        new = [item for item in items if item["custom_id"] not in known]
        _append_jsonl(self.items_path, new)
        return len(new)

    def items(self) -> list[dict[str, Any]]:
        return list(_read_jsonl(self.items_path))

    # State ----------------------------------------------------------------------------------

    def batches(self) -> list[dict[str, Any]]:
        return list(_read_jsonl(self.batches_path))

    def results(self) -> list[dict[str, Any]]:
        return list(_read_jsonl(self.results_path))

    def latest(self) -> dict[str, dict[str, Any]]:
        """The most recent result per custom_id."""
        latest: dict[str, dict[str, Any]] = {}
        for record in self.results():
            latest[record["custom_id"]] = record
        return latest

    def in_flight(self) -> set[str]:
        """custom_ids submitted in a batch whose results were not collected yet."""
        return {
            custom
            for batch in self.batches()
            if not batch.get("collected_at")
            for custom in batch["custom_ids"]
        }

    def pending(self, max_attempts: int = MAX_ATTEMPTS) -> list[dict[str, Any]]:
        """Items to submit: never attempted, or last outcome retryable and attempts remain."""
        attempts: dict[str, int] = {}
        for record in self.results():
            attempts[record["custom_id"]] = attempts.get(record["custom_id"], 0) + 1
        latest = self.latest()
        flying = self.in_flight()
        selected = []
        for item in self.items():
            custom = item["custom_id"]
            if custom in flying:
                continue
            if custom not in latest:
                selected.append(item)
            elif outcome(latest[custom]) in RETRYABLE and attempts[custom] < max_attempts:
                selected.append(item)
        return selected

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for record in self.latest().values():
            counts[outcome(record)] = counts.get(outcome(record), 0) + 1
        spent = sum(record.get("cost_usd") or 0.0 for record in self.results())
        return {
            "items": len(self.items()),
            "outcomes": counts,
            "in_flight": len(self.in_flight()),
            "pending": len(self.pending()),
            "spent_usd": round(spent, 4),
        }

    # API calls ------------------------------------------------------------------------------

    def submit(
        self,
        client: Any,
        build: Callable[[dict[str, Any]], dict[str, Any]],
        *,
        limit: int | None = None,
    ) -> list[str]:
        """Submit pending items (at most `limit`) as one or more batches. Spends money."""
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request

        selected = self.pending()[:limit] if limit is not None else self.pending()
        submitted: list[str] = []
        chunk: list[Any] = []
        chunk_ids: list[str] = []
        chunk_bytes = 0

        def flush() -> None:
            nonlocal chunk, chunk_ids, chunk_bytes
            if not chunk:
                return
            batch = client.messages.batches.create(requests=chunk)
            record = {
                "batch_id": batch.id,
                "custom_ids": chunk_ids,
                "model": chunk[0]["params"]["model"],
                "submitted_at": _now(),
            }
            _append_jsonl(self.batches_path, [record])
            submitted.append(batch.id)
            chunk, chunk_ids, chunk_bytes = [], [], 0

        for item in selected:
            params = build(item)
            size = len(json.dumps(params))
            if chunk and (len(chunk) >= MAX_BATCH_REQUESTS or chunk_bytes + size > MAX_BATCH_BYTES):
                flush()
            chunk.append(
                Request(
                    custom_id=item["custom_id"],
                    params=MessageCreateParamsNonStreaming(**params),  # type: ignore[typeddict-item]
                )
            )
            chunk_ids.append(item["custom_id"])
            chunk_bytes += size
        flush()
        return submitted

    def collect(self, client: Any) -> dict[str, str]:
        """Append the results of every ended, uncollected batch; returns batch statuses."""
        statuses: dict[str, str] = {}
        records = self.batches()
        changed = False
        for record in records:
            if record.get("collected_at"):
                statuses[record["batch_id"]] = "collected"
                continue
            batch = client.messages.batches.retrieve(record["batch_id"])
            statuses[record["batch_id"]] = str(batch.processing_status)
            if batch.processing_status != "ended":
                continue
            results = []
            for entry in client.messages.batches.results(record["batch_id"]):
                results.append(self._result_record(record, entry))
            _append_jsonl(self.results_path, results)
            record["collected_at"] = _now()
            changed = True
        if changed:
            temporary = self.batches_path.with_suffix(".jsonl.partial")
            temporary.write_text(
                "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records),
                encoding="utf-8",
            )
            temporary.replace(self.batches_path)
        return statuses

    @staticmethod
    def _result_record(batch: dict[str, Any], entry: Any) -> dict[str, Any]:
        result = entry.result
        record: dict[str, Any] = {
            "custom_id": entry.custom_id,
            "batch_id": batch["batch_id"],
            "type": result.type,
            "collected_at": _now(),
        }
        if result.type == "succeeded":
            message = result.message
            usage = message.usage.to_dict()
            record.update(
                model=message.model,
                stop_reason=message.stop_reason,
                stop_details=(
                    message.stop_details.to_dict()
                    if getattr(message, "stop_details", None)
                    else None
                ),
                usage=usage,
                cost_usd=cost_usd(message.model, usage),
                message=message.to_dict(),
            )
        elif result.type == "errored":
            record.update(
                error_type=result.error.error.type,
                error=result.error.error.message,
                request_id=result.error.request_id,
            )
        return record


def message_text(record: dict[str, Any]) -> str:
    """Concatenated text blocks of a succeeded result record."""
    return "".join(
        block.get("text", "")
        for block in record["message"]["content"]
        if block.get("type") == "text"
    )
