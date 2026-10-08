<!--
  Created in whole or in part by AI using Cursor (Grok).
  Co-created through collaborative AI pair programming with Gemini.
  Refined / authored with assistance from Cursor (Grok).
-->

# jflow

The **CLI** for Jira Cloud allowing fluid Jira queries, templates, and workflows.

Create and update issues, run JQL searches, manage sprints and labels, and chain multi-step workflows from your terminal.

> **AI collaboration** — Co-designed with **Gemini**. Documentation and cleanup refined with **Cursor (Grok)**.

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Install on Linux](#install-on-linux)
- [Configuration](#configuration)
- [Quick start](#quick-start)
- [Command overview](#command-overview)
- [Further documentation](#further-documentation)

## Features

- **Issue lifecycle** — Create, search (raw JQL or named aliases), assign, change status (`issue change`), comment, and update summary/description
- **Field updates** — Labels, due date, parent, components, story points, blocked links, and generic updates by field name (`issue field`) using a local schema cache
- **Templates** — Reusable issue templates with `{placeholder}` substitution, components, named custom fields, and CLI `--var` overrides
- **Sprints & boards** — List boards; add issues to a sprint by id or board (name or id); list sprints/backlog; create/update sprint state; optional `defaults.board`
- **Auth** — API token (default) or OAuth 2.0 (3LO); see [docs/auth.md](docs/auth.md)
- **Workflow chains** — Multi-step JSON workflows (`issue chain`), including optional trusted external `run` steps
- **Flexible config** — User YAML under `~/.config/jflow/`, overridable by flags or env (`JFLOW_USER_YAML`)
- **Output formats** — Structured `markdown` (default), plain `text`, `unix`, JSON, or YAML (config default or root `-f`)
- **Shell completion** — Print a script with `jflow --show-completion bash` and source it yourself (static scripts also live in the repo root)
- **Staging tests** — Optional live integration checks against a disposable Jira project

Keep real credentials only in `~/.config/jflow/` (or private paths). Example configs in this repo use placeholders only.

## Requirements

- Linux
- Python **3.9+**
- [pipx](https://pipx.pypa.io/) (recommended for an isolated global install)
- A Jira Cloud site and an [API token](https://id.atlassian.com/manage-profile/security/api-tokens)

Install `pipx` if needed:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
# reopen the shell so `pipx` is on PATH
```

On Fedora you can also use `sudo dnf install pipx`.

## Install on Linux

### From a local clone (recommended while developing)

```bash
# clone or copy this repository, then:
cd /path/to/jflow
pipx install .

# or without changing directory:
pipx install /path/to/jflow
```

Upgrade after local changes:

```bash
pipx install --force .
# or:
pipx reinstall jflow
```

This installs the `jflow` command.

### From a Git URL (placeholder)

Once the project is published, install with:

```bash
pipx install git+https://github.com/jobbler/jflow.git
```

Replace `YOUR_USERNAME/jflow` with the real repository path when available.

## Configuration

### Initialize config files

```bash
jflow init
```

Creates:

| File | Purpose |
|------|---------|
| `~/.config/jflow/user.yaml` | Credentials, defaults, templates, JQL aliases |
| `~/.config/jflow/fields_cache.json` | Field name/id/schema cache (`jflow cache sync`) |

Overwrite existing files:

```bash
jflow init --force
```

Example templates live in [`examples/config/`](examples/config/).

### Edit credentials

Open `~/.config/jflow/user.yaml`. **API token** (default):

```yaml
jira:
  auth: "api_token"
  domain: "your-domain.atlassian.net"
  email: "your-email@example.com"
  api_token: "YOUR_JIRA_API_TOKEN"
```

**OAuth 2.0 (3LO)** is also supported (`auth: oauth`, then `jflow auth login`). See [docs/auth.md](docs/auth.md).

Also set `defaults.project` (and optional `defaults.board` as a board id or name) for fewer CLI flags.

### Override config paths

Default is `~/.config/jflow/user.yaml`. Most commands accept an alternate file anywhere on the filesystem:

```bash
jflow query my-bugs --user-yaml /path/to/user.yaml
```

Alias `--user-settings` also works.

You can set the same override via environment variable (useful for scripts). Resolution order is: CLI flag, then env, then the default path.

```bash
export JFLOW_USER_YAML=/path/to/user.yaml
jflow status
```

### Verify connectivity

```bash
jflow status
jflow version
```

### Shell completion

Print a completion script and add it to your shell config yourself (no installer):

```bash
jflow --show-completion bash >> ~/.bashrc
# or: jflow --show-completion zsh >> ~/.zshrc
# reopen the shell (or source your rc file)
jflow sprint <TAB>
```

After upgrading jflow, re-run `--show-completion` and replace the old sourced script (instruction format changed for Typer ≥0.26). Nested groups (`issue`, `sprint`, `auth`, …) and closed-choice flags (`--format`, `--filter`, `--comments`, `--state`) complete via Tab.

## Quick start

```bash
# Create an issue (top-level alias or nested)
jflow create -p PROJ -t Task -s "Fix login timeout"
# same: jflow issue create ...

# Create from a template (see docs/templates.md)
jflow create -T bug_report \
  -V component=Auth -V env=Prod -V steps="Click login"

# Search with raw JQL or a configured alias (see docs/jql-aliases.md)
jflow query 'assignee = currentUser() ORDER BY updated DESC'
jflow issue search my-bugs
jflow query project-open --var project=PROJ

# List my open issues / show one
jflow list --filter open
jflow show PROJ-123
jflow show PROJ-123 --comments last

# Assign, change status, comment, labels (trailing text needs no quotes)
jflow assign PROJ-123 teammate@example.com
jflow change PROJ-123 In Progress
jflow comment PROJ-123 Started investigation
jflow label PROJ-123 bug urgent
jflow label PROJ-123 --overwrite needs-review

# Boards and sprints (board id or name; defaults.board avoids --board)
jflow boards list
jflow boards search PROJ
jflow create -p PROJ -t Task -s "Fix timeout"
jflow sprint add PROJ-123 --board 42
jflow change PROJ-123 In Progress

# Multi-step workflow JSON (see docs/workflows.md). Use -V for {placeholders};
# @me / @current_sprint work in chain steps (defaults.board required for sprint token).
jflow issue chain examples/workflows/create_and_start.json \
  -V project=PROJ -V summary="Investigate intermittent timeout"
jflow issue chain PROJ-123 examples/workflows/start_existing.json
```

Root options such as `--format` / `-f` and config paths apply before the subcommand:

```bash
jflow -f json query my-bugs
jflow -f unix list
```

Output format defaults come from config (`markdown`, `text`, `unix`, `json`, `yaml`, or `table` as a text alias). See [docs/output-formats.md](docs/output-formats.md).

## Command overview

| Command | Description |
|---------|-------------|
| `jflow init` | Scaffold config under `~/.config/jflow/` |
| `jflow cache sync` | Download field names/schema into `fields_cache.json` |
| `jflow cache fields` | List fields from the local cache |
| `jflow version` | Package version (no network) |
| `jflow status` | Client, me, and server sections (health) |
| `jflow auth login` / `logout` / `status` | OAuth 2.0 (3LO) token management |
| `jflow query` | JQL or alias search (same as `issue search`); supports `--var` |
| `jflow show` / `list` / `create` / `assign` / `comment` / `label` / `change` | Top-level aliases for common `issue` commands |
| `jflow boards list` | List all Agile boards (id and name; optional `--limit`) |
| `jflow boards search` | Search boards by name substring (`-q`; optional `--limit`) |
| `jflow issue create` | Create issue (optional `--template` / `--var` / `--parent`; Sub-task requires `--parent`) |
| `jflow issue list` | List my issues (`--filter` / `--status` / `--jql`) |
| `jflow issue show ISSUE` | Show issue details (`--comments none\|last\|all\|N`, `--only`) |
| `jflow issue search` | JQL or alias search; supports `--var` |
| `jflow issue assign` / `reporter` | Set assignee or reporter |
| `jflow issue change ISSUE STATUS` | Change issue workflow status |
| `jflow issue convert ISSUE TYPE [PARENT]` | Change issue type (parent required for Sub-task) |
| `jflow issue comment` | Add a comment (multiline OK) |
| `jflow issue summary` / `description` | Update summary or description |
| `jflow issue field` | Update any field by display name or id |
| `jflow issue label` | Replace labels (default), or `--append` / `--delete` |
| `jflow issue due-date` / `parent` / `components` / `story-points` / `blocked` | Field updates |
| `jflow issue chain` | Run a JSON workflow |
| `jflow sprint list` | List board sprints (`--board` name or id) |
| `jflow sprint current` | Show the active sprint for a board |
| `jflow sprint add` | Add issue to a sprint (`--sprint-id` or `--board`) |
| `jflow sprint backlog` | List backlog issues |
| `jflow sprint create` / `sprint state` | Create or update sprint state |

Run `jflow --help`, `jflow sprint --help`, and `jflow issue --help` for full flag lists.

## Further documentation

| Guide | Topic |
|-------|--------|
| [docs/auth.md](docs/auth.md) | API token vs OAuth 2.0 (3LO), `auth login` |
| [docs/output-formats.md](docs/output-formats.md) | `markdown` / `text` / `unix` / `json` / `yaml` (`-f`, config default) |
| [docs/boards-and-sprints.md](docs/boards-and-sprints.md) | Boards, `--board`, sprint commands |
| [docs/fields.md](docs/fields.md) | Field schema cache, `cache sync`, `issue field` |
| [docs/templates.md](docs/templates.md) | Issue templates and `{placeholders}` |
| [docs/workflows.md](docs/workflows.md) | Chained workflow actions |
| [docs/text-fields.md](docs/text-fields.md) | Summary, description, comments, labels |
| [docs/jql-aliases.md](docs/jql-aliases.md) | Named JQL shortcuts |
| [docs/staging-tests.md](docs/staging-tests.md) | Live staging integration tests |
| [examples/workflows/README.md](examples/workflows/README.md) | Example chain JSON workflows |

## Development / tests

Unit suite (mocked / local):

```bash
python3 -m pip install -e .
python3 run_all_tests.py
```

Staging integration tests (requires staging `user.yaml`; default is read-only):

```bash
python -m jflow.staging.cli \
  --user-yaml /path/to/staging-user.yaml \
  --board-id 123
```

See [docs/staging-tests.md](docs/staging-tests.md) for `--lifecycle`, `--group`, and safety notes.
