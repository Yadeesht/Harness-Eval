"""Runner: tasks x models x harnesses x runs, one JSONL record per run (AGENTS.md "Per-run record").

    .venv/Scripts/python.exe eval/harness/runner.py --tasks cal_02 --harnesses graph hermes \
        --models gpt-4.1-mini --runs 1 --out eval/runs/phase3

Every run gets fresh processes: the fake MCP server (task seed + tool-call cap), the LLM relay
(the only process holding the Azure key) and the harness adapter (from config.json: python +
script). The runner never looks inside a harness: it starts the adapter with the same
arguments for every harness, then grades the server's final state and builds the record from
the server's tool log, the relay's model-call log and the adapter's output file.

More than 4 runs need --yes (AGENTS.md: ask before any matrix run).
"""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import (  # noqa: E402
    EVAL,
    ROOT,
    free_port,
    frozen_now,
    load_config,
    load_json,
    model_settings,
    read_task,
    sanitized_env,
    settings_hash,
    sha256_file,
    shared_settings,
    write_json,
)

sys.path.insert(0, str(EVAL))
from grade.diff import diff  # noqa: E402
from grade.grader import grade  # noqa: E402
from grade.judge import judge, judge_key  # noqa: E402

PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
SERVER = EVAL / "lab" / "server.py"
RELAY = HERE / "llm_relay.py"
SEED_INDEX = EVAL / "seed" / "seed_index.json"
MAX_RUNS_WITHOUT_YES = 4


# ---------------------------------------------------------------------------
# processes
# ---------------------------------------------------------------------------


def _wait_port(port: int, proc: subprocess.Popen, what: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"{what} exited early (code {proc.returncode})")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.3)
    raise RuntimeError(f"{what} did not open port {port} within {timeout:.0f}s")


def _start(cmd: list[str], log: Path, env: dict | None = None, cwd: Path | None = None) -> subprocess.Popen:
    handle = log.open("w", encoding="utf-8")
    return subprocess.Popen(cmd, stdout=handle, stderr=subprocess.STDOUT, env=env, cwd=cwd)


def _stop(proc: subprocess.Popen | None) -> None:
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _git(args: list[str], cwd: Path) -> str:
    try:
        # strip newlines only: `git status --porcelain` lines start with a meaningful space
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30).stdout.strip("\n")
    except (OSError, subprocess.SubprocessError):
        return ""


def versions(config: dict) -> dict:
    hermes_dir = ROOT / config["harnesses"]["hermes"]["checkout"]
    return {
        "repo_commit": _git(["rev-parse", "HEAD"], ROOT),
        "repo_dirty": sorted(l[3:] for l in _git(["status", "--porcelain"], ROOT).splitlines() if l.strip()),
        "hermes_commit": _git(["rev-parse", "HEAD"], hermes_dir),
        "hermes_dirty": sorted(l[3:] for l in _git(["status", "--porcelain"], hermes_dir).splitlines() if l.strip()),
        "seed_sha256": sha256_file(EVAL / "seed" / "seed.json")[:16],
    }


# ---------------------------------------------------------------------------
# measurement
# ---------------------------------------------------------------------------


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


MODEL_CALL_SUFFIXES = ("/chat/completions", "/responses", "/completions")


def _is_model_call(c: dict) -> bool:
    return c.get("method") == "POST" and c.get("path", "").endswith(MODEL_CALL_SUFFIXES)


