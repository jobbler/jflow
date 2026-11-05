# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
"""Computed `blocked` state for issues (never written back to Jira).

An issue is blocked when it is in progress (statusCategory ``indeterminate``)
AND at least one of:
  - an unresolved "is blocked by" link (the linked issue is not done), or
  - any ancestor issue is itself blocked, or
  - the native Blocked/Flagged field is set to a truthy value.
"""
from typing import Any, Dict, List, Optional

from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager

BLOCKED_RELATIONS = {"is blocked by"}
_IN_PROGRESS = "indeterminate"
_DONE = "done"
_NATIVE_FIELD_NAMES = ("Blocked", "Flagged")
_CHUNK_SIZE = 50
_SEARCH_ENDPOINT = "/rest/api/3/search/jql"




def resolve_native_blocked_id(
    fields_mgr: Optional[FieldCacheManager],
) -> Optional[str]:
    """Field id of the native Blocked/Flagged field, or None when absent.

    Read-only and tolerant: a missing/unsynced cache or an error while
    resolving just disables the native clause (never raises, never warns).
    """
    if fields_mgr is None:
        return None
    for name in _NATIVE_FIELD_NAMES:
        try:
            meta = fields_mgr.resolve_field(name)
        except Exception:
            return None
        if meta:
            return meta["id"]
    return None


def fetch_blocked_payload(
    client: JiraClient, keys: List[str], native_id: Optional[str]
) -> Dict[str, dict]:
    """Fetch raw issue payloads for ``keys`` via chunked key-IN searches."""
    from jflow.core.actions.tree import _search_all

    result: Dict[str, dict] = {}
    for start in range(0, len(keys), _CHUNK_SIZE):
        chunk = keys[start:start + _CHUNK_SIZE]
        quoted = ", ".join(f'"{key}"' for key in chunk)
        jql = f"key IN ({quoted})"
        fields = ["status", "parent", "issuelinks", "resolution"]
        if native_id:
            fields.append(native_id)
        for issue in _search_all(client, jql, fields):
            result[issue.get("key")] = issue
    return result


def _link_relation(link: Dict[str, Any]) -> Optional[str]:
    """Relation phrase for a link as seen from the subject issue."""
    link_type = link.get("type") or {}
    if link.get("inwardIssue"):
        return (link_type.get("inward") or "").strip().lower()
    if link.get("outwardIssue"):
        return (link_type.get("outward") or "").strip().lower()
    return None


def _is_done(raw: Optional[dict]) -> bool:
    if not raw:
        return True
    f = raw.get("fields") or {}
    status = f.get("status") or {}
    category = ((status.get("statusCategory") or {}).get("key") or "").lower()
    if category == _DONE:
        return True
    return f.get("resolution") is not None


def _is_in_progress(raw: Optional[dict]) -> bool:
    if not raw:
        return False
    status = (raw.get("fields") or {}).get("status") or {}
    category = ((status.get("statusCategory") or {}).get("key") or "").lower()
    if category:
        return category == _IN_PROGRESS
    # Nonstandard site: fall back to the status name.
    return "progress" in (status.get("name") or "").lower()


def _referenced_keys(raw: dict, native_id: Optional[str]) -> Dict[str, bool]:
    """Referenced keys of an issue → True when they are blocking references."""
    refs: Dict[str, bool] = {}
    f = raw.get("fields") or {}
    for link in f.get("issuelinks") or []:
        if _link_relation(link) in BLOCKED_RELATIONS:
            other = link.get("inwardIssue") or link.get("outwardIssue")
            key = (other or {}).get("key")
            if key:
                refs[key] = True
    parent_key = ((f.get("parent") or {}).get("key"))
    if parent_key:
        refs.setdefault(parent_key, False)
    return refs


