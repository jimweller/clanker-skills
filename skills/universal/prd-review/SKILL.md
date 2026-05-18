---
name: prd-review
description: Review a PRD for structural defects via a subagent.
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 📑

# PRD Review

Dispatch a subagent to review a PRD for structural defects.

## Arguments

The user provides a path to the PRD file. Extract it from the invocation message.

## Dispatch

Read the PRD file to confirm it loads, then dispatch a subagent with the review prompt below, substituting `<PRD_PATH>` with the actual file path.

Relay the response verbatim.

## Review Prompt

You are a PRD reviewer. Read the PRD and evaluate it for defects.

Source: Read `<PRD_PATH>`.

### What a Good PRD Looks Like

The reader is a junior developer or AI agent with no prior context. Required sections in order:

1. Introduction/Overview
2. Goals (specific, measurable)
3. User Stories (US-NNN IDs, third-person description, verifiable acceptance criteria)
4. Non-Goals
5. Design Considerations (or n/a)
6. Technical Considerations (or n/a)
7. Success Metrics (quantified)
8. Open Questions (at most 3, blockers only)

User stories: third-person voice, acceptance criteria are verifiable assertions ("button shows confirmation dialog" not "works correctly"), sized to one focused session, UI stories include browser verification.

### What Counts as a Finding

A finding is a defect, gap, or risk the author should fix before implementation. Conformance is the baseline, not a finding. Severity is HIGH or MEDIUM only. Omit anything less severe.

HIGH: missing required section; first-person voice in user stories; implementer pronouns (CLANKER, we, our, AI, the developer); vague acceptance criteria; unmeasurable goals or success metrics; Open Questions > 3; Non-Goals missing, empty, or vague; PRD contradicts its own goals.

MEDIUM: oversized user story; UI story missing browser verification; Technical Considerations n/a when constraints exist; Design Considerations n/a when a UI surface exists; Open Questions empty while ambiguity exists; acceptance criteria phrased as developer instructions; missing stable IDs; technique-named titles; build-hygiene items as acceptance criteria; cross-story dependencies in acceptance criteria.

### Evaluation Areas

Review for these defect patterns only. Report defects found, nothing else.

1. **Goal Clarity** - vague problem statements; unmeasurable goals; implementation tasks as goals; redundant goals; ambiguous scope
2. **User Stories Quality** - missing IDs; wrong voice; implementer pronouns; vague criteria; build-hygiene criteria; cross-story dependencies in criteria; oversized stories; missing browser verification; technique-named titles
3. **Scope Discipline** - vague Non-Goals; goals inconsistent with Introduction; untied success metrics; scope creep across stories
4. **Completeness** - missing sections; generic Technical/Design Considerations; unquantified success metrics
5. **Risk and Gaps** - nice-to-know Open Questions; implicit assumptions; unflagged dependencies; unaddressed failure modes
6. **Implementability** - absent clarifications; inter-dependent stories; non-machine-verifiable criteria; over-specified implementation choices

### Output Format

```text
# PRD Review
**PRD**: <PRD_PATH>

## Goal Clarity
## User Stories Quality
## Scope Discipline
## Completeness
## Risk and Gaps
## Implementability
## Summary
```

Finding format: `- **[high]** Title. Description.` or `- **[medium]** Title. Description.`

Every section heading present. Defects only under each. 'No findings.' when a section has no defects.

Summary: overall assessment and top 3 recommendations.

Cite user story IDs (US-NNN) and section names. Produce the review, nothing else.
