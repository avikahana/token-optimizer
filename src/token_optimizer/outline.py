"""Read-only file outline helpers."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from token_optimizer.paths import reject_symlink_components_for_path


class OutlineError(ValueError):
    """Raised when an outline cannot be produced safely."""


@dataclass(frozen=True)
class OutlineItem:
    """One structural item in a file outline."""

    line: int
    level: int
    kind: str
    name: str


@dataclass(frozen=True)
class OutlineReport:
    """A compact structure map for one explicit file."""

    file_path: Path
    file_type: str
    items: tuple[OutlineItem, ...]


MARKDOWN_SUFFIXES = {".md", ".markdown"}
PYTHON_SUFFIXES = {".py", ".pyw"}


def build_outline(file_path: str | Path) -> OutlineReport:
    """Build a compact outline for a Markdown or Python file."""

    path = _resolve_input_file(file_path)
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix in MARKDOWN_SUFFIXES:
        return OutlineReport(path, "Markdown", tuple(_outline_markdown(text)))
    if suffix in PYTHON_SUFFIXES:
        return OutlineReport(path, "Python", tuple(_outline_python(text)))
    raise OutlineError(f"unsupported file type: {path.suffix or '<none>'}")


def format_outline(report: OutlineReport) -> str:
    """Render an outline for human CLI output."""

    lines = [
        f"{report.file_type} Outline",
        f"File: {report.file_path}",
        "",
    ]
    if not report.items:
        lines.append(f"No {report.file_type} structure found.")
        return "\n".join(lines)
    for item in report.items:
        indent = "  " * (item.level - 1)
        lines.append(f"{item.line}: {indent}{_format_item_label(item)}")
    return "\n".join(lines)


def _resolve_input_file(file_path: str | Path) -> Path:
    raw_path = Path(file_path).expanduser()
    reject_symlink_components_for_path(raw_path, "outline input")
    path = raw_path.resolve(strict=False)
    if not path.exists():
        raise OutlineError(f"file does not exist: {path}")
    if not path.is_file():
        raise OutlineError(f"path is not a file: {path}")
    return path


def _outline_markdown(text: str) -> list[OutlineItem]:
    items: list[OutlineItem] = []
    fence_marker: str | None = None
    pending_setext: tuple[int, str] | None = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        marker = _fence_marker(stripped)
        if marker is not None:
            if fence_marker is None:
                fence_marker = marker
            elif marker == fence_marker:
                fence_marker = None
            pending_setext = None
            continue
        if fence_marker is not None:
            continue
        compact = line.strip()
        if pending_setext is not None and _is_setext_underline(compact):
            heading_line, heading = pending_setext
            items.append(
                OutlineItem(
                    line=heading_line,
                    level=1 if compact.startswith("=") else 2,
                    kind="heading",
                    name=heading,
                )
            )
            pending_setext = None
            continue
        if not line.startswith("#"):
            pending_setext = (line_number, compact) if compact else None
            continue
        marker, _, title = line.partition(" ")
        if not title.strip() or len(marker) > 6 or set(marker) != {"#"}:
            pending_setext = None
            continue
        items.append(
            OutlineItem(
                line=line_number,
                level=len(marker),
                kind="heading",
                name=title.strip(),
            )
        )
        pending_setext = None
    return items


def _outline_python(text: str) -> list[OutlineItem]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise OutlineError(f"invalid Python syntax: line {exc.lineno}") from exc
    items: list[OutlineItem] = []
    _collect_python_items(tree.body, items, level=1)
    return items


def _collect_python_items(
    statements: list[ast.stmt],
    items: list[OutlineItem],
    *,
    level: int,
) -> None:
    for statement in statements:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "async function" if isinstance(statement, ast.AsyncFunctionDef) else "function"
            items.append(OutlineItem(statement.lineno, level, kind, statement.name))
            _collect_python_items(statement.body, items, level=level + 1)
        elif isinstance(statement, ast.ClassDef):
            items.append(OutlineItem(statement.lineno, level, "class", statement.name))
            _collect_python_items(statement.body, items, level=level + 1)


def _format_item_label(item: OutlineItem) -> str:
    if item.kind == "heading":
        return f"{'#' * item.level} {item.name}"
    return f"{item.kind} {item.name}"


def _fence_marker(stripped_line: str) -> str | None:
    if stripped_line.startswith("```"):
        return "```"
    if stripped_line.startswith("~~~"):
        return "~~~"
    return None


def _is_setext_underline(stripped_line: str) -> bool:
    return bool(stripped_line) and set(stripped_line) in ({"="}, {"-"})
