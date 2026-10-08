# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Grok 4.5).
# Updated in whole or in part by AI using Cursor (Composer).
# ==============================================================================
from unittest.mock import MagicMock

from jflow.config.models import (
    AppConfig,
    Defaults,
    IssueTemplate,
    JiraCredentials,
    UserConfig,
)
from jflow.core import JiraClient
from jflow.core.actions.create import create_issue
from jflow.core.actions.fields import decode_field_value, encode_field_value, update_field
from jflow.core.fields import FieldCacheManager
from jflow.core.templates import process_template

# --- decode_field_value ---
assert decode_field_value({"type": "string"}, "hello") == "hello"
assert decode_field_value({"type": "option"}, {"value": "QA"}) == "QA"
assert decode_field_value({"type": "user"}, {"displayName": "Ada", "accountId": "x"}) == "Ada"
assert decode_field_value({"type": "number"}, 5) == 5
assert decode_field_value({"type": "array", "items": "option"}, [{"value": "Impediment"}]) == [
    "Impediment"
]
assert decode_field_value(
    {"type": "array", "items": "component"}, [{"name": "Auth"}, {"name": "API"}]
) == ["Auth", "API"]
assert decode_field_value({"type": "status"}, {"name": "Open"}) == "Open"
assert decode_field_value(None, None) is None
adf = {
    "type": "doc",
    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Body"}]}],
}
assert decode_field_value(
    {
        "type": "string",
        "custom": "com.atlassian.jira.plugin.system.customfieldtypes:textarea",
    },
    adf,
) == "Body"

# --- decode issuelinks ---
_link_type_blocks = {
    "id": "10000",
    "name": "Blocks",
    "inward": "is blocked by",
    "outward": "blocks",
}
_inward_raw = {
    "id": "10001",
    "self": "https://example.atlassian.net/rest/api/3/issueLink/10001",
    "type": _link_type_blocks,
    "inwardIssue": {
        "id": "10002",
        "key": "PROJ-100",
        "self": "https://example.atlassian.net/rest/api/3/issue/10002",
        "fields": {
            "summary": "This is another {name}",
            "status": {"name": "To Do"},
        },
    },
}
_outward_raw = {
    "id": "10003",
    "type": _link_type_blocks,
    "outwardIssue": {
        "key": "PROJ-101",
        "self": "https://example.atlassian.net/rest/api/3/issue/1",
        "fields": {
            "summary": "Blocked work",
            "status": {"name": "In Progress"},
        },
    },
}
assert decode_field_value(
    {"type": "array", "items": "issuelinks", "system": "issuelinks"},
    [_inward_raw],
) == [
    {
        "type": "Blocks",
        "relation": "is blocked by",
        "key": "PROJ-100",
        "summary": "This is another {name}",
        "status": "To Do",
        "url": "https://example.atlassian.net/browse/PROJ-100",
    }
]
assert decode_field_value(
    {"type": "array", "items": "issuelinks"},
    [_outward_raw],
) == [
    {
        "type": "Blocks",
        "relation": "blocks",
        "key": "PROJ-101",
        "summary": "Blocked work",
        "status": "In Progress",
        "url": "https://example.atlassian.net/browse/PROJ-101",
    }
]
assert decode_field_value(
    {"type": "array", "items": "issuelinks", "system": "issuelinks"},
    [],
) == []
# Structural fallback when schema items are unknown
assert decode_field_value({"type": "array"}, [_inward_raw]) == [
    {
        "type": "Blocks",
        "relation": "is blocked by",
        "key": "PROJ-100",
        "summary": "This is another {name}",
        "status": "To Do",
        "url": "https://example.atlassian.net/browse/PROJ-100",
    }
]

# --- defaults.show_fields ---
assert Defaults(show_fields=["summary", "Story Points"]).show_fields == [
    "summary",
    "Story Points",
]
assert Defaults().show_fields is None

# --- encode_field_value ---
assert encode_field_value({"type": "string"}, "hello") == "hello"
from jflow.core.adf import text_to_adf_doc

