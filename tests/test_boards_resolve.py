# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
from unittest.mock import MagicMock, call

from jflow.core.actions.sprint import list_boards, resolve_board
from jflow.core.client import JiraClient

mock_client = MagicMock(spec=JiraClient)

# Numeric id / string
assert resolve_board(mock_client, "42") == 42
assert resolve_board(mock_client, 7) == 7
mock_client.get.assert_not_called()

# Name resolve (API may return substring hits; resolve keeps exact match)
mock_client.get.return_value = {
    "values": [
        {"id": 10, "name": "Alpha Board", "type": "scrum", "location": {"projectKey": "ALP"}},
        {"id": 11, "name": "Beta Board", "type": "kanban", "location": {}},
    ],
    "isLast": True,
}
assert resolve_board(mock_client, "alpha board") == 10

# Missing
mock_client.get.return_value = {"values": [], "isLast": True}
try:
    resolve_board(mock_client, "Missing")
    raise AssertionError("expected ValueError for missing board")
except ValueError as exc:
    assert "No board found" in str(exc)

# Ambiguous
mock_client.get.return_value = {
    "values": [
        {"id": 1, "name": "Same", "type": "scrum"},
        {"id": 2, "name": "Same", "type": "scrum"},
    ],
    "isLast": True,
}
try:
    resolve_board(mock_client, "Same")
    raise AssertionError("expected ValueError for ambiguous board")
except ValueError as exc:
    assert "Ambiguous" in str(exc)

# list_boards shape (uncapped)
mock_client.reset_mock()
mock_client.get.return_value = {
    "values": [
        {
            "id": 5,
            "name": "PROJ board",
            "type": "scrum",
            "location": {"projectKey": "PROJ"},
        }
    ],
    "isLast": True,
}
boards = list_boards(mock_client)
assert boards == [
    {"id": 5, "name": "PROJ board", "type": "scrum", "projectKey": "PROJ"}
]
mock_client.get.assert_called_with(
    "/rest/agile/1.0/board",
    params={"startAt": 0, "maxResults": 50},
)

# Multi-page list-all
mock_client.reset_mock()
mock_client.get.side_effect = [
    {
        "values": [{"id": 1, "name": "A", "type": "scrum", "location": {}}],
        "isLast": False,
    },
    {
        "values": [{"id": 2, "name": "B", "type": "kanban", "location": {}}],
        "isLast": True,
    },
]
paged = list_boards(mock_client)
assert [b["id"] for b in paged] == [1, 2]
assert mock_client.get.call_args_list == [
    call("/rest/agile/1.0/board", params={"startAt": 0, "maxResults": 50}),
    call("/rest/agile/1.0/board", params={"startAt": 1, "maxResults": 50}),
]

# Search keeps substring matches (no exact-only filter in list_boards)
mock_client.reset_mock()
mock_client.get.side_effect = None
mock_client.get.return_value = {
    "values": [
        {"id": 10, "name": "Alpha Board", "type": "scrum", "location": {}},
        {"id": 12, "name": "Alpha Extra", "type": "scrum", "location": {}},
    ],
    "isLast": True,
}
search_hits = list_boards(mock_client, name="Alpha", max_results=50)
assert len(search_hits) == 2
mock_client.get.assert_called_with(
    "/rest/agile/1.0/board",
    params={"startAt": 0, "maxResults": 50, "name": "Alpha"},
)

# Limit caps list-all
mock_client.reset_mock()
mock_client.get.return_value = {
    "values": [
        {"id": i, "name": f"B{i}", "type": "scrum", "location": {}}
        for i in range(1, 6)
    ],
    "isLast": False,
}
limited = list_boards(mock_client, max_results=3)
assert [b["id"] for b in limited] == [1, 2, 3]

print("✅ Board list/resolve tests passed successfully!")
