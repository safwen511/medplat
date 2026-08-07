from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ingestion.hashing import sha256_file
from ingestion.preparation.cleaning import clean_export
from ingestion.preparation.models import (
    LocationMarkerMode,
    ModelIdentity,
    ModelTransformation,
    PreparationConfiguration,
    PreparationStatus,
    ReadinessStatus,
    SourceSpan,
    TransformationType,
)
from ingestion.preparation.parsing import (
    discover_exports,
    load_export_manifest,
    parse_raw_export,
)
from ingestion.preparation.provider import OllamaPreparationProvider, StructuredResponse
from ingestion.preparation.service import _failure_attempt, prepare_course_text_tree
from ingestion.preparation.validation import validate_reconstruction
from ingestion.text_tree.models import (
    ExportStatus,
    TextExportEntry,
    TextExportManifest,
)

SOURCE_HASH = "a" * 64
GENERATOR = ModelIdentity(
    tag="gemma3:12b",
    digest="b" * 64,
    size_bytes=8_000_000_000,
    parameter_size="12.2B",
    quantization="Q4_K_M",
)
REVIEWER = ModelIdentity(
    tag="medgemma:4b",
    digest="c" * 64,
    size_bytes=3_300_000_000,
    parameter_size="4.3B",
    quantization="Q4_K_M",
)


def _export_value(relative_source: str, body: str, *, document_type: str = "pdf") -> str:
    extension = (
        ".pptx" if document_type == "powerpoint" else ".docx" if document_type == "word" else ".pdf"
    )
    return "\n".join(
        [
            f"SOURCE_FILE: {Path(relative_source).name}",
            f"SOURCE_RELATIVE_PATH: {relative_source}",
            f"SOURCE_EXTENSION: {extension}",
            f"SOURCE_SHA256: {SOURCE_HASH}",
            f"DOCUMENT_TYPE: {document_type}",
            "EXTRACTION_STATUS: exported",
            "EXTRACTION_TOOL: synthetic-local-test",
            "EXPORTED_AT: 2026-08-03T00:00:00+00:00",
            "TEXT_EXPORT_SCHEMA_VERSION: 1.0.0",
            "",
            body.rstrip(),
            "",
        ]
    )


