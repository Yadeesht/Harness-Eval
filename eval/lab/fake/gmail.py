"""Fake Gmail API v1 (users.messages / labels / drafts / settings.filters / getProfile)."""

from __future__ import annotations

import base64
import html
import re
from email import message_from_bytes
from email.message import EmailMessage
from email.utils import format_datetime, getaddresses
from typing import TYPE_CHECKING

from .base import FakeRequest, api_uri, http_error
from .gmail_search import MessageView, compile_query

if TYPE_CHECKING:
    from ..workspace import Workspace

BASE = "https://gmail.googleapis.com"
SYSTEM_LABELS = [
    "CHAT", "SENT", "INBOX", "IMPORTANT", "TRASH", "DRAFT", "SPAM", "CATEGORY_FORUMS",
    "CATEGORY_UPDATES", "CATEGORY_PERSONAL", "CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL",
    "STARRED", "UNREAD",
]
HEX16 = re.compile(r"^[0-9a-f]{16}$")


def snippet_of(body: str) -> str:
    """Gmail escapes first, then cuts at ~201 characters (measured on the real
    account), never inside an &...; entity."""
    text = " ".join((body or "").split())
    escaped = html.escape(text, quote=True).replace("&#x27;", "&#39;")
    if len(escaped) <= 201:
        return escaped
    cut = escaped[:201]
    amp = cut.rfind("&")
    if amp != -1 and ";" not in cut[amp:]:
        cut = cut[:amp]
    return cut


class Gmail:
    def __init__(self, ws: "Workspace"):
        self.ws = ws
        self._http = None

    def users(self):
        return _Users(self.ws)


class _Users:
    def __init__(self, ws):
        self.ws = ws

    def getProfile(self, userId="me"):
        g = self.ws.state["gmail"]
        return FakeRequest(
            lambda: {
                "emailAddress": self.ws.user_email,
                "messagesTotal": len(g["messages"]),
                "threadsTotal": len({m["threadId"] for m in g["messages"].values()}),
                "historyId": "100000",
            },
            api_uri(BASE, "/gmail/v1/users/me/profile"),
        )

    def messages(self):
        return _Messages(self.ws)

    def labels(self):
        return _Labels(self.ws)

    def drafts(self):
        return _Drafts(self.ws)

    def settings(self):
        return _Settings(self.ws)


