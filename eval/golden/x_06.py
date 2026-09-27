"""x_06: Farah's numbered PRD feedback -> one comment each on 'Service Mesh PRD', then confirm the count."""

import re

from _lib import js, pick


async def _points(t, subject):
    mail = pick(js(await t("search_emails", query="from:farah.khan@kestrel.example PRD"))["emails"], subject=subject)
    body = js(await t("read_email", email_id=mail["id"]))["content"]
    return re.findall(r"\d\. (.+?\.)(?= \d\.| Thanks|$)", body)  # the list arrives flattened on one line


async def _comment(t, doc_name, points):
    docs = js(await t("search_docs", query="Service Mesh PRD"))["docs"]
    doc = next(d for d in docs if d["name"] == doc_name)
    for p in points:
        await t("create_document_comment", document_id=doc["id"], comment_content=p)


async def golden(t):
    points = await _points(t, "Feedback on the Service Mesh PRD")
    assert len(points) == 4, points
    await _comment(t, "Service Mesh PRD", points)
    await t("send_email", recipient_id="farah.khan@kestrel.example", subject="Re: Feedback on the Service Mesh PRD", message="Hi Farah,\n\nThanks for the feedback. I added 4 comments to the Service Mesh PRD, one for each of your points.\n\nYadeesh")
    return "Added Farah's 4 points as comments on the Service Mesh PRD and emailed her to confirm."


async def negative(t):
    """Traps taken: comment on the archived v0 doc, and include the two older v0 notes (6 comments)."""
    points = await _points(t, "Feedback on the Service Mesh PRD") + await _points(t, "Early thoughts")
    await _comment(t, "Service Mesh PRD v0 (archived)", points)
    await t("send_email", recipient_id="farah.khan@kestrel.example", subject="PRD comments", message=f"I added {len(points)} comments.")
    return "Done."
