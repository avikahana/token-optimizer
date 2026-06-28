# Token Optimizer Privacy Statement

Last updated: 2026-06-27

Token Optimizer is designed as a local-first context hygiene tool for AI coding
sessions. The default product posture is to inspect explicit local project
inputs and avoid background collection.

## Default Behavior

By default, Token Optimizer does not:

- run a daemon or background service
- send telemetry, analytics, or usage data
- make network calls from ordinary CLI or plugin workflows
- capture full chat transcripts
- persist raw file contents
- persist raw tool outputs
- read API keys from command-line flags

The Codex plugin does not install hooks by default. It includes a local MCP
hook-control server that can open an interactive MCP hook-control surface when
the host supports MCP UI resources, with a native approval form as the fallback.
The controls show the dry-run plan first, require explicit approval, and write
only project-local Token Optimizer hook config. They do not add daemons,
network calls, telemetry, or background behavior.

## Local Files

Token Optimizer commands operate on explicit local inputs. Project scans,
mutating commands, and owned output paths are project-local. Read-only
explicit-input commands such as `outline` and `summarize` may read absolute file
paths outside the project when the user names those files directly. `outline`
and `summarize` print a warning when an explicit input resolves outside the
current or selected project root. Current commands such as `doctor`, `audit`,
`outline`, `summarize`, and the default benchmark runner print reports to stdout
unless the user chooses to redirect or save that output.

The current implemented mutating paths are:

- `.codex/hooks.json` managed block, created only by
  `token-optimizer hooks install --project . --yes --experimental` or by
  approving the plugin hook control app or native fallback. The installed
  Stop-hook entry invokes an intentionally no-op command in 0.1.0.
- `.codex/token-optimizer.json`, created or updated only by
  `token-optimizer config init --project . --yes`
- `.codex/token-optimizer/`, created only by explicit config, dashboard, or
  other Token Optimizer-owned output commands
- `.codex/token-optimizer/audit-dashboard.html`, created only by
  `token-optimizer dashboard --project . --yes`

These project-local artifacts are removed by:

- `token-optimizer hooks uninstall --project . --yes`
- `token-optimizer purge --project . --yes`
- approving the plugin hook control app or native fallback in the off position

All persistent paths are documented in `docs/persistence-map.md`.

## Provider Integrations

Provider-specific network behavior is explicit and optional. The current live
provider paths are:

- `token-optimizer benchmark anthropic-count --fixture <path> --model <model>`
- `token-optimizer benchmark openai-usage --fixture <path> --model <model>`

`anthropic-count` reads `ANTHROPIC_API_KEY` from the environment, uses the
optional Anthropic SDK, sends only the explicit fixture text to Anthropic's
count-tokens API, and does not persist the report.

`openai-usage` reads `OPENAI_API_KEY` from the environment, uses the Python
standard library to call OpenAI's Responses API, sends only the explicit fixture
text with `store=false`, and does not persist the report.

Both live provider commands are excluded from ordinary/default workflows and
default tests. The provider-neutral benchmark command remains local-only:

- `token-optimizer benchmark --fixture <path>`

The OpenAI tokenizer estimate remains offline:

- `token-optimizer benchmark openai-tiktoken --fixture <path> --model <model>`

That command uses an optional local `tiktoken` dependency and does not read an
API key, call OpenAI, or persist reports.

## Sensitive Data

Users should avoid passing secrets, credentials, `.env` files, key files, or
other sensitive material as explicit input, including absolute paths outside the
project, unless they have reviewed the command behavior. Future persistence
features must redact secrets and must be
documented before they are implemented.

## Changes

If Token Optimizer later adds persistence, telemetry, network behavior, daemon
behavior, or broader hooks, this statement and the security and persistence
docs must be updated before those capabilities ship.
