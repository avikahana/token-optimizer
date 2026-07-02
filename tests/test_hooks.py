from __future__ import annotations

import fcntl
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from token_optimizer.doctor import MANAGED_MARKER
from token_optimizer.hooks import (
    HookConfigError,
    MANAGED_COMMAND,
    apply_hook_file_change,
    file_change_plan_to_json,
    format_file_change_plan,
    merge_managed_block,
    plan_hook_install_file_change,
    plan_hook_uninstall_file_change,
    parse_hooks_json,
    remove_managed_blocks,
    render_hooks_json,
)
from token_optimizer.paths import UnsafePathError


class HookMergeTests(unittest.TestCase):
    def test_merge_creates_managed_document_from_empty_input(self) -> None:
        merged = merge_managed_block(None)

        self.assertEqual(merged["_tokenOptimizer"]["marker"], MANAGED_MARKER)
        self.assertEqual(
            merged["Stop"][0]["hooks"][0]["command"],
            MANAGED_COMMAND,
        )

    def test_merge_preserves_user_owned_hooks(self) -> None:
        existing = {
            "Stop": [
                {
                    "matcher": "pytest",
                    "hooks": [{"type": "command", "command": "echo user"}],
                }
            ],
            "SessionStart": [
                {
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": "echo hello"}],
                }
            ],
            "customTopLevel": {"kept": True},
        }

        merged = merge_managed_block(existing)

        self.assertEqual(merged["Stop"][0]["hooks"][0]["command"], "echo user")
        self.assertEqual(
            merged["Stop"][1]["hooks"][0]["command"],
            MANAGED_COMMAND,
        )
        self.assertEqual(merged["SessionStart"], existing["SessionStart"])
        self.assertEqual(merged["customTopLevel"], {"kept": True})

    def test_merge_replaces_existing_token_optimizer_block(self) -> None:
        stale = merge_managed_block(None)
        stale["Stop"][0]["hooks"][0]["timeout"] = 999

        merged = merge_managed_block(stale)

        self.assertEqual(len(merged["Stop"]), 1)
        self.assertEqual(merged["Stop"][0]["hooks"][0]["timeout"], 30)

    def test_merge_is_stable_when_rendered_twice(self) -> None:
        first = render_hooks_json(merge_managed_block(None))
        second = render_hooks_json(merge_managed_block(parse_hooks_json(first)))

        self.assertEqual(first, second)

    def test_merge_rejects_invalid_existing_event_shape(self) -> None:
        with self.assertRaises(HookConfigError):
            merge_managed_block({"Stop": {"not": "a list"}})

    def test_merge_rejects_foreign_token_optimizer_metadata(self) -> None:
        with self.assertRaises(HookConfigError):
            merge_managed_block({"_tokenOptimizer": {"owner": "someone else"}})

    def test_merge_does_not_duplicate_managed_command_without_metadata(self) -> None:
        existing = {
            "Stop": [
                {
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": MANAGED_COMMAND}],
                }
            ]
        }

        merged = merge_managed_block(existing)

        commands = [
            hook["command"] for entry in merged["Stop"] for hook in entry["hooks"]
        ]
        self.assertEqual(commands.count(MANAGED_COMMAND), 1)

    def test_merge_keeps_user_command_sharing_entry_with_managed_command(self) -> None:
        existing = {
            "Stop": [
                {
                    "matcher": "*",
                    "hooks": [
                        {"type": "command", "command": "echo user"},
                        {"type": "command", "command": MANAGED_COMMAND},
                    ],
                }
            ]
        }

        merged = merge_managed_block(existing)

        commands = [
            hook["command"] for entry in merged["Stop"] for hook in entry["hooks"]
        ]
        self.assertIn("echo user", commands)
        self.assertEqual(commands.count(MANAGED_COMMAND), 1)


