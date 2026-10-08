# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from unittest.mock import MagicMock
from jflow.core import JiraClient
from jflow.core.fields import FieldCacheManager
from jflow.core.actions.fields import (
    update_due_date,
    update_parent,
    update_components,
    update_story_points,
    set_blocked,
)

mock_client = MagicMock(spec=JiraClient)
mock_client.put.return_value = None

fields_mgr = MagicMock(spec=FieldCacheManager)
def mock_field_resolver(name):
    if name in ["Story Points", "Story point estimate"]:
        return "customfield_10016"
    if name == "Flagged":
        return "customfield_10021"
    return None

def mock_resolve_field(name):
    if name == "Blocked":
        return {
            "id": "customfield_10102",
            "name": "Blocked",
            "schema": {
                "type": "option",
                "custom": "com.atlassian.jira.plugin.system.customfieldtypes:select",
            },
        }
    if name == "Flagged":
        return {
            "id": "customfield_10021",
            "name": "Flagged",
            "schema": {
                "type": "array",
                "items": "option",
                "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multicheckboxes",
            },
        }
    return None

fields_mgr.resolve_field_id.side_effect = mock_field_resolver
fields_mgr.resolve_field.side_effect = mock_resolve_field

# 1. Test Due Date Update
res_due = update_due_date(mock_client, "PROJ-10", "2026-10-01")
assert res_due["duedate"] == "2026-10-01"

# 2. Test Parent Update
res_parent = update_parent(mock_client, "PROJ-10", "PROJ-1")
assert res_parent["parent"] == "PROJ-1"

# 3. Test Components
res_comp = update_components(mock_client, "PROJ-10", ["API", "UI"])
assert res_comp["components"] == ["API", "UI"]

# 4. Test Story Points
res_sp = update_story_points(mock_client, fields_mgr, "PROJ-10", 5.0)
assert res_sp["story_points"] == 5.0

# 5. Test Blocked select (True/False), preferred over Flagged
res_blocked = set_blocked(mock_client, fields_mgr, "PROJ-10", True)
assert res_blocked["blocked"] is True
assert res_blocked["field_id"] == "customfield_10102"
mock_client.put.assert_called_with(
    "/rest/api/3/issue/PROJ-10",
    payload={"fields": {"customfield_10102": {"value": "True"}}},
)

print("✅ Phase 8 Extended Field Operations (Blocked refactor) tests passed successfully!")
