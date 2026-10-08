# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Grok 4.5).
# Updated in whole or in part by AI using Cursor (Composer).
# ==============================================================================
from typing import Any, Dict, List, Optional

from jflow.core.adf import adf_to_text, collapse_to_single_line, text_to_adf_doc
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager


def _browse_url_from_linked_issue(issue: Dict[str, Any]) -> str:
    """Build a browse URL from a linked issue's self URL and key."""
    key = issue.get("key") or ""
    self_url = issue.get("self") or ""
    if key and "/rest/" in self_url:
        base = self_url.split("/rest/", 1)[0].rstrip("/")
        return f"{base}/browse/{key}"
    return ""


def _decode_issuelink(item: Any) -> Optional[Dict[str, Any]]:
    """Normalize a Jira issuelink object into a compact display dict."""
    if not isinstance(item, dict):
        return None
    link_type = item.get("type") if isinstance(item.get("type"), dict) else {}
    if "inwardIssue" in item:
        linked = item.get("inwardIssue") or {}
        relation = link_type.get("inward") or link_type.get("name") or ""
    elif "outwardIssue" in item:
        linked = item.get("outwardIssue") or {}
        relation = link_type.get("outward") or link_type.get("name") or ""
    else:
        return None
    if not isinstance(linked, dict):
        return None
    fields = linked.get("fields") if isinstance(linked.get("fields"), dict) else {}
    status = fields.get("status")
    status_name = status.get("name") if isinstance(status, dict) else (status or "")
    key = linked.get("key") or ""
    return {
        "type": link_type.get("name") or "",
        "relation": relation,
        "key": key,
        "summary": fields.get("summary") or "",
        "status": status_name or "",
        "url": _browse_url_from_linked_issue(linked),
    }


