"""x_03: my open items from the 28 Sep notes -> Work tasks; everyone else gets one mail with only their items."""

import re
from datetime import datetime

from _lib import js, open_items, pick, sheet_rows


async def _items(t, source="28 Sep"):
    docs = js(await t("search_docs", query="Platform Weekly Sync"))["docs"]
    return js(await t("get_doc_content", document_id=pick(docs, name=source)["id"]))["content"]


async def _directory(t):
    sid = pick(js(await t("list_spreadsheets"))["spreadsheets"], name="Team Directory")["id"]
    return {r[0]: r[1] for r in sheet_rows(await t("read_sheet_values", spreadsheet_id=sid))[1:]}


async def _mail(t, directory, groups):
    for owner, items in groups.items():
        if owner.startswith("Yadeesh"):
            continue
        body = "Hi,\n\nYour open action items from the 28 Sep Platform weekly sync:\n" + "\n".join(f"- {i}" for i in items) + "\n\nThanks,\nYadeesh"
        await t("send_email", recipient_id=directory[owner], subject="Your open action items (28 Sep sync)", message=body)


async def golden(t):
    groups = open_items(await _items(t))
    work = pick(js(await t("list_task_lists"))["task_lists"], title="Work")["id"]
    for item in groups["Yadeesh T"]:
        title, due = re.match(r"(.+) \(due (.+)\)$", item).groups()
        await t("create_task", task_list_id=work, title=title, due=datetime.strptime(due, "%d %b %Y").strftime("%Y-%m-%dT00:00:00Z"))
    await _mail(t, await _directory(t), groups)
    return "Added your 2 open items to Work (capacity planning meeting due 16 Oct, hiring plan due 12 Oct) and emailed Vikram, Neha, Karthik and Meera their own open items."


async def negative(t):
    """Trap taken: Karthik's mail still lists the capacity model (its 21 Sep owner)."""
    groups = open_items(await _items(t))
    work = pick(js(await t("list_task_lists"))["task_lists"], title="Work")["id"]
    for item in groups["Yadeesh T"]:
        title, due = re.match(r"(.+) \(due (.+)\)$", item).groups()
        await t("create_task", task_list_id=work, title=title, due=datetime.strptime(due, "%d %b %Y").strftime("%Y-%m-%dT00:00:00Z"))
    groups["Karthik Subramanian"].append("Capacity model v1")
    await _mail(t, await _directory(t), groups)
    return "Done."
