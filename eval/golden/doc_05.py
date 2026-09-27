"""doc_05: header, bold the 'Open Roles' heading, export as PDF."""

from _lib import js, pick

HEADER = "DRAFT — not for distribution"


async def _doc(t):
    docs = js(await t("search_docs", query="Hiring Plan H2"))["docs"]
    doc_id = pick(docs, name="Hiring Plan H2")["id"]
    elements = js(await t("inspect_doc_structure", document_id=doc_id, detailed=True))["structure"]["elements"]
    return doc_id, elements


async def golden(t):
    doc_id, elements = await _doc(t)
    heading = next(e for e in elements if e.get("text_preview") == "Open Roles\n")
    await t("modify_doc_text", document_id=doc_id, start_index=heading["start_index"], end_index=heading["end_index"] - 1, bold=True)
    await t("update_doc_headers_footers", document_id=doc_id, section_type="header", content=HEADER)
    await t("export_doc_to_pdf", document_id=doc_id, pdf_filename="Hiring Plan H2 — v2")
    return "Added the header, bolded 'Open Roles' and exported 'Hiring Plan H2 — v2.pdf'."


async def negative(t):
    """Trap taken: bold the first 'open roles' text (in the Summary sentence) instead of the heading."""
    doc_id, elements = await _doc(t)
    summary = next(e for e in elements if "open roles" in e.get("text_preview", ""))
    start = summary["start_index"] + summary["text_preview"].index("open roles")
    await t("modify_doc_text", document_id=doc_id, start_index=start, end_index=start + len("open roles"), bold=True)
    await t("update_doc_headers_footers", document_id=doc_id, section_type="header", content=HEADER)
    await t("export_doc_to_pdf", document_id=doc_id, pdf_filename="Hiring Plan H2 — v2")
    return "Done."
