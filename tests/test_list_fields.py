# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
"""Configurable `list` / `query` columns (defaults.list_fields and --fields)."""
import warnings
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from jflow.config.models import AppConfig, Defaults, JiraCredentials, UserConfig
from jflow.core.actions.issue_view import get_issue
from jflow.core.actions.search import list_my_issues, search_issues
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager
from jflow.core.formatter import format_output
from jflow.interfaces.cli import app


def _config(list_fields=None, board=None):
    return AppConfig(
        user=UserConfig(
            jira=JiraCredentials(
                domain="x.atlassian.net", email="a@b.com", api_token="t"
            ),
            defaults=Defaults(list_fields=list_fields, board=board),
        )
    )


def _client():
    client = MagicMock(spec=JiraClient)
    client.post.return_value = {
        "issues": [
            {
                "key": "PROJ-7",
                "fields": {
                    "summary": "Ship it",
                    "status": {"name": "In Progress"},
                    "issuetype": {"name": "Story"},
                    "assignee": {"displayName": "Ada"},
                    "updated": "2026-10-01T12:00:00.000+0000",
                    "customfield_10016": 5,
                    "components": [{"name": "API"}],
                },
            }
        ]
    }
    return client


def _fields_mgr():
    mgr = MagicMock(spec=FieldCacheManager)
    mgr.resolve_field.side_effect = lambda name: (
        {
            "id": "customfield_10016",
            "name": "Story Points",
            "schema": {"type": "number"},
        }
        if name in ("Story Points", "customfield_10016")
        else (
            {
                "id": "customfield_10020",
                "name": "Sprint",
                "schema": {"type": "array", "items": "string"},
            }
            if name in ("Sprint", "customfield_10020")
            else None
        )
    )
    return mgr


ACTIVE_SPRINTS = {"values": [{"id": 7, "name": "Sprint 7", "state": "active"}]}


# --- defaults model ---
assert Defaults(list_fields=["summary", "Story Points"]).list_fields == [
    "summary",
    "Story Points",
]
assert Defaults().list_fields is None

# --- explicit fields define columns and order ---
client = _client()
rows = search_issues(
    client,
    jql="project = PROJ",
    list_fields=["key", "Status", "Story Points", "Updated"],
    fields_mgr=_fields_mgr(),
)
assert list(rows[0].keys()) == ["Key", "Status", "Story Points", "Updated"]
assert rows[0]["Key"] == "PROJ-7"
assert rows[0]["Status"] == "In Progress"
assert rows[0]["Story Points"] == 5
assert rows[0]["Updated"] == "2026-10-01T12:00:00.000+0000"
payload = client.post.call_args.args[1]
assert payload["fields"] == ["status", "customfield_10016", "updated"]
assert payload["jql"] == "project = PROJ"

# --- Key is only shown when requested ---
client = _client()
rows = search_issues(
    client, jql="project = PROJ", list_fields=["Summary"], fields_mgr=_fields_mgr()
)
assert list(rows[0].keys()) == ["Summary"]
assert client.post.call_args.args[1]["fields"] == ["summary"]

# --- a Key-only list does not request any fields from the search API ---
client = _client()
rows = search_issues(
    client, jql="project = PROJ", list_fields=["key"], fields_mgr=_fields_mgr()
)
assert rows[0] == {"Key": "PROJ-7"}
assert "fields" not in client.post.call_args.args[1]

# --- system aliases resolve to display labels and friendly values ---
client = _client()
rows = search_issues(
    client,
    jql="project = PROJ",
    list_fields=["Type", "Assignee", "Components"],
    fields_mgr=_fields_mgr(),
)
assert rows[0] == {
    "Type": "Story",
    "Assignee": "Ada",
    "Components": ["API"],
}

# --- unknown field is skipped with a warning ---
client = _client()
warnings_seen = []
rows = search_issues(
    client,
    jql="project = PROJ",
    list_fields=["Summary", "Not A Field"],
    fields_mgr=_fields_mgr(),
    on_warning=warnings_seen.append,
)
assert list(rows[0].keys()) == ["Summary"]
assert len(warnings_seen) == 1
assert "Not A Field" in warnings_seen[0]
assert client.post.call_args.args[1]["fields"] == ["summary"]

# --- without a callback the skip still emits a warning ---
client = _client()
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    search_issues(
        client,
        jql="project = PROJ",
        list_fields=["Summary", "Nope"],
        fields_mgr=_fields_mgr(),
    )
assert any("Nope" in str(item.message) for item in caught)

# --- all-unknown configuration fails clearly ---
client = _client()
try:
    search_issues(
        client,
        jql="project = PROJ",
        list_fields=["Nope"],
        fields_mgr=_fields_mgr(),
        on_warning=lambda _message: None,
    )
    raise AssertionError("expected ValueError")
