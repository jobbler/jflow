# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
"""CLI helpers: label parsing, var parsing, search --var, deeper CLI shape."""
from unittest.mock import MagicMock

from typer.testing import CliRunner

from jflow.interfaces.cli import _parse_labels, _parse_vars, app
from jflow.core.actions.search import search_issues
from jflow.config.models import (
    AppConfig,
    UserConfig,
    JiraCredentials,
    Defaults,
)


def test_parse_labels_space_and_comma():
    assert _parse_labels(["bug", "urgent"]) == ["bug", "urgent"]
    assert _parse_labels(["bug,urgent", "hotfix"]) == ["bug", "urgent", "hotfix"]
    assert _parse_labels([" bug , ,x "]) == ["bug", "x"]
    assert _parse_labels(None) == []
    assert _parse_labels([]) == []


def test_parse_vars():
    assert _parse_vars(["project=PROJ", "env=Prod"]) == {"project": "PROJ", "env": "Prod"}
    assert _parse_vars(None) == {}
    assert _parse_vars(["noequals"]) == {}


def _config_with_alias(**defaults_kwargs):
    return AppConfig(
        user=UserConfig(
            jira=JiraCredentials(
                domain="x.atlassian.net",
                email="a@b.com",
                api_token="t",
            ),
            defaults=Defaults(**defaults_kwargs),
            jql_aliases={
                "project-open": "project = {project} AND status != Closed",
                "mine": "assignee = {user} AND project = {project} AND component = {component}",
            },
        ),
    )


def _searched_jql(client):
    args, _kwargs = client.post.call_args
    assert args[0] == "/rest/api/3/search/jql"
    return args[1]["jql"]


def test_search_issues_template_vars():
    client = MagicMock()
    client.post.return_value = {"issues": []}
    config = _config_with_alias()
    search_issues(
        client,
        jql="project-open",
        config=config,
        template_vars={"project": "FOO"},
    )
    assert _searched_jql(client) == "project = FOO AND status != Closed"


def test_search_issues_jql_vars_from_config():
    client = MagicMock()
    client.post.return_value = {"issues": []}
    config = _config_with_alias(
        project="PROJ",
        vars={"user": "me", "component": "My Team Component"},
    )
    search_issues(client, jql="mine", config=config)
    assert _searched_jql(client) == (
        "assignee = me AND project = PROJ AND component = My Team Component"
    )


def test_search_issues_cli_var_overrides_jql_vars():
    client = MagicMock()
    client.post.return_value = {"issues": []}
    config = _config_with_alias(
        project="PROJ",
        vars={"user": "me", "component": "My Team Component", "project": "FROM-MAP"},
    )
    search_issues(
        client,
        jql="mine",
        config=config,
        template_vars={"user": "not-me"},
    )
    assert _searched_jql(client) == (
        "assignee = not-me AND project = FROM-MAP AND component = My Team Component"
    )


def test_search_issues_unknown_placeholder_stays():
    client = MagicMock()
    client.post.return_value = {"issues": []}
    config = _config_with_alias(project="PROJ")
    search_issues(
        client,
        jql="assignee = {user} AND project = {project}",
        config=config,
    )
    assert _searched_jql(client) == "assignee = {user} AND project = PROJ"


def test_list_jql_uses_config_vars():
    from jflow.core.actions.search import list_my_issues

    client = MagicMock()
    client.post.return_value = {"issues": []}
    config = _config_with_alias(project="PROJ", vars={"user": "me"})
    list_my_issues(client, jql="assignee = {user} AND project = {project}", config=config)
    assert _searched_jql(client) == "assignee = me AND project = PROJ"


def test_deeper_cli_shape():
    runner = CliRunner()
    root = runner.invoke(app, ["--help"])
    assert root.exit_code == 0
    for name in ("show", "list", "create", "assign", "comment", "label", "change", "query"):
        assert name in root.output
    assert runner.invoke(app, ["search", "--help"]).exit_code != 0

    issue = runner.invoke(app, ["issue", "--help"])
    assert issue.exit_code == 0
    assert "change" in issue.output
    assert runner.invoke(app, ["issue", "status", "--help"]).exit_code != 0

    assert runner.invoke(app, ["change", "--help"]).exit_code == 0
    assert runner.invoke(app, ["issue", "change", "--help"]).exit_code == 0

    sprint = runner.invoke(app, ["sprint", "--help"])
    assert sprint.exit_code == 0
    assert "add" in sprint.output
    assert "issue-add" not in sprint.output
    assert runner.invoke(app, ["sprint", "issue-add", "--help"]).exit_code != 0

    assert "status" in root.output


if __name__ == "__main__":
    test_parse_labels_space_and_comma()
    test_parse_vars()
    test_search_issues_template_vars()
    test_search_issues_jql_vars_from_config()
    test_search_issues_cli_var_overrides_jql_vars()
    test_search_issues_unknown_placeholder_stays()
    test_list_jql_uses_config_vars()
    test_deeper_cli_shape()
    print("✅ CLI UX helper tests passed successfully!")
