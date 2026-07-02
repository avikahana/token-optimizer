from __future__ import annotations

import io
import json
import sys
import types
import urllib.error
import unittest
from pathlib import Path
from unittest.mock import patch

from token_optimizer.benchmark_runner import BenchmarkRunnerError
from token_optimizer.openai_benchmark import (
    OPENAI_PROVIDER_USAGE_LABEL,
    OPENAI_TOKENIZER_ESTIMATE_LABEL,
    build_live_openai_usage_report,
    build_openai_usage_payloads,
    build_openai_usage_report,
    build_openai_tokenizer_inputs,
    build_openai_tokenizer_report,
    count_text_tokens_with_tiktoken,
    format_openai_usage_report,
    format_openai_tokenizer_report,
    _NoRedirectHandler,
    _openai_responses_client_factory,
    openai_usage_report_to_json,
    openai_tokenizer_report_to_json,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/fixtures/common-python-cli-session"
)
MODEL = "gpt-test"


class OpenAIBenchmarkTests(unittest.TestCase):
    def test_builds_baseline_and_optimized_tokenizer_inputs(self) -> None:
        baseline, optimized = build_openai_tokenizer_inputs(FIXTURE, model=MODEL)

        self.assertEqual(baseline.side, "baseline")
        self.assertEqual(optimized.side, "optimized")
        self.assertEqual(baseline.model, MODEL)
        self.assertEqual(optimized.model, MODEL)
        self.assertIn("baseline/readme.md", baseline.text)
        self.assertIn("optimized/summary-output.txt", optimized.text)

    def test_rejects_missing_model(self) -> None:
        with self.assertRaises(BenchmarkRunnerError):
            build_openai_tokenizer_inputs(FIXTURE, model=" ")

    def test_builds_tokenizer_report_with_injected_counter(self) -> None:
        seen_models: list[str] = []

        def fake_count(text: str, model: str) -> int:
            seen_models.append(model)
            if "baseline/readme.md" in text:
                return 120
            return 80

        report = build_openai_tokenizer_report(
            FIXTURE,
            model=MODEL,
            count_tokens=fake_count,
        )

        self.assertEqual(seen_models, [MODEL, MODEL])
        self.assertEqual(report.provider, "openai")
        self.assertEqual(report.measurement_label, OPENAI_TOKENIZER_ESTIMATE_LABEL)
        self.assertEqual(report.baseline_input_tokens, 120)
        self.assertEqual(report.optimized_input_tokens, 80)
        self.assertEqual(report.reduction, 40)
        self.assertEqual(report.reduction_percent, 33.33)
        self.assertTrue(all(check.present for check in report.preservation_checks))

    def test_rejects_invalid_counter_result(self) -> None:
        with self.assertRaises(BenchmarkRunnerError):
            build_openai_tokenizer_report(
                FIXTURE,
                model=MODEL,
                count_tokens=lambda _text, _model: "10",  # type: ignore[return-value]
            )

    def test_formats_human_report(self) -> None:
        rendered = format_openai_tokenizer_report(
            build_openai_tokenizer_report(
                FIXTURE,
                model=MODEL,
                count_tokens=lambda _text, _model: 10,
            )
        )

        self.assertIn("Token Optimizer OpenAI Benchmark", rendered)
        self.assertIn("Measurement label: openai_tokenizer_estimate", rendered)
        self.assertIn("Baseline input tokens:", rendered)
        self.assertIn("Limitations:", rendered)

    def test_json_report_is_machine_readable(self) -> None:
        payload = json.loads(
            openai_tokenizer_report_to_json(
                build_openai_tokenizer_report(
                    FIXTURE,
                    model=MODEL,
                    count_tokens=lambda _text, _model: 10,
                )
            )
        )

        self.assertEqual(payload["provider"], "openai")
        self.assertEqual(payload["measurementLabel"], "openai_tokenizer_estimate")
        self.assertIn("baselineInputTokens", payload)
        self.assertIn("optimizedInputTokens", payload)

    def test_builds_live_usage_payloads(self) -> None:
        baseline, optimized = build_openai_usage_payloads(
            FIXTURE,
            model=MODEL,
            max_output_tokens=16,
        )

        self.assertEqual(baseline.side, "baseline")
        self.assertEqual(optimized.side, "optimized")
        self.assertEqual(baseline.payload["model"], MODEL)
        self.assertEqual(baseline.payload["max_output_tokens"], 16)
        self.assertFalse(baseline.payload["store"])
        self.assertIn("baseline/readme.md", baseline.payload["input"])
        self.assertIn("optimized/summary-output.txt", optimized.payload["input"])

    def test_builds_usage_report_with_injected_response_client(self) -> None:
        seen_payloads: list[dict[str, object]] = []

        def fake_create_response(payload: dict[str, object]) -> dict[str, object]:
            seen_payloads.append(payload)
            if "baseline/readme.md" in str(payload["input"]):
                return {"usage": {"input_tokens": 120, "output_tokens": 1, "total_tokens": 121}}
            return {"usage": {"input_tokens": 80, "output_tokens": 1, "total_tokens": 81}}

        report = build_openai_usage_report(
            FIXTURE,
            model=MODEL,
            create_response=fake_create_response,
        )

        self.assertEqual(len(seen_payloads), 2)
        self.assertEqual(report.provider, "openai")
        self.assertEqual(report.measurement_label, OPENAI_PROVIDER_USAGE_LABEL)
        self.assertEqual(report.baseline_input_tokens, 120)
        self.assertEqual(report.optimized_input_tokens, 80)
        self.assertEqual(report.baseline_output_tokens, 1)
        self.assertEqual(report.optimized_output_tokens, 1)
        self.assertEqual(report.baseline_total_tokens, 121)
        self.assertEqual(report.optimized_total_tokens, 81)
        self.assertEqual(report.reduction, 40)
        self.assertEqual(report.reduction_percent, 33.33)
        self.assertTrue(all(check.present for check in report.preservation_checks))

    def test_live_usage_requires_openai_api_key(self) -> None:
        with self.assertRaises(BenchmarkRunnerError):
            build_live_openai_usage_report(FIXTURE, model=MODEL, environ={})

    def test_live_usage_uses_injected_client_factory(self) -> None:
        seen_keys: list[str] = []

        def fake_factory(api_key: str):
            seen_keys.append(api_key)

            def fake_create_response(payload: dict[str, object]) -> dict[str, object]:
                if "baseline/readme.md" in str(payload["input"]):
                    return {
                        "usage": {
                            "input_tokens": 100,
                            "output_tokens": 1,
                            "total_tokens": 101,
                        }
                    }
                return {"usage": {"input_tokens": 50, "output_tokens": 1, "total_tokens": 51}}

            return fake_create_response

        report = build_live_openai_usage_report(
            FIXTURE,
            model=MODEL,
            environ={"OPENAI_API_KEY": "secret"},
            client_factory=fake_factory,
        )

        self.assertEqual(seen_keys, ["secret"])
        self.assertEqual(report.measurement_label, "openai_provider_usage")
        self.assertEqual(report.baseline_input_tokens, 100)
        self.assertEqual(report.optimized_input_tokens, 50)

    def test_usage_report_rejects_missing_usage(self) -> None:
        with self.assertRaises(BenchmarkRunnerError):
            build_openai_usage_report(
                FIXTURE,
                model=MODEL,
                create_response=lambda _payload: {},
            )

    def test_formats_usage_report(self) -> None:
        rendered = format_openai_usage_report(
            build_openai_usage_report(
                FIXTURE,
                model=MODEL,
                create_response=lambda _payload: {
                    "usage": {"input_tokens": 10, "output_tokens": 1, "total_tokens": 11}
                },
            )
        )

        self.assertIn("Token Optimizer OpenAI Usage Benchmark", rendered)
        self.assertIn("Measurement label: openai_provider_usage", rendered)
        self.assertIn("Baseline total tokens:", rendered)
        self.assertIn("Limitations:", rendered)

    def test_usage_json_report_is_machine_readable(self) -> None:
        payload = json.loads(
            openai_usage_report_to_json(
                build_openai_usage_report(
                    FIXTURE,
                    model=MODEL,
                    create_response=lambda _payload: {
                        "usage": {"input_tokens": 10, "output_tokens": 1, "total_tokens": 11}
                    },
                )
            )
        )

        self.assertEqual(payload["provider"], "openai")
        self.assertEqual(payload["measurementLabel"], "openai_provider_usage")
        self.assertIn("baselineTotalTokens", payload)
        self.assertIn("optimizedTotalTokens", payload)

    def test_live_http_error_body_is_truncated(self) -> None:
        error = urllib.error.HTTPError(
            url="https://api.openai.com/v1/responses",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b"x" * 1000),
        )
        client = _openai_responses_client_factory("secret")

        with patch("token_optimizer.openai_benchmark._urlopen_no_redirect", side_effect=error):
            with self.assertRaises(BenchmarkRunnerError) as raised:
                client({"model": MODEL, "input": "hello"})

        message = str(raised.exception)
        self.assertIn("[truncated]", message)
        self.assertLess(len(message), 700)
        self.assertNotIn("secret", message)

    def test_live_url_error_is_wrapped_without_leaking_the_key(self) -> None:
        client = _openai_responses_client_factory("secret")

        with patch(
            "token_optimizer.openai_benchmark._urlopen_no_redirect",
            side_effect=urllib.error.URLError("dns failure"),
        ):
            with self.assertRaises(BenchmarkRunnerError) as raised:
                client({"model": MODEL, "input": "hello"})

        message = str(raised.exception)
        self.assertIn("dns failure", message)
        self.assertNotIn("secret", message)

    def test_redirect_handler_refuses_to_follow_redirects(self) -> None:
        handler = _NoRedirectHandler()

        self.assertIsNone(
            handler.redirect_request(
                None, None, 302, "Found", {}, "https://evil.example/steal"
            )
        )

    def test_live_request_retries_retryable_statuses_then_succeeds(self) -> None:
        class _FakeResponse:
            def __init__(self, payload: dict) -> None:
                self._data = json.dumps(payload).encode("utf-8")

            def read(self) -> bytes:
                return self._data

            def __enter__(self) -> "_FakeResponse":
                return self

            def __exit__(self, *_args: object) -> bool:
                return False

        rate_limited = urllib.error.HTTPError(
            url="https://api.openai.com/v1/responses",
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=io.BytesIO(b"slow down"),
        )
        usage = {"usage": {"input_tokens": 10, "output_tokens": 1, "total_tokens": 11}}
        client = _openai_responses_client_factory("secret")

        with patch(
            "token_optimizer.openai_benchmark._urlopen_no_redirect",
            side_effect=[rate_limited, _FakeResponse(usage)],
        ) as opened, patch("token_optimizer.openai_benchmark.time.sleep") as slept:
            result = client({"model": MODEL, "input": "hello"})

        self.assertEqual(result, usage)
        self.assertEqual(opened.call_count, 2)
        slept.assert_called_once()

    def test_live_request_does_not_retry_non_retryable_status(self) -> None:
        bad_request = urllib.error.HTTPError(
            url="https://api.openai.com/v1/responses",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b"nope"),
        )
        client = _openai_responses_client_factory("secret")

        with patch(
            "token_optimizer.openai_benchmark._urlopen_no_redirect",
            side_effect=bad_request,
        ) as opened, patch("token_optimizer.openai_benchmark.time.sleep") as slept:
            with self.assertRaises(BenchmarkRunnerError):
                client({"model": MODEL, "input": "hello"})

        self.assertEqual(opened.call_count, 1)
        slept.assert_not_called()

    def test_zero_baseline_reports_percent_as_unavailable(self) -> None:
        report = build_openai_tokenizer_report(
            FIXTURE,
            model=MODEL,
            count_tokens=lambda _text, _model: 0,
        )

        self.assertIsNone(report.reduction_percent)
        self.assertIn(
            "Reduction percent: n/a (baseline is zero)",
            format_openai_tokenizer_report(report),
        )
        payload = json.loads(openai_tokenizer_report_to_json(report))
        self.assertIsNone(payload["reductionPercent"])

    def test_rejects_boolean_and_negative_token_counts(self) -> None:
        with self.assertRaises(BenchmarkRunnerError):
            build_openai_tokenizer_report(
                FIXTURE,
                model=MODEL,
                count_tokens=lambda _text, _model: True,  # type: ignore[return-value]
            )
        with self.assertRaises(BenchmarkRunnerError):
            build_openai_tokenizer_report(
                FIXTURE,
                model=MODEL,
                count_tokens=lambda _text, _model: -1,
            )

    def test_usage_report_rejects_boolean_usage_fields(self) -> None:
        with self.assertRaises(BenchmarkRunnerError):
            build_openai_usage_report(
                FIXTURE,
                model=MODEL,
                create_response=lambda _payload: {
                    "usage": {"input_tokens": True, "output_tokens": 1, "total_tokens": 2}
                },
            )

    def test_tiktoken_counter_uses_model_encoding_when_known(self) -> None:
        class _Encoding:
            def encode(self, text: str) -> list[int]:
                return list(range(len(text)))

        fake = types.ModuleType("tiktoken")
        fake.encoding_for_model = lambda _model: _Encoding()
        fake.get_encoding = lambda _name: self.fail("fallback must not be used")

        with patch.dict(sys.modules, {"tiktoken": fake}):
            self.assertEqual(count_text_tokens_with_tiktoken("hi", MODEL), 2)

    def test_tiktoken_counter_falls_back_to_o200k_base_for_unknown_model(self) -> None:
        class _Encoding:
            def encode(self, text: str) -> list[int]:
                return list(range(len(text)))

        requested: list[str] = []

        def get_encoding(name: str) -> _Encoding:
            requested.append(name)
            return _Encoding()

        def encoding_for_model(model: str) -> _Encoding:
            raise KeyError(model)

        fake = types.ModuleType("tiktoken")
        fake.encoding_for_model = encoding_for_model
        fake.get_encoding = get_encoding

        with patch.dict(sys.modules, {"tiktoken": fake}):
            self.assertEqual(count_text_tokens_with_tiktoken("hey", "unknown-model"), 3)

        self.assertEqual(requested, ["o200k_base"])


if __name__ == "__main__":
    unittest.main()
