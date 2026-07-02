# Marketplace layout

This directory packages the Codex marketplace listing for Token Optimizer.

- `.agents/plugins/marketplace.json` is the primary marketplace manifest.
- `marketplace.json` is a compatibility copy of the same manifest.
- `plugins/token-optimizer/` is the plugin package, kept byte-identical to the
  root plugin files (enforced by `tests/test_plugin_manifest.py`; sync with
  `scripts/sync_mirrors.py`).

## Path resolution note

The plugin entry uses `"path": "./plugins/token-optimizer"`. That path is
written relative to this `marketplace/` directory (the marketplace root), not
relative to the manifest's own `.agents/plugins/` directory. Hosts that
resolve plugin paths relative to the manifest file location will not find the
package; if a host does that, either move the manifest or adjust the path for
that host's semantics before publishing.