class _Messages:
    def __init__(self, ws):
        self.ws = ws
        self.g = ws.state["gmail"]

    # ---- helpers ---------------------------------------------------------
    def _get(self, msg_id: str, uri: str) -> dict:
        if msg_id in self.g["messages"]:
            return self.g["messages"][msg_id]
        if not HEX16.match(msg_id or ""):
            raise http_error(400, "Invalid id value", uri, reason="invalidArgument")
        raise http_error(404, "Requested entity was not found.", uri, reason="notFound")

    def _labels_by_id(self):
        labels = {l: {"id": l, "name": l} for l in SYSTEM_LABELS}
        labels.update(self.g["labels"])
        return labels

    def _raw(self, m: dict) -> str:
        em = EmailMessage()
        em["From"] = m["from"]
        em["To"] = m.get("to", "")
        if m.get("cc"):
            em["Cc"] = m["cc"]
        em["Subject"] = m.get("subject", "")
        em["Date"] = m["date_header"]
        em["Message-ID"] = f"<{m['id']}@mail.kestrel.test>"
        em.set_content(m.get("body", ""))
        return base64.urlsafe_b64encode(em.as_bytes()).decode()

    def _headers(self, m: dict, wanted: list[str] | None) -> list[dict]:
        all_headers = [
            ("From", m["from"]),
            ("To", m.get("to", "")),
            ("Cc", m.get("cc", "")),
            ("Subject", m.get("subject", "")),
            ("Date", m["date_header"]),
        ]
        out = [{"name": n, "value": v} for n, v in all_headers if v != "" or n != "Cc"]
        if wanted:
            want = {w.lower() for w in wanted}
            out = [h for h in out if h["name"].lower() in want]
        return out

    # ---- API -------------------------------------------------------------
    def list(self, userId="me", q=None, maxResults=None, labelIds=None, pageToken=None, includeSpamTrash=False, **_):
        uri = api_uri(BASE, "/gmail/v1/users/me/messages", q=q, maxResults=maxResults, labelIds=labelIds, pageToken=pageToken)

        def run():
            match = compile_query(q, self.ws.clock.now())
            labels = self._labels_by_id()
            hits = []
            for m in self.g["messages"].values():
                view = MessageView(m, labels, self.ws.user_email)
                if labelIds and not set(labelIds) <= view.label_ids:
                    continue
                if match(view):
                    hits.append(m)
            hits.sort(key=lambda m: m["internalDate"], reverse=True)
            size = int(maxResults) if maxResults else 100
            start = int(pageToken) if pageToken else 0
            page = hits[start : start + size]
            out = {"messages": [{"id": m["id"], "threadId": m["threadId"]} for m in page], "resultSizeEstimate": len(page)}
            if not page:
                out = {"resultSizeEstimate": 0}
            if start + size < len(hits):
                out["nextPageToken"] = str(start + size)
            return out

        return FakeRequest(run, uri)

    def get(self, userId="me", id=None, format="full", metadataHeaders=None, **_):
        uri = api_uri(BASE, f"/gmail/v1/users/me/messages/{id}", format=format, metadataHeaders=metadataHeaders)

        def run():
            m = self._get(id, uri)
            base = {
                "id": m["id"],
                "threadId": m["threadId"],
                "labelIds": list(m.get("labelIds", [])),
                "snippet": snippet_of(m.get("body", "")),
                "sizeEstimate": 800 + len(m.get("body", "")),
                "historyId": "100000",
                "internalDate": str(int(self._when(m).timestamp() * 1000)),
            }
            if format == "raw":
                base["raw"] = self._raw(m)
                return base
            headers = self._headers(m, metadataHeaders if format == "metadata" else None)
            payload = {"mimeType": "text/plain", "headers": headers}
            if format != "metadata":
                payload["body"] = {"data": base64.urlsafe_b64encode(m.get("body", "").encode()).decode()}
            base["payload"] = payload
            return base

        return FakeRequest(run, uri)

    def _when(self, m):
        from datetime import datetime

        return datetime.fromisoformat(m["internalDate"])

    def send(self, userId="me", body=None, **_):
        uri = api_uri(BASE, "/gmail/v1/users/me/messages/send")

        def run():
            parsed = message_from_bytes(base64.urlsafe_b64decode(body["raw"]))
            payload = parsed.get_payload(decode=True) if not parsed.is_multipart() else b""
            text = (payload or b"").decode("utf-8", errors="replace")
            msg_id = self.ws.ids.new("gmail_msg", 16)
            to = str(parsed.get("To", ""))
            labels = ["SENT"]
            if any(a.lower() == self.ws.user_email for _, a in getaddresses([to])):
                labels += ["INBOX", "UNREAD", "CATEGORY_PERSONAL"]
            when = self.ws.clock.stamp()
            self.g["messages"][msg_id] = {
                "id": msg_id,
                "threadId": msg_id,
                "labelIds": labels,
                "internalDate": when.isoformat(),
                "date_header": format_datetime(when),
                "from": str(parsed.get("From", self.ws.user_email)),
                "to": to,
                "cc": str(parsed.get("Cc", "") or ""),
                "subject": str(parsed.get("Subject", "")),
                "body": text.rstrip("\n"),
                "origin": "agent",
            }
            return {"id": msg_id, "threadId": msg_id, "labelIds": labels}

        return FakeRequest(run, uri, "POST")

    def modify(self, userId="me", id=None, body=None, **_):
        uri = api_uri(BASE, f"/gmail/v1/users/me/messages/{id}/modify")

        def run():
            m = self._get(id, uri)
            known = set(SYSTEM_LABELS) | set(self.g["labels"])
            add = (body or {}).get("addLabelIds", []) or []
            remove = (body or {}).get("removeLabelIds", []) or []
            for label in add + remove:
                if label not in known:
                    raise http_error(400, "labelId not found", uri, reason="invalidArgument")
            labels = [l for l in m["labelIds"] if l not in remove]
            labels += [l for l in add if l not in labels]
            m["labelIds"] = labels
            return {"id": m["id"], "threadId": m["threadId"], "labelIds": labels}

        return FakeRequest(run, uri, "POST")

    def trash(self, userId="me", id=None, **_):
        uri = api_uri(BASE, f"/gmail/v1/users/me/messages/{id}/trash")

        def run():
            m = self._get(id, uri)
            m["labelIds"] = [l for l in m["labelIds"] if l not in ("INBOX", "UNREAD")] + ["TRASH"]
            return {"id": m["id"], "threadId": m["threadId"], "labelIds": m["labelIds"]}

        return FakeRequest(run, uri, "POST")

    def delete(self, userId="me", id=None, **_):
        uri = api_uri(BASE, f"/gmail/v1/users/me/messages/{id}")

        def run():
            self._get(id, uri)
            del self.g["messages"][id]
            return ""

        return FakeRequest(run, uri, "DELETE")


