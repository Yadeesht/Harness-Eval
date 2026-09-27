"""sh_05: apply Samantha's comment on the Hiring Pipeline (Pillai, not Pillay), reply, resolve."""

import re

from _lib import comments, js, pick, sheet_rows


async def _prepare(t):
    sid = pick(js(await t("list_spreadsheets"))["spreadsheets"], name="Hiring Pipeline")["id"]
    ask = next(c for c in comments(await t("read_spreadsheet_comments", spreadsheet_id=sid)) if c["author"] == "Samantha Lee" and not c["resolved"])
    rows = sheet_rows(await t("read_sheet_values", spreadsheet_id=sid))
    return sid, ask, rows


def _row_of(rows, name):
    return next(i for i, r in enumerate(rows) if r[0] == name) + 1


async def _finish(t, sid, ask):
    await t("reply_to_spreadsheet_comment", spreadsheet_id=sid, comment_id=ask["id"], reply_content="Updated")
    await t("resolve_spreadsheet_comment", spreadsheet_id=sid, comment_id=ask["id"])


async def golden(t):
    sid, ask, rows = await _prepare(t)
    changes = re.findall(r'(?:move|mark) ([A-Z]\w+ [A-Z]\w+) (?:to|as) "(\w+)"', ask["content"])
    assert changes == [("Divya Menon", "Offer"), ("Rakesh Pillai", "Rejected")], changes
    for name, stage in changes:
        await t("modify_sheet_values", spreadsheet_id=sid, range_name=f"Candidates!C{_row_of(rows, name)}", values=[[stage]])
    await _finish(t, sid, ask)
    return "Moved Divya Menon to Offer and marked Rakesh Pillai (Backend Engineer) as Rejected, replied 'Updated' and resolved Samantha's comment."


async def negative(t):
    """Trap taken: reject Rakesh Pillay (the Data Engineer) instead of Rakesh Pillai."""
    sid, ask, rows = await _prepare(t)
    await t("modify_sheet_values", spreadsheet_id=sid, range_name=f"Candidates!C{_row_of(rows, 'Divya Menon')}", values=[["Offer"]])
    await t("modify_sheet_values", spreadsheet_id=sid, range_name=f"Candidates!C{_row_of(rows, 'Rakesh Pillay')}", values=[["Rejected"]])
    await _finish(t, sid, ask)
    return "Done."
