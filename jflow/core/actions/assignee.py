# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
from typing import Any, Dict, Optional
from jflow.core.client import JiraClient

_SELF_TOKEN = "@me"


def resolve_account_id(client: JiraClient, query: str) -> str:
    """Resolves @me, email, username, or display name to a Jira accountId."""
    if query == _SELF_TOKEN:
        me = client.get("/rest/api/3/myself")
        account_id = me.get("accountId")
        if not account_id:
            raise ValueError("Could not resolve @me: /myself returned no accountId")
        return account_id
    users = client.get("/rest/api/3/user/search", params={"query": query})
    if not users:
        raise ValueError(f"No user found matching query: '{query}'")
    return users[0]["accountId"]


def assign_issue(
    client: JiraClient, issue_key: str, assignee: Optional[str] = None
) -> Dict[str, Any]:
    """Assigns an issue to a user by account ID, email, or query string. Pass None to unassign."""
    account_id = None
    if assignee:
        if assignee.lower() in ("-1", "default"):
            account_id = "-1"
        elif assignee == _SELF_TOKEN:
            account_id = resolve_account_id(client, assignee)
        elif ":" in assignee or len(assignee) >= 24:
            account_id = assignee
        else:
            account_id = resolve_account_id(client, assignee)

    client.put(
        f"/rest/api/3/issue/{issue_key}/assignee",
        payload={"accountId": account_id},
    )
    return {
        "key": issue_key,
        "assignee": assignee or "Unassigned",
        "status": "Updated",
    }


def set_reporter(client: JiraClient, issue_key: str, reporter: str) -> Dict[str, Any]:
    """Updates the reporter of an issue."""
    if reporter == _SELF_TOKEN or not (":" in reporter or len(reporter) >= 24):
        account_id = resolve_account_id(client, reporter)
    else:
        account_id = reporter

    payload = {"fields": {"reporter": {"accountId": account_id}}}
    client.put(f"/rest/api/3/issue/{issue_key}", payload=payload)
    return {"key": issue_key, "reporter": reporter, "status": "Updated"}
