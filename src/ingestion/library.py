"""Per-year course library layout resolved from library.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIBRARY_CONFIG = PROJECT_ROOT / "library.toml"


@dataclass(frozen=True)
class Year:
    """One study year: read-only originals plus the data directories derived from them."""

    id: str
    label: str
    source: Path

    @property
    def data(self) -> Path:
        return PROJECT_ROOT / "data" / self.id

    @property
    def text(self) -> Path:
        """Mirrored text exports of the originals."""
        return self.data / "text"

    @property
    def text_office(self) -> Path:
        """Text exports of legacy Office files converted to .pptx derivatives."""
        return self.data / "text-office"

    @property
    def office(self) -> Path:
        """Content-addressed LibreOffice derivatives."""
        return self.data / "office"

    @property
    def ocr(self) -> Path:
        """Content-addressed OCR derivatives."""
        return self.data / "ocr"

    @property
    def reports(self) -> Path:
        return self.data / "reports"

    @property
    def catalog(self) -> Path:
        return self.data / "catalog"

    @property
    def lessons(self) -> Path:
        return self.data / "lessons"


def _config(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def load_years(path: Path = LIBRARY_CONFIG) -> dict[str, Year]:
    years = _config(path).get("years", {})
    if not isinstance(years, dict):
        raise ValueError(f"{path}: [years] must be a table.")
    return {
        year_id: Year(id=year_id, label=entry["label"], source=PROJECT_ROOT / entry["source"])
        for year_id, entry in years.items()
    }


def get_year(year_id: str, path: Path = LIBRARY_CONFIG) -> Year:
    years = load_years(path)
    if year_id not in years:
        raise ValueError(f"Unknown year {year_id!r}; configured: {', '.join(sorted(years))}.")
    return years[year_id]


def docling_artifacts_path(path: Path = LIBRARY_CONFIG) -> Path:
    models = _config(path).get("models", {})
    if not isinstance(models, dict) or "docling" not in models:
        raise ValueError(f"{path}: [models] docling is not configured.")
    return PROJECT_ROOT / str(models["docling"])
