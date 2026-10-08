# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from jflow.core.actions.create import create_issue
from jflow.core.actions.sprint import (
    add_issue_to_sprint,
    create_sprint,
    get_backlog_issues,
    get_board_sprints,
    update_sprint_state,
)
from jflow.staging.context import STAGING_LABEL, StagingContext, delete_issue


def run_sprint_smoke(ctx: StagingContext) -> None:
    group = "sprint"
    if ctx.board_id is None:
        ctx.record(group, "board_required", "FAIL", "--board-id is required for sprint tests")
        return

    try:
        sprints = get_board_sprints(ctx.client, board_id=ctx.board_id, state="active")
        assert isinstance(sprints, list)
        ctx.record(group, "get_board_sprints", "PASS", f"{len(sprints)} active")
    except Exception as exc:
        ctx.record(group, "get_board_sprints", "FAIL", str(exc))

    try:
        backlog = get_backlog_issues(ctx.client, board_id=ctx.board_id, max_results=10)
        assert isinstance(backlog, list)
        ctx.record(group, "get_backlog_issues", "PASS", f"{len(backlog)} issue(s)")
    except Exception as exc:
        ctx.record(group, "get_backlog_issues", "FAIL", str(exc))


def run_sprint_lifecycle(ctx: StagingContext) -> None:
    group = "sprint"
    if ctx.board_id is None:
        ctx.record(group, "board_required", "FAIL", "--board-id is required for sprint lifecycle")
        return

    sprint_id = None
    issue_key = None
    try:
        sprint = create_sprint(
            ctx.client,
            name=f"{STAGING_LABEL}-{ctx.run_id}",
            board_id=ctx.board_id,
            goal="jflow staging lifecycle sprint",
        )
        sprint_id = sprint["id"]
        ctx.record(group, "create_sprint", "PASS", f"id={sprint_id}")

        created = create_issue(
            client=ctx.client,
            config=ctx.config,
            fields_mgr=ctx.fields_mgr,
            project=ctx.project,
            issue_type=ctx.config.user.defaults.issue_type or "Task",
            summary=ctx.unique_summary("sprint-lifecycle"),
            description="Staging sprint lifecycle issue.",
            labels=[STAGING_LABEL],
        )
        issue_key = created["key"]
        ctx.record(group, "create_issue_for_sprint", "PASS", issue_key)

        add_issue_to_sprint(ctx.client, issue_key=issue_key, sprint_id=sprint_id)
        ctx.record(group, "add_issue_to_sprint", "PASS", f"{issue_key} -> {sprint_id}")

        # Close without activating a production sprint: future -> closed is allowed on many boards.
        # If close fails from future, try activate then close.
        try:
            update_sprint_state(ctx.client, sprint_id=sprint_id, state="closed")
            ctx.record(group, "close_sprint", "PASS", f"id={sprint_id}")
        except Exception:
            update_sprint_state(ctx.client, sprint_id=sprint_id, state="active")
            update_sprint_state(ctx.client, sprint_id=sprint_id, state="closed")
            ctx.record(group, "close_sprint", "PASS", f"id={sprint_id} (via active)")

    except Exception as exc:
        ctx.record(group, "sprint_lifecycle", "FAIL", str(exc))
    finally:
        if issue_key:
            try:
                delete_issue(ctx.client, issue_key)
                ctx.record(group, "cleanup_issue", "PASS", issue_key)
            except Exception as exc:
                ctx.record(group, "cleanup_issue", "FAIL", f"{issue_key}: {exc}")
        if sprint_id:
            try:
                ctx.client.delete(f"/rest/agile/1.0/sprint/{sprint_id}")
                ctx.record(group, "cleanup_sprint_delete", "PASS", f"id={sprint_id}")
            except Exception as exc:
                ctx.record(
                    group,
                    "cleanup_sprint_delete",
                    "SKIP",
                    f"could not delete sprint {sprint_id} (often already closed): {exc}",
                )
