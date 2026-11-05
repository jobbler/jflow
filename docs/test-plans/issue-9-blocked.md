# Testing computed `blocked` status (issue #9)

Manual checks for the read-only `blocked` virtual field. Run from the `issue-9-blocked` worktree, logged in to a real Jira instance (`jflow login` done). All commands are `jflow …`.

`blocked` is computed, never written to Jira. Rule: issue is in progress AND (unresolved "is blocked by" link OR any ancestor blocked OR native Blocked/Flagged field set). Display appends ` (blocked)` to the status text.

## 1. `issue list` / `query` with a blocked column

|#|Command|Expected|
|---|---|---|
|1.1|`jflow issue list --fields key,status,blocked`|Table renders a `Blocked` column with `yes`/`no`. In-progress issues with an unresolved blocked-by link show `In Progress (blocked)` in the Status cell.|
|1.2|`jflow issue list` (no `--fields`, no `defaults.list_fields`)|Default Key/Type/Summary/Status/Assignee columns unchanged — `blocked` is opt-in.|
|1.3|`jflow query 'project = PROJ' --fields key,blocked`|Works without `defaults.board` (unlike `current_sprint`).|
|1.4|Add `blocked` to `defaults.list_fields` in `user.yaml`|Column appears for every list/query run.|
|1.5|`jflow query 'project = PROJ' --fields key,status,blocked --output json`|Rows contain `"Blocked": "yes"`/`"no"`; no `_blocked` internal key leaks into output.|

## 2. `issue show`

|#|Command|Expected|
|---|---|---|
|2.1|`jflow issue show KEY` on an in-progress issue with an unresolved blocked-by link|Output renders (this itself verifies the restored emit path) and includes `Blocked: yes`; status line reads `In Progress (blocked)`.|
|2.2|Same issue after the blocker moves to Done (or gets a resolution)|`Blocked: no`; status line plain `In Progress`.|
|2.3|`jflow issue show KEY --only blocked`|Single `Blocked: yes/no` detail.|
|2.4|`jflow issue show KEY --only status,blocked`|Status line + blocked line only.|
|2.5|Done-status issue with an unresolved blocked-by link|`Blocked: no` — done issues are never blocked.|
|2.6|Issue whose parent epic is blocked|`Blocked: yes` even if the issue itself has no links.|
|2.7|Issue with the native Blocked/Flagged field set (if your site has one)|`Blocked: yes` on the flag alone, in progress.|

## 3. No writes

|#|Check|Expected|
|---|---|---|
|3.1|Run 2.1, then reload the issue in the Jira UI|Issue is unchanged — no status edits, no comment, no field write. The existing `jflow issue blocked KEY` write command is untouched.|
