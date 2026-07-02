"""Shared input-size limits for whole-file reads."""

from __future__ import annotations

from pathlib import Path

# Whole files are loaded into memory (and, for live benchmarks, sent to a
# provider in one request); refuse anything unreasonably large up front.
MAX_INPUT_BYTES = 10 * 1024 * 1024


def require_readable_size(path: Path, *, max_bytes: int = MAX_INPUT_BYTES) -> int:
    """Return the file size, raising ValueError when it exceeds the cap."""

    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(
            f"{path} is {size} bytes; refusing to read files over {max_bytes} bytes"
        )
    return size
