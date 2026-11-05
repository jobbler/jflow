# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Composer).
"""Issue hierarchy tree: `jflow tree KEY` rooted at the topmost ancestor."""
from typing import Any, Dict, List, Optional, Tuple

from jflow.core.actions.field_selection import INPUT_TO_API
from jflow.core.actions.fields import decode_field_value
from jflow.core.actions.issue_view import needs_field_cache
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager

_BASE_FIELDS = ["issuetype", "summary", "status", "parent"]


def _search_all(client: JiraClient, jql: str, fields: List[str]) -> List[Dict[str, Any]]:
    """Paginated POST search over /rest/api/3/search/jql."""
    payload: Dict[str, Any] = {"jql": jql, "maxResults": 100, "fields": fields}
    issues: List[Dict[str, Any]] = []
    while True:
        resp = client.post("/rest/api/3/search/jql", payload) or {}
        page = resp.get("issues", [])
        issues.extend(page)
        token = resp.get("nextPageToken")
        if token is not None and page:
            payload["nextPageToken"] = token
            continue
        total = resp.get("total")
        if token is None and total is not None and page and len(issues) < total:
            payload["startAt"] = len(issues)
            continue
        return issues


def _resolve_extra_fields(
    fields: List[str],
    fields_mgr: Optional[FieldCacheManager],
) -> List[Tuple[str, str, Optional[Dict[str, Any]]]]:
    """Resolve extra field names to (api_id, display_name, schema) triples."""
    if not fields:
        return []
    resolved: List[Tuple[str, str, Optional[Dict[str, Any]]]] = []
    seen: set = set()
    for original in fields:
        needle = (original or "").strip()
        if not needle:
            continue
        api_id = INPUT_TO_API.get(needle.casefold())
        meta: Optional[Dict[str, Any]] = None
        if api_id is None:
            if fields_mgr is None:
                raise ValueError(
                    f"Unknown field '{original}'. Run 'jflow cache sync'."
                )
            meta = fields_mgr.resolve_field(needle)
            if not meta:
                raise ValueError(f"Unknown field '{original}'. Run 'jflow cache sync'.")
            api_id = meta["id"]
        if api_id in seen:
            continue
        seen.add(api_id)
        display = (meta or {}).get("name") or original
        schema = (meta or {}).get("schema")
        resolved.append((api_id, display, schema))
    return resolved


def _node_from_raw(
    item: Dict[str, Any],
    extras: List[Tuple[str, str, Optional[Dict[str, Any]]]],
) -> Dict[str, Any]:
    """Build a tree node dict from a raw Jira issue payload."""
    f = item.get("fields") or {}
    node: Dict[str, Any] = {
        "key": item.get("key"),
        "type": (f.get("issuetype") or {}).get("name"),
        "summary": f.get("summary") or "",
        "status": (f.get("status") or {}).get("name"),
        "children": [],
    }
    for api_id, display, schema in extras:
        node[display] = decode_field_value(schema, f.get(api_id))
    return node


def _fetch_node(
    client: JiraClient,
    key: str,
    api_fields: List[str],
    extras: List[Tuple[str, str, Optional[Dict[str, Any]]]],
) -> Dict[str, Any]:
    res = client.get(f"/rest/api/3/issue/{key}", params={"fields": ",".join(api_fields)})
    node = _node_from_raw(res, extras)
    node["_parent_key"] = ((res.get("fields") or {}).get("parent") or {}).get("key")
    return node


def _epic_link_field_id(client: JiraClient) -> Optional[str]:
    mgr = FieldCacheManager(client)
    field_id = mgr.resolve_field_id("Epic Link")
    if field_id:
        return field_id
    for entry in (mgr.load_cache().get("by_id") or {}).values():
        if (entry.get("schema") or {}).get("type") == "epiclink":
            return entry.get("id")
    return None


def _children(
    client: JiraClient,
    node: Dict[str, Any],
    api_fields: List[str],
    extras: List[Tuple[str, str, Optional[Dict[str, Any]]]],
    path: set,
) -> List[Dict[str, Any]]:
    """Direct children of a node (depth-first recursion happens in build_tree)."""
    key = node["key"]
    raw = _search_all(client, f'parent = "{key}"', api_fields)
    if not raw and (node.get("type") or "").lower() == "epic":
        epic_link_id = _epic_link_field_id(client)
        if epic_link_id:
            raw = _search_all(client, f'cf[{epic_link_id}] = "{key}"', api_fields)
    children = [_node_from_raw(item, extras) for item in raw]
    children.sort(key=lambda c: c["key"] or "")
    return [c for c in children if c["key"] not in path]


def build_tree(
    client: JiraClient,
    key: str,
    fields: Optional[List[str]] = None,
    fields_mgr: Optional[FieldCacheManager] = None,
) -> Dict[str, Any]:
    """Return the issue's hierarchy rooted at its topmost ancestor.

    The returned root dict carries an internal ``_tree`` marker (stripped from
    json/yaml output) so the formatter can render tree connectors.
    """
    extras: List[Tuple[str, str, Optional[Dict[str, Any]]]] = []
    if fields:
        if fields_mgr is None and needs_field_cache(fields):
            fields_mgr = FieldCacheManager(client)
        extras = _resolve_extra_fields(fields, fields_mgr)
    api_fields = list(dict.fromkeys(_BASE_FIELDS + [api_id for api_id, _, _ in extras]))

    node = _fetch_node(client, key, api_fields, extras)
    visited = {key}

    # Parent ascent: follow fields.parent upward until no parent or a cycle.
    while True:
        parent_key = node.pop("_parent_key", None)
        if not parent_key:
            break
        parent = _fetch_node(client, parent_key, api_fields, extras)
        next_key = parent.pop("_parent_key", None)
        if next_key and (next_key == key or next_key in visited):
            # Cycle detected: stop the ascent at the current node.
            break
        visited.add(parent_key)
        node = parent

    root = node


    # Depth-first descent.
    def descend(node: Dict[str, Any], path: set) -> Dict[str, Any]:
        path = path | {node["key"]}
        node["children"] = [
            descend(child, path)
            for child in _children(client, node, api_fields, extras, path)
        ]
        return node

    root = descend(root, set())
    root["_tree"] = True
    return root


def fetch_family_status(
    client: JiraClient, keys: List[str]
) -> Dict[str, Dict[str, Any]]:
    """Batch raw status/parent/issuelinks/issuetype for issue keys."""
    unique = list(dict.fromkeys(k for k in keys if k))
    result: Dict[str, Dict[str, Any]] = {}
    fields = ["status", "parent", "issuelinks", "issuetype"]
    for i in range(0, len(unique), 50):
        chunk = unique[i : i + 50]
        jql = 'key IN (' + ",".join(f'"{k}"' for k in chunk) + ')'
        for item in _search_all(client, jql, fields):
            result[item.get("key")] = item.get("fields") or {}
    return result
