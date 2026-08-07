"""Sequential full-tree cleaning, readiness, reconstruction, validation, and reporting."""

from __future__ import annotations

import json
import os
import re
import resource
import shutil
import subprocess
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from pydantic import ValidationError

from ingestion.hashing import sha256_file
from ingestion.output import ensure_output_outside_source, write_json_atomic, write_text_atomic
from ingestion.preparation.cleaning import CleanedArtifact, clean_export
from ingestion.preparation.models import (
    CLEANING_VERSION,
    PREPARATION_SCHEMA_VERSION,
    PROMPT_VERSION,
    RECONSTRUCTION_VERSION,
    CleaningSidecar,
    ModelIdentity,
    ModelTransformation,
    PreparationConfiguration,
    PreparationManifest,
    PreparationManifestEntry,
    PreparationRunReport,
    PreparationRunResult,
    PreparationStatus,
    ReadinessStatus,
    ReconstructionDraft,
    ReconstructionSidecar,
    ReviewDraft,
    ReviewerFinding,
    ReviewVerdict,
    SectionState,
    SourceSpan,
    TransformationType,
    ValidationIssue,
)
from ingestion.preparation.parsing import (
    RawExport,
    discover_exports,
    load_export_manifest,
    parse_raw_export,
)
from ingestion.preparation.prompts import (
    AUTHORIZED_IMAGE_MARKER,
    AUTHORIZED_INCOMPLETE_MARKER,
    RECONSTRUCTION_SYSTEM_PROMPT,
    REVIEW_SYSTEM_PROMPT,
    prompt_hash,
    reconstruction_schema,
    reconstruction_user_prompt,
    review_schema,
    review_user_prompt,
    schema_hash,
)
from ingestion.preparation.provider import LocalModelError, OllamaPreparationProvider
from ingestion.preparation.validation import validate_reconstruction

_HEADING = re.compile(r"^(?:(?:[IVXLC]+|\d+(?:\.\d+)*)[.)\-:]?\s*)?[A-ZÀ-ÖØ-Þ][^.!?]{1,140}$")


@dataclass(frozen=True)
class _PreparedDocument:
    raw: RawExport
    cleaned_text: str
    cleaning_sidecar: CleaningSidecar
    clean_entry: PreparationManifestEntry


@dataclass(frozen=True)
class _Section:
    section_id: str
    spans: tuple[SourceSpan, ...]
    source_text: str
    model_eligible: bool
    readiness_statuses: tuple[ReadinessStatus, ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class _SectionResult:
    text: str
    transformations: tuple[ModelTransformation, ...]
    unresolved_fragments: tuple[str, ...]
    image_annotations: tuple[str, ...]
    issues: tuple[ValidationIssue, ...]
    suspicious_additions: tuple[str, ...]
    status: PreparationStatus
    generator_attempt_count: int
    runtime_seconds: float


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_hash(payload: object) -> str:
    value = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(value.encode("utf-8")).hexdigest()


def _sidecar_relative(relative: str, suffix: str) -> str:
    return Path(relative).with_suffix(suffix).as_posix()


def _safe_path(root: Path, relative: str) -> Path:
    candidate = root / Path(relative)
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("Preparation output path is unsafe.")
    if not resolved.is_relative_to(resolved_root):
        raise ValueError("Preparation output path escaped its configured root.")
    return candidate


def _validate_roots(configuration: PreparationConfiguration) -> None:
    input_root = configuration.input_root.resolve()
    outputs = [
        configuration.clean_output_root.resolve(),
        configuration.reconstructed_output_root.resolve(),
        configuration.report_output_root.resolve(),
    ]
    for output in outputs:
        ensure_output_outside_source(output, input_root)
        if input_root.is_relative_to(output):
            raise ValueError("Preparation input and output roots must be disjoint.")
    for index, left in enumerate(outputs):
        for right in outputs[index + 1 :]:
            if left == right or left.is_relative_to(right) or right.is_relative_to(left):
                raise ValueError("Clean, reconstructed, and report roots must be disjoint.")


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
        if path.is_file()
    }


def _snapshot_changes(before: dict[str, str], after: dict[str, str]) -> list[str]:
    changes: list[str] = []
    for path in sorted(before.keys() - after.keys()):
        changes.append(f"removed:{path}")
    for path in sorted(after.keys() - before.keys()):
        changes.append(f"added:{path}")
    for path in sorted(before.keys() & after.keys()):
        if before[path] != after[path]:
            changes.append(f"modified:{path}")
    return changes


def _clean_entry(artifact: CleanedArtifact, relative: str) -> PreparationManifestEntry:
    sidecar_relative = _sidecar_relative(relative, ".cleaning.json")
    status = (
        PreparationStatus.CLEANED_WITH_WARNINGS
        if artifact.sidecar.warnings
        else PreparationStatus.CLEANED
    )
    return PreparationManifestEntry(
        source_relative_path=artifact.sidecar.source_relative_path,
        source_sha256=artifact.sidecar.source_sha256,
        raw_text_sha256=artifact.sidecar.raw_extracted_text_sha256,
        output_relative_path=relative,
        sidecar_relative_path=sidecar_relative,
        status=status,
        readiness_status=artifact.sidecar.readiness_status,
        artifact_identity=artifact.sidecar.cleaning_identity,
        output_sha256=artifact.sidecar.cleaned_text_sha256,
        character_count=len(artifact.text),
        warning_count=len(artifact.sidecar.warnings),
    )


def _write_sidecar(path: Path, sidecar: CleaningSidecar | ReconstructionSidecar) -> str:
    write_json_atomic(path, sidecar.model_dump(mode="json"))
    return sha256_file(path)


def _write_clean_artifact(
    artifact: CleanedArtifact,
    entry: PreparationManifestEntry,
    configuration: PreparationConfiguration,
) -> PreparationManifestEntry:
    output = _safe_path(configuration.clean_output_root, entry.output_relative_path)
    sidecar_path = _safe_path(configuration.clean_output_root, entry.sidecar_relative_path)
    if (output.exists() or sidecar_path.exists()) and not (
        configuration.resume or configuration.overwrite
    ):
        raise FileExistsError(f"Clean output exists; use --resume or --overwrite: {output}")
    write_text_atomic(output, artifact.text)
    if sha256_file(output) != artifact.sidecar.cleaned_text_sha256:
        raise ValueError("Finalized cleaned output hash changed during atomic persistence.")
    sidecar_digest = _write_sidecar(sidecar_path, artifact.sidecar)
    CleaningSidecar.model_validate_json(sidecar_path.read_text(encoding="utf-8"))
    return entry.model_copy(update={"sidecar_sha256": sidecar_digest})


def _load_manifest(path: Path, kind: str) -> PreparationManifest | None:
    if not path.is_file():
        return None
    try:
        value = PreparationManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError):
        return None
    return value if value.kind == kind else None


