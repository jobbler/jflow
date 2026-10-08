# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from unittest.mock import MagicMock
from jflow.core import JiraClient
from jflow.core.actions.sprint import (
    add_issue_to_sprint,
    get_backlog_issues,
    create_sprint,
    update_sprint_state,
)

mock_client = MagicMock(spec=JiraClient)

# 1. Test Auto-Detect Active Sprint & Add Issue
mock_client.get.return_value = {
    "values": [{"id": 102, "name": "Sprint 2", "state": "active"}]
}
mock_client.post.return_value = None

res_auto = add_issue_to_sprint(mock_client, issue_key="PROJ-20", board_id=5)
assert res_auto["sprint_id"] == 102
mock_client.get.assert_called_with("/rest/agile/1.0/board/5/sprint", params={"state": "active"})
mock_client.post.assert_called_with("/rest/agile/1.0/sprint/102/issue", payload={"issues": ["PROJ-20"]})

# 2. Test Get Backlog Issues
mock_client.get.return_value = {
    "issues": [
        {
            "key": "PROJ-88",
            "fields": {
                "summary": "Backlog Task",
                "status": {"name": "To Do"},
                "issuetype": {"name": "Task"},
                "assignee": None,
            },
        }
    ]
}

backlog = get_backlog_issues(mock_client, board_id=5)
assert len(backlog) == 1
assert backlog[0]["Key"] == "PROJ-88"
assert backlog[0]["Assignee"] == "Unassigned"
mock_client.get.assert_called_with("/rest/agile/1.0/board/5/backlog", params={"maxResults": 50})

# 3. Test Create Sprint
mock_client.post.return_value = {
    "id": 103,
    "name": "Sprint 3",
    "state": "future",
}

res_create = create_sprint(mock_client, name="Sprint 3", board_id=5, goal="Deliver Phase 9")
assert res_create["id"] == 103
assert res_create["status"] == "Sprint Created"
mock_client.post.assert_called_with(
    "/rest/agile/1.0/sprint",
    payload={"name": "Sprint 3", "originBoardId": 5, "goal": "Deliver Phase 9"},
)

# 4. Test Update Sprint State
mock_client.put.return_value = {"id": 103, "state": "active"}

res_state = update_sprint_state(mock_client, sprint_id=103, state="active")
assert res_state["sprint_id"] == 103
assert res_state["state"] == "active"
mock_client.put.assert_called_with("/rest/agile/1.0/sprint/103", payload={"state": "active"})

print("✅ Phase 9 Agile, Backlog & Sprint Lifecycle tests passed successfully!")
