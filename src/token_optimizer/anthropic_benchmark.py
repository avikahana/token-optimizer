"""Anthropic benchmark adapter contract."""

from __future__ import annotations

import json
import importlib
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from token_optimizer.benchmark_runner import (
    BenchmarkRunnerError,
    PreservationCheck,
    fixture_side_text,
    preservation_checks_for_fixture,
    resolve_benchmark_fixture,
)


ANTHROPIC_PROVIDER = "anthropic"
ANTHROPIC_COUNT_TOKENS_LABEL = "anthropic_count_tokens"

DEFAULT_ANTHROPIC_LIMITATIONS = (
    "anthropic_count_tokens is provider-specific and requires Anthropic token counting.",
    "The report counts explicit fixture text; live CLI mode sends that fixture text to Anthropic.",
    "Count-token values may differ slightly from actual message usage.",
)


@dataclass(frozen=True)
class AnthropicPayload:
    """One Anthropic count-tokens payload for a fixture side."""

    side: str
    model: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class AnthropicCountReport:
    """Anthropic provider-specific benchmark report."""

    provider: str
    model: str
    measurement_label: str
    fixture_path: Path
    baseline_input_tokens: int
    optimized_input_tokens: int
    reduction: int
    reduction_percent: float
    preservation_checks: tuple[PreservationCheck, ...]
    limitations: tuple[str, ...]


CountTokens = Callable[[Mapping[str, Any]], Any]
ClientFactory = Callable[[str], Any]


def build_anthropic_payloads(
    fixture_path: str | Path,
    *,
    model: str,
) -> tuple[AnthropicPayload, AnthropicPayload]:
    """Build baseline and optimized Anthropic count-tokens payloads."""

    if not model.strip():
        raise BenchmarkRunnerError("Anthropic model is required")
    fixture = _resolve_fixture(fixture_path)
    baseline_text = _fixture_side_text(fixture, "baseline")
    optimized_text = _fixture_side_text(fixture, "optimized")
    return (
        AnthropicPayload(
            side="baseline",
            model=model,
            payload=_payload(model, baseline_text),
        ),
        AnthropicPayload(
            side="optimized",
            model=model,
            payload=_payload(model, optimized_text),
        ),
    )


def build_anthropic_count_report(
    fixture_path: str | Path,
    *,
    model: str,
    count_tokens: CountTokens,
) -> AnthropicCountReport:
    """Build an Anthropic report using an injected count-token function."""

    fixture = _resolve_fixture(fixture_path)
    baseline, optimized = build_anthropic_payloads(fixture, model=model)
    baseline_tokens = _count_input_tokens(count_tokens(baseline.payload))
    optimized_tokens = _count_input_tokens(count_tokens(optimized.payload))
    reduction = baseline_tokens - optimized_tokens
    reduction_percent = 0.0
    if baseline_tokens:
        reduction_percent = round((reduction / baseline_tokens) * 100, 2)
    return AnthropicCountReport(
        provider=ANTHROPIC_PROVIDER,
        model=model,
        measurement_label=ANTHROPIC_COUNT_TOKENS_LABEL,
        fixture_path=fixture,
        baseline_input_tokens=baseline_tokens,
        optimized_input_tokens=optimized_tokens,
        reduction=reduction,
        reduction_percent=reduction_percent,
        preservation_checks=_preservation_checks(fixture),
        limitations=DEFAULT_ANTHROPIC_LIMITATIONS,
    )


def build_live_anthropic_count_report(
    fixture_path: str | Path,
    *,
    model: str,
    environ: Mapping[str, str] | None = None,
    client_factory: ClientFactory | None = None,
) -> AnthropicCountReport:
    """Build an Anthropic report using the optional live Anthropic SDK path."""

    environment = os.environ if environ is None else environ
    api_key = environment.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise BenchmarkRunnerError("ANTHROPIC_API_KEY is required for live Anthropic counting")
    factory = client_factory if client_factory is not None else _anthropic_client_factory
    client = factory(api_key)

    def count_tokens(payload: Mapping[str, Any]) -> Any:
        try:
            return client.messages.count_tokens(**payload)
        except Exception as exc:  # SDK errors share no useful common base
            raise BenchmarkRunnerError(f"Anthropic count_tokens failed: {exc}") from exc

    return build_anthropic_count_report(
        fixture_path,
        model=model,
        count_tokens=count_tokens,
    )


def format_anthropic_count_report(report: AnthropicCountReport) -> str:
    """Render an Anthropic count-token report for humans."""

    lines = [
        "Token Optimizer Anthropic Benchmark",
        f"Fixture: {report.fixture_path}",
        f"Provider: {report.provider}",
        f"Model: {report.model}",
        f"Measurement label: {report.measurement_label}",
        f"Baseline input tokens: {report.baseline_input_tokens}",
        f"Optimized input tokens: {report.optimized_input_tokens}",
        f"Reduction: {report.reduction}",
        f"Reduction percent: {report.reduction_percent:.2f}%",
        "",
        "Preservation checks:",
    ]
    for check in report.preservation_checks:
        status = "pass" if check.present else "fail"
        lines.append(f"- [{status}] {check.fact}")
    lines.extend(
        [
            "",
            "Limitations:",
            *[f"- {limitation}" for limitation in report.limitations],
        ]
    )
    return "\n".join(lines)


def anthropic_count_report_to_json(report: AnthropicCountReport) -> str:
    """Render an Anthropic count-token report as stable JSON."""

    payload: dict[str, Any] = {
        "provider": report.provider,
        "model": report.model,
        "measurementLabel": report.measurement_label,
        "fixturePath": str(report.fixture_path),
        "baselineInputTokens": report.baseline_input_tokens,
        "optimizedInputTokens": report.optimized_input_tokens,
        "reduction": report.reduction,
        "reductionPercent": report.reduction_percent,
        "preservationChecks": [
            {"fact": check.fact, "present": check.present}
            for check in report.preservation_checks
        ],
        "limitations": list(report.limitations),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _payload(model: str, text: str) -> Mapping[str, Any]:
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": text,
            }
        ],
    }


def _resolve_fixture(fixture_path: str | Path) -> Path:
    return resolve_benchmark_fixture(
        fixture_path,
        label="Anthropic benchmark fixture",
        require_contract=True,
    )


def _fixture_side_text(fixture: Path, side: str) -> str:
    return fixture_side_text(fixture, side)


def _preservation_checks(fixture: Path) -> tuple[PreservationCheck, ...]:
    return preservation_checks_for_fixture(fixture)


def _count_input_tokens(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, Mapping):
        input_tokens = value.get("input_tokens")
        if isinstance(input_tokens, int):
            return input_tokens
    input_tokens = getattr(value, "input_tokens", None)
    if isinstance(input_tokens, int):
        return input_tokens
    raise BenchmarkRunnerError("count-token function must return int or input_tokens mapping")


def _anthropic_client_factory(api_key: str) -> Any:
    try:
        anthropic = importlib.import_module("anthropic")
    except ImportError as exc:
        raise BenchmarkRunnerError(
            "Anthropic SDK is required for live counting; install optional package `anthropic`"
        ) from exc
    client_class = getattr(anthropic, "Anthropic", None)
    if client_class is None:
        raise BenchmarkRunnerError("Anthropic SDK does not expose Anthropic client")
    return client_class(api_key=api_key)
