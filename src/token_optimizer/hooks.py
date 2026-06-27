"""Dry-run hook planning for Token Optimizer."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from token_optimizer.doctor import HOOKS_RELATIVE_PATH, MANAGED_MARKER
from token_optimizer.paths import UnsafePathError, resolve_owned_path, resolve_project_path

SUPPORTED_PROFILES = ("quiet",)
INACTIVE_PLACEHOLDER_HOOK_MODE = "inactive-placeholder-v1"
MANAGED_COMMAND = (
    "token-optimizer summarize --hook stop "
    f"--hook-mode {INACTIVE_PLACEHOLDER_HOOK_MODE}"
)
LEGACY_MANAGED_COMMAND = "token-optimizer summarize --hook stop"
EXPERIMENTAL_HOOK_WARNING = (
    "Stop hook installation is experimental and inactive in 0.1.0; "
    "use --experimental with --yes only after reviewing the dry-run plan."
)


@dataclass(frozen=True)
class HookPlan:
    project_path: Path
    hooks_path: Path
    profile: str
    dry_run: bool
    experimental: bool
    block: dict[str, Any]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class HookFileChangePlan:
    project_path: Path
    hooks_path: Path
    operation: str
    action: str
    experimental: bool
    before: str | None
    after: str | None
    would_create: bool
    would_update: bool
    would_remove: bool
    unchanged: bool
    warnings: tuple[str, ...]


class HookConfigError(ValueError):
    """Raised when an in-memory hooks document cannot be safely handled."""


def build_install_plan(
    project_path: Path | str | None = None,
    *,
    profile: str = "quiet",
    dry_run: bool = True,
    experimental: bool = False,
) -> HookPlan:
    """Build a project-local hook install plan without writing files."""

    if profile not in SUPPORTED_PROFILES:
        supported = ", ".join(SUPPORTED_PROFILES)
        raise ValueError(f"unsupported profile {profile!r}; supported profiles: {supported}")
    project = resolve_project_path(project_path)
    hooks_path = _owned_hooks_path(project)
    if hooks_path.exists() and not hooks_path.is_file():
        raise UnsafePathError(f"hooks path exists but is not a file: {hooks_path}")
    block = _quiet_hook_block()
    warnings = tuple(_warnings(hooks_path, experimental=experimental))
    return HookPlan(
        project_path=project,
        hooks_path=hooks_path,
        profile=profile,
        dry_run=dry_run,
        experimental=experimental,
        block=block,
        warnings=warnings,
    )


def format_plan(plan: HookPlan) -> str:
    """Render a hook plan for humans."""

    lines = [
        "Token Optimizer Hook Install Plan",
        f"Project: {plan.project_path}",
        f"Hooks path: {plan.hooks_path}",
        f"Profile: {plan.profile}",
        f"Dry run: {'yes' if plan.dry_run else 'no'}",
        f"Experimental: {_yes_no(plan.experimental)}",
        "",
        "Planned managed block:",
        json.dumps(plan.block, indent=2, sort_keys=True),
    ]
    if plan.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in plan.warnings)
    else:
        lines.append("")
        lines.append("Warnings: none")
    return "\n".join(lines)


def plan_to_json(plan: HookPlan) -> str:
    """Render a hook plan as JSON."""

    payload = {
        "project": str(plan.project_path),
        "hooksPath": str(plan.hooks_path),
        "profile": plan.profile,
        "dryRun": plan.dry_run,
        "experimental": plan.experimental,
        "managedMarker": MANAGED_MARKER,
        "managedBlock": plan.block,
        "warnings": list(plan.warnings),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def format_file_change_plan(plan: HookFileChangePlan, *, dry_run: bool = True) -> str:
    """Render a hook file-change plan for humans."""

    lines = [
        f"Token Optimizer Hook {plan.operation.title()} Plan",
        f"Project: {plan.project_path}",
        f"Hooks path: {plan.hooks_path}",
        "Dry run: " + _yes_no(dry_run),
        "Experimental: " + _yes_no(plan.experimental),
        f"Action: {plan.action}",
        "",
        "Would create: " + _yes_no(plan.would_create),
        "Would update: " + _yes_no(plan.would_update),
        "Would remove: " + _yes_no(plan.would_remove),
        "Unchanged: " + _yes_no(plan.unchanged),
    ]
    if plan.after is not None:
        lines.extend(["", "Planned hooks file:", plan.after])
    elif plan.would_remove:
        lines.extend(["", "Planned hooks file: remove"])
    if plan.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in plan.warnings)
    else:
        lines.append("")
        lines.append("Warnings: none")
    return "\n".join(lines)


def file_change_plan_to_json(plan: HookFileChangePlan, *, dry_run: bool = True) -> str:
    """Render a hook file-change plan as stable JSON."""

    payload = {
        "project": str(plan.project_path),
        "hooksPath": str(plan.hooks_path),
        "operation": plan.operation,
        "action": plan.action,
        "dryRun": dry_run,
        "experimental": plan.experimental,
        "managedMarker": MANAGED_MARKER,
        "wouldCreate": plan.would_create,
        "wouldUpdate": plan.would_update,
        "wouldRemove": plan.would_remove,
        "unchanged": plan.unchanged,
        "before": plan.before,
        "after": plan.after,
        "warnings": list(plan.warnings),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def apply_hook_file_change(plan: HookFileChangePlan) -> HookFileChangePlan:
    """Apply a previously planned project-local hook file change."""

    hooks_path = _owned_hooks_path(plan.project_path)
    if plan.hooks_path != hooks_path:
        raise UnsafePathError(f"hooks path does not match project-owned path: {plan.hooks_path}")
    if plan.operation == "install" and not plan.experimental:
        raise HookConfigError("hook install apply requires experimental consent")
    before = _read_existing_hooks(hooks_path)
    if before != plan.before:
        raise HookConfigError("hooks file changed since plan was created")
    if plan.action in ("create", "update"):
        if plan.after is None:
            raise HookConfigError(f"{plan.action} plan is missing output")
        if hooks_path.exists() and not hooks_path.is_file():
            raise UnsafePathError(f"hooks path exists but is not a file: {hooks_path}")
        hooks_path.parent.mkdir(parents=True, exist_ok=True)
        hooks_path.write_text(plan.after, encoding="utf-8")
    elif plan.action == "remove":
        if hooks_path.exists():
            if not hooks_path.is_file():
                raise UnsafePathError(f"hooks path exists but is not a file: {hooks_path}")
            hooks_path.unlink()
    elif plan.action == "unchanged":
        return plan
    else:
        raise HookConfigError(f"unsupported hook file action: {plan.action}")
    return plan


def plan_hook_install_file_change(
    project_path: Path | str | None = None,
    *,
    experimental: bool = False,
) -> HookFileChangePlan:
    """Plan a project-local hooks install file change without writing it."""

    project, hooks_path = _resolve_hooks_path(project_path)
    before = _read_existing_hooks(hooks_path)
    existing = parse_hooks_json(before) if before is not None else None
    after = render_hooks_json(merge_managed_block(existing))
    if before is None:
        action = "create"
    elif before == after:
        action = "unchanged"
    else:
        action = "update"
    return _file_change_plan(
        project_path=project,
        hooks_path=hooks_path,
        operation="install",
        action=action,
        experimental=experimental,
        before=before,
        after=after,
        warnings=tuple(_warnings(hooks_path, experimental=experimental)),
    )


def plan_hook_uninstall_file_change(project_path: Path | str | None = None) -> HookFileChangePlan:
    """Plan a project-local hooks uninstall file change without writing it."""

    project, hooks_path = _resolve_hooks_path(project_path)
    before = _read_existing_hooks(hooks_path)
    if before is None:
        return _file_change_plan(
            project_path=project,
            hooks_path=hooks_path,
            operation="uninstall",
            action="unchanged",
            experimental=False,
            before=None,
            after=None,
            warnings=("No hooks file found; nothing to uninstall.",),
        )
    existing = parse_hooks_json(before)
    after_document = remove_managed_blocks(existing)
    if after_document == existing:
        action = "unchanged"
        after = before
    elif not after_document:
        action = "remove"
        after = None
    else:
        action = "update"
        after = render_hooks_json(after_document)
    return _file_change_plan(
        project_path=project,
        hooks_path=hooks_path,
        operation="uninstall",
        action=action,
        experimental=False,
        before=before,
        after=after,
        warnings=(),
    )


def parse_hooks_json(contents: str) -> dict[str, Any]:
    """Parse a hooks JSON document into an object for in-memory planning."""

    try:
        parsed = json.loads(contents)
    except json.JSONDecodeError as error:
        raise HookConfigError(f"hooks JSON is invalid: {error.msg}") from error
    if not isinstance(parsed, dict):
        raise HookConfigError("hooks JSON must be an object")
    return parsed


def render_hooks_json(document: dict[str, Any]) -> str:
    """Render a hooks document with stable formatting."""

    return json.dumps(document, indent=2, sort_keys=True)


def merge_managed_block(
    existing: dict[str, Any] | None,
    managed_block: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge the Token Optimizer block into an in-memory hooks document."""

    document = _copy_hooks_document(existing)
    block = copy.deepcopy(managed_block if managed_block is not None else _quiet_hook_block())
    metadata = document.get("_tokenOptimizer")
    if metadata is not None and not _is_managed_metadata(metadata):
        raise HookConfigError("existing hooks document has foreign _tokenOptimizer metadata")
    document = remove_managed_blocks(document)
    document["_tokenOptimizer"] = block["_tokenOptimizer"]
    for event, entries in block.items():
        if event == "_tokenOptimizer":
            continue
        if not isinstance(entries, list):
            raise HookConfigError(f"managed hook event must be a list: {event}")
        current_entries = document.setdefault(event, [])
        if not isinstance(current_entries, list):
            raise HookConfigError(f"existing hook event must be a list: {event}")
        current_entries.extend(copy.deepcopy(entries))
    return document


