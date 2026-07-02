from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from token_optimizer.git_state import GitStateError, build_git_state_summary, format_git_state_summary


class GitStateTests(unittest.TestCase):
    def test_builds_git_state_summary_from_local_git_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            def fake_run(command: tuple[str, ...], **_: object) -> subprocess.CompletedProcess[str]:
                if command[-3:] == ("status", "--short", "--branch"):
                    return subprocess.CompletedProcess(command, 0, "## main...origin/main\n M README.md\n", "")
                if command[-3:] == ("log", "--oneline", "-5"):
                    return subprocess.CompletedProcess(command, 0, "abc123 First\n", "")
                return subprocess.CompletedProcess(command, 1, "", "unexpected")

            with patch("subprocess.run", side_effect=fake_run):
                summary = build_git_state_summary(project)

            rendered = format_git_state_summary(summary)

            self.assertEqual(summary.branch, "## main...origin/main")
            self.assertEqual(summary.status_lines, (" M README.md",))
            self.assertIn("abc123 First", rendered)

    def test_git_state_errors_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            with patch(
                "subprocess.run",
                return_value=subprocess.CompletedProcess(("git",), 128, "", "not a git repo"),
            ):
                with self.assertRaises(ValueError):
                    build_git_state_summary(project)

    def test_fresh_repo_without_commits_reports_commits_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            def fake_run(command: tuple[str, ...], **_: object) -> subprocess.CompletedProcess[str]:
                if command[-3:] == ("status", "--short", "--branch"):
                    return subprocess.CompletedProcess(command, 0, "## No commits yet on main\n", "")
                if command[-3:] == ("log", "--oneline", "-5"):
                    return subprocess.CompletedProcess(
                        command,
                        128,
                        "",
                        "fatal: your current branch 'main' does not have any commits yet",
                    )
                return subprocess.CompletedProcess(command, 1, "", "unexpected")

            with patch("subprocess.run", side_effect=fake_run):
                summary = build_git_state_summary(project)

            self.assertEqual(summary.recent_commits, ())
            self.assertIn("- unavailable", format_git_state_summary(summary))

    def test_git_timeout_raises_git_state_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            with patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd=("git",), timeout=5),
            ):
                with self.assertRaises(GitStateError) as context:
                    build_git_state_summary(project)

            self.assertIn("timed out", str(context.exception))


if __name__ == "__main__":
    unittest.main()