def _is_issuelink_object(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if "type" not in item:
        return False
    return "inwardIssue" in item or "outwardIssue" in item


def decode_field_value(schema: Optional[Dict[str, Any]], raw: Any) -> Any:
    """Decode a Jira API field value into a human-friendly display value."""
    if raw is None:
        return None

    schema = schema or {}
    field_type = schema.get("type")
    items = schema.get("items")
    system = schema.get("system")

    if field_type in ("string", "date", "datetime") or field_type in (None, "any"):
        if isinstance(raw, dict) and "content" in raw:
            return adf_to_text(raw)
        if field_type in (None, "any") and isinstance(raw, dict):
            if "value" in raw:
                return raw.get("value")
            if "name" in raw:
                return raw.get("name")
            if "displayName" in raw:
                return raw.get("displayName")
            if "key" in raw:
                return raw.get("key")
        return raw

    if field_type == "number":
        return raw

    if field_type == "option":
        if isinstance(raw, dict):
            return raw.get("value") if raw.get("value") is not None else raw
        return raw

    if field_type == "user":
        if isinstance(raw, dict):
            return raw.get("displayName") or raw.get("emailAddress") or raw.get("accountId") or ""
        return raw

    if field_type == "priority" or system == "priority":
        if isinstance(raw, dict):
            return raw.get("name") or ""
        return raw

    if field_type == "issuetype" or system == "issuetype":
        if isinstance(raw, dict):
            return raw.get("name") or ""
        return raw

    if field_type == "status" or system == "status":
        if isinstance(raw, dict):
            return raw.get("name") or ""
        return raw

    if field_type == "project" or system == "project":
        if isinstance(raw, dict):
            return raw.get("key") or raw.get("name") or ""
        return raw

    if field_type == "array":
        if not isinstance(raw, list):
            raw = [raw] if raw is not None else []
        if items == "option":
            return [
                item.get("value") if isinstance(item, dict) else item for item in raw
            ]
        if items == "string":
            return [str(item) if not isinstance(item, dict) else item for item in raw]
        if items == "component" or system == "components":
            return [
                item.get("name") if isinstance(item, dict) else item for item in raw
            ]
        if items == "user":
            out = []
            for item in raw:
                if isinstance(item, dict):
                    out.append(
                        item.get("displayName")
                        or item.get("emailAddress")
                        or item.get("accountId")
                        or ""
                    )
                else:
                    out.append(item)
            return out
        if items == "issuelinks" or system == "issuelinks":
            out = []
            for item in raw:
                decoded = _decode_issuelink(item)
                if decoded is not None:
                    out.append(decoded)
            return out
        # Generic array of objects: pick a useful label when present.
        out = []
        for item in raw:
            if _is_issuelink_object(item):
                decoded = _decode_issuelink(item)
                if decoded is not None:
                    out.append(decoded)
            elif isinstance(item, dict):
                if "value" in item:
                    out.append(item["value"])
                elif "name" in item:
                    out.append(item["name"])
                elif "displayName" in item:
                    out.append(item["displayName"])
                elif "key" in item:
                    out.append(item["key"])
                else:
                    out.append(item)
            else:
                out.append(item)
        return out

    if system == "components":
        if isinstance(raw, list):
            return [item.get("name") if isinstance(item, dict) else item for item in raw]
        if isinstance(raw, dict):
            return raw.get("name") or ""
        return raw

    if isinstance(raw, dict) and "content" in raw:
        return adf_to_text(raw)

    return raw


def encode_field_value(schema: Optional[Dict[str, Any]], value: Any) -> Any:
    """Encode a human-friendly value into the shape Jira expects for a field schema."""
    if value is None:
        return None
    if isinstance(value, (dict, list)) and schema is None:
        return value

    schema = schema or {}
    field_type = schema.get("type")
    items = schema.get("items")
    system = schema.get("system")

    if field_type in (None, "any"):
        return value

    if field_type in ("string", "date", "datetime"):
        # Jira Cloud API v3 multiline custom fields require ADF, not plain string.
        if (
            field_type == "string"
            and isinstance(value, str)
            and str(schema.get("custom") or "").endswith(":textarea")
        ):
            return text_to_adf_doc(value)
        return value if not isinstance(value, (dict, list)) else value

    if field_type == "number":
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str) and value.strip():
            if "." in value:
                return float(value)
            return int(value)
        return value

    if field_type == "option":
        if isinstance(value, dict):
            return value
        return {"value": str(value)}

    if field_type == "user":
        if isinstance(value, dict):
            return value
        return {"accountId": str(value)}

    if field_type == "priority" or system == "priority":
        if isinstance(value, dict):
            return value
        return {"name": str(value)}

    if field_type == "issuetype" or system == "issuetype":
        if isinstance(value, dict):
            return value
        return {"name": str(value)}

    if field_type == "project" or system == "project":
        if isinstance(value, dict):
            return value
        return {"key": str(value)}

    if field_type == "array":
        if items == "option":
            if isinstance(value, str):
                return [{"value": value}]
            if isinstance(value, list):
                out = []
                for item in value:
                    if isinstance(item, dict):
                        out.append(item)
                    else:
                        out.append({"value": str(item)})
                return out
        if items == "string":
            if isinstance(value, str):
                return [value]
            if isinstance(value, list):
                return [str(v) if not isinstance(v, dict) else v for v in value]
        if items == "component" or system == "components":
            if isinstance(value, str):
                return [{"name": value}]
            if isinstance(value, list):
                out = []
                for item in value:
                    if isinstance(item, dict):
                        out.append(item)
                    else:
                        out.append({"name": str(item)})
                return out
        if items == "user":
            if isinstance(value, str):
                return [{"accountId": value}]
            if isinstance(value, list):
                out = []
                for item in value:
                    if isinstance(item, dict):
                        out.append(item)
                    else:
                        out.append({"accountId": str(item)})
                return out
        if isinstance(value, list):
            return value
        return [value]

    # Component system field sometimes reported without array items detail
    if system == "components":
        if isinstance(value, str):
            return [{"name": value}]
        if isinstance(value, list):
            return [
                item if isinstance(item, dict) else {"name": str(item)} for item in value
            ]

    return value


