---
name: relay
description: Write a session state document for a follow-up agent
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 📡

# Relay: Capture Session State for Continuation

Capture session state so a follow-up run can continue.

## What the Relay File Is

`.llmtmp/relay.md` is a one-shot message from a dying session to the session that replaces it. It is written once, read once, and then it is garbage.

It is not a plan file. It is not a task list. It is not project state. It has no lifecycle beyond the handoff.

An agent that reads a relay file to resume work does not update it, check items off in it, append progress to it, or keep it in sync with the work. The relay file is stale the moment the next session starts, and that is correct. The only reason to write `.llmtmp/relay.md` again is a fresh `/relay` invocation at the end of another session, which overwrites it wholesale.

## Process

### 1. Analyze the Current Session

Review everything that happened in this conversation:

- What was the original goal or task?
- What has been completed so far?
- What is still in progress or blocked?
- What key decisions were made and WHY?
- What files were read, created, or modified?
- What errors were encountered and how were they resolved?
- What dead ends were explored (so a follow-up run doesn't repeat them)?

### 2. Gather Current State

````bash
git status
git diff --stat HEAD
git log --oneline -5
git branch --show-current
```text

### 3. Write the Relay Document

Save to: `.llmtmp/relay.md` in the current working directory (or the worktree root if in a worktree).

**Use this exact structure:**

```markdown
# Relay: [Brief Task Description]

**Date:** [current date]
**Branch:** [current branch name]
**Last Commit:** [hash + message, or "uncommitted changes"]

> One-time handoff. Read once, do not update.

## Goal

[1-2 sentences: what we're trying to accomplish. Include the original user request or plan reference.]

## Completed

- [x] [Task 1 — brief description of what was done]
- [x] [Task 2 — brief description]
  - [Sub-detail if non-obvious]

## In Progress / Next Steps

- [ ] [Task 3 — what needs to happen next, with enough detail to act on]
- [ ] [Task 4 — include file paths and specific areas to focus on]
- [ ] [Task 5 — any blocked items with explanation of the blocker]

## Key Decisions

Document WHY choices were made, not just what was chosen:

- **[Decision]**: [What was chosen] — [Why, including alternatives rejected]
- **[Decision]**: [What was chosen] — [Why]

## Dead Ends (Don't Repeat These)

- [Approach that was tried and didn't work] — [Why it failed]
- [Investigation path that turned out to be irrelevant] — [What we found instead]

## Files Changed

- `path/to/file.ts` — [what changed and why, 1 line]
- `path/to/new-file.ts` — [NEW: what this file does]
- `path/to/deleted-file.ts` — [DELETED: why it was removed]

## Current State

- **Tests:** [passing/failing — which specific tests and why]
- **Type-check:** [clean/N errors — what kind]
- **Lint:** [clean/N warnings — what kind]
- **Build:** [working/broken]
- **Manual verification:** [what was tested manually, results]

## Relay Context

[2-4 sentences: the MOST IMPORTANT thing the next agent needs to know. What's the current situation? What's the biggest risk? What should they do first?]

**Recommended first action:** [Exact command or step to take first]
```text

### 4. Confirm and Advise

After writing the relay:

1. Confirm the file was written with its full path
2. Suggest this resume command:

   ```text
   Read .llmtmp/relay.md and continue from where the previous session left off.
````

3. If there are uncommitted changes, suggest committing first:

   ```text
   /commit
   ```

## Quality Criteria

A good relay document should:

- Let a fresh agent continue without asking any clarifying questions
- Be under 100 lines (concise, not comprehensive — link to files rather than duplicating content)
- Include enough "why" context that the next agent makes the same decisions
- Explicitly list dead ends to prevent wasted exploration
- Have a concrete "first action" recommendation

## Anti-patterns

- Don't include full file contents — reference paths instead
- Don't include conversation history or debugging transcripts — summarize findings
- Don't be vague ("fix the bug") — be specific ("fix the SSE reconnection in `packages/web/src/hooks/useSSE.ts` by adding exponential backoff after the `onclose` handler")
- Don't skip the "Dead Ends" section — this prevents the most common wasted effort
- Don't forget the "Key Decisions" section — without it, the next agent may reverse your decisions
- Don't treat the relay file as a living document — no incremental edits, no checking off boxes, no appending progress as work proceeds
- Don't re-read the relay file mid-session to see what's left — the conversation is the source of truth once work resumes
- Don't reference `.llmtmp/relay.md` in commits, PR descriptions, or docs — it is scratch, not an artifact
