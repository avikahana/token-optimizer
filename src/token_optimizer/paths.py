"""Path safety helpers for project-local Token Optimizer operations."""

from __future__ import annotations

from pathlib import Path


class UnsafePathError(ValueError):
    """Raised when a path escapes the selected project boundary."""


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
    """Resolve an owned project path without following a symlinked leaf."""

    raw = Path(relative_path)
    if raw.is_absolute():
        raise UnsafePathError(f"path must be project-relative: {raw}")
    unresolved = project / raw
    reject_symlink(unresolved, label)
    return resolve_under_project(project, raw)


def reject_symlink(path: Path, label: str) -> None:
    """Reject an existing symlink path."""

    if path.is_symlink():
        raise UnsafePathError(f"{label} path is a symlink: {path}")
