from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from token_optimizer.benchmark_runner import (
    BenchmarkRunnerError,
    benchmark_report_to_json,
    build_static_benchmark_report,
    format_benchmark_report,
    preservation_checks_for_fixture,
)
from token_optimizer.estimator import STATIC_MEASUREMENT_LABEL, estimate_static_tokens


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/fixtures/common-python-cli-session"
)


class BenchmarkRunnerTests(unittest.TestCase):
    def test_builds_static_benchmark_report_from_explicit_fixture(self) -> None:
        report = build_static_benchmark_report(FIXTURE)
        expected_baseline = sum(
            estimate_static_tokens(path.stat().st_size)
            for path in (FIXTURE / "baseline").iterdir()
            if path.is_file()
        )
        expected_optimized = sum(
            estimate_static_tokens(path.stat().st_size)
            for path in (FIXTURE / "optimized").iterdir()
            if path.is_file()
        )

        self.assertEqual(report.measurement_label, STATIC_MEASUREMENT_LABEL)
        self.assertEqual(report.baseline_estimate, expected_baseline)
        self.assertEqual(report.optimized_estimate, expected_optimized)
        self.assertEqual(report.reduction, expected_baseline - expected_optimized)
        self.assertTrue(report.preservation_checks)
        self.assertTrue(all(check.present for check in report.preservation_checks))

    def test_formats_human_report(self) -> None:
        rendered = format_benchmark_report(build_static_benchmark_report(FIXTURE))

        self.assertIn("Token Optimizer Benchmark", rendered)
        self.assertIn("Measurement label: static_estimate", rendered)
        self.assertIn("Baseline estimate:", rendered)
        self.assertIn("Optimized estimate:", rendered)
        self.assertIn("Preservation checks:", rendered)
        self.assertIn("Limitations:", rendered)

    def test_json_report_is_stable_and_machine_readable(self) -> None:
        payload = json.loads(benchmark_report_to_json(build_static_benchmark_report(FIXTURE)))

        self.assertEqual(payload["measurementLabel"], "static_estimate")
        self.assertIn("baselineEstimate", payload)
        self.assertIn("optimizedEstimate", payload)
        self.assertIn("reductionPercent", payload)
        self.assertIn("preservationChecks", payload)
        self.assertIn("limitations", payload)

    def test_reports_missing_preservation_fact_as_failed_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = _write_fixture(Path(directory), optimized_text="Project purpose only")

            report = build_static_benchmark_report(fixture)

            self.assertFalse(all(check.present for check in report.preservation_checks))
            self.assertIn(False, [check.present for check in report.preservation_checks])

    def test_rejects_missing_fixture_parts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            (fixture / "baseline").mkdir()
            (fixture / "baseline/input.txt").write_text("baseline", encoding="utf-8")

            with self.assertRaises(BenchmarkRunnerError):
                build_static_benchmark_report(fixture)

    def test_facts_matching_only_file_paths_are_not_counted_as_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            baseline = fixture / "baseline"
            optimized = fixture / "optimized"
            baseline.mkdir()
            optimized.mkdir()
            (baseline / "notes.md").write_text("optimized/notes.md holds the facts", encoding="utf-8")
            (optimized / "notes.md").write_text("unrelated content", encoding="utf-8")
            (fixture / "must-preserve.md").write_text(
                "# Must Preserve\n\n- optimized/notes.md\n",
                encoding="utf-8",
            )

            checks = preservation_checks_for_fixture(fixture)

            self.assertEqual([check.present for check in checks], [False])

    def test_rejects_symlink_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = _write_fixture(root / "fixture", optimized_text="Project purpose")
            link = root / "link"
            link.symlink_to(fixture, target_is_directory=True)

            with self.assertRaises(ValueError):
                build_static_benchmark_report(link)


def _write_fixture(root: Path, *, optimized_text: str) -> Path:
    baseline = root / "baseline"
    optimized = root / "optimized"
    baseline.mkdir(parents=True)
    optimized.mkdir()
    (baseline / "input.txt").write_text("Project purpose\nSecond fact", encoding="utf-8")
    (optimized / "summary.txt").write_text(optimized_text, encoding="utf-8")
    (root / "must-preserve.md").write_text(
        "# Must Preserve\n\n- Project purpose\n- Second fact\n",
        encoding="utf-8",
    )
    return root


if __name__ == "__main__":
    unittest.main()
