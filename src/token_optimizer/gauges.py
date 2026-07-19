"""Read-only context gauges derived from the static audit."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from token_optimizer import __version__
from token_optimizer.audit import build_audit
from token_optimizer.doctor import HOOKS_RELATIVE_PATH, MANAGED_MARKER
from token_optimizer.estimator import (
    STATIC_ESTIMATOR_NAME,
    STATIC_MEASUREMENT_LABEL,
    estimate_static_tokens,
)

SEVERITY_ORDER = ("warning", "info")


@dataclass(frozen=True)
class GaugesReport:
    """Compact on-demand context-health gauge values for a project."""

    version: str
    project_path: Path
    score: int
    static_token_estimate: int
    scanned_files: int
    signal_counts: tuple[tuple[str, int], ...]
    outline_candidate_count: int
    managed_hooks_present: bool


def build_gauges(project_path: str | Path | None = None) -> GaugesReport:
    """Build a read-only gauges report by recomputing the static audit."""

    audit = build_audit(project_path)
    counts: dict[str, int] = {severity: 0 for severity in SEVERITY_ORDER}
    for signal in audit.signals:
        counts[signal.severity] = counts.get(signal.severity, 0) + 1
    return GaugesReport(
        version=__version__,
        project_path=audit.project_path,
        score=audit.score,
        static_token_estimate=estimate_static_tokens(audit.total_text_bytes),
        scanned_files=audit.scanned_files,
        signal_counts=tuple(sorted(counts.items())),
        outline_candidate_count=len(audit.outline_candidates),
        managed_hooks_present=_managed_hooks_present(audit.project_path),
    )


def format_gauges(report: GaugesReport) -> str:
    """Render a human-readable gauges report."""

    signal_text = ", ".join(
        f"{count} {severity}" for severity, count in report.signal_counts
    )
    return "\n".join(
        [
            "Token Optimizer Gauges",
            f"Version: {report.version}",
            f"Project: {report.project_path}",
            f"Score: {report.score}/100",
            f"Static token estimate ({STATIC_ESTIMATOR_NAME}): {report.static_token_estimate}",
            f"Scanned files: {report.scanned_files}",
            f"Signals: {signal_text if signal_text else 'none'}",
            f"Outline candidates: {report.outline_candidate_count}",
            f"Managed hooks present: {'yes' if report.managed_hooks_present else 'no'}",
        ]
    )


def gauges_to_json(report: GaugesReport) -> str:
    """Render a stable JSON gauges report."""

    payload = {
        "version": report.version,
        "project": str(report.project_path),
        "score": report.score,
        "staticTokenEstimate": report.static_token_estimate,
        "estimator": STATIC_ESTIMATOR_NAME,
        "measurement": STATIC_MEASUREMENT_LABEL,
        "scannedFiles": report.scanned_files,
        "signalCounts": dict(report.signal_counts),
        "outlineCandidateCount": report.outline_candidate_count,
        "managedHooksPresent": report.managed_hooks_present,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _managed_hooks_present(project: Path) -> bool:
    hooks = project / HOOKS_RELATIVE_PATH
    if not hooks.exists() or hooks.is_symlink() or not hooks.is_file():
        return False
    try:
        return MANAGED_MARKER in hooks.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
