"""sh_01: Summary 'Approved total' = sum of Approved Line Items per category."""

from _lib import js, pick, sheet_rows


def amount(text: str) -> int:
    return int(text.replace("₹", "").replace(",", ""))


async def _prepare(t):
    sid = pick(js(await t("list_spreadsheets"))["spreadsheets"], name="Platform Budget 2026")["id"]
    await t("get_spreadsheet_info", spreadsheet_id=sid)
    items = sheet_rows(await t("read_sheet_values", spreadsheet_id=sid, range_name="Line Items!A1:E100"))
    summary = sheet_rows(await t("read_sheet_values", spreadsheet_id=sid, range_name="Summary!A1:C100"))
    return sid, items[1:], [r[0] for r in summary[1:]]


async def _write(t, sid, categories, totals):
    await t("modify_sheet_values", spreadsheet_id=sid, range_name=f"Summary!B2:B{len(categories) + 1}", values=[[str(totals.get(c, 0))] for c in categories])


async def golden(t):
    sid, items, categories = await _prepare(t)
    totals: dict[str, int] = {}
    for vendor, category, month, value, status in items:
        if status == "Approved":
            totals[category] = totals.get(category, 0) + amount(value)
    await _write(t, sid, categories, totals)
    return "Approved totals: Infra ₹3,38,000, Observability ₹1,62,750, Tooling ₹97,500, Travel ₹74,050."


async def negative(t):
    """Trap taken: count Pending rows as approved."""
    sid, items, categories = await _prepare(t)
    totals: dict[str, int] = {}
    for vendor, category, month, value, status in items:
        if status != "Rejected":
            totals[category] = totals.get(category, 0) + amount(value)
    await _write(t, sid, categories, totals)
    return "Done."
