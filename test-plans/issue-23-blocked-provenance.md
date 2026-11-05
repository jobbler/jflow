# Testing blocked provenance (issue #23)

Manual checks for *why* an issue is blocked: reason strings in `show`, node annotation in `tree`. Run from the repo worktree, logged in to a real Jira instance. Read-only — nothing is written to Jira.

## 1. `issue show` — reason detail

|#|Setup|Command|Expected|
|---|---|---|---|
|1.1|In-progress issue with an unresolved "is blocked by" link to PROJ-42|`jflow issue show KEY`|`Blocked: yes (blocked by PROJ-42)`; status line `In Progress (blocked)`.|
|1.2|Same issue, blocker now Done/resolved in Jira|`jflow issue show KEY`|`Blocked: no`; plain status.|
|1.3|In-progress issue with the native Blocked/Flagged field set, no links|`jflow issue show KEY`|`Blocked: yes (native flag)`.|
|1.4|Story whose epic is blocked (story itself has no links)|`jflow issue show STORY`|`Blocked: yes (ancestor EPIC-1)` — the nearest blocked ancestor.|
|1.5|Story deeper in the chain with unblocked intermediates above it|`jflow issue show STORY`|Still `yes (ancestor <nearest blocked ancestor key>)` — the walk continues past unblocked parents.|
|1.6|Link + flag together|`jflow issue show KEY`|`Blocked: yes (blocked by PROJ-42; native flag)` — reasons joined with `;`.|
|1.7|Blocker issue deleted or not visible to your account|`jflow issue show KEY`|`Blocked: yes (blocked by PROJ-99 (unavailable))` — no error.|
|1.8|Done-status issue with unresolved link|`jflow issue show KEY`|`Blocked: no`.|
|1.9|`--only blocked` / `--only status,blocked`|`jflow issue show KEY --only blocked`|Same blocked line; comma form works.|

## 2. `tree` — node annotation

|#|Setup|Command|Expected|
|---|---|---|---|
|2.1|Epic blocked (any cause) with in-progress and done children|`jflow tree STORY-KEY`|Epic and every in-progress descendant render ` (blocked)` after status; done descendants don't. Blocked-by links themselves are NOT drawn (by design — run `show` on a node for the link detail).|
|2.2|Same tree, json|`jflow --format json tree STORY-KEY`|Every node has `"blocked": "yes"/"no"`; no `_`-prefixed keys.|
|2.3|Unblocked hierarchy|`jflow tree KEY`|No `(blocked)` suffixes, `"blocked": "no"` throughout.|
|2.4|Native-flag-blocked epic (no links)|`jflow tree KEY`|Epic shows ` (blocked)` — verifies the field-cache resolution on plain `jflow tree` (no `--fields` needed).|
|2.5|Child of a blocked epic, text|`jflow tree CHILD`|Child line carries ` (blocked)`; no ` | blocked:` noise in text/markdown.|

## 3. No writes / compat

|#|Check|Expected|
|---|---|---|
|3.1|Run 1.1 and 2.1, then reload the issues in the Jira UI|Unchanged — read-only.|
|3.2|`jflow issue list --fields key,status,blocked`|Blocked column still plain `yes`/`no` (reasons live in show only).|
