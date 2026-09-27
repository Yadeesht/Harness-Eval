"""Fake workspace MCP server: the 75 real app_tools tools over an in-memory workspace.

One process per run. It loads the seed (plus the task's seed_additions),
serves the real tool functions under their real names, descriptions and
parameters, and for every call:
  - appends a line to <out>/calls.jsonl (tool, args, result, error, timing)
  - writes the full workspace state to <out>/state.json
  - stops executing tools once the call cap is reached (same cap for every harness)

    .venv/Scripts/python.exe eval/lab/server.py --out eval/runs/<run> [--task cal_02] [--cap 60] [--port 8765]
    .venv/Scripts/python.exe eval/lab/server.py --out ... --transport stdio
"""

from __future__ import annotations

import argparse
import functools
import inspect
import json
import logging
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL = HERE.parent
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(EVAL / "seed"))

from fastmcp import FastMCP  # noqa: E402
from fastmcp.exceptions import NotFoundError, ToolError, ValidationError  # noqa: E402
from fastmcp.server.middleware import Middleware  # noqa: E402
from fastmcp.tools import Tool  # noqa: E402

from lab.bind import all_tools, bind  # noqa: E402
from lab.workspace import Workspace  # noqa: E402

SEED = EVAL / "seed" / "seed.json"
SEED_INDEX = EVAL / "seed" / "seed_index.json"
TASKS = EVAL / "tasks"


def _text(result) -> str:
    """How a tool result reaches the model: strings as-is, dicts as JSON."""
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False, default=str)


class Recorder:
    def __init__(self, ws: Workspace, out: Path, cap: int):
        self.ws = ws
        self.out = out
        self.cap = cap
        self.count = 0
        self.log = open(out / "calls.jsonl", "a", encoding="utf-8")

    def dump_state(self) -> None:
        tmp = self.out / "state.json.tmp"
        tmp.write_text(json.dumps(self.ws.state, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.out / "state.json")

    def write(self, record: dict) -> None:
        self.log.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self.log.flush()

    async def call(self, name: str, fn, kwargs: dict) -> str:
        self.count += 1
        n = self.count
        start = time.perf_counter()
        if n > self.cap:
            text = f"Error: the tool-call limit of {self.cap} calls has been reached. No further tools will run."
            self.write({"n": n, "tool": name, "args": kwargs, "result": text, "error": True, "capped": True, "ms": 0})
            raise ToolError(text)
        try:
            result = await fn(**kwargs)
        except Exception as error:  # the real tools sometimes raise; the model sees the message
            text = f"{type(error).__name__}: {error}"
            self.write({"n": n, "tool": name, "args": kwargs, "result": text, "error": True, "ms": round((time.perf_counter() - start) * 1000)})
            self.dump_state()
            raise ToolError(text)
        text = _text(result)
        self.write({"n": n, "tool": name, "args": kwargs, "result": text, "error": False, "ms": round((time.perf_counter() - start) * 1000)})
        self.dump_state()
        return text

    def reject(self, name: str, args: dict, message: str) -> None:
        """A call the MCP layer refused before the tool ran (bad arguments, unknown tool).
        It is logged and counts toward the cap, like any other call attempt."""
        self.count += 1
        self.write({"n": self.count, "tool": name, "args": args, "result": message, "error": True, "rejected": True, "ms": 0})


class RejectedCalls(Middleware):
    """Logs calls that fail argument validation or name an unknown tool."""

    def __init__(self, recorder: Recorder):
        self.recorder = recorder

    async def on_call_tool(self, context, call_next):
        try:
            return await call_next(context)
        except (ValidationError, NotFoundError) as error:
            params = context.message
            self.recorder.reject(params.name, dict(params.arguments or {}), f"{type(error).__name__}: {error}")
            raise


def build_server(ws: Workspace, recorder: Recorder) -> FastMCP:
    mcp = FastMCP("workspace")
    mcp.add_middleware(RejectedCalls(recorder))
    for lc_tool in all_tools():
        fn = lc_tool.coroutine
        name = lc_tool.name

        def make(fn=fn, name=name):
            sig = inspect.signature(fn)

            @functools.wraps(fn)
            async def wrapper(*args, **kwargs):
                bound = sig.bind(*args, **kwargs)
                return await recorder.call(name, fn, dict(bound.arguments))

            # Same parameters as the real tool; the result always reaches the model as text.
            wrapper.__signature__ = sig.replace(return_annotation=str)
            wrapper.__annotations__ = {**getattr(fn, "__annotations__", {}), "return": str}
            return wrapper

        mcp.add_tool(Tool.from_function(make(), name=name, description=lc_tool.description, output_schema=None))
    return mcp


def load_workspace(task: str | None) -> Workspace:
    """A fresh workspace: the seed, plus the task's seed_additions (from its task file)."""
    ws = Workspace(json.loads(SEED.read_text(encoding="utf-8")), namespace="run")
    if task:
        from build_seed import apply_additions

        spec = json.loads((TASKS / f"{task}.json").read_text(encoding="utf-8"))
        apply_additions(ws, spec.get("seed_additions", {}), json.loads(SEED_INDEX.read_text(encoding="utf-8")))
    return ws


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="run folder for calls.jsonl and state.json")
    parser.add_argument("--task", help="task id, to apply its seed_additions")
    parser.add_argument("--cap", type=int, default=60, help="tool-call cap for the run")
    parser.add_argument("--transport", default="http", choices=["http", "stdio"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    logging.disable(logging.INFO)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ws = bind(load_workspace(args.task))
    (out / "state_initial.json").write_text(json.dumps(ws.state, ensure_ascii=False), encoding="utf-8")
    recorder = Recorder(ws, out, args.cap)
    recorder.dump_state()
    mcp = build_server(ws, recorder)
    if args.transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
    else:
        mcp.run(transport="http", host=args.host, port=args.port, path="/mcp", show_banner=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
