# Local Marketplace Verification

Use this checklist when changing the repo-local Token Optimizer plugin package
or its bundled MCP server.

## Scope

This verifies the local marketplace package under:

```text
marketplace/plugins/token-optimizer/
```

It does not publish the plugin, change repository visibility, create a release
tag, or install the experimental no-op Stop-hook entry by default.

## Checklist

1. Confirm the local marketplace root.

```bash
codex plugin marketplace list
```

Expected: `token-optimizer-local` points at this repository's `marketplace/`
directory.

2. Reinstall from the local marketplace after changing plugin files.

```bash
codex plugin remove token-optimizer@token-optimizer-local --json
codex plugin add token-optimizer@token-optimizer-local --json
```

3. Compare the source package and installed cache.

Check that these files match between `marketplace/plugins/token-optimizer/` and
`~/.codex/plugins/cache/token-optimizer-local/token-optimizer/0.1.0/`:

- `.codex-plugin/plugin.json`
- `.mcp.json`
- `mcp/server.mjs`
- `mcp/hook-control-widget.html`
- `skills/token-optimizer/SKILL.md`
- marketplace assets under `assets/`

4. Smoke-test the MCP server protocol.

Verify that:

- `tools/list` includes `token_optimizer_hook_status`,
  `token_optimizer_hook_toggle`, `token_optimizer_hook_control_app`, and
  app-only `token_optimizer_hook_apply`
- `resources/list` includes `ui://token-optimizer/hook-control.html`
- `resources/read` returns `text/html;profile=mcp-app`
- `token_optimizer_hook_control_app` returns `openai/outputTemplate` metadata
  for the widget resource

5. Start a fresh Codex thread after reinstalling.

Codex loads installed plugin cache state at thread start, so already-open
threads may show stale plugin prompts, tools, or MCP metadata.

6. Keep runtime hook state out of commits.

`.codex/hooks.json` is project-local runtime state for hook-control testing.
Do not commit it.
