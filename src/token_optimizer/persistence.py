"""Project-local config, data, and purge planning."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from token_optimizer import __version__
from token_optimizer.doctor import CONFIG_RELATIVE_PATH, DATA_RELATIVE_PATH
from token_optimizer.hooks import (
    HookFileChangePlan,
    apply_hook_file_change,
    plan_hook_uninstall_file_change,
)
from token_optimizer.paths import UnsafePathError, reject_symlink, resolve_owned_path, resolve_project_path


DEFAULT_DASHBOARD_RELATIVE_PATH = DATA_RELATIVE_PATH / "audit-dashboard.html"


class PurgeApplyError(OSError):
    """Raised when purge fails after completing zero or more removal steps."""

    def __init__(self, message: str, completed_steps: tuple[str, ...], original: OSError) -> None:
        super().__init__(message)
        self.completed_steps = completed_steps
        self.original = original


@dataclass(frozen=True)
class ConfigInitPlan:
    """Planned project-local config/data initialization."""

    project_path: Path
    config_path: Path
    data_path: Path
    action: str
    before: str | None
    after: str
    would_create_config: bool
    would_update_config: bool
    would_create_data_dir: bool
    unchanged: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class PurgePlan:
    """Planned removal of Token Optimizer-owned project-local state."""

    project_path: Path
    config_path: Path
    data_path: Path
    hooks_plan: HookFileChangePlan
    would_remove_config: bool
    would_remove_data_dir: bool
    would_update_hooks: bool
    would_remove_hooks: bool
    unchanged: bool
    warnings: tuple[str, ...]


def plan_config_init(project_path: str | Path | None = None) -> ConfigInitPlan:
    """Plan config/data initialization without writing files."""

    project = resolve_project_path(project_path)
    config_path, data_path = _owned_config_paths(project)
    _validate_config_paths(config_path, data_path)
    before = _read_config(config_path)
    after = _render_default_config()
    would_create_data_dir = not data_path.exists()
    if before is None:
        action = "create"
    elif before == after:
        action = "unchanged"
    else:
        action = "update"
    return ConfigInitPlan(
        project_path=project,
        config_path=config_path,
        data_path=data_path,
        action=action,
        before=before,
        after=after,
        would_create_config=before is None,
        would_update_config=before is not None and before != after,
        would_create_data_dir=would_create_data_dir,
        unchanged=action == "unchanged" and not would_create_data_dir,
        warnings=tuple(_config_warnings(config_path, data_path)),
    )


def apply_config_init(plan: ConfigInitPlan) -> ConfigInitPlan:
    """Apply a previously planned config/data initialization."""

    config_path, data_path = _owned_config_paths(plan.project_path)
    if plan.config_path != config_path or plan.data_path != data_path:
        raise UnsafePathError("config/data paths do not match project-owned paths")
    _validate_config_paths(config_path, data_path)
    if _read_config(config_path) != plan.before:
        raise ValueError("config file changed since plan was created")
    data_existed = data_path.exists()
    if data_existed == plan.would_create_data_dir:
        raise ValueError("data directory state changed since plan was created")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.mkdir(parents=True, exist_ok=True)
    config_path, data_path = _owned_config_paths(plan.project_path)
    if plan.config_path != config_path or plan.data_path != data_path:
        raise UnsafePathError("config/data paths do not match project-owned paths")
    _validate_config_paths(config_path, data_path)
    config_path.write_text(plan.after, encoding="utf-8")
    return plan


def format_config_init_plan(plan: ConfigInitPlan, *, dry_run: bool = True) -> str:
    """Render a config init plan for humans."""

    lines = [
        "Token Optimizer Config Init Plan",
        f"Project: {plan.project_path}",
        f"Config path: {plan.config_path}",
        f"Data path: {plan.data_path}",
        f"Dry run: {_yes_no(dry_run)}",
        f"Action: {plan.action}",
        "",
        f"Would create config: {_yes_no(plan.would_create_config)}",
        f"Would update config: {_yes_no(plan.would_update_config)}",
        f"Would create data dir: {_yes_no(plan.would_create_data_dir)}",
        f"Unchanged: {_yes_no(plan.unchanged)}",
        "",
        "Planned config:",
        plan.after,
    ]
    _append_warnings(lines, plan.warnings)
    return "\n".join(lines)


def config_init_plan_to_json(plan: ConfigInitPlan, *, dry_run: bool = True) -> str:
    """Render a config init plan as stable JSON."""

    payload = {
        "project": str(plan.project_path),
        "configPath": str(plan.config_path),
        "dataPath": str(plan.data_path),
        "dryRun": dry_run,
        "action": plan.action,
        "wouldCreateConfig": plan.would_create_config,
        "wouldUpdateConfig": plan.would_update_config,
        "wouldCreateDataDir": plan.would_create_data_dir,
        "unchanged": plan.unchanged,
        "before": plan.before,
        "after": plan.after,
        "warnings": list(plan.warnings),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def plan_purge(project_path: str | Path | None = None) -> PurgePlan:
    """Plan removal of Token Optimizer-owned state without writing files."""

    project = resolve_project_path(project_path)
    config_path, data_path = _owned_config_paths(project)
    _validate_config_paths(config_path, data_path)
    hooks_plan = plan_hook_uninstall_file_change(project)
    would_remove_config = config_path.exists()
    would_remove_data_dir = data_path.exists()
    would_update_hooks = hooks_plan.would_update
    would_remove_hooks = hooks_plan.would_remove
    unchanged = not (
        would_remove_config
        or would_remove_data_dir
        or would_update_hooks
        or would_remove_hooks
    )
    return PurgePlan(
        project_path=project,
        config_path=config_path,
        data_path=data_path,
        hooks_plan=hooks_plan,
        would_remove_config=would_remove_config,
        would_remove_data_dir=would_remove_data_dir,
        would_update_hooks=would_update_hooks,
        would_remove_hooks=would_remove_hooks,
        unchanged=unchanged,
        warnings=tuple(_purge_warnings(config_path, data_path)),
    )


def apply_purge(plan: PurgePlan) -> PurgePlan:
    """Apply a previously planned purge."""

    config_path, data_path = _owned_config_paths(plan.project_path)
    if plan.config_path != config_path or plan.data_path != data_path:
        raise UnsafePathError("purge paths do not match project-owned paths")
    _validate_config_paths(config_path, data_path)
    if config_path.exists() != plan.would_remove_config:
        raise ValueError("config file state changed since purge plan was created")
    if data_path.exists() != plan.would_remove_data_dir:
        raise ValueError("data directory state changed since purge plan was created")
    completed_steps: list[str] = []
    try:
        apply_hook_file_change(plan.hooks_plan)
        completed_steps.append("hooks")
        if config_path.exists():
            config_path, data_path = _owned_config_paths(plan.project_path)
            _validate_config_paths(config_path, data_path)
            if not config_path.is_file():
                raise UnsafePathError(f"config path exists but is not a file: {config_path}")
            config_path.unlink()
            completed_steps.append("config")
        if data_path.exists():
            config_path, data_path = _owned_config_paths(plan.project_path)
            _validate_config_paths(config_path, data_path)
            if not data_path.is_dir():
                raise UnsafePathError(f"data path exists but is not a directory: {data_path}")
            shutil.rmtree(data_path)
            completed_steps.append("data")
    except OSError as exc:
        completed = ", ".join(completed_steps) if completed_steps else "none"
        raise PurgeApplyError(
            f"{exc}; completed purge steps before failure: {completed}",
            tuple(completed_steps),
            exc,
        ) from exc
    return plan


def format_purge_plan(plan: PurgePlan, *, dry_run: bool = True) -> str:
    """Render a purge plan for humans."""

    lines = [
        "Token Optimizer Purge Plan",
        f"Project: {plan.project_path}",
        f"Config path: {plan.config_path}",
        f"Data path: {plan.data_path}",
        f"Hooks path: {plan.hooks_plan.hooks_path}",
        f"Dry run: {_yes_no(dry_run)}",
        "",
        f"Would remove config: {_yes_no(plan.would_remove_config)}",
        f"Would remove data dir: {_yes_no(plan.would_remove_data_dir)}",
        f"Would update hooks: {_yes_no(plan.would_update_hooks)}",
        f"Would remove hooks file: {_yes_no(plan.would_remove_hooks)}",
        f"Unchanged: {_yes_no(plan.unchanged)}",
    ]
    _append_warnings(lines, plan.warnings)
    return "\n".join(lines)


def purge_plan_to_json(plan: PurgePlan, *, dry_run: bool = True) -> str:
    """Render a purge plan as stable JSON."""

    payload = {
        "project": str(plan.project_path),
        "configPath": str(plan.config_path),
        "dataPath": str(plan.data_path),
        "hooksPath": str(plan.hooks_plan.hooks_path),
        "dryRun": dry_run,
        "wouldRemoveConfig": plan.would_remove_config,
        "wouldRemoveDataDir": plan.would_remove_data_dir,
        "wouldUpdateHooks": plan.would_update_hooks,
        "wouldRemoveHooksFile": plan.would_remove_hooks,
        "unchanged": plan.unchanged,
        "warnings": list(plan.warnings),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _render_default_config() -> str:
    payload: dict[str, Any] = {
        "version": __version__,
        "createdBy": "token-optimizer",
        "defaults": {
            "dashboardPath": DEFAULT_DASHBOARD_RELATIVE_PATH.as_posix(),
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _validate_config_paths(config_path: Path, data_path: Path) -> None:
    reject_symlink(config_path, "Config")
    reject_symlink(data_path, "Data")
    if config_path.exists() and not config_path.is_file():
        raise UnsafePathError(f"config path exists but is not a file: {config_path}")
    if data_path.exists() and not data_path.is_dir():
        raise UnsafePathError(f"data path exists but is not a directory: {data_path}")


def _owned_config_paths(project: Path) -> tuple[Path, Path]:
    config_path = resolve_owned_path(project, CONFIG_RELATIVE_PATH, "Config")
    data_path = resolve_owned_path(project, DATA_RELATIVE_PATH, "Data")
    return config_path, data_path


def _read_config(config_path: Path) -> str | None:
    if not config_path.exists():
        return None
    try:
        return config_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise UnsafePathError("config file is not UTF-8") from error


def _config_warnings(config_path: Path, data_path: Path) -> list[str]:
    warnings: list[str] = []
    if config_path.exists():
        warnings.append("Existing Token Optimizer config will be updated if --yes is used.")
    if data_path.exists():
        warnings.append("Existing Token Optimizer data directory will be reused.")
    return warnings


def _purge_warnings(config_path: Path, data_path: Path) -> list[str]:
    warnings: list[str] = []
    if data_path.exists():
        warnings.append("Purge removes the Token Optimizer-owned data directory recursively.")
    if config_path.exists():
        warnings.append("Purge removes the Token Optimizer project-local config file.")
    return warnings


def _append_warnings(lines: list[str], warnings: tuple[str, ...]) -> None:
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("")
        lines.append("Warnings: none")


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
