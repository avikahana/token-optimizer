# Provider And Surface Support

This page separates two different meanings of support:

- Model/token providers: measurement backends such as OpenAI, Anthropic, Gemini,
  local Hugging Face models, or Mistral.
- Coding-tool surfaces: places where a developer might use Token Optimizer, such
  as Codex, Claude Code, Cursor, GitHub Copilot/VS Code, JetBrains, or other AI
  coding tools.

Current public wording should describe shipped behavior first. Future support is
listed only as planned or research-needed.

## Current Model Provider Modes

| Provider mode | Status | Command | Network | Credential | Label |
|---|---|---|---|---|---|
| Provider-neutral static estimate | Implemented | `token-optimizer benchmark --fixture <path>` | No | None | `static_estimate` |
| OpenAI tokenizer estimate | Implemented | `token-optimizer benchmark openai-tiktoken --fixture <path> --model <model>` | No | None | `openai_tokenizer_estimate` |
| OpenAI live usage | Implemented, explicit opt-in | `token-optimizer benchmark openai-usage --fixture <path> --model <model>` | Yes | `OPENAI_API_KEY` | `openai_provider_usage` |
| Anthropic live count | Implemented, explicit opt-in | `token-optimizer benchmark anthropic-count --fixture <path> --model <model>` | Yes | `ANTHROPIC_API_KEY` | `anthropic_count_tokens` |

The provider-neutral benchmark remains offline and reads only the explicit
fixture. Live provider modes send only explicit fixture text, print reports to
stdout, and are not run in default tests.

## Planned Or Contributor Model Providers

| Provider | Status | Notes |
|---|---|---|
| Gemini | Contributor-adapter candidate | Use official Gemini token counting or usage metadata. Keep labels such as `gemini_count_tokens` or `gemini_provider_usage`. |
| Hugging Face / local models | Contributor-adapter candidate | Use model-specific tokenizers or runtime usage reports. Keep labels such as `hf_tokenizer_estimate` or `local_runtime_usage`. |
| Mistral and other providers | Contributor-adapter candidate | Add through `docs/provider-benchmark-contributor-guide.md` unless first-party support is separately approved. |

Do not reuse OpenAI tokenizer counts as Anthropic, Gemini, local-model, or
universal counts.

## Current Coding-Tool Surfaces

| Surface | Status | Install docs | Boundary |
|---|---|---|---|
| CLI | Implemented core surface | `docs/install-cli.md` | Local-first CLI, explicit commands, no default daemon or network calls. |
| Codex | Native package implemented | `docs/install-codex.md` | Skill guidance plus local MCP hook-control surface. No default hook install. |
| Claude Code | Native skill-only package implemented | `docs/install-claude-code.md` | Skill-only in 0.1.0. Requires separate CLI install. No hooks, MCP server, daemon, or bundled CLI. |

## CLI-Compatible Or Research-Needed Surfaces

These tools may be able to use Token Optimizer through ordinary CLI workflows,
but Token Optimizer does not currently ship native packages or extensions for
them:

- Cursor
- GitHub Copilot / VS Code workflows
- JetBrains IDEs
- Windsurf / Devin Desktop workflows
- Cline / Roo Code / aider / Continue
- Replit Agent / Bolt / Lovable style workflows, where local CLI invocation is
  applicable
- Qodo, CodeRabbit, Sourcegraph Cody, and other review-focused tools

Use `CLI-compatible` for these surfaces unless a future package, extension, MCP
server, or verified integration is implemented.

## Non-Claims

Token Optimizer does not currently claim:

- token savings from plugin installation alone
- live Codex context-window usage measurement from static files
- private transcript capture
- automatic monitoring across all AI coding tools
- native support for every AI coding surface
- universal token counts across providers

Future public claims should be checked against implemented behavior and current
provider or host documentation before publishing.
