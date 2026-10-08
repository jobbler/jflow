# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
# Updated in whole or in part by AI using Cursor (Composer).
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
    # Field names/ids for `jflow show` / `jflow issue show`. None/empty = built-in set.
    show_fields: Optional[List[str]] = None


class ProjectConfig(BaseModel):
    default_issue_type: str = "Task"
    issue_key: Optional[str] = None


class IssueTemplate(BaseModel):
    summary: Optional[str] = None
    description: Optional[str] = None
    issue_type: Optional[str] = None
    project: Optional[str] = None
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


ConfigContext = AppConfig
