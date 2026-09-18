# Prose eval suite

Measures whether the ghostwriting contract changes prose the model writes. Each
case hands the model a span and asks for a rewrite. Graders check the output,
never the path the model took to get there.

The contract itself is `configs/claude-code/claude_md.md` in the dotfiles repo,
which is the source of truth and the only copy to edit. dotbot symlinks it to
`~/.claude/CLAUDE.md` and to `~/.codex/AGENTS.md`, so both harnesses read the
same file. This eval suite lives in the clanker-skills repo, so the contract sits
in a sibling repo rather than in this one. The `prose` skill beside
this folder tells an editor how to apply it. Nothing in this suite restates the
rules, because the provider shells out to `claude -p` and the global
instructions are already loaded. That means a run measures the deployed
contract, and editing the catalog changes what this suite scores.

## Running it

```bash
cd skills/universal/prose/evals
npx promptfoo@latest eval          # full suite
npx promptfoo@latest view          # browse the results
```

No install step. The provider authenticates through whatever Claude Code already
uses, so no API key is needed.

```bash
EVAL_MODEL=claude-opus-5 npx promptfoo@latest eval   # pin a model
npx promptfoo@latest eval --filter-first-n 20        # quick smoke
npx promptfoo@latest eval --filter-pattern gnomic    # one bullet
npx promptfoo@latest eval -j 8 --no-cache            # full, 8 at a time
```

`repeat: 3` and `maxConcurrency: 14` are defaults in the config, so every command
above already repeats. Pass `--repeat 1` when you only want a broken-case check.

Costs, measured. A solo call takes 10s and the harness delivers about eleven
effective workers whatever `-j` says, so throughput runs near 65 cases per
minute. The full suite is 595 cases, which is 9 minutes at `--repeat 1` and
roughly 27 minutes at the default 3. One bullet at five repeats is 50 runs and
lands under a minute.

Do not raise `-j` past 16. A wave takes 15s at `-j 16`, 29s at `-j 32` and 50s at
`-j 48`, so wave time grows in step with the fan-out and throughput stays flat.
Each case spawns a full `claude -p` process that loads the whole CLI, so the cap
is process cost rather than tokens.

## Measuring a rule change

One pass per case cannot tell a rule improvement from model variance. Three full
runs of this suite scored 94, 97 and 96 percent, and between the second and third
`praise adjectives` fell from 100 to 70 on cases nobody had touched. At ten cases
per bullet the noise band is wide enough to swallow any edit worth making.

Capture a baseline, edit the catalog, capture the result.

```bash
tools/measure-bullet.sh gnomic- before
# edit configs/claude-code/claude_md.md
tools/measure-bullet.sh gnomic- after
```

That runs five repeats per case and prints the delta split by polarity. Read the
two arms rather than the overall number, because most catalog edits move them in
opposite directions. Telling an editor to cut harder raises the rewrite arm and
lowers the preserve arm, and the overall figure hides which trade you just made.

A worked example. The `phantom-foil contrast` edit measured 87 to 90 percent
overall, which looks like noise. Split by arm it was rewrite 77 to 83 and
preserve 100 to 97, so the edit bought six points where the bullet was failing
and cost three where it was not. That is a decision you can evaluate. The overall
number is not.

One case flipping by a single trial out of five is noise. Trust an arm-level
delta, and treat a single case moving as a prompt to add repeats rather than as a
result.

## Adding a new slop sample

This is the loop the suite exists for. When a new AI tell shows up in the wild,
paste the sample and work through these five steps.

**One. Name the bullet it violates.** Search `## Banned Patterns in All Writing`
in the dotfiles repo's `configs/claude-code/claude_md.md` for a bullet that
already covers it. Never edit `~/.claude/CLAUDE.md`, which is a symlink. Most
new samples are an old pattern in a new surface form, and those need no catalog
change.

**Two. If no bullet covers it, write the bullet first.** A case with no rule
behind it grades nothing, because the model has no instruction to follow. A new
bullet needs a name, the markers that locate it, the repair, an exemption, and a
`[move N]` tag. Add it to the catalog, bump the count in the `Most writing needs
the first two` line, and add the name to that move's repair list.

**Three. Write the rewrite row.** Pick the file by granularity. One sentence goes
in `cases/sentences.csv`, a multi-sentence sample in `cases/paragraphs.csv`,
correspondence in `cases/register.csv`, a judgment bullet in
`cases/judgment.csv`, everything else in `cases/mechanics.csv`.

