# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Composer).
# ==============================================================================
"""JiraClient handles empty success bodies (e.g. POST /issueLink → 201)."""
from unittest.mock import MagicMock

from jflow.core.client import JiraClient


def _client() -> JiraClient:
    return JiraClient("https://example.atlassian.net", auth=("a", "b"))


def test_204_returns_none():
    client = _client()
    resp = MagicMock()
    resp.status_code = 204
    resp.content = b""
    resp.raise_for_status = MagicMock()
    assert client._handle_response(resp) is None


def test_201_empty_body_returns_none():
    client = _client()
    resp = MagicMock()
    resp.status_code = 201
    resp.content = b""
    resp.raise_for_status = MagicMock()
    assert client._handle_response(resp) is None


def test_200_json_parsed():
    client = _client()
    resp = MagicMock()
    resp.status_code = 200
    resp.content = b'{"ok": true}'
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"ok": True}
    assert client._handle_response(resp) == {"ok": True}


test_204_returns_none()
test_201_empty_body_returns_none()
test_200_json_parsed()
print("✅ client empty-body tests passed successfully!")
