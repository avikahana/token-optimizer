from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from token_optimizer.doctor import MANAGED_MARKER, build_report, format_report, report_to_json

GOLDEN_DIR = Path(__file__).parent / "golden"


class DoctorTests(unittest.TestCase):
    def test_doctor_reports_project_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            report = build_report(project)
            resolved = project.resolve()

            self.assertEqual(report.project_path, resolved)
            self.assertEqual(report.config.path, resolved / ".codex/token-optimizer.json")
            self.assertEqual(report.data.path, resolved / ".codex/token-optimizer")
            self.assertEqual(report.hooks.path, resolved / ".codex/hooks.json")
            self.assertFalse(report.managed_hooks_present)
            self.assertEqual(report.warnings, ())

    def test_doctor_detects_managed_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            hooks.write_text('{"_comment": "TOKEN_OPTIMIZER_MANAGED"}', encoding="utf-8")

            report = build_report(project)

            self.assertTrue(report.hooks.exists)
            self.assertTrue(report.managed_hooks_present)

    def test_doctor_handles_hooks_path_directory_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / ".codex/hooks.json").mkdir(parents=True)

            report = build_report(project)

            self.assertFalse(report.managed_hooks_present)
            self.assertTrue(
                any("not a file" in warning for warning in report.warnings)
            )

    def test_doctor_warns_about_symlink_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            codex_dir = project / ".codex"
            codex_dir.mkdir()
            target = project / "target.json"
            target.write_text("{}", encoding="utf-8")
            (codex_dir / "token-optimizer.json").symlink_to(target)

            report = build_report(project)

            self.assertTrue(
                any("Config path is a symlink" in warning for warning in report.warnings)
            )

    def test_format_report_includes_expected_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            rendered = format_report(build_report(project))

            self.assertIn("Token Optimizer Doctor", rendered)
            self.assertIn("Version: 0.1.0", rendered)
            self.assertIn(f"Project: {project.resolve()}", rendered)
            self.assertIn("Managed hooks present: no", rendered)
            self.assertIn("Warnings: none", rendered)

    def test_default_report_matches_golden_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            rendered = format_report(build_report(project))

            self.assertEqual(
                _normalize_project_path(rendered, project),
                _read_golden("doctor_default.txt"),
            )

    def test_default_json_report_matches_golden_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            rendered = report_to_json(build_report(project))

            self.assertEqual(
                _normalize_project_path(rendered, project),
                _read_golden("doctor_default.json"),
            )

    def test_json_report_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            payload = json.loads(report_to_json(build_report(project)))

            self.assertEqual(payload["version"], "0.1.0")
            self.assertEqual(payload["project"], str(project.resolve()))
            self.assertEqual(payload["managedMarker"], MANAGED_MARKER)
            self.assertFalse(payload["managedHooksPresent"])
            self.assertEqual(payload["warnings"], [])
            self.assertEqual(
                payload["paths"]["config"]["path"],
                str(project.resolve() / ".codex/token-optimizer.json"),
            )
            self.assertFalse(payload["paths"]["config"]["exists"])
            self.assertFalse(payload["paths"]["config"]["symlink"])


def _read_golden(name: str) -> str:
    return (GOLDEN_DIR / name).read_text(encoding="utf-8").removesuffix("\n")


def _normalize_project_path(rendered: str, project: Path) -> str:
    return rendered.replace(str(project.resolve()), "<PROJECT>")


if __name__ == "__main__":
    unittest.main()
