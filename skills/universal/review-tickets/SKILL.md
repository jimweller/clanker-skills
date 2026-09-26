---
name: review-tickets
description: Turn review-deep's verified issues into Jira ticket files. Re-cuts each issue into one ticket per file from the reviewers' own text, judges and edits every finding against a clean checkout with isolated claude -p processes, merges tickets that share one fix, assembles Jira wiki tickets with code copied from git, and checks them. Ends with posting guidance for any Jira client and a bundle ticket for deferred low-priority work.
context: fork
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🧾

# Review Tickets

Turn a review-deep run into ticket files that a person or a model can act on without re-reading the review. Every sentence in a ticket is a reviewer's own sentence, kept, narrowed, or deleted by a judge that read the code. The only new text is the Summary.

The input is a review-deep run directory. It holds `run.json`, `findings.jsonl`, `issues.jsonl`, `verify/results.jsonl`, `verify/second.jsonl`, and `checkout/`, a clean checkout of the reviewed commit. Everything this skill writes goes under `<run>/tickets/`. The scripts are in `scripts/` next to this file and use the Python standard library, except `dupscreen.py`, which runs through `uv`.

## Arguments

The run directory printed by review-deep. Every command below uses it as `RUN`.

## Requirements

- `claude` on `PATH`, logged in to a provider. Each judge is a `claude -p` process that inherits this environment, so model aliases such as `opus` and `fable` resolve through the same provider settings as the invoking session.
- `git`, and the repository at `run.json` `repo` with the reviewed commit present.
- `uv` for the duplicate screen.

`run.json` sets the models as `[alias, effort]` pairs under `models`. Defaults are `judge` Opus at xhigh, `critical` Fable at high, and `sibling` Opus at xhigh. `concurrency` defaults to 50.

## Procedure

Run each model step as a background Bash call. The pool returns when every call has finished, and the completion notification is the signal to continue. Never poll a running step with `sleep`.

### Step 1: Plan

```bash
S=<this skill's directory>/scripts
python3 $S/plan.py RUN
```

An issue is planned when its review rating is at or above the floor, High by default, and the verifier confirmed it. Its ticket severity is the lower of the verifier's and the second check's ratings, even below the floor. `tickets/decisions.json` can list `skip_issues`, for issues already tracked elsewhere, and `include_issues`, for issues whose first verdict is unusable, such as a placeholder answer. The judge verifies included issues itself.

### Step 2: Re-cut into units

```bash
python3 $S/recut.py RUN
```

A unit is one issue's findings in one file. A themed issue that merged 77 findings across 24 files produced tickets whose cited locations did not support the claim. Per-file units fixed that, and Step 4 merges units back only when one change fixes them.

### Step 3: Judge and edit

```bash
python3 $S/judge.py RUN              # every unit, background
python3 $S/apply.py RUN
python3 $S/judge.py RUN --critical   # second model on units still Critical, background
python3 $S/apply.py RUN
```

The judge reads the code, tries to refute every claim, and returns each finding as keep, edit, or delete. A keep must name the code behind each of its claims. An edit changes only what the code contradicts. Every edit and delete cites code, and a script checks each quote against git at the reviewed commit before the answer is accepted. `apply.py` writes `tickets/edits.json`. A unit is excluded when the judge refutes it, when the second model disagrees on the verdict, or when a quote is not the code.

`judge.py --ids FILE` reruns a JSON list of unit IDs and keeps every other answer.

### Step 4: Merge siblings that share one fix

```bash
python3 $S/siblings.py RUN           # background
python3 $S/judge.py RUN --merged     # background
python3 $S/apply.py RUN --merged
```

Splitting by file also splits one defect seen from a caller and its callee. For every issue with two or more ready units, a judge groups the units whose defect one change at a single location resolves. The same pattern in two independent places stays two tickets. A merged ticket is then judged again as a whole, which checks its new Summary and can edit its findings. A merged ticket keeps every finding as its own bullet, so a caller and a callee both appear.

