<!--
  Created in whole or in part by AI using Cursor (Grok 4.5).
  Updated in whole or in part by AI using Cursor (Composer).
-->

# Fields and schema cache

Jira Cloud has many custom fields (and system fields) whose ids look like `customfield_10100`. **jflow** downloads field metadata into a local cache so you can use **display names** and simple values instead of raw API shapes.

## Sync the cache

```bash
jflow cache sync
```

This writes `~/.config/jflow/fields_cache.json` (created on first sync or first field resolve). List cached fields with:

```bash
jflow cache fields
```

Open the JSON file anytime to see exact field **names**, **ids**, and **schema** types for your site.

The cache refreshes automatically when a name is missing. Run `cache sync` after admins add or rename fields.

## Update any field by name

```bash
# String custom field
jflow issue field PROJ-123 \
  --name "Environment" \
  --value "QA"

# Number
jflow issue field PROJ-123 --name "Story Points" --value 5

# Option (select list) — pass the option label; encoding adds {"value": "..."}
jflow issue field PROJ-123 --name "Priority" --value "High"

# Array / multi-select — pass JSON
jflow issue field PROJ-123 \
  --name "Flagged" \
  --value '["Impediment"]'
```

`--name` accepts the display name from the cache **or** a raw id (`customfield_10100`). `--value` is parsed as JSON when possible; otherwise it is treated as a string.

## Fields shown by `jflow show`

By default, `jflow show` / `jflow issue show` use a fixed set of system fields. To include custom fields (or a shorter set), set `defaults.show_fields` in `user.yaml`:

```yaml
defaults:
  show_fields:
    - summary
    - status
    - assignee
    - description
    - Story Points          # display name from cache
    - Git Pull Request
    - customfield_10100     # raw id also accepted
```

Unset or empty keeps the built-in set. `jflow show KEY --only status --only summary` overrides the config list for that invocation. Run `jflow cache sync` first so display names resolve.

See also [output-formats.md](output-formats.md).

## When to use dedicated commands

Keep using the focused commands when they fit:

| Command | Use when |
|---------|----------|
| `jflow issue story-points` | Setting story points |
| `jflow issue blocked` | Toggle Flagged / Impediment |
| `jflow issue components` | Set component list after create |
| `jflow issue field` | Any other custom or system field by name |

Dedicated helpers stay unchanged; `issue field` is the generic path.

## Templates and workflows

Templates can set `components` and a `fields:` map of name → value. Names must match the cache (run `cache sync` first). See [templates.md](templates.md).

In a workflow `create` step:

- **`template_name`** — applies the template’s `components` and `fields` (same as `issue create -T`).
- **`extra_fields`** — same human names / schema encoding for fields not coming from a template (including components via the cache name, often `Component/s`).
- Only documented create keys are read; a top-level `"components"` key on the step is **ignored**. Prefer template `components:` or `extra_fields`.

```json
{
  "action": "create",
  "project": "PROJ",
  "issue_type": "Task",
  "summary": "Work item",
  "extra_fields": {
    "Component/s": "API",
    "Story Points": 3
  }
}
```

To update a field later in a chain:

```json
{ "action": "field", "field": "Environment", "value": "QA" }
```

Full create-step rules: [workflows.md](workflows.md#create-step-fields-what-is-honored).
