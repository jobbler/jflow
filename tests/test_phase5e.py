# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from unittest.mock import MagicMock
from jflow.config.models import AppConfig, UserConfig, JiraCredentials
from jflow.core import JiraClient
from jflow.core.actions.search import search_issues

user_cfg = UserConfig(
    jira=JiraCredentials(domain="test.atlassian.net", email="a@b.com", api_token="tok"),
    jql_aliases={
        "my-bugs": "assignee = currentUser() AND issuetype = Bug AND status != Closed",
        "recent": "updated >= -7d ORDER BY updated DESC",
    },
)
config = AppConfig(user=user_cfg)

mock_client = MagicMock(spec=JiraClient)
mock_client.post.return_value = {
    "issues": [
        {
            "key": "PROJ-301",
            "fields": {
                "summary": "Fix memory leak",
                "status": {"name": "In Progress"},
                "issuetype": {"name": "Bug"},
                "assignee": {"displayName": "Dev User"},
            },
        }
    ]
}

# 1. Test Alias Resolution
results = search_issues(mock_client, jql="my-bugs", max_results=10, config=config)

assert len(results) == 1
assert results[0]["Key"] == "PROJ-301"

# Verify exact resolved JQL was posted
mock_client.post.assert_called_with(
    "/rest/api/3/search/jql",
    {
        "jql": "assignee = currentUser() AND issuetype = Bug AND status != Closed",
        "maxResults": 10,
        "fields": ["summary", "status", "issuetype", "assignee", "updated"],
    },
)

# 2. Test Pass-through for Unmapped Direct JQL
search_issues(mock_client, jql="project = DEMO", max_results=5, config=config)

mock_client.post.assert_called_with(
    "/rest/api/3/search/jql",
    {
        "jql": "project = DEMO",
        "maxResults": 5,
        "fields": ["summary", "status", "issuetype", "assignee", "updated"],
    },
)

print("✅ Phase 5e Smart JQL Aliases tests passed successfully!")
