"""Shared pieces of the fake Google API: requests, errors, clock, IDs.

The real tools call googleapiclient chains such as
``service.users().messages().list(userId="me", q=...).execute()``. Each fake
resource method returns a ``FakeRequest`` whose ``execute`` runs the operation
against the in-memory workspace, so the tool code runs unchanged.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import quote, urlencode

import httplib2
from googleapiclient.errors import HttpError

IST = timezone(timedelta(hours=5, minutes=30))


class FakeRequest:
    """Stand-in for googleapiclient.http.HttpRequest."""

    def __init__(self, run: Callable[[], Any], uri: str, method: str = "GET"):
        self._run = run
        self.uri = uri
        self.method = method

    def execute(self, *args, **kwargs):
        return self._run()


def api_uri(base: str, path: str, **params) -> str:
    """URI as googleapiclient would report it in an HttpError."""
    query = {k: v for k, v in params.items() if v is not None}
    query["alt"] = "json"
    flat = []
    for key, value in query.items():
        if isinstance(value, list):
            flat.extend((key, str(v)) for v in value)
        elif isinstance(value, bool):
            flat.append((key, "true" if value else "false"))
        else:
            flat.append((key, str(value)))
    return f"{base}{path}?{urlencode(flat)}"


def http_error(
    status: int,
    message: str,
    uri: str,
    *,
    errors: list[dict] | None = None,
    reason: str | None = None,
    domain: str = "global",
    detail_style: str = "errors",
) -> HttpError:
    """Build the HttpError Google would raise, so the tools print the same text.

    detail_style:
      "errors"  -> error.errors list (Gmail, Calendar, Drive, Tasks)
      "message" -> no list; details fall back to the message (Sheets, Docs)
    """
    body: dict[str, Any] = {"code": status, "message": message}
    if detail_style == "errors":
        body["errors"] = errors or [
            {"message": message, "domain": domain, "reason": reason or "invalid"}
        ]
    status_text = {400: "INVALID_ARGUMENT", 403: "PERMISSION_DENIED", 404: "NOT_FOUND", 409: "ALREADY_EXISTS"}
    body["status"] = status_text.get(status, "UNKNOWN")
    resp = httplib2.Response({"status": status})
    resp.reason = {400: "Bad Request", 403: "Forbidden", 404: "Not Found", 409: "Conflict"}.get(status, "Error")
    return HttpError(resp, json.dumps({"error": body}).encode("utf-8"), uri=uri)


class Clock:
    """Frozen 'now' for the run, plus a tiny tick per write so records keep an order."""

    def __init__(self, now: datetime):
        self.frozen = now
        self._ticks = 0

    def now(self) -> datetime:
        return self.frozen

    def stamp(self) -> datetime:
        """A moment just after 'now' for created/updated fields (1 s per write)."""
        self._ticks += 1
        return self.frozen + timedelta(seconds=self._ticks)

    @staticmethod
    def rfc3339(dt: datetime) -> str:
        """Google-style UTC timestamp with milliseconds: 2026-10-07T04:00:01.000Z."""
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def make_id(kind: str, seed: str, length: int, alphabet: str = "hex") -> str:
    """Deterministic ID shaped like the real ones (see tool_reference / world.md §10)."""
    digest = hashlib.sha256(f"{kind}:{seed}".encode()).digest()
    if alphabet == "hex":
        return digest.hex()[:length]
    if alphabet == "b32hex":  # calendar event ids: 0-9a-v
        chars = "0123456789abcdefghijklmnopqrstuv"
        value = int.from_bytes(digest, "big")
        out = []
        while len(out) < length:
            value, rem = divmod(value, 32)
            out.append(chars[rem])
        return "".join(out)
    if alphabet == "b64":  # tasks, docs, sheets, comments
        text = base64.urlsafe_b64encode(digest * 2).decode().rstrip("=")
        return text[:length]
    raise ValueError(alphabet)


class IdFactory:
    """Per-kind counters so every new object gets a fresh, deterministic ID."""

    def __init__(self, namespace: str = "run"):
        self.namespace = namespace
        self.counts: dict[str, int] = {}

    def new(self, kind: str, length: int, alphabet: str = "hex") -> str:
        self.counts[kind] = self.counts.get(kind, 0) + 1
        return make_id(kind, f"{self.namespace}:{self.counts[kind]}", length, alphabet)


def quote_id(value: str) -> str:
    return quote(value, safe="")
