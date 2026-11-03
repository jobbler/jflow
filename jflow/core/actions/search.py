# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
import warnings
from typing import Any, Callable, Dict, List, NamedTuple, Optional

from jflow.config.models import AppConfig
from jflow.core.actions.field_selection import (
    API_TO_DETAIL,
    CURRENT_SPRINT,
    CURRENT_SPRINT_LABEL,
    INPUT_TO_API,
    SPRINT_FIELD_NAME,
    active_board_sprints,
    current_sprint_name,
    flatten_system_value,
    virtual_field,
)
from jflow.core.actions.fields import decode_field_value
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager

_DEFAULT_LIST_TARGET_FIELDS = ["summary", "status", "issuetype", "assignee", "updated"]

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


class ListColumn(NamedTuple):
    api_id: str
    label: str
    schema: Optional[Dict[str, Any]] = None
    virtual: Optional[str] = None


def _warn_list_field(
    on_warning: Optional[Callable[[str], None]], message: str
) -> None:
    if on_warning is not None:
        on_warning(message)
    else:
        warnings.warn(message, RuntimeWarning, stacklevel=3)


def _warn_unknown_list_field(
    on_warning: Optional[Callable[[str], None]], original: str
) -> None:
    _warn_list_field(
        on_warning,
        f"Skipping unknown list field '{original}'. "
        "Run 'jflow cache sync' and check the name.",
    )


def _list_fields_need_cache(names: List[str]) -> bool:
    for name in names:
        needle = (name or "").strip()
        if not needle:
            continue
        if needle.casefold() == "key" or needle.casefold() in INPUT_TO_API:
            continue
        return True
    return False


def _list_field_label(
    api_id: str, meta: Optional[Dict[str, Any]], original: str
) -> str:
    if api_id == "issuetype":
        return "Type"
    detail_key = API_TO_DETAIL.get(api_id)
    if detail_key:
        return detail_key.replace("_", " ").capitalize()
    return (meta or {}).get("name") or original


def _resolve_list_fields(
    names: List[str],
    client: JiraClient,
    fields_mgr: Optional[FieldCacheManager],
    on_warning: Optional[Callable[[str], None]],
) -> List[ListColumn]:
    """Resolve display names/ids to list columns."""
    resolved: List[ListColumn] = []
    seen: set = set()
    for original in names:
        needle = (original or "").strip()
        if not needle:
            continue
        if needle.casefold() == "key":
            if "key" in seen:
                continue
            seen.add("key")
            resolved.append(ListColumn("key", "Key"))
            continue

        virtual = virtual_field(needle)
        if virtual is not None:
            if virtual in seen:
                continue
            if fields_mgr is None:
                fields_mgr = FieldCacheManager(client)
            sprint_meta = fields_mgr.resolve_field(SPRINT_FIELD_NAME)
            if not sprint_meta:
                _warn_list_field(
                    on_warning,
                    f"Skipping '{original}': no '{SPRINT_FIELD_NAME}' field in the "
                    "field cache. Run 'jflow cache sync'.",
                )
                continue
            seen.add(virtual)
            resolved.append(
                ListColumn(
                    sprint_meta["id"],
                    CURRENT_SPRINT_LABEL,
                    sprint_meta.get("schema"),
                    virtual,
                )
            )
            continue

        api_id = INPUT_TO_API.get(needle.casefold())
        meta: Optional[Dict[str, Any]] = None
        if api_id is None:
            if fields_mgr is None:
                fields_mgr = FieldCacheManager(client)
            meta = fields_mgr.resolve_field(needle)
            if not meta:
                _warn_unknown_list_field(on_warning, original)
                continue
            api_id = meta["id"]
        elif fields_mgr is not None:
            meta = fields_mgr.resolve_field(api_id)

        if api_id in seen:
            continue
        seen.add(api_id)
        label = _list_field_label(api_id, meta, original)
        schema = (meta or {}).get("schema")
        resolved.append(ListColumn(api_id, label, schema))
    return resolved


