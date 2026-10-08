# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
"""Atlassian OAuth 2.0 (3LO) helpers: authorize, token store, refresh, cloudId."""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from jflow.config.models import JiraCredentials

ENV_OAUTH_CLIENT_ID = "JFLOW_OAUTH_CLIENT_ID"
ENV_OAUTH_CLIENT_SECRET = "JFLOW_OAUTH_CLIENT_SECRET"

AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
TOKEN_URL = "https://auth.atlassian.com/oauth/token"
RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"

DEFAULT_REDIRECT_URI = "http://127.0.0.1:8391/callback"
DEFAULT_SCOPES = (
    "read:jira-work write:jira-work read:jira-user offline_access"
)

# Refresh a bit before real expiry to avoid edge races.
_EXPIRY_SKEW_SECONDS = 60


def default_token_path() -> Path:
    return Path.home() / ".config" / "jflow" / "oauth_tokens.json"


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: Optional[str]
    expires_at: float  # unix timestamp
    cloud_id: str
    scope: Optional[str] = None
    site_url: Optional[str] = None

    def access_expired(self) -> bool:
        return time.time() >= (self.expires_at - _EXPIRY_SKEW_SECONDS)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "cloud_id": self.cloud_id,
            "scope": self.scope,
            "site_url": self.site_url,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OAuthTokens":
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=float(data["expires_at"]),
            cloud_id=data["cloud_id"],
            scope=data.get("scope"),
            site_url=data.get("site_url"),
        )


def resolve_oauth_client(creds: JiraCredentials) -> Tuple[str, str, str]:
    """Return (client_id, client_secret, redirect_uri) with env overrides."""
    client_id = os.environ.get(ENV_OAUTH_CLIENT_ID) or creds.oauth_client_id
    client_secret = os.environ.get(ENV_OAUTH_CLIENT_SECRET) or creds.oauth_client_secret
    redirect_uri = creds.oauth_redirect_uri or DEFAULT_REDIRECT_URI
    if not client_id or not client_secret:
        raise ValueError(
            "OAuth requires oauth_client_id and oauth_client_secret "
            f"(or {ENV_OAUTH_CLIENT_ID} / {ENV_OAUTH_CLIENT_SECRET})"
        )
    return client_id, client_secret, redirect_uri


def load_tokens(path: Optional[Path] = None) -> Optional[OAuthTokens]:
    token_path = path or default_token_path()
    if not token_path.exists():
        return None
    data = json.loads(token_path.read_text())
    return OAuthTokens.from_dict(data)


def save_tokens(tokens: OAuthTokens, path: Optional[Path] = None) -> Path:
    token_path = path or default_token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(json.dumps(tokens.to_dict(), indent=2) + "\n")
    try:
        os.chmod(token_path, 0o600)
    except OSError:
        pass
    return token_path


def delete_tokens(path: Optional[Path] = None) -> bool:
    token_path = path or default_token_path()
    if token_path.exists():
        token_path.unlink()
        return True
    return False


