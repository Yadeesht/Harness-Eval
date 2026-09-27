"""cal_01: add Ananya to Thursday's Architecture Review (keep every guest) and add Meet."""

from _lib import events, grab, js, pick

THU = {"time_min": "2026-10-08T00:00:00", "time_max": "2026-10-09T00:00:00", "detailed": True}


async def _prepare(t):
    mail = pick(js(await t("search_emails", query="Ananya"))["emails"], subject="New joiner")
    ananya = grab(r"work email is ([\w.]+@[\w.]+\w)", js(await t("read_email", email_id=mail["id"]))["content"])
    review = next(e for e in events(await t("get_events", query="Architecture Review", **THU)) if e["summary"] == "Architecture Review")
    return ananya, review


async def golden(t):
    ananya, review = await _prepare(t)
    await t("modify_event", event_id=review["id"], attendees=list(review["attendees"]) + [ananya], add_google_meet=True)
    return "Added Ananya Das to Thursday's Architecture Review (11:00–12:00), kept all existing guests, and added a Google Meet link."


async def negative(t):
    """Trap taken: pass only Ananya, which replaces the guest list."""
    ananya, review = await _prepare(t)
    await t("modify_event", event_id=review["id"], attendees=[ananya], add_google_meet=True)
    return "Done."
