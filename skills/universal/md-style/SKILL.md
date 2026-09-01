---
name: md-style
description: README style guide for concise, direct documentation. Use when writing or editing README files.
---

<!-- markdownlint-disable-file MD041 -->

# README Style Guide

Write concise, direct README files for experienced engineers.

## Voice

Prose style is not defined here. Two sections of the global agent instructions own it, and both
load every session:

- `Ghostwriting for Other Humans` - a README is read by another human, so it takes the ghostwriting
  contract: minimum facts, one fact per sentence, the deletion test on every word
- `Banned Patterns in All Writing` - the catalog of forbidden words and constructions, including
  hype vocabulary, opposing phrases, phantom-foil contrast, emojis, and emdashes

This skill covers what belongs in a README and in what order.

## Principles

- **No fluff** - Skip tables of contents, verbose explanations, development history
- **No roadmaps** - Document current state only, not plans or decisions. Readme is an engineering specification. Not a project plan or changelog.

## Structure

Sections in order: Overview, Prerequisites, Usage, Architecture, Configuration, Testing, File Structure. One-line purpose statement at top under H1.

## Exclude

- Tables of contents
- Verbose troubleshooting guides
- Development decisions/history
- Future plans/roadmaps
- Lengthy explanations of concepts
- Multiple examples of similar things

### Formatting

- Tables for structured data (components, variables, test coverage)
- Code blocks for commands and examples
- Bold for emphasis sparingly
