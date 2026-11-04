# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
"""Configurable sorting: defaults.sort_* keys, --sort flags, JQL and client-side."""
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from jflow.config.models import AppConfig, Defaults, JiraCredentials, UserConfig
from jflow.core.actions.search import (
    apply_sort,
    jql_has_order_by,
    list_my_issues,
    parse_sort_terms,
    search_issues,
)
from jflow.core.actions.sprint import get_board_sprints, list_boards, sort_records
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager
from jflow.interfaces.cli import app


def _config(sort_issues=None, sort_boards=None):
    return AppConfig(
        user=UserConfig(
            jira=JiraCredentials(
                domain="x.atlassian.net", email="a@b.com", api_token="t"
            ),
            defaults=Defaults(sort_issues=sort_issues, sort_boards=sort_boards),
        )
    )


def _client():
    client = MagicMock(spec=JiraClient)
    client.post.return_value = {"issues": []}
    client.get.return_value = {"values": [], "isLast": True}
    return client


def _fields_mgr():
    mgr = MagicMock(spec=FieldCacheManager)
    mgr.resolve_field_id.side_effect = lambda name: (
        "customfield_10016" if name == "Story Points" else None
    )
    return mgr


# --- parse_sort_terms ---
assert parse_sort_terms(None) is None
assert parse_sort_terms([""]) is None
assert parse_sort_terms([",", " "]) is None
assert parse_sort_terms(["key,-updated", " priority "]) == ["key", "-updated", "priority"]

# --- jql_has_order_by ---
assert jql_has_order_by("project = X ORDER BY key")
assert not jql_has_order_by("project = X")
assert not jql_has_order_by('summary ~ "ORDER BY foo"')
assert jql_has_order_by('summary ~ "ORDER BY foo" ORDER BY created DESC')

# --- (a) append on plain JQL ---
assert apply_sort("project = X", ["key"]) == "project = X ORDER BY key ASC"

# --- (b) replace existing ORDER BY ---
result = apply_sort("project = X ORDER BY priority DESC", ["-updated"])
assert result == "project = X ORDER BY updated DESC"
assert result.count("ORDER BY ") == 1

# --- (c) quoted ORDER BY survives ---
result = apply_sort('summary ~ "ORDER BY foo" ORDER BY created DESC', ["key"])
assert 'summary ~ "ORDER BY foo"' in result
assert result.endswith("ORDER BY key ASC")
prefix = result[: result.rfind("ORDER BY")]
assert not jql_has_order_by(prefix)  # the only unquoted ORDER BY is the new clause

# --- (d) descending prefix ---
assert apply_sort("project = X", ["-updated"]).endswith("updated DESC")
assert result.count("ORDER BY key ASC") == 1  # quoted text is not a clause
# --- (e) alias mapping ---
assert apply_sort("project = X", ["type"]).endswith("issuetype ASC")
assert apply_sort("project = X", ["due"]).endswith("duedate ASC")

# --- custom field via cache ---
assert apply_sort("project = X", ["Story Points"], _fields_mgr()).endswith(
    "customfield_10016 ASC"
)

# --- (j) unknown field raises ---
try:
    apply_sort("project = X", ["bogus"], None)
    raise AssertionError("expected ValueError")
except ValueError as exc:
    assert "bogus" in str(exc)

# --- (f) presets: built-in default applied; config default overrides ---
client = _client()
list_my_issues(client, filter_name="open")
jql = client.post.call_args.args[1]["jql"]
assert jql.endswith("ORDER BY updated DESC")
assert jql.count("ORDER BY ") == 1
assert "statusCategory != Done" in jql

client = _client()
list_my_issues(client, filter_name="open", config=_config(sort_issues=["assignee"]))
jql = client.post.call_args.args[1]["jql"]
assert jql.endswith("ORDER BY assignee ASC")

# --- (g) JQL with its own ORDER BY passes through; --sort replaces ---
alias_jql = "updated >= -7d ORDER BY created DESC"
client = _client()
search_issues(client, jql=alias_jql, config=_config())
assert client.post.call_args.args[1]["jql"] == alias_jql

client = _client()
search_issues(client, jql=alias_jql, config=_config(), sort=["key"])
jql = client.post.call_args.args[1]["jql"]
assert jql.endswith("ORDER BY key ASC")
assert jql.count("ORDER BY") == 1
assert jql.count("ORDER BY ") == 1
# --- config default does not override a JQL-level ORDER BY ---
client = _client()
search_issues(client, jql=alias_jql, config=_config(sort_issues=["key"]))
assert client.post.call_args.args[1]["jql"] == alias_jql

# --- sort flag passed through list_my_issues ---
client = _client()
list_my_issues(client, filter_name="open", sort=["-priority"])
assert client.post.call_args.args[1]["jql"].endswith("priority DESC")

# --- sort_records: client-side sprints/boards ---
sprints = [
    {"id": 3, "name": "Sprint C", "startDate": "2026-03-01", "endDate": "2026-03-15"},
    {"id": 1, "name": "sprint a", "startDate": "2026-01-01", "endDate": None},
    {"id": 2, "name": "Sprint B", "startDate": "2026-02-01", "endDate": "2026-02-15"},
]
ordered = sort_records(sprints, ["start_date"], {"start_date": "startDate"})
assert [s["id"] for s in ordered] == [1, 2, 3]
assert sprints[0]["id"] == 3  # input not mutated

rev = sort_records(sprints, ["-name"])
assert [s["name"] for s in rev] == ["Sprint C", "Sprint B", "sprint a"]

