"""Grade one run: state checks first, then "nothing else changed", then forbidden calls.

    result = grade(task, initial_state, final_state, calls, final_message, index)

A task's expect block:
  "state":       list of checks (below); each verifies part of the end state and
                 claims the changes it covers
  "allow":       change kinds that may appear unclaimed (e.g. "gmail.label.new")
  "strict_read": true when read/unread status is part of the task (em_06)
  "forbidden":   [{"tool": name, "args": {k: v}}]: any successful matching call fails
  "judge":       rubric for the LLM judge (ambiguous/impossible tasks); grade()
                 reports it as pending, the runner calls the judge

Checks (extend here as tasks need them):
  calendar  event, event_deleted
  gmail     sent, draft, mail (label/inbox/read state of seeded mail), label
  tasks     task (seeded task end state), task_deleted, tasklist (new list + its tasks)
  docs      doc (seeded doc: text, bold lines, header/footer), doc_new
  drive     file_new
  sheets    book (tab grids, unordered rows, label/number pairs; other tabs unchanged)
  message   final_message (anchors in the agent's last message)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from .diff import diff, summarize
from .normalize import matches, norm, same

CHECKS: dict[str, Callable] = {}


def check(name: str):
    def register(fn):
        CHECKS[name] = fn
        return fn

    return register


class Ctx:
    def __init__(self, task, initial, final, calls, final_message, index):
        self.task = task
        self.initial = initial
        self.final = final
        self.calls = calls
        self.final_message = final_message or ""
        self.index = index
        self.changes = diff(initial, final, strict_read=task["expect"].get("strict_read", False))
        self.claimed: set[str] = set()

    def ids(self, kind: str, wid: str) -> str:
        return self.index[kind][wid]

    def changes_of(self, *kinds) -> list[dict]:
        return [c for c in self.changes if c["kind"] in kinds]

    def claim(self, kind: str, obj_id: str) -> None:
        for c in self.changes:
            if c["kind"] == kind and c["id"] == obj_id:
                self.claimed.add(c["key"])


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------


def _busy_for(ev: dict, email: str) -> bool:
    """True when the event blocks `email`: on their calendar, not declined, not transparent."""
    if ev.get("transparency") == "transparent" or "dateTime" not in ev["start"]:
        return False
    email = email.lower()
    for a in ev.get("attendees", []):
        if a["email"].lower() == email:
            return a.get("responseStatus") != "declined"
    return ev.get("home", "").lower() == email


def _conflicts(state: dict, email: str, start: datetime, end: datetime, skip: set) -> list[dict]:
    out = []
    for ev in state["calendar"]["events"].values():
        if ev["id"] in skip or not _busy_for(ev, email):
            continue
        if _dt(ev["start"]["dateTime"]) < end and start < _dt(ev["end"]["dateTime"]):
            out.append(ev)
    return out


def _event_ok(ctx: Ctx, ev: dict, spec: dict) -> list[str]:
    problems = []
    if "summary" in spec and not same(ev.get("summary", ""), spec["summary"]):
        problems.append(f"summary {ev.get('summary')!r} != {spec['summary']!r}")
    for key in ("start", "end"):
        if key in spec:
            got = ev[key].get("dateTime") or ev[key].get("date")
            if got != spec[key]:
                problems.append(f"{key} {got} != {spec[key]}")
    if "start_in" in spec and ev["start"].get("dateTime") not in spec["start_in"]:
        problems.append(f"start {ev['start'].get('dateTime')} not in {spec['start_in']}")
    for wid in spec.get("description_has_doc", []):
        if ctx.ids("docs", wid) not in ev.get("description", ""):
            problems.append(f"description lacks the link to {wid}")
    for wid in spec.get("description_lacks_doc", []):
        if ctx.ids("docs", wid) in ev.get("description", ""):
            problems.append(f"description links {wid}")
    attendees = {a["email"].lower() for a in ev.get("attendees", [])}
    for email in spec.get("attendees_include", []):
        if email.lower() not in attendees:
            problems.append(f"missing attendee {email}")
    for email in spec.get("attendees_exclude", []):
        if email.lower() in attendees:
            problems.append(f"unwanted attendee {email}")
    if "attendees_exact" in spec and attendees - {ev["organizer"].lower()} != {e.lower() for e in spec["attendees_exact"]}:
        problems.append(f"attendees {sorted(attendees)} != {sorted(spec['attendees_exact'])}")
    if "meet" in spec and bool(ev.get("conferenceData")) != spec["meet"]:
        problems.append(f"meet={bool(ev.get('conferenceData'))}")
    description = norm(ev.get("description", ""))
    for anchor in spec.get("description_has", []):
        if not matches(ev.get("description", ""), anchor):
            problems.append(f"description lacks {anchor!r}")
    if "description_prefix" in spec and not description.startswith(norm(spec["description_prefix"])):
        problems.append(f"description does not keep {spec['description_prefix']!r} at the start")
    if "description_suffix" in spec and not description.rstrip(" .").endswith(norm(spec["description_suffix"]).rstrip(" .")):
        problems.append(f"description does not end with {spec['description_suffix']!r}")
    if "dateTime" in ev["start"]:
        start, end = _dt(ev["start"]["dateTime"]), _dt(ev["end"]["dateTime"])
        if "minutes" in spec and (end - start).total_seconds() != spec["minutes"] * 60:
            problems.append(f"lasts {(end - start).total_seconds() / 60:g} min, not {spec['minutes']}")
        if "window" in spec:
            lo, hi = _dt(spec["window"][0]), _dt(spec["window"][1])
            if start < lo or end > hi:
                problems.append(f"{ev['start']['dateTime']} is outside {spec['window']}")
        if spec.get("working_hours"):
            local = start.astimezone(_dt(spec["window"][0]).tzinfo) if "window" in spec else start
            local_end = end.astimezone(local.tzinfo)
            if local.weekday() >= 5 or local.hour < 10 or (local_end.hour, local_end.minute) > (18, 0) or local_end.date() != local.date():
                problems.append(f"{ev['start']['dateTime']} is outside working hours")
        for email in spec.get("free", []):
            clash = _conflicts(ctx.final, email, start, end, {ev["id"]})
            if clash:
                problems.append(f"{email} is busy then ({clash[0].get('summary')!r})")
    return problems


@check("event")
def check_event(ctx: Ctx, spec: dict) -> list[str]:
    """A new or changed event. `wid` pins a seeded event; otherwise match by summary
    (or `summary_has`) and optionally `attendees_include`, and expect `count` of them."""
    mode = spec.get("change", "new")
    if "wid" in spec:
        eid = ctx.ids("events", spec["wid"])
        candidates = [c for c in ctx.changes_of("calendar.event.changed") if c["id"] == eid]
        if not candidates:
            return [f"event {spec['wid']} was not changed"]
    else:
        kinds = {"new": ("calendar.event.new",), "changed": ("calendar.event.changed",), "any": ("calendar.event.new", "calendar.event.changed")}[mode]
        candidates = ctx.changes_of(*kinds)
        if "summary" in spec:
            candidates = [c for c in candidates if same(c["event"].get("summary", ""), spec["summary"])]
        if "summary_has" in spec:
            candidates = [c for c in candidates if matches(c["event"].get("summary", ""), spec["summary_has"])]
        if "select_date" in spec:
            candidates = [c for c in candidates if (c["event"]["start"].get("dateTime") or c["event"]["start"].get("date", ""))[:10] == spec["select_date"]]
        if "select_attendee" in spec:
            who = spec["select_attendee"].lower()
            candidates = [c for c in candidates if who in {a["email"].lower() for a in c["event"].get("attendees", [])}]
        if not candidates:
            label = spec.get("summary") or spec.get("summary_has") or spec.get("select_attendee") or spec.get("select_date")
            return [f"no {mode} event matching {label!r}"]
    if len(candidates) != spec.get("count", 1):
        return [f"expected {spec.get('count', 1)} matching event(s), found {len(candidates)}: " + "; ".join(summarize(c) for c in candidates)]
    problems = []
    for c in candidates:
        problems += _event_ok(ctx, c["event"], spec)
        if "only_fields" in spec and "fields" in c:
            extra = sorted(set(c["fields"]) - set(spec["only_fields"]))
            if extra:
                problems.append(f"{c['event'].get('summary')!r} also changed {extra}")
        ctx.claimed.add(c["key"])
    return problems


@check("allday")
def check_allday(ctx: Ctx, spec: dict) -> list[str]:
    """New all-day events titled like `summary_has` cover exactly `dates` (one multi-day
    event or several; the end date is exclusive, as in the API)."""
    from datetime import date, timedelta

    covered: list[str] = []
    for c in ctx.changes_of("calendar.event.new"):
        ev = c["event"]
        if "date" not in ev["start"] or not matches(ev.get("summary", ""), spec["summary_has"]):
            continue
        ctx.claimed.add(c["key"])
        day, end = date.fromisoformat(ev["start"]["date"]), date.fromisoformat(ev["end"]["date"])
        while day < end:
            covered.append(day.isoformat())
            day += timedelta(days=1)
    if sorted(covered) != sorted(spec["dates"]):
        return [f"all-day events cover {sorted(covered)}, expected {spec['dates']}"]
    return []


@check("event_deleted")
def check_event_deleted(ctx: Ctx, spec: dict) -> list[str]:
    eid = ctx.ids("events", spec["wid"])
    hit = [c for c in ctx.changes_of("calendar.event.deleted") if c["id"] == eid]
    if not hit:
        return [f"event {spec['wid']} was not deleted"]
    ctx.claimed.add(hit[0]["key"])
    return []


@check("no_overlap")
def check_no_overlap(ctx: Ctx, spec: dict) -> list[str]:
    """New events matching `summary_has` must not overlap each other."""
    evs = [c["event"] for c in ctx.changes_of("calendar.event.new") if matches(c["event"].get("summary", ""), spec["summary_has"])]
    evs = [e for e in evs if "dateTime" in e["start"]]
    evs.sort(key=lambda e: _dt(e["start"]["dateTime"]))
    return [
        f"{a.get('summary')!r} overlaps {b.get('summary')!r}"
        for a, b in zip(evs, evs[1:])
        if _dt(b["start"]["dateTime"]) < _dt(a["end"]["dateTime"])
    ]


# ---------------------------------------------------------------------------
# Mail
# ---------------------------------------------------------------------------


def _anchors(text: str, spec: dict, what: str) -> list[str]:
    problems = [f"{what} lacks {a!r}" for a in spec.get("has", []) if not matches(text, a)]
    problems += [f"{what} contains {a!r}" for a in spec.get("not", []) if matches(text, a)]
    return problems


@check("sent")
def check_sent(ctx: Ctx, spec: dict) -> list[str]:
    to = spec["to"].lower()
    hits = [c for c in ctx.changes_of("gmail.message.new") if "SENT" in c["message"]["labelIds"] and to in c["message"]["to"].lower()]
    if len(hits) != spec.get("count", 1):
        return [f"expected {spec.get('count', 1)} sent mail(s) to {to}, found {len(hits)}"]
    problems = []
    for c in hits:
        m = c["message"]
        text = m["subject"] + "\n" + m["body"]
        problems += _anchors(text, spec, f"mail to {to}")
        problems += _event_times(ctx, text, spec.get("event_times", []), f"mail to {to}")
        if "new_doc_link" in spec:
            docs = [c["file"]["id"] for c in ctx.changes_of("drive.file.new") if same(c["file"]["name"], spec["new_doc_link"])]
            if not any(d in text for d in docs):
                problems.append(f"mail to {to} lacks the link to the new doc {spec['new_doc_link']!r}")
        ctx.claimed.add(c["key"])
    return problems


def _event_times(ctx: Ctx, text: str, attendees: list[str], what: str) -> list[str]:
    """For each attendee, the new event they are invited to must be named in the text by its
    start time and its date (or weekday). Used when the agent picks the slots itself."""
    problems = []
    for email in attendees:
        evs = [c["event"] for c in ctx.changes_of("calendar.event.new") if email.lower() in {a["email"].lower() for a in c["event"].get("attendees", [])}]
        if len(evs) != 1:
            problems.append(f"{what}: cannot tell which event is {email}'s ({len(evs)} new)")
            continue
        start = _dt(evs[0]["start"]["dateTime"])
        if not matches(text, {"time": start.strftime("%H:%M")}):
            problems.append(f"{what} lacks {email}'s start time {start:%H:%M}")
        if not matches(text, [{"date": start.date().isoformat()}, start.strftime("%A"), start.strftime("%a ")]):
            problems.append(f"{what} lacks {email}'s day {start:%a %d %b}")
    return problems


@check("draft")
def check_draft(ctx: Ctx, spec: dict) -> list[str]:
    to = spec["to"].lower()
    hits = [c for c in ctx.changes_of("gmail.draft.new") if to in c["draft"]["to"].lower()]
    if len(hits) != spec.get("count", 1):
        return [f"expected {spec.get('count', 1)} draft(s) to {to}, found {len(hits)}"]
    problems = []
    for c in hits:
        d = c["draft"]
        problems += _anchors(d["subject"] + "\n" + d["body"], spec, f"draft to {to}")
        ctx.claimed.add(c["key"])
    return problems


def _label_names(state: dict, label_ids: list[str]) -> set[str]:
    labels = state["gmail"]["labels"]
    return {labels[l]["name"] if l in labels else l for l in label_ids}


@check("mail")
def check_mail(ctx: Ctx, spec: dict) -> list[str]:
    """End state of seeded messages (`wid` or `wids`): in_inbox, unread,
    labels_include / labels_exclude (label names). Claims their label changes."""
    problems = []
    for wid in spec.get("wids", [spec.get("wid")]):
        mid = ctx.ids("gmail", wid)
        msg = ctx.final["gmail"]["messages"].get(mid)
        if msg is None:
            problems.append(f"{wid} was deleted")
            continue
        labels = set(msg["labelIds"])
        names = _label_names(ctx.final, msg["labelIds"])
        if "in_inbox" in spec and ("INBOX" in labels) != spec["in_inbox"]:
            problems.append(f"{wid} {'is not' if spec['in_inbox'] else 'is still'} in the inbox")
        if "unread" in spec and ("UNREAD" in labels) != spec["unread"]:
            problems.append(f"{wid} is {'read' if spec['unread'] else 'unread'}")
        for name in spec.get("labels_include", []):
            if name not in names:
                problems.append(f"{wid} lacks label {name!r}")
        for name in spec.get("labels_exclude", []):
            if name in names:
                problems.append(f"{wid} has label {name!r}")
        ctx.claim("gmail.message.labels", mid)
    return problems


@check("label")
def check_label(ctx: Ctx, spec: dict) -> list[str]:
    """A user label with this name exists at the end (claims its creation)."""
    hit = [l for l in ctx.final["gmail"]["labels"].values() if l["name"] == spec["name"]]
    if not hit:
        return [f"no label named {spec['name']!r}"]
    ctx.claim("gmail.label.new", hit[0]["id"])
    return []


@check("filter_deleted")
def check_filter_deleted(ctx: Ctx, spec: dict) -> list[str]:
    fid = ctx.ids("filters", spec["wid"])
    if fid in ctx.final["gmail"]["filters"]:
        return [f"filter {spec['wid']} still exists"]
    ctx.claim("gmail.filter.deleted", fid)
    return []


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


def _due_date(task: dict) -> str | None:
    return task["due"][:10] if task.get("due") else None


@check("task")
def check_task(ctx: Ctx, spec: dict) -> list[str]:
    """End state of a seeded task: status, hidden, due (yyyy-mm-dd or null), parent (wid)."""
    tid = ctx.ids("tasks", spec["wid"])
    task = ctx.final["tasks"]["tasks"].get(tid)
    if task is None:
        return [f"task {spec['wid']} was deleted"]
    problems = []
    if "status" in spec and task.get("status") != spec["status"]:
        problems.append(f"task {spec['wid']} status {task.get('status')}")
    if "hidden" in spec and bool(task.get("hidden")) != spec["hidden"]:
        problems.append(f"task {spec['wid']} hidden={bool(task.get('hidden'))}")
    if "due" in spec and _due_date(task) != spec["due"]:
        problems.append(f"task {spec['wid']} due {_due_date(task)}")
    if "parent_title" in spec:
        parent = ctx.final["tasks"]["tasks"].get(task.get("parent") or "")
        if parent is None or not same(parent["title"], spec["parent_title"]):
            problems.append(f"task {spec['wid']} parent is {parent['title'] if parent else None!r}")
    ctx.claim("tasks.task.changed", tid)
    return problems


@check("task_deleted")
def check_task_deleted(ctx: Ctx, spec: dict) -> list[str]:
    tid = ctx.ids("tasks", spec["wid"])
    if tid in ctx.final["tasks"]["tasks"]:
        return [f"task {spec['wid']} still exists"]
    ctx.claim("tasks.task.deleted", tid)
    return []


def _match_tasks(ctx: Ctx, tasks: list[dict], wanted: list[dict], where: str) -> list[str]:
    """Each wanted spec {title: anchor, due, parent: anchor|null} matches exactly one task."""
    problems = []
    by_id = ctx.final["tasks"]["tasks"]
    used: set[str] = set()
    for w in wanted:
        hits = [t for t in tasks if t["id"] not in used and matches(t["title"], w["title"])]
        if len(hits) != 1:
            problems.append(f"{where}: {len(hits)} task(s) match {w['title']!r}")
            continue
        t = hits[0]
        used.add(t["id"])
        if "due" in w and _due_date(t) != w["due"]:
            problems.append(f"{where}: {t['title']!r} due {_due_date(t)}, not {w['due']}")
        if "parent" in w:
            parent = by_id.get(t.get("parent") or "")
            if w["parent"] is None and parent is not None:
                problems.append(f"{where}: {t['title']!r} is a subtask of {parent['title']!r}")
            elif w["parent"] is not None and (parent is None or not matches(parent["title"], w["parent"])):
                problems.append(f"{where}: {t['title']!r} is not a subtask of {w['parent']!r}")
        if "status" in w and t.get("status") != w["status"]:
            problems.append(f"{where}: {t['title']!r} status {t.get('status')}")
    extra = [t["title"] for t in tasks if t["id"] not in used]
    if extra:
        problems.append(f"{where}: unexpected task(s) {extra}")
    return problems


@check("tasklist")
def check_tasklist(ctx: Ctx, spec: dict) -> list[str]:
    """A new task list titled `title` holding exactly `tasks` (claims the list and them)."""
    lists = [l for l in ctx.final["tasks"]["lists"].values() if l.get("origin") == "agent" and same(l["title"], spec["title"])]
    if len(lists) != 1:
        return [f"expected one new task list {spec['title']!r}, found {len(lists)}"]
    lid = lists[0]["id"]
    ctx.claim("tasks.list.new", lid)
    tasks = [t for t in ctx.final["tasks"]["tasks"].values() if t["list"] == lid]
    for t in tasks:
        ctx.claim("tasks.task.new", t["id"])
    return _match_tasks(ctx, tasks, spec["tasks"], spec["title"])


@check("tasks_new")
def check_tasks_new(ctx: Ctx, spec: dict) -> list[str]:
    """Exactly these new tasks in the seeded list `list` (wid)."""
    lid = ctx.ids("tasklists", spec["list"])
    tasks = [c["task"] for c in ctx.changes_of("tasks.task.new") if c["task"]["list"] == lid]
    for t in tasks:
        ctx.claim("tasks.task.new", t["id"])
    return _match_tasks(ctx, tasks, spec["tasks"], spec["list"])


# ---------------------------------------------------------------------------
# Docs and Drive
# ---------------------------------------------------------------------------


def _segment_text(doc: dict, seg_id: str | None) -> str:
    if not seg_id:
        return ""
    return "".join(t["c"] for t in doc["segments"].get(seg_id, []) if "c" in t)


def _body_text(doc: dict) -> str:
    return _segment_text(doc, "body")


def _paragraph_spans(tokens: list[dict]) -> list[tuple[int, int, str]]:
    """(start, end, text) per paragraph; end is the position of its newline."""
    spans, start, buf = [], 0, []
    for i, t in enumerate(tokens):
        if t.get("c") == "\n":
            spans.append((start, i, "".join(buf)))
            start, buf = i + 1, []
        elif "c" in t:
            buf.append(t["c"])
        else:
            start, buf = i + 1, []
    return spans


def _tables(doc: dict) -> list[list[list[str]]]:
    """Every body table as rows of cell texts (cell text without its closing newline)."""
    tables, rows, cell = [], None, None
    for tok in doc["segments"]["body"]:
        k = tok.get("k")
        if k == "ts":
            rows = []
        elif k == "rs":
            rows.append([])
        elif k == "cs":
            rows[-1].append("")
        elif k == "te":
            tables.append([[c.rstrip("\n") for c in row] for row in rows])
            rows = None
        elif rows is not None and "c" in tok and rows and rows[-1]:
            rows[-1][-1] += tok["c"]
    return tables


def _lines(body: str) -> list[str]:
    return [l for l in body.split("\n") if l.strip()]


def _line_ok(line: str, want) -> bool:
    if isinstance(want, dict):
        return all(matches(line, a) for a in want.get("has", [])) and not any(matches(line, a) for a in want.get("not", []))
    return norm(line) == norm(want)


def _section_problems(lines: list[str], spec: dict, name: str) -> list[str]:
    """Owner headings (a line holding the owner's name and at most two other words), each
    followed by that owner's items up to the next heading."""
    heads = {}
    for i, line in enumerate(lines):
        words = [w.strip("-–—#*:()[].,").lower() for w in line.split()]
        for owner in spec:
            rest = [w for w in words if w and w not in norm(owner).split()]
            # a heading is the owner's name plus at most two more words ("Rao", "Owner:", "(me)")
            if matches(line, owner) and len(rest) <= 2 and owner not in heads:
                heads[owner] = i
    problems = []
    order = sorted(heads.values())
    for owner, want in spec.items():
        if owner not in heads:
            problems.append(f"{name}: no heading for {owner!r}")
            continue
        start = heads[owner]
        end = next((j for j in order if j > start), len(lines))
        section = "\n".join(lines[start + 1:end])
        problems += [f"{name}: {a!r} is not under {owner!r}" for a in want.get("has", []) if not matches(section, a)]
        problems += [f"{name}: {a!r} is under {owner!r}" for a in want.get("not", []) if matches(section, a)]
    return problems


def _doc_problems(before: dict | None, doc: dict, spec: dict, name: str) -> list[str]:
    problems = []
    body = _body_text(doc)
    if spec.get("text_unchanged") and before is not None and body != _body_text(before):
        problems.append(f"{name}: body text changed")
    if "text" in spec and norm(body) != norm(spec["text"]):
        problems.append(f"{name}: body text differs from the expected text")
    if "lines" in spec:
        got = _lines(body)
        if len(got) != len(spec["lines"]):
            problems.append(f"{name}: {len(got)} lines, expected {len(spec['lines'])}")
        for i, (line, want) in enumerate(zip(got, spec["lines"])):
            if not _line_ok(line, want):
                problems.append(f"{name} line {i + 1}: {line!r} != {want!r}")
    if "sections" in spec:
        problems += _section_problems(_lines(body), spec["sections"], name)
    if "table" in spec:
        tables = _tables(doc)
        if not tables:
            problems.append(f"{name}: no table")
        else:
            got, want = tables[0], spec["table"]
            if len(got) != len(want):
                problems.append(f"{name}: table has {len(got)} rows, expected {len(want)}")
            for i, (row, wrow) in enumerate(zip(got, want)):
                if len(row) != len(wrow) or not all(_cell_ok(c, w) for c, w in zip(row, wrow)):
                    problems.append(f"{name}: table row {i + 1} {row} != {wrow}")
    problems += _anchors(body, spec, name)
    for kind, key in (("header", "defaultHeaderId"), ("footer", "defaultFooterId")):
        if kind in spec:
            got = _segment_text(doc, doc.get(key))
            if norm(got) != norm(spec[kind]):
                problems.append(f"{name}: {kind} is {got.strip()!r}")
    bold = spec.get("bold_lines")
    if bold is not None:
        tokens = doc["segments"]["body"]
        old = before["segments"]["body"] if before else None
        targets = set()
        for line in bold:
            spans = [s for s in _paragraph_spans(tokens) if norm(s[2]) == norm(line)]
            if len(spans) != 1:
                problems.append(f"{name}: {len(spans)} line(s) read {line!r}")
                continue
            lo, hi, _ = spans[0]
            if not all(tokens[i].get("s", {}).get("bold") for i in range(lo, hi)):
                problems.append(f"{name}: {line!r} is not fully bold")
            targets.update(range(lo, hi + 1))
        if old is not None and len(old) == len(tokens):
            changed = [i for i in range(len(tokens)) if i not in targets and tokens[i].get("s") != old[i].get("s")]
            if changed:
                problems.append(f"{name}: formatting changed outside {bold} (near {''.join(t.get('c', '') for t in tokens[changed[0]:changed[0] + 20])!r})")
    return problems


@check("doc")
def check_doc(ctx: Ctx, spec: dict) -> list[str]:
    """End state of a seeded doc: text_unchanged, text, has/not, header, footer, bold_lines."""
    did = ctx.ids("docs", spec["wid"])
    doc = ctx.final["docs"].get(did)
    if doc is None:
        return [f"doc {spec['wid']} was deleted"]
    ctx.claim("docs.doc.changed", did)
    ctx.claim("drive.file.changed", did)
    return _doc_problems(ctx.initial["docs"].get(did), doc, spec, spec["wid"])


@check("doc_new")
def check_doc_new(ctx: Ctx, spec: dict) -> list[str]:
    """Exactly one new doc titled `title`, with the doc checks above."""
    files = [c["file"] for c in ctx.changes_of("drive.file.new") if c["file"]["mimeType"].endswith(".document") and same(c["file"]["name"], spec["title"])]
    if len(files) != 1:
        return [f"expected one new doc {spec['title']!r}, found {len(files)}"]
    ctx.claim("drive.file.new", files[0]["id"])
    return _doc_problems(None, ctx.final["docs"][files[0]["id"]], spec, spec["title"])


def _file_id(ctx: Ctx, wid: str) -> str:
    kind = "sheets" if wid.startswith("sh_") else "docs"
    return ctx.ids(kind, wid)


@check("comment")
def check_comment(ctx: Ctx, spec: dict) -> list[str]:
    """A seeded comment ("<file wid>:<comment wid>"): resolved, reply_has (one new reply
    containing the anchor), untouched."""
    file_wid = spec["wid"].split(":")[0]
    fid, cid = _file_id(ctx, file_wid), ctx.ids("comments", spec["wid"])
    before = next(c for c in ctx.initial["drive"]["comments"][fid] if c["id"] == cid)
    after = next((c for c in ctx.final["drive"]["comments"].get(fid, []) if c["id"] == cid), None)
    if after is None:
        return [f"comment {spec['wid']} was deleted"]
    ctx.claim("drive.comment.changed", f"{fid}:{cid}")
    if spec.get("untouched"):
        return [] if after == before else [f"comment {spec['wid']} was changed"]
    problems = []
    if "resolved" in spec and bool(after.get("resolved")) != spec["resolved"]:
        problems.append(f"comment {spec['wid']} resolved={bool(after.get('resolved'))}")
    seen = {x.get("id") for x in before.get("replies", [])}
    new = [r for r in after.get("replies", []) if r.get("id") not in seen and not r.get("action")]  # resolve adds its own reply
    if "reply_has" in spec:
        if len(new) != 1:
            problems.append(f"comment {spec['wid']}: {len(new)} new replies with text")
        elif not matches(new[0]["content"], spec["reply_has"]):
            problems.append(f"comment {spec['wid']}: reply {new[0]['content']!r} lacks {spec['reply_has']!r}")
    return problems


@check("comments_new")
def check_comments_new(ctx: Ctx, spec: dict) -> list[str]:
    """New top-level comments on a file (`wid`): exactly `count`; with `each`, every anchor
    is in exactly one comment; `has` anchors must all be in every comment."""
    fid = _file_id(ctx, spec["wid"])
    new = [c for c in ctx.changes_of("drive.comment.new") if c["file_id"] == fid]
    for c in new:
        ctx.claimed.add(c["key"])
    texts = [c["comment"]["content"] for c in new]
    problems = []
    if "count" in spec and len(texts) != spec["count"]:
        problems.append(f"{len(texts)} new comments on {spec['wid']}, expected {spec['count']}")
    for anchor in spec.get("each", []):
        n = sum(matches(t, anchor) for t in texts)
        if n != 1:
            problems.append(f"{n} new comments on {spec['wid']} mention {anchor!r}")
    for text in texts:
        problems += _anchors(text, {"has": spec.get("has", [])}, f"comment on {spec['wid']}")
    return problems


@check("file_new")
def check_file_new(ctx: Ctx, spec: dict) -> list[str]:
    """Exactly one new Drive file named `name` (a trailing extension may be added) of `mime`."""
    def named(f):
        n = f["name"]
        return same(n, spec["name"]) or any(same(n, spec["name"] + ext) for ext in spec.get("ext", []))

    files = [c["file"] for c in ctx.changes_of("drive.file.new") if named(c["file"])]
    if len(files) != 1:
        return [f"expected one new file {spec['name']!r}, found {len(files)}"]
    ctx.claim("drive.file.new", files[0]["id"])
    if "mime" in spec and files[0]["mimeType"] != spec["mime"]:
        return [f"{files[0]['name']!r} is {files[0]['mimeType']}"]
    return []


# ---------------------------------------------------------------------------
# Sheets
# ---------------------------------------------------------------------------


def _book_view(state: dict, sid: str):
    from lab.fake.sheets import Book
    from lab.workspace import Workspace

    ws = Workspace(state, namespace="grade")
    return Book(ws, sid, state["sheets"][sid])


def _grid(book, tab) -> list[list[str]]:
    rows, cols = book.extent(tab)
    grid = [[book.shown(tab, r, c) for c in range(cols)] for r in range(rows)]
    while grid and not any(grid[-1]):
        grid.pop()
    width = max((max((i + 1 for i, v in enumerate(row) if v), default=0) for row in grid), default=0)
    return [row[:width] + [""] * (width - len(row[:width])) for row in grid]


def _cell_ok(got: str, want) -> bool:
    if isinstance(want, list):
        return any(_cell_ok(got, w) for w in want)
    if isinstance(want, dict):
        if "exact" in want:
            return got.strip() == want["exact"]
        if "prefix" in want:
            return norm(got).startswith(norm(want["prefix"]))
        if "has" in want:
            return norm(want["has"]) in norm(got)
        return matches(got, want)
    return norm(got) == norm(str(want))


def _row_ok(got: list[str], want: list) -> bool:
    got = got + [""] * (len(want) - len(got))
    return all(_cell_ok(g, w) for g, w in zip(got, want)) and not any(got[len(want):])


def _to_number(text: str) -> float | None:
    t = text.replace(",", "").replace("₹", "").strip()
    try:
        return float(t)
    except ValueError:
        return None


def _hex(color: dict | None) -> str | None:
    if not color:
        return None
    return "#" + "".join(f"{round(color.get(k, 0) * 255):02X}" for k in ("red", "green", "blue"))


def _rule_view(rule: dict) -> dict:
    """A conditional-format rule as {type, values, bg, text, range} for comparison."""
    from lab.fake import sheets_calc as calc

    cond = rule.get("booleanRule", {}).get("condition", {})
    fmt = rule.get("booleanRule", {}).get("format", {})
    g = rule["ranges"][0]
    a1 = f"{calc.index_to_col(g['startColumnIndex'])}{g['startRowIndex'] + 1}:{calc.index_to_col(g['endColumnIndex'] - 1)}{g['endRowIndex']}"
    return {
        "type": cond.get("type"),
        "values": [
            (v.get("userEnteredValue") or "").replace(",", "") if str(cond.get("type", "")).startswith("NUMBER") else v.get("userEnteredValue")
            for v in cond.get("values", [])
        ],
        "bg": _hex(fmt.get("backgroundColor")),
        "text": _hex(fmt.get("textFormat", {}).get("foregroundColor")),
        "range": a1,
    }


def _tab_problems(book, tab, spec: dict, before: dict | None = None) -> list[str]:
    name = tab["title"]
    grid = _grid(book, tab)
    problems = []
    if spec.get("grid_unchanged") and before is not None:
        if tab["cells"] != before["cells"] or tab.get("formats") != before.get("formats"):
            problems.append(f"{name}: cell values or formats changed")
    if "grid" in spec:
        want = spec["grid"]
        if len(grid) != len(want):
            problems.append(f"{name}: {len(grid)} rows, expected {len(want)}")
        for i, (g, w) in enumerate(zip(grid, want)):
            if not _row_ok(g, w):
                problems.append(f"{name} row {i + 1}: {g} != {w}")
    if "rules" in spec:
        got = [_rule_view(r) for r in tab.get("conditionalFormats", [])]
        want = spec["rules"]
        if len(got) != len(want) or any(g != {**g, **w} for g, w in zip(got, want)):
            problems.append(f"{name}: rules {got} != {want}")
    if "rows_unordered" in spec:
        header, body = (grid[0], grid[1:]) if grid else ([], [])
        if spec.get("header_optional") and grid and not _row_ok(header, spec["header"]):
            header, body = spec["header"], grid
        if "header" in spec and not _row_ok(header, spec["header"]):
            problems.append(f"{name}: header {header}")
        want = list(spec["rows_unordered"])
        if len(body) != len(want):
            problems.append(f"{name}: {len(body)} data rows, expected {len(want)}")
        left = list(body)
        for w in want:
            hit = next((g for g in left if _row_ok(g, w)), None)
            if hit is None:
                problems.append(f"{name}: no row matches {w}")
            else:
                left.remove(hit)
        for g in left[:3]:
            problems.append(f"{name}: unexpected row {g}")
    if "pairs" in spec:
        found: dict[str, float] = {}
        for row in grid:
            for label, value in zip(row, row[1:]):
                n = _to_number(value)
                if label and n is not None and _to_number(label) is None:
                    found[norm(label)] = n
        for label, n in spec["pairs"].items():
            if found.get(norm(label)) != n:
                problems.append(f"{name}: {label} = {found.get(norm(label))}, expected {n}")
        wanted = {norm(l) for l in spec["pairs"]}
        extra = [f"{l}={n:g}" for l, n in found.items() if l not in wanted and n and "total" not in l]
        if extra:
            problems.append(f"{name}: unexpected counts {extra}")
    if "cells" in spec:
        for a1, want in spec["cells"].items():
            from lab.fake import sheets_calc as calc

            r0, c0, _, _ = calc.parse_a1(a1)
            got = book.shown(tab, r0, c0)
            if not _cell_ok(got, want):
                problems.append(f"{name}!{a1} = {got!r}, expected {want!r}")
    return problems


@check("book")
def check_book(ctx: Ctx, spec: dict) -> list[str]:
    """A spreadsheet's end state. `wid` (seeded) or `title` (new). `tabs`: {title: tab spec}
    with grid / header+rows_unordered / pairs / cells. Seeded tabs not listed must be
    unchanged; new tabs must be listed, except empty ones when `allow_empty_tabs`."""
    if "wid" in spec:
        sid = ctx.ids("sheets", spec["wid"])
        ctx.claim("sheets.book.changed", sid)
        ctx.claim("drive.file.changed", sid)
    else:
        files = [c["file"] for c in ctx.changes_of("drive.file.new") if c["file"]["mimeType"].endswith(".spreadsheet") and same(c["file"]["name"], spec["title"])]
        if len(files) != 1:
            return [f"expected one new spreadsheet {spec['title']!r}, found {len(files)}"]
        sid = files[0]["id"]
        ctx.claim("drive.file.new", sid)
    book = _book_view(ctx.final, sid)
    before = {t["title"]: t for t in ctx.initial["sheets"].get(sid, {"tabs": []})["tabs"]}
    wanted = {norm(k): v for k, v in spec.get("tabs", {}).items()}
    problems = []
    seen = set()
    for tab in book.data["tabs"]:
        key = norm(tab["title"])
        if key in wanted:
            seen.add(key)
            problems += _tab_problems(book, tab, wanted[key], before.get(tab["title"]))
        elif tab["title"] in before:
            if tab != before[tab["title"]]:
                problems.append(f"tab {tab['title']!r} changed")
        elif not (spec.get("allow_empty_tabs") and not tab["cells"]):
            problems.append(f"unexpected tab {tab['title']!r}")
    for key in wanted.keys() - seen:
        problems.append(f"no tab {key!r}")
    for title in before.keys() - {t["title"] for t in book.data["tabs"]}:
        problems.append(f"tab {title!r} was deleted")
    return problems


# ---------------------------------------------------------------------------
# Final message
# ---------------------------------------------------------------------------


@check("final_message")
def check_final_message(ctx: Ctx, spec: dict) -> list[str]:
    """The agent's last message: non-empty, contains `has`, lacks `not`."""
    if not ctx.final_message.strip():
        return ["empty final message"]
    return _anchors(ctx.final_message, spec, "final message")


# ---------------------------------------------------------------------------


def _forbidden(calls: list[dict], rules: list[dict]) -> list[str]:
    problems = []
    for rule in rules:
        for call in calls:
            if call.get("error") or call["tool"] != rule["tool"]:
                continue
            args = call.get("args", {})
            if all(str(args.get(k, "")).lower() == str(v).lower() for k, v in rule.get("args", {}).items()):
                problems.append(f"forbidden call {rule['tool']}({rule.get('args', {})}) at #{call['n']}")
    return problems


def grade(task: dict, initial: dict, final: dict, calls: list[dict], final_message: str, index: dict) -> dict[str, Any]:
    ctx = Ctx(task, initial, final, calls, final_message, index)
    failed: list[str] = []
    for spec in task["expect"].get("state", []):
        problems = CHECKS[spec["check"]](ctx, spec)
        failed += [f"[{spec['check']}] {p}" for p in problems]
    allowed = set(task["expect"].get("allow", []))
    unexpected = [c for c in ctx.changes if c["key"] not in ctx.claimed and c["kind"] not in allowed]
    failed += [f"[unexpected change] {summarize(c)}" for c in unexpected]
    failed += _forbidden(calls, task["expect"].get("forbidden", []))
    judge = task["expect"].get("judge")
    return {
        "passed": not failed,
        "failed_checks": failed,
        "judge_pending": bool(judge) and not failed,
        "n_changes": len(ctx.changes),
        "n_calls": len(calls),
    }
