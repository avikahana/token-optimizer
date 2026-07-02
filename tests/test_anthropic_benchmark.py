from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from token_optimizer.anthropic_benchmark import (
    ANTHROPIC_COUNT_TOKENS_LABEL,
    anthropic_count_report_to_json,
    build_anthropic_count_report,
    build_live_anthropic_count_report,
    build_anthropic_payloads,
    format_anthropic_count_report,
)
from token_optimizer.benchmark_runner import BenchmarkRunnerError


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/fixtures/common-python-cli-session"
)
MODEL = "claude-sonnet-test"


class AnthropicBenchmarkTests(unittest.TestCase):
    def test_builds_baseline_and_optimized_payloads(self) -> None:
        baseline, optimized = build_anthropic_payloads(FIXTURE, model=MODEL)

        self.assertEqual(baseline.side, "baseline")
        self.assertEqual(optimized.side, "optimized")
        self.assertEqual(baseline.payload["model"], MODEL)
        self.assertEqual(optimized.payload["model"], MODEL)
        self.assertIn("baseline/readme.md", baseline.payload["messages"][0]["content"])
        self.assertIn("optimized/summary-output.txt", optimized.payload["messages"][0]["content"])

    def test_rejects_missing_model(self) -> None:
        with self.assertRaises(BenchmarkRunnerError):
            build_anthropic_payloads(FIXTURE, model=" ")

    def test_builds_count_report_with_injected_counter(self) -> None:
        seen_sides: list[str] = []

        def fake_count(payload: dict[str, Any]) -> dict[str, int]:
            content = payload["messages"][0]["content"]
            if "baseline/readme.md" in content:
                seen_sides.append("baseline")
                return {"input_tokens": 120}
            seen_sides.append("optimized")
            return {"input_tokens": 80}

        report = build_anthropic_count_report(
            FIXTURE,
            model=MODEL,
            count_tokens=fake_count,
        )

        self.assertEqual(seen_sides, ["baseline", "optimized"])
        self.assertEqual(report.provider, "anthropic")
        self.assertEqual(report.measurement_label, ANTHROPIC_COUNT_TOKENS_LABEL)
        self.assertEqual(report.baseline_input_tokens, 120)
        self.assertEqual(report.optimized_input_tokens, 80)
        self.assertEqual(report.reduction, 40)
        self.assertEqual(report.reduction_percent, 33.33)
        self.assertTrue(all(check.present for check in report.preservation_checks))

    def test_accepts_integer_counter_result(self) -> None:
        report = build_anthropic_count_report(
            FIXTURE,
            model=MODEL,
            count_tokens=lambda _payload: 10,
        )

        self.assertEqual(report.baseline_input_tokens, 10)
        self.assertEqual(report.optimized_input_tokens, 10)

    def test_accepts_sdk_object_counter_result(self) -> None:
        class CountResult:
            input_tokens = 10

        report = build_anthropic_count_report(
            FIXTURE,
            model=MODEL,
            count_tokens=lambda _payload: CountResult(),  # type: ignore[return-value]
        )

        self.assertEqual(report.baseline_input_tokens, 10)
        self.assertEqual(report.optimized_input_tokens, 10)

    def test_live_report_requires_api_key(self) -> None:
        with self.assertRaises(BenchmarkRunnerError):
            build_live_anthropic_count_report(
                FIXTURE,
                model=MODEL,
                environ={},
                client_factory=lambda _api_key: object(),
            )

    def test_live_report_uses_env_key_and_injected_client_factory(self) -> None:
        seen_keys: list[str] = []

        class CountResult:
            def __init__(self, input_tokens: int) -> None:
                self.input_tokens = input_tokens

        class FakeMessages:
            def count_tokens(self, **payload: Any) -> CountResult:
                content = payload["messages"][0]["content"]
                if "baseline/readme.md" in content:
                    return CountResult(120)
                return CountResult(80)

        class FakeClient:
            messages = FakeMessages()

        def fake_factory(api_key: str) -> FakeClient:
            seen_keys.append(api_key)
            return FakeClient()

        report = build_live_anthropic_count_report(
            FIXTURE,
            model=MODEL,
            environ={"ANTHROPIC_API_KEY": "test-key"},
            client_factory=fake_factory,
        )

        self.assertEqual(seen_keys, ["test-key"])
        self.assertEqual(report.baseline_input_tokens, 120)
        self.assertEqual(report.optimized_input_tokens, 80)
        self.assertEqual(report.reduction, 40)

    def test_live_report_wraps_sdk_errors_as_benchmark_errors(self) -> None:
        class FakeMessages:
            def count_tokens(self, **_payload: Any) -> None:
                raise RuntimeError("authentication_error: invalid x-api-key")

        class FakeClient:
            messages = FakeMessages()

        with self.assertRaises(BenchmarkRunnerError) as context:
            build_live_anthropic_count_report(
                FIXTURE,
                model=MODEL,
                environ={"ANTHROPIC_API_KEY": "test-key"},
                client_factory=lambda _api_key: FakeClient(),
            )

        self.assertIn("Anthropic count_tokens failed", str(context.exception))

    def test_rejects_invalid_counter_result(self) -> None:
        with self.assertRaises(BenchmarkRunnerError):
            build_anthropic_count_report(
                FIXTURE,
                model=MODEL,
                count_tokens=lambda _payload: {"tokens": 10},
            )

    def test_formats_human_report(self) -> None:
        rendered = format_anthropic_count_report(
            build_anthropic_count_report(
                FIXTURE,
                model=MODEL,
                count_tokens=lambda _payload: 10,
            )
        )

        self.assertIn("Token Optimizer Anthropic Benchmark", rendered)
        self.assertIn("Measurement label: anthropic_count_tokens", rendered)
        self.assertIn("Baseline input tokens:", rendered)
        self.assertIn("Limitations:", rendered)

    def test_json_report_is_machine_readable(self) -> None:
        payload = json.loads(
            anthropic_count_report_to_json(
                build_anthropic_count_report(
                    FIXTURE,
                    model=MODEL,
                    count_tokens=lambda _payload: 10,
                )
            )
        )

        self.assertEqual(payload["provider"], "anthropic")
        self.assertEqual(payload["measurementLabel"], "anthropic_count_tokens")
        self.assertIn("baselineInputTokens", payload)
        self.assertIn("optimizedInputTokens", payload)

    def test_zero_baseline_reports_percent_as_unavailable(self) -> None:
        report = build_anthropic_count_report(
            FIXTURE,
            model=MODEL,
            count_tokens=lambda _payload: 0,
        )

        self.assertIsNone(report.reduction_percent)
        self.assertIn(
            "Reduction percent: n/a (baseline is zero)",
            format_anthropic_count_report(report),
        )
        payload = json.loads(anthropic_count_report_to_json(report))
        self.assertIsNone(payload["reductionPercent"])

    def test_rejects_boolean_and_negative_token_counts(self) -> None:
        with self.assertRaises(BenchmarkRunnerError):
            build_anthropic_count_report(
                FIXTURE,
                model=MODEL,
                count_tokens=lambda _payload: True,  # type: ignore[return-value]
            )
        with self.assertRaises(BenchmarkRunnerError):
            build_anthropic_count_report(
                FIXTURE,
                model=MODEL,
                count_tokens=lambda _payload: {"input_tokens": -3},
            )


if __name__ == "__main__":
    unittest.main()
