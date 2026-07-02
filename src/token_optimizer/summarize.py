"""Explicit-input summary generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from token_optimizer.git_state import GitStateSummary, build_git_state_summary, format_git_state_summary
from token_optimizer.limits import require_readable_size
from token_optimizer.outline import OutlineError, OutlineItem, build_outline
from token_optimizer.paths import reject_symlink_components_for_path, resolve_project_path


class SummaryError(ValueError):
    """Raised when a summary cannot be produced safely."""


@dataclass(frozen=True)
class InputSummary:
    """Compact facts about one explicit input file."""

    file_path: Path
    line_count: int
    byte_count: int
    outline_lines: tuple[str, ...]
    excerpt: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SummaryReport:
    """A compact handoff summary built only from explicit files."""

    inputs: tuple[InputSummary, ...]
    git_state: GitStateSummary | None = None


MAX_EXCERPT_CHARS = 500


def build_summary(
    file_paths: list[str] | tuple[str, ...],
    *,
    include_git_state: bool = False,
    project_path: str | Path | None = None,
) -> SummaryReport:
    """Build a read-only summary from explicit input files."""

    if not file_paths and not include_git_state:
        raise SummaryError("summarize requires at least one explicit input file")
    project = resolve_project_path(project_path)
    summaries = tuple(_summarize_file(path, project_path=project) for path in file_paths)
    git_state = build_git_state_summary(project_path) if include_git_state else None
    return SummaryReport(inputs=summaries, git_state=git_state)


def format_summary(report: SummaryReport) -> str:
    """Render a compact handoff summary."""

    lines = ["Token Optimizer Summary", f"Inputs: {len(report.inputs)}", ""]
    for index, item in enumerate(report.inputs, start=1):
        lines.append(f"{index}. {item.file_path}")
        lines.append(f"   Lines: {item.line_count}")
        lines.append(f"   Bytes: {item.byte_count}")
        lines.extend(f"   Warning: {warning}" for warning in item.warnings)
        if item.outline_lines:
            lines.append("   Outline:")
            lines.extend(f"   - {line}" for line in item.outline_lines)
        else:
            lines.append("   Outline: unavailable")
        if item.excerpt:
            lines.append(f"   Excerpt: {item.excerpt}")
        else:
            lines.append("   Excerpt: <empty file>")
        if index != len(report.inputs):
            lines.append("")
    if report.git_state is not None:
        if report.inputs:
            lines.append("")
        lines.append(format_git_state_summary(report.git_state))
    return "\n".join(lines)


def _summarize_file(file_path: str | Path, *, project_path: Path) -> InputSummary:
    raw_path = Path(file_path).expanduser()
    reject_symlink_components_for_path(raw_path, "summary input")
    path = raw_path.resolve(strict=False)
    if not path.exists():
        raise SummaryError(f"file does not exist: {path}")
    if not path.is_file():
        raise SummaryError(f"path is not a file: {path}")
    try:
        require_readable_size(path)
    except ValueError as error:
        raise SummaryError(str(error)) from error
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise SummaryError(f"input file is not UTF-8: {path}") from error
    try:
        outline = build_outline(path, project_path=project_path)
    except OutlineError:
        outline_lines: tuple[str, ...] = ()
    else:
        outline_lines = tuple(_compact_outline_item(item) for item in outline.items[:12])
    return InputSummary(
        file_path=path,
        line_count=len(text.splitlines()),
        byte_count=len(text.encode("utf-8")),
        outline_lines=outline_lines,
        excerpt=_compact_excerpt(text),
        warnings=_outside_project_warnings(path, project_path),
    )


def _compact_outline_item(item: OutlineItem) -> str:
    if item.kind == "heading":
        return f"line {item.line}: {'#' * item.level} {item.name}"
    return f"line {item.line}: {item.kind} {item.name}"


def _compact_excerpt(text: str) -> str:
    excerpt = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if len(excerpt) <= MAX_EXCERPT_CHARS:
        return excerpt
    return f"{excerpt[:MAX_EXCERPT_CHARS].rstrip()}..."


def _outside_project_warnings(path: Path, project_path: Path) -> tuple[str, ...]:
    try:
        path.relative_to(project_path)
    except ValueError:
        return (f"input resolves outside project: {project_path}",)
    return ()