def update_field(
    client: JiraClient,
    fields_mgr: FieldCacheManager,
    issue_key: str,
    field: str,
    value: Any,
) -> Dict[str, Any]:
    """Update any issue field by display name or customfield id, encoding via schema."""
    meta = fields_mgr.resolve_field(field)
    if not meta:
        raise ValueError(f"Unknown field '{field}'. Run 'jflow cache sync' and check the name.")
    field_id = meta["id"]
    encoded = encode_field_value(meta.get("schema"), value)
    payload = {"fields": {field_id: encoded}}
    client.put(f"/rest/api/3/issue/{issue_key}", payload=payload)
    return {
        "key": issue_key,
        "field": meta.get("name") or field,
        "field_id": field_id,
        "value": encoded,
        "status": "Field Updated",
    }


def update_summary(client: JiraClient, issue_key: str, summary: str) -> Dict[str, Any]:
    """Replaces the issue summary (single-line; newlines collapsed to spaces)."""
    cleaned = collapse_to_single_line(summary)
    if not cleaned:
        raise ValueError("Summary cannot be empty.")
    payload = {"fields": {"summary": cleaned}}
    client.put(f"/rest/api/3/issue/{issue_key}", payload=payload)
    return {"key": issue_key, "summary": cleaned, "status": "Summary Updated"}


def update_description(
    client: JiraClient, issue_key: str, description: Optional[str]
) -> Dict[str, Any]:
    """Replaces or clears the issue description. Newlines become ADF paragraphs."""
    if description is None or description == "":
        desc_val = None
    else:
        desc_val = text_to_adf_doc(description)
    payload = {"fields": {"description": desc_val}}
    client.put(f"/rest/api/3/issue/{issue_key}", payload=payload)
    return {
        "key": issue_key,
        "description_cleared": desc_val is None,
        "status": "Description Updated",
    }


def update_due_date(client: JiraClient, issue_key: str, due_date: Optional[str]) -> Dict[str, Any]:
    """Sets or clears the due date on an issue (Format: YYYY-MM-DD or None)."""
    payload = {"fields": {"duedate": due_date}}
    client.put(f"/rest/api/3/issue/{issue_key}", payload=payload)
    return {"key": issue_key, "duedate": due_date, "status": "Due Date Updated"}


def update_parent(client: JiraClient, issue_key: str, parent_key: Optional[str]) -> Dict[str, Any]:
    """Sets or clears the parent issue key (e.g., Epic or Parent Issue)."""
    parent_val = {"key": parent_key} if parent_key else None
    payload = {"fields": {"parent": parent_val}}
    client.put(f"/rest/api/3/issue/{issue_key}", payload=payload)
    return {"key": issue_key, "parent": parent_key, "status": "Parent Updated"}


def update_components(client: JiraClient, issue_key: str, components: List[str]) -> Dict[str, Any]:
    """Sets the component list for an issue."""
    payload = {"fields": {"components": [{"name": c} for c in components]}}
    client.put(f"/rest/api/3/issue/{issue_key}", payload=payload)
    return {"key": issue_key, "components": components, "status": "Components Updated"}


def update_story_points(
    client: JiraClient,
    fields_mgr: FieldCacheManager,
    issue_key: str,
    points: Optional[float],
) -> Dict[str, Any]:
    """Updates the story points estimate using dynamic custom field resolution."""
    field_id = (
        fields_mgr.resolve_field_id("Story Points")
        or fields_mgr.resolve_field_id("Story point estimate")
        or "customfield_10016"
    )
    payload = {"fields": {field_id: points}}
    client.put(f"/rest/api/3/issue/{issue_key}", payload=payload)
    return {"key": issue_key, "story_points": points, "field_id": field_id, "status": "Story Points Updated"}