def _current_entry(
    entry: PreparationManifestEntry,
    previous: PreparationManifestEntry | None,
    output_root: Path,
    sidecar_type: type[CleaningSidecar] | type[ReconstructionSidecar],
) -> tuple[bool, CleaningSidecar | ReconstructionSidecar | None]:
    if previous is None or previous.artifact_identity != entry.artifact_identity:
        return False, None
    if previous.output_sha256 is None or previous.sidecar_sha256 is None:
        return False, None
    output = _safe_path(output_root, previous.output_relative_path)
    sidecar_path = _safe_path(output_root, previous.sidecar_relative_path)
    if not output.is_file() or not sidecar_path.is_file():
        return False, None
    if (
        sha256_file(output) != previous.output_sha256
        or sha256_file(sidecar_path) != previous.sidecar_sha256
    ):
        return False, None
    try:
        sidecar = sidecar_type.model_validate_json(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError):
        return False, None
    output_digest = sha256_file(output)
    expected = (
        sidecar.cleaned_text_sha256
        if isinstance(sidecar, CleaningSidecar)
        else sidecar.reconstructed_text_sha256
    )
    return output_digest == expected, sidecar


def _manifest(
    *,
    kind: str,
    run_id: str,
    generated_at: datetime,
    input_root: Path,
    output_root: Path,
    entries: list[PreparationManifestEntry],
) -> PreparationManifest:
    return PreparationManifest(
        kind=kind,  # type: ignore[arg-type]
        run_id=run_id,
        generated_at=generated_at,
        input_root=str(input_root.resolve()),
        output_root=str(output_root.resolve()),
        entries=sorted(entries, key=lambda item: item.output_relative_path),
    )


def _persist_manifest(path: Path, manifest: PreparationManifest) -> None:
    write_json_atomic(path, manifest.model_dump(mode="json"))


def _replace_entry(
    entries: list[PreparationManifestEntry], entry: PreparationManifestEntry
) -> None:
    for index, existing in enumerate(entries):
        if existing.output_relative_path == entry.output_relative_path:
            entries[index] = entry
            return
    entries.append(entry)


def _is_heading(value: str) -> bool:
    text = " ".join(value.split())
    if not _HEADING.fullmatch(text) or text.startswith(("-", "[")):
        return False
    letters = [character for character in text if character.isalpha()]
    uppercase_ratio = (
        sum(character.isupper() for character in letters) / len(letters) if letters else 0
    )
    return uppercase_ratio >= 0.55 or bool(re.match(r"^(?:[IVXLC]+|\d+(?:\.\d+)*)[.)\-:]?\s", text))


def _segments(
    cleaned_text: str,
    sidecar: CleaningSidecar,
    context_budget: int,
) -> list[_Section]:
    retained = sorted(
        (span for span in sidecar.spans if span.retained and span.cleaned_end > span.cleaned_start),
        key=lambda item: item.cleaned_start,
    )
    readiness = {item.location_id: item for item in sidecar.location_readiness}
    max_characters = min(12000, max(6000, int(context_budget * 1.1)))
    natural: list[list[SourceSpan]] = []
    current: list[SourceSpan] = []
    for span in retained:
        value = cleaned_text[span.cleaned_start : span.cleaned_end]
        if current and _is_heading(value):
            natural.append(current)
            current = []
        current.append(span)
    if current:
        natural.append(current)

    split_natural: list[list[SourceSpan]] = []
    for group in natural:
        part: list[SourceSpan] = []
        length = 0
        for span in group:
            span_length = span.cleaned_end - span.cleaned_start + 2
            if part and length + span_length > max_characters:
                split_natural.append(part)
                part = []
                length = 0
            part.append(span)
            length += span_length
        if part:
            split_natural.append(part)

    packed: list[list[SourceSpan]] = []
    for group in split_natural:
        eligible = all(readiness[span.location_id].model_eligible for span in group)
        group_length = sum(span.cleaned_end - span.cleaned_start + 2 for span in group)
        if packed:
            previous = packed[-1]
            previous_eligible = all(readiness[span.location_id].model_eligible for span in previous)
            previous_length = sum(span.cleaned_end - span.cleaned_start + 2 for span in previous)
            if previous_eligible == eligible and previous_length + group_length <= max_characters:
                previous.extend(group)
                continue
        packed.append(list(group))

    result: list[_Section] = []
    for index, spans in enumerate(packed, start=1):
        statuses = tuple(dict.fromkeys(readiness[span.location_id].status for span in spans))
        result.append(
            _Section(
                section_id=f"section-{index:06d}",
                spans=tuple(spans),
                source_text="\n\n".join(
                    cleaned_text[span.cleaned_start : span.cleaned_end] for span in spans
                ),
                model_eligible=all(readiness[span.location_id].model_eligible for span in spans),
                readiness_statuses=statuses,
                reason_codes=tuple(
                    sorted(
                        {
                            reason
                            for span in spans
                            for reason in readiness[span.location_id].reason_codes
                        }
                    )
                ),
            )
        )
    return result


def _annotated_source(section: _Section) -> str:
    value = section.source_text.strip()
    if (
        ReadinessStatus.IMAGE_DEPENDENT in section.readiness_statuses
        or "probable_flattened_flowchart_or_spatial_layout" in section.reason_codes
    ):
        value += "\n\n" + AUTHORIZED_IMAGE_MARKER
    elif ReadinessStatus.UNUSABLE in section.readiness_statuses:
        value += "\n\n" + AUTHORIZED_INCOMPLETE_MARKER
    return value


def _simple_clean_document(sidecar: CleaningSidecar) -> bool:
    disruptive = {
        TransformationType.DUPLICATE_SUPPRESSION,
        TransformationType.SPLIT_WORD_REPAIR,
        TransformationType.FRAGMENT_REPAIR,
        TransformationType.TABLE_REORGANIZATION,
    }
    return sidecar.readiness_status is ReadinessStatus.READY and not any(
        item.transformation_type in disruptive for item in sidecar.transformations
    )


def _section_needs_model(section: _Section) -> bool:
    actionable = {
        "broken_sentence_fragments",
        "empty_or_detached_table",
        "malformed_heading",
    }
    return bool(actionable.intersection(section.reason_codes))


def _state_path(root: Path, identity: str) -> Path:
    return _safe_path(root, f".preparation-state/{identity}.json")


def _load_section_state(path: Path, identity: str) -> dict[str, dict[str, object]]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(value, dict) or value.get("reconstruction_identity") != identity:
        return {}
    sections = value.get("sections")
    if not isinstance(sections, dict):
        return {}
    return {str(key): item for key, item in sections.items() if isinstance(item, dict)}


def _save_section_state(path: Path, identity: str, sections: dict[str, dict[str, object]]) -> None:
    write_json_atomic(
        path,
        {
            "schema_version": PREPARATION_SCHEMA_VERSION,
            "reconstruction_identity": identity,
            "sections": sections,
        },
    )