assert encode_field_value(
    {
        "type": "string",
        "custom": "com.atlassian.jira.plugin.system.customfieldtypes:textarea",
    },
    "hello\nworld",
) == text_to_adf_doc("hello\nworld")
assert encode_field_value({"type": "number"}, "3.5") == 3.5
assert encode_field_value({"type": "option"}, "QA") == {"value": "QA"}
assert encode_field_value({"type": "array", "items": "option"}, "Impediment") == [
    {"value": "Impediment"}
]
assert encode_field_value({"type": "array", "items": "component"}, ["Auth", "API"]) == [
    {"name": "Auth"},
    {"name": "API"},
]
assert encode_field_value({"type": "user"}, "abc-123") == {"accountId": "abc-123"}
assert encode_field_value({"type": "option"}, {"value": "Already"}) == {"value": "Already"}

# --- update_field ---
mock_client = MagicMock(spec=JiraClient)
fields_mgr = MagicMock(spec=FieldCacheManager)
fields_mgr.resolve_field.return_value = {
    "id": "customfield_10100",
    "name": "Environment",
    "custom": True,
    "schema": {"type": "string"},
}
res = update_field(
    mock_client,
    fields_mgr,
    "PROJ-1",
    "Environment",
    "QA",
)
assert res["field_id"] == "customfield_10100"
assert res["value"] == "QA"
mock_client.put.assert_called_once()
assert mock_client.put.call_args.kwargs["payload"] == {
    "fields": {"customfield_10100": "QA"}
}

# --- template components + fields ---
user_cfg = UserConfig(
    jira=JiraCredentials(domain="test.atlassian.net", email="a@b.com", api_token="tok"),
    templates={
        "bug_report": IssueTemplate(
            summary="[BUG] {component}: Issue in {env}",
            description="Steps:\n{steps}",
            issue_type="Bug",
            labels=["bug"],
            components=["{component}"],
            fields={"Environment": "{stage}"},
        )
    },
)
config = AppConfig(user=user_cfg)

rendered = process_template(
    config,
    "bug_report",
    {"component": "Auth", "env": "Prod", "steps": "Click", "stage": "QA"},
)
assert rendered.components == ["Auth"]
assert rendered.fields["Environment"] == "QA"

create_client = MagicMock(spec=JiraClient)
create_client.post.return_value = {"id": "1", "key": "PROJ-9", "self": "http://x"}
create_client.get.return_value = {"baseUrl": "https://test.atlassian.net"}
create_fields = MagicMock(spec=FieldCacheManager)

def resolve_field(name):
    if name == "Environment":
        return {
            "id": "customfield_10100",
            "name": name,
            "schema": {"type": "string"},
        }
    return None

create_fields.resolve_field.side_effect = resolve_field

create_res = create_issue(
    client=create_client,
    config=config,
    fields_mgr=create_fields,
    project="PROJ",
    template_name="bug_report",
    template_vars={"component": "Auth", "env": "Prod", "steps": "Click", "stage": "QA"},
)
assert create_res["key"] == "PROJ-9"
posted = create_client.post.call_args[0][1]["fields"]
assert posted["components"] == [{"name": "Auth"}]
assert posted["customfield_10100"] == "QA"

# --- extra_fields encoding ---
extra_client = MagicMock(spec=JiraClient)
extra_client.post.return_value = {"id": "2", "key": "PROJ-10", "self": "http://x"}
extra_client.get.return_value = {"baseUrl": "https://test.atlassian.net"}
extra_fields_mgr = MagicMock(spec=FieldCacheManager)
extra_fields_mgr.resolve_field.return_value = {
    "id": "customfield_1",
    "name": "Priority Label",
    "schema": {"type": "option"},
}
create_issue(
    client=extra_client,
    config=config,
    fields_mgr=extra_fields_mgr,
    project="PROJ",
    issue_type="Task",
    summary="Extra fields",
    extra_fields={"Priority Label": "High"},
)
extra_posted = extra_client.post.call_args[0][1]["fields"]
assert extra_posted["customfield_1"] == {"value": "High"}

print("✅ Field schema / encoder / template field tests passed successfully!")
