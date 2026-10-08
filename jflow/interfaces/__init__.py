# ==============================================================================
# jflow - CLI for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Composer).
# ==============================================================================
"""CLI package. Avoid eager imports so ``python -m jflow.interfaces.cli`` works cleanly."""

from typing import Any

__all__ = ["cli_app"]


def __getattr__(name: str) -> Any:
    if name == "cli_app":
        from .cli import app as cli_app

        return cli_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
