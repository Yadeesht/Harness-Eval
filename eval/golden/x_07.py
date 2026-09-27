"""x_07: follow-up with every postmortem action owner on the first working day after the last due date; [SEC] items to Rohan."""

from datetime import date, datetime, timedelta

from _lib import busy, events, free, hhmm, js, pick

ME = "yadeesh@kestrel.example"


async def _items(t):
    doc = pick(js(await t("search_docs", query="Postmortem Payments"))["docs"], name="Payments API outage")
    lines = js(await t("get_doc_content", document_id=doc["id"]))["content"].split("\n")
    start = lines.index("Action items") + 5  # skip the header cells (Owner, Action, Due, Tag)
    cells = [l for l in lines[start:] if l]
    return [cells[i:i + 4] for i in range(0, len(cells), 4)]


async def _owners(t, rows):
    cals = js(await t("list_calendars"))["calendars"]
    by_name = {c["summary"]: c["id"] for c in cals}
    return cals, sorted({by_name[r[0]] for r in rows})


async def _mail_rohan(t, rows):
    sec = [f"- {r[1]} (due {r[2]})" for r in rows if r[3] == "[SEC]"]
    await t("send_email", recipient_id="rohan.kapoor@kestrel.example", subject="Payments postmortem: [SEC] action items", message="Hi Rohan,\n\nThe [SEC] action items from the Payments API postmortem:\n" + "\n".join(sec) + "\n\nThanks,\nYadeesh")


async def golden(t):
    rows = await _items(t)
    cals, owners = await _owners(t, rows)
    latest = max(datetime.strptime(r[2], "%d %b %Y").date() for r in rows)
    holidays_cal = pick(cals, summary="Holidays")["id"]
    holidays = {e["start"][:10] for e in events(await t("get_events", calendar_id=holidays_cal, time_min="2026-10-30T00:00:00", time_max="2026-11-15T00:00:00"))}
    day = latest + timedelta(days=1)
    while day.weekday() >= 5 or day.isoformat() in holidays:
        day += timedelta(days=1)
    assert day == date(2026, 11, 2)
    window = {"time_min": f"{day}T00:00:00", "time_max": f"{day + timedelta(days=1)}T00:00:00", "detailed": True, "max_results": 100}
    blocked = busy(events(await t("get_events", **window)), ME)
    for email in owners:
        blocked += busy(events(await t("get_events", calendar_id=email, **window)), email)
    slot = datetime.fromisoformat(f"{day}T10:00:00+05:30")
    while not free(blocked, slot, slot + timedelta(minutes=30)):
        slot += timedelta(minutes=15)
    await t("create_event", summary="Payments postmortem follow-up", start_time=hhmm(slot), end_time=hhmm(slot + timedelta(minutes=30)), attendees=owners)
    await _mail_rohan(t, rows)
    return f"Booked 'Payments postmortem follow-up' on Mon 2 Nov at {slot:%H:%M} (the first time all 5 owners and you are free) and emailed Rohan the two [SEC] items."


async def negative(t):
    """Trap taken: the day after the last due date (Sat 31 Oct), without checking calendars."""
    rows = await _items(t)
    _, owners = await _owners(t, rows)
    await t("create_event", summary="Payments postmortem follow-up", start_time="2026-10-31T11:00:00", end_time="2026-10-31T11:30:00", attendees=owners)
    await _mail_rohan(t, rows)
    return "Done."
