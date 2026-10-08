# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
"""Shell completion: nested groups, options, value completers, script format."""
import io
import os
from contextlib import redirect_stdout

from typer.completion import completion_init, shell_complete
from typer.testing import CliRunner

from jflow.interfaces.cli import app
import typer


runner = CliRunner()


def _complete(words: str, cword: int) -> list[str]:
    """Return completion lines for COMP_WORDS / COMP_CWORD via Typer."""
    completion_init()
    os.environ["COMP_WORDS"] = words
    os.environ["COMP_CWORD"] = str(cword)
    cli = typer.main.get_command(app)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = shell_complete(cli, {}, "jflow", "_JFLOW_COMPLETE", "complete_bash")
    assert rc == 0
    return [line for line in buf.getvalue().splitlines() if line]


def test_nested_issue_group_subcommands():
    lines = _complete("jflow issue ", 2)
    assert "show" in lines
    assert "create" in lines
    assert "change" in lines
    # Must not fall back to root-only suggestions (e.g. only top-level aliases).
    assert "field" in lines
    assert "link" in lines
    assert "pullrequest" in lines
    assert "convert" in lines
    assert "auth" not in lines


def test_link_flags_and_root_alias():
    root = _complete("jflow ", 1)
    assert "link" in root
    flags = _complete("jflow link --", 3)
    assert "--blocks" in flags
    assert "--blocked-by" in flags
    assert "--relates" in flags
    assert "--clones" in flags
    assert "--cloned-by" in flags
    assert "--duplicates" in flags
    assert "--duplicated-by" in flags
    assert "--type" in flags


def test_nested_auth_sprint_boards_cache():
    assert set(_complete("jflow auth ", 2)) >= {"login", "logout", "status"}
    assert set(_complete("jflow sprint ", 2)) >= {
        "list",
        "current",
        "add",
        "create",
        "state",
        "backlog",
    }
    assert set(_complete("jflow boards ", 2)) >= {"list", "search"}
    assert set(_complete("jflow cache ", 2)) >= {"sync", "fields"}


def test_leaf_options_for_issue_show():
    lines = _complete("jflow issue show --", 3)
    assert "--comments" in lines
    assert "--only" in lines


def test_format_value_completer():
    assert _complete("jflow --format ", 2) == [
        "markdown",
        "text",
        "unix",
        "json",
        "yaml",
        "table",
    ]
    assert _complete("jflow --format j", 2) == ["json"]


def test_filter_and_comments_and_state_completers():
    filters = _complete("jflow list --filter ", 3)
    assert "open" in filters
    assert "in-progress" in filters
    assert "code-review" in filters

    assert _complete("jflow issue show --comments ", 4) == [
        "none",
        "last",
        "all",
    ]
    assert _complete("jflow sprint list --state ", 4) == [
        "active",
        "future",
        "closed",
    ]


def test_show_completion_shell_values():
    assert _complete("jflow --show-completion ", 2) == ["bash", "zsh", "fish"]


def test_show_completion_script_uses_typer_instruction():
    result = runner.invoke(app, ["--show-completion", "bash"])
    assert result.exit_code == 0
    assert "complete_bash" in result.stdout
    assert "bash_complete" not in result.stdout
    assert "_jflow_completion" in result.stdout
    assert "complete " in result.stdout


if __name__ == "__main__":
    test_nested_issue_group_subcommands()
    test_link_flags_and_root_alias()
    test_nested_auth_sprint_boards_cache()
    test_leaf_options_for_issue_show()
    test_format_value_completer()
    test_filter_and_comments_and_state_completers()
    test_show_completion_shell_values()
    test_show_completion_script_uses_typer_instruction()
    print("✅ Shell completion tests passed successfully!")
