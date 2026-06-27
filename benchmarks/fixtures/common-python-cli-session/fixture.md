# Common Python CLI Session Fixture

Status: fixture contract defined.

Purpose: provide a persistent, realistic, repeatable benchmark case for Token
Optimizer.

## Scenario

A coding agent starts work in a Python CLI repository.

The agent:

- reads the README
- reads product/security docs
- opens CLI and helper modules
- runs the test suite
- receives verbose test output
- inspects one failure or warning
- creates a continuation summary

## Baseline Inputs

The baseline side lives under:

```text
baseline/
```

It includes raw-ish session context inputs:

- README content
- selected docs
- selected source files
- raw test output
- raw error output
- raw continuation note

## Optimized Inputs

The optimized side lives under:

```text
optimized/
```

It includes outputs from explicit Token Optimizer-style workflows:

- file outlines instead of full rereads where appropriate
- a compact `summarize` output
- preserved error and next-step information
- hook-generated Stop summary only after hooks are safe

Hook-generated output is intentionally not part of this initial contract.

## Must Preserve

Required facts live in:

```text
must-preserve.md
```

Optimized outputs must retain these facts:

- project purpose
- files inspected
- commands run
- failing or important test output
- decisions made
- next step
- safety warnings

## Must Not Depend On

- private transcripts
- network calls
- background daemons
- global hooks
- upstream Token Optimizer code or fixtures

## Initial Estimator

Use `ceil(bytes / 4)` with measurement label `static_estimate` until
provider-specific adapters are explicitly added.

## Notes

This fixture is a contract, not a benchmark runner. Runner logic should only be
implemented after this layout and preservation contract are accepted.
