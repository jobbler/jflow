# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from datetime import date, timedelta

from jflow.core.actions.create import create_issue
from jflow.core.actions.assignee import assign_issue
from jflow.core.actions.status_comment import add_comment, transition_issue
from jflow.core.actions.labels import add_labels, remove_labels, set_labels
from jflow.core.actions.fields import update_due_date, update_story_points
from jflow.core.actions.search import search_issues
from jflow.staging.context import STAGING_LABEL, StagingContext, delete_issue


def run_issue_smoke(ctx: StagingContext) -> None:
    group = "issue"
    jql = f'project = {ctx.project} ORDER BY updated DESC'
    try:
        results = search_issues(ctx.client, jql=jql, max_results=5, config=ctx.config)
        assert isinstance(results, list)
        ctx.record(group, "project_access_search", "PASS", f"{len(results)} result(s)")
    except Exception as exc:
        ctx.record(group, "project_access_search", "FAIL", str(exc))


def _best_effort_transition(ctx: StagingContext, issue_key: str) -> None:
    group = "issue"
    try:
        transitions = ctx.client.get(f"/rest/api/3/issue/{issue_key}/transitions").get("transitions", [])
        if not transitions:
            ctx.record(group, "transition", "SKIP", "no transitions available")
            return
        preferred = None
        for name in ("In Progress", "Selected for Development", "To Do", "Done"):
            for t in transitions:
                if t["name"].lower() == name.lower():
                    preferred = t["name"]
                    break
            if preferred:
                break
        target = preferred or transitions[0]["name"]
        res = transition_issue(ctx.client, issue_key, target)
        ctx.record(group, "transition", "PASS", res.get("status", target))
    except Exception as exc:
        ctx.record(group, "transition", "FAIL", str(exc))


def run_issue_lifecycle(ctx: StagingContext) -> None:
    group = "issue"
    issue_key = None
    try:
        created = create_issue(
            client=ctx.client,
            config=ctx.config,
            fields_mgr=ctx.fields_mgr,
            project=ctx.project,
            issue_type=ctx.config.user.defaults.issue_type or "Task",
            summary=ctx.unique_summary("issue-lifecycle"),
            description="Created by jflow staging lifecycle test.",
            labels=[STAGING_LABEL],
        )
        issue_key = created["key"]
        ctx.record(group, "create", "PASS", issue_key)

        assignee = ctx.config.user.jira.email
        try:
            assign_issue(ctx.client, issue_key, assignee)
            ctx.record(group, "assign", "PASS", assignee)
        except Exception as exc:
            ctx.record(group, "assign", "FAIL", str(exc))

        try:
            add_comment(ctx.client, issue_key, f"Staging comment {ctx.run_id}")
            ctx.record(group, "comment", "PASS")
        except Exception as exc:
            ctx.record(group, "comment", "FAIL", str(exc))

        try:
            add_labels(ctx.client, issue_key, ["staging-temp"])
            remove_labels(ctx.client, issue_key, ["staging-temp"])
            set_labels(ctx.client, issue_key, [STAGING_LABEL])
            ctx.record(group, "labels", "PASS")
        except Exception as exc:
            ctx.record(group, "labels", "FAIL", str(exc))

        try:
            due = (date.today() + timedelta(days=7)).isoformat()
            update_due_date(ctx.client, issue_key, due)
            ctx.record(group, "due_date", "PASS", due)
        except Exception as exc:
            ctx.record(group, "due_date", "FAIL", str(exc))

        try:
            update_story_points(ctx.client, ctx.fields_mgr, issue_key, 1.0)
            ctx.record(group, "story_points", "PASS", "1.0")
        except Exception as exc:
            ctx.record(group, "story_points", "SKIP", f"field unavailable or rejected: {exc}")

        _best_effort_transition(ctx, issue_key)

    except Exception as exc:
        ctx.record(group, "create", "FAIL", str(exc))
    finally:
        if issue_key:
            try:
                delete_issue(ctx.client, issue_key)
                ctx.record(group, "cleanup_delete", "PASS", issue_key)
            except Exception as exc:
                ctx.record(group, "cleanup_delete", "FAIL", f"{issue_key}: {exc}")
