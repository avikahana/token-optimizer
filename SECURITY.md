# Security

Token Optimizer is designed as a local-first context hygiene tool. The default
commands inspect explicit local project inputs and do not start daemons, install
global hooks, capture raw transcripts, persist raw file contents, persist raw
tool output, or make network requests.

Project scans, mutating commands, and Token Optimizer-owned output paths are
constrained to the selected project. Read-only explicit-input commands such as
`outline` and `summarize` may read absolute local file paths outside the project
when the user names those files directly; those commands print a warning when an
explicit input resolves outside the current or selected project root.

## Default Behavior

- `doctor`, `audit`, `outline`, `summarize`, `handoff`, dashboard dry-runs,
  config dry-runs, purge dry-runs, hook dry-runs, and provider-neutral benchmark
  runs are local-only.
- Mutating CLI commands require an explicit `--yes` flag, and hook installation
  also requires `--experimental`.
- The Codex plugin package does not install hooks by default. It ships a local
  MCP hook-control server that can open an interactive MCP control for the
  experimental Stop-hook entry, with a native approval form as the fallback.
  Both controls show the dry-run plan and write only after explicit approval;
  the installed entry invokes an intentionally no-op command in 0.2.0.
- The Codex plugin package does not ship global hooks, daemons, services,
  background processes, or networked control surfaces.
- The Claude Code plugin package is skill-only in 0.2.0. It does not bundle the
  Python CLI, install hooks, start an MCP server, start a daemon, or add
  background behavior.
- Managed project state is constrained to `.codex/token-optimizer.json`,
  `.codex/token-optimizer/`, and managed Token Optimizer hook blocks.

## Explicit Network Modes

Live provider benchmarks are separate opt-in commands:

- `benchmark anthropic-count --fixture ... --model ...` reads
  `ANTHROPIC_API_KEY` from the environment and sends only the explicit fixture
  text to Anthropic count-tokens behavior.
- `benchmark openai-usage --fixture ... --model ...` reads `OPENAI_API_KEY` from
  the environment and sends only the explicit fixture text to the OpenAI
  Responses API with `store=false`.
- `benchmark openai-tiktoken --fixture ... --model ...` is an offline tokenizer
  estimate. It uses optional local `tiktoken` support and does not call OpenAI
  or read an API key.

Provider benchmark reports are printed to stdout and are not persisted by Token
Optimizer.

## Release Artifact Boundaries

The release surface is checked so public artifacts exclude private/internal
project records. The Python wheel should contain only the installable package,
distribution metadata, entry point metadata, and license. The source
distribution should contain source, tests, package metadata, and public docs. The
Codex plugin package should remain focused: `.codex-plugin/`, `.mcp.json`,
`mcp/`, `skills/`, and `assets/` only. The Claude Code plugin package should
remain skill-only: `.claude-plugin/`, `skills/`, and its package README only.

Run this before tagging or publishing:

```bash
python3 scripts/check_release_artifacts.py
```

## Reporting Issues

For private security reports, contact the maintainer directly before public
disclosure. Include the affected command, the exact version or commit, the local
artifact involved, and a minimal reproduction that avoids sharing sensitive
project data.