none_last = sort_records(
    [{"name": "x", "endDate": None}, {"name": "y", "endDate": "2026-01-01"}],
    ["end_date"],
    {"end_date": "endDate"},
)
assert [item["name"] for item in none_last] == ["y", "x"]

by_id = sort_records([{"id": 10}, {"id": 2}], ["id"])
assert [item["id"] for item in by_id] == [2, 10]

assert sort_records(sprints, None) is sprints
assert sort_records(sprints, []) is sprints

try:
    sort_records([{"id": 1}], ["bogus"])
    raise AssertionError("expected ValueError")
except ValueError as exc:
    assert "bogus" in str(exc)

# --- multi-term stable sort: earlier terms dominate ---
multi = sort_records(
    [{"g": 1, "n": "b"}, {"g": 2, "n": "a"}, {"g": 1, "n": "a"}], ["g", "n"]
)
assert multi == [{"g": 1, "n": "a"}, {"g": 1, "n": "b"}, {"g": 2, "n": "a"}]

# --- get_board_sprints sorts with key mapping ---
client = _client()
client.get.return_value = {"values": sprints}
out = get_board_sprints(client, board_id=42, state="active", sort=["-start_date"])
assert [s["id"] for s in out] == [3, 2, 1]
client.get.assert_called_once_with(
    "/rest/agile/1.0/board/42/sprint", params={"state": "active"}
)

# --- list_boards sorts before truncation ---
boards = [
    {"id": 5, "name": "Zeta", "type": "scrum", "projectKey": "Z"},
    {"id": 3, "name": "alpha", "type": "kanban", "projectKey": "A"},
    {"id": 9, "name": "Mid", "type": "scrum", "projectKey": "M"},
]
client = _client()
client.get.side_effect = [
    {"values": boards, "isLast": False},
    {"values": [], "isLast": True},
]
out = list_boards(client, max_results=2, sort=["name"])
assert [b["name"] for b in out] == ["alpha", "Mid"]
assert client.get.call_count == 1  # page collected fully, no extra fetch

# --- defaults.sort_boards applied via CLI when --sort absent; --sort wins ---
def _run_boards(extra_args, cfg):
    runner = CliRunner()
    with patch("jflow.interfaces.cli._load_cfg") as load_cfg, patch(
        "jflow.interfaces.cli.JiraClient"
    ) as Client:
        load_cfg.return_value = cfg
        client = MagicMock(spec=JiraClient)
        client.get.return_value = {"values": list(boards), "isLast": True}
        Client.from_settings.return_value = client
        result = runner.invoke(app, ["boards", "list"] + extra_args)
        assert result.exit_code == 0, result.output
        return client, result.output


# No --sort, no defaults.sort_boards: API order preserved.
client, text = _run_boards([], _config())
assert text.index("Zeta") < text.index("alpha") < text.index("Mid")

# --sort name wins over defaults.sort_boards: sorted ascending.
client, text = _run_boards(["--sort", "name"], _config(sort_boards=["id"]))
assert text.index("alpha") < text.index("Mid") < text.index("Zeta")

# defaults.sort_boards applied when --sort absent.
client, text = _run_boards([], _config(sort_boards=["name"]))
assert text.index("alpha") < text.index("Mid") < text.index("Zeta")



# --- (h) CLI wiring: --sort on jflow list ---
def test_cli_list_sort():
    runner = CliRunner()
    cfg = _config()
    with patch("jflow.interfaces.cli._load_cfg") as load_cfg, patch(
        "jflow.interfaces.cli.JiraClient"
    ) as Client:
        load_cfg.return_value = cfg
        client = MagicMock(spec=JiraClient)
        client.post.return_value = {"issues": []}
        Client.from_settings.return_value = client
        result = runner.invoke(app, ["list", "--sort", "key,-updated"])
        assert result.exit_code == 0, result.output
        payload = client.post.call_args.args[1]
        assert payload["jql"].endswith("ORDER BY key ASC, updated DESC")


def test_cli_list_default_sort():
    runner = CliRunner()
    cfg = _config()
    with patch("jflow.interfaces.cli._load_cfg") as load_cfg, patch(
        "jflow.interfaces.cli.JiraClient"
    ) as Client:
        load_cfg.return_value = cfg
        client = MagicMock(spec=JiraClient)
        client.post.return_value = {"issues": []}
        Client.from_settings.return_value = client
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0, result.output
        payload = client.post.call_args.args[1]
        assert payload["jql"].endswith("ORDER BY updated DESC")


def test_cli_sprint_list_sort():
    runner = CliRunner()
    cfg = _config()
    with patch("jflow.interfaces.cli._load_cfg") as load_cfg, patch(
        "jflow.interfaces.cli.JiraClient"
    ) as Client, patch("jflow.interfaces.cli._resolve_board_id", return_value=42):
        load_cfg.return_value = cfg
        client = MagicMock(spec=JiraClient)
        client.get.return_value = {"values": list(sprints)}
        Client.from_settings.return_value = client
        result = runner.invoke(app, ["sprint", "list", "--sort", "start_date"])
        assert result.exit_code == 0, result.output
        client.get.assert_called_once_with(
            "/rest/agile/1.0/board/42/sprint", params={"state": "active"}
        )
        # Output is ordered by startDate (sprints[1], sprints[2], sprints[0]).
        assert (
            result.output.index("2026-01-01")
            < result.output.index("2026-02-01")
            < result.output.index("2026-03-01")
        )


test_cli_list_sort()
test_cli_list_default_sort()
test_cli_sprint_list_sort()

print("✅ Sorting tests passed successfully!")
