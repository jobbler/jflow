# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from unittest.mock import MagicMock
from jflow.core import JiraClient
from jflow.core.actions.search import search_issues

mock_client = MagicMock(spec=JiraClient)
mock_client.post.return_value = {
    "issues": [
        {
            "key": "PROJ-101",
            "fields": {
                "summary": "Fix login crash",
                "status": {"name": "In Progress"},
                "issuetype": {"name": "Bug"},
                "assignee": {"displayName": "Alex Dev"},
            },
        }
    ]
}

results = search_issues(mock_client, jql="project = PROJ AND status = 'In Progress'")

assert len(results) == 1
assert results[0]["Key"] == "PROJ-101"
assert results[0]["Summary"] == "Fix login crash"
assert results[0]["Assignee"] == "Alex Dev"

mock_client.post.assert_called_with(
    "/rest/api/3/search/jql",
    {
        "jql": "project = PROJ AND status = 'In Progress'",
        "maxResults": 15,
        "fields": ["summary", "status", "issuetype", "assignee", "updated"],
    },
)

print("✅ Phase 6 tests passed successfully!")
