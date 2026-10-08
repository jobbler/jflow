# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Composer).
# ==============================================================================
from typing import Any, Dict, List, Optional
from jflow.config.models import AppConfig
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager
from jflow.core.actions.create import CURRENT_SPRINT_TOKEN, create_issue
from jflow.core.actions.assignee import assign_issue, set_reporter
from jflow.core.actions.status_comment import transition_issue, add_comment
from jflow.core.actions.labels import add_labels
from jflow.core.actions.sprint import add_issue_to_sprint, resolve_board
from jflow.core.actions.fields import update_field, update_summary, update_description
from jflow.core.actions.run_cmd import run_external_command
from jflow.core.templates import apply_workflow_vars


def execute_chain(
    client: JiraClient,
    config: AppConfig,
    fields_mgr: FieldCacheManager,
    steps: List[Dict[str, Any]],
    initial_key: Optional[str] = None,
    variables: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Executes a sequence of Jira actions, reusing the active issue key across steps."""
    results = []
    current_key = initial_key
    steps = apply_workflow_vars(steps, variables)

    for step_index, step in enumerate(steps):
        action = step.get("action")
        if not action:
            raise ValueError("Workflow step missing 'action' parameter.")

        issue_key = step.get("issue_key") or current_key

        if action == "create":
            res = create_issue(
                client=client,
                config=config,
                fields_mgr=fields_mgr,
                project=step.get("project"),
                issue_type=step.get("issue_type"),
                summary=step.get("summary"),
                description=step.get("description"),
                template_name=step.get("template_name"),
                template_vars=step.get("template_vars"),
                labels=step.get("labels"),
                extra_fields=step.get("extra_fields"),
            )
            current_key = res.get("key")
            results.append({"step": "create", "result": res})

        elif action == "assign":
            if not issue_key:
                raise ValueError("Action 'assign' requires an active issue key.")
            res = assign_issue(client, issue_key=issue_key, assignee=step.get("assignee"))
            results.append({"step": "assign", "result": res})

        elif action == "reporter":
            if not issue_key:
                raise ValueError("Action 'reporter' requires an active issue key.")
            res = set_reporter(client, issue_key=issue_key, reporter=step.get("reporter"))
            results.append({"step": "reporter", "result": res})

        elif action == "transition":
            if not issue_key:
                raise ValueError("Action 'transition' requires an active issue key.")
            res = transition_issue(client, issue_key=issue_key, target_status=step.get("status"))
            results.append({"step": "transition", "result": res})

        elif action == "comment":
            if not issue_key:
                raise ValueError("Action 'comment' requires an active issue key.")
            msg = step.get("message") or step.get("comment_text", "")
            res = add_comment(client, issue_key=issue_key, comment_text=msg)
            results.append({"step": "comment", "result": res})

        elif action == "label":
            if not issue_key:
                raise ValueError("Action 'label' requires an active issue key.")
            labels = step.get("labels", [])
            res = add_labels(client, issue_key=issue_key, labels=labels)
            results.append({"step": "label", "result": res})

        elif action == "sprint":
            if not issue_key:
                raise ValueError("Action 'sprint' requires an active issue key.")
            sprint_id = step.get("sprint_id")
            use_current = (
                sprint_id is None
                or sprint_id == ""
                or sprint_id == CURRENT_SPRINT_TOKEN
            )
            if use_current:
                board = config.get_default_board()
                if not board:
                    raise ValueError(
                        f"Action 'sprint' used {CURRENT_SPRINT_TOKEN} (or omitted "
                        "sprint_id) but defaults.board is not set in user.yaml."
                    )
                board_id = resolve_board(client, board)
                res = add_issue_to_sprint(
                    client, issue_key=issue_key, board_id=board_id
                )
            else:
                try:
                    numeric_id = int(sprint_id)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        "Action 'sprint' requires numeric 'sprint_id' or "
                        f"'{CURRENT_SPRINT_TOKEN}'."
                    ) from exc
                res = add_issue_to_sprint(
                    client, issue_key=issue_key, sprint_id=numeric_id
                )
            results.append({"step": "sprint", "result": res})

        elif action == "summary":
            if not issue_key:
                raise ValueError("Action 'summary' requires an active issue key.")
            summary = step.get("summary")
            if summary is None:
                raise ValueError("Action 'summary' requires 'summary'.")
            res = update_summary(client, issue_key=issue_key, summary=summary)
            results.append({"step": "summary", "result": res})

        elif action == "description":
            if not issue_key:
                raise ValueError("Action 'description' requires an active issue key.")
            desc = step.get("description")
            if desc is None:
                desc = step.get("message")
            res = update_description(client, issue_key=issue_key, description=desc)
            results.append({"step": "description", "result": res})

        elif action == "field":
            if not issue_key:
                raise ValueError("Action 'field' requires an active issue key.")
            field_name = step.get("field") or step.get("name")
            if not field_name:
                raise ValueError("Action 'field' requires 'field' (or 'name').")
            if "value" not in step:
                raise ValueError("Action 'field' requires 'value'.")
            res = update_field(
                client,
                fields_mgr=fields_mgr,
                issue_key=issue_key,
                field=field_name,
                value=step.get("value"),
            )
            results.append({"step": "field", "result": res})

        elif action == "run":
            fail_on_error = step.get("fail_on_error", True)
            if not isinstance(fail_on_error, bool):
                fail_on_error = bool(fail_on_error)
            res = run_external_command(
                command=step.get("command"),
                issue_key=issue_key,
                step_index=step_index,
                prior_results=list(results),
                format=step.get("format") or "json",
                timeout_seconds=step.get("timeout_seconds"),
                fail_on_error=fail_on_error,
                cwd=step.get("cwd"),
                extra=step.get("extra"),
            )
            results.append({"step": "run", "result": res})

        else:
            raise ValueError(f"Unknown action '{action}' in workflow chain.")

    return results
