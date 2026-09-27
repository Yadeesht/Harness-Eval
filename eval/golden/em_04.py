"""em_04: delete Rohan's filter, restore his last-30-days mail, label the ones with deadlines."""

import re

from _lib import js, pick

DEADLINE = re.compile(r"\b(due|by)\s+\d{1,2}\s+\w{3}", re.I)


async def _filter_and_mail(t, query):
    filters = js(await t("list_filters"))["filters"]
    rohan = next(f for f in filters if f["criteria"].get("from") == "rohan.kapoor@kestrel.example")
    return filters, rohan, js(await t("search_emails", query=query))["emails"]


async def _finish(t, mails, deadline):
    for m in mails:
        await t("restore_to_inbox", email_id=m["id"])
    label = pick(js(await t("list_labels"))["labels"], name="Action Required")["id"]
    for m in mails:
        if deadline(m):
            await t("apply_label", email_id=m["id"], label_id=label)


async def golden(t):
    _, rohan, mails = await _filter_and_mail(t, "from:rohan.kapoor@kestrel.example after:2026/09/07")
    await t("delete_filter_tool", filter_id=rohan["id"])
    assert len(mails) == 5
    await _finish(t, mails, lambda m: DEADLINE.search(m["subject"]) and "no action" not in m["subject"].lower())
    return "Deleted the Rohan filter, moved his 5 emails from the last 30 days back to the inbox, labelled the access review (due 12 Oct) and key rotation (by 9 Oct) as Action Required."


async def negative(t):
    """Traps taken: delete every filter, restore all of Rohan's mail, label the 'no action needed' pen test too."""
    filters, _, mails = await _filter_and_mail(t, "from:rohan.kapoor@kestrel.example")
    for f in filters:
        await t("delete_filter_tool", filter_id=f["id"])
    await _finish(t, mails, lambda m: DEADLINE.search(m["subject"]) or "pen test" in m["subject"].lower())
    return "Done."
