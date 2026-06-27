from __future__ import annotations

import json
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
        self.assertNotIn("hooks", manifest)
        self.assertNotIn("mcpServers", manifest)
        self.assertNotIn("apps", manifest)
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
        self.assertEqual(manifest["interface"]["composerIcon"], "./assets/icon.png")
        self.assertTrue((plugin_root / "skills/token-optimizer/SKILL.md").is_file())
        self.assertTrue((plugin_root / "assets/icon.png").is_file())
        self.assertTrue((plugin_root / "assets/screenshot-dashboard.png").is_file())
        self.assertNotIn("hooks", manifest)
        self.assertNotIn("mcpServers", manifest)
        self.assertNotIn("apps", manifest)


if __name__ == "__main__":
    unittest.main()
