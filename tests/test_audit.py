from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from token_optimizer.audit import AuditError, audit_to_json, build_audit, format_audit
from token_optimizer.hooks import merge_managed_block, render_hooks_json


class AuditTests(unittest.TestCase):
    def test_detects_large_markdown_and_python_outline_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")
            docs = project / "docs"
            docs.mkdir()
            (docs / "big.md").write_text("# Big\n" + "detail\n" * 320, encoding="utf-8")
            src = project / "app.py"
            src.write_text("def f():\n    pass\n" * 260, encoding="utf-8")

            report = build_audit(project)
            codes = {signal.code for signal in report.signals}

            self.assertIn("large_markdown", codes)
            self.assertIn("large_source", codes)
            self.assertIn("docs/big.md", [item.relative_path for item in report.outline_candidates])
            self.assertIn("app.py", [item.relative_path for item in report.outline_candidates])

    def test_detects_generated_dirs_without_descending_into_them(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")
            cache = project / "node_modules"
            cache.mkdir()
            (cache / "huge.md").write_text("# Ignored\n" + "x\n" * 500, encoding="utf-8")

            report = build_audit(project)

            self.assertIn("node_modules", report.skipped_dirs)
            self.assertIn("generated_directory", {signal.code for signal in report.signals})
            self.assertNotIn(
                "node_modules/huge.md",
                [item.relative_path for item in report.outline_candidates],
            )

    def test_skips_token_optimizer_generated_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")
            generated = project / ".codex/token-optimizer"
            generated.mkdir(parents=True)
            (generated / "audit-dashboard.html").write_text("x\n" * 1000, encoding="utf-8")

            report = build_audit(project)

            self.assertNotIn(".codex/token-optimizer", report.skipped_dirs)
            self.assertNotIn(
                ".codex/token-optimizer/audit-dashboard.html",
                [item.relative_path for item in report.outline_candidates],
            )

    def test_detects_noisy_fixture_outputs_and_security_like_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")
            fixtures = project / "fixtures"
            fixtures.mkdir()
            (fixtures / "build-output.log").write_text("warning\n" * 2000, encoding="utf-8")
            (fixtures / "test-output.out").write_text("FAILED test_x\n" * 1000, encoding="utf-8")
            (fixtures / "tree.txt").write_text("src/file.py\n" * 1000, encoding="utf-8")
            (fixtures / "failed-command.err").write_text("traceback\n" * 1000, encoding="utf-8")
            (fixtures / "security-report.md").write_text(
                "# Security\n" + "finding details\n" * 800,
                encoding="utf-8",
            )

            codes = [signal.code for signal in build_audit(project).signals]

            self.assertGreaterEqual(codes.count("noisy_output"), 4)
            self.assertIn("security_context", codes)

    def test_detects_guidance_and_capability_overhead(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")
            skills = project / "skills/example"
            skills.mkdir(parents=True)
            (skills / "SKILL.md").write_text("---\nname: example\n---\nUse me.\n", encoding="utf-8")
            manifest_dir = project / ".codex-plugin"
            manifest_dir.mkdir()
            (manifest_dir / "plugin.json").write_text(
                json.dumps(
                    {
                        "name": "example",
                        "skills": "./skills/",
                        "commands": "./commands/",
                        "mcpServers": {"example": {}},
                        "apps": [],
                        "hooks": "./hooks/hooks.json",
                        "interface": {"capabilities": ["Local", "Tools"]},
                    }
                ),
                encoding="utf-8",
            )
            (project / ".mcp.json").write_text("{}", encoding="utf-8")

            codes = {signal.code for signal in build_audit(project).signals}

            self.assertIn("plugin_capabilities", codes)
            self.assertIn("skill_inventory", codes)
            self.assertIn("mcp_config", codes)

    def test_detects_token_optimizer_hook_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            hooks.write_text(render_hooks_json(merge_managed_block(None)), encoding="utf-8")

            codes = {signal.code for signal in build_audit(project).signals}

            self.assertIn("token_optimizer_hooks", codes)

    def test_warns_for_non_utf8_hooks_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            hooks.write_bytes(b"\xff")

            report = build_audit(project)

            codes = {signal.code for signal in report.signals}
            self.assertIn("unreadable_codex_hooks", codes)

    def test_reports_missing_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codes = {signal.code for signal in build_audit(directory).signals}

            self.assertIn("missing_guidance", codes)

    def test_json_report_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")

            payload = json.loads(audit_to_json(build_audit(project)))

            self.assertEqual(payload["project"], str(project.resolve()))
            self.assertIn("score", payload)
            self.assertIn("signals", payload)
            self.assertIn("outlineCandidates", payload)

    def test_format_audit_includes_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")

            rendered = format_audit(build_audit(project))

            self.assertIn("Token Optimizer Audit", rendered)
            self.assertIn("Signals:", rendered)
            self.assertIn("Top outline candidates:", rendered)

    def test_audit_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")
            before = sorted(path.relative_to(project).as_posix() for path in project.rglob("*"))

            build_audit(project)

            after = sorted(path.relative_to(project).as_posix() for path in project.rglob("*"))
            self.assertEqual(before, after)

    def test_rejects_symlink_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            link = root / "link"
            link.symlink_to(project, target_is_directory=True)

            with self.assertRaises(ValueError):
                build_audit(link)

    def test_rejects_file_as_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "file.txt"
            path.write_text("not a project", encoding="utf-8")

            with self.assertRaises(AuditError):
                build_audit(path)


if __name__ == "__main__":
    unittest.main()
