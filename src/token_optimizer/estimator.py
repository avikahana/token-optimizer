"""Provider-neutral token estimation helpers."""

from __future__ import annotations

import math


STATIC_ESTIMATOR_NAME = "ceil(bytes / 4)"
STATIC_MEASUREMENT_LABEL = "static_estimate"


def estimate_static_tokens(byte_count: int) -> int:
    """Estimate provider-neutral tokens from byte count."""

    if byte_count < 0:
        raise ValueError("byte_count must be non-negative")
    return math.ceil(byte_count / 4)
