---
name: readme
description: Write or update README.md files from folder contents and conversation history. Use when asked to write, refresh, or fix a README.
argument-hint: "[optional guidance]"
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 📓

# Documentation Creation

Write markdown content based on the current conversation context and folder contents.

README is current state specification for a human user, not a changelog, not a decision log, not historical record. Never record
historical information or choices made, only the specification as it stands at the time of writing the README.

## Related Skills

- use the md-syntax skill (/md-syntax, $md-syntax) for markdown rules and syntax
- use the md-style skill (/md-style, $md-style) for authoring conventions and writing style
- After writing, use the md-lint skill (/md-lint, $md-lint) on the file to format and lint

## Scope

Find all README.md files in the project and update each.
Folder contents are at the README's level and below (siblings and subfolders), never above (parents).
Pay attention to subfolder layers, scope and bounded contexts. Do not leak
concepts between documents at different layers. Each README covers its own
directory level and below, never parent concerns.

If the user provided specific guidance or focus areas, apply that context
when deciding what to emphasize in the documentation.

## Gather Context

For each README found, scoped to its directory:

1. Read current README (if exists)
2. Compute what changed since it was last touched. Include committed, staged, unstaged, and untracked work:

```bash
TARGET_README=<path to the README being updated>
TARGET_DIR=$(dirname "$TARGET_README")

BASELINE=$(git log -1 --format=%H -- "$TARGET_README" 2>/dev/null)
[ -z "$BASELINE" ] && BASELINE=$(git rev-list --max-parents=0 HEAD 2>/dev/null)
HEAD_SHA=$(git rev-parse --verify -q HEAD)

if [ -n "$BASELINE" ] && [ "$BASELINE" != "$HEAD_SHA" ]; then
  git log --oneline "$BASELINE"..HEAD -- "$TARGET_DIR"
  git diff "$BASELINE" --stat -- "$TARGET_DIR"
  git diff "$BASELINE" -- "$TARGET_DIR"
elif [ -n "$HEAD_SHA" ]; then
  git show --stat HEAD -- "$TARGET_DIR"
  git diff HEAD --stat -- "$TARGET_DIR"
  git diff HEAD -- "$TARGET_DIR"
fi

git status --short -- "$TARGET_DIR"
```

`--stat` must come before `--`. Placed after it, git reads it as a pathspec and silently prints the full diff instead of the summary.

Read the `--stat` summary first and let it decide whether to run the full diff. A README with no commit of its own falls back to the root commit, so the full diff can be the entire history of that directory, thousands of lines on a mid-sized repository. When the summary is large, skip the full diff and read the changed files directly.

The diff carries no `..HEAD`, so it spans the baseline through the working tree and includes staged and unstaged edits. The branches cover four states: a README with a commit of its own, a README with none, a repository whose only commit is the root, and a repository with no commits at all. Without them an empty or HEAD-equal baseline makes every command return nothing and the skill wrongly concludes there is nothing to document.

`git status --short` lists staged, unstaged, and untracked paths in one view. Untracked files appear as `??` and their content is in no diff, so read those files directly. Files matching `.gitignore` are excluded throughout.

3. Explore codebase at that directory level and below
4. Review conversation history for relevant decisions, changes, or lessons learned
5. Use the diff and conversation context to identify what sections need updating. Verify code against docs and docs against code.

If nothing changed that warrants a README update, say so and move on.

## README.md Outline

Section order and content for a README.md. Every section is filled from the target project. Omit a section the project has nothing for.

- `# Title` and an overview of no more than five sentences
- Optional image or video
- `## Architecture` - components as a bullet list, each with its purpose
- `## Prerequisites` - accounts, keys, credentials, tools, runtimes, CLIs, each with the reason it is needed
- `## Project Structure` - folders only, no files, each with a one-line purpose
- `## Installation` - the commands that install it
- `## Usage` - the commands that run it
- `## Testing` - omitted when the project has no tests

Target under 500 lines. Split a longer README by moving detail into a nested README beside the code it describes.

### Shape

````markdown
# Title

Brief overview. No more than five sentences.

<!-- OPTIONAL IMAGE OR VIDEO HIGHLIGHT -->
<img src="demo.png" alt="Demo" width="800"/>

## Architecture

High level components and purpose

- Component - purpose
- Component - purpose

## Prerequisites

- Prerequisite - description and reason (accounts, keys, credentials, tools, runtimes, CLIs)

## Project Structure

Show folder structure. Don't include files.

```text
project/
├── src/
│   ├── component-a/     # purpose - see src/component-a/README.md
│   └── component-b/     # purpose - see src/component-b/README.md
├── scripts/             # purpose
└── tests/               # purpose
```

## Installation

```bash
# how the project is installed
<install command>
```

## Usage

```bash
# how the project is run
<run command>
```

## Testing

```bash
# how the tests are run
<test command>
```
````
