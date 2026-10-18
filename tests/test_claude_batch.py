from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ingestion.claude_batch import BatchRun, cost_usd, custom_id, load_api_key, message_text


class Dumpable(SimpleNamespace):
    def to_dict(self) -> dict[str, Any]:
        return {
            key: value.to_dict() if isinstance(value, Dumpable) else value
            for key, value in vars(self).items()
        }


def message(text: str, stop_reason: str = "end_turn") -> Dumpable:
    return Dumpable(
        model="claude-opus-5-5",
        stop_reason=stop_reason,
        stop_details=None,
        usage=Dumpable(input_tokens=1000, output_tokens=500),
        content=[{"type": "text", "text": text}],
    )


class FakeBatches:
    def __init__(self, outcomes: dict[str, list[Dumpable]]) -> None:
        self.outcomes = outcomes
        self.created: list[list[Any]] = []

    def create(self, requests: list[Any]) -> SimpleNamespace:
        self.created.append(requests)
        return SimpleNamespace(id=f"batch-{len(self.created)}")

    def retrieve(self, batch_id: str) -> SimpleNamespace:
        return SimpleNamespace(processing_status="ended")

    def results(self, batch_id: str) -> list[SimpleNamespace]:
        requests = self.created[int(batch_id.split("-")[1]) - 1]
        return [
            SimpleNamespace(
                custom_id=request["custom_id"],
                result=SimpleNamespace(
                    type="succeeded", message=self.outcomes[request["custom_id"]].pop(0)
                ),
            )
            for request in requests
        ]


def fake_client(outcomes: dict[str, list[Dumpable]]) -> SimpleNamespace:
    return SimpleNamespace(messages=SimpleNamespace(batches=FakeBatches(outcomes)))


def build(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": "claude-opus-5-5",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": item["prompt"]}],
    }


def test_custom_id_is_stable_and_valid() -> None:
    first = custom_id("vision", "a/b.pdf#3")
    assert first == custom_id("vision", "a/b.pdf#3")
    assert first != custom_id("vision", "a/b.pdf#4")
    assert len(first) <= 64 and first.startswith("vision-")


def test_cost_applies_batch_discount_and_cache_prices() -> None:
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    assert cost_usd("claude-opus-5-5", usage, batch=False) == pytest.approx(24.0)
    assert cost_usd("claude-opus-5-5", usage) == pytest.approx(12.0)
    cached = {"cache_read_input_tokens": 1_000_000, "cache_creation_input_tokens": 1_000_000}
    assert cost_usd("claude-opus-5-5", cached, batch=False) == pytest.approx(0.20 + 5.0)
    assert cost_usd("unknown-model", usage) is None


def test_run_submits_collects_and_retries_refusals_once(tmp_path: Path) -> None:
    run = BatchRun(tmp_path / "run")
    items = [{"custom_id": custom_id("t", key), "prompt": key} for key in ("a", "b")]
    assert run.plan(items) == 2
    assert run.plan(items) == 0
    a, b = (item["custom_id"] for item in items)
    client = fake_client(
        {a: [message("ok a")], b: [message("", "refusal"), message("", "refusal")]}
    )

    assert run.submit(client, build) == ["batch-1"]
    assert run.pending() == []
    assert run.collect(client) == {"batch-1": "ended"}
    assert message_text(run.latest()[a]) == "ok a"
    assert [item["custom_id"] for item in run.pending()] == [b]

    run.submit(client, build)
    run.collect(client)
    assert run.pending() == []
    summary = run.summary()
    assert summary["outcomes"] == {"succeeded": 1, "refusal": 1}
    assert summary["spent_usd"] == pytest.approx(
        3 * cost_usd("claude-opus-5-5", {"input_tokens": 1000, "output_tokens": 500})
    )
    assert len(run.results()) == 3


def test_api_key_is_read_from_env_file_without_overriding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env = tmp_path / ".env"
    assert load_api_key(env) is False
    env.write_text("OTHER=1\nANTHROPIC_API_KEY='sk-test'\n", encoding="utf-8")
    assert load_api_key(env) is True
    import os

    assert os.environ["ANTHROPIC_API_KEY"] == "sk-test"
