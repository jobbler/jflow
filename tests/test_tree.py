# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
"""Issue hierarchy tree: jflow tree KEY (parent ascent, children, epic link fallback)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
from unittest.mock import MagicMock, patch
from jflow.config.models import AppConfig, JiraCredentials, UserConfig

from typer.testing import CliRunner

from jflow.core.actions.tree import build_tree, fetch_family_status
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager
from jflow.core.formatter import format_output
from jflow.interfaces.cli import app

BASE_FIELDS = "issuetype,summary,status,parent"


def _issue(key, summary, itype="Task", status="To Do", parent=None):
    f = {
        "summary": summary,
        "issuetype": {"name": itype},
        "status": {"name": status},
    }
    if parent:
        f["parent"] = {"key": parent}
    return {"key": key, "fields": f}


def _search_result(*issues):
    return {"issues": list(issues), "nextPageToken": None, "total": len(issues)}


def _client(issues_by_key, children_by_jql=None):
    """MagicMock routing client.get by issue key and client.post by JQL substring."""
    client = MagicMock(spec=JiraClient)
    client.get.side_effect = lambda path, params=None: issues_by_key[
        path.rsplit("/", 1)[-1]
    ]
    routes = children_by_jql or {}

    def post(path, payload):
        for needle, result in routes.items():
            if needle in payload.get("jql", ""):
                return result
        return _search_result()

    client.post.side_effect = post
    return client


# --- 1. parent ascent: PROJ-2 has parent PROJ-1; PROJ-1 has none ---
client = _client(
    {
        "PROJ-1": _issue("PROJ-1", "Root epic", itype="Epic", status="Done"),
        "PROJ-2": _issue("PROJ-2", "Child story", parent="PROJ-1"),
        "PROJ-3": _issue("PROJ-3", "Other story", parent="PROJ-1"),
        "PROJ-4": _issue("PROJ-4", "Grandchild", parent="PROJ-2"),
    },
    {
        'parent = "PROJ-1"': _search_result(
            _issue("PROJ-2", "Child story", parent="PROJ-1"),
            _issue("PROJ-3", "Other story", parent="PROJ-1"),
        ),
        'parent = "PROJ-2"': _search_result(_issue("PROJ-4", "Grandchild", parent="PROJ-2")),
        'parent = "PROJ-3"': _search_result(),
        'parent = "PROJ-4"': _search_result(),
    },
)
tree = build_tree(client, "PROJ-2")
assert tree["key"] == "PROJ-1", tree["key"]
child_keys = [c["key"] for c in tree["children"]]
assert child_keys == ["PROJ-2", "PROJ-3"], child_keys  # 2. siblings, sorted by key
proj2 = tree["children"][0]
assert [c["key"] for c in proj2["children"]] == ["PROJ-4"]  # 3. recursion depth 2
assert tree["type"] == "Epic" and tree["status"] == "Done"
assert tree["summary"] == "Root epic"
assert tree["_tree"] is True
for c in tree["children"]:
    assert "_tree" not in c and "children" in c

# --- 3. text connectors ---
text = format_output(tree, "text")
lines = text.strip().splitlines()
assert lines[0] == "PROJ-1 Root epic [Done]", lines[0]
assert "├── PROJ-2 Child story [To Do]" in lines
assert "│   └── PROJ-4 Grandchild [To Do]" in lines
assert "└── PROJ-3 Other story [To Do]" in lines

# --- 6. json: nested dict, no _tree key ---
parsed = json.loads(format_output(tree, "json"))
assert parsed["key"] == "PROJ-1"
assert [c["key"] for c in parsed["children"]] == ["PROJ-2", "PROJ-3"]
assert [c["key"] for c in parsed["children"][0]["children"]] == ["PROJ-4"]
assert "_tree" not in parsed
assert "_tree" not in parsed["children"][0]

# --- 7. markdown: fenced code block with connectors ---
md = format_output(tree, "markdown")
assert md.strip().startswith("```") and md.strip().endswith("```")
assert "└── PROJ-3 Other story" in md
assert "├── PROJ-2 Child story" in md

# --- 4. epic-link fallback ---
epic = _issue("EPIC-1", "Epic without parent link", itype="Epic", status="In Progress")
child_of_epic = _issue("STORY-9", "Epic child", parent="EPIC-1")
client = _client({"EPIC-1": epic}, {})
client.post.side_effect = lambda path, payload: (
    _search_result()
    if 'parent = "EPIC-1"' in payload["jql"]
    else _search_result(child_of_epic)
)
with patch("jflow.core.actions.tree.FieldCacheManager") as mgr_cls:
    mgr = MagicMock(spec=FieldCacheManager)
    mgr.resolve_field_id.return_value = "customfield_10014"
    mgr_cls.return_value = mgr
    tree = build_tree(client, "EPIC-1")
mgr.resolve_field_id.assert_called_once_with("Epic Link")
assert [c["key"] for c in tree["children"]] == ["STORY-9"]
assert tree["_tree"] is True

# --- epic-link fallback skipped when field unresolvable (leaf epic, no error) ---
client = _client({"EPIC-1": epic}, {'parent = "EPIC-1"': _search_result()})
with patch("jflow.core.actions.tree.FieldCacheManager") as mgr_cls:
    mgr = MagicMock(spec=FieldCacheManager)
    mgr.resolve_field_id.return_value = None
    mgr.load_cache.return_value = {"by_id": {}}
    mgr_cls.return_value = mgr
    tree = build_tree(client, "EPIC-1")
assert tree["children"] == []

# --- 5. cycle guard: PROJ-1 <-> PROJ-2 ---
client = _client(
    {
        "PROJ-1": _issue("PROJ-1", "One", parent="PROJ-2"),
        "PROJ-2": _issue("PROJ-2", "Two", parent="PROJ-1"),
    },
    {'parent = "PROJ-1"': _search_result(), 'parent = "PROJ-2"': _search_result()},
)
tree = build_tree(client, "PROJ-1")
assert tree["key"] == "PROJ-1"
assert tree["children"] == []

# --- extra fields: built-in alias resolved without cache ---
client = _client(
    {"PROJ-9": _issue("PROJ-9", "Solo")},
    {'parent = "PROJ-9"': _search_result()},
)
client.get.side_effect = lambda path, params=None: {
    "key": "PROJ-9",
    "fields": {
        "summary": "Solo",
        "issuetype": {"name": "Task"},
        "status": {"name": "To Do"},
        "priority": {"name": "High"},
    },
}
tree = build_tree(client, "PROJ-9", fields=["priority"])
assert tree["priority"] == "High", tree
text = format_output(tree, "text")
assert "| priority: High" in text, text

# --- unknown extra field raises ---
client = _client({"PROJ-9": _issue("PROJ-9", "Solo")}, {})
with patch("jflow.core.actions.tree.FieldCacheManager") as mgr_cls:
    mgr = MagicMock(spec=FieldCacheManager)
    mgr.resolve_field.return_value = None
    mgr_cls.return_value = mgr
    try:
        build_tree(client, "PROJ-9", fields=["bogus"])
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "bogus" in str(exc)

# --- duplicate child on current path dropped ---
client = _client(
    {
        "PROJ-1": _issue("PROJ-1", "Root"),
        "PROJ-2": _issue("PROJ-2", "Loop child", parent="PROJ-1"),
    },
    {
        'parent = "PROJ-1"': _search_result(_issue("PROJ-2", "Loop child", parent="PROJ-1")),
        'parent = "PROJ-2"': _search_result(_issue("PROJ-1", "Root", parent="PROJ-2")),
    },
)
tree = build_tree(client, "PROJ-1")
assert [c["key"] for c in tree["children"]] == ["PROJ-2"]
assert tree["children"][0]["children"] == []  # PROJ-1 already on path, dropped

# --- 8. fetch_family_status: two keys, one POST call ---
client = MagicMock(spec=JiraClient)
client.post.return_value = {
    "issues": [
        {"key": "A-1", "fields": {"status": {"name": "Done"}, "parent": None, "issuelinks": [], "issuetype": {"name": "Task"}}},
        {"key": "A-2", "fields": {"status": {"name": "To Do"}, "parent": {"key": "A-1"}, "issuelinks": [{"id": "1"}], "issuetype": {"name": "Story"}}},
    ],
    "nextPageToken": None,
}
fam = fetch_family_status(client, ["A-1", "A-2", "A-1"])
assert client.post.call_count == 1
payload = client.post.call_args.args[1]
assert payload["jql"] == 'key IN ("A-1","A-2")'
assert set(payload["fields"]) == {"status", "parent", "issuelinks", "issuetype"}
assert fam["A-1"]["status"]["name"] == "Done"
assert fam["A-2"]["parent"]["key"] == "A-1"
assert fam["A-2"]["issuelinks"] == [{"id": "1"}]
assert fam["A-2"]["issuetype"]["name"] == "Story"

# --- CLI wiring: jflow tree via CliRunner ---
runner = CliRunner()
def _config():
    return AppConfig(
        user=UserConfig(
            jira=JiraCredentials(
                domain="x.atlassian.net", email="a@b.com", api_token="t"
            ),
        )
    )





def _issue_cli(key, summary, parent=None, itype="Task"):
    f = {"summary": summary, "issuetype": {"name": itype}, "status": {"name": "To Do"}}
    if parent:
        f["parent"] = {"key": parent}
    return {"key": key, "fields": f}


issues = {
    "PROJ-1": _issue_cli("PROJ-1", "Root", itype="Epic"),
    "PROJ-2": _issue_cli("PROJ-2", "Mid", parent="PROJ-1"),
    "PROJ-3": _issue_cli("PROJ-3", "Side", parent="PROJ-1"),
    "PROJ-4": _issue_cli("PROJ-4", "Leaf", parent="PROJ-2"),
}
routes = {
    'parent = "PROJ-1"': _search_result(issues["PROJ-2"], issues["PROJ-3"]),
    'parent = "PROJ-2"': _search_result(issues["PROJ-4"]),
    'parent = "PROJ-3"': _search_result(),
    'parent = "PROJ-4"': _search_result(),
}
fake_client = MagicMock(spec=JiraClient)
fake_client.get.side_effect = lambda path, params=None: issues[path.rsplit("/", 1)[-1]]
fake_client.post.side_effect = lambda path, payload: next(
    (r for needle, r in routes.items() if needle in payload.get("jql", "")),
    _search_result(),
)
with patch("jflow.interfaces.cli._load_cfg") as load_cfg, patch(
    "jflow.interfaces.cli.JiraClient"
) as jc:
    load_cfg.return_value = _config()
    jc.from_settings.return_value = fake_client
    result = runner.invoke(app, ["tree", "PROJ-2"])
assert result.exit_code == 0, result.output
out = result.output.strip()
assert out.startswith("```") and out.endswith("```")
out = out[3:-3].strip("\n")
assert out.startswith("PROJ-1 Root [To Do]"), out
assert "├── PROJ-2 Mid [To Do]" in out
assert "│   └── PROJ-4 Leaf [To Do]" in out
assert "└── PROJ-3 Side [To Do]" in out

with patch("jflow.interfaces.cli._load_cfg") as load_cfg, patch(
    "jflow.interfaces.cli.JiraClient"
) as jc:
    load_cfg.return_value = _config()
    jc.from_settings.return_value = fake_client
    result = runner.invoke(app, ["--format", "json", "tree", "PROJ-2"])

assert result.exit_code == 0, result.output
parsed = json.loads(result.output)
assert parsed["key"] == "PROJ-1"
assert [c["key"] for c in parsed["children"]] == ["PROJ-2", "PROJ-3"]
assert "_tree" not in parsed

# --- 23. blocked annotation: native flag on the epic blocks the subtree ---
def _issue_b(key, summary, itype="Task", status="To Do", parent=None, native=False):
    f = {"summary": summary, "issuetype": {"name": itype}, "status": {"name": status}}
    if parent:
        f["parent"] = {"key": parent}
    if native:
        f["customfield_10021"] = True
    return {"key": key, "fields": f}


issues_b = {
    "EPIC-9": _issue_b("EPIC-9", "Blocked epic", itype="Epic", status="In Progress", native=True),
    "STORY-1": _issue_b("STORY-1", "Story under epic", status="In Progress", parent="EPIC-9"),
    "STORY-2": _issue_b("STORY-2", "Done story", status="Done", parent="EPIC-9"),
}
routes_b = {
    'parent = "EPIC-9"': _search_result(issues_b["STORY-1"], issues_b["STORY-2"]),
    'parent = "STORY-1"': _search_result(),
    'parent = "STORY-2"': _search_result(),
}
client_b = MagicMock(spec=JiraClient)
client_b.get.side_effect = lambda path, params=None: issues_b[path.rsplit("/", 1)[-1]]
def _post_b(path, payload):
    jql = payload.get("jql", "")
    if "key IN" in jql:
        # blocked-payload refetch: echo full payloads for requested keys
        wanted = [k.strip('" ') for k in jql[jql.index("(") + 1:jql.rindex(")")].split(",")]
        return _search_result(*[issues_b[k] for k in wanted if k in issues_b])
    for needle, result in routes_b.items():
        if needle in jql:
            return result
    return _search_result()


client_b.post.side_effect = _post_b
with patch("jflow.core.actions.tree.FieldCacheManager") as mgr_cls:
    mgr = MagicMock(spec=FieldCacheManager)
    mgr.resolve_field.side_effect = lambda name: (
        {"id": "customfield_10021", "name": name}
        if name in ("Blocked", "Flagged") else None
    )
    mgr_cls.return_value = mgr
    tree = build_tree(client_b, "EPIC-9")

assert tree["blocked"] == "yes", tree
assert tree["status"] == "In Progress (blocked)", tree["status"]
story1, story2 = tree["children"]
assert story1["blocked"] == "yes" and story1["status"] == "In Progress (blocked)"
assert story2["blocked"] == "no" and story2["status"] == "Done", story2

# text render: suffix only, no `| blocked:` extra
text_b = format_output(tree, "text")
assert "EPIC-9 Blocked epic [In Progress (blocked)]" in text_b, text_b
assert "blocked:" not in text_b, text_b

# json: blocked key present, no _-prefixed leaks
parsed_b = json.loads(format_output(tree, "json"))
assert parsed_b["blocked"] == "yes"
assert parsed_b["children"][0]["blocked"] == "yes"
assert parsed_b["children"][1]["blocked"] == "no"
assert "_tree" not in parsed_b

print("✅ Tree tests passed successfully!")
