<!--
  Created in whole or in part by AI using Cursor (Grok 4.5).
-->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `jflow issue convert KEY TYPE [PARENT]` — change any issue type; parent required when converting to a sub-task type; converting away from a sub-task clears parent
- `jflow issue create --parent KEY` — create Sub-task in one shot (parent required for sub-task types)
- Template first-class `parent` (supports `{placeholders}`); CLI `--parent` overrides template
- Workflow `create` honors `parent`; new chain action `convert` (`issue_type`, optional `parent`)
- `jflow issue chain --var` / `-V` fills `{placeholders}` in workflow strings and merges into create `template_vars`
- Chain `sprint` action accepts `"sprint_id": "@current_sprint"` (or omits `sprint_id`) using active sprint on `defaults.board`

## [0.2.6] - 2026-10-08

### Added

- `defaults.show_fields` in `user.yaml` to control which fields `jflow show` / `jflow issue show` fetch and display (display names or `customfield_*` ids; CLI `--only` overrides)
- `decode_field_value` for human-readable custom/system field values on show
- Explicitly requested show fields always appear in text/markdown output even when empty
- Template field token `@current_sprint` (adds created issue to the active sprint on `defaults.board`)
- `jflow link` / `jflow issue link` with native-type shortcuts and `--type`
- `jflow issue pullrequest` (append by default; `--overwrite` / `--clear`)

### Removed

- `global.yaml` scaffolding and config path (`--global-yaml` / `JFLOW_GLOBAL_YAML` / `GlobalConfig`); config is `user.yaml` only

## [0.2.5] - 2026-10-07

### Removed

- FastMCP server (`jflow-mcp`), `fastmcp` dependency, MCP docs, and `mcp_roles` / `MCPRole` from global config (CLI-only)
- `jflow-staging-test` console script (staging runner remains in-package: `python -m jflow.staging.cli`)

### Changed

- Trailing positional text for `comment`, `issue summary`, `issue description`, `change`, `query` / `issue search`, and `boards search` joins all remaining argv tokens, so multi-word values need not be quoted

## [0.2.4] - 2026-10-06

### Fixed

- Normalize issue keys to uppercase (Agile sprint APIs reject lowercase keys like `proj-123`)

## [0.2.3] - 2026-10-06

### Fixed

- `jflow sprint add` always uses `defaults.board` (or `--board`) to pick the active sprint when `--sprint-id` is omitted; errors include board/sprint context

## [0.2.2] - 2026-10-06

### Changed

- Breaking: `jflow label` / `issue label` now **appends** by default; use `--overwrite` to replace all labels; removed `--append`
- `jflow issue blocked` resolves Flagged/Blocked via the field schema cache (no hardcoded `customfield_10021` fallback) and encodes Impediment with the field schema

### Fixed

- Clearer error when Flagged/Blocked cannot be resolved (`jflow cache sync` / `cache fields`)

## [0.2.1] - 2026-10-06

### Changed

- Breaking CLI UX: prefer positional arguments over short-flag options for common issue commands (`assign`, `comment`, `reporter`, `field`, `chain`, `summary`, `description`, `due-date`, `parent`, `components`, `story-points`, `blocked`) and `boards search`
- `jflow create` / `issue create`: `--desc` / `-d` → `--description`
- Create success output is `{key, url}` (browse URL from server base) instead of `{id, key, self, summary}`
- Clearable fields require an explicit `--clear` (empty values no longer clear)
- Removed `table` output format (was a `text` alias)

### Added

- `@me` token for assignee/reporter resolution (authenticated user)

## [0.2.0] - 2026-09-28

First published release of **jflow** (package `jflow`, CLI `jflow` / `jflow-mcp` / `jflow-staging-test`, config under `~/.config/jflow/`).

### Added

