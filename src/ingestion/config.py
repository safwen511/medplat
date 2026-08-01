"""Typed runtime configuration for local-only Docling PDF models."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from importlib import import_module
from pathlib import Path

DOCLING_ARTIFACTS_ENV = "DOCLING_ARTIFACTS_PATH"


class DoclingErrorCategory(str, Enum):
    ARTIFACTS_NOT_CONFIGURED = "docling_artifacts_not_configured"
    ARTIFACTS_PATH_MISSING = "docling_artifacts_path_missing"
    ARTIFACTS_INVALID = "docling_artifacts_invalid"
    REQUIRED_MODEL_MISSING = "docling_required_model_missing"
    MODEL_INITIALIZATION_FAILED = "docling_model_initialization_failed"
    PDF_PARSE_FAILED = "pdf_parse_failed"
    SOURCE_PARSE_FAILED = "source_parse_failed"
    OCR_REQUIRED_BUT_DISABLED = "ocr_required_but_disabled"


class DoclingConfigurationError(RuntimeError):
    """Actionable local-model configuration failure."""

    def __init__(self, category: DoclingErrorCategory, message: str) -> None:
        self.category = category
        super().__init__(f"{category.value}: {message}")


@dataclass(frozen=True)
class DoclingArtifactInventory:
    """Validated, non-secret description of the required local model set."""

    root: Path
    components: tuple[str, ...]
    artifact_identifiers: tuple[str, ...]


@dataclass(frozen=True)
class DoclingSettings:
    """Settings resolved with CLI-over-environment precedence."""

    artifacts_path: Path | None
    local_only: bool = True
    ocr_enabled: bool = False
    table_structure_enabled: bool = True

    @classmethod
    def from_sources(
        cls,
        cli_artifacts_path: Path | None = None,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> DoclingSettings:
        values = os.environ if environ is None else environ
        configured = cli_artifacts_path
        if configured is None:
            raw = values.get(DOCLING_ARTIFACTS_ENV)
            configured = Path(raw) if raw else None
        normalized = configured.expanduser().resolve() if configured is not None else None
        return cls(artifacts_path=normalized)

    def enforce_local_only(self) -> None:
        """Prevent Hugging Face/Transformers network fallback in this process."""
        if not self.local_only:
            raise DoclingConfigurationError(
                DoclingErrorCategory.ARTIFACTS_INVALID,
                "PDF parsing must run in local-only mode.",
            )
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        # Docling imports huggingface_hub before the first PDF parse. Keep its cached
        # process-level flag aligned with the environment set above.
        constants = import_module("huggingface_hub.constants")
        constants.__dict__["HF_HUB_OFFLINE"] = True

    def validate_pdf_artifacts(self) -> DoclingArtifactInventory:
        """Validate the minimal non-OCR standard PDF model layout."""
        root = self.artifacts_path
        if root is None:
            raise DoclingConfigurationError(
                DoclingErrorCategory.ARTIFACTS_NOT_CONFIGURED,
                f"Set {DOCLING_ARTIFACTS_ENV} or pass --docling-artifacts-path.",
            )
        if not root.exists():
            raise DoclingConfigurationError(
                DoclingErrorCategory.ARTIFACTS_PATH_MISSING,
                f"Configured artifact directory does not exist: {root}",
            )
        if not root.is_dir():
            raise DoclingConfigurationError(
                DoclingErrorCategory.ARTIFACTS_INVALID,
                f"Configured artifact path is not a directory: {root}",
            )

        layout = root / "docling-project--docling-layout-heron"
        table = (
            root
            / "docling-project--docling-models"
            / "model_artifacts"
            / "tableformer"
            / "accurate"
        )
        if not layout.exists() and not table.exists():
            raise DoclingConfigurationError(
                DoclingErrorCategory.ARTIFACTS_INVALID,
                "The directory is not a Docling artifact root; expected the official "
                "layout and TableFormer repository folders.",
            )

        required = (
            layout / "config.json",
            layout / "preprocessor_config.json",
            layout / "model.safetensors",
            table / "tm_config.json",
        )
        missing = [path.relative_to(root).as_posix() for path in required if not path.is_file()]
        weights = sorted(table.glob("tableformer_*.safetensors")) if table.is_dir() else []
        if not weights:
            missing.append(
                "docling-project--docling-models/model_artifacts/tableformer/accurate/"
                "tableformer_*.safetensors"
            )
        empty = [
            path.relative_to(root).as_posix()
            for path in required
            if path.is_file() and path.stat().st_size == 0
        ]
        empty.extend(
            path.relative_to(root).as_posix() for path in weights if path.stat().st_size == 0
        )
        if missing or empty:
            details = []
            if missing:
                details.append(f"missing: {', '.join(missing)}")
            if empty:
                details.append(f"empty: {', '.join(empty)}")
            raise DoclingConfigurationError(
                DoclingErrorCategory.REQUIRED_MODEL_MISSING,
                "Required local model artifacts are incomplete (" + "; ".join(details) + ").",
            )

        return DoclingArtifactInventory(
            root=root,
            components=("layout", "tableformer-accurate"),
            artifact_identifiers=(
                layout.name,
                "docling-project--docling-models/tableformer-accurate",
            ),
        )
