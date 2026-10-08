<!--
  Created in whole or in part by AI using Cursor (Grok).
  Co-created through collaborative AI pair programming with Gemini.
  Refined / authored with assistance from Cursor (Grok).
  Updated in whole or in part by AI using Cursor (Composer).
-->

# Workflows (issue chain)

`jflow issue chain` runs a sequence of Jira actions from a JSON file or inline JSON. It is the way to automate multi-step flows (create, assign, sprint, transition, and so on) in one invocation.

## Create vs workflow

| Command | What it does |
|---------|----------------|
| `jflow issue create` | Creates **one** issue (optional template). Does **not** run a workflow. |
| `jflow issue chain` | Runs an explicit list of steps. Workflows run **only** when you call chain. |

There is no config hook that auto-runs a workflow after `issue create`. To create and then sprint/transition, either:

- run follow-up commands (`sprint add`, `issue change`, …), or
- put those steps in a chain workflow.

## CLI vs chain naming

Some everyday CLI verbs differ from the JSON `action` names. Use this table when writing workflows:

| Task | CLI | Chain `action` |
|------|-----|----------------|
| Change status | `jflow change KEY STATUS` or `issue change` | `"transition"` with `"status"` |
| Labels | `jflow label KEY …` (replace by default; `--append` / `--delete`) | `"label"` with `"labels"` list — **adds only**, does not replace or remove |
| Add to sprint | `jflow sprint add KEY --board …` | `"sprint"` with numeric `"sprint_id"` or `"@current_sprint"` |

## CLI usage

```bash
# JSON file
jflow issue chain examples/workflows/create_and_start.json \
  -V project=PROJ -V summary="Investigate intermittent timeout"

# Inline JSON array (operate on an existing issue)
jflow issue chain PROJ-123 '[
  {"action": "assign", "assignee": "@me"},
  {"action": "comment", "message": "Picked up"}
]'
```

A file may be either a bare array of steps or an object with a `steps` key:

```json
{ "steps": [ ... ] }
```

## How issue keys thread through steps

1. A `create` step sets the **active key** to the new issue.
2. Later steps reuse that key unless you override it.
3. Pass the issue key as a positional argument to start from an existing issue (no create required).
4. Any step may set `"issue_key": "PROJ-99"` to target a specific issue for that step only.

## Dynamic fields (`--var` and tokens)

Use `{placeholders}` in any workflow string and fill them from the CLI with `--var` / `-V` (same syntax as `issue create`):

```bash
jflow issue chain examples/workflows/create_and_start.json \
  -V project=PROJ -V summary="Fix login timeout"
```

```json
{ "action": "create", "summary": "{summary}", "project": "{project}", "issue_type": "Task" }
```

CLI `--var` values also merge into a create step’s `template_vars` (CLI wins on key conflicts), so named templates work without embedding every value in JSON:

```bash
jflow issue chain examples/workflows/create_from_template.json \
  -V component=Auth -V env=Prod -V steps="Click login"
```

You can still hard-code values or put `template_vars` in the workflow JSON. Define templates in `user.yaml`. See [templates.md](templates.md).

**Tokens (not `--var` placeholders):**

| Token | Where | Notes |
|-------|--------|--------|
| `@me` | `assign` / `reporter` | Must be a JSON string (`"assignee": "@me"`). Resolves to the authenticated user. |
| `@current_sprint` | create `extra_fields` / template `fields` `Sprint`, or chain `"action": "sprint"` | Requires `defaults.board` in `user.yaml`. |

### Create-step fields (what is honored)

A `create` step only reads these **first-class** keys (anything else at the top level is **ignored**, including a bare `"components"` key):

| Key | Role |
|-----|------|
| `project`, `issue_type`, `summary`, `description`, `labels`, `parent` | Direct create params (strings support `{placeholders}`). `parent` is required when `issue_type` is a sub-task type. |
| `template_name`, `template_vars` | Load a named template from `user.yaml` (template may supply `parent`) |
| `extra_fields` | Map of field display name → value (schema-encoded; see [fields.md](fields.md)) |

**Templates apply their full create shape.** With `"template_name": "bug_report"`, the chain uses the same path as `jflow issue create -T bug_report`: template `summary`, `description`, `issue_type`, `project`, `labels`, **`components`**, and **`fields`** are all applied (after `{placeholder}` render). You do **not** need to repeat `components` in the workflow JSON if the template already defines them.

Example template in `user.yaml` (see [`examples/config/user.yaml`](../examples/config/user.yaml)):

