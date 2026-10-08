# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Composer).
# ==============================================================================
from typing import Any, Dict, Optional, Tuple

from jflow.core.client import JiraClient
from jflow.core.keys import normalize_issue_key

# Shortcut flag -> (Jira link type name, swap direction)
# When swap is False: from_key is outward, to_key is inward.
# When swap is True: from_key is inward, to_key is outward.
LINK_SHORTCUTS = {
    "relates": ("Relates", False),
    "blocks": ("Blocks", False),
    "blocked_by": ("Blocks", True),
    "clones": ("Clones", False),
    "cloned_by": ("Clones", True),
    "duplicates": ("Duplicate", False),
    "duplicated_by": ("Duplicate", True),
}


def resolve_link_type(
    *,
    relates: bool = False,
    blocks: bool = False,
    blocked_by: bool = False,
    clones: bool = False,
    cloned_by: bool = False,
    duplicates: bool = False,
    duplicated_by: bool = False,
    link_type: Optional[str] = None,
) -> Tuple[str, bool]:
    """Resolve mutually exclusive link flags to (type_name, swap_direction)."""
    selected = []
    if relates:
        selected.append("relates")
    if blocks:
        selected.append("blocks")
    if blocked_by:
        selected.append("blocked_by")
    if clones:
        selected.append("clones")
    if cloned_by:
        selected.append("cloned_by")
    if duplicates:
        selected.append("duplicates")
    if duplicated_by:
        selected.append("duplicated_by")
    if link_type is not None:
        selected.append("type")

    if len(selected) > 1:
        raise ValueError(
            "Use only one of --relates, --blocks, --blocked-by, --clones, "
            "--cloned-by, --duplicates, --duplicated-by, or --type."
        )

    if not selected:
        return "Relates", False

    choice = selected[0]
    if choice == "type":
        name = (link_type or "").strip()
        if not name:
            raise ValueError("--type requires a non-empty link type name.")
        return name, False

    return LINK_SHORTCUTS[choice]


def link_issues(
    client: JiraClient,
    from_key: str,
    to_key: str,
    *,
    type_name: str = "Relates",
    swap: bool = False,
) -> Dict[str, Any]:
    """Create an issue link. By default from_key is outward and to_key is inward."""
    from_key = normalize_issue_key(from_key)
    to_key = normalize_issue_key(to_key)

    if swap:
        outward_key, inward_key = to_key, from_key
    else:
        outward_key, inward_key = from_key, to_key

    payload = {
        "type": {"name": type_name},
        "outwardIssue": {"key": outward_key},
        "inwardIssue": {"key": inward_key},
    }
    client.post("/rest/api/3/issueLink", payload=payload)
    return {
        "from": from_key,
        "to": to_key,
        "type": type_name,
        "outward": outward_key,
        "inward": inward_key,
        "status": "Linked",
    }
