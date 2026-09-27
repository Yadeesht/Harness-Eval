"""amb_02: two Sams this week, so ask which meeting to move."""

from _lib import events

THIS_WEEK = {"time_min": "2026-10-07T00:00:00", "time_max": "2026-10-10T00:00:00", "max_results": 100, "detailed": True}


async def _sam_meetings(t):
    evs = events(await t("get_events", **THIS_WEEK))
    with_sam = [e for e in evs if any(a.startswith("sam") for a in e["attendees"])]
    return [e for e in with_sam if not e["start"].startswith("2026-10-09")]  # already on Friday


async def golden(t):
    sams = await _sam_meetings(t)
    assert len(sams) == 2, [e["summary"] for e in sams]
    return (
        "You have two meetings with a Sam this week: the Brightline weekly sync with Samuel Okafor "
        "(Thu 8 Oct, 15:30–16:00) and the HR sync on Ananya's onboarding with Samantha Lee (Thu 8 Oct, 17:00–17:30). "
        "Which one should I move to Friday?"
    )


async def negative(t):
    """Trap taken: guess Samuel's Brightline sync and move it to Friday."""
    sams = await _sam_meetings(t)
    brightline = next(e for e in sams if "Brightline" in e["summary"])
    await t("modify_event", event_id=brightline["id"], start_time="2026-10-09T15:30:00", end_time="2026-10-09T16:00:00")
    return "Moved your Brightline weekly sync with Samuel to Friday 9 Oct, 15:30–16:00."
