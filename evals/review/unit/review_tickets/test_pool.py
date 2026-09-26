"""Retry and isolation behavior of the bare claude -p pool, with a fake process runner."""
import pytest

import pool

INIT = {"type": "system", "subtype": "init", "tools": ["Bash", "Read", "StructuredOutput"],
        "permissionMode": "dontAsk"}


def result(so):
    return {"type": "result", "subtype": "success", "is_error": False, "structured_output": so,
            "total_cost_usd": 0.01, "usage": {}, "num_turns": 3, "permission_denials": []}


def fake(answers, seen):
    """A runner that returns the next scripted answer and records every prompt it was given."""
    it = iter(answers)

    def runner(cmd, text, cwd, env, base):
        seen.append({"cmd": cmd, "text": text, "env": env})
        a = next(it)
        return a if isinstance(a, list) else [INIT, result(a)]
    return runner


def run(tmp_path, answers, check, seen=None):
    seen = [] if seen is None else seen
    out = pool.run([{"id": "U1", "prompt": "judge this"}], model="opus", effort="xhigh", schema={"type": "object"},
                   check=check, out_dir=str(tmp_path), cwd=str(tmp_path), runner=fake(answers, seen))
    return out["U1"], seen


def test_accepts_a_clean_first_answer(tmp_path):
    o, seen = run(tmp_path, [{"x": 1}], lambda r, t: [])
    assert o["ok"] and o["attempts"] == 1 and o["result"] == {"x": 1}


def test_retries_with_the_rejection_note(tmp_path):
    o, seen = run(tmp_path, [{"x": "test"}, {"x": 2}], lambda r, t: ["x is a placeholder"] if r["x"] == "test" else [])
    assert o["ok"] and o["attempts"] == 2
    assert "x is a placeholder" in seen[1]["text"]
    assert o["rejections"] == [["x is a placeholder"]]


def test_gives_up_after_three_attempts_but_keeps_the_last_answer(tmp_path):
    o, _ = run(tmp_path, [{"x": 0}] * 3, lambda r, t: ["always wrong"])
    assert not o["ok"] and o["attempts"] == 3 and o["result"] == {"x": 0}


def test_missing_structured_output_is_retried(tmp_path):
    o, _ = run(tmp_path, [[INIT, {"type": "result", "subtype": "error_max_structured_output_retries", "is_error": True}],
                          {"x": 1}], lambda r, t: [])
    assert o["ok"] and o["attempts"] == 2


def test_wrong_tool_set_aborts_the_pool(tmp_path):
    bad_init = dict(INIT, tools=["Read"])
    with pytest.raises(SystemExit):
        run(tmp_path, [[bad_init, result({"x": 1})]], lambda r, t: [])


def test_process_isolation_settings(tmp_path):
    _, seen = run(tmp_path, [{"x": 1}], lambda r, t: [])
    cmd, env, text = seen[0]["cmd"], seen[0]["env"], seen[0]["text"]
    for flag in ("--bare", "--disable-slash-commands"):
        assert flag in cmd
    assert cmd[cmd.index("--tools") + 1] == "Bash,Read"
    assert cmd[cmd.index("--permission-mode") + 1] == "dontAsk"
    assert cmd[cmd.index("--output-format") + 1] == "stream-json"
    assert "ENABLE_PROMPT_CACHING_1H" not in env
    assert env["CLAUDE_CODE_PROMPT_CACHE_TTL"] == "5m"
    assert "cd, awk, xargs" in text


def test_record_then_replay_returns_the_same_answers_without_a_process(tmp_path, monkeypatch):
    cas = tmp_path / "cas"
    monkeypatch.setenv("REVIEW_POOL_CASSETTE", f"record:{cas}")
    seen = []
    run_args = dict(model="opus", effort="xhigh", schema={"type": "object"}, check=lambda r, t: [], cwd=str(tmp_path / "co"))
    out = pool.run([{"id": "U1", "prompt": f"judge code at {tmp_path / 'co'}"}], out_dir=str(tmp_path / "run1" / "judge"),
                   runner=fake([{"x": 1}], seen), **run_args)
    assert out["U1"]["ok"] and (cas / "judge" / "U1.opus.try1.json").exists()
    monkeypatch.setenv("REVIEW_POOL_CASSETTE", f"replay:{cas}")
    # A different run directory and checkout path replays the same cassette.
    run_args["cwd"] = str(tmp_path / "other")
    out2 = pool.run([{"id": "U1", "prompt": f"judge code at {tmp_path / 'other'}"}], out_dir=str(tmp_path / "run2" / "judge"),
                    runner=lambda *a: pytest.fail("replay must not start a process"), **run_args)
    assert out2["U1"]["result"] == {"x": 1}


def test_replay_fails_when_the_prompt_changed(tmp_path, monkeypatch):
    cas = tmp_path / "cas"
    monkeypatch.setenv("REVIEW_POOL_CASSETTE", f"record:{cas}")
    args = dict(model="opus", effort="xhigh", schema={"type": "object"}, check=lambda r, t: [], cwd=str(tmp_path), out_dir=str(tmp_path / "judge"))
    pool.run([{"id": "U1", "prompt": "old prompt"}], runner=fake([{"x": 1}], []), **args)
    monkeypatch.setenv("REVIEW_POOL_CASSETTE", f"replay:{cas}")
    with pytest.raises(SystemExit, match="prompt changed"):
        pool.run([{"id": "U1", "prompt": "new prompt"}], runner=fake([], []), **args)
    with pytest.raises(SystemExit, match="no recording"):
        pool.run([{"id": "U2", "prompt": "old prompt"}], runner=fake([], []), **args)


def test_recording_keeps_only_the_init_fields_the_pool_checks(tmp_path, monkeypatch):
    cas = tmp_path / "cas"
    monkeypatch.setenv("REVIEW_POOL_CASSETTE", f"record:{cas}")
    local = dict(INIT, cwd="/home/someone/run/checkout", session_id="s-1", model="opus",
                 plugins=[{"name": "private-plugin", "path": "/home/someone/.claude/plugins/private-plugin"}])
    pool.run([{"id": "U1", "prompt": "judge this"}], model="opus", effort="xhigh", schema={"type": "object"},
             check=lambda r, t: [], out_dir=str(tmp_path / "judge"), cwd=str(tmp_path), runner=fake([[local, result({"x": 1})]], []))
    saved = (cas / "judge" / "U1.opus.try1.json").read_text()
    assert "/home/someone" not in saved and "private-plugin" not in saved and "s-1" not in saved
    monkeypatch.setenv("REVIEW_POOL_CASSETTE", f"replay:{cas}")
    out = pool.run([{"id": "U1", "prompt": "judge this"}], model="opus", effort="xhigh", schema={"type": "object"},
                   check=lambda r, t: [], out_dir=str(tmp_path / "judge"), cwd=str(tmp_path), runner=fake([], []))
    assert out["U1"]["ok"] and out["U1"]["result"] == {"x": 1}
