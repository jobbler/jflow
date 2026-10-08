<!--
  Created in whole or in part by AI using Cursor (Grok).
-->

# Boards and sprints

Agile boards and sprints are grouped under `jflow boards` and `jflow sprint`. Pass a board as a **name or numeric id** with `--board` / `-b`, or set a default so you can omit the flag.

## Default board

In `user.yaml`:

```yaml
defaults:
  board: "42"          # or a board name, e.g. "PROJ board"
```

Sprint commands that need a board use `defaults.board` when `--board` is omitted.

## Boards

```bash
# All Agile boards (paginated; optional --limit)
jflow boards list
jflow boards list --limit 20

# Name substring search
jflow boards search -q PROJ
```

Output includes numeric **id** and **name** — use either with `--board` afterward.

## Sprints

| Command | Purpose |
|---------|---------|
| `sprint list --board … [--state active\|future\|closed]` | List sprints for a board (default state `active`) |
| `sprint current --board …` | Show the active sprint |
| `sprint add ISSUE [--sprint-id N \| --board …]` | Add an issue to a sprint (by id, or board’s active sprint) |
| `sprint create --name … --board …` | Create a sprint (optional `--start` / `--end` / `--goal`) |
| `sprint state --sprint-id N --state …` | Update state (`active` / `closed` / `future`) or metadata |
| `sprint backlog --board …` | List backlog issues |

```bash
jflow sprint list --board 42 --state active
jflow sprint current --board "PROJ board"
jflow sprint add PROJ-123 --board 42
jflow sprint add PROJ-123 --sprint-id 10001
```

## Workflows vs CLI

Chain workflows that add an issue to a sprint need a numeric `"sprint_id"` in the JSON. There is no “current sprint” keyword in chain steps. Prefer `sprint add --board …` on the CLI when you want the active sprint without looking up an id. See [workflows.md](workflows.md#sprints-in-workflows-vs-cli).

## Staging runner note

The **staging** runner (`python -m jflow.staging.cli`) still takes `--board-id` (numeric only). That flag is **not** the same as main CLI `--board`. See [staging-tests.md](staging-tests.md).

## Related

- Output formats: [output-formats.md](output-formats.md)
- Field cache / custom fields: [fields.md](fields.md)
