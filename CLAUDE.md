# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Token Optimizer is a local-first context-hygiene CLI for AI coding sessions (Python 3.11+, zero runtime dependencies), plus a Node MCP hook-control server and plugin packaging for Codex and Claude Code. The core product promise — no default network calls, no daemon, no raw transcript capture, dry-run before every write — is enforced by code and tests, not just documented. Treat any change that weakens that posture as a design change, not a bug fix.

## Commands

```bash
# Run the full test suite (stdlib unittest, no pytest needed; ~1s)
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q

# Run a single test module / test case
PYTHONPATH=src python3 -m unittest tests.test_hooks -q
PYTHONPATH=src python3 -m unittest tests.test_cli.CliTests.test_doctor_json -q

# Run the CLI from source (no install needed)
PYTHONPATH=src python3 -m token_optimizer.cli doctor
PYTHONPATH=src python3 -m token_optimizer.cli benchmark --fixture benchmarks/fixtures/common-python-cli-session

# After editing any root plugin file (.codex-plugin/, .mcp.json, mcp/, skills/, assets/)
python3 scripts/sync_mirrors.py

# Release artifact boundary check
python3 scripts/check_release_artifacts.py
```

There is no linter or formatter configured. Tests never hit the network; live provider benchmarks are exercised only via injected fakes.

## Architecture

### CLI module pattern

`src/token_optimizer/cli.py` is a single argparse entrypoint that dispatches to one module per command. Every command module follows the same contract:

- `build_X(...)` returns a frozen dataclass report/plan (pure logic, testable without the CLI)
- `format_X(...)` renders human text; `X_to_json(...)` renders stable JSON (`--json`)
- Errors are module-specific `ValueError` subclasses (`AuditError`, `SummaryError`, `BenchmarkRunnerError`, ...); the CLI catches them, prints `command: message`, and returns exit code 1

### Plan/apply split for anything that writes

Mutating commands (`dashboard`, `config init`, `purge`, `hooks install/uninstall`) require exactly one of `--dry-run` or `--yes`. They build a plan object first (`plan_X`), and `apply_X(plan)` executes it only under `--yes`. Apply functions re-validate the plan against current disk state and reject stale plans. Preserve this shape when adding any command that writes.

### Path safety layer

`paths.py` is the containment boundary: `resolve_project_path`, `resolve_owned_path`, `reject_symlink`, and `atomic_write_text`. All writes are constrained to Token Optimizer-owned paths under the selected project (see `docs/persistence-map.md`):

- `.codex/token-optimizer.json` (config), `.codex/token-optimizer/` (outputs, incl. the dashboard HTML)
- a managed block in `.codex/hooks.json`, identified by the `TOKEN_OPTIMIZER_MANAGED` marker

Symlinked-parent escapes must be rejected after resolution. `limits.py` caps whole-file reads at 10 MiB. Route new file I/O through these helpers rather than raw `open()`/`Path.write_text()`.

### Benchmark layering and measurement labels

- `estimator.py`: provider-neutral `ceil(bytes / 4)`, label `static_estimate` — no file reads, no network
- `benchmark_runner.py`: offline fixture runner (baseline vs. optimized sides plus `must-preserve.md` preservation checks; fixture contract in `docs/benchmarking.md`)
- `openai_benchmark.py` / `anthropic_benchmark.py`: opt-in provider modes with distinct labels (`openai_tokenizer_estimate`, `openai_provider_usage`, `anthropic_count_tokens`). Provider SDKs (`tiktoken`, Anthropic) are soft-imported only when those subcommands run; API keys come from env vars; adapters accept injected counting functions so tests stay offline

Never mix or sum measurement categories in reports or docs — `docs/benchmarking.md` defines what may and may not be claimed. `tests/test_no_network.py` asserts default code paths import no network modules.

### The hook is intentionally a no-op in 0.1.0

`hooks.py` installs a Stop-hook entry whose command (`token-optimizer summarize --hook stop --hook-mode inactive-placeholder-v1`) deliberately does nothing when invoked — `.codex/hooks.json` is a consent record, not an active hook surface. Install requires `--yes --experimental` after a dry run. Do not make the hook do real work without a new consent flow; tests and docs assume inactivity.

### MCP server and plugin packaging

- `mcp/server.mjs` is a dependency-free Node stdio MCP server for interactive hook control (Codex plugin surface). It duplicates the Python-side constants (`TOKEN_OPTIMIZER_MANAGED`, the managed command, `inactive-placeholder-v1`) — keep both sides in sync when changing any of them.
- Root plugin files are mirrored byte-identically into `marketplace/plugins/token-optimizer/`; `tests/test_plugin_manifest.py` fails on any drift. Always run `python3 scripts/sync_mirrors.py` after editing a mirrored file (list in that script's `MIRRORED_FILES`).
- The Claude Code plugin (`.claude-plugin/marketplace.json` + `plugins/token-optimizer/`) is skill-only: no hooks, no MCP server, no bundled CLI. `test_plugin_manifest.py` also enforces manifest shape and required URLs.

### Golden and contract tests

`tests/golden/` holds exact expected `doctor` output (text and JSON). Changing user-visible report output means updating goldens deliberately. `tests/test_benchmark_fixture_contract.py` pins the checked-in fixture's numbers — the README's Benchmark Snapshot tables must match if the fixture changes.

## Conventions

- Runtime code is stdlib-only (`dependencies = []` in pyproject.toml). Do not add runtime dependencies; optional integrations go behind extras + soft imports.
- Frozen dataclasses for all report/plan types; `from __future__ import annotations` in every module.
- This file (CLAUDE.md), AGENTS.md, `brain/`, `chatgpt/`, and `docs/research/` are private working files: excluded from sdists via MANIFEST.in and rejected by `scripts/check_release_artifacts.py`. Never add them to release artifacts or plugin packages.
