---
name: token-optimizer
description: Use when the user wants to inspect, reduce, or plan around AI coding-session context waste with Token Optimizer; run safe read-only commands first and avoid hooks unless the user explicitly asks for them.
version: 0.1.0
---

# Token Optimizer

Token Optimizer is a local-first context hygiene tool for AI coding sessions.
Use it to inspect project setup, identify context bloat, create explicit
summaries, and manage low-risk project-local hooks only when requested.

## Safety Rules

- Start with read-only commands.
- Prefer `doctor` before any install, hook, or persistence work.
- Do not install hooks unless the user explicitly asks for the advanced
  experimental Stop hook and reviews the dry-run plan.
- Do not use global install paths by default.
- Do not start daemons, live dashboards, network calls, or keepwarm behavior.
- Generate dashboards only through the explicit static file command.
- Keep dashboard output under `.codex/token-optimizer/`.
- Reject hook/config/purge/dashboard paths that escape the selected project
  through symlinks.
- Do not capture raw transcripts, file contents, or tool outputs by default.
- Do not copy third-party implementation code into this project.

## Current Commands

```bash
PYTHONPATH=src python3 -m token_optimizer.cli doctor
PYTHONPATH=src python3 -m token_optimizer.cli audit
PYTHONPATH=src python3 -m token_optimizer.cli audit --json
PYTHONPATH=src python3 -m token_optimizer.cli dashboard --project . --dry-run
PYTHONPATH=src python3 -m token_optimizer.cli outline <file>
PYTHONPATH=src python3 -m token_optimizer.cli summarize README.md SECURITY.md
PYTHONPATH=src python3 -m token_optimizer.cli summarize --git-state
PYTHONPATH=src python3 -m token_optimizer.cli handoff README.md
PYTHONPATH=src python3 -m token_optimizer.cli benchmark --fixture <path>
PYTHONPATH=src python3 -m token_optimizer.cli config init --project . --dry-run
PYTHONPATH=src python3 -m token_optimizer.cli purge --project . --dry-run
PYTHONPATH=src python3 -m token_optimizer.cli hooks install --project . --dry-run
PYTHONPATH=src python3 -m token_optimizer.cli hooks uninstall --project . --dry-run
```

`summarize` is canonical. `handoff` is an alias.

The Stop hook is an advanced experimental opt-in in 0.1.0. Plugin installation
does not enable it. Applying the install requires:

```bash
PYTHONPATH=src python3 -m token_optimizer.cli hooks install --project . --yes --experimental
```

Disable it with:

```bash
PYTHONPATH=src python3 -m token_optimizer.cli hooks uninstall --project . --yes
```

The managed Stop-hook entry names an intentionally no-op command in
`inactive-placeholder-v1` mode. `.codex/hooks.json` is a Token Optimizer-managed
consent record: no current host (Claude Code or Codex CLI) reads or executes
entries in this file, so nothing ever invokes the entry in 0.1.0. Future active
hook behavior requires a new install flow and fresh consent rather than silently
changing old no-op installs.

The Codex plugin also exposes local MCP controls for the same experimental
no-op Stop-hook entry. `token_optimizer_hook_control_app` opens an interactive
MCP control when the host supports MCP UI resources.
`token_optimizer_hook_toggle` remains the native approval-form fallback. Both
paths show the dry-run plan first, require explicit approval, and write only
the project-local `.codex/hooks.json` Token Optimizer managed block.

Live provider benchmarks are explicit optional behavior. The current live
provider command is:

```bash
PYTHONPATH=src python3 -m token_optimizer.cli benchmark anthropic-count --fixture <path> --model <model>
PYTHONPATH=src python3 -m token_optimizer.cli benchmark openai-tiktoken --fixture <path> --model <model>
PYTHONPATH=src python3 -m token_optimizer.cli benchmark openai-usage --fixture <path> --model <model>
```

`anthropic-count` requires `ANTHROPIC_API_KEY` in the environment and must not
be treated as a default offline workflow. `openai-tiktoken` uses an optional
local `tiktoken` dependency and does not call OpenAI. `openai-usage` requires
`OPENAI_API_KEY` in the environment, sends only explicit fixture text with
`store=false`, and reports `openai_provider_usage`.

## Recommended Workflow

1. Run `doctor` to inspect project-local paths and hook state.
2. Use `audit`, `outline`, `summarize`, and `benchmark` only with explicit
   project inputs.
3. Before any mutating action, require dry-run output that shows exact planned
   paths and managed blocks.
4. After changes, verify uninstall or cleanup behavior.

## Implementation State

The safe CLI baseline, explicit optimization commands, provider-neutral
benchmark runner, static dashboard, config/data persistence, purge, optional
git-state summary, optional live Anthropic count-tokens command, optional
OpenAI `tiktoken` command, optional live OpenAI provider-usage command,
marketplace assets, and Codex plugin with local hook control plus an
MCP control surface are implemented.
Stop-hook entry installation is gated behind advanced `--experimental` consent
and invokes an intentionally no-op command in 0.1.0.
Post-review safety hardening rejects symlinked parent escapes, stale apply
plans, malformed non-UTF hooks crashes, and arbitrary dashboard overwrite paths.
