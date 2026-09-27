"""Validate tasks: golden path PASS, do-nothing FAIL, negative path FAIL (AGENTS.md Phase 2).

    .venv/Scripts/python.exe eval/validate.py            # every task in eval/tasks
    .venv/Scripts/python.exe eval/validate.py cal_02     # selected tasks

Each path runs in-process against a fresh workspace, through the same MCP
layer the harnesses use (FastMCP in-memory transport). Run folders land in
eval/runs/validate/<task>/<path>/. Exits non-zero if any expectation fails.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import shutil
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(EVAL / "seed"))
sys.path.insert(0, str(EVAL / "golden"))

from fastmcp import Client  # noqa: E402
from fastmcp.exceptions import ToolError  # noqa: E402

from grade.grader import grade  # noqa: E402
from lab.bind import bind  # noqa: E402
from lab.server import Recorder, build_server, load_workspace  # noqa: E402

TASKS = EVAL / "tasks"
GOLDEN = EVAL / "golden"
RUNS = EVAL / "runs" / "validate"
INDEX = json.loads((EVAL / "seed" / "seed_index.json").read_text(encoding="utf-8"))
CAP = 60
logging.disable(logging.INFO)


def load_golden(task_id: str):
    path = GOLDEN / f"{task_id}.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"golden_{task_id}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def run_path(task: dict, path_name: str, fn) -> dict:
    out = RUNS / task["id"] / path_name
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    ws = bind(load_workspace(task["id"]))
    initial = json.loads(json.dumps(ws.state))
    recorder = Recorder(ws, out, CAP)
    server = build_server(ws, recorder)
    final_message = ""
    async with Client(server) as client:

        async def call(_tool, **args):
            try:
                result = await client.call_tool(_tool, args)
                return result.content[0].text if result.content else ""
            except ToolError as error:
                return f"ERROR: {error}"

        crash = None
        if fn is not None:
            try:
                final_message = await fn(call) or ""
            except Exception as error:  # a broken script must not count as "the grader failed it"
                crash = f"{path_name} script crashed: {type(error).__name__}: {error}"
    recorder.log.close()
    calls = [json.loads(line) for line in (out / "calls.jsonl").open(encoding="utf-8")]
    result = grade(task, initial, ws.state, calls, final_message, INDEX)
    result["crash"] = crash
    (out / "grade.json").write_text(json.dumps({**result, "final_message": final_message}, indent=1, ensure_ascii=False), encoding="utf-8")
    return result


async def validate(task_id: str) -> list[tuple[str, bool, dict]]:
    task = json.loads((TASKS / f"{task_id}.json").read_text(encoding="utf-8"))
    golden = load_golden(task_id)
    rows = []
    if golden is None or not hasattr(golden, "golden"):
        return [("golden", False, {"failed_checks": ["no golden path"], "n_calls": 0})]
    res = await run_path(task, "golden", golden.golden)
    rows.append(("golden PASS", res["passed"] and not res["crash"], res))
    res = await run_path(task, "nothing", None)
    rows.append(("do-nothing FAIL", not res["passed"], res))
    if hasattr(golden, "negative"):
        res = await run_path(task, "negative", golden.negative)
        rows.append(("negative FAIL", not res["passed"] and not res["crash"], res))
    elif task["patterns"]:
        rows.append(("negative FAIL", False, {"failed_checks": ["task has traps but no negative path"], "n_calls": 0}))
    return rows


def main() -> int:
    ids = sys.argv[1:] or sorted(p.stem for p in TASKS.glob("*.json"))
    bad = 0
    for task_id in ids:
        rows = asyncio.run(validate(task_id))
        for label, ok, res in rows:
            bad += not ok
            detail = res.get("crash") or ("" if ok and label.startswith("golden") else "; ".join(res["failed_checks"][:3]))
            print(f"{task_id:8s} {label:16s} {'ok ' if ok else 'BAD'}  calls={res['n_calls']:<3} {detail}")
    print(f"\n{'all expectations met' if not bad else f'{bad} expectation(s) not met'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
