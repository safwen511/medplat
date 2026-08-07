"""Strict loopback-only Ollama HTTP provider."""

from __future__ import annotations

import http.client
import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from ingestion.generation.config import validate_loopback_base_url
from ingestion.generation.models import GenerationConfiguration
from ingestion.generation.providers.base import GenerationProviderError, ProviderResult


class OllamaProviderError(GenerationProviderError):
    """Concise local-provider failure."""


ConnectionFactory = Callable[[str, int, float], http.client.HTTPConnection]


def _connection(host: str, port: int, timeout: float) -> http.client.HTTPConnection:
    return http.client.HTTPConnection(host, port, timeout=timeout)


class OllamaGenerationProvider:
    def __init__(self, connection_factory: ConnectionFactory = _connection) -> None:
        self._connection_factory = connection_factory

    def generate(
        self,
        messages: list[dict[str, str]],
        configuration: GenerationConfiguration,
        response_schema: dict[str, Any],
    ) -> ProviderResult:
        base_url = validate_loopback_base_url(configuration.base_url)
        parsed = urlsplit(base_url)
        assert parsed.hostname is not None
        host = parsed.hostname
        port = parsed.port or 11434
        request_payload: dict[str, Any] = {
            "model": configuration.model,
            "messages": messages,
            "stream": False,
            "format": response_schema,
            "options": {
                "temperature": configuration.temperature,
                "num_ctx": configuration.context_size,
                "num_predict": configuration.maximum_output_tokens,
            },
        }
        if configuration.seed is not None:
            request_payload["options"]["seed"] = configuration.seed
        encoded = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
        last_error: Exception | None = None
        last_raw_response: str | None = None
        last_envelope: dict[str, Any] | None = None
        last_content: str | None = None
        last_http_status: int | None = None
        last_provider_version: str | None = None
        for attempt in range(1, configuration.retry_count + 2):
            last_raw_response = None
            last_envelope = None
            last_content = None
            last_http_status = None
            last_provider_version = None
            connection: http.client.HTTPConnection | None = None
            try:
                connection = self._connection_factory(host, port, configuration.timeout_seconds)
                connection.request(
                    "POST",
                    "/api/chat",
                    body=encoded,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                )
                response = connection.getresponse()
                body = response.read().decode("utf-8")
                last_raw_response = body
                last_http_status = response.status
                if response.status != 200:
                    try:
                        parsed_error = json.loads(body)
                        if isinstance(parsed_error, dict):
                            last_envelope = parsed_error
                    except json.JSONDecodeError:
                        pass
                    raise OllamaProviderError(f"Ollama returned HTTP {response.status}.")
                envelope = json.loads(body)
                if not isinstance(envelope, dict):
                    raise OllamaProviderError("Ollama response envelope is not an object.")
                last_envelope = envelope
                last_provider_version = (
                    str(envelope["version"]) if envelope.get("version") is not None else None
                )
                message = envelope.get("message")
                if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                    raise OllamaProviderError("Ollama response lacks message.content.")
                content = str(message["content"])
                last_content = content
                return ProviderResult(
                    raw_envelope=envelope,
                    raw_response_text=body,
                    content=content,
                    attempt_count=attempt,
                    http_status=response.status,
                    provider_version=last_provider_version,
                )
            except (
                OSError,
                UnicodeDecodeError,
                http.client.HTTPException,
                json.JSONDecodeError,
                OllamaProviderError,
            ) as exc:
                last_error = exc
            finally:
                if connection is not None:
                    connection.close()
        attempt_count = configuration.retry_count + 1
        raise OllamaProviderError(
            f"Ollama generation failed after {attempt_count} attempt(s): {last_error}",
            raw_response_text=last_raw_response,
            raw_envelope=last_envelope,
            content=last_content,
            attempt_count=attempt_count,
            http_status=last_http_status,
            provider_version=last_provider_version,
        )
