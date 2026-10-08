# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Composer).
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
from jflow.core.actions.chain import execute_chain
from jflow.core.actions.create import CURRENT_SPRINT_TOKEN
from jflow.core.fields import FieldCacheManager
from jflow.core.templates import apply_workflow_vars

# --- apply_workflow_vars: deep render ---
steps = [
    {
        "action": "create",
        "project": "{project}",
        "summary": "{summary}",
        "issue_type": "Task",
        "description": "Hello {name}",
    },
    {"action": "comment", "message": "Done for {project}"},
]
rendered = apply_workflow_vars(
    steps,
    {"project": "PROJ", "summary": "Investigate timeout", "name": "world"},
)
assert rendered[0]["project"] == "PROJ"
assert rendered[0]["summary"] == "Investigate timeout"
assert rendered[0]["description"] == "Hello world"
assert rendered[1]["message"] == "Done for PROJ"
assert rendered[0]["template_vars"]["project"] == "PROJ"
assert rendered[0]["template_vars"]["summary"] == "Investigate timeout"

# --- apply_workflow_vars: CLI vars win over embedded template_vars ---
merged = apply_workflow_vars(
    [
        {
            "action": "create",
            "template_name": "bug_report",
            "template_vars": {"component": "Auth", "env": "Staging"},
        }
    ],
    {"env": "Prod", "steps": "Click login"},
)
assert merged[0]["template_vars"]["component"] == "Auth"
assert merged[0]["template_vars"]["env"] == "Prod"
assert merged[0]["template_vars"]["steps"] == "Click login"

# No vars → identity (no template_vars injection)
plain = [{"action": "assign", "assignee": "@me"}]
assert apply_workflow_vars(plain, None) is plain
assert apply_workflow_vars(plain, {}) is plain

# --- execute_chain: create with --var placeholders ---
user_cfg = UserConfig(
    jira=JiraCredentials(domain="test.atlassian.net", email="a@b.com", api_token="tok"),
    defaults=Defaults(project="PROJ", board="42"),
    templates={
        "bug_report": IssueTemplate(
            summary="[BUG] {component}: Issue in {env}",
            description="Steps:\n{steps}",
            issue_type="Bug",
            project="PROJ",
        )
    },
)
config = AppConfig(user=user_cfg)
mock_client = MagicMock(spec=JiraClient)
fields_mgr = MagicMock(spec=FieldCacheManager)


def _get(path, params=None):
    if path == "/rest/api/3/issuetype":
        return [
            {"id": "1", "name": "Task", "subtask": False},
            {"id": "2", "name": "Bug", "subtask": False},
        ]
    if path == "/rest/api/3/serverInfo":
        return {"baseUrl": "https://test.atlassian.net"}
    if path == "/rest/agile/1.0/board/42/sprint":
        return {"values": [{"id": 99, "name": "Sprint 99", "state": "active"}]}
    if "transitions" in path:
        return {"transitions": [{"id": "21", "name": "In Progress"}]}
    if path == "/rest/api/3/myself":
        return {"accountId": "acct-me"}
    return {}


def _post(path, payload=None):
    if path == "/rest/api/3/issue":
        fields = (payload or {}).get("fields") or {}
        assert fields.get("summary") == "Investigate timeout"
        assert fields.get("project", {}).get("key") == "PROJ"
        return {"key": "PROJ-1", "id": "1"}
    if path.startswith("/rest/agile/1.0/sprint/"):
        return {}
    if "comment" in path:
        return {"id": "c1"}
    return {}


mock_client.get.side_effect = _get
mock_client.post.side_effect = _post
mock_client.put.return_value = None

results = execute_chain(
    client=mock_client,
    config=config,
    fields_mgr=fields_mgr,
    steps=[
        {
            "action": "create",
            "project": "{project}",
            "issue_type": "Task",
            "summary": "{summary}",
        },
        {"action": "assign", "assignee": "@me"},
        {"action": "comment", "message": "Created {summary}"},
    ],
    variables={"project": "PROJ", "summary": "Investigate timeout"},
)
assert results[0]["result"]["key"] == "PROJ-1"
assert results[1]["step"] == "assign"
assert results[1]["result"]["key"] == "PROJ-1"
assert results[2]["step"] == "comment"

# --- execute_chain: template_vars merge from CLI ---
mock_client.reset_mock()
mock_client.get.side_effect = _get


def _post_tpl(path, payload=None):
    if path == "/rest/api/3/issue":
        fields = (payload or {}).get("fields") or {}
        assert fields.get("summary") == "[BUG] Auth: Issue in Prod"
        return {"key": "PROJ-9", "id": "9"}
    return {}


mock_client.post.side_effect = _post_tpl
results = execute_chain(
    client=mock_client,
    config=config,
    fields_mgr=fields_mgr,
    steps=[{"action": "create", "template_name": "bug_report"}],
    variables={"component": "Auth", "env": "Prod", "steps": "Click"},
)
assert results[0]["result"]["key"] == "PROJ-9"

# --- execute_chain: sprint @current_sprint ---
mock_client.reset_mock()
mock_client.get.side_effect = _get
sprint_posts = []


def _post_sprint(path, payload=None):
    sprint_posts.append((path, payload))
    if path == "/rest/api/3/issue":
        return {"key": "PROJ-10", "id": "10"}
    return {}


mock_client.post.side_effect = _post_sprint
results = execute_chain(
    client=mock_client,
    config=config,
    fields_mgr=fields_mgr,
    steps=[
        {
            "action": "create",
            "project": "PROJ",
            "issue_type": "Task",
            "summary": "Sprint me",
        },
        {"action": "sprint", "sprint_id": CURRENT_SPRINT_TOKEN},
    ],
)
assert results[1]["step"] == "sprint"
assert results[1]["result"]["sprint_id"] == 99
assert any(
    path == "/rest/agile/1.0/sprint/99/issue" for path, _ in sprint_posts
)

# omitted sprint_id also resolves current sprint
mock_client.reset_mock()
mock_client.get.side_effect = _get
sprint_posts.clear()
mock_client.post.side_effect = _post_sprint
results = execute_chain(
    client=mock_client,
    config=config,
    fields_mgr=fields_mgr,
    steps=[
        {
            "action": "create",
            "project": "PROJ",
            "issue_type": "Task",
            "summary": "Sprint omit",
        },
        {"action": "sprint"},
    ],
)
assert results[1]["result"]["sprint_id"] == 99

# missing defaults.board → clear error
bare = AppConfig(
    user=UserConfig(
        jira=JiraCredentials(
            domain="test.atlassian.net", email="a@b.com", api_token="tok"
        ),
    )
)
mock_client.reset_mock()
mock_client.get.side_effect = _get
mock_client.post.side_effect = lambda path, payload=None: (
    {"key": "PROJ-11", "id": "11"} if path == "/rest/api/3/issue" else {}
)
try:
    execute_chain(
        client=mock_client,
        config=bare,
        fields_mgr=fields_mgr,
        steps=[
            {
                "action": "create",
                "project": "PROJ",
                "issue_type": "Task",
                "summary": "No board",
            },
            {"action": "sprint", "sprint_id": CURRENT_SPRINT_TOKEN},
        ],
    )
    assert False, "expected ValueError for missing defaults.board"
except ValueError as exc:
    assert "defaults.board" in str(exc)

print("✅ Workflow vars / @current_sprint chain tests passed successfully!")