def _resolve_pullrequest_field(
    fields_mgr: FieldCacheManager,
) -> Dict[str, Any]:
    """Resolve Git Pull Request field by display name from the field cache."""
    meta = fields_mgr.resolve_field("Git Pull Request")
    if meta:
        return meta
    raise ValueError(
        "Could not resolve Git Pull Request field. "
        "Run 'jflow cache sync' and confirm the field name in 'jflow cache fields'."
    )


def _pullrequest_value_as_text(raw: Any) -> str:
    """Normalize a Git Pull Request field value to plain text."""
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        # ADF-ish or wrapped value — flatten to string best-effort.
        if "content" in raw:
            from jflow.core.adf import adf_to_text

            try:
                return adf_to_text(raw) or ""
            except Exception:
                return str(raw)
        if "value" in raw:
            return str(raw["value"])
    return str(raw)


def update_pull_request(
    client: JiraClient,
    fields_mgr: FieldCacheManager,
    issue_key: str,
    text: Optional[str] = None,
    *,
    overwrite: bool = False,
    clear: bool = False,
) -> Dict[str, Any]:
    """Update the Git Pull Request text field (append by default)."""
    if overwrite and clear:
        raise ValueError("Use only one of --overwrite or --clear.")
    if clear and text is not None and text != "":
        raise ValueError("Pass text or --clear, not both.")
    if clear:
        new_value: Optional[str] = None
        mode = "cleared"
    else:
        if text is None or text == "":
            raise ValueError("Pull request text is required (or pass --clear).")
        meta_preview = _resolve_pullrequest_field(fields_mgr)
        field_id = meta_preview["id"]
        if overwrite:
            new_value = text
            mode = "overwritten"
        else:
            existing = client.get(
                f"/rest/api/3/issue/{issue_key}",
                params={"fields": field_id},
            )
            current_raw = (existing.get("fields") or {}).get(field_id)
            current = _pullrequest_value_as_text(current_raw).rstrip()
            new_value = f"{current}\n{text}" if current else text
            mode = "appended"

    meta = _resolve_pullrequest_field(fields_mgr)
    field_id = meta["id"]
    api_value = encode_field_value(meta.get("schema"), new_value)
    payload = {"fields": {field_id: api_value}}
    client.put(f"/rest/api/3/issue/{issue_key}", payload=payload)
    return {
        "key": issue_key,
        "field": meta.get("name") or "Git Pull Request",
        "field_id": field_id,
        "value": new_value,
        "mode": mode,
        "status": "Pull Request Updated",
    }


def set_blocked(
    client: JiraClient,
    fields_mgr: FieldCacheManager,
    issue_key: str,
    blocked: bool,
) -> Dict[str, Any]:
    """Set the issue Blocked field (prefer exact name Blocked; else Flagged)."""
    # Prefer "Blocked" (e.g. select True/False) over Atlassian "Flagged"/Impediment.
    meta = None
    for name in ("Blocked", "Flagged"):
        meta = fields_mgr.resolve_field(name)
        if meta:
            break
    if not meta:
        raise ValueError(
            "Could not resolve Blocked/Flagged field. "
            "Run 'jflow cache sync' and confirm the field name in 'jflow cache fields'."
        )

    field_id = meta["id"]
    schema = meta.get("schema") or {}
    field_type = schema.get("type")
    items = schema.get("items")

    if field_type == "option":
        # Site-specific Blocked select fields often use True/False options.
        encoded = encode_field_value(schema, "True" if blocked else "False")
    elif field_type == "array" and items == "option":
        # Classic Jira Flagged multicheckbox.
        encoded = encode_field_value(schema, "Impediment") if blocked else []
    elif blocked:
        encoded = encode_field_value(schema, "Impediment")
    elif field_type == "array":
        encoded = []
    else:
        encoded = None

    payload = {"fields": {field_id: encoded}}
    client.put(f"/rest/api/3/issue/{issue_key}", payload=payload)
    return {
        "key": issue_key,
        "blocked": blocked,
        "field": meta.get("name") or field_id,
        "field_id": field_id,
        "status": "Blocked Status Updated",
    }
