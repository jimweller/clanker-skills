---
name: fact-check
description: "Use when a factual claim lacks evidence, when called out for fabricating facts, or when a statement needs verification before being presented as true. Takes a claim as argument."
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🔬

# Fact-Check

A claim was made without evidence. This skill forces verification before the claim can stand.

## Input

The argument to this skill is the claim to verify. If no argument is provided, scan the last CLANKER response for all factual claims (statements presented as true, not hedged as speculation). Run the procedure on each one.

## Procedure

1. **State the claim exactly.** Quote it. No paraphrasing.
2. **Classify the claim.**
   - **Empirically testable now**: a command, file read, or API call can confirm or refute it in this turn. Go to step 3.
   - **Researchable**: documentation, source code, or web search can provide evidence. Go to step 4.
   - **Unverifiable**: no available tool or source can confirm it. Go to step 5.
3. **Test it.** Run the command or read the file. Report the raw output. Compare to the claim. Verdict: confirmed, refuted, or partially true (state which parts hold and which fail).
4. **Research it.** Use c7, g MCP servers, WebSearch, or Read to find authoritative sources. Cite the source (URL, file path, or command output). Verdict: confirmed, refuted, partially true, or insufficient evidence.
5. **Declare it unverifiable.** State why no available tool can test it. Retract the claim or restate it as speculation with explicit qualification.

## Output format

```text
CLAIM: "<exact quote>"
TYPE: empirical | researchable | unverifiable
EVIDENCE: <raw output, citation, or "none available">
VERDICT: confirmed | refuted | partially true | unverifiable
CORRECTION: <if refuted or partially true, state the accurate version>
```

## Rules

- Never skip straight to a verdict. Show the evidence first.
- Never confirm a claim using the same reasoning that produced it. Independent evidence only.
- If the claim came from a prior observation or memory entry, that is not independent evidence. Observations record what was said, not what is true.
- If the verdict is "refuted," retract the original claim in plain language after the output block.
- A fact conceded for comfort is a lie by omission. Do not soften a refutation.
