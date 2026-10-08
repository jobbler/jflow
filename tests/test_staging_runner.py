# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from jflow.staging.context import VALID_GROUPS
from jflow.staging.runner import parse_groups

assert parse_groups("all") == set(VALID_GROUPS)
assert parse_groups("system,search") == {"system", "search"}
assert parse_groups(" ISSUE ") == {"issue"}

try:
    parse_groups("system,nope")
    assert False, "expected ValueError for unknown group"
except ValueError as exc:
    assert "Unknown group" in str(exc)

print("✅ Staging runner parse_groups tests passed successfully!")
