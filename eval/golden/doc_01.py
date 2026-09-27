"""doc_01: change only the Service Mesh launch date (two places) in 'Q4 Planning — Platform'."""

import re

from _lib import grab, js, pick


async def _prepare(t):
    mail = pick(js(await t("search_emails", query="from:farah.khan@kestrel.example Service Mesh launch"))["emails"], subject="launch date")
    body = js(await t("read_email", email_id=mail["id"]))["content"]
    old, new = grab(r"moves from (\d+ \w+) to (\d+ \w+ \d{4})", body, 1), grab(r"moves from (\d+ \w+) to (\d+ \w+ \d{4})", body, 2)
    doc = pick(js(await t("search_docs", query="Q4 Planning Platform"))["docs"], name="Q4 Planning — Platform")
    content = js(await t("get_doc_content", document_id=doc["id"]))["content"]
    return doc["id"], content, f"{old} 2026", new


async def golden(t):
    doc_id, content, old, new = await _prepare(t)
    lines = [l for l in content.split("\n") if "Service Mesh Migration" in l and old in l]
    assert len(lines) == 2, lines
    for line in lines:
        await t("find_and_replace_doc", document_id=doc_id, find_text=line, replace_text=line.replace(old, new))
    return f"Changed the Service Mesh Migration launch date from {old} to {new} in both places; Billing Revamp still launches on {old}."


async def negative(t):
    """Trap taken: a blanket replace of the date, which also moves Billing Revamp."""
    doc_id, _, old, new = await _prepare(t)
    await t("find_and_replace_doc", document_id=doc_id, find_text=old, replace_text=new)
    return "Done."
