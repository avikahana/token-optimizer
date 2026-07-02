from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from token_optimizer.limits import MAX_INPUT_BYTES, require_readable_size


class LimitsTests(unittest.TestCase):
    def test_allows_files_at_or_under_the_cap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "small.txt"
            path.write_text("ok", encoding="utf-8")

            self.assertEqual(require_readable_size(path), 2)
            self.assertEqual(require_readable_size(path, max_bytes=2), 2)

    def test_rejects_files_over_the_cap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "big.txt"
            path.write_text("0123456789", encoding="utf-8")

            with self.assertRaises(ValueError) as raised:
                require_readable_size(path, max_bytes=4)

            self.assertIn("refusing to read", str(raised.exception))

    def test_default_cap_is_ten_mebibytes(self) -> None:
        self.assertEqual(MAX_INPUT_BYTES, 10 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