except ValueError as exc:
    assert "No valid list fields" in str(exc)

# --- config supplies defaults; explicit list_fields overrides it ---
client = _client()
rows = search_issues(
    client, jql="project = PROJ", config=_config(["Status"]), fields_mgr=_fields_mgr()
)
assert list(rows[0].keys()) == ["Status"]
client = _client()
rows = search_issues(
    client,
    jql="project = PROJ",
    config=_config(["Status"]),
    list_fields=["Summary"],
    fields_mgr=_fields_mgr(),
)
assert list(rows[0].keys()) == ["Summary"]

# --- list_my_issues passes fields through ---
client = _client()
rows = list_my_issues(
    client, jql="project = PROJ", list_fields=["Summary"], fields_mgr=_fields_mgr()
)
assert list(rows[0].keys()) == ["Summary"]
assert client.post.call_args.args[1]["jql"] == "project = PROJ"

# --- custom columns render in human formats ---
client = _client()
rows = search_issues(
    client,
    jql="project = PROJ",
    list_fields=["key", "Summary", "Story Points", "Updated"],
    fields_mgr=_fields_mgr(),
)
markdown = format_output(rows, format_type="markdown")
assert "**PROJ-7**" in markdown
assert "Story Points: 5" in markdown
assert "2026-10-01T12:00:00.000+0000" not in markdown
assert "Updated:" in markdown and "ago" in markdown
text = format_output(rows, format_type="text")
assert "Story Points" in text
assert "2026-10-01T12:00:00.000+0000" not in text
assert "Updated" in text and "ago" in text
# Machine formats keep the raw ISO value.
unix = format_output(rows, format_type="unix")
assert "2026-10-01T12:00:00.000+0000" in unix

# --- current_sprint: board's active sprint intersected with the issue's Sprint field ---
client = _client()
client.get.return_value = ACTIVE_SPRINTS
legacy_active = (
    "com.atlassian.greenhopper.service.sprint.Sprint@1a2b"
    "[id=7,rapidViewId=2,state=ACTIVE,name=Sprint 7]"
)
client.post.return_value = {
    "issues": [
        {
            "key": "PROJ-1",
            "fields": {"customfield_10020": [{"id": 7, "name": "Sprint 7"}]},
        },
        {
            "key": "PROJ-2",
            "fields": {
                "customfield_10020": [{"id": 3, "name": "Sprint 3", "state": "closed"}]
            },
        },
        {
            "key": "PROJ-3",
            "fields": {
                "customfield_10020": [
                    {"id": 9, "name": "Other board sprint", "state": "active"}
                ]
            },
        },
        {"key": "PROJ-4", "fields": {}},
        {"key": "PROJ-5", "fields": {"customfield_10020": [legacy_active]}},
    ]
}
rows = search_issues(
    client,
    jql="project = PROJ",
    config=_config(board="42"),
    list_fields=["key", "current_sprint"],
    fields_mgr=_fields_mgr(),
)
assert [row["Current Sprint"] for row in rows] == [
    "Sprint 7",
    "Backlog",
    "Backlog",
    "Backlog",
    "Sprint 7",
]
assert client.post.call_args.args[1]["fields"] == ["customfield_10020"]
client.get.assert_called_once_with(
    "/rest/agile/1.0/board/42/sprint", params={"state": "active"}
)

# --- current_sprint is skipped, with a warning, when no board is configured ---
warnings_seen = []
client = _client()
client.get.return_value = ACTIVE_SPRINTS
rows = search_issues(
    client,
    jql="project = PROJ",
    config=_config(),
    list_fields=["summary", "current_sprint"],
    fields_mgr=_fields_mgr(),
    on_warning=warnings_seen.append,
)
assert list(rows[0].keys()) == ["Summary"]
assert len(warnings_seen) == 1 and "current_sprint" in warnings_seen[0]
assert "defaults.board" in warnings_seen[0]

client = _client()
try:
    search_issues(
        client,
        jql="project = PROJ",
        config=_config(),
        list_fields=["current_sprint"],
        fields_mgr=_fields_mgr(),
        on_warning=lambda _message: None,
    )
    raise AssertionError("expected ValueError")
except ValueError as exc:
    assert "No valid list fields" in str(exc)

# --- current_sprint is skipped when the Sprint field is not in the cache ---
mgr = MagicMock(spec=FieldCacheManager)
mgr.resolve_field.return_value = None
client = _client()
warnings_seen = []
rows = search_issues(
    client,
    jql="project = PROJ",
    config=_config(board="42"),
    list_fields=["summary", "current_sprint"],
    fields_mgr=mgr,
    on_warning=warnings_seen.append,
)
assert list(rows[0].keys()) == ["Summary"]
assert len(warnings_seen) == 1 and "Sprint" in warnings_seen[0]
assert client.get.call_count == 0

