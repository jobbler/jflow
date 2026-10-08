# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
# Updated in whole or in part by AI using Cursor (Composer).
import json
from typing import Dict, List, Optional, Sequence

import typer
from typer.completion import completion_init, get_completion_script

from jflow.config.loader import load_config
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager
from jflow.core.formatter import format_output
from jflow.core.keys import normalize_issue_key

from jflow.core.actions import (
    create_issue,
    assign_issue,
    set_reporter,
    transition_issue,
    add_comment,
    search_issues,
    list_my_issues,
    get_issue,
    init_config,
)
from jflow.core.actions.issue_view import needs_field_cache
from jflow.core.actions.search import MY_ISSUE_FILTERS
from jflow.core.actions.system import build_status
from jflow.core.actions.sprint import (
    add_issue_to_sprint,
    create_sprint,
    get_active_sprint,
    get_backlog_issues,
    get_board_sprints,
    list_boards,
    resolve_board,
    update_sprint_state,
)
from jflow.core.actions.labels import add_labels, remove_labels, set_labels
from jflow.core.actions.chain import execute_chain
from jflow.core.actions.fields import (
    update_field,
    update_summary,
    update_description,
    update_due_date,
    update_parent,
    update_components,
    update_story_points,
    update_pull_request,
    set_blocked,
)
from jflow.core.actions.links import link_issues, resolve_link_type
from jflow.version import __version__


app = typer.Typer(
    name="jflow",
    help="CLI for Jira Cloud",
    add_completion=False,
    invoke_without_command=True,
)
issue_app = typer.Typer(help="Create, view, list, and update Jira issues")
cache_app = typer.Typer(help="Manage local field schema cache")
boards_app = typer.Typer(help="List and search Agile boards")
sprint_app = typer.Typer(help="Manage sprints and board backlog")
auth_app = typer.Typer(help="OAuth 2.0 (3LO) login and token management")
app.add_typer(issue_app, name="issue")
app.add_typer(cache_app, name="cache")
app.add_typer(boards_app, name="boards")
app.add_typer(sprint_app, name="sprint")
app.add_typer(auth_app, name="auth")

# Register bash/zsh/fish completers for Typer's runtime _JFLOW_COMPLETE handler.
# Required even with add_completion=False; safe if the console script calls app() not main().
completion_init()


