# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
# Updated in whole or in part by AI using Cursor (Composer).
from unittest.mock import MagicMock

from jflow.core.actions.issue_view import get_issue, needs_field_cache, parse_comments_arg
from jflow.core.actions.search import build_my_issues_jql, list_my_issues
from jflow.core.adf import adf_to_text
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager
from jflow.core.formatter import format_output

# --- adf_to_text ---
doc = {
    "type": "doc",
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "Hello"}]},
        {"type": "paragraph", "content": [{"type": "text", "text": "World"}]},
    ],
}
assert adf_to_text(doc) == "Hello\nWorld"
assert adf_to_text(None) == ""

# --- parse_comments_arg ---
assert parse_comments_arg("none") == ("none", None)
assert parse_comments_arg("last") == ("last", 2)
assert parse_comments_arg("all") == ("all", None)
assert parse_comments_arg("3") == ("last", 3)
try:
    parse_comments_arg("nope")
    raise AssertionError("expected ValueError")
except ValueError:
    pass

# --- build_my_issues_jql ---
assert "statusCategory != Done" in build_my_issues_jql("open")
assert 'status = "Blocked"' in build_my_issues_jql(status="Blocked")
assert build_my_issues_jql(jql="project = X") == "project = X"

# --- get_issue with comments last ---
client = MagicMock(spec=JiraClient)
client.get.side_effect = [
    {
        "key": "PROJ-1",
        "fields": {
            "summary": "Test",
            "status": {"name": "Open"},
            "issuetype": {"name": "Task"},
            "assignee": {"displayName": "Ada"},
            "reporter": {"displayName": "Bob"},
            "priority": {"name": "Medium"},
            "labels": ["a"],
            "components": [{"name": "API"}],
            "parent": {},
            "created": "2026-01-01",
            "updated": "2026-01-02",
            "description": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Desc"}]}]},
        },
    },
    {
        "comments": [
            {
                "id": "1",
                "author": {"displayName": "A"},
                "created": "2026-01-01",
                "body": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "c1"}]}]},
            },
            {
                "id": "2",
                "author": {"displayName": "B"},
                "created": "2026-01-02",
                "body": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "c2"}]}]},
            },
            {
                "id": "3",
                "author": {"displayName": "C"},
                "created": "2026-01-03",
                "body": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "c3"}]}]},
            },
        ],
        "total": 3,
    },
]
shown = get_issue(client, "PROJ-1", comments="last")
assert shown["key"] == "PROJ-1"
assert shown["description"] == "Desc"
assert len(shown["comments"]) == 2
assert shown["comments"][0]["body"] == "c2"
assert shown["comments"][1]["body"] == "c3"

client.get.side_effect = [
    {
        "key": "PROJ-1",
        "fields": {
            "summary": "Test",
            "status": {"name": "Open"},
            "issuetype": {"name": "Task"},
            "assignee": None,
            "reporter": None,
            "priority": {},
            "labels": [],
            "components": [],
            "parent": {},
            "created": "",
            "updated": "",
            "description": None,
        },
    }
]
partial = get_issue(client, "PROJ-1", comments="none", only=["status", "summary"])
assert partial["key"] == "PROJ-1"
assert partial["status"] == "Open"
assert partial["summary"] == "Test"
assert "status" in partial and "summary" in partial

# --- needs_field_cache ---
assert needs_field_cache(None) is False
assert needs_field_cache(["status", "summary"]) is False
assert needs_field_cache(["Story Points"]) is True

# --- show_fields config with custom field ---
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
custom_client = MagicMock(spec=JiraClient)
custom_client.get.return_value = {
    "key": "PROJ-2",
    "fields": {
        "summary": "With points",
        "status": {"name": "In Progress"},
        "customfield_10016": 5,
    },
}
custom_shown = get_issue(
    custom_client,
    "PROJ-2",
    comments="none",
    show_fields=["summary", "status", "Story Points"],
    fields_mgr=fields_mgr,
)
assert custom_shown["key"] == "PROJ-2"
assert custom_shown["summary"] == "With points"
assert custom_shown["status"] == "In Progress"
assert custom_shown["Story Points"] == 5
# Requested Story Points + system fields; API fields= should include customfield id
args, kwargs = custom_client.get.call_args
params = kwargs.get("params") or {}
assert "customfield_10016" in params.get("fields", "")
assert "summary" in params.get("fields", "")

# Empty explicitly-requested custom fields still render in text/markdown
empty_client = MagicMock(spec=JiraClient)
empty_client.get.return_value = {
    "key": "PROJ-4",
    "fields": {
        "summary": "Empty customs",
        "status": {"name": "Open"},
        "customfield_10016": None,
    },
}
empty_shown = get_issue(
    empty_client,
    "PROJ-4",
    comments="none",
    show_fields=["summary", "status", "Story Points"],
    fields_mgr=fields_mgr,
)
assert empty_shown["Story Points"] is None
empty_text = format_output(empty_shown, format_type="text")
assert "Story Points:" in empty_text
assert "Status: Open" in empty_text
# Internal order key must not leak into json
empty_json = format_output(empty_shown, format_type="json")
assert "_jflow_field_order" not in empty_json
assert "Story Points" in empty_json

# --- --only overrides show_fields ---
override_client = MagicMock(spec=JiraClient)
override_client.get.return_value = {
    "key": "PROJ-3",
    "fields": {
        "status": {"name": "Done"},
    },
}
overridden = get_issue(
    override_client,
    "PROJ-3",
    comments="none",
    only=["status"],
    show_fields=["summary", "status", "Story Points"],
    fields_mgr=fields_mgr,
)
assert overridden["key"] == "PROJ-3"
assert overridden["status"] == "Done"
assert "summary" not in overridden
args, kwargs = override_client.get.call_args
params = kwargs.get("params") or {}
assert params.get("fields") == "status"

# --- list_my_issues wires search ---
search_client = MagicMock(spec=JiraClient)
search_client.post.return_value = {
    "issues": [
        {
            "key": "PROJ-9",
            "fields": {
                "summary": "Mine",
                "status": {"name": "Open"},
                "issuetype": {"name": "Bug"},
                "assignee": {"displayName": "Me"},
            },
        }
    ]
}
listed = list_my_issues(search_client, filter_name="open", max_results=5)
assert listed[0]["Key"] == "PROJ-9"
args, kwargs = search_client.post.call_args
payload = kwargs.get("payload") if kwargs else None
if payload is None:
    payload = args[1] if len(args) > 1 else None
assert payload and "statusCategory != Done" in payload["jql"]

# --- unix format ---
unix_dict = format_output({"a": 1, "b": "x"}, format_type="unix")
assert unix_dict == "a=1\nb=x"
unix_list = format_output([{"Key": "A", "Status": "Open"}], format_type="unix")
assert unix_list.splitlines()[0] == "Key\tStatus"
assert "A\tOpen" in unix_list

print("✅ Issue show/list/formatter tests passed successfully!")