def compute_blocked_reasons(
    client: JiraClient,
    issues: List[dict],
    fields_mgr: Optional[FieldCacheManager] = None,
) -> Dict[str, List[str]]:
    """Compute `{key: reasons}` for exactly the passed issues.

    Reasons are stable strings (see ``blocked_reasons``). Empty list = not
    blocked. The boolean ``compute_blocked`` is derived from this walk.
    """
    native_id = resolve_native_blocked_id(fields_mgr)
    raw_by_key: Dict[str, dict] = {}
    memo: Dict[str, List[str]] = {}

    for issue in issues:
        key = issue.get("key")
        if key and key not in raw_by_key:
            raw_by_key[key] = issue

    def fetch_missing(keys: List[str]) -> None:
        missing = [k for k in dict.fromkeys(keys) if k not in raw_by_key]
        if not missing:
            return
        fetched = fetch_blocked_payload(client, missing, native_id)
        # Store everything the search returned (batched chunks may include
        # keys other rounds will need), then pad the truly-absent keys.
        for key, raw in fetched.items():
            raw_by_key[key] = raw
        for key in missing:
            if key not in raw_by_key:
                # Absent from the result (deleted / no permission): treat as
                # a present-but-empty raw entry so the fixed point terminates.
                raw_by_key[key] = {"key": key, "fields": {}}

    def reasons(key: str) -> List[str]:
        if key in memo:
            return memo[key]
        # Guard against cycles: pessimistically mark as unblocked while
        # evaluating, so a parent cycle cannot recurse forever. Cycle nodes
        # therefore report only their link/native clauses.
        memo[key] = []
        raw = raw_by_key.get(key)
        if raw is None or not raw.get("fields"):
            memo[key] = []
            return []
        if not _is_in_progress(raw):
            memo[key] = []
            return []
        f = raw.get("fields") or {}
        found: List[str] = []
        for link in f.get("issuelinks") or []:
            if _link_relation(link) not in BLOCKED_RELATIONS:
                continue
            other = link.get("inwardIssue") or link.get("outwardIssue")
            other_key = (other or {}).get("key")
            if not other_key:
                continue
            other_raw = raw_by_key.get(other_key)
            if other_raw is None or not other_raw.get("fields"):
                # Unresolvable blocker target: counts as unresolved.
                found.append(f"link:?{other_key}")
                continue
            if not _is_done(other_raw):
                found.append(f"link:{other_key}")
        # Ancestor walk: nearest blocked ancestor up the parent chain.
        # Cycle-safe via the memo (in-flight nodes read as unblocked).
        cur = (f.get("parent") or {}).get("key")
        walked: set = set()
        while cur and cur in raw_by_key and cur not in walked:
            walked.add(cur)
            cur_raw = raw_by_key[cur]
            if not cur_raw.get("fields"):
                break
            if reasons(cur):
                found.append(f"ancestor:{cur}")
                break
            cur = ((cur_raw.get("fields") or {}).get("parent") or {}).get("key")
        if native_id and f.get(native_id):
            found.append("native")
        memo[key] = found
        return found

    # Fixed point: batch-fetch every referenced key transitively.
    pending = [issue.get("key") for issue in issues if issue.get("key")]
    seen_fetch: set = set(pending)
    while True:
        to_fetch: List[str] = []
        for key in list(raw_by_key):
            raw = raw_by_key[key]
            if not raw.get("fields"):
                continue
            for ref, _ in _referenced_keys(raw, native_id).items():
                if ref not in seen_fetch:
                    to_fetch.append(ref)
        if not to_fetch:
            break
        seen_fetch.update(to_fetch)
        fetch_missing(to_fetch)

    return {
        issue.get("key"): reasons(issue.get("key")) if issue.get("key") else []
        for issue in issues
    }


def compute_blocked(
    client: JiraClient,
    issues: List[dict],
    fields_mgr: Optional[FieldCacheManager] = None,
) -> Dict[str, bool]:
    """Compute `{key: blocked}` for exactly the passed issues."""
    reasons_map = compute_blocked_reasons(client, issues, fields_mgr)
    return {key: bool(found) for key, found in reasons_map.items()}


def compute_blocked_one(
    client: JiraClient, issue: dict, fields_mgr: Optional[FieldCacheManager] = None
) -> bool:
    """Blocked state for a single issue."""
    key = issue.get("key")
    return compute_blocked(client, [issue], fields_mgr).get(key, False)


def compute_blocked_reasons_one(
    client: JiraClient, issue: dict, fields_mgr: Optional[FieldCacheManager] = None
) -> List[str]:
    """Blocked reasons for a single issue (empty list = not blocked)."""
    key = issue.get("key")
    return compute_blocked_reasons(client, [issue], fields_mgr).get(key, [])


def format_blocked_reasons(reasons: List[str]) -> str:
    """Human-readable summary: `blocked by PROJ-42; ancestor EPIC-1; native flag`."""
    parts: List[str] = []
    for reason in reasons:
        if reason.startswith("link:?"):
            parts.append(f"blocked by {reason[6:]} (unavailable)")
        elif reason.startswith("link:"):
            parts.append(f"blocked by {reason[5:]}")
        elif reason.startswith("ancestor:"):
            parts.append(f"ancestor {reason[9:]}")
        elif reason == "native":
            parts.append("native flag")
        else:
            parts.append(reason)
    return "; ".join(parts)