def _parse_field_value(raw: str) -> object:
    """Parse a field value as JSON when possible; otherwise keep as string."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def _parse_field_assignments(assignments: List[str]) -> List[tuple]:
    """Parse positional fieldname=value tokens into (name, value) pairs."""
    pairs: List[tuple] = []
    for item in assignments:
        if "=" not in item:
            raise typer.BadParameter(
                f"Expected fieldname=value, got '{item}'",
                param_hint="assignments",
            )
        name, value = item.split("=", 1)
        name = name.strip()
        if not name:
            raise typer.BadParameter(
                f"Empty field name in '{item}'",
                param_hint="assignments",
            )
        pairs.append((name, _parse_field_value(value)))
    return pairs


def _parse_vars(var: Optional[List[str]]) -> Dict[str, str]:
    template_vars: Dict[str, str] = {}
    if not var:
        return template_vars
    for item in var:
        if "=" in item:
            k, v = item.split("=", 1)
            template_vars[k.strip()] = v.strip()
    return template_vars


def _join_text(parts: Optional[List[str]]) -> Optional[str]:
    """Join trailing positional tokens into one string (quoting optional)."""
    if not parts:
        return None
    return " ".join(parts)


def _parse_bool_token(raw: str) -> bool:
    """Parse a true/false positional token."""
    value = (raw or "").strip().lower()
    if value in ("true", "1", "yes"):
        return True
    if value in ("false", "0", "no"):
        return False
    raise typer.BadParameter("Expected true or false", param_hint="blocked")


def _issue_key_callback(value: str) -> str:
    """Typer callback: canonicalize issue keys (Agile APIs are case-sensitive)."""
    normalized = normalize_issue_key(value)
    if not normalized:
        raise typer.BadParameter("Issue key is required.")
    return normalized


def _optional_issue_key_callback(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return value
    return normalize_issue_key(value)


def _require_value_or_clear(
    *,
    value: Optional[str],
    clear: bool,
    prompt_label: Optional[str] = None,
    allow_empty_prompt: bool = False,
) -> Optional[str]:
    """Return a value to set, or None when --clear. Reject empty clears without --clear."""
    if clear and value is not None:
        raise typer.BadParameter("Pass a value or --clear, not both.")
    if clear:
        return None
    if value is None and prompt_label:
        value = typer.prompt(prompt_label)
    if value is None or (not allow_empty_prompt and value == ""):
        raise typer.BadParameter("A value is required (or pass --clear).")
    return value


def _parse_labels(tokens: Optional[List[str]]) -> List[str]:
    """Split space- and comma-separated label tokens into a flat list."""
    if not tokens:
        return []
    labels: List[str] = []
    for token in tokens:
        for part in token.split(","):
            label = part.strip()
            if label:
                labels.append(label)
    return labels


def _require_board(board_opt: Optional[str], config) -> str:
    board = board_opt or config.get_default_board()
    if not board:
        raise typer.BadParameter(
            "Board is required. Pass --board NAME|ID or set defaults.board in user.yaml."
        )
    return str(board)


def _resolve_board_id(client: JiraClient, board_opt: Optional[str], config) -> int:
    return resolve_board(client, _require_board(board_opt, config))


def _load_cfg(ctx: typer.Context):
    obj = ctx.ensure_object(dict)
    return load_config(user_settings_path=obj.get("user_yaml"))


def _fmt(ctx: typer.Context, config) -> str:
    obj = ctx.ensure_object(dict)
    fmt = obj.get("format") or config.user.defaults.output_format or "markdown"
    if fmt not in _OUTPUT_FORMATS:
        raise typer.BadParameter(
            f"Unsupported format '{fmt}'. Use: {', '.join(_OUTPUT_FORMATS)}"
        )
    return fmt


def _emit(ctx: typer.Context, config, data) -> None:
    typer.echo(format_output(data, format_type=_fmt(ctx, config)))


_COMPLETE_SHELLS = ("bash", "zsh", "fish")
_OUTPUT_FORMATS = ("markdown", "text", "unix", "json", "yaml")
_COMMENT_MODES = ("none", "last", "all")
_SPRINT_STATES = ("active", "future", "closed")


def _complete_from(choices: Sequence[str], incomplete: str) -> List[str]:
    """Prefix-filter closed choice values for shell completion."""
    prefix = incomplete or ""
    return [c for c in choices if c.startswith(prefix)]


def _complete_format(incomplete: str) -> List[str]:
    return _complete_from(_OUTPUT_FORMATS, incomplete)


def _complete_shell(incomplete: str) -> List[str]:
    return _complete_from(_COMPLETE_SHELLS, incomplete)


def _complete_comments(incomplete: str) -> List[str]:
    return _complete_from(_COMMENT_MODES, incomplete)


def _complete_filter(incomplete: str) -> List[str]:
    return _complete_from(sorted(MY_ISSUE_FILTERS), incomplete)


def _complete_sprint_state(incomplete: str) -> List[str]:
    return _complete_from(_SPRINT_STATES, incomplete)


def _show_completion(shell: str) -> None:
    name = (shell or "").strip().lower()
    if name not in _COMPLETE_SHELLS:
        raise typer.BadParameter(
            f"Unsupported shell '{shell}'. Use bash, zsh, or fish."
        )
    completion_init()
    typer.echo(
        get_completion_script(
            prog_name="jflow",
            complete_var="_JFLOW_COMPLETE",
            shell=name,
        )
    )


@app.callback()
def root_callback(
    ctx: typer.Context,
    format_type: Optional[str] = typer.Option(
        None,
        "--format",
        "-f",
        help="Output format (markdown, text, unix, json, yaml)",
        autocompletion=_complete_format,
    ),
    user_yaml: Optional[str] = typer.Option(
        None,
        "--user-yaml",
        "--user-settings",
        help="Path to user.yaml (default: ~/.config/jflow/user.yaml)",
    ),
    show_completion: Optional[str] = typer.Option(
        None,
        "--show-completion",
        help="Print shell completion script (bash|zsh|fish) for sourcing manually",
        metavar="SHELL",
        autocompletion=_complete_shell,
    ),
):
    """CLI for Jira Cloud."""
    if show_completion:
        _show_completion(show_completion)
        raise typer.Exit()

    obj = ctx.ensure_object(dict)
    obj["format"] = format_type
    obj["user_yaml"] = user_yaml

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@cache_app.command("sync")
def cli_cache_sync(ctx: typer.Context):
    """Download field schema from Jira into the local fields cache."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    fields_mgr = FieldCacheManager(client)
    cache = fields_mgr.sync_field_cache()
    res = {
        "cache_path": str(fields_mgr.cache_path),
        "field_count": len(cache.get("by_id", {})),
        "status": "Fields Cache Synced",
    }
    _emit(ctx, config, res)


