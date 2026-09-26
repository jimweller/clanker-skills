"""Run many model calls as isolated `claude -p` processes, with a content check and retry.

    pool.run(tasks, model=, effort=, schema=, check=, out_dir=, cwd=)

Each task is {"id", "prompt"}. Every call is its own process:

    claude -p --bare --model M --effort E --tools Bash,Read --permission-mode dontAsk
           --disable-slash-commands --json-schema S --output-format stream-json --verbose

and the prompt arrives on stdin. The settings come from measured failures:
- --bare keeps the operator's CLAUDE.md, skills, plugins, MCP servers, and hooks out of the judge.
  Workflow subagents received all of them, a hook denied their reads, and the CLAUDE.md prose
  rules rewrote punctuation inside quoted code.
- --bare has no Grep or Glob tool, and asking for them yields Read only. Search runs through Bash
  with the embedded grep and find. dontAsk runs read-only commands and denies the rest, so a
  judge cannot write. SHELL_NOTE names the constructs that were denied in practice.
- A top-level `claude -p` session caches for 1 hour when ENABLE_PROMPT_CACHING_1H is set, at
  twice the input price. Removing it and setting CLAUDE_CODE_PROMPT_CACHE_TTL=5m moves every
  cache write to the 5-minute rate.
- The init event must list exactly Bash, Read, and StructuredOutput in dontAsk mode. Any other
  tool set aborts the pool, because every answer after it would come from a different judge.
- A JSON schema checks shape, not truth. Models submit placeholders such as reason "test" after
  schema rejections, so check(result, task) returns content errors, and a rejected answer is
  retried with the errors appended, up to ATTEMPTS times.

Returns {id: {"ok", "attempts", "result", "rejections", "calls"}}. "result" holds the accepted
answer, or the last answer when every attempt was rejected. Raw event streams are kept under
out_dir/calls/, and out_dir/pool.log records every call.

REVIEW_POOL_CASSETTE=record:DIR saves every call's events under DIR/<stage>/<task>.<model>.try<n>.json,
where <stage> is the basename of out_dir, with a hash of the prompt. REVIEW_POOL_CASSETTE=replay:DIR
returns those events without starting a process, and stops when a recording is missing or its
prompt hash differs, so a changed prompt forces a new recording. The hash ignores the checkout
path, so a recording replays from any run directory.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

ATTEMPTS = 3
STALL_S = 600
TIMEOUT_S = 2400
TOOLS = ["Bash", "Read", "StructuredOutput"]
SHELL_NOTE = ("\n\nSearch and read with grep, sed -n, cat, head, tail, ls, and find, using paths relative "
              "to the working directory. cd, awk, xargs, cut, node, shell variable assignments, and $(...) are "
              "denied in this environment, so do not use them.")


def env():
    e = {k: v for k, v in os.environ.items() if k != "ENABLE_PROMPT_CACHING_1H"}
    e["CLAUDE_CODE_PROMPT_CACHE_TTL"] = "5m"
    return e


def command(model, effort, schema, add_dirs=()):
    cmd = ["claude", "-p", "--bare", "--model", model, "--effort", effort, "--tools", "Bash,Read",
           "--permission-mode", "dontAsk", "--disable-slash-commands", "--json-schema", json.dumps(schema),
           "--output-format", "stream-json", "--verbose"]
    for d in add_dirs:
        cmd += ["--add-dir", d]
    return cmd


def process_runner(cmd, text, cwd, environ, base):
    """Run one claude -p process, stream its events to base.ndjson, kill it on a stall."""
    last = {"t": time.time()}
    events = []
    p = subprocess.Popen(cmd, cwd=cwd, env=environ, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=open(f"{base}.err", "w"), text=True)

    def feed():
        p.stdin.write(text)
        p.stdin.close()

    def read():
        with open(f"{base}.ndjson", "w") as f:
            for line in p.stdout:
                f.write(line)
                last["t"] = time.time()
                if line.lstrip().startswith("{"):
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    threads = [threading.Thread(target=feed, daemon=True), threading.Thread(target=read, daemon=True)]
    for t in threads:
        t.start()
    t0 = time.time()
    while p.poll() is None:
        if time.time() - last["t"] > STALL_S or time.time() - t0 > TIMEOUT_S:
            p.kill()
            events.append({"type": "killed", "after_s": round(time.time() - t0)})
            break
        time.sleep(2)
    p.wait()
    threads[1].join(timeout=30)
    return events


INIT_KEEP = ("type", "subtype", "tools", "permissionMode", "model", "claude_code_version")


def scrub(event):
    """Drop what a recording must not carry into a shared repository: the local paths, plugins, and session ids."""
    if event.get("type") == "system" and event.get("subtype") == "init":
        return {k: event[k] for k in INIT_KEEP if k in event}
    return {k: v for k, v in event.items() if k != "session_id"}


def cassette(runner, spec, out_dir, cwd):
    mode, _, root = spec.partition(":")
    if mode not in ("record", "replay") or not root:
        sys.exit(f"REVIEW_POOL_CASSETTE must be record:DIR or replay:DIR, got {spec!r}")
    stage = os.path.basename(os.path.normpath(out_dir))

    def wrapped(cmd, text, cwd_, environ, base):
        path = os.path.join(root, stage, os.path.basename(base) + ".json")
        sha = hashlib.sha256(text.replace(cwd, "<CWD>").encode()).hexdigest()
        if mode == "replay":
            if not os.path.exists(path):
                sys.exit(f"no recording at {path}")
            saved = json.load(open(path))
            if saved["prompt_sha"] != sha:
                sys.exit(f"prompt changed since {path} was recorded; record again")
            return saved["events"]
        events = runner(cmd, text, cwd_, environ, base)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump({"prompt_sha": sha, "events": [scrub(e) for e in events]}, open(path, "w"))
        return events
    return wrapped


def run(tasks, *, model, effort, schema, check, out_dir, cwd, concurrency=50, add_dirs=(), runner=None):
    runner = runner or process_runner
    if os.environ.get("REVIEW_POOL_CASSETTE"):
        runner = cassette(runner, os.environ["REVIEW_POOL_CASSETTE"], out_dir, cwd)
    os.makedirs(f"{out_dir}/calls", exist_ok=True)
    lock = threading.Lock()
    environ = env()
    cmd = command(model, effort, schema, add_dirs)

    def log(msg):
        with lock, open(f"{out_dir}/pool.log", "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")

    def one(task):
        tid = re.sub(r"[^A-Za-z0-9._-]", "_", str(task["id"]))
        rejections, calls, last = [], [], None
        for n in range(1, ATTEMPTS + 1):
            note = (f"\n\nA previous answer was rejected for these reasons: {'; '.join(rejections[-1])}. "
                    "Answer again, fixing them.") if rejections else ""
            t0 = time.time()
            events = runner(cmd, task["prompt"] + SHELL_NOTE + note, cwd, environ, f"{out_dir}/calls/{tid}.{model}.try{n}")
            init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), None)
            result = next((e for e in reversed(events) if e.get("type") == "result"), None)
            denials = (result or {}).get("permission_denials") or []
            calls.append({"attempt": n, "seconds": round(time.time() - t0), "cost_usd": (result or {}).get("total_cost_usd"),
                          "usage": (result or {}).get("usage"), "turns": (result or {}).get("num_turns"),
                          "denials": len(denials)})
            log(f"{task['id']} {model} try{n} {calls[-1]['seconds']}s denials={len(denials)}"
                f"{' killed' if any(e.get('type') == 'killed' for e in events) else ''}")
            if init and (sorted(init.get("tools") or []) != TOOLS or init.get("permissionMode") != "dontAsk"):
                log(f"ABORT {task['id']}: tools {init.get('tools')} mode {init.get('permissionMode')}")
                sys.exit(f"pool aborted: judge had tools {init.get('tools')} in mode {init.get('permissionMode')}")
            so = (result or {}).get("structured_output")
            if not init or not result or result.get("is_error") or not so:
                rejections.append([f"no structured output ({(result or {}).get('subtype') or 'no result event'})"])
                continue
            last = so
            errs = check(so, task)
            if not errs:
                return task["id"], {"ok": True, "attempts": n, "result": so, "rejections": rejections, "calls": calls}
            rejections.append(errs)
        return task["id"], {"ok": False, "attempts": ATTEMPTS, "result": last, "rejections": rejections, "calls": calls}

    log(f"start {len(tasks)} tasks, model {model}, effort {effort}, concurrency {concurrency}")
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        out = dict(ex.map(one, tasks))
    log(f"end, ok {sum(o['ok'] for o in out.values())} of {len(out)}")
    return out


def cost(outcomes):
    return round(sum(c.get("cost_usd") or 0 for o in outcomes.values() for c in o["calls"]), 2)
