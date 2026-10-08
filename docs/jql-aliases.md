<!--
  Created in whole or in part by AI using Cursor (Grok).
  Co-created through collaborative AI pair programming with Gemini.
  Refined / authored with assistance from Cursor (Grok).
-->

# JQL aliases

Named shortcuts for common JQL queries live under `jql_aliases:` in `user.yaml`.

## Define aliases

```yaml
jql_aliases:
  my-bugs: "assignee = currentUser() AND issuetype = Bug AND status != Closed"
  active-sprint: "project = PROJ AND sprint in openSprints()"
  project-open: "project = {project} AND status != Closed"
```

Placeholders like `{project}` are filled with `--var key=value` (same syntax as issue templates).

## Use aliases

Pass the alias name (or raw JQL) as the first argument to `query` / `issue search`. If the name matches an alias key, the mapped JQL is used; otherwise the string is treated as raw JQL.

```bash
jflow query my-bugs
jflow issue search active-sprint --limit 25
jflow query project-open --var project=PROJ

# Raw JQL still works
jflow issue search 'project = PROJ AND status = "To Do"'
```

## How resolution works

1. `AppConfig.resolve_jql()` looks up the string in `user.jql_aliases` and returns the mapped query or the original input.
2. Optional `--var` values substitute `{placeholders}` via `render_string`.

The CLI passes the loaded config so aliases apply. Alias names are exact string matches (including hyphens). Prefer short, memorable keys without spaces.
