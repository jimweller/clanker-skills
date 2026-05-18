---
name: obsidian
description: Obsidian vault operations using the obsidian cli
---

# Obsidian CLI

The official Obsidian CLI (v1.12+) controls Obsidian from the terminal via IPC with a running desktop instance.

> Read `references/command-reference.md` for specific flags, output formats, or
> subcommands. It covers all 130+ commands with full parameter tables.

## Prerequisites

| Requirement      | Details                                           |
| ---------------- | ------------------------------------------------- |
| Obsidian Desktop | v1.12.0+                                          |
| CLI enabled      | Settings, Command line interface, Toggle ON       |
| Obsidian running | Desktop app must be running for CLI to work (IPC) |

## Syntax

All parameters use `key=value` syntax. Quote values containing spaces.

```bash
obsidian <command> [subcommand] [key=value ...] [flags]
```

### Multi-Vault

Target a specific vault by making it the first argument:

```bash
obsidian "My Vault" daily:read
obsidian "Work Notes" search query="meeting"
```

If omitted, the CLI targets the most recently active vault.

## Command Overview

The CLI provides 130+ commands across these groups:

| Group      | Key Commands                                                                                                     | Purpose                                                   |
| ---------- | ---------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| files      | `read`, `create`, `append`, `prepend`, `move`, `rename`, `delete`, `files`, `folders`, `file`, `random`          | Note CRUD and file discovery                              |
| daily      | `daily`, `daily:read`, `daily:append`, `daily:prepend`, `daily:path`                                             | Daily note operations                                     |
| search     | `search`, `search:context`                                                                                       | Full-text search; `search:context` returns matching lines |
| properties | `properties`, `property:read`, `property:set`, `property:remove`, `aliases`                                      | Frontmatter/metadata management                           |
| tags       | `tags`, `tag`                                                                                                    | Tag listing, counts, and filtering                        |
| tasks      | `tasks`, `task`                                                                                                  | Task querying, filtering, and toggling                    |
| links      | `backlinks`, `links`, `unresolved`, `orphans`, `deadends`                                                        | Graph and link analysis                                   |
| bookmarks  | `bookmarks`, `bookmark`                                                                                          | List and add bookmarks                                    |
| templates  | `templates`, `template:read`, `template:insert`                                                                  | Template listing, rendering, insertion                    |
| plugins    | `plugins`, `plugin`, `plugin:enable`, `plugin:disable`, `plugin:install`, `plugin:uninstall`, `plugins:restrict` | Plugin management                                         |
| sync       | `sync`, `sync:status`, `sync:history`, `sync:read`, `sync:restore`, `sync:deleted`                               | Obsidian Sync operations                                  |
| themes     | `themes`, `theme`, `theme:set`, `theme:install`, `theme:uninstall`                                               | Theme management                                          |
| snippets   | `snippets`, `snippets:enabled`, `snippet:enable`, `snippet:disable`                                              | CSS snippet management                                    |
| commands   | `commands`, `command`, `hotkeys`, `hotkey`                                                                       | Execute Obsidian commands by ID; inspect hotkeys          |
| bases      | `bases`, `base:query`, `base:views`, `base:create`                                                               | Obsidian Bases (v1.12+ database feature)                  |
| history    | `history`, `history:list`, `history:read`, `history:restore`                                                     | File version recovery (File Recovery plugin)              |
| workspace  | `workspace`, `tabs`, `tab:open`                                                                                  | Workspace layout and tab management                       |
| diff       | `diff`                                                                                                           | Compare local vs sync file versions                       |
| dev        | `eval`, `dev:screenshot`, `dev:debug`, `dev:console`, `dev:errors`, `dev:css`, `dev:dom`, `devtools`             | Developer/debugging tools                                 |
| vault      | `vault`, `vaults`, `version`, `reload`, `restart`                                                                | Vault info and app control                                |
| other      | `outline`, `wordcount`, `recents`                                                                                | Utility commands                                          |

## Quick Reference

### Reading and Writing Notes

```bash
obsidian read path="folder/note.md"
obsidian create path="folder/note" content="# New Note"
obsidian create path="folder/note" template="meeting-notes"
obsidian append path="folder/note.md" content="New paragraph"
obsidian prepend path="folder/note.md" content="Top content"
obsidian move path="old/note.md" to="new/note.md"
obsidian delete path="folder/note.md"
obsidian delete path="folder/note.md" permanent
```

