from __future__ import annotations

import unittest

from token_optimizer.estimator import (
    STATIC_ESTIMATOR_NAME,
    STATIC_MEASUREMENT_LABEL,
    estimate_static_tokens,
)


class StaticEstimatorTests(unittest.TestCase):
    def test_estimates_tokens_with_ceil_bytes_over_four(self) -> None:
        self.assertEqual(estimate_static_tokens(0), 0)
        self.assertEqual(estimate_static_tokens(1), 1)
        self.assertEqual(estimate_static_tokens(4), 1)
        self.assertEqual(estimate_static_tokens(5), 2)

    def test_rejects_negative_byte_count(self) -> None:
        with self.assertRaises(ValueError):
            estimate_static_tokens(-1)

    def test_exposes_static_measurement_label(self) -> None:
        self.assertEqual(STATIC_ESTIMATOR_NAME, "ceil(bytes / 4)")
        self.assertEqual(STATIC_MEASUREMENT_LABEL, "static_estimate")


if __name__ == "__main__":
    unittest.main()
