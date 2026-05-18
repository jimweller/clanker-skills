---
name: ralph-review
description: Review a Ralph plan and bd graph for defects via a subagent.
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🔍

# Ralph Review

Dispatch a subagent to review the ralph plan and bd graph for defects.

## Dispatch

The launcher validates the bd graph, captures graph state, then invokes the subagent.

### 1. Validate the bd Graph

Derive the slug and locate the run epic:

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
SLUG=$(git branch --show-current | tr '/' '-')
EPIC=$(bd list -t epic -l "ralph:${SLUG}" --json | jq -r '[.[] | select(.status=="open")] | .[0].id // empty')
```

Run structural checks. Each failure is a HIGH finding:

- Exactly one open epic with label `ralph:${SLUG}`
- `bd dep cycles` reports no cycles
- Epic has at least one child (`bd list --parent "$EPIC"`)
- At least one ready task (`bd ready --parent "$EPIC"`)
- Every child has a description
- Parent set (`bd list --parent "$EPIC"`) equals label set (`bd list --label "ralph:${SLUG}"` excluding the epic)

Check for isolated nodes (MEDIUM).

If any HIGH finding, report directly and stop. The graph must be sound before review.

### 2. Capture Graph State

```bash
bd list --parent "$EPIC" --json
bd ready --parent "$EPIC" --json
bd list --label "ralph:${SLUG}" --json
```

### 3. Invoke the Subagent

Dispatch a subagent with the review prompt below. Substitute `<PROJECT_ROOT>`, `<SLUG>`, `<EPIC>`, the graph validation findings, and the captured graph state.

Relay the response verbatim, prefixed with the graph validation findings.

## Review Prompt

You are a plan reviewer. Read the plan, evaluate it against the graph state, and review for defects.

### Source

Read `<PROJECT_ROOT>/.llmtmp/ralph-plan.md`. Then locate the `## Inputs` section and parse the `plan documents:` line. Split on commas, trim whitespace, Read each path. These are plan documents: forward-looking intent the planner consulted (a PRD, a design note). The plan must faithfully render them. Flag the plan if it omits, contradicts, or stale-references a plan document requirement.

### How Ralph Loops Work

A ralph loop is an autonomous, iterative execution mechanism. Two modes share the same artifacts:

- **In-session (ralph-loop plugin)**: a Stop hook re-feeds the prompt to the same Claude session.
- **External (scripts/ralph.sh)**: a bash while-loop spawns a fresh `claude --print` per iteration.

Mechanics:

- The bd graph is the state machine. Each run is organized under a per-run epic; concurrent worktrees stay isolated by `--parent` filtering.
- The run epic carries label `ralph:<slug>`. Every child task carries both `--parent <epic>` and the same label. The two signals are independent for orphan detection.
- The plan's "Run Identity" section records the literal slug and epic ID. The agent reads them from the plan each iteration.
- One task per iteration. The agent reads `bd ready --parent <epic> --json`, takes the first result, executes its description, closes the task, then stops.
- When the ready queue is empty, the agent closes the epic and emits the sentinel.
- Every action is a bd task (branch creation, BEGIN tag, code, docs, END tag), all parented to the run epic.
- Each bead carries full instructions in its description: files, verification command, commit message.
- Run-wide conventions live in ralph-plan.md, not in every description.
- Environment is a precondition. Credentials, toolchain, and runtime dependencies are the operator's responsibility.

Accepted patterns (do not flag): collapsing tasks into bundles, partial completion, the `ralph:<slug>` label as run-identity (not workflow dispatch).

### What Counts as a Finding

A finding is a defect, gap, or risk the author should fix before execution. Conformance is the baseline, not a finding. Severity is HIGH or MEDIUM only. Omit anything less severe.

HIGH: zero or multiple open epics for `ralph:<slug>`; empty descriptions; graph cycles; no children under epic; children but no ready tasks; parent/label set mismatch; per-task workflow continues after `bd close` instead of stopping; per-task workflow omits epic closure before sentinel; missing Run Identity section; missing Inputs section with `plan documents:` line; plan contradicts a plan document; Approach prose declares ordering the dependency edges do not enforce.

MEDIUM: description omits verification command or commit message; isolated task in a multi-task graph; plan duplicates bead descriptions; bead touching README.md/CLAUDE.md/.llmdocs/ authors edits instead of running the docs skill (/docs, $docs).

### Evaluation Areas

Review for these defect patterns only. Report defects found, nothing else.

1. **Goal Clarity** - vague objective; fresh-context iteration cannot determine success from the plan alone
2. **Task Decomposition** - wrong granularity; tasks not independently completable; missing or redundant tasks; technique-named titles; insufficient description detail for cold-start worker
3. **Sequencing and Dependencies** - incorrect edges; `bd ready` order produces wrong results; implicit dependencies missing explicit edges; cycles; isolated nodes
4. **Plan Completeness** - missing conventions/tools/commands; inaccurate build/test/lint commands; unclear per-task workflow; missing Run Identity; missing epic scoping in workflow; missing epic closure; missing STOP instruction; missing `ralph/` branch and BEGIN/END tags; inline edits instead of docs skill delegation
5. **Risk and Gaps** - autonomous execution failures; tasks requiring human judgment; tasks that leave repo broken
6. **Feasibility** - tasks a single iteration cannot realistically complete; tasks exceeding fresh-context autonomy

### Output Format

```text
# Ralph Loop Review

## Goal Clarity
## Task Decomposition
## Sequencing and Dependencies
## Plan Completeness
## Risk and Gaps
## Feasibility
## Summary
```

Finding format: `- **[high]** Title. Description.` or `- **[medium]** Title. Description.`

Every section heading present. Defects only under each. 'No findings.' when a section has no defects.

Summary: overall assessment and top 3 recommendations.

Cite task IDs and section names. Produce the review, nothing else.
