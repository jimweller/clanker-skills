---
name: llmdocs
description: Update project documentation (CLAUDE.md + .llmdocs/). Use after significant work to keep docs in sync.
argument-hint: "[optional guidance]"
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 📐

# Update Project Documentation

Two responsibilities:

1. **CLAUDE.md** — concise project overview (always loaded)
2. **.llmdocs/** — detailed per-concept docs (loaded on demand). All files here are persistent design docs.

---

## 1. CLAUDE.md — The Map

### Scope

Find all CLAUDE.md and .llmdocs/ directories in the project and update each.
Pay attention to subfolder layers, scope and bounded contexts. Do not leak
concepts between documents at different layers. Each CLAUDE.md and .llmdocs/
covers its own directory level and below, never parent concerns.

If the user provided specific guidance or focus areas, apply that context
when deciding which docs to update and what to emphasize.

### Gather Context

For each CLAUDE.md/.llmdocs/ pair found, scoped to its directory:

1. Read current `CLAUDE.md` (if exists)
2. Compute what changed since docs were last touched. Include committed, staged, unstaged, and untracked work:

```bash
TARGET_DIR=<directory containing CLAUDE.md and .llmdocs/>
BASELINE=$(git log -1 --format=%H -- "$TARGET_DIR/CLAUDE.md" "$TARGET_DIR/.llmdocs/")
[ -z "$BASELINE" ] && BASELINE=$(git rev-list --max-parents=0 HEAD)

git log --oneline ${BASELINE}..HEAD -- "$TARGET_DIR"
git diff ${BASELINE} -- "$TARGET_DIR" --stat
git diff ${BASELINE} -- "$TARGET_DIR"
git ls-files --others --exclude-standard -- "$TARGET_DIR"
```

The diff has no `..HEAD` so it spans the baseline through the working tree, including staged and unstaged edits. `ls-files --others` surfaces new untracked files. Files matching `.gitignore` are excluded.

3. Explore codebase at that directory level and below
4. Review conversation history for relevant decisions, changes, or lessons learned
5. Use the diff and conversation context to identify what changed. llmdocs are current state specification, not a change log, not a decision log, not a historical record. Never record historical information or choices made, only the specification as it stands at the time of writing the llmdocs.

### Write/Update CLAUDE.md

Target: **under 500 lines**. Every line must earn its place.

```markdown
# <Name>

<1-2 line purpose of this directory/component>

## Stack

<bullet list: language, frameworks, key deps relevant to this level>

## Architecture

<key dirs and what they contain at this level>

## Commands

<build, test, lint, deploy — commands only>

## Conventions

<style, naming, patterns — only what prevents mistakes>

## Key Concepts

<domain terms, business logic Claude must know at this level>

## Docs

Detailed docs in `.llmdocs/`:

- @.llmdocs/architecture.md — <1-line description>
- @.llmdocs/data-model.md — <1-line description>
```

### CLAUDE.md Rules

- NO verbose explanations — Claude infers
- NO duplicating .llmdocs/ content — just reference with short description
- The `## Docs` section MUST list all .llmdocs/ files with a 1-line description each
- Preserve existing custom instructions (git workflow, env vars, etc.)
- Ask before removing any existing content
- Use `@.llmdocs/filename.md` import if a doc should always be loaded

---

## 2. .llmdocs/ — The Territory

### Process

1. **Assess**: use the diff from Gather Context to identify which docs are affected
2. **Identify**: determine which existing docs are affected, or if a new doc is needed
3. **Propose**: tell the user which docs you plan to update/create and what changes
4. **Validate**: get user approval before writing
5. **Update CLAUDE.md**: ensure the `## Docs` section lists any new doc files

If nothing changed that warrants doc updates, say so and move on.

### Location

Use the path specified in existing CLAUDE.md, or default `.llmdocs/` at the target directory level. CLAUDE.md and .llmdocs/ can exist at any directory level in the project.

### Structure

Flat, 1 file per concept. The first 6 files are **required** and must always exist. Additional concept files are created as needed.

```text
.llmdocs/
  architecture.md    # Components, interactions, data flow (required)
  api.md             # Endpoints, request/response, authentication, authorization (required)
  data-model.md      # Schema, models, relationships (required)
  deployment.md      # Deploy process, environments (required)
  ops.md             # Maintenance, operations, runbooks (required)
  security.md        # Trust boundaries, secrets handling, authn/authz, threat model (required)
  <concept>.md       # Domain-specific as needed
```

### Doc File Format

```markdown
# <Concept>

<1-line purpose>

## <Section>

<content: headers, tables, code blocks — no prose paragraphs>
```

### .llmdocs/ Rules

- Max 500 lines per file — split if larger
- Include file paths with line refs where useful (`src/auth/login.ts:42`)
- Update existing docs incrementally, don't rewrite from scratch
- If a doc is accurate and unaffected by recent changes, don't touch it
- Accuracy over coverage: only document what's verifiable from code

---

## 3. Summary Output

After running, output:

- Files created/modified
- CLAUDE.md changes (sections added/updated/removed)
- Docs updated/created (or "no doc changes needed")