@cache_app.command("fields")
def cli_cache_fields(
    ctx: typer.Context,
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Max fields to show"),
):
    """List fields from the local schema cache (syncs if missing)."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    fields_mgr = FieldCacheManager(client)
    cache = fields_mgr.load_cache()
    rows = []
    for entry in cache.get("by_id", {}).values():
        rows.append({
            "id": entry.get("id"),
            "name": entry.get("name"),
            "custom": entry.get("custom"),
        })
    rows.sort(key=lambda r: (r.get("name") or "").casefold())
    if limit is not None:
        rows = rows[: max(limit, 0)]
    _emit(ctx, config, rows)


@issue_app.command("field")
def cli_update_field(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    assignments: List[str] = typer.Argument(
        ..., help="One or more field updates as fieldname=value"
    ),
):
    """Update issue field(s) by name using the cached field schema."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    fields_mgr = FieldCacheManager(client)
    pairs = _parse_field_assignments(assignments)
    results = []
    for field_name, value in pairs:
        results.append(
            update_field(
                client,
                fields_mgr=fields_mgr,
                issue_key=issue_key,
                field=field_name,
                value=value,
            )
        )
    _emit(ctx, config, results if len(results) > 1 else results[0])


@issue_app.command("create")
@app.command("create")
def issue_create(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project Key"),
    issue_type: Optional[str] = typer.Option(None, "--type", "-t", help="Issue Type"),
    summary: Optional[str] = typer.Option(None, "--summary", "-s", help="Summary"),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description (multiline OK; newlines become paragraphs)"
    ),
    template: Optional[str] = typer.Option(None, "--template", "-T", help="Template name from config"),
    var: Optional[List[str]] = typer.Option(None, "--var", "-V", help="Template variable in key=value format"),
):
    """Create a new issue (optionally from a template)."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    fields_mgr = FieldCacheManager(client)
    result = create_issue(
        client=client,
        config=config,
        fields_mgr=fields_mgr,
        project=project,
        issue_type=issue_type,
        summary=summary,
        description=description,
        template_name=template,
        template_vars=_parse_vars(var),
    )
    _emit(ctx, config, result)


@issue_app.command("assign")
@app.command("assign")
def issue_assign(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    user: str = typer.Argument(..., help="Assignee email, name, account ID, or @me"),
):
    """Assign an issue to a user."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    result = assign_issue(client, issue_key=issue_key, assignee=user)
    _emit(ctx, config, result)


