"""em_02: remind only the people who haven't sent their Q4 OKR draft."""

import re

from _lib import js, pick


async def _status(t):
    ask = pick(js(await t("search_emails", query="in:sent OKR"))["emails"], subject="Q4 OKR drafts")
    asked = re.findall(r"[\w.]+@kestrel\.example", js(await t("read_email", email_id=ask["id"]))["to"])
    asked = [a for a in asked if a != "yadeesh@kestrel.example"]
    replies = js(await t("search_emails", query="OKR after:2026/09/28 -in:sent"))["emails"]
    sent_draft = set()
    for r in replies:
        sender = re.search(r"<(.+)>", r["from"]).group(1)
        body = js(await t("read_email", email_id=r["id"]))["content"]
        if re.search(r"\bO1\b", body):  # the draft itself, not a promise
            sent_draft.add(sender)
    return asked, sent_draft


async def _remind(t, people):
    for to in people:
        await t("send_email", recipient_id=to, subject="Reminder: Q4 OKR draft", message="Hi,\n\nA quick reminder to send me your draft Q4 OKRs when you can.\n\nThanks,\nYadeesh")


async def golden(t):
    asked, done = await _status(t)
    assert len(asked) == 4 and len(done) == 2, (asked, done)
    await _remind(t, [a for a in asked if a not in done])
    return "Reminded Karthik and Neha. Meera and Arjun Mehta already sent their drafts."


async def negative(t):
    """Trap taken: treat Karthik's reply as done (he only promised the draft)."""
    asked, done = await _status(t)
    replied = done | {"karthik.s@kestrel.example"}
    await _remind(t, [a for a in asked if a not in replied])
    return "Reminded Neha."
