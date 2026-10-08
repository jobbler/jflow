<!--
  Created in whole or in part by AI using Cursor (Grok).
-->

# Output formats

`jflow` prints results in one of several formats. Choose with the root flag or a config default.

## How to set the format

| Source | Example |
|--------|---------|
| Root flag (wins for that invocation) | `jflow -f json status` or `jflow --format unix list` |
| Config default | `defaults.output_format` in `user.yaml` |

```yaml
defaults:
  output_format: "markdown"   # markdown | text | unix | json | yaml  (table ≈ text)
  # Optional: fields for `jflow show` (names or customfield ids). See fields.md.
  # show_fields: [summary, status, assignee, "Story Points"]
```

## Formats

| Name | Best for | Behavior |
|------|----------|----------|
| `markdown` (default) | Terminal reading / piping to `glow` or a pager | Structured issue views (`#` title, metadata, `## Description`, `## Comments`). Lists become bullet lines. Nested payloads (e.g. `status`) use `##` sections. |
| `text` | Plain terminal reading | Same hierarchy as markdown without MD markers (title, `Label: value` metadata, Description/Comments blocks). Lists stay space-aligned columns. |
| `table` | Same as `text` | Alias for `text` (no separate Rich table mode). |
| `unix` | Shell scripts | Flat dicts → `key=value` lines (nested dicts flattened). Lists of objects → TSV with a header row. Timestamps stay raw ISO. |
| `json` | Tools / scripting | Indented JSON. Timestamps stay raw ISO. |
| `yaml` | Readable dumps | YAML document. Timestamps stay raw ISO. |

## Issue `show` layout (markdown / text)

Human formats separate title, metadata, description, and comments. Metadata prints every non-empty field from the issue payload (except `key`/`summary`/`description`/`comments`), in a stable order. Which fields are fetched is controlled by `defaults.show_fields` or `--only` (see [fields.md](fields.md)).

Timestamps in human formats show **local time and ISO together**, for example:

`2026-09-20 09:32 CDT (2026-09-20T14:32:11.000+0000)`

Machine formats (`json`, `yaml`, `unix`) keep the original ISO string only.

Description and comment bodies are plain text (from ADF), not rich markdown.

## Examples

```bash
# Structured issue view (markdown default)
jflow show PROJ-123 --comments all

# Same layout without markdown markers
jflow -f text show PROJ-123 --comments last

# Sectioned health output
jflow status

# Script-friendly list of my issues
jflow -f unix list --filter open

# Machine-readable show
jflow -f json show PROJ-123

# Pretty markdown in the terminal (optional host tool)
jflow show PROJ-123 --comments all | glow
```

Root options such as `-f` come **before** the subcommand:

```bash
jflow -f unix sprint list --board 42
```

## Related

- Boards and sprints: [boards-and-sprints.md](boards-and-sprints.md)
- Quick start samples: [README](../README.md#quick-start)
