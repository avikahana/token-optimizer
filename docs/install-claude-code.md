# Install The Claude Code Plugin

Token Optimizer ships a Claude Code native package at `plugins/token-optimizer/`.
The 0.2.0 Claude Code package is intentionally skill-only.

It does not bundle the Python CLI, install hooks, start an MCP server, start a
daemon, or add background behavior. Install the `token-optimizer` CLI separately
before relying on the Claude Code skill in normal projects.

## Install The CLI First

Use the source checkout or GitHub source install from `docs/install-cli.md`.
Then verify:

```bash
token-optimizer --version
token-optimizer doctor
```

## Install From GitHub Marketplace Source

After the repository is public or otherwise available to your Claude Code
environment:

```bash
claude plugin marketplace add avikahana/token-optimizer
claude plugin install token-optimizer@token-optimizer
```

Before advertising this as the recommended external install path, verify it from
a fresh Claude Code environment after repository visibility changes.

## Local Development Verification

From the repository root, validate the marketplace catalog and plugin package:

```bash
claude plugin validate .
claude plugin validate ./plugins/token-optimizer
```

Run Claude Code with the local plugin package for development checks:

```bash
claude --plugin-dir ./plugins/token-optimizer
```

## What The Package Includes

- `plugins/token-optimizer/.claude-plugin/plugin.json`
- `plugins/token-optimizer/README.md`
- `plugins/token-optimizer/skills/token-optimizer/SKILL.md`

## What The Package Does Not Include

- bundled Python CLI binary
- hook installation
- MCP server
- commands package
- daemon or background process

## Recommended First Use

Ask Claude Code to use safe read-only commands first:

```bash
token-optimizer doctor
token-optimizer audit --project .
token-optimizer outline README.md
token-optimizer summarize README.md SECURITY.md
```

Mutating workflows such as dashboard writes, config init, purge, or hook-control
operations should be reviewed through dry-run output before applying them.
