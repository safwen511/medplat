from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from generate_exercises import check, to_web  # noqa: E402

import ingestion.library  # noqa: E402


def lesson_dir(tmp_path: Path, monkeypatch) -> Path:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("generate_exercises.PROJECT_ROOT", tmp_path)
    (tmp_path / "text").mkdir()
    (tmp_path / "text" / "s1.txt").write_text(
        "===== PAGE 1 =====\n\nDose de 20 mg/kg/j pendant 7 jours, ou 10 mg/kg/j chez l'enfant.\n",
        encoding="utf-8",
    )
    directory = tmp_path / "lesson"
    directory.mkdir()
    (directory / "lesson.json").write_text(
        json.dumps({"sources": {"S1": {"text_root": "text", "text_relative_path": "s1.txt"}}}),
        encoding="utf-8",
    )
    return directory


def qcm(**changes: object) -> dict[str, object]:
    item: dict[str, object] = {
        "type": "qcm",
        "stem": "Quelle dose ?",
        "options": [{"id": "A", "text": "20 mg/kg/j"}, {"id": "B", "text": "10 mg/kg/j"}],
        "answer": "A",
        "hints": ["h1", "h2", "h3"],
        "explanation": "La dose est de 20 mg/kg/j. [S1 p.1]",
        "citations": "[S1 p.1]",
        "high_yield": True,
        "difficulty": 1,
    }
    item.update(changes)
    return item


def test_valid_item_passes_and_converts(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    directory = lesson_dir(tmp_path, monkeypatch)
    assert check(directory, qcm()) == []
    web = to_web("x.y.z", 1, qcm())
    assert web["id"] == "x.y.z#q1" and web["answer"] == "A" and web["highYield"] is True


def test_distractor_with_unsupported_number_is_rejected(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    directory = lesson_dir(tmp_path, monkeypatch)
    item = qcm(options=[{"id": "A", "text": "20 mg/kg/j"}, {"id": "B", "text": "40 mg/kg/j"}])
    assert any("numbers not in cited pages" in error for error in check(directory, item))


def test_shape_and_citation_errors(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    directory = lesson_dir(tmp_path, monkeypatch)
    errors = check(directory, qcm(answer="C", hints=["h1"], citations="[S9 p.1]"))
    assert "answer is not an option" in errors
    assert "hint ladder must have 3 steps" in errors
    assert "unknown source S9" in errors
    assert ingestion.library.PROJECT_ROOT != tmp_path