def build_authorize_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    scopes: str = DEFAULT_SCOPES,
) -> str:
    query = urlencode(
        {
            "audience": "api.atlassian.com",
            "client_id": client_id,
            "scope": scopes,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def exchange_code_for_tokens(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> Dict[str, Any]:
    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(TOKEN_URL, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Token exchange failed ({resp.status_code}): {resp.text}"
            )
        return resp.json()


def refresh_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> Dict[str, Any]:
    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(TOKEN_URL, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Token refresh failed ({resp.status_code}): {resp.text}"
            )
        return resp.json()


def fetch_accessible_resources(access_token: str) -> List[Dict[str, Any]]:
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            RESOURCES_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"accessible-resources failed ({resp.status_code}): {resp.text}"
            )
        data = resp.json()
        return data if isinstance(data, list) else []


def pick_cloud_resource(
    resources: List[Dict[str, Any]],
    domain: Optional[str] = None,
    cloud_id_override: Optional[str] = None,
) -> Dict[str, Any]:
    if not resources:
        raise RuntimeError(
            "No accessible Atlassian sites for this token. "
            "Check app permissions and site access."
        )
    if cloud_id_override:
        for item in resources:
            if item.get("id") == cloud_id_override:
                return item
        raise RuntimeError(
            f"oauth_cloud_id '{cloud_id_override}' not in accessible-resources"
        )
    if domain:
        needle = domain.lower().rstrip("/")
        if needle.startswith("https://"):
            needle = needle[len("https://") :]
        elif needle.startswith("http://"):
            needle = needle[len("http://") :]
        for item in resources:
            url = (item.get("url") or "").lower().rstrip("/")
            if needle in url or url.endswith(needle) or needle in url.replace("https://", ""):
                return item
        # fall through to first if no match? Better to error.
        raise RuntimeError(
            f"No accessible site matching domain '{domain}'. "
            f"Available: {[r.get('url') for r in resources]}"
        )
    return resources[0]


def tokens_from_response(
    token_payload: Dict[str, Any],
    cloud_id: str,
    site_url: Optional[str] = None,
    previous: Optional[OAuthTokens] = None,
) -> OAuthTokens:
    expires_in = int(token_payload.get("expires_in") or 3600)
    refresh = token_payload.get("refresh_token")
    if not refresh and previous:
        refresh = previous.refresh_token
    return OAuthTokens(
        access_token=token_payload["access_token"],
        refresh_token=refresh,
        expires_at=time.time() + expires_in,
        cloud_id=cloud_id,
        scope=token_payload.get("scope"),
        site_url=site_url or (previous.site_url if previous else None),
    )


def get_valid_access_token(
    creds: JiraCredentials,
    path: Optional[Path] = None,
) -> Tuple[str, str]:
    """Return (access_token, cloud_id), refreshing and persisting if needed."""
    client_id, client_secret, _redirect = resolve_oauth_client(creds)
    tokens = load_tokens(path)
    if not tokens:
        raise RuntimeError(
            "No OAuth tokens found. Run `jflow auth login` first."
        )
    if tokens.access_expired():
        if not tokens.refresh_token:
            raise RuntimeError(
                "Access token expired and no refresh token is stored. "
                "Run `jflow auth login` again."
            )
        payload = refresh_access_token(
            client_id, client_secret, tokens.refresh_token
        )
        tokens = tokens_from_response(
            payload,
            cloud_id=creds.oauth_cloud_id or tokens.cloud_id,
            site_url=tokens.site_url,
            previous=tokens,
        )
        save_tokens(tokens, path)
    cloud_id = creds.oauth_cloud_id or tokens.cloud_id
    return tokens.access_token, cloud_id


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def _wait_for_callback(redirect_uri: str, state: str, timeout: float = 300.0) -> str:
    parsed = urlparse(redirect_uri)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8391
    result: Dict[str, Optional[str]] = {"code": None, "error": None}

    class Handler(_OAuthCallbackHandler):
        expected_state = state

        def do_GET(self) -> None:  # noqa: N802
            parsed_path = urlparse(self.path)
            if parsed_path.path.rstrip("/") != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            params = parse_qs(parsed_path.query)
            got_state = (params.get("state") or [None])[0]
            if got_state != self.expected_state:
                result["error"] = "state_mismatch"
                body = b"State mismatch. You can close this window."
                self.send_response(400)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if "error" in params:
                result["error"] = (params.get("error") or ["unknown"])[0]
                body = f"Authorization failed: {result['error']}".encode()
                self.send_response(400)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            result["code"] = (params.get("code") or [None])[0]
            body = (
                b"Authorization successful. You can close this window "
                b"and return to the terminal."
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer((host, port), Handler)
    server.timeout = 1.0
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            server.handle_request()
            if result["code"]:
                return result["code"]
            if result["error"]:
                raise RuntimeError(f"OAuth callback error: {result['error']}")
        raise RuntimeError("Timed out waiting for OAuth callback")
    finally:
        server.server_close()


def login(
    creds: JiraCredentials,
    *,
    open_browser: bool = True,
    token_path: Optional[Path] = None,
    scopes: str = DEFAULT_SCOPES,
) -> OAuthTokens:
    """Run 3LO authorization code flow and persist tokens."""
    client_id, client_secret, redirect_uri = resolve_oauth_client(creds)
    state = secrets.token_urlsafe(32)
    auth_url = build_authorize_url(client_id, redirect_uri, state, scopes=scopes)
    print(f"Authorize URL:\n{auth_url}\n", flush=True)

    def _open() -> None:
        time.sleep(0.4)
        if open_browser:
            webbrowser.open(auth_url)

    opener = threading.Thread(target=_open, daemon=True)
    opener.start()

    code = _wait_for_callback(redirect_uri, state)
    token_payload = exchange_code_for_tokens(
        client_id, client_secret, code, redirect_uri
    )
    access = token_payload["access_token"]
    resources = fetch_accessible_resources(access)
    resource = pick_cloud_resource(
        resources,
        domain=creds.domain,
        cloud_id_override=creds.oauth_cloud_id,
    )
    cloud_id = resource["id"]
    site_url = resource.get("url")
    tokens = tokens_from_response(
        token_payload, cloud_id=cloud_id, site_url=site_url
    )
    save_tokens(tokens, token_path)
    return tokens


def auth_status_dict(
    creds: JiraCredentials,
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    tokens = load_tokens(path)
    mode = creds.auth
    info: Dict[str, Any] = {
        "configured_auth": mode,
        "token_file": str(path or default_token_path()),
        "has_tokens": tokens is not None,
    }
    if tokens:
        info.update(
            {
                "cloud_id": tokens.cloud_id,
                "site_url": tokens.site_url,
                "expires_at": tokens.expires_at,
                "access_expired": tokens.access_expired(),
                "has_refresh_token": bool(tokens.refresh_token),
                "scope": tokens.scope,
            }
        )
    return info
