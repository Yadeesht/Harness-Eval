"""x_02: onboarding task list, three non-overlapping intro 1:1s, schedule mail to the buddy."""

from datetime import datetime, timedelta

from _lib import events, grab, js, pick

ANANYA = "ananya.das@kestrel.example"
INTROS = [("Meera Pillai", "meera.pillai@kestrel.example"), ("Neha Gupta", "neha.gupta@kestrel.example"), ("Farah Khan", "farah.khan@kestrel.example")]
WINDOW = (datetime.fromisoformat("2026-10-12T14:00:00+05:30"), datetime.fromisoformat("2026-10-14T18:00:00+05:30"))


async def _read_sources(t):
    doc = pick(js(await t("search_docs", query="Onboarding Checklist"))["docs"], name="Onboarding Checklist")
    text = js(await t("get_doc_content", document_id=doc["id"]))["content"]
    assert "Day 1 is the new hire's start date" in text
    mail = pick(js(await t("search_emails", query="Ananya"))["emails"], subject="New joiner")
    body = await t("read_email", email_id=mail["id"])
    return grab(r"onboarding buddy will be ([A-Z]\w+ [A-Z]\w+)", body)


async def _tasks(t):
    lid = js(await t("create_task_list", title="Ananya Onboarding"))["task_list_id"]

    async def add(title, due=None, parent=None):
        args = {"task_list_id": lid, "title": title}
        if due:
            args["due"] = f"{due}T00:00:00Z"
        if parent:
            args["parent"] = parent
        return js(await t("create_task", **args))["task_id"]

    it = await add("IT setup", "2026-10-12")
    for step in ("Collect the laptop from the IT desk", "Enable 2-step verification", "Request GitHub and CloudNest access"):
        await add(step, "2026-10-12", parent=it)
    await add("HR induction", "2026-10-12")
    await add("Read the Platform Architecture Overview", "2026-10-13")
    await add("Shadow an on-call handover", "2026-10-14")
    await add("First pull request merged", "2026-10-16")


def _busy(evs, email):
    """Intervals when `email` is busy: events they haven't declined, and their own guest-less events."""
    out = []
    for e in evs:
        status = e["attendees"].get(email, "accepted" if not e["attendees"] else None)
        if status and status != "declined":
            out.append((datetime.fromisoformat(e["start"]), datetime.fromisoformat(e["end"])))
    return out


def _first_slot(busy, taken):
    slot = WINDOW[0]
    while slot + timedelta(minutes=30) <= WINDOW[1]:
        end = slot + timedelta(minutes=30)
        in_hours = slot.hour >= 10 and (end.hour, end.minute) <= (18, 0)
        if in_hours and not any(s < end and slot < e for s, e in busy + taken):
            return slot
        slot += timedelta(minutes=15)
    raise AssertionError("no slot")


async def _book(t, choose):
    await t("list_calendars")
    booked = []
    for name, email in INTROS:
        evs = events(await t("get_events", calendar_id=email, time_min="2026-10-12T00:00:00", time_max="2026-10-15T00:00:00", max_results=100, detailed=True))
        start = choose(_busy(evs, email), [(s, s + timedelta(minutes=30)) for s, _ in booked])
        await t(
            "create_event",
            summary=f"Intro: Ananya Das / {name.split()[0]}",
            start_time=start.strftime("%Y-%m-%dT%H:%M:%S"),
            end_time=(start + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S"),
            attendees=[ANANYA, email],
        )
        booked.append((start, name))
    return booked


def _schedule(booked):
    return "\n".join(f"- {name}: {start:%a %d %b}, {start:%H:%M}–{start + timedelta(minutes=30):%H:%M}" for start, name in booked)


async def golden(t):
    assert await _read_sources(t) == "Vikram Rao"
    await _tasks(t)
    booked = await _book(t, _first_slot)
    await t(
        "send_email",
        recipient_id="vikram.rao@kestrel.example",
        subject="Ananya's intro 1:1s",
        message="Hi Vikram,\n\nYou're Ananya's onboarding buddy. Her intro 1:1s:\n" + _schedule(booked) + "\n\nThanks,\nYadeesh",
    )
    return "Created 'Ananya Onboarding' (5 tasks, IT setup with 3 subtasks), booked the three intros, emailed Vikram the schedule."


async def negative(t):
    """Traps taken: Meera's intro at Mon 11:30 (before Day 1 14:00, Meera busy); schedule sent to Ananya, not the buddy."""
    await _read_sources(t)
    await _tasks(t)
    first = [True]

    def early_then_first(busy, taken):
        if first[0]:
            first[0] = False
            return datetime.fromisoformat("2026-10-12T11:30:00+05:30")
        return _first_slot(busy, taken)

    booked = await _book(t, early_then_first)
    await t("send_email", recipient_id=ANANYA, subject="Your intro 1:1s", message="Hi Ananya,\n\nYour intro 1:1s:\n" + _schedule(booked))
    return "Done."
