"""Re-prove the claims world.md makes, on the generated seed.

    .venv/Scripts/python.exe eval/seed/check_seed.py

Calendar claims are brute-forced over 15-minute starts from each person's
calendar as the fake API returns it. Mail claims go through the real tools.
Exits non-zero if any claim fails.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from lab.bind import bind  # noqa: E402
from lab.fake.base import IST  # noqa: E402
from lab.fake.calendar import Calendar, event_bounds  # noqa: E402
from lab.workspace import Workspace  # noqa: E402

import world_data as W  # noqa: E402
from app_tools.tools.google import calendar_tools as cal  # noqa: E402
from app_tools.tools.google import gdocs_tools as gd  # noqa: E402
from app_tools.tools.google import gmail_tools as gm  # noqa: E402
from app_tools.tools.google import gsheet_tools as gs  # noqa: E402
from app_tools.tools.google import gtask_tools as tk  # noqa: E402

logging.disable(logging.INFO)
results: list[tuple[str, bool, str]] = []


def claim(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------


def busy(ws: Workspace, person: str, day: str) -> list[tuple[datetime, datetime]]:
    cal_id = W.addr(person)
    lo = datetime.fromisoformat(day).replace(tzinfo=IST)
    events = Calendar(ws).events().list(calendarId=cal_id, timeMin=lo.isoformat(), timeMax=(lo + timedelta(days=1)).isoformat(), maxResults=250).execute()["items"]
    out = []
    for e in events:
        if e.get("transparency") == "transparent":
            continue
        me = next((a for a in e.get("attendees", []) if a["email"].lower() == cal_id), None)
        if me and me["responseStatus"] == "declined":
            continue
        out.append(event_bounds(e))
    return out


def free_slots(ws, people, days, minutes, lo="10:00", hi="18:00", step=15, exclude=None):
    out = []
    for day in days:
        blocks = {p: busy(ws, p, day) for p in people}
        if exclude:
            blocks = {p: [b for b in bl if b not in exclude] for p, bl in blocks.items()}
        t = datetime.fromisoformat(f"{day}T{lo}").replace(tzinfo=IST)
        end = datetime.fromisoformat(f"{day}T{hi}").replace(tzinfo=IST)
        while t + timedelta(minutes=minutes) <= end:
            s, e = t, t + timedelta(minutes=minutes)
            if all(not (s < be and e > bs) for bl in blocks.values() for bs, be in bl):
                out.append(f"{day} {t:%H:%M}")
            t += timedelta(minutes=step)
    return out


def calendar_claims(ws):
    slots = free_slots(ws, ["yadeesh", "meera.pillai", "karthik.s", "neha.gupta"], ["2026-10-12", "2026-10-13", "2026-10-14"], 60)
    claim("cal_02 earliest common hour is Tue 13 Oct 16:00, unique", slots[:1] == ["2026-10-13 16:00"] and (len(slots) < 2 or slots[1] > "2026-10-13 16:00"), f"first slots {slots[:3]}")

    # cal_03: 1:1 moved to 15:00; demo prep's own slot is freed.
    demo = next(e for e in ws.state["calendar"]["events"].values() if e.get("wid") == "demo_prep")
    demo_bounds = event_bounds(demo)
    after = [s for s in free_slots(ws, ["yadeesh", "meera.pillai", "karthik.s"], ["2026-10-08"], 30, lo="15:30", exclude=[demo_bounds])]
    claim("cal_03 next 30-min slot after the moved 1:1 is 16:30", after[:1] == ["2026-10-08 16:30"], f"slots {after[:3]}")

    tue = free_slots(ws, ["yadeesh"], ["2026-10-13"], 45, lo="14:30", hi="15:15")
    claim("cal_05 Yadeesh free Tue 13 Oct 14:30–15:15", tue == ["2026-10-13 14:30"], str(tue))
    ext = {}
    for day in ["2026-10-12", "2026-10-13"]:
        items = Calendar(ws).events().list(calendarId="primary", timeMin=f"{day}T00:00:00+05:30", timeMax=f"{day}T23:59:00+05:30").execute()["items"]
        ext[day] = [e["summary"] for e in items if any(not a["email"].endswith("@" + W.DOMAIN) for a in e.get("attendees", []))]
    claim("cal_05 Mon 12 has an external meeting, Tue 13 none", bool(ext["2026-10-12"]) and not ext["2026-10-13"], str(ext))

    none = free_slots(ws, ["yadeesh", "rahul.verma", "farah.khan", "meera.pillai"], ["2026-10-08", "2026-10-09"], 120, lo="12:00")
    claim("imp_02 no 2-hour slot Thu/Fri 12:00–18:00", not none, str(none))

    x07 = free_slots(ws, ["yadeesh", "neha.gupta", "karthik.s", "rohan.kapoor", "meera.pillai", "arjun.mehta"], ["2026-11-02"], 30)
    claim("x_07 only 17:00–18:00 fits on Mon 2 Nov", x07 == ["2026-11-02 17:00", "2026-11-02 17:15", "2026-11-02 17:30"], str(x07))

    for p in ["meera.pillai", "neha.gupta", "farah.khan"]:
        n = [s for s in free_slots(ws, [p], ["2026-10-12", "2026-10-13", "2026-10-14"], 30) if s >= "2026-10-12 14:00"]
        claim(f"x_02 {p} has intro slots Mon 14:00–Wed", len(n) >= 10, f"{len(n)} slots")

    for person in ["neha.gupta", "arjun.mehta"]:
        leave = [e["summary"] for day in [f"2026-10-{d}" for d in range(19, 31)] for e in Calendar(ws).events().list(calendarId=W.addr(person), timeMin=f"{day}T00:00:00+05:30", timeMax=f"{day}T23:59:00+05:30").execute()["items"] if any(w in e["summary"].lower() for w in ("ooo", "leave", "out of office"))]
        claim(f"x_01 {person} has no leave 19–30 Oct", not leave, str(leave))


# ---------------------------------------------------------------------------
# Mail, docs, sheets, tasks through the real tools
# ---------------------------------------------------------------------------


async def tool_claims(ws, index):
    wid_of = {v: k for k, v in index["gmail"].items()}

    async def search(q, n=None):
        r = await gm.search_emails(query=q, max_results=n)
        return {wid_of.get(e["id"], e["id"]) for e in r["emails"]}

    unread = await search("is:unread in:inbox after:2026/10/05")
    want = {"jr_412", "jr_415", "gh_881", "hr_timesheet", "ne_swap", "me_canary", "ka_capq", "rh_staff", "rh_move", "fk_prd_fb", "fk_prd_agenda", "so_call"}
    claim("em_06 unread this week is exactly the listed mail", unread == want, f"extra {sorted(unread - want)} missing {sorted(want - unread)}")

    jira = await search("from:notifications@jira.kestrel.example in:inbox")
    claim("imp_01 12 Jira notifications in the inbox", len(jira) == 12, str(len(jira)))

    cloud = await search("from:cloudnest.example after:2026/09/07")
    claim("em_03 CloudNest mail in window", cloud == {"cn_rcpt_aug", "cn_tkt_1", "cn_tkt_1b", "cn_status", "cn_tkt_2", "cn_renewal", "cn_inv_sep", "cn_inv_sep_r"}, str(sorted(cloud)))

    rohan = await search("from:rohan.kapoor@kestrel.example after:2026/09/07")
    claim("em_04 5 Rohan mails in window, all archived", rohan == {"rk_access", "rk_phish", "rk_keys", "rk_hours", "rk_pentest"}, str(sorted(rohan)))
    rohan_inbox = await search("from:rohan.kapoor@kestrel.example in:inbox")
    claim("em_04 none of Rohan's mail is in the inbox", not rohan_inbox, str(rohan_inbox))

    expense = await search("subject:(expense approval)")
    claim("em_05 7 expense requests + 1 answer", expense >= {"ex_v_dock", "ex_k_lunch", "ex_n_taxi", "ex_a_conf", "ex_m_books", "ex_m_monitor", "ex_k_cab"}, str(sorted(expense)))

    body = await gm.read_email(email_id=index["gmail"]["cn_inv_sep_r"])
    claim("read_email shows ₹1,84,500 and 20 Oct 2026", "₹1,84,500" in body["content"] and "20 Oct 2026" in body["content"], body["content"][:120])

    pm = await gd.get_doc_content(document_id=index["docs"]["doc_pm_payments"])
    claim("doc postmortem table reads as flat lines", "Owner\nAction\nDue\nTag\nNeha Gupta\n" in pm["content"], pm["content"][-200:])

    li = json.loads(await gs.read_sheet_values(spreadsheet_id=index["sheets"]["sh_budget"], range_name="Line Items!A1:E17"))["message"]
    claim("budget amounts display as ₹184,500", "'₹184,500'" in li and "'₹12,800'" in li, li[:160])

    rsvp = json.loads(await gs.read_sheet_values(spreadsheet_id=index["sheets"]["sh_rsvp"], range_name="Responses!A1:F18"))["message"]
    claim("RSVP timestamps display as dd/mm/yyyy hh:mm:ss", "'25/09/2026 10:12:00'" in rsvp, rsvp[:200])

    info = json.loads(await gs.get_spreadsheet_info(spreadsheet_id=index["sheets"]["sh_budget"]))["message"]
    claim("budget has 3 highlight rules in the planned order", info.count("NUMBER_GREATER") == 2 and "values=['100000']" in info.split("[1]")[0], info[:400])

    work = await tk.list_tasks(task_list_id=index["tasklists"]["tl_work"])
    claim("Work list: w1 note cut before DONE", "Notes: Context: agreed in the 28 Sep sync" in work and "DONE" not in work.split("Send Q4 capacity model")[1].split("\n- ")[0], "")
    claim("Work list fits one page (<20 tasks)", work.count("(ID: ") == 18 and "Next page token" not in work, str(work.count("(ID: ")))

    # Tool results under Hermes' 50k limit for the broadest calls an agent can make.
    sizes = {
        "search_emails in:anywhere": len(json.dumps(await gm.search_emails(query="in:anywhere"))),
        "list_archived 100": len(json.dumps(await gm.list_archived(max_results=100))),
        "get_unread_emails 30d": len(json.dumps(await gm.get_unread_emails(date=30, max_results=100))),
        "get_events 250 detailed": len(await cal.get_events(time_min="2026-09-01", time_max="2026-12-31", max_results=250, detailed=True)),
        "list_tasks Work": len(await tk.list_tasks(task_list_id=index["tasklists"]["tl_work"], max_results=100)),
        "read_sheet_values RSVP": len(await gs.read_sheet_values(spreadsheet_id=index["sheets"]["sh_rsvp"])),
        "get_doc_content onboarding": len(json.dumps(await gd.get_doc_content(document_id=index["docs"]["doc_onboarding"]))),
    }
    worst = max(sizes.items(), key=lambda kv: kv[1])
    claim("every broad tool result < 50,000 chars", worst[1] < 50_000, f"largest: {worst[0]} = {worst[1]:,}")
    return sizes


def main() -> int:
    seed = json.loads((HERE / "seed.json").read_text(encoding="utf-8"))
    index = json.loads((HERE / "seed_index.json").read_text(encoding="utf-8"))
    ws = bind(Workspace(seed))
    calendar_claims(ws)
    sizes = asyncio.run(tool_claims(ws, index))
    failed = 0
    for name, ok, detail in results:
        failed += not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"\n        {detail}"))
    print("\nlargest tool results:", ", ".join(f"{k} {v:,}" for k, v in sorted(sizes.items(), key=lambda kv: -kv[1])[:3]))
    print(f"\n{len(results) - failed}/{len(results)} claims hold")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
