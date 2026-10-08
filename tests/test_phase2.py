# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Grok 4.5).
# ==============================================================================
from pathlib import Path
from unittest.mock import MagicMock
from jflow.config import load_config
from jflow.core import JiraClient, FieldCacheManager

# 1. Verify client initialization from configuration
config = load_config()
client = JiraClient.from_settings(config.user)
assert client.base_url.startswith("http"), "Client base_url must be a valid HTTP(S) URL"

# 2. Test cache resolution using a non-existent temp path to force API invocation
mock_client = MagicMock(spec=JiraClient)
mock_client.get.return_value = [
    {"id": "summary", "name": "Summary", "custom": False, "schema": {"type": "string", "system": "summary"}},
    {
        "id": "customfield_10020",
        "name": "Sprint",
        "custom": True,
        "schema": {"type": "array", "items": "json", "custom": "com.pyxis.greenhopper.jira:gh-sprint"},
    },
]

temp_cache_path = Path("/tmp/jflow_test_fields_cache.json")
if temp_cache_path.exists():
    temp_cache_path.unlink()

cache_mgr = FieldCacheManager(mock_client, cache_path=temp_cache_path)
resolved_id = cache_mgr.resolve_field_id("Sprint")

assert resolved_id == "customfield_10020"
mock_client.get.assert_called_with("/rest/api/3/field")

meta = cache_mgr.resolve_field("Sprint")
assert meta is not None
assert meta["id"] == "customfield_10020"
assert meta["schema"]["type"] == "array"

# Old flat cache migrates on load
flat_path = Path("/tmp/jflow_test_fields_cache_flat.json")
flat_path.write_text('{"Sprint": "customfield_10020"}', encoding="utf-8")
cache_mgr2 = FieldCacheManager(mock_client, cache_path=flat_path)
assert cache_mgr2.resolve_field_id("Sprint") == "customfield_10020"

# Clean up temp files
for p in (temp_cache_path, flat_path):
    if p.exists():
        p.unlink()

print("✅ Phase 2 tests passed successfully!")
