# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Composer).
# ==============================================================================
import os
import re
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple
import yaml
from .models import AppConfig, UserConfig

ENV_USER_YAML = "JFLOW_USER_YAML"

# ``${VAR}`` or ``${VAR:-default}``; ``$$`` escapes a literal dollar sign.
_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")
_ENV_ESCAPE = "\x00"


class ConfigEnvError(ValueError):
    """Environment variable referenced from user.yaml is not set."""


def _expand_env_string(
    value: str, path: Tuple[Any, ...], environ: Mapping[str, str]
) -> str:
    # ``$$`` becomes ``$``; swap it out first so it is not treated as a reference.
    value = value.replace("$$", _ENV_ESCAPE)

    def replace(match: "re.Match[str]") -> str:
        name = match.group(1)
        default = match.group(2)
        if name in environ:
            return environ[name]
        if default is not None:
            return default
        location = ".".join(str(part) for part in path) or "<root>"
        raise ConfigEnvError(
            f"Environment variable '{name}' referenced at '{location}' in user.yaml "
            f"is not set (use ${{{name}:-default}} to supply a default)."
        )

    return _ENV_PATTERN.sub(replace, value).replace(_ENV_ESCAPE, "$")


def expand_env(
    value: Any,
    path: Tuple[Any, ...] = (),
    environ: Optional[Mapping[str, str]] = None,
) -> Any:
    """Recursively expand ``${VAR}`` references in string values loaded from YAML.

    Only string values are expanded (dict keys are left as-is). Values are not
    expanded recursively: a variable whose value contains ``${OTHER}`` stays literal.
    """
    env = os.environ if environ is None else environ
    if isinstance(value, str):
        return _expand_env_string(value, path, env)
    if isinstance(value, list):
        return [
            expand_env(item, path + (index,), env)
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        return {
            key: expand_env(item, path + (key,), env)
            for key, item in value.items()
        }
    return value


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

    # Expand ${VAR} / ${VAR:-default} after parsing so env values cannot alter
    # the YAML structure. Pydantic then validates the resolved values.
    user_data = expand_env(user_data)

    user_cfg = UserConfig(**user_data)
    return AppConfig(user=user_cfg)
