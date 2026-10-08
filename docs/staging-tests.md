<!--
  Created in whole or in part by AI using Cursor (Grok).
  Co-created through collaborative AI pair programming with Gemini.
  Refined / authored with assistance from Cursor (Grok).
  Updated in whole or in part by AI using Cursor (Composer).
-->

# Staging Jira integration tests

`python -m jflow.staging.cli` runs live checks against a **staging** Jira Cloud site. It is separate from the mocked unit suite (`python run_all_tests.py`).

**Warning:** With `--lifecycle`, tests create and delete issues and create/close sprints. Use a disposable staging project and board only — never production.

## Requirements

Config path is **required** (no `~/.config/jflow/` fallback for this runner):

| Flag | Purpose |
|------|---------|
| `--user-yaml` | Staging credentials, `defaults.project`, optional aliases/templates |

Also:

- `--project` optional override of `defaults.project`
- `--board-id` **required** whenever the `sprint` group is selected (including `--group all`)

Example config (placeholders only; **no secrets**):

- [`examples/config/staging-user.yaml.example`](../examples/config/staging-user.yaml.example)

### Reference workflows (JSON)

Use JSON under [`examples/workflows/`](../examples/workflows/) (see that folder’s [README](../examples/workflows/README.md)).

The staging `--lifecycle` **workflow** group loads [`staging_create_assign_comment.json`](../examples/workflows/staging_create_assign_comment.json) (packaged fixture + examples copy), then substitutes your staging project, email, and run id at runtime.

Run the same shape manually after editing placeholders (`PROJ`, assignee):

```bash
jflow issue chain examples/workflows/staging_create_assign_comment.json \
  --user-yaml ./staging-user.yaml
```

## Modes

### Read-only smoke (default)

Exercises non-mutating APIs only.

```bash
python -m jflow.staging.cli \
  --user-yaml /path/to/staging-user.yaml \
  --board-id 123
```

### Full lifecycle (opt-in)

```bash
python -m jflow.staging.cli \
  --user-yaml /path/to/staging-user.yaml \
  --board-id 123 \
  --lifecycle
```

Lifecycle creates issues labeled `jflow-staging` with summaries prefixed `[jflow-staging]`, then deletes them in cleanup. Sprints are created for the test board and closed afterward (delete attempted when the API allows).

## Groups

| Group | Read-only | With `--lifecycle` |
|-------|-----------|--------------------|
| `system` | `myself`, `serverInfo` | — |
| `search` | raw JQL + first `jql_aliases` entry (if any) | — |
| `issue` | project search | create → assign → comment → labels → due date → story points (skip if unavailable) → transition → delete |
| `sprint` | list sprints, backlog | create sprint → create issue → add to sprint → close sprint → cleanup |
| `workflow` | skipped | chain from `staging_create_assign_comment.json` (create → assign → comment) → delete |
| `all` | all of the above (default) | all of the above |

```bash
# System + search only (no board id needed)
python -m jflow.staging.cli \
  --user-yaml ./staging-user.yaml \
  --group system,search

# Issue lifecycle only
python -m jflow.staging.cli \
  --user-yaml ./staging-user.yaml \
  --group issue \
  --lifecycle

# Workflow group (uses reference JSON fixture)
python -m jflow.staging.cli \
  --user-yaml ./staging-user.yaml \
  --group workflow \
  --lifecycle
```

## Output

Each case prints `PASS`, `FAIL`, or `SKIP`. Exit code is `1` if any case failed, `2` for bad arguments / missing files, `0` on success.

## Install

After `pipx install .` (or an editable install), the staging package ships with `jflow`. Run it with `python -m jflow.staging.cli` (not a separate console script).
