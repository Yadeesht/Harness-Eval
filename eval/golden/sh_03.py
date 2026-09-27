"""sh_03: normalise Attending, keep each person's latest response, add a Summary tab."""

from collections import Counter
from datetime import datetime

from _lib import js, pick, sheet_rows

YES = {"yes", "y", "true"}


async def _rows(t):
    books = js(await t("list_spreadsheets"))["spreadsheets"]
    sid = pick(books, name="Offsite RSVPs")["id"]
    rows = sheet_rows(await t("read_sheet_values", spreadsheet_id=sid))
    return sid, rows[0], rows[1:]


def _latest(rows, keep_first=False):
    by_email = {}
    for row in rows:
        stamp = datetime.strptime(row[0], "%d/%m/%Y %H:%M:%S")
        key = row[2].lower()
        if key not in by_email or (stamp > by_email[key][0]) != keep_first:
            by_email[key] = (stamp, row)
    kept = sorted(by_email.values(), key=lambda p: p[0])
    return [[r[0], r[1], r[2], "Yes" if r[3].lower() in YES else "No", r[4], r[5]] for _, r in kept]


async def _write(t, sid, total, kept):
    await t("modify_sheet_values", spreadsheet_id=sid, range_name=f"Responses!A2:F{len(kept) + 1}", values=kept)
    await t("modify_sheet_values", spreadsheet_id=sid, range_name=f"Responses!A{len(kept) + 2}:F{total + 1}", clear_values=True)
    diets = Counter((r[4] or "None") for r in kept if r[3] == "Yes")
    await t("create_sheet", spreadsheet_id=sid, sheet_name="Summary")
    table = [["Dietary preference", "Attending"]] + [[d, str(n)] for d, n in diets.most_common()]
    await t("modify_sheet_values", spreadsheet_id=sid, range_name=f"Summary!A1:B{len(table)}", values=table)


async def golden(t):
    sid, _, rows = await _rows(t)
    kept = _latest(rows)
    assert len(kept) == 13
    await _write(t, sid, len(rows), kept)
    return "Normalised Attending, removed 5 duplicate responses (kept the latest), and added a Summary tab."


async def negative(t):
    """Trap taken: keep each person's first response instead of the latest."""
    sid, _, rows = await _rows(t)
    await _write(t, sid, len(rows), _latest(rows, keep_first=True))
    return "Done."
