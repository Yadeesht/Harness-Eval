"""Fake Google Drive API v3: files.list/get/create/delete/export_media/get_media, comments, replies.

Docs and sheets are Drive files too, so search_docs / list_spreadsheets and
the comment tools all land here.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .base import FakeRequest, api_uri, http_error

if TYPE_CHECKING:
    from ..workspace import Workspace

BASE = "https://www.googleapis.com"
DOC = "application/vnd.google-apps.document"
SHEET = "application/vnd.google-apps.spreadsheet"
TOKEN = re.compile(r"[0-9a-z]+")


def web_link(file: dict) -> str:
    if file["mimeType"] == DOC:
        return f"https://docs.google.com/document/d/{file['id']}/edit?usp=drivesdk"
    if file["mimeType"] == SHEET:
        return f"https://docs.google.com/spreadsheets/d/{file['id']}/edit?usp=drivesdk"
    return f"https://drive.google.com/file/d/{file['id']}/view?usp=drivesdk"


def _not_found(file_id: str, uri: str):
    msg = f"File not found: {file_id}."
    return http_error(404, msg, uri, errors=[{"message": msg, "domain": "global", "reason": "notFound", "location": "fileId", "locationType": "parameter"}])


def _invalid_q(uri: str):
    return http_error(400, "Invalid Value", uri, errors=[{"message": "Invalid Value", "domain": "global", "reason": "invalid", "location": "q", "locationType": "parameter"}])


def name_contains(name: str, query: str) -> bool:
    """Drive `name contains`: every query word is a prefix of some word in the name.

    Observed: "Probe <tag> Plan" matches "Probe <tag> Q4 Planning — Platform"
    (words need not be adjacent), punctuation is ignored, body words never match.
    """
    want = TOKEN.findall(query.lower())
    have = TOKEN.findall(name.lower())
    return all(any(h.startswith(w) for h in have) for w in want)


def _split_and(q: str) -> list[str]:
    parts, buf, quoted = [], "", False
    i = 0
    while i < len(q):
        ch = q[i]
        if ch == "'" and (i == 0 or q[i - 1] != "\\"):
            quoted = not quoted
        if not quoted and q[i : i + 5].lower() == " and ":
            parts.append(buf.strip())
            buf = ""
            i += 5
            continue
        buf += ch
        i += 1
    if buf.strip():
        parts.append(buf.strip())
    return parts


def _unquote(value: str) -> str:
    return value.strip().strip("'").replace("\\'", "'")


def compile_q(q: str | None, text_of) -> callable:
    clauses = _split_and(q or "")
    tests = []
    for clause in clauses:
        m = re.fullmatch(r"name\s+contains\s+('(?:[^'\\]|\\.)*')", clause, re.I)
        if m:
            value = _unquote(m.group(1))
            tests.append(lambda f, v=value: name_contains(f["name"], v))
            continue
        m = re.fullmatch(r"name\s*=\s*('(?:[^'\\]|\\.)*')", clause, re.I)
        if m:
            value = _unquote(m.group(1))
            tests.append(lambda f, v=value: f["name"] == v)
            continue
        m = re.fullmatch(r"fullText\s+contains\s+('(?:[^'\\]|\\.)*')", clause, re.I)
        if m:
            value = _unquote(m.group(1)).lower()
            tests.append(lambda f, v=value: v in (f["name"] + " " + text_of(f)).lower())
            continue
        m = re.fullmatch(r"mimeType\s*(=|!=)\s*('(?:[^'\\]|\\.)*')", clause, re.I)
        if m:
            op, value = m.group(1), _unquote(m.group(2))
            tests.append(lambda f, v=value, eq=(op == "="): (f["mimeType"] == v) == eq)
            continue
        m = re.fullmatch(r"trashed\s*=\s*(true|false)", clause, re.I)
        if m:
            want = m.group(1).lower() == "true"
            tests.append(lambda f, w=want: bool(f.get("trashed")) == w)
            continue
        m = re.fullmatch(r"('(?:[^'\\]|\\.)*')\s+in\s+parents", clause, re.I)
        if m:
            parent = _unquote(m.group(1))
            tests.append(lambda f, p=parent: p in f.get("parents", ["root"]))
            continue
        return None  # unsupported clause -> caller raises "Invalid Value"
    return lambda f: all(t(f) for t in tests)


class Drive:
    def __init__(self, ws: "Workspace"):
        self.ws = ws
        self._http = None

    def files(self):
        return _Files(self.ws)

    def comments(self):
        return _Comments(self.ws)

    def replies(self):
        return _Replies(self.ws)


class _Files:
    def __init__(self, ws):
        self.ws = ws
        self.d = ws.state["drive"]

    def _file(self, file_id, uri):
        f = self.d["files"].get(file_id)
        if f is None or f.get("trashed"):
            raise _not_found(file_id, uri)
        return f

    def _view(self, f):
        return {
            "kind": "drive#file",
            "id": f["id"],
            "name": f["name"],
            "mimeType": f["mimeType"],
            "createdTime": f["createdTime"],
            "modifiedTime": f["modifiedTime"],
            "webViewLink": web_link(f),
            "parents": f.get("parents", ["root"]),
            "trashed": bool(f.get("trashed")),
        }

    def list(self, q=None, pageSize=None, orderBy=None, pageToken=None, **_):
        uri = api_uri(BASE, "/drive/v3/files", q=q, pageSize=pageSize, orderBy=orderBy)

        def run():
            test = compile_q(q, self.ws.file_text)
            if test is None:
                raise _invalid_q(uri)
            files = [f for f in self.d["files"].values() if test(f) and ("trashed" in (q or "") or not f.get("trashed"))]
            files.sort(key=lambda f: f["modifiedTime"], reverse=True)
            if orderBy and orderBy.startswith("name"):
                files.sort(key=lambda f: f["name"].lower(), reverse=orderBy.endswith("desc"))
            size = int(pageSize) if pageSize else 100
            start = int(pageToken) if pageToken else 0
            out = {"kind": "drive#fileList", "files": [self._view(f) for f in files[start : start + size]]}
            if start + size < len(files):
                out["nextPageToken"] = str(start + size)
            return out

        return FakeRequest(run, uri)

    def get(self, fileId=None, fields=None, **_):
        uri = api_uri(BASE, f"/drive/v3/files/{fileId}", fields=fields, supportsAllDrives=_.get("supportsAllDrives"))
        return FakeRequest(lambda: self._view(self._file(fileId, uri)), uri)

    def create(self, body=None, media_body=None, fields=None, **_):
        def run():
            body_ = body or {}
            now = self.ws.clock.rfc3339(self.ws.clock.stamp())
            file_id = self.ws.ids.new("drive_file", 33, "b64")
            f = {
                "id": file_id,
                "name": body_.get("name", "Untitled"),
                "mimeType": body_.get("mimeType", "application/octet-stream"),
                "createdTime": now,
                "modifiedTime": now,
                "parents": body_.get("parents", ["root"]),
                "origin": "agent",
            }
            data = getattr(media_body, "_fake_bytes", None)
            if data is not None:
                f["size"] = len(data)
                f["source"] = getattr(media_body, "_fake_source", None)
            self.d["files"][file_id] = f
            return self._view(f)

        return FakeRequest(run, api_uri(BASE, "/upload/drive/v3/files", uploadType="resumable"), "POST")

    def delete(self, fileId=None, **_):
        uri = api_uri(BASE, f"/drive/v3/files/{fileId}")

        def run():
            self._file(fileId, uri)
            del self.d["files"][fileId]
            self.ws.forget_file(fileId)
            return ""

        return FakeRequest(run, uri, "DELETE")

    def update(self, fileId=None, body=None, **_):
        uri = api_uri(BASE, f"/drive/v3/files/{fileId}")

        def run():
            f = self._file(fileId, uri)
            for key in ("name", "trashed"):
                if key in (body or {}):
                    f[key] = body[key]
            f["modifiedTime"] = self.ws.clock.rfc3339(self.ws.clock.stamp())
            return self._view(f)

        return FakeRequest(run, uri, "PATCH")

    def export_media(self, fileId=None, mimeType=None, **_):
        uri = api_uri(BASE, f"/drive/v3/files/{fileId}/export", mimeType=mimeType)

        def run():
            f = self._file(fileId, uri)
            return f"%PDF-1.4 fake export of {f['name']}\n{self.ws.file_text(f)}".encode()

        req = FakeRequest(run, uri)
        req._fake_download = True
        return req

    def get_media(self, fileId=None, **_):
        uri = api_uri(BASE, f"/drive/v3/files/{fileId}", alt="media")

        def run():
            f = self._file(fileId, uri)
            return self.ws.file_text(f).encode()

        req = FakeRequest(run, uri)
        req._fake_download = True
        return req


class _Comments:
    def __init__(self, ws):
        self.ws = ws
        self.d = ws.state["drive"]

    def _check_file(self, file_id, uri):
        if file_id not in self.d["files"]:
            raise _not_found(file_id, uri)

    def list(self, fileId=None, fields=None, **_):
        uri = api_uri(BASE, f"/drive/v3/files/{fileId}/comments", fields=fields)

        def run():
            self._check_file(fileId, uri)
            comments = [c for c in self.d["comments"].get(fileId, []) if not c.get("deleted")]
            ordered = sorted(comments, key=lambda c: c["createdTime"], reverse=True)
            return {"comments": [_comment_view(c) for c in ordered]}

        return FakeRequest(run, uri)

    def create(self, fileId=None, body=None, fields=None, **_):
        uri = api_uri(BASE, f"/drive/v3/files/{fileId}/comments", fields=fields)

        def run():
            self._check_file(fileId, uri)
            now = self.ws.clock.rfc3339(self.ws.clock.stamp())
            comment = {
                "id": "AAAB" + self.ws.ids.new("comment", 7, "b64"),
                "content": (body or {}).get("content", ""),
                "author": {"displayName": self.ws.user_name, "me": True},
                "createdTime": now,
                "modifiedTime": now,
                "resolved": False,
                "replies": [],
                "origin": "agent",
            }
            self.d["comments"].setdefault(fileId, []).append(comment)
            return _comment_view(comment)

        return FakeRequest(run, uri, "POST")


class _Replies:
    def __init__(self, ws):
        self.ws = ws
        self.d = ws.state["drive"]

    def create(self, fileId=None, commentId=None, body=None, fields=None, **_):
        uri = api_uri(BASE, f"/drive/v3/files/{fileId}/comments/{commentId}/replies", fields=fields)

        def run():
            if fileId not in self.d["files"]:
                raise _not_found(fileId, uri)
            comment = next((c for c in self.d["comments"].get(fileId, []) if c["id"] == commentId), None)
            if comment is None:
                msg = f"Comment not found: {commentId}."
                raise http_error(404, msg, uri, errors=[{"message": msg, "domain": "global", "reason": "notFound", "location": "commentId", "locationType": "parameter"}])
            now = self.ws.clock.rfc3339(self.ws.clock.stamp())
            body_ = body or {}
            reply = {
                "id": "AAAB" + self.ws.ids.new("reply", 7, "b64"),
                "content": body_.get("content", ""),
                "author": {"displayName": self.ws.user_name, "me": True},
                "createdTime": now,
                "modifiedTime": now,
                "origin": "agent",
            }
            if body_.get("action") in ("resolve", "reopen"):
                reply["action"] = body_["action"]
                comment["resolved"] = body_["action"] == "resolve"
            comment["replies"].append(reply)
            comment["modifiedTime"] = now
            return dict(reply)

        return FakeRequest(run, uri, "POST")


def _comment_view(c: dict) -> dict:
    return {
        "id": c["id"],
        "content": c["content"],
        "author": dict(c["author"]),
        "createdTime": c["createdTime"],
        "modifiedTime": c["modifiedTime"],
        "resolved": bool(c.get("resolved")),
        "replies": [dict(r) for r in c.get("replies", [])],
    }
