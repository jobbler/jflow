# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

DISABLE_EXEC_ENV = "JFLOW_DISABLE_EXEC"
DEFAULT_TIMEOUT = 60
MAX_TIMEOUT = 300
MAX_CAPTURE_BYTES = 64 * 1024


def _truncate(text: str, limit: int = MAX_CAPTURE_BYTES) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} bytes]"


def validate_command(command: Any) -> List[str]:
    """Require a non-empty argv list of strings (no shell string form)."""
    if isinstance(command, str):
        raise ValueError(
            "Action 'run' requires 'command' as a list of strings "
            '(e.g. ["./hook.sh"]), not a shell string.'
        )
    if not isinstance(command, list) or not command:
        raise ValueError("Action 'run' requires a non-empty 'command' list.")
    argv: List[str] = []
    for item in command:
        if not isinstance(item, str) or not item:
            raise ValueError("Action 'run' command entries must be non-empty strings.")
        argv.append(item)
    return argv


def build_payload(
    *,
    issue_key: Optional[str],
    step_index: int,
    results: List[Dict[str, Any]],
    extra: Optional[Dict[str, Any]],
    fmt: str,
) -> Dict[str, Any]:
    return {
        "issue_key": issue_key,
        "format": fmt,
        "step_index": step_index,
        "results": results,
        "extra": extra or {},
    }


def encode_payload(payload: Dict[str, Any], fmt: str) -> str:
    fmt = (fmt or "json").lower()
    if fmt == "json":
        return json.dumps(payload, indent=2)
    if fmt == "yaml":
        return yaml.safe_dump(payload, sort_keys=False)
    if fmt == "text":
        key = payload.get("issue_key") or ""
        results_json = json.dumps(payload.get("results") or [], separators=(",", ":"))
        extra_json = json.dumps(payload.get("extra") or {}, separators=(",", ":"))
        return (
            f"ISSUE_KEY={key}\n"
            f"STEP_INDEX={payload.get('step_index')}\n"
            f"RESULTS_JSON={results_json}\n"
            f"EXTRA_JSON={extra_json}\n"
        )
    raise ValueError(f"Unsupported run format '{fmt}'. Use json, yaml, or text.")


def run_external_command(
    *,
    command: Any,
    issue_key: Optional[str],
    step_index: int,
    prior_results: List[Dict[str, Any]],
    format: str = "json",
    timeout_seconds: Optional[int] = None,
    fail_on_error: bool = True,
    cwd: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run an external program with chain context on stdin (shell=False)."""
    if os.environ.get(DISABLE_EXEC_ENV, "").strip() in ("1", "true", "yes"):
        raise RuntimeError(
            f"External commands disabled ({DISABLE_EXEC_ENV}=1)."
        )

    argv = validate_command(command)
    fmt = (format or "json").lower()
    timeout = DEFAULT_TIMEOUT if timeout_seconds is None else int(timeout_seconds)
    if timeout < 1 or timeout > MAX_TIMEOUT:
        raise ValueError(f"timeout_seconds must be between 1 and {MAX_TIMEOUT}.")

    workdir = None
    if cwd is not None:
        workdir = Path(cwd).expanduser()
        if not workdir.is_dir():
            raise FileNotFoundError(f"run cwd does not exist or is not a directory: {workdir}")
        workdir = str(workdir.resolve())

    payload = build_payload(
        issue_key=issue_key,
        step_index=step_index,
        results=prior_results,
        extra=extra,
        fmt=fmt,
    )
    stdin_data = encode_payload(payload, fmt)

    timed_out = False
    try:
        completed = subprocess.run(
            argv,
            input=stdin_data,
            capture_output=True,
            text=True,
            shell=False,
            cwd=workdir,
            timeout=timeout,
            check=False,
        )
        returncode = completed.returncode
        stdout = _truncate(completed.stdout or "")
        stderr = _truncate(completed.stderr or "")
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = -1
        stdout = _truncate((exc.stdout or "") if isinstance(exc.stdout, str) else "")
        stderr = _truncate((exc.stderr or "") if isinstance(exc.stderr, str) else "")
        stderr = (stderr + f"\n[timed out after {timeout}s]").strip()

    result = {
        "command": argv,
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "format": fmt,
        "status": "External Command Failed" if (timed_out or returncode != 0) else "External Command OK",
    }

    if fail_on_error and (timed_out or returncode != 0):
        detail = stderr.strip() or stdout.strip() or f"exit {returncode}"
        raise RuntimeError(
            f"External command failed (returncode={returncode}, timed_out={timed_out}): {detail}"
        )

    return result