def llm_metrics(calls: list[dict], model_cfg: dict) -> dict:
    """Tokens, cost, latency and step count from the relay log (identical method for every harness).
    Other requests (Hermes' model-metadata lookups, endpoint probes) are listed, not counted."""
    chat = [c for c in calls if _is_model_call(c)]
    ok = [c for c in chat if (c.get("status") or 0) < 400 and c.get("usage")]
    tokens = {k: sum(c["usage"].get(k) or 0 for c in ok) for k in ("prompt", "completion", "cached", "cache_write", "reasoning")}
    prices = model_cfg.get("prices_usd_per_mtok")
    cost = None
    if prices:
        cost = ((tokens["prompt"] - tokens["cached"]) * prices["input"] + tokens["cached"] * prices["cached_input"]
                + tokens["completion"] * prices["output"]) / 1e6
    return {
        "input_tokens": tokens["prompt"],
        "output_tokens": tokens["completion"],
        "cache_read_tokens": tokens["cached"],
        "cache_write_tokens": tokens["cache_write"],
        "reasoning_tokens": tokens["reasoning"],
        "cost_usd": round(cost, 6) if cost is not None else None,
        "llm_latency_s": round(sum(c.get("latency_s") or 0 for c in chat), 3),
        "n_steps": len(ok),
        "n_llm_requests": len(chat),
        "served_models": sorted({c["served_model"] for c in ok if c.get("served_model")}),
        "other_requests": [f"{c.get('method')} {c.get('path')} -> {c.get('status')}" for c in calls if c not in chat],
    }


def audit(calls: list[dict], config: dict, model: str) -> dict:
    """Do the wire parameters match the shared config? Every mismatch is a fairness warning.

    The model's API decides where reasoning lives: chat completions takes a top-level
    reasoning_effort (an OpenRouter-style `reasoning` field is wrong there); the Responses API
    takes reasoning.effort (a top-level reasoning_effort is wrong there)."""
    model_cfg = config["models"][model]
    api = config["endpoint"]["api_path"]
    kind = model_cfg.get("api", "chat_completions")
    suffix = "/responses" if kind == "responses" else "/chat/completions"
    want_effort = model_cfg.get("reasoning_effort")
    warnings, seen = [], {}
    for c in calls:
        path = c.get("path", "")
        if not _is_model_call(c):
            continue  # metadata requests: listed in other_requests
        if not path.startswith(api) or not path.endswith(suffix):
            warnings.append(f"#{c['n']} model call to {path} (expected {api}{suffix})")
            continue
        params = c.get("params") or {}
        for key in ("model", "temperature", "reasoning_effort", "reasoning", "max_tokens", "max_completion_tokens", "max_output_tokens",
                    "parallel_tool_calls", "tool_choice", "stream", "store", "top_p", "seed"):
            if key in params:
                seen.setdefault(key, set()).add(json.dumps(params[key], sort_keys=True))
        if params.get("model") != model_cfg["deployment"]:
            warnings.append(f"#{c['n']} model {params.get('model')!r} != deployment {model_cfg['deployment']!r}")
        want_temp = model_cfg.get("temperature")
        if want_temp is None and "temperature" in params:
            warnings.append(f"#{c['n']} sent temperature={params['temperature']!r} but config says none")
        elif want_temp is not None and params.get("temperature") != want_temp:
            warnings.append(f"#{c['n']} temperature={params.get('temperature')!r} != config {want_temp!r}")
        if kind == "responses":
            got = (params.get("reasoning") or {}).get("effort") if isinstance(params.get("reasoning"), dict) else None
            if "reasoning_effort" in params:
                warnings.append(f"#{c['n']} sent top-level reasoning_effort on the Responses API")
        else:
            got = params.get("reasoning_effort")
            if "reasoning" in params:
                warnings.append(f"#{c['n']} sent an OpenRouter-style 'reasoning' field")
        if got != want_effort:
            warnings.append(f"#{c['n']} reasoning effort {got!r} != config {want_effort!r}")
    return {"ok": not warnings, "warnings": warnings[:20], "wire_params": {k: sorted(v) for k, v in seen.items()}}


# ---------------------------------------------------------------------------
# LLM judge (ambiguous / impossible tasks, only when every code check passed)
# ---------------------------------------------------------------------------


