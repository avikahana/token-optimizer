# Token Optimizer Claude Code Plugin

Token Optimizer's Claude Code plugin provides native Claude Code skill guidance
for the `token-optimizer` CLI.

The plugin is intentionally skill-only in 0.1.0. It does not install hooks, start
an MCP server, bundle a daemon, or ship the Python CLI binary. Install the CLI
separately from the Token Optimizer source/package, then use the plugin skill to
choose safe read-only commands first.

## Local Testing

From the repository root:

```bash
claude --plugin-dir ./plugins/token-optimizer
```

Validate the plugin package with:

```bash
claude plugin validate ./plugins/token-optimizer
```

Validate the marketplace catalog with:

```bash
claude plugin validate .
```
