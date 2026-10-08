# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from jflow.version import __version__
from jflow.core import JiraClient
from jflow.core.actions.system import get_myself, get_server_info, init_config, build_status

# 1. Version Check
assert __version__ == "0.2.7"

# 2. Test Get Myself (friendly keys)
mock_client = MagicMock(spec=JiraClient)
mock_client.get.return_value = {
    "accountId": "acc-12345",
    "displayName": "Test User",
    "emailAddress": "test@example.com",
    "active": True,
    "timeZone": "UTC",
}

me = get_myself(mock_client)
assert me["account_id"] == "acc-12345"
assert me["name"] == "Test User"
assert me["email"] == "test@example.com"
assert me["timezone"] == "UTC"
mock_client.get.assert_called_with("/rest/api/3/myself")

# 3. Test Get Server Info (friendly keys)
mock_client.get.return_value = {
    "baseUrl": "https://test.atlassian.net",
    "version": "1001.0.0-SNAPSHOT",
    "deploymentType": "Cloud",
    "buildNumber": 100000,
    "serverTime": "2026-09-16T12:00:00.000+0000",
}

info = get_server_info(mock_client)
assert info["deployment"] == "Cloud"
assert info["url"] == "https://test.atlassian.net"
assert info["build"] == 100000
mock_client.get.assert_called_with("/rest/api/3/serverInfo")

# 4. build_status sections
mock_client.get.side_effect = [
    {
        "accountId": "acc-12345",
        "displayName": "Test User",
        "emailAddress": "test@example.com",
        "active": True,
        "timeZone": "UTC",
    },
    {
        "baseUrl": "https://test.atlassian.net",
        "version": "1001.0.0-SNAPSHOT",
        "deploymentType": "Cloud",
        "buildNumber": 100000,
        "serverTime": "2026-09-16T12:00:00.000+0000",
    },
]
status = build_status(mock_client, __version__)
assert status["client"]["version"] == __version__
assert status["me"]["name"] == "Test User"
assert status["server"]["url"] == "https://test.atlassian.net"

# 5. Test Init Config
with tempfile.TemporaryDirectory() as tmpdir:
    tmp_path = Path(tmpdir)
    res = init_config(target_dir=tmp_path)

    assert res["status"] == "Configuration Initialized"
    assert (tmp_path / "user.yaml").exists()
    assert not (tmp_path / "global.yaml").exists()
    assert len(res["created"]) == 1
    user_text = (tmp_path / "user.yaml").read_text()
    assert 'output_format: "markdown"' in user_text
    assert "project-open:" in user_text

    # Second run without force skips creation
    res_skip = init_config(target_dir=tmp_path)
    assert len(res_skip["skipped"]) == 1

print("✅ Phase 7 System Utilities & Metadata tests passed successfully!")