class Judge:
    """The LLM judge behind its own relay (started on first use, one per runner invocation).
    Verdicts are cached in the run folder, keyed by rubric, prompt, final message and judge
    settings, so --rebuild never pays twice for the same judgement."""

    def __init__(self, config: dict, out: Path):
        self.config, self.out = config, out
        self.relay: subprocess.Popen | None = None
        self.client = None

    def _client(self):
        if self.client is None:
            from openai import OpenAI

            port = free_port()
            self.relay = _start([PY, str(RELAY), "--port", str(port), "--out", str(self.out / "judge_llm"), "--save-bodies"], self.out / "judge_relay.log")
            _wait_port(port, self.relay, "judge relay")
            limits = self.config["limits"]
            self.client = OpenAI(base_url=f"http://127.0.0.1:{port}{self.config['endpoint']['api_path']}", api_key="eval-relay",
                                 max_retries=limits["llm_max_retries"], timeout=limits["llm_timeout_s"])
        return self.client

    def verdict(self, run_dir: Path, task: dict, final_message: str) -> dict:
        settings = self.config["judge"]
        rubric = task["expect"]["judge"]
        key = judge_key(rubric, task["prompt"], final_message, {k: settings.get(k) for k in ("deployment", "reasoning_effort")})
        cache = run_dir / "judge.json"
        if cache.exists():
            cached = load_json(cache)
            if cached.get("key") == key:
                return cached
        try:
            result = judge(self._client(), settings, rubric, task["prompt"], final_message)
        except Exception as error:  # a judge failure leaves the run undecided, never passed
            result = {"verdict": "ERROR", "reason": f"{type(error).__name__}: {error}"[:300]}
        result["key"] = key
        write_json(cache, result)
        return result

    def stop(self) -> None:
        _stop(self.relay)


# ---------------------------------------------------------------------------
# one run
# ---------------------------------------------------------------------------


def run_dir_of(out: Path, task_id: str, harness: str, model: str, run_no: int) -> Path:
    return out / task_id / harness / model / f"run{run_no}"