```yaml
templates:
  bug_report:
    summary: "[BUG] {component}: Issue in {env}"
    issue_type: "Bug"
    components: ["{component}"]
    fields:
      "Environment": "QA"
```

```json
{ "action": "create", "template_name": "bug_report" }
```

```bash
jflow issue chain examples/workflows/create_from_template.json \
  -V component=Auth -V env=Prod -V steps="Click login"
```

**Without a template (or to add/override named fields):** put them under `extra_fields`. Keys must match the [field cache](fields.md) display name (run `jflow cache sync`). Components without a template go here too — often as `Component/s`:

```json
{
  "action": "create",
  "summary": "{summary}",
  "project": "{project}",
  "issue_type": "Bug",
  "extra_fields": {
    "Component/s": "Payments",
    "Sprint": "@current_sprint",
    "Environment": "QA",
    "Story Points": 3
  }
}
```

Do **not** write top-level `"components": "…"` on the create step — that key is not forwarded and is silently ignored. Use a template’s `components:` list or `extra_fields`.

Update a field later in the same chain:

```json
{ "action": "field", "field": "Environment", "value": "Production" }
```

Create a sub-task, or convert types:

```json
{ "action": "create", "issue_type": "Sub-task", "parent": "{parent}", "summary": "{summary}", "project": "{project}" }
{ "action": "convert", "issue_type": "Task" }
{ "action": "convert", "issue_type": "Sub-task", "parent": "PROJ-100" }
```

Story → Sub-task often needs two converts (Story → Task, then Task → Sub-task), matching the Jira UI.

**Parent hierarchy:** Sub-task parents must be a standard issue (Story, Task, Bug, …). An Epic (or another Sub-task) is rejected. Converting to/from Sub-task uses Jira’s bulk-move API so type and parent change together (a normal field edit fails hierarchy checks even when the parent is a valid Story).

## Sprints in workflows vs CLI

| Approach | How to target a sprint |
|----------|------------------------|
| Chain action `sprint` | Numeric `"sprint_id"`, or `"@current_sprint"` / omit `sprint_id` (uses active sprint on `defaults.board`) |
| Create `extra_fields` / template `Sprint` | `"@current_sprint"` adds the new issue to the active sprint on `defaults.board` after create |
| CLI `sprint add` | `--sprint-id N` **or** `--board NAME\|ID` (auto-detects the **active** sprint; uses `defaults.board` if omitted) |

Look up an active sprint id when you need a fixed numeric value:

```bash
jflow sprint list --board 42 --state active
# or:
jflow sprint current --board 42
```

Or use a chain with `"sprint_id": "@current_sprint"` ([`create_to_sprint.json`](../examples/workflows/create_to_sprint.json)).

## Supported actions

