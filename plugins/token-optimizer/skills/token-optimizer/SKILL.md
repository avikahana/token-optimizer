---
name: token-optimizer
description: This skill should be used when the user asks to "run Token Optimizer", "inspect context bloat", "summarize files for handoff", "generate a token optimizer report", "benchmark context usage", or "manage Token Optimizer hooks" in Claude Code.
version: 0.2.0
---

# Token Optimizer

Token Optimizer is a local-first context hygiene tool for AI coding sessions.
Use it to inspect project setup, identify context bloat, create explicit
summaries, generate local audit dashboards, and manage low-risk project-local
hook state only when explicitly requested.

This Claude Code plugin provides workflow guidance for the `token-optimizer`
CLI. It does not bundle the Python CLI binary, install hooks, start an MCP
server, or add background automation in 0.2.0.

## Safety Rules

- Start with read-only commands.
- Prefer `token-optimizer doctor` before install, hook, persistence, or cleanup
  work.
- Keep default workflows local-only.
- Do not start daemons, live dashboards, network calls, or keepwarm behavior.
- Do not capture raw transcripts, raw file contents, or raw tool outputs by
  default.
- Use explicit project paths or explicit input files.
- Generate dashboards only through the explicit static file command.
- Keep dashboard output under `.codex/token-optimizer/`.
- Do not install hooks unless the user explicitly asks for the advanced
  experimental Stop hook and reviews the dry-run plan.
- Before any mutating action, show or inspect the dry-run output first.
- Do not copy third-party implementation code into the project.

## CLI Availability

Before using Token Optimizer commands, confirm the CLI is available:

```bash
token-optimizer --version
```

If the command is unavailable in a source checkout, use the module form from the
repository root:

```bash
PYTHONPATH=src python3 -m token_optimizer.cli --version
```

Prefer installed `token-optimizer` commands in ordinary Claude Code projects.
Use the `PYTHONPATH=src python3 -m token_optimizer.cli ...` form only when
working inside the Token Optimizer source checkout.

## Read-Only Workflow

Start with these commands:

```bash
token-optimizer doctor
token-optimizer audit --project .
token-optimizer audit --project . --json
token-optimizer outline README.md
token-optimizer summarize README.md SECURITY.md
token-optimizer summarize --git-state README.md
token-optimizer benchmark --fixture <fixture-path>
```

For `benchmark`, pass an explicit fixture directory containing `baseline/`,
`optimized/`, and `must-preserve.md`. Sample fixtures such as
`benchmarks/fixtures/common-python-cli-session` exist only inside a checkout of
the token-optimizer source repository, not in ordinary user projects.

Use `outline` before rereading large Markdown or Python files. Use `summarize`
for compact continuation notes from explicit files. Treat `handoff` as an alias
for `summarize`; prefer `summarize` in new instructions.

## Static Dashboard

Generate a local audit dashboard only after dry-run review:

```bash
token-optimizer dashboard --project . --dry-run
token-optimizer dashboard --project . --yes
```

The dashboard is a static HTML file under `.codex/token-optimizer/`. It does not
start a server or background process.

## Project-Local State

Inspect config and cleanup plans before writing:

```bash
token-optimizer config init --project . --dry-run
token-optimizer purge --project . --dry-run
```

Apply only after explicit user approval:

```bash
token-optimizer config init --project . --yes
token-optimizer purge --project . --yes
```

## Hook Handling

Treat hooks as advanced and experimental in 0.2.0. The managed Stop-hook entry
is intentionally no-op and uses `inactive-placeholder-v1`. The managed block
lives in `.codex/hooks.json`, which is a Token Optimizer-managed consent
record: no current host (Claude Code or Codex CLI) reads or executes entries
in this file, so nothing ever invokes the entry. Future active hook behavior
requires a new install flow and fresh consent.

Inspect first:

```bash
token-optimizer hooks install --project . --dry-run
token-optimizer hooks uninstall --project . --dry-run
```

Apply only when the user explicitly requests the experimental hook and approves
the dry-run plan:

```bash
token-optimizer hooks install --project . --yes --experimental
token-optimizer hooks uninstall --project . --yes
```

Do not silently install, upgrade, or activate hooks from plugin installation.

## Provider Benchmarks

Keep provider numbers separate from static estimates:

```bash
token-optimizer benchmark --fixture <path>
token-optimizer benchmark anthropic-count --fixture <path> --model <model>
token-optimizer benchmark openai-tiktoken --fixture <path> --model <model>
token-optimizer benchmark openai-usage --fixture <path> --model <model>
```

- `benchmark --fixture` reports provider-neutral `static_estimate`.
- `anthropic-count` requires `ANTHROPIC_API_KEY` and reports
  `anthropic_count_tokens`.
- `openai-tiktoken` uses an optional local tokenizer dependency and reports
  `openai_tokenizer_estimate`.
- `openai-usage` requires `OPENAI_API_KEY`, sends only explicit fixture text
  with `store=false`, and reports `openai_provider_usage`.

Do not blend these labels into one headline number.

## Recommended Response Pattern

When a user asks for Token Optimizer help in Claude Code:

1. Confirm the project root and whether the CLI is installed.
2. Run or suggest `token-optimizer doctor`.
3. Use read-only `audit`, `outline`, `summarize`, or `benchmark` commands with
   explicit inputs.
4. For dashboard/config/purge/hook changes, inspect `--dry-run` output first.
5. Apply mutating commands only after explicit approval.
6. Report exactly which paths were read or written.
