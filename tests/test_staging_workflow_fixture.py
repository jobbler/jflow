# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from unittest.mock import MagicMock

from jflow.config.models import (
    AppConfig,
    JiraCredentials,
    UserConfig,
    Defaults,
)
from jflow.core.client import JiraClient
from jflow.core.fields import FieldCacheManager
from jflow.staging.cases.workflow import (
    load_staging_workflow_steps,
    resolve_staging_workflow_path,
)
from jflow.staging.context import StagingContext

path = resolve_staging_workflow_path()
assert path.name == "staging_create_assign_comment.json"
assert path.is_file()

config = AppConfig(
    user=UserConfig(
        jira=JiraCredentials(
            domain="test.atlassian.net",
            email="staging@example.com",
            api_token="tok",
        ),
        defaults=Defaults(project="STAG", issue_type="Task"),
    ),
)
ctx = StagingContext(
    config=config,
    client=MagicMock(spec=JiraClient),
    fields_mgr=MagicMock(spec=FieldCacheManager),
    project="STAG",
    board_id=None,
    lifecycle=True,
    run_id="TESTRUN",
)

steps = load_staging_workflow_steps(ctx)
assert len(steps) == 3
assert steps[0]["action"] == "create"
assert steps[0]["project"] == "STAG"
assert "TESTRUN" in steps[0]["summary"] or "workflow-chain" in steps[0]["summary"]
assert steps[1]["assignee"] == "staging@example.com"
assert "TESTRUN" in steps[2]["message"]

print("✅ Staging workflow fixture load tests passed successfully!")
