"""Read-only deterministic source discovery and mirrored output planning."""

from __future__ import annotations

import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath

from ingestion.hashing import sha256_file
from ingestion.text_tree.models import SUPPORTED_TEXT_EXPORT_EXTENSIONS


def _path_key(value: str) -> bytes:
    return value.encode("utf-8", errors="surrogateescape")


@dataclass(frozen=True)
class DiscoveredSource:
    """One regular source file captured in a read-only snapshot."""

    path: Path
    relative_path: str
    extension: str
    size_bytes: int
    sha256: str | None
    error: str | None = None


@dataclass(frozen=True)
class SourceSnapshot:
    """Complete file and directory identity for an input tree."""

    directories: tuple[str, ...]
    files: tuple[DiscoveredSource, ...]


@dataclass(frozen=True)
class OutputPlan:
    """Collision-safe output mapping for supported sources."""

    output_by_source: dict[str, str]
    collisions: dict[str, tuple[str, ...]]


def _walk_directory(root: Path, current: Path, directories: list[str], files: list[Path]) -> None:
    try:
        entries = sorted(
            os.scandir(current),
            key=lambda entry: _path_key(Path(entry.path).relative_to(root).as_posix()),
        )
    except OSError as exc:
        raise OSError(f"Cannot inspect source directory {current}: {exc}") from exc
    for entry in entries:
        path = Path(entry.path)
        relative = path.relative_to(root).as_posix()
        if entry.is_symlink():
            continue
        if entry.is_dir(follow_symlinks=False):
            directories.append(relative)
            _walk_directory(root, path, directories, files)
        elif entry.is_file(follow_symlinks=False):
            files.append(path)


def snapshot_source_tree(input_root: Path) -> SourceSnapshot:
    """Hash every regular file without following symlinks or mutating the source."""
    root = input_root.resolve()
    if not root.is_dir():
        raise ValueError(f"Input root is not a readable directory: {root}")
    directories: list[str] = []
    paths: list[Path] = []
    _walk_directory(root, root, directories, paths)
    sources: list[DiscoveredSource] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        try:
            size = path.stat().st_size
            digest = sha256_file(path)
            error = None
        except OSError as exc:
            size = 0
            digest = None
            error = f"{type(exc).__name__}: {exc}"
        sources.append(
            DiscoveredSource(
                path=path,
                relative_path=relative,
                extension=path.suffix.casefold(),
                size_bytes=size,
                sha256=digest,
                error=error,
            )
        )
    return SourceSnapshot(
        directories=tuple(sorted(directories, key=_path_key)),
        files=tuple(sorted(sources, key=lambda item: _path_key(item.relative_path))),
    )


def plan_output_paths(sources: tuple[DiscoveredSource, ...]) -> OutputPlan:
    """Map supported sources to mirrored paths without permitting overwrites."""
    groups: dict[str, list[DiscoveredSource]] = {}
    for source in sources:
        if source.extension not in SUPPORTED_TEXT_EXPORT_EXTENSIONS:
            continue
        source_path = PurePosixPath(source.relative_path)
        proposed = source_path.with_suffix(".txt").as_posix()
        groups.setdefault(proposed, []).append(source)

    output_by_source: dict[str, str] = {}
    collisions: dict[str, tuple[str, ...]] = {}
    used: set[str] = set()
    for proposed in sorted(groups, key=_path_key):
        members = sorted(groups[proposed], key=lambda item: _path_key(item.relative_path))
        if len(members) == 1 and proposed not in used:
            output_by_source[members[0].relative_path] = proposed
            used.add(proposed)
            continue
        collisions[proposed] = tuple(item.relative_path for item in members)
        for member in members:
            original = PurePosixPath(member.relative_path)
            extension_label = member.extension.removeprefix(".") or "noext"
            candidate = original.with_name(f"{original.stem}__{extension_label}.txt").as_posix()
            if candidate in used:
                identity = member.sha256 or sha256(member.relative_path.encode("utf-8")).hexdigest()
                candidate = original.with_name(
                    f"{original.stem}__{extension_label}__{identity[:12]}.txt"
                ).as_posix()
            if candidate in used:
                raise ValueError(f"Could not resolve output collision for {member.relative_path}")
            output_by_source[member.relative_path] = candidate
            used.add(candidate)
    return OutputPlan(output_by_source=output_by_source, collisions=collisions)


def safe_output_path(output_root: Path, output_relative_path: str) -> Path:
    """Resolve a POSIX relative output while rejecting traversal and root escape."""
    relative = PurePosixPath(output_relative_path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("Output-relative path must stay below the configured output root.")
    root = output_root.resolve()
    candidate = root.joinpath(*relative.parts)
    if not candidate.resolve().is_relative_to(root):
        raise ValueError("Output path escaped the configured output root.")
    return candidate
