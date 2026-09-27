"""Fake Google Tasks API v1 (tasklists.* and tasks.*).

Behaviour copied from the real account (tool_reference §4): new tasks go to
the top of their sibling group, due dates keep only the date part, a
date-only due is rejected, and clear() hides completed tasks.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .base import FakeRequest, api_uri, http_error

if TYPE_CHECKING:
    from ..workspace import Workspace

BASE = "https://tasks.googleapis.com"


def _bad_list(uri):
    return http_error(400, "Invalid task list ID", uri, errors=[{"message": "Invalid task list ID", "domain": "global", "reason": "invalid"}])


def _bad_task(uri):
    return http_error(400, "Invalid task ID", uri, errors=[{"message": "Invalid task ID", "domain": "global", "reason": "invalid"}])


def _bad_request(uri):
    msg = "Request contains an invalid argument."
    return http_error(400, msg, uri, errors=[{"message": msg, "domain": "global", "reason": "badRequest"}])


def _norm_due(value: str, uri: str) -> str:
    """Tasks keeps only the date of `due`, and rejects values without a time."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}T", value or ""):
        raise _bad_request(uri)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _bad_request(uri)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT00:00:00.000Z")


def _to_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class Tasks:
    def __init__(self, ws: "Workspace"):
        self.ws = ws
        self._http = None

    def tasklists(self):
        return _TaskLists(self.ws)

    def tasks(self):
        return _Tasks(self.ws)


class _TaskLists:
    def __init__(self, ws):
        self.ws = ws
        self.t = ws.state["tasks"]

    def _view(self, tl):
        return {
            "kind": "tasks#taskList",
            "id": tl["id"],
            "etag": f"\"{tl['id'][:8]}\"",
            "title": tl["title"],
            "updated": tl["updated"],
            "selfLink": f"https://www.googleapis.com/tasks/v1/users/@me/lists/{tl['id']}",
        }

    def _get(self, list_id, uri):
        if list_id not in self.t["lists"]:
            raise _bad_list(uri)
        return self.t["lists"][list_id]

    def list(self, maxResults=None, pageToken=None, **_):
        def run():
            lists = sorted(self.t["lists"].values(), key=lambda l: l.get("order", 0))
            return {"kind": "tasks#taskLists", "items": [self._view(l) for l in lists]}

        return FakeRequest(run, api_uri(BASE, "/tasks/v1/users/@me/lists", maxResults=maxResults))

    def get(self, tasklist=None, **_):
        uri = api_uri(BASE, f"/tasks/v1/users/@me/lists/{tasklist}")
        return FakeRequest(lambda: self._view(self._get(tasklist, uri)), uri)

    def insert(self, body=None, **_):
        def run():
            list_id = self.ws.ids.new("tasklist", 22, "b64")
            tl = {
                "id": list_id,
                "title": (body or {}).get("title", ""),
                "updated": self.ws.clock.rfc3339(self.ws.clock.stamp()),
                "order": len(self.t["lists"]),
                "origin": "agent",
            }
            self.t["lists"][list_id] = tl
            return self._view(tl)

        return FakeRequest(run, api_uri(BASE, "/tasks/v1/users/@me/lists"), "POST")

    def update(self, tasklist=None, body=None, **_):
        uri = api_uri(BASE, f"/tasks/v1/users/@me/lists/{tasklist}")

        def run():
            tl = self._get(tasklist, uri)
            tl["title"] = (body or {}).get("title", tl["title"])
            tl["updated"] = self.ws.clock.rfc3339(self.ws.clock.stamp())
            return self._view(tl)

        return FakeRequest(run, uri, "PUT")

    def delete(self, tasklist=None, **_):
        uri = api_uri(BASE, f"/tasks/v1/users/@me/lists/{tasklist}")

        def run():
            self._get(tasklist, uri)
            del self.t["lists"][tasklist]
            for task_id in [k for k, v in self.t["tasks"].items() if v["list"] == tasklist]:
                del self.t["tasks"][task_id]
            return ""

        return FakeRequest(run, uri, "DELETE")