class HookUninstallTests(unittest.TestCase):
    def test_remove_managed_blocks_preserves_user_hooks(self) -> None:
        existing = merge_managed_block(
            {
                "Stop": [
                    {
                        "matcher": "pytest",
                        "hooks": [{"type": "command", "command": "echo user"}],
                    }
                ]
            }
        )

        uninstalled = remove_managed_blocks(existing)

        self.assertNotIn("_tokenOptimizer", uninstalled)
        self.assertEqual(len(uninstalled["Stop"]), 1)
        self.assertEqual(uninstalled["Stop"][0]["hooks"][0]["command"], "echo user")

    def test_remove_managed_blocks_clears_only_managed_document(self) -> None:
        uninstalled = remove_managed_blocks(merge_managed_block(None))

        self.assertEqual(uninstalled, {})

    def test_remove_managed_blocks_ignores_unmarked_user_document(self) -> None:
        existing = {
            "Stop": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "token-optimizer summarize --hook stop",
                        }
                    ],
                }
            ]
        }

        uninstalled = remove_managed_blocks(existing)

        self.assertEqual(uninstalled, existing)

    def test_remove_managed_blocks_keeps_user_hook_inside_managed_entry(self) -> None:
        existing = merge_managed_block(None)
        existing["Stop"][0]["hooks"].append({"type": "command", "command": "echo user"})

        uninstalled = remove_managed_blocks(existing)

        self.assertNotIn("_tokenOptimizer", uninstalled)
        self.assertEqual(len(uninstalled["Stop"]), 1)
        commands = [hook["command"] for hook in uninstalled["Stop"][0]["hooks"]]
        self.assertEqual(commands, ["echo user"])

    def test_remove_managed_blocks_is_stable_when_rendered_twice(self) -> None:
        merged = merge_managed_block({"Stop": [{"hooks": [{"command": "echo user"}]}]})

        first = render_hooks_json(remove_managed_blocks(merged))
        second = render_hooks_json(remove_managed_blocks(parse_hooks_json(first)))

        self.assertEqual(first, second)

    def test_parse_hooks_json_rejects_invalid_json(self) -> None:
        with self.assertRaises(HookConfigError):
            parse_hooks_json("{not json")

    def test_parse_hooks_json_rejects_non_object_json(self) -> None:
        with self.assertRaises(HookConfigError):
            parse_hooks_json("[]")


