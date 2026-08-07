"""Atomic, append-only output for course artifacts."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from ingestion.courses.models import CourseCatalog, CourseCoverageLedger, KnowledgeUnitCollection
from ingestion.courses.service import load_course_artifacts
from ingestion.output import ensure_output_outside_source, write_json_atomic


class CourseOutputExistsError(RuntimeError):
    """Course output is immutable once finalized."""


def write_course_artifacts(
    catalog: CourseCatalog,
    units: KnowledgeUnitCollection,
    ledger: CourseCoverageLedger,
    *,
    output_root: Path = Path("data/courses"),
) -> Path:
    for protected in (
        Path("pdfsrc"),
        Path("data/processed"),
        Path("data/derived"),
        Path("data/reports"),
        Path("data/generated"),
        Path("data/generated-failures"),
    ):
        ensure_output_outside_source(output_root, protected)
    final = output_root / catalog.course_id
    if final.exists():
        raise CourseOutputExistsError(f"Course output already exists: {final}")
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = output_root / f".{catalog.course_id}.{uuid4().hex}.tmp"
    try:
        temporary.mkdir()
        write_json_atomic(temporary / "course-catalog.json", catalog.model_dump(mode="json"))
        write_json_atomic(temporary / "knowledge-units.json", units.model_dump(mode="json"))
        write_json_atomic(temporary / "qcm-coverage.json", ledger.model_dump(mode="json"))
        persisted = load_course_artifacts(temporary)
        if persisted != (catalog, units, ledger):
            raise ValueError("Persisted course artifacts changed during validation.")
        temporary.rename(final)
        return final
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