class _Tasks:
    def __init__(self, ws):
        self.ws = ws
        self.t = ws.state["tasks"]

    # ---- helpers ---------------------------------------------------------
    def _list(self, list_id, uri):
        if list_id not in self.t["lists"]:
            raise _bad_list(uri)

    def _task(self, list_id, task_id, uri):
        self._list(list_id, uri)
        task = self.t["tasks"].get(task_id)
        if task is None or task["list"] != list_id or task.get("deleted"):
            raise _bad_task(uri)
        return task

    def _siblings(self, list_id, parent):
        return sorted(
            (t for t in self.t["tasks"].values() if t["list"] == list_id and t.get("parent") == parent and not t.get("deleted")),
            key=lambda t: t["order"],
        )

    def _place(self, task, parent, previous):
        """Put task among its siblings: after `previous`, or at the top."""
        sibs = [s for s in self._siblings(task["list"], parent) if s["id"] != task["id"]]
        if previous:
            idx = next((i for i, s in enumerate(sibs) if s["id"] == previous), None)
            if idx is not None:
                after = sibs[idx]["order"]
                before = sibs[idx + 1]["order"] if idx + 1 < len(sibs) else after + 2
                task["order"] = (after + before) / 2
                task["parent"] = parent
                return
        task["order"] = (sibs[0]["order"] - 1) if sibs else 0.0
        task["parent"] = parent

    def _view(self, task):
        sibs = self._siblings(task["list"], task.get("parent"))
        rank = next((i for i, s in enumerate(sibs) if s["id"] == task["id"]), 0)
        out = {
            "kind": "tasks#task",
            "id": task["id"],
            "etag": f"\"{task['id'][:8]}\"",
            "title": task.get("title", ""),
            "updated": task["updated"],
            "selfLink": f"https://www.googleapis.com/tasks/v1/lists/{task['list']}/tasks/{task['id']}",
            "position": f"{rank:020d}",
            "status": task.get("status", "needsAction"),
            "links": [],
            "webViewLink": f"https://tasks.google.com/task/{task['id'][:16]}?sa=6",
        }
        for key in ("parent", "notes", "due", "completed"):
            if task.get(key):
                out[key] = task[key]
        if task.get("hidden"):
            out["hidden"] = True
        return out

    def _ordered(self, list_id):
        """Hierarchy order: each top-level task followed by its subtasks.

        Hidden (cleared) tasks come after the visible ones, as on the real account.
        """
        out = []
        tops = self._siblings(list_id, None)
        tops = [t for t in tops if not t.get("hidden")] + [t for t in tops if t.get("hidden")]
        for top in tops:
            out.append(top)
            out.extend(self._siblings(list_id, top["id"]))
        return out

    # ---- API -------------------------------------------------------------
    def list(self, tasklist=None, maxResults=None, pageToken=None, showCompleted=True, showDeleted=False, showHidden=False, showAssigned=False, completedMax=None, completedMin=None, dueMax=None, dueMin=None, updatedMin=None, **_):
        uri = api_uri(BASE, f"/tasks/v1/lists/{tasklist}/tasks", maxResults=maxResults, showCompleted=showCompleted, showDeleted=showDeleted, showHidden=showHidden, showAssigned=showAssigned)

        def truthy(v):
            return v is True or str(v).lower() == "true"

        def run():
            self._list(tasklist, uri)
            items = []
            for task in self._ordered(tasklist):
                if task.get("hidden") and not truthy(showHidden):
                    continue
                if task.get("status") == "completed" and not truthy(showCompleted if showCompleted is not None else True):
                    continue
                if completedMin and (not task.get("completed") or _to_utc(task["completed"]) < _to_utc(completedMin)):
                    continue
                if completedMax and (not task.get("completed") or _to_utc(task["completed"]) > _to_utc(completedMax)):
                    continue
                if dueMin and (not task.get("due") or _to_utc(task["due"]) < _to_utc(dueMin)):
                    continue
                if dueMax and (not task.get("due") or _to_utc(task["due"]) > _to_utc(dueMax)):
                    continue
                if updatedMin and _to_utc(task["updated"]) < _to_utc(updatedMin):
                    continue
                items.append(self._view(task))
            size = int(maxResults) if maxResults else 20
            start = int(pageToken) if pageToken else 0
            out = {"kind": "tasks#tasks", "items": items[start : start + size]}
            if start + size < len(items):
                out["nextPageToken"] = str(start + size)
            return out

        return FakeRequest(run, uri)

    def get(self, tasklist=None, task=None, **_):
        uri = api_uri(BASE, f"/tasks/v1/lists/{tasklist}/tasks/{task}")
        return FakeRequest(lambda: self._view(self._task(tasklist, task, uri)), uri)

    def insert(self, tasklist=None, body=None, parent=None, previous=None, **_):
        uri = api_uri(BASE, f"/tasks/v1/lists/{tasklist}/tasks", parent=parent, previous=previous)

        def run():
            self._list(tasklist, uri)
            body_ = body or {}
            if parent and (parent not in self.t["tasks"] or self.t["tasks"][parent]["list"] != tasklist):
                raise _bad_task(uri)
            task = {
                "id": self.ws.ids.new("task", 22, "b64"),
                "list": tasklist,
                "title": body_.get("title", ""),
                "status": body_.get("status", "needsAction"),
                "updated": self.ws.clock.rfc3339(self.ws.clock.stamp()),
                "origin": "agent",
            }
            if body_.get("notes"):
                task["notes"] = body_["notes"]
            if body_.get("due"):
                task["due"] = _norm_due(body_["due"], uri)
            if task["status"] == "completed":
                task["completed"] = task["updated"]
            self._place(task, parent, previous)
            self.t["tasks"][task["id"]] = task
            return self._view(task)

        return FakeRequest(run, uri, "POST")

    def update(self, tasklist=None, task=None, body=None, **_):
        uri = api_uri(BASE, f"/tasks/v1/lists/{tasklist}/tasks/{task}")

        def run():
            item = self._task(tasklist, task, uri)
            body_ = body or {}
            due = _norm_due(body_["due"], uri) if body_.get("due") else None
            if "title" in body_:
                item["title"] = body_["title"]
            if "notes" in body_:
                if body_["notes"]:
                    item["notes"] = body_["notes"]
                else:
                    item.pop("notes", None)
            if due:
                item["due"] = due
            elif "due" in body_ and not body_["due"]:
                item.pop("due", None)
            item["updated"] = self.ws.clock.rfc3339(self.ws.clock.stamp())
            if "status" in body_:
                if body_["status"] == "completed" and item.get("status") != "completed":
                    item["completed"] = item["updated"]
                if body_["status"] == "needsAction":
                    item.pop("completed", None)
                    item.pop("hidden", None)
                item["status"] = body_["status"]
            return self._view(item)

        return FakeRequest(run, uri, "PUT")

    def delete(self, tasklist=None, task=None, **_):
        uri = api_uri(BASE, f"/tasks/v1/lists/{tasklist}/tasks/{task}")

        def run():
            self._task(tasklist, task, uri)
            doomed = [task] + [t["id"] for t in self.t["tasks"].values() if t.get("parent") == task]
            for task_id in doomed:
                del self.t["tasks"][task_id]
            return ""

        return FakeRequest(run, uri, "DELETE")

    def move(self, tasklist=None, task=None, parent=None, previous=None, destinationTasklist=None, **_):
        uri = api_uri(BASE, f"/tasks/v1/lists/{tasklist}/tasks/{task}/move", parent=parent, previous=previous, destinationTasklist=destinationTasklist)

        def run():
            item = self._task(tasklist, task, uri)
            target = destinationTasklist or tasklist
            if destinationTasklist:
                self._list(destinationTasklist, uri)
            if parent:
                p = self.t["tasks"].get(parent)
                if p is None or p["list"] != target:
                    raise _bad_task(uri)
            children = [t for t in self.t["tasks"].values() if t.get("parent") == task]
            item["list"] = target
            for child in children:
                child["list"] = target
            self._place(item, parent, previous)
            item["updated"] = self.ws.clock.rfc3339(self.ws.clock.stamp())
            return self._view(item)

        return FakeRequest(run, uri, "POST")

    def clear(self, tasklist=None, **_):
        uri = api_uri(BASE, f"/tasks/v1/lists/{tasklist}/clear")

        def run():
            self._list(tasklist, uri)
            # Cleared tasks are hidden and move to the bottom (real positions do).
            bottom = max((t["order"] for t in self.t["tasks"].values() if t["list"] == tasklist), default=0)
            for item in sorted(self.t["tasks"].values(), key=lambda t: t["order"]):
                if item["list"] == tasklist and item.get("status") == "completed" and not item.get("hidden"):
                    item["hidden"] = True
                    bottom += 1
                    item["order"] = bottom
            return ""

        return FakeRequest(run, uri, "POST")
