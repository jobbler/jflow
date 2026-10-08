# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
# Updated in whole or in part by AI using Cursor (Composer).
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import yaml

# Preferred metadata order for issue detail views.
_META_ORDER: Tuple[str, ...] = (
    "type",
    "status",
    "assignee",
    "reporter",
    "priority",
    "labels",
    "components",
    "parent",
    "created",
    "updated",
)
_STRUCTURAL_KEYS = frozenset({"key", "summary", "description", "comments"})
_DATE_KEYS = frozenset({"created", "updated"})
# Internal: ordered meta keys that must render even when empty (explicit show_fields/--only).
FIELD_ORDER_KEY = "_jflow_field_order"
_INTERNAL_KEYS = frozenset({FIELD_ORDER_KEY})
# Jira often emits offsets like +0000 instead of +00:00.
_JIRA_OFFSET_RE = re.compile(r"([+-]\d{2})(\d{2})$")


def flatten_dict(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Flatten nested dicts into dotted keys. Leaves lists and scalars as leaf values."""
    flat: Dict[str, Any] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flat.update(flatten_dict(value, full_key))
        else:
            flat[full_key] = value
    return flat


def _dict_has_nested_dict(data: Dict[str, Any]) -> bool:
    return any(isinstance(v, dict) for v in data.values())


def _parse_jira_datetime(value: str) -> Optional[datetime]:
    """Parse a Jira ISO-8601 timestamp into an aware datetime, or None."""
    raw = (value or "").strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    match = _JIRA_OFFSET_RE.search(normalized)
    if match and ":" not in match.group(0):
        normalized = (
            normalized[: match.start()]
            + f"{match.group(1)}:{match.group(2)}"
        )
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def format_timestamp_human(value: str) -> str:
    """Local time first, original ISO in parentheses. Non-parseable values pass through."""
    raw = value if isinstance(value, str) else str(value)
    dt = _parse_jira_datetime(raw)
    if dt is None:
        return raw
    local = dt.astimezone()
    tz = local.strftime("%Z") or local.strftime("%z")
    local_str = local.strftime("%Y-%m-%d %H:%M")
    if tz:
        local_str = f"{local_str} {tz}"
    return f"{local_str} ({raw})"


def _format_scalar(value: Any, *, human_dates: bool = False, date_key: bool = False) -> str:
    if isinstance(value, list):
        if not value:
            return ""
        if all(isinstance(item, dict) for item in value):
            blocks = []
            for item in value:
                parts = [f"{k}={v}" for k, v in item.items()]
                blocks.append("; ".join(parts))
            return " | ".join(blocks)
        return ",".join(str(item) for item in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if human_dates and date_key and isinstance(value, str):
        return format_timestamp_human(value)
    return str(value)


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and not value:
        return True
    return False


def _is_issue_detail(data: Dict[str, Any]) -> bool:
    if "key" not in data:
        return False
    return any(k in data for k in ("summary", "description", "comments", "status", "type"))


def _is_issue_list(data: List[Any]) -> bool:
    if not data or not isinstance(data[0], dict):
        return False
    keys = {str(k).casefold() for k in data[0].keys()}
    return "key" in keys and ("summary" in keys or "status" in keys)


def _meta_items(data: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """Metadata fields for issue detail views.

    When ``FIELD_ORDER_KEY`` is set (explicit ``show_fields`` / ``--only``), emit
    those keys in order even if empty. Otherwise skip empties and use preferred order.
    """
    forced = data.get(FIELD_ORDER_KEY)
    if isinstance(forced, list):
        items: List[Tuple[str, Any]] = []
        for key in forced:
            if key in _STRUCTURAL_KEYS or key in _INTERNAL_KEYS:
                continue
            if key not in data:
                continue
            value = data[key]
            items.append((key, "" if value is None else value))
        return items

    items = []
    seen = set()
    for key in _META_ORDER:
        if key in data and key not in _STRUCTURAL_KEYS and not _is_empty(data[key]):
            items.append((key, data[key]))
            seen.add(key)
    for key, value in data.items():
        if (
            key in _STRUCTURAL_KEYS
            or key in _INTERNAL_KEYS
            or key in seen
            or _is_empty(value)
        ):
            continue
        items.append((key, value))
    return items


def _labelize(key: str) -> str:
    if not key:
        return key
    # Preserve Jira display names (e.g. "Story Points", "Git Pull Request").
    if " " in key:
        return key
    return key.replace("_", " ").strip().capitalize()


def _public_payload(data: Any) -> Any:
    """Strip internal formatter keys from machine-readable payloads."""
    if not isinstance(data, dict):
        return data
    return {k: v for k, v in data.items() if k not in _INTERNAL_KEYS}


def _indent_block(text: str, prefix: str = "  ") -> str:
    if not text:
        return ""
    return "\n".join(prefix + line if line else prefix.rstrip() for line in text.splitlines())


def _is_linked_issues_value(value: Any) -> bool:
    """True when value looks like decoded issuelinks (list of link dicts)."""
    if not isinstance(value, list) or not value:
        return False
    if not all(isinstance(item, dict) for item in value):
        return False
    for item in value:
        if "key" not in item:
            return False
        if "type" not in item and "relation" not in item:
            return False
    return True


def _linked_issue_heading(item: Dict[str, Any]) -> str:
    """Subsection label from directional relation (e.g. blocks / is blocked by)."""
    raw = (item.get("relation") or item.get("type") or "").strip() or "Linked"
    return raw[:1].upper() + raw[1:] if raw else "Linked"


def _format_linked_issues(value: List[Dict[str, Any]]) -> str:
    """Group linked issues by directional relation into indented subsections."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for item in value:
        heading = _linked_issue_heading(item)
        if heading not in groups:
            groups[heading] = []
            order.append(heading)
        groups[heading].append(item)

    lines: List[str] = []
    for heading in order:
        lines.append(f"  {heading}:")
        for item in groups[heading]:
            key = item.get("key") or ""
            status = item.get("status") or ""
            summary = item.get("summary") or ""
            parts = [p for p in (key, status, summary) if p]
            lines.append(f"    {' '.join(parts)}")
    return "\n".join(lines)


def _format_issue_text(data: Dict[str, Any]) -> str:
    key = data.get("key") or ""
    summary = data.get("summary") or ""
    lines: List[str] = []
    title = f"{key}: {summary}".strip(": ").strip()
    lines.append(title or str(key))
    lines.append("")

    for meta_key, value in _meta_items(data):
        label = _labelize(meta_key)
        if _is_linked_issues_value(value):
            lines.append(f"{label}:")
            lines.append(_format_linked_issues(value))
        else:
            rendered = _format_scalar(value, human_dates=True, date_key=meta_key in _DATE_KEYS)
            lines.append(f"{label}: {rendered}")

    description = data.get("description")
    if not _is_empty(description):
        if lines and lines[-1] != "":
            lines.append("")
        lines.append("Description")
        lines.append(_indent_block(str(description)))

    comments = data.get("comments")
    if isinstance(comments, list) and comments:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append("Comments")
        for i, comment in enumerate(comments):
            if not isinstance(comment, dict):
                lines.append("")
                lines.append(_indent_block(str(comment)))
                continue
            author = comment.get("author") or ""
            created_raw = comment.get("created") or ""
            created = (
                format_timestamp_human(str(created_raw)) if created_raw else ""
            )
            header = f"[{author} — {created}]" if created else f"[{author}]"
            if i > 0:
                lines.append("")
            lines.append(header)
            body = comment.get("body") or ""
            if body:
                lines.append(_indent_block(str(body)))

    return "\n".join(lines).rstrip() + "\n"


def _format_issue_markdown(data: Dict[str, Any]) -> str:
    key = data.get("key") or ""
    summary = data.get("summary") or ""
    lines: List[str] = []
    if summary:
        lines.append(f"# {key}: {summary}")
    else:
        lines.append(f"# {key}")
    lines.append("")

    meta = _meta_items(data)
    if meta:
        for meta_key, value in meta:
            label = _labelize(meta_key)
            if _is_linked_issues_value(value):
                lines.append(f"**{label}:**")
                lines.append(_format_linked_issues(value))
            else:
                rendered = _format_scalar(
                    value, human_dates=True, date_key=meta_key in _DATE_KEYS
                )
                lines.append(f"**{label}:** {rendered}")
        lines.append("")

    description = data.get("description")
    if not _is_empty(description):
        lines.append("## Description")
        lines.append("")
        lines.append(str(description).rstrip())
        lines.append("")

    comments = data.get("comments")
    if isinstance(comments, list) and comments:
        lines.append("## Comments")
        lines.append("")
        for i, comment in enumerate(comments):
            if i > 0:
                lines.append("")
            if not isinstance(comment, dict):
                lines.append(str(comment))
                continue
            author = comment.get("author") or "Unknown"
            created_raw = comment.get("created") or ""
            created = (
                format_timestamp_human(str(created_raw)) if created_raw else ""
            )
            heading = f"### {author} — {created}" if created else f"### {author}"
            lines.append(heading)
            lines.append("")
            body = comment.get("body") or ""
            if body:
                lines.append(str(body).rstrip())

    return "\n".join(lines).rstrip() + "\n"


def _format_sectioned_text(data: Dict[str, Any], *, human_dates: bool = False) -> str:
    """Render nested dicts as section headers with indented key: value lines."""
    lines: List[str] = []
    first = True
    for section, value in data.items():
        if not first:
            lines.append("")
        first = False
        if isinstance(value, dict):
            lines.append(f"{section}:")
            for k, v in value.items():
                if isinstance(v, dict):
                    lines.append(f"  {k}:")
                    for sk, sv in v.items():
                        lines.append(
                            f"    {sk}: {_format_scalar(sv, human_dates=human_dates, date_key=sk in _DATE_KEYS)}"
                        )
                else:
                    lines.append(
                        f"  {k}: {_format_scalar(v, human_dates=human_dates, date_key=k in _DATE_KEYS)}"
                    )
        else:
            lines.append(
                f"{section}: {_format_scalar(value, human_dates=human_dates, date_key=section in _DATE_KEYS)}"
            )
    return "\n".join(lines)


def _format_aligned_table(rows: List[Dict[str, Any]]) -> str:
    """Plain space-aligned columns (no box drawing)."""
    if not rows:
        return ""
    headers = list(rows[0].keys())
    str_rows = [[_format_scalar(item.get(h, "")) for h in headers] for item in rows]
    widths = [len(str(h)) for h in headers]
    for row in str_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    header_line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
    body = ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in str_rows]
    return "\n".join([header_line, *body])


