# Local Marketplace Verification

Use this checklist when changing the repo-local Token Optimizer plugin packages
or bundled plugin control surfaces.

## Scope

This verifies:

```text
marketplace/plugins/token-optimizer/
.claude-plugin/marketplace.json
plugins/token-optimizer/
```

It does not publish the plugin, change repository visibility, create a release
tag, or install the experimental no-op Stop-hook entry by default.

For user-facing installation notes, see `docs/install-codex.md`,
`docs/install-claude-code.md`, and `docs/install-cli.md`.

## Codex Checklist

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

## Claude Code Checklist

1. Validate the repository-level Claude marketplace catalog.

```bash
claude plugin validate .
```

Expected: validation passes for `.claude-plugin/marketplace.json`.

2. Validate the Claude Code plugin package.

```bash
claude plugin validate ./plugins/token-optimizer
```

Expected: validation passes for
`plugins/token-optimizer/.claude-plugin/plugin.json`.

3. Confirm the Claude package stays skill-only in 0.1.0.

Expected package contents:

- `plugins/token-optimizer/.claude-plugin/plugin.json`
- `plugins/token-optimizer/README.md`
- `plugins/token-optimizer/skills/token-optimizer/SKILL.md`

Expected absent paths:

- `plugins/token-optimizer/.mcp.json`
- `plugins/token-optimizer/hooks/`
- `plugins/token-optimizer/commands/`
- bundled Python CLI scripts or daemons

4. After the GitHub repository becomes public, verify GitHub install from a
fresh Claude Code environment before advertising it as the recommended external
path.

```bash
claude plugin marketplace add avikahana/token-optimizer
claude plugin install token-optimizer@token-optimizer
```

The Claude Code plugin expects the `token-optimizer` CLI to be installed
separately.
