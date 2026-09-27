"""x_10: append Farah's agenda points and the Service Mesh PRD link to tomorrow's PRD Review description."""

import re

from _lib import events, js, pick

THU = {"time_min": "2026-10-08T00:00:00", "time_max": "2026-10-09T00:00:00", "detailed": True, "query": "PRD Review"}


async def _prepare(t):
    mail = pick(js(await t("search_emails", query="from:farah.khan@kestrel.example PRD Review agenda"))["emails"], subject="Agenda for Thursday")
    body = js(await t("read_email", email_id=mail["id"]))["content"]
    points = re.findall(r"\d\. (.+?)(?= \d\.|$)", body)
    review = pick(events(await t("get_events", **THU)), summary="PRD Review")
    doc = next(d for d in js(await t("search_docs", query="Service Mesh PRD"))["docs"] if d["name"] == "Service Mesh PRD")
    addition = "Agenda:\n" + "\n".join(f"{i}. {p}" for i, p in enumerate(points, 1)) + f"\n\nPRD: {doc['web_view_link']}"
    return review, addition


async def golden(t):
    review, addition = await _prepare(t)
    await t("modify_event", event_id=review["id"], description=review["description"] + "\n\n" + addition)
    return "Added Farah's three agenda points and the Service Mesh PRD link to Thursday's PRD Review, keeping the existing description."


async def negative(t):
    """Trap taken: replace the description instead of appending."""
    review, addition = await _prepare(t)
    await t("modify_event", event_id=review["id"], description=addition)
    return "Done."
