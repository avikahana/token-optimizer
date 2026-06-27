from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from token_optimizer.summarize import SummaryError, build_summary, format_summary


class SummaryTests(unittest.TestCase):
    def test_requires_explicit_inputs(self) -> None:
        with self.assertRaises(SummaryError):
            build_summary([])

    def test_summarizes_markdown_input_with_outline_and_excerpt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.md"
            path.write_text("# Decision\n\nUse explicit inputs.\n", encoding="utf-8")

            report = build_summary([str(path)])
            rendered = format_summary(report)

            self.assertEqual(len(report.inputs), 1)
            self.assertIn("Token Optimizer Summary", rendered)
            self.assertIn("line 1: # Decision", rendered)
            self.assertIn("Excerpt: # Decision Use explicit inputs.", rendered)

    def test_summarizes_python_input_with_outline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.py"
            path.write_text("class App:\n    def run(self):\n        pass\n", encoding="utf-8")

            rendered = format_summary(build_summary([str(path)]))

            self.assertIn("line 1: class App", rendered)
            self.assertIn("line 2: function run", rendered)

    def test_summarizes_unsupported_input_without_outline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "log.txt"
            path.write_text("build failed\nnext line\n", encoding="utf-8")

            rendered = format_summary(build_summary([str(path)]))

            self.assertIn("Outline: unavailable", rendered)
            self.assertIn("Excerpt: build failed next line", rendered)

    def test_rejects_symlink_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.md"
            target.write_text("# Title\n", encoding="utf-8")
            link = Path(directory) / "link.md"
            link.symlink_to(target)

            with self.assertRaises(ValueError):
                build_summary([str(link)])

    def test_can_include_opt_in_git_state_without_file_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch("token_optimizer.summarize.build_git_state_summary") as fake_git:
                fake_git.return_value = type(
                    "FakeGitState",
                    (),
                    {
                        "project_path": Path(directory),
                        "branch": "## main",
                        "status_lines": (),
                        "recent_commits": ("abc123 Commit",),
                    },
                )()

                rendered = format_summary(
                    build_summary([], include_git_state=True, project_path=directory)
                )

        self.assertIn("Inputs: 0", rendered)
        self.assertIn("Git State", rendered)
        self.assertIn("abc123 Commit", rendered)


if __name__ == "__main__":
    unittest.main()