def _format_list_markdown(rows: List[Dict[str, Any]]) -> str:
    """Bullet list for issue-like or generic list-of-dicts."""
    if not rows:
        return ""
    lines: List[str] = []
    for item in rows:
        # Prefer Key/Summary style when present (case-insensitive lookup).
        key_map = {str(k).casefold(): (k, v) for k, v in item.items()}
        key_pair = key_map.get("key")
        summary_pair = key_map.get("summary")
        status_pair = key_map.get("status")
        if key_pair is not None:
            key_val = key_pair[1]
            parts = [f"**{key_val}**"]
            if status_pair is not None and not _is_empty(status_pair[1]):
                parts.append(str(status_pair[1]))
            if summary_pair is not None and not _is_empty(summary_pair[1]):
                parts.append(str(summary_pair[1]))
            # Include remaining non-empty fields briefly.
            used = {"key", "summary", "status"}
            extras = []
            for k, v in item.items():
                if str(k).casefold() in used or _is_empty(v):
                    continue
                extras.append(f"{k}: {v}")
            line = " — ".join(parts)
            if extras:
                line = f"{line} ({'; '.join(extras)})"
            lines.append(f"- {line}")
        else:
            bits = [f"{k}: {v}" for k, v in item.items() if not _is_empty(v)]
            lines.append(f"- {'; '.join(bits)}")
    return "\n".join(lines)


