from __future__ import annotations

import unittest
from pathlib import Path


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/fixtures/common-python-cli-session"
)


class BenchmarkFixtureContractTests(unittest.TestCase):
    def test_fixture_contract_files_exist(self) -> None:
        self.assertTrue((FIXTURE / "fixture.md").is_file())
        self.assertTrue((FIXTURE / "must-preserve.md").is_file())
        self.assertTrue((FIXTURE / "baseline").is_dir())
        self.assertTrue((FIXTURE / "optimized").is_dir())

    def test_baseline_and_optimized_sides_have_inputs(self) -> None:
        baseline_files = sorted(path.name for path in (FIXTURE / "baseline").iterdir())
        optimized_files = sorted(path.name for path in (FIXTURE / "optimized").iterdir())

        self.assertIn("readme.md", baseline_files)
        self.assertIn("security-model.md", baseline_files)
        self.assertIn("cli.py", baseline_files)
        self.assertIn("test-output.txt", baseline_files)
        self.assertIn("continuation-note.md", baseline_files)
        self.assertIn("outline-output.txt", optimized_files)
        self.assertIn("summary-output.txt", optimized_files)

    def test_must_preserve_facts_appear_in_optimized_output(self) -> None:
        facts = _must_preserve_facts()
        optimized_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((FIXTURE / "optimized").iterdir())
            if path.is_file()
        )

        for fact in facts:
            with self.subTest(fact=fact):
                self.assertIn(fact, optimized_text)


def _must_preserve_facts() -> list[str]:
    facts: list[str] = []
    for line in (FIXTURE / "must-preserve.md").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            facts.append(stripped[2:])
    return facts


if __name__ == "__main__":
    unittest.main()
