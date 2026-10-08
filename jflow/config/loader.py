# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Composer).
# ==============================================================================
import os
from pathlib import Path
from typing import Optional
import yaml
from .models import AppConfig, ConfigContext, UserConfig, UserSettings

ENV_USER_YAML = "JFLOW_USER_YAML"


def get_default_user_config_path() -> Path:
    return Path.home() / ".config" / "jflow" / "user.yaml"


def _normalize_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def resolve_user_config_path(explicit: Optional[str] = None) -> Path:
    """Resolve user.yaml: CLI arg > env > ~/.config/jflow/user.yaml."""
    if explicit:
        return _normalize_path(explicit)
    env_path = os.environ.get(ENV_USER_YAML)
    if env_path:
        return _normalize_path(env_path)
    return get_default_user_config_path()


def load_config(user_settings_path: Optional[str] = None) -> AppConfig:
    u_path = resolve_user_config_path(user_settings_path)

    if not u_path.exists():
        raise FileNotFoundError(f"User configuration file not found at: {u_path}")

    with open(u_path, "r") as f:
        user_data = yaml.safe_load(f) or {}

    user_cfg = UserConfig(**user_data)
    return AppConfig(user=user_cfg)
