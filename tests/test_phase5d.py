# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from unittest.mock import MagicMock
from jflow.config.models import AppConfig, UserConfig, JiraCredentials
from jflow.core import JiraClient
from jflow.core.fields import FieldCacheManager
from jflow.core.actions.chain import execute_chain

user_cfg = UserConfig(
    jira=JiraCredentials(domain="test.atlassian.net", email="a@b.com", api_token="tok"),
)
config = AppConfig(user=user_cfg)

mock_client = MagicMock(spec=JiraClient)
fields_mgr = MagicMock(spec=FieldCacheManager)

# 1. Mock POST responses (1: create_issue, 2: transition_issue, 3: add_comment)
mock_client.post.side_effect = [
    {"id": "101", "key": "PROJ-500", "self": "http://test"},
    None,            # transition endpoint returns 204/None
    {"id": "2001"},  # comment creation
]

# 2. Mock GET responses based on route path
def mock_get_handler(path, params=None):
    if path == "/rest/api/3/issuetype":
        return [{"id": "1", "name": "Task", "subtask": False}]
    if "user/search" in path:
        return [{"accountId": "account-id-alex"}]
    if "transitions" in path:
        return {"transitions": [{"id": "21", "name": "In Progress"}]}
    if "serverInfo" in path:
        return {"baseUrl": "https://test.atlassian.net"}
    return {}

mock_client.get.side_effect = mock_get_handler
mock_client.put.return_value = None

steps = [
    {"action": "create", "project": "PROJ", "summary": "Chain test issue", "issue_type": "Task"},
    {"action": "assign", "assignee": "alex@example.com"},
    {"action": "transition", "status": "In Progress"},
    {"action": "comment", "message": "Initial workflow setup completed."},
]

results = execute_chain(
    client=mock_client,
    config=config,
    fields_mgr=fields_mgr,
    steps=steps,
)

assert len(results) == 4
assert results[0]["step"] == "create"
assert results[0]["result"]["key"] == "PROJ-500"
assert results[1]["step"] == "assign"
assert results[1]["result"]["key"] == "PROJ-500"
assert results[2]["step"] == "transition"
assert results[2]["result"]["status"] == "In Progress"
assert results[3]["step"] == "comment"
assert results[3]["result"]["comment_id"] == "2001"

print("✅ Phase 5d Workflow Chaining Engine tests passed successfully!")
