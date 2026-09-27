"""x_04: revised CloudNest invoice vs monthly budget; >10% over -> sheet comment, variance doc, mail Priya Nair the link."""

from _lib import grab, js, pick, sheet_rows


def amount(text: str) -> int:
    return int(text.replace("₹", "").replace(",", ""))


async def _numbers(t, revised=True):
    found = js(await t("search_emails", query="CloudNest invoice September"))["emails"]
    mail = pick(found, subject="Revised") if revised else pick(found, subject="CloudNest invoice CN-2026-09 ")
    invoice = amount(grab(r"Amount due: (₹[\d,]+)", js(await t("read_email", email_id=mail["id"]))["content"]))
    sid = pick(js(await t("list_spreadsheets"))["spreadsheets"], name="Platform Budget 2026")["id"]
    rows = sheet_rows(await t("read_sheet_values", spreadsheet_id=sid, range_name="Monthly Budget!A1:C20"))
    budget = amount(next(r for r in rows if r[0] == "CloudNest")[2])
    return sid, invoice, budget


async def _act(t, sid, invoice, budget):
    diff = invoice - budget
    pct = diff / budget * 100
    assert pct > 10
    await t("create_spreadsheet_comment", spreadsheet_id=sid, comment_content=f"CloudNest September invoice ₹{invoice:,} is {pct:.2f}% over the monthly budget of ₹{budget:,}.")
    doc = js(await t("create_doc", title="CloudNest September Variance", content=(
        f"CloudNest September Variance\nInvoice amount: ₹{invoice:,}\nMonthly budget: ₹{budget:,}\nDifference: ₹{diff:,}\nOver budget by: {pct:.2f}%"
    )))["document_id"]
    priya = grab(r"<(.+)>", js(await t("search_emails", query="from:(Priya Nair)"))["emails"][0]["from"])
    link = f"https://docs.google.com/document/d/{doc}/edit"
    await t("send_email", recipient_id=priya, subject="CloudNest September variance", message=f"Hi Priya,\n\nCloudNest's September invoice is {pct:.2f}% over budget. Details: {link}\n\nThanks,\nYadeesh")
    return diff, pct


async def golden(t):
    sid, invoice, budget = await _numbers(t)
    diff, pct = await _act(t, sid, invoice, budget)
    return f"The revised invoice (₹{invoice:,}) is ₹{diff:,} ({pct:.2f}%) over the ₹{budget:,} budget: commented on the sheet, created the variance doc and emailed Priya Nair the link."


async def negative(t):
    """Trap taken: the superseded CN-2026-09 invoice (₹1,92,400)."""
    sid, invoice, budget = await _numbers(t, revised=False)
    await _act(t, sid, invoice, budget)
    return "Done."
