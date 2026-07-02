"""Static context-hygiene audit helpers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from token_optimizer.doctor import DATA_RELATIVE_PATH, MANAGED_MARKER
from token_optimizer.paths import reject_symlink, resolve_project_path


class AuditError(ValueError):
    """Raised when a project cannot be audited safely."""


@dataclass(frozen=True)
class FileMetric:
    """Cheap metadata for one scanned file."""

    path: Path
    relative_path: str
    byte_count: int
    line_count: int | None
    text: bool


@dataclass(frozen=True)
class AuditSignal:
    """One static context-hygiene signal."""

    code: str
    severity: str
    path: str
    message: str
    recommendation: str
    byte_count: int | None = None
    line_count: int | None = None


@dataclass(frozen=True)
class AuditReport:
    """Static context-hygiene report for a project."""

    project_path: Path
    scanned_files: int
    skipped_dirs: tuple[str, ...]
    score: int
    signals: tuple[AuditSignal, ...]
    outline_candidates: tuple[FileMetric, ...]


SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
}
GENERATED_DIR_NAMES = SKIP_DIR_NAMES - {".git"}
TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".log",
    ".md",
    ".markdown",
    ".out",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
SOURCE_SUFFIXES = {".py", ".js", ".ts", ".tsx"}
MARKDOWN_SUFFIXES = {".md", ".markdown"}
NOISY_SUFFIXES = {".log", ".out", ".err"}
GUIDANCE_NAMES = {"AGENTS.md", "CLAUDE.md", "README.md", "SKILL.md"}
GUIDANCE_PATH_PARTS = {".codex", ".codex-plugin", "skills"}

LARGE_MARKDOWN_LINES = 300
LARGE_MARKDOWN_BYTES = 20_000
LARGE_SOURCE_LINES = 500
LARGE_SOURCE_BYTES = 35_000
LARGE_TEXT_BYTES = 80_000
LARGE_GUIDANCE_LINES = 200
LARGE_GUIDANCE_BYTES = 15_000
NOISY_OUTPUT_BYTES = 8_000
SECURITY_CONTEXT_BYTES = 8_000


def build_audit(project_path: str | Path | None = None) -> AuditReport:
    """Build a read-only static audit report for a project."""

    if project_path is not None:
        reject_symlink(Path(project_path).expanduser(), "project")
    project = resolve_project_path(project_path)
    if not project.exists():
        raise AuditError(f"project does not exist: {project}")
    if not project.is_dir():
        raise AuditError(f"project is not a directory: {project}")

    metrics, skipped_dirs, generated_signals = _scan_project(project)
    signals = list(generated_signals)
    signals.extend(_file_signals(metrics))
    signals.extend(_guidance_signals(project, metrics))
    signals.extend(_token_optimizer_state_signals(project))
    signals.extend(_plugin_capability_signals(project, metrics))
    candidates = tuple(_outline_candidates(metrics))
    score = max(0, 100 - sum(_severity_cost(signal.severity) for signal in signals))
    return AuditReport(
        project_path=project,
        scanned_files=len(metrics),
        skipped_dirs=tuple(sorted(skipped_dirs)),
        score=score,
        signals=tuple(signals),
        outline_candidates=candidates,
    )


def format_audit(report: AuditReport) -> str:
    """Render a human-readable audit report."""

    lines = [
        "Token Optimizer Audit",
        f"Project: {report.project_path}",
        f"Score: {report.score}/100",
        f"Scanned files: {report.scanned_files}",
        f"Skipped directories: {', '.join(report.skipped_dirs) if report.skipped_dirs else 'none'}",
        "",
        "Signals:",
    ]
    if not report.signals:
        lines.append("- none")
    else:
        for signal in report.signals:
            detail = _signal_detail(signal)
            lines.append(f"- [{signal.severity}] {signal.message}{detail}")
            lines.append(f"  Path: {signal.path}")
            lines.append(f"  Suggestion: {signal.recommendation}")
    lines.append("")
    lines.append("Top outline candidates:")
    if not report.outline_candidates:
        lines.append("- none")
    else:
        for metric in report.outline_candidates:
            line_text = "unknown" if metric.line_count is None else str(metric.line_count)
            lines.append(
                f"- {metric.relative_path} ({line_text} lines, {metric.byte_count} bytes)"
            )
    return "\n".join(lines)


def audit_to_json(report: AuditReport) -> str:
    """Render a stable JSON audit report."""

    payload = {
        "project": str(report.project_path),
        "score": report.score,
        "scannedFiles": report.scanned_files,
        "skippedDirectories": list(report.skipped_dirs),
        "signals": [
            {
                "code": signal.code,
                "severity": signal.severity,
                "path": signal.path,
                "message": signal.message,
                "recommendation": signal.recommendation,
                "bytes": signal.byte_count,
                "lines": signal.line_count,
            }
            for signal in report.signals
        ],
        "outlineCandidates": [
            {
                "path": metric.relative_path,
                "bytes": metric.byte_count,
                "lines": metric.line_count,
            }
            for metric in report.outline_candidates
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _scan_project(project: Path) -> tuple[list[FileMetric], set[str], list[AuditSignal]]:
    metrics: list[FileMetric] = []
    skipped_dirs: set[str] = set()
    generated_signals: list[AuditSignal] = []
    for root, dirs, files in os.walk(project, followlinks=False):
        root_path = Path(root)
        kept_dirs = []
        for directory in dirs:
            directory_path = root_path / directory
            relative = _relative(project, directory_path)
            if directory_path.is_symlink():
                skipped_dirs.add(relative)
                continue
            if Path(relative) == DATA_RELATIVE_PATH:
                continue
            if directory in SKIP_DIR_NAMES:
                skipped_dirs.add(relative)
                if directory in GENERATED_DIR_NAMES:
                    generated_signals.append(
                        AuditSignal(
                            code="generated_directory",
                            severity="info",
                            path=relative,
                            message=f"generated/cache directory present: {relative}",
                            recommendation="Keep generated or cache directories out of agent context unless explicitly needed.",
                        )
                    )
                continue
            kept_dirs.append(directory)
        dirs[:] = kept_dirs
        for filename in files:
            path = root_path / filename
            if path.is_symlink() or not path.is_file():
                continue
            metrics.append(_file_metric(project, path))
    return metrics, skipped_dirs, generated_signals


def _file_metric(project: Path, path: Path) -> FileMetric:
    byte_count = path.stat().st_size
    relative = _relative(project, path)
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return FileMetric(path, relative, byte_count, None, text=False)
    if byte_count >= LARGE_TEXT_BYTES:
        # The byte count alone already trips the size thresholds; skip
        # reading the whole file end-to-end just to count its lines.
        return FileMetric(path, relative, byte_count, None, text=True)
    try:
        line_count = _count_text_lines(path)
    except UnicodeDecodeError:
        return FileMetric(path, relative, byte_count, None, text=False)
    return FileMetric(path, relative, byte_count, line_count, text=True)


def _file_signals(metrics: list[FileMetric]) -> list[AuditSignal]:
    signals: list[AuditSignal] = []
    for metric in metrics:
        suffix = metric.path.suffix.lower()
        name_lower = metric.path.name.lower()
        if suffix in MARKDOWN_SUFFIXES and _exceeds(
            metric, LARGE_MARKDOWN_LINES, LARGE_MARKDOWN_BYTES
        ):
            signals.append(
                _file_signal(
                    "large_markdown",
                    "warning",
                    metric,
                    "large Markdown/docs file",
                    f"Run `token-optimizer outline {metric.relative_path}` before rereading the full file.",
                )
            )
        elif suffix in SOURCE_SUFFIXES and _exceeds(
            metric, LARGE_SOURCE_LINES, LARGE_SOURCE_BYTES
        ):
            signals.append(
                _file_signal(
                    "large_source",
                    "warning",
                    metric,
                    "large source file",
                    f"Run `token-optimizer outline {metric.relative_path}` and inspect focused sections.",
                )
            )
        elif metric.text and metric.byte_count >= LARGE_TEXT_BYTES:
            signals.append(
                _file_signal(
                    "large_text",
                    "info",
                    metric,
                    "large text file",
                    "Summarize or inspect focused sections instead of reading the full file repeatedly.",
                )
            )
        if suffix in NOISY_SUFFIXES or _looks_like_output_artifact(name_lower):
            if metric.byte_count >= NOISY_OUTPUT_BYTES:
                signals.append(
                    _file_signal(
                        "noisy_output",
                        "warning",
                        metric,
                        "potentially noisy log or command-output artifact",
                        "Summarize output artifacts before adding them to long agent context.",
                    )
                )
        if _looks_security_related(metric.relative_path) and metric.byte_count >= SECURITY_CONTEXT_BYTES:
            signals.append(
                _file_signal(
                    "security_context",
                    "info",
                    metric,
                    "security-like content may be sensitive or verbose",
                    "Summarize security-like artifacts carefully and avoid broad raw sharing.",
                )
            )
    return signals


def _guidance_signals(project: Path, metrics: list[FileMetric]) -> list[AuditSignal]:
    signals: list[AuditSignal] = []
    guidance_paths = {metric.relative_path for metric in metrics if _is_guidance(metric)}
    if not ({"README.md", "AGENTS.md", "brain/START-HERE.md"} & guidance_paths):
        signals.append(
            AuditSignal(
                code="missing_guidance",
                severity="info",
                path=".",
                message="no obvious project guidance file found",
                recommendation="Add README.md, AGENTS.md, or brain/START-HERE.md to reduce rediscovery work.",
            )
        )
    for metric in metrics:
        if not _is_guidance(metric):
            continue
        if _exceeds(metric, LARGE_GUIDANCE_LINES, LARGE_GUIDANCE_BYTES):
            signals.append(
                _file_signal(
                    "large_guidance",
                    "warning",
                    metric,
                    "large instruction/guidance file",
                    "Keep always-consulted guidance concise or split detailed references into targeted files.",
                )
            )
    if _has_project_codex_config(project / ".codex"):
        signals.append(
            AuditSignal(
                code="codex_config_present",
                severity="info",
                path=".codex",
                message="project-local Codex configuration directory present",
                recommendation="Review project-local Codex config and hooks when context behavior is surprising.",
            )
        )
    return signals


def _has_project_codex_config(codex_dir: Path) -> bool:
    if not codex_dir.is_dir():
        return False
    for child in codex_dir.iterdir():
        if child.name != DATA_RELATIVE_PATH.name:
            return True
    return False


def _token_optimizer_state_signals(project: Path) -> list[AuditSignal]:
    hooks = project / ".codex/hooks.json"
    if not hooks.exists() or hooks.is_symlink() or not hooks.is_file():
        return []
    try:
        text = hooks.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [
            AuditSignal(
                code="unreadable_codex_hooks",
                severity="warning",
                path=".codex/hooks.json",
                message="project-local Codex hooks file is not UTF-8",
                recommendation="Inspect the hooks file manually before relying on audit hook-state detection.",
                byte_count=hooks.stat().st_size,
                line_count=None,
            )
        ]
    if MANAGED_MARKER in text:
        return [
            AuditSignal(
                code="token_optimizer_hooks",
                severity="info",
                path=".codex/hooks.json",
                message="Token Optimizer managed hook state is present",
                recommendation="Use `token-optimizer hooks uninstall --project . --yes` to remove managed hook state.",
                byte_count=len(text.encode("utf-8")),
                line_count=len(text.splitlines()),
            )
        ]
    return [
        AuditSignal(
            code="codex_hooks",
            severity="info",
            path=".codex/hooks.json",
            message="project-local Codex hooks file is present",
            recommendation="Inspect hooks with Codex before assuming turn behavior is default.",
            byte_count=len(text.encode("utf-8")),
            line_count=len(text.splitlines()),
        )
    ]


def _plugin_capability_signals(project: Path, metrics: list[FileMetric]) -> list[AuditSignal]:
    signals: list[AuditSignal] = []
    manifest = project / ".codex-plugin/plugin.json"
    if manifest.exists() and not manifest.is_symlink() and manifest.is_file():
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            signals.append(
                AuditSignal(
                    code="invalid_plugin_manifest",
                    severity="warning",
                    path=".codex-plugin/plugin.json",
                    message="plugin manifest is not valid JSON",
                    recommendation="Fix the manifest before relying on plugin capability inventory.",
                )
            )
        else:
            if not isinstance(payload, dict):
                signals.append(
                    AuditSignal(
                        code="invalid_plugin_manifest",
                        severity="warning",
                        path=".codex-plugin/plugin.json",
                        message="plugin manifest must be a JSON object",
                        recommendation="Fix the manifest before relying on plugin capability inventory.",
                    )
                )
                payload = {}
            count = _declared_capability_count(payload)
            if count:
                signals.append(
                    AuditSignal(
                        code="plugin_capabilities",
                        severity="info" if count <= 3 else "warning",
                        path=".codex-plugin/plugin.json",
                        message=f"plugin declares {count} capability surface(s)",
                        recommendation="Keep plugin capabilities minimal and explicit; defer apps, MCP servers, and hooks until needed.",
                    )
                )
    skill_metrics = [
        metric
        for metric in metrics
        if metric.relative_path.startswith("skills/") and metric.path.name == "SKILL.md"
    ]
    if skill_metrics:
        total_bytes = sum(metric.byte_count for metric in skill_metrics)
        signals.append(
            AuditSignal(
                code="skill_inventory",
                severity="info" if len(skill_metrics) <= 3 and total_bytes < 20_000 else "warning",
                path="skills",
                message=f"{len(skill_metrics)} skill file(s), {total_bytes} bytes total",
                recommendation="Keep skill descriptions targeted so they load only for the right tasks.",
                byte_count=total_bytes,
            )
        )
    mcp_file = project / ".mcp.json"
    if mcp_file.exists() and not mcp_file.is_symlink() and mcp_file.is_file():
        signals.append(
            AuditSignal(
                code="mcp_config",
                severity="warning",
                path=".mcp.json",
                message="project MCP configuration file is present",
                recommendation="Review declared MCP tools for capability overhead and approval requirements.",
                byte_count=mcp_file.stat().st_size,
            )
        )
    return signals


def _outline_candidates(metrics: list[FileMetric]) -> list[FileMetric]:
    candidates = [
        metric
        for metric in metrics
        if metric.path.suffix.lower() in (MARKDOWN_SUFFIXES | {".py"})
        and metric.line_count is not None
        and (metric.line_count >= 40 or metric.byte_count >= 4_000)
    ]
    return sorted(
        candidates,
        key=lambda metric: (metric.line_count or 0, metric.byte_count),
        reverse=True,
    )[:10]


def _file_signal(
    code: str,
    severity: str,
    metric: FileMetric,
    message: str,
    recommendation: str,
) -> AuditSignal:
    return AuditSignal(
        code=code,
        severity=severity,
        path=metric.relative_path,
        message=f"{message}: {metric.relative_path}",
        recommendation=recommendation,
        byte_count=metric.byte_count,
        line_count=metric.line_count,
    )


def _declared_capability_count(payload: dict[str, Any]) -> int:
    count = 0
    for key in ("skills", "commands", "mcpServers", "mcp_servers", "apps", "hooks"):
        if key in payload:
            count += 1
    return count


def _is_guidance(metric: FileMetric) -> bool:
    parts = set(Path(metric.relative_path).parts)
    return metric.path.name in GUIDANCE_NAMES or bool(parts & GUIDANCE_PATH_PARTS)


def _exceeds(metric: FileMetric, line_threshold: int, byte_threshold: int) -> bool:
    return (
        (metric.line_count is not None and metric.line_count >= line_threshold)
        or metric.byte_count >= byte_threshold
    )


def _looks_like_output_artifact(name_lower: str) -> bool:
    return any(
        token in name_lower
        for token in ("test-output", "build-output", "command-output", "failed-command", "tree")
    )


def _looks_security_related(relative_path: str) -> bool:
    lower = relative_path.lower()
    return any(token in lower for token in ("security", "vulnerability", "secret"))


def _count_text_lines(path: Path) -> int:
    line_count = 0
    with path.open("r", encoding="utf-8") as handle:
        for _line in handle:
            line_count += 1
    return line_count


def _severity_cost(severity: str) -> int:
    if severity == "warning":
        return 8
    if severity == "info":
        return 3
    return 5


def _signal_detail(signal: AuditSignal) -> str:
    details = []
    if signal.line_count is not None:
        details.append(f"{signal.line_count} lines")
    if signal.byte_count is not None:
        details.append(f"{signal.byte_count} bytes")
    return f" ({', '.join(details)})" if details else ""


def _relative(project: Path, path: Path) -> str:
    return path.relative_to(project).as_posix()