def _model_section(
    section: _Section,
    cleaned_text: str,
    provider: OllamaPreparationProvider,
    model: ModelIdentity,
    configuration: PreparationConfiguration,
) -> _SectionResult:
    started = time.monotonic()
    span_values = [
        (span.span_id, cleaned_text[span.cleaned_start : span.cleaned_end])
        for span in section.spans
    ]
    response = provider.chat_json(
        model=model,
        system_prompt=RECONSTRUCTION_SYSTEM_PROMPT,
        user_prompt=reconstruction_user_prompt(section.section_id, span_values),
        response_schema=reconstruction_schema(),
        context_budget=configuration.context_budget,
        temperature=configuration.temperature,
        seed=configuration.seed,
        maximum_retries=configuration.maximum_retries,
    )
    draft = ReconstructionDraft.model_validate(response.content)
    transformations = [
        ModelTransformation(
            transformation_id=f"{section.section_id}:{item.transformation_id}",
            transformation_type=item.transformation_type,
            raw_span_ids=item.span_ids,
            cleaned_span_ids=item.span_ids,
            original_text=item.original_text,
            reconstructed_text=item.reconstructed_text,
            support_basis=item.support_basis,
            confidence=item.confidence,
            model_identity=model,
            validation_status="accepted",
        )
        for item in draft.transformations
    ]
    issues, suspicious = validate_reconstruction(
        section.source_text,
        draft.reconstructed_text,
        transformations,
        list(section.spans),
        span_texts=dict(span_values),
    )
    normalized_source = " ".join(section.source_text.split())
    normalized_output = " ".join(draft.reconstructed_text.split())
    if normalized_source != normalized_output and not transformations:
        issues.append(
            ValidationIssue(
                code="unreported_model_transformation",
                message="Model changed section text without declaring transformations.",
                severity="error",
                section_id=section.section_id,
            )
        )
    has_error = any(issue.severity == "error" for issue in issues)
    if has_error:
        rejected = tuple(
            item.model_copy(update={"validation_status": "rejected"}) for item in transformations
        )
        return _SectionResult(
            text=section.source_text,
            transformations=rejected,
            unresolved_fragments=tuple(draft.unresolved_fragments),
            image_annotations=tuple(draft.image_dependency_annotations),
            issues=tuple(issues),
            suspicious_additions=tuple(suspicious),
            status=PreparationStatus.NEEDS_HUMAN_REVIEW,
            generator_attempt_count=response.attempt_count,
            runtime_seconds=time.monotonic() - started,
        )
    status = (
        PreparationStatus.UNCHANGED_CLEAN
        if normalized_source == normalized_output
        else PreparationStatus.RECONSTRUCTED_WITH_WARNINGS
        if draft.unresolved_fragments or draft.image_dependency_annotations
        else PreparationStatus.RECONSTRUCTED
    )
    return _SectionResult(
        text=draft.reconstructed_text.strip(),
        transformations=tuple(transformations),
        unresolved_fragments=tuple(draft.unresolved_fragments),
        image_annotations=tuple(draft.image_dependency_annotations),
        issues=tuple(issues),
        suspicious_additions=tuple(suspicious),
        status=status,
        generator_attempt_count=response.attempt_count,
        runtime_seconds=time.monotonic() - started,
    )


def _section_result_payload(section: _Section, result: _SectionResult) -> dict[str, object]:
    return {
        "source_text_sha256": sha256(section.source_text.encode("utf-8")).hexdigest(),
        "text": result.text,
        "transformations": [item.model_dump(mode="json") for item in result.transformations],
        "unresolved_fragments": list(result.unresolved_fragments),
        "image_annotations": list(result.image_annotations),
        "issues": [item.model_dump(mode="json") for item in result.issues],
        "suspicious_additions": list(result.suspicious_additions),
        "status": result.status.value,
        "generator_attempt_count": result.generator_attempt_count,
        "runtime_seconds": result.runtime_seconds,
    }


def _section_result_from_payload(
    section: _Section, value: dict[str, object]
) -> _SectionResult | None:
    expected = sha256(section.source_text.encode("utf-8")).hexdigest()
    if value.get("source_text_sha256") != expected or not isinstance(value.get("text"), str):
        return None
    transformation_values = value.get("transformations")
    unresolved_values = value.get("unresolved_fragments")
    annotation_values = value.get("image_annotations")
    issue_values = value.get("issues")
    suspicious_values = value.get("suspicious_additions")
    status_value = value.get("status")
    attempt_value = value.get("generator_attempt_count")
    runtime_value = value.get("runtime_seconds")
    if (
        not isinstance(transformation_values, list)
        or not isinstance(unresolved_values, list)
        or not isinstance(annotation_values, list)
        or not isinstance(issue_values, list)
        or not isinstance(suspicious_values, list)
        or not isinstance(status_value, str)
    ):
        return None
    try:
        return _SectionResult(
            text=str(value["text"]),
            transformations=tuple(
                ModelTransformation.model_validate(item) for item in transformation_values
            ),
            unresolved_fragments=tuple(str(item) for item in unresolved_values),
            image_annotations=tuple(str(item) for item in annotation_values),
            issues=tuple(ValidationIssue.model_validate(item) for item in issue_values),
            suspicious_additions=tuple(str(item) for item in suspicious_values),
            status=PreparationStatus(status_value),
            generator_attempt_count=int(attempt_value) if isinstance(attempt_value, int) else 0,
            runtime_seconds=(
                float(runtime_value) if isinstance(runtime_value, (int, float)) else 0.0
            ),
        )
    except (TypeError, ValueError, ValidationError):
        return None


def _reconstruction_identity(
    prepared: _PreparedDocument,
    configuration: PreparationConfiguration,
    generator: ModelIdentity | None,
    reviewer: ModelIdentity | None,
    ollama_version: str | None,
) -> str:
    return _stable_hash(
        {
            "strategy": RECONSTRUCTION_VERSION,
            "schema_version": PREPARATION_SCHEMA_VERSION,
            "cleaning_identity": prepared.cleaning_sidecar.cleaning_identity,
            "cleaned_text_sha256": prepared.cleaning_sidecar.cleaned_text_sha256,
            "generator": generator.model_dump(mode="json")
            if generator
            else configuration.generator_model,
            "reviewer": reviewer.model_dump(mode="json")
            if reviewer
            else configuration.reviewer_model,
            "ollama_version": ollama_version,
            "prompt_sha256": prompt_hash(),
            "schema_sha256": schema_hash(),
            "context_budget": configuration.context_budget,
            "temperature": configuration.temperature,
            "seed": configuration.seed,
            "model_disabled": configuration.disable_model_reconstruction,
            "review_disabled": configuration.disable_medgemma_review,
        }
    )


