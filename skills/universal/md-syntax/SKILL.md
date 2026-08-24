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
- **Write to the formatter contract** - A PostToolUse hook reformats markdown after every write. See `/md-lint` for what it rewrites and which lint rules it cannot fix
- **Blank lines between styles** - Put single blank line between different markdown types

## Examples

### Blank lines between styles

Put a single blank line between markdown types/styles. Do not put multiple blank lines between markdown styles.

CORRECT

```text
## Heading

paragraph

- list item one
- list item two

> block quote
```

INCORRECT

```text
## Heading


paragraph
- list item one
- list item two
> block quote
```

### Headings not bold

CORRECT

```text
### Heading

paragraph
```

INCORRECT

```text
**heading incorrect bold**

paragraph
```

### Code Blocks

Always specify language.

CORRECT with language

````text
```bash
#!/bin/bash
```
````

INCORRECT without language

````text
```
#!/bin/bash
```
````

### Trailing New Line

End the file with a single newline after the last line of content. A fenced example can't show this, because the fence hides the final byte. Check it with `tail -c 1 file.md | xxd`, which must print `0a`.
