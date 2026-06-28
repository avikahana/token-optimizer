from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from token_optimizer.hooks import merge_managed_block, render_hooks_json
from token_optimizer.persistence import (
    PurgeApplyError,
    apply_config_init,
    apply_purge,
    config_init_plan_to_json,
    plan_config_init,
    plan_purge,
    purge_plan_to_json,
)
from token_optimizer.paths import UnsafePathError


class PersistenceTests(unittest.TestCase):
    def test_config_init_plan_is_read_only_until_applied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = plan_config_init(directory)

            self.assertTrue(plan.would_create_config)
            self.assertTrue(plan.would_create_data_dir)
            self.assertFalse(plan.config_path.exists())
            self.assertFalse(plan.data_path.exists())

    def test_config_init_apply_writes_config_and_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = apply_config_init(plan_config_init(directory))

            self.assertTrue(plan.config_path.is_file())
            self.assertTrue(plan.data_path.is_dir())
            payload = json.loads(plan.config_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["createdBy"], "token-optimizer")
            self.assertEqual(
                payload["defaults"]["dashboardPath"],
                ".codex/token-optimizer/audit-dashboard.html",
            )

    def test_config_init_json_plan_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = json.loads(config_init_plan_to_json(plan_config_init(directory)))

            self.assertTrue(payload["wouldCreateConfig"])
            self.assertTrue(payload["wouldCreateDataDir"])
            self.assertEqual(payload["action"], "create")

    def test_config_init_rejects_symlinked_codex_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            outside = root / "outside"
            project.mkdir()
            outside.mkdir()
            (project / ".codex").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(UnsafePathError):
                plan_config_init(project)

    def test_config_init_rejects_symlinked_codex_parent_inside_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            user_owned = project / "user-owned"
            user_owned.mkdir()
            (project / ".codex").symlink_to(user_owned, target_is_directory=True)

            with self.assertRaises(UnsafePathError):
                plan_config_init(project)
            self.assertFalse((user_owned / "token-optimizer.json").exists())

    def test_config_init_apply_rejects_symlinked_codex_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            outside = root / "outside"
            project.mkdir()
            outside.mkdir()
            plan = plan_config_init(project)
            (project / ".codex").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(UnsafePathError):
                apply_config_init(plan)
            self.assertFalse((outside / "token-optimizer.json").exists())

    def test_config_init_apply_rejects_stale_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            plan = plan_config_init(project)
            config = project / ".codex/token-optimizer.json"
            config.parent.mkdir()
            config.write_text("{}", encoding="utf-8")

            with self.assertRaises(ValueError):
                apply_config_init(plan)
            self.assertEqual(config.read_text(encoding="utf-8"), "{}")

    def test_purge_plan_includes_owned_paths_and_managed_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            apply_config_init(plan_config_init(project))
            hooks = project / ".codex/hooks.json"
            hooks.write_text(render_hooks_json(merge_managed_block(None)), encoding="utf-8")

            plan = plan_purge(project)

            self.assertTrue(plan.would_remove_config)
            self.assertTrue(plan.would_remove_data_dir)
            self.assertTrue(plan.would_remove_hooks)
            self.assertFalse(plan.unchanged)

    def test_purge_apply_removes_owned_paths_and_managed_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            apply_config_init(plan_config_init(project))
            hooks = project / ".codex/hooks.json"
            hooks.write_text(render_hooks_json(merge_managed_block(None)), encoding="utf-8")

            apply_purge(plan_purge(project))

            self.assertFalse((project / ".codex/token-optimizer.json").exists())
            self.assertFalse((project / ".codex/token-optimizer").exists())
            self.assertFalse(hooks.exists())

    def test_purge_plan_rejects_symlinked_codex_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            outside = root / "outside"
            project.mkdir()
            outside.mkdir()
            (project / ".codex").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(UnsafePathError):
                plan_purge(project)

    def test_purge_plan_rejects_symlinked_codex_parent_inside_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            user_owned = project / "user-owned"
            data = user_owned / "token-optimizer"
            data.mkdir(parents=True)
            (data / "keep.txt").write_text("do not delete", encoding="utf-8")
            (project / ".codex").symlink_to(user_owned, target_is_directory=True)

            with self.assertRaises(UnsafePathError):
                plan_purge(project)
            self.assertTrue((data / "keep.txt").exists())

    def test_purge_apply_rejects_symlinked_codex_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            outside = root / "outside"
            project.mkdir()
            outside.mkdir()
            apply_config_init(plan_config_init(project))
            plan = plan_purge(project)
            (project / ".codex").rename(project / ".codex-real")
            (project / ".codex").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(UnsafePathError):
                apply_purge(plan)
            self.assertFalse((outside / "token-optimizer").exists())
            self.assertTrue((project / ".codex-real/token-optimizer.json").exists())

    def test_purge_apply_rejects_symlinked_codex_parent_inside_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            apply_config_init(plan_config_init(project))
            plan = plan_purge(project)
            real_codex = project / ".codex-real"
            user_owned = project / "user-owned"
            user_data = user_owned / "token-optimizer"
            (project / ".codex").rename(real_codex)
            user_data.mkdir(parents=True)
            (user_data / "keep.txt").write_text("do not delete", encoding="utf-8")
            (project / ".codex").symlink_to(user_owned, target_is_directory=True)

            with self.assertRaises(UnsafePathError):
                apply_purge(plan)
            self.assertTrue((user_data / "keep.txt").exists())
            self.assertTrue((real_codex / "token-optimizer.json").exists())

    def test_purge_apply_rejects_stale_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            apply_config_init(plan_config_init(project))
            plan = plan_purge(project)
            (project / ".codex/token-optimizer.json").unlink()

            with self.assertRaises(ValueError):
                apply_purge(plan)

    def test_purge_apply_reports_partial_steps_on_os_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            apply_config_init(plan_config_init(project))
            plan = plan_purge(project)

            with patch("token_optimizer.persistence.shutil.rmtree", side_effect=OSError("boom")):
                with self.assertRaises(PurgeApplyError) as raised:
                    apply_purge(plan)

            self.assertEqual(raised.exception.completed_steps, ("hooks", "config"))
            self.assertIn("completed purge steps before failure: hooks, config", str(raised.exception))

    def test_purge_json_plan_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            apply_config_init(plan_config_init(project))

            payload = json.loads(purge_plan_to_json(plan_purge(project)))

            self.assertTrue(payload["wouldRemoveConfig"])
            self.assertTrue(payload["wouldRemoveDataDir"])
            self.assertFalse(payload["unchanged"])


if __name__ == "__main__":
    unittest.main()
