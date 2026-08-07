from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ingestion.chunking.builder import build_chunk_collection
from ingestion.chunking.models import ChunkingConfiguration
from ingestion.cli import app
from ingestion.datasets.builder import build_ai_ready_dataset
from ingestion.generation.config import generation_configuration
from ingestion.generation.evidence import EvidenceResolutionError, resolve_chunk_evidence_span
from ingestion.generation.models import (
    ContentType,
    FailureReport,
    FailureStage,
    GeneratedContentBatch,
    GenerationRequest,
    GenerationValidationReport,
    GroundingReport,
    IssueSeverity,
    KnowledgeMode,
    ProviderKind,
    QCMType,
    RawProviderResponseRecord,
    ReportStatus,
    ReviewStatus,
    ValidationIssue,
)
from ingestion.generation.output import (
    GenerationFailureOutputExistsError,
    GenerationOutputExistsError,
    write_generation_failure,
)
from ingestion.generation.prompts import build_qcm_response_schema
from ingestion.generation.providers.base import GenerationProviderError
from ingestion.generation.providers.mock import MockGenerationProvider
from ingestion.generation.providers.ollama import OllamaGenerationProvider, OllamaProviderError
from ingestion.generation.review import ReviewTransitionError, review_content
from ingestion.generation.service import (
    GenerationFailure,
    build_generation_plan,
    generate_content,
)
from ingestion.generation.validation import validate_generated_content
from ingestion.normalization.models import BlockType, LocationType, SourceReference
from tests.test_chunking import block, document, section


def _dataset_path(tmp_path: Path) -> Path:
    blocks = [
        block("h1", BlockType.HEADING, "Diagnostic", 1, section_id="s1"),
        block(
            "p1",
            BlockType.PARAGRAPH,
            "Le signe alpha concerne 50% des observations et est associé au constat bêta. "
            + "Contexte clinique source. " * 20,
            2,
            section_id="s1",
        ),
        block("h2", BlockType.HEADING, "Traitement", 3, section_id="s2"),
        block(
            "p2",
            BlockType.PARAGRAPH,
            "Le traitement gamma nécessite la surveillance delta. "
            + "Donnée thérapeutique source. " * 20,
            4,
            section_id="s2",
        ),
        block("h3", BlockType.HEADING, "Suivi", 5, section_id="s3"),
        block(
            "p3",
            BlockType.PARAGRAPH,
            "Le suivi epsilon documente le résultat zêta. " + "Donnée de suivi source. " * 20,
            6,
            section_id="s3",
        ),
    ]
    source = document(
        [blocks],
        sections=[
            section("s1", "Diagnostic", 1, ["h1", "p1"]),
            section("s2", "Traitement", 1, ["h2", "p2"]),
            section("s3", "Suivi", 1, ["h3", "p3"]),
        ],
    )
    collection = build_chunk_collection(
        source,
        ChunkingConfiguration(
            target_characters=400,
            soft_max_characters=800,
            hard_max_characters=1200,
            minimum_characters=50,
        ),
    )
    dataset = build_ai_ready_dataset(source, collection)
    path = tmp_path / "fixture-dataset.json"
    path.write_text(dataset.model_dump_json(indent=2), encoding="utf-8")
    return path


def _configuration(count: int = 2) -> Any:
    return generation_configuration(
        content_type=ContentType.QCM,
        qcm_type=QCMType.SINGLE_ANSWER,
        count=count,
        language="fr",
        difficulty="mixed",
        knowledge_mode=KnowledgeMode.SOURCE_ONLY,
        provider=ProviderKind.MOCK,
        model="fixture-model",
        validation_retry_count=0,
        environ={},
    )


@dataclass
class _EvidenceChunkFixture:
    chunk_id: str
    text: str
    source_references: list[SourceReference]


def _evidence_chunk_fixture() -> _EvidenceChunkFixture:
    excerpts = ["Alpha 50%.", "Intermédiaire.", "Contexte.", "Conclusion."]
    block_ids = ["block-000004", "block-000005", "block-000006", "block-000007"]
    return _EvidenceChunkFixture(
        chunk_id="d" * 64,
        text="\n".join(excerpts),
        source_references=[
            SourceReference(
                source_relative_path="fixture/source.docx",
                location_type=LocationType.DOCUMENT,
                block_id=block_id,
                source_excerpt=excerpt,
            )
            for block_id, excerpt in zip(block_ids, excerpts, strict=True)
        ],
    )


def _response_for_plan(plan: Any, *, duplicate: bool = False) -> dict[str, object]:
    difficulties = ["medium", "easy", "hard"]
    questions: list[dict[str, object]] = []
    for index, chunk in enumerate(plan.request.source.selected_chunks):
        reference = chunk.source_references[-1]
        quote = reference.source_excerpt
        assert quote is not None
        assert reference.block_id is not None
        distinct_stems = [
            "Quelle proposition diagnostique reprend la source ?",
            "Quelle proposition thérapeutique reprend le document ?",
            "Quelle proposition de suivi correspond au passage ?",
        ]
        stem = "Quelle proposition reprend la source ?" if duplicate else distinct_stems[index]
        questions.append(
            {
                "topic": "Révision",
                "difficulty": difficulties[index],
                "stem": stem,
                "choices": [
                    {"key": "a", "text": quote},
                    {"key": "b", "text": "Alternative sans appui"},
                    {"key": "c", "text": "Autre alternative sans appui"},
                ],
                "correct_choice_keys": ["a"],
                "explanation": f"La source indique : {quote}",
                "evidence": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "source_reference_block_ids": [reference.block_id],
                    }
                ],
            }
        )
    return {"questions": questions}


def _correction_from_response(
    response: dict[str, object], ordinals: list[int]
) -> dict[str, object]:
    questions = response["questions"]
    assert isinstance(questions, list)
    return {
        "question_replacements": [
            {"question_ordinal": ordinal, "replacement": questions[ordinal - 1]}
            for ordinal in ordinals
        ],
        "insufficient_evidence": False,
        "shortfall_reason": None,
    }


def test_noncontiguous_block_000004_and_000007_are_rejected() -> None:
    with pytest.raises(EvidenceResolutionError) as captured:
        resolve_chunk_evidence_span(
            _evidence_chunk_fixture(),
            ["block-000004", "block-000007"],
        )
    assert captured.value.code == "noncontiguous_evidence_block_ids"


def test_contiguous_multiblock_span_resolves_exact_retained_substring() -> None:
    chunk = _evidence_chunk_fixture()
    resolved = resolve_chunk_evidence_span(
        chunk,
        ["block-000004", "block-000005", "block-000006"],
    )

    assert resolved.quotation == "Alpha 50%.\nIntermédiaire.\nContexte."
    assert [reference.block_id for reference in resolved.source_references] == [
        "block-000004",
        "block-000005",
        "block-000006",
    ]


