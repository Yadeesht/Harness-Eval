"""Every change between the starting workspace and the final one.

Each change is a dict with a unique "key" (kind:id...). Grader checks claim the
keys they verified; anything left unclaimed is an unexpected change and fails
the task ("nothing else changed", AGENTS.md grading rules).

Read status (the UNREAD label) is reported separately, because read_email
marks mail as read; it only counts when a task opts in (strict_read).
"""

from __future__ import annotations

from typing import Any

IGNORED_EVENT_FIELDS = {"updated"}
IGNORED_TASK_FIELDS = {"updated", "order"}


def _change(kind: str, obj_id: str, **extra) -> dict:
    return {"key": f"{kind}:{obj_id}", "kind": kind, "id": obj_id, **extra}


def _dict_diff(before: dict, after: dict, ignore: set) -> list[str]:
    keys = (set(before) | set(after)) - ignore
    return sorted(k for k in keys if before.get(k) != after.get(k))


def diff(initial: dict, final: dict, strict_read: bool = False) -> list[dict]:
    out: list[dict] = []

    # ---- Gmail -------------------------------------------------------------
    g0, g1 = initial["gmail"], final["gmail"]
    for mid in g1["messages"].keys() - g0["messages"].keys():
        out.append(_change("gmail.message.new", mid, message=g1["messages"][mid]))
    for mid in g0["messages"].keys() - g1["messages"].keys():
        out.append(_change("gmail.message.deleted", mid, message=g0["messages"][mid]))
    for mid in g0["messages"].keys() & g1["messages"].keys():
        before, after = set(g0["messages"][mid]["labelIds"]), set(g1["messages"][mid]["labelIds"])
        added, removed = sorted(after - before), sorted(before - after)
        if not strict_read:
            added = [l for l in added if l != "UNREAD"]
            removed = [l for l in removed if l != "UNREAD"]
        if added or removed:
            out.append(_change("gmail.message.labels", mid, added=added, removed=removed, message=g1["messages"][mid]))
    for did in g1["drafts"].keys() - g0["drafts"].keys():
        out.append(_change("gmail.draft.new", did, draft=g1["drafts"][did]))
    for did in g0["drafts"].keys() - g1["drafts"].keys():
        out.append(_change("gmail.draft.deleted", did, draft=g0["drafts"][did]))
    for lid in g1["labels"].keys() - g0["labels"].keys():
        out.append(_change("gmail.label.new", lid, label=g1["labels"][lid]))
    for lid in g0["labels"].keys() - g1["labels"].keys():
        out.append(_change("gmail.label.deleted", lid, label=g0["labels"][lid]))
    for lid in g0["labels"].keys() & g1["labels"].keys():
        if g0["labels"][lid]["name"] != g1["labels"][lid]["name"]:
            out.append(_change("gmail.label.renamed", lid, before=g0["labels"][lid]["name"], after=g1["labels"][lid]["name"]))
    for fid in g1["filters"].keys() - g0["filters"].keys():
        out.append(_change("gmail.filter.new", fid, filter=g1["filters"][fid]))
    for fid in g0["filters"].keys() - g1["filters"].keys():
        out.append(_change("gmail.filter.deleted", fid, filter=g0["filters"][fid]))

    # ---- Calendar ------------------------------------------------------------
    e0, e1 = initial["calendar"]["events"], final["calendar"]["events"]
    for eid in e1.keys() - e0.keys():
        out.append(_change("calendar.event.new", eid, event=e1[eid]))
    for eid in e0.keys() - e1.keys():
        out.append(_change("calendar.event.deleted", eid, event=e0[eid]))
    for eid in e0.keys() & e1.keys():
        fields = _dict_diff(e0[eid], e1[eid], IGNORED_EVENT_FIELDS)
        if fields:
            out.append(_change("calendar.event.changed", eid, fields=fields, before=e0[eid], event=e1[eid]))

    # ---- Tasks ---------------------------------------------------------------
    t0, t1 = initial["tasks"], final["tasks"]
    for lid in t1["lists"].keys() - t0["lists"].keys():
        out.append(_change("tasks.list.new", lid, tasklist=t1["lists"][lid]))
    for lid in t0["lists"].keys() - t1["lists"].keys():
        out.append(_change("tasks.list.deleted", lid, tasklist=t0["lists"][lid]))
    for lid in t0["lists"].keys() & t1["lists"].keys():
        if t0["lists"][lid]["title"] != t1["lists"][lid]["title"]:
            out.append(_change("tasks.list.renamed", lid, before=t0["lists"][lid]["title"], after=t1["lists"][lid]["title"]))
    for tid in t1["tasks"].keys() - t0["tasks"].keys():
        out.append(_change("tasks.task.new", tid, task=t1["tasks"][tid]))
    for tid in t0["tasks"].keys() - t1["tasks"].keys():
        out.append(_change("tasks.task.deleted", tid, task=t0["tasks"][tid]))
    for tid in t0["tasks"].keys() & t1["tasks"].keys():
        fields = _dict_diff(t0["tasks"][tid], t1["tasks"][tid], IGNORED_TASK_FIELDS)
        if fields:
            out.append(_change("tasks.task.changed", tid, fields=fields, before=t0["tasks"][tid], task=t1["tasks"][tid]))

    # ---- Drive, docs, sheets, comments ----------------------------------------
    f0, f1 = initial["drive"]["files"], final["drive"]["files"]
    for fid in f1.keys() - f0.keys():
        out.append(_change("drive.file.new", fid, file=f1[fid]))
    for fid in f0.keys() - f1.keys():
        out.append(_change("drive.file.deleted", fid, file=f0[fid]))
    for fid in f0.keys() & f1.keys():
        fields = _dict_diff(f0[fid], f1[fid], {"modifiedTime"})
        if fields:
            out.append(_change("drive.file.changed", fid, fields=fields, file=f1[fid]))
    for did in initial["docs"].keys() & final["docs"].keys():
        a, b = initial["docs"][did], final["docs"][did]
        if {k: v for k, v in a.items() if k != "revision"} != {k: v for k, v in b.items() if k != "revision"}:
            out.append(_change("docs.doc.changed", did, before=a, doc=b))
    for sid in initial["sheets"].keys() & final["sheets"].keys():
        if initial["sheets"][sid] != final["sheets"][sid]:
            out.append(_change("sheets.book.changed", sid, before=initial["sheets"][sid], book=final["sheets"][sid]))
    c0, c1 = initial["drive"]["comments"], final["drive"]["comments"]
    for fid in set(c0) | set(c1):
        before = {c["id"]: c for c in c0.get(fid, [])}
        after = {c["id"]: c for c in c1.get(fid, [])}
        for cid in after.keys() - before.keys():
            out.append(_change("drive.comment.new", f"{fid}:{cid}", file_id=fid, comment=after[cid]))
        for cid in before.keys() - after.keys():
            out.append(_change("drive.comment.deleted", f"{fid}:{cid}", file_id=fid, comment=before[cid]))
        for cid in before.keys() & after.keys():
            if before[cid] != after[cid]:
                out.append(_change("drive.comment.changed", f"{fid}:{cid}", file_id=fid, before=before[cid], comment=after[cid]))
    return out


def read_changes(initial: dict, final: dict) -> dict[str, tuple[bool, bool]]:
    """{message id: (was unread, is unread)} for messages whose read state changed."""
    out = {}
    g0, g1 = initial["gmail"]["messages"], final["gmail"]["messages"]
    for mid in g0.keys() & g1.keys():
        a, b = "UNREAD" in g0[mid]["labelIds"], "UNREAD" in g1[mid]["labelIds"]
        if a != b:
            out[mid] = (a, b)
    return out


def summarize(change: dict) -> str:
    kind = change["kind"]
    obj: Any = change.get("event") or change.get("message") or change.get("task") or change.get("file") or change.get("draft") or change.get("label") or {}
    title = obj.get("summary") or obj.get("subject") or obj.get("title") or obj.get("name") or ""
    extra = f" fields={change['fields']}" if "fields" in change else ""
    return f"{kind} {change['id']} {title!r}{extra}"
