---
name: ralph-builder
description: Author a beads-backed Ralph Wiggum loop for in-session or external autonomous execution.
context: fork
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🔁

# Ralph Builder

Author the artifacts a ralph loop needs to run autonomously against the current repo. Tasks live in a beads (`bd`) graph database. The plan and two prompt wrappers live in `.llmtmp/`.

## Arguments

The user provides a goal description. It may reference a file containing a PRD, plan, or task list. Extract the goal from the invocation message.

## Output Artifacts

| Path                                | Purpose                                                    |
| ----------------------------------- | ---------------------------------------------------------- |
| `.beads/`                           | Beads database (single source of task state)               |
| `.llmtmp/ralph-plan.md`             | Mode-neutral execution plan                                |
| `.llmtmp/ralph-prompt-insession.md` | Slash-command wrapper for the in-session ralph-loop plugin |
| `.llmtmp/ralph-prompt-external.md`  | Body fed to `claude --print` by `scripts/ralph.sh`         |

Each prompt wrapper carries a mode-specific body: in-session loops continuously, external stops after each task.

## Procedure

### Step 1: Gather Context

Read the repo to ground the plan:

1. `README.md` (project root)
2. All `.md` files in `.llmdocs/`
3. Any file referenced in the user's goal arguments

Create `.llmtmp/` if it does not exist.

### Step 2: Initialize beads and mint the run epic

The bead graph is shared across worktrees of the same repo. Each ralph run is organized under a per-run epic so concurrent runs in different worktrees stay isolated by `--parent` filtering.

```bash
if ! bd list >/dev/null 2>&1; then
  bd init --skip-agents
fi

slug=$(git branch --show-current | tr '/' '-')
epic=$(bd q "Ralph: ${slug}" -t epic -p 1 -l "ralph:${slug}")
```

`--skip-agents` suppresses bd's default `AGENTS.md` generation, `CLAUDE.md` modification, and `.claude/settings.json` injection. The project's existing agent guidance and the `beads` skill provide bd workflow context; bd's per-project agent files are redundant and conflict with project conventions.

The epic carries the label `ralph:${slug}` as run-identity. Children created in Step 3 carry both `--parent "${epic}"` and the same label, providing two independent signals so the reviewer can detect orphans.

### Step 3: Translate Goal to bd Graph

