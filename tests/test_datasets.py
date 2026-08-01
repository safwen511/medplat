from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ingestion.chunking.builder import build_chunk_collection
from ingestion.datasets.builder import build_ai_ready_dataset
from ingestion.datasets.models import AIReadyDataset
from ingestion.datasets.output import (
    DerivedOutputExistsError,
    write_dataset_output,
)
from ingestion.datasets.validation import validate_dataset_file
from tests.test_chunking import DOCUMENT_ID, simple_nested_document


def test_dataset_serialization_is_deterministic_and_contains_no_generated_content() -> None:
    document = simple_nested_document()
    collection = build_chunk_collection(document)

    first = build_ai_ready_dataset(document, collection)
    second = build_ai_ready_dataset(document, collection)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    serialized = first.model_dump_json()
    assert "generated_questions" not in serialized
    assert "embeddings" not in serialized
    assert first.provenance_metadata["generated_content_present"] is False


def test_dataset_validates_document_and_chunk_relationships() -> None:
    document = simple_nested_document()
    collection = build_chunk_collection(document)
    mismatched = collection.model_copy(update={"document_id": "b" * 64})

    with pytest.raises(ValueError, match="does not belong"):
        build_ai_ready_dataset(document, mismatched)

    dataset = build_ai_ready_dataset(document, collection)
    payload = dataset.model_dump(mode="json")
    payload["chunks"][0]["document_id"] = "b" * 64
    with pytest.raises(ValidationError):
        AIReadyDataset.model_validate(payload)


def test_dataset_atomic_output_validation_cleanup_and_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = simple_nested_document()
    before = copy.deepcopy(document.model_dump(mode="json"))
    collection = build_chunk_collection(document)
    dataset = build_ai_ready_dataset(document, collection)
    canonical_dir = tmp_path / DOCUMENT_ID
    canonical_dir.mkdir()
    canonical_path = canonical_dir / "document.json"
    canonical_path.write_text(document.model_dump_json(), encoding="utf-8")

    output = write_dataset_output(canonical_path, dataset)
    validated = validate_dataset_file(output / "ai-ready-dataset.json")
    assert validated.chunk_count == collection.chunk_count
    assert document.model_dump(mode="json") == before
    with pytest.raises(DerivedOutputExistsError):
        write_dataset_output(canonical_path, dataset)

    write_dataset_output(canonical_path, dataset, force=True)

    def fail_validation(_path: Path) -> AIReadyDataset:
        raise ValueError("dataset validation interrupted")

    monkeypatch.setattr("ingestion.datasets.output.validate_dataset_file", fail_validation)
    with pytest.raises(ValueError, match="dataset validation interrupted"):
        write_dataset_output(canonical_path, dataset, force=True)
    assert validate_dataset_file(output / "ai-ready-dataset.json").document_id == DOCUMENT_ID
    assert not list(canonical_dir.glob(".datasets.*.tmp"))


def test_dataset_json_is_one_complete_valid_object(tmp_path: Path) -> None:
    document = simple_nested_document()
    collection = build_chunk_collection(document)
    dataset = build_ai_ready_dataset(document, collection)
    path = tmp_path / "dataset.json"
    path.write_text(dataset.model_dump_json(indent=2), encoding="utf-8")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert AIReadyDataset.model_validate(payload).dataset_schema_version == "1.0.0"
