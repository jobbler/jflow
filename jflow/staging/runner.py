# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Updated in whole or in part by AI using Cursor (Composer).
# ==============================================================================
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set

from jflow.config.loader import load_config
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager
from jflow.staging.cases import issue as issue_cases
from jflow.staging.cases import search as search_cases
from jflow.staging.cases import sprint as sprint_cases
from jflow.staging.cases import system as system_cases
from jflow.staging.cases import workflow as workflow_cases
from jflow.staging.context import VALID_GROUPS, StagingContext


def parse_groups(group_arg: str) -> Set[str]:
    raw = [g.strip().lower() for g in group_arg.split(",") if g.strip()]
    if not raw or raw == ["all"]:
        return set(VALID_GROUPS)
    unknown = [g for g in raw if g not in VALID_GROUPS]
    if unknown:
        raise ValueError(
            f"Unknown group(s): {', '.join(unknown)}. Valid: {', '.join(VALID_GROUPS)}, all"
        )
    return set(raw)


def _require_existing_paths(user_yaml: str) -> None:
    u = Path(user_yaml).expanduser()
    if not u.is_file():
        raise FileNotFoundError(f"--user-yaml file not found: {u}")


def run_staging_tests(
    user_yaml: str,
    lifecycle: bool = False,
    groups: Optional[Iterable[str]] = None,
    board_id: Optional[int] = None,
    project: Optional[str] = None,
) -> int:
    """Execute staging tests. Returns process exit code (0 = success)."""
    _require_existing_paths(user_yaml)

    # Explicit paths only — no home-dir default for this runner.
    config = load_config(user_settings_path=user_yaml)
    client = JiraClient.from_settings(config.user)
    fields_mgr = FieldCacheManager(client)

    selected = set(groups) if groups is not None else set(VALID_GROUPS)
    proj = project or config.get_default_project()
    if not proj:
        raise ValueError(
            "Project key required: set defaults.project in user.yaml or pass --project"
        )

    if "sprint" in selected and board_id is None:
        raise ValueError("--board-id is required when running the sprint group")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ctx = StagingContext(
        config=config,
        client=client,
        fields_mgr=fields_mgr,
        project=proj,
        board_id=board_id,
        lifecycle=lifecycle,
        run_id=run_id,
    )

    mode = "lifecycle" if lifecycle else "read-only"
    print(f"Staging tests | mode={mode} | groups={','.join(sorted(selected))} | project={proj}")
    print(f"user.yaml={user_yaml}")
    if board_id is not None:
        print(f"board_id={board_id}")
    print("-" * 60)

    if "system" in selected:
        system_cases.run_system_smoke(ctx)

    if "search" in selected:
        search_cases.run_search_smoke(ctx)

    if "issue" in selected:
        issue_cases.run_issue_smoke(ctx)
        if lifecycle:
            issue_cases.run_issue_lifecycle(ctx)

    if "sprint" in selected:
        sprint_cases.run_sprint_smoke(ctx)
        if lifecycle:
            sprint_cases.run_sprint_lifecycle(ctx)

    if "workflow" in selected:
        if lifecycle:
            workflow_cases.run_workflow_lifecycle(ctx)
        else:
            ctx.record("workflow", "execute_chain", "SKIP", "needs --lifecycle")

    return _print_summary(ctx.results)


def _print_summary(results: Sequence) -> int:
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    skipped = sum(1 for r in results if r.status == "SKIP")

    print("-" * 60)
    for r in results:
        detail = f" — {r.detail}" if r.detail else ""
        print(f"[{r.status}] {r.group}/{r.name}{detail}")

    print("-" * 60)
    print(f"Summary: {passed} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0