class HookFileChangePlanTests(unittest.TestCase):
    def test_install_file_change_plans_create_from_missing_hooks_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            plan = plan_hook_install_file_change(project)

            self.assertEqual(plan.project_path, project.resolve())
            self.assertEqual(plan.hooks_path, project.resolve() / ".codex/hooks.json")
            self.assertEqual(plan.operation, "install")
            self.assertEqual(plan.action, "create")
            self.assertTrue(plan.would_create)
            self.assertFalse(plan.would_update)
            self.assertFalse(plan.would_remove)
            self.assertFalse(plan.unchanged)
            self.assertIsNone(plan.before)
            self.assertIsNotNone(plan.after)
            self.assertIn(MANAGED_MARKER, plan.after or "")
            self.assertFalse(plan.hooks_path.exists())

    def test_install_file_change_plans_merge_without_writing_user_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            before = render_hooks_json(
                {
                    "Stop": [
                        {
                            "matcher": "pytest",
                            "hooks": [{"type": "command", "command": "echo user"}],
                        }
                    ]
                }
            )
            hooks.write_text(before, encoding="utf-8")

            plan = plan_hook_install_file_change(project)

            self.assertEqual(plan.action, "update")
            self.assertTrue(plan.would_update)
            self.assertEqual(plan.before, before)
            self.assertIn("echo user", plan.after or "")
            self.assertIn(MANAGED_COMMAND, plan.after or "")
            self.assertEqual(hooks.read_text(encoding="utf-8"), before)

    def test_install_file_change_is_unchanged_for_current_managed_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            before = render_hooks_json(merge_managed_block(None))
            hooks.write_text(before, encoding="utf-8")

            plan = plan_hook_install_file_change(project)

            self.assertEqual(plan.action, "unchanged")
            self.assertTrue(plan.unchanged)
            self.assertEqual(plan.before, before)
            self.assertEqual(plan.after, before)

    def test_install_replaces_legacy_placeholder_command_with_mode_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            before = render_hooks_json(
                {
                    "_tokenOptimizer": {
                        "marker": MANAGED_MARKER,
                        "profile": "quiet",
                        "description": "Managed by Token Optimizer. Remove with uninstall.",
                    },
                    "Stop": [
                        {
                            "matcher": "*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "token-optimizer summarize --hook stop",
                                    "timeout": 30,
                                }
                            ],
                        }
                    ],
                }
            )
            hooks.write_text(before, encoding="utf-8")

            plan = plan_hook_install_file_change(project)

            self.assertEqual(plan.action, "update")
            self.assertIn(MANAGED_COMMAND, plan.after or "")
            self.assertIn("requiresFreshConsentForActiveBehavior", plan.after or "")

    def test_uninstall_file_change_plans_remove_for_managed_only_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            before = render_hooks_json(merge_managed_block(None))
            hooks.write_text(before, encoding="utf-8")

            plan = plan_hook_uninstall_file_change(project)

            self.assertEqual(plan.operation, "uninstall")
            self.assertEqual(plan.action, "remove")
            self.assertTrue(plan.would_remove)
            self.assertEqual(plan.before, before)
            self.assertIsNone(plan.after)
            self.assertEqual(hooks.read_text(encoding="utf-8"), before)

    def test_uninstall_file_change_plans_update_when_user_hooks_remain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            before = render_hooks_json(
                merge_managed_block(
                    {
                        "Stop": [
                            {
                                "matcher": "pytest",
                                "hooks": [{"type": "command", "command": "echo user"}],
                            }
                        ]
                    }
                )
            )
            hooks.write_text(before, encoding="utf-8")

            plan = plan_hook_uninstall_file_change(project)

            self.assertEqual(plan.action, "update")
            self.assertTrue(plan.would_update)
            self.assertIn("echo user", plan.after or "")
            self.assertNotIn(MANAGED_MARKER, plan.after or "")
            self.assertEqual(hooks.read_text(encoding="utf-8"), before)

    def test_uninstall_file_change_is_unchanged_when_no_hooks_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            plan = plan_hook_uninstall_file_change(project)

            self.assertEqual(plan.action, "unchanged")
            self.assertTrue(plan.unchanged)
            self.assertIsNone(plan.before)
            self.assertIsNone(plan.after)
            self.assertTrue(any("No hooks file found" in warning for warning in plan.warnings))

    def test_file_change_plans_reject_invalid_json_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            before = "{not json"
            hooks.write_text(before, encoding="utf-8")

            with self.assertRaises(HookConfigError):
                plan_hook_install_file_change(project)
            with self.assertRaises(HookConfigError):
                plan_hook_uninstall_file_change(project)
            self.assertEqual(hooks.read_text(encoding="utf-8"), before)

    def test_file_change_plans_reject_hooks_symlink_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            target = project / "target-hooks.json"
            target.write_text("{}", encoding="utf-8")
            hooks.symlink_to(target)

            with self.assertRaises(UnsafePathError):
                plan_hook_install_file_change(project)
            with self.assertRaises(UnsafePathError):
                plan_hook_uninstall_file_change(project)

    def test_file_change_plans_reject_symlinked_codex_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            outside = root / "outside"
            project.mkdir()
            outside.mkdir()
            (project / ".codex").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(UnsafePathError):
                plan_hook_install_file_change(project)
            with self.assertRaises(UnsafePathError):
                plan_hook_uninstall_file_change(project)

    def test_file_change_plans_reject_symlinked_codex_parent_inside_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            user_owned = project / "user-owned"
            user_owned.mkdir()
            (project / ".codex").symlink_to(user_owned, target_is_directory=True)

            with self.assertRaises(UnsafePathError):
                plan_hook_install_file_change(project)
            with self.assertRaises(UnsafePathError):
                plan_hook_uninstall_file_change(project)
            self.assertFalse((user_owned / "hooks.json").exists())

    def test_format_file_change_plan_includes_action_and_planned_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            rendered = format_file_change_plan(plan_hook_install_file_change(project))

            self.assertIn("Token Optimizer Hook Install Plan", rendered)
            self.assertIn("Dry run: yes", rendered)
            self.assertIn("Action: create", rendered)
            self.assertIn("Would create: yes", rendered)
            self.assertIn("Planned hooks file:", rendered)
            self.assertIn(MANAGED_MARKER, rendered)

    def test_format_file_change_plan_shows_remove_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            hooks.write_text(render_hooks_json(merge_managed_block(None)), encoding="utf-8")

            rendered = format_file_change_plan(plan_hook_uninstall_file_change(project))

            self.assertIn("Token Optimizer Hook Uninstall Plan", rendered)
            self.assertIn("Action: remove", rendered)
            self.assertIn("Would remove: yes", rendered)
            self.assertIn("Planned hooks file: remove", rendered)

    def test_file_change_plan_to_json_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            payload = json.loads(file_change_plan_to_json(plan_hook_install_file_change(project)))

            self.assertEqual(payload["operation"], "install")
            self.assertEqual(payload["action"], "create")
            self.assertTrue(payload["dryRun"])
            self.assertTrue(payload["wouldCreate"])
            self.assertEqual(payload["managedMarker"], MANAGED_MARKER)
            self.assertIsNone(payload["before"])
            self.assertIn(MANAGED_MARKER, payload["after"])

    def test_file_change_plan_to_json_can_render_applied_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            payload = json.loads(
                file_change_plan_to_json(plan_hook_install_file_change(project), dry_run=False)
            )

            self.assertFalse(payload["dryRun"])


