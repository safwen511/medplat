"""Strict source-only prompts for local structured QCM generation."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from hashlib import sha256
from typing import Any

from ingestion.generation.models import (
    Difficulty,
    GeneratedContentBatch,
    GenerationConfiguration,
    GenerationSource,
    ProviderQCMCorrectionResponse,
    ProviderQCMResponse,
    ValidationIssue,
)

_NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?\b")


def _evidence_numeric_pattern(quotation: str) -> tuple[str, list[str]]:
    """Return a JSON Schema pattern permitting only exact retained numeric tokens."""
    allowed = sorted(set(_NUMBER.findall(quotation)), key=lambda value: (-len(value), value))
    if not allowed:
        return r"^[^0-9٠-٩۰-۹０-９]*$", []
    alternatives = "|".join(re.escape(value) for value in allowed)
    # Keep this expression within the regular subset accepted by Ollama's JSON
    # grammar compiler. The final numeric validator still enforces token
    # boundaries and is authoritative.
    return (
        rf"^(?:[^0-9٠-٩۰-۹０-９]|(?:{alternatives}))*$",
        sorted(allowed),
    )


def build_qcm_response_schema(source: GenerationSource) -> dict[str, Any]:
    """Bind each selected chunk to only its own retained block identifiers."""
    evidence_variants: list[dict[str, Any]] = []
    for chunk in sorted(source.selected_chunks, key=lambda item: item.chunk_id):
        block_ids = list(
            dict.fromkeys(
                reference.block_id
                for reference in chunk.source_references
                if reference.block_id is not None
            )
        )
        if not block_ids:
            raise ValueError(f"Selected chunk has no valid evidence block IDs: {chunk.chunk_id}")
        evidence_variants.append(
            {
                "additionalProperties": False,
                "properties": {
                    "chunk_id": {"enum": [chunk.chunk_id], "type": "string"},
                    "source_reference_block_ids": {
                        "items": {"enum": block_ids, "type": "string"},
                        "maxItems": 1,
                        "minItems": 1,
                        "type": "array",
                    },
                },
                "required": ["chunk_id", "source_reference_block_ids"],
                "type": "object",
            }
        )

    schema = deepcopy(ProviderQCMResponse.model_json_schema())
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict) or "ProviderEvidenceDraft" not in definitions:
        raise ValueError("Provider QCM schema lacks its evidence definition.")
    definitions["ProviderEvidenceDraft"] = {
        "oneOf": evidence_variants,
        "title": "ProviderEvidenceDraft",
    }
    return schema


def build_qcm_messages(
    configuration: GenerationConfiguration, source: GenerationSource
) -> list[dict[str, str]]:
    """Build deterministic chat messages containing only selected source evidence."""
    source_payload = [
        {
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "source_references": [
                reference.model_dump(mode="json") for reference in chunk.source_references
            ],
        }
        for chunk in source.selected_chunks
    ]
    difficulty = {
        item.value: count for item, count in configuration.difficulty_distribution.items()
    }
    system = (
        "You generate draft medical QCMs using only the supplied local source text. In source_only "
        "mode, the supplied source is authoritative. Do not use prior knowledge, web knowledge, "
        "guidelines, or facts absent from the sources. Never correct, replace, dispute, or "
        "reinterpret a supplied value as a mistake. If the source says 50%, use 50%. Never use "
        "phrases such as 'likely a typo', 'probable typo', 'should be interpreted as', 'likely an "
        "error', 'erreur probable', 'coquille probable', 'doit être interprété', or an equivalent "
        "source-correction phrase. Every medical number in the stem, every choice including "
        "distractors, the correct answer, and the explanation must occur in the selected evidence "
        "span. Choice keys such as A, B, C, and D are identifiers, not medical claims. For each "
        "question, identify exactly one coherent evidence span using one selected chunk_id and "
        "exactly one source_reference_block_id. Do not write or "
        "copy quotation text; MedPlat materializes it. If grounded distractors cannot be produced, "
        "return fewer questions only with insufficient_evidence=true and a nonempty "
        "shortfall_reason. Otherwise insufficient_evidence must be false and shortfall_reason "
        "null. "
        "Return only JSON matching the supplied schema. Content remains unreviewed draft material."
    )
    request_payload = {
        "language": configuration.language,
        "question_count": configuration.count,
        "question_type": configuration.qcm_type.value if configuration.qcm_type else None,
        "difficulty_distribution": difficulty,
        "knowledge_mode": configuration.knowledge_mode.value,
        "topic": configuration.topic,
        "sources": source_payload,
    }
    user = json.dumps(request_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_qcm_correction_schema(
    source: GenerationSource,
    initial_content: GeneratedContentBatch,
    working_content: GeneratedContentBatch,
    target_ordinals: list[int],
    *,
    enforce_difficulty: bool,
    numeric_target_ordinals: set[int],
) -> dict[str, Any]:
    """Build an inlined Ollama-compatible schema for targeted replacements."""
    chunks = {chunk.chunk_id: chunk for chunk in source.selected_chunks}
    variants: list[dict[str, Any]] = []
    working_by_id = {question.question_id: question for question in working_content.qcm_questions}
    for ordinal in sorted(target_ordinals):
        question = initial_content.qcm_questions[ordinal - 1]
        question_id = question.question_id
        current_question = working_by_id.get(question_id, question)
        chunk_id = question.explanation.evidence[0].chunk_id
        chunk = chunks.get(chunk_id)
        if chunk is None:
            raise ValueError("Correction baseline cites a chunk outside the selected source.")
        chunk_block_ids = list(
            dict.fromkeys(
                reference.block_id
                for reference in chunk.source_references
                if reference.block_id is not None
            )
        )
        if not chunk_block_ids:
            raise ValueError(f"Correction chunk has no valid evidence block IDs: {chunk_id}")
        numeric_pattern: str | None = None
        if ordinal in numeric_target_ordinals:
            block_ids = [
                reference.block_id
                for reference in current_question.source_references
                if reference.block_id is not None
            ]
            numeric_pattern, _allowed_numbers = _evidence_numeric_pattern(
                current_question.explanation.evidence[0].quotation
            )
        else:
            block_ids = chunk_block_ids
        string_schema: dict[str, Any] = {"minLength": 1, "type": "string"}
        choice_text_schema = string_schema
        if numeric_pattern is not None:
            string_schema = {
                "minLength": 1,
                "pattern": numeric_pattern,
                "type": "string",
            }
            choice_text_schema = string_schema
        replacement_properties: dict[str, Any] = {
            "topic": {"minLength": 1, "type": "string"},
            "difficulty": {
                "enum": [item.value for item in Difficulty],
                "type": "string",
            },
            "stem": string_schema,
            "choices": {
                "items": {
                    "additionalProperties": False,
                    "properties": {
                        "key": {"minLength": 1, "type": "string"},
                        "text": choice_text_schema,
                    },
                    "required": ["key", "text"],
                    "type": "object",
                },
                "minItems": 3,
                "type": "array",
            },
            "correct_choice_keys": {
                "items": {"minLength": 1, "type": "string"},
                "minItems": 1,
                "type": "array",
            },
            "explanation": string_schema,
            "evidence": {
                "items": {
                    "additionalProperties": False,
                    "properties": {
                        "chunk_id": {"enum": [chunk_id], "type": "string"},
                        "source_reference_block_ids": {
                            "items": {"enum": block_ids, "type": "string"},
                            "maxItems": 1,
                            "minItems": 1,
                            "type": "array",
                        },
                    },
                    "required": ["chunk_id", "source_reference_block_ids"],
                    "type": "object",
                },
                "maxItems": 1,
                "minItems": 1,
                "type": "array",
            },
        }
        if enforce_difficulty:
            replacement_properties["difficulty"] = {
                "enum": [question.difficulty.value],
                "type": "string",
            }
        variants.append(
            {
                "additionalProperties": False,
                "properties": {
                    "question_ordinal": {"enum": [ordinal], "type": "integer"},
                    "replacement": {
                        "additionalProperties": False,
                        "properties": replacement_properties,
                        "required": [
                            "topic",
                            "difficulty",
                            "stem",
                            "choices",
                            "correct_choice_keys",
                            "explanation",
                            "evidence",
                        ],
                        "type": "object",
                    },
                },
                "required": ["question_ordinal", "replacement"],
                "type": "object",
            }
        )

    return {
        "additionalProperties": False,
        "properties": {
            "question_replacements": {
                "items": {"oneOf": variants},
                "maxItems": len(target_ordinals),
                "type": "array",
            },
            "insufficient_evidence": {"type": "boolean"},
            "shortfall_reason": {
                "anyOf": [
                    {"minLength": 1, "type": "string"},
                    {"type": "null"},
                ]
            },
        },
        "required": [
            "question_replacements",
            "insufficient_evidence",
            "shortfall_reason",
        ],
        "title": ProviderQCMCorrectionResponse.__name__,
        "type": "object",
    }


def build_qcm_corrective_messages(
    issues: list[ValidationIssue],
    content: GeneratedContentBatch,
    *,
    retry_sequence: int,
    target_ordinals: list[int],
) -> list[dict[str, str]]:
    """Build a compact, single-question correction using only its retained evidence."""
    if len(target_ordinals) != 1:
        raise ValueError("A corrective provider call must target exactly one question ordinal.")
    target_ordinal = target_ordinals[0]
    target_question_id = sha256(
        f"{content.generation_id}:qcm:{target_ordinal - 1}".encode()
    ).hexdigest()
    target_question = next(
        (
            question
            for question in content.qcm_questions
            if question.question_id == target_question_id
        ),
        None,
    )
    if target_question is None:
        raise ValueError("Targeted correction question is absent from the working batch.")
    question_by_id = {target_question.question_id: (target_ordinal, target_question)}
    grouped: dict[str, dict[str, Any]] = {}

    def issue_sort_key(issue: ValidationIssue) -> tuple[int, str, str]:
        found = question_by_id.get(issue.question_id) if issue.question_id is not None else None
        return (found[0] if found is not None else 10**9, issue.question_id or "", issue.code)

    ordered_issues = sorted(
        issues,
        key=issue_sort_key,
    )
    for issue in ordered_issues:
        found = question_by_id.get(issue.question_id) if issue.question_id is not None else None
        key = f"question-{found[0]}" if found is not None else (issue.question_id or "batch")
        record = grouped.setdefault(
            key,
            {
                "question_ordinal": found[0] if found is not None else None,
                "temporary_question_key": key,
                "issue_codes": [],
                "unsupported_numbers": [],
                "evidence_span": None,
            },
        )
        record["issue_codes"].append(issue.code)
        unsupported = issue.details.get("unsupported_numbers", [])
        if isinstance(unsupported, list):
            record["unsupported_numbers"].extend(str(item) for item in unsupported)
        expected_span = issue.details.get("expected_evidence_span")
        if isinstance(expected_span, dict):
            record["evidence_span"] = expected_span
        elif found is not None:
            question = found[1]
            evidence = question.explanation.evidence[0]
            record["evidence_span"] = {
                "chunk_id": evidence.chunk_id,
                "source_reference_block_ids": [
                    reference.block_id
                    for reference in question.source_references
                    if reference.block_id is not None
                ],
            }
        if found is not None:
            record["evidence_text"] = found[1].explanation.evidence[0].quotation

    corrections = []
    for key in sorted(
        grouped, key=lambda value: (grouped[value]["question_ordinal"] or 10**9, value)
    ):
        record = grouped[key]
        record["issue_codes"] = sorted(set(record["issue_codes"]))
        record["unsupported_numbers"] = sorted(set(record["unsupported_numbers"]))
        corrections.append(record)

    target_evidence = target_question.explanation.evidence[0]
    target_block_ids = [
        reference.block_id
        for reference in target_question.source_references
        if reference.block_id is not None
    ]
    corrective_payload = {
        "validation_retry_sequence": retry_sequence,
        "required_action": "return_targeted_question_replacements",
        "required_question_ordinals": sorted(target_ordinals),
        "corrections": corrections,
        "instructions": [
            "Return replacements only for the required question ordinals.",
            "Use only the same selected local source evidence already supplied.",
            "Do not defend or explain the prior response.",
            (
                "Remove unsupported numeric distractors or replace them with nonnumeric "
                "distractors grounded in the same evidence."
            ),
            (
                "Align wording more closely with retained evidence and remove "
                "source-correction language."
            ),
            "Never change a source value or add outside medical knowledge.",
            "Use the explicit insufficiency contract when grounded distractors cannot be produced.",
            (
                "Keep each question on its supplied evidence chunk and cite exactly one retained "
                "source-reference block from that chunk."
            ),
            "Do not return or rewrite any question ordinal not requested for correction.",
            (
                "If an ordinal cannot be grounded, omit its replacement and declare "
                "insufficient_evidence with a nonempty shortfall_reason."
            ),
            "Use ASCII digits for JSON integer fields such as question_ordinal.",
            (
                "Use exactly the field names in response_contract. Never use options, answers, "
                "correct_answer, source_id, questions, or sources."
            ),
        ],
        "response_contract": {
            "question_replacements": [
                {
                    "question_ordinal": target_ordinal,
                    "replacement": {
                        "topic": "nonempty string",
                        "difficulty": target_question.difficulty.value,
                        "stem": "nonempty string",
                        "choices": [
                            {"key": "A", "text": "nonempty grounded string"},
                            {"key": "B", "text": "nonempty grounded string"},
                            {"key": "C", "text": "nonempty grounded string"},
                        ],
                        "correct_choice_keys": ["A"],
                        "explanation": "nonempty grounded string",
                        "evidence": [
                            {
                                "chunk_id": target_evidence.chunk_id,
                                "source_reference_block_ids": target_block_ids,
                            }
                        ],
                    },
                }
            ],
            "insufficient_evidence": False,
            "shortfall_reason": None,
        },
    }
    corrective_system = (
        "This is a deterministic single-question technical-validation retry. The supplied local "
        "evidence is authoritative. Use no outside knowledge and never change source values. "
        "Return exactly one JSON object matching response_contract, or use its explicit shortfall "
        "fields. Do not repeat the object, the source, or the instructions."
    )
    corrective_user = json.dumps(
        corrective_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return [
        {"role": "system", "content": corrective_system},
        {"role": "user", "content": corrective_user},
    ]


def prompt_size(messages: list[dict[str, str]]) -> tuple[int, int]:
    characters = sum(len(message["role"]) + len(message["content"]) for message in messages)
    return characters, (characters + 3) // 4
