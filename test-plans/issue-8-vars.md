# Testing `defaults.vars`

Manual checks for named `{placeholder}` values in `user.yaml`. Run from the `issue-8-jql-vars` worktree, logged in to a real Jira instance (`jflow login` done, `defaults.project` set). All commands are `jflow …` from the repo: `.venv/bin/jflow …`.

## Sample `user.yaml` section

Add to your `user.yaml` (adjust `jira.email` is already set; the pointer test uses it):

```yaml
defaults:
  project: "PROJ"          # your real project key
  vars:
    user: jira.email        # pointer: resolved to your configured email
    component: "My Team Component"   # literal
    team: "my.team"         # looks like a pointer but path doesn't exist -> stays literal
    project: "OVERRIDE"     # optional: set to prove vars.project beats defaults.project
jql_aliases:
  team-issues: 'assignee = "{user}" AND project = {project} AND component = "{component}"'
templates:
  bug_report:
    summary: "[BUG] {component}: Issue in {env}"
    issue_type: "Bug"
```

## 1. JQL: `query` / `issue search`

|#|Command|Expected|
|---|---|---|
|1.1|`jflow query 'project = {project} AND assignee = "{user}"'`|Query runs; `{project}` = `PROJ` (or `OVERRIDE` if `vars.project` set), `{user}` = your email. Results or Jira "no match", NOT a 400 about `{`.|
|1.2|`jflow query team-issues`|Alias expands and all three placeholders fill (`{component}` = `My Team Component`).|
|1.3|`jflow query "project = {project} AND summary ~ {word}"` without `-V`|Fails fast with `Unknown JQL placeholder(s): {word}. Define them under defaults.vars in user.yaml or pass --var/-V name=value.` — before any request.|
|1.4|Same with `-V word=login`|Runs; no error.|
|1.5|`jflow query 'assignee = "{user}"' -V user=not-me@example.com`|CLI value wins over saved var.|

## 2. JQL: `list --jql` / `issue list --jql`

|#|Command|Expected|
|---|---|---|
|2.1|`jflow list --jql 'project = {project} AND assignee = "{user}"'`|Same filling as query; table renders.|
|2.2|`jflow issue list --jql "summary ~ {word}"`|Same unknown-placeholder error as 1.3.|

## 3. Templates: `issue create -T`

|#|Command|Expected|
|---|---|---|
|3.1|`jflow create -T bug_report -V env=Prod -V component=Auth`|Summary `[BUG] Auth: Issue in Prod`. (Pre-existing behavior.)|
|3.2|`jflow create -T bug_report -V env=Prod` (no `-V component`)|Summary `[BUG] My Team Component: Issue in Prod` — `defaults.vars` fills `{component}`.|
|3.3|`jflow create -T bug_report -V env=Prod -V component=Other`|Summary `[BUG] Other: Issue in Prod` — CLI wins.|
|3.4|Template with an unknown `{placeholder}`|Left as written in the created issue (templates do NOT fail fast; only JQL does).|

Use `--dry-run` if available, or delete the test issues after.

## 4. Pointer resolution

|#|Setup|Expected|
|---|---|---|
|4.1|`vars: {user: jira.email}`|`{user}` → configured email (used in 1.1).|
|4.2|`vars: {team: "my.team"}`|Stays literal `my.team` — matches dotted-path shape but no such config path; no error.|
|4.3|Point at a real non-string setting, e.g. `vars: {proj: defaults.project}`|Resolved to that value (`PROJ`).|

## 5. Chain / workflow

|#|Setup|Expected|
|---|---|---|
|5.1|Run a workflow/chain with a step containing `{component}` in summary or template fields, no `-V`|`defaults.vars` fills it.|
|5.2|Same with `-V component=X`|CLI value wins.|

## 6. Config edge cases

|#|Setup|Expected|
|---|---|---|
|6.1|`vars.project: "OVERRIDE"` + `defaults.project: "PROJ"`|`{project}` = `OVERRIDE`.|
|6.2|`-V project=OTHER`|`OTHER` beats both.|
|6.3|No `vars:` section at all|Everything behaves as before (issue #7 behavior).|
|6.4|Old `jql_vars:` key in yaml|Ignored by pydantic (not an alias) — verify your yaml uses `vars:`.|
