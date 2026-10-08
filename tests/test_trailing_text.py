# ==============================================================================
# jflow - CLI for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Composer).
"""CLI: unquoted multi-word trailing text is joined into one string."""
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from jflow.interfaces.cli import _join_text, app


def test_join_text():
    assert _join_text(None) is None
    assert _join_text([]) is None
    assert _join_text(["Started"]) == "Started"
    assert _join_text(["Started", "investigation"]) == "Started investigation"
    assert _join_text(["In", "Progress"]) == "In Progress"


def test_comment_joins_unquoted_message():
    runner = CliRunner()
    with patch("jflow.interfaces.cli._load_cfg") as load_cfg, patch(
        "jflow.interfaces.cli.JiraClient"
    ) as Client, patch("jflow.interfaces.cli.add_comment") as add_comment:
        cfg = MagicMock()
        cfg.user.defaults.output_format = "json"
        load_cfg.return_value = cfg
        Client.from_settings.return_value = MagicMock()
        add_comment.return_value = {"comment_id": "1"}

        result = runner.invoke(
            app, ["comment", "PROJ-123", "Started", "investigation"]
        )
        assert result.exit_code == 0, result.output
        add_comment.assert_called_once()
        assert add_comment.call_args.kwargs["comment_text"] == "Started investigation"


def test_change_joins_unquoted_status():
    runner = CliRunner()
    with patch("jflow.interfaces.cli._load_cfg") as load_cfg, patch(
        "jflow.interfaces.cli.JiraClient"
    ) as Client, patch("jflow.interfaces.cli.transition_issue") as transition:
        cfg = MagicMock()
        cfg.user.defaults.output_format = "json"
        load_cfg.return_value = cfg
        Client.from_settings.return_value = MagicMock()
        transition.return_value = {"status": "In Progress"}

        result = runner.invoke(app, ["change", "PROJ-123", "In", "Progress"])
        assert result.exit_code == 0, result.output
        transition.assert_called_once()
        assert transition.call_args.kwargs["target_status"] == "In Progress"


def test_summary_joins_unquoted_text():
    runner = CliRunner()
    with patch("jflow.interfaces.cli._load_cfg") as load_cfg, patch(
        "jflow.interfaces.cli.JiraClient"
    ) as Client, patch("jflow.interfaces.cli.update_summary") as update_summary:
        cfg = MagicMock()
        cfg.user.defaults.output_format = "json"
        load_cfg.return_value = cfg
        Client.from_settings.return_value = MagicMock()
        update_summary.return_value = {"summary": "Fix login timeout"}

        result = runner.invoke(
            app, ["issue", "summary", "PROJ-123", "Fix", "login", "timeout"]
        )
        assert result.exit_code == 0, result.output
        update_summary.assert_called_once()
        assert update_summary.call_args.kwargs["summary"] == "Fix login timeout"


def test_description_joins_unquoted_text():
    runner = CliRunner()
    with patch("jflow.interfaces.cli._load_cfg") as load_cfg, patch(
        "jflow.interfaces.cli.JiraClient"
    ) as Client, patch(
        "jflow.interfaces.cli.update_description"
    ) as update_description:
        cfg = MagicMock()
        cfg.user.defaults.output_format = "json"
        load_cfg.return_value = cfg
        Client.from_settings.return_value = MagicMock()
        update_description.return_value = {"description": "Line one"}

        result = runner.invoke(
            app, ["issue", "description", "PROJ-123", "Line", "one"]
        )
        assert result.exit_code == 0, result.output
        update_description.assert_called_once()
        assert update_description.call_args.kwargs["description"] == "Line one"


def test_query_joins_unquoted_jql():
    runner = CliRunner()
    with patch("jflow.interfaces.cli._load_cfg") as load_cfg, patch(
        "jflow.interfaces.cli.JiraClient"
    ) as Client, patch("jflow.interfaces.cli.search_issues") as search_issues:
        cfg = MagicMock()
        cfg.user.defaults.output_format = "json"
        load_cfg.return_value = cfg
        Client.from_settings.return_value = MagicMock()
        search_issues.return_value = []

        result = runner.invoke(
            app, ["query", "assignee", "=", "currentUser()"]
        )
        assert result.exit_code == 0, result.output
        search_issues.assert_called_once()
        assert search_issues.call_args.kwargs["jql"] == "assignee = currentUser()"


def test_boards_search_joins_unquoted_query():
    runner = CliRunner()
    with patch("jflow.interfaces.cli._load_cfg") as load_cfg, patch(
        "jflow.interfaces.cli.JiraClient"
    ) as Client, patch("jflow.interfaces.cli.list_boards") as list_boards:
        cfg = MagicMock()
        cfg.user.defaults.output_format = "json"
        load_cfg.return_value = cfg
        Client.from_settings.return_value = MagicMock()
        list_boards.return_value = []

        result = runner.invoke(app, ["boards", "search", "My", "Board"])
        assert result.exit_code == 0, result.output
        list_boards.assert_called_once()
        assert list_boards.call_args.kwargs["name"] == "My Board"


if __name__ == "__main__":
    test_join_text()
    test_comment_joins_unquoted_message()
    test_change_joins_unquoted_status()
    test_summary_joins_unquoted_text()
    test_description_joins_unquoted_text()
    test_query_joins_unquoted_jql()
    test_boards_search_joins_unquoted_query()
    print("✅ Trailing text tests passed successfully!")
