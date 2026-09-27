"""sh_04: new spreadsheet with one tab per category (Vendor, Month, Amount) plus Totals."""

from _lib import js, pick, sheet_rows


def amount(text: str) -> int:
    return int(text.replace("₹", "").replace(",", ""))


async def _run(t, keep):
    sid = pick(js(await t("list_spreadsheets"))["spreadsheets"], name="Platform Budget 2026")["id"]
    items = sheet_rows(await t("read_sheet_values", spreadsheet_id=sid, range_name="Line Items!A1:E100"))[1:]
    by_cat: dict[str, list] = {}
    for vendor, category, month, value, status in items:
        if keep(status):
            by_cat.setdefault(category, []).append([vendor, month, str(amount(value))])
    new = js(await t("create_spreadsheet", title="Category Spend Q3", sheet_names=list(by_cat) + ["Totals"]))["spreadsheet_id"]
    for category, rows in by_cat.items():
        table = [["Vendor", "Month", "Amount"]] + rows
        await t("modify_sheet_values", spreadsheet_id=new, range_name=f"{category}!A1:C{len(table)}", values=table)
    totals = [["Category", "Total"]] + [[c, str(sum(int(r[2]) for r in rows))] for c, rows in by_cat.items()]
    await t("modify_sheet_values", spreadsheet_id=new, range_name=f"Totals!A1:B{len(totals)}", values=totals)


async def golden(t):
    await _run(t, lambda status: True)
    return "Created 'Category Spend Q3' with tabs Infra, Observability, Tooling, Travel and Totals (Infra ₹5,22,500, Observability ₹1,72,550, Tooling ₹1,81,500, Travel ₹97,450)."


async def negative(t):
    """Trap taken: drop Rejected rows (the prompt says all statuses)."""
    await _run(t, lambda status: status != "Rejected")
    return "Done."
