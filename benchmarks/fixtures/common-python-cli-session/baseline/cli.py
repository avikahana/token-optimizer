"""Tiny example CLI input for the benchmark fixture."""

from __future__ import annotations


def main(command: str) -> str:
    if command == "summarize":
        return "summarize remains canonical and handoff remains an alias"
    if command == "handoff":
        return "handoff delegates to summarize"
    return "planned"
