"""LLM judge for ambiguous and impossible tasks (AGENTS.md: only where code cannot decide).

The judge sees the task's rubric (`expect.judge`), the user's prompt and the agent's final
message, nothing else: no trajectory, no workspace state. It answers PASS or FAIL with a
one-sentence reason. It is only called when every code check has already passed, so an empty
final message never reaches it.

Judge settings (model, reasoning effort) live in eval/harness/config.json under "judge".
Calls go through an LLM relay like the harnesses' calls, so they are logged and the key stays
in the relay process.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SYSTEM = (
    "You grade one reply from an AI assistant against a rubric. The assistant was given a single "
    "request and could not ask follow-up questions before replying; its reply below is final.\n"
    "Apply the rubric strictly and literally. Do not reward effort or politeness.\n"
    'Answer with JSON only: {"verdict": "PASS" or "FAIL", "reason": "<one sentence>"}'
)


def judge_key(rubric: str, prompt: str, final_message: str, settings: dict) -> str:
    blob = json.dumps([rubric, prompt, final_message, settings], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def build_messages(rubric: str, prompt: str, final_message: str) -> list[dict]:
    user = (
        f"RUBRIC:\n{rubric}\n\n"
        f"USER REQUEST:\n{prompt}\n\n"
        f"ASSISTANT'S FINAL REPLY:\n{final_message}"
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def parse_verdict(text: str) -> dict[str, Any]:
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        data = json.loads(text[start:end])
        verdict = str(data.get("verdict", "")).strip().upper()
        if verdict in ("PASS", "FAIL"):
            return {"verdict": verdict, "reason": str(data.get("reason", "")).strip()}
    except (ValueError, AttributeError):
        pass
    return {"verdict": "UNPARSEABLE", "reason": text[:300]}


def judge(client, settings: dict, rubric: str, prompt: str, final_message: str) -> dict[str, Any]:
    """One judge call. `client` is an OpenAI client pointed at a relay; `settings` is config["judge"]."""
    kwargs: dict[str, Any] = {
        "model": settings["deployment"],
        "messages": build_messages(rubric, prompt, final_message),
        "response_format": {"type": "json_object"},
    }
    if settings.get("reasoning_effort"):
        kwargs["reasoning_effort"] = settings["reasoning_effort"]
    response = client.chat.completions.create(**kwargs)
    text = response.choices[0].message.content or ""
    result = parse_verdict(text)
    result["model"] = getattr(response, "model", settings["deployment"])
    result["usage"] = response.usage.model_dump() if response.usage else None
    return result
