"""Convert Office sources to citable derivatives and export their text.

Legacy slides (.ppt, .ppsx) become .pptx, exported with the Docling Office route (one
`===== SLIDE n =====` per slide). Word documents (.doc, .docx) become PDF, exported with the
standard local PDF route: a Word export has no pages, so without a paginated derivative its
content could not be cited. Pages of a Word document are those of the LibreOffice PDF rendering.

The read-only source is copied to a temporary directory and converted there with LibreOffice
headless; the source tree is never written. Sources are discovered directly in library/<year>, so
this can run before the inventory exists. Each derivative is content-addressed under
data/<year>/office/<source-sha256>/ with a provenance record. Text exports are written in the
standard mirrored format under data/<year>/text-office/, keeping the original source-relative
path, extension, and SHA-256 in the header; the inventory prefers them over the direct export.
Usage: python scripts/convert_office.py --year dcem1
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ingestion.config import DoclingSettings
from ingestion.hashing import sha256_file
from ingestion.library import Year, docling_artifacts_path, get_year
from ingestion.output import write_json_atomic, write_text_atomic
from ingestion.text_tree.discovery import DiscoveredSource
from ingestion.text_tree.extraction import LocalTextExtractor, inspect_pdf_technically
from ingestion.text_tree.models import ExportStatus
from ingestion.text_tree.rendering import render_export

# Source extension -> format LibreOffice converts it to.
OFFICE_TARGETS = {".ppt": "pptx", ".ppsx": "pptx", ".doc": "pdf", ".docx": "pdf"}


def libreoffice_version() -> str:
    result = subprocess.run(["soffice", "--version"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def convert(source: Path, workdir: Path, target: str) -> Path:
    staged = workdir / f"source{source.suffix.lower()}"
    shutil.copyfile(source, staged)
    subprocess.run(
        [
            "soffice",
            "--headless",
            f"-env:UserInstallation=file://{workdir / 'profile'}",
            "--convert-to",
            target,
            "--outdir",
            str(workdir / "out"),
            str(staged),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    converted = workdir / "out" / f"source.{target}"
    if not converted.is_file():
        raise RuntimeError(f"LibreOffice produced no .{target} output.")
    return converted


def main(year: Year) -> int:
    source_root, derived_root, text_root = year.source, year.office, year.text_office
    sources = sorted(
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*")
        if path.is_file() and path.suffix.lower() in OFFICE_TARGETS
    )
    version = libreoffice_version()
    settings = DoclingSettings.from_sources()
    if settings.artifacts_path is None:
        settings = DoclingSettings.from_sources(cli_artifacts_path=docling_artifacts_path())
    extractor = LocalTextExtractor(settings)
    manifest = []
    for relative_path in sources:
        source = source_root / relative_path
        source_sha = sha256_file(source)
        target = OFFICE_TARGETS[source.suffix.lower()]
        entry: dict[str, object] = {
            "source_relative_path": relative_path,
            "source_sha256": source_sha,
            "status": "failed",
        }
        try:
            target_dir = derived_root / source_sha
            derivative = target_dir / f"derivative.{target}"
            if not derivative.is_file():
                with tempfile.TemporaryDirectory(prefix="medplat-office-") as tmp:
                    converted = convert(source, Path(tmp), target)
                    target_dir.mkdir(parents=True, exist_ok=True)
                    partial = target_dir / f"derivative.{target}.partial"
                    shutil.copyfile(converted, partial)
                    partial.replace(derivative)
            derivative_sha = sha256_file(derivative)
            write_json_atomic(
                target_dir / "derivative.json",
                {
                    "source_relative_path": relative_path,
                    "source_sha256": source_sha,
                    "source_extension": source.suffix,
                    "derivative_file": derivative.name,
                    "derivative_sha256": derivative_sha,
                    "tool": version,
                    "operation": f"soffice --headless --convert-to {target}",
                },
            )
            discovered = DiscoveredSource(
                path=derivative,
                relative_path=relative_path,
                extension=f".{target}",
                size_bytes=derivative.stat().st_size,
                sha256=source_sha,
            )
            result = extractor.extract(
                discovered,
                input_root=source_root,
                pdf_inspection=(
                    inspect_pdf_technically(discovered, source_root) if target == "pdf" else None
                ),
                accepted_derivative=None,
                derivative_warnings=(
                    f"Extracted from a LibreOffice .{target} derivative (sha256 {derivative_sha}).",
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
                        extraction_tool=(
                            f"libreoffice-{target}-derivative+{result.extraction_tool}"
                        ),
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
