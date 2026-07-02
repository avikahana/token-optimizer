"""Path safety helpers for project-local Token Optimizer operations."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


class UnsafePathError(ValueError):
    """Raised when a path escapes the selected project boundary."""


def atomic_write_text(path: Path, contents: str) -> None:
    """Write text via a same-directory temp file and atomic rename."""

    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(contents)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def resolve_project_path(project_path: Path | str | None = None) -> Path:
    """Resolve the project path used as the trust boundary."""

    return Path(project_path or Path.cwd()).expanduser().resolve()


def resolve_under_project(project: Path, relative_path: Path | str) -> Path:
    """Resolve a relative path and ensure it stays inside the project."""

    raw = Path(relative_path)
    if raw.is_absolute():
        raise UnsafePathError(f"path must be project-relative: {raw}")
    candidate = (project / raw).resolve(strict=False)
    try:
        candidate.relative_to(project)
    except ValueError as exc:
        raise UnsafePathError(f"path escapes project: {raw}") from exc
    return candidate


def resolve_owned_path(project: Path, relative_path: Path | str, label: str) -> Path:
    """Resolve an owned project path without following symlinked components."""

    raw = Path(relative_path)
    if raw.is_absolute():
        raise UnsafePathError(f"path must be project-relative: {raw}")
    unresolved = project / raw
    reject_symlink_components(project, raw, label)
    return resolve_under_project(project, raw)


def reject_symlink(path: Path, label: str) -> None:
    """Reject an existing symlink path."""

    if path.is_symlink():
        raise UnsafePathError(f"{label} path is a symlink: {path}")


def reject_symlink_components(project: Path, relative_path: Path | str, label: str) -> None:
    """Reject existing symlinks in a project-relative path's component chain."""

    current = project
    for part in Path(relative_path).parts:
        if part in ("", "."):
            continue
        current = current / part
        reject_symlink(current, label)


def reject_symlink_components_for_path(path: Path | str, label: str) -> None:
    """Reject existing symlinks in an explicit filesystem path's component chain."""

    raw = Path(path)
    if raw.is_absolute():
        current = Path(raw.anchor)
        parts = raw.parts[1:]
    else:
        current = Path.cwd()
        parts = raw.parts
    for part in parts:
        if part in ("", "."):
            continue
        current = current / part
        reject_symlink(current, label)
