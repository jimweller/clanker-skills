# Prose eval suite

Two instruments measuring the same contract at different scales.

The rewrite suite grades one rule at a time on a sentence or two, with string
assertions checking that a marker went away and a fact survived. The compliance
loop takes a whole Confluence paragraph, hands it to the prose skill, and has a
separate session grade the edit against the contract.

The contract is `configs/claude-code/claude_md.md` in the dotfiles repo, which is
the source of truth and the only copy to edit. A `<prose-contract>` tag wraps the
three sections that make up the written-artifact contract, and every rule inside
opens with a `PC-` id. dotbot symlinks the file to `~/.claude/CLAUDE.md` and to
`~/.codex/AGENTS.md`, so editing it changes what both suites score.

## Running it

```bash
cd skills/universal/prose/evals
npx promptfoo@latest eval                                # rewrite suite, 595 cases
npx promptfoo@latest eval -c promptfooconfig.comply.yaml # compliance loop, 71 paragraphs
tools/comply-report.py /tmp/out.json                     # triage the compliance run
```

No install step. The providers authenticate through whatever Claude Code already
uses, so no API key is needed.

Concurrency measured at 6.2 cases per minute at `-j 24`, 10.7 at `-j 48`, and 20.3
at `-j 96`. A 213-call compliance arm runs in 5 to 6 minutes at 96. Load average
spikes near 140 on 14 cores for the first minute, which is 96 CLI processes
booting rather than contention, and settles near 45. 96 sessions hold 16.8 GB
resident, 175 MB each.

Foundry is not the limit. At `-j 96` the run draws roughly 1M input tokens per
minute against a 2M ITPM Opus allocation, and that count is pessimistic because it
charges the contract and the catalog on every call when both are cache reads after
the first, which ITPM excludes.

## What the compliance loop measures

Each case runs two sessions. The rewriter invokes the prose skill on a paragraph
and writes its notes to a file. A second session receives the original, the
rewrite, and the contract, and reports findings of two opposite kinds.

A **violation** is a span in the rewrite that a rule bans and no exemption covers.
An **over-application** is a span in the original that an exemption protected,
which the editor changed anyway. A single pass-or-fail score cannot tell those
apart, and they call for opposite repairs: a violation means a rule is too weak, an
over-application means its exemption is.

`tools/comply-report.py` buckets the findings by diffing the editor's notes against
the judge's findings.

| Bucket                    | Means                                                                     |
| ------------------------- | ------------------------------------------------------------------------- |
| `self-inflicted`          | The violating span is absent from the original, so the rewrite created it |
| `fired-then-over-applied` | The editor recorded applying the rule and an exemption covered the span   |
| `held-then-violation`     | The editor recorded an exemption and the judge rejected it                |
| `over-applied-untraced`   | Cut a protected span without recording the rule at all                    |
| `unseen-violation`        | The judge cites a rule the notes never mention                            |

## Where the numbers stand

| | Clean |
| --- | --- |
| Sources, judged with no edit at all | 7% |
| After the prose skill rewrites them | 70% |
| Ceiling, what a perfect editor could score | about 82% |

The source paragraphs are not compliant. Judging all 71 unmodified scores 7 percent
clean, and the `good` arm scores 0. Those are the paragraphs the contract was
written from, and "written from" is not "satisfies." Taking 7 to 70 is the measure
of what the contract does.

Split by class, on the current contract with the judge pinned to the pre-edit
catalog:

| Class | Clean |
| --- | --- |
| `good` | 83% |
| `mixed` | 67% |
| `slop` | 56% |

### The target is 80 percent, not 95

A paragraph one judge pass calls clean is called clean again 82 percent of the
time, 14 of 17 measured on identical re-judges. The judge spuriously flags about
one clean paragraph in six, so a perfect editor producing perfectly compliant prose
still caps near 82 on this instrument. The noise runs both ways: a paragraph called
dirty comes back clean on a second pass 8 times in 31.

Treat any run above 78 percent as at the ceiling rather than as an improvement.
Targeting 90 or 95 means targeting a number the instrument cannot produce, and the
only way to reach it is to make the judge less strict, which is not the same as
better prose.

Two ways to raise the ceiling itself, neither tried. Run the judge more than once
per case and take a majority, which trades runtime for precision and is cheap at
`-j 96`. Or narrow what the judge grades, since it holds all 76 rules at once and
Anthropic's own guidance is that an isolated judge per dimension beats one judge
holding every dimension.

## What this instrument can and cannot measure

