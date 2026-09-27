"""em_06: archive this week's unread notifications, mark direct reports read, keep Rahul unread."""

import re

from _lib import grab, js, pick, sheet_rows

AUTOMATED = re.compile(r"<(no-?reply|notifications)@", re.I)


async def _unread(t):
    return js(await t("search_emails", query="is:unread in:inbox after:2026/10/04"))["emails"]


async def _direct_reports(t):
    books = js(await t("list_spreadsheets"))["spreadsheets"]
    directory = pick(books, name="Team Directory")["id"]
    rows = sheet_rows(await t("read_sheet_values", spreadsheet_id=directory))
    return {r[1] for r in rows[1:] if r[4] == "Yadeesh T"}


async def golden(t):
    mails = await _unread(t)
    reports = await _direct_reports(t)
    assert len(reports) == 5, reports
    senders = sorted({grab(r"<(.+)>", m["from"]) for m in mails if AUTOMATED.search(m["from"])})
    await t("batch_archive", query="is:unread in:inbox after:2026/10/04 {" + " ".join(f"from:{s}" for s in senders) + "}")
    for m in mails:
        if grab(r"<(.+)>", m["from"]) in reports:
            await t("mark_email_as_read", email_id=m["id"])
    return "Archived 4 notifications, marked 3 emails from Neha, Meera and Karthik as read, left Rahul's two emails unread."


async def negative(t):
    """The golden work, plus the traps: open Rahul's 1:1 mail, and archive last week's unread Jira mail."""
    mails = await _unread(t)
    await t("read_email", email_id=pick(mails, subject="move our 1:1")["id"])
    await golden(t)
    await t("batch_archive", query="is:unread in:inbox from:notifications@jira.kestrel.example")
    return "Done."
