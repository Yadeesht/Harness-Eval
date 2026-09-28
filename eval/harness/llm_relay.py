"""Local LLM relay: both harnesses call this instead of Azure (AGENTS.md: same endpoint).

    .venv/Scripts/python.exe eval/harness/llm_relay.py --port 8790 --out eval/runs/<run>/llm

Forwards `<api_path>/*` (config: /openai/v1) to the Azure resource named in the endpoint
env var, adding the real key from the key env var. Harness processes only ever hold a dummy
key. Nothing is changed in the request or the response.

For every request it appends one line to <out>/llm_calls.jsonl:
    n, time, path, status, latency_s, client (user-agent), retry header,
    params (the wire parameters: model, temperature, reasoning_effort, max tokens, ...),
    tools (names), tools_sha, n_messages, usage (prompt/completion/cached/reasoning),
    finish_reason, served_model (the snapshot Azure answered with), error (first 500 chars)
With --save-bodies the full request and response go to <out>/bodies/<n>.json.
Streaming responses are passed through chunk by chunk; usage comes from the final SSE chunk.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse, Response, StreamingResponse  # noqa: E402
from starlette.routing import Route  # noqa: E402

from common import ROOT, load_config  # noqa: E402

# Parameters worth auditing; anything else in the body is listed under "other_keys".
PARAM_KEYS = (
    "model", "temperature", "top_p", "reasoning_effort", "reasoning", "max_tokens", "max_completion_tokens",
    "parallel_tool_calls", "tool_choice", "stream", "stream_options", "n", "seed", "stop",
    "presence_penalty", "frequency_penalty", "response_format", "prompt_cache_key", "service_tier",
    "store", "user", "metadata", "logprobs", "verbosity", "include", "max_output_tokens", "truncation", "text",
)
DROP_REQUEST_HEADERS = {"host", "content-length", "authorization", "api-key", "accept-encoding", "connection", "transfer-encoding"}
DROP_RESPONSE_HEADERS = {"content-length", "content-encoding", "transfer-encoding", "connection"}


class CallLog:
    def __init__(self, out: Path, save_bodies: bool):
        out.mkdir(parents=True, exist_ok=True)
        self.path = out / "llm_calls.jsonl"
        self.bodies = out / "bodies" if save_bodies else None
        if self.bodies:
            self.bodies.mkdir(exist_ok=True)
        self.n = 0

    def next(self) -> int:
        self.n += 1
        return self.n

    def write(self, entry: dict, request_body: bytes | None, response_text: str | None) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        if self.bodies is not None:
            req = None
            if request_body:
                try:
                    req = json.loads(request_body)
                except ValueError:
                    req = request_body.decode("utf-8", "replace")
            (self.bodies / f"{entry['n']:04d}.json").write_text(
                json.dumps({"request": req, "response": response_text}, ensure_ascii=False, default=str), encoding="utf-8"
            )


def summarize_request(body: dict) -> dict:
    params = {k: body[k] for k in PARAM_KEYS if k in body}
    tools = body.get("tools") or []
    names = [t.get("function", {}).get("name") or t.get("name") for t in tools]
    known = set(PARAM_KEYS) | {"messages", "tools", "input", "instructions"}
    messages = body.get("messages") or (body.get("input") if isinstance(body.get("input"), list) else [])
    return {
        "params": params,
        "other_keys": sorted(set(body) - known),
        "tools": names,
        "tools_sha": hashlib.sha256(json.dumps(tools, sort_keys=True).encode()).hexdigest()[:12] if tools else None,
        "n_messages": len(messages),
    }


def usage_of(usage: dict | None) -> dict | None:
    """Normalize chat-completions (prompt/completion_tokens) and Responses (input/output_tokens) usage."""
    if not usage:
        return None
    if "input_tokens" in usage:  # Responses API
        details = usage.get("input_tokens_details") or {}
        return {
            "prompt": usage.get("input_tokens"),
            "completion": usage.get("output_tokens"),
            "cached": details.get("cached_tokens") or 0,
            "cache_write": details.get("cache_write_tokens") or 0,
            "reasoning": (usage.get("output_tokens_details") or {}).get("reasoning_tokens") or 0,
        }
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    return {
        "prompt": usage.get("prompt_tokens"),
        "completion": usage.get("completion_tokens"),
        "cached": prompt_details.get("cached_tokens") or 0,
        "cache_write": prompt_details.get("cache_write_tokens") or 0,
        "reasoning": completion_details.get("reasoning_tokens") or 0,
    }


def parse_sse(text: str) -> tuple[dict | None, str | None, str | None]:
    """(usage, finish_reason, served model) from a chat-completions or Responses SSE stream."""
    usage, finish, served = None, None, None
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            chunk = json.loads(data)
        except ValueError:
            continue
        response = chunk.get("response") if isinstance(chunk.get("response"), dict) else None
        if response is not None:  # Responses API events carry the response object
            if response.get("model") and not served:
                served = response["model"]
            if chunk.get("type") in ("response.completed", "response.incomplete", "response.failed"):
                usage = response.get("usage") or usage
                finish = response.get("status")
            continue
        if chunk.get("usage"):
            usage = chunk["usage"]
        if chunk.get("model") and not served:
            served = chunk["model"]
        for choice in chunk.get("choices") or []:
            if choice.get("finish_reason"):
                finish = choice["finish_reason"]
    return usage, finish, served


def build_app(upstream: str, key: str, api_path: str, log: CallLog, timeout_s: float) -> Starlette:
    client = httpx.AsyncClient(base_url=upstream, timeout=httpx.Timeout(timeout_s, connect=30.0))

    async def relay(request: Request):
        path = request.url.path
        n = log.next()
        started = time.perf_counter()
        entry = {
            "n": n,
            "time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "method": request.method,
            "path": path,
            "client": request.headers.get("user-agent"),
            "retry": request.headers.get("x-stainless-retry-count"),
        }
        body = await request.body()
        parsed: dict = {}
        if body:
            try:
                parsed = json.loads(body)
            except ValueError:
                parsed = {}
        if isinstance(parsed, dict) and parsed:
            entry.update(summarize_request(parsed))

        if not path.startswith(api_path):
            entry.update(status=404, latency_s=0.0, error=f"path outside {api_path}")
            log.write(entry, body, None)
            return JSONResponse({"error": {"message": f"eval relay: only {api_path}/* is forwarded"}}, status_code=404)

        headers = {k: v for k, v in request.headers.items() if k.lower() not in DROP_REQUEST_HEADERS}
        headers["api-key"] = key
        upstream_request = client.build_request(request.method, path, params=request.query_params, headers=headers, content=body)
        try:
            upstream_response = await client.send(upstream_request, stream=True)
        except httpx.HTTPError as error:
            entry.update(status=502, latency_s=round(time.perf_counter() - started, 3), error=f"{type(error).__name__}: {error}"[:500])
            log.write(entry, body, None)
            return JSONResponse({"error": {"message": f"eval relay: upstream unreachable ({type(error).__name__})"}}, status_code=502)

        out_headers = {k: v for k, v in upstream_response.headers.items() if k.lower() not in DROP_RESPONSE_HEADERS}
        is_sse = "text/event-stream" in upstream_response.headers.get("content-type", "")
        entry["status"] = upstream_response.status_code
        entry["stream"] = is_sse

        if is_sse:
            async def passthrough():
                chunks = []
                try:
                    async for chunk in upstream_response.aiter_bytes():
                        chunks.append(chunk)
                        yield chunk
                finally:
                    await upstream_response.aclose()
                    text = b"".join(chunks).decode("utf-8", "replace")
                    usage, finish, served = parse_sse(text)
                    entry.update(latency_s=round(time.perf_counter() - started, 3), usage=usage_of(usage), finish_reason=finish, served_model=served)
                    if upstream_response.status_code >= 400:
                        entry["error"] = text[:500]
                    log.write(entry, body, text)

            return StreamingResponse(passthrough(), status_code=upstream_response.status_code, headers=out_headers)

        content = await upstream_response.aread()
        await upstream_response.aclose()
        text = content.decode("utf-8", "replace")
        entry["latency_s"] = round(time.perf_counter() - started, 3)
        try:
            payload = json.loads(text)
        except ValueError:
            payload = {}
        if isinstance(payload, dict):
            entry["usage"] = usage_of(payload.get("usage"))
            entry["served_model"] = payload.get("model")
            choices = payload.get("choices") or []
            if choices:
                entry["finish_reason"] = choices[0].get("finish_reason")
            elif payload.get("object") == "response":
                entry["finish_reason"] = payload.get("status")
        if upstream_response.status_code >= 400:
            entry["error"] = text[:500]
        log.write(entry, body, text)
        return Response(content, status_code=upstream_response.status_code, headers=out_headers)

    return Starlette(routes=[Route("/{path:path}", relay, methods=["GET", "POST", "PUT", "DELETE", "PATCH"])])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--out", required=True, help="folder for llm_calls.jsonl (and bodies/)")
    parser.add_argument("--config", default=None)
    parser.add_argument("--save-bodies", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config) if args.config else load_config()
    load_dotenv(ROOT / ".env")  # the relay is the only process that reads the real endpoint and key
    endpoint = os.environ.get(config["endpoint"]["origin_env"], "").strip()
    key = os.environ.get(config["endpoint"]["key_env"], "").strip()
    if not endpoint or not key:
        print(f"relay: set {config['endpoint']['origin_env']} and {config['endpoint']['key_env']}", file=sys.stderr)
        return 2
    parsed = urlparse(endpoint)
    upstream = f"{parsed.scheme}://{parsed.netloc}"
    log = CallLog(Path(args.out), args.save_bodies)
    app = build_app(upstream, key, config["endpoint"]["api_path"], log, float(config["limits"]["llm_timeout_s"]) + 30.0)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