class _Labels:
    def __init__(self, ws):
        self.ws = ws
        self.g = ws.state["gmail"]

    def _system(self):
        return [{"id": l, "name": l, "type": "system"} for l in SYSTEM_LABELS]

    def list(self, userId="me", **_):
        return FakeRequest(
            lambda: {"labels": self._system() + [dict(l) for l in self.g["labels"].values()]},
            api_uri(BASE, "/gmail/v1/users/me/labels"),
        )

    def _find(self, label_id, uri):
        if label_id in self.g["labels"]:
            return self.g["labels"][label_id]
        if label_id in SYSTEM_LABELS:
            return {"id": label_id, "name": label_id, "type": "system"}
        raise http_error(404, "Requested entity was not found.", uri, reason="notFound")

    def get(self, userId="me", id=None, **_):
        uri = api_uri(BASE, f"/gmail/v1/users/me/labels/{id}")
        return FakeRequest(lambda: dict(self._find(id, uri)), uri)

    def create(self, userId="me", body=None, **_):
        uri = api_uri(BASE, "/gmail/v1/users/me/labels")

        def run():
            name = (body or {}).get("name", "")
            taken = {l["name"].lower() for l in self.g["labels"].values()} | {l.lower() for l in SYSTEM_LABELS}
            if not name.strip() or name.lower() in taken:
                raise http_error(409, "Label name exists or conflicts", uri, reason="aborted")
            n = max([int(i.split("_")[1]) for i in self.g["labels"] if i.startswith("Label_") and i.split("_")[1].isdigit()] or [0]) + 1
            label = {
                "id": f"Label_{n}",
                "name": name,
                "type": "user",
                "labelListVisibility": body.get("labelListVisibility", "labelShow"),
                "messageListVisibility": body.get("messageListVisibility", "show"),
            }
            self.g["labels"][label["id"]] = label
            return dict(label)

        return FakeRequest(run, uri, "POST")

    def update(self, userId="me", id=None, body=None, **_):
        uri = api_uri(BASE, f"/gmail/v1/users/me/labels/{id}")

        def run():
            label = self._find(id, uri)
            if label.get("type") == "system":
                raise http_error(400, "Invalid label name", uri, reason="invalidArgument")
            new_name = (body or {}).get("name", label["name"])
            clash = [l for l in self.g["labels"].values() if l["name"].lower() == new_name.lower() and l["id"] != id]
            if clash:
                raise http_error(409, "Label name exists or conflicts", uri, reason="aborted")
            label["name"] = new_name
            return dict(label)

        return FakeRequest(run, uri, "PUT")

    def delete(self, userId="me", id=None, **_):
        uri = api_uri(BASE, f"/gmail/v1/users/me/labels/{id}")

        def run():
            if id not in self.g["labels"]:
                if id in SYSTEM_LABELS:
                    raise http_error(400, "Invalid delete request", uri, reason="invalidArgument")
                raise http_error(404, "Requested entity was not found.", uri, reason="notFound")
            del self.g["labels"][id]
            for m in self.g["messages"].values():
                if id in m["labelIds"]:
                    m["labelIds"].remove(id)
            return ""

        return FakeRequest(run, uri, "DELETE")


