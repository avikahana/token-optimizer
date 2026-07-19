# Security Model

## Default Trust Boundary

Token Optimizer runs locally and should only inspect the project where it is invoked,
plus its own project-local config directory.

Writable or removable Token Optimizer-owned paths must resolve under the selected
project after symlink resolution. If a parent such as `.codex/` is a symlink that
would make an owned path escape the project, mutating commands must reject it.

Default config path:

- `.codex/token-optimizer.json`

Default data path:

- `.codex/token-optimizer/`

## Sensitive Data Rules

- Do not store raw transcripts by default.
- Do not store raw file contents by default.
- Do not store raw tool outputs by default.
- Redact secrets before any optional persistence.
- Treat `.env`, key files, auth files, and credential directories as excluded.

## Hook Rules

- Hooks must be project-local by default.
- Hooks must include a stable marker so uninstall can remove only managed blocks.
- Hook install must support `--dry-run`.
- Hook uninstall must remove all managed blocks and generated files.
- Stop hook installation is an advanced experimental opt-in for 0.2.0:
  `hooks install --yes` must require `--experimental`.
- The 0.2.0 managed Stop-hook entry must invoke an intentionally no-op command
  and include an explicit behavior marker. Future active hook behavior requires
  fresh consent and must not silently activate older no-op hook installs.
- Global install must require an explicit flag and warning.

## Network Rules

- No default network calls in MVP command paths.
- No local daemon in MVP.
- Dashboard generation is explicit, static HTML output only; it is not a daemon
  and does not watch files.
- Dashboard output must stay under `.codex/token-optimizer/`; custom dashboard
  output paths cannot target arbitrary project files.
- Provider-specific benchmark network calls, such as live Anthropic
  count-tokens execution, must be explicit optional modes with separate
  credential handling and must not run in default tests.
- Live Anthropic count-tokens reads `ANTHROPIC_API_KEY` from the environment,
  never from a command-line flag, and does not persist reports.
- OpenAI tokenizer estimates use optional local `tiktoken` execution and do not
  call OpenAI or read an API key.
- Live OpenAI provider usage reads `OPENAI_API_KEY` from the environment, never
  from a command-line flag, sends only explicit fixture text to the Responses
  API with `store=false`, labels reports `openai_provider_usage`, and does not
  persist reports.

## Persistence Rules

Every persistent file must be documented in `docs/persistence-map.md` before it
is introduced in code.
