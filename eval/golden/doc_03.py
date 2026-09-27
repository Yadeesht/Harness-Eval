"""doc_03: Payments postmortem action items -> new doc with a sorted Owner/Action/Due table and a footer."""

from datetime import datetime

from _lib import js, pick

TITLE = "Postmortem Action Items — Payments API"
FOOTER = "Confidential — internal only"


async def _items(t):
    doc = pick(js(await t("search_docs", query="Postmortem Payments"))["docs"], name="Payments API outage")
    lines = js(await t("get_doc_content", document_id=doc["id"]))["content"].split("\n")
    start = lines.index("Action items") + 1
    assert lines[start:start + 4] == ["Owner", "Action", "Due", "Tag"]  # the table reads as one cell per line
    cells = [l for l in lines[start + 4:] if l]
    return [cells[i:i + 4] for i in range(0, len(cells), 4)]


async def _write(t, rows):
    doc_id = js(await t("create_doc", title=TITLE))["document_id"]
    await t("create_table_with_data", document_id=doc_id, table_data=[["Owner", "Action", "Due"]] + [r[:3] for r in rows], index=1)
    await t("update_doc_headers_footers", document_id=doc_id, section_type="footer", content=FOOTER)


async def golden(t):
    rows = await _items(t)
    assert len(rows) == 6
    rows.sort(key=lambda r: datetime.strptime(r[2], "%d %b %Y"))
    await _write(t, rows)
    return f"Created '{TITLE}' with the 6 action items sorted by due date (9 Oct to 30 Oct) and the footer '{FOOTER}'."


async def negative(t):
    """Trap taken: copy the rows in the postmortem's order, unsorted."""
    await _write(t, await _items(t))
    return "Done."
