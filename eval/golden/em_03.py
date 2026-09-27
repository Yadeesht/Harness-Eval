"""em_03: label + archive the last 30 days of CloudNest billing mail, nothing else."""

import re

from _lib import js

LABEL = "Vendors/CloudNest/Billing"
BILLING = re.compile(r"\b(invoice|receipt)\b", re.I)


async def _billing(t, query):
    found = js(await t("search_emails", query=query))["emails"]
    return [m for m in found if BILLING.search(m["subject"]) and "billing@" in m["from"]]


async def _label_and_archive(t, mails):
    labels = js(await t("list_labels"))["labels"]
    assert not any(l["name"] == LABEL for l in labels)
    label_id = js(await t("create_label", name=LABEL))["label_id"]
    for m in mails:
        await t("apply_label", email_id=m["id"], label_id=label_id)
        await t("archive_email", email_id=m["id"])


async def golden(t):
    mails = await _billing(t, "from:cloudnest.example after:2026/09/07")
    assert len(mails) == 3, [m["subject"] for m in mails]
    await _label_and_archive(t, mails)
    return "Created 'Vendors/CloudNest/Billing', labelled and archived 3 billing emails (Aug receipt, Sep invoice and its revision)."


async def negative(t):
    """Trap taken: no date window, so the August invoice and July mail are swept up too."""
    await _label_and_archive(t, await _billing(t, "from:cloudnest.example"))
    return "Done."
