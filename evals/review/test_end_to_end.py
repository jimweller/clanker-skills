"""Replay the recorded model answers through every stage and compare with the golden set.

    cd evals/review && uv run --with pytest pytest -q test_end_to_end.py

No model calls and no cost. A changed prompt fails with "prompt changed" and needs a new recording
(pipeline.py --mode record, then golden.py save). A changed script that alters any output fails the
golden comparison, which is the point: review the difference, then save a new golden set on purpose.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import golden  # noqa: E402
import pipeline  # noqa: E402


def test_replay_reproduces_the_golden_run(tmp_path):
    run = pipeline.run(str(tmp_path / "work"), "replay", pipeline.CASSETTES)
    assert golden.diff(run) == []
