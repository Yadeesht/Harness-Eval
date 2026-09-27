"""Build the lab's starting workspace from world_data.py (+ deterministic filler).

    .venv/Scripts/python.exe eval/seed/build_seed.py

Writes eval/seed/seed.json (the workspace state every run starts from),
eval/seed/seed_index.json (world ids -> generated ids, for graders only) and
eval/seed/seed.sha256. Building twice gives byte-identical output.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import world_data as W  # noqa: E402
from filler import filler_emails, filler_events, notification_emails  # noqa: E402
from lab.fake.base import IST, Clock, make_id  # noqa: E402
from lab.fake.docs import build_body  # noqa: E402
from lab.fake import sheets_calc as calc  # noqa: E402
from lab.workspace import Workspace, empty_state  # noqa: E402

OUT = HERE / "seed.json"
INDEX = HERE / "seed_index.json"


def ist(when: str) -> datetime:
    return datetime.strptime(when, "%Y-%m-%d %H:%M").replace(tzinfo=IST)


def rfc(dt: datetime) -> str:
    return Clock.rfc3339(dt)


def _tz(offset: str) -> timezone:
    sign = 1 if offset[0] == "+" else -1
    h, m = map(int, offset[1:].split(":"))
    return timezone(sign * timedelta(hours=h, minutes=m))


# ---------------------------------------------------------------------------
# Gmail
# ---------------------------------------------------------------------------


def add_gmail(ws: Workspace, index: dict, emails: list[dict]) -> None:
    g = ws.state["gmail"]
    label_ids = {l["name"]: l["id"] for l in g["labels"].values()}
    threads = index.setdefault("_threads", {})
    for m in emails:
        msg_id = make_id("msg", m["wid"], 16)
        thread_key = m.get("thread") or m["wid"]
        thread_id = threads.setdefault(thread_key, msg_id)
        labels = []
        if m["inbox"]:
            labels.append("INBOX")
        if m["unread"]:
            labels.append("UNREAD")
        if m["sent"]:
            labels.append("SENT")
        if not m["sent"] or m["inbox"]:
            labels.append("CATEGORY_UPDATES" if m["category"] == "updates" else "CATEGORY_PERSONAL")
        labels += [label_ids[name] for name in m["labels"]]
        when = ist(m["when"])
        g["messages"][msg_id] = {
            "id": msg_id,
            "threadId": thread_id,
            "labelIds": labels,
            "internalDate": when.isoformat(),
            "date_header": format_datetime(when.astimezone(_tz(m["tz"]))),
            "from": m["from"],
            "to": ", ".join(m["to"]),
            "cc": ", ".join(m["cc"]),
            "subject": m["subject"],
            "body": m["body"],
            "origin": "seed",
            "wid": m["wid"],
        }
        index["gmail"][m["wid"]] = msg_id


def build_gmail(ws: Workspace, index: dict) -> None:
    g = ws.state["gmail"]
    for n, name in enumerate(W.USER_LABELS, 1):
        g["labels"][f"Label_{n}"] = {"id": f"Label_{n}", "name": name, "type": "user", "labelListVisibility": "labelShow", "messageListVisibility": "show"}
    label_ids = {l["name"]: l["id"] for l in g["labels"].values()}
    for wid, criteria, add, remove in W.FILTERS:
        fid = make_id("filter", wid, 40, "b64")
        g["filters"][fid] = {"id": fid, "criteria": criteria, "action": {"addLabelIds": [label_ids[a] for a in add], "removeLabelIds": remove}}
        index["filters"][wid] = fid
    add_gmail(ws, index, W.EMAILS + notification_emails() + filler_emails())


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------


def _email_of(guest: str) -> str:
    return guest[1:] if guest.startswith("@") else W.addr(guest)


def _timed(day: str, hhmm: str) -> dict:
    return {"dateTime": f"{day}T{hhmm}:00+05:30", "timeZone": "Asia/Kolkata"}


def _event(ev_id: str, spec: dict, organizer_email: str, home: str) -> dict:
    guests = spec["guests"]
    attendees = []
    if guests:
        attendees.append({"email": organizer_email, "responseStatus": "accepted", "organizer": True})
        for guest, status in guests.items():
            email = _email_of(guest)
            if email.lower() != organizer_email.lower():
                attendees.append({"email": email, "responseStatus": status})
    if spec.get("start"):
        start, end = _timed(spec["date"], spec["start"]), _timed(spec["date"], spec["end"])
    else:
        start, end = {"date": spec["date"]}, {"date": spec["all_day_end"]}
    created = rfc(datetime.fromisoformat(spec["date"]).replace(tzinfo=IST) - timedelta(days=14))
    out = {
        "id": ev_id, "home": home, "organizer": organizer_email, "summary": spec["title"],
        "start": start, "end": end, "created": created, "updated": created, "origin": "seed", "wid": spec["wid"],
    }
    if attendees:
        out["attendees"] = attendees
    for key in ("description", "location", "transparency"):
        if spec.get(key):
            out[key] = spec[key]
    return out


def build_calendar(ws: Workspace, index: dict) -> None:
    c = ws.state["calendar"]
    c["calendars"][W.USER["email"]]["summary"] = W.USER["email"]
    c["calendars"][W.INTERVIEWS_CAL] = {"summary": "Interviews", "accessRole": "writer", "timeZone": "Asia/Kolkata"}
    c["calendars"][W.HOLIDAYS_CAL] = {"summary": "Kestrel Holidays (India)", "description": "Company holidays, India offices", "accessRole": "reader", "timeZone": "Asia/Kolkata"}
    for local in W.COLLEAGUE_CALENDARS:
        c["calendars"][W.addr(local)] = {"summary": W.NAME[local], "accessRole": "reader", "timeZone": "Asia/Kolkata"}

    def add(ev_id, spec, organizer_email, home):
        c["events"][ev_id] = _event(ev_id, spec, organizer_email, home)
        index["events"][spec["wid"]] = ev_id

    for spec in W.EVENTS + filler_events():
        org = W.addr(spec["organizer"])
        add(make_id("event", spec["wid"], 26, "b32hex"), spec, org, org)

    # Recurring series as instances: <series id>_<yyyymmdd>
    lo, hi = (date.fromisoformat(d) for d in W.SERIES_RANGE)
    holidays = {d for d, _ in W.HOLIDAYS} | set(W.OFFSITE_DAYS)
    for wid, title, weekdays, start, end, organizer, guests, skips, moves in W.SERIES:
        series_id = make_id("series", wid, 26, "b32hex")
        org = W.addr(organizer)
        day = lo
        while day <= hi:
            iso = day.isoformat()
            if day.weekday() in weekdays and iso not in holidays and iso not in skips or iso in moves:
                on, s, e = moves.get(iso, (iso, start, end))
                spec = W.ev(f"{wid}_{iso}", on, s, e, title, organizer, guests)
                ev_id = f"{series_id}_{iso.replace('-', '')}"
                add(ev_id, spec, org, org)
                c["events"][ev_id]["recurringEventId"] = series_id
            day += timedelta(days=1)
    for iso in W.FARAH_1ON1_DATES:
        spec = W.ev(f"oo_farah_{iso}", iso, "12:00", "13:00", "1:1 Farah / Yadeesh", "farah.khan", {"yadeesh": "accepted"})
        series_id = make_id("series", "oo_farah", 26, "b32hex")
        ev_id = f"{series_id}_{iso.replace('-', '')}"
        add(ev_id, spec, W.addr("farah.khan"), W.addr("farah.khan"))
        c["events"][ev_id]["recurringEventId"] = series_id

    for wid, day, start, end, title, candidate in W.INTERVIEWS:
        spec = W.ev(wid, day, start, end, title, "yadeesh", {"yadeesh": "accepted", "@" + candidate: "accepted"})
        e = _event(make_id("event", wid, 26, "b32hex"), spec, "recruiting@" + W.DOMAIN, W.INTERVIEWS_CAL)
        e["attendees"] = [a for a in e["attendees"] if not a.get("organizer")]
        e["attendees"][0]["responseStatus"] = "accepted"
        c["events"][e["id"]] = e
        index["events"][wid] = e["id"]

    for iso, title in W.HOLIDAYS:
        wid = f"hol_{iso}"
        end = (date.fromisoformat(iso) + timedelta(days=1)).isoformat()
        spec = W.ev(wid, iso, None, None, title, "yadeesh", all_day_end=end, transparency="transparent")
        e = _event(make_id("event", wid, 26, "b32hex"), spec, W.HOLIDAYS_CAL, W.HOLIDAYS_CAL)
        c["events"][e["id"]] = e
        index["events"][wid] = e["id"]


# ---------------------------------------------------------------------------
# Drive: docs, sheets, comments
# ---------------------------------------------------------------------------


def _comment_records(ws, specs, index, file_wid):
    out = []
    for cid, author, content, resolved, replies, created in specs:
        comment_id = "AAAB" + make_id("comment", f"{file_wid}:{cid}", 7, "b64")
        index["comments"][f"{file_wid}:{cid}"] = comment_id
        record = {
            "id": comment_id, "content": content, "author": {"displayName": author},
            "createdTime": created, "modifiedTime": created, "resolved": resolved, "replies": [], "origin": "seed",
        }
        for n, (reply_author, reply_text) in enumerate(replies):
            record["replies"].append({
                "id": "AAAB" + make_id("reply", f"{file_wid}:{cid}:{n}", 7, "b64"),
                "content": reply_text, "author": {"displayName": reply_author},
                "createdTime": created, "modifiedTime": created, "origin": "seed",
                **({"action": "resolve"} if resolved and n == len(replies) - 1 else {}),
            })
        out.append(record)
    return out


def build_docs(ws: Workspace, index: dict) -> None:
    for wid, title, modified, blocks in W.DOCS:
        doc_id = make_id("doc", wid, 44, "b64")
        stamp = rfc(datetime.fromisoformat(modified).replace(tzinfo=IST, hour=11))
        ws.add_doc(doc_id, title, build_body(blocks), origin="seed", when=stamp)
        index["docs"][wid] = doc_id
        if wid in W.DOC_COMMENTS:
            ws.state["drive"]["comments"][doc_id] = _comment_records(ws, W.DOC_COMMENTS[wid], index, wid)


def _grid(tab: dict, a1: str) -> dict:
    r0, c0, r1, c1 = calc.parse_a1(a1)
    return {"sheetId": tab["sheetId"], "startRowIndex": r0, "endRowIndex": r1 + 1, "startColumnIndex": c0, "endColumnIndex": c1 + 1}


def build_sheets(ws: Workspace, index: dict) -> None:
    from app_tools.tools.google.gsheet_tools import _build_boolean_rule

    for spec in W.SHEETS:
        sid = make_id("sheet", spec["wid"], 44, "b64")
        stamp = rfc(datetime.fromisoformat(spec["modified"]).replace(tzinfo=IST, hour=12))
        book = ws.add_sheet(sid, spec["title"], [{"title": t["title"]} for t in spec["tabs"]], origin="seed", when=stamp)
        index["sheets"][spec["wid"]] = sid
        for tab_spec, tab in zip(spec["tabs"], book["tabs"]):
            for r, row in enumerate(tab_spec["rows"]):
                for col, value in enumerate(row):
                    cell = calc.parse_input(value, raw=False)
                    if cell:
                        tab["cells"][f"{r},{col}"] = cell
            for a1, fmt in tab_spec.get("formats", []):
                grid = _grid(tab, a1)
                tab["formats"].append({"range": {k: v for k, v in grid.items() if k != "sheetId"}, "format": {"numberFormat": fmt}})
            for a1, kind, values, bg, fg in tab_spec.get("rules", []):
                rule, _ = _build_boolean_rule([_grid(tab, a1)], kind, values, bg, fg)
                tab["conditionalFormats"].append(rule)
        if spec["wid"] in W.SHEET_COMMENTS:
            ws.state["drive"]["comments"][sid] = _comment_records(ws, W.SHEET_COMMENTS[spec["wid"]], index, spec["wid"])


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


def build_tasks(ws: Workspace, index: dict) -> None:
    t = ws.state["tasks"]
    for order, (list_wid, title, items) in enumerate(W.TASK_LISTS):
        list_id = make_id("tasklist", list_wid, 22, "b64")
        t["lists"][list_id] = {"id": list_id, "title": title, "updated": "2026-10-06T05:00:00.000Z", "order": order, "origin": "seed"}
        index["tasklists"][list_wid] = list_id
        for pos, (wid, task_title, due, status, notes, completed) in enumerate(items):
            task_id = make_id("task", wid, 22, "b64")
            task = {
                "id": task_id, "list": list_id, "title": task_title, "status": status,
                "updated": "2026-10-06T05:00:00.000Z", "order": float(pos), "origin": "seed", "wid": wid,
            }
            if due:
                task["due"] = f"{due}T00:00:00.000Z"
            if notes:
                task["notes"] = notes
            if completed:
                task["completed"] = rfc(ist(completed))
                task["updated"] = task["completed"]
            t["tasks"][task_id] = task
            index["tasks"][wid] = task_id


# ---------------------------------------------------------------------------


def build_state() -> tuple[dict, dict]:
    ws = Workspace(empty_state(W.NOW, W.USER["email"], W.USER["name"]), namespace="seed")
    index = {"gmail": {}, "filters": {}, "events": {}, "docs": {}, "sheets": {}, "comments": {}, "tasklists": {}, "tasks": {}}
    build_gmail(ws, index)
    build_calendar(ws, index)
    build_docs(ws, index)
    build_sheets(ws, index)
    build_tasks(ws, index)
    index.pop("_threads", None)
    return ws.state, index


def apply_additions(ws: Workspace, additions: dict, index: dict) -> None:
    """Add a task's seed_additions (world.md §9) to a freshly loaded workspace.

    `additions` is the task file's field, e.g. {"emails": ["pn_dinner"]}; the items
    themselves live in world_data.SEED_ADDITIONS.
    """
    unknown = set(additions) - set(W.SEED_ADDITIONS)
    if unknown:
        raise ValueError(f"unknown seed_additions kinds: {sorted(unknown)}")
    extra = {kind: [W.SEED_ADDITIONS[kind][wid] for wid in wids] for kind, wids in additions.items()}
    if not extra:
        return
    threads = {}
    for wid, msg_id in index["gmail"].items():
        m = ws.state["gmail"]["messages"].get(msg_id)
        if m:
            threads[m.get("wid")] = m["threadId"]
    lookup = {spec["thread"]: None for spec in extra.get("emails", []) if spec.get("thread")}
    for key in lookup:
        seed_msg = next((m for m in W.EMAILS if m.get("thread") == key), None)
        if seed_msg:
            lookup[key] = index["gmail"][seed_msg["wid"]]
    sub_index = {"gmail": index["gmail"], "_threads": {k: ws.state["gmail"]["messages"][v]["threadId"] for k, v in lookup.items() if v}}
    add_gmail(ws, sub_index, extra.get("emails", []))


def main() -> int:
    state, index = build_state()
    text = json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True)
    OUT.write_text(text, encoding="utf-8")
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (HERE / "seed.sha256").write_text(digest + "\n", encoding="utf-8")
    g, c = state["gmail"], state["calendar"]
    print(f"seed.json: {len(text) // 1024} KB, sha256 {digest[:16]}")
    print(f"  mail {len(g['messages'])}, labels {len(g['labels'])}, filters {len(g['filters'])}")
    print(f"  calendars {len(c['calendars'])}, events {len(c['events'])}")
    print(f"  docs {len(state['docs'])}, sheets {len(state['sheets'])}, task lists {len(state['tasks']['lists'])}, tasks {len(state['tasks']['tasks'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
