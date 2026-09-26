import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "skills", "universal", "review-deep", "scripts"))

SOURCE = "".join(f"line {n}\n" for n in range(1, 41))


@pytest.fixture
def repo(tmp_path):
    """A one-commit repository with source files, agent-instruction files, and review state."""
    r = tmp_path / "repo"
    for p in ("src/a.ts", "src/b.ts", "pkg/CLAUDE.md", "CLAUDE.md", ".claude/settings.json"):
        (r / p).parent.mkdir(parents=True, exist_ok=True)
        (r / p).write_text(SOURCE)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    for cmd in (["init", "-q"], ["add", "."], ["-c", "commit.gpgsign=false", "commit", "-q", "-m", "one"]):
        subprocess.run(["git", "-C", str(r), *cmd], check=True, env=env)
    sha = subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    state = r / ".llmtmp" / "review-deep"
    (state / "components").mkdir(parents=True)
    (state / "components" / "c01.txt").write_text("src/a.ts\nsrc/b.ts\n")
    (state / "claude-security.md").write_text(
        "## Security\n\n"
        "- **High** `src/a.ts:12` `login` Trusts the header with no check.\n"
        "- **Medium** `src/b.ts:3-5` Missing timeout on fetch.\n")
    (state / "openai-security.md").write_text("## Security\n\n- **Critical** `src/a.ts:12` `login` Header forgery grants admin.\n")
    (state / "ocr-scan.json").write_text(json.dumps({"comments": [
        {"path": "src/b.ts", "start_line": 4, "severity": "low", "category": "bug", "content": "No timeout.", "suggestion_code": "x"}]}))
    run = tmp_path / "run"
    run.mkdir()
    (run / "run.json").write_text(json.dumps({"repo": str(r), "commit": sha, "state_dir": str(state), "run_dir": str(run),
                                              "checkout": str(tmp_path / "run" / "checkout"),
                                              "judge_exclude": ["CLAUDE.md", ".claude", ".llmtmp"]}))
    return {"repo": r, "sha": sha, "run": run, "state": state}