```csv
__description,polarity,bullet,input,__expected1,__expected2
"my-case-01","rewrite","gnomic restatement","The job dropped 400 rows. A pipeline that writes before it validates hands the next run a corrupt partition.","not-contains:A pipeline that","icontains:400"
```

Most rewrite rows want one `not-contains` proving the marker went away and one
`icontains` proving a fact survived. A rewrite that drops the defect by dropping
the content is a failure, and only the second assertion catches it.

**Four. Write at least one preserve row.** This is the step that matters and the
easy one to skip. Every bullet carries an exemption, so a suite built only from
defects trains an editor to delete on sight. A preserve row uses the same surface
form and the exemption's context, and the assertions prove the thing survived.

```csv
"my-case-02","preserve","gnomic restatement","A failed probe is not a healthy pod. Treat a timeout as a failure everywhere in this document.","icontains:timeout",""
```

Aim for three preserve rows in every ten. The suite currently sits at 30 percent.

**Five. Run it and keep only what fails.** A case that passes on its first run
teaches nothing, because the model already handles it without the rule. It also
costs a model call on every future run forever.

```bash
npx promptfoo@latest eval --filter-pattern my-case --no-cache
```

A failing case is the useful one. Fix the catalog wording, rerun, and the case
should flip to passing. If it still fails after a wording fix, either the bullet
is unclear or the case is ambiguous, and Anthropic's eval guidance says a good
case is one two careful editors grade the same way.

## Layout

| Path                    | Holds                                                |
| ----------------------- | ---------------------------------------------------- |
| `promptfooconfig.yaml`  | Provider, shared graders, the case file list         |
| `prompts/rewrite.txt`   | The instruction wrapped around every case            |
| `providers/deployed.sh` | `claude -p` wrapper, MCP and session persistence off |
| `graders/`              | JavaScript assertions that run on every case         |
| `cases/*.csv`           | The suite, one row per case                          |
| `tools/`                | Confluence mining and corpus chunking                |
| `corpus/`               | Mined pages and candidate spans, gitignored          |

## Case columns

`__description` is the case name and the only column `--filter-pattern` matches,
so keep it unique and greppable.

`polarity` is `rewrite` for a real defect and `preserve` for a span an exemption
protects.

`bullet` names the catalog entry verbatim. Nothing reads it at run time, and the
coverage tally groups on it, so a typo silently creates a new bullet.

`__expected1` and `__expected2` take promptfoo's string assertion syntax.
`not-contains:X`, `icontains:X`, `contains:X`, and `regex:X` all work.

## Writing an assertion that survives a rewrite

On the first full run, 36 of 595 cases failed and most of those were the
assertion rather than the rule. Four traps produced nearly all of them.

Matching an inflected word. A rewrite changes `flagging` to `flags` and `merging`
to `merged`, so `icontains:flagging` fails on correct output. Match the stem,
`icontains:flag`, or match a noun the rewrite has no reason to touch.

Demanding the deleted thing survive. `This is more than a runbook, it is an
operating model` becomes `This is an operating model`, and an
`icontains:runbook` assertion insists the foil stay. Assert on what the rewrite
keeps, not on what it removes.

Banning the fact instead of the defect. An empty-table case whose input reads
`All nine rows show a dash` still has to say the rows are empty. Ban the
structure that is wrong, `not-contains:by service. All`, and leave the fact
alone.

Escaping a regex through CSV. `regex:\\b(is|are)\\b` arrives at the grader as a
literal backslash and never matches. Prefer `contains` and `not-contains`, and
reach for `regex` only when nothing simpler works.

The general rule is that a `not-contains` should name the marker and an
`icontains` should name a fact the rewrite must carry forward. An assertion
naming a whole phrase is testing the model's word choice rather than the rule.

## Graders

Three JavaScript graders in `defaultTest` run on every case, and only three.

`banned-literals.js` fails on an em-dash, a spaced double hyphen, a semicolon, or
`load-bearing`. Those four are the only marks the catalog bans with no exemption
anywhere, so they are the only ones safe to assert blindly.

`no-prose-colon.js` fails on any colon surviving after code fences, code spans,
URLs, clock times, and ratios are stripped.

`length-guard.js` fails a rewrite that grew past 1.1x its source, and only on
sources of 40 words or more. A sentence rewrite legitimately grows, because
splitting one clause into two costs words. `MIN_WORDS` and `TOLERANCE` are
guesses and want calibrating against real pages.

