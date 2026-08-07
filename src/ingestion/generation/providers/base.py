"""Provider protocol shared by local generation backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ingestion.generation.models import GenerationConfiguration


@dataclass(frozen=True)
class ProviderResult:
    raw_envelope: dict[str, Any]
    raw_response_text: str
    content: str
    attempt_count: int
    http_status: int | None = None
    provider_version: str | None = None


class GenerationProviderError(RuntimeError):
    """Provider failure retaining the terminal local HTTP diagnostic payload."""

    def __init__(
        self,
        message: str,
        *,
        raw_response_text: str | None = None,
        raw_envelope: dict[str, Any] | None = None,
        content: str | None = None,
        attempt_count: int = 1,
        http_status: int | None = None,
        provider_version: str | None = None,
    ) -> None:
        super().__init__(message)
        self.raw_response_text = raw_response_text
        self.raw_envelope = raw_envelope
        self.content = content
        self.attempt_count = attempt_count
        self.http_status = http_status
        self.provider_version = provider_version


class GenerationProvider(Protocol):
    def generate(
        self,
        messages: list[dict[str, str]],
        configuration: GenerationConfiguration,
        response_schema: dict[str, Any],
    ) -> ProviderResult:
        """Return one structured provider response or raise a concise failure."""
        ...
