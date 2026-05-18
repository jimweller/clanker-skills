---
name: md-syntax
description: Markdown authoring guidelines for formatting, code blocks, and structure. Use when writing or editing markdown files.
---

<!-- markdownlint-disable-file MD041 -->

# Markdown Authoring Guidelines

Follow these rules when creating or editing markdown files.

## Rules

- **Always specify language on code blocks** - Use `bash`, `yaml`, `json`, `text`, `hcl`, `go`, etc. Never use bare ` ``` `
- **No AI slop** - Never use emojis, glyphs or emdashes
- **Use headings, not bold for section titles** - Use proper heading levels (`##`, `###`, etc.) not `**Bold**` on its own line
- **One H1 per file** - Only one `# Title` at the top
- **First line should be H1** - Start files with `# Title`
- **Run md-lint command** - Use `/md-lint` to format and lint after writing the file
- **Blank lines between styles** - Put single blank line between different markdown types

## Examples

### Blank lines between styles

Put a single blank line between markdown types/styles. Do not put multiple blank lines between markdown styles.

CORRECT

`````markdown
## Heading

paragraph

- list item one
- list item two

> block quote

````text

INCORRECT

```markdown
## Heading

paragraph

- list item one
- list item two

> block quote
```text

### Headings not bold

CORRECT

```markdown
### Heading

paragraph
```text

INCORRECT

```markdown
**heading incorrect bold**

paragraph
```text

### Code Blocks

Always specify language

CORRECT with language

```bash
#!/bin/bash
```text

INCORRECT without language

```text
#!/bin/bash
```text

### Trailing New Line

Always include a single trailing newline so the file ends in a blank line

INCORRECT no trailing newline

```markdown
The End.
```text

CORRECT trailing newline

```markdown
The End.
```text
````
`````
