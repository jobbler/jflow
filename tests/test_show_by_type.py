# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# ==============================================================================
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jflow.core.actions.issue_view import get_issue
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager
from jflow.core.formatter import format_output

fields_mgr = MagicMock(spec=FieldCacheManager)
fields_mgr.resolve_field.side_effect = lambda name: (
    {
        "id": "customfield_10016",
        "name": "Story Points",
        "schema": {"type": "number"},
    }
    if name in ("Story Points", "customfield_10016")
    else None
)


def _full_response():
    return {
        "key": "PROJ-1",
        "fields": {
            "summary": "Epic summary",
            "status": {"name": "In Progress"},
            "customfield_10016": 5,
        },
    }


# --- per-type match: second GET fetches the resolved per-type fields ---
client = MagicMock(spec=JiraClient)
client.get.side_effect = [
    {"key": "PROJ-1", "fields": {"issuetype": {"name": "Epic"}}},
    _full_response(),
]
shown = get_issue(
    client,
    "PROJ-1",
    comments="none",
    show_fields_by_type={"Epic": ["summary", "status", "Story Points"]},
    fields_mgr=fields_mgr,
)
assert client.get.call_count == 2
second_kwargs = client.get.call_args_list[1].kwargs
fields_param = second_kwargs.get("params", {}).get("fields", "")
assert "summary" in fields_param
assert "customfield_10016" in fields_param
assert shown["summary"] == "Epic summary"
assert shown["status"] == "In Progress"
assert shown["Story Points"] == 5
text = format_output(shown, format_type="text")
assert "Story Points: 5" in text
# show_fields not passed; per-type list alone drives selection (no built-in fields)
assert "assignee" not in shown

# --- case-insensitive type match (mock says "Epic", config key "epic") ---
client = MagicMock(spec=JiraClient)
client.get.side_effect = [
    {"key": "PROJ-1", "fields": {"issuetype": {"name": "Epic"}}},
    _full_response(),
]
shown = get_issue(
    client,
    "PROJ-1",
    comments="none",
    show_fields_by_type={"epic": ["summary", "Story Points"]},
    show_fields=["status"],
    fields_mgr=fields_mgr,
)
assert shown["summary"] == "Epic summary"
assert shown["Story Points"] == 5
assert "status" not in shown  # per-type replaces show_fields

# --- reverse direction: mock type "epic", config key "Epic" ---
client = MagicMock(spec=JiraClient)
client.get.side_effect = [
    {"key": "PROJ-1", "fields": {"issuetype": {"name": "epic"}}},
    _full_response(),
]
shown = get_issue(
    client,
    "PROJ-1",
    comments="none",
    show_fields_by_type={"Epic": ["summary"]},
    fields_mgr=fields_mgr,
)
assert shown["summary"] == "Epic summary"
assert "status" not in shown

# --- unknown type falls back to show_fields ---
client = MagicMock(spec=JiraClient)
client.get.side_effect = [
    {"key": "PROJ-1", "fields": {"issuetype": {"name": "Bug"}}},
    _full_response(),
]
shown = get_issue(
    client,
    "PROJ-1",
    comments="none",
    show_fields_by_type={"epic": ["summary", "Story Points"]},
    show_fields=["status"],
    fields_mgr=fields_mgr,
)
assert shown["status"] == "In Progress"
assert "summary" not in shown
assert "Story Points" not in shown

# --- empty per-type list = no match, falls through to show_fields ---
client = MagicMock(spec=JiraClient)
client.get.side_effect = [
    {"key": "PROJ-1", "fields": {"issuetype": {"name": "Epic"}}},
    _full_response(),
]
shown = get_issue(
    client,
    "PROJ-1",
    comments="none",
    show_fields_by_type={"epic": []},
    show_fields=["status"],
    fields_mgr=fields_mgr,
)
assert shown["status"] == "In Progress"
assert "summary" not in shown

# --- --only beats per-type map; exactly one GET (no type probe) ---
client = MagicMock(spec=JiraClient)
client.get.return_value = _full_response()
shown = get_issue(
    client,
    "PROJ-1",
    comments="none",
    only=["summary"],
    show_fields_by_type={"Epic": ["status", "Story Points"]},
    fields_mgr=fields_mgr,
)
assert client.get.call_count == 1
fields_param = client.get.call_args.kwargs["params"]["fields"]
assert fields_param == "summary"
assert shown["summary"] == "Epic summary"
assert "status" not in shown

# --- empty requested field masked by default, rendered with show_empty ---
def _empty_response():
    return {
        "key": "PROJ-1",
        "fields": {
            "summary": "Empty points",
            "status": {"name": "Open"},
            "customfield_10016": None,
        },
    }


client = MagicMock(spec=JiraClient)
client.get.side_effect = [
    {"key": "PROJ-1", "fields": {"issuetype": {"name": "Epic"}}},
    _empty_response(),
]
shown = get_issue(
    client,
    "PROJ-1",
    comments="none",
    show_fields_by_type={"Epic": ["summary", "status", "Story Points"]},
    fields_mgr=fields_mgr,
)
assert shown["Story Points"] is None
masked_text = format_output(shown, format_type="text")
assert "Story Points:" not in masked_text
assert "Status: Open" in masked_text

client = MagicMock(spec=JiraClient)
client.get.side_effect = [
    {"key": "PROJ-1", "fields": {"issuetype": {"name": "Epic"}}},
    _empty_response(),
]
shown = get_issue(
    client,
    "PROJ-1",
    comments="none",
    show_fields_by_type={"Epic": ["summary", "status", "Story Points"]},
    show_empty=True,
    fields_mgr=fields_mgr,
)
assert shown["Story Points"] is None
forced_text = format_output(shown, format_type="text")
assert "Story Points:" in forced_text
assert "Status: Open" in forced_text

print("test_show_by_type.py PASSED")