def test_plan_is_read_only_deterministic_and_independently_versioned(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    before = dataset_path.read_bytes()
    first = build_generation_plan(
        dataset_path, _configuration(), output_root=tmp_path / "generated"
    )
    second = build_generation_plan(
        dataset_path, _configuration(), output_root=tmp_path / "generated"
    )

    assert first.request.generation_schema_version == "1.0.0"
    assert first.request.generation_id == second.request.generation_id
    assert [item.chunk_id for item in first.request.source.selected_chunks] == [
        item.chunk_id for item in second.request.source.selected_chunks
    ]
    assert dataset_path.read_bytes() == before
    assert not (tmp_path / "generated").exists()


def _evidence_schema_variants(schema: dict[str, Any]) -> list[dict[str, Any]]:
    definitions = schema["$defs"]
    assert isinstance(definitions, dict)
    evidence = definitions["ProviderEvidenceDraft"]
    assert isinstance(evidence, dict)
    variants = evidence["oneOf"]
    assert isinstance(variants, list)
    return variants


def _schema_allows_evidence(schema: dict[str, Any], chunk_id: str, block_ids: list[str]) -> bool:
    for variant in _evidence_schema_variants(schema):
        properties = variant["properties"]
        allowed_chunk_ids = properties["chunk_id"]["enum"]
        block_schema = properties["source_reference_block_ids"]
        allowed_block_ids = block_schema["items"]["enum"]
        if (
            chunk_id in allowed_chunk_ids
            and len(block_ids) <= block_schema["maxItems"]
            and all(item in allowed_block_ids for item in block_ids)
        ):
            return True
    return False


def test_dynamic_schema_is_deterministic_and_binds_blocks_to_their_chunk(tmp_path: Path) -> None:
    plan = build_generation_plan(_dataset_path(tmp_path), _configuration())
    schema = plan.provider_response_schema
    assert schema == build_qcm_response_schema(plan.request.source)

    first, second = plan.request.source.selected_chunks[:2]
    first_block = first.source_references[0].block_id
    second_block = second.source_references[0].block_id
    assert first_block is not None and second_block is not None
    assert _schema_allows_evidence(schema, first.chunk_id, [first_block])
    assert not _schema_allows_evidence(schema, first.chunk_id, [second_block])
    assert not _schema_allows_evidence(schema, first.chunk_id, ["block-invented"])
    assert not _schema_allows_evidence(schema, "f" * 64, [first_block])
    first_two_blocks = [
        reference.block_id for reference in first.source_references[:2] if reference.block_id
    ]
    assert len(first_two_blocks) == 2
    assert not _schema_allows_evidence(schema, first.chunk_id, first_two_blocks)

    variant_chunk_ids = [
        variant["properties"]["chunk_id"]["enum"][0]
        for variant in _evidence_schema_variants(schema)
    ]
    assert variant_chunk_ids == sorted(variant_chunk_ids)


def test_dynamic_schema_rejects_selected_chunk_without_block_ids(tmp_path: Path) -> None:
    plan = build_generation_plan(_dataset_path(tmp_path), _configuration())
    first = plan.request.source.selected_chunks[0]
    references = [
        reference.model_copy(update={"block_id": None}) for reference in first.source_references
    ]
    source = plan.request.source.model_copy(
        update={"selected_chunks": [first.model_copy(update={"source_references": references})]}
    )

    with pytest.raises(ValueError, match="no valid evidence block IDs"):
        build_qcm_response_schema(source)


def test_mock_generation_has_deterministic_ids_and_dataset_references(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    plan = build_generation_plan(dataset_path, _configuration(), output_root=tmp_path / "generated")
    provider = MockGenerationProvider(lambda _call: _response_for_plan(plan))
    result = generate_content(
        dataset_path, _configuration(), provider, output_root=tmp_path / "generated"
    )

    assert result.validation_report.status is ReportStatus.SUCCESS
    assert provider.calls == 1
    for index, question in enumerate(result.content.qcm_questions):
        selected = plan.request.source.selected_chunks[index]
        assert question.source_references == [selected.source_references[-1]]
        assert question.explanation.evidence[0].quotation in selected.text
        assert question.generation_status.value == "draft"
        assert question.medical_review.status is ReviewStatus.UNREVIEWED
    second_ids = [
        question.question_id
        for question in GeneratedContentBatch.model_validate_json(
            (result.output_directory / "generated-content.json").read_text()
        ).qcm_questions
    ]
    assert second_ids == [question.question_id for question in result.content.qcm_questions]
    assert sorted(path.name for path in result.output_directory.iterdir()) == sorted(
        [
            "request.json",
            "selected-sources.json",
            "raw-provider-response.json",
            "generated-content.json",
            "grounding-report.json",
            "validation-report.json",
            "generation-report.json",
        ]
    )


def test_medplat_materializes_exact_50_percent_evidence(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    plan = build_generation_plan(dataset_path, _configuration())
    payload = _response_for_plan(plan)
    provider = MockGenerationProvider(lambda _call: payload)

    result = generate_content(
        dataset_path,
        _configuration(),
        provider,
        output_root=tmp_path / "generated",
    )

    first_draft = payload["questions"]
    assert isinstance(first_draft, list)
    assert isinstance(first_draft[0], dict)
    assert "quotation" not in first_draft[0]["evidence"][0]  # type: ignore[index]
    first = result.content.qcm_questions[0]
    assert "50%" in first.explanation.evidence[0].quotation
    assert (
        first.explanation.evidence[0].quotation
        == (first.source_references[0].source_excerpt or "").strip()
    )
    assert result.validation_report.status is ReportStatus.SUCCESS


def test_replacing_source_50_percent_with_30_to_40_is_rejected(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    plan = build_generation_plan(dataset_path, _configuration())
    payload = _response_for_plan(plan)
    questions = payload["questions"]
    assert isinstance(questions, list) and isinstance(questions[0], dict)
    choices = questions[0]["choices"]
    assert isinstance(choices, list) and isinstance(choices[0], dict)
    choices[0]["text"] = "30–40%"
    questions[0]["explanation"] = "La valeur retenue est 30–40%."

    with pytest.raises(GenerationFailure) as captured:
        generate_content(
            dataset_path,
            _configuration(),
            MockGenerationProvider(lambda _call: payload),
            output_root=tmp_path / "generated",
            failure_output_root=tmp_path / "failures",
        )
    assert "unsupported_numeric_claim" in captured.value.issue_codes
    validation = json.loads(
        (captured.value.failure_directory / "validation-report.json").read_text()
    )
    numeric = next(
        issue for issue in validation["issues"] if issue["code"] == "unsupported_numeric_claim"
    )
    assert numeric["details"]["unsupported_numbers"] == ["30", "40"]


def test_unsupported_numeric_distractor_is_rejected(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    plan = build_generation_plan(dataset_path, _configuration())
    payload = _response_for_plan(plan)
    questions = payload["questions"]
    assert isinstance(questions, list) and isinstance(questions[0], dict)
    choices = questions[0]["choices"]
    assert isinstance(choices, list) and isinstance(choices[1], dict)
    choices[1]["text"] = "Une fréquence de 30%"

    with pytest.raises(GenerationFailure) as captured:
        generate_content(
            dataset_path,
            _configuration(),
            MockGenerationProvider(lambda _call: payload),
            output_root=tmp_path / "generated",
            failure_output_root=tmp_path / "failures",
        )
    assert "unsupported_numeric_claim" in captured.value.issue_codes


def test_source_correction_language_is_fatal(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    plan = build_generation_plan(dataset_path, _configuration())
    payload = _response_for_plan(plan)
    questions = payload["questions"]
    assert isinstance(questions, list) and isinstance(questions[0], dict)
    questions[0]["explanation"] = "The source value 50% is likely a typo."

    with pytest.raises(GenerationFailure) as captured:
        generate_content(
            dataset_path,
            _configuration(),
            MockGenerationProvider(lambda _call: payload),
            output_root=tmp_path / "generated",
            failure_output_root=tmp_path / "failures",
        )
    assert "source_correction_language" in captured.value.issue_codes


def test_validation_retry_repairs_numeric_distractor_and_preserves_parent(
    tmp_path: Path,
) -> None:
    dataset_path = _dataset_path(tmp_path)
    configuration = _configuration().model_copy(update={"validation_retry_count": 1})
    plan = build_generation_plan(dataset_path, configuration)
    invalid = _response_for_plan(plan)
    invalid_questions = invalid["questions"]
    assert isinstance(invalid_questions, list) and isinstance(invalid_questions[0], dict)
    invalid_choices = invalid_questions[0]["choices"]
    assert isinstance(invalid_choices, list) and isinstance(invalid_choices[1], dict)
    invalid_choices[1]["text"] = "Fréquence 999%"
    repaired = _correction_from_response(_response_for_plan(plan), [1])
    provider = MockGenerationProvider(lambda call: invalid if call == 1 else repaired)
    failure_root = tmp_path / "failures"

    result = generate_content(
        dataset_path,
        configuration,
        provider,
        output_root=tmp_path / "generated",
        failure_output_root=failure_root,
    )

    failed_directories = list(
        (
            failure_root / plan.request.source.document_id / "qcm" / plan.request.generation_id
        ).iterdir()
    )
    assert len(failed_directories) == 1
    parent = FailureReport.model_validate_json(
        (failed_directories[0] / "failure-report.json").read_text()
    )
    parent_snapshot = {
        path.name: path.read_bytes() for path in failed_directories[0].iterdir() if path.is_file()
    }
    assert parent.validation_retry_sequence == 0
    assert parent.parent_attempt_id is None
    assert result.generation_report.validation_retry_sequence == 1
    assert result.generation_report.parent_attempt_id == parent.attempt_id
    assert result.generation_report.retry_issue_codes == ["unsupported_numeric_claim"]
    assert result.generation_report.question_count_changed is False
    assert provider.calls == 2
    assert len(provider.message_history[1]) == 2
    assert provider.message_history[1] != plan.messages
    assert provider.response_schema_history[0] == plan.provider_response_schema
    assert provider.response_schema_history[1] != plan.provider_response_schema
    correction_schema = provider.response_schema_history[1]
    assert "$defs" not in correction_schema
    serialized_schema = json.dumps(correction_schema, sort_keys=True)
    assert '"$ref"' not in serialized_schema
    assert '"allOf"' not in serialized_schema
    assert "(?!" not in serialized_schema
    variants = correction_schema["properties"]["question_replacements"]["items"]["oneOf"]
    assert isinstance(variants, list) and len(variants) == 1
    variant = variants[0]
    assert variant["properties"]["question_ordinal"]["enum"] == [1]
    replacement_schema = variant["properties"]["replacement"]
    replacement_constraint = replacement_schema["properties"]
    assert replacement_schema["additionalProperties"] is False
    assert "choices" in replacement_schema["required"]
    assert "correct_choice_keys" in replacement_schema["required"]
    assert "options" not in replacement_constraint
    assert "correct_answer" not in replacement_constraint
    assert "source_id" not in replacement_constraint
    assert replacement_constraint["difficulty"]["enum"] == [invalid_questions[0]["difficulty"]]
    assert replacement_constraint["evidence"]["items"]["properties"]["chunk_id"]["enum"] == [
        plan.request.source.selected_chunks[0].chunk_id
    ]
    first_span_block_ids = [
        reference.block_id
        for reference in plan.request.source.selected_chunks[0].source_references[-1:]
    ]
    assert (
        replacement_constraint["evidence"]["items"]["properties"]["source_reference_block_ids"][
            "items"
        ]["enum"]
        == first_span_block_ids
    )
    numeric_pattern = replacement_constraint["stem"]["pattern"]
    assert re.fullmatch(numeric_pattern, "Environ 50%")
    assert not re.fullmatch(numeric_pattern, "Environ 5%")
    assert not re.fullmatch(numeric_pattern, "Près de 10%")
    assert not re.fullmatch(numeric_pattern, "Environ ٥٠%")
    assert not re.fullmatch(numeric_pattern, "Environ ５０%")
    choice_pattern = replacement_constraint["choices"]["items"]["properties"]["text"]["pattern"]
    assert choice_pattern == numeric_pattern
    assert replacement_constraint["explanation"]["pattern"] == numeric_pattern
    retry_payload = json.loads(provider.message_history[1][-1]["content"])
    assert retry_payload["required_action"] == "return_targeted_question_replacements"
    assert retry_payload["required_question_ordinals"] == [1]
    contract = retry_payload["response_contract"]
    contract_replacement = contract["question_replacements"][0]["replacement"]
    assert set(contract_replacement) == {
        "topic",
        "difficulty",
        "stem",
        "choices",
        "correct_choice_keys",
        "explanation",
        "evidence",
    }
    instructions = " ".join(retry_payload["instructions"])
    assert "ASCII digits" in instructions
    assert "Never use options, answers, correct_answer, source_id, questions, or sources" in (
        instructions
    )
    correction = retry_payload["corrections"][0]
    assert correction["question_ordinal"] == 1
    assert correction["issue_codes"] == ["unsupported_numeric_claim"]
    assert correction["unsupported_numbers"] == ["999"]
    assert correction["evidence_span"]["chunk_id"] == (
        plan.request.source.selected_chunks[0].chunk_id
    )
    assert correction["evidence_text"] == (
        result.content.qcm_questions[0].explanation.evidence[0].quotation
    )
    assert (
        plan.request.source.selected_chunks[1].text
        not in provider.message_history[1][-1]["content"]
    )
    original_questions = invalid["questions"]
    assert isinstance(original_questions, list) and isinstance(original_questions[1], dict)
    assert result.content.qcm_questions[1].stem == original_questions[1]["stem"]
    original_second_choices = original_questions[1]["choices"]
    assert isinstance(original_second_choices, list)
    assert [choice.text for choice in result.content.qcm_questions[1].choices] == [
        choice["text"] for choice in original_second_choices if isinstance(choice, dict)
    ]
    assert parent_snapshot == {
        path.name: path.read_bytes() for path in failed_directories[0].iterdir() if path.is_file()
    }


def test_validation_retry_accepts_explicit_grounded_shortfall(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    configuration = _configuration().model_copy(update={"validation_retry_count": 1})
    plan = build_generation_plan(dataset_path, configuration)
    invalid = _response_for_plan(plan)
    invalid_questions = invalid["questions"]
    assert isinstance(invalid_questions, list) and isinstance(invalid_questions[0], dict)
    invalid_choices = invalid_questions[0]["choices"]
    assert isinstance(invalid_choices, list) and isinstance(invalid_choices[1], dict)
    invalid_choices[1]["text"] = "Fréquence 999%"
    shortfall = {
        "question_replacements": [],
        "insufficient_evidence": True,
        "shortfall_reason": "No grounded nonnumeric distractors were available.",
    }
    provider = MockGenerationProvider(lambda call: invalid if call == 1 else shortfall)

    result = generate_content(
        dataset_path,
        configuration,
        provider,
        output_root=tmp_path / "generated",
        failure_output_root=tmp_path / "failures",
    )

    assert len(result.content.qcm_questions) == 1
    assert result.validation_report.status is ReportStatus.NEEDS_REVISION
    assert result.generation_report.question_count_changed is True
    assert any(
        issue.code == "insufficient_grounded_questions" for issue in result.validation_report.issues
    )


def test_failed_corrective_retry_is_append_only_and_limit_is_enforced(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    configuration = _configuration().model_copy(update={"validation_retry_count": 1})
    plan = build_generation_plan(dataset_path, configuration)
    first_payload = _response_for_plan(plan)
    first_questions = first_payload["questions"]
    assert isinstance(first_questions, list) and isinstance(first_questions[0], dict)
    first_choices = first_questions[0]["choices"]
    assert isinstance(first_choices, list) and isinstance(first_choices[1], dict)
    first_choices[1]["text"] = "Fréquence 998%"
    second_response = _response_for_plan(plan)
    second_questions = second_response["questions"]
    assert isinstance(second_questions, list) and isinstance(second_questions[0], dict)
    second_choices = second_questions[0]["choices"]
    assert isinstance(second_choices, list) and isinstance(second_choices[1], dict)
    second_choices[1]["text"] = "Fréquence 999%"
    payloads = [first_payload, _correction_from_response(second_response, [1])]
    provider = MockGenerationProvider(lambda call: payloads[call - 1])
    failure_root = tmp_path / "failures"

    with pytest.raises(GenerationFailure) as captured:
        generate_content(
            dataset_path,
            configuration,
            provider,
            output_root=tmp_path / "generated",
            failure_output_root=failure_root,
        )

    attempt_root = (
        failure_root / plan.request.source.document_id / "qcm" / plan.request.generation_id
    )
    reports = [
        FailureReport.model_validate_json((path / "failure-report.json").read_text())
        for path in attempt_root.iterdir()
    ]
    reports.sort(key=lambda report: report.validation_retry_sequence)
    assert provider.calls == 2
    assert len(reports) == 2
    assert reports[0].validation_retry_sequence == 0
    assert reports[1].validation_retry_sequence == 1
    assert reports[1].parent_attempt_id == reports[0].attempt_id
    assert reports[1].retry_issue_codes == ["unsupported_numeric_claim"]
    assert reports[1].question_count_changed is False
    assert captured.value.failure_directory.name == reports[1].attempt_id
    assert not (tmp_path / "generated").exists()


def test_output_limited_corrections_are_discarded_as_explicit_shortfalls(
    tmp_path: Path,
) -> None:
    dataset_path = _dataset_path(tmp_path)
    configuration = _configuration(count=3).model_copy(update={"validation_retry_count": 2})
    plan = build_generation_plan(dataset_path, configuration)
    initial = _response_for_plan(plan)
    initial_questions = initial["questions"]
    assert isinstance(initial_questions, list)
    for index, number in ((0, "998"), (1, "999")):
        question = initial_questions[index]
        assert isinstance(question, dict)
        choices = question["choices"]
        assert isinstance(choices, list) and isinstance(choices[1], dict)
        choices[1]["text"] = f"Fréquence {number}%"
    provider = MockGenerationProvider(
        lambda call: initial if call == 1 else "{malformed correction",
        done_reason_factory=lambda call: "stop" if call == 1 else "length",
    )
    failure_root = tmp_path / "failures"

    result = generate_content(
        dataset_path,
        configuration,
        provider,
        output_root=tmp_path / "generated",
        failure_output_root=failure_root,
    )

    assert provider.calls == 3
    assert len(result.content.qcm_questions) == 1
    assert result.validation_report.status is ReportStatus.NEEDS_REVISION
    assert result.generation_report.question_count_changed is True
    assert result.generation_report.validation_retry_sequence == 2
    assert "malformed_provider_json" in result.generation_report.retry_issue_codes
    assert any(
        issue.code == "insufficient_grounded_questions" for issue in result.validation_report.issues
    )
    attempt_root = (
        failure_root / plan.request.source.document_id / "qcm" / plan.request.generation_id
    )
    reports = [
        FailureReport.model_validate_json((path / "failure-report.json").read_text())
        for path in attempt_root.iterdir()
    ]
    assert len(reports) == 3
    assert sorted(report.validation_retry_sequence for report in reports) == [0, 1, 2]
    assert all((path / "raw-provider-response.json").exists() for path in attempt_root.iterdir())
    successful_raw = json.loads(
        (result.output_directory / "raw-provider-response.json").read_text()
    )
    assert successful_raw["message"]["content"] != "{malformed correction"
    successful_content = GeneratedContentBatch.model_validate_json(
        (result.output_directory / "generated-content.json").read_text()
    )
    retained_choice_text = [
        choice.text for question in successful_content.qcm_questions for choice in question.choices
    ]
    assert all("998" not in text and "999" not in text for text in retained_choice_text)


def test_later_targeted_retry_preserves_prior_successful_replacement(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    configuration = _configuration().model_copy(update={"validation_retry_count": 2})
    plan = build_generation_plan(dataset_path, configuration)
    initial = _response_for_plan(plan)
    initial_questions = initial["questions"]
    assert isinstance(initial_questions, list)
    for index, number in ((0, "998"), (1, "999")):
        question = initial_questions[index]
        assert isinstance(question, dict)
        choices = question["choices"]
        assert isinstance(choices, list) and isinstance(choices[1], dict)
        choices[1]["text"] = f"Fréquence {number}%"

    first_replacements = _response_for_plan(plan)
    first_questions = first_replacements["questions"]
    assert isinstance(first_questions, list) and isinstance(first_questions[0], dict)
    first_questions[0]["stem"] = "Version corrigée et conservée de la première question."
    assert isinstance(first_questions[1], dict)
    first_choices = first_questions[1]["choices"]
    assert isinstance(first_choices, list) and isinstance(first_choices[1], dict)
    first_choices[1]["text"] = "Fréquence 997%"
    first_correction = _correction_from_response(first_replacements, [1])
    second_correction = _correction_from_response(_response_for_plan(plan), [2])
    payloads = [initial, first_correction, second_correction]
    provider = MockGenerationProvider(lambda call: payloads[call - 1])

    result = generate_content(
        dataset_path,
        configuration,
        provider,
        output_root=tmp_path / "generated",
        failure_output_root=tmp_path / "failures",
    )

    assert provider.calls == 3
    assert result.content.qcm_questions[0].stem == (
        "Version corrigée et conservée de la première question."
    )
    second_retry_payload = json.loads(provider.message_history[2][-1]["content"])
    assert second_retry_payload["required_question_ordinals"] == [2]
    assert result.validation_report.status is ReportStatus.SUCCESS


def test_corrective_retry_does_not_copy_source_correction_or_add_knowledge(
    tmp_path: Path,
) -> None:
    dataset_path = _dataset_path(tmp_path)
    configuration = _configuration().model_copy(update={"validation_retry_count": 1})
    plan = build_generation_plan(dataset_path, configuration)
    invalid = _response_for_plan(plan)
    invalid_questions = invalid["questions"]
    assert isinstance(invalid_questions, list) and isinstance(invalid_questions[0], dict)
    invalid_questions[0]["explanation"] = "The source value 50% is likely a typo."
    repaired = _correction_from_response(_response_for_plan(plan), [1])
    provider = MockGenerationProvider(lambda call: invalid if call == 1 else repaired)

    result = generate_content(
        dataset_path,
        configuration,
        provider,
        output_root=tmp_path / "generated",
        failure_output_root=tmp_path / "failures",
    )

    correction_text = provider.message_history[1][-1]["content"]
    correction_payload = json.loads(correction_text)
    assert "likely a typo" not in correction_text
    assert correction_payload["corrections"][0]["issue_codes"] == ["source_correction_language"]
    assert any(
        "Never change a source value or add outside medical knowledge" in instruction
        for instruction in correction_payload["instructions"]
    )
    assert result.content.qcm_questions[0].explanation.text != (
        "The source value 50% is likely a typo."
    )


def test_transport_failure_does_not_consume_validation_retries(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    configuration = _configuration().model_copy(
        update={"retry_count": 2, "validation_retry_count": 2}
    )

    class TransportFailureProvider:
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, *_args: object, **_kwargs: object) -> Any:
            self.calls += 1
            raise GenerationProviderError("transport exhausted", attempt_count=3)

    provider = TransportFailureProvider()
    with pytest.raises(GenerationFailure) as captured:
        generate_content(
            dataset_path,
            configuration,
            provider,
            output_root=tmp_path / "generated",
            failure_output_root=tmp_path / "failures",
        )

    report = FailureReport.model_validate_json(
        (captured.value.failure_directory / "failure-report.json").read_text()
    )
    assert provider.calls == 1
    assert report.provider_attempt_count == 3
    assert report.validation_retry_sequence == 0
    assert report.parent_attempt_id is None


def test_targeted_correction_rejects_unrequested_question_ordinal(
    tmp_path: Path,
) -> None:
    dataset_path = _dataset_path(tmp_path)
    configuration = _configuration().model_copy(update={"validation_retry_count": 1})
    plan = build_generation_plan(dataset_path, configuration)
    invalid = _response_for_plan(plan)
    invalid_questions = invalid["questions"]
    assert isinstance(invalid_questions, list) and isinstance(invalid_questions[0], dict)
    invalid_choices = invalid_questions[0]["choices"]
    assert isinstance(invalid_choices, list) and isinstance(invalid_choices[1], dict)
    invalid_choices[1]["text"] = "Fréquence 999%"

    replacement = _response_for_plan(plan)
    questions = replacement["questions"]
    assert len(questions) == 2 and all(isinstance(question, dict) for question in questions)
    second = questions[1]
    assert isinstance(second, dict)
    second["stem"] = "Question sans issue réécrite pendant la correction."
    correction = _correction_from_response(replacement, [1, 2])
    provider = MockGenerationProvider(lambda call: invalid if call == 1 else correction)

    with pytest.raises(GenerationFailure) as captured:
        generate_content(
            dataset_path,
            configuration,
            provider,
            output_root=tmp_path / "generated",
            failure_output_root=tmp_path / "failures",
        )

    assert captured.value.issue_codes == ["retry_unrequested_question_change"]
    report = FailureReport.model_validate_json(
        (captured.value.failure_directory / "failure-report.json").read_text()
    )
    assert report.validation_retry_sequence == 1
    assert report.parent_attempt_id is not None


@pytest.mark.parametrize(
    ("change", "expected_code"),
    [("evidence", "retry_evidence_chunk_changed"), ("difficulty", "retry_difficulty_changed")],
)
def test_targeted_correction_backstop_rejects_scope_changes(
    tmp_path: Path,
    change: str,
    expected_code: str,
) -> None:
    dataset_path = _dataset_path(tmp_path)
    configuration = _configuration().model_copy(update={"validation_retry_count": 1})
    plan = build_generation_plan(dataset_path, configuration)
    invalid = _response_for_plan(plan)
    invalid_questions = invalid["questions"]
    assert isinstance(invalid_questions, list) and isinstance(invalid_questions[0], dict)
    invalid_choices = invalid_questions[0]["choices"]
    assert isinstance(invalid_choices, list) and isinstance(invalid_choices[1], dict)
    invalid_choices[1]["text"] = "Fréquence 999%"
    replacement = _response_for_plan(plan)
    replacement_questions = replacement["questions"]
    assert isinstance(replacement_questions, list) and isinstance(replacement_questions[0], dict)
    if change == "difficulty":
        replacement_questions[0]["difficulty"] = "hard"
    else:
        foreign_chunk = plan.request.source.selected_chunks[1]
        foreign_block_id = foreign_chunk.source_references[-1].block_id
        assert foreign_block_id is not None
        replacement_questions[0]["evidence"] = [
            {
                "chunk_id": foreign_chunk.chunk_id,
                "source_reference_block_ids": [foreign_block_id],
            }
        ]
    correction = _correction_from_response(replacement, [1])
    provider = MockGenerationProvider(lambda call: invalid if call == 1 else correction)

    with pytest.raises(GenerationFailure) as captured:
        generate_content(
            dataset_path,
            configuration,
            provider,
            output_root=tmp_path / "generated",
            failure_output_root=tmp_path / "failures",
        )

    assert captured.value.issue_codes == [expected_code]


def test_corrective_retry_allows_another_contiguous_span_in_same_chunk(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    configuration = _configuration().model_copy(update={"validation_retry_count": 1})
    plan = build_generation_plan(dataset_path, configuration)
    invalid = _response_for_plan(plan)
    invalid_questions = invalid["questions"]
    assert isinstance(invalid_questions, list) and isinstance(invalid_questions[0], dict)
    invalid_choices = invalid_questions[0]["choices"]
    assert isinstance(invalid_choices, list) and isinstance(invalid_choices[1], dict)
    invalid_choices[1]["text"] = "Fréquence 999%"

    replacement = _response_for_plan(plan)
    replacement_questions = replacement["questions"]
    assert isinstance(replacement_questions, list) and isinstance(replacement_questions[0], dict)
    chunk = plan.request.source.selected_chunks[0]
    block_ids = [reference.block_id for reference in chunk.source_references]
    assert len(block_ids) >= 2 and block_ids[-2] is not None and block_ids[-1] is not None
    replacement_questions[0]["evidence"] = [
        {
            "chunk_id": chunk.chunk_id,
            "source_reference_block_ids": [block_ids[-2], block_ids[-1]],
        }
    ]
    correction = _correction_from_response(replacement, [1])
    provider = MockGenerationProvider(lambda call: invalid if call == 1 else correction)

    result = generate_content(
        dataset_path,
        configuration,
        provider,
        output_root=tmp_path / "generated",
        failure_output_root=tmp_path / "failures",
    )

    assert result.validation_report.status is ReportStatus.SUCCESS
    assert result.content.qcm_questions[0].source_chunk_ids == [chunk.chunk_id]


def test_explicit_valid_shortfall_is_needs_revision(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    plan = build_generation_plan(dataset_path, _configuration())
    payload = _response_for_plan(plan)
    questions = payload["questions"]
    assert isinstance(questions, list)
    payload["questions"] = questions[:1]
    payload["insufficient_evidence"] = True
    payload["shortfall_reason"] = "No second question had fully grounded distractors."

    result = generate_content(
        dataset_path,
        _configuration(),
        MockGenerationProvider(lambda _call: payload),
        output_root=tmp_path / "generated",
    )

    assert len(result.content.qcm_questions) == 1
    assert result.validation_report.status is ReportStatus.NEEDS_REVISION
    issue = next(
        issue
        for issue in result.validation_report.issues
        if issue.code == "insufficient_grounded_questions"
    )
    assert issue.severity is IssueSeverity.WARNING


def test_undeclared_shortfall_remains_fatal(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    plan = build_generation_plan(dataset_path, _configuration())
    payload = _response_for_plan(plan)
    questions = payload["questions"]
    assert isinstance(questions, list)
    payload["questions"] = questions[:1]

    with pytest.raises(GenerationFailure) as captured:
        generate_content(
            dataset_path,
            _configuration(),
            MockGenerationProvider(lambda _call: payload),
            output_root=tmp_path / "generated",
            failure_output_root=tmp_path / "failures",
        )
    assert "question_count_mismatch" in captured.value.issue_codes


def test_empty_provider_question_list_remains_invalid(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    payload: dict[str, object] = {
        "questions": [],
        "insufficient_evidence": True,
        "shortfall_reason": "No grounded question could be formed.",
    }

    with pytest.raises(GenerationFailure) as captured:
        generate_content(
            dataset_path,
            _configuration(),
            MockGenerationProvider(lambda _call: payload),
            output_root=tmp_path / "generated",
            failure_output_root=tmp_path / "failures",
        )
    assert "invalid_provider_schema" in captured.value.issue_codes


def test_low_lexical_support_remains_nonfatal(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    plan = build_generation_plan(dataset_path, _configuration())
    payload = _response_for_plan(plan)
    questions = payload["questions"]
    assert isinstance(questions, list) and isinstance(questions[0], dict)
    choices = questions[0]["choices"]
    assert isinstance(choices, list) and isinstance(choices[0], dict)
    choices[0]["text"] = "Réponse abstraite"
    questions[0]["explanation"] = "Concept distinct sans terminologie commune."

    result = generate_content(
        dataset_path,
        _configuration(),
        MockGenerationProvider(lambda _call: payload),
        output_root=tmp_path / "generated",
    )

    assert result.validation_report.status is ReportStatus.NEEDS_REVISION
    low_support = next(
        issue for issue in result.validation_report.issues if issue.code == "low_lexical_support"
    )
    assert low_support.severity is IssueSeverity.WARNING


def _failure_files(directory: Path) -> set[str]:
    return {path.name for path in directory.iterdir()}


def test_malformed_json_persists_exact_response_without_success_output(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    output_root = tmp_path / "generated"
    failure_root = tmp_path / "generated-failures"
    provider = MockGenerationProvider(lambda _call: "{malformed")

    with pytest.raises(GenerationFailure, match="malformed") as captured:
        generate_content(
            dataset_path,
            _configuration(),
            provider,
            output_root=output_root,
            failure_output_root=failure_root,
        )
    directory = captured.value.failure_directory
    raw = json.loads((directory / "raw-provider-response.json").read_text())
    report = FailureReport.model_validate_json((directory / "failure-report.json").read_text())
    assert raw["exact_raw_http_response_text"] == (
        '{"message": {"content": "{malformed"}, "mock": true}'
    )
    assert raw["parsed_provider_envelope"]["message"]["content"] == "{malformed"
    assert raw["provider_content"] == "{malformed"
    assert report.failure_stage is FailureStage.STRUCTURED_PARSING
    assert report.failure_code == "malformed_provider_json"
    assert report.raw_response_is_json is True
    assert report.raw_response_sha256 is not None
    assert not output_root.exists()
    assert "generated-content.json" not in _failure_files(directory)


def test_valid_json_with_invalid_structure_persists_schema_details(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    provider = MockGenerationProvider(lambda _call: {"questions": [{"stem": "incomplete"}]})

    with pytest.raises(GenerationFailure) as captured:
        generate_content(
            dataset_path,
            _configuration(),
            provider,
            output_root=tmp_path / "generated",
            failure_output_root=tmp_path / "failures",
        )
    validation = json.loads(
        (captured.value.failure_directory / "validation-report.json").read_text()
    )
    issue = validation["issues"][0]
    assert issue["code"] == "invalid_provider_schema"
    assert issue["severity"] == "error"
    assert issue["details"]["pydantic_errors"]


def test_materialization_failure_is_persisted(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    plan = build_generation_plan(dataset_path, _configuration())
    payload = _response_for_plan(plan)
    questions = payload["questions"]
    assert isinstance(questions, list)
    first = questions[0]
    assert isinstance(first, dict)
    first["evidence"] = [{"chunk_id": "b" * 64, "source_reference_block_ids": ["block-missing"]}]
    provider = MockGenerationProvider(lambda _call: payload)

    with pytest.raises(GenerationFailure) as captured:
        generate_content(
            dataset_path,
            _configuration(),
            provider,
            output_root=tmp_path / "generated",
            failure_output_root=tmp_path / "failures",
        )
    report = FailureReport.model_validate_json(
        (captured.value.failure_directory / "failure-report.json").read_text()
    )
    assert report.failure_stage is FailureStage.MATERIALIZATION
    assert report.failure_code == "provider_cited_unselected_chunk"
    assert report.provenance_issue_count == 1


def test_mock_schema_bypass_still_rejects_cross_chunk_pair(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    plan = build_generation_plan(dataset_path, _configuration())
    payload = _response_for_plan(plan)
    questions = payload["questions"]
    assert isinstance(questions, list) and isinstance(questions[0], dict)
    first, second = plan.request.source.selected_chunks[:2]
    foreign_block_id = second.source_references[0].block_id
    assert foreign_block_id is not None
    questions[0]["evidence"] = [
        {
            "chunk_id": first.chunk_id,
            "source_reference_block_ids": [foreign_block_id],
        }
    ]
    provider = MockGenerationProvider(lambda _call: payload)

    with pytest.raises(GenerationFailure) as captured:
        generate_content(
            dataset_path,
            _configuration(),
            provider,
            output_root=tmp_path / "generated",
            failure_output_root=tmp_path / "failures",
        )

    assert captured.value.issue_codes == ["unknown_evidence_block_ids"]
    assert provider.last_response_schema == plan.provider_response_schema


def test_grounding_rejects_excluded_chunk_and_detects_duplicate_questions(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    plan = build_generation_plan(dataset_path, _configuration(), output_root=tmp_path / "one")
    provider = MockGenerationProvider(lambda _call: _response_for_plan(plan))
    result = generate_content(
        dataset_path, _configuration(), provider, output_root=tmp_path / "one"
    )
    duplicate_questions = list(result.content.qcm_questions)
    duplicate_questions[1] = duplicate_questions[1].model_copy(
        update={"stem": duplicate_questions[0].stem}
    )
    duplicate_batch = result.content.model_copy(update={"qcm_questions": duplicate_questions})
    _, duplicate_report = validate_generated_content(duplicate_batch, plan.request, plan.dataset)
    assert any(issue.code == "duplicate_question" for issue in duplicate_report.issues)

    cited = result.content.qcm_questions[0].source_chunk_ids[0]
    altered_chunks = [
        chunk.model_copy(
            update={"eligible_for_generation": False, "generation_exclusion_reasons": ["fixture"]}
        )
        if chunk.chunk_id == cited
        else chunk
        for chunk in plan.dataset.chunks
    ]
    altered_dataset = plan.dataset.model_copy(update={"chunks": altered_chunks})
    grounding, validation = validate_generated_content(
        result.content, plan.request, altered_dataset
    )
    assert grounding.status is ReportStatus.FAILED
    assert validation.status is ReportStatus.FAILED
    assert any(issue.code == "excluded_chunk_used" for issue in grounding.issues)


def test_validation_rejects_wrong_difficulty_distribution(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    plan = build_generation_plan(dataset_path, _configuration())
    provider = MockGenerationProvider(lambda _call: _response_for_plan(plan))
    result = generate_content(
        dataset_path, _configuration(), provider, output_root=tmp_path / "generated"
    )
    questions = [
        question.model_copy(update={"difficulty": "easy"})
        for question in result.content.qcm_questions
    ]
    altered = GeneratedContentBatch.model_validate(
        result.content.model_copy(update={"qcm_questions": questions})
    )

    _, validation = validate_generated_content(altered, plan.request, plan.dataset)

    assert validation.status is ReportStatus.FAILED
    assert any(issue.code == "difficulty_distribution_mismatch" for issue in validation.issues)


def test_grounding_failure_persists_numeric_diagnostics(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    plan = build_generation_plan(dataset_path, _configuration())
    payload = _response_for_plan(plan)
    questions = payload["questions"]
    assert isinstance(questions, list)
    first = questions[0]
    assert isinstance(first, dict)
    first["explanation"] = "Le résultat numérique est 999."
    provider = MockGenerationProvider(lambda _call: payload)

    with pytest.raises(GenerationFailure) as captured:
        generate_content(
            dataset_path,
            _configuration(),
            provider,
            output_root=tmp_path / "generated",
            failure_output_root=tmp_path / "failures",
        )
    directory = captured.value.failure_directory
    grounding = json.loads((directory / "grounding-report.json").read_text())
    issue = next(
        item for item in grounding["issues"] if item["code"] == "unsupported_numeric_claim"
    )
    assert issue["question_id"]
    assert issue["chunk_ids"] == [plan.request.source.selected_chunks[0].chunk_id]
    assert issue["details"]["unsupported_numbers"] == ["999"]
    assert not (directory / "generated-content.json").exists()
    assert not (tmp_path / "generated").exists()


def test_provenance_validation_failure_is_persisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset_path = _dataset_path(tmp_path)
    plan = build_generation_plan(dataset_path, _configuration())
    provider = MockGenerationProvider(lambda _call: _response_for_plan(plan))
    issue = ValidationIssue(
        severity=IssueSeverity.ERROR,
        code="source_reference_mismatch",
        message="Fixture provenance mismatch.",
        question_id="c" * 64,
        chunk_ids=[plan.request.source.selected_chunks[0].chunk_id],
        details={"expected_source_references": ["fixture-expected"]},
    )

    def fail_provenance(*_args: object, **_kwargs: object) -> tuple[GroundingReport, Any]:
        from ingestion.generation.models import GenerationValidationReport

        grounding = GroundingReport(
            generation_id=plan.request.generation_id,
            status=ReportStatus.FAILED,
            grounded_question_count=1,
            needs_revision_question_ids=[],
            issues=[issue],
        )
        validation = GenerationValidationReport(
            generation_id=plan.request.generation_id,
            status=ReportStatus.FAILED,
            issue_count=1,
            issues=[issue],
        )
        return grounding, validation

    monkeypatch.setattr("ingestion.generation.service.validate_generated_content", fail_provenance)
    with pytest.raises(GenerationFailure) as captured:
        generate_content(
            dataset_path,
            _configuration(),
            provider,
            output_root=tmp_path / "generated",
            failure_output_root=tmp_path / "failures",
        )
    report = FailureReport.model_validate_json(
        (captured.value.failure_directory / "failure-report.json").read_text()
    )
    assert report.failure_stage is FailureStage.CONTENT_VALIDATION
    assert report.provenance_issue_count == 1
    assert captured.value.issue_codes == ["source_reference_mismatch"]


def test_failed_attempt_directories_are_append_only(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    failure_root = tmp_path / "failures"
    directories: list[Path] = []
    for _index in range(2):
        provider = MockGenerationProvider(lambda _call: "{malformed")
        with pytest.raises(GenerationFailure) as captured:
            generate_content(
                dataset_path,
                _configuration(),
                provider,
                output_root=tmp_path / "generated",
                failure_output_root=failure_root,
            )
        directories.append(captured.value.failure_directory)
    assert directories[0] != directories[1]
    assert all(directory.is_dir() for directory in directories)
    assert all(
        _failure_files(directory)
        == {
            "request.json",
            "selected-sources.json",
            "raw-provider-response.json",
            "validation-report.json",
            "grounding-report.json",
            "failure-report.json",
        }
        for directory in directories
    )
    first = directories[0]
    with pytest.raises(GenerationFailureOutputExistsError):
        write_generation_failure(
            GenerationRequest.model_validate_json((first / "request.json").read_text()),
            RawProviderResponseRecord.model_validate_json(
                (first / "raw-provider-response.json").read_text()
            ),
            GenerationValidationReport.model_validate_json(
                (first / "validation-report.json").read_text()
            ),
            GroundingReport.model_validate_json((first / "grounding-report.json").read_text()),
            FailureReport.model_validate_json((first / "failure-report.json").read_text()),
            failure_root=failure_root,
        )


def test_provider_failure_without_response_uses_exception_fingerprint_path(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)

    class FailingProvider:
        def generate(self, *_args: object) -> Any:
            raise GenerationProviderError("fixture connection failure", attempt_count=3)

    with pytest.raises(GenerationFailure) as captured:
        generate_content(
            dataset_path,
            _configuration(),
            FailingProvider(),
            output_root=tmp_path / "generated",
            failure_output_root=tmp_path / "failures",
        )
    report = FailureReport.model_validate_json(
        (captured.value.failure_directory / "failure-report.json").read_text()
    )
    raw = RawProviderResponseRecord.model_validate_json(
        (captured.value.failure_directory / "raw-provider-response.json").read_text()
    )
    assert report.failure_stage is FailureStage.PROVIDER_RESPONSE
    assert report.provider_attempt_count == 3
    assert report.raw_response_sha256 is None
    assert len(report.exception_fingerprint) == 64
    assert raw.exact_raw_http_response_text is None


def test_atomic_failure_finalization_cleans_partial_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset_path = _dataset_path(tmp_path)
    failure_root = tmp_path / "failures"
    provider = MockGenerationProvider(lambda _call: "{malformed")

    def fail_write(_path: Path, _value: object) -> None:
        raise OSError("fixture failure-write interruption")

    monkeypatch.setattr("ingestion.generation.output._write_model", fail_write)
    with pytest.raises(OSError, match="failure-write interruption"):
        generate_content(
            dataset_path,
            _configuration(),
            provider,
            output_root=tmp_path / "generated",
            failure_output_root=failure_root,
        )
    assert not list(failure_root.rglob("*.json")) if failure_root.exists() else True
    assert not list(failure_root.rglob(".*.tmp")) if failure_root.exists() else True
    assert not (tmp_path / "generated").exists()


def test_reviewed_generation_is_terminal_and_generation_never_overwrites(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    output_root = tmp_path / "generated"
    plan = build_generation_plan(dataset_path, _configuration(), output_root=output_root)
    provider = MockGenerationProvider(lambda _call: _response_for_plan(plan))
    result = generate_content(dataset_path, _configuration(), provider, output_root=output_root)
    question_id = result.content.qcm_questions[0].question_id
    reviewed = review_content(
        result.output_directory,
        decision=ReviewStatus.ACCEPTED,
        reviewer="fixture-reviewer",
        question_id=question_id,
    )
    assert reviewed.qcm_questions[0].medical_review.status is ReviewStatus.ACCEPTED
    with pytest.raises(ReviewTransitionError, match="terminal"):
        review_content(
            result.output_directory,
            decision=ReviewStatus.REJECTED,
            reviewer="fixture-reviewer",
            question_id=question_id,
        )
    with pytest.raises(GenerationOutputExistsError):
        generate_content(dataset_path, _configuration(), provider, output_root=output_root)
    assert provider.calls == 1


def test_atomic_write_failure_cleans_temporary_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset_path = _dataset_path(tmp_path)
    output_root = tmp_path / "generated"
    plan = build_generation_plan(dataset_path, _configuration(), output_root=output_root)
    provider = MockGenerationProvider(lambda _call: _response_for_plan(plan))

    def fail_write(_path: Path, _value: object) -> None:
        raise OSError("fixture write interruption")

    monkeypatch.setattr("ingestion.generation.output._write_model", fail_write)
    with pytest.raises(OSError, match="fixture write interruption"):
        generate_content(dataset_path, _configuration(), provider, output_root=output_root)
    assert not plan.proposed_output_directory.exists()
    assert not list(plan.proposed_output_directory.parent.glob(".*.tmp"))


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.status = 200
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()


class _FakeConnection:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = responses
        self.request_body: bytes | None = None

    def request(self, *_args: object, **kwargs: object) -> None:
        body = kwargs.get("body")
        assert isinstance(body, bytes)
        self.request_body = body

    def getresponse(self) -> _FakeResponse:
        return _FakeResponse(self.responses.pop(0))

    def close(self) -> None:
        return None


def test_ollama_provider_preserves_exact_http_text_without_socket(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    configuration = _configuration(1).model_copy(
        update={
            "provider": ProviderKind.OLLAMA,
            "base_url": "http://127.0.0.1:11434",
            "retry_count": 1,
        }
    )
    plan = build_generation_plan(dataset_path, configuration)
    malformed_envelope = {"message": {"content": "{malformed"}}
    fake = _FakeConnection(
        [
            malformed_envelope,
        ]
    )
    provider = OllamaGenerationProvider(lambda _host, _port, _timeout: fake)  # type: ignore[arg-type]
    result = provider.generate(plan.messages, configuration, plan.provider_response_schema)

    assert result.attempt_count == 1
    assert result.raw_response_text == json.dumps(malformed_envelope)
    assert result.raw_envelope == malformed_envelope
    assert result.content == "{malformed"
    assert fake.request_body is not None
    assert json.loads(fake.request_body)["format"] == plan.provider_response_schema


def test_ollama_provider_wraps_http_protocol_errors(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    configuration = _configuration(1).model_copy(
        update={"provider": ProviderKind.OLLAMA, "retry_count": 1}
    )
    plan = build_generation_plan(dataset_path, configuration)

    class ProtocolFailureConnection(_FakeConnection):
        def getresponse(self) -> _FakeResponse:
            from http.client import BadStatusLine

            raise BadStatusLine("fixture malformed HTTP response")

    provider = OllamaGenerationProvider(
        lambda _host, _port, _timeout: ProtocolFailureConnection([])  # type: ignore[arg-type]
    )

    with pytest.raises(OllamaProviderError, match="after 2 attempt") as captured:
        provider.generate(plan.messages, configuration, plan.provider_response_schema)

    assert captured.value.attempt_count == 2
    assert captured.value.raw_response_text is None


def test_cli_reports_failed_attempt_path_and_issue_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failure_directory = tmp_path / "failures" / ("a" * 64)

    def fail_generation(*_args: object, **_kwargs: object) -> None:
        raise GenerationFailure(
            "fixture validation failure",
            failure_directory,
            ["evidence_quotation_mismatch", "unsupported_numeric_claim"],
        )

    monkeypatch.setattr("ingestion.cli.generate_content", fail_generation)
    result = CliRunner().invoke(
        app,
        [
            "generate-content",
            str(tmp_path / "dataset.json"),
            "--model",
            "fixture-model",
            "--content-type",
            "qcm",
            "--count",
            "1",
        ],
    )

    assert result.exit_code == 1
    assert "failed_attempt:" in result.output
    assert str(failure_directory.parent) in result.output
    assert "evidence_quotation_mismatch" in result.output
    assert "unsupported_numeric_claim" in result.output
    assert "Contexte clinique source" not in result.output


def test_cli_generation_options_use_ollama_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset_path = _dataset_path(tmp_path)
    monkeypatch.setenv("MEDPARSE_OLLAMA_MODEL", "environment-model")
    monkeypatch.setenv("MEDPARSE_OLLAMA_CONTEXT_SIZE", "4096")

    result = CliRunner().invoke(
        app,
        [
            "plan-generation",
            str(dataset_path),
            "--content-type",
            "qcm",
            "--count",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert "model: environment-model" in result.output


def test_validate_generation_rejects_tampered_recorded_request(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    configuration = _configuration()
    plan = build_generation_plan(dataset_path, configuration, output_root=tmp_path / "generated")
    provider = MockGenerationProvider(lambda _call: _response_for_plan(plan))
    result = generate_content(
        dataset_path, configuration, provider, output_root=tmp_path / "generated"
    )
    request_path = result.output_directory / "request.json"
    request = json.loads(request_path.read_text())
    request["source"]["dataset_sha256"] = "f" * 64
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation = CliRunner().invoke(app, ["validate-generation", str(result.output_directory)])

    assert validation.exit_code == 1
    assert "Recorded source selection" in validation.output


def test_loopback_configuration_rejects_remote_endpoint() -> None:
    with pytest.raises(ValueError, match="loopback"):
        generation_configuration(
            content_type=ContentType.QCM,
            qcm_type=QCMType.SINGLE_ANSWER,
            count=1,
            language="fr",
            difficulty="easy",
            knowledge_mode=KnowledgeMode.SOURCE_ONLY,
            provider=ProviderKind.OLLAMA,
            model="fixture",
            base_url="http://example.com:11434",
            environ={},
        )


def test_validation_retry_configuration_defaults_to_one() -> None:
    configuration = generation_configuration(
        content_type=ContentType.QCM,
        qcm_type=QCMType.SINGLE_ANSWER,
        count=1,
        language="fr",
        difficulty="easy",
        knowledge_mode=KnowledgeMode.SOURCE_ONLY,
        provider=ProviderKind.OLLAMA,
        model="fixture",
        environ={},
    )

    assert configuration.validation_retry_count == 1


def test_generation_does_not_mutate_dataset(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    before = copy.deepcopy(dataset_path.read_bytes())
    plan = build_generation_plan(dataset_path, _configuration(), output_root=tmp_path / "generated")
    provider = MockGenerationProvider(lambda _call: _response_for_plan(plan))
    generate_content(dataset_path, _configuration(), provider, output_root=tmp_path / "generated")
    assert dataset_path.read_bytes() == before
