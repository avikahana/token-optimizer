# Provider Benchmark Contributor Guide

Token Optimizer welcomes provider-specific benchmark adapters, but each adapter
must keep measurement claims precise.

## Required Principles

- Use the shared benchmark fixtures when possible.
- Start from the provider-neutral command:
  `token-optimizer benchmark --fixture <path>`.
- Never upload private transcripts by default.
- Separate estimates from provider-reported usage.
- Label every token number with its measurement type.
- Include provider name, model name, SDK/tool version if available, and date.
- Keep provider-specific benchmark failures separate from provider-neutral tests.

## Measurement Labels

Use or extend these labels:

- `static_estimate`
- `openai_tokenizer_estimate`
- `openai_provider_usage`
- `anthropic_count_tokens`
- `anthropic_provider_usage`
- `gemini_count_tokens`
- `gemini_provider_usage`
- `hf_tokenizer_estimate`
- `local_runtime_usage`

If a provider reports separate categories, preserve them separately:

- input tokens
- output tokens
- total tokens
- cached tokens
- reasoning/thinking tokens
- tool-use tokens

Do not collapse these categories into one headline without also showing the
underlying parts.

## Adapter Output Contract

Provider adapters should produce a report containing:

- provider
- model
- measurement label
- fixture path
- baseline tokens
- optimized tokens
- reduction
- reduction percent
- token categories when available
- commands used
- preservation checks
- known limitations
- reproduction command

Provider-specific adapters must not replace or relabel `static_estimate`. They
should add clearly named measurements beside it, such as
`openai_tokenizer_estimate` or `anthropic_count_tokens`.

## OpenAI Notes

The current OpenAI adapter contract builds tokenizer-estimate and provider-usage
inputs from explicit fixtures. The tokenizer path accepts an injected text-token
counting function. The provider-usage path accepts injected Responses API
execution for tests.

Implemented OpenAI paths:

- `openai_tokenizer_estimate` through optional local `tiktoken`
- `openai_provider_usage` through explicit live Responses API usage

Live OpenAI mode rules:

- use `token-optimizer benchmark openai-usage --fixture ... --model ...`
- read `OPENAI_API_KEY` from the environment
- do not accept API keys as command-line flags
- send only explicit fixture text
- set `store=false`
- do not persist reports
- do not run live OpenAI calls in default tests
- preserve input, output, and total token categories separately

Do not present `tiktoken` counts as Anthropic, Gemini, or universal counts.

## Anthropic Notes

Anthropic adapters should use Anthropic-specific token-counting or provider
usage mechanisms.

Do not use `tiktoken` for Anthropic estimates.

The current Anthropic adapter contract builds count-token payloads from explicit
fixtures and accepts an injected count-token function.

Live Anthropic provider execution is implemented as an explicit optional mode
with its own credential and network rules.

Live mode rules:

- read `ANTHROPIC_API_KEY` from the environment
- do not accept API keys as command-line flags
- keep the Anthropic SDK optional or soft-imported
- do not run live Anthropic calls in default tests
- label results as `anthropic_count_tokens`
- do not present count-token results as billing usage or generated output usage

## Other Providers

For Gemini, local Hugging Face models, Mistral, and other providers, contributors
should document:

- official token-counting method or tokenizer
- whether counting is local or API-backed
- whether network/API keys are required
- known differences between count estimates and provider-reported usage
