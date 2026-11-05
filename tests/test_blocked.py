# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
"""Computed `blocked` status (issue #9): predicate, batching, rendering, CLI."""
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jflow.config.models import AppConfig, Defaults, JiraCredentials, UserConfig
from jflow.core.actions.blocked import (
    compute_blocked,
    compute_blocked_one,
    resolve_native_blocked_id,
)
from jflow.core.actions.issue_view import get_issue
from jflow.core.actions.search import search_issues
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager
from jflow.interfaces.cli import app

runner = CliRunner()


def _status(name, category):
    return {"name": name, "statusCategory": {"key": category}}


def _issue(key, fields=None, links=None, parent=None, native=None):
    f = {
        "status": _status("In Progress", "indeterminate"),
        "issuelinks": links or [],
    }
    if parent is not None:
        f["parent"] = parent
    if native is not None:
        f["customfield_10021"] = native
    if fields:
        f.update(fields)
    return {"key": key, "fields": f}


def _blocked_by(key, category, resolution=None):
    other = {"key": key, "fields": {
        "status": _status("Whatever", category),
        "issuelinks": [],
    }}
    if resolution is not None:
        other["fields"]["resolution"] = resolution
    return {
        "type": {"inward": "is blocked by", "outward": "blocks"},
        "inwardIssue": other,
    }

def _remote(key, category, resolution=None):
    """Raw issue payload as a key-IN search would return it."""
    f = {"status": _status("Whatever", category), "issuelinks": []}
    if resolution is not None:
        f["resolution"] = resolution
    return {"key": key, "fields": f}


def _search_page(*issues):
    return {"issues": list(issues), "total": len(issues)}


def _client(search_results=None):
    client = MagicMock(spec=JiraClient)
    responses = list(search_results or [])
    client.post.side_effect = responses or [{}]
    return client


def _fields_mgr(native_id="customfield_10021"):
    mgr = MagicMock(spec=FieldCacheManager)

    def resolve(name):
        if name in ("Blocked", "Flagged") and native_id:
            return {"id": native_id, "name": name}
        return None

    mgr.resolve_field.side_effect = resolve
    return mgr


# --- 23. provenance: blocked_reasons strings ---
from jflow.core.actions.blocked import (
    compute_blocked_reasons,
    compute_blocked_reasons_one,
    format_blocked_reasons,
)

# link reason, resolved blocker
client = _client(search_results=[_search_page(_remote("B", "indeterminate"))])
r = compute_blocked_reasons(client, [_issue("A", links=[_blocked_by("B", "indeterminate")])])
assert r == {"A": ["link:B"]}, r

# unavailable link target
client = _client(search_results=[_search_page()])
r = compute_blocked_reasons(client, [_issue("A", links=[_blocked_by("GONE", "indeterminate")])])
assert r == {"A": ["link:?GONE"]}, r

# nearest blocked ancestor, all intermediates blocked
grandparent = _issue("EPIC-0", native=True, parent=None)
parent = _issue("EPIC-1", parent={"key": "EPIC-0", "fields": {}})
child = _issue("C", parent={"key": "EPIC-1", "fields": {}})
client = _client()
r = compute_blocked_reasons(
    client, [grandparent, parent, child], fields_mgr=_fields_mgr()
)
assert r == {"EPIC-0": ["native"], "EPIC-1": ["ancestor:EPIC-0"], "C": ["ancestor:EPIC-1"]}, r

# nearest blocked ancestor through an UNBLOCKED intermediate parent
grandparent2 = _issue("EPIC-G", native=True, parent=None)
parent2 = _issue("EPIC-M", parent={"key": "EPIC-G", "fields": {}})  # not blocked itself
child2 = _issue("C2", parent={"key": "EPIC-M", "fields": {}})
client = _client()
r = compute_blocked_reasons(
    client, [grandparent2, parent2, child2], fields_mgr=_fields_mgr()
)
assert r == {"EPIC-G": ["native"], "EPIC-M": ["ancestor:EPIC-G"], "C2": ["ancestor:EPIC-M"]}, r
# boolean over the full family matches
client = _client()
assert compute_blocked(
    client, [grandparent2, parent2, child2], fields_mgr=_fields_mgr()
) == {"EPIC-G": True, "EPIC-M": True, "C2": True}

# combination: link + native
client = _client()
r = compute_blocked_reasons(
    client,
    [_issue("A", links=[_blocked_by("B", "indeterminate")], native=True)],
    fields_mgr=_fields_mgr(),
)
assert r == {"A": ["link:?B", "native"]}, r

# not blocked -> empty list
client = _client(search_results=[_search_page(_remote("B", "done"))])
r = compute_blocked_reasons(client, [_issue("A", links=[_blocked_by("B", "done")])])
assert r == {"A": []}, r

# cycle: link reasons only, no ancestor reason, terminates
a = _issue("A", parent={"key": "B", "fields": {}})
b = _issue("B", parent={"key": "A", "fields": {}})
client = _client()
r = compute_blocked_reasons(client, [a, b])
assert r == {"A": [], "B": []}, r

