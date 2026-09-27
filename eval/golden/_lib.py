"""Helpers for golden-path scripts: parse tool results the way an agent reads them.

Golden paths get every ID from tool output (never from the seed index), which
proves the information is discoverable through the tools.
"""

from __future__ import annotations

import json
import re


def js(text: str):
    """A tool result as JSON (most tools return dicts rendered as JSON)."""
    return json.loads(text)


def pick(items: list[dict], **want) -> dict:
    """The one item whose fields contain each wanted substring (case-insensitive)."""
    hits = [i for i in items if all(v.lower() in str(i.get(k, "")).lower() for k, v in want.items())]
    if len(hits) != 1:
        raise AssertionError(f"expected one match for {want}, got {len(hits)}")
    return hits[0]


def grab(pattern: str, text: str, group: int = 1) -> str:
    m = re.search(pattern, text, re.S)
    if not m:
        raise AssertionError(f"pattern {pattern!r} not found")
    return m.group(group)


def grab_all(pattern: str, text: str) -> list:
    return re.findall(pattern, text, re.S)


def sheet_rows(text: str) -> list[list[str]]:
    """Rows from a read_sheet_values result ("Row  3: ['a', 'b']" lines)."""
    import ast

    message = js(text)["message"]
    return [ast.literal_eval(m) for m in re.findall(r"^Row\s+\d+: (\[.*\])$", message, re.M)]


def task_items(text: str) -> list[dict]:
    """Tasks from a list_tasks result: [{title, id, status, due, notes, parent}]."""
    items = []
    for block in re.split(r"\n(?=\s*- .+ \(ID: )", text):
        m = re.search(r"- (.+) \(ID: ([^)]+)\)", block)
        if not m:
            continue
        item = {"title": m.group(1), "id": m.group(2)}
        for key in ("Status", "Due", "Notes", "Parent"):
            f = re.search(rf"^\s*{key}: (.*)$", block, re.M)
            item[key.lower()] = f.group(1).strip() if f else None
        items.append(item)
    return items


def events(text: str) -> list[dict]:
    """Events from a get_events result: [{summary, start, end, id, attendees{email: status}, organizer, description}]."""
    message = js(text)["message"]
    out = []
    for block in re.split(r"\n(?=- \")", message):
        m = re.search(r'- "(.*)" \(Starts: ([^,]+), Ends: ([^)]+)\)', block)
        if not m:
            continue
        ev = {"summary": m.group(1), "start": m.group(2), "end": m.group(3), "id": grab(r"ID: (\S+)", block), "attendees": {}, "organizer": None}
        d = re.search(r"Description: (.*)", block)
        ev["description"] = d.group(1) if d else None
        details = re.search(r"Attendee Details: (.*?)\n  ID:", block, re.S)
        if details:
            for email, status, org in re.findall(r"([\w.+-]+@[\w.-]+): (\w+)( \(organizer\))?", details.group(1)):
                ev["attendees"][email] = status
                if org:
                    ev["organizer"] = email
        out.append(ev)
    return out


def comments(text: str) -> list[dict]:
    """Comments from read_*_comments: [{id, author, resolved, content}] (replies ignored)."""
    out = []
    for block in re.split(r"\n\n(?=Comment ID: )", text):
        m = re.search(r"Comment ID: (\S+)\nAuthor: (.+)\nCreated: (.+)\nContent: (.*)", block)
        if m:
            out.append({"id": m.group(1), "author": m.group(2).strip(), "resolved": "[RESOLVED]" in m.group(3), "content": m.group(4)})
    return out


def busy(evs: list[dict], email: str) -> list[tuple]:
    """(start, end) datetimes when `email` is busy in a detailed get_events listing of their
    calendar: events they haven't declined, and their own events without guests."""
    from datetime import datetime

    out = []
    for e in evs:
        if "T" not in e["start"]:
            continue
        status = e["attendees"].get(email, "accepted" if not e["attendees"] else None)
        if status and status != "declined":
            out.append((datetime.fromisoformat(e["start"]), datetime.fromisoformat(e["end"])))
    return out


def free(intervals: list[tuple], start, end) -> bool:
    return not any(s < end and start < e for s, e in intervals)


def hhmm(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def open_items(latest: str) -> dict[str, list[str]]:
    """Owner -> open items, from the text of a weekly sync doc (the 28 Sep format)."""
    groups: dict[str, list[str]] = {}
    for line in latest.split("\n"):
        m = re.match(r"(.+) \((.+)\) — (DONE|open)$", line)  # "Item (Owner) — status"
        if m and m.group(3) == "open":
            groups.setdefault(m.group(2), []).append(m.group(1))
        m = re.match(r"(.+) — reassigned from .+ to (.+) — open$", line)
        if m:
            groups.setdefault(m.group(2), []).append(m.group(1))
        m = re.match(r"([A-Z]\w+ [A-Z]\w*): (.+?)(?: — (DONE|due .+))?$", line)  # "Owner: item — due/DONE"
        if m and m.group(1) not in ("Platform Weekly",) and m.group(3) != "DONE" and not line.startswith(("Attendees", "Notes")):
            item = m.group(2) + (f" (due {m.group(3)[4:]})" if m.group(3) else "")
            groups.setdefault(m.group(1), []).append(item)
    return groups