- Field schema cache (`jflow cache sync`) storing name, id, and datatype in `~/.config/jflow/fields_cache.json`
- Generic field update: CLI `jflow issue field`, MCP `update_field_tool` / `sync_fields_tool`, workflow action `field`
- Template support for `components` and a `fields:` map (schema-encoded on create); `extra_fields` on create uses the same encoder
- Docs: [docs/fields.md](docs/fields.md); templates/workflows/MCP/README updates
- `jflow boards list` (paginate all) and `boards search -q` (name substring); board name/id resolution for sprint commands
- `jflow issue show` / `issue list`; top-level `query`; `issue change` (renamed from transition)
- `jflow cache sync` / `cache fields` (renamed from `fields sync`)
- `unix` output format (TSV lists / `key=value` dicts)
- `defaults.board` in `user.yaml` (id or name)
- Sprint CLI group: `sprint list|current|add|create|state|backlog`
- `jflow version` and `jflow status` (client / me / server sections)
- MCP `list_boards_tool` / `get_status_tool`; board-using tools accept `board` name or id
- Query/search `--var` for `{placeholder}` fill in JQL aliases
- Custom `--show-completion SHELL` (bash|zsh|fish) for manual sourcing
- Top-level aliases: `show`, `list`, `create`, `assign`, `comment`, `label`, `change` (same as nested `issue …`)
- OAuth 2.0 (3LO) beside API tokens: `jflow auth login|logout|status`, token file, Bearer client via `api.atlassian.com/ex/jira/{cloudId}`; [docs/auth.md](docs/auth.md)
- `markdown` output format with structure-aware issue views (title, metadata, description, comments); local+ISO timestamps in human formats

### Changed

- Breaking CLI rename: removed `issue sprints`, `issue sprint-add`, `issue backlog`, `sprint-create`, `sprint-state` in favor of the `sprint` / `boards` groups
- Sprint board flag is `--board` / `-b` (name or id) instead of `--board-id`
- Breaking: removed `me`, `server-info`, `--key`/`-k`, query `--jql`/`-q`; issue keys and JQL are positional
- Breaking: replaced `label-add` / `label-remove` / `label-set` with `issue label [--append|--delete]`
- Breaking: removed `--install-completion`; use `--show-completion` instead
- Breaking: `issue status` → `issue change` (plus top-level `change`); `sprint issue-add` → `sprint add`
- Shell completion uses Typer’s script/runtime (`complete_bash`); re-source `--show-completion` after upgrade. Nested groups and closed-choice values (`--format`, `--filter`, `--comments`, `--state`) complete correctly.
- Default output format is `markdown` (structured human layout); `text` is plain structured; `table` remains a `text` alias (no Rich box-drawing)
- Root-level `--format` / `--user-yaml` / `--global-yaml` (no longer per-command)
- Status and MCP `get_status` use friendly keys under `client` / `me` / `server`
- MCP: removed `get_myself` / `get_server_info` tools in favor of `get_status`

## [0.1.0] - 2026-09-16

Early development snapshot (not published under the `jflow` name).

### Added

- CLI entry point `jflow` for issue lifecycle operations (create, search, assign, transition, comment, field updates)
- FastMCP server entry point `jflow-mcp` for AI clients (Claude Desktop, Cursor, and similar)
- Issue templates with `{placeholder}` substitution and CLI `--var` overrides
- Sprint helpers: add to sprint, list sprints/backlog, create and update sprint state
- Multi-step JSON workflow chains (`issue chain`), including optional trusted external `run` steps
- Label, due date, parent, component, story point, and blocked-link updates
- ADF-aware summary, description, and comment text handling
- User and global YAML configuration under `~/.config/jflow/`, overridable via flags or `JFLOW_USER_YAML` / `JFLOW_GLOBAL_YAML`
- MCP per-client tool allowlists via `global.yaml` and `MCP_CLIENT_KEY`
- Output formats: table, JSON, and YAML
- Staging integration test runner (`jflow-staging-test`) with packaged fixtures and example workflows
- Example configs and workflow JSON under `examples/`
- Project documentation under `docs/` (MCP, templates, workflows, text fields, staging tests)

[Unreleased]: https://github.com/jobbler/jflow/compare/v0.2.5...HEAD
[0.2.5]: https://github.com/jobbler/jflow/releases/tag/v0.2.5
[0.2.4]: https://github.com/jobbler/jflow/releases/tag/v0.2.4
[0.2.3]: https://github.com/jobbler/jflow/releases/tag/v0.2.3
[0.2.2]: https://github.com/jobbler/jflow/releases/tag/v0.2.2
[0.2.1]: https://github.com/jobbler/jflow/releases/tag/v0.2.1
[0.2.0]: https://github.com/jobbler/jflow/releases/tag/v0.2.0
[0.1.0]: https://github.com/jobbler/jflow/releases/tag/v0.1.0
