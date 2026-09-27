"""cal_06: RSVP audit of next week's meetings I organise: append the line, or cancel at 0 accepted."""

from _lib import events

NEXT_WEEK = {"time_min": "2026-10-12T00:00:00", "time_max": "2026-10-17T00:00:00", "detailed": True, "max_results": 100}
ME = "yadeesh@kestrel.example"
LINE = "Low RSVP — please confirm"


def _audit(evs):
    for e in evs:
        guests = {a: s for a, s in e["attendees"].items() if a != ME}
        if e["organizer"] != ME or not guests:
            continue
        yield e, sum(s == "accepted" for s in guests.values()), len(guests)


def _existing(e):
    return "" if e["description"] in (None, "No Description") else e["description"]


async def golden(t):
    for e, accepted, total in _audit(events(await t("get_events", **NEXT_WEEK))):
        if accepted == 0:
            await t("delete_event", event_id=e["id"])
        elif accepted * 2 < total:
            old = _existing(e)
            await t("modify_event", event_id=e["id"], description=(old + "\n" if old else "") + LINE)
    return (
        "Added 'Low RSVP — please confirm' to the Hiring debrief (1 of 4 accepted) and the Q4 roadmap pre-read (1 of 5), "
        "and cancelled the Budget check-in (0 of 1). Welcome Ananya is at exactly half, so I left it."
    )


async def negative(t):
    """Traps taken: replace the description instead of appending, and treat exactly half as low."""
    for e, accepted, total in _audit(events(await t("get_events", **NEXT_WEEK))):
        if accepted == 0:
            await t("delete_event", event_id=e["id"])
        elif accepted * 2 <= total:
            await t("modify_event", event_id=e["id"], description=LINE)
    return "Done."
