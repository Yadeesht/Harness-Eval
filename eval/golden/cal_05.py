"""cal_05: Samuel's 45-min call at 10:00 WAT = 14:30 IST, first day next week without an external meeting."""

import re
from datetime import date, datetime, timedelta

from _lib import events, hhmm, js, pick

NEXT_WEEK = {"time_min": "2026-10-12T00:00:00", "time_max": "2026-10-17T00:00:00", "detailed": True, "max_results": 100}


async def _prepare(t):
    mail = pick(js(await t("search_emails", query="from:sam.okafor@brightline.example"))["emails"], subject="Call next week")
    body = js(await t("read_email", email_id=mail["id"]))["content"]
    assert "10:00 my time" in body and "UTC+1" in body and "45-minute" in body
    agenda = re.search(r"Agenda: (.*?) Best", body).group(1)
    return agenda, events(await t("get_events", **NEXT_WEEK))


async def _book(t, day, agenda):
    start = datetime.fromisoformat(f"{day}T14:30:00")  # 10:00 WAT (UTC+1) = 14:30 IST
    await t(
        "create_event",
        summary="Brightline call: Samuel / Yadeesh",
        start_time=hhmm(start),
        end_time=hhmm(start + timedelta(minutes=45)),
        attendees=["sam.okafor@brightline.example"],
        add_google_meet=True,
        description=f"Agenda: {agenda}",
    )


async def golden(t):
    agenda, evs = await _prepare(t)
    external = {e["start"][:10] for e in evs if "T" in e["start"] and any(not a.endswith("@kestrel.example") for a in e["attendees"])}
    day = date(2026, 10, 12)
    while day.isoformat() in external:
        day += timedelta(days=1)
    await _book(t, day.isoformat(), agenda)
    return f"Booked a 45-minute call with Samuel on {day:%a %d %b}, 14:30–15:15 IST (10:00 in Lagos), with a Meet link and his agenda. Monday already has the external CloudNest sync."


async def negative(t):
    """Trap taken: book Monday, which already has an external meeting."""
    agenda, _ = await _prepare(t)
    await _book(t, "2026-10-12", agenda)
    return "Done."
