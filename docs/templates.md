<!--
  Created in whole or in part by AI using Cursor (Grok).
  Co-created through collaborative AI pair programming with Gemini.
  Refined / authored with assistance from Cursor (Grok).
  Updated in whole or in part by AI using Cursor (Grok 4.5).
  Updated in whole or in part by AI using Cursor (Composer).
-->

# Issue templates

Templates live under `templates:` in `user.yaml` (default path `~/.config/jflow/user.yaml`; see also [`examples/config/user.yaml`](../examples/config/user.yaml)).

## When to use a template

| Approach | Best for |
|----------|----------|
| `issue create -s "…"` | One-off summaries |
| `issue create -T name -V key=value` | Reusable shapes (bugs, chores) with placeholders filled at invoke time |
| Chain `template_name` + `template_vars` or `issue chain -V` | Same reusable shape inside a multi-step workflow |

Templates set **create** fields: summary, description, type, project, labels, **components**, and optional **named fields**. They do **not** transition status. To put the new issue on the active sprint, use the `@current_sprint` token (requires `defaults.board` in `user.yaml`):

```bash
jflow issue create -T bug_report -V component=Auth -V env=Prod -V steps="Click login"
jflow issue change PROJ-123 "In Progress"
```

## Define a template

```yaml
templates:
  bug_report:
    summary: "[BUG] {component}: Issue in {env}"
    description: "Steps to reproduce:\n{steps}"
    issue_type: "Bug"
    labels: ["bug"]
    components: ["{component}"]
    fields:
      "Environment": "QA"
      Sprint: "@current_sprint"
    # optional:
    # project: "PROJ"
```

| Field | Required | Notes |
|-------|----------|--------|
| `summary` | usually | Supports `{placeholders}` |
| `description` | no | Supports `{placeholders}` |
| `issue_type` | no | Falls back to CLI / defaults |
| `project` | no | Falls back to CLI / defaults |
| `labels` | no | Applied on create |
| `components` | no | List of component names; string entries support `{placeholders}` |
| `fields` | no | Map of **field display name** → value (custom or system). Names must match the [field cache](fields.md). Values support `{placeholders}` in strings. Use `@current_sprint` on the Sprint field to add the issue to the active sprint on `defaults.board` after create. |

Placeholders use `{name}` syntax (letters, digits, underscore). Unresolved placeholders are left unchanged in the text.

**Field names:** run `jflow cache sync`, then copy exact names from `~/.config/jflow/fields_cache.json` into `fields:`. Values are encoded from the cached schema (string, number, option, etc.). Details: [fields.md](fields.md).

**Multiline:** put `\n` in `description` (or in `--var` values). Newlines become separate Jira paragraphs. Summaries stay single-line. Details: [text-fields.md](text-fields.md).

## Create from a template (CLI)

```bash
jflow issue create \
  --template bug_report \
  --var component=Auth \
  --var env=Staging \
  --var steps="1. Open checkout\n2. Submit payment"
```

That example fills the summary placeholder **and** sets `components` to `Auth` when the template uses `components: ["{component}"]`.

Short flags:

```bash
jflow issue create -T bug_report \
  -V component=Auth -V env=Prod -V steps="Click login"
```

CLI flags such as `--project`, `--type`, `--summary`, and `--desc` can override template values when provided.

## Use a template in a workflow

A chain `create` step with `template_name` applies the **same** template attrs as `issue create -T`: summary, description, type, project, labels, **`components`**, and **`fields`**. You do not need a top-level `"components"` key in the workflow JSON (that key is ignored on create steps — see [workflows.md](workflows.md#create-step-fields-what-is-honored)).

Put variables in the JSON **or** pass them with `issue chain --var` / `-V` (merged into `template_vars`; CLI wins on conflicts):

```bash
jflow issue chain examples/workflows/create_from_template.json \
  -V component=Payments -V env=Prod -V steps="Timeout on submit"
```

```json
{
  "action": "create",
  "template_name": "bug_report",
  "template_vars": {
    "component": "Payments",
    "env": "Prod",
    "steps": "Timeout on submit"
  }
}
```

With the sample `bug_report` template (`components: ["{component}"]`), that create sets the component to `Payments` from `-V` / `template_vars`.

To set components or other named fields **without** a template, use create-step `extra_fields` (e.g. `"Component/s": "Payments"`). Details: [workflows.md](workflows.md#create-step-fields-what-is-honored) and [fields.md](fields.md).

Full example: [`examples/workflows/create_from_template.json`](../examples/workflows/create_from_template.json).
