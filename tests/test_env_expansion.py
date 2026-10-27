# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
import os
from pathlib import Path
import tempfile

from jflow.config.loader import ConfigEnvError, expand_env, load_config


# 1. Simple expansion across nested dicts/lists (values only)
data = {
    "jira": {"api_token": "${JIRA_TOKEN}"},
    "defaults": {"project": "${PROJ}"},
    "jql_aliases": {"mine": "project = ${PROJ} AND assignee = currentUser()"},
    "templates": {"bug": {"labels": ["${PROJ}", "static"]}},
}
out = expand_env(data, environ={"JIRA_TOKEN": "s3cret", "PROJ": "ABC"})
assert out["jira"]["api_token"] == "s3cret"
assert out["defaults"]["project"] == "ABC"
assert out["jql_aliases"]["mine"] == "project = ABC AND assignee = currentUser()"
assert out["templates"]["bug"]["labels"] == ["ABC", "static"]

# 2. Defaults: ${VAR:-default} falls back when unset; ${VAR:-} yields empty
assert expand_env("${MISSING:-fallback}", environ={}) == "fallback"
assert expand_env("${MISSING:-}", environ={}) == ""
assert expand_env("${SET:-fallback}", environ={"SET": "value"}) == "value"
assert expand_env("${URL:-http://127.0.0.1:8391/cb}", environ={}) == "http://127.0.0.1:8391/cb"

# 3. Missing variable raises ConfigEnvError naming variable and config path
try:
    expand_env({"jira": {"api_token": "${MISSING}"}}, environ={})
    assert False, "Expected ConfigEnvError for missing variable"
except ConfigEnvError as exc:
    assert "MISSING" in str(exc)
    assert "jira.api_token" in str(exc)

# 4. $$ escapes a literal dollar sign; escaped references stay literal
assert expand_env("$${VAR}", environ={"VAR": "x"}) == "${VAR}"
assert expand_env("cost: $$5", environ={}) == "cost: $5"

# 5. Existing {placeholder} template syntax is untouched
assert expand_env("{project} and ${PROJ}", environ={"PROJ": "ABC"}) == "{project} and ABC"

# 6. Expansion is not recursive
assert expand_env("${OUTER}", environ={"OUTER": "${INNER}", "INNER": "x"}) == "${INNER}"

# 7. Non-string scalars are untouched
assert expand_env({"n": 1, "b": True, "z": None}, environ={}) == {
    "n": 1,
    "b": True,
    "z": None,
}

# 8. Env values with YAML metacharacters do not alter the parsed structure
weird = "a: b\n# not a comment\n- not a list"
assert expand_env({"jira": {"email": "${WEIRD}"}}, environ={"WEIRD": weird}) == {
    "jira": {"email": weird}
}

# 9. load_config end-to-end (env values resolved before Pydantic validation)
with tempfile.TemporaryDirectory() as tmp:
    user_path = Path(tmp) / "user.yaml"
    user_path.write_text(
        "jira:\n"
        '  domain: "${JIRA_DOMAIN}"\n'
        '  email: "${JIRA_EMAIL:-me@example.com}"\n'
        '  api_token: "${JIRA_API_TOKEN}"\n'
        "defaults:\n"
        '  project: "PROJ"\n'
    )

    os.environ["JIRA_DOMAIN"] = "example.atlassian.net"
    os.environ["JIRA_API_TOKEN"] = "tok"
    os.environ.pop("JIRA_EMAIL", None)

    cfg = load_config(user_settings_path=str(user_path))
    assert cfg.user.jira.domain == "example.atlassian.net"
    assert cfg.user.jira.email == "me@example.com"
    assert cfg.user.jira.api_token == "tok"

    # 10. Missing credential surfaces through load_config (fails fast)
    os.environ.pop("JIRA_API_TOKEN")
    try:
        load_config(user_settings_path=str(user_path))
        assert False, "Expected ConfigEnvError for unset JIRA_API_TOKEN"
    except ConfigEnvError as exc:
        assert "JIRA_API_TOKEN" in str(exc)
        assert "jira.api_token" in str(exc)

    os.environ.pop("JIRA_DOMAIN", None)

print("✅ Environment variable expansion tests passed successfully!")
