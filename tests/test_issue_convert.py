# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# ==============================================================================
# Created in whole or in part by AI using Cursor (Composer).
"""Issue type convert and create-as-subtask."""
from unittest.mock import MagicMock

from jflow.config.models import (
    AppConfig,
    IssueTemplate,
    JiraCredentials,
    UserConfig,
)
from jflow.core import JiraClient
from jflow.core.actions.chain import execute_chain
from jflow.core.actions.create import create_issue
from jflow.core.actions.fields import (
    convert_issue_type,
    resolve_issue_type,
    validate_subtask_parent,
)
from jflow.core.fields import FieldCacheManager
from jflow.core.templates import process_template

ISSUE_TYPES = [
    {"id": "1", "name": "Story", "subtask": False, "hierarchyLevel": 0},
    {"id": "2", "name": "Task", "subtask": False, "hierarchyLevel": 0},
    {"id": "3", "name": "Bug", "subtask": False, "hierarchyLevel": 0},
    {"id": "4", "name": "Sub-task", "subtask": True, "hierarchyLevel": -1},
    {"id": "5", "name": "Epic", "subtask": False, "hierarchyLevel": 1},
]

_STANDARD_PARENT = {
    "fields": {
        "issuetype": {"name": "Task", "subtask": False, "hierarchyLevel": 0},
        "project": {"key": "PROJ"},
        "parent": None,
    }
}


def _types_get(path, params=None):
    if path == "/rest/api/3/issuetype":
        return list(ISSUE_TYPES)
    if "serverInfo" in path:
        return {"baseUrl": "https://test.atlassian.net"}
    if path.startswith("/rest/api/3/issue/"):
        return dict(_STANDARD_PARENT)
    return {}


# --- resolve_issue_type ---
mock_client = MagicMock(spec=JiraClient)
mock_client.get.side_effect = _types_get
resolved = resolve_issue_type(mock_client, "sub-task")
assert resolved["name"] == "Sub-task"
assert resolved["subtask"] is True

try:
    resolve_issue_type(mock_client, "Nope")
    assert False, "expected unknown type error"
except ValueError as exc:
    assert "Unknown issue type" in str(exc)

# --- convert: Story → Bug (plain PUT; no hierarchy change) ---
conv_client = MagicMock(spec=JiraClient)


def _conv_get_story_bug(path, params=None):
    if path == "/rest/api/3/project/PROJ":
        return {"key": "PROJ", "issueTypes": list(ISSUE_TYPES)}
    if path == "/rest/api/3/issuetype":
        return list(ISSUE_TYPES)
    if path.startswith("/rest/api/3/issue/"):
        return {
            "fields": {
                "issuetype": {"name": "Story", "subtask": False, "hierarchyLevel": 0},
                "project": {"key": "PROJ"},
                "parent": None,
            }
        }
    return {}


conv_client.get.side_effect = _conv_get_story_bug
conv_client.put.return_value = None
res = convert_issue_type(conv_client, "proj-1", "Bug")
assert res["from_type"] == "Story"
assert res["to_type"] == "Bug"
assert res["parent"] is None
assert res["status"] == "Type Converted"
conv_client.put.assert_called_with(
    "/rest/api/3/issue/PROJ-1",
    payload={"fields": {"issuetype": {"id": "3"}}},
)

# --- convert: Task → Sub-task with parent (bulk move) ---
sub_client = MagicMock(spec=JiraClient)


def _conv_get_task_sub(path, params=None):
    if path == "/rest/api/3/project/PROJ":
        return {"key": "PROJ", "issueTypes": list(ISSUE_TYPES)}
    if path == "/rest/api/3/issuetype":
        return list(ISSUE_TYPES)
    if path.startswith("/rest/api/3/bulk/queue/"):
        return {"taskId": "99", "status": "COMPLETE", "progressPercent": 100}
    if path.startswith("/rest/api/3/issue/PROJ-100"):
        return dict(_STANDARD_PARENT)
    if path.startswith("/rest/api/3/issue/"):
        return {
            "fields": {
                "issuetype": {"name": "Task", "subtask": False, "hierarchyLevel": 0},
                "project": {"key": "PROJ"},
                "parent": None,
            }
        }
    return {}


sub_client.get.side_effect = _conv_get_task_sub
sub_client.post.return_value = {"taskId": "99"}
res = convert_issue_type(sub_client, "PROJ-2", "Sub-task", parent_key="proj-100")
assert res["to_type"] == "Sub-task"
assert res["parent"] == "PROJ-100"
sub_client.post.assert_called_with(
    "/rest/api/3/bulk/issues/move",
    {
        "targetToSourcesMapping": {
            "PROJ,4,PROJ-100": {
                "issueIdsOrKeys": ["PROJ-2"],
                "inferClassificationDefaults": True,
                "inferFieldDefaults": True,
                "inferStatusDefaults": True,
                "inferSubtaskTypeDefault": True,
            }
        },
    },
)

