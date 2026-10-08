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


def test_search_issues_template_vars():
    client = MagicMock()
    client.post.return_value = {"issues": []}
    config = AppConfig(
        user=UserConfig(
            jira=JiraCredentials(
                domain="x.atlassian.net",
                email="a@b.com",
                api_token="t",
            ),
            defaults=Defaults(),
            jql_aliases={
                "project-open": "project = {project} AND status != Closed",
            },
        ),
    )
    search_issues(
        client,
        jql="project-open",
        config=config,
        template_vars={"project": "FOO"},
    )
    args, _kwargs = client.post.call_args
    assert args[0] == "/rest/api/3/search/jql"
    payload = args[1]
    assert payload["jql"] == "project = FOO AND status != Closed"


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
    test_deeper_cli_shape()
    print("✅ CLI UX helper tests passed successfully!")
