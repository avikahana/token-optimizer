from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from token_optimizer.dashboard import (
    apply_dashboard_plan,
    dashboard_plan_to_json,
    plan_dashboard,
    render_dashboard_html,
)


class DashboardTests(unittest.TestCase):
    def test_renders_static_dashboard_from_audit_json(self) -> None:
        audit_json = json.dumps(
            {
                "project": "/tmp/project",
                "score": 92,
                "scannedFiles": 3,
                "signals": [
                    {
                        "severity": "warning",
                        "path": "large.md",
                        "message": "large Markdown/docs file",
                        "recommendation": "outline it",
                    }
                ],
                "outlineCandidates": [{"path": "large.md", "lines": 320, "bytes": 12000}],
            }
        )

        rendered = render_dashboard_html(audit_json)

        self.assertIn("Token Optimizer Audit Dashboard", rendered)
        self.assertIn("92/100", rendered)
        self.assertIn("large Markdown/docs file", rendered)
        self.assertIn("large.md", rendered)

    def test_dashboard_plan_is_read_only_until_applied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")

            plan = plan_dashboard(project)

            self.assertTrue(plan.would_create)
            self.assertFalse(plan.output_path.exists())

    def test_apply_dashboard_plan_writes_project_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")

            plan = apply_dashboard_plan(plan_dashboard(project))

            self.assertTrue(plan.output_path.is_file())
            self.assertIn(
                "Token Optimizer Audit Dashboard",
                plan.output_path.read_text(encoding="utf-8"),
            )

    def test_dashboard_plan_is_stable_after_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")

            first = apply_dashboard_plan(plan_dashboard(project))
            second = plan_dashboard(project)

            self.assertEqual(second.output_path, first.output_path)
            self.assertTrue(second.unchanged)

    def test_dashboard_json_plan_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")

            payload = json.loads(dashboard_plan_to_json(plan_dashboard(project)))

            self.assertEqual(payload["action"], "create")
            self.assertTrue(payload["wouldCreate"])
            self.assertIn("audit-dashboard.html", payload["outputPath"])

    def test_rejects_output_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                plan_dashboard(project, output_path="../dashboard.html")

    def test_rejects_dashboard_output_outside_owned_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                plan_dashboard(project, output_path="README.md")

    def test_allows_custom_dashboard_output_inside_owned_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")

            plan = plan_dashboard(
                project,
                output_path=".codex/token-optimizer/custom-dashboard.html",
            )

            self.assertTrue(plan.would_create)
            self.assertEqual(
                plan.output_path,
                project.resolve() / ".codex/token-optimizer/custom-dashboard.html",
            )

    def test_apply_dashboard_rejects_stale_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")
            plan = plan_dashboard(project)
            plan.output_path.parent.mkdir(parents=True)
            plan.output_path.write_text("changed", encoding="utf-8")

            with self.assertRaises(ValueError):
                apply_dashboard_plan(plan)
            self.assertEqual(plan.output_path.read_text(encoding="utf-8"), "changed")


if __name__ == "__main__":
    unittest.main()
