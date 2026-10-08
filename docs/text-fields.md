<!--
  Created in whole or in part by AI using Cursor (Grok).
  Co-created through collaborative AI pair programming with Gemini.
  Refined / authored with assistance from Cursor (Grok).
  Updated in whole or in part by AI using Cursor (Composer).
-->

# Summary, description, and comments

How text fields work in `jflow`, including multiline handling and editing after create.

## Requirements on create

| Field | Required? | Notes |
|-------|-----------|--------|
| **Summary** | Yes | Via `-s`, a template, or both. Jira (and this tool) require it. |
| **Description** | No | Omit `--desc` to create without one. |

## Summary (single line)

Jira summaries are single-line. If you pass newlines, they are collapsed to spaces on update.

```bash
# On create
jflow issue create -p PROJ -t Task -s "Fix login timeout"

# Change later (positional; quoting optional for multi-word text)
jflow issue summary PROJ-123 Fix login timeout on mobile
```

Workflow step:

```json
{ "action": "summary", "summary": "Updated title" }
```

## Description (multiline)

Set on create with `--desc` / `-d`, or via a template. **Newlines become separate paragraphs** in Jira (ADF).

```bash
# bash: $'...' expands \n
jflow issue create -p PROJ -t Task -s "Bug" \
  --description $'Steps:\n1. Open app\n2. Tap login\n\nExpected: success'

# Replace description later (positional; quoting optional)
jflow issue description PROJ-123 Line one
jflow issue description PROJ-123 --clear
```

In YAML templates and workflow JSON, use `\n` inside strings:

```yaml
description: "Steps to reproduce:\n{steps}"
```

```json
{ "action": "description", "description": "Para 1\n\nPara 2" }
```

Edits **replace** the whole description (they do not append).

## Comments (multiline)

Same newline → paragraph behavior as descriptions.

```bash
# Multi-word comments do not need quotes
jflow issue comment PROJ-123 Done with QA
# Newlines still work when quoted / $'...'
jflow issue comment PROJ-123 $'Done with QA.\n\nNext: deploy to staging.'
```

Workflow:

```json
{ "action": "comment", "message": "Line 1\nLine 2" }
```

## Labels

CLI labels **replace** the full set by default. Use flags to add or remove without wiping others:

```bash
# Replace all labels with these
jflow label PROJ-123 bug urgent
# same: jflow issue label PROJ-123 bug urgent

# Add without removing existing
jflow label PROJ-123 --append needs-review

# Remove specific labels
jflow label PROJ-123 --delete stale
```

Space- or comma-separated tokens are accepted. In a workflow chain, `"action": "label"` with a `"labels"` list **adds only** (it does not replace or delete)—see [workflows.md](workflows.md#cli-vs-chain-naming).

## Tips

- Prefer `$'…\n…'` in bash, or JSON/`"\n"` in workflow files.
- Template and chain `--var` values can include `\n` (see [templates.md](templates.md)).
- Chain string fields accept `{placeholders}` filled by `issue chain --var` / `-V`.
- See [workflows.md](workflows.md) for `summary` / `description` chain actions.
