"""cal_04: all-day OOO 28-30 Oct (exclusive end), cancel only my own 1:1s in that window."""

from _lib import events

WINDOW = {"time_min": "2026-10-28T00:00:00", "time_max": "2026-10-31T00:00:00", "detailed": True, "max_results": 100}
ME = "yadeesh@kestrel.example"


async def _run(t, end_date, own_only):
    await t("create_event", summary="Out of office (leave)", start_time="2026-10-28", end_time=end_date)
    for e in events(await t("get_events", **WINDOW)):
        if e["summary"].startswith("1:1") and (e["organizer"] == ME or not own_only):
            await t("delete_event", event_id=e["id"])


async def golden(t):
    await _run(t, "2026-10-31", own_only=True)
    return (
        "Blocked 28–30 Oct as out of office and cancelled your 1:1s with Meera (28), Rahul (29) and Karthik (30). "
        "The 1:1 on the 29th with Priya Raman is organised by her, so I left it."
    )


async def negative(t):
    """Traps taken: all-day end = 30 Oct (Friday not covered) and Priya Raman's 1:1 cancelled too."""
    await _run(t, "2026-10-30", own_only=False)
    return "Done."
