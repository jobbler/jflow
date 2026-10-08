# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from unittest.mock import MagicMock
from jflow.config import load_config
from jflow.core import JiraClient, FieldCacheManager
from jflow.core.actions.create import create_issue, validate_create_params

config = load_config()

mock_client = MagicMock(spec=JiraClient)
mock_client.post.return_value = {"id": "10000", "key": "TEST-1", "self": "https://..."}
mock_client.get.return_value = {"baseUrl": "https://test.atlassian.net"}

mock_fields = MagicMock(spec=FieldCacheManager)
mock_fields.resolve_field.return_value = None
mock_fields.resolve_field_id.side_effect = lambda x: "customfield_10020" if x == "Sprint" else None

# Explicitly test payload generation independent of user config fallbacks
result = create_issue(
    client=mock_client,
    config=config,
    fields_mgr=mock_fields,
    project="TEST_PROJ",
    issue_type="Story",
    summary="Implement API endpoints",
    description="Detailed description body",
    extra_fields={"Sprint": "Sprint 1"},
)

assert result["key"] == "TEST-1"

posted_payload = mock_client.post.call_args[0][1]
fields = posted_payload["fields"]

assert fields["project"]["key"] == "TEST_PROJ"
assert fields["issuetype"]["name"] == "Story"
assert fields["summary"] == "Implement API endpoints"
assert fields["customfield_10020"] == "Sprint 1"

missing = validate_create_params(None, None, None)
assert missing == ["project", "issue_type", "summary"]

print("✅ Phase 3 tests passed successfully!")
