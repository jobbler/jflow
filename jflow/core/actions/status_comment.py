# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from typing import Any, Dict
from jflow.core.adf import text_to_adf_doc
from jflow.core.client import JiraClient


def transition_issue(client: JiraClient, issue_key: str, target_status: str) -> Dict[str, Any]:
    """Fetches valid transitions for an issue and executes the matching status move."""
    response = client.get(f"/rest/api/3/issue/{issue_key}/transitions")
    transitions = response.get("transitions", [])

    matched_id = None
    matched_name = target_status

    for t in transitions:
        if t["id"] == target_status or t["name"].lower() == target_status.lower():
            matched_id = t["id"]
            matched_name = t["name"]
            break

    if not matched_id:
        available = ", ".join(f"'{t['name']}'" for t in transitions)
        raise ValueError(
            f"Transition '{target_status}' unavailable for issue {issue_key}. Available options: {available}"
        )

    client.post(
        f"/rest/api/3/issue/{issue_key}/transitions",
        payload={"transition": {"id": matched_id}},
    )
    return {"key": issue_key, "status": matched_name, "action": "Transitioned"}


def add_comment(client: JiraClient, issue_key: str, comment_text: str) -> Dict[str, Any]:
    """Adds a comment to a Jira ticket using Atlassian Document Format (ADF).

    Newlines in ``comment_text`` become separate paragraphs (same as descriptions).
    """
    payload = {"body": text_to_adf_doc(comment_text)}
    response = client.post(f"/rest/api/3/issue/{issue_key}/comment", payload=payload)
    return {"key": issue_key, "comment_id": response.get("id"), "action": "Comment Added"}
