# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Updated in whole or in part by AI using Cursor (Composer).
# ==============================================================================
import contextlib
import io
import sys
import unittest.mock as mock

from jflow.core.actions.system import run_update

PIP_PREFIX = "/home/user/.local/pipx/venvs/jflow"
_real_prefix = sys.prefix


def _restore():
    sys.prefix = _real_prefix


# Case A: pipx venv, pipx binary on PATH.
sys.prefix = PIP_PREFIX
run_result = mock.Mock(returncode=0)
with mock.patch("shutil.which", return_value="/usr/bin/pipx"), mock.patch(
    "subprocess.run", return_value=run_result
) as run_mock:
    code = run_update()
try:
    assert run_mock.call_count == 1
    assert run_mock.call_args[0][0] == ["pipx", "upgrade", "jflow"]
    assert code == 0
finally:
    _restore()

# Case B: pipx venv, pipx binary missing -> python -m pipx fallback.
sys.prefix = PIP_PREFIX
run_result = mock.Mock(returncode=0)
with mock.patch("shutil.which", return_value=None), mock.patch(
    "subprocess.run", return_value=run_result
) as run_mock:
    code = run_update()
try:
    assert run_mock.call_count == 1
    assert run_mock.call_args[0][0] == [sys.executable, "-m", "pipx", "upgrade", "jflow"]
    assert code == 0
finally:
    _restore()

# Case C: non-pipx environment -> no subprocess, prints guidance, returns 0.
sys.prefix = "/usr"
with mock.patch("shutil.which", return_value="/usr/bin/pipx"), mock.patch(
    "subprocess.run"
) as run_mock, contextlib.redirect_stdout(io.StringIO()) as out:
    code = run_update()
try:
    assert run_mock.call_count == 0
    assert code == 0
    assert "pipx upgrade jflow" in out.getvalue()
finally:
    _restore()

sys.prefix = "/usr"
with mock.patch("shutil.which", return_value=None), mock.patch(
    "subprocess.run"
) as run_mock, contextlib.redirect_stdout(io.StringIO()) as out:
    code = run_update()
try:
    assert run_mock.call_count == 0
    assert code == 0
    assert "python -m pip install --upgrade jflow" in out.getvalue()
finally:
    _restore()

print("✅ Update command tests passed!")
