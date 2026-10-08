# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from jflow.config.models import AppConfig
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager

VALID_GROUPS = ("system", "search", "issue", "sprint", "workflow")
STAGING_LABEL = "jflow-staging"
SUMMARY_PREFIX = "[jflow-staging]"


@dataclass
class CaseResult:
    group: str
    name: str
    status: str  # PASS | FAIL | SKIP
    detail: str = ""


@dataclass
class StagingContext:
    config: AppConfig
    client: JiraClient
    fields_mgr: FieldCacheManager
    project: str
    board_id: Optional[int]
    lifecycle: bool
    run_id: str
    results: List[CaseResult] = field(default_factory=list)

    def record(self, group: str, name: str, status: str, detail: str = "") -> None:
        self.results.append(CaseResult(group=group, name=name, status=status, detail=detail))

    def unique_summary(self, suffix: str) -> str:
        return f"{SUMMARY_PREFIX} {suffix} ({self.run_id})"


def delete_issue(client: JiraClient, issue_key: str) -> None:
    """Best-effort permanent delete of a staging issue."""
    client.delete(f"/rest/api/3/issue/{issue_key}?deleteSubtasks=true")
