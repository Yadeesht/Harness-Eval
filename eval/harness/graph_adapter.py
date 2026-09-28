"""Graph adapter: one isolated run of the routed LangGraph harness (runs in the repo .venv).

    .venv/Scripts/python.exe eval/harness/graph_adapter.py --task cal_02 --model gpt-4.1-mini \
        --run-id cal_02-graph-1 --mcp-url http://127.0.0.1:P/mcp --llm-url http://127.0.0.1:Q/openai/v1 \
        --out eval/runs/<run>/adapter.json

The graph is the product's own build_graph, unchanged; only its inputs are swapped:
  - tools:   the MCP server's tools (the names, descriptions and schemas Hermes sees), split into
             the product's communication / planning / content sets by the app_tools registries
  - model:   ChatOpenAI against the LLM relay (Azure's v1 API, like Hermes), settings from
             eval/harness/config.json; chat completions or the Responses API per the model's `api`
  - clock:   get_current_time returns the workspace's frozen time
  - context: the task's context line is appended to every agent's system prompt (supervisor and
             the four workers), after a blank line: the same text Hermes appends to its prompt
  - memory:  a fresh InMemorySaver and a new thread; data/checkpoints.db is never opened, and
             .env is never read (the relay holds the key)
  - steps:   at most limits.max_llm_calls model calls; LangGraph's recursion limit is raised so
             it never binds first
Writes one JSON file: final message, transcript, harness-side usage, errors, isolation facts.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import ROOT, content_text, frozen_now, load_config, message, model_settings, read_task, write_json  # noqa: E402

sys.path.insert(0, str(ROOT))


class StepLimitReached(Exception):
    pass


def _patch_environment(llm_url: str, deployment: str) -> None:
    """Before any product import: never read .env, and give config.settings harmless values."""
    import dotenv

    dotenv.load_dotenv = lambda *args, **kwargs: False
    os.environ["AZURE_AI_ENDPOINT"] = llm_url
    os.environ["AZURE_AI_CREDENTIAL"] = "eval-relay"
    os.environ["MODEL_NAME"] = deployment


def _mcp_tool(client, spec, timeout_s: float):
    """A LangChain tool that forwards to the MCP server. Arguments pass through unchanged, so the
    server's own validation (the same for both harnesses) is the only one."""
    from langchain_core.tools import StructuredTool, ToolException

    async def call(**kwargs):
        result = await client.call_tool(spec.name, kwargs, timeout=timeout_s, raise_on_error=False)
        parts = []
        for block in result.content or []:
            text = getattr(block, "text", None)
            parts.append(text if text is not None else json.dumps(block.model_dump(), ensure_ascii=False, default=str))
        text = "\n".join(parts)
        if result.is_error:
            raise ToolException(text)
        return text

    schema = getattr(spec, "input_schema", None) or {"type": "object", "properties": {}}
    return StructuredTool(name=spec.name, description=spec.description or "", args_schema=schema, coroutine=call)


def _tool_sets(mcp_tools: list) -> dict:
    """Split the MCP tools exactly as main.py splits the in-process ones: by the app_tools registries."""
    import app_tools.tools.google.calendar_tools  # noqa: F401  (importing registers the tools)
    import app_tools.tools.google.gdocs_tools  # noqa: F401
    import app_tools.tools.google.gmail_tools  # noqa: F401
    import app_tools.tools.google.gsheet_tools  # noqa: F401
    import app_tools.tools.google.gtask_tools  # noqa: F401
    from app_tools.core.server_init import communication_server, content_server, planning_server

    groups = {
        "communication": {t.name for t in communication_server.list_tools()},
        "planning": {t.name for t in planning_server.list_tools()},
        "content": {t.name for t in content_server.list_tools()},
    }
    sets = {key: [t for t in mcp_tools if t.name in names] for key, names in groups.items()}
    placed = [t.name for tools in sets.values() for t in tools]
    missing = sorted({t.name for t in mcp_tools} - set(placed))
    if missing or len(placed) != len(set(placed)) or len(placed) != sum(len(n) for n in groups.values()):
        raise SystemExit(f"MCP tools don't match the app_tools registries (unplaced: {missing})")
    return sets


