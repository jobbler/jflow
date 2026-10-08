# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
from typing import Any, Callable, Dict, Optional

import httpx

from jflow.config.models import UserSettings
from jflow.core.oauth import get_valid_access_token


class JiraClient:
    """HTTP client for Jira Cloud (API token Basic Auth or OAuth Bearer)."""

    def __init__(
        self,
        base_url: str,
        *,
        auth: Optional[tuple] = None,
        headers: Optional[Dict[str, str]] = None,
        token_provider: Optional[Callable[[], str]] = None,
        oauth_refresh: Optional[Callable[[], None]] = None,
    ):
        cleaned = base_url.rstrip("/")
        if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
            cleaned = f"https://{cleaned}"
        self.base_url = cleaned
        self._token_provider = token_provider
        self._oauth_refresh = oauth_refresh
        self._auth = auth

        default_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if headers:
            default_headers.update(headers)

        self.client = httpx.Client(
            base_url=self.base_url,
            auth=auth,
            headers=default_headers,
            timeout=30.0,
        )

    @classmethod
    def from_settings(cls, settings: UserSettings) -> "JiraClient":
        jira = settings.jira
        if jira.auth == "oauth":
            return cls._from_oauth(settings)
        domain = jira.domain or ""
        return cls(
            domain,
            auth=(jira.email, jira.api_token),
        )

    @classmethod
    def _from_oauth(cls, settings: UserSettings) -> "JiraClient":
        jira = settings.jira

        def provider() -> str:
            token, _cloud = get_valid_access_token(jira)
            return token

        # Resolve cloud_id once for base URL (refresh keeps same cloud).
        _token, cloud_id = get_valid_access_token(jira)
        base = f"https://api.atlassian.com/ex/jira/{cloud_id}"

        def refresh_hook() -> None:
            # Force refresh by clearing expiry via get_valid_access_token logic:
            # call again after marking — get_valid_access_token refreshes when expired.
            # On 401 we re-fetch; if still stale, refresh_access_token path runs when expired.
            from jflow.core.oauth import load_tokens, save_tokens

            tokens = load_tokens()
            if tokens:
                tokens.expires_at = 0
                save_tokens(tokens)

        return cls(
            base,
            headers={"Authorization": f"Bearer {_token}"},
            token_provider=provider,
            oauth_refresh=refresh_hook,
        )

    def _apply_bearer(self) -> None:
        if self._token_provider:
            token = self._token_provider()
            self.client.headers["Authorization"] = f"Bearer {token}"

    def _handle_response(self, response: httpx.Response) -> Any:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                error_data = exc.response.json()
                error_msgs = error_data.get("errorMessages", [])
                errors = error_data.get("errors", {})
                detail = "; ".join(error_msgs) if error_msgs else str(errors)
            except Exception:
                detail = exc.response.text
            raise RuntimeError(f"Jira API Error ({exc.response.status_code}): {detail}") from exc

        # 204 No Content, and some 2xx endpoints (e.g. POST issueLink → 201)
        # return an empty body that is not valid JSON.
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        self._apply_bearer()
        resp = self.client.request(method, endpoint, **kwargs)
        if resp.status_code == 401 and self._oauth_refresh:
            self._oauth_refresh()
            self._apply_bearer()
            resp = self.client.request(method, endpoint, **kwargs)
        return self._handle_response(resp)

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        return self._request("POST", endpoint, json=payload)

    def put(self, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        return self._request("PUT", endpoint, json=payload)

    def delete(self, endpoint: str) -> Any:
        return self._request("DELETE", endpoint)
