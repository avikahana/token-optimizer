from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from token_optimizer.cli import main
from token_optimizer.hooks import merge_managed_block, render_hooks_json


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/fixtures/common-python-cli-session"
)


class CliTests(unittest.TestCase):
    def test_version_uses_package_version(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                main(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), "token-optimizer 0.1.0")

    def test_summarize_accepts_hook_placeholder(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            status = main(
                [
                    "summarize",
                    "--hook",
                    "stop",
                    "--hook-mode",
                    "inactive-placeholder-v1",
                ]
            )

        self.assertEqual(status, 0)
        self.assertIn("hook source stop is intentionally inactive", output.getvalue())
        self.assertIn("no transcript, file content, or tool output", output.getvalue())

    def test_summarize_rejects_hook_mode_without_hook_source(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            status = main(["summarize", "--hook-mode", "inactive-placeholder-v1"])

        self.assertEqual(status, 1)
        self.assertIn("--hook-mode requires --hook", output.getvalue())

    def test_handoff_alias_still_works(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            status = main(["handoff", "--hook", "stop"])

        self.assertEqual(status, 0)
        self.assertIn("alias for summarize", output.getvalue())
        self.assertIn("intentionally inactive", output.getvalue())

    def test_outline_markdown_outputs_structure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "notes.md"
            path.write_text("# Title\n\n## Next\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["outline", str(path)])

            self.assertEqual(status, 0)
            self.assertIn("Markdown Outline", output.getvalue())
            self.assertIn("1: # Title", output.getvalue())

    def test_outline_python_outputs_structure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "app.py"
            path.write_text("class App:\n    def run(self):\n        pass\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["outline", str(path)])

            self.assertEqual(status, 0)
            self.assertIn("Python Outline", output.getvalue())
            self.assertIn("1: class App", output.getvalue())

    def test_summarize_requires_explicit_inputs(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            status = main(["summarize"])

        self.assertEqual(status, 1)
        self.assertIn("requires at least one explicit input file", output.getvalue())

    def test_summarize_reads_only_explicit_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "notes.md"
            path.write_text("# Decision\n\nKeep it explicit.\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["summarize", str(path)])

            self.assertEqual(status, 0)
            self.assertIn("Token Optimizer Summary", output.getvalue())
            self.assertIn("line 1: # Decision", output.getvalue())

    def test_handoff_summarizes_explicit_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "notes.md"
            path.write_text("# Handoff\n\nContinue here.\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["handoff", str(path)])

            self.assertEqual(status, 0)
            self.assertIn("Token Optimizer Summary", output.getvalue())

    def test_doctor_json_outputs_machine_readable_report(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            status = main(["doctor", "--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["version"], "0.1.0")
        self.assertIn("paths", payload)
        self.assertIn("config", payload["paths"])
        self.assertIn("managedHooksPresent", payload)

    def test_audit_outputs_static_context_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")
            (project / "large.md").write_text("# Large\n" + "line\n" * 320, encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["audit", "--project", directory])

            self.assertEqual(status, 0)
            self.assertIn("Token Optimizer Audit", output.getvalue())
            self.assertIn("large Markdown/docs file", output.getvalue())

    def test_audit_json_outputs_machine_readable_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["audit", "--project", directory, "--json"])

            payload = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertEqual(payload["project"], str(project.resolve()))
            self.assertIn("score", payload)
            self.assertIn("signals", payload)

    def test_dashboard_requires_dry_run_or_yes(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            status = main(["dashboard", "--project", "."])

        self.assertEqual(status, 1)
        self.assertIn("use --dry-run to preview or --yes to write", output.getvalue())

    def test_dashboard_dry_run_outputs_plan_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["dashboard", "--project", directory, "--dry-run", "--json"])

            payload = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertTrue(payload["wouldCreate"])
            self.assertFalse((project / ".codex/token-optimizer/audit-dashboard.html").exists())

    def test_dashboard_yes_writes_static_html(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "README.md").write_text("# Project\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["dashboard", "--project", directory, "--yes", "--json"])

            payload = json.loads(output.getvalue())
            dashboard = project / ".codex/token-optimizer/audit-dashboard.html"
            self.assertEqual(status, 0)
            self.assertFalse(payload["dryRun"])
            self.assertTrue(dashboard.is_file())
            self.assertIn("Token Optimizer Audit Dashboard", dashboard.read_text(encoding="utf-8"))

    def test_benchmark_outputs_static_fixture_report(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            status = main(["benchmark", "--fixture", str(FIXTURE)])

        self.assertEqual(status, 0)
        self.assertIn("Token Optimizer Benchmark", output.getvalue())
        self.assertIn("Measurement label: static_estimate", output.getvalue())
        self.assertIn("Preservation checks:", output.getvalue())

    def test_benchmark_json_outputs_machine_readable_report(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            status = main(["benchmark", "--fixture", str(FIXTURE), "--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["measurementLabel"], "static_estimate")
        self.assertIn("baselineEstimate", payload)
        self.assertIn("optimizedEstimate", payload)
        self.assertIn("preservationChecks", payload)

    def test_benchmark_rejects_missing_fixture(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            status = main(["benchmark", "--fixture", "/no/such/fixture"])

        self.assertEqual(status, 1)
        self.assertIn("benchmark: fixture does not exist", output.getvalue())

    def test_benchmark_requires_fixture_for_static_mode(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            status = main(["benchmark"])

        self.assertEqual(status, 1)
        self.assertIn("benchmark: --fixture is required", output.getvalue())

    def test_anthropic_count_cli_requires_env_key(self) -> None:
        output = io.StringIO()

        with patch.dict("os.environ", {}, clear=True), redirect_stdout(output):
            status = main(
                [
                    "benchmark",
                    "anthropic-count",
                    "--fixture",
                    str(FIXTURE),
                    "--model",
                    "claude-test",
                ]
            )

        self.assertEqual(status, 1)
        self.assertIn("benchmark anthropic-count: ANTHROPIC_API_KEY is required", output.getvalue())

    def test_openai_tiktoken_cli_uses_optional_counter(self) -> None:
        output = io.StringIO()

        with patch(
            "token_optimizer.openai_benchmark.count_text_tokens_with_tiktoken",
            side_effect=lambda text, _model: 100 if "baseline/readme.md" in text else 60,
        ), redirect_stdout(output):
            status = main(
                [
                    "benchmark",
                    "openai-tiktoken",
                    "--fixture",
                    str(FIXTURE),
                    "--model",
                    "gpt-test",
                    "--json",
                ]
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["measurementLabel"], "openai_tokenizer_estimate")
        self.assertEqual(payload["baselineInputTokens"], 100)
        self.assertEqual(payload["optimizedInputTokens"], 60)

    def test_openai_usage_cli_requires_env_key(self) -> None:
        output = io.StringIO()

        with patch.dict("os.environ", {}, clear=True), redirect_stdout(output):
            status = main(
                [
                    "benchmark",
                    "openai-usage",
                    "--fixture",
                    str(FIXTURE),
                    "--model",
                    "gpt-test",
                ]
            )

        self.assertEqual(status, 1)
        self.assertIn("benchmark openai-usage: OPENAI_API_KEY is required", output.getvalue())

    def test_openai_usage_cli_outputs_provider_usage_json(self) -> None:
        output = io.StringIO()

        def fake_create_response(payload: dict[str, object]) -> dict[str, object]:
            if "baseline/readme.md" in str(payload["input"]):
                return {"usage": {"input_tokens": 90, "output_tokens": 1, "total_tokens": 91}}
            return {"usage": {"input_tokens": 40, "output_tokens": 1, "total_tokens": 41}}

        with patch(
            "token_optimizer.openai_benchmark._openai_responses_client_factory",
            return_value=fake_create_response,
        ), patch.dict("os.environ", {"OPENAI_API_KEY": "secret"}, clear=True), redirect_stdout(
            output
        ):
            status = main(
                [
                    "benchmark",
                    "openai-usage",
                    "--fixture",
                    str(FIXTURE),
                    "--model",
                    "gpt-test",
                    "--json",
                ]
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["measurementLabel"], "openai_provider_usage")
        self.assertEqual(payload["baselineInputTokens"], 90)
        self.assertEqual(payload["optimizedInputTokens"], 40)

    def test_hooks_install_dry_run_outputs_file_change_plan_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["hooks", "install", "--project", directory, "--dry-run", "--json"])

            payload = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertEqual(payload["operation"], "install")
            self.assertEqual(payload["action"], "create")
            self.assertTrue(payload["wouldCreate"])
            self.assertFalse((Path(directory) / ".codex/hooks.json").exists())

    def test_hooks_uninstall_dry_run_outputs_file_change_plan_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            hooks = Path(directory) / ".codex/hooks.json"
            hooks.parent.mkdir()
            before = render_hooks_json(merge_managed_block(None))
            hooks.write_text(before, encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(
                    ["hooks", "uninstall", "--project", directory, "--dry-run", "--json"]
                )

            payload = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertEqual(payload["operation"], "uninstall")
            self.assertEqual(payload["action"], "remove")
            self.assertTrue(payload["wouldRemove"])
            self.assertEqual(hooks.read_text(encoding="utf-8"), before)

    def test_hooks_uninstall_without_dry_run_is_rejected(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            status = main(["hooks", "uninstall", "--project", "."])

        self.assertEqual(status, 1)
        self.assertIn("use --dry-run to preview or --yes to apply", output.getvalue())

    def test_hooks_install_yes_creates_hooks_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(
                    [
                        "hooks",
                        "install",
                        "--project",
                        directory,
                        "--yes",
                        "--experimental",
                        "--json",
                    ]
                )

            payload = json.loads(output.getvalue())
            hooks = Path(directory) / ".codex/hooks.json"
            self.assertEqual(status, 0)
            self.assertFalse(payload["dryRun"])
            self.assertTrue(payload["experimental"])
            self.assertEqual(payload["action"], "create")
            self.assertTrue(hooks.is_file())
            self.assertIn("TOKEN_OPTIMIZER_MANAGED", hooks.read_text(encoding="utf-8"))
            self.assertIn("inactive-placeholder-v1", hooks.read_text(encoding="utf-8"))

    def test_hooks_install_yes_requires_experimental_flag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["hooks", "install", "--project", directory, "--yes", "--json"])

            self.assertEqual(status, 1)
            self.assertIn("rerun with --yes --experimental", output.getvalue())
            self.assertFalse((Path(directory) / ".codex/hooks.json").exists())

    def test_hooks_uninstall_yes_removes_managed_hooks_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            hooks = Path(directory) / ".codex/hooks.json"
            hooks.parent.mkdir()
            hooks.write_text(render_hooks_json(merge_managed_block(None)), encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["hooks", "uninstall", "--project", directory, "--yes", "--json"])

            payload = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertFalse(payload["dryRun"])
            self.assertEqual(payload["action"], "remove")
            self.assertFalse(hooks.exists())

    def test_hooks_install_rejects_dry_run_and_yes_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["hooks", "install", "--project", directory, "--dry-run", "--yes"])

            self.assertEqual(status, 1)
            self.assertIn("choose either --dry-run or --yes", output.getvalue())

    def test_config_init_dry_run_outputs_plan_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["config", "init", "--project", directory, "--dry-run", "--json"])

            payload = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertTrue(payload["wouldCreateConfig"])
            self.assertFalse((project / ".codex/token-optimizer.json").exists())

    def test_config_init_yes_writes_project_local_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["config", "init", "--project", directory, "--yes", "--json"])

            payload = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertFalse(payload["dryRun"])
            self.assertTrue((project / ".codex/token-optimizer.json").is_file())
            self.assertTrue((project / ".codex/token-optimizer").is_dir())

    def test_purge_dry_run_outputs_plan_without_removing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            config = project / ".codex/token-optimizer.json"
            config.parent.mkdir()
            config.write_text("{}", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["purge", "--project", directory, "--dry-run", "--json"])

            payload = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertTrue(payload["wouldRemoveConfig"])
            self.assertTrue(config.exists())

    def test_purge_yes_removes_project_local_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            config = project / ".codex/token-optimizer.json"
            data = project / ".codex/token-optimizer"
            data.mkdir(parents=True)
            config.write_text("{}", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["purge", "--project", directory, "--yes", "--json"])

            payload = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertFalse(payload["dryRun"])
            self.assertFalse(config.exists())
            self.assertFalse(data.exists())
            self.assertFalse((Path(directory) / ".codex/hooks.json").exists())

    def test_purge_yes_reports_os_errors_without_traceback(self) -> None:
        output = io.StringIO()

        with patch("token_optimizer.cli.apply_purge", side_effect=OSError("boom")):
            with redirect_stdout(output):
                status = main(["purge", "--project", ".", "--yes"])

        self.assertEqual(status, 1)
        self.assertIn("purge: boom", output.getvalue())



class DoctorProjectFlagTests(unittest.TestCase):
    def test_doctor_reports_on_explicit_project_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            hooks = project / ".codex/hooks.json"
            hooks.parent.mkdir()
            hooks.write_text(render_hooks_json(merge_managed_block(None)), encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                status = main(["doctor", "--project", str(project), "--json"])

            payload = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertEqual(payload["project"], str(project))
            self.assertTrue(payload["managedHooksPresent"])


if __name__ == "__main__":
    unittest.main()
