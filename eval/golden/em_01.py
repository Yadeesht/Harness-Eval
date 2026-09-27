"""em_01: draft (not send) the revised September invoice to Priya Nair in Finance."""

from _lib import grab, js, pick


async def _invoice(t, revised=True):
    found = js(await t("search_emails", query="CloudNest invoice September"))["emails"]
    mail = pick(found, subject="Revised") if revised else pick(found, subject="CloudNest invoice CN-2026-09 ")
    body = js(await t("read_email", email_id=mail["id"]))["content"]
    return grab(r"Amount due: (₹[\d,]+)", body), grab(r"Due date: (\d+ \w+ \d{4})", body)


async def _priya_nair(t):
    found = js(await t("search_emails", query="from:(Priya Nair)"))["emails"]
    return grab(r"<(.+)>", found[0]["from"])


async def golden(t):
    amount, due = await _invoice(t)
    to = await _priya_nair(t)
    assert to == "priya.nair@kestrel.example"
    await t(
        "create_draft",
        recipient_id=to,
        subject="CloudNest invoice CN-2026-09R for processing",
        message=f"Hi Priya,\n\nCould you please process CloudNest's revised September invoice (CN-2026-09R)? Amount due: {amount}, due date: {due}. It replaces CN-2026-09.\n\nThanks,\nYadeesh",
    )
    return f"Drafted (not sent) an email to Priya Nair with the revised invoice: {amount}, due {due}."


async def negative(t):
    """Trap taken: use the superseded CN-2026-09 amount and due date."""
    amount, due = await _invoice(t, revised=False)
    to = await _priya_nair(t)
    await t("create_draft", recipient_id=to, subject="CloudNest invoice for processing", message=f"Hi Priya, please process CloudNest's September invoice: {amount}, due {due}.")
    return "Drafted."
