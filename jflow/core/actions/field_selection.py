# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
import re
from typing import Any, Dict, List, Optional

from jflow.core.adf import adf_to_text
from jflow.core.actions.sprint import get_board_sprints, resolve_board
from jflow.core.client import JiraClient

# Virtual fields are computed by jflow rather than read directly from Jira.
CURRENT_SPRINT = "current_sprint"
CURRENT_SPRINT_LABEL = "Current Sprint"
VIRTUAL_FIELD_ALIASES: Dict[str, str] = {
    "current_sprint": CURRENT_SPRINT,
    "current sprint": CURRENT_SPRINT,
}
SPRINT_FIELD_NAME = "Sprint"
_BACKLOG = "Backlog"
_SPRINT_ID_RE = re.compile(r"\bid=(\d+)")
_SPRINT_NAME_RE = re.compile(r"\bname=([^,\]]+)")

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


def virtual_field(name: str) -> Optional[str]:
    """Canonical virtual field name, or None for a real Jira field."""
    return VIRTUAL_FIELD_ALIASES.get((name or "").strip().casefold())


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _sprint_entry(raw: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw, dict):
        return {
            "id": _as_int(raw.get("id")),
            "name": raw.get("name") or "",
        }
    if isinstance(raw, str):
        id_match = _SPRINT_ID_RE.search(raw)
        name_match = _SPRINT_NAME_RE.search(raw)
        if not id_match and not name_match:
            return None
        return {
            "id": _as_int(id_match.group(1)) if id_match else None,
            "name": name_match.group(1).strip() if name_match else "",
        }
    return None


def sprint_entries(raw: Any) -> List[Dict[str, Any]]:
    """Normalize the Sprint field payload (sprint objects or legacy strings)."""
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    entries = (_sprint_entry(item) for item in raw)
    return [entry for entry in entries if entry is not None]


def current_sprint_name(raw: Any, active_sprints: Dict[int, str]) -> str:
    """The board's active sprint the issue belongs to, else ``Backlog``."""
    for entry in sprint_entries(raw):
        sprint_id = entry.get("id")
        if sprint_id is not None and sprint_id in active_sprints:
            return entry.get("name") or active_sprints.get(sprint_id) or ""
    return _BACKLOG


def active_board_sprints(client: JiraClient, board: Any) -> Dict[int, str]:
    """Active sprints on ``board`` (id or name) as ``{id: name}``."""
    board_id = resolve_board(client, board)
    active: Dict[int, str] = {}
    for sprint in get_board_sprints(client, board_id, state="active"):
        sprint_id = _as_int(sprint.get("id"))
        if sprint_id is not None:
            active[sprint_id] = sprint.get("name") or ""
    return active