def _serialize(messages: list) -> list[dict]:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    out = []
    for m in messages:
        if isinstance(m, AIMessage):
            out.append(message("assistant", m.content, agent=m.name, tool_calls=m.tool_calls))
        elif isinstance(m, ToolMessage):
            out.append(message("tool", m.content, name=m.name, tool_call_id=m.tool_call_id))
        elif isinstance(m, HumanMessage):
            out.append(message("user", m.content, name=m.name))
        elif isinstance(m, SystemMessage):
            out.append(message("system", m.content))
    return out


def _final_message(state: dict) -> str:
    """What main.py shows the user: the active agent's last message, if it is an AI message
    (its text blocks, when the Responses API returns content as a list)."""
    from langchain_core.messages import AIMessage

    from core.agent import AGENT_MESSAGE_KEY

    active = state.get("current_agent") or "supervisor"
    messages = state.get(AGENT_MESSAGE_KEY.get(active, "supervisor_messages")) or state.get("messages", [])
    last = messages[-1] if messages else None
    return content_text(last.content)[0] if isinstance(last, AIMessage) else ""


async def run(args) -> dict:
    config = load_config(args.config) if args.config else load_config()
    limits = config["limits"]
    model_cfg = model_settings(config, args.model)
    task = read_task(args.task)
    frozen = datetime.fromisoformat(frozen_now())
    _patch_environment(args.llm_url, model_cfg["deployment"])

    from fastmcp import Client
    from langchain_core.callbacks import BaseCallbackHandler, UsageMetadataCallbackHandler
    from langchain_core.messages import HumanMessage
    from langchain_openai import ChatOpenAI
    from langgraph.checkpoint.memory import InMemorySaver

    import core.agent
    import core.graph
    import core.llm
    import utils.helper
    from config.settings import CHECKPOINT_DB

    # Clock: the product formats "now" with get_current_time(); freeze it to the workspace time.
    frozen_text = frozen.strftime("%Y-%m-%d %H:%M:%S IST")
    utils.helper.get_current_time = core.agent.get_current_time = lambda: frozen_text

    # Context: appended to every agent's system prompt, the way Hermes appends ephemeral_system_prompt.
    prompt_names = ["SUPERVISOR_SYSTEM_PROMPT", "COMMUNICATION_SYSTEM_PROMPT", "PLANNING_SYSTEM_PROMPT", "DOCUMENT_SYSTEM_PROMPT", "DATA_SYSTEM_PROMPT"]
    for name in prompt_names:
        setattr(core.graph, name, getattr(core.graph, name) + "\n\n" + task["context"])

    # Model: one client factory for every node (supervisor, workers, summarizer), with a step limit.
    class StepCounter(BaseCallbackHandler):
        raise_error = True

        def __init__(self, limit: int):
            self.limit, self.calls = limit, 0

        def on_chat_model_start(self, serialized, messages, **kwargs):
            self.calls += 1
            if self.calls > self.limit:
                raise StepLimitReached(f"step limit reached: {self.limit} model calls")

    steps = StepCounter(limits["max_llm_calls"])
    usage = UsageMetadataCallbackHandler()

    def build_llm(model=None):
        kwargs = {
            "model": model_cfg["deployment"],
            "base_url": args.llm_url,
            "api_key": "eval-relay",
            "max_retries": limits["llm_max_retries"],
            "timeout": limits["llm_timeout_s"],
            "use_responses_api": model_cfg.get("api") == "responses",
            "callbacks": [steps, usage],
        }
        if model_cfg.get("temperature") is not None:
            kwargs["temperature"] = model_cfg["temperature"]
        if model_cfg.get("reasoning_effort") is not None:
            if kwargs["use_responses_api"]:
                kwargs["reasoning"] = {"effort": model_cfg["reasoning_effort"]}  # Responses: reasoning.effort
            else:
                kwargs["reasoning_effort"] = model_cfg["reasoning_effort"]  # chat completions: top level
        return ChatOpenAI(**kwargs)

    core.llm._build_llm = build_llm

    db_before = CHECKPOINT_DB.stat().st_mtime if CHECKPOINT_DB.exists() else None
    result: dict = {"harness": "graph", "model": args.model, "run_id": args.run_id, "errors": []}

    async with Client(args.mcp_url) as client:
        mcp_tools = [_mcp_tool(client, spec, limits["tool_timeout_s"]) for spec in await client.list_tools()]
        tool_sets = _tool_sets(mcp_tools)
        graph = core.graph.build_graph(tool_sets, InMemorySaver())
        documents, data = core.graph.split_content_tools(tool_sets["content"])
        result["exposed_tools"] = {
            "communication_agent": sorted(t.name for t in tool_sets["communication"]),
            "planning_agent": sorted(t.name for t in tool_sets["planning"]),
            "document_agent": sorted(t.name for t in documents),
            "data_agent": sorted(t.name for t in data),
        }
        run_config = {"configurable": {"thread_id": f"eval-{args.run_id}"}, "recursion_limit": 3 * limits["max_llm_calls"] + 10}
        if args.dry_run:  # everything built, no model call: report what the model would be given
            from langchain_core.utils.function_calling import convert_to_openai_tool

            specs = [convert_to_openai_tool(t) for tools in tool_sets.values() for t in tools]
            result.update(stop_reason="dry_run", final_message="", tool_specs=specs,
                          system_prompts={n: getattr(core.graph, n).replace("{current_time}", frozen_text) for n in prompt_names})
            return result
        prompt = HumanMessage(content=task["prompt"])
        state: dict = {}
        stop = "completed"
        started = time.perf_counter()  # wall_s: prompt submitted -> final answer (same span as Hermes)
        result["started_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            state = await graph.ainvoke({"messages": [prompt], "supervisor_messages": [prompt]}, config=run_config)
        except StepLimitReached as error:
            stop = "step_limit"
            result["errors"].append(str(error))
        except Exception as error:  # the run ends; the workspace state is graded as it is
            stop = "error"
            result["errors"].append(f"{type(error).__name__}: {error}")
            result["traceback"] = traceback.format_exc()[-4000:]
        if not state:
            try:
                snapshot = await graph.aget_state(run_config)
                state = dict(snapshot.values) if snapshot and snapshot.values else {}
            except Exception as error:  # the checkpoint itself can hold the failed step's writes
                result["errors"].append(f"state after the error unavailable: {type(error).__name__}")
        if stop == "completed" and steps.calls > limits["max_llm_calls"]:
            stop = "step_limit"  # the supervisor turns exceptions into an [ERROR] reply instead of raising
        result["wall_s"] = round(time.perf_counter() - started, 2)

    result["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    result["stop_reason"] = stop
    result["final_message"] = _final_message(state) if state else ""
    result["transcript"] = _serialize(state.get("messages", [])) if state else []
    result["channels"] = {key: _serialize(state.get(key, [])) for key in ("supervisor_messages", "communication_messages", "planning_messages", "document_messages", "data_messages")} if state else {}
    result["harness_llm_calls"] = steps.calls
    result["harness_usage"] = {k: dict(v) for k, v in usage.usage_metadata.items()}
    db_after = CHECKPOINT_DB.stat().st_mtime if CHECKPOINT_DB.exists() else None
    result["isolation"] = {
        "checkpointer": "InMemorySaver",
        "thread_id": run_config["configurable"]["thread_id"],
        "sqlite_checkpoint_untouched": db_before == db_after,
        "dotenv_read": False,
        "frozen_time_in_prompts": frozen_text,
        "context_appended_to": prompt_names,
        "recursion_limit": run_config["recursion_limit"],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--task", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mcp-url", required=True)
    parser.add_argument("--llm-url", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", default=None)
    parser.add_argument("--dry-run", action="store_true", help="build everything, make no model call")
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args))
    except SystemExit:
        raise
    except Exception as error:
        result = {"harness": "graph", "model": args.model, "run_id": args.run_id, "stop_reason": "adapter_error",
                  "errors": [f"{type(error).__name__}: {error}"], "traceback": traceback.format_exc()[-4000:], "final_message": ""}
    write_json(args.out, result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
