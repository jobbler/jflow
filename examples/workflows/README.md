<!--
  Created in whole or in part by AI using Cursor (Grok).
  Co-created through collaborative AI pair programming with Gemini.
  Refined / authored with assistance from Cursor (Grok).
  Updated in whole or in part by AI using Cursor (Composer).
-->

# Example workflows

JSON workflows for `jflow issue chain …`. Full reference: [docs/workflows.md](../../docs/workflows.md).

## Security

These files are **templates with `{placeholders}`** (filled via `--var` / `-V`) and tokens like `@me` / `@current_sprint`. They contain **no API tokens**. Prefer a disposable staging project. Set `defaults.board` when using `@current_sprint`.

**`run` steps:** only use trusted workflow JSON. `command` is an argv list executed without a shell; the child inherits the same environment as `jflow` (including any tokens already in that env). On locked-down hosts set `JFLOW_DISABLE_EXEC=1`. Details: [docs/workflows.md](../../docs/workflows.md#external-commands-run).

## Index

| File | Use when |
|------|----------|
| [create_and_start.json](create_and_start.json) | Create (`{project}`/`{summary}`) → `@me` → In Progress → comment; Sprint `@current_sprint` |
| [create_from_template.json](create_from_template.json) | Create via `bug_report` template (`components`/`fields` from `user.yaml`); pass vars with `-V` |
| [create_to_sprint.json](create_to_sprint.json) | Create → sprint `@current_sprint` → In Progress |
| [start_existing.json](start_existing.json) | Assign / transition / comment with positional issue key |
| [staging_create_assign_comment.json](staging_create_assign_comment.json) | Staging/reference: create → assign → comment (same shape as staging `--lifecycle` workflow group) |
| [run_external_example.json](run_external_example.json) | Demo `run` action → [hooks/echo_payload.sh](hooks/echo_payload.sh) (run from repo root) |

Chain JSON still uses `"action": "transition"` for status changes; on the CLI that is `issue change` / top-level `change`. See [docs/workflows.md](../../docs/workflows.md#cli-vs-chain-naming).

## Staging reference

`staging_create_assign_comment.json` matches the live staging workflow lifecycle test. Before running it manually, set `project` and `assignee` (and optionally the summary). Staging docs: [docs/staging-tests.md](../../docs/staging-tests.md).

```bash
jflow issue chain examples/workflows/create_and_start.json \
  -V project=PROJ -V summary="Investigate intermittent timeout"

# Staging reference (edit project/assignee in JSON or use your staging yaml):
jflow issue chain examples/workflows/staging_create_assign_comment.json \
  --user-yaml ./staging-user.yaml
```

Workflows stay as JSON files in this directory.
