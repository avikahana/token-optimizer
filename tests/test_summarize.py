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
            path = Path(directory).resolve() / "notes.md"
            path.write_text("# Decision\n\nUse explicit inputs.\n", encoding="utf-8")

            report = build_summary([str(path)])
            rendered = format_summary(report)

            self.assertEqual(len(report.inputs), 1)
            self.assertIn("Token Optimizer Summary", rendered)
            self.assertIn("line 1: # Decision", rendered)
            self.assertIn("Excerpt: # Decision Use explicit inputs.", rendered)

    def test_summarizes_python_input_with_outline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "app.py"
            path.write_text("class App:\n    def run(self):\n        pass\n", encoding="utf-8")

            rendered = format_summary(build_summary([str(path)]))

            self.assertIn("line 1: class App", rendered)
            self.assertIn("line 2: function run", rendered)

    def test_summarizes_unsupported_input_without_outline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "log.txt"
            path.write_text("build failed\nnext line\n", encoding="utf-8")

            rendered = format_summary(build_summary([str(path)]))

            self.assertIn("Outline: unavailable", rendered)
            self.assertIn("Excerpt: build failed next line", rendered)

    def test_warns_when_explicit_input_resolves_outside_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / "project"
            outside = root / "outside"
            project.mkdir()
            outside.mkdir()
            path = outside / "notes.md"
            path.write_text("# Outside\n", encoding="utf-8")

            report = build_summary([str(path)], project_path=project)
            rendered = format_summary(report)

            self.assertEqual(
                report.inputs[0].warnings,
                (f"input resolves outside project: {project}",),
            )
            self.assertIn(f"Warning: input resolves outside project: {project}", rendered)

    def test_wraps_non_utf8_input_in_summary_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "binary.md"
            path.write_bytes(b"\xff\xfe")

            with self.assertRaisesRegex(SummaryError, "input file is not UTF-8"):
                build_summary([str(path)], project_path=path.parent)

    def test_rejects_symlink_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "target.md"
            target.write_text("# Title\n", encoding="utf-8")
            link = root / "link.md"
            link.symlink_to(target)

            with self.assertRaises(ValueError):
                build_summary([str(link)])

    def test_rejects_symlinked_parent_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            outside = root / "outside"
            outside.mkdir()
            (outside / "target.md").write_text("# Title\n", encoding="utf-8")
            link_dir = root / "linked"
            link_dir.symlink_to(outside, target_is_directory=True)

            with self.assertRaises(ValueError):
                build_summary([str(link_dir / "target.md")])

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



class SummaryLimitTests(unittest.TestCase):
    def test_rejects_oversized_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "big.md"
            path.write_text("# Big\n", encoding="utf-8")

            with patch(
                "token_optimizer.summarize.require_readable_size",
                side_effect=ValueError("refusing to read files over 10485760 bytes"),
            ):
                with self.assertRaises(SummaryError) as raised:
                    build_summary([str(path)])

            self.assertIn("refusing to read", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
