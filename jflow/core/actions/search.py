# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
import re
import warnings
from typing import Any, Callable, Dict, List, NamedTuple, Optional

from jflow.config.models import AppConfig
from jflow.core.actions.field_selection import (
    API_TO_DETAIL,
    BLOCKED,
    BLOCKED_LABEL,
    CURRENT_SPRINT,
    CURRENT_SPRINT_LABEL,
    INPUT_TO_API,
    SPRINT_FIELD_NAME,
    active_board_sprints,
    current_sprint_name,
    flatten_system_value,
    virtual_field,
)
from jflow.core.actions.blocked import compute_blocked, resolve_native_blocked_id
from jflow.core.actions.fields import decode_field_value
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager

_DEFAULT_LIST_TARGET_FIELDS = ["summary", "status", "issuetype", "assignee", "updated"]

MY_ISSUE_FILTERS = {
    "all": "assignee = currentUser()",
    "open": "assignee = currentUser() AND statusCategory != Done",
    "closed": "assignee = currentUser() AND statusCategory = Done",
    "in-progress": 'assignee = currentUser() AND statusCategory = "In Progress"',
    "review": (
        "assignee = currentUser() AND statusCategory != Done "
        'AND (status = "Review" OR status = "In Review")'
    ),
    "code-review": (
        "assignee = currentUser() AND "
        '(status = "Code Review" OR status = "Code review")'
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
        return f'assignee = currentUser() AND status = "{safe}"'
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

_SORT_JQL_FIELDS = {
    "key", "issuetype", "summary", "status", "priority", "assignee",
    "reporter", "created", "updated", "resolution", "duedate", "due",
}
_SORT_FIELD_ALIASES = {"type": "issuetype", "due": "duedate"}


def parse_sort_terms(options: Optional[List[str]]) -> Optional[List[str]]:
    """Flatten repeatable/comma-split --sort options to clean terms; None if absent/empty."""
    if options is None:
        return None
    terms: List[str] = []
    for option in options:
        for term in (option or "").split(","):
            term = term.strip()
            if term:
                terms.append(term)
    return terms or None


def parse_list_field_terms(options: Optional[List[str]]) -> Optional[List[str]]:
    """Flatten repeatable/comma-split field options; None if absent/empty."""
    if options is None:
        return None
    names: List[str] = []
    for option in options:
        for name in (option or "").split(","):
            name = name.strip()
            if name:
                names.append(name)
    return names or None


def _find_order_by(jql: str) -> int:
    """Index of the unquoted 'ORDER BY' keyword in jql, or -1 when absent."""
    in_string = False
    i = 0
    while i < len(jql):
        ch = jql[i]
        if ch == '"':
            in_string = not in_string
            i += 1
            continue
        if not in_string and jql[i:i + 8].upper() == "ORDER BY":
            before = jql[i - 1] if i > 0 else " "
            after = jql[i + 8] if i + 8 < len(jql) else " "
            if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
                return i
            i += 8
            continue
        i += 1
    return -1


def jql_has_order_by(jql: str) -> bool:
    """True when jql contains an ORDER BY keyword outside double-quoted strings."""
    return _find_order_by(jql) != -1


def _sort_needs_cache(sort: List[str]) -> bool:
    for term in sort:
        name = (term or "").lstrip("-").strip().lower()
        if not name:
            continue
        name = _SORT_FIELD_ALIASES.get(name, name)
        if name in _SORT_JQL_FIELDS:
            continue
        return True
    return False


def apply_sort(
    jql: str, sort: List[str], fields_mgr: Optional[FieldCacheManager] = None
) -> str:
    """Append (or replace) an ORDER BY clause built from sort terms.

    Each term is a JQL field name, optionally prefixed with ``-`` for descending.
    ``type``/``due`` are aliases for ``issuetype``/``duedate``; other names are
    resolved via the field cache when not in the built-in set.
    """
    parts: List[str] = []
    for term in sort:
        term = (term or "").strip()
        if not term:
            continue
        desc = term.startswith("-")
        name = term.lstrip("-").strip()
        lowered = name.lower()
        lowered = _SORT_FIELD_ALIASES.get(lowered, lowered)
        if lowered in _SORT_JQL_FIELDS:
            resolved = lowered
        elif fields_mgr is not None:
            field_id = fields_mgr.resolve_field_id(name)
            if not field_id:
                raise ValueError(f"Unknown sort field: {name}")
            resolved = field_id
        else:
            raise ValueError(f"Unknown sort field: {name}")
        parts.append(f"{resolved} DESC" if desc else f"{resolved} ASC")
    if not parts:
        return jql
    clause = "ORDER BY " + ", ".join(parts)
    idx = _find_order_by(jql)
    if idx != -1:
        return jql[:idx].rstrip() + " " + clause
    return jql.rstrip() + " " + clause


def _list_field_label(
    api_id: str, meta: Optional[Dict[str, Any]], original: str
) -> str:
    if api_id == "issuetype":
        return "Type"
    if api_id == BLOCKED:
        return BLOCKED_LABEL
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
        if virtual == BLOCKED:
            if BLOCKED in seen:
                continue
            if fields_mgr is None:
                fields_mgr = FieldCacheManager(client)
            seen.add(BLOCKED)
            resolved.append(ListColumn(BLOCKED, BLOCKED_LABEL, None, BLOCKED))
            continue
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
        if column.virtual == BLOCKED:
            row[column.label] = "yes" if item.get("_blocked") else "no"
        elif column.virtual == CURRENT_SPRINT:
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
    if item.get("_blocked"):
        status_label = next(
            (c.label for c in resolved if c.api_id == "status"), None
        )
        if status_label and isinstance(row.get(status_label), str):
            row[status_label] = f"{row[status_label]} (blocked)"
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
    sort: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Queries issues using JQL, resolving aliases and optional {placeholder} vars.

    ``list_fields`` selects the output columns (aliases, display names,
    ``customfield_*`` ids, or the ``current_sprint`` virtual field). When omitted,
    ``defaults.list_fields`` is used if set; otherwise the built-in
    Key/Type/Summary/Status/Assignee columns.
    """
    from jflow.core.templates import render_string

    resolved_jql = config.resolve_jql(jql) if config else jql
    if config is not None or template_vars:
        var_map = config.build_vars(template_vars) if config is not None else (template_vars or {})
        resolved_jql = render_string(resolved_jql, var_map) or resolved_jql
        unknown = re.findall(r"\{([a-zA-Z0-9_]+)\}", resolved_jql)
        if unknown:
            raise ValueError(
                "Unknown JQL placeholder(s): "
                + ", ".join(f"{{{name}}}" for name in sorted(set(unknown)))
                + ". Define them under defaults.vars in user.yaml or pass --var/-V name=value."
            )

    effective_sort = sort if sort is not None else (
        config.user.defaults.sort_issues if config is not None else None
    )
    if (sort is not None or effective_sort) and _sort_needs_cache(sort or effective_sort) and fields_mgr is None:
        fields_mgr = FieldCacheManager(client)
    if sort is not None:
        resolved_jql = apply_sort(resolved_jql, sort, fields_mgr)
    elif not jql_has_order_by(resolved_jql):
        resolved_jql = apply_sort(resolved_jql, effective_sort or ["-updated"], fields_mgr)

    effective_fields = list_fields
    if effective_fields is None and config is not None:
        effective_fields = config.user.defaults.list_fields
    board = config.user.defaults.board if config is not None else None
    effective_fields = parse_list_field_terms(effective_fields)
    configured = [name for name in (effective_fields or []) if (name or "").strip()]
    requested: List[str] = []
    for name in configured:
        if virtual_field(name) == CURRENT_SPRINT and not board:
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
    want_blocked = False
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
                if column.api_id != "key" and column.virtual != BLOCKED
            )
        )
        want_blocked = any(column.virtual == BLOCKED for column in resolved_columns)
        if want_blocked:
            if fields_mgr is None:
                fields_mgr = FieldCacheManager(client)
            native_id = resolve_native_blocked_id(fields_mgr)
            target_fields += [
                f for f in ("parent", "issuelinks", "resolution", "status")
                if f not in target_fields
            ]
            if native_id and native_id not in target_fields:
                target_fields.append(native_id)
        if any(column.virtual == CURRENT_SPRINT for column in resolved_columns):
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
        if want_blocked and issues:
            blocked_map = compute_blocked(client, issues, fields_mgr)
            for item in issues:
                item["_blocked"] = blocked_map.get(item.get("key"), False)
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
    sort: Optional[List[str]] = None,
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
        sort=sort,
    )