def execute_run(config: dict, task_id: str, harness: str, model: str, run_no: int, out: Path) -> Path:
    """Start server, relay and adapter for one run; everything lands in the run folder."""
    limits = config["limits"]
    run_id = f"{task_id}-{harness}-{model}-r{run_no}"
    run_dir = run_dir_of(out, task_id, harness, model, run_no)
    shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)
    py = PY
    h = config["harnesses"][harness]
    server_port, relay_port = free_port(), free_port()
    server = relay = None
    runner_errors: list[str] = []
    try:
        quiet_env = sanitized_env({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
        server = _start([py, str(SERVER), "--out", str(run_dir / "server"), "--task", task_id, "--cap", str(limits["tool_call_cap"]), "--port", str(server_port)], run_dir / "server.log", env=quiet_env)
        relay_cmd = [py, str(RELAY), "--port", str(relay_port), "--out", str(run_dir / "llm")]
        if config["relay"].get("save_bodies"):
            relay_cmd.append("--save-bodies")
        relay = _start(relay_cmd, run_dir / "relay.log")
        _wait_port(server_port, server, "MCP server")
        _wait_port(relay_port, relay, "LLM relay")
        adapter_cmd = [
            str(ROOT / h["python"]), str(ROOT / h["adapter"]),
            "--task", task_id, "--model", model, "--run-id", run_id,
            "--mcp-url", f"http://127.0.0.1:{server_port}/mcp",
            "--llm-url", f"http://127.0.0.1:{relay_port}{config['endpoint']['api_path']}",
            "--out", str(run_dir / "adapter.json"),
        ]
        adapter = _start(adapter_cmd, run_dir / "adapter.log", env=quiet_env, cwd=run_dir)
        try:
            adapter.wait(timeout=limits["run_timeout_s"])
        except subprocess.TimeoutExpired:
            adapter.kill()
            runner_errors.append(f"run timeout after {limits['run_timeout_s']}s")
    except RuntimeError as error:
        runner_errors.append(str(error))
    finally:
        _stop(relay)
        _stop(server)
    write_json(run_dir / "runner_errors.json", runner_errors)
    bodies = run_dir / "llm" / "bodies"
    if bodies.exists():  # keep run folders small: full request/response bodies go into one zip
        with zipfile.ZipFile(run_dir / "llm" / "bodies.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(bodies.iterdir()):
                z.write(f, f.name)
        shutil.rmtree(bodies)
    return run_dir


def build_record(config: dict, task_id: str, harness: str, model: str, run_no: int, run_dir: Path, index: dict, vers: dict, judge_service: "Judge") -> dict:
    """Grade one finished run folder and assemble its record (safe to repeat: no harness model calls;
    the judge is only called for a judgement not already cached in the run folder)."""
    task = read_task(task_id)
    model_cfg = model_settings(config, model)
    runner_errors = list(load_json(run_dir / "runner_errors.json")) if (run_dir / "runner_errors.json").exists() else []
    result = load_json(run_dir / "adapter.json") if (run_dir / "adapter.json").exists() else {"errors": ["adapter wrote no output"], "final_message": "", "stop_reason": "adapter_error"}
    tool_calls = _jsonl(run_dir / "server" / "calls.jsonl")
    llm_calls = _jsonl(run_dir / "llm" / "llm_calls.jsonl")
    initial_path, final_path = run_dir / "server" / "state_initial.json", run_dir / "server" / "state.json"
    if initial_path.exists() and final_path.exists():
        initial, final = load_json(initial_path), load_json(final_path)
        graded = grade(task, initial, final, tool_calls, result.get("final_message", ""), index)
        changes = [{k: v for k, v in c.items() if k not in ("before",)} for c in diff(initial, final)]
    else:
        graded, changes = {"passed": False, "failed_checks": ["no server state"], "judge_pending": False}, []
        runner_errors.append("server state missing")

    metrics = llm_metrics(llm_calls, model_cfg)
    fairness = audit(llm_calls, config, model)
    reported_calls = result.get("harness_llm_calls")
    if reported_calls is not None and reported_calls != metrics["n_steps"]:
        fairness["warnings"].append(f"harness reports {reported_calls} model calls, relay saw {metrics['n_steps']} successful ones")
        fairness["ok"] = False
    relay_errors = [f"model call #{c['n']} -> HTTP {c.get('status')}: {(c.get('error') or '')[:200]}" for c in llm_calls if _is_model_call(c) and (c.get("status") or 0) >= 400]
    transcript = result.get("transcript", [])
    capped = [c for c in tool_calls if c.get("capped")]
    passed: bool | None = bool(graded["passed"])
    failed_checks = list(graded["failed_checks"])
    judged = None
    if graded.get("judge_pending"):  # code checks passed; the judge decides
        judged = judge_service.verdict(run_dir, task, result.get("final_message", ""))
        passed = {"PASS": True, "FAIL": False}.get(judged["verdict"])  # ERROR / UNPARSEABLE: undecided
        if judged["verdict"] != "PASS":
            failed_checks.append(f"[judge] {judged['verdict']}: {judged.get('reason', '')}")
    record = {
        "task_id": task_id,
        "split": task["split"],
        "difficulty": task["difficulty"],
        "category": task["category"],
        "harness": harness,
        "model": model,
        "run": run_no,
        "settings_hash": settings_hash(config, model),
        "passed": passed,
        "failed_checks": failed_checks,
        "judge": {k: judged.get(k) for k in ("verdict", "reason", "model", "key")} if judged else None,
        "final_message": result.get("final_message", ""),
        "stop_reason": result.get("stop_reason"),
        **{k: metrics[k] for k in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "reasoning_tokens", "cost_usd", "llm_latency_s", "n_steps")},
        "wall_s": result.get("wall_s"),
        "n_tool_calls": len(tool_calls),
        "n_model_tool_calls": sum(len(m.get("tool_calls") or []) for m in transcript if m.get("role") == "assistant"),
        "errors": (result.get("errors") or []) + relay_errors + runner_errors + ([f"tool-call cap hit: {len(capped)} call(s) refused"] if capped else []),
        "failure_category": None,
        "trajectory": {
            "messages": transcript,
            "tool_calls": [{k: c.get(k) for k in ("n", "tool", "args", "result", "error", "rejected", "capped", "ms")} for c in tool_calls],
            "llm_calls": llm_calls,
        },
        "final_state": {"changes": changes, "state_file": _rel(final_path) if final_path.exists() else None},
        "fairness": fairness,
        "harness_reported": {"llm_calls": reported_calls, "usage": result.get("harness_usage")},
        "isolation": result.get("isolation"),
        "exposed_tools": result.get("exposed_tools"),
        "n_llm_requests": metrics["n_llm_requests"],
        "served_models": metrics["served_models"],
        "other_requests": metrics["other_requests"],
        "shared_settings": shared_settings(config, model),
        "versions": vers,
        "frozen_now": frozen_now(),
        "started_at": result.get("started_at"),
        "run_dir": _rel(run_dir),
    }
    write_json(run_dir / "record.json", record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tasks", nargs="+", required=True)
    parser.add_argument("--harnesses", nargs="+", default=["graph", "hermes"])
    parser.add_argument("--models", nargs="+", default=["gpt-4.1-mini"])
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--out", required=True, help="folder for records.jsonl and the run folders")
    parser.add_argument("--yes", action="store_true", help=f"confirm a batch of more than {MAX_RUNS_WITHOUT_YES} runs")
    parser.add_argument("--rebuild", action="store_true", help="re-grade the existing run folders (no model calls)")
    args = parser.parse_args()

    config = load_config()
    for model in args.models:
        model_settings(config, model)  # fail before starting anything
    plan = [(t, r, m, h) for t in args.tasks for r in range(1, args.runs + 1) for m in args.models for h in args.harnesses]
    print(f"{len(plan)} run(s): {len(args.tasks)} task(s) x {args.runs} run(s) x {len(args.models)} model(s) x {len(args.harnesses)} harness(es)")
    if len(plan) > MAX_RUNS_WITHOUT_YES and not args.yes and not args.rebuild:
        print(f"More than {MAX_RUNS_WITHOUT_YES} LLM runs: re-run with --yes to confirm.")
        return 2

    vers = versions(config)
    if vers["hermes_commit"] != config["harnesses"]["hermes"]["commit"] and "hermes" in args.harnesses:
        print(f"FAIRNESS: Hermes checkout is {vers['hermes_commit'][:10]}, config pins {config['harnesses']['hermes']['commit'][:10]}")
        return 2

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    index = load_json(SEED_INDEX)
    records_path = out / "records.jsonl"
    judge_service = Judge(config, out)
    if args.rebuild:  # re-grade existing run folders into a fresh records.jsonl, no model calls
        records_path.unlink(missing_ok=True)
    for task_id, run_no, model, harness in plan:
        started = datetime.now()
        if args.rebuild:
            run_dir = run_dir_of(out, task_id, harness, model, run_no)
            if not (run_dir / "adapter.json").exists():
                print(f"{task_id} {harness} {model} r{run_no}: no run folder, skipped")
                continue
        else:
            run_dir = execute_run(config, task_id, harness, model, run_no, out)
        record = build_record(config, task_id, harness, model, run_no, run_dir, index, vers, judge_service)
        with records_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        verdict = "PASS" if record["passed"] else ("UNDEC" if record["passed"] is None else "FAIL")
        cost = f"${record['cost_usd']:.4f}" if record["cost_usd"] is not None else "$?"
        print(f"{task_id:8s} {harness:7s} {model:14s} r{run_no}  {verdict:5s} steps={record['n_steps']:<3} tools={record['n_tool_calls']:<3} "
              f"tokens={record['input_tokens']}/{record['output_tokens']} {cost} wall={record['wall_s']}s  "
              f"fairness={'ok' if record['fairness']['ok'] else 'WARN'}  ({(datetime.now() - started).seconds}s)")
        for w in record["fairness"]["warnings"][:5]:
            print(f"    fairness: {w}")
        for e in record["errors"][:3]:
            print(f"    error: {e[:200]}")
    print(f"\nrecords: {_rel(records_path)}")
    judge_service.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
