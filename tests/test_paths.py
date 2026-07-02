from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from token_optimizer.paths import (
    UnsafePathError,
    atomic_write_text,
    reject_symlink_components_for_path,
    resolve_project_path,
    resolve_under_project,
)


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

    def test_reject_symlink_components_for_path_checks_first_absolute_component(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "target"
            target.mkdir()
            symlink = root / "link"
            symlink.symlink_to(target, target_is_directory=True)

            with self.assertRaises(UnsafePathError):
                reject_symlink_components_for_path(symlink / "file.txt", "fixture")

    def test_atomic_write_text_creates_and_overwrites_without_temp_leftovers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "hooks.json"

            atomic_write_text(target, "first")
            self.assertEqual(target.read_text(encoding="utf-8"), "first")

            atomic_write_text(target, "second")
            self.assertEqual(target.read_text(encoding="utf-8"), "second")
            self.assertEqual([path.name for path in Path(directory).iterdir()], ["hooks.json"])


if __name__ == "__main__":
    unittest.main()
