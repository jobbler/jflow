# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Composer).
# ==============================================================================
from unittest.mock import MagicMock, call

from jflow.config.models import (
    AppConfig,
    Defaults,
    IssueTemplate,
    JiraCredentials,
    UserConfig,
)
from jflow.core import JiraClient
from jflow.core.actions.create import CURRENT_SPRINT_TOKEN, create_issue
from jflow.core.actions.fields import update_pull_request
from jflow.core.actions.links import link_issues, resolve_link_type
from jflow.core.fields import FieldCacheManager

# --- resolve_link_type ---
assert resolve_link_type() == ("Relates", False)
assert resolve_link_type(relates=True) == ("Relates", False)
assert resolve_link_type(blocks=True) == ("Blocks", False)
assert resolve_link_type(blocked_by=True) == ("Blocks", True)
assert resolve_link_type(clones=True) == ("Clones", False)
assert resolve_link_type(cloned_by=True) == ("Clones", True)
assert resolve_link_type(duplicates=True) == ("Duplicate", False)
assert resolve_link_type(duplicated_by=True) == ("Duplicate", True)
assert resolve_link_type(link_type="Custom Link") == ("Custom Link", False)

try:
    resolve_link_type(blocks=True, relates=True)
    assert False, "expected mutual exclusion error"
except ValueError as exc:
    assert "only one" in str(exc).lower()

try:
    resolve_link_type(blocks=True, link_type="Relates")
    assert False, "expected mutual exclusion with --type"
except ValueError as exc:
    assert "only one" in str(exc).lower()

# --- link_issues ---
mock_client = MagicMock(spec=JiraClient)
res = link_issues(mock_client, "proj-1", "proj-2", type_name="Blocks", swap=False)
assert res["from"] == "PROJ-1"
assert res["to"] == "PROJ-2"
assert res["outward"] == "PROJ-1"
assert res["inward"] == "PROJ-2"
assert res["type"] == "Blocks"
mock_client.post.assert_called_once_with(
    "/rest/api/3/issueLink",
    payload={
        "type": {"name": "Blocks"},
        "outwardIssue": {"key": "PROJ-1"},
        "inwardIssue": {"key": "PROJ-2"},
    },
)

mock_client.reset_mock()
res = link_issues(mock_client, "PROJ-1", "PROJ-2", type_name="Blocks", swap=True)
assert res["outward"] == "PROJ-2"
assert res["inward"] == "PROJ-1"

# --- @current_sprint on create ---
user_cfg = UserConfig(
    jira=JiraCredentials(domain="test.atlassian.net", email="a@b.com", api_token="tok"),
    defaults=Defaults(project="PROJ", board="42"),
    templates={
        "sprinted": IssueTemplate(
            summary="In sprint work",
            issue_type="Task",
            fields={"Sprint": CURRENT_SPRINT_TOKEN},
        )
    },
)
config = AppConfig(user=user_cfg)
mock_client = MagicMock(spec=JiraClient)


def _create_side_effect(endpoint, payload=None):
    if endpoint == "/rest/api/3/issue":
        # Sprint token must not appear in create payload
        fields = (payload or {}).get("fields") or {}
        assert CURRENT_SPRINT_TOKEN not in str(fields)
        assert "Sprint" not in fields
        return {"key": "PROJ-500", "id": "500"}
    if endpoint.startswith("/rest/agile/1.0/sprint/"):
        return {}
    return {}


mock_client.post.side_effect = _create_side_effect
mock_client.get.side_effect = lambda endpoint, params=None: {
    "/rest/api/3/serverInfo": {"baseUrl": "https://test.atlassian.net"},
    "/rest/agile/1.0/board/42/sprint": {
        "values": [{"id": 99, "name": "Sprint 99", "state": "active"}]
    },
}.get(endpoint, {})

fields_mgr = MagicMock(spec=FieldCacheManager)
created = create_issue(
    client=mock_client,
    config=config,
    fields_mgr=fields_mgr,
    template_name="sprinted",
)
assert created["key"] == "PROJ-500"
assert created["url"] == "https://test.atlassian.net/browse/PROJ-500"
# create + sprint add
assert mock_client.post.call_count == 2
sprint_call = mock_client.post.call_args_list[1]
assert sprint_call == call(
    "/rest/agile/1.0/sprint/99/issue", payload={"issues": ["PROJ-500"]}
)

# Missing board should error
no_board = AppConfig(
    user=UserConfig(
        jira=JiraCredentials(
            domain="test.atlassian.net", email="a@b.com", api_token="tok"
        ),
        defaults=Defaults(project="PROJ", board=None),
        templates={
            "sprinted": IssueTemplate(
                summary="x",
                issue_type="Task",
                fields={"Sprint": CURRENT_SPRINT_TOKEN},
            )
        },
    )
)
mock_client2 = MagicMock(spec=JiraClient)
mock_client2.post.return_value = {"key": "PROJ-1"}
mock_client2.get.return_value = {"baseUrl": "https://test.atlassian.net"}
try:
    create_issue(
        client=mock_client2,
        config=no_board,
        fields_mgr=fields_mgr,
        template_name="sprinted",
    )
    assert False, "expected missing board error"
except ValueError as exc:
    assert "defaults.board" in str(exc)

# --- update_pull_request ---
pr_client = MagicMock(spec=JiraClient)
pr_fields = MagicMock(spec=FieldCacheManager)
pr_fields.resolve_field.side_effect = lambda name: (
    {
        "id": "customfield_10101",
        "name": "Git Pull Request",
        "schema": {
            "type": "string",
            "custom": "com.atlassian.jira.plugin.system.customfieldtypes:textarea",
        },
    }
    if name == "Git Pull Request"
    else None
)

pr_client.get.return_value = {
    "fields": {"customfield_10101": "https://git.example/pr/1"}
}
appended = update_pull_request(
    pr_client, pr_fields, "PROJ-1", "https://git.example/pr/2"
)
assert appended["mode"] == "appended"
assert appended["value"] == "https://git.example/pr/1\nhttps://git.example/pr/2"
from jflow.core.adf import text_to_adf_doc

pr_client.put.assert_called_with(
    "/rest/api/3/issue/PROJ-1",
    payload={
        "fields": {
            "customfield_10101": text_to_adf_doc(
                "https://git.example/pr/1\nhttps://git.example/pr/2"
            )
        }
    },
)

pr_client.reset_mock()
overwritten = update_pull_request(
    pr_client, pr_fields, "PROJ-1", "only-this", overwrite=True
)
assert overwritten["mode"] == "overwritten"
assert overwritten["value"] == "only-this"
pr_client.get.assert_not_called()

pr_client.reset_mock()
cleared = update_pull_request(pr_client, pr_fields, "PROJ-1", clear=True)
assert cleared["mode"] == "cleared"
assert cleared["value"] is None
pr_client.put.assert_called_with(
    "/rest/api/3/issue/PROJ-1",
    payload={"fields": {"customfield_10101": None}},
)

try:
    update_pull_request(pr_client, pr_fields, "PROJ-1", "x", overwrite=True, clear=True)
    assert False, "expected flag conflict"
except ValueError:
    pass

try:
    update_pull_request(pr_client, pr_fields, "PROJ-1", "x", clear=True)
    assert False, "expected clear+text conflict"
except ValueError:
    pass

print("✅ current sprint / link / pullrequest tests passed successfully!")
