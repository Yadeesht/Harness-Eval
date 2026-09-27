"""x_09: on-call handovers at 11:00 on each week's first working day (holidays skipped), this + previous primary."""

from datetime import datetime, timedelta

from _lib import events, js, pick, sheet_rows


async def _prepare(t):
    sid = pick(js(await t("list_spreadsheets"))["spreadsheets"], name="On-call Rotation Q4")["id"]
    rows = sheet_rows(await t("read_sheet_values", spreadsheet_id=sid))[1:]
    cals = js(await t("list_calendars"))["calendars"]
    email = {c["summary"]: c["id"] for c in cals}
    holidays_cal = pick(cals, summary="Holidays")["id"]
    holidays = {e["start"][:10] for e in events(await t("get_events", calendar_id=holidays_cal, time_min="2026-10-01T00:00:00", time_max="2026-11-01T00:00:00"))}
    return rows, email, holidays


async def _book(t, rows, email, first_day):
    for prev, row in zip(rows, rows[1:]):
        start = datetime.strptime(row[0], "%d/%m/%Y")
        if start.month != 10 or start.day < 12:
            continue
        day = first_day(start)
        await t(
            "create_event",
            summary="On-call handover",
            start_time=f"{day:%Y-%m-%d}T11:00:00",
            end_time=f"{day:%Y-%m-%d}T11:30:00",
            attendees=[email[row[1]], email[prev[1]]],
        )


async def golden(t):
    rows, email, holidays = await _prepare(t)

    def first_working(day):
        while day.weekday() >= 5 or f"{day:%Y-%m-%d}" in holidays:
            day += timedelta(days=1)
        return day

    await _book(t, rows, email, first_working)
    return "Created 3 handovers: Mon 12 Oct (Meera, Karthik), Wed 21 Oct (Neha, Meera; 19 and 20 Oct are holidays), Mon 26 Oct (Arjun, Neha), all 11:00–11:30."


async def negative(t):
    """Trap taken: skip only one holiday (the second handover lands on Tue 20 Oct, also a holiday)."""
    rows, email, holidays = await _prepare(t)
    await _book(t, rows, email, lambda day: day + timedelta(days=1) if f"{day:%Y-%m-%d}" in holidays else day)
    return "Done."
