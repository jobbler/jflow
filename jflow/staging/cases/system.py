# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
# Created in whole or in part by AI using Cursor (Grok).
from jflow.core.actions.system import build_status, get_myself, get_server_info
from jflow.staging.context import StagingContext
from jflow.version import __version__


def run_system_smoke(ctx: StagingContext) -> None:
    group = "system"
    try:
        me = get_myself(ctx.client)
        assert me.get("account_id"), "myself response missing account_id"
        ctx.record(group, "get_myself", "PASS", me.get("name", ""))
    except Exception as exc:
        ctx.record(group, "get_myself", "FAIL", str(exc))

    try:
        info = get_server_info(ctx.client)
        assert info.get("url") or info.get("version"), "serverInfo missing expected fields"
        ctx.record(group, "get_server_info", "PASS", info.get("version", ""))
    except Exception as exc:
        ctx.record(group, "get_server_info", "FAIL", str(exc))

    try:
        status = build_status(ctx.client, __version__)
        assert status["client"]["version"] == __version__
        assert status["me"].get("account_id")
        assert status["server"].get("url") or status["server"].get("version")
        ctx.record(group, "get_status", "PASS", status["client"]["version"])
    except Exception as exc:
        ctx.record(group, "get_status", "FAIL", str(exc))
