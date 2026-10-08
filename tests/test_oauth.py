# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
"""OAuth helpers and dual-mode JiraClient tests."""
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from jflow.config.models import JiraCredentials
from jflow.core.client import JiraClient
from jflow.core.oauth import (
    OAuthTokens,
    build_authorize_url,
    pick_cloud_resource,
    tokens_from_response,
    save_tokens,
    load_tokens,
    delete_tokens,
    get_valid_access_token,
)


def test_build_authorize_url_contains_required_params():
    url = build_authorize_url("cid", "http://127.0.0.1:8391/callback", "stategood")
    assert "auth.atlassian.com/authorize" in url
    assert "client_id=cid" in url
    assert "state=stategood" in url
    assert "audience=api.atlassian.com" in url
    assert "offline_access" in url
    assert "prompt=consent" in url


def test_pick_cloud_resource_by_domain():
    resources = [
        {"id": "a", "url": "https://other.atlassian.net"},
        {"id": "b", "url": "https://mine.atlassian.net"},
    ]
    picked = pick_cloud_resource(resources, domain="mine.atlassian.net")
    assert picked["id"] == "b"


def test_pick_cloud_resource_override():
    resources = [{"id": "a", "url": "https://a.atlassian.net"}]
    picked = pick_cloud_resource(resources, cloud_id_override="a")
    assert picked["id"] == "a"


def test_tokens_roundtrip(tmp_path: Path = None):
    path = Path("/tmp/jflow-oauth-test-tokens.json")
    try:
        tokens = OAuthTokens(
            access_token="acc",
            refresh_token="ref",
            expires_at=time.time() + 3600,
            cloud_id="cloud-1",
            site_url="https://x.atlassian.net",
        )
        save_tokens(tokens, path)
        loaded = load_tokens(path)
        assert loaded is not None
        assert loaded.access_token == "acc"
        assert loaded.cloud_id == "cloud-1"
        assert delete_tokens(path) is True
        assert load_tokens(path) is None
    finally:
        if path.exists():
            path.unlink()


def test_tokens_from_response_keeps_previous_refresh():
    prev = OAuthTokens(
        access_token="old",
        refresh_token="keep-me",
        expires_at=0,
        cloud_id="c1",
    )
    payload = {"access_token": "new", "expires_in": 100}
    tokens = tokens_from_response(payload, cloud_id="c1", previous=prev)
    assert tokens.access_token == "new"
    assert tokens.refresh_token == "keep-me"


def test_jira_credentials_api_token_requires_fields():
    try:
        JiraCredentials(auth="api_token", domain="x.atlassian.net")
        assert False, "expected validation error"
    except Exception:
        pass
    ok = JiraCredentials(
        auth="api_token",
        domain="x.atlassian.net",
        email="a@b.com",
        api_token="tok",
    )
    assert ok.auth == "api_token"


def test_jira_credentials_oauth_requires_client():
    try:
        JiraCredentials(auth="oauth", domain="x.atlassian.net")
        assert False, "expected validation error"
    except Exception:
        pass
    ok = JiraCredentials(
        auth="oauth",
        domain="x.atlassian.net",
        oauth_client_id="cid",
        oauth_client_secret="sec",
    )
    assert ok.oauth_client_id == "cid"


def test_client_from_settings_api_token():
    from jflow.config.models import UserConfig, Defaults

    settings = UserConfig(
        jira=JiraCredentials(
            domain="example.atlassian.net",
            email="a@b.com",
            api_token="tok",
        ),
        defaults=Defaults(),
    )
    client = JiraClient.from_settings(settings)
    assert "example.atlassian.net" in client.base_url
    assert client._auth == ("a@b.com", "tok")
    client.client.close()


def test_client_from_settings_oauth():
    from jflow.config.models import UserConfig, Defaults

    settings = UserConfig(
        jira=JiraCredentials(
            auth="oauth",
            domain="example.atlassian.net",
            oauth_client_id="cid",
            oauth_client_secret="sec",
            oauth_cloud_id="cloud-xyz",
        ),
        defaults=Defaults(),
    )

    def fake_get(creds, path=None):
        return "bearer-token", "cloud-xyz"

    with patch("jflow.core.client.get_valid_access_token", side_effect=fake_get):
        client = JiraClient.from_settings(settings)
    assert client.base_url == "https://api.atlassian.com/ex/jira/cloud-xyz"
    assert "Bearer" in client.client.headers.get("Authorization", "")
    client.client.close()


def test_get_valid_access_token_refreshes(tmp_path=None):
    path = Path("/tmp/jflow-oauth-refresh-test.json")
    try:
        tokens = OAuthTokens(
            access_token="old-acc",
            refresh_token="ref",
            expires_at=0,  # expired
            cloud_id="cloud-1",
        )
        save_tokens(tokens, path)
        creds = JiraCredentials(
            auth="oauth",
            oauth_client_id="cid",
            oauth_client_secret="sec",
        )

        def fake_refresh(client_id, client_secret, refresh_token):
            assert refresh_token == "ref"
            return {
                "access_token": "new-acc",
                "refresh_token": "new-ref",
                "expires_in": 3600,
            }

        with patch("jflow.core.oauth.refresh_access_token", side_effect=fake_refresh):
            access, cloud = get_valid_access_token(creds, path=path)
        assert access == "new-acc"
        assert cloud == "cloud-1"
        loaded = load_tokens(path)
        assert loaded is not None
        assert loaded.refresh_token == "new-ref"
    finally:
        if path.exists():
            path.unlink()


if __name__ == "__main__":
    test_build_authorize_url_contains_required_params()
    test_pick_cloud_resource_by_domain()
    test_pick_cloud_resource_override()
    test_tokens_roundtrip()
    test_tokens_from_response_keeps_previous_refresh()
    test_jira_credentials_api_token_requires_fields()
    test_jira_credentials_oauth_requires_client()
    test_client_from_settings_api_token()
    test_client_from_settings_oauth()
    test_get_valid_access_token_refreshes()
    print("✅ OAuth tests passed successfully!")