def _build_list_row(
    item: Dict[str, Any],
    resolved: List[ListColumn],
    active_sprints: Optional[Dict[int, str]] = None,
) -> Dict[str, Any]:
    f = item.get("fields") or {}
    row: Dict[str, Any] = {}
    for column in resolved:
        if column.virtual == CURRENT_SPRINT:
            row[column.label] = current_sprint_name(
                f.get(column.api_id), active_sprints or {}
            )
        elif column.api_id == "key":
            row[column.label] = item.get("key")
        elif column.api_id in API_TO_DETAIL:
            row[column.label] = flatten_system_value(
                column.api_id, f.get(column.api_id)
            )
        else:
            row[column.label] = decode_field_value(
                column.schema, f.get(column.api_id)
            )
    return row


def search_issues(
    client: JiraClient,
    jql: str,
    max_results: int = 15,
    fields: Optional[List[str]] = None,
    config: Optional[AppConfig] = None,
    template_vars: Optional[Dict[str, str]] = None,
    list_fields: Optional[List[str]] = None,
    fields_mgr: Optional[FieldCacheManager] = None,
    on_warning: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, Any]]:
    """Queries issues using JQL, resolving aliases and optional {placeholder} vars.

    ``list_fields`` selects the output columns (aliases, display names,
    ``customfield_*`` ids, or the ``current_sprint`` virtual field). When omitted,
    ``defaults.list_fields`` is used if set; otherwise the built-in
    Key/Type/Summary/Status/Assignee columns.
    """
    from jflow.core.templates import merge_config_vars, render_string

    resolved_jql = config.resolve_jql(jql) if config else jql
    jql_vars = merge_config_vars(config, template_vars)
    if jql_vars:
        resolved_jql = render_string(resolved_jql, jql_vars) or resolved_jql

    effective_fields = list_fields
    if effective_fields is None and config is not None:
        effective_fields = config.user.defaults.list_fields
    board = config.user.defaults.board if config is not None else None
    configured = [name for name in (effective_fields or []) if (name or "").strip()]
    requested: List[str] = []
    for name in configured:
        if virtual_field(name) and not board:
            _warn_list_field(
                on_warning,
                f"Skipping '{name}': set defaults.board to use it.",
            )
            continue
        requested.append(name)
    if configured and not requested:
        raise ValueError(
            "No valid list fields were configured. "
            "Check defaults.list_fields or --fields."
        )

    resolved_columns: Optional[List[ListColumn]] = None
    active_sprints: Dict[int, str] = {}
    if requested:
        if _list_fields_need_cache(requested) and fields_mgr is None:
            fields_mgr = FieldCacheManager(client)
        resolved_columns = _resolve_list_fields(
            requested, client, fields_mgr, on_warning
        )
        if not resolved_columns:
            raise ValueError(
                "No valid list fields were configured. "
                "Check defaults.list_fields or --fields."
            )
        target_fields = list(
            dict.fromkeys(
                column.api_id
                for column in resolved_columns
                if column.api_id != "key"
            )
        )
        if any(column.virtual for column in resolved_columns):
            active_sprints = active_board_sprints(client, board)
    else:
        target_fields = fields or list(_DEFAULT_LIST_TARGET_FIELDS)

    payload: Dict[str, Any] = {
        "jql": resolved_jql,
        "maxResults": max_results,
    }
    if target_fields:
        payload["fields"] = target_fields

    response = client.post("/rest/api/3/search/jql", payload)
    issues = response.get("issues", []) if response else []

    if resolved_columns is not None:
        return [
            _build_list_row(item, resolved_columns, active_sprints)
            for item in issues
        ]

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
    list_fields: Optional[List[str]] = None,
    fields_mgr: Optional[FieldCacheManager] = None,
    on_warning: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, Any]]:
    """List issues assigned to the current user using presets, status, or raw JQL."""
    resolved = build_my_issues_jql(filter_name=filter_name, status=status, jql=jql)
    return search_issues(
        client,
        jql=resolved,
        max_results=max_results,
        config=config,
        template_vars=template_vars,
        list_fields=list_fields,
        fields_mgr=fields_mgr,
        on_warning=on_warning,
    )
