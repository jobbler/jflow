# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
# Updated in whole or in part by AI using Cursor (Composer).
import re
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class JiraCredentials(BaseModel):
    """Jira Cloud credentials: API token (default) or OAuth 2.0 (3LO)."""

    domain: Optional[str] = None
    email: Optional[str] = None
    api_token: Optional[str] = None
    auth: Literal["api_token", "oauth"] = "api_token"
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    oauth_cloud_id: Optional[str] = None
    oauth_redirect_uri: Optional[str] = None

    @model_validator(mode="after")
    def _validate_auth_mode(self) -> "JiraCredentials":
        if self.auth == "oauth":
            if not self.oauth_client_id:
                raise ValueError("oauth_client_id is required when auth is 'oauth'")
            if not self.oauth_client_secret:
                raise ValueError(
                    "oauth_client_secret is required when auth is 'oauth' "
                    "(Atlassian 3LO requires a client secret)"
                )
        else:
            missing = [
                name
                for name, val in (
                    ("domain", self.domain),
                    ("email", self.email),
                    ("api_token", self.api_token),
                )
                if not val
            ]
            if missing:
                raise ValueError(
                    f"Missing required fields for api_token auth: {', '.join(missing)}"
                )
        return self


class Defaults(BaseModel):
    project: Optional[str] = None
    issue_type: str = "Task"
    output_format: str = "markdown"
    board: Optional[str] = None
    # Values for {placeholders} in queries, templates, and workflow steps.
    # A value that is a dotted path into user.yaml (e.g. "jira.email") is
    # resolved to that setting; otherwise it is a literal string.
    # {project} also comes from defaults.project unless vars sets it.
    # CLI --var / -V wins.
    vars: Dict[str, str] = Field(default_factory=dict)
    # Field names/ids for `jflow show` / `jflow issue show`. None/empty = built-in set.
    show_fields: Optional[List[str]] = None
    # Field names/ids for `jflow list` / `jflow query`. None/empty = built-in columns.
    list_fields: Optional[List[str]] = None
    # Sort terms for `jflow list` / `jflow query` (JQL fields, "-" prefix = descending).
    # None/empty = built-in "updated DESC" (only when the JQL has no ORDER BY of its own).
    sort_issues: Optional[List[str]] = None
    # Sort terms for `jflow sprint list` (client-side; "-" prefix = descending).
    sort_sprints: Optional[List[str]] = None
    # Sort terms for `jflow boards list` (client-side; "-" prefix = descending).
    sort_boards: Optional[List[str]] = None


class ProjectConfig(BaseModel):
    default_issue_type: str = "Task"
    issue_key: Optional[str] = None


class IssueTemplate(BaseModel):
    summary: Optional[str] = None
    description: Optional[str] = None
    issue_type: Optional[str] = None
    project: Optional[str] = None
    parent: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    components: List[str] = Field(default_factory=list)
    fields: Dict[str, Any] = Field(default_factory=dict)


class UserConfig(BaseModel):
    jira: JiraCredentials
    defaults: Defaults = Field(default_factory=Defaults)
    projects: Dict[str, ProjectConfig] = Field(default_factory=dict)
    templates: Dict[str, IssueTemplate] = Field(default_factory=dict)
    jql_aliases: Dict[str, str] = Field(default_factory=dict)


UserSettings = UserConfig


class AppConfig(BaseModel):
    user: UserConfig

    @property
    def user_settings(self) -> UserConfig:
        return self.user

    def get_default_project(self) -> Optional[str]:
        return self.user.defaults.project

    def get_default_board(self) -> Optional[str]:
        return self.user.defaults.board

    def get_project_config(self, project_key: str) -> Optional[ProjectConfig]:
        return self.user.projects.get(project_key)

    def get_default_issue_key(self) -> Optional[str]:
        proj_key = self.get_default_project()
        if proj_key and proj_key in self.user.projects:
            return self.user.projects[proj_key].issue_key
        return None

    def resolve_jql(self, query_or_alias: str) -> str:
        """Returns the mapped JQL query if query_or_alias matches an alias key, else returns raw input."""
        return self.user.jql_aliases.get(query_or_alias, query_or_alias)

    def resolve_var_pointers(self, values: Dict[str, str]) -> Dict[str, str]:
        """Resolve dotted-path pointers like "jira.email" to their config values."""
        resolved: Dict[str, str] = {}
        for key, value in values.items():
            if _VAR_POINTER_RE.match(value or ""):
                node: Any = self.user
                ok = True
                for part in value.split("."):
                    if isinstance(node, dict):
                        if part in node:
                            node = node[part]
                        else:
                            ok = False
                            break
                    elif isinstance(node, BaseModel):
                        if hasattr(node, part):
                            node = getattr(node, part)
                        else:
                            ok = False
                            break
                    else:
                        ok = False
                        break
                resolved[key] = str(node) if ok and node is not None else value
            else:
                resolved[key] = value
        return resolved

    def build_vars(self, cli_vars: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Merged {placeholder} map: defaults.vars (pointers resolved) > defaults.project > CLI --var."""
        merged: Dict[str, str] = self.resolve_var_pointers(
            dict(self.user.defaults.vars)
        )
        if "project" not in merged and self.user.defaults.project:
            merged["project"] = self.user.defaults.project
        if cli_vars:
            merged.update(cli_vars)
        return merged


_VAR_POINTER_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


ConfigContext = AppConfig