**Only the clean rate is reliable.** Re-judging 48 stored rewrites with the same
model and settings agreed on 39 percent of individual findings and 81 percent of
clean-or-dirty verdicts. Per-rule counts below about five are inside that noise.
On a 213-run arm, roughly 40 runs can flip between two identical runs, so a
movement smaller than that is not a result.

**Repeats are a recall mechanism, not noise-averaging.** One pass finds about 39
percent of what a second pass finds, so `comply-report.py` takes the union across
repeats rather than counting every occurrence. Counting occurrences ranked rules by
how reliably the judge noticed them instead of how often the editor broke them.

**Both sides read the same contract**, so sharpening a rule teaches the judge what
to look for at the same moment it instructs the editor. Adding a modality clause to
`PC-add-nothing` raised its finding count, and one finding cited the new clause by
name while faulting the editor. That was a detector, not a repair. For an A/B, copy
the pre-edit catalog aside and point `JUDGE_CATALOG` at it, which pins the grader
so any movement is the editor.

```bash
cp corpus/catalog.md /tmp/catalog-pinned.md
# edit the contract
JUDGE_CATALOG=/tmp/catalog-pinned.md npx promptfoo@latest eval \
  -c promptfooconfig.comply.yaml --repeat 3 -j 96 -o /tmp/after.json
```

**Run an A/B twice before believing it.** The first pinned-judge A/B moved clean
from 62 to 66 percent, which is inside the noise. The repeat landed at 70, and the
two post-edit runs agreed with each other more closely than either agreed with the
baseline, which is what made the movement credible. One run is a direction, two are
a result.

### Measuring the source baseline

Judging the sources with the rewrite set equal to the source gives the floor, and
the harness has no config for it. Stage the pairs by hand.

```bash
mkdir -p /tmp/ceil
python3 - <<'PY'
import csv, pathlib
for r in csv.DictReader(open("corpus/comply.csv")):
    d = pathlib.Path("/tmp/ceil")/r["__description"]; d.mkdir(exist_ok=True)
    (d/"source.txt").write_text(r["passage"])
    (d/"rewrite.txt").write_text(r["passage"])
PY
```

Then render `prompts/comply.txt` against each pair and run the judge with `--bare`.
71 calls at `-P 48` takes under a minute.

## Isolation

Eval sessions inherit this machine's configuration unless told otherwise, and both
kinds of leak have already corrupted a run.

**Hooks.** On one 213-call run the claude-mem worker went unreachable for 65
consecutive hooks, and some sessions returned the block banner in place of a
rewrite, which the judge graded as prose. That produced 10 `PC-assistant-tool-leaks`
findings and 21 runs with no notes file. The rewriter now passes
`--setting-sources project`, which drops user settings where the hooks live while
keeping the contract and the skill, because `~/.claude/CLAUDE.md` is a symlink into
this repo and resolves as a project source.

**The contract reaching the judge twice.** The judge is supposed to hold only the
catalog its prompt carries. `--setting-sources project` does not deliver that from
inside this repo, for the same symlink reason, so an earlier version had to `cd` to
a temp directory first. The judge now passes `--bare`, which loads no CLAUDE.md at
all and removes the cwd dependency. `--bare` is wrong for the rewriter: it strips
the contract and the skill, which is the thing under test.

## The corpus

`corpus/comply.csv` holds 71 paragraphs selected by reading all 262 candidates
rather than by a filter. An `expect` column records the judgment a reader should
reach.

| Class   | n   | Tests                                             |
| ------- | --- | ------------------------------------------------- |
| `good`  | 27  | Restraint. A rewrite should change almost nothing |
| `mixed` | 28  | Ordinary technical prose                          |
| `slop`  | 16  | Repair. Generic openings, triads, hype            |

The `good` set comes from the SEAD platform pages, which are the prose the contract
was written from. Two of the selected paragraphs appear in the contract as exemption
examples. That gives the suite a ceiling, since damage to those is over-application
with no ambiguity about the source.

The previous selection took the 60 longest paragraphs the judge wanted rewritten on
every pass, which loaded the set entirely with defective text and made
over-application nearly unmeasurable. It also keyed on passage text and discarded
the page id the pool already carried, so no case traced back to a page. Selection
now round-robins across spaces and authors and writes `page_id`, `space_id`,
`author_id`, `created` and `expect`.

Meeting minutes are excluded. They are AI-transcribed attributed speech rather than
authored prose, they score about 10 points worse on the clean rate, and a prose
contract has no business being measured on them. Also excluded: Jira ADF JSON dumps,
UUID action-item lists, testimonial quotes, and PRD boilerplate that appeared
verbatim on three separate pages.

