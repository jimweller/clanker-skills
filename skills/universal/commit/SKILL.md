---
name: commit
description: Create an atomic conventional commit with AI context tracking
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 📌

# Commit Changes

## Process

### 1. Review Changes

````bash
git status
git diff HEAD
git diff --stat HEAD
```text

Check for new untracked files:

```bash
git ls-files --others --exclude-standard
```text

### 2. Stage Files

Add the untracked and changed files relevant to the current work.

**Do NOT stage:**

- `.env` or credential files
- Large binary files
- Files unrelated to the current task

### 3. Create Commit

Write an atomic commit message with a conventional commit tag:

- `feat:` -- New capability or feature
- `fix:` -- Bug fix
- `refactor:` -- Code restructure without behavior change
- `docs:` -- Documentation only
- `test:` -- Test additions or fixes
- `chore:` -- Build, CI, tooling changes
- `perf:` -- Performance improvement

**For monorepo changes spanning multiple packages**, note the primary package in the scope:

```text
feat(workflows): add DAG condition evaluator
fix(web): resolve SSE reconnection on navigation
refactor(isolation): simplify worktree resolution order
```text

**Commit message format:**

```text
tag(scope): concise description of what changed

[Optional body explaining WHY this change was made,
not just what changed. Include context changes that aren't
obvious from the diff.]

[Optional: Fixes #123, Closes #456]
```text

### 4. Capture AI Context Changes

If any AI context assets were modified in this commit, add a `Context:` section to the commit body:

```text
feat(orchestrator): add retry logic for session recovery

Added exponential backoff when SDK subprocess crashes mid-session.
Previously a single crash would fail the entire workflow.

Context:
- Updated .claude/rules/orchestrator.md with retry conventions
- Added .claude/commands/debug-session.md for session state inspection
- Surfaced issue: mock.module() in retry tests needs isolated batch

Fixes #482
```text

**What counts as AI context changes:**

- `.claude/rules/` -- on-demand conventions added, updated, or removed
- `.claude/commands/` -- slash commands created or modified
- `.claude/skills/` -- slash commands created or modified
- `.llmdocs/` -- reference docs added or updated
- `CLAUDE.md` -- global rules changes
- `**/CLAUDE.md` -- folder local rules changes

Git log is long-term memory for future sessions.
````
