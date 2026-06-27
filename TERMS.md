# Token Optimizer Terms

Last updated: 2026-06-27

Token Optimizer is provided under the Apache License 2.0. See `LICENSE` for the
full license text.

## Use

Token Optimizer is local-first developer tooling for inspecting and improving AI
coding-session context hygiene. Users are responsible for reviewing command
output and for deciding which files or fixtures they provide as explicit input.

## No Warranty

Token Optimizer is provided on an "as is" basis, without warranties or
conditions of any kind. The software may report estimates, static analysis
signals, or provider-specific measurements, but those reports should be treated
as developer guidance rather than guarantees.

## Third-Party Providers

Optional provider-specific commands may call third-party APIs only when the user
explicitly invokes them and supplies credentials through the documented
environment variables. Any third-party API use is subject to that provider's
own terms and billing rules.

## Project Scope

The current MVP avoids default telemetry, daemons, network calls, raw transcript
capture, raw file-content persistence, and raw tool-output persistence. Future
capabilities must be documented before they change that scope.
