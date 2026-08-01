"""Non-parsing environment diagnostics for the local PDF pipeline."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from ingestion.config import DoclingConfigurationError, DoclingSettings


@dataclass(frozen=True)
class EnvironmentCheck:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class EnvironmentDoctorReport:
    ready: bool
    checks: tuple[EnvironmentCheck, ...]
    remediation: tuple[str, ...] = field(default_factory=tuple)


def _package_check(module: str, distribution: str, label: str) -> EnvironmentCheck:
    try:
        import_module(module)
        installed = version(distribution)
    except (ImportError, PackageNotFoundError) as exc:
        return EnvironmentCheck(label, False, f"unavailable ({type(exc).__name__})")
    return EnvironmentCheck(label, True, installed)


def _writable_directory(path: Path) -> bool:
    candidate = path.resolve()
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate.is_dir() and os.access(candidate, os.W_OK)


def check_environment(
    settings: DoclingSettings,
    *,
    output_root: Path = Path("data/processed"),
) -> EnvironmentDoctorReport:
    """Check configuration and packages without parsing or downloading."""
    checks = [
        EnvironmentCheck(
            "Python",
            sys.version_info >= (3, 10),
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        ),
        _package_check("docling", "docling", "Docling"),
        _package_check("fitz", "pymupdf", "PyMuPDF"),
        _package_check("pydantic", "pydantic", "Pydantic"),
        _package_check("typer", "typer", "Typer"),
        _package_check("rich", "rich", "Rich"),
        EnvironmentCheck("Local-only mode", settings.local_only, "enabled"),
        EnvironmentCheck("OCR", not settings.ocr_enabled, "disabled"),
        EnvironmentCheck(
            "Output directory",
            _writable_directory(output_root),
            f"writable parent for {output_root}",
        ),
        EnvironmentCheck(
            "Source library policy",
            True,
            "pdfsrc is treated as read-only; diagnostic performs no source writes",
        ),
    ]
    remediation: list[str] = []
    try:
        inventory = settings.validate_pdf_artifacts()
    except DoclingConfigurationError as exc:
        checks.append(EnvironmentCheck("Docling artifacts", False, str(exc)))
        remediation.append(
            "Download layout and TableFormer with docling-tools, then set "
            "DOCLING_ARTIFACTS_PATH to that artifact root."
        )
    else:
        checks.append(EnvironmentCheck("Configured artifact path", True, str(inventory.root)))
        checks.append(
            EnvironmentCheck(
                "Docling artifacts",
                True,
                f"validated components: {', '.join(inventory.components)}",
            )
        )
    return EnvironmentDoctorReport(
        ready=all(check.ok for check in checks),
        checks=tuple(checks),
        remediation=tuple(remediation),
    )
