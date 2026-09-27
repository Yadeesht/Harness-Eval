"""The in-memory workspace: one JSON-serialisable state dict plus clock and IDs.

State layout (all plain JSON):
  now, user{email,name}
  gmail{messages{id:msg}, labels{id:label}, filters{id:filter}, drafts{id:draft}}
  calendar{calendars{id:cal}, events{id:event}}
  tasks{lists{id:list}, tasks{id:task}}
  drive{files{id:file}, comments{fileId:[comment]}}
  docs{docId: {title, segments{body|headerId: [units]}, headers[], footers[], ...}}
  sheets{spreadsheetId: {title, locale, tabs[...]}}
Every object an agent creates carries origin="agent", which makes diffs easy.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path

from .fake.base import Clock, IdFactory
from .fake.docs import plain_text, text_tokens
from .fake.drive import DOC, SHEET
from .fake.sheets import new_tab


def empty_state(now: str, email: str, name: str) -> dict:
    return {
        "now": now,
        "user": {"email": email, "name": name},
        "gmail": {"messages": {}, "labels": {}, "filters": {}, "drafts": {}},
        "calendar": {"calendars": {email: {"summary": email, "accessRole": "owner", "primary": True, "timeZone": "Asia/Kolkata"}}, "events": {}},
        "tasks": {"lists": {}, "tasks": {}},
        "drive": {"files": {}, "comments": {}},
        "docs": {},
        "sheets": {},
    }


class Workspace:
    def __init__(self, state: dict, namespace: str = "run"):
        self.state = state
        self.clock = Clock(datetime.fromisoformat(state["now"]))
        self.ids = IdFactory(namespace)

    # ---- identity ---------------------------------------------------------
    @property
    def user_email(self) -> str:
        return self.state["user"]["email"].lower()

    @property
    def user_name(self) -> str:
        return self.state["user"]["name"]

    # ---- persistence ------------------------------------------------------
    @classmethod
    def load(cls, path: str | Path, namespace: str = "run") -> "Workspace":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")), namespace)

    def snapshot(self) -> dict:
        return copy.deepcopy(self.state)

    def dump(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.state, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    # ---- drive-backed objects ---------------------------------------------
    def _new_file(self, file_id, name, mime, origin, when=None):
        stamp = when or self.clock.rfc3339(self.clock.stamp())
        self.state["drive"]["files"][file_id] = {
            "id": file_id,
            "name": name,
            "mimeType": mime,
            "createdTime": stamp,
            "modifiedTime": stamp,
            "parents": ["root"],
            "origin": origin,
        }

    def add_doc(self, doc_id: str, title: str, body_tokens: list, origin: str = "seed", when: str | None = None) -> dict:
        self._new_file(doc_id, title, DOC, origin, when)
        self.state["docs"][doc_id] = {
            "documentId": doc_id,
            "title": title,
            "segments": {"body": body_tokens or text_tokens("\n")},
            "headers": [],
            "footers": [],
            "revision": 1,
        }
        return self.state["docs"][doc_id]

    def add_sheet(self, sid: str, title: str, tabs: list[dict], origin: str = "seed", when: str | None = None) -> dict:
        self._new_file(sid, title, SHEET, origin, when)
        self.state["sheets"][sid] = {
            "title": title,
            "locale": "en_GB",
            "tabs": [new_tab(t["title"], i, f"{sid}:{t['title']}") for i, t in enumerate(tabs)],
        }
        return self.state["sheets"][sid]

    def touch_file(self, file_id: str) -> None:
        f = self.state["drive"]["files"].get(file_id)
        if f:
            f["modifiedTime"] = self.clock.rfc3339(self.clock.stamp())
        if file_id in self.state["docs"]:
            self.state["docs"][file_id]["title"] = f["name"] if f else self.state["docs"][file_id]["title"]

    def forget_file(self, file_id: str) -> None:
        self.state["docs"].pop(file_id, None)
        self.state["sheets"].pop(file_id, None)
        self.state["drive"]["comments"].pop(file_id, None)

    def file_text(self, f: dict) -> str:
        if f["mimeType"] == DOC and f["id"] in self.state["docs"]:
            return plain_text(self.state["docs"][f["id"]])
        return ""
