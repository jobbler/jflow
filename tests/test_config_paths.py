# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Composer).
# ==============================================================================
import os
from pathlib import Path
import tempfile

from jflow.config.loader import (
    ENV_USER_YAML,
    get_default_user_config_path,
    load_config,
    resolve_user_config_path,
)

# Isolate env for this process
os.environ.pop(ENV_USER_YAML, None)

# 1. Defaults when nothing is set
assert resolve_user_config_path() == get_default_user_config_path()

# 2. Explicit CLI arg wins over env
with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    user_cli = tmp_path / "cli-user.yaml"
    user_env = tmp_path / "env-user.yaml"

    user_cli.write_text(
        "jira:\n  domain: cli.atlassian.net\n  email: a@b.com\n  api_token: tok\n"
    )
    user_env.write_text(
        "jira:\n  domain: env.atlassian.net\n  email: a@b.com\n  api_token: tok\n"
    )

    os.environ[ENV_USER_YAML] = str(user_env)

    assert resolve_user_config_path(str(user_cli)) == user_cli.resolve()

    cfg = load_config(user_settings_path=str(user_cli))
    assert cfg.user.jira.domain == "cli.atlassian.net"

    # 3. Env used when CLI omitted
    assert resolve_user_config_path() == user_env.resolve()

    cfg_env = load_config()
    assert cfg_env.user.jira.domain == "env.atlassian.net"

    # 4. Missing overridden user path raises
    missing_user = tmp_path / "missing-user.yaml"
    try:
        load_config(user_settings_path=str(missing_user))
        assert False, "Expected FileNotFoundError for missing user.yaml"
    except FileNotFoundError as exc:
        assert "User configuration file not found" in str(exc)

os.environ.pop(ENV_USER_YAML, None)

print("✅ Config path override resolution tests passed successfully!")
