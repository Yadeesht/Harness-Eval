"""doc_04: reconcile the 21 Sep and 28 Sep sync notes into open items grouped by owner."""

import re

from _lib import js, open_items, pick

TITLE = "Open Action Items — 7 Oct"


async def _notes(t):
    docs = js(await t("search_docs", query="Platform Weekly Sync"))["docs"]
    older = js(await t("get_doc_content", document_id=pick(docs, name="21 Sep")["id"]))["content"]
    latest = js(await t("get_doc_content", document_id=pick(docs, name="28 Sep")["id"]))["content"]
    return older, latest


def _content(groups):
    parts = []
    for owner, items in groups.items():
        parts.append(owner)
        parts += [f"- {i}" for i in items]
    return "\n".join(parts)


async def golden(t):
    _, latest = await _notes(t)
    groups = open_items(latest)
    assert sum(len(v) for v in groups.values()) == 7, groups
    await t("create_doc", title=TITLE, content=_content(groups))
    return f"Created '{TITLE}' with 7 open items under {len(groups)} owners (the capacity model is now Vikram's)."


async def negative(t):
    """Traps taken: trust the 21 Sep owners (capacity model under Karthik) and keep closed items (canary plan)."""
    older, _ = await _notes(t)
    groups: dict[str, list[str]] = {}
    for owner, item in re.findall(r"^([A-Z]\w+ [A-Z]\w+): (.+)$", older, re.M):
        groups.setdefault(owner, []).append(item)
    await t("create_doc", title=TITLE, content=_content(groups))
    return "Done."
