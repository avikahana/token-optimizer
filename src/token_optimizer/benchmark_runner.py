"""Provider-neutral static benchmark runner."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from token_optimizer.estimator import (
    STATIC_ESTIMATOR_NAME,
    STATIC_MEASUREMENT_LABEL,
    estimate_static_tokens,
)
from token_optimizer.limits import require_readable_size
from token_optimizer.paths import reject_symlink


class BenchmarkRunnerError(ValueError):
    """Raised when a benchmark fixture cannot be measured safely."""


@dataclass(frozen=True)
class BenchmarkFileEstimate:
    """Static estimate for one fixture file."""

    path: str
    byte_count: int
    static_estimate: int


@dataclass(frozen=True)
class PreservationCheck:
    """Whether an optimized fixture preserves one required fact."""

    fact: str
    present: bool


@dataclass(frozen=True)
class BenchmarkReport:
    """Provider-neutral static benchmark report."""

    fixture_path: Path
    estimator: str
    measurement_label: str
    baseline_estimate: int
    optimized_estimate: int
    reduction: int
    reduction_percent: float | None
    preservation_checks: tuple[PreservationCheck, ...]
    limitations: tuple[str, ...]
    baseline_files: tuple[BenchmarkFileEstimate, ...]
    optimized_files: tuple[BenchmarkFileEstimate, ...]


DEFAULT_LIMITATIONS = (
    "static_estimate is a provider-neutral approximation, not exact model tokens.",
    "The runner measures checked-in fixture files, not live Codex context usage.",
    "The runner does not call provider APIs, use network access, or estimate billing.",
)


def build_static_benchmark_report(fixture_path: str | Path) -> BenchmarkReport:
    """Build a static benchmark report from one explicit fixture."""

    fixture = resolve_benchmark_fixture(fixture_path)
    baseline_dir = required_fixture_directory(fixture / "baseline", "baseline")
    optimized_dir = required_fixture_directory(fixture / "optimized", "optimized")
    must_preserve = required_fixture_file(fixture / "must-preserve.md", "must-preserve")

    baseline_files = _measure_files(fixture, baseline_dir)
    optimized_files = _measure_files(fixture, optimized_dir)
    baseline_estimate = sum(item.static_estimate for item in baseline_files)
    optimized_estimate = sum(item.static_estimate for item in optimized_files)
    reduction = baseline_estimate - optimized_estimate
    reduction_percent = reduction_percent_or_none(reduction, baseline_estimate)

    checks = _preservation_checks(must_preserve, optimized_dir)
    return BenchmarkReport(
        fixture_path=fixture,
        estimator=STATIC_ESTIMATOR_NAME,
        measurement_label=STATIC_MEASUREMENT_LABEL,
        baseline_estimate=baseline_estimate,
        optimized_estimate=optimized_estimate,
        reduction=reduction,
        reduction_percent=reduction_percent,
        preservation_checks=checks,
        limitations=DEFAULT_LIMITATIONS,
        baseline_files=baseline_files,
        optimized_files=optimized_files,
    )


def format_benchmark_report(report: BenchmarkReport) -> str:
    """Render a static benchmark report for humans."""

    lines = [
        "Token Optimizer Benchmark",
        f"Fixture: {report.fixture_path}",
        f"Estimator: {report.estimator}",
        f"Measurement label: {report.measurement_label}",
        f"Baseline estimate: {report.baseline_estimate}",
        f"Optimized estimate: {report.optimized_estimate}",
        f"Reduction: {report.reduction}",
        "Reduction percent: " + format_reduction_percent(report.reduction_percent),
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
            "",
            "Baseline files:",
            *_format_file_estimates(report.baseline_files),
            "",
            "Optimized files:",
            *_format_file_estimates(report.optimized_files),
        ]
    )
    return "\n".join(lines)


def benchmark_report_to_json(report: BenchmarkReport) -> str:
    """Render a static benchmark report as stable JSON."""

    payload: dict[str, Any] = {
        "fixturePath": str(report.fixture_path),
        "estimator": report.estimator,
        "measurementLabel": report.measurement_label,
        "baselineEstimate": report.baseline_estimate,
        "optimizedEstimate": report.optimized_estimate,
        "reduction": report.reduction,
        "reductionPercent": report.reduction_percent,
        "preservationChecks": [
            {"fact": check.fact, "present": check.present}
            for check in report.preservation_checks
        ],
        "limitations": list(report.limitations),
        "baselineFiles": [_file_estimate_to_json(item) for item in report.baseline_files],
        "optimizedFiles": [_file_estimate_to_json(item) for item in report.optimized_files],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def resolve_benchmark_fixture(
    fixture_path: str | Path,
    *,
    label: str = "benchmark fixture",
    require_contract: bool = False,
) -> Path:
    """Resolve and validate an explicit benchmark fixture directory."""

    raw_path = Path(fixture_path).expanduser()
    reject_symlink(raw_path, label)
    fixture = raw_path.resolve(strict=False)
    if not fixture.exists():
        raise BenchmarkRunnerError(f"fixture does not exist: {fixture}")
    if not fixture.is_dir():
        raise BenchmarkRunnerError(f"fixture is not a directory: {fixture}")
    if require_contract:
        required_fixture_directory(fixture / "baseline", "baseline")
        required_fixture_directory(fixture / "optimized", "optimized")
        required_fixture_file(fixture / "must-preserve.md", "must-preserve")
    return fixture


def required_fixture_directory(path: Path, label: str) -> Path:
    """Return a required fixture directory, rejecting symlinks."""

    reject_symlink(path, label)
    if not path.exists():
        raise BenchmarkRunnerError(f"{label} directory does not exist: {path}")
    if not path.is_dir():
        raise BenchmarkRunnerError(f"{label} path is not a directory: {path}")
    return path


def required_fixture_file(path: Path, label: str) -> Path:
    """Return a required fixture file, rejecting symlinks."""

    reject_symlink(path, label)
    if not path.exists():
        raise BenchmarkRunnerError(f"{label} file does not exist: {path}")
    if not path.is_file():
        raise BenchmarkRunnerError(f"{label} path is not a file: {path}")
    return path


def reduction_percent_or_none(reduction: int, baseline_tokens: int) -> float | None:
    """Compute a reduction percentage, or None when the baseline is zero."""

    if not baseline_tokens:
        return None
    return round((reduction / baseline_tokens) * 100, 2)


def format_reduction_percent(reduction_percent: float | None) -> str:
    """Render a reduction percentage for humans, with n/a for a zero baseline."""

    if reduction_percent is None:
        return "n/a (baseline is zero)"
    return f"{reduction_percent:.2f}%"


def require_token_count(value: Any, label: str) -> int:
    """Validate a provider-reported token count as a non-negative real int."""

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BenchmarkRunnerError(f"{label} token count must be a non-negative integer")
    return value


def fixture_side_text(fixture: Path, side: str) -> str:
    """Read one fixture side as labeled text chunks."""

    directory = required_fixture_directory(fixture / side, side)
    chunks: list[str] = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise BenchmarkRunnerError(f"fixture contains symlink: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(fixture).as_posix()
        chunks.append(f"## {relative}\n\n{_read_fixture_file(path)}")
    if not chunks:
        raise BenchmarkRunnerError(f"fixture side has no files: {directory}")
    return "\n\n".join(chunks)


def preservation_checks_for_fixture(fixture: Path) -> tuple[PreservationCheck, ...]:
    """Check that the optimized fixture side preserves required facts."""

    directory = required_fixture_directory(fixture / "optimized", "optimized")
    optimized_text = _read_text_files(directory)
    return tuple(
        PreservationCheck(fact=fact, present=fact in optimized_text)
        for fact in must_preserve_facts(fixture / "must-preserve.md")
    )


def must_preserve_facts(path: Path) -> tuple[str, ...]:
    """Read required facts from a must-preserve file."""

    facts: list[str] = []
    for line in _read_fixture_file(path).splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            facts.append(stripped[2:])
    if not facts:
        raise BenchmarkRunnerError(f"must-preserve file has no facts: {path}")
    return tuple(facts)


def _measure_files(fixture: Path, directory: Path) -> tuple[BenchmarkFileEstimate, ...]:
    estimates: list[BenchmarkFileEstimate] = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise BenchmarkRunnerError(f"fixture contains symlink: {path}")
        if not path.is_file():
            continue
        byte_count = path.stat().st_size
        estimates.append(
            BenchmarkFileEstimate(
                path=path.relative_to(fixture).as_posix(),
                byte_count=byte_count,
                static_estimate=estimate_static_tokens(byte_count),
            )
        )
    if not estimates:
        raise BenchmarkRunnerError(f"fixture side has no files: {directory}")
    return tuple(estimates)


def _preservation_checks(
    must_preserve: Path,
    optimized_dir: Path,
) -> tuple[PreservationCheck, ...]:
    optimized_text = _read_text_files(optimized_dir)
    return tuple(
        PreservationCheck(fact=fact, present=fact in optimized_text)
        for fact in must_preserve_facts(must_preserve)
    )


def _read_text_files(directory: Path) -> str:
    chunks: list[str] = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise BenchmarkRunnerError(f"fixture contains symlink: {path}")
        if path.is_file():
            chunks.append(_read_fixture_file(path))
    return "\n".join(chunks)


def _read_fixture_file(path: Path) -> str:
    try:
        require_readable_size(path)
    except ValueError as error:
        raise BenchmarkRunnerError(str(error)) from error
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise BenchmarkRunnerError(f"fixture file is not UTF-8: {path}") from error


def _format_file_estimates(files: tuple[BenchmarkFileEstimate, ...]) -> list[str]:
    return [
        f"- {item.path}: {item.byte_count} bytes, {item.static_estimate} static estimate"
        for item in files
    ]


def _file_estimate_to_json(item: BenchmarkFileEstimate) -> dict[str, Any]:
    return {
        "path": item.path,
        "bytes": item.byte_count,
        "staticEstimate": item.static_estimate,
    }
