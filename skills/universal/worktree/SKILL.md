---
name: worktree
description: Git worktree management for parallel branch development. Use for creating, merging, rebasing, and removing worktrees.
argument-hint: "[create|list|merge|rebase|remove] [branch-name]"
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🎋

# Git Worktree Management

Manage git worktrees for parallel branch development. Worktrees live under `~/.worktrees/<repo>/<branch>`. Slashes in branch names create nested directories (e.g. `feature/foo` becomes `~/.worktrees/<repo>/feature/foo`).

## Arguments

Extract the operation and branch name from the user's message.
First argument is the operation. Second argument is the branch name (required for create, merge, rebase, remove).
If no operation was specified, default to `list`.

## Path Discovery

All operations derive paths from git, not from `dirname` math.

```bash
PRIMARY=$(git worktree list --porcelain | awk '/^worktree / { print $2; exit }')
REPO_NAME=$(basename "$PRIMARY")
WORKTREE_DIR="$HOME/.worktrees/$REPO_NAME/<branch>"
```

`PRIMARY` is the original clone (the first entry in `git worktree list`). Other worktrees live under `~/.worktrees/$REPO_NAME/`.

## Operations

### create <branch>

Create a new worktree under `~/.worktrees/<repo>/<branch>` with a new branch. Copy `.llmtmp/` from the primary if present. Open a new tmux window named `wt:<branch>` if running inside tmux. Focus does not switch.

```bash
PRIMARY=$(git worktree list --porcelain | awk '/^worktree / { print $2; exit }')
REPO_NAME=$(basename "$PRIMARY")
WORKTREE_DIR="$HOME/.worktrees/$REPO_NAME/<branch>"

mkdir -p "$(dirname "$WORKTREE_DIR")"
git worktree add "$WORKTREE_DIR" -b <branch>

[ -d "$PRIMARY/.llmtmp" ] && cp -r "$PRIMARY/.llmtmp" "$WORKTREE_DIR/.llmtmp"

[ -n "$TMUX" ] && tmux new-window -d -n "wt:<branch>" -c "$WORKTREE_DIR"
```

After creation, report the worktree path and the tmux window number (if created).

### list

Show all worktrees.

```bash
git worktree list
```

### merge

Merge the current worktree's branch into main. Run from the feature worktree.

Pre-check: verify the current branch is NOT main. If on main, refuse.

```bash
PRIMARY=$(git worktree list --porcelain | awk '/^worktree / { print $2; exit }')
BRANCH=$(git rev-parse --abbrev-ref HEAD)

git -C "$PRIMARY" fetch origin && git -C "$PRIMARY" pull
git -C "$PRIMARY" merge "$BRANCH"
git -C "$PRIMARY" push origin main
```

If there are conflicts, help the user resolve them before pushing.

### rebase <branch>

Rebase a branch onto the latest main. Must be run from within the branch's worktree.

Pre-check: verify the current branch matches `<branch>`. If not, refuse and instruct the user to switch to the correct worktree.

```bash
git fetch origin
git rebase origin/main
```

If there are conflicts, help the user resolve them. After successful rebase, force-push is required if the branch was previously pushed (only with explicit permission per safety rules).

### remove <branch>

Remove a worktree and delete its branch. Must be run from the primary worktree.

Pre-checks:

1. Verify the current directory is the primary worktree (`git rev-parse --show-toplevel` equals `$PRIMARY`). If not, refuse.
2. Verify the branch is merged into main using `git branch --merged`. If not merged, refuse and instruct the user to merge first.

```bash
PRIMARY=$(git worktree list --porcelain | awk '/^worktree / { print $2; exit }')
REPO_NAME=$(basename "$PRIMARY")
WORKTREE_DIR="$HOME/.worktrees/$REPO_NAME/<branch>"

git worktree remove "$WORKTREE_DIR"
git branch -d <branch>

PARENT="$(dirname "$WORKTREE_DIR")"
while [ "$PARENT" != "$HOME/.worktrees" ] && rmdir "$PARENT" 2>/dev/null; do
  PARENT="$(dirname "$PARENT")"
done
```

If `git branch -d` fails with "not fully merged", stop and tell the user to merge first. Never use `git branch -D`.

The `rmdir` loop cleans up empty parent directories left by slash-nested branch names and removes the per-repo dir when no branches remain.

## Safety Rules

- Local merges only. Do not create pull requests.
- If the worktree has unstaged or uncommitted work during remove, ask the user about merging or forcing delete.
- Never delete a worktree branch manually. Only use `git worktree remove`.
- Never delete a worktree directory manually. Always use `git worktree remove`.
- Never force push without explicit user permission.
- Derive paths from `git worktree list --porcelain`. Never hardcode paths.