# --- convert: Sub-task → Task clears parent (bulk move) ---
promote_client = MagicMock(spec=JiraClient)


def _conv_get_sub_task(path, params=None):
    if path == "/rest/api/3/project/PROJ":
        return {"key": "PROJ", "issueTypes": list(ISSUE_TYPES)}
    if path == "/rest/api/3/issuetype":
        return list(ISSUE_TYPES)
    if path.startswith("/rest/api/3/bulk/queue/"):
        return {"taskId": "100", "status": "COMPLETE", "progressPercent": 100}
    if path.startswith("/rest/api/3/issue/"):
        return {
            "fields": {
                "issuetype": {"name": "Sub-task", "subtask": True, "hierarchyLevel": -1},
                "project": {"key": "PROJ"},
                "parent": {"key": "PROJ-100"},
            }
        }
    return {}


promote_client.get.side_effect = _conv_get_sub_task
promote_client.post.return_value = {"taskId": "100"}
res = convert_issue_type(promote_client, "PROJ-3", "Task")
assert res["from_type"] == "Sub-task"
assert res["to_type"] == "Task"
assert res["parent"] is None
promote_client.post.assert_called_with(
    "/rest/api/3/bulk/issues/move",
    {
        "targetToSourcesMapping": {
            "PROJ,2": {
                "issueIdsOrKeys": ["PROJ-3"],
                "inferClassificationDefaults": True,
                "inferFieldDefaults": True,
                "inferStatusDefaults": True,
                "inferSubtaskTypeDefault": True,
            }
        },
    },
)

# --- convert errors ---
err_client = MagicMock(spec=JiraClient)
err_client.get.side_effect = _conv_get_task_sub
try:
    convert_issue_type(err_client, "PROJ-2", "Sub-task")
    assert False, "expected parent required"
except ValueError as exc:
    assert "Parent issue key is required" in str(exc)

try:
    convert_issue_type(err_client, "PROJ-2", "Bug", parent_key="PROJ-100")
    assert False, "expected parent not allowed"
except ValueError as exc:
    assert "only allowed when converting to a sub-task" in str(exc)

# --- validate_subtask_parent rejects Epic ---
epic_client = MagicMock(spec=JiraClient)


def _epic_parent_get(path, params=None):
    if path == "/rest/api/3/project/PROJ":
        return {"key": "PROJ", "issueTypes": list(ISSUE_TYPES)}
    if path == "/rest/api/3/issuetype":
        return list(ISSUE_TYPES)
    if path.startswith("/rest/api/3/issue/PROJ-EPIC"):
        return {
            "fields": {
                "issuetype": {"name": "Epic", "subtask": False, "hierarchyLevel": 1},
                "project": {"key": "PROJ"},
            }
        }
    if path.startswith("/rest/api/3/issue/"):
        return {
            "fields": {
                "issuetype": {"name": "Task", "subtask": False, "hierarchyLevel": 0},
                "project": {"key": "PROJ"},
                "parent": None,
            }
        }
    return {}


epic_client.get.side_effect = _epic_parent_get
try:
    validate_subtask_parent(epic_client, "PROJ-EPIC", child_project_key="PROJ")
    assert False, "expected Epic parent rejected"
except ValueError as exc:
    assert "hierarchy level 1" in str(exc)
    assert "Story, Task, Bug" in str(exc)

try:
    convert_issue_type(epic_client, "PROJ-2", "Sub-task", parent_key="PROJ-EPIC")
    assert False, "expected convert with Epic parent rejected"
except ValueError as exc:
    assert "hierarchy level 1" in str(exc)

# --- create Sub-task with parent ---
create_client = MagicMock(spec=JiraClient)
create_client.get.side_effect = _types_get
create_client.post.return_value = {"id": "10", "key": "PROJ-10"}
fields_mgr = MagicMock(spec=FieldCacheManager)
user_cfg = UserConfig(
    jira=JiraCredentials(domain="test.atlassian.net", email="a@b.com", api_token="tok"),
)
config = AppConfig(user=user_cfg)
created = create_issue(
    client=create_client,
    config=config,
    fields_mgr=fields_mgr,
    project="PROJ",
    issue_type="Sub-task",
    summary="Child work",
    parent="proj-100",
)
assert created["key"] == "PROJ-10"
posted = create_client.post.call_args[0][1]["fields"]
assert posted["issuetype"]["name"] == "Sub-task"
assert posted["parent"] == {"key": "PROJ-100"}

# --- create Sub-task without parent raises ---
try:
    create_issue(
        client=create_client,
        config=config,
        fields_mgr=fields_mgr,
        project="PROJ",
        issue_type="Sub-task",
        summary="Missing parent",
    )
    assert False, "expected parent required on create"
