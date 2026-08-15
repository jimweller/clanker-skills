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

Not every run touches every class. Step 3 picks the ones that hold evidence for the questions at
hand and records why the rest were left out.

| Class | Tool | Notes |
| ----- | ---- | ----- |
| Jira | `mcg-atlassian:jira` skill, `j` CLI | Load `mcg-jira-prefs` after the main skill. Host `https://mcghealth.atlassian.net` |
| Confluence | `mcg-atlassian:confluence` skill, `c` CLI | Load `mcg-confluence-prefs` after the main skill. Same host. Read page history for version-level claims |
| Azure DevOps | `ado` skill, `az` CLI, ADO REST with `$AZURE_DEVOPS_EXT_PAT` | `dev.azure.com/mcgsead`. Commits, PRs, reviewers, branch policy, pipelines, releases |
| GitHub | `gh` CLI | Same evidence classes as ADO for repos that live there |
| Local git | `git log`, `git rev-list`, `git blame`, `git show` | Bare `git log` caps at 50 commits in this environment. Use `rev-list` for counts |
| Slack | slack MCP tools | Channel history, search, permalinks. Coverage is bounded by the querying account |
| Mail, calendar, Teams | ms365 MCP tools | Microsoft Graph. Mail `$search` needs a double-quoted KQL value |
| Azure runtime | `az` CLI, `az graph query` | Read-only. Resource state, app settings, network posture, identities |
| AWS runtime | `aws` CLI, `kubectl` for EKS | Read-only |
| Cloud inventory | steampipe | Cross-account queries when the CLI path is slow |
| Cost | Azure Cost Management API, Azure Retail Prices API, AWS Cost Explorer | List price is an upper bound. Label it as such |
| Code quality | SonarQube | Quality gate history, scan failures |
| Logs | Sumo Logic | Deploy events, error onset, traffic shape |
| APM and tracing | Datadog | Traces, monitors, incident and alert history |
| Terminology | `mcg-lookup` skill | MCG Dictionary. Record absence when a term is missing |
| Code review | repomix plus the reviewer agents | Automated output is unverified until hand-checked |
| Agent history | claude-mem search, `transcript-search` skill, total-recall | These record what was said, not what is true. Never cite one as proof of a fact |
| External docs and vendors | context7, researcher MCP, `defuddle`, WebSearch | Prefer context7 and researcher over the builtin web tools |

## Procedure

1. **Frame the questions.** Restate each question. State the time window the set covers. State the
   scope boundary, meaning whose story this is and whose it is not.
2. **Establish anchors.** Confirm the identifiers each source needs before any sweep: Jira project
   keys and epic keys, Confluence space keys and page ids, repo names and ids, Slack channel ids,
   the mail corpus, cloud subscription and account ids. Record each anchor with the query that
   confirmed it.
3. **Select the source classes.** Name which classes from the table hold evidence for these
   questions and this subject. Most runs use a handful. State which classes are in and which are
   out, with the reason for each exclusion. The exclusions carry into Method.
4. **Sweep in parallel.** Dispatch one subagent per selected class. Give each agent the questions,
   the anchors, the time window, the citation format, and the evidence rules below. Each returns
   dated, cited findings, not raw query dumps. An agent that finds nothing reports the queries it
   ran and the empty result, which is evidence of absence bounded by that query.
5. **Assemble the milestones.** Merge the returned findings into one chronology. Split it into
   named phases. Tag every entry that bears on a question with `[Qn]`.
6. **Resolve conflicts.** Where a source claim and an artifact disagree, keep both and say which is
   which. Where two artifacts disagree, keep both and name the discrepancy.
7. **Write the report.** Follow the output structure below.
8. **Record method and caveats.** Every access boundary, denial, result cap, and unverified claim.

## Output structure

Sections in this order.

| Section | Contents |
| ------- | -------- |
| Title and preamble | Working-document line, last-updated date, and a "Sources so far" sentence naming every system queried |
| Executive summary | The answer, in prose, for a reader who reads nothing else |
| Summary | Narrative for a leadership audience. Every figure traces to a section below |
| Purpose | Q1 through Qn, each with what is established and what stays open |
| Acronyms | Expansion plus provenance marker: `(dict)`, `(meta)`, `(record)`, or unverified |
| Cast | People, roles, and the artifact that establishes each role |
| Milestones | Phases in date order. Each entry: bold date and headline, link line, evidence, `[Qn]` tag |
| Per-system records | Repo facts, issue-tracker record, runtime state, documentation record, consumer record, cost |
| Findings | Numbered, one claim each |
| Open questions | Numbered, each with what would settle it |
| Method and caveats | Query provenance, access boundaries, denials, caps, and what stays unverified |

Milestone entry shape:

```text
**YYYY-MM-DD. Headline** `[Qn]`
[Identifier](url) | [Identifier](url)
Evidence. Quote the source verbatim where the wording carries the claim.
```

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
