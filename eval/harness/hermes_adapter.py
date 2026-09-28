"""Hermes adapter: one isolated Hermes Agent run (runs in Hermes' own venv, one process per run).

    eval/venvs/hermes/Scripts/python.exe eval/harness/hermes_adapter.py --task cal_02 --model gpt-4.1-mini \
        --run-id cal_02-hermes-1 --mcp-url http://127.0.0.1:P/mcp --llm-url http://127.0.0.1:Q/openai/v1 \
        --out eval/runs/<run>/adapter.json

Hermes as it ships, with every shared setting from eval/harness/config.json passed explicitly:
  - model:     AIAgent against the LLM relay (Azure's v1 API), provider azure-foundry, api_mode from the
               model's `api` (chat_completions, or codex_responses for the Responses API). On chat
               completions, reasoning effort goes through request_overrides (the azure-foundry profile
               never sends reasoning_config); on the Responses API, through reasoning_config.
  - tools:     the workspace MCP server only (enabled_toolsets=["mcp-workspace"]); tool search on
               (Hermes' default)
  - clock:     hermes_time.now frozen to the workspace time; session id minted from it
  - context:   the task's context line as ephemeral_system_prompt
  - isolation: fresh HERMES_HOME inside the run folder; memory, context files, background review,
               checkpoints and trajectory saving off; ~/.hermes checked for writes
  - limits:    max_iterations = limits.max_llm_calls; MCP tool timeout; model request timeout and
               retries written to HERMES_HOME/config.yaml
Any setting this Hermes commit doesn't accept aborts the run (a fairness warning is never ignored).
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import shutil
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import ROOT, frozen_now, load_config, message, model_settings, read_task, write_json  # noqa: E402

TOKEN_KEYS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "reasoning_tokens",
              "prompt_tokens", "completion_tokens", "total_tokens", "estimated_cost_usd", "cost_status", "api_calls")


def _mtimes(root: Path) -> dict:
    if not root.exists():
        return {}
    return {str(p): p.stat().st_mtime for p in root.rglob("*") if p.is_file()}


def _serialize(messages: list) -> list[dict]:
    out = []
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        calls = []
        for c in m.get("tool_calls") or []:
            fn = c.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = fn.get("arguments")
            calls.append({"id": c.get("id"), "name": fn.get("name"), "args": args})
        content = m.get("content")
        if isinstance(content, list):  # multimodal parts: keep the text
            content = "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
        out.append(message(m.get("role", "?"), content or "", agent="hermes" if m.get("role") == "assistant" else None,
                           tool_calls=calls, tool_call_id=m.get("tool_call_id"), name=m.get("name")))
    return out


def run(args) -> dict:
    config = load_config(args.config) if args.config else load_config()
    limits, hermes_cfg = config["limits"], config["harnesses"]["hermes"]
    model_cfg = model_settings(config, args.model)
    task = read_task(args.task)
    zone = ZoneInfo(config["clock"]["timezone"])
    frozen = datetime.fromisoformat(frozen_now()).astimezone(zone)
    hermes_dir = (ROOT / hermes_cfg["checkout"]).resolve()

    # ---- isolation: all before the first Hermes import --------------------------------
    home = Path(args.out).resolve().parent / "hermes_home"
    shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True)
    (home / "config.yaml").write_text(
        "# Written by eval/harness/hermes_adapter.py: shared limits from eval/harness/config.json\n"
        "agent:\n"
        f"  api_max_retries: {limits['llm_max_retries']}\n"
        "providers:\n"
        f"  {hermes_cfg['provider']}:\n"
        f"    request_timeout_seconds: {limits['llm_timeout_s']}\n",
        encoding="utf-8",
    )
    os.environ["HERMES_HOME"] = str(home)
    os.environ["HERMES_TIMEZONE"] = config["clock"]["timezone"]
    default_home = Path.home() / ".hermes"
    before_default = _mtimes(default_home)

    sys.path.insert(0, str(hermes_dir))
    try:
        import hermes_bootstrap  # type: ignore # noqa: F401  (Hermes' required first import)
    except ModuleNotFoundError:
        pass
    import hermes_time  # type: ignore

    hermes_time.now = lambda: frozen

    from tools.mcp_tool_discovery import register_mcp_servers  # type: ignore

    registered = register_mcp_servers({
        "workspace": {"url": args.mcp_url, "timeout": limits["tool_timeout_s"], "tools": {"prompts": False, "resources": False}},
    })

    from run_agent import AIAgent  # type: ignore

    api = model_cfg.get("api", "chat_completions")
    overrides, reasoning_config = {}, None
    if model_cfg.get("temperature") is not None:
        overrides["temperature"] = model_cfg["temperature"]
    if model_cfg.get("reasoning_effort") is not None:
        if api == "responses":  # Hermes' Responses transport sends reasoning_config as reasoning.effort
            reasoning_config = {"enabled": True, "effort": model_cfg["reasoning_effort"]}
        else:  # the azure-foundry chat profile drops reasoning_config: only request_overrides reach the wire
            overrides["reasoning_effort"] = model_cfg["reasoning_effort"]
    # Hermes reads the session start from the id's stamp, in the machine's local zone.
    session_id = frozen.astimezone().strftime("%Y%m%d_%H%M%S") + f"_{args.run_id}"
    wanted = {
        "base_url": args.llm_url,
        "api_key": "eval-relay",
        "provider": hermes_cfg["provider"],
        "api_mode": hermes_cfg["api_modes"][api],
        "model": model_cfg["deployment"],
        "max_iterations": limits["max_llm_calls"],
        "enabled_toolsets": ["mcp-workspace"],
        "save_trajectories": False,
        "quiet_mode": True,
        "skip_context_files": True,
        "skip_memory": True,
        "skip_background_review": True,
        "checkpoints_enabled": False,
        "ephemeral_system_prompt": task["context"],
        "request_overrides": overrides or None,
        "reasoning_config": reasoning_config,
        "session_id": session_id,
        "platform": hermes_cfg["platform"],
    }
    accepted = inspect.signature(AIAgent.__init__).parameters
    dropped = [k for k in wanted if k not in accepted]
    if dropped:
        raise RuntimeError(f"FAIRNESS: this Hermes commit does not accept {dropped}; refusing to run")
    agent = AIAgent(**{k: v for k, v in wanted.items() if v is not None})

    result: dict = {
        "harness": "hermes",
        "model": args.model,
        "run_id": args.run_id,
        "errors": [],
        "exposed_tools": {"hermes": sorted(agent.valid_tool_names or [])},
        "settings_passed": {k: v for k, v in wanted.items() if k not in ("api_key", "ephemeral_system_prompt")},
        "mcp_registered": list(registered or []),
    }
    if args.dry_run:
        result.update(stop_reason="dry_run", final_message="", tool_specs=agent.tools)
        return result

    started = time.perf_counter()
    result["started_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        outcome = agent.run_conversation(task["prompt"], task_id=args.run_id)
    except Exception as error:  # the run ends; the workspace state is graded as it is
        outcome = {}
        result["errors"].append(f"{type(error).__name__}: {error}")
        result["traceback"] = traceback.format_exc()[-4000:]
    result["wall_s"] = round(time.perf_counter() - started, 2)
    result["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")

    api_calls = outcome.get("api_calls") or 0
    if outcome.get("completed"):
        stop = "completed"
    elif api_calls >= limits["max_llm_calls"]:
        stop = "step_limit"
    else:
        stop = "error"
        if outcome.get("error"):
            result["errors"].append(str(outcome.get("error"))[:2000])
    result["stop_reason"] = stop
    result["final_message"] = outcome.get("final_response") or ""
    result["transcript"] = _serialize(outcome.get("messages"))
    result["harness_llm_calls"] = api_calls
    result["harness_usage"] = {k: outcome.get(k) for k in TOKEN_KEYS if k in outcome}
    system_prompt = getattr(agent, "_cached_system_prompt", "") or ""
    real_today = datetime.now(zone).strftime("%B %d, %Y")
    result["system_prompt"] = system_prompt
    result["isolation"] = {
        "hermes_home": str(home),
        "hermes_home_files": sorted(str(p.relative_to(home)) for p in home.rglob("*") if p.is_file()),
        "default_home_writes": sorted(k for k, v in _mtimes(default_home).items() if before_default.get(k) != v),
        "frozen_date_in_prompt": frozen.strftime("%B %d, %Y") in system_prompt,
        "real_date_in_prompt": real_today != frozen.strftime("%B %d, %Y") and real_today in system_prompt,
        "session_id": session_id,
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
        result = run(args)
    except Exception as error:
        result = {"harness": "hermes", "model": args.model, "run_id": args.run_id, "stop_reason": "adapter_error",
                  "errors": [f"{type(error).__name__}: {error}"], "traceback": traceback.format_exc()[-4000:], "final_message": ""}
    write_json(args.out, result)
    try:  # tidy shutdown of Hermes' MCP background loop
        from tools.mcp_tool_lifecycle import shutdown_mcp_servers  # type: ignore

        shutdown_mcp_servers()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