# --- show: current_sprint renders as a Current Sprint metadata line ---
client = MagicMock(spec=JiraClient)
client.get.side_effect = [
    {
        "key": "PROJ-1",
        "fields": {"customfield_10020": [{"id": 7, "name": "Sprint 7"}]},
    },
    ACTIVE_SPRINTS,
]
shown = get_issue(
    client,
    "PROJ-1",
    only=["current_sprint"],
    fields_mgr=_fields_mgr(),
    board="42",
)
assert shown["Current Sprint"] == "Sprint 7"
assert client.get.call_args_list[0].args[0] == "/rest/api/3/issue/PROJ-1"
assert client.get.call_args_list[0].kwargs["params"] == {"fields": "customfield_10020"}

client = MagicMock(spec=JiraClient)
client.get.side_effect = [{"key": "PROJ-2", "fields": {}}, ACTIVE_SPRINTS]
shown = get_issue(
    client,
    "PROJ-2",
    only=["current_sprint"],
    fields_mgr=_fields_mgr(),
    board="42",
)
assert shown["Current Sprint"] == "Backlog"

# --- show: current_sprint without a board fails clearly ---
client = MagicMock(spec=JiraClient)
client.get.return_value = {"key": "PROJ-1", "fields": {}}
try:
    get_issue(client, "PROJ-1", only=["current_sprint"], fields_mgr=_fields_mgr())
    raise AssertionError("expected ValueError")
except ValueError as exc:
    assert "defaults.board" in str(exc)

# --- text output shows the Current Sprint column ---
rows = [{"Key": "PROJ-1", "Current Sprint": "Sprint 7"}]
text = format_output(rows, format_type="text")
assert "Current Sprint" in text and "Sprint 7" in text


# --- CLI wiring: --fields overrides defaults.list_fields ---
def test_cli_list_fields():
    runner = CliRunner()
    with patch("jflow.interfaces.cli._load_cfg") as load_cfg, patch(
        "jflow.interfaces.cli.JiraClient"
    ) as Client, patch("jflow.interfaces.cli.list_my_issues") as list_my:
        cfg = MagicMock()
        cfg.user.defaults.output_format = "json"
        cfg.user.defaults.list_fields = ["summary"]
        load_cfg.return_value = cfg
        Client.from_settings.return_value = MagicMock()
        list_my.return_value = []

        result = runner.invoke(
            app, ["list", "--fields", "status", "--fields", "summary"]
        )
        assert result.exit_code == 0, result.output
        assert list_my.call_args.kwargs["list_fields"] == ["status", "summary"]
        assert callable(list_my.call_args.kwargs["on_warning"])

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0, result.output
        assert list_my.call_args.kwargs["list_fields"] == ["summary"]


def test_cli_query_fields():
    runner = CliRunner()
    with patch("jflow.interfaces.cli._load_cfg") as load_cfg, patch(
        "jflow.interfaces.cli.JiraClient"
    ) as Client, patch("jflow.interfaces.cli.search_issues") as search:
        cfg = MagicMock()
        cfg.user.defaults.output_format = "json"
        cfg.user.defaults.list_fields = ["summary"]
        load_cfg.return_value = cfg
        Client.from_settings.return_value = MagicMock()
        search.return_value = []

        result = runner.invoke(
            app, ["query", "project = PROJ", "--fields", "status"]
        )
        assert result.exit_code == 0, result.output
        assert search.call_args.kwargs["list_fields"] == ["status"]
        assert callable(search.call_args.kwargs["on_warning"])


def test_cli_show_current_sprint():
    runner = CliRunner()
    with patch("jflow.interfaces.cli._load_cfg") as load_cfg, patch(
        "jflow.interfaces.cli.JiraClient"
    ) as Client, patch("jflow.interfaces.cli.get_issue") as get_issue_mock:
        cfg = MagicMock()
        cfg.user.defaults.output_format = "json"
        cfg.user.defaults.show_fields = None
        cfg.user.defaults.board = "42"
        load_cfg.return_value = cfg
        Client.from_settings.return_value = MagicMock()
        get_issue_mock.return_value = {"key": "PROJ-1"}

        result = runner.invoke(app, ["show", "PROJ-1", "--only", "current_sprint"])
        assert result.exit_code == 0, result.output
        assert get_issue_mock.call_args.kwargs["only"] == ["current_sprint"]
        assert get_issue_mock.call_args.kwargs["board"] == "42"


test_cli_list_fields()
test_cli_query_fields()
test_cli_show_current_sprint()

print("✅ Configurable list field tests passed successfully!")
