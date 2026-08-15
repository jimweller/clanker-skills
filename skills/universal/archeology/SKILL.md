---
name: archeology
description: Build an evidence-based historical report to answer questions. Use when the user asks for archeology, detective work, historical timeline, or historical record.
argument-hint: "<questions to answer>"
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🏺

# Archeology

Reconstruct what happened from surviving evidence, then answer the questions from that record.

Deliverable is `.llmtmp/timeline.md`. Working notes stay under `.llmtmp/`. Write nothing else
without being asked.

## Input

The argument is one or more questions, split on `?`. Number them Q1 through Qn and keep that
numbering for the whole run. If no argument is given, ask for at least one question and stop until
it arrives. Do no research against an unstated question.

## Sources

These are labels, not instructions. Reach each one with whatever tool the environment provides.

Jira, Confluence, and Slack are the seed. The rest get reached when the evidence points at them.
Never ask which sources to use.

- Issue trackers and portfolio boards
- Wikis, design docs, and decision records
- Chat
- Mail, calendar, and meeting records
- Source repos: commits, pull requests, reviewers, branch policy, pipelines, releases
- The code itself
- Cloud runtime state
- Cost and billing
- Logs, traces, monitors, and incident history
- Code quality and scan history
- Dictionaries and terminology registries
- Agent memory and session transcripts
- External docs, vendor material, and the web

## Procedure

1. **Frame the questions.** Restate each question. State the time window the set covers. State the
   scope boundary, meaning whose story this is and whose it is not.
2. **Seed sweep.** Dispatch three subagents in parallel, one each against Jira, Confluence, and
   Slack. Give each the questions, the subject, the time window, the citation format, and the
   evidence rules below. These three carry the identifiers everything else needs. Each returns
   dated, cited findings plus the anchors it confirmed: project keys, epic keys, space keys, page
   ids, channel ids, repo names, environment names, and every other system the record mentions.
3. **Follow the evidence.** Each round names new ground. A ticket names a repo, a page names a
   dashboard, a message names an incident or a mailbox. Fan out one subagent per newly named
   source, in parallel, and keep going until a round turns up nothing new. Judge what is worth
   chasing and chase it. Do not ask which sources to use, and do not stop at the seed. An agent
   that finds nothing reports the queries it ran and the empty result, which is evidence of
   absence bounded by that query.
4. **Assemble the milestones.** Merge the returned findings into one chronology. Split it into
   named phases. Tag every entry that bears on a question with `[Qn]`.
5. **Resolve conflicts.** Where a source claim and an artifact disagree, keep both and say which is
   which. Where two artifacts disagree, keep both and name the discrepancy.
6. **Write the report.** Follow the sample below. Same headings, same order, every run.
7. **Record the method.** Every access boundary, denial, result cap, and unverified claim. Name the
   sources reached and the ones the record pointed at that this run never got to.

## Sample report

Every run produces this shape. Same headings, same order, same entry form.

````markdown
# <Subject>: Evidence Timeline

This is a working document. Each milestone carries a slug, a link, and its supporting evidence.
Amend as new evidence arrives. Last updated YYYY-MM-DD.

Sources so far: <system>, <system>, and <system>.

## Executive summary

<The answer to every question, in prose, for a reader who reads nothing else. Sequence and
measured state. Three to six paragraphs.>

## Summary

<Narrative for a leadership audience. Every figure traces to a section below.>

<Closing paragraph naming what this summary does not assert and which figures are bounded.>

## Purpose

<N> open questions drive this timeline. Entries are tagged `[Q1]` through `[Qn]` where they bear
on one.

**Q1. <Question>?** <What the record establishes.> <What stays open.>

**Q2. <Question>?** <What the record establishes.> <What stays open.>

## Acronyms

Expansions marked **(dict)** come from a terminology registry. Expansions marked **(meta)** come
from project or space metadata. Expansions marked **(record)** are established by artifacts in
this timeline. Unverified entries say so.

| Term | Expansion | Meaning here |
| ---- | --------- | ------------ |
| <ABC> | <Expansion> (dict) | <What it refers to in this record> |
| <XYZ> | <Expansion> (record) | <What it refers to in this record> |

## Cast

| Person | Role | Established by |
| ------ | ---- | -------------- |
| <Name> | <Role> | <Artifact and link> |

## Milestones

### Phase 0: <Name>, <start> to <end>

**YYYY-MM-DD. <Headline>** `[Q1]`
[<ABC-123>](url) | [<Page title>](url)
<Evidence. Quote the source verbatim where the wording carries the claim.>

**YYYY-MM-DD HH:MM TZ. <Headline>**
[<Chat>](permalink)
<Name>: "<verbatim quote>" <What the quote establishes.>

### Phase 1: <Name>, <start> to <end>, <count> <units>

<Entries in date order.>

## <System> record

<One section per system: repo facts, issue-tracker record, runtime state, documentation record,
consumer record, cost. Sub-sections as the evidence requires.>

| <Metric> | <Value> | Source |
| -------- | ------- | ------ |
| <Metric> | <Value> | <Query or link> |

## Findings

1. <One claim, carrying the figure that supports it.>
2. <One claim, carrying the figure that supports it.>

## Open questions

1. <Question.> <What would settle it.>
2. <Question.> <What would settle it.>

## Method

<Every claim above is one of three kinds. Name them: a quoted source is a claim by its author on
that date, a system record is an artifact, a live query result is state observed on that date.
Where a claim and an artifact disagree, both appear.>

- <Query provenance: tool, host, credential, and date for each system.>
- <Result caps, and how counts were taken above the expected row count.>
- <Denials, recorded rather than worked around.>
- <Sources the record named that this run never reached.>
- <What stays unverified.>
````

## Evidence rules

- Cite the system, the identifier, and the URL on every claim.
- A source claim differs from an artifact. An email saying an issue closed is a claim. The issue
  transition record is the artifact. Say which one a statement rests on.
- Record contradictions. Never resolve one silently.
- Label every unverified statement as unverified, in place.
- Record a denied query as a denial. Do not work around it.
- Never print a secret value. Compare and classify without echoing.
- All queries are read-only. No write, delete, or restart operation.
- Agent memory and transcripts are not independent evidence.
- State the result cap on every count, and take counts with a limit above the expected row count.
- Bound every count by the credential that produced it.

## Framing rules

- Describe, do not evaluate. "What was requested" is a question. "Whether the request was any good"
  is a verdict.
- Attribute every characterization to its author, verbatim, or delete it.
- Do not link sources with convergence language that walks the reader toward a judgment.
- Scope every absolute to what was searched, and name the search.
- Label list prices, projections, and estimates as what they are.
- Ghostwriting rules apply. The reader is a human colleague.

## Formatting

- ISO dates. Name the timezone when the source gives one.
- Wrap prose at 95 columns.
- Compact tables: one space inside the pipes, separator dashes sized to the header text.
- Do not run `md-lint` or prettier on the deliverable. Both break the house format.
