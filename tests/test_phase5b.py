# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from unittest.mock import MagicMock
from jflow.core import JiraClient
from jflow.core.actions.status_comment import transition_issue, add_comment

# Setup mock client
mock_client = MagicMock(spec=JiraClient)

# 1. Test Transition Matching
mock_client.get.return_value = {
    "transitions": [
        {"id": "11", "name": "To Do"},
        {"id": "21", "name": "In Progress"},
        {"id": "31", "name": "Done"},
    ]
}
mock_client.post.return_value = None

res_trans = transition_issue(mock_client, "PROJ-101", "In Progress")
assert res_trans["status"] == "In Progress"
mock_client.post.assert_called_with(
    "/rest/api/3/issue/PROJ-101/transitions",
    payload={"transition": {"id": "21"}},
)

# 2. Test Comment ADF Formatting
mock_client.post.return_value = {"id": "10050"}

res_comment = add_comment(mock_client, "PROJ-101", "Automated deployment finished.")
assert res_comment["comment_id"] == "10050"

expected_adf = {
    "body": {
        "version": 1,
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "Automated deployment finished."}],
            }
        ],
    }
}
mock_client.post.assert_called_with(
    "/rest/api/3/issue/PROJ-101/comment", payload=expected_adf
)

print("✅ Phase 5b tests passed successfully!")
