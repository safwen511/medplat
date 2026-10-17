"""Convert legacy PowerPoint sources (.ppt, .ppsx) to .pptx derivatives and export their text.

The read-only source is copied to a temporary directory and converted there with LibreOffice
headless; the source tree is never written. Each derivative is content-addressed under
data/<year>/office/<source-sha256>/ with a provenance record, then extracted with the project's
existing Docling Office route (no PDF models, no OCR). Text exports are written in the standard
mirrored format under data/<year>/text-office/, keeping the original source-relative path,
extension, and SHA-256 in the header. Usage: python scripts/convert_legacy_office.py --year dcem1
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ingestion.config import DoclingSettings
from ingestion.hashing import sha256_file
from ingestion.library import Year, get_year
from ingestion.output import write_json_atomic, write_text_atomic
from ingestion.text_tree.discovery import DiscoveredSource
from ingestion.text_tree.extraction import LocalTextExtractor
from ingestion.text_tree.models import ExportStatus
from ingestion.text_tree.rendering import render_export

LEGACY_EXTENSIONS = {".ppt", ".ppsx"}


def libreoffice_version() -> str:
    result = subprocess.run(["soffice", "--version"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def convert(source: Path, workdir: Path) -> Path:
    staged = workdir / f"source{source.suffix.lower()}"
    shutil.copyfile(source, staged)
    subprocess.run(
        [
            "soffice",
            "--headless",
            f"-env:UserInstallation=file://{workdir / 'profile'}",
            "--convert-to",
            "pptx",
            "--outdir",
            str(workdir / "out"),
            str(staged),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    converted = workdir / "out" / "source.pptx"
    if not converted.is_file():
        raise RuntimeError("LibreOffice produced no .pptx output.")
    return converted


def main(year: Year) -> int:
    source_root, derived_root, text_root = year.source, year.office, year.text_office
    inventory = year.catalog / "inventory.json"
    records = json.loads(inventory.read_text(encoding="utf-8"))["records"]
    legacy = [r for r in records if r["extension"].lower() in LEGACY_EXTENSIONS]
    version = libreoffice_version()
    extractor = LocalTextExtractor(DoclingSettings.from_sources())
    manifest = []
    for record in legacy:
        relative_path = record["source_relative_path"]
        source = source_root / relative_path
        source_sha = sha256_file(source)
        if source_sha != record["source_sha256"]:
            raise RuntimeError(f"Source hash changed since inventory: {relative_path}")
        entry: dict[str, object] = {
            "source_relative_path": relative_path,
            "source_sha256": source_sha,
            "status": "failed",
        }
        try:
            target_dir = derived_root / source_sha
            derivative = target_dir / "derivative.pptx"
            if not derivative.is_file():
                with tempfile.TemporaryDirectory(prefix="medplat-office-") as tmp:
                    converted = convert(source, Path(tmp))
                    target_dir.mkdir(parents=True, exist_ok=True)
                    partial = target_dir / "derivative.pptx.partial"
                    shutil.copyfile(converted, partial)
                    partial.replace(derivative)
            derivative_sha = sha256_file(derivative)
            write_json_atomic(
                target_dir / "derivative.json",
                {
                    "source_relative_path": relative_path,
                    "source_sha256": source_sha,
                    "source_extension": source.suffix,
                    "derivative_file": "derivative.pptx",
                    "derivative_sha256": derivative_sha,
                    "tool": version,
                    "operation": "soffice --headless --convert-to pptx",
                },
            )
            result = extractor.extract(
                DiscoveredSource(
                    path=derivative,
                    relative_path=relative_path,
                    extension=".pptx",
                    size_bytes=derivative.stat().st_size,
                    sha256=source_sha,
                ),
                input_root=source_root,
                pdf_inspection=None,
                accepted_derivative=None,
                derivative_warnings=(
                    f"Extracted from a LibreOffice .pptx derivative (sha256 {derivative_sha}).",
                ),
            )
            entry.update(status=result.status.value, errors=list(result.errors))
            if result.status in {ExportStatus.EXPORTED, ExportStatus.EXPORTED_WITH_WARNINGS}:
                assert result.body is not None
                text_relative = str(Path(relative_path).with_suffix(".txt"))
                write_text_atomic(
                    text_root / text_relative,
                    render_export(
                        source_filename=source.name,
                        source_relative_path=relative_path,
                        source_extension=source.suffix,
                        source_sha256=source_sha,
                        document_type=result.document_type,
                        status=result.status,
                        extraction_tool=f"libreoffice-pptx-derivative+{result.extraction_tool}",
                        exported_at=datetime.now(timezone.utc),
                        body=result.body,
                    ),
                )
                entry.update(
                    derivative_sha256=derivative_sha,
                    output_relative_path=text_relative,
                    text_character_count=result.body.text_character_count,
                    page_or_slide_count=result.body.page_or_slide_count,
                )
        except Exception as exc:  # keep converting unrelated files
            entry["errors"] = [f"{type(exc).__name__}: {exc}"]
        manifest.append(entry)
        print(
            f"{entry['status']:24} {entry.get('text_character_count', '-')!s:>7}c  {relative_path}"
        )
    write_json_atomic(text_root / "derived-export-manifest.json", {"entries": manifest})
    return 0 if all(e["status"] != "failed" for e in manifest) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", required=True, help="year id from library.toml")
    sys.exit(main(get_year(parser.parse_args().year)))
