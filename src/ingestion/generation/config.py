"""CLI and environment configuration for local generation."""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping
from urllib.parse import urlsplit

from ingestion.generation.models import (
    ContentType,
    Difficulty,
    GenerationConfiguration,
    KnowledgeMode,
    ProviderKind,
    QCMType,
)

OLLAMA_BASE_URL_ENV = "MEDPARSE_OLLAMA_BASE_URL"
OLLAMA_MODEL_ENV = "MEDPARSE_OLLAMA_MODEL"
OLLAMA_TIMEOUT_ENV = "MEDPARSE_OLLAMA_TIMEOUT_SECONDS"
OLLAMA_TEMPERATURE_ENV = "MEDPARSE_OLLAMA_TEMPERATURE"
OLLAMA_CONTEXT_ENV = "MEDPARSE_OLLAMA_CONTEXT_SIZE"
OLLAMA_SEED_ENV = "MEDPARSE_OLLAMA_SEED"
OLLAMA_MAX_OUTPUT_ENV = "MEDPARSE_OLLAMA_MAX_OUTPUT_TOKENS"
OLLAMA_RETRY_ENV = "MEDPARSE_OLLAMA_RETRY_COUNT"
OLLAMA_VALIDATION_RETRY_ENV = "MEDPARSE_OLLAMA_VALIDATION_RETRY_COUNT"


def mixed_difficulty_distribution(count: int) -> dict[Difficulty, int]:
    """Return a stable balanced distribution, assigning remainders medium then easy."""
    base, remainder = divmod(count, 3)
    values = {
        Difficulty.EASY: base,
        Difficulty.MEDIUM: base,
        Difficulty.HARD: base,
    }
    if remainder >= 1:
        values[Difficulty.MEDIUM] += 1
    if remainder >= 2:
        values[Difficulty.EASY] += 1
    return values


def validate_loopback_base_url(value: str) -> str:
    """Accept plain HTTP Ollama URLs bound strictly to the local machine."""
    parsed = urlsplit(value)
    if parsed.scheme != "http":
        raise ValueError("Ollama base URL must use plain HTTP on a loopback interface.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Ollama base URL cannot contain credentials, query, or fragment.")
    if parsed.path not in {"", "/"}:
        raise ValueError("Ollama base URL must not contain an API path.")
    hostname = parsed.hostname
    if hostname is None:
        raise ValueError("Ollama base URL must contain a loopback hostname.")
    if hostname != "localhost":
        try:
            if not ipaddress.ip_address(hostname).is_loopback:
                raise ValueError("Ollama base URL must resolve only to a loopback address.")
        except ValueError as exc:
            if "loopback" in str(exc):
                raise
            raise ValueError(
                "Ollama hostname must be localhost or a literal loopback address."
            ) from exc
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Ollama port is invalid.")
    return value.rstrip("/")


def generation_configuration(
    *,
    content_type: ContentType,
    qcm_type: QCMType | None,
    count: int,
    language: str,
    difficulty: str,
    knowledge_mode: KnowledgeMode,
    provider: ProviderKind,
    model: str | None,
    base_url: str | None = None,
    timeout_seconds: float | None = None,
    temperature: float | None = None,
    context_size: int | None = None,
    seed: int | None = None,
    maximum_output_tokens: int | None = None,
    retry_count: int | None = None,
    validation_retry_count: int | None = None,
    maximum_source_characters: int = 12000,
    maximum_source_tokens: int = 3000,
    topic: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> GenerationConfiguration:
    """Resolve explicit CLI values over non-secret environment configuration."""
    values = os.environ if environ is None else environ
    resolved_model = model or values.get(OLLAMA_MODEL_ENV)
    if not resolved_model:
        raise ValueError("An explicit Ollama model is required via --model or environment.")
    resolved_base_url = validate_loopback_base_url(
        base_url or values.get(OLLAMA_BASE_URL_ENV, "http://127.0.0.1:11434")
    )
    if difficulty == "mixed":
        distribution = mixed_difficulty_distribution(count)
    else:
        selected = Difficulty(difficulty)
        distribution = {item: count if item is selected else 0 for item in Difficulty}
    return GenerationConfiguration(
        content_type=content_type,
        qcm_type=qcm_type,
        count=count,
        language=language,
        difficulty_distribution=distribution,
        knowledge_mode=knowledge_mode,
        provider=provider,
        model=resolved_model,
        base_url=resolved_base_url,
        timeout_seconds=(
            timeout_seconds
            if timeout_seconds is not None
            else float(values.get(OLLAMA_TIMEOUT_ENV, "120"))
        ),
        temperature=(
            temperature
            if temperature is not None
            else float(values.get(OLLAMA_TEMPERATURE_ENV, "0"))
        ),
        context_size=(
            context_size
            if context_size is not None
            else int(values.get(OLLAMA_CONTEXT_ENV, "8192"))
        ),
        seed=seed if seed is not None else int(values.get(OLLAMA_SEED_ENV, "42")),
        maximum_output_tokens=(
            maximum_output_tokens
            if maximum_output_tokens is not None
            else int(values.get(OLLAMA_MAX_OUTPUT_ENV, "2048"))
        ),
        retry_count=(
            retry_count if retry_count is not None else int(values.get(OLLAMA_RETRY_ENV, "2"))
        ),
        validation_retry_count=(
            validation_retry_count
            if validation_retry_count is not None
            else int(values.get(OLLAMA_VALIDATION_RETRY_ENV, "1"))
        ),
        maximum_source_characters=maximum_source_characters,
        maximum_source_tokens=maximum_source_tokens,
        topic=topic,
    )
