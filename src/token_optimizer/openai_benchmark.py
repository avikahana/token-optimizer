"""OpenAI benchmark adapter contract."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from token_optimizer.benchmark_runner import BenchmarkRunnerError, PreservationCheck
from token_optimizer.paths import reject_symlink


OPENAI_PROVIDER = "openai"
OPENAI_TOKENIZER_ESTIMATE_LABEL = "openai_tokenizer_estimate"
OPENAI_PROVIDER_USAGE_LABEL = "openai_provider_usage"
MAX_PROVIDER_ERROR_DETAIL_CHARS = 500

DEFAULT_OPENAI_LIMITATIONS = (
    "openai_tokenizer_estimate is OpenAI-specific and depends on the injected tokenizer.",
    "This adapter contract builds explicit fixture texts; it does not call OpenAI directly.",
    "Tokenizer estimates are not provider-reported API usage or billing records.",
)

DEFAULT_OPENAI_USAGE_LIMITATIONS = (
    "openai_provider_usage is provider-reported usage from live OpenAI Responses API calls.",
    "Live mode sends only explicit fixture text to OpenAI and sets store=false.",
    "Input, output, and total tokens are provider usage fields; they are not static_estimate values.",
)


@dataclass(frozen=True)
class OpenAITokenizerInput:
    """One OpenAI tokenizer-estimate input for a fixture side."""

    side: str
    model: str
    text: str


@dataclass(frozen=True)
class OpenAITokenizerReport:
    """OpenAI provider-specific tokenizer benchmark report."""

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


@dataclass(frozen=True)
class OpenAIUsagePayload:
    """One live OpenAI Responses API payload for a fixture side."""

    side: str
    model: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class OpenAIUsageReport:
    """OpenAI provider-reported usage benchmark report."""

    provider: str
    model: str
    measurement_label: str
    fixture_path: Path
    baseline_input_tokens: int
    optimized_input_tokens: int
    baseline_output_tokens: int
    optimized_output_tokens: int
    baseline_total_tokens: int
    optimized_total_tokens: int
    reduction: int
    reduction_percent: float
    preservation_checks: tuple[PreservationCheck, ...]
    limitations: tuple[str, ...]


CountTextTokens = Callable[[str, str], int]
CreateOpenAIResponse = Callable[[dict[str, Any]], Any]
ClientFactory = Callable[[str], CreateOpenAIResponse]


def build_openai_tokenizer_inputs(
    fixture_path: str | Path,
    *,
    model: str,
) -> tuple[OpenAITokenizerInput, OpenAITokenizerInput]:
    """Build baseline and optimized OpenAI tokenizer inputs."""

    if not model.strip():
        raise BenchmarkRunnerError("OpenAI model is required")
    fixture = _resolve_fixture(fixture_path)
    baseline_text = _fixture_side_text(fixture, "baseline")
    optimized_text = _fixture_side_text(fixture, "optimized")
    return (
        OpenAITokenizerInput(side="baseline", model=model, text=baseline_text),
        OpenAITokenizerInput(side="optimized", model=model, text=optimized_text),
    )


def build_openai_tokenizer_report(
    fixture_path: str | Path,
    *,
    model: str,
    count_tokens: CountTextTokens,
) -> OpenAITokenizerReport:
    """Build an OpenAI report using an injected text-token counting function."""

    fixture = _resolve_fixture(fixture_path)
    baseline, optimized = build_openai_tokenizer_inputs(fixture, model=model)
    baseline_tokens = _count_input_tokens(count_tokens(baseline.text, model))
    optimized_tokens = _count_input_tokens(count_tokens(optimized.text, model))
    reduction = baseline_tokens - optimized_tokens
    reduction_percent = 0.0
    if baseline_tokens:
        reduction_percent = round((reduction / baseline_tokens) * 100, 2)
    return OpenAITokenizerReport(
        provider=OPENAI_PROVIDER,
        model=model,
        measurement_label=OPENAI_TOKENIZER_ESTIMATE_LABEL,
        fixture_path=fixture,
        baseline_input_tokens=baseline_tokens,
        optimized_input_tokens=optimized_tokens,
        reduction=reduction,
        reduction_percent=reduction_percent,
        preservation_checks=_preservation_checks(fixture),
        limitations=DEFAULT_OPENAI_LIMITATIONS,
    )


def build_openai_usage_payloads(
    fixture_path: str | Path,
    *,
    model: str,
    max_output_tokens: int = 16,
) -> tuple[OpenAIUsagePayload, OpenAIUsagePayload]:
    """Build baseline and optimized live OpenAI Responses API payloads."""

    if not model.strip():
        raise BenchmarkRunnerError("OpenAI model is required")
    if max_output_tokens < 16:
        raise BenchmarkRunnerError("max_output_tokens must be at least 16")
    fixture = _resolve_fixture(fixture_path)
    baseline_text = _fixture_side_text(fixture, "baseline")
    optimized_text = _fixture_side_text(fixture, "optimized")
    return (
        OpenAIUsagePayload(
            side="baseline",
            model=model,
            payload=_usage_payload(model, baseline_text, max_output_tokens),
        ),
        OpenAIUsagePayload(
            side="optimized",
            model=model,
            payload=_usage_payload(model, optimized_text, max_output_tokens),
        ),
    )


def build_openai_usage_report(
    fixture_path: str | Path,
    *,
    model: str,
    create_response: CreateOpenAIResponse,
    max_output_tokens: int = 16,
) -> OpenAIUsageReport:
    """Build an OpenAI report using injected Responses API execution."""

    fixture = _resolve_fixture(fixture_path)
    baseline, optimized = build_openai_usage_payloads(
        fixture,
        model=model,
        max_output_tokens=max_output_tokens,
    )
    baseline_usage = _usage_values(create_response(baseline.payload))
    optimized_usage = _usage_values(create_response(optimized.payload))
    reduction = baseline_usage["input_tokens"] - optimized_usage["input_tokens"]
    reduction_percent = 0.0
    if baseline_usage["input_tokens"]:
        reduction_percent = round((reduction / baseline_usage["input_tokens"]) * 100, 2)
    return OpenAIUsageReport(
        provider=OPENAI_PROVIDER,
        model=model,
        measurement_label=OPENAI_PROVIDER_USAGE_LABEL,
        fixture_path=fixture,
        baseline_input_tokens=baseline_usage["input_tokens"],
        optimized_input_tokens=optimized_usage["input_tokens"],
        baseline_output_tokens=baseline_usage["output_tokens"],
        optimized_output_tokens=optimized_usage["output_tokens"],
        baseline_total_tokens=baseline_usage["total_tokens"],
        optimized_total_tokens=optimized_usage["total_tokens"],
        reduction=reduction,
        reduction_percent=reduction_percent,
        preservation_checks=_preservation_checks(fixture),
        limitations=DEFAULT_OPENAI_USAGE_LIMITATIONS,
    )


def build_live_openai_usage_report(
    fixture_path: str | Path,
    *,
    model: str,
    max_output_tokens: int = 16,
    environ: Mapping[str, str] | None = None,
    client_factory: ClientFactory | None = None,
) -> OpenAIUsageReport:
    """Build an OpenAI report using the optional live Responses API path."""

    environment = os.environ if environ is None else environ
    api_key = environment.get("OPENAI_API_KEY", "")
    if not api_key:
        raise BenchmarkRunnerError("OPENAI_API_KEY is required for live OpenAI usage")
    factory = client_factory if client_factory is not None else _openai_responses_client_factory
    return build_openai_usage_report(
        fixture_path,
        model=model,
        create_response=factory(api_key),
        max_output_tokens=max_output_tokens,
    )


def build_tiktoken_openai_tokenizer_report(
    fixture_path: str | Path,
    *,
    model: str,
) -> OpenAITokenizerReport:
    """Build an OpenAI tokenizer report with the optional tiktoken dependency."""

    return build_openai_tokenizer_report(
        fixture_path,
        model=model,
        count_tokens=count_text_tokens_with_tiktoken,
    )


def count_text_tokens_with_tiktoken(text: str, model: str) -> int:
    """Count text tokens with tiktoken when the optional dependency is installed."""

    try:
        import tiktoken  # type: ignore[import-not-found]
    except ImportError as error:
        raise BenchmarkRunnerError(
            "tiktoken is required for OpenAI tokenizer estimates; "
            "install token-optimizer[openai] to enable this command"
        ) from error
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("o200k_base")
    return len(encoding.encode(text))


def format_openai_tokenizer_report(report: OpenAITokenizerReport) -> str:
    """Render an OpenAI tokenizer-estimate report for humans."""

    lines = [
        "Token Optimizer OpenAI Benchmark",
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


def format_openai_usage_report(report: OpenAIUsageReport) -> str:
    """Render an OpenAI provider-usage report for humans."""

    lines = [
        "Token Optimizer OpenAI Usage Benchmark",
        f"Fixture: {report.fixture_path}",
        f"Provider: {report.provider}",
        f"Model: {report.model}",
        f"Measurement label: {report.measurement_label}",
        f"Baseline input tokens: {report.baseline_input_tokens}",
        f"Optimized input tokens: {report.optimized_input_tokens}",
        f"Baseline output tokens: {report.baseline_output_tokens}",
        f"Optimized output tokens: {report.optimized_output_tokens}",
        f"Baseline total tokens: {report.baseline_total_tokens}",
        f"Optimized total tokens: {report.optimized_total_tokens}",
        f"Input reduction: {report.reduction}",
        f"Input reduction percent: {report.reduction_percent:.2f}%",
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


def openai_tokenizer_report_to_json(report: OpenAITokenizerReport) -> str:
    """Render an OpenAI tokenizer-estimate report as stable JSON."""

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


def openai_usage_report_to_json(report: OpenAIUsageReport) -> str:
    """Render an OpenAI provider-usage report as stable JSON."""

    payload: dict[str, Any] = {
        "provider": report.provider,
        "model": report.model,
        "measurementLabel": report.measurement_label,
        "fixturePath": str(report.fixture_path),
        "baselineInputTokens": report.baseline_input_tokens,
        "optimizedInputTokens": report.optimized_input_tokens,
        "baselineOutputTokens": report.baseline_output_tokens,
        "optimizedOutputTokens": report.optimized_output_tokens,
        "baselineTotalTokens": report.baseline_total_tokens,
        "optimizedTotalTokens": report.optimized_total_tokens,
        "inputReduction": report.reduction,
        "inputReductionPercent": report.reduction_percent,
        "preservationChecks": [
            {"fact": check.fact, "present": check.present}
            for check in report.preservation_checks
        ],
        "limitations": list(report.limitations),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _usage_payload(model: str, text: str, max_output_tokens: int) -> dict[str, Any]:
    return {
        "model": model,
        "input": text,
        "max_output_tokens": max_output_tokens,
        "store": False,
    }


def _resolve_fixture(fixture_path: str | Path) -> Path:
    raw_path = Path(fixture_path).expanduser()
    reject_symlink(raw_path, "OpenAI benchmark fixture")
    fixture = raw_path.resolve(strict=False)
    if not fixture.exists():
        raise BenchmarkRunnerError(f"fixture does not exist: {fixture}")
    if not fixture.is_dir():
        raise BenchmarkRunnerError(f"fixture is not a directory: {fixture}")
    _required_directory(fixture / "baseline", "baseline")
    _required_directory(fixture / "optimized", "optimized")
    _required_file(fixture / "must-preserve.md", "must-preserve")
    return fixture


def _fixture_side_text(fixture: Path, side: str) -> str:
    directory = _required_directory(fixture / side, side)
    chunks: list[str] = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise BenchmarkRunnerError(f"fixture contains symlink: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(fixture).as_posix()
        chunks.append(f"## {relative}\n\n{path.read_text(encoding='utf-8')}")
    if not chunks:
        raise BenchmarkRunnerError(f"fixture side has no files: {directory}")
    return "\n\n".join(chunks)


def _preservation_checks(fixture: Path) -> tuple[PreservationCheck, ...]:
    optimized_text = _fixture_side_text(fixture, "optimized")
    return tuple(
        PreservationCheck(fact=fact, present=fact in optimized_text)
        for fact in _must_preserve_facts(fixture / "must-preserve.md")
    )


def _must_preserve_facts(path: Path) -> tuple[str, ...]:
    facts: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            facts.append(stripped[2:])
    if not facts:
        raise BenchmarkRunnerError(f"must-preserve file has no facts: {path}")
    return tuple(facts)


def _required_directory(path: Path, label: str) -> Path:
    reject_symlink(path, label)
    if not path.exists():
        raise BenchmarkRunnerError(f"{label} directory does not exist: {path}")
    if not path.is_dir():
        raise BenchmarkRunnerError(f"{label} path is not a directory: {path}")
    return path


def _required_file(path: Path, label: str) -> Path:
    reject_symlink(path, label)
    if not path.exists():
        raise BenchmarkRunnerError(f"{label} file does not exist: {path}")
    if not path.is_file():
        raise BenchmarkRunnerError(f"{label} path is not a file: {path}")
    return path


def _count_input_tokens(value: object) -> int:
    if isinstance(value, int):
        return value
    raise BenchmarkRunnerError("OpenAI token counter must return an int")


def _usage_values(response: Any) -> dict[str, int]:
    usage = _get_field(response, "usage")
    if usage is None:
        raise BenchmarkRunnerError("OpenAI response did not include usage")
    input_tokens = _required_int_field(usage, "input_tokens")
    output_tokens = _required_int_field(usage, "output_tokens")
    total_tokens = _required_int_field(usage, "total_tokens")
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _required_int_field(value: Any, field: str) -> int:
    field_value = _get_field(value, field)
    if isinstance(field_value, int):
        return field_value
    raise BenchmarkRunnerError(f"OpenAI usage field must be an int: {field}")


def _get_field(value: Any, field: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(field)
    return getattr(value, field, None)


def _openai_responses_client_factory(api_key: str) -> CreateOpenAIResponse:
    def create_response(payload: dict[str, Any]) -> Any:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise BenchmarkRunnerError(
                f"OpenAI Responses API request failed with HTTP {exc.code}: "
                f"{_truncate_error_detail(detail)}"
            ) from exc
        except urllib.error.URLError as exc:
            raise BenchmarkRunnerError(f"OpenAI Responses API request failed: {exc.reason}") from exc

    return create_response


def _truncate_error_detail(detail: str) -> str:
    compact = " ".join(detail.split())
    if len(compact) <= MAX_PROVIDER_ERROR_DETAIL_CHARS:
        return compact
    return f"{compact[:MAX_PROVIDER_ERROR_DETAIL_CHARS].rstrip()}... [truncated]"
