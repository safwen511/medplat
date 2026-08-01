"""Read-only checks for local OCR executables and languages."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ingestion.ocr.models import OCREnvironmentReport


def _version(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    output = (result.stdout or result.stderr).strip().splitlines()
    return output[0].strip() if output else None


def installed_tesseract_languages() -> list[str]:
    if shutil.which("tesseract") is None:
        return []
    try:
        result = subprocess.run(
            ["tesseract", "--list-langs"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return sorted(
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and not line.startswith("List of available")
    )


def _writable_parent(path: Path) -> bool:
    candidate = path.expanduser().resolve()
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate.is_dir() and os.access(candidate, os.W_OK)


def check_ocr_environment(
    requested_languages: list[str], output_root: Path = Path("data/derived")
) -> OCREnvironmentReport:
    tools = {
        "ocrmypdf": _version(["ocrmypdf", "--version"]),
        "tesseract": _version(["tesseract", "--version"]),
        "qpdf": _version(["qpdf", "--version"]),
        "ghostscript": _version(["gs", "--version"]),
    }
    missing_tools = [name for name, value in tools.items() if value is None]
    installed = installed_tesseract_languages()
    missing_languages = sorted(set(requested_languages) - set(installed))
    writable = _writable_parent(output_root)
    return OCREnvironmentReport(
        ready=not missing_tools and not missing_languages and writable,
        ocrmypdf_version=tools["ocrmypdf"],
        tesseract_version=tools["tesseract"],
        qpdf_version=tools["qpdf"],
        ghostscript_version=tools["ghostscript"],
        installed_languages=installed,
        requested_languages=requested_languages,
        missing_tools=missing_tools,
        missing_languages=missing_languages,
        derivative_output_writable=writable,
        source_library_policy="pdfsrc is read-only; OCR output is derivative-only",
    )