@issue_app.command("reporter")
def issue_set_reporter(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    user: str = typer.Argument(..., help="Reporter email, name, account ID, or @me"),
):
    """Set the reporter on an issue."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    result = set_reporter(client, issue_key=issue_key, reporter=user)
    _emit(ctx, config, result)


@issue_app.command("change")
@app.command("change")
def issue_change(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    status: List[str] = typer.Argument(
        ..., help="Target status name or ID (multi-word OK without quotes)"
    ),
):
    """Change an issue's workflow status."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    result = transition_issue(
        client, issue_key=issue_key, target_status=_join_text(status) or ""
    )
    _emit(ctx, config, result)


@issue_app.command("comment")
@app.command("comment")
def issue_comment(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    message: Optional[List[str]] = typer.Argument(
        None, help="Comment body (multi-word OK without quotes; newlines become paragraphs)"
    ),
):
    """Add a comment to an issue."""
    config = _load_cfg(ctx)
    text = _join_text(message)
    if not text:
        text = typer.prompt("Comment text")
    if not text:
        raise typer.BadParameter("Comment text is required.")
    client = JiraClient.from_settings(config.user)
    result = add_comment(client, issue_key=issue_key, comment_text=text)
    _emit(ctx, config, result)


@issue_app.command("label")
@app.command("label")
def issue_label(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    labels: Optional[List[str]] = typer.Argument(
        None, help="Labels (space- and/or comma-separated)"
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Replace all labels with the given list"
    ),
    delete: bool = typer.Option(False, "--delete", help="Remove the given labels"),
):
    """Append (default), overwrite, or delete issue labels."""
    if overwrite and delete:
        raise typer.BadParameter("Use only one of --overwrite or --delete.")
    config = _load_cfg(ctx)
    parsed = _parse_labels(labels)
    client = JiraClient.from_settings(config.user)
    if delete:
        result = remove_labels(client, issue_key=issue_key, labels=parsed)
    elif overwrite:
        result = set_labels(client, issue_key=issue_key, labels=parsed)
    else:
        result = add_labels(client, issue_key=issue_key, labels=parsed)
    _emit(ctx, config, result)


@issue_app.command("chain")
def issue_chain(
    ctx: typer.Context,
    parts: List[str] = typer.Argument(
        ...,
        help="Optional issue key then workflow JSON string or file path",
    ),
    var: Optional[List[str]] = typer.Option(
        None,
        "--var",
        "-V",
        help="Workflow variable in key=value format (fills {placeholders})",
    ),
):
    """Run a multi-step workflow chain: [issue_key] workflow."""
    if len(parts) == 1:
        issue_key, workflow = None, parts[0]
    elif len(parts) == 2:
        issue_key, workflow = normalize_issue_key(parts[0]), parts[1]
    else:
        raise typer.BadParameter(
            "Expected: jflow issue chain [issue_key] workflow",
            param_hint="parts",
        )

    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    fields_mgr = FieldCacheManager(client)

    if workflow.startswith("{") or workflow.startswith("["):
        steps = json.loads(workflow)
    else:
        with open(workflow, "r") as f:
            steps = json.load(f)

    if isinstance(steps, dict) and "steps" in steps:
        steps = steps["steps"]

    results = execute_chain(
        client=client,
        config=config,
        fields_mgr=fields_mgr,
        steps=steps,
        initial_key=issue_key,
        variables=_parse_vars(var),
    )
    _emit(ctx, config, results)


