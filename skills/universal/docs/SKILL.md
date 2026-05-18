---
name: docs
description: Update all project docs (README.md + CLAUDE.md + .llmdocs/) in parallel.
disable-model-invocation: true
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 📚

# Update All Documentation

## Arguments

If the user provided a path or scope with the invocation, pass it through to both skills below.

## Step 1: Run both doc updates in parallel

Spawn two subagents:

**Agent 1:** Run the llmdocs skill (/llmdocs, $llmdocs) with any arguments
**Agent 2:** Run the readme skill (/readme, $readme) with any arguments

## Step 2: Report

List all files created or modified across both agents.
