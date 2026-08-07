"""Versioned source-only contracts for contextual course-text reconstruction."""

from __future__ import annotations

import json
from hashlib import sha256

from ingestion.preparation.models import PROMPT_VERSION, TransformationType

RECONSTRUCTION_SYSTEM_PROMPT = f"""You are a local text-layout reconstruction component.
Contract version: {PROMPT_VERSION}.

The supplied course extraction is authoritative. Return a structural plan made only of supplied span
IDs and join operations. Python, not you, materializes every course word from those spans. Do not
emit rewritten course prose. Reorganize for readability without adding, correcting, translating,
summarizing, or interpreting medical content.
Never use pretrained medical knowledge to complete a missing statement. Never infer a superscript,
flowchart relation, image, dose, table cell, or missing classification.

You may only group adjacent spans as paragraphs, headings, bullets, or recoverable table rows. Every
input span ID must appear exactly once, in original order. Never omit, duplicate, or reorder a span.
Use space only to join sentence fragments, line for bullets/table lines, and blank_line otherwise.
Preserve contradictions and uncertainty. Mark unresolved or image-dependent spans by ID; Python adds
the authorized source-review markers. Return only JSON matching the supplied schema."""

REVIEW_SYSTEM_PROMPT = """You are a constrained local source-support reviewer. The extracted source
spans are authoritative. Do not rewrite text and do not correct medicine. For each supplied
transformation, classify it only as supported, unsupported, ambiguous, possible_extraction_error,
or external_medical_observation. A fact known from pretrained knowledge but absent from the supplied
spans is external_medical_observation. Return only JSON matching the supplied schema."""

AUTHORIZED_INCOMPLETE_MARKER = "[Texte incomplet ou illisible dans la source extraite]"
AUTHORIZED_IMAGE_MARKER = (
    "[Contenu probablement dépendant d’une image — consulter le document original]"
)


def reconstruction_schema() -> dict[str, object]:
    transformation_types = [item.value for item in TransformationType]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "groups",
            "unresolved_span_ids",
            "image_dependency_span_ids",
        ],
        "properties": {
            "groups": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "group_id",
                        "transformation_type",
                        "span_ids",
                        "join_with",
                        "support_basis",
                        "confidence",
                    ],
                    "properties": {
                        "group_id": {"type": "string"},
                        "transformation_type": {
                            "type": ["string", "null"],
                            "enum": [*transformation_types, None],
                        },
                        "span_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                        "join_with": {
                            "type": "string",
                            "enum": ["space", "line", "blank_line"],
                        },
                        "support_basis": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                },
            },
            "unresolved_span_ids": {"type": "array", "items": {"type": "string"}},
            "image_dependency_span_ids": {"type": "array", "items": {"type": "string"}},
        },
    }


def review_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["findings"],
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["transformation_id", "verdict", "source_span_ids", "message"],
                    "properties": {
                        "transformation_id": {"type": ["string", "null"]},
                        "verdict": {
                            "type": "string",
                            "enum": [
                                "supported",
                                "unsupported",
                                "ambiguous",
                                "possible_extraction_error",
                                "external_medical_observation",
                            ],
                        },
                        "source_span_ids": {"type": "array", "items": {"type": "string"}},
                        "message": {"type": "string"},
                    },
                },
            }
        },
    }


def prompt_hash() -> str:
    payload = (
        RECONSTRUCTION_SYSTEM_PROMPT
        + "\n"
        + json.dumps(reconstruction_schema(), sort_keys=True, separators=(",", ":"))
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def schema_hash() -> str:
    payload = json.dumps(reconstruction_schema(), sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def reconstruction_user_prompt(section_id: str, spans: list[tuple[str, str]]) -> str:
    rendered = "\n\n".join(f"<{span_id}>\n{text}\n</{span_id}>" for span_id, text in spans)
    return f"""Reconstruct section {section_id} using only the following extracted spans.

Authorized marker for illegible extraction:
{AUTHORIZED_INCOMPLETE_MARKER}

Authorized marker for missing image-dependent content:
{AUTHORIZED_IMAGE_MARKER}

Return every supplied span ID exactly once and in the same order. Do not return the course prose.
Do not create student exercises or study material.

SOURCE SPANS:
{rendered}"""


def review_user_prompt(
    section_id: str,
    source_spans: list[tuple[str, str]],
    reconstructed_text: str,
    transformations: list[dict[str, object]],
) -> str:
    rendered = "\n\n".join(f"<{span_id}>\n{text}\n</{span_id}>" for span_id, text in source_spans)
    return f"""Review source support only for section {section_id}.

SOURCE SPANS:
{rendered}

RECONSTRUCTED SECTION:
{reconstructed_text}

TRANSFORMATIONS:
{json.dumps(transformations, ensure_ascii=False, sort_keys=True)}"""