def _base_reconstruction_entry(
    prepared: _PreparedDocument, identity: str
) -> PreparationManifestEntry:
    relative = prepared.raw.relative_path
    return PreparationManifestEntry(
        source_relative_path=prepared.cleaning_sidecar.source_relative_path,
        source_sha256=prepared.cleaning_sidecar.source_sha256,
        raw_text_sha256=prepared.cleaning_sidecar.raw_extracted_text_sha256,
        output_relative_path=relative,
        sidecar_relative_path=_sidecar_relative(relative, ".reconstruction.json"),
        status=PreparationStatus.RECONSTRUCTED,
        readiness_status=prepared.cleaning_sidecar.readiness_status,
        artifact_identity=identity,
    )


def _write_reconstruction(
    text: str,
    sidecar: ReconstructionSidecar,
    entry: PreparationManifestEntry,
    configuration: PreparationConfiguration,
) -> PreparationManifestEntry:
    output = _safe_path(configuration.reconstructed_output_root, entry.output_relative_path)
    sidecar_path = _safe_path(configuration.reconstructed_output_root, entry.sidecar_relative_path)
    write_text_atomic(output, text)
    digest = sha256_file(output)
    if digest != sidecar.reconstructed_text_sha256:
        raise ValueError("Finalized reconstructed output hash changed during persistence.")
    sidecar_digest = _write_sidecar(sidecar_path, sidecar)
    ReconstructionSidecar.model_validate_json(sidecar_path.read_text(encoding="utf-8"))
    return entry.model_copy(
        update={
            "status": sidecar.final_status,
            "output_sha256": digest,
            "sidecar_sha256": sidecar_digest,
            "character_count": len(text),
            "warning_count": len(sidecar.warnings) + len(sidecar.validation_issues),
        }
    )


def _reconstruct_document(
    prepared: _PreparedDocument,
    configuration: PreparationConfiguration,
    provider: OllamaPreparationProvider | None,
    generator: ModelIdentity | None,
    reviewer: ModelIdentity | None,
    ollama_version: str | None,
) -> tuple[str, ReconstructionSidecar, int]:
    started = time.monotonic()
    identity = _reconstruction_identity(
        prepared, configuration, generator, reviewer, ollama_version
    )
    sections = _segments(
        prepared.cleaned_text, prepared.cleaning_sidecar, configuration.context_budget
    )
    state_path = _state_path(configuration.reconstructed_output_root, identity)
    persisted = _load_section_state(state_path, identity) if configuration.resume else {}
    results: list[tuple[_Section, _SectionResult]] = []
    model_skipped = (
        configuration.dry_run
        or configuration.disable_model_reconstruction
        or _simple_clean_document(prepared.cleaning_sidecar)
        or prepared.cleaning_sidecar.readiness_status is ReadinessStatus.HUMAN_REVIEW_REQUIRED
    )
    for section in sections:
        existing = _section_result_from_payload(section, persisted.get(section.section_id, {}))
        if existing is not None:
            results.append((section, existing))
            continue
        if not section.model_eligible:
            location_status = (
                PreparationStatus.IMAGE_DEPENDENT
                if ReadinessStatus.IMAGE_DEPENDENT in section.readiness_statuses
                else PreparationStatus.UNUSABLE
            )
            result = _SectionResult(
                text=_annotated_source(section),
                transformations=(),
                unresolved_fragments=(
                    "Location retained without inferred content because extraction is incomplete.",
                ),
                image_annotations=(section.section_id,)
                if location_status is PreparationStatus.IMAGE_DEPENDENT
                else (),
                issues=(),
                suspicious_additions=(),
                status=location_status,
                generator_attempt_count=0,
                runtime_seconds=0.0,
            )
        elif model_skipped or not _section_needs_model(section):
            result = _SectionResult(
                text=section.source_text,
                transformations=(),
                unresolved_fragments=(),
                image_annotations=(),
                issues=(),
                suspicious_additions=(),
                status=PreparationStatus.UNCHANGED_CLEAN,
                generator_attempt_count=0,
                runtime_seconds=0.0,
            )
        elif provider is None or generator is None:
            result = _SectionResult(
                text=section.source_text,
                transformations=(),
                unresolved_fragments=(),
                image_annotations=(),
                issues=(
                    ValidationIssue(
                        code="generator_model_unavailable",
                        message=(
                            "Local generator model is unavailable; cleaned source was retained."
                        ),
                        severity="warning",
                        section_id=section.section_id,
                    ),
                ),
                suspicious_additions=(),
                status=PreparationStatus.MODEL_UNAVAILABLE,
                generator_attempt_count=0,
                runtime_seconds=0.0,
            )
        else:
            try:
                result = _model_section(
                    section, prepared.cleaned_text, provider, generator, configuration
                )
            except (LocalModelError, ValidationError, ValueError) as exc:
                result = _SectionResult(
                    text=section.source_text,
                    transformations=(),
                    unresolved_fragments=(),
                    image_annotations=(),
                    issues=(
                        ValidationIssue(
                            code="generator_model_failure",
                            message=f"{type(exc).__name__}: {exc}",
                            severity="error",
                            section_id=section.section_id,
                        ),
                    ),
                    suspicious_additions=(),
                    status=PreparationStatus.MODEL_FAILURE,
                    generator_attempt_count=configuration.maximum_retries + 1,
                    runtime_seconds=0.0,
                )
        results.append((section, result))
        if not configuration.dry_run:
            persisted[section.section_id] = _section_result_payload(section, result)
            _save_section_state(state_path, identity, persisted)

    output_parts: list[str] = []
    section_states: list[SectionState] = []
    transformations: list[ModelTransformation] = []
    unresolved: list[str] = []
    image_annotations: list[str] = []
    issues: list[ValidationIssue] = []
    suspicious_count = 0
    offset = 0
    statuses: list[PreparationStatus] = []
    for section, result in results:
        if output_parts:
            output_parts.append("\n\n")
            offset += 2
        start = offset
        value = result.text.strip()
        output_parts.append(value)
        offset += len(value)
        end = offset
        section_states.append(
            SectionState(
                section_id=section.section_id,
                span_ids=[span.span_id for span in section.spans],
                source_text_sha256=sha256(section.source_text.encode("utf-8")).hexdigest(),
                output_text_sha256=sha256(value.encode("utf-8")).hexdigest(),
                status=result.status,
                generator_attempt_count=result.generator_attempt_count,
                reviewer_attempt_count=0,
                runtime_seconds=result.runtime_seconds,
                reconstructed_start=start,
                reconstructed_end=end,
            )
        )
        transformations.extend(result.transformations)
        unresolved.extend(result.unresolved_fragments)
        image_annotations.extend(result.image_annotations)
        issues.extend(result.issues)
        suspicious_count += len(result.suspicious_additions)
        statuses.append(result.status)
    output = "".join(output_parts).strip() + "\n"
    if not sections:
        output = prepared.cleaned_text
        statuses.append(PreparationStatus.UNUSABLE)
    if PreparationStatus.NEEDS_HUMAN_REVIEW in statuses:
        final_status = PreparationStatus.NEEDS_HUMAN_REVIEW
    elif prepared.cleaning_sidecar.readiness_status is ReadinessStatus.HUMAN_REVIEW_REQUIRED:
        final_status = PreparationStatus.NEEDS_HUMAN_REVIEW
    elif (
        prepared.cleaning_sidecar.readiness_status is ReadinessStatus.PARTIALLY_RECONSTRUCTABLE
        and statuses
        and all(status is PreparationStatus.UNCHANGED_CLEAN for status in statuses)
    ):
        final_status = PreparationStatus.PARTIALLY_RECONSTRUCTABLE
    elif PreparationStatus.MODEL_FAILURE in statuses:
        final_status = PreparationStatus.MODEL_FAILURE
    elif PreparationStatus.MODEL_UNAVAILABLE in statuses:
        final_status = PreparationStatus.MODEL_UNAVAILABLE
    elif PreparationStatus.UNUSABLE in statuses and all(
        status is PreparationStatus.UNUSABLE for status in statuses
    ):
        final_status = PreparationStatus.UNUSABLE
    elif PreparationStatus.IMAGE_DEPENDENT in statuses and all(
        status in {PreparationStatus.IMAGE_DEPENDENT, PreparationStatus.UNUSABLE}
        for status in statuses
    ):
        final_status = PreparationStatus.IMAGE_DEPENDENT
    elif any(
        status
        in {
            PreparationStatus.IMAGE_DEPENDENT,
            PreparationStatus.UNUSABLE,
            PreparationStatus.RECONSTRUCTED_WITH_WARNINGS,
        }
        for status in statuses
    ):
        final_status = PreparationStatus.RECONSTRUCTED_WITH_WARNINGS
    elif statuses and all(status is PreparationStatus.UNCHANGED_CLEAN for status in statuses):
        final_status = PreparationStatus.UNCHANGED_CLEAN
    else:
        final_status = PreparationStatus.RECONSTRUCTED
    warnings = list(prepared.cleaning_sidecar.warnings)
    if model_skipped:
        warnings.append(
            "Model reconstruction was skipped because deterministic cleaned text was coherent."
        )
    sidecar = ReconstructionSidecar(
        reconstruction_identity=identity,
        source_relative_path=prepared.cleaning_sidecar.source_relative_path,
        source_sha256=prepared.cleaning_sidecar.source_sha256,
        raw_extracted_text_sha256=prepared.cleaning_sidecar.raw_extracted_text_sha256,
        cleaned_text_sha256=prepared.cleaning_sidecar.cleaned_text_sha256,
        reconstructed_text_sha256=sha256(output.encode("utf-8")).hexdigest(),
        generator_model=generator,
        reviewer_model=None,
        ollama_version=ollama_version,
        prompt_version=PROMPT_VERSION,
        prompt_sha256=prompt_hash(),
        schema_sha256=schema_hash(),
        document_status=prepared.cleaning_sidecar.readiness_status,
        detected_language=prepared.cleaning_sidecar.detected_language,
        detected_title=prepared.cleaning_sidecar.detected_title,
        teacher_names=prepared.cleaning_sidecar.teacher_names,
        institutions=prepared.cleaning_sidecar.institutions,
        deterministic_transformations=prepared.cleaning_sidecar.transformations,
        model_transformations=transformations,
        repaired_fragments=[
            item.transformation_id
            for item in transformations
            if item.transformation_type
            in {TransformationType.SPLIT_WORD_REPAIR, TransformationType.FRAGMENT_REPAIR}
            and item.validation_status == "accepted"
        ],
        unresolved_fragments=unresolved,
        removed_duplicates=prepared.cleaning_sidecar.removed_duplicates,
        retained_duplicates=prepared.cleaning_sidecar.retained_duplicates,
        image_dependent_locations=sorted(set(image_annotations)),
        warnings=warnings,
        validation_issues=issues,
        sections=section_states,
        runtime_seconds=time.monotonic() - started,
        retry_count=sum(max(0, state.generator_attempt_count - 1) for state in section_states),
        final_status=final_status,
    )
    return output, sidecar, suspicious_count


