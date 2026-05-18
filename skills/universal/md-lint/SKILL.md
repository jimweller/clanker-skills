---
name: md-lint
description: Format and lint markdown files using prettier and markdownlint-cli2. Always use after writing markdown files (*.md) intended for humans.
context: fork
---

<!-- markdownlint-disable-file MD041 -->

STARTER_CHARACTER = 🔏

# Markdown Lint

Format and lint markdown files with auto-fix enabled.

## Usage

If the user specified file paths, process only those markdown files.
If no files were specified, process all markdown files in the repository (submodule contents excluded).

To fix all markdown files in the repository, run from the git root:

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"

mapfile -t md_files < <({
  git ls-files '*.md'
  git ls-files --others --exclude-standard '*.md'
} | sort -u)

if [ ${#md_files[@]} -eq 0 ]; then
  echo "No markdown files to process."
else
  prettier --config ~/.prettierrc --write "${md_files[@]}" \
    && markdownlint-cli2 --config ~/.config/markdownlint/.markdownlint-cli2.jsonc --fix "${md_files[@]}"
fi
```

`git ls-files` does not recurse into submodules, so submodule contents are skipped automatically. Untracked-but-not-ignored markdown is included via the second `git ls-files --others` invocation.

To fix a specific file (can run from any directory):

```bash
prettier --config ~/.prettierrc --write "path/to/file.md" && markdownlint-cli2 --config ~/.config/markdownlint/.markdownlint-cli2.jsonc --fix "path/to/file.md"
```

## Notes

- Some markdownlint rules (like MD060) are not auto-fixable, but prettier handles them
- If an error cannot be fixed automatically by prettier, ask the user if you should fix them manually for the user.
- Submodule contents are excluded automatically. To lint files inside a submodule, run the skill from that submodule's working tree.