def _library(
    root: Path,
    files: dict[str, tuple[str, str, str]],
) -> None:
    entries: list[TextExportEntry] = []
    for relative, (relative_source, body, document_type) in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _export_value(relative_source, body, document_type=document_type),
            encoding="utf-8",
        )
        extension = (
            ".pptx"
            if document_type == "powerpoint"
            else ".docx"
            if document_type == "word"
            else ".pdf"
        )
        entries.append(
            TextExportEntry(
                source_relative_path=relative_source,
                source_sha256=SOURCE_HASH,
                source_size_bytes=100,
                extension=extension,
                output_relative_path=relative,
                export_status=ExportStatus.EXPORTED,
                extraction_tool="synthetic-local-test",
                text_character_count=len(body),
                page_or_slide_count=(
                    body.count("===== PAGE")
                    if document_type == "pdf"
                    else body.count("===== SLIDE")
                    if document_type == "powerpoint"
                    else None
                ),
                export_identity="d" * 64,
                output_sha256=sha256_file(path),
            )
        )
    manifest = TextExportManifest(
        run_id="e" * 24,
        generated_at=datetime.now(timezone.utc),
        input_root=str((root.parent / "sources").resolve()),
        output_root=str(root.resolve()),
        entries=entries,
    )
    (root / "export-manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )


def _parsed(root: Path, relative: str):  # type: ignore[no-untyped-def]
    manifest = load_export_manifest(root)
    path, entry = discover_exports(root, manifest, selected_file=Path(relative), limit=None)[0]
    return parse_raw_export(path, root, entry)


def test_metadata_removed_title_teacher_institution_retained_and_markers_compacted(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    body = """===== PAGE 1 =====

FACULTE DE MEDECINE DE SFAX

CANCER DU REIN

Dr Nadia Test

Introduction clinique.

===== PAGE 2 =====

Dr Nadia Test

Suite du cours."""
    _library(root, {"A/Cours.txt": ("A/Cours.pdf", body, "pdf")})
    artifact = clean_export(_parsed(root, "A/Cours.txt"), LocationMarkerMode.COMPACT)
    assert "SOURCE_FILE:" not in artifact.text
    assert "[Page 1]" in artifact.text and "===== PAGE" not in artifact.text
    assert artifact.text.count("Dr Nadia Test") == 1
    assert "CANCER DU REIN" in artifact.text
    assert artifact.sidecar.teacher_names == ["Dr Nadia Test"]
    assert artifact.sidecar.institutions == ["FACULTE DE MEDECINE DE SFAX"]
    assert artifact.sidecar.metadata_header["SOURCE_SHA256"] == SOURCE_HASH


@pytest.mark.parametrize(
    ("mode", "expected", "forbidden"),
    [
        (LocationMarkerMode.KEEP, "===== SLIDE 1 =====", "[Slide 1]"),
        (LocationMarkerMode.COMPACT, "[Slide 1]", "===== SLIDE 1 ====="),
        (LocationMarkerMode.REMOVE, "Texte", "Slide 1"),
    ],
)
def test_slide_marker_modes(
    tmp_path: Path, mode: LocationMarkerMode, expected: str, forbidden: str
) -> None:
    root = tmp_path / "raw"
    body = "===== SLIDE 1 =====\n\nTITLE:\nCours\n\nCONTENT:\nTexte\n\nNOTES:\n"
    _library(root, {"slide.txt": ("slide.pptx", body, "powerpoint")})
    artifact = clean_export(_parsed(root, "slide.txt"), mode)
    assert expected in artifact.text
    assert forbidden not in artifact.text
    assert "TITLE:" not in artifact.text and "CONTENT:" not in artifact.text


def test_split_word_table_duplicate_legitimate_repetition_and_provenance(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    body = """===== PAGE 1 =====

Le carci-
nome est cité.

===== TABLE 1 =====

Valeur | Dose | Unité | Traitement

Valeur Dose Unité Traitement

Répétition légitime.

Intermédiaire.

Répétition légitime."""
    _library(root, {"course.txt": ("course.pdf", body, "pdf")})
    artifact = clean_export(_parsed(root, "course.txt"), LocationMarkerMode.COMPACT)
    assert "carcinome" in artifact.text
    assert artifact.text.count("Valeur Dose Unité Traitement") == 0
    assert artifact.text.count("Répétition légitime.") == 2
    assert artifact.sidecar.removed_duplicates
    retained = [span for span in artifact.sidecar.spans if span.retained]
    assert all(artifact.text[span.cleaned_start : span.cleaned_end].strip() for span in retained)


def test_readiness_detects_ocr_noise_sparse_images_and_ambiguous_numbers(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    files = {
        "scan.txt": (
            "scan.pdf",
            "===== PAGE 1 =====\n\nCamScanner\n\nFigure 1",
            "pdf",
        ),
        "noise.txt": (
            "noise.pdf",
            "===== PAGE 1 =====\n\nee eas,\n\nn --- |\n\nque¥ ey re\n\n©",
            "pdf",
        ),
        "number.txt": (
            "number.pdf",
            "===== PAGE 1 =====\n\nValeur extraite 10  8 BK dans un paragraphe lisible.",
            "pdf",
        ),
    }
    _library(root, files)
    scan = clean_export(_parsed(root, "scan.txt"), LocationMarkerMode.COMPACT)
    noise = clean_export(_parsed(root, "noise.txt"), LocationMarkerMode.COMPACT)
    number = clean_export(_parsed(root, "number.txt"), LocationMarkerMode.COMPACT)
    assert scan.sidecar.readiness_status in {
        ReadinessStatus.IMAGE_DEPENDENT,
        ReadinessStatus.UNUSABLE,
    }
    assert noise.sidecar.readiness_status in {
        ReadinessStatus.UNUSABLE,
        ReadinessStatus.HUMAN_REVIEW_REQUIRED,
    }
    assert "ambiguous_numerical_notation" in number.sidecar.warnings


def test_french_accents_arabic_and_numbers_are_preserved(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    body = "===== PAGE 1 =====\n\nÉlévation à 2,5 mg/j — علاج محفوظ."
    _library(root, {"unicode.txt": ("unicode.pdf", body, "pdf")})
    artifact = clean_export(_parsed(root, "unicode.txt"), LocationMarkerMode.COMPACT)
    assert "Élévation à 2,5 mg/j — علاج محفوظ." in artifact.text
    assert artifact.sidecar.detected_language == "fr+ar"


def test_lexical_audit_rejects_number_unit_medical_term_and_negation() -> None:
    issues, suspicious = validate_reconstruction(
        "Traitement 5 mg indiqué.",
        "Traitement 10 ml jamais indiqué avec amoxicilline.",
        [],
        [],
    )
    codes = {issue.code for issue in issues}
    assert "unsupported_numerical_token" in codes
    assert "unsupported_unit" in codes
    assert "unsupported_lexical_addition" in codes
    assert "changed_negation" in codes or "changed_modal_word" in codes
    assert "amoxicilline" in suspicious


def test_transformation_requires_known_source_span() -> None:
    transformation = ModelTransformation(
        transformation_id="section-000001:t1",
        transformation_type=TransformationType.PARAGRAPH_REASSEMBLY,
        raw_span_ids=["span-999999"],
        cleaned_span_ids=["span-999999"],
        original_text="Texte",
        reconstructed_text="Texte",
        support_basis="same words",
        confidence=1.0,
        model_identity=GENERATOR,
        validation_status="accepted",
    )
    issues, _ = validate_reconstruction("Texte", "Texte", [transformation], [])
    assert {issue.code for issue in issues} == {"invalid_transformation_source_spans"}


def test_transformation_original_must_occur_in_its_cited_span() -> None:
    transformation = ModelTransformation(
        transformation_id="section-000001:t1",
        transformation_type=TransformationType.FRAGMENT_REPAIR,
        raw_span_ids=["span-000001"],
        cleaned_span_ids=["span-000001"],
        original_text="mot inventé",
        reconstructed_text="Texte",
        support_basis="claimed source",
        confidence=1.0,
        model_identity=GENERATOR,
        validation_status="accepted",
    )
    span = SourceSpan(
        span_id="span-000001",
        location_id="location-000001",
        location_type="page",
        location_number=1,
        raw_start=0,
        raw_end=5,
        cleaned_start=0,
        cleaned_end=5,
        source_sha256=SOURCE_HASH,
    )
    issues, _ = validate_reconstruction(
        "Texte",
        "Texte",
        [transformation],
        [span],
        span_texts={"span-000001": "Texte"},
    )
    assert "transformation_original_not_in_cited_spans" in {issue.code for issue in issues}


class _FakeProvider:
    def __init__(self, mode: str = "identity") -> None:
        self.mode = mode
        self.chat_calls = 0
        self.unloaded: list[str] = []

    def version(self) -> str:
        return "test-ollama"

    def resolve_model(self, requested: str, *, reviewer: bool = False) -> ModelIdentity:
        return REVIEWER if reviewer or "medgemma" in requested else GENERATOR

    def chat_json(self, **kwargs: Any) -> StructuredResponse:
        self.chat_calls += 1
        user = str(kwargs["user_prompt"])
        if "Review source support" in user:
            marker = '"transformation_id": "'
            start = user.find(marker)
            transformation_id = user[start + len(marker) : user.find('"', start + len(marker))]
            verdict = "unsupported" if self.mode == "disagree" else "external_medical_observation"
            return StructuredResponse(
                content={
                    "findings": [
                        {
                            "transformation_id": transformation_id,
                            "verdict": verdict,
                            "source_span_ids": ["span-000001"],
                            "message": "Synthetic constrained review.",
                        }
                    ]
                },
                raw_response="{}",
                attempt_count=1,
            )
        source_matches = re.findall(r"<(span-[0-9]{6})>\n(.*?)\n</\1>", user, flags=re.DOTALL)
        source = "\n\n".join(value for _, value in source_matches)
        span_ids = [span_id for span_id, _ in source_matches]
        reconstructed = source
        if self.mode == "addition":
            reconstructed += " amoxicilline 10 mg"
            transformations: list[dict[str, object]] = []
        else:
            transformations = [
                {
                    "transformation_id": "t1",
                    "transformation_type": "paragraph_reassembly",
                    "span_ids": span_ids,
                    "original_text": source,
                    "reconstructed_text": source,
                    "support_basis": "Exact source words.",
                    "confidence": 1.0,
                }
            ]
        return StructuredResponse(
            content={
                "reconstructed_text": reconstructed,
                "transformations": transformations,
                "unresolved_fragments": [],
                "image_dependency_annotations": [],
            },
            raw_response="{}",
            attempt_count=1,
        )

    def unload(self, model: ModelIdentity) -> None:
        self.unloaded.append(model.tag)


def _configuration(
    tmp_path: Path, *, resume: bool = False, dry_run: bool = False
) -> PreparationConfiguration:
    return PreparationConfiguration(
        input_root=tmp_path / "raw",
        clean_output_root=tmp_path / "clean",
        reconstructed_output_root=tmp_path / "reconstructed",
        report_output_root=tmp_path / "reports",
        resume=resume,
        dry_run=dry_run,
        jobs=1,
    )


def _noisy_library(root: Path) -> None:
    body = """===== PAGE 1 =====

COURS TEST

IIntroduction

Fragment court

Autre fragment

Troisième fragment

Quatrième fragment

Cinquième fragment

Sixième fragment

Septième fragment

Huitième fragment

Neuvième fragment"""
    _library(root, {"nested/course.txt": ("nested/course.pdf", body, "pdf")})


def test_full_service_dry_run_is_no_write_and_no_inference(tmp_path: Path) -> None:
    _noisy_library(tmp_path / "raw")
    provider = _FakeProvider()
    result = prepare_course_text_tree(
        _configuration(tmp_path, dry_run=True),
        provider_factory=lambda _url, _timeout: provider,  # type: ignore[arg-type]
    )
    assert result.report.total_raw_text_files == 1
    assert result.report.source_immutable
    assert provider.chat_calls == 0
    assert not (tmp_path / "clean").exists()
    assert not (tmp_path / "reconstructed").exists()


def test_service_rejects_suspicious_model_addition_and_retains_clean_source(tmp_path: Path) -> None:
    _noisy_library(tmp_path / "raw")
    provider = _FakeProvider("addition")
    result = prepare_course_text_tree(
        _configuration(tmp_path),
        provider_factory=lambda _url, _timeout: provider,  # type: ignore[arg-type]
    )
    entry = result.reconstruction_manifest.entries[0]
    assert entry.status is PreparationStatus.NEEDS_HUMAN_REVIEW
    reconstructed = (tmp_path / "reconstructed/nested/course.txt").read_text(encoding="utf-8")
    assert "amoxicilline" not in reconstructed
    assert sha256_file(tmp_path / "raw/nested/course.txt") == entry.raw_text_sha256


def test_external_medgemma_observation_is_separate_and_not_applied(tmp_path: Path) -> None:
    _noisy_library(tmp_path / "raw")
    provider = _FakeProvider("identity")
    result = prepare_course_text_tree(
        _configuration(tmp_path),
        provider_factory=lambda _url, _timeout: provider,  # type: ignore[arg-type]
    )
    sidecar_path = tmp_path / "reconstructed/nested/course.reconstruction.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["reviewer_findings"][0]["verdict"] == "external_medical_observation"
    assert result.report.no_study_material_generated
    assert GENERATOR.tag in provider.unloaded and REVIEWER.tag in provider.unloaded


def test_model_disagreement_preserves_cleaned_version_and_requires_review(tmp_path: Path) -> None:
    _noisy_library(tmp_path / "raw")
    provider = _FakeProvider("disagree")
    result = prepare_course_text_tree(
        _configuration(tmp_path),
        provider_factory=lambda _url, _timeout: provider,  # type: ignore[arg-type]
    )
    entry = result.reconstruction_manifest.entries[0]
    assert entry.status is PreparationStatus.NEEDS_HUMAN_REVIEW
    assert (tmp_path / "clean/nested/course.txt").read_bytes() == (
        tmp_path / "reconstructed/nested/course.txt"
    ).read_bytes()


def test_resume_validates_hash_and_corruption_regenerates(tmp_path: Path) -> None:
    _noisy_library(tmp_path / "raw")
    disabled = _configuration(tmp_path).model_copy(update={"disable_model_reconstruction": True})
    prepare_course_text_tree(disabled)
    resumed = prepare_course_text_tree(disabled.model_copy(update={"resume": True}))
    assert resumed.cleaning_manifest.entries[0].status is PreparationStatus.SKIPPED_CURRENT
    (tmp_path / "clean/nested/course.txt").write_text("corrupt\n", encoding="utf-8")
    regenerated = prepare_course_text_tree(disabled.model_copy(update={"resume": True}))
    assert regenerated.cleaning_manifest.entries[0].status is not PreparationStatus.SKIPPED_CURRENT
    assert "corrupt" not in (tmp_path / "clean/nested/course.txt").read_text(encoding="utf-8")


def test_atomic_outputs_path_containment_and_source_immutability(tmp_path: Path) -> None:
    _noisy_library(tmp_path / "raw")
    before = sha256_file(tmp_path / "raw/nested/course.txt")
    configuration = _configuration(tmp_path).model_copy(
        update={"disable_model_reconstruction": True}
    )
    result = prepare_course_text_tree(configuration)
    assert before == sha256_file(tmp_path / "raw/nested/course.txt")
    assert result.report.source_immutable
    assert not list(tmp_path.rglob("*.tmp"))
    unsafe = configuration.model_copy(update={"clean_output_root": tmp_path / "raw/clean"})
    with pytest.raises(ValueError, match="outside"):
        prepare_course_text_tree(unsafe)


def test_append_only_failure_attempts(tmp_path: Path) -> None:
    _failure_attempt(tmp_path, "course.txt", "model", "first")
    _failure_attempt(tmp_path, "course.txt", "model", "second")
    attempts = list(tmp_path.rglob("attempt-*.json"))
    assert len(attempts) == 2
    assert {json.loads(path.read_text())["error"] for path in attempts} == {"first", "second"}


def test_jobs_rejection_and_resume_overwrite_conflict() -> None:
    with pytest.raises(ValidationError, match="jobs must be 1"):
        PreparationConfiguration(jobs=2)
    with pytest.raises(ValidationError, match="cannot be used together"):
        PreparationConfiguration(resume=True, overwrite=True)


class _HTTPResponse:
    def __init__(self, body: str, status: int = 200) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body.encode("utf-8")


class _HTTPConnection:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes

    def request(self, *_args: object, **_kwargs: object) -> None:
        return None

    def getresponse(self) -> _HTTPResponse:
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, _HTTPResponse)
        return outcome

    def close(self) -> None:
        return None


def test_provider_retries_timeout_and_malformed_json() -> None:
    valid = _HTTPResponse(json.dumps({"message": {"content": json.dumps({"value": "ok"})}}))
    outcomes: list[object] = [OSError("timeout"), _HTTPResponse("not-json"), valid]

    def factory(_host: str, _port: int, _timeout: float) -> _HTTPConnection:
        return _HTTPConnection(outcomes)

    provider = OllamaPreparationProvider(
        "http://127.0.0.1:11434",
        1,
        connection_factory=factory,  # type: ignore[arg-type]
    )
    response = provider.chat_json(
        model=GENERATOR,
        system_prompt="system",
        user_prompt="user",
        response_schema={"type": "object"},
        context_budget=4096,
        temperature=0,
        seed=42,
        maximum_retries=2,
    )
    assert response.content == {"value": "ok"}
    assert response.attempt_count == 3
