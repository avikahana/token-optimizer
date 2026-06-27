# Benchmarking

Token Optimizer benchmarks must be reproducible, explicit, and honest about what
kind of token number they report.

## Phase 7 Structure

### Estimator

First implementation unit.

- function: `ceil(bytes / 4)`
- label: `static_estimate`
- input: byte count only
- no file reads
- no CLI
- no fixture assumptions
- no network
- no API keys
- no provider-specific tokenizer dependency

This is safe, tiny, and easy to test.

### Fixture Contract

First real design choice.

- fixture path: `benchmarks/fixtures/common-python-cli-session/`
- baseline side: raw-ish session context inputs
- optimized side: outputs from `outline` / `summarize`
- must-preserve file: facts that must still appear in optimized output

The fixture contract must be agreed before implementing benchmark runner logic.
It supports preservation checks without depending on private transcripts,
network calls, raw automatic capture, or provider-specific tokenizers.

### Benchmark Runner

Default static benchmark runner and current CLI surface.

- reads only the explicit fixture
- computes baseline static estimate
- computes optimized static estimate
- reports `measurement_label: static_estimate`
- reports baseline estimate, optimized estimate, reduction, reduction percent,
  preservation checks, and limitations
- supports human and JSON output

This supports a limited claim:

```text
Token Optimizer reduced estimated static context size on this fixture.
```

The current CLI is intentionally narrow:

```bash
token-optimizer benchmark --fixture benchmarks/fixtures/common-python-cli-session/
token-optimizer benchmark --fixture benchmarks/fixtures/common-python-cli-session/ --json
token-optimizer benchmark anthropic-count --fixture benchmarks/fixtures/common-python-cli-session/ --model <anthropic-model>
token-optimizer benchmark openai-tiktoken --fixture benchmarks/fixtures/common-python-cli-session/ --model <openai-model>
token-optimizer benchmark openai-usage --fixture benchmarks/fixtures/common-python-cli-session/ --model <openai-model>
```

The default static command requires an explicit fixture path. It does not scan
the current project, read private transcripts, call `outline` or `summarize`
dynamically, persist reports, call provider APIs, or make network requests.
The `anthropic-count` subcommand is the explicit optional live provider mode.
The `openai-tiktoken` subcommand is an explicit optional offline tokenizer mode.
The `openai-usage` subcommand is an explicit optional live provider mode.

Example current fixture output:

```text
Measurement label: static_estimate
Baseline estimate: 435
Optimized estimate: 202
Reduction: 233
Reduction percent: 53.56%
Preservation checks: all pass
```

### Provider Layer: OpenAI Benchmark

Required later because Avi uses OpenAI/Codex.

Current OpenAI work has an adapter contract, an optional `tiktoken` CLI path,
and an explicit live Responses API usage path:

- file: `src/token_optimizer/openai_benchmark.py`
- labels: `openai_tokenizer_estimate` and `openai_provider_usage`
- builds tokenizer inputs from the explicit fixture
- accepts an injected text-token counting function
- produces human and JSON reports
- exposes optional CLI mode:
  `token-optimizer benchmark openai-tiktoken --fixture ... --model ...`
- uses a soft `tiktoken` import only when the optional command runs
- exposes live CLI mode:
  `token-optimizer benchmark openai-usage --fixture ... --model ...`
- live mode reads `OPENAI_API_KEY` from the environment
- live mode sends only explicit fixture text to OpenAI's Responses API with
  `store=false`
- live mode reports provider usage fields separately from `static_estimate`
- default tests do not run live OpenAI calls

Live execution shape:

```bash
token-optimizer benchmark openai-usage \
  --fixture benchmarks/fixtures/common-python-cli-session/ \
  --model gpt-5.4-mini
```

The provider-neutral `benchmark --fixture` command remains offline.

### Provider Layer: Anthropic Benchmark

Required later because Avi uses Anthropic.

Possible measurement labels:

- `anthropic_count_tokens`
- `anthropic_provider_usage`

Do not use `tiktoken` for Anthropic. Anthropic measurement must use Anthropic's
own token-counting or usage mechanisms.

Anthropic work has both a testable adapter contract and an optional live API
mode:

- file: `src/token_optimizer/anthropic_benchmark.py`
- label: `anthropic_count_tokens`
- builds count-token payloads from the explicit fixture
- accepts an injected count-token function
- produces human and JSON reports
- exposes live CLI mode:
  `token-optimizer benchmark anthropic-count --fixture ... --model ...`
- live mode reads `ANTHROPIC_API_KEY` from the environment
- live mode uses a soft Anthropic SDK import
- default tests do not run live Anthropic calls

Live execution shape:

```bash
token-optimizer benchmark anthropic-count \
  --fixture benchmarks/fixtures/common-python-cli-session/ \
  --model claude-sonnet-4-5
```

The provider-neutral `benchmark --fixture` command remains offline.

## Required Report Fields

Benchmark reports should include:

- benchmark name
- fixture version/path
- estimator or provider
- measurement label
- baseline tokens
- optimized tokens
- reduction
- reduction percent
- commands/features used
- preservation checks
- known limitations

## Non-Claims

Do not claim:

- plugin-install savings
- exact provider tokens from static estimates
- live Codex context-window usage from static files
- universal savings across all providers
- combined totals across static estimates, tokenizer estimates, provider usage,
  and opportunity estimates

## Methodology Comparison

Evaluate Token Optimizer benchmarks by methodology, not raw numbers from other
tools.

Allowed comparison:

- deterministic fixture coverage
- preservation checks
- reproduction commands
- known limitations
- measurement labels
- separation of static estimates, measured savings, estimated savings,
  provider-specific counts, and opportunity
- safety posture around private transcripts, raw tool output, hooks, daemons,
  and network calls

Disallowed comparison:

- treating third-party savings as our target
- claiming our fixture numbers are comparable to private-session numbers from
  other tools
- claiming universal savings from one local fixture
- combining our `static_estimate` reduction with provider usage or cost savings

Current fixture numbers are only a provider-neutral static estimate for the
checked-in fixture. They are useful for proving the benchmark machinery and
fixture preservation contract; they are not measured product savings.

## Reporting Categories

Keep these categories separate in reports and docs:

- `static_estimate`: provider-neutral `ceil(bytes / 4)` fixture estimate.
- measured savings: future directly observed before/after events, only when the
  tool explicitly records such events.
- estimated savings: future counterfactual estimates with stated assumptions.
- opportunity: future recommendations the user has not necessarily acted on.
- provider-specific tokenizer estimates: model/provider tokenizer counts such as
  OpenAI-specific tokenizer estimates.
- provider-reported usage: actual API usage reported by a named provider.

Never sum these categories into one headline.

## Current Fixture

First fixture:

```text
benchmarks/fixtures/common-python-cli-session/
```

It should model a common AI coding session over a Python CLI repo:

- README/docs
- source files
- test output
- failed command output
- directory listing
- continuation notes
- must-preserve facts

The fixture is split into:

- `baseline/`: raw-ish session context inputs
- `optimized/`: outputs from `outline` / `summarize` style workflows
- `must-preserve.md`: facts that must still appear in optimized output