### Daily Notes

```bash
obsidian daily                          # Open today's daily note
obsidian daily:read                     # Print content of today's note
obsidian daily:append content="- [ ] New task"
obsidian daily:prepend content="## Morning Notes"
```

### Search

```bash
obsidian search query="project alpha"
obsidian search query="TODO" path="projects" limit=10
obsidian search query="meeting" format=json
obsidian search query="urgent" case
```

### Properties and Tags

```bash
obsidian properties path="note.md"
obsidian property:set path="note.md" name="status" value="active"
obsidian property:read path="note.md" name="status"
obsidian property:remove path="note.md" name="draft"
obsidian tags counts sort=count
obsidian tag name="project/alpha"
```

### Tasks

```bash
obsidian tasks                          # All tasks
obsidian tasks all                      # All tasks
obsidian tasks done                     # Completed only
obsidian tasks daily                    # Tasks in today's daily note
obsidian task path="note.md" line=12 toggle
obsidian tasks | grep "\[ \]"           # Filter to incomplete only
```

### Developer and Automation

```bash
obsidian eval code="app.vault.getFiles().length"
obsidian dev:screenshot path="folder/screenshot.png"
obsidian dev:debug on
obsidian dev:console limit=20
obsidian dev:errors
```

## TUI Mode

Running `obsidian` with no arguments launches an interactive TUI.

## Common Agent Patterns

### Daily Journal Automation

```bash
obsidian daily:append content="## $(date '+%H:%M') -- Status Update
- Completed: feature branch merge
- Next: code review for PR #42
- Blocked: waiting on API credentials"
```

### Create Note from Template with Metadata

```bash
obsidian create path="projects/new-feature" template="project-template"
obsidian property:set path="projects/new-feature.md" name="status" value="planning"
obsidian property:set path="projects/new-feature.md" name="created" value="$(date -I)"
obsidian daily:append content="- Started [[projects/new-feature|New Feature]]"
```

### Vault Analytics

```bash
obsidian files total                    # Total file count
obsidian tags counts sort=count         # Most used tags
obsidian tasks | grep "\[ \]"          # Incomplete tasks across vault
obsidian orphans                        # Notes needing integration
obsidian unresolved                     # Broken links to fix
```

### Search and Extract

```bash
obsidian search query="meeting notes" format=json | jq '.[]'
obsidian read path="meetings/standup.md" | grep "Action item"
```

### Sync Management

```bash
obsidian sync:status                    # Check sync health
obsidian sync:history path="important.md"
obsidian sync:restore path="important.md" version=3
```

### Execute Obsidian Commands

```bash
obsidian commands | grep "graph"
obsidian command id="graph:open"
obsidian command id="app:open-settings"
```

## Direct File Editing

`obsidian vault` returns the filesystem path of the active vault. Use this path with Read, Edit, and Write tools to modify markdown files directly instead of delete/recreate cycles through the CLI.

```bash
obsidian vault          # returns: path /Users/.../ObsidianVault/MCG
```

Frontmatter (properties, tags, dates) is plain YAML between `---` fences. No special format. Default frontmatter for new notes:

```yaml
---
tags:
  - topic-a
  - topic-b
created: 2026-04-14
---
```

Tags should be lowercase, hyphenated. Created date is ISO 8601 (YYYY-MM-DD). Read/Edit/Write handles everything including metadata. Use the CLI for search, vault operations, and commands that interact with the Obsidian app (sync, plugins, templates, eval).

## Tips

1. Paths are vault-relative. Use `folder/note.md`, not absolute filesystem paths.
2. `create` paths omit `.md`. The extension is added automatically.
3. `move` requires full target path including `.md` extension.
4. Plain text output works with `grep`, `awk`, `sed`, `jq`.
5. Use `format=json` on `search` for JSON array of file paths.
6. `daily:prepend` inserts content after frontmatter, not at byte 0.
7. Use `eval` to run arbitrary JavaScript against the Obsidian API (`app.*`).
8. `template:insert` inserts into the currently active file in the Obsidian UI. To create a file from a template via CLI, use `obsidian create path="..." template="..."`.
9. `property:set` stores list values as strings. For proper array fields, edit frontmatter directly or use `eval`.
10. `eval` requires single-line JavaScript. For multiline, write to a temp file first.
11. Multi-vault targeting may not work in all environments. If vault name fails, omit it and switch vaults manually in Obsidian UI.