Every action in a ralph run is a bead. Each bead has a title (imperative one-liner) and a description (the worker's full instructions for that task). Lifecycle scaffolding (branch creation, BEGIN tag, END tag) is encoded as ordinary beads, all parented to the run epic.

Create child beads with `bd create -t task --parent "${epic}" -l "ralph:${slug}" -q --json | jq -r .id`. Capture each ID for downstream `bd link` calls. Set descriptions with `bd update <id> -d "<text>"` (or `--body-file -` heredoc for multi-line). Wire dependencies with `bd link <a> <b>` (b blocks a). Every run starts with a branch task and a BEGIN tag task; every run ends with an END tag task that depends transitively on every other task.

#### Example

The block below shows a hypothetical run adding three greeting functions to `lib/greeting.go` and updating the README. The literal values (`SLUG`, file paths, function names, commit prefixes) are illustrative; substitute the real run's facts. Bead descriptions carry task-specific facts only. Each coding task description uses the RED/GREEN/VERIFY structure defined below. Universal rules (conventional commits, persona constraints) already live in `CLAUDE.md`. Run-wide conventions (build, test, lint commands) live in `ralph-plan.md`. Descriptions do not restate either.

```bash
DATE=$(date +%Y%m%d)
SLUG=greeting   # derive from the goal; lowercase alphanumeric plus hyphen, max ~20 chars
HASH=$(openssl rand -hex 2 | head -c 3)
RUN="${DATE}-${SLUG}-${HASH}"
BRANCH="ralph/${RUN}"

# slug and epic are in scope from Step 2.

bdc() {
  bd create "$1" -t task -p 2 --parent "${epic}" -l "ralph:${slug}" -q --json | jq -r .id
}

T_BRANCH=$(bdc "Switch to branch ${BRANCH}")
bd update "$T_BRANCH" -d "Switch to branch ${BRANCH}, creating it if missing. Verify: git rev-parse --abbrev-ref HEAD prints ${BRANCH}."

T_BEGIN=$(bdc "Tag RALPH-${RUN}-BEGIN")
bd link "$T_BEGIN" "$T_BRANCH"
bd update "$T_BEGIN" -d "Run: git tag RALPH-${RUN}-BEGIN. Verify: git tag -l RALPH-${RUN}-BEGIN is non-empty."

T1=$(bdc "Add hello() to lib/greeting.go")
bd link "$T1" "$T_BEGIN"
bd update "$T1" --body-file - <<'DESC'
TDD workflow: write failing tests first, then implement minimum code to pass.

RED phase (write first):
Create lib/greeting_test.go. Test cases: hello() returns "world".

GREEN phase (then implement):
Create hello() in lib/greeting.go returning "world".

VERIFY: go test ./lib/... passes. Commit: feat(greeting): add hello
DESC

T2=$(bdc "Add goodbye() to lib/greeting.go")
bd link "$T2" "$T_BEGIN"
bd update "$T2" --body-file - <<'DESC'
TDD workflow: write failing tests first, then implement minimum code to pass.

RED phase (write first):
Add to lib/greeting_test.go. Test cases: goodbye() returns "bye".

GREEN phase (then implement):
Create goodbye() in lib/greeting.go returning "bye".

VERIFY: go test ./lib/... passes. Commit: feat(greeting): add goodbye
DESC

T3=$(bdc "Add greet(name) to lib/greeting.go")
bd link "$T3" "$T1"
bd link "$T3" "$T2"
bd update "$T3" --body-file - <<'DESC'
TDD workflow: write failing tests first, then implement minimum code to pass.

RED phase (write first):
Add to lib/greeting_test.go. Test cases: greet("Jim") returns
"world Jim bye".

GREEN phase (then implement):
Create greet(name) in lib/greeting.go composing hello() and goodbye().

VERIFY: go test ./lib/... passes. Commit: feat(greeting): add greet
DESC

T4=$(bdc "Document greetings API")
bd link "$T4" "$T3"
bd update "$T4" -d "Run the docs skill (/docs, \$docs) to document hello(), goodbye(), and greet() now exposed by lib/greeting.go. Commit: docs: document greetings API"

T_END=$(bdc "Tag RALPH-${RUN}-END")
bd link "$T_END" "$T4"
bd update "$T_END" -d "Run: git tag RALPH-${RUN}-END. Verify: git tag -l RALPH-${RUN}-END is non-empty."
```

The 3-char hash suffix prevents branch and tag collisions when multiple ralph runs share a date and slug.

After authoring, assert no cycles, every child has a description, at least one task is ready, and the parent set equals the label set (excluding the epic):

```bash
bd dep cycles
bd list --parent "${epic}" --json | jq -e 'all(.[]; (.description // "") | length > 0)'
bd ready --parent "${epic}" --json | jq 'length'

parent_ids=$(bd list --parent "${epic}" --json | jq -r '.[].id' | sort)
label_ids=$(bd list --label "ralph:${slug}" --json | jq -r '.[] | select(.issue_type != "epic") | .id' | sort)
[[ "${parent_ids}" == "${label_ids}" ]] || { echo "parent/label set mismatch: orphans or misclassified beads"; exit 1; }
```

Title rules:

- Imperative voice, one line
- Names the deliverable, not the procedure
- No meta-tasks like "read the codebase" or "understand the architecture"

Description rules:

- Task-specific facts only: which file, what behavior, the commit message for this task
- Include a verification command only when it differs from the run's standard test command (typically tag and branch tasks)
- Do not restate code style or persona rules; those live in `CLAUDE.md`. Do not restate run-wide build, test, or lint commands; those live in `ralph-plan.md`
- Every coding task description uses RED/GREEN/VERIFY structure: RED phase names the test file and enumerates specific test cases with expected behavior. GREEN phase describes implementation only. VERIFY names the test command and conventional commit message. Lifecycle, config, SQL, shell, Helm, and docs beads are exempt.
- Never create standalone "write tests", "add unit tests", or "integration checkpoint" beads. Tests live inside each coding task via RED phase. No test-only beads, no deferred test-suite beads.

Skill delegations (mandatory):

| Work                                                          | Skill                   |
| ------------------------------------------------------------- | ----------------------- |
| Updating `README.md`, `CLAUDE.md`, or any file in `.llmdocs/` | docs (/docs, $docs)     |

Beads in these categories must invoke the skill in the description, not author edits inline. Example: `Run the docs skill to document the new auth middleware` rather than `Edit .llmdocs/architecture.md to add an Authentication subsection`. The skill carries its own guardrails and parallelism; reproducing its job inline loses both.

### Step 4: Write `.llmtmp/ralph-plan.md`

Each iteration reads this file cold with no memory of prior runs. Every command, pattern, and convention belongs here. Dense, repo-specific detail is correct.

The "Run Identity" section records the literal `${slug}` and `${epic}` values produced in Step 2 so the agent can read them directly without re-deriving each iteration.

The "Inputs" section's `plan documents:` line records the source documents the planner was passed via the user's arguments. The reviewer parses that line and reads each path as authoritative intent. This is a passthrough: list exactly the files from the user's arguments, no more, no fewer, no inferred additions. If a referenced path does not exist, fail the build with a clear error rather than dropping it.

Required sections:

```markdown
# Ralph Plan

## Goal

<one paragraph>

## Approach

<strategy specific to this goal; include all relevant repo-specific detail directly>

## Inputs

plan documents: <comma-separated paths from the user's arguments, or empty if none>

## Run Identity

- Branch slug: `<slug from Step 2>`
- Epic ID: `<epic ID from Step 2>`
- Epic label: `ralph:<slug>`
- Driver: `scripts/ralph.sh .llmtmp/ralph-prompt-external.md`

## Conventions

<repo-specific patterns, tools, test commands, build commands, commit style>

## Git Workflow

All git operations execute as bd tasks per the per-task workflow. Branch creation, BEGIN tag, code commits, docs commits, and END tag are first-class beads in the graph, parented to the run epic. Never commit on `main`.

## Per-Task Workflow

Exactly ONE task per iteration. After step 5, follow the driver instruction. The driver controls whether the agent loops in-session or stops for a fresh context.

Each iteration:

1. Read the epic ID and slug from the "Run Identity" section above.
2. Run `bd ready --parent <epic-id> --json`. If the result is `[]`, run `bd close <epic-id> -m "ralph run complete"`, output `<promise>ALLDONE</promise>`, and stop.
3. Pick the first task. Run `bd show <id>` to read the title and description.
4. Execute the description exactly. The description names the files, commands, verification step, and commit message for this task.
5. Run `bd close <id>`. Follow the driver instruction below.

The sentinel `<promise>ALLDONE</promise>` is emitted only on the iteration where step 2 finds the ready queue empty (all children closed and the epic just closed).

## Driver Instruction

<!-- Replaced at plan-write time by the prompt wrapper. -->
<!-- In-session: "Return to step 1 to pick the next task." -->
<!-- External: "STOP. The driver spawns a fresh context for the next task." -->
```

Plan rules:

- Ground instructions in actual repo structure and tooling
- Include build, test, and lint commands when known
- Do not duplicate the project's CLAUDE.md
- Define what "done" means for a task (tests pass, linter clean)
- State current facts only
- `plan documents:` lists exactly the files referenced in the user's arguments. Do not add `README.md`, `CLAUDE.md`, or `.llmdocs/*` (the reviewer reads those independently as baseline). Do not infer related files from `.llmtmp/` or elsewhere. If a referenced path does not exist, fail the build with a clear error rather than dropping it.

### Step 5: Write Prompt Wrappers

Each mode gets its own body because the driver instruction differs.

**In-session body** (loops without stopping):

```text
Read .llmtmp/ralph-plan.md and follow it. After closing each task, return to step 1 of the Per-Task Workflow to pick the next ready task. Do not stop between tasks.
```

**External body** (one task per invocation):

```text
Read .llmtmp/ralph-plan.md and follow it. After closing each task, STOP. The driver spawns a fresh context for the next task.
```

`.llmtmp/ralph-prompt-insession.md` is one line using the in-session body:

```text
/ralph-loop:ralph-loop "<in-session body>" --max-iterations 100 --completion-promise ALLDONE
```

`.llmtmp/ralph-prompt-external.md` is the external body alone, no wrapper.

## Validation

Before finishing, assert:

- `bd list >/dev/null 2>&1` exits zero
- `bd dep cycles` exits zero
- A single open epic exists for this run: `bd list -t epic -l "ralph:${slug}" --json | jq -e 'length == 1'`
- `bd ready --parent "${epic}" --json | jq 'length'` is greater than zero
- Every child of the epic has a non-empty description: `bd list --parent "${epic}" --json | jq -e 'all(.[]; (.description // "") | length > 0)'`
- Parent set equals label set (excluding the epic itself):

  ```bash
  diff <(bd list --parent "${epic}" --json | jq -r '.[].id' | sort) \
       <(bd list --label "ralph:${slug}" --json | jq -r '.[] | select(.issue_type != "epic") | .id' | sort)
  ```

- `.llmtmp/ralph-plan.md`, `.llmtmp/ralph-prompt-insession.md`, `.llmtmp/ralph-prompt-external.md` all exist
- The plan's "Run Identity" section records the literal slug and epic ID
- The in-session prompt contains "return to step 1" and "Do not stop between tasks"
- The external prompt contains "STOP" and "fresh context"

If any assertion fails, fix and re-validate.
