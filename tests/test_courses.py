from __future__ import annotations

import copy
from pathlib import Path, PurePosixPath

import pytest
from typer.testing import CliRunner

from ingestion.cli import app
from ingestion.courses.models import CoverageStatus
from ingestion.courses.output import CourseOutputExistsError, write_course_artifacts
from ingestion.courses.service import (
    build_course_catalog,
    build_course_qcm_plan,
    build_coverage_ledger,
    load_course_artifacts,
)
from ingestion.generation.providers.mock import MockGenerationProvider
from ingestion.generation.service import build_generation_plan, generate_content
from tests.test_generation import _configuration, _dataset_path, _response_for_plan


def test_course_catalog_preserves_folder_taxonomy_without_copying_source_text(
    tmp_path: Path,
) -> None:
    dataset_path = _dataset_path(tmp_path)
    before = dataset_path.read_bytes()

    first_catalog, first_units = build_course_catalog([dataset_path], course_name="Fixture course")
    second_catalog, second_units = build_course_catalog(
        [dataset_path], course_name="Fixture course"
    )

    assert first_catalog == second_catalog
    assert first_units == second_units
    source_parent = PurePosixPath(first_catalog.documents[0].source_relative_path).parent
    assert first_catalog.course_root == str(source_parent)
    assert first_catalog.taxonomy_labels == list(source_parent.parts)
    assert first_catalog.knowledge_unit_count == first_units.unit_count
    assert first_catalog.eligible_unit_count > 0
    assert first_catalog.knowledge_unit_strategy_version == "qcm-substantive-chunk-v1"
    assert all(unit.folder_path == list(source_parent.parts) for unit in first_units.units)
    assert all(
        unit.taxonomy_path[: len(source_parent.parts)] == list(source_parent.parts)
        for unit in first_units.units
    )
    assert dataset_path.read_bytes() == before


def test_coverage_ledger_tracks_pending_excluded_and_existing_drafts(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    catalog, units = build_course_catalog([dataset_path], course_name="Fixture course")
    initial = build_coverage_ledger(units, generation_root=tmp_path / "generated")
    assert initial.course_id == catalog.course_id
    assert initial.status_counts[CoverageStatus.PENDING] == catalog.eligible_unit_count
    assert initial.status_counts.get(CoverageStatus.EXCLUDED, 0) == catalog.excluded_unit_count

    configuration = _configuration()
    generation_plan = build_generation_plan(
        dataset_path, configuration, output_root=tmp_path / "generated"
    )
    provider = MockGenerationProvider(lambda _call: _response_for_plan(generation_plan))
    generated = generate_content(
        dataset_path,
        configuration,
        provider,
        output_root=tmp_path / "generated",
        failure_output_root=tmp_path / "failures",
    )
    assert generated.output_directory.exists()

    updated = build_coverage_ledger(units, generation_root=tmp_path / "generated")
    attempted = [record for record in updated.records if record.question_ids]
    assert attempted
    assert all(record.status is CoverageStatus.NEEDS_REVISION for record in attempted)
    assert all(
        record.generation_ids == [generation_plan.request.generation_id] for record in attempted
    )


def test_course_qcm_plan_selects_only_pending_units_deterministically(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    catalog, units = build_course_catalog([dataset_path], course_name="Fixture course")
    ledger = build_coverage_ledger(units, generation_root=tmp_path / "generated")
    first = build_course_qcm_plan(
        catalog,
        units,
        ledger,
        requested_count=2,
        maximum_source_characters=12000,
        maximum_source_tokens=3000,
        proposed_plan_root=tmp_path / "course",
    )
    second = build_course_qcm_plan(
        catalog,
        units,
        ledger,
        requested_count=2,
        maximum_source_characters=12000,
        maximum_source_tokens=3000,
        proposed_plan_root=tmp_path / "course",
    )

    assert first == second
    assert first.provider_request == "none"
    assert first.writes == "none"
    assert first.planned_question_count == 2
    records = {record.unit_id: record for record in ledger.records}
    assert all(
        records[unit.unit_id].status is CoverageStatus.PENDING for unit in first.selected_units
    )
    assert len({unit.chunk_id for unit in first.selected_units}) == 2
    assert all(unit.character_count >= 100 for unit in first.selected_units)
    assert all(unit.source_references for unit in first.selected_units)
    assert not (tmp_path / "course" / "plans").exists()


def test_course_output_is_atomic_immutable_and_does_not_mutate_inputs(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    catalog, units = build_course_catalog([dataset_path], course_name="Fixture course")
    ledger = build_coverage_ledger(units, generation_root=tmp_path / "generated")
    before = copy.deepcopy((catalog.model_dump(mode="json"), units.model_dump(mode="json")))

    output = write_course_artifacts(catalog, units, ledger, output_root=tmp_path / "courses")
    loaded = load_course_artifacts(output)
    assert loaded == (catalog, units, ledger)
    assert before == (catalog.model_dump(mode="json"), units.model_dump(mode="json"))
    with pytest.raises(CourseOutputExistsError):
        write_course_artifacts(catalog, units, ledger, output_root=tmp_path / "courses")
    assert not list((tmp_path / "courses").glob(".*.tmp"))


def test_course_cli_builds_catalog_and_plans_without_plan_writes(tmp_path: Path) -> None:
    dataset_path = _dataset_path(tmp_path)
    runner = CliRunner()
    build = runner.invoke(
        app,
        [
            "build-course-catalog",
            str(dataset_path),
            "--course-name",
            "Fixture course",
            "--output-root",
            str(tmp_path / "courses"),
            "--generation-root",
            str(tmp_path / "generated"),
        ],
    )
    assert build.exit_code == 0, build.output
    course_output = next((tmp_path / "courses").iterdir())

    plan = runner.invoke(app, ["plan-course-qcm", str(course_output), "--count", "2"])
    assert plan.exit_code == 0, plan.output
    assert "planned_questions: 2" in plan.output
    assert "provider_request: none" in plan.output
    assert "writes: none" in plan.output
    assert not (course_output / "plans").exists()
