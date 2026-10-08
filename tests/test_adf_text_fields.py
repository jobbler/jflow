# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from unittest.mock import MagicMock

from jflow.core.adf import collapse_to_single_line, text_to_adf_doc
from jflow.core.client import JiraClient
from jflow.core.actions.fields import update_summary, update_description
from jflow.core.actions.status_comment import add_comment

# 1. ADF multiline + blank lines
doc = text_to_adf_doc("Line 1\n\nLine 3")
assert doc["type"] == "doc"
assert len(doc["content"]) == 3
assert doc["content"][0]["content"][0]["text"] == "Line 1"
assert "content" not in doc["content"][1]
assert doc["content"][2]["content"][0]["text"] == "Line 3"

# 2. CRLF normalization
doc_crlf = text_to_adf_doc("A\r\nB")
assert len(doc_crlf["content"]) == 2
assert doc_crlf["content"][0]["content"][0]["text"] == "A"
assert doc_crlf["content"][1]["content"][0]["text"] == "B"

# 3. collapse summary newlines
assert collapse_to_single_line("Hello\nWorld") == "Hello World"
assert collapse_to_single_line("  a   b  ") == "a b"

# 4. update_summary / update_description payloads
mock_client = MagicMock(spec=JiraClient)
mock_client.put.return_value = None

res_sum = update_summary(mock_client, "PROJ-1", "New\ntitle")
assert res_sum["summary"] == "New title"
mock_client.put.assert_called_with(
    "/rest/api/3/issue/PROJ-1",
    payload={"fields": {"summary": "New title"}},
)

update_description(mock_client, "PROJ-1", "A\nB")
payload = mock_client.put.call_args.kwargs["payload"]
assert payload["fields"]["description"]["content"][0]["content"][0]["text"] == "A"
assert payload["fields"]["description"]["content"][1]["content"][0]["text"] == "B"

update_description(mock_client, "PROJ-1", "")
payload = mock_client.put.call_args.kwargs["payload"]
assert payload["fields"]["description"] is None

# 5. Multiline comment ADF
mock_client.post.return_value = {"id": "9"}
add_comment(mock_client, "PROJ-1", "One\nTwo")
comment_payload = mock_client.post.call_args.kwargs["payload"]
assert len(comment_payload["body"]["content"]) == 2
assert comment_payload["body"]["content"][0]["content"][0]["text"] == "One"
assert comment_payload["body"]["content"][1]["content"][0]["text"] == "Two"

print("✅ ADF and text-field update tests passed successfully!")