def remove_managed_blocks(existing: dict[str, Any] | None) -> dict[str, Any]:
    """Remove Token Optimizer-managed blocks from an in-memory hooks document."""

    document = _copy_hooks_document(existing)
    metadata = document.get("_tokenOptimizer")
    if not _is_managed_metadata(metadata):
        return document
    document.pop("_tokenOptimizer", None)
    for event in tuple(document.keys()):
        entries = document[event]
        if not isinstance(entries, list):
            continue
        remaining = [entry for entry in entries if not _is_managed_entry(entry)]
        if remaining:
            document[event] = remaining
        else:
            document.pop(event)
    return document


def _quiet_hook_block() -> dict[str, Any]:
    return {
        "_tokenOptimizer": {
            "marker": MANAGED_MARKER,
            "profile": "quiet",
            "feature": "experimental-stop-hook",
            "behavior": INACTIVE_PLACEHOLDER_HOOK_MODE,
            "requiresFreshConsentForActiveBehavior": True,
            "description": (
                "Managed by Token Optimizer. Experimental inactive Stop hook; "
                "remove with uninstall."
            ),
        },
        "Stop": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": MANAGED_COMMAND,
                        "timeout": 30,
                    }
                ],
            }
        ],
    }


def _warnings(hooks_path: Path, *, experimental: bool = False) -> list[str]:
    warnings: list[str] = []
    if not experimental:
        warnings.append(EXPERIMENTAL_HOOK_WARNING)
    if hooks_path.exists():
        try:
            contents = hooks_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            warnings.append("Existing hooks file is not UTF-8; install must not overwrite it.")
        else:
            if MANAGED_MARKER in contents:
                warnings.append("Existing Token Optimizer managed marker found.")
            else:
                warnings.append("Existing hooks file found; install must merge without overwriting.")
    return warnings


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _resolve_hooks_path(project_path: Path | str | None) -> tuple[Path, Path]:
    project = resolve_project_path(project_path)
    hooks_path = _owned_hooks_path(project)
    if hooks_path.exists() and not hooks_path.is_file():
        raise UnsafePathError(f"hooks path exists but is not a file: {hooks_path}")
    return project, hooks_path


