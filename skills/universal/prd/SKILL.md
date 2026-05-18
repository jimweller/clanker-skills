---
name: prd
description: Generate a Product Requirements Document (PRD) for a new feature. Use when planning a feature, starting a new project, or when asked to create a PRD.
argument-hint: "<feature description>"
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 📋

# PRD Generator

Generate a PRD.

## The Job

1. Receive a feature description from the user
2. Ground the spec by reading the repo
3. Ask clarifying questions (with lettered options); iterate in additional rounds as needed
4. Generate a structured PRD based on answers
5. Save to `.llmtmp/prd.md` (or `.llmtmp/prd-<slug>.md` if a slug is given)

### Note

Do NOT start implementing. Just create the PRD.

## Slug Derivation

If the user supplies a slug, use it. Otherwise derive from the feature title: lowercase, alphanumeric plus hyphen, capped at 20 chars.

## Step 1: Gather Context

Read the repo before asking questions. Uninformed questions waste the user's time and produce a vague spec. Sources, in order:

1. `README.md` (project root)
2. `CLAUDE.md` (project root) if it exists
3. All `.md` files in `.llmdocs/`
4. Any file the user named in the prompt
5. Code relevant to the feature: grep, Glob, or Serena symbol search for terms named in the feature description (e.g., for an auth feature, find the auth middleware, JWT validators, identity-mapping code)

Read enough to know what exists, what conventions are in use, what vocabulary the repo uses, and which files the feature would touch. Then the questions can be specific to the actual codebase, not hypotheticals.

## Step 2: Clarifying Questions

Ask only critical questions where the initial prompt is ambiguous. Focus on:

- Problem/Goal: What problem does this solve?
- Core Functionality: What are the key actions?
- Scope/Boundaries: What should it NOT do?
- Success Criteria: How do we know it's done?

### Follow-Up Rounds

Multiple rounds are expected, not exceptional. After the first set of answers, deeper code reading or the user's responses often surface new decision points. Ask another lettered round whenever a decision is unresolved, or in response to user push-back. The PRD reflects the final state of the dialogue, not the first answer.

The user may also ask CLANKER to revise a draft PRD; treat that as another follow-up round.

### Format Questions Like This

```text
1. What is the primary goal of this feature?
   A. Improve user onboarding experience
   B. Increase user retention
   C. Reduce support burden
   D. Other: [please specify]

2. Who is the target user?
   A. New users only
   B. Existing users only
   C. All users
   D. Admin users only

3. What is the scope?
   A. Minimal viable version
   B. Full-featured implementation
   C. Just the backend/API
   D. Just the UI
```

This lets users respond with "1A, 2C, 3B" for quick iteration. Indent the options.

## Step 3: PRD Structure

PRD reader is a junior developer or AI agent. Be explicit, no jargon, numbered requirements, concrete examples.

Generate the PRD with these sections:

### 1. Introduction/Overview

Brief description of the feature and the problem it solves.

### 2. Goals

Specific, measurable objectives (bullet list).

### 3. User Stories

Each story needs:

- Title: Short descriptive name
- Description: "A [user role] needs [feature] so that [benefit]" where [user role] is the actor (platform operator, end user, admin), never the implementer
- Acceptance Criteria: Verifiable functional assertions about the story's own behavior

Each story should be small enough to implement in one focused session.

Format:

```markdown
### US-001: [Title]

**Description:** A [user role] needs [feature] so that [benefit].

**Acceptance Criteria:**

- [ ] Specific verifiable functional criterion
- [ ] Another verifiable functional criterion
- [ ] **[UI stories only]** Observable outcome verified in a browser session
```

### Note

Acceptance criteria rules:

- Verifiable functional assertions about the story's own behavior. "Works correctly" is bad. "Button shows confirmation dialog before deleting" is good.
- [user role] is the actor who benefits (platform operator, end user, admin). Never the implementer, never CLANKER, never "we", never "the developer", never "AI".
- Build hygiene (lint passes, tests pass, typecheck passes) is a delivery baseline, not a feature criterion. Omit from acceptance criteria.
- Each criterion is self-contained. No cross-story references ("widened in this run via US-011"). Move sequencing to Technical Considerations.
- UI criteria state the observable outcome ("browser session shows the forced reauth screen"), not the verification tool.

### 4. Non-Goals (Out of Scope)

What this feature will NOT include. Critical for managing scope.

### 5. Design Considerations

UI/UX requirements, mockup links, existing components to reuse. Use "n/a" if not applicable.

### 6. Technical Considerations

Constraints, dependencies, integration points, performance requirements. Use "n/a" if not applicable.

### 7. Success Metrics

How will success be measured? Examples:

- "Reduce time to complete X by 50%"
- "Increase conversion rate by 10%"

### 8. Open Questions

Remaining questions. List at most 3. Open questions are blockers, not nice-to-knows.

## Output

- Format: Markdown (`.md`)
- Location: `.llmtmp/`
- Filename: `prd.md` or `prd-<slug>.md`

## Example

See `references/example-prd.md` for a worked example.

## Checklist

Before saving the PRD:

- [ ] Asked clarifying questions with lettered options
- [ ] Incorporated user's answers
- [ ] User stories are small with verifiable acceptance criteria
- [ ] Non-goals section defines clear boundaries
- [ ] Open Questions has at most 3 items
- [ ] Saved to `.llmtmp/prd.md` (or `.llmtmp/prd-<slug>.md`)

If any item fails, fix and re-validate before saving.