### Step 5: Assemble and check

```bash
python3 $S/assemble.py RUN
python3 $S/checks.py RUN
```

`checks.py` must print `problems 0` before anything is posted. It compares every code block to git byte for byte, checks every location, and flags markup Jira will not render.

### Step 6: Screen for duplicates

Export the target project's issues with any Jira client as JSON, one object per issue with `key`, `summary`, and `description`, at the top level or under `fields`. Then:

```bash
uv run --with scikit-learn --with numpy python $S/dupscreen.py RUN existing.json
```

The screen prints pairs by shared vocabulary for a person to read. Most pairs share a topic, not a defect.

### Step 7: Record decisions

Write the operator's decisions to `tickets/decisions.json` and rerun Step 5.

| Key | Effect |
| --- | ------ |
| `drop` | `{ID: reason}`. The ticket is removed, for example as a duplicate of an existing issue. |
| `defer_priorities` | A list such as `["Low"]`. Those tickets stay assembled and checked but leave `tickets/postable.json`. |
| `skip_issues`, `include_issues` | Read by Step 1. |

### Step 8: Post

Post only after the operator's explicit go. Use whichever Jira client is available. The rules below held on 385 tickets.

- Post one ticket at a time, in priority order. Map Critical to Highest, High to High, Medium to Medium, and Low to Low. Send the `summary`, the `type`, the mapped priority, the `labels`, and the `description` as Jira wiki markup.
- Append the ticket ID and the new key to a log the moment the create call returns, before anything else.
- Read every ticket back with its description as ADF and run `python3 $S/readback.py TICKET_JSON FIELDS_JSON`. Stop on the first mismatch. One run stopped when two code spans joined by an en dash rendered as a single span. The checker caught it before the next 300 tickets repeated it.
- Stop on the first error. Retry only a 429, after its Retry-After wait. A timeout or a 5xx may have created the issue, so reconcile before retrying.
- Before any resume, reconcile the log against a search for the `review-deep` label. Jira search leaves out archived issues, so an issue archived on purpose never counts as a stray.
- Post the first ticket alone, read it back field by field, and continue only after it matches.

### Step 9: Bundle deferred tickets

```bash
python3 $S/bundle.py RUN
```

`tickets/bundle/ticket.json` describes one ticket for all deferred work, with every category label, and `tickets/bundle/<name>-deferred-defects.md` holds each deferred ticket's summary, categories, and findings. Post the ticket, attach the file, and compare the downloaded attachment with the local file byte for byte.

## Jira wiki markup

The assembler handles these, and `checks.py` flags any it misses. Each was found by posting and reading back.

