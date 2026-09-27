"""x_01: check both calendars for leave, swap the two primaries, confirm by email."""

import re

from _lib import events, js, pick, sheet_rows

LEAVE = re.compile(r"\b(ooo|out of office|leave|vacation|holiday)\b", re.I)
WEEKS = {"time_min": "2026-10-19T00:00:00", "time_max": "2026-10-31T00:00:00", "max_results": 100}


async def _prepare(t):
    mail = pick(js(await t("search_emails", query="from:neha.gupta@kestrel.example on-call swap"))["emails"], subject="swap")
    await t("read_email", email_id=mail["id"])
    await t("list_calendars")
    for cal in ("neha.gupta@kestrel.example", "arjun.mehta@kestrel.example"):
        leave = [e for e in events(await t("get_events", calendar_id=cal, **WEEKS)) if LEAVE.search(e["summary"])]
        assert not leave, leave
    books = js(await t("list_spreadsheets"))["spreadsheets"]
    sid = pick(books, name="On-call Rotation Q4")["id"]
    rows = sheet_rows(await t("read_sheet_values", spreadsheet_id=sid))
    r19 = next(i for i, r in enumerate(rows) if r[0] == "19/10/2026") + 1
    r26 = next(i for i, r in enumerate(rows) if r[0] == "26/10/2026") + 1
    assert rows[r19 - 1][1] == "Neha Gupta" and rows[r26 - 1][1] == "Arjun Mehta"
    return sid, r19, r26


async def _confirm(t):
    for to in ("neha.gupta@kestrel.example", "arjun.mehta@kestrel.example"):
        await t(
            "send_email",
            recipient_id=to,
            subject="On-call swap confirmed",
            message="Hi,\n\nConfirming the on-call swap: Arjun is now primary for the week of 19 Oct and Neha for the week of 26 Oct. The rotation sheet is updated.\n\nThanks,\nYadeesh",
        )


async def golden(t):
    sid, r19, r26 = await _prepare(t)
    await t("modify_sheet_values", spreadsheet_id=sid, range_name=f"Rotation!B{r19}:B{r26}", values=[["Arjun Mehta"], ["Neha Gupta"]])
    await _confirm(t)
    return "Neither Neha nor Arjun has leave in the weeks of 19 or 26 Oct, so I swapped them in the rotation and emailed both."


async def negative(t):
    """Trap taken: swap the secondary column instead of the primaries."""
    sid, r19, r26 = await _prepare(t)
    await t("modify_sheet_values", spreadsheet_id=sid, range_name=f"Rotation!C{r19}:C{r26}", values=[["Meera Pillai"], ["Karthik Subramanian"]])
    await _confirm(t)
    return "Done."
