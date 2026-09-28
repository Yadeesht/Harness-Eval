"""Shared helpers for the runner and both adapters.

Standard library only: the Hermes adapter imports this from Hermes' own venv.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "eval"
HARNESS_DIR = EVAL / "harness"
CONFIG_PATH = HARNESS_DIR / "config.json"
TASKS_DIR = EVAL / "tasks"
SEED_PATH = EVAL / "seed" / "seed.json"

# Environment variables a harness process must never see (the relay holds the real key).
SECRET_MARKERS = ("KEY", "SECRET", "TOKEN", "CREDENTIAL", "PASSWORD", "ENDPOINT")


def load_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path | str, obj: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def load_config(path: Path | str = CONFIG_PATH) -> dict:
    return load_json(path)


def model_settings(config: dict, model: str) -> dict:
    """The config entry for `model`; fails loudly if it can't be run yet."""
    if model not in config["models"]:
        raise SystemExit(f"model {model!r} is not in {CONFIG_PATH.name}")
    entry = config["models"][model]
    if not entry.get("deployment"):
        raise SystemExit(f"model {model!r} has no Azure deployment name in {CONFIG_PATH.name}")
    return entry


def shared_settings(config: dict, model: str) -> dict:
    """Everything that must be identical for both harnesses on this model."""
    entry = config["models"][model]
    return {
        "limits": config["limits"],
        "api_path": config["endpoint"]["api_path"],
        "model": model,
        "deployment": entry.get("deployment"),
        "api": entry.get("api", "chat_completions"),
        "temperature": entry.get("temperature"),
        "reasoning_effort": entry.get("reasoning_effort"),
    }


def settings_hash(config: dict, model: str) -> str:
    """Hash of the shared settings: two records are comparable only if this matches."""
    blob = json.dumps(shared_settings(config, model), sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def read_task(task_id: str) -> dict:
    return load_json(TASKS_DIR / f"{task_id}.json")


def frozen_now() -> str:
    """The workspace clock (ISO with offset); every harness and the server share it."""
    return load_json(SEED_PATH)["now"]


def sha256_file(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sanitized_env(extra: dict | None = None) -> dict:
    """os.environ without anything secret-looking, plus `extra` (for harness processes)."""
    env = {k: v for k, v in os.environ.items() if not any(m in k.upper() for m in SECRET_MARKERS)}
    env.update(extra or {})
    return env


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def content_text(content: Any) -> tuple[str, int]:
    """(visible text, number of reasoning items) of a message's content.

    Chat completions give a string. The Responses API gives a list of blocks: text blocks
    ("text" / "output_text") plus reasoning items, whose encrypted payload is not text."""
    if isinstance(content, str) or content is None:
        return content or "", 0
    if not isinstance(content, list):
        return json.dumps(content, ensure_ascii=False, default=str), 0
    texts, reasoning = [], 0
    for block in content:
        if isinstance(block, str):
            texts.append(block)
        elif isinstance(block, dict):
            if block.get("type") == "reasoning":
                reasoning += 1
            elif block.get("type") in ("text", "output_text") and isinstance(block.get("text"), str):
                texts.append(block["text"])
    return "\n".join(texts), reasoning


def message(role: str, content: Any, *, agent: str | None = None, tool_calls: list | None = None,
            tool_call_id: str | None = None, name: str | None = None) -> dict:
    """One transcript entry in the shared format both adapters write."""
    text, reasoning = content_text(content)
    out: dict[str, Any] = {"role": role, "content": text}
    if reasoning:
        out["reasoning_items"] = reasoning
    if agent:
        out["agent"] = agent
    if name:
        out["name"] = name
    if tool_calls:
        out["tool_calls"] = [{"id": c.get("id"), "name": c.get("name"), "args": c.get("args")} for c in tool_calls]
    if tool_call_id:
        out["tool_call_id"] = tool_call_id
    return out
