from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path


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
        self.assertTrue((plugin_root / "assets/icon.png").is_file())
        self.assertTrue((plugin_root / "assets/screenshot-dashboard.png").is_file())
        self.assertNotIn("hooks", manifest)
        self.assertNotIn("apps", manifest)

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
                self.assertIn("token_optimizer_hook_toggle", {tool["name"] for tool in tools})

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
                    "Enable experimental inactive Stop hook",
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
