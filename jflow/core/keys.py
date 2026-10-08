# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# ==============================================================================
# Created in whole or in part by AI using Cursor (Composer).
"""Issue-key helpers."""


def normalize_issue_key(key: str) -> str:
    """Return a canonical Jira issue key (trimmed, uppercase).

    Agile APIs (e.g. sprint move) reject lowercase keys even when the core
    REST API accepts them.
    """
    return (key or "").strip().upper()
