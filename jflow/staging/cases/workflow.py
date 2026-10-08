# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List

from jflow.core.actions.chain import execute_chain
from jflow.staging.context import STAGING_LABEL, StagingContext, delete_issue

_FIXTURE_NAME = "staging_create_assign_comment.json"


def resolve_staging_workflow_path() -> Path:
    """Prefer repo examples/ when present; else packaged staging fixture."""
    here = Path(__file__).resolve()
    # jflow/staging/cases/workflow.py -> repo root examples/
    repo_example = here.parents[3] / "examples" / "workflows" / _FIXTURE_NAME
    if repo_example.is_file():
        return repo_example
    packaged = here.parents[1] / "fixtures" / _FIXTURE_NAME
    if packaged.is_file():
        return packaged
    raise FileNotFoundError(
        f"Staging workflow fixture not found (checked {repo_example} and {packaged})"
    )


def load_staging_workflow_steps(ctx: StagingContext) -> List[Dict[str, Any]]:
    """Load reference JSON and substitute project, assignee, summary, comment."""
    path = resolve_staging_workflow_path()
    raw = json.loads(path.read_text())
    steps = raw["steps"] if isinstance(raw, dict) and "steps" in raw else raw
    steps = copy.deepcopy(steps)

    for step in steps:
        action = step.get("action")
        if action == "create":
            step["project"] = ctx.project
            step["issue_type"] = ctx.config.user.defaults.issue_type or step.get("issue_type") or "Task"
            step["summary"] = ctx.unique_summary("workflow-chain")
            step["description"] = (
                f"Created by staging workflow chain test (run_id={ctx.run_id})."
            )
            labels = list(step.get("labels") or [])
            if STAGING_LABEL not in labels:
                labels.append(STAGING_LABEL)
            step["labels"] = labels
        elif action == "assign":
            step["assignee"] = ctx.config.user.jira.email
        elif action == "comment":
            step["message"] = f"Workflow staging comment {ctx.run_id}"

    return steps


def run_workflow_lifecycle(ctx: StagingContext) -> None:
    group = "workflow"
    issue_key = None
    try:
        steps = load_staging_workflow_steps(ctx)
        results = execute_chain(
            client=ctx.client,
            config=ctx.config,
            fields_mgr=ctx.fields_mgr,
            steps=steps,
        )
        assert len(results) == 3
        issue_key = results[0]["result"].get("key")
        assert issue_key, "chain create did not return an issue key"
        ctx.record(group, "execute_chain", "PASS", f"{issue_key} (from {resolve_staging_workflow_path().name})")
    except Exception as exc:
        ctx.record(group, "execute_chain", "FAIL", str(exc))
    finally:
        if issue_key:
            try:
                delete_issue(ctx.client, issue_key)
                ctx.record(group, "cleanup_delete", "PASS", issue_key)
            except Exception as exc:
                ctx.record(group, "cleanup_delete", "FAIL", f"{issue_key}: {exc}")