- Inside `{{...}}`, Jira drops the escaping backslash before `{ } [ ] * | !` and keeps it before anything else, so `{{"a\"b"}}` shows `"a\"b"`.
- A code span holding only a backslash has no working encoding. `{{\}}` loses the monospace, `{{\\}}` shows two backslashes, and `&#92;` stays undecoded. The assembler writes the word backslash.
- Jira closes `{{...}}` only next to certain characters. The confirmed ones are a space, `, / . ' - ; )`, and a newline after a span, and a space, `/`, `(`, and a newline before one. The assembler puts a space between a span and any other neighbor.
- A markdown backtick run pairs only with a run of the same length. A literal ```` ```json ```` in a finding stays text.
- Code languages outside `javascript json yaml bash python sql csharp` are written as `none`, because no other language name was seen rendering.

## What the settings are based on

| Setting | Evidence |
| ------- | -------- |
| Opus at xhigh as the judge | On 10 units holding 10 known wrong sentences, Opus xhigh removed 10 of 10 for $3.84, Fable at medium 10 of 10 for $6.93, Fable at high 10 of 10 for $9.65, and Opus at high 9 of 10 for $1.72. On the full run, 618 units took 17 minutes and $188.59 at list price with 50 concurrent. |
| A reason on every keep | Every wrong sentence that survived a judge was a keep with an empty reason. A re-judge of the 291 units with such keeps, under the rule, cost $98.49. |
| Isolated `claude -p --bare` processes | Workflow subagents received the operator's CLAUDE.md, skill listing, MCP instructions, and hooks. A Serena hook denied their reads, and the CLAUDE.md prose rules changed punctuation inside quoted code. A bare process starts with about 3,000 tokens of context, against 77,000. |
| `--tools Bash,Read` under `dontAsk` | `--bare` has no Grep or Glob, and asking for them yields Read alone, which hid search from a whole run. Search runs through Bash, read-only commands run, and writes are denied. `cd`, `awk`, `xargs`, `cut`, `node`, variable assignment, and `$(...)` were denied in practice, so the prompt names them. |
| A 5-minute prompt cache | With `ENABLE_PROMPT_CACHING_1H` set, every cache write was billed at the 1-hour rate, twice the input price. The pool removes it and sets `CLAUDE_CODE_PROMPT_CACHE_TTL=5m`. |
| A content check on every answer | A JSON schema checks shape. Models answered schema rejections with placeholders such as `reason: "test"` and evidence `a:1`, and quoted code with dropped type annotations and rewritten punctuation. |
| One process per ticket, not one long session | A session judging many tickets rereads its whole growing context every turn. A per-ticket session ends near 26,000 tokens. |
| A clean checkout of the commit | Judges that searched the live tree read other reviewers' findings from the review state directory. The checkout also drops the files listed in `run.json` `judge_exclude`, such as `CLAUDE.md` and `.claude/`. |
| The lower of two ratings | The operator's rule. Judges rate lower than reviewers, and on one 618-unit production run 459 units moved down. |

## Reporting counts

A ticket carries one category label for every perspective that raised any of its findings, and most tickets carry more than one. In a table of tickets by category and priority, the category rows count labels, so they add up to more than the number of tickets. Label the rows as tickets carrying that category, and give distinct tickets as a separate total.

## Files

Under `RUN/tickets/`:

- `plan.json`, `units.jsonl`, the planned issues and their per-file units
- `judge/results.json`, `judge/merged.json`, every judge answer with its attempts and cost, and `judge/calls/` with each process's event stream
- `edits.json`, `merges.json`, `merge_edits.json`, `decisions.json`
- `final/<ID>.json`, one posting payload per ticket, `final/manifest.json`, and `postable.json`
- `dup_pairs.json`, `bundle/`

## Tests

Tests and evals for both review skills live in `evals/review/` at the root of the clanker-skills repository, outside the installed skill.

| Check | Command, from `evals/review/` | Cost |
| ----- | ------ | ---- |
| Unit tests, one directory per skill | `uv run --with pytest pytest -q unit/review_deep` and `unit/review_tickets` | none |
| End-to-end replay on the harbor fixture | `uv run --with pytest pytest -q test_end_to_end.py` | none |
| Live quality eval against `fixture/truth.json` | `python3 live_eval.py WORK_DIR --run` | about $3 at list price |

Run the unit tests and the replay after any change to `scripts/`. The replay stops with "prompt changed" when a prompt changes. Record again with `python3 pipeline.py WORK_DIR --mode record`, check the run with `live_eval.py`, and save it with `python3 golden.py save RUN_DIR`. Run the live eval on demand after changing a model, an effort level, or a prompt.

## Rules

- NEVER post without the operator's explicit go, and never bulk-post before the first ticket has been read back.
- NEVER let a judge read the live working tree. Judges run in `run.json` `checkout`.
- NEVER accept a model answer without its content check, and never accept an evidence quote that is not the code at the reviewed commit.
- Keep prompts in `prompts/` as `.txt`. A markdown formatter rewrote a `.md` prompt and changed its meaning.
- Report counts as measured. A ticket count, a label count, and a finding count are three different numbers.
