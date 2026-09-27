"""x_05: last week's Interviews calendar -> Hiring Pipeline (Stage 'Onsite done', Interviewer 'Yadeesh')."""

import re

from _lib import events, js, pick, sheet_rows


async def _run(t, time_max):
    cal = pick(js(await t("list_calendars"))["calendars"], summary="Interviews")["id"]
    evs = events(await t("get_events", calendar_id=cal, time_min="2026-09-28T00:00:00", time_max=time_max, max_results=100))
    names = [re.match(r"Interview: (.+?) \(", e["summary"]).group(1) for e in evs if e["summary"].startswith("Interview:")]
    sid = pick(js(await t("list_spreadsheets"))["spreadsheets"], name="Hiring Pipeline")["id"]
    rows = sheet_rows(await t("read_sheet_values", spreadsheet_id=sid))
    for i, row in enumerate(rows):
        if row[0] in names and row[2] not in ("Offer", "Rejected"):
            await t("modify_sheet_values", spreadsheet_id=sid, range_name=f"Candidates!C{i + 1}:D{i + 1}", values=[["Onsite done", "Yadeesh"]])


async def golden(t):
    await _run(t, "2026-10-03T00:00:00")
    return "Updated Divya Menon and Lakshmi Iyer to 'Onsite done' with you as interviewer. Karan Shah is already at Offer, so unchanged."


async def negative(t):
    """Trap taken: window runs to today, so this week's Rakesh Pillai is updated too."""
    await _run(t, "2026-10-07T09:30:00")
    return "Done."