def _review_document(
    prepared: _PreparedDocument,
    text: str,
    sidecar: ReconstructionSidecar,
    provider: OllamaPreparationProvider,
    reviewer: ModelIdentity,
    configuration: PreparationConfiguration,
) -> tuple[str, ReconstructionSidecar]:
    accepted_transformations = [
        item for item in sidecar.model_transformations if item.validation_status == "accepted"
    ]
    if not accepted_transformations:
        return text, sidecar.model_copy(update={"reviewer_model": reviewer})
    findings: list[ReviewerFinding] = []
    attempt_count = 0
    transformations_by_section: dict[str, list[ModelTransformation]] = {}
    for transformation in accepted_transformations:
        section_id = transformation.transformation_id.partition(":")[0]
        transformations_by_section.setdefault(section_id, []).append(transformation)
    span_by_id = {span.span_id: span for span in prepared.cleaning_sidecar.spans}
    section_by_id = {section.section_id: section for section in sidecar.sections}
    disagreement = False
    review_failure: str | None = None
    for section_id, transformations in transformations_by_section.items():
        section = section_by_id.get(section_id)
        if section is None:
            disagreement = True
            continue
        source_spans = [
            (
                span_id,
                prepared.cleaned_text[
                    span_by_id[span_id].cleaned_start : span_by_id[span_id].cleaned_end
                ],
            )
            for span_id in section.span_ids
            if span_id in span_by_id
        ]
        section_text = text[section.reconstructed_start : section.reconstructed_end]
        try:
            response = provider.chat_json(
                model=reviewer,
                system_prompt=REVIEW_SYSTEM_PROMPT,
                user_prompt=review_user_prompt(
                    section_id,
                    source_spans,
                    section_text,
                    [item.model_dump(mode="json") for item in transformations],
                ),
                response_schema=review_schema(),
                context_budget=configuration.context_budget,
                temperature=0.0,
                seed=configuration.seed,
                maximum_retries=configuration.maximum_retries,
            )
            attempt_count += response.attempt_count
            draft = ReviewDraft.model_validate(response.content)
        except (LocalModelError, ValidationError, ValueError) as exc:
            review_failure = f"{type(exc).__name__}: {exc}"
            disagreement = True
            break
        known_transformation_ids = {item.transformation_id for item in transformations}
        reviewed_ids: set[str] = set()
        for item in draft.findings:
            if item.transformation_id is not None:
                reviewed_ids.add(item.transformation_id)
            finding = ReviewerFinding.model_validate(item.model_dump())
            findings.append(finding)
            if finding.verdict in {
                ReviewVerdict.UNSUPPORTED,
                ReviewVerdict.AMBIGUOUS,
                ReviewVerdict.POSSIBLE_EXTRACTION_ERROR,
            }:
                disagreement = True
        if not known_transformation_ids.issubset(reviewed_ids):
            disagreement = True
            findings.append(
                ReviewerFinding(
                    transformation_id=None,
                    verdict=ReviewVerdict.AMBIGUOUS,
                    source_span_ids=section.span_ids,
                    message="Reviewer did not classify every supplied transformation.",
                )
            )

    updates: dict[str, object] = {
        "reviewer_model": reviewer,
        "reviewer_findings": findings,
        "retry_count": sidecar.retry_count
        + max(0, attempt_count - len(transformations_by_section)),
    }
    if review_failure is not None:
        fallback = prepared.cleaned_text
        issue = ValidationIssue(
            code="reviewer_model_failure",
            message=review_failure,
            severity="error",
        )
        updates.update(
            {
                "reconstructed_text_sha256": sha256(fallback.encode("utf-8")).hexdigest(),
                "validation_issues": [*sidecar.validation_issues, issue],
                "warnings": [*sidecar.warnings, "Reviewer failed; cleaned source was retained."],
                "final_status": PreparationStatus.MODEL_FAILURE,
                "model_transformations": [
                    item.model_copy(update={"validation_status": "needs_human_review"})
                    for item in sidecar.model_transformations
                ],
            }
        )
        return fallback, sidecar.model_copy(update=updates)
    if disagreement:
        fallback = prepared.cleaned_text
        updates.update(
            {
                "reconstructed_text_sha256": sha256(fallback.encode("utf-8")).hexdigest(),
                "warnings": [
                    *sidecar.warnings,
                    "Gemma and MedGemma did not agree; cleaned source was retained.",
                ],
                "final_status": PreparationStatus.NEEDS_HUMAN_REVIEW,
                "model_transformations": [
                    item.model_copy(update={"validation_status": "needs_human_review"})
                    for item in sidecar.model_transformations
                ],
            }
        )
        return fallback, sidecar.model_copy(update=updates)
    return text, sidecar.model_copy(update=updates)