def _format_human(data: Any) -> str:
    """Unix-like human output: structured issues, sectioned dicts, or aligned columns."""
    if isinstance(data, dict):
        if _is_issue_detail(data):
            return _format_issue_text(data)
        if _dict_has_nested_dict(data):
            return _format_sectioned_text(data, human_dates=True)
        return "\n".join(
            f"{k}: {_format_scalar(v, human_dates=True, date_key=k in _DATE_KEYS)}"
            for k, v in data.items()
        )
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            return _format_aligned_table(data)
        return "\n".join(str(item) for item in data)
    return str(data)


def _format_markdown(data: Any) -> str:
    """Markdown human output for issues, lists, and generic payloads."""
    if isinstance(data, dict):
        if _is_issue_detail(data):
            return _format_issue_markdown(data)
        if _dict_has_nested_dict(data):
            lines: List[str] = []
            for section, value in data.items():
                lines.append(f"## {section}")
                lines.append("")
                if isinstance(value, dict):
                    for k, v in value.items():
                        if isinstance(v, dict):
                            lines.append(f"### {k}")
                            lines.append("")
                            for sk, sv in v.items():
                                lines.append(
                                    f"- **{sk}:** {_format_scalar(sv, human_dates=True, date_key=sk in _DATE_KEYS)}"
                                )
                            lines.append("")
                        else:
                            lines.append(
                                f"- **{k}:** {_format_scalar(v, human_dates=True, date_key=k in _DATE_KEYS)}"
                            )
                else:
                    lines.append(
                        _format_scalar(
                            value, human_dates=True, date_key=section in _DATE_KEYS
                        )
                    )
                lines.append("")
            return "\n".join(lines).rstrip() + "\n"
        lines = [
            f"- **{k}:** {_format_scalar(v, human_dates=True, date_key=k in _DATE_KEYS)}"
            for k, v in data.items()
        ]
        return "\n".join(lines) + ("\n" if lines else "")
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            return _format_list_markdown(data) + "\n"
        return "\n".join(f"- {item}" for item in data) + ("\n" if data else "")
    return str(data) + "\n"


def format_output(data: Any, format_type: str = "markdown") -> str:
    if format_type in ("json", "yaml", "unix"):
        data = _public_payload(data)
    if format_type == "json":
        return json.dumps(data, indent=2)
    if format_type == "yaml":
        return yaml.dump(data, default_flow_style=False)
    if format_type == "unix":
        if isinstance(data, dict):
            rows = flatten_dict(data) if _dict_has_nested_dict(data) else data
            return "\n".join(f"{k}={_format_scalar(v)}" for k, v in rows.items())
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                headers = list(data[0].keys())
                lines = ["\t".join(headers)]
                for item in data:
                    lines.append("\t".join(_format_scalar(item.get(h, "")) for h in headers))
                return "\n".join(lines)
            return "\n".join(str(item) for item in data)
        return str(data)
    if format_type == "markdown":
        return _format_markdown(data)
    if format_type == "text":
        return _format_human(data)
    return str(data)
