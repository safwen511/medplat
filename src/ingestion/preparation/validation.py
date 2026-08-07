"""Conservative lexical, numerical, provenance, and transformation validation."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from ingestion.preparation.models import ModelTransformation, SourceSpan, ValidationIssue
from ingestion.preparation.prompts import AUTHORIZED_IMAGE_MARKER, AUTHORIZED_INCOMPLETE_MARKER

_TOKEN = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
_NUMBER = re.compile(r"(?<!\w)[<>≤≥±+\-]?\d+(?:[.,]\d+)?(?:\s*[%‰])?(?!\w)")
_UNIT = re.compile(
    r"\b(?:mg|g|kg|µg|mcg|ml|l|mmol|mol|ui|iu|mmhg|cmh2o|bpm|hz|mhz|mm|cm|m)\b",
    re.I,
)
_NEGATIONS = {"ne", "pas", "jamais", "aucun", "sans", "ni"}
_MODALS = {
    "toujours",
    "jamais",
    "obligatoire",
    "obligatoirement",
    "contre-indiqué",
    "contre-indiquée",
    "recommandé",
    "recommandée",
}
_PRESENTATION_WORDS = {
    "page",
    "slide",
    "table",
    "titre",
    "auteur",
    "enseignant",
    "institution",
    "contenu",
    "probablement",
    "dépendant",
    "image",
    "consulter",
    "document",
    "original",
    "texte",
    "incomplet",
    "illisible",
    "source",
    "extraite",
}


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _tokens(value: str) -> Counter[str]:
    stripped = value.replace(AUTHORIZED_IMAGE_MARKER, "").replace(AUTHORIZED_INCOMPLETE_MARKER, "")
    return Counter(_normalized(token) for token in _TOKEN.findall(stripped))


def _values(pattern: re.Pattern[str], value: str) -> Counter[str]:
    return Counter(" ".join(_normalized(item).split()) for item in pattern.findall(value))


def validate_reconstruction(
    source_text: str,
    reconstructed_text: str,
    transformations: list[ModelTransformation],
    spans: list[SourceSpan],
    *,
    span_texts: dict[str, str] | None = None,
) -> tuple[list[ValidationIssue], list[str]]:
    """Reject unsupported additions and report every conservative lexical concern."""
    issues: list[ValidationIssue] = []
    span_by_id = {span.span_id: span for span in spans if span.retained}
    source_tokens = _tokens(source_text)
    output_tokens = _tokens(reconstructed_text)
    new_numbers = sorted(_values(_NUMBER, reconstructed_text) - _values(_NUMBER, source_text))
    if new_numbers:
        issues.append(
            ValidationIssue(
                code="unsupported_numerical_token",
                message="Reconstruction introduced a numerical token absent from its source spans.",
                severity="error",
                details={"tokens": new_numbers},
            )
        )
    new_units = sorted(_values(_UNIT, reconstructed_text) - _values(_UNIT, source_text))
    if new_units:
        issues.append(
            ValidationIssue(
                code="unsupported_unit",
                message="Reconstruction introduced a unit absent from its source spans.",
                severity="error",
                details={"units": new_units},
            )
        )
    suspicious = sorted(
        token
        for token in (output_tokens - source_tokens)
        if len(token) >= 4 and token not in _PRESENTATION_WORDS and not token.isdigit()
    )
    if suspicious:
        issues.append(
            ValidationIssue(
                code="unsupported_lexical_addition",
                message="Reconstruction introduced lexical material absent from its source spans.",
                severity="error",
                details={"tokens": suspicious[:100]},
            )
        )
    missing = sorted(
        token
        for token in (source_tokens - output_tokens)
        if len(token) >= 3 and not token.isdigit()
    )
    if missing:
        issues.append(
            ValidationIssue(
                code="informative_source_tokens_missing",
                message=(
                    "Reconstruction omitted source tokens without deterministic duplicate evidence."
                ),
                severity="error",
                details={"tokens": missing[:100]},
            )
        )
    for vocabulary, code in ((_NEGATIONS, "changed_negation"), (_MODALS, "changed_modal_word")):
        source_values = source_tokens.keys() & vocabulary
        output_values = output_tokens.keys() & vocabulary
        if source_values != output_values:
            issues.append(
                ValidationIssue(
                    code=code,
                    message="Reconstruction changed protected negation or modality vocabulary.",
                    severity="error",
                    details={
                        "source": sorted(source_values),
                        "reconstructed": sorted(output_values),
                    },
                )
            )
    known_ids = set(span_by_id)
    evidence_by_id = span_texts or {}
    for transformation in transformations:
        cited = set(transformation.cleaned_span_ids)
        if not cited or not cited.issubset(known_ids):
            issues.append(
                ValidationIssue(
                    code="invalid_transformation_source_spans",
                    message="A model transformation cites unknown or removed source spans.",
                    severity="error",
                    details={"transformation_id": transformation.transformation_id},
                )
            )
        elif evidence_by_id:
            cited_text = "\n".join(
                evidence_by_id[span_id]
                for span_id in transformation.cleaned_span_ids
                if span_id in evidence_by_id
            )
            normalized_original = " ".join(_normalized(transformation.original_text).split())
            normalized_evidence = " ".join(_normalized(cited_text).split())
            if normalized_original and normalized_original not in normalized_evidence:
                issues.append(
                    ValidationIssue(
                        code="transformation_original_not_in_cited_spans",
                        message=(
                            "A model transformation's original text does not occur in its cited "
                            "source spans."
                        ),
                        severity="error",
                        details={"transformation_id": transformation.transformation_id},
                    )
                )
        normalized_reconstructed = " ".join(_normalized(transformation.reconstructed_text).split())
        normalized_output = " ".join(_normalized(reconstructed_text).split())
        if normalized_reconstructed and normalized_reconstructed not in normalized_output:
            issues.append(
                ValidationIssue(
                    code="transformation_output_not_materialized",
                    message="A declared model transformation does not occur in reconstructed text.",
                    severity="error",
                    details={"transformation_id": transformation.transformation_id},
                )
            )
        if not transformation.support_basis.strip():
            issues.append(
                ValidationIssue(
                    code="missing_transformation_support_basis",
                    message="A model transformation has no source support basis.",
                    severity="error",
                    details={"transformation_id": transformation.transformation_id},
                )
            )
    return issues, suspicious
