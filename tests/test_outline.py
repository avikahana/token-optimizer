from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from token_optimizer.outline import OutlineError, build_outline, format_outline


class MarkdownOutlineTests(unittest.TestCase):
    def test_builds_markdown_outline_from_headings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "notes.md"
            path.write_text("# Title\n\n## Work\nText\n### Detail\n", encoding="utf-8")

            report = build_outline(path)

            self.assertEqual(report.file_type, "Markdown")
            self.assertEqual([item.name for item in report.items], ["Title", "Work", "Detail"])
            self.assertEqual([item.level for item in report.items], [1, 2, 3])

    def test_ignores_markdown_headings_inside_fenced_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "notes.md"
            path.write_text("# Title\n```markdown\n# Ignored\n```\n## Kept\n", encoding="utf-8")

            report = build_outline(path)

            self.assertEqual([item.name for item in report.items], ["Title", "Kept"])

    def test_does_not_close_fenced_code_with_different_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "notes.md"
            path.write_text(
                "# Title\n```markdown\n# Ignored\n~~~\n# Still ignored\n```\n## Kept\n",
                encoding="utf-8",
            )

            report = build_outline(path)

            self.assertEqual([item.name for item in report.items], ["Title", "Kept"])

    def test_detects_setext_headings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "notes.md"
            path.write_text("Title\n=====\n\nWork\n----\n", encoding="utf-8")

            report = build_outline(path)

            self.assertEqual([item.name for item in report.items], ["Title", "Work"])
            self.assertEqual([item.level for item in report.items], [1, 2])

    def test_formats_markdown_outline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "notes.md"
            path.write_text("# Title\n\n## Work\n", encoding="utf-8")

            rendered = format_outline(build_outline(path))

            self.assertIn("Markdown Outline", rendered)
            self.assertIn("1: # Title", rendered)
            self.assertIn("3:   ## Work", rendered)


class PythonOutlineTests(unittest.TestCase):
    def test_builds_python_outline_from_classes_and_functions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "app.py"
            path.write_text(
                "def top():\n"
                "    def nested():\n"
                "        pass\n"
                "\n"
                "class Runner:\n"
                "    async def run(self):\n"
                "        pass\n",
                encoding="utf-8",
            )

            report = build_outline(path)

            self.assertEqual(report.file_type, "Python")
            self.assertEqual(
                [(item.line, item.level, item.kind, item.name) for item in report.items],
                [
                    (1, 1, "function", "top"),
                    (2, 2, "function", "nested"),
                    (5, 1, "class", "Runner"),
                    (6, 2, "async function", "run"),
                ],
            )

    def test_rejects_invalid_python(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "broken.py"
            path.write_text("def nope(:\n", encoding="utf-8")

            with self.assertRaises(OutlineError):
                build_outline(path)


class OutlineSafetyTests(unittest.TestCase):
    def test_rejects_unsupported_file_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "notes.txt"
            path.write_text("hello", encoding="utf-8")

            with self.assertRaises(OutlineError):
                build_outline(path)

    def test_warns_when_explicit_input_resolves_outside_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / "project"
            outside = root / "outside"
            project.mkdir()
            outside.mkdir()
            path = outside / "notes.md"
            path.write_text("# Outside\n", encoding="utf-8")

            report = build_outline(path, project_path=project)
            rendered = format_outline(report)

            self.assertEqual(
                report.warnings,
                (f"input resolves outside project: {project}",),
            )
            self.assertIn(f"Warning: input resolves outside project: {project}", rendered)

    def test_wraps_non_utf8_input_in_outline_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "binary.md"
            path.write_bytes(b"\xff\xfe")

            with self.assertRaisesRegex(OutlineError, "input file is not UTF-8"):
                build_outline(path, project_path=path.parent)

    def test_rejects_symlink_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "target.md"
            target.write_text("# Title\n", encoding="utf-8")
            link = root / "link.md"
            link.symlink_to(target)

            with self.assertRaises(ValueError):
                build_outline(link)

    def test_rejects_symlinked_parent_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            outside = root / "outside"
            outside.mkdir()
            (outside / "target.md").write_text("# Title\n", encoding="utf-8")
            link_dir = root / "linked"
            link_dir.symlink_to(outside, target_is_directory=True)

            with self.assertRaises(ValueError):
                build_outline(link_dir / "target.md")

    def test_reports_no_structure_for_plain_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "notes.md"
            path.write_text("plain text only\n", encoding="utf-8")

            rendered = format_outline(build_outline(path))

            self.assertIn("No Markdown structure found.", rendered)


if __name__ == "__main__":
    unittest.main()
