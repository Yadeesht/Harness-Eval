"""cal_02 — earliest common hour next week for Yadeesh, Meera, Karthik and Neha."""

PEOPLE = ["meera.pillai@kestrel.example", "karthik.s@kestrel.example", "neha.gupta@kestrel.example"]
WEEK = {"time_min": "2026-10-12T00:00:00", "time_max": "2026-10-17T00:00:00", "max_results": 100}


async def golden(t):
    await t("list_calendars")
    for calendar in ["primary"] + PEOPLE:
        await t("get_events", calendar_id=calendar, **WEEK)
    await t(
        "create_event",
        summary="Q4 Capacity Planning",
        start_time="2026-10-13T16:00:00",
        end_time="2026-10-13T17:00:00",
        attendees=PEOPLE,
    )
    return "Booked 'Q4 Capacity Planning' for Tue 13 Oct, 16:00–17:00 IST, with Meera, Karthik and Neha."


async def negative(t):
    """The trap: pick the first free hour on Yadeesh's own calendar (Mon 16:00, Meera is busy)."""
    await t("get_events", **WEEK)
    await t(
        "create_event",
        summary="Q4 Capacity Planning",
        start_time="2026-10-12T16:00:00",
        end_time="2026-10-12T17:00:00",
        attendees=PEOPLE,
    )
    return "Booked 'Q4 Capacity Planning' for Mon 12 Oct, 16:00–17:00 IST."