@issue_app.command("list")
@app.command("list")
def issue_list(
    ctx: typer.Context,
    filter_name: str = typer.Option(
        "open",
        "--filter",
        help="Preset: all, open, closed, in-progress, review, code-review",
        autocompletion=_complete_filter,
    ),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Exact status name (overrides --filter)"),
    jql: Optional[str] = typer.Option(None, "--jql", help="Raw JQL or alias (overrides --filter/--status)"),
    max_results: int = typer.Option(15, "--limit", "-l", help="Max results to return"),
    var: Optional[List[str]] = typer.Option(None, "--var", "-V", help="JQL variable in key=value format"),
):
    """List issues assigned to you (filter presets, status, or JQL)."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    results = list_my_issues(
        client,
        filter_name=filter_name,
        status=status,
        jql=jql,
        max_results=max_results,
        config=config,
        template_vars=_parse_vars(var),
    )
    _emit(ctx, config, results)


@issue_app.command("show")
@app.command("show")
def issue_show(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    comments: str = typer.Option(
        "none",
        "--comments",
        "-c",
        help="Comments: none (default), last (2), all, or a positive integer N",
        autocompletion=_complete_comments,
    ),
    only: Optional[List[str]] = typer.Option(
        None, "--only", "-o", help="Show only these detail fields (repeatable)"
    ),
):
    """Show issue details, optionally with comments."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    show_fields = config.user.defaults.show_fields
    effective = only if only else show_fields
    fields_mgr = FieldCacheManager(client) if needs_field_cache(effective) else None
    res = get_issue(
        client,
        issue_key=issue_key,
        comments=comments,
        only=only,
        show_fields=show_fields,
        fields_mgr=fields_mgr,
    )
    _emit(ctx, config, res)


@issue_app.command("search")
@app.command("query")
def issue_search(
    ctx: typer.Context,
    jql: List[str] = typer.Argument(
        ..., help="JQL query string or alias name (multi-word OK without quotes)"
    ),
    max_results: int = typer.Option(15, "--limit", "-l", help="Max results to return"),
    var: Optional[List[str]] = typer.Option(None, "--var", "-V", help="JQL variable in key=value format"),
):
    """Search issues with raw JQL or a configured alias."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    results = search_issues(
        client,
        jql=_join_text(jql) or "",
        max_results=max_results,
        config=config,
        template_vars=_parse_vars(var),
    )
    _emit(ctx, config, results)


@app.command("init")
def cli_init_config(
    force: bool = typer.Option(False, "--force", help="Overwrite existing configuration files"),
):
    """Scaffold default user.yaml under ~/.config/jflow/."""
    res = init_config(force=force)
    typer.echo(format_output(res, format_type="text"))


@app.command("version")
def cli_version():
    """Print jflow package version."""
    typer.echo(__version__)


@app.command("status")
def cli_status(ctx: typer.Context):
    """Show client, authenticated user, and Jira server status."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    res = build_status(client, __version__)
    _emit(ctx, config, res)


@auth_app.command("login")
def auth_login(
    ctx: typer.Context,
    no_browser: bool = typer.Option(
        False,
        "--no-browser",
        help="Do not open a browser; print the authorize URL and wait for callback",
    ),
):
    """Authorize via Atlassian OAuth 2.0 (3LO) and store tokens locally."""
    from jflow.core.oauth import login, resolve_oauth_client

    config = _load_cfg(ctx)
    creds = config.user.jira
    if creds.auth != "oauth":
        raise typer.BadParameter(
            "Set jira.auth: oauth (and oauth_client_id / oauth_client_secret) in user.yaml"
        )
    _client_id, _secret, redirect_uri = resolve_oauth_client(creds)
    typer.echo(f"Starting OAuth login (callback {redirect_uri})...")
    tokens = login(creds, open_browser=not no_browser)
    _emit(
        ctx,
        config,
        {
            "status": "OAuth login complete",
            "cloud_id": tokens.cloud_id,
            "site_url": tokens.site_url,
            "has_refresh_token": bool(tokens.refresh_token),
        },
    )


@auth_app.command("logout")
def auth_logout(ctx: typer.Context):
    """Delete stored OAuth tokens."""
    from jflow.core.oauth import delete_tokens, default_token_path

    config = _load_cfg(ctx)
    removed = delete_tokens()
    _emit(
        ctx,
        config,
        {
            "status": "OAuth tokens deleted" if removed else "No token file to delete",
            "token_file": str(default_token_path()),
        },
    )


