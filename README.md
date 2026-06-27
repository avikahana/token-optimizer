# Token Optimizer

Token Optimizer is a local-first context hygiene tool for AI coding sessions.

The goal is to help reduce repeated reads, noisy command output, bloated context
setup, and poor handoff quality without installing invasive global hooks or
persisting sensitive session data by default.

## Principles

- Project-local by default.
- Dry-run before every mutating action.
- No daemon by default.
- No default network calls; live provider calls require an explicit command.
- No full transcript, file-content, or tool-output capture by default.
- Explicit opt-in for any persistent telemetry.
- Clean uninstall that removes every file and hook it created.
- Small, inspectable components over a giant all-in-one script.

## Planned Commands

- `token-optimizer audit`: inspect repo/context overhead and suggest fixes.
- `token-optimizer audit --json`: print the audit report as stable JSON.
- `token-optimizer dashboard --project . --dry-run`: plan a static HTML audit dashboard.
- `token-optimizer dashboard --project . --yes`: write the static HTML audit dashboard.
- `token-optimizer doctor`: show installed hooks, config, data paths, and risks.
- `token-optimizer doctor --json`: print the doctor report as stable JSON.
- `token-optimizer config init --project . --dry-run`: plan project-local config/data setup.
- `token-optimizer config init --project . --yes`: create project-local config/data paths.
- `token-optimizer purge --project . --dry-run`: plan Token Optimizer-owned cleanup.
- `token-optimizer purge --project . --yes`: remove Token Optimizer-owned config/data and managed hooks.
- `token-optimizer hooks install --project . --dry-run`: plan the advanced experimental Stop hook install.
- `token-optimizer hooks install --project . --yes --experimental`: enable the advanced experimental Stop hook.
- `token-optimizer hooks uninstall --project . --dry-run`: plan managed hook removal.
- `token-optimizer hooks uninstall --project . --yes`: disable/remove managed project-local hooks.
- `token-optimizer outline <file>`: print a structure map before rereading large files.
- `token-optimizer summarize`: generate a compact continuation summary.
- `token-optimizer handoff`: alias for `summarize`.
- `token-optimizer benchmark --fixture <path>`: measure an explicit benchmark
  fixture with the provider-neutral `static_estimate`.
- `token-optimizer benchmark --fixture <path> --json`: print the benchmark
  report as stable JSON.
- `token-optimizer benchmark anthropic-count --fixture <path> --model <model>`:
  run explicit live Anthropic count-tokens measurement.
- `token-optimizer benchmark openai-tiktoken --fixture <path> --model <model>`:
  run an OpenAI-specific tokenizer estimate with the optional `tiktoken`
  dependency.
- `token-optimizer benchmark openai-usage --fixture <path> --model <model>`:
  run explicit live OpenAI Responses API usage measurement.
- `token-optimizer summarize --git-state`: include opt-in local git branch,
  status, and recent commits in the summary.

## Status

Safe CLI baseline, inert plugin skeleton, explicit optimization commands,
provider-neutral static benchmark CLI, static audit dashboard generation,
project-local config/data persistence, top-level purge, optional git-state
handoff summaries, marketplace assets, and OpenAI/Anthropic provider-specific
benchmark paths are implemented. Mutating commands require explicit `--yes`.
Writable Token Optimizer-owned paths are constrained to the selected project,
and dashboard output is constrained to `.codex/token-optimizer/`.

Stop hook installation is an advanced experimental opt-in. It is never enabled
by plugin installation and `hooks install --yes` requires `--experimental`.
The 0.1.0 Stop hook target is intentionally inactive and carries an
`inactive-placeholder-v1` mode marker so any future active hook behavior
requires fresh opt-in consent. Use `hooks uninstall --yes` or `purge --yes` to
disable/remove managed hook state.

The default benchmark command reads only an explicit fixture path and reports
`static_estimate` values. It does not scan private project context, call
provider APIs, make network requests, or report exact OpenAI/Anthropic tokens.
The Anthropic provider mode is explicit live API behavior: it reads
`ANTHROPIC_API_KEY` from the environment, uses a soft Anthropic SDK import, and
does not persist reports. The OpenAI tokenizer mode is explicit offline
tokenizer behavior: it uses an optional `tiktoken` dependency and does not call
OpenAI or read an API key. The OpenAI provider-usage mode is explicit live API
behavior: it reads `OPENAI_API_KEY` from the environment, sends only the
explicit fixture text to the Responses API with `store=false`, reports
`openai_provider_usage`, and does not persist reports.

## License

Token Optimizer is licensed under the Apache License 2.0.

## Public URLs

Project URLs for package and marketplace metadata:

- Repository: `https://github.com/avikahana/token-optimizer`
- Privacy policy: `https://github.com/avikahana/token-optimizer/blob/main/PRIVACY.md`
- Terms: `https://github.com/avikahana/token-optimizer/blob/main/TERMS.md`
- Release notes: `https://github.com/avikahana/token-optimizer/blob/main/RELEASE_NOTES.md`

## Security And Release Checks

The default command paths are local-only, and live provider benchmark modes are
explicit opt-ins. See `SECURITY.md` for the trust model and run
`python3 scripts/check_release_artifacts.py` before tagging or publishing.

## Plugin Skeleton

The first Codex plugin skeleton lives in `.codex-plugin/plugin.json` with a
safe usage skill under `skills/token-optimizer/`. It intentionally has no hooks,
MCP server, app, daemon, or background behavior. Marketplace presentation assets
live under `assets/` and are mirrored into the repo-local marketplace package.
