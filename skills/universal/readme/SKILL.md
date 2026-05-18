---
name: readme
description: Write documentation based on conversation history and folder contents
argument-hint: "[optional guidance]"
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 📓

# Documentation Creation

Write markdown content based on the current conversation context and folder contents.

README is current state specification for a human user, not a changelog, not a decision log, not historical record. Never record
historical information or choices made, only the specification as it stands at the time of writing the README.

## Related Skills

- use the md-syntax skill (/md-syntax, $md-syntax) for markdown rules and syntax
- use the md-style skill (/md-style, $md-style) for authoring conventions and writing style
- After writing, use the md-lint skill (/md-lint, $md-lint) on the file to format and lint

## Scope

Find all README.md files in the project and update each.
Folder contents are at the README's level and below (siblings and subfolders), never above (parents).
Pay attention to subfolder layers, scope and bounded contexts. Do not leak
concepts between documents at different layers. Each README covers its own
directory level and below, never parent concerns.

If the user provided specific guidance or focus areas, apply that context
when deciding what to emphasize in the documentation.

## Gather Context

For each README found, scoped to its directory:

1. Read current README (if exists)
2. Compute what changed since it was last touched:

```bash
TARGET_DIR=$(dirname <target-readme-path>)
BASELINE=$(git log -1 --format=%H -- <target-readme-path>)
git diff ${BASELINE}..HEAD --stat -- "$TARGET_DIR"
git log --oneline ${BASELINE}..HEAD -- "$TARGET_DIR"
```

3. Explore codebase at that directory level and below
4. Review conversation history for relevant decisions, changes, or lessons learned
5. Use the diff and conversation context to identify what sections need updating. Verify code against docs and docs against code.

## README.md Outline

Example document structure for README.md.

```markdown
# Title

Brief overview. No more than five sentencies.

<!-- OPTIONAL IMAGE OR VIDEO HIGHLIGHT -->
<img src="somedemo.png" alt="Some Demo" width="800"/>

## Architecture

High level components and purpose

- Component - purpose
- Component - purpose

## Prerequisites

- Prerequisite - description and reason (accounts, keys, credentials, tools, runtimes, CLIs)

## Project Structure

Show folder structure. Don't include files.

\`\`\`text
davit/
├── src/
│ ├── davit-api/ # Go API server (k8s client) - see src/davit-api/README.md
│ ├── davit-ui/ # Go web UI server - see src/davit-ui/README.md
│ ├── davit-dinghy/ # Alpine dinghy container - see src/davit-dinghy/README.md
│ └── macos-proto-handler/ # macOS VSCode integration - see src/macos-proto-handler/README.md
├── scripts/ # Build and deployment scripts
└── tests/ # Test suites
\`\`\`

## Installation

\`\`\`bash

# install manifest

kubectl apply manifest.yaml
\`\`\`

## Usage

\`\`\`bash

# Build all components

make all

# Or build individually

make build-api
make build-dinghy
\`\`\`

## Testing (optional if tests present)

\`\`\`bash

# Run all tests (placeholder)

make test

# Run specific test suites

make test-api
make test-pod
make test-integration
\`\`\`
```