@auth_app.command("status")
def auth_status(ctx: typer.Context):
    """Show OAuth configuration and token status (no secrets)."""
    from jflow.core.oauth import auth_status_dict

    config = _load_cfg(ctx)
    info = auth_status_dict(config.user.jira)
    _emit(ctx, config, info)


@boards_app.command("list")
def cli_boards_list(
    ctx: typer.Context,
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Max boards to return (default: all)"),
):
    """List all Agile boards with numeric id and name (paginated)."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    results = list_boards(client, max_results=limit)
    _emit(ctx, config, results)


@boards_app.command("search")
def cli_boards_search(
    ctx: typer.Context,
    query: List[str] = typer.Argument(
        ..., help="Board name substring to search (multi-word OK without quotes)"
    ),
    limit: int = typer.Option(50, "--limit", help="Max boards to return"),
):
    """Search Agile boards by name substring."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    results = list_boards(client, name=_join_text(query) or "", max_results=limit)
    _emit(ctx, config, results)


@sprint_app.command("list")
def cli_sprint_list(
    ctx: typer.Context,
    board: Optional[str] = typer.Option(None, "--board", "-b", help="Board id or name (default: defaults.board)"),
    state: str = typer.Option(
        "active",
        "--state",
        help="Sprint state (active, future, closed)",
        autocompletion=_complete_sprint_state,
    ),
):
    """List sprints for a board."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    board_id = _resolve_board_id(client, board, config)
    results = get_board_sprints(client, board_id=board_id, state=state)
    _emit(ctx, config, results)


@sprint_app.command("current")
def cli_sprint_current(
    ctx: typer.Context,
    board: Optional[str] = typer.Option(None, "--board", "-b", help="Board id or name (default: defaults.board)"),
):
    """Show the current active sprint for a board."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    board_id = _resolve_board_id(client, board, config)
    sprint = get_active_sprint(client, board_id=board_id)
    if not sprint:
        _emit(ctx, config, {"status": f"No active sprint for board {board_id}"})
        raise typer.Exit(code=1)
    _emit(ctx, config, sprint)


@sprint_app.command("add")
def cli_sprint_add(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    sprint_id: Optional[int] = typer.Option(
        None, "--sprint-id", "-s", help="Sprint ID (default: active sprint on the board)"
    ),
    board: Optional[str] = typer.Option(
        None,
        "--board",
        "-b",
        help="Board id or name (default: defaults.board; used to find the active sprint)",
    ),
):
    """Add an issue to a sprint (default: defaults.board + that board's active sprint)."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    # When sprint id is omitted, always resolve board (flag or defaults.board) for active sprint.
    board_id = None
    if sprint_id is None:
        board_id = _resolve_board_id(client, board, config)
    elif board is not None:
        board_id = _resolve_board_id(client, board, config)
    res = add_issue_to_sprint(
        client, issue_key=issue_key, sprint_id=sprint_id, board_id=board_id
    )
    _emit(ctx, config, res)


@sprint_app.command("create")
def cli_sprint_create(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", "-n", help="Sprint name"),
    board: Optional[str] = typer.Option(None, "--board", "-b", help="Board id or name (default: defaults.board)"),
    start_date: Optional[str] = typer.Option(None, "--start", help="Start date (YYYY-MM-DDTHH:MM:SS.000Z)"),
    end_date: Optional[str] = typer.Option(None, "--end", help="End date (YYYY-MM-DDTHH:MM:SS.000Z)"),
    goal: Optional[str] = typer.Option(None, "--goal", help="Sprint goal"),
):
    """Create a sprint on a board."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    board_id = _resolve_board_id(client, board, config)
    res = create_sprint(client, name=name, board_id=board_id, start_date=start_date, end_date=end_date, goal=goal)
    _emit(ctx, config, res)


