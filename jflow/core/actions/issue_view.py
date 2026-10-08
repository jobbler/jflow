# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
# Updated in whole or in part by AI using Cursor (Composer).
from typing import Any, Dict, List, Optional, Tuple

from jflow.core.adf import adf_to_text
from jflow.core.actions.fields import decode_field_value
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager
from jflow.core.formatter import FIELD_ORDER_KEY

ISSUE_SHOW_FIELDS = [
    "summary",
    "status",
    "issuetype",
    "assignee",
    "reporter",
    "priority",
    "labels",
    "components",
    "parent",
    "created",
    "updated",
    "description",
]

# Input aliases (detail keys / short names) → Jira API field id.
_INPUT_TO_API: Dict[str, str] = {
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
_API_TO_DETAIL: Dict[str, str] = {
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


def parse_comments_arg(comments: str) -> Tuple[str, Optional[int]]:
    """Parse --comments value into (mode, count).

    Modes: none | last | all | <positive int as last N>.
    ``last`` means last 2 comments.
    """
    raw = (comments or "none").strip().lower()
    if raw == "none":
        return "none", None
    if raw == "all":
        return "all", None
    if raw == "last":
        return "last", 2
    if raw.isdigit():
        count = int(raw)
        if count < 1:
            raise ValueError("--comments N must be a positive integer.")
        return "last", count
    raise ValueError(
        "Invalid --comments value. Use none, last, all, or a positive integer."
    )


def _fetch_comments(client: JiraClient, issue_key: str) -> List[Dict[str, Any]]:
    path = f"/rest/api/3/issue/{issue_key}/comment"
    collected: List[Dict[str, Any]] = []
    start_at = 0
    page_size = 50
    while True:
        res = client.get(path, params={"startAt": start_at, "maxResults": page_size, "orderBy": "created"}) or {}
        values = res.get("comments", [])
        for item in values:
            author = item.get("author") or {}
            collected.append({
                "id": item.get("id"),
                "author": author.get("displayName") or author.get("emailAddress") or "",
                "created": item.get("created"),
                "body": adf_to_text(item.get("body")),
            })
        total = res.get("total")
        start_at += len(values)
        if not values or (total is not None and start_at >= total) or len(values) < page_size:
            break
    return collected


def _flatten_system_value(api_id: str, raw: Any) -> Any:
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


def needs_field_cache(names: Optional[List[str]]) -> bool:
    """True when any requested show field is not a built-in alias."""
    if not names:
        return False
    return any(
        _INPUT_TO_API.get((name or "").strip().casefold()) is None for name in names
    )


def _resolve_requested_fields(
    names: List[str],
    fields_mgr: Optional[FieldCacheManager],
) -> List[Tuple[str, str, Optional[Dict[str, Any]]]]:
    """Resolve requested names to (api_id, detail_key, schema_or_none).

    Raises ValueError for unknown names when a fields manager is required.
    """
    resolved: List[Tuple[str, str, Optional[Dict[str, Any]]]] = []
    seen_api: set = set()
    for original in names:
        needle = (original or "").strip()
        if not needle:
            continue
        api_id = _INPUT_TO_API.get(needle.casefold())
        meta: Optional[Dict[str, Any]] = None
        if api_id is None:
            if fields_mgr is None:
                raise ValueError(
                    f"Unknown field '{original}'. "
                    "Pass a FieldCacheManager or use a built-in field name."
                )
            meta = fields_mgr.resolve_field(needle)
            if not meta:
                raise ValueError(
                    f"Unknown field '{original}'. "
                    "Run 'jflow cache sync' and check the name."
                )
            api_id = meta["id"]
        else:
            # Prefer cache schema when available (e.g. description ADF).
            if fields_mgr is not None:
                meta = fields_mgr.resolve_field(api_id)

        if api_id in seen_api:
            continue
        seen_api.add(api_id)

        if api_id in _API_TO_DETAIL:
            detail_key = _API_TO_DETAIL[api_id]
        elif meta and meta.get("name"):
            detail_key = meta["name"]
        else:
            detail_key = original
        schema = (meta or {}).get("schema") if meta else None
        resolved.append((api_id, detail_key, schema))
    return resolved


def _build_default_details(res: Dict[str, Any], issue_key: str) -> Dict[str, Any]:
    f = res.get("fields") or {}
    assignee = f.get("assignee")
    reporter = f.get("reporter")
    parent = f.get("parent") or {}
    components = f.get("components") or []
    labels = f.get("labels") or []
    return {
        "key": res.get("key") or issue_key,
        "summary": f.get("summary") or "",
        "status": (f.get("status") or {}).get("name", ""),
        "type": (f.get("issuetype") or {}).get("name", ""),
        "assignee": assignee.get("displayName") if assignee else "Unassigned",
        "reporter": reporter.get("displayName") if reporter else "",
        "priority": (f.get("priority") or {}).get("name", ""),
        "labels": labels,
        "components": [c.get("name") for c in components if c.get("name")],
        "parent": parent.get("key") or "",
        "created": f.get("created") or "",
        "updated": f.get("updated") or "",
        "description": adf_to_text(f.get("description")),
    }


def get_issue(
    client: JiraClient,
    issue_key: str,
    comments: str = "none",
    only: Optional[List[str]] = None,
    show_fields: Optional[List[str]] = None,
    fields_mgr: Optional[FieldCacheManager] = None,
) -> Dict[str, Any]:
    """Fetch issue details, optionally with comments.

    Field selection precedence:
    1. ``only`` (CLI ``--only``) — overrides config
    2. ``show_fields`` (``defaults.show_fields`` in user.yaml)
    3. Built-in ``ISSUE_SHOW_FIELDS``

    ``key`` is always included. Comments are controlled separately via ``comments``.
    """
    mode, count = parse_comments_arg(comments)
    path = f"/rest/api/3/issue/{issue_key}"

    requested = only if only else (show_fields if show_fields else None)
    use_builtin = not requested

    if use_builtin:
        res = client.get(path, params={"fields": ",".join(ISSUE_SHOW_FIELDS)}) or {}
        details = _build_default_details(res, issue_key)
    else:
        if needs_field_cache(list(requested)) and fields_mgr is None:
            fields_mgr = FieldCacheManager(client)
        resolved = _resolve_requested_fields(list(requested), fields_mgr)
        if not resolved:
            raise ValueError("No fields requested for show.")
        api_ids = [api_id for api_id, _, _ in resolved]
        res = client.get(path, params={"fields": ",".join(api_ids)}) or {}
        f = res.get("fields") or {}
        details = {"key": res.get("key") or issue_key}
        field_order: List[str] = []
        for api_id, detail_key, schema in resolved:
            raw = f.get(api_id)
            if api_id in _API_TO_DETAIL:
                details[detail_key] = _flatten_system_value(api_id, raw)
            else:
                details[detail_key] = decode_field_value(schema, raw)
            # Force meta lines for explicitly requested non-structural fields,
            # including when empty (so show_fields like Story Points always appear).
            if detail_key not in ("key", "summary", "description", "comments"):
                field_order.append(detail_key)
        details[FIELD_ORDER_KEY] = field_order

    result: Dict[str, Any] = dict(details)
    if mode != "none":
        all_comments = _fetch_comments(client, issue_key)
        if mode == "last" and count is not None:
            result["comments"] = all_comments[-count:]
        else:
            result["comments"] = all_comments
    return result