Everything under `corpus/` is gitignored and stays that way. Both repos holding this
suite are public, so mined page bodies never get committed. A case reaching
`cases/*.csv` is written fresh over invented facts.

## Rule ids

Every rule opens with a `PC-` id, 76 in total, 55 in `Banned Patterns` and 21 in
`Ghostwriting`. The five moves in `How to Write` keep their `[move N]` tags, which
already cross-reference from every banned-pattern rule.

Free-text rule names did not survive two sessions. One run scored
`trailing supplements` and `trailing supplements that hang a second beat on a
finished clause` as two rules at 3 each instead of one at 6, and did that to three
rules. An id is either in the contract or it is not, so `comply-report.py` reports
any finding citing an id the contract does not define.

`tools/check-anchors.py` fails on an unknown id, a rule with no id or two, a
duplicate id, a `[move N]` pointing at nothing, and a `corpus/catalog.md` whose
content differs from the contract. That last check exists because the provider
rebuilds the catalog on an `mtime` comparison, which a `git checkout` defeats.

Watch for terms the callers use that the contract never defines. `style-rule`
appeared once in the judge prompt carrying the definition of a violation, and zero
times in the contract, so the judge had to infer it. Same defect as
`house prose contract`, which the contract also never answered to.

## Measuring a rule change

One pass per case cannot tell a rule improvement from model variance. Three full
runs of the rewrite suite scored 94, 97 and 96 percent, and between two of them
`praise adjectives` fell from 100 to 70 on cases nobody had touched.

```bash
tools/measure-bullet.sh gnomic- before
# edit configs/claude-code/claude_md.md
tools/measure-bullet.sh gnomic- after
```

That runs five repeats per case and prints the delta split by polarity. Read the two
arms rather than the overall number, because most contract edits move them in
opposite directions. Telling an editor to cut harder raises the rewrite arm and
lowers the preserve arm.

## Adding a new slop sample

**One. Name the rule it violates.** Search inside `<prose-contract>` for a rule that
already covers it. Never edit `~/.claude/CLAUDE.md`, which is a symlink. Most new
samples are an old pattern in a new surface form.

**Two. If no rule covers it, write the rule first.** A case with no rule behind it
grades nothing. A new rule needs a `PC-` id, a name, the markers that locate it, the
repair, an exemption, and a `[move N]` tag.

**Three. Write the rewrite row.** One sentence goes in `cases/sentences.csv`, a
multi-sentence sample in `cases/paragraphs.csv`, correspondence in
`cases/register.csv`, a judgment rule in `cases/judgment.csv`, everything else in
`cases/mechanics.csv`.

```csv
__description,polarity,bullet,input,__expected1,__expected2
"my-case-01","rewrite","PC-gnomic-restatement","The job dropped 400 rows. A pipeline that writes before it validates hands the next run a corrupt partition.","not-contains:A pipeline that","icontains:400"
```

Most rewrite rows want one `not-contains` proving the marker went away and one
`icontains` proving a fact survived. A rewrite that drops the defect by dropping the
content is a failure, and only the second assertion catches it.

**Four. Write at least one preserve row.** Every rule carries an exemption, so a
suite built only from defects trains an editor to delete on sight. Aim for three
preserve rows in every ten. The suite sits at 29 percent.

**Five. Run it and keep only what fails.** A case that passes on its first run
teaches nothing and costs a model call on every future run forever.

## Writing an assertion that survives a rewrite

On the first full run, 36 of 595 cases failed and most were the assertion rather
than the rule. Four traps produced nearly all of them.

Matching an inflected word. A rewrite changes `flagging` to `flags`, so
`icontains:flagging` fails on correct output. Match the stem.

Demanding the deleted thing survive. `This is more than a runbook, it is an
operating model` becomes `This is an operating model`, and `icontains:runbook`
insists the foil stay. Assert on what the rewrite keeps.

Banning the fact instead of the defect. An empty-table case whose input reads `All
nine rows show a dash` still has to say the rows are empty. Ban the structure.

Escaping a regex through CSV. `regex:\\b(is|are)\\b` arrives as a literal backslash.
Prefer `contains` and `not-contains`.

## Graders

Three JavaScript graders in `defaultTest` run on every rewrite-suite case.

`banned-literals.js` fails on an em-dash, a spaced double hyphen, a semicolon, or
`load-bearing`. Those four are the only marks the contract bans with no exemption
anywhere, so they are the only ones safe to assert blindly.

`no-prose-colon.js` fails on any colon surviving after code fences, code spans,
URLs, clock times, and ratios are stripped.

`length-guard.js` fails a rewrite that grew past 1.1x its source, and only on
sources of 40 words or more. `MIN_WORDS` and `TOLERANCE` are guesses.