@sprint_app.command("state")
def cli_sprint_state(
    ctx: typer.Context,
    sprint_id: int = typer.Option(..., "--sprint-id", "-s", help="Sprint ID"),
    state: str = typer.Option(
        ...,
        "--state",
        help="New state ('active', 'closed', 'future')",
        autocompletion=_complete_sprint_state,
    ),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name"),
    goal: Optional[str] = typer.Option(None, "--goal", help="New goal"),
):
    """Update sprint state or metadata."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    res = update_sprint_state(client, sprint_id=sprint_id, state=state, name=name, goal=goal)
    _emit(ctx, config, res)


@sprint_app.command("backlog")
def cli_sprint_backlog(
    ctx: typer.Context,
    board: Optional[str] = typer.Option(None, "--board", "-b", help="Board id or name (default: defaults.board)"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results"),
):
    """List backlog issues for a board."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    board_id = _resolve_board_id(client, board, config)
    res = get_backlog_issues(client, board_id=board_id, max_results=limit)
    _emit(ctx, config, res)


@issue_app.command("summary")
def cli_update_summary(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    summary: List[str] = typer.Argument(
        ..., help="New summary (single line; multi-word OK without quotes)"
    ),
):
    """Update an issue summary."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    res = update_summary(
        client, issue_key=issue_key, summary=_join_text(summary) or ""
    )
    _emit(ctx, config, res)


@issue_app.command("description")
def cli_update_description(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    description: Optional[List[str]] = typer.Argument(
        None, help="New description (multi-word OK without quotes; use --clear to clear)"
    ),
    clear: bool = typer.Option(False, "--clear", help="Clear the description"),
):
    """Update an issue description."""
    config = _load_cfg(ctx)
    desc = _require_value_or_clear(
        value=_join_text(description),
        clear=clear,
        prompt_label="Description",
    )
    client = JiraClient.from_settings(config.user)
    res = update_description(client, issue_key=issue_key, description=desc)
    _emit(ctx, config, res)


@issue_app.command("due-date")
def cli_update_due_date(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    due_date: Optional[str] = typer.Argument(
        None, help="Due date (YYYY-MM-DD); use --clear to clear"
    ),
    clear: bool = typer.Option(False, "--clear", help="Clear the due date"),
):
    """Update an issue due date."""
    config = _load_cfg(ctx)
    value = _require_value_or_clear(value=due_date, clear=clear)
    client = JiraClient.from_settings(config.user)
    res = update_due_date(client, issue_key=issue_key, due_date=value)
    _emit(ctx, config, res)


@issue_app.command("parent")
def cli_update_parent(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    parent_key: Optional[str] = typer.Argument(
        None,
        help="Parent issue key; use --clear to clear",
        callback=_optional_issue_key_callback,
    ),
    clear: bool = typer.Option(False, "--clear", help="Clear the parent"),
):
    """Set or clear an issue parent."""
    config = _load_cfg(ctx)
    value = _require_value_or_clear(value=parent_key, clear=clear)
    client = JiraClient.from_settings(config.user)
    res = update_parent(client, issue_key=issue_key, parent_key=value)
    _emit(ctx, config, res)


@issue_app.command("components")
def cli_update_components(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    components: Optional[List[str]] = typer.Argument(
        None, help="Component name(s); use --clear to clear"
    ),
    clear: bool = typer.Option(False, "--clear", help="Clear all components"),
):
    """Set issue components."""
    if clear and components:
        raise typer.BadParameter("Pass component names or --clear, not both.")
    if clear:
        names: List[str] = []
    elif not components:
        raise typer.BadParameter("At least one component name is required (or pass --clear).")
    else:
        names = components
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    res = update_components(client, issue_key=issue_key, components=names)
    _emit(ctx, config, res)


@issue_app.command("story-points")
def cli_update_story_points(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    points: Optional[str] = typer.Argument(
        None, help="Story points estimate; use --clear to clear"
    ),
    clear: bool = typer.Option(False, "--clear", help="Clear story points"),
):
    """Set story points on an issue."""
    config = _load_cfg(ctx)
    raw = _require_value_or_clear(value=points, clear=clear)
    points_val: Optional[float]
    if raw is None:
        points_val = None
    else:
        try:
            points_val = float(raw)
        except ValueError as exc:
            raise typer.BadParameter("Story points must be a number.") from exc
    client = JiraClient.from_settings(config.user)
    fields_mgr = FieldCacheManager(client)
    res = update_story_points(
        client, fields_mgr=fields_mgr, issue_key=issue_key, points=points_val
    )
    _emit(ctx, config, res)


@issue_app.command("blocked")
def cli_set_blocked(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    blocked: str = typer.Argument(..., help="true or false"),
):
    """Mark an issue blocked or unblocked."""
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    fields_mgr = FieldCacheManager(client)
    res = set_blocked(
        client,
        fields_mgr=fields_mgr,
        issue_key=issue_key,
        blocked=_parse_bool_token(blocked),
    )
    _emit(ctx, config, res)


@issue_app.command("link")
@app.command("link")
def cli_link_issues(
    ctx: typer.Context,
    from_key: str = typer.Argument(
        ...,
        help="Source issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    to_key: str = typer.Argument(
        ...,
        help="Target issue key (e.g. PROJ-456)",
        callback=_issue_key_callback,
    ),
    relates: bool = typer.Option(False, "--relates", help="Relates (default)"),
    blocks: bool = typer.Option(False, "--blocks", help="from blocks to"),
    blocked_by: bool = typer.Option(
        False, "--blocked-by", help="from is blocked by to"
    ),
    clones: bool = typer.Option(False, "--clones", help="from clones to"),
    cloned_by: bool = typer.Option(
        False, "--cloned-by", help="from is cloned by to"
    ),
    duplicates: bool = typer.Option(
        False, "--duplicates", help="from duplicates to"
    ),
    duplicated_by: bool = typer.Option(
        False, "--duplicated-by", help="from is duplicated by to"
    ),
    link_type: Optional[str] = typer.Option(
        None, "--type", help="Custom or site-specific link type name"
    ),
):
    """Link two issues (default: Relates)."""
    try:
        type_name, swap = resolve_link_type(
            relates=relates,
            blocks=blocks,
            blocked_by=blocked_by,
            clones=clones,
            cloned_by=cloned_by,
            duplicates=duplicates,
            duplicated_by=duplicated_by,
            link_type=link_type,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    result = link_issues(
        client, from_key=from_key, to_key=to_key, type_name=type_name, swap=swap
    )
    _emit(ctx, config, result)


@issue_app.command("pullrequest")
def cli_issue_pullrequest(
    ctx: typer.Context,
    issue_key: str = typer.Argument(
        ...,
        help="Issue key (e.g. PROJ-123)",
        callback=_issue_key_callback,
    ),
    text: Optional[List[str]] = typer.Argument(
        None,
        help="Pull request URL or text (multi-word OK; default appends)",
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Replace the field instead of appending"
    ),
    clear: bool = typer.Option(False, "--clear", help="Clear the Git Pull Request field"),
):
    """Append (default), overwrite, or clear the Git Pull Request field."""
    if overwrite and clear:
        raise typer.BadParameter("Use only one of --overwrite or --clear.")
    joined = _join_text(text)
    if clear and joined:
        raise typer.BadParameter("Pass text or --clear, not both.")
    if not clear and not joined:
        joined = typer.prompt("Pull request text")
    if not clear and not joined:
        raise typer.BadParameter("Pull request text is required (or pass --clear).")
    config = _load_cfg(ctx)
    client = JiraClient.from_settings(config.user)
    fields_mgr = FieldCacheManager(client)
    try:
        result = update_pull_request(
            client,
            fields_mgr=fields_mgr,
            issue_key=issue_key,
            text=None if clear else joined,
            overwrite=overwrite,
            clear=clear,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(ctx, config, result)


def main() -> None:
    """Console-script entry point for the jflow CLI."""
    completion_init()
    app()


if __name__ == "__main__":
    main()
