# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
"""Structured issue / markdown / date formatting tests for the CLI formatter."""
from jflow.core.formatter import (
    flatten_dict,
    format_output,
    format_timestamp_human,
)

nested = {
    "client": {"version": "0.1.0"},
    "me": {"name": "Ada", "email": "ada@example.com"},
    "server": {"url": "https://example.atlassian.net", "version": "1000"},
}

flat = flatten_dict(nested)
assert flat["client.version"] == "0.1.0"
assert flat["me.name"] == "Ada"
assert flat["me.email"] == "ada@example.com"
assert flat["server.url"] == "https://example.atlassian.net"
assert flat["server.version"] == "1000"

text_out = format_output(nested, format_type="text")
assert "client:" in text_out
assert "  version: 0.1.0" in text_out
assert "me:" in text_out
assert "  name: Ada" in text_out
assert "server:" in text_out
assert "  url: https://example.atlassian.net" in text_out
assert "me.name" not in text_out
assert "┏" not in text_out
assert "jflow Output" not in text_out

unix_out = format_output(nested, format_type="unix")
assert "me.name=Ada" in unix_out
assert "server.url=https://example.atlassian.net" in unix_out

json_out = format_output(nested, format_type="json")
assert '"me"' in json_out
assert "me.name" not in json_out

# Flat dict (no nested dicts) stays undotted
flat_only = format_output({"a": 1, "b": 2}, format_type="text")
assert flat_only == "a: 1\nb: 2"

# List-of-dicts: aligned columns, no boxes
list_out = format_output(
    [{"Key": "PROJ-1", "Status": "Open"}, {"Key": "PROJ-2", "Status": "Done"}],
    format_type="text",
)
assert "Key" in list_out
assert "PROJ-1" in list_out
assert "┏" not in list_out

# --- timestamps: local + ISO ---
iso = "2026-09-20T14:32:11.000+0000"
human_ts = format_timestamp_human(iso)
assert iso in human_ts
assert human_ts.endswith(f"({iso})")
assert "2026-09-20" in human_ts
assert format_timestamp_human("not-a-date") == "not-a-date"

# --- issue detail: markdown separates title / metadata / comments ---
issue = {
    "key": "PROJ-123",
    "summary": "Fix null pointer",
    "type": "Bug",
    "status": "In Progress",
    "assignee": "Alice",
    "reporter": "Bob",
    "priority": "High",
    "labels": ["auth"],
    "components": [],
    "parent": "",
    "created": iso,
    "updated": iso,
    "description": "Line one\nLine two",
    "comments": [
        {
            "id": "1",
            "author": "Alice",
            "created": "2026-09-20T15:00:00.000+0000",
            "body": "First comment",
        },
        {
            "id": "2",
            "author": "Bob",
            "created": "2026-09-21T16:00:00.000+0000",
            "body": "Second comment",
        },
    ],
}

md = format_output(issue, format_type="markdown")
assert md.startswith("# PROJ-123: Fix null pointer")
assert "**Type:** Bug" in md
assert "**Status:** In Progress" in md
assert "Components:" not in md  # empty skipped
assert "Parent:" not in md
assert "## Description" in md
assert "Line one\nLine two" in md
assert "## Comments" in md
assert "### Alice —" in md
assert "First comment" in md
assert "### Bob —" in md
assert "Second comment" in md
assert " | " not in md  # comments must not be scalar-joined
assert iso in md  # ISO retained alongside local

text_issue = format_output(issue, format_type="text")
assert text_issue.startswith("PROJ-123: Fix null pointer")
assert "Type: Bug" in text_issue
assert "Description" in text_issue
assert "  Line one" in text_issue
assert "Comments" in text_issue
assert "[Alice —" in text_issue
assert "  First comment" in text_issue
assert "[Bob —" in text_issue
assert " | " not in text_issue

# json keeps raw ISO, no local dual form wrapper required beyond original string
json_issue = format_output(issue, format_type="json")
assert iso in json_issue
assert '"comments"' in json_issue

# markdown list of issues
md_list = format_output(
    [
        {"Key": "PROJ-1", "Type": "Bug", "Summary": "One", "Status": "Open", "Assignee": "Ada"},
        {"Key": "PROJ-2", "Type": "Task", "Summary": "Two", "Status": "Done", "Assignee": "Bob"},
    ],
    format_type="markdown",
)
assert "- **PROJ-1**" in md_list
assert "One" in md_list
assert "- **PROJ-2**" in md_list

# default format is markdown
default_out = format_output({"key": "X-1", "summary": "Hi", "status": "Open"})
assert default_out.startswith("# X-1: Hi")

# --- linked issues: grouped by directional relation ---
linked_issue = {
    "key": "PROJ-1",
    "summary": "Parent",
    "status": "Open",
    "Linked Issues": [
        {
            "type": "Blocks",
            "relation": "is blocked by",
            "key": "PROJ-100",
            "summary": "This is another {name}",
            "status": "To Do",
            "url": "https://example.atlassian.net/browse/PROJ-100",
        },
        {
            "type": "Blocks",
            "relation": "blocks",
            "key": "PROJ-101",
            "summary": "Blocked work",
            "status": "In Progress",
            "url": "https://example.atlassian.net/browse/PROJ-101",
        },
        {
            "type": "Blocks",
            "relation": "blocks",
            "key": "PROJ-102",
            "summary": "Also blocked",
            "status": "To Do",
            "url": "https://example.atlassian.net/browse/PROJ-102",
        },
        {
            "type": "Relates",
            "relation": "relates to",
            "key": "PROJ-50",
            "summary": "Related item",
            "status": "Done",
            "url": "https://example.atlassian.net/browse/PROJ-50",
        },
    ],
}
linked_text = format_output(linked_issue, format_type="text")
assert "Linked Issues:" in linked_text
assert "  Is blocked by:" in linked_text
assert "    PROJ-100 To Do This is another {name}" in linked_text
assert "  Blocks:" in linked_text
assert "    PROJ-101 In Progress Blocked work" in linked_text
assert "    PROJ-102 To Do Also blocked" in linked_text
assert "  Relates to:" in linked_text
assert "    PROJ-50 Done Related item" in linked_text
assert "relation=" not in linked_text
assert "url=" not in linked_text
# Directional Blocks relations are separate; same relation shares one heading
assert linked_text.count("  Blocks:") == 1
assert linked_text.count("  Is blocked by:") == 1
blocked_by_idx = linked_text.index("  Is blocked by:")
blocks_idx = linked_text.index("  Blocks:")
relates_idx = linked_text.index("  Relates to:")
assert blocked_by_idx < blocks_idx < relates_idx

linked_md = format_output(linked_issue, format_type="markdown")
assert "**Linked Issues:**" in linked_md
assert "  Is blocked by:" in linked_md
assert "  Blocks:" in linked_md
assert "    PROJ-100 To Do This is another {name}" in linked_md
assert "  Relates to:" in linked_md
assert "relation=" not in linked_md

print("✅ Formatter nested-flatten / issue-layout tests passed successfully!")
