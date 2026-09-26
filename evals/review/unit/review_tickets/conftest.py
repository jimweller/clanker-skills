import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "skills", "universal", "review-tickets", "scripts"))

SOURCE = "\n".join([
    "export async function fetchUserList() {",
    "  try {",
    '    const res = await fetch("/api/admin/users");',
    "    if (!res.ok) return [];",
    "    return (await res.json()).users ?? [];",
    "  } catch {",
    "    return [];",
    "  }",
    "}",
    "",
    "export function lone() {",
    "  return 1;",
    "}",
]) + "\n"


@pytest.fixture
def repo(tmp_path):
    """A one-commit git repository holding src/api.ts, and a run directory pointing at it."""
    r = tmp_path / "repo"
    (r / "src").mkdir(parents=True)
    (r / "src" / "api.ts").write_text(SOURCE)
    (r / "CLAUDE.md").write_text("agent notes\n")
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    for cmd in (["init", "-q"], ["add", "."], ["-c", "commit.gpgsign=false", "commit", "-q", "-m", "one"]):
        subprocess.run(["git", "-C", str(r), *cmd], check=True, env=env)
    sha = subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    run = tmp_path / "run"
    run.mkdir()
    (run / "run.json").write_text(json.dumps({"repo": str(r), "commit": sha, "run_dir": str(run),
                                              "commit_sentence": f"Paths and line numbers refer to commit {{{{{sha}}}}}."}))
    return {"repo": r, "sha": sha, "run": run}
