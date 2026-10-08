# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from jflow.core.actions.search import search_issues
from jflow.staging.context import StagingContext


def run_search_smoke(ctx: StagingContext) -> None:
    group = "search"
    jql = f'project = {ctx.project} ORDER BY updated DESC'
    try:
        results = search_issues(ctx.client, jql=jql, max_results=5, config=ctx.config)
        assert isinstance(results, list), "search_issues should return a list"
        ctx.record(group, "search_raw_jql", "PASS", f"{len(results)} result(s)")
    except Exception as exc:
        ctx.record(group, "search_raw_jql", "FAIL", str(exc))

    aliases = ctx.config.user.jql_aliases
    if not aliases:
        ctx.record(group, "search_jql_alias", "SKIP", "no jql_aliases configured")
        return

    alias_name = next(iter(aliases.keys()))
    try:
        results = search_issues(ctx.client, jql=alias_name, max_results=5, config=ctx.config)
        assert isinstance(results, list), "alias search should return a list"
        ctx.record(group, "search_jql_alias", "PASS", f"alias={alias_name}, {len(results)} result(s)")
    except Exception as exc:
        ctx.record(group, "search_jql_alias", "FAIL", f"alias={alias_name}: {exc}")
