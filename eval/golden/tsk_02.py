"""tsk_02: new 'Q4 Planning' task; move open, undated Q4 tasks under it."""

from _lib import js, pick, task_items


async def _prepare(t):
    work = pick(js(await t("list_task_lists"))["task_lists"], title="Work")["id"]
    items = task_items(await t("list_tasks", task_list_id=work))
    parent = js(await t("create_task", task_list_id=work, title="Q4 Planning", due="2026-10-30T00:00:00Z"))["task_id"]
    return work, items, parent


async def golden(t):
    work, items, parent = await _prepare(t)
    for item in items:
        if "Q4" in item["title"] and item["status"] == "needsAction" and not item["due"]:
            await t("move_task", task_list_id=work, task_id=item["id"], parent=parent)
    return "Created 'Q4 Planning' (due 30 Oct) and moved 'Q4 hiring plan draft', 'Draft Q4 budget asks' and 'Q4 on-call schedule' under it."


async def negative(t):
    """Traps taken: ignore the due-date and open filters (moves the dated and completed Q4 tasks too)."""
    work, items, parent = await _prepare(t)
    for item in items:
        if "Q4" in item["title"]:
            await t("move_task", task_list_id=work, task_id=item["id"], parent=parent)
    return "Done."
