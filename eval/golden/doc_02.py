"""doc_02: make Rahul's edits, reply Done + resolve his comments, reply to others and leave them open."""

from _lib import comments, js, pick

LATER = "I'll review this on Friday"


async def _prepare(t):
    doc = pick(js(await t("search_docs", query="Offsite Agenda"))["docs"], name="Platform Offsite Agenda")
    notes = comments(await t("read_document_comments", document_id=doc["id"]))
    content = js(await t("get_doc_content", document_id=doc["id"]))["content"]
    assert "10:00 Roadmap review" in content and "12:30 Lunch" in content
    return doc["id"], notes


async def _edits(t, doc_id):
    await t("find_and_replace_doc", document_id=doc_id, find_text="Roadmap review", replace_text="Roadmap & OKRs", match_case=True)
    await t("find_and_replace_doc", document_id=doc_id, find_text="12:30 Lunch", replace_text="13:00 Lunch", match_case=True)


async def golden(t):
    doc_id, notes = await _prepare(t)
    await _edits(t, doc_id)
    for c in notes:
        if c["resolved"]:
            continue
        if c["author"] == "Rahul Verma":
            await t("reply_to_document_comment", document_id=doc_id, comment_id=c["id"], reply_content="Done")
            await t("resolve_document_comment", document_id=doc_id, comment_id=c["id"])
        else:
            await t("reply_to_document_comment", document_id=doc_id, comment_id=c["id"], reply_content=LATER)
    return "Renamed 'Roadmap review' to 'Roadmap & OKRs', moved Day 1 lunch to 13:00, replied Done and resolved Rahul's two comments, and replied to Priya's and Farah's."


async def negative(t):
    """Traps taken: also reply to the already-resolved c4, and resolve everyone's comments."""
    doc_id, notes = await _prepare(t)
    await _edits(t, doc_id)
    for c in notes:
        await t("reply_to_document_comment", document_id=doc_id, comment_id=c["id"], reply_content="Done" if c["author"] == "Rahul Verma" else LATER)
        if not c["resolved"]:
            await t("resolve_document_comment", document_id=doc_id, comment_id=c["id"])
    return "Done."