class _Drafts:
    def __init__(self, ws):
        self.ws = ws
        self.g = ws.state["gmail"]

    def create(self, userId="me", body=None, **_):
        uri = api_uri(BASE, "/gmail/v1/users/me/drafts")

        def run():
            raw = (body or {}).get("message", {}).get("raw", "")
            parsed = message_from_bytes(base64.urlsafe_b64decode(raw))
            payload = parsed.get_payload(decode=True) if not parsed.is_multipart() else b""
            draft_id = "r" + str(int(self.ws.ids.new("draft", 15), 16))[:19]
            msg_id = self.ws.ids.new("gmail_msg", 16)
            self.g["drafts"][draft_id] = {
                "id": draft_id,
                "message_id": msg_id,
                "to": str(parsed.get("To", "")),
                "subject": str(parsed.get("Subject", "")),
                "body": (payload or b"").decode("utf-8", errors="replace").rstrip("\n"),
                "created": self.ws.clock.stamp().isoformat(),
                "origin": "agent",
            }
            return {"id": draft_id, "message": {"id": msg_id, "threadId": msg_id, "labelIds": ["DRAFT"]}}

        return FakeRequest(run, uri, "POST")

    def list(self, userId="me", q=None, **_):
        def run():
            items = sorted(self.g["drafts"].values(), key=lambda d: d["created"], reverse=True)
            if q:
                items = [d for d in items if q.lower() in (d["subject"] + " " + d["body"]).lower()]
            if not items:
                return {"resultSizeEstimate": 0}
            return {"drafts": [{"id": d["id"], "message": {"id": d["message_id"], "threadId": d["message_id"]}} for d in items]}

        return FakeRequest(run, api_uri(BASE, "/gmail/v1/users/me/drafts"))

    def get(self, userId="me", id=None, format="full", **_):
        uri = api_uri(BASE, f"/gmail/v1/users/me/drafts/{id}")

        def run():
            d = self.g["drafts"].get(id)
            if not d:
                raise http_error(404, "Requested entity was not found.", uri, reason="notFound")
            headers = [{"name": "To", "value": d["to"]}, {"name": "Subject", "value": d["subject"]}, {"name": "From", "value": self.ws.user_email}]
            return {"id": d["id"], "message": {"id": d["message_id"], "threadId": d["message_id"], "labelIds": ["DRAFT"], "payload": {"headers": headers}}}

        return FakeRequest(run, uri)

    def delete(self, userId="me", id=None, **_):
        uri = api_uri(BASE, f"/gmail/v1/users/me/drafts/{id}")

        def run():
            if id not in self.g["drafts"]:
                raise http_error(404, "Requested entity was not found.", uri, reason="notFound")
            del self.g["drafts"][id]
            return ""

        return FakeRequest(run, uri, "DELETE")


class _Settings:
    def __init__(self, ws):
        self.ws = ws

    def filters(self):
        return _Filters(self.ws)


class _Filters:
    def __init__(self, ws):
        self.ws = ws
        self.g = ws.state["gmail"]

    def list(self, userId="me", **_):
        def run():
            if not self.g["filters"]:
                return {}
            return {"filter": [dict(f) for f in self.g["filters"].values()]}

        return FakeRequest(run, api_uri(BASE, "/gmail/v1/users/me/settings/filters"))

    def get(self, userId="me", id=None, **_):
        uri = api_uri(BASE, f"/gmail/v1/users/me/settings/filters/{id}")

        def run():
            if id not in self.g["filters"]:
                raise http_error(404, "Requested entity was not found.", uri, reason="notFound")
            return dict(self.g["filters"][id])

        return FakeRequest(run, uri)

    def delete(self, userId="me", id=None, **_):
        uri = api_uri(BASE, f"/gmail/v1/users/me/settings/filters/{id}")

        def run():
            if id not in self.g["filters"]:
                raise http_error(404, "Requested entity was not found.", uri, reason="notFound")
            del self.g["filters"][id]
            return ""

        return FakeRequest(run, uri, "DELETE")

    def create(self, userId="me", body=None, **_):
        def run():
            fid = self.ws.ids.new("filter", 40, "b64")
            self.g["filters"][fid] = {"id": fid, **(body or {})}
            return dict(self.g["filters"][fid])

        return FakeRequest(run, api_uri(BASE, "/gmail/v1/users/me/settings/filters"), "POST")
