from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

from token_optimizer.doctor import MANAGED_MARKER
from token_optimizer.hooks import INACTIVE_PLACEHOLDER_HOOK_MODE, MANAGED_COMMAND


class PluginManifestTests(unittest.TestCase):
    REPOSITORY_URL = "https://github.com/avikahana/token-optimizer"
    PRIVACY_URL = "https://github.com/avikahana/token-optimizer/blob/main/PRIVACY.md"
    TERMS_URL = "https://github.com/avikahana/token-optimizer/blob/main/TERMS.md"

    def test_plugin_manifest_has_safe_initial_shape(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / ".codex-plugin/plugin.json").read_text())

        self.assertEqual(manifest["name"], "token-optimizer")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(manifest["license"], "Apache-2.0")
        self.assertEqual(manifest["homepage"], self.REPOSITORY_URL)
        self.assertEqual(manifest["repository"], self.REPOSITORY_URL)
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["mcpServers"], "./.mcp.json")
        self.assertNotIn("hooks", manifest)
        self.assertNotIn("apps", manifest)
        self.assertIn("Interactive hook control", manifest["interface"]["capabilities"])
        self.assertIn("MCP control", manifest["interface"]["capabilities"])
        self.assertEqual(manifest["interface"]["displayName"], "Token Optimizer")
        self.assertEqual(manifest["interface"]["websiteURL"], self.REPOSITORY_URL)
        self.assertEqual(manifest["interface"]["privacyPolicyURL"], self.PRIVACY_URL)
        self.assertEqual(manifest["interface"]["termsOfServiceURL"], self.TERMS_URL)
        self.assertEqual(manifest["interface"]["composerIcon"], "./assets/icon.png")
        self.assertEqual(manifest["interface"]["logo"], "./assets/logo.png")
        self.assertEqual(manifest["interface"]["logoDark"], "./assets/logo-dark.png")
        self.assertEqual(
            manifest["interface"]["screenshots"],
            ["./assets/screenshot-dashboard.png"],
        )
        for asset in (
            "assets/icon.png",
            "assets/logo.png",
            "assets/logo-dark.png",
            "assets/screenshot-dashboard.png",
        ):
            self.assertTrue((root / asset).is_file())

    def test_package_metadata_uses_approved_license(self) -> None:
        root = Path(__file__).resolve().parents[1]
        metadata = tomllib.loads((root / "pyproject.toml").read_text())

        self.assertEqual(metadata["project"]["license"], "Apache-2.0")
        self.assertTrue((root / "LICENSE").is_file())

    def test_package_metadata_uses_approved_urls(self) -> None:
        root = Path(__file__).resolve().parents[1]
        metadata = tomllib.loads((root / "pyproject.toml").read_text())

        self.assertEqual(metadata["project"]["urls"]["Homepage"], self.REPOSITORY_URL)
        self.assertEqual(metadata["project"]["urls"]["Repository"], self.REPOSITORY_URL)
        self.assertEqual(metadata["project"]["urls"]["Privacy"], self.PRIVACY_URL)
        self.assertEqual(metadata["project"]["urls"]["Terms"], self.TERMS_URL)

    def test_plugin_skill_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]

        self.assertTrue((root / "skills/token-optimizer/SKILL.md").is_file())

    def test_claude_marketplace_entry_shape(self) -> None:
        root = Path(__file__).resolve().parents[1]
        marketplace = json.loads((root / ".claude-plugin/marketplace.json").read_text())

        self.assertEqual(marketplace["name"], "token-optimizer")
        self.assertEqual(marketplace["owner"]["name"], "Avi Kahana")
        self.assertEqual(len(marketplace["plugins"]), 1)

        entry = marketplace["plugins"][0]
        self.assertEqual(entry["name"], "token-optimizer")
        self.assertEqual(entry["source"], "./plugins/token-optimizer")
        self.assertEqual(entry["displayName"], "Token Optimizer")
        self.assertEqual(entry["homepage"], self.REPOSITORY_URL)
        self.assertEqual(entry["repository"], self.REPOSITORY_URL)
        self.assertEqual(entry["license"], "Apache-2.0")
        self.assertNotIn("version", entry)

    def test_claude_plugin_package_is_skill_only(self) -> None:
        root = Path(__file__).resolve().parents[1]
        plugin_root = root / "plugins/token-optimizer"
        manifest = json.loads((plugin_root / ".claude-plugin/plugin.json").read_text())

        self.assertEqual(manifest["name"], "token-optimizer")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(manifest["license"], "Apache-2.0")
        self.assertEqual(manifest["homepage"], self.REPOSITORY_URL)
        self.assertEqual(manifest["repository"], self.REPOSITORY_URL)
        self.assertTrue((plugin_root / "skills/token-optimizer/SKILL.md").is_file())
        self.assertTrue((plugin_root / "README.md").is_file())
        self.assertFalse((plugin_root / ".mcp.json").exists())
        self.assertFalse((plugin_root / "hooks").exists())
        self.assertFalse((plugin_root / "commands").exists())
        self.assertNotIn("mcpServers", manifest)
        self.assertNotIn("hooks", manifest)
        self.assertNotIn("commands", manifest)

    def test_repo_local_marketplace_entry_shape(self) -> None:
        root = Path(__file__).resolve().parents[1]
        marketplace = json.loads(
            (root / "marketplace/.agents/plugins/marketplace.json").read_text()
        )

        self.assertEqual(marketplace["name"], "token-optimizer-local")
        self.assertEqual(
            marketplace["interface"]["displayName"], "Token Optimizer Local"
        )
        self.assertEqual(len(marketplace["plugins"]), 1)

        entry = marketplace["plugins"][0]
        self.assertEqual(entry["name"], "token-optimizer")
        self.assertEqual(entry["source"], {
            "source": "local",
            "path": "./plugins/token-optimizer",
        })
        self.assertEqual(entry["policy"], {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        })
        self.assertEqual(entry["category"], "Productivity")

    def test_compatibility_marketplace_entry_matches_primary_manifest(self) -> None:
        root = Path(__file__).resolve().parents[1]
        primary = json.loads(
            (root / "marketplace/.agents/plugins/marketplace.json").read_text()
        )
        compatibility = json.loads((root / "marketplace/marketplace.json").read_text())

        self.assertEqual(compatibility, primary)

    def test_repo_local_marketplace_plugin_copy_matches_manifest_identity(self) -> None:
        root = Path(__file__).resolve().parents[1]
        plugin_root = root / "marketplace/plugins/token-optimizer"
        manifest = json.loads((plugin_root / ".codex-plugin/plugin.json").read_text())

        self.assertEqual(manifest["name"], "token-optimizer")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(manifest["license"], "Apache-2.0")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["mcpServers"], "./.mcp.json")
        self.assertEqual(manifest["interface"]["composerIcon"], "./assets/icon.png")
        self.assertTrue((plugin_root / "skills/token-optimizer/SKILL.md").is_file())
        self.assertTrue((plugin_root / ".mcp.json").is_file())
        self.assertTrue((plugin_root / "mcp/server.mjs").is_file())
        self.assertTrue((plugin_root / "mcp/hook-control-widget.html").is_file())
        self.assertTrue((plugin_root / "assets/icon.png").is_file())
        self.assertTrue((plugin_root / "assets/screenshot-dashboard.png").is_file())
        self.assertNotIn("hooks", manifest)
        self.assertNotIn("apps", manifest)

    def test_repo_local_marketplace_package_matches_root_plugin_files(self) -> None:
        root = Path(__file__).resolve().parents[1]
        plugin_root = root / "marketplace/plugins/token-optimizer"
        mirrored_files = (
            ".codex-plugin/plugin.json",
            ".mcp.json",
            "mcp/server.mjs",
            "mcp/hook-control-widget.html",
            "skills/token-optimizer/SKILL.md",
            "assets/icon.png",
            "assets/logo.png",
            "assets/logo-dark.png",
            "assets/screenshot-dashboard.png",
        )

        for relative_path in mirrored_files:
            with self.subTest(relative_path=relative_path):
                self.assertEqual(
                    (root / relative_path).read_bytes(),
                    (plugin_root / relative_path).read_bytes(),
                )

    def test_skill_frontmatter_name_matches_directory_in_every_copy(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for relative_path in (
            "skills/token-optimizer/SKILL.md",
            "plugins/token-optimizer/skills/token-optimizer/SKILL.md",
            "marketplace/plugins/token-optimizer/skills/token-optimizer/SKILL.md",
        ):
            with self.subTest(relative_path=relative_path):
                text = (root / relative_path).read_text(encoding="utf-8")
                self.assertTrue(
                    text.startswith("---\nname: token-optimizer\n"),
                    f"{relative_path} frontmatter name must be token-optimizer",
                )

    def test_claude_plugin_manifest_has_no_undocumented_fields(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads(
            (root / "plugins/token-optimizer/.claude-plugin/plugin.json").read_text()
        )

        self.assertNotIn("defaultEnabled", manifest)

    def test_claude_plugin_skill_shares_core_safety_rules(self) -> None:
        # The plugins/ (Claude Code) skill copy is intentionally worded for
        # Claude Code and is not byte-identical to the root skill, so pin the
        # shared safety invariants instead of full file equality.
        root = Path(__file__).resolve().parents[1]
        text = (
            root / "plugins/token-optimizer/skills/token-optimizer/SKILL.md"
        ).read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        invariants = (
            "Start with read-only commands.",
            "Do not start daemons, live dashboards, network calls, or keepwarm behavior.",
            "no current host (Claude Code or Codex CLI) reads or executes entries in this file",
            "requires a new install flow and fresh consent",
            "Do not install hooks unless the user explicitly asks for the advanced "
            "experimental Stop hook and reviews the dry-run plan.",
        )
        for invariant in invariants:
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, normalized)

    def test_plugin_mcp_config_points_to_local_server(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / ".mcp.json").read_text())

        server = config["mcpServers"]["token-optimizer-hook-control"]
        self.assertEqual(server["cwd"], ".")
        self.assertEqual(server["command"], "node")
        self.assertEqual(server["args"], ["./mcp/server.mjs"])
        self.assertTrue((root / "mcp/server.mjs").is_file())

    def test_hook_toggle_mcp_server_installs_and_uninstalls_inactive_hook(self) -> None:
        node = os.environ.get("NODE_BINARY") or shutil.which("node")
        if node is None:
            self.skipTest("node is required to test the plugin MCP server")
        root = Path(__file__).resolve().parents[1]
        server_path = root / "mcp/server.mjs"
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            process = subprocess.Popen(
                [node, str(server_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                cwd=project,
            )
            try:
                self._send_mcp(process, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
                initialize = self._read_mcp(process)
                self.assertEqual(
                    initialize["result"]["serverInfo"]["name"],
                    "Token Optimizer Hook Control",
                )

                self._send_mcp(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
                tools = self._read_mcp(process)["result"]["tools"]
                tools_by_name = {tool["name"]: tool for tool in tools}
                self.assertIn("token_optimizer_hook_toggle", tools_by_name)
                self.assertIn("token_optimizer_hook_control_app", tools_by_name)
                self.assertIn("token_optimizer_hook_apply", tools_by_name)
                self.assertIn(
                    "token_optimizer_hook_control_app",
                    initialize["result"]["instructions"],
                )
                self.assertEqual(
                    tools_by_name["token_optimizer_hook_control_app"]["_meta"]["ui"]["resourceUri"],
                    "ui://token-optimizer/hook-control.html",
                )
                self.assertEqual(
                    tools_by_name["token_optimizer_hook_apply"]["_meta"]["ui"]["visibility"],
                    ["app"],
                )

                self._send_mcp(process, {"jsonrpc": "2.0", "id": 20, "method": "resources/list", "params": {}})
                resources = self._read_mcp(process)["result"]["resources"]
                self.assertIn("ui://token-optimizer/hook-control.html", {resource["uri"] for resource in resources})

                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 21,
                        "method": "resources/read",
                        "params": {"uri": "ui://token-optimizer/hook-control.html"},
                    },
                )
                resource = self._read_mcp(process)["result"]["contents"][0]
                self.assertEqual(resource["mimeType"], "text/html;profile=mcp-app")
                self.assertIn("Token Optimizer Hook Control", resource["text"])
                self.assertIn("token_optimizer_hook_apply", resource["text"])
                self.assertIn("Install no-op hook entry", resource["text"])
                self.assertIn("reviewedPlanDigest", resource["text"])
                self.assertIn("trustedParentOrigin", resource["text"])
                self.assertIn("window.parent.postMessage(message, trustedParentOrigin)", resource["text"])
                self.assertIn("event.origin !== trustedParentOrigin", resource["text"])
                self.assertIn("Host bridge origin is unavailable.", resource["text"])
                self.assertNotIn('postMessage({ jsonrpc: "2.0", method, params }, "*")', resource["text"])

                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 22,
                        "method": "tools/call",
                        "params": {
                            "name": "token_optimizer_hook_control_app",
                            "arguments": {"projectPath": str(project)},
                        },
                    },
                )
                app_result = self._read_mcp(process)["result"]
                self.assertEqual(app_result["_meta"]["ui"]["resourceUri"], "ui://token-optimizer/hook-control.html")
                self.assertEqual(app_result["structuredContent"]["status"], "disabled")
                managed_block = json.loads(app_result["structuredContent"]["installPlan"]["after"])
                self.assertEqual(managed_block["_tokenOptimizer"]["marker"], MANAGED_MARKER)
                self.assertEqual(
                    managed_block["_tokenOptimizer"]["behavior"],
                    INACTIVE_PLACEHOLDER_HOOK_MODE,
                )
                self.assertEqual(
                    managed_block["Stop"][0]["hooks"][0]["command"],
                    MANAGED_COMMAND,
                )
                install_digest = app_result["structuredContent"]["installPlan"]["planDigest"]
                self.assertEqual(len(install_digest), 64)

                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 23,
                        "method": "tools/call",
                        "params": {
                            "name": "token_optimizer_hook_apply",
                            "arguments": {
                                "projectPath": str(project),
                                "enabled": True,
                                "reviewedDryRun": False,
                            },
                        },
                    },
                )
                not_approved = self._read_mcp(process)["result"]["structuredContent"]
                self.assertEqual(not_approved["status"], "not_approved")
                self.assertFalse((project / ".codex/hooks.json").exists())

                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 26,
                        "method": "tools/call",
                        "params": {
                            "name": "token_optimizer_hook_apply",
                            "arguments": {
                                "projectPath": str(project),
                                "enabled": True,
                                "reviewedDryRun": True,
                                "reviewedPlanDigest": "stale",
                            },
                        },
                    },
                )
                stale_plan = self._read_mcp(process)["result"]["structuredContent"]
                self.assertEqual(stale_plan["status"], "stale_plan")
                self.assertFalse((project / ".codex/hooks.json").exists())

                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 24,
                        "method": "tools/call",
                        "params": {
                            "name": "token_optimizer_hook_apply",
                            "arguments": {
                                "projectPath": str(project),
                                "enabled": True,
                                "reviewedDryRun": True,
                                "reviewedPlanDigest": install_digest,
                            },
                        },
                    },
                )
                approval = self._read_mcp(process)
                self.assertEqual(approval["method"], "elicitation/create")
                self.assertIn("Token Optimizer hook-control app approval", approval["params"]["message"])
                self.assertIn("Requested state: installed", approval["params"]["message"])
                self.assertEqual(
                    approval["params"]["requestedSchema"]["properties"]["approveChange"]["title"],
                    "I approve this project-local hook change",
                )
                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": approval["id"],
                        "result": {
                            "action": "accept",
                            "content": {"approveChange": False},
                        },
                    },
                )
                cancelled = self._read_mcp(process)["result"]["structuredContent"]
                self.assertEqual(cancelled["status"], "cancelled")
                self.assertFalse((project / ".codex/hooks.json").exists())

                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 27,
                        "method": "tools/call",
                        "params": {
                            "name": "token_optimizer_hook_apply",
                            "arguments": {
                                "projectPath": str(project),
                                "enabled": True,
                                "reviewedDryRun": True,
                                "reviewedPlanDigest": install_digest,
                            },
                        },
                    },
                )
                approval = self._read_mcp(process)
                self.assertEqual(approval["method"], "elicitation/create")
                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": approval["id"],
                        "result": {
                            "action": "accept",
                            "content": {"approveChange": True},
                        },
                    },
                )
                app_apply = self._read_mcp(process)["result"]["structuredContent"]
                self.assertTrue(app_apply["enabled"])
                self.assertTrue((project / ".codex/hooks.json").exists())
                uninstall_digest = app_apply["uninstallPlan"]["planDigest"]

                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 25,
                        "method": "tools/call",
                        "params": {
                            "name": "token_optimizer_hook_apply",
                            "arguments": {
                                "projectPath": str(project),
                                "enabled": False,
                                "reviewedDryRun": True,
                                "reviewedPlanDigest": uninstall_digest,
                            },
                        },
                    },
                )
                approval = self._read_mcp(process)
                self.assertEqual(approval["method"], "elicitation/create")
                self.assertIn("Requested state: not installed", approval["params"]["message"])
                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": approval["id"],
                        "result": {
                            "action": "accept",
                            "content": {"approveChange": True},
                        },
                    },
                )
                app_disable = self._read_mcp(process)["result"]["structuredContent"]
                self.assertFalse(app_disable["enabled"])
                self.assertFalse((project / ".codex/hooks.json").exists())

                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "token_optimizer_hook_toggle",
                            "arguments": {"projectPath": str(project)},
                        },
                    },
                )
                request = self._read_mcp(process)
                self.assertEqual(request["method"], "elicitation/create")
                message = request["params"]["message"]
                self.assertIn("If switched ON:", message)
                self.assertIn("If switched OFF:", message)
                self.assertIn("Target file: .codex/hooks.json", message)
                self.assertIn("Command: token-optimizer summarize --hook stop --hook-mode inactive-placeholder-v1", message)
                self.assertNotIn("Planned hooks file:", message)
                self.assertNotIn("_tokenOptimizer", message)
                schema = request["params"]["requestedSchema"]
                self.assertEqual(
                    schema["properties"]["enabled"]["title"],
                    "Install experimental no-op Stop-hook entry",
                )
                self.assertEqual(schema["properties"]["enabled"]["type"], "boolean")
                self.assertEqual(schema["properties"]["reviewedDryRun"]["type"], "boolean")

                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": request["id"],
                        "result": {
                            "action": "accept",
                            "content": {"enabled": True, "reviewedDryRun": True},
                        },
                    },
                )
                result = self._read_mcp(process)
                self.assertEqual(result["result"]["structuredContent"]["status"], "enabled")
                hooks = project / ".codex/hooks.json"
                self.assertIn(
                    "token-optimizer summarize --hook stop --hook-mode inactive-placeholder-v1",
                    hooks.read_text(encoding="utf-8"),
                )

                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 4,
                        "method": "tools/call",
                        "params": {
                            "name": "token_optimizer_hook_toggle",
                            "arguments": {"projectPath": str(project)},
                        },
                    },
                )
                request = self._read_mcp(process)
                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": request["id"],
                        "result": {
                            "action": "accept",
                            "content": {"enabled": False, "reviewedDryRun": True},
                        },
                    },
                )
                result = self._read_mcp(process)
                self.assertEqual(result["result"]["structuredContent"]["status"], "disabled")
                self.assertFalse(hooks.exists())
            finally:
                if process.stdin is not None:
                    process.stdin.close()
                if process.stdout is not None:
                    process.stdout.close()
                process.kill()
                process.wait(timeout=5)

    def test_hook_apply_and_toggle_never_write_when_state_already_matches(self) -> None:
        node = os.environ.get("NODE_BINARY") or shutil.which("node")
        if node is None:
            self.skipTest("node is required to test the plugin MCP server")
        root = Path(__file__).resolve().parents[1]
        server_path = root / "mcp/server.mjs"
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            hooks_path = project / ".codex/hooks.json"
            hooks_path.parent.mkdir()
            # Installed state whose on-disk content diverges from the canonical
            # rendering (legacy command, unsorted keys), so a fresh install plan
            # is action "update" and a consent-free rewrite would be observable.
            divergent = json.dumps(
                {
                    "_tokenOptimizer": {"marker": MANAGED_MARKER},
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
            hooks_path.write_text(divergent, encoding="utf-8")
            process = subprocess.Popen(
                [node, str(server_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                cwd=project,
            )
            try:
                self._send_mcp(process, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
                self._read_mcp(process)

                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "token_optimizer_hook_apply",
                            "arguments": {
                                "projectPath": str(project),
                                "enabled": True,
                                "reviewedDryRun": False,
                                "reviewedPlanDigest": "",
                            },
                        },
                    },
                )
                apply_result = self._read_mcp(process)["result"]["structuredContent"]
                self.assertEqual(apply_result["status"], "noop")
                self.assertEqual(hooks_path.read_text(encoding="utf-8"), divergent)

                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "token_optimizer_hook_toggle",
                            "arguments": {"projectPath": str(project)},
                        },
                    },
                )
                request = self._read_mcp(process)
                self.assertEqual(request["method"], "elicitation/create")
                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": request["id"],
                        "result": {
                            "action": "accept",
                            "content": {"enabled": True, "reviewedDryRun": False},
                        },
                    },
                )
                toggle_result = self._read_mcp(process)["result"]["structuredContent"]
                self.assertEqual(toggle_result["status"], "noop")
                self.assertEqual(hooks_path.read_text(encoding="utf-8"), divergent)
            finally:
                if process.stdin is not None:
                    process.stdin.close()
                if process.stdout is not None:
                    process.stdout.close()
                process.kill()
                process.wait(timeout=5)

    def test_hook_toggle_mcp_server_rejects_project_outside_workspace(self) -> None:
        node = os.environ.get("NODE_BINARY") or shutil.which("node")
        if node is None:
            self.skipTest("node is required to test the plugin MCP server")
        root = Path(__file__).resolve().parents[1]
        server_path = root / "mcp/server.mjs"
        with tempfile.TemporaryDirectory() as directory:
            temp_root = Path(directory)
            workspace = temp_root / "workspace"
            outside = temp_root / "outside"
            workspace.mkdir()
            outside.mkdir()
            process = subprocess.Popen(
                [node, str(server_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                cwd=workspace,
            )
            try:
                self._send_mcp(process, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
                self._read_mcp(process)
                self._send_mcp(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "token_optimizer_hook_status",
                            "arguments": {"projectPath": str(outside)},
                        },
                    },
                )
                response = self._read_mcp(process)
                self.assertEqual(response["error"]["code"], -32602)
                self.assertIn("MCP workspace root", response["error"]["message"])
            finally:
                if process.stdin is not None:
                    process.stdin.close()
                if process.stdout is not None:
                    process.stdout.close()
                process.kill()
                process.wait(timeout=5)

    @staticmethod
    def _send_mcp(process: subprocess.Popen[str], message: dict[str, object]) -> None:
        assert process.stdin is not None
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    @staticmethod
    def _read_mcp(process: subprocess.Popen[str]) -> dict[str, object]:
        assert process.stdout is not None
        line = process.stdout.readline()
        if not line:
            raise AssertionError("MCP server produced no response")
        return json.loads(line)


if __name__ == "__main__":
    unittest.main()
