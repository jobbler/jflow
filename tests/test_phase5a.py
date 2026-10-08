# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from unittest.mock import MagicMock
from jflow.core import JiraClient
from jflow.core.actions.assignee import assign_issue, set_reporter, resolve_account_id

# Setup mock client
mock_client = MagicMock(spec=JiraClient)
mock_client.get.return_value = [{"accountId": "5b10ac8d82e05b22cc7d4ef5", "displayName": "Alex Dev"}]
mock_client.put.return_value = None

# Test 1: Resolve user accountId
acc_id = resolve_account_id(mock_client, "alex@company.com")
assert acc_id == "5b10ac8d82e05b22cc7d4ef5"
mock_client.get.assert_called_with("/rest/api/3/user/search", params={"query": "alex@company.com"})

# Test 2: Assign issue using user lookup query
res_assign = assign_issue(mock_client, "PROJ-101", "alex@company.com")
assert res_assign["status"] == "Updated"
mock_client.put.assert_called_with(
    "/rest/api/3/issue/PROJ-101/assignee",
    payload={"accountId": "5b10ac8d82e05b22cc7d4ef5"},
)

# Test 3: Set reporter using direct account ID
res_reporter = set_reporter(mock_client, "PROJ-101", "5b10ac8d82e05b22cc7d4ef5")
assert res_reporter["status"] == "Updated"
mock_client.put.assert_called_with(
    "/rest/api/3/issue/PROJ-101",
    payload={"fields": {"reporter": {"accountId": "5b10ac8d82e05b22cc7d4ef5"}}},
)

print("✅ Phase 5a tests passed successfully!")