The compliance loop carries one assertion, that the judge emitted a parseable
`VERDICT` line. That is a format check so a malformed run is visible, not a style
judgment. The contract is stylistic and every rule has an exemption, so a string
assertion cannot encode one.

## Layout

| Path                          | Holds                                                            |
| ----------------------------- | ---------------------------------------------------------------- |
| `promptfooconfig.yaml`        | Rewrite suite: provider, shared graders, case files              |
| `promptfooconfig.comply.yaml` | Compliance loop                                                  |
| `promptfooconfig.pool.yaml`   | Pass one of corpus selection                                     |
| `prompts/`                    | The instructions wrapped around each case                        |
| `providers/`                  | `claude -p` wrappers                                             |
| `graders/`                    | JavaScript assertions for the rewrite suite                      |
| `cases/*.csv`                 | The rewrite suite, one row per case                              |
| `tools/`                      | Mining, selection, reporting, anchor checking, judge calibration |
| `corpus/`                     | Mined pages, selected paragraphs, notes, gitignored              |

## Judge calibration

`tools/calibrate-judge.sh` re-judges rewrites a previous run already produced, using
a different model or effort, and `calibrate-report.py` diffs the findings. Both
judges see identical text, so the only variable is the model. Re-running the whole
pipeline would prove nothing, because the rewriter is non-deterministic and the two
judges would be scoring different text.

```bash
tools/calibrate-judge.sh /tmp/run.json claude-sonnet-5 48 medium
tools/calibrate-report.py corpus/calibrate/claude-sonnet-5-medium
```

Measured against a 39 percent finding-level and 81 percent clean-or-dirty noise
floor:

| Judge                    | Finding-level | Clean or dirty |
| ------------------------ | ------------- | -------------- |
| Opus, identical settings | 39%           | 81%            |
| Opus, medium effort      | 30%           | 79%            |
| Sonnet, default          | 21%           | 67%            |
| Sonnet, medium           | 20%           | 60%            |

Opus at medium sits inside the floor and cannot be shown to differ, so the judge
runs at medium effort. Sonnet is clearly below it and is not a substitute at any
effort.

## Mining candidates

`tools/mine-confluence.sh` pulls page bodies. `tools/judge-scan.sh` runs a judgment
pass over the chunked corpus, one rule group per call, writing candidates to
`corpus/candidates-<source>.jsonl`. Groups live in `tools/bullet-groups.json` and
carry `PC-` ids. No group holds more than seven rules, because grading each
dimension with an isolated judge beats one judge holding every dimension.

The miner runs one query per month rather than one for the window. A single
`created >= X ORDER BY created DESC` with a limit returns the newest N and nothing
else, so a year-long window produced a corpus spanning nine days.

One trap if you edit `judge-scan.sh`. The array is `BULLET_GROUPS` and never
`GROUPS`. Bash owns `GROUPS` as a special variable holding Unix group ids, so an
assignment to it yields a list of gids and a `mapfile` into it aborts the script
under `set -e` with nothing on stdout or stderr.

## Coverage

595 rewrite-suite cases across 56 rules, every one at ten or more, 29 percent
preserve rows. The compliance loop runs 71 paragraphs at three repeats, 213 calls.

Twenty of the 76 rules have no rewrite-suite case. `check-anchors.py` lists them and
does not fail, because a rule is allowed to exist before anyone writes a case.

## Open

**The 70 percent is not attributed.** Three contract changes landed in the same
A/B: the worked paragraph, the `PC-emdashes` trim, and the `PC-evidential-status`
compression. Removing the worked paragraph and re-running with the judge still
pinned separates them, and the answer decides what the next edits look like. If the
example carries the gain, write more worked paragraphs. If the trims do, trim the
other overloaded rules.

**The quotable number is still unmeasured.** 70 percent was measured with the judge
pinned to the pre-edit catalog. The deployed configuration has the judge on the
current one, and that run has not happened.

**The `good` arm damages about one run in six.** The diagnosis is specific and not
what it looks like. The editor is not over-applying there. It is editing text that
needed no edit and introducing defects doing it: a trailing anaphor, a gerund
subject, a nominalization in the subject slot, a reassigned attribution. That points
at a missing stop condition rather than a wrong rule.

**`PC-add-nothing` leads every run** at 28 of 74 findings, almost all self-inflicted.
The editor drops modals, tenses and scoping quantifiers, turning "worked that day"
into "were working" and "sometimes for days or even weeks" into "for days or even
weeks." A modality clause was added to the rule and did not move the number.
