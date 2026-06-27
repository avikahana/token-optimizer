from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from token_optimizer.paths import UnsafePathError, resolve_project_path, resolve_under_project


class PathSafetyTests(unittest.TestCase):
    def test_resolve_project_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            self.assertEqual(resolve_project_path(project), project.resolve())

    def test_resolve_under_project_accepts_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()

            self.assertEqual(
                resolve_under_project(project, ".codex/hooks.json"),
                project / ".codex/hooks.json",
            )

    def test_resolve_under_project_rejects_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()

            with self.assertRaises(UnsafePathError):
                resolve_under_project(project, Path("/tmp/outside"))

    def test_resolve_under_project_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()

            with self.assertRaises(UnsafePathError):
                resolve_under_project(project, "../outside")


if __name__ == "__main__":
    unittest.main()
