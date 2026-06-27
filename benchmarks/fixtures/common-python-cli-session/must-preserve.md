# Must Preserve Facts

- Project purpose: local-first context hygiene for AI coding sessions.
- Files inspected: README.md, docs/security-model.md, src/token_optimizer/cli.py.
- Command run: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests.
- Important test output: test_summary_requires_explicit_inputs passed after explicit input handling.
- Decision made: summarize remains canonical and handoff remains an alias.
- Next step: review Fixture Contract before implementing benchmark runner logic.
- Safety warning: no default network calls, daemons, raw transcript capture, raw file-content persistence, or raw tool-output persistence in MVP.
