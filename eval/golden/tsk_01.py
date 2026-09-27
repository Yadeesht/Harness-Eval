"""tsk_01: complete done tasks, drop later-dated duplicates, clear completed."""

import re

from _lib import js, pick, task_items

DONE = re.compile(r"\bdone\b", re.I)
NOT_DONE = re.compile(r"\bnot done\b", re.I)


async def _work(t):
    lists = js(await t("list_task_lists"))["task_lists"]
    work = pick(lists, title="Work")["id"]
    return work, task_items(await t("list_tasks", task_list_id=work))


def _duplicates_to_drop(items, keep_later=False):
    by_title = {}
    for item in items:
        if item["status"] != "completed":
            by_title.setdefault(item["title"], []).append(item)
    drop = []
    for copies in by_title.values():
        if len(copies) > 1:
            copies.sort(key=lambda i: i["due"] or "9999", reverse=keep_later)
            drop += copies[1:]
    return drop


async def golden(t):
    work, items = await _work(t)
    for item in items:
        notes = item["notes"] or ""
        if item["status"] == "completed" or not notes:
            continue
        if notes.endswith("..."):
            detail = js(await t("get_task", task_list_id=work, task_id=item["id"]))["message"]
            notes = re.search(r"- Notes: (.*)", detail).group(1)
        if DONE.search(notes) and not NOT_DONE.search(notes):
            await t("update_task", task_list_id=work, task_id=item["id"], status="completed")
    for item in _duplicates_to_drop(items):
        await t("delete_task", task_list_id=work, task_id=item["id"])
    await t("clear_completed_tasks", task_list_id=work)
    return "Completed 2 tasks, deleted 2 later-dated duplicates, cleared completed tasks."


async def negative(t):
    """Traps taken: trust the truncated notes (w1 stays open), complete w4, keep the later-dated copies."""
    work, items = await _work(t)
    for item in items:
        if item["status"] != "completed" and item["notes"] and DONE.search(item["notes"]):
            await t("update_task", task_list_id=work, task_id=item["id"], status="completed")
    for item in _duplicates_to_drop(items, keep_later=True):
        await t("delete_task", task_list_id=work, task_id=item["id"])
    await t("clear_completed_tasks", task_list_id=work)
    return "Done."
