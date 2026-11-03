# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from typing import Any, Dict

from jflow.core.adf import adf_to_text

# Input aliases (detail keys / short names) → Jira API field id.
INPUT_TO_API: Dict[str, str] = {
    "summary": "summary",
    "status": "status",
    "type": "issuetype",
    "issuetype": "issuetype",
    "issue type": "issuetype",
    "assignee": "assignee",
    "reporter": "reporter",
    "priority": "priority",
    "labels": "labels",
    "components": "components",
    "parent": "parent",
    "created": "created",
    "updated": "updated",
    "description": "description",
}

# API field id → detail dict key used in show output.
API_TO_DETAIL: Dict[str, str] = {
    "summary": "summary",
    "status": "status",
    "issuetype": "type",
    "assignee": "assignee",
    "reporter": "reporter",
    "priority": "priority",
    "labels": "labels",
    "components": "components",
    "parent": "parent",
    "created": "created",
    "updated": "updated",
    "description": "description",
}


def flatten_system_value(api_id: str, raw: Any) -> Any:
    """Flatten known system fields into the familiar show detail values."""
    if api_id == "summary":
        return raw or ""
    if api_id == "status":
        return (raw or {}).get("name", "") if isinstance(raw, dict) else (raw or "")
    if api_id == "issuetype":
        return (raw or {}).get("name", "") if isinstance(raw, dict) else (raw or "")
    if api_id == "assignee":
        return raw.get("displayName") if raw else "Unassigned"
    if api_id == "reporter":
        return raw.get("displayName") if raw else ""
    if api_id == "priority":
        return (raw or {}).get("name", "") if isinstance(raw, dict) else (raw or "")
    if api_id == "labels":
        return raw or []
    if api_id == "components":
        components = raw or []
        return [c.get("name") for c in components if isinstance(c, dict) and c.get("name")]
    if api_id == "parent":
        parent = raw or {}
        return parent.get("key") or "" if isinstance(parent, dict) else ""
    if api_id in ("created", "updated"):
        return raw or ""
    if api_id == "description":
        return adf_to_text(raw)
    return raw
