# Release Notes

## 0.1.0 - Initial Release

Initial local-first Token Optimizer baseline.

Implemented:

- `token-optimizer doctor` and `doctor --json`
- project-local hook install/uninstall planning, advanced experimental Stop
  hook enablement, and explicit `--yes` writes
- `outline` for Markdown and Python files
- `summarize` plus `handoff` alias for explicit input files
- `audit` and `audit --json` for static context-hygiene signals
- provider-neutral benchmark runner using labeled `static_estimate` values
- common Python CLI benchmark fixture contract
- Anthropic and OpenAI provider adapter contracts
- explicit live Anthropic count-tokens command
- optional offline OpenAI `tiktoken` tokenizer command
- explicit live OpenAI Responses API provider-usage command
- static HTML dashboard generation from `audit --json`
- project-local config/data initialization
- top-level purge for Token Optimizer-owned state
- optional git-state summary support
- Codex plugin with safe usage skill, local visual hook-control MCP server, and optional MCP control surface
- Claude Code native skill-only plugin package
- marketplace icon, logo, dark logo, and screenshot assets

Safety notes:

- no daemon or background process by default
- no default network calls in ordinary CLI or plugin workflows
- no raw transcript, raw file-content, or raw tool-output persistence by default
- Stop hook install apply requires explicit `--yes --experimental`; plugin
  installation does not enable hooks
- Claude Code plugin installation does not enable hooks, start MCP servers,
  bundle the Python CLI, or add background behavior
- the 0.1.0 managed Stop-hook entry invokes an intentionally no-op command and
  carries an `inactive-placeholder-v1` mode marker so future active behavior
  requires fresh consent
- hook uninstall remains available with explicit `--yes` so advanced users can
  disable/remove managed hook state
- dashboard, config init, and purge support `--dry-run` before writes/removals
- hook/config/purge/dashboard writes reject owned paths that escape the selected
  project through symlinked parents
- dashboard output is constrained to Token Optimizer-owned
  `.codex/token-optimizer/` paths
- audit reports malformed non-UTF-8 Codex hooks as a warning instead of
  crashing
- live Anthropic count-tokens requires an explicit command and
  `ANTHROPIC_API_KEY`
- OpenAI tokenizer estimates use optional local `tiktoken` and do not call
  OpenAI
- live OpenAI provider usage requires an explicit command and `OPENAI_API_KEY`,
  sends only explicit fixture text with `store=false`, and does not persist
  reports

Marketplace readiness:

- Apache-2.0 license metadata is present
- repository, privacy policy, and terms URLs are present in package and plugin
  metadata
- privacy statement and terms files are now present at the advertised paths
- marketplace presentation assets are present in both the root plugin and the
  repo-local marketplace package
- Claude Code marketplace metadata and skill-only package validate locally with
  `claude plugin validate`
