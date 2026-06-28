from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from token_optimizer.cli import main


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/fixtures/common-python-cli-session"
)


FORBIDDEN_NETWORK_TOKENS = (
    "http.client",
    "httpx",
    "requests",
    "socket",
    "urllib",
)


class NoNetworkTests(unittest.TestCase):
    def test_default_source_does_not_import_network_clients(self) -> None:
        source_root = Path(__file__).resolve().parents[1] / "src"
        allowed_live_provider_files = {
            source_root / "token_optimizer/openai_benchmark.py",
        }
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in source_root.rglob("*.py")
            if path not in allowed_live_provider_files
        )

        for token in FORBIDDEN_NETWORK_TOKENS:
            self.assertNotIn(token, source)

    def test_default_cli_paths_do_not_open_network_sockets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            note = project / "note.md"
            note.write_text("# Note\n\nKeep default paths local.\n", encoding="utf-8")
            (project / "README.md").write_text("# Project\n", encoding="utf-8")
            commands = [
                ["doctor", "--json"],
                ["audit", "--project", str(project), "--json"],
                ["dashboard", "--project", str(project), "--dry-run", "--json"],
                ["config", "init", "--project", str(project), "--dry-run", "--json"],
                ["purge", "--project", str(project), "--dry-run", "--json"],
                ["hooks", "install", "--project", str(project), "--dry-run", "--json"],
                ["hooks", "uninstall", "--project", str(project), "--dry-run", "--json"],
                ["outline", str(note)],
                ["summarize", str(note)],
                ["handoff", str(note)],
                ["benchmark", "--fixture", str(FIXTURE), "--json"],
            ]

            for command in commands:
                with self.subTest(command=command):
                    output = io.StringIO()
                    with patch.dict(
                        "os.environ",
                        {
                            "OPENAI_API_KEY": "unused",
                            "ANTHROPIC_API_KEY": "unused",
                        },
                        clear=True,
                    ), patch(
                        "socket.socket",
                        side_effect=AssertionError("default CLI path opened a socket"),
                    ), patch(
                        "socket.create_connection",
                        side_effect=AssertionError(
                            "default CLI path opened a socket connection"
                        ),
                    ), redirect_stdout(
                        output
                    ):
                        status = main(command)

                    self.assertEqual(status, 0, output.getvalue())


if __name__ == "__main__":
    unittest.main()