def _owned_hooks_path(project: Path) -> Path:
    return resolve_owned_path(project, HOOKS_RELATIVE_PATH, "Hooks")


def _read_existing_hooks(hooks_path: Path) -> str | None:
    if not hooks_path.exists():
        return None
    try:
        return hooks_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise HookConfigError("hooks file is not UTF-8") from error


def _file_change_plan(
    *,
    project_path: Path,
    hooks_path: Path,
    operation: str,
    action: str,
    experimental: bool,
    before: str | None,
    after: str | None,
    warnings: tuple[str, ...],
) -> HookFileChangePlan:
    return HookFileChangePlan(
        project_path=project_path,
        hooks_path=hooks_path,
        operation=operation,
        action=action,
        experimental=experimental,
        before=before,
        after=after,
        would_create=action == "create",
        would_update=action == "update",
        would_remove=action == "remove",
        unchanged=action == "unchanged",
        warnings=warnings,
    )


def _copy_hooks_document(existing: dict[str, Any] | None) -> dict[str, Any]:
    if existing is None:
        return {}
    if not isinstance(existing, dict):
        raise HookConfigError("hooks document must be an object")
    return copy.deepcopy(existing)


def _is_managed_metadata(value: Any) -> bool:
    return isinstance(value, dict) and value.get("marker") == MANAGED_MARKER


def _is_managed_entry(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    hooks = entry.get("hooks")
    if not isinstance(hooks, list):
        return False
    return any(_is_managed_command(hook) for hook in hooks)


def _is_managed_command(hook: Any) -> bool:
    return isinstance(hook, dict) and hook.get("command") in {
        MANAGED_COMMAND,
        LEGACY_MANAGED_COMMAND,
    }
