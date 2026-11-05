# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
from typing import Any, Dict, List, Optional, Union

from jflow.core.client import JiraClient
from jflow.core.keys import normalize_issue_key


def list_boards(
    client: JiraClient,
    name: Optional[str] = None,
    max_results: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """List Agile boards (id, name, type).

    When ``name`` is set, uses the Agile API name filter (substring match).
    When ``max_results`` is None, paginates until all matching boards are fetched.
    Exact name matching for resolve stays in ``resolve_board``.
    """
    path = "/rest/agile/1.0/board"
    collected: List[Dict[str, Any]] = []
    start_at = 0
    page_size = 50
    if max_results is not None:
        page_size = min(max(max_results, 1), 50)

    while True:
        params: Dict[str, Any] = {"startAt": start_at, "maxResults": page_size}
        if name:
            params["name"] = name
        res = client.get(path, params=params) or {}
        values = res.get("values", [])
        for item in values:
            location = item.get("location") or {}
            collected.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "type": item.get("type"),
                "projectKey": location.get("projectKey") or location.get("projectName"),
            })
            if max_results is not None and len(collected) >= max_results:
                return collected[:max_results]

        is_last = res.get("isLast", True)
        if is_last or not values:
            break
        start_at += len(values)

    return collected


def resolve_board(client: JiraClient, board: Union[str, int]) -> int:
    """Resolve a board id or case-insensitive exact name to a numeric board id."""
    if isinstance(board, int):
        return board
    text = str(board).strip()
    if not text:
        raise ValueError("Board must be a numeric id or non-empty board name.")
    if text.isdigit():
        return int(text)

    matches = list_boards(client, name=text, max_results=None)
    # API name filter is often a substring; enforce exact case-insensitive match.
    needle = text.casefold()
    exact = [b for b in matches if (b.get("name") or "").casefold() == needle]
    if not exact:
        raise ValueError(f"No board found with name '{text}'.")
    if len(exact) > 1:
        ids = ", ".join(str(b.get("id")) for b in exact)
        raise ValueError(f"Ambiguous board name '{text}' matches ids: {ids}.")
    board_id = exact[0].get("id")
    if board_id is None:
        raise ValueError(f"Board '{text}' has no id.")
    return int(board_id)


def get_board_sprints(client: JiraClient, board_id: int, state: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists sprints for a given board, optionally filtered by state ('active', 'future', 'closed')."""
    path = f"/rest/agile/1.0/board/{board_id}/sprint"
    params = {}
    if state:
        params["state"] = state
    res = client.get(path, params=params)
    return res.get("values", [])


def get_active_sprint(client: JiraClient, board_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves the current active sprint for a given board ID."""
    sprints = get_board_sprints(client, board_id=board_id, state="active")
    return sprints[0] if sprints else None


def add_issue_to_sprint(
    client: JiraClient,
    issue_key: str,
    sprint_id: Optional[int] = None,
    board_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Adds an issue to a sprint. Auto-detects active sprint if sprint_id is omitted and board_id is provided."""
    issue_key = normalize_issue_key(issue_key)
    target_sprint_id = sprint_id
    sprint_name: Optional[str] = None

    if target_sprint_id is None:
        if board_id is None:
            raise ValueError(
                "Must provide --sprint-id or a board (--board or defaults.board) "
                "to select the active sprint."
            )
        active_sprint = get_active_sprint(client, board_id=board_id)
        if not active_sprint:
            raise ValueError(f"No active sprint found for board {board_id}.")
        target_sprint_id = active_sprint["id"]
        sprint_name = active_sprint.get("name")

    path = f"/rest/agile/1.0/sprint/{target_sprint_id}/issue"
    try:
        client.post(path, payload={"issues": [issue_key]})
    except RuntimeError as exc:
        context = f"issue={issue_key}, sprint_id={target_sprint_id}"
        if board_id is not None:
            context += f", board_id={board_id}"
        if sprint_name:
            context += f", sprint={sprint_name!r}"
        raise RuntimeError(f"{exc} ({context})") from exc

    result: Dict[str, Any] = {
        "key": issue_key,
        "sprint_id": target_sprint_id,
        "status": "Added to Sprint",
    }
    if board_id is not None:
        result["board_id"] = board_id
    if sprint_name:
        result["sprint"] = sprint_name
    return result


def get_backlog_issues(client: JiraClient, board_id: int, max_results: int = 50) -> List[Dict[str, Any]]:
    """Retrieves issues from the backlog for a specific board."""
    path = f"/rest/agile/1.0/board/{board_id}/backlog"
    res = client.get(path, params={"maxResults": max_results})
    issues = res.get("issues", []) if res else []

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


def create_sprint(
    client: JiraClient,
    name: str,
    board_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    goal: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a new sprint associated with a board."""
    path = "/rest/agile/1.0/sprint"
    payload: Dict[str, Any] = {
        "name": name,
        "originBoardId": board_id,
    }
    if start_date:
        payload["startDate"] = start_date
    if end_date:
        payload["endDate"] = end_date
    if goal:
        payload["goal"] = goal

    res = client.post(path, payload=payload)
    return {
        "id": res.get("id"),
        "name": res.get("name"),
        "state": res.get("state"),
        "status": "Sprint Created",
    }


def update_sprint_state(
    client: JiraClient,
    sprint_id: int,
    state: str,
    name: Optional[str] = None,
    goal: Optional[str] = None,
) -> Dict[str, Any]:
    """Updates sprint metadata or changes state ('active', 'closed', 'future')."""
    path = f"/rest/agile/1.0/sprint/{sprint_id}"
    payload: Dict[str, Any] = {"state": state}
    if name:
        payload["name"] = name
    if goal:
        payload["goal"] = goal

    res = client.put(path, payload=payload)
    state_res = res.get("state", state) if isinstance(res, dict) else state
    return {
        "sprint_id": sprint_id,
        "state": state_res,
        "status": f"Sprint Updated to {state.capitalize()}",
    }