# formatter
assert format_blocked_reasons(["link:PROJ-42"]) == "blocked by PROJ-42"
assert format_blocked_reasons(["link:?PROJ-99"]) == "blocked by PROJ-99 (unavailable)"
assert format_blocked_reasons(["ancestor:EPIC-1"]) == "ancestor EPIC-1"
assert format_blocked_reasons(["native"]) == "native flag"
assert format_blocked_reasons(["link:PROJ-42", "ancestor:EPIC-1", "native"]) == (
    "blocked by PROJ-42; ancestor EPIC-1; native flag"
)

# single-issue wrapper
client = _client()
assert compute_blocked_reasons_one(
    client, _issue("A", native=True), _fields_mgr()
) == ["native"]


# --- 1. in-progress + unresolved blocked-by link -> blocked ---
client = _client(search_results=[{"issues": [_remote("B", "indeterminate")], "total": 1}])
result = compute_blocked(client, [_issue("A", links=[_blocked_by("B", "indeterminate")])])
assert result == {"A": True}, result

# --- 2. blocked-by a done issue (statusCategory done; resolution non-null) ---
client = _client(search_results=[{"issues": [_remote("B", "done")], "total": 1}])
result = compute_blocked(
    client, [_issue("A", links=[_blocked_by("B", "done")])]
)
assert result == {"A": False}, result

client = _client(
    search_results=[
        {"issues": [_remote("B", "new", resolution={"name": "Fixed"})], "total": 1}
    ]
)
result = compute_blocked(
    client,
    [_issue("A", links=[_blocked_by("B", "new", resolution={"name": "Fixed"})])],
)
assert result == {"A": False}, result

# --- 3. blocked parent epic blocks the child; batch fetch is chunk-bounded ---
# 10 children in progress, all parented to one unfetched epic that is itself
# blocked by an unfetched issue -> exactly 1 batched search call for all refs.
epic = _issue(
    "EPIC-1",
    fields={"status": _status("In Progress", "indeterminate")},
    links=[_blocked_by("GHOST-1", "indeterminate")],
)
children = [
    _issue(f"C-{i}", parent={"key": "EPIC-1", "fields": {}})
    for i in range(10)
]
search_response = {
    "issues": [epic, _issue("GHOST-1", links=[])],
    "total": 2,
}
client = _client(search_results=[search_response])
result = compute_blocked(client, children)
assert result == {f"C-{i}": True for i in range(10)}, result
assert client.post.call_count == 1, client.post.call_count

# --- 4. native flag alone blocks; unresolvable native field is ignored ---
client = _client()
result = compute_blocked(
    client, [_issue("A", native=True)], fields_mgr=_fields_mgr()
)
assert result == {"A": True}, result

mgr_no_native = _fields_mgr(native_id=None)
assert resolve_native_blocked_id(mgr_no_native) is None
client = _client()
result = compute_blocked(
    client, [_issue("A", native=True)], fields_mgr=mgr_no_native
)
assert result == {"A": False}, result

# --- 5. done-status issue with unresolved blocked-by -> not blocked ---
client = _client()
done_issue = _issue("A", links=[_blocked_by("B", "indeterminate")])
done_issue["fields"]["status"] = _status("Done", "done")
result = compute_blocked(client, [done_issue])
assert result == {"A": False}, result

# --- 6. parent cycle A<->B both in-progress with unresolved blocked-by ---
a = _issue("A", links=[_blocked_by("B", "indeterminate")], parent={"key": "B", "fields": {}})
b = _issue("B", links=[_blocked_by("A", "indeterminate")], parent={"key": "A", "fields": {}})
client = _client()
result = compute_blocked(client, [a, b])
assert result == {"A": True, "B": True}, result

# missing blocker target (deleted / no permission) blocks and never raises
client = _client(search_results=[{"issues": [], "total": 0}])
result = compute_blocked(client, [_issue("A", links=[_blocked_by("GONE", "indeterminate")])])
assert result == {"A": True}, result

# issue without fields maps to False
client = _client()
result = compute_blocked(client, [{"key": "A"}])
assert result == {"A": False}, result

# compute_blocked_one wrapper
client = _client()
assert compute_blocked_one(
    client, _issue("A", links=[_blocked_by("B", "indeterminate")])
) is True

# --- 7. list rendering: status suffix + blocked cell; no _blocked leak ---
def _list_client(issue):
    client = MagicMock(spec=JiraClient)
    client.post.return_value = {"issues": [issue], "total": 1}
    return client