class HookFileApplyTests(unittest.TestCase):
    def test_apply_install_creates_hooks_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            plan = plan_hook_install_file_change(project, experimental=True)

            apply_hook_file_change(plan)

            hooks = project / ".codex/hooks.json"
            self.assertTrue(hooks.is_file())
            self.assertEqual(hooks.read_text(encoding="utf-8"), plan.after)

    def test_apply_install_merges_user_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            hooks.write_text(
                render_hooks_json(
                    {
                        "Stop": [
                            {
                                "matcher": "pytest",
                                "hooks": [{"type": "command", "command": "echo user"}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            apply_hook_file_change(plan_hook_install_file_change(project, experimental=True))

            rendered = hooks.read_text(encoding="utf-8")
            self.assertIn("echo user", rendered)
            self.assertIn(MANAGED_COMMAND, rendered)

    def test_apply_uninstall_removes_managed_only_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            hooks.write_text(render_hooks_json(merge_managed_block(None)), encoding="utf-8")

            apply_hook_file_change(plan_hook_uninstall_file_change(project))

            self.assertFalse(hooks.exists())

    def test_apply_uninstall_preserves_user_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            hooks.write_text(
                render_hooks_json(
                    merge_managed_block(
                        {
                            "Stop": [
                                {
                                    "matcher": "pytest",
                                    "hooks": [{"type": "command", "command": "echo user"}],
                                }
                            ]
                        }
                    )
                ),
                encoding="utf-8",
            )

            apply_hook_file_change(plan_hook_uninstall_file_change(project))

            rendered = hooks.read_text(encoding="utf-8")
            self.assertIn("echo user", rendered)
            self.assertNotIn(MANAGED_MARKER, rendered)

    def test_apply_unchanged_plan_is_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            before = render_hooks_json(merge_managed_block(None))
            hooks.write_text(before, encoding="utf-8")

            apply_hook_file_change(plan_hook_install_file_change(project, experimental=True))

            self.assertEqual(hooks.read_text(encoding="utf-8"), before)

    def test_apply_install_requires_experimental_consent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            plan = plan_hook_install_file_change(project)

            with self.assertRaises(HookConfigError):
                apply_hook_file_change(plan)

            self.assertFalse((project / ".codex/hooks.json").exists())

    def test_apply_rejects_hooks_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            target = project / "target-hooks.json"
            target.write_text("{}", encoding="utf-8")
            hooks.symlink_to(target)

            with self.assertRaises(UnsafePathError):
                apply_hook_file_change(
                    _fake_file_change_plan(
                        project_path=project.resolve(),
                        hooks_path=hooks,
                        action="update",
                        after="{}",
                        experimental=True,
                    )
                )
            self.assertEqual(target.read_text(encoding="utf-8"), "{}")

    def test_apply_rejects_symlinked_codex_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            outside = root / "outside"
            project.mkdir()
            outside.mkdir()
            plan = plan_hook_install_file_change(project, experimental=True)
            (project / ".codex").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(UnsafePathError):
                apply_hook_file_change(plan)
            self.assertFalse((outside / "hooks.json").exists())

    def test_apply_blocks_on_project_lock_and_rereads_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            plan = plan_hook_install_file_change(project, experimental=True)

            lock_fd = os.open(project.resolve(), os.O_RDONLY)
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            errors: list[HookConfigError] = []

            def run_apply() -> None:
                try:
                    apply_hook_file_change(plan)
                except HookConfigError as exc:
                    errors.append(exc)

            thread = threading.Thread(target=run_apply)
            try:
                thread.start()
                thread.join(timeout=0.5)
                self.assertTrue(thread.is_alive(), "apply must block while the lock is held")

                hooks = project / ".codex/hooks.json"
                hooks.parent.mkdir()
                hooks.write_text("{}", encoding="utf-8")
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            thread.join(timeout=5)

            self.assertFalse(thread.is_alive())
            self.assertEqual(len(errors), 1)
            self.assertIn("changed since plan was created", str(errors[0]))
            self.assertEqual(hooks.read_text(encoding="utf-8"), "{}")

    def test_apply_rejects_stale_hooks_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            plan = plan_hook_install_file_change(project, experimental=True)
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            hooks.write_text("{}", encoding="utf-8")

            with self.assertRaises(HookConfigError):
                apply_hook_file_change(plan)
            self.assertEqual(hooks.read_text(encoding="utf-8"), "{}")


def _fake_file_change_plan(
    *,
    project_path: Path,
    hooks_path: Path,
    action: str,
    after: str | None,
    experimental: bool = False,
):
    from token_optimizer.hooks import HookFileChangePlan

    return HookFileChangePlan(
        project_path=project_path,
        hooks_path=hooks_path,
        operation="install",
        action=action,
        experimental=experimental,
        before=None,
        after=after,
        would_create=action == "create",
        would_update=action == "update",
        would_remove=action == "remove",
        unchanged=action == "unchanged",
        warnings=(),
    )


if __name__ == "__main__":
    unittest.main()
