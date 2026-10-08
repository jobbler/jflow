# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from unittest.mock import MagicMock
from jflow.config.models import AppConfig, IssueTemplate, UserConfig, JiraCredentials
from jflow.core import JiraClient
from jflow.core.fields import FieldCacheManager
from jflow.core.templates import process_template
from jflow.core.actions.create import create_issue

user_cfg = UserConfig(
    jira=JiraCredentials(domain="test.atlassian.net", email="a@b.com", api_token="tok"),
    templates={
        "bug_report": IssueTemplate(
            summary="[BUG] {component}: Issue in {env}",
            description="Steps to reproduce:\n{steps}",
            issue_type="Bug",
            labels=["automated-bug"],
        )
    },
)
config = AppConfig(user=user_cfg)

# 1. Test Template Processing & Placeholder Rendering
rendered = process_template(
    config,
    "bug_report",
    {"component": "Auth", "env": "Production", "steps": "1. Login 2. Crash"},
)
assert rendered.summary == "[BUG] Auth: Issue in Production"
assert "1. Login 2. Crash" in rendered.description
assert rendered.labels == ["automated-bug"]

# 2. Test Integration with Create Action
mock_client = MagicMock(spec=JiraClient)
mock_client.post.return_value = {"id": "1001", "key": "PROJ-200", "self": "http://example"}
mock_client.get.return_value = {"baseUrl": "https://test.atlassian.net"}

fields_mgr = MagicMock(spec=FieldCacheManager)

res = create_issue(
    client=mock_client,
    config=config,
    fields_mgr=fields_mgr,
    project="PROJ",
    template_name="bug_report",
    template_vars={"component": "Payment", "env": "Staging", "steps": "Checkout timeout"},
)

assert res["key"] == "PROJ-200"
assert res["url"] == "https://test.atlassian.net/browse/PROJ-200"
create_payload = mock_client.post.call_args[0][1]
assert create_payload["fields"]["summary"] == "[BUG] Payment: Issue in Staging"

print("✅ Phase 3 Template Engine tests passed successfully!")
