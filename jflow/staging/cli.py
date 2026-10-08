# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Composer).
# ==============================================================================
from typing import Optional
import typer

from jflow.staging.context import VALID_GROUPS
from jflow.staging.runner import parse_groups, run_staging_tests


def main(
    user_yaml: str = typer.Option(
        ...,
        "--user-yaml",
        help="Path to staging user.yaml (required; no default)",
    ),
    lifecycle: bool = typer.Option(
        False,
        "--lifecycle",
        help="Enable mutating full-lifecycle tests (issue/sprint/workflow). Default is read-only smoke.",
    ),
    group: str = typer.Option(
        "all",
        "--group",
        "-g",
        help=f"Comma-separated groups or 'all'. Valid: {', '.join(VALID_GROUPS)}",
    ),
    board_id: Optional[int] = typer.Option(
        None,
        "--board-id",
        help="Agile board ID (required when sprint group is selected)",
    ),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Project key override (default: defaults.project from user.yaml)",
    ),
) -> None:
    """Run integration tests against a staging Jira Cloud environment."""
    try:
        groups = parse_groups(group)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    try:
        code = run_staging_tests(
            user_yaml=user_yaml,
            lifecycle=lifecycle,
            groups=groups,
            board_id=board_id,
            project=project,
        )
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    raise typer.Exit(code=code)


def app() -> None:
    """Console-script entry point."""
    typer.run(main)


if __name__ == "__main__":
    app()