except ValueError as exc:
    assert "Parent issue key is required" in str(exc)

# --- create Task with parent raises ---
try:
    create_issue(
        client=create_client,
        config=config,
        fields_mgr=fields_mgr,
        project="PROJ",
        issue_type="Task",
        summary="Bad parent",
        parent="PROJ-100",
    )
    assert False, "expected parent not allowed on non-subtask create"
except ValueError as exc:
    assert "only allowed when creating a sub-task" in str(exc)

# --- template parent ---
tpl_cfg = AppConfig(
    user=UserConfig(
        jira=JiraCredentials(
            domain="test.atlassian.net", email="a@b.com", api_token="tok"
        ),
        templates={
            "breakdown": IssueTemplate(
                summary="{summary}",
                issue_type="Sub-task",
                parent="{parent}",
            )
        },
    )
)
rendered = process_template(
    tpl_cfg, "breakdown", {"summary": "Do thing", "parent": "PROJ-50"}
)
assert rendered.parent == "PROJ-50"
assert rendered.issue_type == "Sub-task"

tpl_client = MagicMock(spec=JiraClient)
tpl_client.get.side_effect = _types_get
tpl_client.post.return_value = {"id": "11", "key": "PROJ-11"}
tpl_created = create_issue(
    client=tpl_client,
    config=tpl_cfg,
    fields_mgr=fields_mgr,
    project="PROJ",
    template_name="breakdown",
    template_vars={"summary": "Do thing", "parent": "PROJ-50"},
)
tpl_posted = tpl_client.post.call_args[0][1]["fields"]
assert tpl_posted["parent"] == {"key": "PROJ-50"}
assert tpl_posted["summary"] == "Do thing"

# CLI parent overrides template parent
tpl_created2 = create_issue(
    client=tpl_client,
    config=tpl_cfg,
    fields_mgr=fields_mgr,
    project="PROJ",
    template_name="breakdown",
    template_vars={"summary": "Do thing", "parent": "PROJ-50"},
    parent="PROJ-99",
)
tpl_posted2 = tpl_client.post.call_args[0][1]["fields"]
assert tpl_posted2["parent"] == {"key": "PROJ-99"}

# --- workflow create + convert ---
chain_client = MagicMock(spec=JiraClient)


def _chain_get(path, params=None):
    if path == "/rest/api/3/project/PROJ":
        return {"key": "PROJ", "issueTypes": list(ISSUE_TYPES)}
    if path == "/rest/api/3/issuetype":
        return list(ISSUE_TYPES)
    if "serverInfo" in path:
        return {"baseUrl": "https://test.atlassian.net"}
    if path.startswith("/rest/api/3/bulk/queue/"):
        return {"taskId": "77", "status": "COMPLETE", "progressPercent": 100}
    if path.startswith("/rest/api/3/issue/"):
        return {
            "fields": {
                "issuetype": {"name": "Task", "subtask": False, "hierarchyLevel": 0},
                "project": {"key": "PROJ"},
                "parent": None,
            }
        }
    return {}


def _chain_post(path, payload=None):
    if path == "/rest/api/3/issue":
        return {"id": "20", "key": "PROJ-20"}
    if path == "/rest/api/3/bulk/issues/move":
        return {"taskId": "77"}
    return {}


chain_client.get.side_effect = _chain_get
chain_client.post.side_effect = _chain_post
chain_results = execute_chain(
    client=chain_client,
    config=config,
    fields_mgr=fields_mgr,
    steps=[
        {
            "action": "create",
            "project": "PROJ",
            "issue_type": "Sub-task",
            "parent": "{parent}",
            "summary": "{summary}",
        },
        {"action": "convert", "issue_type": "Task"},
    ],
    variables={"parent": "PROJ-100", "summary": "Workflow child"},
    initial_key=None,
)
assert chain_results[0]["step"] == "create"
assert chain_results[0]["result"]["key"] == "PROJ-20"
create_posts = [
    c for c in chain_client.post.call_args_list if c.args and c.args[0] == "/rest/api/3/issue"
]
assert create_posts[0].args[1]["fields"]["parent"] == {"key": "PROJ-100"}
assert chain_results[1]["step"] == "convert"
assert chain_results[1]["result"]["to_type"] == "Task"

# convert action alone on existing key (Task → Sub-task via bulk move)
chain_client.reset_mock()
chain_client.get.side_effect = _chain_get
chain_client.post.side_effect = _chain_post
conv_only = execute_chain(
    client=chain_client,
    config=config,
    fields_mgr=fields_mgr,
    steps=[
        {"action": "convert", "issue_type": "Sub-task", "parent": "PROJ-100"},
    ],
    initial_key="PROJ-2",
)
assert conv_only[0]["step"] == "convert"
assert conv_only[0]["result"]["parent"] == "PROJ-100"

print("✅ Issue convert / create sub-task tests passed successfully!")
