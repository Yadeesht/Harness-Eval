"""em_05: answer pending Sep/Oct expense requests, one mail per person."""

import re

from _lib import js

APPROVE, RECEIPT = "approved", "receipt"


async def _requests(t):
    found = js(await t("search_emails", query="subject:(expense approval) after:2026/08/31"))["emails"]
    sent = js(await t("search_emails", query="in:sent subject:(expense approval)"))["emails"]
    answered = {re.sub(r"^re:\s*", "", s["subject"], flags=re.I) for s in sent}
    pending = {}
    for mail in found:
        if mail["from"].startswith("Yadeesh") or mail["subject"] in answered:
            continue
        item, amount = re.search(r"Expense approval: (.+) \(₹([\d,]+)\)", mail["subject"]).groups()
        address = re.search(r"<(.+)>", mail["from"]).group(1)
        pending.setdefault(address, []).append((item, int(amount.replace(",", ""))))
    return pending


def _body(items):
    lines = []
    for item, amount in items:
        if amount <= 5000:
            lines.append(f"- {item} (₹{amount:,}): approved.")
        else:
            lines.append(f"- {item} (₹{amount:,}): please send me the receipt before I approve it.")
    return "Hi,\n\nYour pending expense requests:\n" + "\n".join(lines) + "\n\nThanks,\nYadeesh"


async def golden(t):
    pending = await _requests(t)
    assert len(pending) == 4, pending
    for address, items in pending.items():
        await t("send_email", recipient_id=address, subject="Your expense approval requests", message=_body(items))
    return "Replied to Neha, Arjun Mehta, Meera (one mail covering both requests) and Karthik."


async def negative(t):
    """Traps taken: Meera gets two separate mails, and Vikram's August request is answered too."""
    pending = await _requests(t)
    for address, items in pending.items():
        for item in items:
            await t("send_email", recipient_id=address, subject=f"Re: Expense approval: {item[0]}", message=_body([item]))
    await t("send_email", recipient_id="vikram.rao@kestrel.example", subject="Re: Expense approval: USB-C dock", message=_body([("USB-C dock", 2000)]))
    return "Done."
