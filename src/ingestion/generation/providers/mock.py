"""Deterministic no-network provider for fixtures and tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from ingestion.generation.models import GenerationConfiguration
from ingestion.generation.providers.base import ProviderResult


class MockGenerationProvider:
    def __init__(
        self,
        response_factory: Callable[[int], dict[str, object] | str],
        *,
        done_reason_factory: Callable[[int], str | None] | None = None,
    ) -> None:
        self._response_factory = response_factory
        self._done_reason_factory = done_reason_factory
        self.calls = 0
        self.last_response_schema: dict[str, Any] | None = None
        self.message_history: list[list[dict[str, str]]] = []
        self.response_schema_history: list[dict[str, Any]] = []

    def generate(
        self,
        messages: list[dict[str, str]],
        configuration: GenerationConfiguration,
        response_schema: dict[str, Any],
    ) -> ProviderResult:
        del configuration
        self.last_response_schema = response_schema
        self.message_history.append(messages)
        self.response_schema_history.append(response_schema)
        self.calls += 1
        payload = self._response_factory(self.calls)
        content = (
            payload
            if isinstance(payload, str)
            else json.dumps(payload, sort_keys=True, ensure_ascii=False)
        )
        envelope: dict[str, object] = {"mock": True, "message": {"content": content}}
        if self._done_reason_factory is not None:
            done_reason = self._done_reason_factory(self.calls)
            if done_reason is not None:
                envelope["done_reason"] = done_reason
        raw_response_text = json.dumps(envelope, sort_keys=True, ensure_ascii=False)
        return ProviderResult(
            raw_envelope=envelope,
            raw_response_text=raw_response_text,
            content=content,
            # Each mock generate call is one transport attempt. Application-level
            # validation retries are tracked independently by the service.
            attempt_count=1,
            http_status=200,
            provider_version="deterministic-mock-1",
        )
