"""x_08: weekly status to Rahul: Work tasks completed since Monday + next week's Brightline meetings."""

from _lib import events, js, pick, task_items


async def _status(t, since):
    work = pick(js(await t("list_task_lists"))["task_lists"], title="Work")["id"]
    done = task_items(await t("list_tasks", task_list_id=work, show_completed=True, show_hidden=True, completed_min=since))
    done = [d["title"] for d in done if d["status"] == "completed"]
    meetings = events(await t("get_events", time_min="2026-10-12T00:00:00", time_max="2026-10-17T00:00:00", query="Brightline"))
    return done, meetings


async def _send(t, done, meetings):
    lines = ["Hi Rahul,", "", "Completed since Monday:"] + [f"- {d}" for d in done]
    lines += ["", "Brightline meetings next week:"] + [f"- {m['summary']}: {m['start'][:10]} {m['start'][11:16]}" for m in meetings]
    await t("send_email", recipient_id="rahul.verma@kestrel.example", subject="Weekly status", message="\n".join(lines + ["", "Yadeesh"]))


async def golden(t):
    done, meetings = await _status(t, "2026-10-04T18:30:00Z")  # Monday 5 Oct 00:00 IST
    assert len(done) == 2 and len(meetings) == 1, (done, meetings)
    await _send(t, done, meetings)
    return "Sent Rahul your status: PR #881 review and Karan Shah's interview feedback done; Brightline sync next week is on Wed 14 Oct, 15:30."


async def negative(t):
    """Trap taken: count everything completed in the last week (includes the 2 Oct timesheet and 1 Oct roadmap comments)."""
    done, meetings = await _status(t, "2026-09-30T18:30:00Z")
    await _send(t, done, meetings)
    return "Done."