Every other bullet carries an exemption, so a blanket assertion on it would fail
correct output. Those belong in per-row `__expected` columns.

The LLM rubric graders are not wired up. Bullets needing real judgment, meaning
gnomic restatement and phantom-foil, are graded today by deterministic proxies
that catch the marker and not the reasoning. Wiring a rubric means setting
`defaultTest.options.provider` and confirming the chosen provider returns the
JSON verdict promptfoo expects.

## The corpus

`tools/mine-confluence.sh` pulls page bodies and keeps the ones dense in
em-dashes, which is the strongest single selector for generated prose. Measured
across 193 recent pages against 140 written before mid-2023, em-dash density runs
9.03 per thousand words against 0.23, a 39x gap.

```bash
MINE_LIMIT=480 MINE_MONTHS=12 MINE_PARALLEL=8 ./tools/mine-confluence.sh
python3 tools/chunk-corpus.py --source raw
```

### Keeping the corpus representative

Three constructions exist because the first version was not, and each is tied to
a number.

The miner runs one query per month rather than one for the window. A single
`created >= X ORDER BY created DESC` with a limit returns the newest N and
nothing else, so a year-long window produced a corpus spanning nine days. Twelve
buckets at 40 pages each gives 480 pages across 74 spaces and 126 authors, with
the top five spaces at 30 percent.

The pool builder caps paragraphs at three per page. Uncapped, five pages supplied
45 percent of the in-band paragraphs and one status update supplied 23 alone. The
cap takes those five to 7 percent and leaves 220 paragraphs from 123 pages.

Paragraphs come from `<p>` only, and the selector has a third verdict for content
that is not prose at all. A data dump, a task export or a scorecard is not a bad
paragraph, and the two-verdict version voted rewrite on all of them.

Two limits to state rather than fix. The buckets run 2025-09 through 2026-08, so
the newest month is missing along with the most AI-dense prose in it. And an
agent-authored page is undetectable after the fact, so the corpus cannot be
proven free of prose this contract produced. The year-wide sample cuts that share
to roughly a twelfth of what a recent-only window carried.

Marker density itself is a moving target. 36 percent of pages in a nine-day
September 2026 window carried three or more em-dashes against 14 percent across
the full year, so any density threshold ages.

Everything under `corpus/` is gitignored and stays that way. This repo and the
dotfiles repo are both public, so mined page bodies, the candidate spans, and the
scrub table never get committed. A case reaching `cases/*.csv` is written fresh
over invented facts, carrying the defect shape and none of the source content.

Scrubbing real spans was tried and dropped. The substitution table is itself an
inventory of proprietary terms, and replacing nouns changes the specificity and
rhythm that a style eval exists to measure.

## The launder loop

This is the end-to-end measurement. A bad paragraph goes in, the contract
rewrites it, and a separate process with no history decides whether the result
reads human. The target is 90 percent.

```bash
tools/build-launder-set.py --pool --pool-size 200
npx promptfoo@latest eval -c promptfooconfig.pool.yaml -o /tmp/pool.json
tools/build-launder-set.py --select /tmp/pool.json --n 60
npx promptfoo@latest eval -c promptfooconfig.launder.yaml -o /tmp/launder.json
tools/launder-report.py /tmp/launder.json
```

Three things about it are deliberate.

Every judge reasons before it decides. Both `prompts/select.txt` and
`prompts/discriminate.txt` ask for the words that decided it, then a `VERDICT`
line the assertion reads. An earlier version demanded one word with no
explanation, which threw away the only diagnostic signal in the run. Reading five
judge explanations found in a minute what three rounds of feature engineering had
missed.

Nothing heuristic picks the set. Pass one writes every prose paragraph in the
word band to a pool, and pass two keeps the ones the selector wanted rewritten on
every run. The first version ranked paragraphs by marker density and counted
label-colon among the markers, which selected scorecards and rubrics written as
paragraphs. A prose contract has no business being scored on those.

Paragraphs come from `<p>` elements only. `chunk-corpus.py` used to split on
`</li>`, `</td>` and `</h*>` as well, which let every list item and table cell
past twelve words through as a paragraph. That was 8 percent of the corpus.

The baseline arm is the same paragraphs judged with no rewrite, so its
run-to-run movement is a free noise estimate. On one pair of runs it moved 1.7
points, which sets the bar a real effect has to clear.

