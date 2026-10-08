# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Updated in whole or in part by AI using Cursor (Composer).
# ==============================================================================
from pathlib import Path
from typing import Any, Dict, Optional
from jflow.core.client import JiraClient

DEFAULT_USER_YAML = """jira:
  # --- API token (default) ---
  auth: "api_token"
  domain: "your-domain.atlassian.net"
  email: "your-email@example.com"
  api_token: "YOUR_JIRA_API_TOKEN"
  # --- OAuth 2.0 (3LO); see docs/auth.md ---
  # auth: "oauth"
  # domain: "your-domain.atlassian.net"   # used to pick cloudId after login
  # oauth_client_id: "YOUR_CLIENT_ID"
  # oauth_client_secret: "YOUR_CLIENT_SECRET"
  # oauth_redirect_uri: "http://127.0.0.1:8391/callback"
  # oauth_cloud_id: null                 # optional override after first login
defaults:
  project: "PROJ"
  issue_type: "Task"
  output_format: "markdown"
  board: null
  # Optional: fields for `jflow show` / `jflow issue show` (names or customfield ids).
  # Unset/empty keeps the built-in set. CLI --only overrides this list.
  # show_fields:
  #   - summary
  #   - status
  #   - assignee
  #   - description
  #   - Story Points
projects:
  PROJ:
    default_issue_type: "Task"
    issue_key: "PROJ-1"
templates:
  bug_report:
    summary: "[BUG] {component}: Issue in {env}"
    description: "Steps to reproduce:\\n{steps}"
    issue_type: "Bug"
    labels: ["bug"]
    components: ["{component}"]
    fields: {}
jql_aliases:
  my-bugs: "assignee = currentUser() AND issuetype = Bug AND status != Closed"
  active-sprint: "project = PROJ AND sprint in openSprints()"
  project-open: "project = {project} AND status != Closed"
"""

def get_myself(client: JiraClient) -> Dict[str, Any]:
    """Fetches details for the currently authenticated Jira user (friendly keys)."""
    res = client.get("/rest/api/3/myself")
    return {
        "name": res.get("displayName"),
        "email": res.get("emailAddress"),
        "account_id": res.get("accountId"),
        "active": res.get("active"),
        "timezone": res.get("timeZone"),
    }


def get_server_info(client: JiraClient) -> Dict[str, Any]:
    """Fetches Jira Cloud server and build metadata (friendly keys)."""
    res = client.get("/rest/api/3/serverInfo")
    return {
        "url": res.get("baseUrl"),
        "version": res.get("version"),
        "deployment": res.get("deploymentType"),
        "build": res.get("buildNumber"),
        "time": res.get("serverTime"),
    }


def build_status(client: JiraClient, version: str) -> Dict[str, Any]:
    """Combined client/me/server status payload for the CLI."""
    return {
        "client": {"version": version},
        "me": get_myself(client),
        "server": get_server_info(client),
    }


def init_config(target_dir: Optional[Path] = None, force: bool = False) -> Dict[str, Any]:
    """Scaffolds a default user.yaml config file."""
    base_dir = target_dir or (Path.home() / ".config" / "jflow")
    base_dir.mkdir(parents=True, exist_ok=True)

    user_file = base_dir / "user.yaml"

    created = []
    skipped = []

    if not user_file.exists() or force:
        user_file.write_text(DEFAULT_USER_YAML)
        created.append(str(user_file))
    else:
        skipped.append(str(user_file))

    return {
        "directory": str(base_dir),
        "created": created,
        "skipped": skipped,
        "status": "Configuration Initialized",
    }
