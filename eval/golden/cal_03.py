"""cal_03: move Rahul's 1:1 to 15:00, re-slot the clashing internal meeting to the next free half hour."""

from datetime import datetime, timedelta

from _lib import busy, events, free, hhmm, js, pick

THU = {"time_min": "2026-10-08T00:00:00", "time_max": "2026-10-09T00:00:00", "detailed": True, "max_results": 100}
ME = "yadeesh@kestrel.example"


async def _prepare(t):
    mail = pick(js(await t("search_emails", query="from:rahul.verma@kestrel.example 1:1"))["emails"], subject="move our 1:1")
    body = js(await t("read_email", email_id=mail["id"]))["content"]
    assert "15:00" in body
    mine = events(await t("get_events", **THU))
    one_on_one = pick(mine, summary="1:1 Yadeesh / Rahul")
    start = datetime.fromisoformat("2026-10-08T15:00:00+05:30")
    end = start + (datetime.fromisoformat(one_on_one["end"]) - datetime.fromisoformat(one_on_one["start"]))
    await t("modify_event", event_id=one_on_one["id"], start_time=hhmm(start), end_time=hhmm(end))
    clashes = [
        e for e in mine
        if e["id"] != one_on_one["id"] and "T" in e["start"]
        and datetime.fromisoformat(e["start"]) < end and start < datetime.fromisoformat(e["end"])
    ]
    assert len(clashes) == 1 and all(a.endswith("@kestrel.example") for a in clashes[0]["attendees"])
    return mine, clashes[0], end


async def golden(t):
    mine, clash, after = await _prepare(t)
    length = datetime.fromisoformat(clash["end"]) - datetime.fromisoformat(clash["start"])
    blocked = [(s, e) for s, e in busy(mine, ME) if s != datetime.fromisoformat(clash["start"])]
    for guest in clash["attendees"]:
        if guest != ME:
            blocked += busy(events(await t("get_events", calendar_id=guest, **THU)), guest)
    slot = after
    while not free(blocked, slot, slot + length):
        slot += timedelta(minutes=15)
    await t("modify_event", event_id=clash["id"], start_time=hhmm(slot), end_time=hhmm(slot + length))
    return (
        f"Moved your 1:1 with Rahul to 15:00–15:30. It clashed with Sprint demo prep, which I moved to "
        f"{slot:%H:%M}–{slot + length:%H:%M} (15:30 has the external Brightline sync, and Meera is busy at 16:00)."
    )


async def negative(t):
    """Trap taken: move the clashing meeting to the next half hour without checking (15:30, the Brightline slot)."""
    _, clash, after = await _prepare(t)
    await t("modify_event", event_id=clash["id"], start_time=hhmm(after), end_time=hhmm(after + timedelta(minutes=30)))
    return "Done."
