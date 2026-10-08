# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from unittest.mock import MagicMock
from jflow.core import JiraClient
from jflow.core.actions.sprint import add_issue_to_sprint, get_board_sprints

mock_client = MagicMock(spec=JiraClient)

# 1. Test Add Issue to Sprint
mock_client.post.return_value = None
res_add = add_issue_to_sprint(mock_client, "PROJ-101", 42)

assert res_add["status"] == "Added to Sprint"
assert res_add["sprint_id"] == 42
mock_client.post.assert_called_with(
    "/rest/agile/1.0/sprint/42/issue", payload={"issues": ["PROJ-101"]}
)

# 2. Test Get Board Sprints
mock_client.get.return_value = {
    "values": [
        {"id": 42, "name": "Sprint 10", "state": "active", "startDate": "2026-09-01"},
        {"id": 43, "name": "Sprint 11", "state": "future", "startDate": "2026-09-15"},
    ]
}

sprints = get_board_sprints(mock_client, board_id=5, state="active")
assert len(sprints) == 2
assert sprints[0]["id"] == 42
assert sprints[0]["name"] == "Sprint 10"
mock_client.get.assert_called_with("/rest/agile/1.0/board/5/sprint", params={"state": "active"})

print("✅ Phase 5b Sprint Management tests passed successfully!")
