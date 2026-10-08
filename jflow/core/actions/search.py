# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from typing import Any, Dict, List, Optional

from jflow.config.models import AppConfig
from jflow.core.client import JiraClient

MY_ISSUE_FILTERS = {
    "all": "assignee = currentUser() ORDER BY updated DESC",
    "open": "assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC",
    "closed": "assignee = currentUser() AND statusCategory = Done ORDER BY updated DESC",
    "in-progress": 'assignee = currentUser() AND statusCategory = "In Progress" ORDER BY updated DESC',
    "review": (
        "assignee = currentUser() AND statusCategory != Done "
        'AND (status = "Review" OR status = "In Review") ORDER BY updated DESC'
    ),
    "code-review": (
        "assignee = currentUser() AND "
        '(status = "Code Review" OR status = "Code review") ORDER BY updated DESC'
    ),
}


def build_my_issues_jql(
    filter_name: str = "open",
    status: Optional[str] = None,
    jql: Optional[str] = None,
) -> str:
    """Resolve JQL for listing the current user's issues."""
    if jql:
        return jql
    if status:
        safe = status.replace("\\", "\\\\").replace('"', '\\"')
        return f'assignee = currentUser() AND status = "{safe}" ORDER BY updated DESC'
    key = (filter_name or "open").strip().lower()
    if key not in MY_ISSUE_FILTERS:
        raise ValueError(
            f"Unknown filter '{filter_name}'. "
            f"Valid: {', '.join(sorted(MY_ISSUE_FILTERS))}"
        )
    return MY_ISSUE_FILTERS[key]


def search_issues(
    client: JiraClient,
    jql: str,
    max_results: int = 15,
    fields: Optional[List[str]] = None,
    config: Optional[AppConfig] = None,
    template_vars: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Queries issues using JQL, resolving aliases and optional {placeholder} vars."""
    from jflow.core.templates import render_string

    resolved_jql = config.resolve_jql(jql) if config else jql
    if template_vars:
        resolved_jql = render_string(resolved_jql, template_vars) or resolved_jql

    target_fields = fields or ["summary", "status", "issuetype", "assignee", "updated"]
    payload = {
        "jql": resolved_jql,
        "maxResults": max_results,
        "fields": target_fields,
    }

    response = client.post("/rest/api/3/search/jql", payload)
    issues = response.get("issues", []) if response else []

    results = []
    for item in issues:
        f = item.get("fields", {})
        assignee = f.get("assignee")
        results.append({
            "Key": item.get("key"),
            "Type": f.get("issuetype", {}).get("name", "Unknown"),
            "Summary": f.get("summary", ""),
            "Status": f.get("status", {}).get("name", "Unknown"),
            "Assignee": assignee.get("displayName") if assignee else "Unassigned",
        })

    return results


def list_my_issues(
    client: JiraClient,
    filter_name: str = "open",
    status: Optional[str] = None,
    jql: Optional[str] = None,
    max_results: int = 15,
    config: Optional[AppConfig] = None,
    template_vars: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """List issues assigned to the current user using presets, status, or raw JQL."""
    resolved = build_my_issues_jql(filter_name=filter_name, status=status, jql=jql)
    return search_issues(
        client,
        jql=resolved,
        max_results=max_results,
        config=config,
        template_vars=template_vars,
    )