def _failure_attempt(report_directory: Path, relative: str, stage: str, error: str) -> None:
    identity = _stable_hash({"relative": relative, "stage": stage})[:24]
    directory = report_directory / "failure-attempts" / identity
    existing = sorted(directory.glob("attempt-*.json")) if directory.is_dir() else []
    write_json_atomic(
        directory / f"attempt-{len(existing) + 1:04d}.json",
        {
            "source_relative_path": relative,
            "stage": stage,
            "error": error,
            "recorded_at": _utc_now().isoformat(),
        },
    )


def _hardware_usage() -> dict[str, object]:
    usage: dict[str, object] = {
        "cpu_count": os.cpu_count(),
        "peak_process_ram_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    }
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                usage["system_ram_bytes"] = int(line.split()[1]) * 1024
                break
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is not None:
        try:
            result = subprocess.run(
                [
                    nvidia_smi,
                    "--query-gpu=name,memory.total,memory.used",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                check=True,
                text=True,
                timeout=10,
            )
            usage["gpu_snapshot"] = result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            usage["gpu_snapshot"] = "unavailable"
    return usage


def _persist_reports(
    directory: Path,
    report: PreparationRunReport,
    cleaning_entries: list[PreparationManifestEntry],
    reconstruction_entries: list[PreparationManifestEntry],
    sidecars: list[ReconstructionSidecar],
) -> None:
    write_json_atomic(directory / "run-report.json", report.model_dump(mode="json"))
    write_json_atomic(
        directory / "cleaning-summary.json",
        {
            "counts": dict(Counter(entry.status.value for entry in cleaning_entries)),
            "entries": [entry.model_dump(mode="json") for entry in cleaning_entries],
        },
    )
    write_json_atomic(
        directory / "readiness-summary.json",
        {
            "counts": dict(
                Counter(
                    entry.readiness_status.value
                    for entry in cleaning_entries
                    if entry.readiness_status is not None
                )
            ),
            "entries": [
                {
                    "source_relative_path": entry.source_relative_path,
                    "readiness_status": entry.readiness_status.value
                    if entry.readiness_status
                    else None,
                }
                for entry in cleaning_entries
            ],
        },
    )
    write_json_atomic(
        directory / "reconstruction-summary.json",
        {
            "counts": dict(Counter(entry.status.value for entry in reconstruction_entries)),
            "entries": [entry.model_dump(mode="json") for entry in reconstruction_entries],
        },
    )
    write_json_atomic(
        directory / "model-repairs.json",
        [
            {
                "source_relative_path": sidecar.source_relative_path,
                "transformation_id": item.transformation_id,
                "transformation_type": item.transformation_type.value,
                "validation_status": item.validation_status,
            }
            for sidecar in sidecars
            for item in sidecar.model_transformations
        ],
    )
    write_json_atomic(
        directory / "suspicious-additions.json",
        [
            {
                "source_relative_path": sidecar.source_relative_path,
                "issue": issue.model_dump(mode="json"),
            }
            for sidecar in sidecars
            for issue in sidecar.validation_issues
            if issue.code.startswith("unsupported_") or issue.code.startswith("changed_")
        ],
    )
    groups = {
        "image-dependent.json": {PreparationStatus.IMAGE_DEPENDENT},
        "human-review-required.json": {PreparationStatus.NEEDS_HUMAN_REVIEW},
        "unusable.json": {PreparationStatus.UNUSABLE},
        "failures.json": {
            PreparationStatus.FAILED,
            PreparationStatus.MODEL_FAILURE,
            PreparationStatus.VALIDATION_FAILURE,
        },
        "skipped.json": {PreparationStatus.SKIPPED_CURRENT},
    }
    for filename, statuses in groups.items():
        write_json_atomic(
            directory / filename,
            [
                entry.model_dump(mode="json")
                for entry in reconstruction_entries
                if entry.status in statuses
            ],
        )


def prepare_course_text_tree(
    configuration: PreparationConfiguration,
    *,
    now: Callable[[], datetime] = _utc_now,
    monotonic: Callable[[], float] = time.monotonic,
    provider_factory: Callable[[str, float], OllamaPreparationProvider] = (
        lambda base_url, timeout: OllamaPreparationProvider(base_url, timeout)
    ),
) -> PreparationRunResult:
    """Prepare every selected export sequentially without generating study material."""
    _validate_roots(configuration)
    started_at = now()
    started_clock = monotonic()
    before = _snapshot(configuration.input_root)
    upstream = load_export_manifest(configuration.input_root)
    discovered = discover_exports(
        configuration.input_root,
        upstream,
        selected_file=configuration.file,
        limit=configuration.limit,
    )
    provider: OllamaPreparationProvider | None = None
    generator: ModelIdentity | None = None
    reviewer: ModelIdentity | None = None
    ollama_version: str | None = None
    if not configuration.disable_model_reconstruction:
        try:
            provider = provider_factory(
                configuration.ollama_base_url, configuration.timeout_seconds
            )
            ollama_version = provider.version()
            generator = provider.resolve_model(configuration.generator_model)
            if not configuration.disable_medgemma_review and configuration.reviewer_model:
                reviewer = provider.resolve_model(configuration.reviewer_model, reviewer=True)
        except LocalModelError:
            provider = None
            generator = None
            reviewer = None
    run_id = _stable_hash(
        {
            "strategy": "medplat-course-preparation-run-v1",
            "schema_version": PREPARATION_SCHEMA_VERSION,
            "input_root": str(configuration.input_root.resolve()),
            "files": [
                {
                    "relative": path.relative_to(configuration.input_root).as_posix(),
                    "sha256": entry.output_sha256,
                }
                for path, entry in discovered
            ],
            "cleaning_version": CLEANING_VERSION,
            "reconstruction_version": RECONSTRUCTION_VERSION,
            "generator": generator.model_dump(mode="json")
            if generator
            else configuration.generator_model,
            "reviewer": reviewer.model_dump(mode="json")
            if reviewer
            else configuration.reviewer_model,
            "location_markers": configuration.location_markers.value,
            "context_budget": configuration.context_budget,
            "temperature": configuration.temperature,
            "seed": configuration.seed,
            "file": configuration.file.as_posix() if configuration.file else None,
            "limit": configuration.limit,
        }
    )[:24]
    report_directory = None if configuration.dry_run else configuration.report_output_root / run_id
    if not configuration.dry_run:
        configuration.clean_output_root.mkdir(parents=True, exist_ok=True)
        configuration.reconstructed_output_root.mkdir(parents=True, exist_ok=True)
        assert report_directory is not None
        report_directory.mkdir(parents=True, exist_ok=True)

    clean_manifest_path = configuration.clean_output_root / "cleaning-manifest.json"
    reconstruction_manifest_path = (
        configuration.reconstructed_output_root / "reconstruction-manifest.json"
    )
    previous_clean_manifest = (
        _load_manifest(clean_manifest_path, "cleaning") if configuration.resume else None
    )
    previous_reconstruction_manifest = (
        _load_manifest(reconstruction_manifest_path, "reconstruction")
        if configuration.resume
        else None
    )
    previous_clean = (
        {entry.output_relative_path: entry for entry in previous_clean_manifest.entries}
        if previous_clean_manifest
        else {}
    )
    previous_reconstruction = (
        {entry.output_relative_path: entry for entry in previous_reconstruction_manifest.entries}
        if previous_reconstruction_manifest
        else {}
    )
    cleaning_entries: list[PreparationManifestEntry] = []
    reconstruction_entries: list[PreparationManifestEntry] = []
    prepared_documents: list[_PreparedDocument] = []
    reconstruction_sidecars: list[ReconstructionSidecar] = []
    cleaning_started = monotonic()
    readiness_seconds = 0.0

    for path, upstream_entry in discovered:
        relative = path.relative_to(configuration.input_root).as_posix()
        try:
            raw = parse_raw_export(path, configuration.input_root, upstream_entry)
            readiness_started = monotonic()
            artifact = clean_export(raw, configuration.location_markers)
            readiness_seconds += monotonic() - readiness_started
            proposed = _clean_entry(artifact, relative)
            current, loaded = (
                _current_entry(
                    proposed,
                    previous_clean.get(relative),
                    configuration.clean_output_root,
                    CleaningSidecar,
                )
                if configuration.resume
                else (False, None)
            )
            if current and isinstance(loaded, CleaningSidecar):
                cleaned_text = _safe_path(configuration.clean_output_root, relative).read_text(
                    encoding="utf-8"
                )
                previous = previous_clean[relative]
                entry = previous.model_copy(update={"status": PreparationStatus.SKIPPED_CURRENT})
                sidecar = loaded
            else:
                cleaned_text = artifact.text
                sidecar = artifact.sidecar
                entry = proposed
                if not configuration.dry_run:
                    entry = _write_clean_artifact(artifact, entry, configuration)
            _replace_entry(cleaning_entries, entry)
            prepared_documents.append(
                _PreparedDocument(
                    raw=raw,
                    cleaned_text=cleaned_text,
                    cleaning_sidecar=sidecar,
                    clean_entry=entry,
                )
            )
        except (OSError, ValidationError, ValueError) as exc:
            if upstream_entry.source_sha256 is None or upstream_entry.output_sha256 is None:
                continue
            failed = PreparationManifestEntry(
                source_relative_path=upstream_entry.source_relative_path,
                source_sha256=upstream_entry.source_sha256,
                raw_text_sha256=upstream_entry.output_sha256,
                output_relative_path=relative,
                sidecar_relative_path=_sidecar_relative(relative, ".cleaning.json"),
                status=PreparationStatus.FAILED,
                artifact_identity=_stable_hash({"path": relative, "failure": "cleaning"}),
                error=f"{type(exc).__name__}: {exc}",
            )
            _replace_entry(cleaning_entries, failed)
            if report_directory is not None:
                _failure_attempt(report_directory, relative, "cleaning", failed.error or "unknown")
        if not configuration.dry_run:
            _persist_manifest(
                clean_manifest_path,
                _manifest(
                    kind="cleaning",
                    run_id=run_id,
                    generated_at=now(),
                    input_root=configuration.input_root,
                    output_root=configuration.clean_output_root,
                    entries=cleaning_entries,
                ),
            )
    cleaning_seconds = monotonic() - cleaning_started

    reconstruction_started = monotonic()
    for prepared in prepared_documents:
        relative = prepared.raw.relative_path
        identity = _reconstruction_identity(
            prepared, configuration, generator, reviewer, ollama_version
        )
        proposed = _base_reconstruction_entry(prepared, identity)
        current, loaded = (
            _current_entry(
                proposed,
                previous_reconstruction.get(relative),
                configuration.reconstructed_output_root,
                ReconstructionSidecar,
            )
            if configuration.resume
            else (False, None)
        )
        review_complete = (
            not reviewer
            or not isinstance(loaded, ReconstructionSidecar)
            or not any(
                item.validation_status == "accepted" for item in loaded.model_transformations
            )
            or loaded.reviewer_model == reviewer
        )
        if current and isinstance(loaded, ReconstructionSidecar) and review_complete:
            previous = previous_reconstruction[relative]
            entry = previous.model_copy(update={"status": PreparationStatus.SKIPPED_CURRENT})
            _replace_entry(reconstruction_entries, entry)
            reconstruction_sidecars.append(loaded)
            continue
        try:
            output, recon_sidecar, _ = _reconstruct_document(
                prepared,
                configuration,
                provider,
                generator,
                reviewer,
                ollama_version,
            )
            entry = proposed.model_copy(
                update={
                    "status": recon_sidecar.final_status,
                    "output_sha256": recon_sidecar.reconstructed_text_sha256,
                    "character_count": len(output),
                    "warning_count": len(recon_sidecar.warnings)
                    + len(recon_sidecar.validation_issues),
                }
            )
            if not configuration.dry_run:
                entry = _write_reconstruction(output, recon_sidecar, entry, configuration)
            _replace_entry(reconstruction_entries, entry)
            reconstruction_sidecars.append(recon_sidecar)
        except (OSError, ValidationError, ValueError) as exc:
            failed = proposed.model_copy(
                update={
                    "status": PreparationStatus.FAILED,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            _replace_entry(reconstruction_entries, failed)
            if report_directory is not None:
                _failure_attempt(
                    report_directory, relative, "reconstruction", failed.error or "unknown"
                )
        if not configuration.dry_run:
            _persist_manifest(
                reconstruction_manifest_path,
                _manifest(
                    kind="reconstruction",
                    run_id=run_id,
                    generated_at=now(),
                    input_root=configuration.clean_output_root,
                    output_root=configuration.reconstructed_output_root,
                    entries=reconstruction_entries,
                ),
            )

    if (
        provider is not None
        and generator is not None
        and reviewer is not None
        and not configuration.dry_run
    ):
        try:
            provider.unload(generator)
        except LocalModelError:
            pass
        sidecar_by_path = {item.source_relative_path: item for item in reconstruction_sidecars}
        prepared_by_source = {
            item.cleaning_sidecar.source_relative_path: item for item in prepared_documents
        }
        for entry in list(reconstruction_entries):
            review_sidecar = sidecar_by_path.get(entry.source_relative_path)
            review_prepared = prepared_by_source.get(entry.source_relative_path)
            if (
                review_sidecar is None
                or review_prepared is None
                or not any(
                    item.validation_status == "accepted"
                    for item in review_sidecar.model_transformations
                )
                or review_sidecar.reviewer_model == reviewer
                or entry.status is PreparationStatus.SKIPPED_CURRENT
            ):
                continue
            try:
                path = _safe_path(
                    configuration.reconstructed_output_root, entry.output_relative_path
                )
                text = path.read_text(encoding="utf-8")
                reviewed_text, reviewed_sidecar = _review_document(
                    review_prepared,
                    text,
                    review_sidecar,
                    provider,
                    reviewer,
                    configuration,
                )
                reviewed_entry = _write_reconstruction(
                    reviewed_text, reviewed_sidecar, entry, configuration
                )
                _replace_entry(reconstruction_entries, reviewed_entry)
                reconstruction_sidecars.remove(review_sidecar)
                reconstruction_sidecars.append(reviewed_sidecar)
                sidecar_by_path[entry.source_relative_path] = reviewed_sidecar
            except (OSError, ValidationError, ValueError, LocalModelError) as exc:
                failed = entry.model_copy(
                    update={
                        "status": PreparationStatus.MODEL_FAILURE,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                _replace_entry(reconstruction_entries, failed)
                if report_directory is not None:
                    _failure_attempt(
                        report_directory,
                        entry.output_relative_path,
                        "review",
                        failed.error or "unknown",
                    )
            _persist_manifest(
                reconstruction_manifest_path,
                _manifest(
                    kind="reconstruction",
                    run_id=run_id,
                    generated_at=now(),
                    input_root=configuration.clean_output_root,
                    output_root=configuration.reconstructed_output_root,
                    entries=reconstruction_entries,
                ),
            )
        try:
            provider.unload(reviewer)
        except LocalModelError:
            pass
    reconstruction_seconds = monotonic() - reconstruction_started

    after = _snapshot(configuration.input_root)
    source_changes = _snapshot_changes(before, after)
    completed_at = now()
    status_counts = Counter(entry.status.value for entry in reconstruction_entries)
    readiness_counts = Counter(
        entry.readiness_status.value
        for entry in cleaning_entries
        if entry.readiness_status is not None
    )
    report = PreparationRunReport(
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        dry_run=configuration.dry_run,
        input_root=str(configuration.input_root.resolve()),
        clean_output_root=str(configuration.clean_output_root.resolve()),
        reconstructed_output_root=str(configuration.reconstructed_output_root.resolve()),
        report_output_root=str(configuration.report_output_root.resolve()),
        total_raw_text_files=len(discovered),
        total_cleaned_files=sum(entry.output_sha256 is not None for entry in cleaning_entries),
        total_reconstructed_files=sum(
            entry.output_sha256 is not None for entry in reconstruction_entries
        ),
        status_counts=dict(status_counts),
        readiness_counts=dict(readiness_counts),
        files_with_metadata_removed=sum(
            entry.status is not PreparationStatus.FAILED for entry in cleaning_entries
        ),
        duplicate_blocks_suppressed=sum(
            len(item.removed_duplicates) for item in reconstruction_sidecars
        ),
        split_words_repaired=sum(
            item.transformation_type is TransformationType.SPLIT_WORD_REPAIR
            for sidecar in reconstruction_sidecars
            for item in sidecar.deterministic_transformations
        ),
        fragment_repairs=sum(len(item.repaired_fragments) for item in reconstruction_sidecars),
        suspicious_additions_rejected=sum(
            issue.code.startswith("unsupported_") or issue.code.startswith("changed_")
            for sidecar in reconstruction_sidecars
            for issue in sidecar.validation_issues
        ),
        cleaning_duration_seconds=cleaning_seconds,
        readiness_duration_seconds=readiness_seconds,
        reconstruction_duration_seconds=reconstruction_seconds,
        total_duration_seconds=max(0.0, monotonic() - started_clock),
        generator_model=generator,
        reviewer_model=reviewer,
        ollama_version=ollama_version,
        hardware_usage=_hardware_usage(),
        source_immutable=not source_changes,
        source_changes=source_changes,
    )
    cleaning_manifest = _manifest(
        kind="cleaning",
        run_id=run_id,
        generated_at=completed_at,
        input_root=configuration.input_root,
        output_root=configuration.clean_output_root,
        entries=cleaning_entries,
    )
    reconstruction_manifest = _manifest(
        kind="reconstruction",
        run_id=run_id,
        generated_at=completed_at,
        input_root=configuration.clean_output_root,
        output_root=configuration.reconstructed_output_root,
        entries=reconstruction_entries,
    )
    if not configuration.dry_run:
        _persist_manifest(clean_manifest_path, cleaning_manifest)
        _persist_manifest(reconstruction_manifest_path, reconstruction_manifest)
        assert report_directory is not None
        _persist_reports(
            report_directory,
            report,
            cleaning_entries,
            reconstruction_entries,
            reconstruction_sidecars,
        )
    if source_changes:
        raise ValueError("Immutable raw text tree changed during course-text preparation.")
    return PreparationRunResult(
        cleaning_manifest=cleaning_manifest,
        reconstruction_manifest=reconstruction_manifest,
        report=report,
        report_directory=report_directory,
    )
