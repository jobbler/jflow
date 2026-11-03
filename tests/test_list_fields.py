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
from jflow.core.actions.search import list_my_issues, search_issues
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager
from jflow.core.formatter import format_output
from jflow.interfaces.cli import app


def _config(list_fields=None):
    return AppConfig(
        user=UserConfig(
            jira=JiraCredentials(
                domain="x.atlassian.net", email="a@b.com", api_token="t"
            ),
            defaults=Defaults(list_fields=list_fields),
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
        else None
    )
    return mgr


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


test_cli_list_fields()
test_cli_query_fields()

print("✅ Configurable list field tests passed successfully!")
