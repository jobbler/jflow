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

Placeholders like `{project}` are filled from your settings, then from `--var key=value` (same syntax as issue templates). A `--var` / `-V` value wins for that one search.

`{project}` uses `defaults.project`. Other names live in `defaults.vars`. The same list fills templates and chains. A name the settings do not know is left as written.

```yaml
defaults:
  project: "PROJ"
  vars:
    user: me
    component: "My Team Component"
```

## Use aliases

Pass the alias name (or raw JQL) as the first argument to `query` / `issue search`. If the name matches an alias key, the mapped JQL is used; otherwise the string is treated as raw JQL.

```bash
jflow query my-bugs
jflow issue search active-sprint --limit 25
jflow query project-open
jflow query "assignee = {user} AND project = {project}"
jflow query project-open --var project=OTHER
jflow query "assignee = {user} AND project = {project}" -V user=not-me

# Raw JQL still works
jflow issue search 'project = PROJ AND status = "To Do"'
```

## How resolution works

1. `AppConfig.resolve_jql()` looks up the string in `user.jql_aliases` and returns the mapped query or the original input.
2. `{placeholders}` are filled from `defaults.project` and `defaults.vars`.
3. `--var` / `-V` replaces a saved name for that one command. Unknown `{placeholders}` stay as written.

The same filling applies to `jflow list --jql` and `jflow issue list --jql`.

The CLI passes the loaded config so aliases apply. Alias names are exact string matches (including hyphens). Prefer short, memorable keys without spaces.