### The judge must never load the contract

Every judge call passes `--setting-sources project`, which gives a session that
does not read `~/.claude/CLAUDE.md`. The rewriter does not pass it, because
loading the contract is the thing under test.

This is not a nicety. Without the flag the judge can recite the 55-bullet catalog
verbatim, statistics included, and asked to name the banned marks it answers
"colons and semicolons, in every position." A judge holding the catalog is not
reading the prose, it is grading compliance with the rules that produced the
prose, and every verdict becomes circular. Asked the same question, a session
with the flag replies `NO CONTRACT`.

`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` does not work for this. It was tested and the
catalog still loaded.

Check it after any change to a provider.

```bash
claude -p --setting-sources project 'Name the banned punctuation marks in the house prose contract you were given. If you were given no such contract, reply NO CONTRACT.'
```

An earlier round of this suite ran every judge without the flag. The launder
figures it produced, a 37.2 percent baseline rising to 59.4 and later a 42.8
falling to 33.9, all measured catalog compliance rather than how the prose reads,
and none of them mean what their labels say.

### The ceiling

`promptfooconfig.ceiling.yaml` runs known-human paragraphs from the same
Confluence and the same word band through the same judge. It scored 263 of 270,
97.4 percent. That is what makes the 90 target meaningful and a laundered score
of 62 a real gap rather than a judge artifact. Re-run it whenever the judge
prompt changes.

## Style discrimination

A second suite asks a different question. Hand the model a passage and ask
whether a person wrote it or a model produced it. Labels come from page creation
date, which is the only ground truth available. Pages created 2025-09 onward and
dense in em-dashes count as generated, pages created before 2023-06 count as
human.

```bash
tools/build-discrimination-set.py --n 40
npx promptfoo@latest eval -c promptfooconfig.discriminate.yaml
```

Two arms get built from the same sampled chunks. The marked arm leaves
punctuation alone, so a model can answer by counting em-dashes. The stripped arm
normalises em-dashes, semicolons and colons out of both classes and repairs the
sentence capitalisation the substitution breaks, because a mangled sentence start
lands more often on the class that used more semicolons and would leak the label.

The gap between the two arms is the measurement worth having. It says how much of
the score was mechanical and how much was style.

Two confounds stay open. Length is matched by the sampling band, 90 to 320 words.
Topic is not matched, because the two date ranges cover different work, so read a
high marked score as style plus topic era rather than style alone. And the
generated class was selected by em-dash density in the first place, so the marked
arm is partly scoring its own selector.

Both CSVs land under `corpus/` and stay gitignored, because the passages are real
internal prose.

## Coverage

595 cases across 56 bullets, every one at ten or more. Preserve rows are 29
percent of the suite.

The 56 covers all 55 catalog bullets plus a few rules from the
`Ghostwriting for Other Humans` section that behave the same way, meaning
`subject census`, `a number you computed is invented`, and
`warmth that changes what the reader does`.

## Mining candidates

`tools/judge-scan.sh` runs a judgment pass over the chunked corpus, one bullet
group per call, and writes candidate spans to `corpus/candidates-<source>.jsonl`.

```bash
SCAN_LIMIT=20 SCAN_PARALLEL=6 ./tools/judge-scan.sh
```

The catalog reaches the judge through the global instructions, so the prompt
carries only the group's bullet names. Groups live in `tools/bullet-groups.json`
and cover the bullets a regex pass detects poorly. No group holds more than seven
bullets, because Anthropic's guidance is to grade each dimension with an isolated
judge rather than one judge holding every dimension.

Measured on two chunks across four groups, the pass returned 28 candidates with
13 of them `preserve`. Those spans are real internal prose, so they stay in
`corpus/` and a case reaching `cases/*.csv` gets rewritten over invented facts.

One trap worth knowing if you edit this script. The array is `BULLET_GROUPS` and
never `GROUPS`. Bash owns `GROUPS` as a special variable holding the current
user's Unix group ids and keeps repopulating it, so an assignment to it yields a
list of gids, and a `mapfile` into it aborts the script under `set -e` with
nothing on stdout or stderr.

One gap remains. The Python helpers under `tools/` are loose scripts run with
`python3`, which departs from the repo's uv-and-src-layout convention. They stay
that way because the suite is driven by promptfoo rather than by Python, and a
`pyproject.toml` for six helpers would cost more than it returns.
