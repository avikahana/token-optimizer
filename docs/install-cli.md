# Install The CLI

Token Optimizer's core product is the `token-optimizer` Python CLI. The CLI is
local-first by default: ordinary commands inspect explicit local files or project
state and do not start daemons, install global hooks, capture raw transcripts, or
make network requests.

## Requirements

- Python 3.11 or newer
- A local checkout or GitHub source URL for this repository

## Install From A Local Checkout

From the repository root:

```bash
python3 -m pip install .
token-optimizer --version
```

For an isolated local environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
token-optimizer doctor
```

## Install From GitHub Source

After the repository is available to your GitHub account, install from the Git
source with your preferred Python installer.

With `pipx`:

```bash
pipx install git+https://github.com/avikahana/token-optimizer.git
token-optimizer --version
```

With `pip`:

```bash
python3 -m pip install git+https://github.com/avikahana/token-optimizer.git
token-optimizer --version
```

## First Commands

Start with read-only commands:

```bash
token-optimizer doctor
token-optimizer audit --project .
token-optimizer outline README.md
token-optimizer summarize README.md SECURITY.md
```

Generate a local dashboard only after reviewing the dry-run plan:

```bash
token-optimizer dashboard --project . --dry-run
token-optimizer dashboard --project . --yes
```

The dashboard writes under `.codex/token-optimizer/` in the selected project.

## Optional Provider Modes

Provider-neutral benchmarks stay offline:

```bash
token-optimizer benchmark --fixture benchmarks/fixtures/common-python-cli-session/
```

Live provider commands are explicit opt-in modes. They send only the named
fixture text and require provider credentials in the environment:

```bash
token-optimizer benchmark openai-usage --fixture benchmarks/fixtures/common-python-cli-session/ --model <openai-model>
token-optimizer benchmark anthropic-count --fixture benchmarks/fixtures/common-python-cli-session/ --model <anthropic-model>
```

See `docs/provider-support.md` for the current provider support matrix.