| `action` | Parameters | Notes |
|----------|------------|--------|
| `create` | `project`, `issue_type`, `summary`, `description`, `parent`, `template_name`, `template_vars`, `labels`, `extra_fields` | Sets the active key for following steps. Only these keys are read — top-level `components` and other unknown keys are ignored. `parent` required for sub-task types. `template_name` applies template `components`, `fields`, and `parent` (see [Create-step fields](#create-step-fields-what-is-honored)). `extra_fields` for any other named field (display names, schema-encoded; see [fields.md](fields.md)). String fields accept `{placeholders}` from `--var`. |
| `convert` | `issue_type` (or `type`), optional `parent` | Change issue type. `parent` required when converting to a sub-task type; converting away from a sub-task clears parent. Uses the active key unless `issue_key` is set. |
| `assign` | `assignee` | Email, display name, account ID, or `@me` |
| `reporter` | `reporter` | Same lookup rules as assign |
| `transition` | `status` | Status **name** or transition ID (must be valid for that issue) |
| `comment` | `message` or `comment_text` | Plain text; newlines → paragraphs (ADF) |
| `label` | `labels` | List of labels to **add** (not replace) |
| `sprint` | `sprint_id` | Numeric id, `"@current_sprint"`, or omit (active sprint on `defaults.board`) |
| `summary` | `summary` | Replace issue summary (single line) |
| `description` | `description` or `message` | Replace description (multiline); empty/null clears |
| `field` | `field` or `name`, `value` | Update any field by display name or id (schema-encoded) |
| `run` | `command`, `format`, `extra`, `cwd`, `timeout_seconds`, `fail_on_error` | External program (argv list, no shell). See [External commands](#external-commands-run). |
Any step may include `issue_key` to override the current key.

## External commands (`run`)

A `run` step executes a program with **no shell** (`subprocess`, `shell=False`). The program path and args are defined **in the workflow JSON** (not in `user.yaml`). Chain context is passed on **stdin**.

```json
{
  "action": "run",
  "command": ["./hooks/echo_payload.sh"],
  "format": "json",
  "timeout_seconds": 60,
  "fail_on_error": true,
  "cwd": "examples/workflows",
  "extra": { "channel": "#jira" }
}
```

| Field | Meaning |
|-------|---------|
| `command` | **Required.** Non-empty list of strings (argv). String form is rejected. |
| `format` | `json` (default), `yaml`, or `text` — stdin encoding |
| `extra` | Optional object copied into the stdin payload for your script |
| `cwd` | Optional working directory (must exist); default is the process cwd |
| `timeout_seconds` | Default **60**; hard cap **300** |
| `fail_on_error` | Default **true** — non-zero exit or timeout stops the chain |

**Stdin payload** (json/yaml object; `text` is line-oriented):

| Field | Meaning |
|-------|---------|
| `issue_key` | Active key after earlier steps (if any) |
| `step_index` | Index of this `run` step in the chain |
| `results` | Prior step outcomes (`create` key, `sprint_id`, comment ids, …) |
| `extra` | Your step `extra` object |
| `format` | Encoding name (`json` / `yaml` / `text`) |

For `text`: lines like `ISSUE_KEY=…`, `RESULTS_JSON=…`, `EXTRA_JSON=…`.

**Security defaults**

- No shell; no custom env map (child inherits `jflow`’s environment).
- Kill switch: `JFLOW_DISABLE_EXEC=1` makes `run` fail immediately (useful for locked-down hosts).
- Only run **trusted** workflow files — `run` steps can execute local commands.
- Does **not** pass API tokens or full issue fields unless you put them in `extra` yourself (avoid that).

Demo: [`run_external_example.json`](../examples/workflows/run_external_example.json) + [`hooks/echo_payload.sh`](../examples/workflows/hooks/echo_payload.sh).

## Example files

| File | Use when |
|------|----------|
| [`create_and_start.json`](../examples/workflows/create_and_start.json) | Create → assign → In Progress → comment |
| [`create_from_template.json`](../examples/workflows/create_from_template.json) | Create via template (applies template `components`/`fields`) + `-V` / `template_vars`, then comment |
| [`create_to_sprint.json`](../examples/workflows/create_to_sprint.json) | Create → add to sprint (`sprint_id`) → In Progress |
| [`start_existing.json`](../examples/workflows/start_existing.json) | Assign / transition / comment an existing issue (positional key) |
| [`staging_create_assign_comment.json`](../examples/workflows/staging_create_assign_comment.json) | Staging/reference: create → assign → comment |
| [`run_external_example.json`](../examples/workflows/run_external_example.json) | Run demo hook with JSON stdin (`run` action) |

Index and security notes: [`examples/workflows/README.md`](../examples/workflows/README.md).

```bash
jflow -f json issue chain examples/workflows/create_and_start.json \
  -V project=PROJ -V summary="Investigate intermittent timeout"
jflow issue chain PROJ-123 examples/workflows/start_existing.json
# From repo root (uses cwd in the workflow JSON):
jflow -f json issue chain examples/workflows/run_external_example.json
```

Replace project keys and other `--var` values before running against a real site. Ensure `defaults.board` is set when using `@current_sprint`.

## Recipes

### Create, assign, start, comment

See [`create_and_start.json`](../examples/workflows/create_and_start.json):

```bash
jflow issue chain examples/workflows/create_and_start.json \
  -V project=PROJ -V summary="Investigate intermittent timeout"
```

### Create from template (components, fields, dynamic summary)

See [`create_from_template.json`](../examples/workflows/create_from_template.json). Requires `bug_report` (or your template name) in `user.yaml`. The template’s `components` and `fields` are applied on create. Pass vars with `-V` or embed `template_vars` in the JSON. For fields without a template, use `extra_fields` (not a top-level `"components"` key).

### Create, add to current sprint, start work

See [`create_to_sprint.json`](../examples/workflows/create_to_sprint.json) (`"sprint_id": "@current_sprint"`). Requires `defaults.board`.

### Start work on an existing issue

```bash
jflow issue chain PROJ-123 examples/workflows/start_existing.json
```

### External command after (or instead of) Jira steps

See [`run_external_example.json`](../examples/workflows/run_external_example.json). Put Jira steps before `run` if the script needs `issue_key` / prior `results`.

### Shell-friendly: chain with template vars + current sprint

```bash
jflow issue chain examples/workflows/create_from_template.json \
  -V component=Auth -V env=Prod -V steps="Click login"
```

