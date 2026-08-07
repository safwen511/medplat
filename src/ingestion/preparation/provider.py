"""Loopback-only Ollama access for course-text reconstruction and review."""

from __future__ import annotations

import http.client
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from ingestion.generation.config import validate_loopback_base_url
from ingestion.preparation.models import ModelIdentity


class LocalModelError(RuntimeError):
    """Concise local-provider or structured-response failure."""


ConnectionFactory = Callable[[str, int, float], http.client.HTTPConnection]


def _connection(host: str, port: int, timeout: float) -> http.client.HTTPConnection:
    return http.client.HTTPConnection(host, port, timeout=timeout)


@dataclass(frozen=True)
class StructuredResponse:
    content: dict[str, Any]
    raw_response: str
    attempt_count: int


class OllamaPreparationProvider:
    """Small loopback client that never pulls, installs, or contacts nonlocal services."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        connection_factory: ConnectionFactory = _connection,
    ) -> None:
        parsed = urlsplit(validate_loopback_base_url(base_url))
        assert parsed.hostname is not None
        self._host = parsed.hostname
        self._port = parsed.port or 11434
        self._timeout_seconds = timeout_seconds
        self._connection_factory = connection_factory

    def _request(self, method: str, path: str, payload: object | None = None) -> tuple[int, str]:
        connection = self._connection_factory(self._host, self._port, self._timeout_seconds)
        try:
            body = None
            headers: dict[str, str] = {"Accept": "application/json"}
            if payload is not None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                headers["Content-Type"] = "application/json"
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, response.read().decode("utf-8")
        except (OSError, UnicodeDecodeError, http.client.HTTPException) as exc:
            raise LocalModelError(f"Local Ollama request failed: {exc}") from exc
        finally:
            connection.close()

    def version(self) -> str:
        status, body = self._request("GET", "/api/version")
        if status != 200:
            raise LocalModelError(f"Ollama version request returned HTTP {status}.")
        value = json.loads(body)
        if not isinstance(value, dict) or not isinstance(value.get("version"), str):
            raise LocalModelError("Ollama version response is invalid.")
        return str(value["version"])

    def models(self) -> list[ModelIdentity]:
        status, body = self._request("GET", "/api/tags")
        if status != 200:
            raise LocalModelError(f"Ollama model listing returned HTTP {status}.")
        value = json.loads(body)
        raw_models = value.get("models") if isinstance(value, dict) else None
        if not isinstance(raw_models, list):
            raise LocalModelError("Ollama model listing response is invalid.")
        models: list[ModelIdentity] = []
        for raw in raw_models:
            if not isinstance(raw, dict):
                continue
            raw_details = raw.get("details")
            details: dict[str, Any] = raw_details if isinstance(raw_details, dict) else {}
            name = raw.get("name") or raw.get("model")
            digest = raw.get("digest")
            if not isinstance(name, str) or not isinstance(digest, str):
                continue
            models.append(
                ModelIdentity(
                    tag=name,
                    digest=digest.removeprefix("sha256:"),
                    size_bytes=int(raw.get("size", 0)),
                    parameter_size=(
                        str(details["parameter_size"])
                        if details.get("parameter_size") is not None
                        else None
                    ),
                    quantization=(
                        str(details["quantization_level"])
                        if details.get("quantization_level") is not None
                        else None
                    ),
                )
            )
        return sorted(models, key=lambda item: item.tag)

    def resolve_model(self, requested: str, *, reviewer: bool = False) -> ModelIdentity:
        models = self.models()
        if requested == "auto-medgemma-4b":
            candidates = [
                item
                for item in models
                if "medgemma" in item.tag.casefold()
                and (item.parameter_size or "").casefold().startswith(("4", "4.3"))
            ]
            if not candidates:
                raise LocalModelError("No installed MedGemma 4B model was found.")
            return candidates[0]
        for model in models:
            if model.tag == requested:
                return model
        role = "reviewer" if reviewer else "generator"
        raise LocalModelError(f"Configured {role} model is not installed: {requested}")

    def chat_json(
        self,
        *,
        model: ModelIdentity,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, object],
        context_budget: int,
        temperature: float,
        seed: int,
        maximum_retries: int,
    ) -> StructuredResponse:
        payload = {
            "model": model.tag,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": response_schema,
            "keep_alive": "30m",
            "options": {
                "temperature": temperature,
                "seed": seed,
                "num_ctx": context_budget,
                "num_predict": min(4096, max(1024, context_budget // 2)),
            },
        }
        last_error = "unknown error"
        last_body = ""
        for attempt in range(1, maximum_retries + 2):
            try:
                status, body = self._request("POST", "/api/chat", payload)
            except LocalModelError as exc:
                last_error = str(exc)
                continue
            last_body = body
            if status != 200:
                last_error = f"HTTP {status}"
                continue
            try:
                envelope = json.loads(body)
                message = envelope.get("message") if isinstance(envelope, dict) else None
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, str):
                    raise ValueError("response lacks message.content")
                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    raise ValueError("structured content is not an object")
                return StructuredResponse(
                    content=parsed,
                    raw_response=body,
                    attempt_count=attempt,
                )
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = str(exc)
        raise LocalModelError(
            f"Ollama structured response failed after {maximum_retries + 1} attempt(s): "
            f"{last_error}; last response bytes={len(last_body.encode('utf-8'))}"
        )

    def unload(self, model: ModelIdentity) -> None:
        status, _ = self._request(
            "POST",
            "/api/generate",
            {"model": model.tag, "prompt": "", "stream": False, "keep_alive": 0},
        )
        if status != 200:
            raise LocalModelError(f"Could not unload local model {model.tag}: HTTP {status}.")
