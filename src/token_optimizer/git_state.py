"""Optional local git-state summaries."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from token_optimizer.paths import reject_symlink, resolve_project_path


class GitStateError(ValueError):
    """Raised when git state cannot be summarized."""


@dataclass(frozen=True)
class GitStateSummary:
    """Small local git metadata snapshot."""

    project_path: Path
    branch: str
    status_lines: tuple[str, ...]
    recent_commits: tuple[str, ...]


def build_git_state_summary(project_path: str | Path | None = None) -> GitStateSummary:
    """Build an opt-in local git-state summary."""

    if project_path is not None:
        reject_symlink(Path(project_path).expanduser(), "project")
    project = resolve_project_path(project_path)
    if not project.exists() or not project.is_dir():
        raise GitStateError(f"project is not a directory: {project}")
    branch_lines = _run_git(project, "status", "--short", "--branch")
    if not branch_lines:
        raise GitStateError("git status returned no output")
    try:
        commits = _run_git(project, "log", "--oneline", "-5")
    except GitStateError:
        # A repo with no commits yet makes `git log` exit 128; report the
        # branch/status with commits marked unavailable instead of failing.
        commits = []
    return GitStateSummary(
        project_path=project,
        branch=branch_lines[0],
        status_lines=tuple(branch_lines[1:]),
        recent_commits=tuple(commits),
    )


def format_git_state_summary(summary: GitStateSummary) -> str:
    """Render git state for inclusion in a handoff summary."""

    lines = [
        "Git State",
        f"Project: {summary.project_path}",
        f"Branch: {summary.branch}",
        "Status:",
    ]
    if summary.status_lines:
        lines.extend(f"- {line}" for line in summary.status_lines)
    else:
        lines.append("- clean")
    lines.append("Recent commits:")
    if summary.recent_commits:
        lines.extend(f"- {line}" for line in summary.recent_commits)
    else:
        lines.append("- unavailable")
    return "\n".join(lines)


def _run_git(project: Path, *args: str) -> list[str]:
    command = ("git", "-C", str(project), *args)
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitStateError(f"git command timed out after 5s: {' '.join(args)}") from exc
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise GitStateError(message)
    return [line for line in completed.stdout.splitlines() if line.strip()]
