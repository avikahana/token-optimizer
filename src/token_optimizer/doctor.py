"""Read-only project inspection for Token Optimizer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from token_optimizer import __version__
from token_optimizer.paths import resolve_project_path

CONFIG_RELATIVE_PATH = Path(".codex/token-optimizer.json")
DATA_RELATIVE_PATH = Path(".codex/token-optimizer")
HOOKS_RELATIVE_PATH = Path(".codex/hooks.json")
MANAGED_MARKER = "TOKEN_OPTIMIZER_MANAGED"


@dataclass(frozen=True)
class PathStatus:
    label: str
    path: Path
    exists: bool
    is_symlink: bool


@dataclass(frozen=True)
class DoctorReport:
    version: str
    project_path: Path
    config: PathStatus
    data: PathStatus
    hooks: PathStatus
    managed_hooks_present: bool
    warnings: tuple[str, ...]


def build_report(project_path: Path | None = None) -> DoctorReport:
    """Build a read-only DoctorReport for the selected project path."""

    project = resolve_project_path(project_path)
    config = _path_status("Config", project / CONFIG_RELATIVE_PATH)
    data = _path_status("Data", project / DATA_RELATIVE_PATH)
    hooks = _path_status("Hooks", project / HOOKS_RELATIVE_PATH)
    managed_hooks_present = _has_managed_hooks(hooks.path) if hooks.exists else False
    warnings = tuple(_warnings(project, config, data, hooks))
    return DoctorReport(
        version=__version__,
        project_path=project,
        config=config,
        data=data,
        hooks=hooks,
        managed_hooks_present=managed_hooks_present,
        warnings=warnings,
    )


def format_report(report: DoctorReport) -> str:
    """Render a DoctorReport for humans."""

    lines = [
        "Token Optimizer Doctor",
        f"Version: {report.version}",
        f"Project: {report.project_path}",
        "",
        "Paths:",
        _format_path_status(report.config),
        _format_path_status(report.data),
        _format_path_status(report.hooks),
        "",
        f"Managed hooks present: {_yes_no(report.managed_hooks_present)}",
    ]
    if report.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in report.warnings)
    else:
        lines.append("")
        lines.append("Warnings: none")
    return "\n".join(lines)


def report_to_json(report: DoctorReport) -> str:
    """Render a DoctorReport as stable JSON for tools and plugin workflows."""

    payload = {
        "version": report.version,
        "project": str(report.project_path),
        "paths": {
            "config": _path_status_to_json(report.config),
            "data": _path_status_to_json(report.data),
            "hooks": _path_status_to_json(report.hooks),
        },
        "managedHooksPresent": report.managed_hooks_present,
        "managedMarker": MANAGED_MARKER,
        "warnings": list(report.warnings),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _path_status(label: str, path: Path) -> PathStatus:
    return PathStatus(
        label=label,
        path=path,
        exists=path.exists(),
        is_symlink=path.is_symlink(),
    )


def _format_path_status(status: PathStatus) -> str:
    state = "exists" if status.exists else "missing"
    symlink = ", symlink" if status.is_symlink else ""
    return f"- {status.label}: {status.path} ({state}{symlink})"


def _path_status_to_json(status: PathStatus) -> dict[str, object]:
    return {
        "exists": status.exists,
        "label": status.label,
        "path": str(status.path),
        "symlink": status.is_symlink,
    }


def _has_managed_hooks(path: Path) -> bool:
    try:
        return MANAGED_MARKER in path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False


def _warnings(
    project: Path,
    config: PathStatus,
    data: PathStatus,
    hooks: PathStatus,
) -> list[str]:
    warnings: list[str] = []
    if project == Path.home():
        warnings.append("Project path is the home directory; use a project-specific directory.")
    for status in (config, data, hooks):
        if status.is_symlink:
            warnings.append(f"{status.label} path is a symlink: {status.path}")
    if hooks.exists and not hooks.path.is_file():
        warnings.append(f"Hooks path exists but is not a file: {hooks.path}")
    if data.exists and not data.path.is_dir():
        warnings.append(f"Data path exists but is not a directory: {data.path}")
    return warnings


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
