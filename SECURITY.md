# Security

Token Optimizer is designed as a local-first context hygiene tool. The default
commands inspect explicit local project inputs and do not start daemons, install
global hooks, capture raw transcripts, persist raw file contents, persist raw
tool output, or make network requests.

## Default Behavior

- `doctor`, `audit`, `outline`, `summarize`, `handoff`, dashboard dry-runs,
  config dry-runs, purge dry-runs, hook dry-runs, and provider-neutral benchmark
  runs are local-only.
- Mutating CLI commands require an explicit `--yes` flag, and hook installation
  also requires `--experimental`.
- The Codex plugin package does not install hooks by default. It ships a local
  MCP hook-control server that can open a visual on/off approval form for the
  inactive experimental Stop hook. The form shows the dry-run plan and writes
  only after explicit approval.
- The Codex plugin package does not ship global hooks, apps, daemons, services,
  background processes, or networked control surfaces.
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
`mcp/`, `skills/`, and `assets/` only.

Run this before tagging or publishing:

```bash
python3 scripts/check_release_artifacts.py
```

## Reporting Issues

For private security reports, contact the maintainer directly before public
disclosure. Include the affected command, the exact version or commit, the local
artifact involved, and a minimal reproduction that avoids sharing sensitive
project data.
