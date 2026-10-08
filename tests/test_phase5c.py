# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from unittest.mock import MagicMock
from jflow.core import JiraClient
from jflow.core.actions.labels import add_labels, remove_labels, set_labels

mock_client = MagicMock(spec=JiraClient)
mock_client.put.return_value = None

# 1. Test Add Labels
res_add = add_labels(mock_client, "PROJ-101", ["backend", "urgent"])
assert res_add["status"] == "Labels Added"
mock_client.put.assert_called_with(
    "/rest/api/3/issue/PROJ-101",
    payload={"update": {"labels": [{"add": "backend"}, {"add": "urgent"}]}},
)

# 2. Test Remove Labels
res_rem = remove_labels(mock_client, "PROJ-101", ["deprecated"])
assert res_rem["status"] == "Labels Removed"
mock_client.put.assert_called_with(
    "/rest/api/3/issue/PROJ-101",
    payload={"update": {"labels": [{"remove": "deprecated"}]}},
)

# 3. Test Replace Labels
res_set = set_labels(mock_client, "PROJ-101", ["frontend", "v2"])
assert res_set["status"] == "Labels Updated"
mock_client.put.assert_called_with(
    "/rest/api/3/issue/PROJ-101",
    payload={"fields": {"labels": ["frontend", "v2"]}},
)

print("✅ Phase 5c Label Operations tests passed successfully!")