issue = _issue(
    "PROJ-1",
    links=[_blocked_by("B", "indeterminate")],
    fields={"summary": "Work", "status": _status("In Progress", "indeterminate")},
)
client = _list_client(issue)
rows = search_issues(
    client,
    jql="project = PROJ",
    list_fields=["key", "status", "blocked"],
    fields_mgr=_fields_mgr(),
)
assert rows[0]["Key"] == "PROJ-1"
assert rows[0]["Status"] == "In Progress (blocked)", rows[0]
assert rows[0]["Blocked"] == "yes", rows[0]
assert "_blocked" not in rows[0]
payload = client.post.call_args_list[0].args[1]
assert "blocked" not in payload["fields"], payload
for f in ("parent", "issuelinks", "resolution", "status", "customfield_10021"):
    assert f in payload["fields"], payload

# same issue, blocker now done -> plain status, blocked=no
issue = _issue(
    "PROJ-1",
    links=[_blocked_by("B", "done")],
    fields={"summary": "Work", "status": _status("In Progress", "indeterminate")},
)
client = MagicMock(spec=JiraClient)
client.post.side_effect = [
    _search_page(issue),
    _search_page(_remote("B", "done")),
]
rows = search_issues(
    client,
    jql="project = PROJ",
    list_fields=["key", "status", "blocked"],
    fields_mgr=_fields_mgr(),
)
assert rows[0]["Status"] == "In Progress", rows[0]
assert rows[0]["Blocked"] == "no", rows[0]

# comma-separated list_fields string (CLI --fields key,status,blocked / yaml)
client = MagicMock(spec=JiraClient)
client.post.side_effect = [
    _search_page(issue),
    _search_page(_remote("B", "done")),
]
rows = search_issues(
    client,
    jql="project = PROJ",
    list_fields=["key,status,blocked"],
    fields_mgr=_fields_mgr(),
)
assert list(rows[0].keys()) == ["Key", "Status", "Blocked"], rows[0]
assert rows[0]["Status"] == "In Progress", rows[0]
assert rows[0]["Blocked"] == "no", rows[0]

# --- 8. show: default fields include blocked; status suffixed ---
issue = _issue(
    "PROJ-1",
    links=[_blocked_by("B", "indeterminate")],
    fields={
        "summary": "Work",
        "status": _status("In Progress", "indeterminate"),
        "issuetype": {"name": "Story"},
        "assignee": None,
        "reporter": None,
        "priority": None,
        "labels": [],
        "components": [],
        "parent": None,
        "created": "",
        "updated": "",
        "description": None,
    },
)
client = MagicMock(spec=JiraClient)
client.get.return_value = issue
client.post.return_value = {}  # blocker key absent -> unresolved -> blocked
details = get_issue(client, "PROJ-1", fields_mgr=_fields_mgr())
assert details["blocked"] == "yes (blocked by B (unavailable))", details
assert details["status"] == "In Progress (blocked)", details
sent_fields = client.get.call_args.kwargs["params"]["fields"]
assert "blocked" not in sent_fields, sent_fields
assert "issuelinks" in sent_fields, sent_fields

# not blocked -> plain
issue_done_link = _issue(
    "PROJ-1",
    links=[_blocked_by("B", "done")],
    fields={"summary": "Work", "status": _status("In Progress", "indeterminate")},
)
client = MagicMock(spec=JiraClient)
client.get.return_value = issue_done_link
client.post.return_value = _search_page(_remote("B", "done"))
details = get_issue(client, "PROJ-1", fields_mgr=_fields_mgr())
assert details["blocked"] == "no", details
assert details["status"] == "In Progress", details

# custom show path with --only blocked
client = MagicMock(spec=JiraClient)
client.get.return_value = issue
client.post.return_value = {"issues": [], "total": 0}
details = get_issue(
    client, "PROJ-1", only=["blocked"], fields_mgr=_fields_mgr()
)
assert details["blocked"] == "yes (blocked by B (unavailable))", details

# show-side comma split (--only status,blocked)
client = MagicMock(spec=JiraClient)
client.get.return_value = issue
client.post.return_value = {"issues": [], "total": 0}
details = get_issue(
    client, "PROJ-1", only=["blocked,status"], fields_mgr=_fields_mgr()
)
assert details["blocked"] == "yes (blocked by B (unavailable))", details
assert details["status"] == "In Progress (blocked)", details
assert "_field_order" not in [k for k in details if k.startswith("_")]

# --- 9. CLI regression: jflow show prints output ---
config = AppConfig(
    user=UserConfig(
        jira=JiraCredentials(domain="x.atlassian.net", email="a@b.com", api_token="t"),
        defaults=Defaults(),
    )
)
with patch("jflow.interfaces.cli._load_cfg", return_value=config), \
     patch("jflow.interfaces.cli.JiraClient") as client_cls, \
     patch("jflow.core.actions.issue_view.FieldCacheManager", return_value=_fields_mgr()):
    client_obj = MagicMock(spec=JiraClient)
    client_obj.get.return_value = issue
    client_obj.post.return_value = {"issues": [], "total": 0}
    client_cls.from_settings.return_value = client_obj
    res = runner.invoke(app, ["show", "PROJ-1"])
assert res.exit_code == 0, res.output
assert res.output.strip(), "show printed nothing"

print("test_blocked: all assertions passed")
