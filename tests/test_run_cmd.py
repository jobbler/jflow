# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Created in whole or in part by AI using Cursor (Grok).
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jflow.core.actions.run_cmd import (  # noqa: E402
    DISABLE_EXEC_ENV,
    encode_payload,
    run_external_command,
    validate_command,
)
from jflow.core.actions.chain import execute_chain  # noqa: E402


# --- validate_command ---
assert validate_command(["/bin/echo", "hi"]) == ["/bin/echo", "hi"]
try:
    validate_command("echo hi")
    raise AssertionError("string command should be rejected")
except ValueError:
    pass
try:
    validate_command([])
    raise AssertionError("empty command should be rejected")
except ValueError:
    pass
try:
    validate_command(["ok", 1])
    raise AssertionError("non-string argv should be rejected")
except ValueError:
    pass


# --- encode formats ---
payload = {
    "issue_key": "PROJ-1",
    "format": "json",
    "step_index": 2,
    "results": [{"step": "create", "result": {"key": "PROJ-1"}}],
    "extra": {"channel": "#jira"},
}
as_json = encode_payload(payload, "json")
assert json.loads(as_json)["issue_key"] == "PROJ-1"

as_yaml = encode_payload({**payload, "format": "yaml"}, "yaml")
assert yaml.safe_load(as_yaml)["extra"]["channel"] == "#jira"

as_text = encode_payload({**payload, "format": "text"}, "text")
assert "ISSUE_KEY=PROJ-1" in as_text
assert "RESULTS_JSON=" in as_text
assert "EXTRA_JSON=" in as_text

try:
    encode_payload(payload, "xml")
    raise AssertionError("bad format should raise")
except ValueError:
    pass


# --- disable exec kill switch ---
os.environ[DISABLE_EXEC_ENV] = "1"
try:
    try:
        run_external_command(
            command=["/bin/true"],
            issue_key=None,
            step_index=0,
            prior_results=[],
        )
        raise AssertionError("disable exec should raise")
    except RuntimeError as exc:
        assert DISABLE_EXEC_ENV in str(exc)
finally:
    del os.environ[DISABLE_EXEC_ENV]


# --- successful real subprocess (json stdin) ---
res = run_external_command(
    command=[sys.executable, "-c", "import sys; print(sys.stdin.read()[:20])"],
    issue_key="ABC-9",
    step_index=0,
    prior_results=[],
    format="json",
    extra={"n": 1},
)
assert res["returncode"] == 0
assert res["timed_out"] is False
assert "ABC-9" in res["stdout"] or "{" in res["stdout"]


# --- fail_on_error true vs false ---
try:
    run_external_command(
        command=[sys.executable, "-c", "import sys; sys.exit(3)"],
        issue_key=None,
        step_index=0,
        prior_results=[],
        fail_on_error=True,
    )
    raise AssertionError("nonzero exit should raise when fail_on_error")
except RuntimeError:
    pass

soft = run_external_command(
    command=[sys.executable, "-c", "import sys; sys.exit(3)"],
    issue_key=None,
    step_index=0,
    prior_results=[],
    fail_on_error=False,
)
assert soft["returncode"] == 3
assert soft["timed_out"] is False


# --- timeout ---
try:
    run_external_command(
        command=[sys.executable, "-c", "import time; time.sleep(5)"],
        issue_key=None,
        step_index=0,
        prior_results=[],
        timeout_seconds=1,
        fail_on_error=True,
    )
    raise AssertionError("timeout should raise when fail_on_error")
except RuntimeError as exc:
    assert "timed_out" in str(exc).lower() or "timed out" in str(exc).lower()

timed = run_external_command(
    command=[sys.executable, "-c", "import time; time.sleep(5)"],
    issue_key=None,
    step_index=0,
    prior_results=[],
    timeout_seconds=1,
    fail_on_error=False,
)
assert timed["timed_out"] is True
assert timed["returncode"] == -1


# --- timeout_seconds bounds ---
try:
    run_external_command(
        command=["/bin/true"],
        issue_key=None,
        step_index=0,
        prior_results=[],
        timeout_seconds=999,
    )
    raise AssertionError("timeout > 300 should raise")
except ValueError:
    pass


# --- mocked subprocess argv / shell=False ---
fake = MagicMock()
fake.returncode = 0
fake.stdout = "out"
fake.stderr = ""
with patch("jflow.core.actions.run_cmd.subprocess.run", return_value=fake) as mock_run:
    run_external_command(
        command=["/usr/bin/myhook", "--flag"],
        issue_key="K-1",
        step_index=1,
        prior_results=[{"step": "comment", "result": {"id": "1"}}],
        format="json",
        extra={"x": True},
    )
    kwargs = mock_run.call_args
    assert kwargs.kwargs["shell"] is False
    assert kwargs.args[0] == ["/usr/bin/myhook", "--flag"]
    assert "K-1" in kwargs.kwargs["input"]


# --- chain wires run and preserves current_key ---
mock_client = MagicMock()
mock_config = MagicMock()
mock_fields = MagicMock()
with patch(
    "jflow.core.actions.chain.run_external_command",
    return_value={"returncode": 0, "stdout": "ok", "stderr": "", "timed_out": False, "command": ["x"]},
) as mock_run_cmd:
    out = execute_chain(
        mock_client,
        mock_config,
        mock_fields,
        steps=[
            {
                "action": "run",
                "command": ["./hooks/echo_payload.sh"],
                "format": "json",
                "extra": {"channel": "#t"},
            }
        ],
        initial_key="KEEP-1",
    )
    assert out[0]["step"] == "run"
    call_kw = mock_run_cmd.call_args.kwargs
    assert call_kw["issue_key"] == "KEEP-1"
    assert call_kw["step_index"] == 0
    assert call_kw["extra"] == {"channel": "#t"}


print("✅ run action / external command tests passed successfully!")
