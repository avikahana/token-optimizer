# Install The Codex Plugin

Token Optimizer ships a native Codex plugin package. The plugin provides safe
workflow guidance and a local MCP hook-control surface for the experimental
project-local Stop-hook entry.

The Codex plugin does not install hooks by default, start a daemon, or add a
networked service.

## Install From GitHub Marketplace Source

After the repository is public or otherwise available to your Codex environment,
add the repository marketplace and install the plugin:

```bash
codex plugin marketplace add avikahana/token-optimizer --sparse marketplace
codex plugin add token-optimizer@token-optimizer-local
```

Start a fresh Codex thread after installing or reinstalling. Codex loads plugin
state when a thread starts, so already-open threads may show stale prompts,
tools, or MCP metadata.

## Local Development Verification

For local repo verification, use:

```bash
codex plugin marketplace list
codex plugin remove token-optimizer@token-optimizer-local --json
codex plugin add token-optimizer@token-optimizer-local --json
```

Then compare the source package under `marketplace/plugins/token-optimizer/`
with the installed cache under
`~/.codex/plugins/cache/token-optimizer-local/token-optimizer/0.1.0/`.

The full local checklist lives in `docs/local-marketplace-verification.md`.

## What The Plugin Includes

- `.codex-plugin/plugin.json`
- safe usage skill guidance
- marketplace assets
- `.mcp.json`
- local stdio MCP server under `mcp/`
- hook-control widget resource for hosts that render MCP UI resources
- native approval-form fallback for hook-control actions

## What The Plugin Does Not Include

- default hook installation
- global hooks
- daemons or background services
- networked control surfaces
- raw transcript capture
- raw file-content persistence
- raw tool-output persistence

## Hook-Control Boundary

The visual and native hook-control paths only install or remove Token
Optimizer-managed content in project-local `.codex/hooks.json`, and only after
explicit approval. The installed 0.1.0 Stop-hook entry invokes an intentionally
no-op command.

The MCP server refuses to write outside its workspace root. By default the
root is the server process working directory (the `cwd` in `.mcp.json`); set
the `TOKEN_OPTIMIZER_WORKSPACE_ROOT` environment variable to pin it explicitly
when the host does not honor `cwd`. The server logs the resolved root to
stderr at startup.

Use the CLI directly for ordinary read-only checks:

```bash
token-optimizer doctor
token-optimizer audit --project .
token-optimizer dashboard --project . --dry-run
```
