"""world.md as data. Every graded fact lives here; build_seed.py turns it into the workspace.

Keep this file and eval/design/world.md in step: an item's `wid` is the id
used in world.md, and the "Used by" notes there say which tasks depend on it.
"""

from __future__ import annotations

DOMAIN = "kestrel.example"
NOW = "2026-10-07T09:30:00+05:30"
USER = {"email": f"yadeesh@{DOMAIN}", "name": "Yadeesh T"}


def addr(local: str) -> str:
    return f"{local}@{DOMAIN}"


# ---------------------------------------------------------------------------
# People (world.md §2)
# ---------------------------------------------------------------------------

PEOPLE = [
    # name, email local part, team, role, manager, location, in Team Directory
    ("Yadeesh T", "yadeesh", "Platform", "Engineering Manager", "Rahul Verma", "Bengaluru", True),
    ("Meera Pillai", "meera.pillai", "Platform", "Senior Engineer (Tech Lead)", "Yadeesh T", "Bengaluru", True),
    ("Karthik Subramanian", "karthik.s", "Platform", "Engineer", "Yadeesh T", "Chennai", True),
    ("Arjun Mehta", "arjun.mehta", "Platform", "Engineer", "Yadeesh T", "Bengaluru", True),
    ("Neha Gupta", "neha.gupta", "Platform", "SRE Lead", "Yadeesh T", "Pune", True),
    ("Vikram Rao", "vikram.rao", "Platform", "Engineer", "Yadeesh T", "Bengaluru", True),
    ("Rahul Verma", "rahul.verma", "Engineering", "Director of Engineering", "Kavita Menon", "Bengaluru", True),
    ("Farah Khan", "farah.khan", "Product", "Product Manager, Platform", "Anil Kumar", "Mumbai", True),
    ("Priya Raman", "priya.raman", "Design", "Design Lead", "Anil Kumar", "Bengaluru", True),
    ("Priya Nair", "priya.nair", "Finance", "Finance Business Partner", "Suresh Iyer", "Bengaluru", True),
    ("Samantha Lee", "samantha.lee", "People", "People Partner", "Suresh Iyer", "Bengaluru", True),
    ("Rohan Kapoor", "rohan.kapoor", "Security", "Security Engineer", "Rahul Verma", "Delhi", True),
    ("Deepak Joshi", "deepak.joshi", "IT", "IT Operations", "Suresh Iyer", "Bengaluru", True),
    ("Isha Bhatt", "isha.bhatt", "Operations", "Office & Events Coordinator", "Suresh Iyer", "Bengaluru", True),
    ("Ananya Das", "ananya.das", "Platform", "Engineer (joins Mon 12 Oct)", "Yadeesh T", "Bengaluru", False),
]
NAME = {local: name for name, local, *_ in PEOPLE}


def who(local: str) -> str:
    """'Name <address>' for an internal person."""
    return f"{NAME[local]} <{addr(local)}>"


EXTERNAL = {
    "samuel": "Samuel Okafor <sam.okafor@brightline.example>",
    "arjun_iyer": "Arjun Iyer <arjun.iyer@cloudnest.example>",
    "cn_billing": "CloudNest Billing <billing@cloudnest.example>",
    "cn_support": "CloudNest Support <support@cloudnest.example>",
    "cn_status": "CloudNest Status <status@cloudnest.example>",
    "linh": "Linh Tran <linh.tran@observa.example>",
    "jira": f"Jira <notifications@jira.{DOMAIN}>",
    "github": "GitHub <noreply@github.example>",
    "hr_portal": f"Kestrel HR Portal <no-reply@{DOMAIN}>",
    "newstack": "The New Stack <digest@thenewstack.example>",
    "medium": "Medium Daily Digest <noreply@medium.example>",
    "hirewell": "Hirewell Talent <talent@hirewell.example>",
}

# ---------------------------------------------------------------------------
# Gmail (world.md §4)
# ---------------------------------------------------------------------------

USER_LABELS = ["Vendors", "Vendors/Observa", "Security", "Newsletters", "Reading", "Action Required", "Clients", "Clients/Brightline", "Hiring", "Receipts"]

FILTERS = [
    # wid, criteria, add labels (names), remove
    ("f_rohan", {"from": addr("rohan.kapoor")}, ["Security"], ["INBOX"]),
    ("f_newstack", {"from": "digest@thenewstack.example"}, ["Newsletters"], ["INBOX"]),
    ("f_medium", {"from": "noreply@medium.example"}, ["Reading"], ["INBOX"]),
]


def mail(wid, when, frm, to, subject, body, *, unread=False, inbox=True, labels=(), cat="personal", thread=None, cc=None, tz="+05:30", sent=False):
    """One message. `when` is IST 'YYYY-MM-DD HH:MM'; `tz` is the sender's offset for the Date header."""
    return {
        "wid": wid,
        "when": when,
        "from": frm,
        "to": to if isinstance(to, list) else [to],
        "cc": cc or [],
        "subject": subject,
        "body": body,
        "unread": unread,
        "inbox": inbox,
        "labels": list(labels),
        "category": cat,
        "thread": thread,
        "tz": tz,
        "sent": sent,
    }


ME = who("yadeesh")

EMAILS = [
    # ---- CloudNest (em_01, em_03, x_04) ----
    mail("cn_inv_jul", "2026-08-04 10:05", EXTERNAL["cn_billing"], ME, "CloudNest invoice CN-2026-07 (July 2026)",
         "Invoice CN-2026-07 for July 2026.\nAmount due: ₹1,68,000\nDue date: 18 Aug 2026", tz="+00:00"),
    mail("cn_rcpt_jul", "2026-08-20 09:10", EXTERNAL["cn_billing"], ME, "Payment receipt for invoice CN-2026-07",
         "We received ₹1,68,000 for invoice CN-2026-07. Thank you.", tz="+00:00"),
    mail("cn_inv_aug", "2026-09-03 10:02", EXTERNAL["cn_billing"], ME, "CloudNest invoice CN-2026-08 (August 2026)",
         "Invoice CN-2026-08 for August 2026.\nAmount due: ₹1,70,000\nDue date: 18 Sep 2026", tz="+00:00"),
    mail("cn_rcpt_aug", "2026-09-12 09:40", EXTERNAL["cn_billing"], ME, "Payment receipt for invoice CN-2026-08",
         "We received ₹1,70,000 for invoice CN-2026-08. Thank you.", tz="+00:00"),
    mail("cn_tkt_1", "2026-09-15 14:22", EXTERNAL["cn_support"], ME, "Ticket #48213: Elevated latency in ap-south-1",
         "We are investigating elevated latency for your clusters in ap-south-1. Next update within 4 hours.", tz="+00:00"),
    mail("cn_tkt_1b", "2026-09-18 11:05", EXTERNAL["cn_support"], ME, "Ticket #48213 update: resolved",
         "The latency issue in ap-south-1 is resolved. Root cause: a degraded network path, now replaced.", tz="+00:00"),
    mail("cn_status", "2026-09-28 08:00", EXTERNAL["cn_status"], ME, "Scheduled maintenance on 10 Oct, 02:00–04:00 IST",
         "Planned maintenance of the ap-south-1 control plane on 10 Oct, 02:00–04:00 IST. No action is needed.", tz="+00:00", cat="updates"),
    mail("cn_tkt_2", "2026-09-29 16:40", EXTERNAL["cn_support"], ME, "Ticket #48377: Snapshot restore failing",
         "We have reproduced the snapshot restore failure you reported and are working on a fix.", tz="+00:00"),
    mail("cn_renewal", "2026-09-30 17:15", EXTERNAL["arjun_iyer"], ME, "Draft renewal proposal for Q4",
         "Hi Yadeesh,\nAttaching our draft renewal proposal for Q4 — happy to walk through it at our 12 Oct sync.\nArjun Iyer, CloudNest", tz="+05:30"),
    mail("cn_inv_sep", "2026-10-01 10:00", EXTERNAL["cn_billing"], ME, "CloudNest invoice CN-2026-09 (September 2026)",
         "Invoice CN-2026-09 for September 2026.\nAmount due: ₹1,92,400\nDue date: 15 Oct 2026", tz="+00:00"),
    mail("cn_inv_sep_r", "2026-10-03 12:30", EXTERNAL["cn_billing"], ME, "Revised: CloudNest invoice CN-2026-09R (September 2026)",
         "This invoice replaces CN-2026-09 sent on 1 Oct, which double-counted storage.\nAmount due: ₹1,84,500\nDue date: 20 Oct 2026\nPlease disregard CN-2026-09.", tz="+00:00"),

    # ---- Q4 OKR drafts (em_02) ----
    mail("okr_ask", "2026-09-29 11:02", ME, [who("meera.pillai"), who("karthik.s"), who("arjun.mehta"), who("neha.gupta")],
         "Q4 OKR drafts — due Fri 2 Oct", "Hi all,\nPlease send me your draft Q4 OKRs by Friday 2 Oct. One page is fine.\nThanks, Yadeesh",
         sent=True, inbox=False, thread="okr"),
    mail("okr_meera", "2026-10-01 18:20", who("meera.pillai"), ME, "Re: Q4 OKR drafts — due Fri 2 Oct",
         "Here's my draft:\nO1 Finish the mesh migration with zero Sev1s\nO2 Halve p95 latency on the payments API", thread="okr"),
    mail("okr_arjun", "2026-10-02 15:30", who("arjun.mehta"), ME, "My Q4 OKR draft",
         "Hi Yadeesh, my draft OKRs:\nO1 Cut the flaky-test rate below 1%\nO2 Own the failover runbook"),
    mail("okr_karthik", "2026-10-02 19:05", who("karthik.s"), ME, "Re: Q4 OKR drafts — due Fri 2 Oct",
         "Sorry, I'm running behind — I'll send my draft on Monday.", thread="okr"),

    # ---- Expense approvals (em_05) ----
    mail("ex_v_dock", "2026-08-28 17:30", who("vikram.rao"), ME, "Expense approval: USB-C dock (₹2,000)",
         "Hi Yadeesh, please approve my expense: USB-C dock, ₹2,000. Receipt available on request."),
    mail("ex_k_lunch", "2026-09-08 12:10", who("karthik.s"), ME, "Expense approval: team lunch (₹3,200)",
         "Hi Yadeesh, please approve my expense: team lunch, ₹3,200. Receipt available on request.", thread="ex_lunch"),
    mail("ex_k_lunch_re", "2026-09-09 10:00", ME, who("karthik.s"), "Re: Expense approval: team lunch (₹3,200)", "Approved.",
         sent=True, inbox=False, thread="ex_lunch"),
    mail("ex_n_taxi", "2026-09-22 09:45", who("neha.gupta"), ME, "Expense approval: on-call taxi (₹1,850)",
         "Hi Yadeesh, please approve my expense: on-call taxi, ₹1,850. Receipt available on request."),
    mail("ex_a_conf", "2026-09-25 14:05", who("arjun.mehta"), ME, "Expense approval: conference ticket (₹18,000)",
         "Hi Yadeesh, please approve my expense: conference ticket, ₹18,000. Receipt available on request."),
    mail("ex_m_books", "2026-09-29 11:30", who("meera.pillai"), ME, "Expense approval: technical books (₹5,000)",
         "Hi Yadeesh, please approve my expense: technical books, ₹5,000. Receipt available on request."),
    mail("ex_m_monitor", "2026-10-02 10:15", who("meera.pillai"), ME, "Expense approval: monitor (₹12,500)",
         "Hi Yadeesh, please approve my expense: monitor, ₹12,500. Receipt available on request."),
    mail("ex_k_cab", "2026-10-05 17:40", who("karthik.s"), ME, "Expense approval: cab to client site (₹780)",
         "Hi Yadeesh, please approve my expense: cab to client site, ₹780. Receipt available on request."),
    mail("hr_reimb", "2026-10-03 09:00", EXTERNAL["hr_portal"], ME, "Your expense report ER-1182 has been reimbursed",
         "Your expense report ER-1182 (₹4,300) has been reimbursed to your salary account.", cat="updates"),

    # ---- Rohan (em_04): all archived by f_rohan ----
    mail("rk_laptop", "2026-08-20 10:00", who("rohan.kapoor"), ME, "Laptop encryption audit — due 31 Aug",
         "Please confirm disk encryption on all team laptops by 31 Aug.", inbox=False, labels=["Security"]),
    mail("rk_access", "2026-09-10 11:00", who("rohan.kapoor"), ME, "Quarterly access review — due 12 Oct",
         "Please review and confirm your team's access list in the access portal by 12 Oct.", inbox=False, labels=["Security"]),
    mail("rk_phish", "2026-09-18 15:20", who("rohan.kapoor"), ME, "FYI: phishing campaign targeting finance teams",
         "A phishing campaign is targeting finance teams this week. No action needed; just be alert.", inbox=False, labels=["Security"]),
    mail("rk_keys", "2026-09-25 10:40", who("rohan.kapoor"), ME, "Rotate your team's service-account keys by 9 Oct",
         "Please rotate all service-account keys owned by the Platform team by 9 Oct.", inbox=False, labels=["Security"]),
    mail("rk_hours", "2026-10-02 09:30", who("rohan.kapoor"), ME, "Security office hours move to Thursdays",
         "From next week, security office hours run on Thursdays at 16:00.", inbox=False, labels=["Security"]),
    mail("rk_pentest", "2026-10-05 16:00", who("rohan.kapoor"), ME, "Pen test results for Platform — no action needed",
         "The Q3 pen test found no issues in Platform services. No action needed.", inbox=False, labels=["Security"]),

    # ---- Rahul ----
    mail("rh_dinner", "2026-10-04 11:15", who("rahul.verma"), [ME, who("isha.bhatt")], "Offsite dinner: let's do Villa Shanti",
         "For the team dinner on 15 Oct, let's book Villa Shanti at 19:30.\n— Rahul", thread="dinner"),
    mail("rh_staff", "2026-10-06 09:00", who("rahul.verma"), ME, "Staff meeting agenda — Thursday",
         "Agenda for Thursday's staff meeting: hiring, Q4 budget, offsite logistics.", unread=True),
    mail("rh_move", "2026-10-06 18:40", who("rahul.verma"), ME, "Can we move our 1:1?",
         "Hi Yadeesh, I'm travelling on Thursday morning. Can we move our 1:1 this Thursday to 15:00, same length?\nThanks, Rahul", unread=True),

    # ---- Farah ----
    mail("fk_prd_v0", "2026-09-29 17:00", who("farah.khan"), ME, "Early thoughts on the PRD v0",
         "Two quick notes on v0:\n1. The scope section is too broad.\n2. Add a glossary."),
    mail("fk_mesh_date", "2026-10-05 11:20", who("farah.khan"), ME, "Service Mesh launch date change",
         "Heads-up: the Service Mesh Migration launch moves from 30 Nov to 11 Dec 2026 because of the CloudNest dependency. Everything else in the Q4 plan stays as it is."),
    mail("fk_prd_fb", "2026-10-05 16:05", who("farah.khan"), ME, "Feedback on the Service Mesh PRD",
         "Hi Yadeesh, here is my feedback on the Service Mesh PRD:\n1. Add rollback criteria for the canary stage.\n2. Name an owner for mTLS certificate rotation.\n3. Include a cost estimate for the sidecars.\n4. Link the SLO dashboard in the success-metrics section.\nThanks, Farah", unread=True),
    mail("fk_prd_agenda", "2026-10-06 12:30", who("farah.khan"), ME, "Agenda for Thursday's PRD Review",
         "Agenda for Thursday's PRD Review:\n1. Open questions on the canary rollout\n2. Sidecar cost model\n3. Sign-off owners", unread=True),

    # ---- Samuel (Brightline), sent from +01:00 ----
    mail("so_thanks", "2026-10-01 20:40", EXTERNAL["samuel"], ME, "Thanks for today's sync",
         "Thanks for the sync today, Yadeesh — notes to follow.\nBest, Samuel", tz="+01:00", labels=["Clients/Brightline"]),
    mail("so_call", "2026-10-05 18:40", EXTERNAL["samuel"], ME, "Call next week?",
         "Hi Yadeesh, could we set up a 45-minute call next week? 10:00 my time works best (I'm in Lagos, WAT = UTC+1).\nAgenda:\n1. Q4 data-pipeline SLAs\n2. Snowflake migration timeline\n3. Contract renewal\nBest, Samuel", tz="+01:00", unread=True),

    # ---- People and team ----
    mail("sl_welcome", "2026-10-02 16:20", who("samantha.lee"), ME, "New joiner: Ananya Das starts Mon 12 Oct",
         "Hi Yadeesh,\nAnanya Das joins the Platform team as an Engineer on Monday 12 October. Her work email is ananya.das@kestrel.example.\nHer onboarding buddy will be Vikram Rao. HR induction runs 10:00–13:00 on her first day.\nThanks, Samantha"),
    mail("ne_swap", "2026-10-05 19:10", who("neha.gupta"), ME, "On-call swap?",
         "Hi Yadeesh, could I swap my on-call week of 19 Oct with Arjun's week of 26 Oct? I have a family function on the 20th. Arjun is fine with it.\n— Neha", unread=True),
    mail("me_canary", "2026-10-06 17:30", who("meera.pillai"), ME, "Mesh canary looks good",
         "Canary at 5% for 24h, error rate flat. Planning 25% on Monday.", unread=True),
    mail("ka_capq", "2026-10-06 11:45", who("karthik.s"), ME, "Question on the capacity model",
         "Should the capacity model include the Observa trial nodes?", unread=True),
    mail("dj_jira", "2026-10-02 14:00", who("deepak.joshi"), ME, "Jira migration to the cloud this weekend",
         "Jira will be read-only from Saturday 10:00 to Sunday 18:00 during the move."),

    # ---- Offsite ----
    mail("ib_offsite", "2026-09-22 10:00", who("isha.bhatt"),
         [who("yadeesh"), who("meera.pillai"), who("karthik.s"), who("arjun.mehta"), who("neha.gupta"), who("vikram.rao"), who("rahul.verma"), who("farah.khan"), who("priya.raman"), who("priya.nair"), who("samantha.lee")],
         "Platform offsite: 15–16 Oct at Le Pondy, Puducherry",
         "Hi all,\nThe offsite is confirmed for Thu 15 – Fri 16 Oct at Le Pondy, Puducherry.\nPlease RSVP in the \"Offsite RSVPs\" sheet by 2 Oct.\nIsha"),
    mail("ib_agenda", "2026-10-05 12:00", who("isha.bhatt"), ME, "Offsite agenda v2 — feedback please",
         "Hi Yadeesh,\nThe draft agenda is in the doc \"Platform Offsite Agenda — Draft\". Comments welcome.\nIsha",
         cc=[who("rahul.verma"), who("priya.raman"), who("priya.nair")], thread="agenda"),
    mail("pr_agenda", "2026-10-06 10:15", who("priya.raman"), ME, "Re: Offsite agenda v2 — feedback please",
         "Could you send me the updated agenda once it's final? I want to plan the design critique slot.\nPriya Raman | Design Lead", thread="agenda"),
    mail("pn_agenda", "2026-10-06 14:50", who("priya.nair"), ME, "Re: Offsite agenda v2 — feedback please",
         "Please send me the updated agenda so I can check the catering costs.\nPriya Nair | Finance Business Partner", thread="agenda"),
]

# Notifications (world.md §4.3): 12 Jira, 10 GitHub, 4 HR portal (incl. hr_reimb above).
JIRA = [
    ("jr_3a", "2026-09-14 10:12", "[JIRA] PLAT-361 assigned to you: Rotate CI runners"),
    ("jr_3b", "2026-09-16 15:40", "[JIRA] PLAT-367 moved to In Review"),
    ("jr_3c", "2026-09-18 11:03", "[JIRA] PLAT-372 commented: flaky integration test"),
    ("jr_3d", "2026-09-21 09:55", "[JIRA] PLAT-380 assigned to you: Update alert thresholds"),
    ("jr_3e", "2026-09-23 17:20", "[JIRA] PLAT-384 resolved"),
    ("jr_3f", "2026-09-25 12:48", "[JIRA] PLAT-389 commented: capacity dashboard"),
    ("jr_3g", "2026-09-28 10:31", "[JIRA] PLAT-393 moved to Done"),
    ("jr_3h", "2026-09-30 14:14", "[JIRA] PLAT-397 assigned to you: Mesh canary checklist"),
    ("jr_401", "2026-10-01 16:02", "[JIRA] PLAT-401 commented: payments retry budget"),
    ("jr_406", "2026-10-02 09:18", "[JIRA] PLAT-406 moved to In Progress"),
    ("jr_412", "2026-10-05 14:12", "[JIRA] PLAT-412 assigned to you: Review SLO targets"),
    ("jr_415", "2026-10-07 08:10", "[JIRA] PLAT-415 commented: on-call handover notes"),
]
JIRA_UNREAD = {"jr_401", "jr_412", "jr_415"}

GITHUB = [
    ("gh_840", "2026-09-15 13:20", "[kestrel/platform] PR #840 merged"),
    ("gh_846", "2026-09-17 18:05", "[kestrel/platform] Review requested on PR #846"),
    ("gh_851", "2026-09-21 11:44", "[kestrel/platform] PR #851 merged"),
    ("gh_857", "2026-09-23 16:30", "[kestrel/platform] CI failed on main"),
    ("gh_862", "2026-09-26 10:02", "[kestrel/platform] PR #862 merged"),
    ("gh_866", "2026-09-29 15:15", "[kestrel/platform] Review requested on PR #866"),
    ("gh_871", "2026-10-01 12:40", "[kestrel/platform] PR #871 merged"),
    ("gh_875", "2026-10-02 17:55", "[kestrel/platform] Dependabot opened PR #875"),
    ("gh_878", "2026-10-05 11:25", "[kestrel/platform] PR #878 merged"),
    ("gh_881", "2026-10-06 13:05", "[kestrel/platform] PR #881 merged"),
]
GITHUB_UNREAD = {"gh_881"}

HR_PORTAL = [
    ("hr_holiday", "2026-09-16 09:00", "Holiday calendar for Q4 is now available", False),
    ("hr_policy", "2026-09-24 09:00", "Updated travel policy", False),
    ("hr_timesheet", "2026-10-06 09:00", "Reminder: submit your timesheet", True),
]

# ---------------------------------------------------------------------------
# Calendars (world.md §3)
# ---------------------------------------------------------------------------

COLLEAGUE_CALENDARS = ["meera.pillai", "karthik.s", "neha.gupta", "arjun.mehta", "vikram.rao", "rahul.verma", "farah.khan", "rohan.kapoor"]
INTERVIEWS_CAL = "c_interviews_kestrel@group.calendar.google.com"
HOLIDAYS_CAL = "c_holidays_kestrel@group.calendar.google.com"

HOLIDAYS = [
    ("2026-10-02", "Gandhi Jayanti — office closed"),
    ("2026-10-19", "Mahanavami / Ayudha Pooja — office closed"),
    ("2026-10-20", "Vijayadashami (Dussehra) — office closed"),
    ("2026-12-25", "Christmas — office closed"),
]
OFFSITE_DAYS = ["2026-10-15", "2026-10-16"]
SERIES_RANGE = ("2026-09-28", "2026-11-06")
TEAM = ["yadeesh", "meera.pillai", "karthik.s", "arjun.mehta", "vikram.rao"]

# Recurring series, stored as instances. weekday: 0 = Monday.
SERIES = [
    # wid, title, weekday(s), start, end, organizer, guests (local: status), skip dates, moves {date: (new date, start, end)}
    ("standup", "Platform Standup", [0, 1, 2, 3, 4], "10:00", "10:15", "neha.gupta", {p: "accepted" for p in TEAM}, [], {}),
    ("oo_neha", "1:1 Yadeesh / Neha", [1], "11:30", "12:00", "yadeesh", {"neha.gupta": "accepted"}, [], {}),
    ("oo_meera", "1:1 Yadeesh / Meera", [2], "12:00", "12:30", "yadeesh", {"meera.pillai": "accepted"}, [], {}),
    ("oo_rahul", "1:1 Yadeesh / Rahul", [3], "10:30", "11:00", "yadeesh", {"rahul.verma": "accepted"}, ["2026-10-15"], {}),
    ("oo_karthik", "1:1 Yadeesh / Karthik", [4], "11:00", "11:30", "yadeesh", {"karthik.s": "accepted"}, ["2026-10-16"], {}),
    ("brightline", "Brightline weekly sync", [3], "15:30", "16:00", "yadeesh", {"@sam.okafor@brightline.example": "accepted"}, [], {"2026-10-15": ("2026-10-14", "15:30", "16:00")}),
]
# Every other Tuesday, organised by Farah.
FARAH_1ON1_DATES = ["2026-09-29", "2026-10-13", "2026-10-27", "2026-11-10"]


def ev(wid, date, start, end, title, organizer, guests=None, *, description=None, location=None, home=None, all_day_end=None, transparency=None):
    """One event. guests: {local or '@full address': status}. Own blocks have no guests."""
    return {
        "wid": wid, "date": date, "start": start, "end": end, "title": title, "organizer": organizer,
        "guests": guests or {}, "description": description, "location": location, "home": home,
        "all_day_end": all_day_end, "transparency": transparency,
    }


A, T, N, D = "accepted", "tentative", "needsAction", "declined"

EVENTS = [
    # ---- Wed 7 Oct ----
    ev("arch_prep", "2026-10-07", "16:00", "16:30", "Architecture Review — prep", "yadeesh", {"meera.pillai": A}),
    # ---- Thu 8 Oct ----
    ev("arch_review", "2026-10-08", "11:00", "12:00", "Architecture Review", "yadeesh",
       {"meera.pillai": A, "karthik.s": A, "arjun.mehta": A, "neha.gupta": A, "farah.khan": A}),
    ev("meera_lunch_8", "2026-10-08", "12:30", "13:30", "Lunch", "meera.pillai"),
    ev("karthik_panel_8", "2026-10-08", "13:00", "14:00", "Interview panel", "karthik.s"),
    ev("rahul_lead_8", "2026-10-08", "13:00", "14:30", "Leadership sync", "rahul.verma"),
    ev("prd_review", "2026-10-08", "14:00", "14:45", "PRD Review", "yadeesh",
       {"farah.khan": A, "meera.pillai": A, "karthik.s": N}, description="Review of the Service Mesh PRD before sign-off."),
    ev("demo_prep", "2026-10-08", "15:00", "15:30", "Sprint demo prep", "yadeesh", {"meera.pillai": A, "karthik.s": A}),
    ev("meera_canary_8", "2026-10-08", "16:00", "16:30", "Mesh canary check", "meera.pillai"),
    ev("rahul_board_8", "2026-10-08", "16:00", "18:00", "Board prep", "rahul.verma"),
    ev("farah_call_8", "2026-10-08", "16:30", "17:30", "Customer call", "farah.khan"),
    ev("hr_sync", "2026-10-08", "17:00", "17:30", "HR sync: Ananya onboarding", "samantha.lee", {"yadeesh": A}),
    # ---- Fri 9 Oct ----
    ev("lunch_priya_9", "2026-10-09", "12:30", "13:00", "Lunch with Priya", "priya.raman", {"yadeesh": A}),
    ev("hiring_sync_9", "2026-10-09", "13:30", "14:30", "Hiring sync", "samantha.lee", {"yadeesh": A, "rahul.verma": A}),
    ev("meera_int_9", "2026-10-09", "14:00", "15:00", "Interview", "meera.pillai"),
    ev("farah_calls_9", "2026-10-09", "15:00", "17:00", "Customer calls", "farah.khan"),
    ev("sprint_demo_9", "2026-10-09", "16:00", "16:30", "Sprint demo", "yadeesh",
       {"meera.pillai": A, "karthik.s": A, "arjun.mehta": A, "neha.gupta": A, "vikram.rao": A, "farah.khan": A, "rahul.verma": A}),
    # ---- Mon 12 Oct ----
    ev("karthik_int_12", "2026-10-12", "10:15", "11:00", "Interview: backend candidate", "karthik.s"),
    ev("cn_vendor_sync", "2026-10-12", "10:30", "11:30", "CloudNest vendor sync", "yadeesh", {"neha.gupta": A, "@arjun.iyer@cloudnest.example": A}),
    ev("meera_mesh_12", "2026-10-12", "11:30", "12:30", "Mesh rollout review", "meera.pillai"),
    ev("welcome_ananya", "2026-10-12", "12:00", "13:00", "Welcome Ananya", "yadeesh", {"ananya.das": N, "samantha.lee": A}),
    ev("y_lunch_12", "2026-10-12", "13:00", "13:30", "Lunch", "yadeesh"),
    ev("meera_lunch_12", "2026-10-12", "13:00", "14:00", "Lunch", "meera.pillai"),
    ev("karthik_farah_12", "2026-10-12", "13:30", "14:30", "1:1 Karthik / Farah", "farah.khan", {"karthik.s": A}),
    ev("neha_incident_12", "2026-10-12", "14:00", "15:00", "Incident review", "neha.gupta"),
    ev("hiring_debrief", "2026-10-12", "14:30", "16:00", "Hiring debrief: Senior SRE", "yadeesh",
       {"meera.pillai": A, "karthik.s": D, "neha.gupta": T, "vikram.rao": N},
       description="Debrief for the Senior SRE loop. Scorecards are in the Hiring Pipeline sheet."),
    ev("farah_prep_12", "2026-10-12", "15:30", "17:00", "PRD review prep", "farah.khan"),
    ev("design_sync_12", "2026-10-12", "16:00", "17:00", "Design sync", "priya.raman", {"meera.pillai": A}),
    ev("neha_prep_12", "2026-10-12", "16:30", "18:00", "On-call handover prep", "neha.gupta"),
    ev("karthik_focus_12", "2026-10-12", "17:00", "18:00", "Focus time", "karthik.s"),
    # ---- Tue 13 Oct ----
    ev("neha_slo_13", "2026-10-13", "10:15", "11:15", "SLO review", "neha.gupta"),
    ev("farah_cust_13", "2026-10-13", "10:30", "12:00", "Customer interviews", "farah.khan"),
    ev("capacity_session", "2026-10-13", "11:00", "12:00", "Capacity model working session", "karthik.s", {"meera.pillai": A}),
    ev("neha_lunch_13", "2026-10-13", "12:30", "13:30", "Lunch", "neha.gupta"),
    ev("meera_lunch_13", "2026-10-13", "13:00", "14:00", "Lunch", "meera.pillai"),
    ev("karthik_int_13", "2026-10-13", "13:30", "14:30", "Interview: SRE candidate", "karthik.s"),
    ev("budget_checkin", "2026-10-13", "14:00", "14:30", "Budget check-in", "yadeesh", {"priya.nair": D}),
    ev("meera_hours_13", "2026-10-13", "14:30", "15:30", "Mesh office hours", "meera.pillai"),
    ev("neha_runbook_13", "2026-10-13", "15:00", "16:00", "Runbook review", "neha.gupta"),
    ev("karthik_cr_13", "2026-10-13", "15:30", "16:00", "Code review block", "karthik.s"),
    ev("meera_focus_13", "2026-10-13", "17:00", "18:00", "Focus", "meera.pillai"),
    # ---- Wed 14 Oct ----
    ev("farah_cust_14", "2026-10-14", "10:30", "12:00", "Customer interviews", "farah.khan"),
    ev("observa_call", "2026-10-14", "13:00", "14:00", "Vendor call: Observa", "neha.gupta", {"@linh.tran@observa.example": A}),
    ev("roadmap_preread", "2026-10-14", "16:00", "17:00", "Q4 roadmap pre-read", "yadeesh",
       {"farah.khan": T, "meera.pillai": A, "karthik.s": N, "arjun.mehta": N, "vikram.rao": D}),
    # ---- Offsite (all-day, Thu 15 – Fri 16) ----
    ev("offsite", "2026-10-15", None, None, "Platform Team Offsite", "isha.bhatt",
       {p: A for p in ["yadeesh", "meera.pillai", "karthik.s", "arjun.mehta", "neha.gupta", "vikram.rao", "rahul.verma", "farah.khan", "priya.raman", "priya.nair", "samantha.lee"]},
       all_day_end="2026-10-17", location="Le Pondy, Puducherry"),
    # ---- 27–30 Oct ----
    ev("arjun_dentist", "2026-10-27", "16:00", "17:00", "Dentist", "arjun.mehta"),
    ev("sprint_planning_28", "2026-10-28", "14:00", "15:00", "Sprint planning", "yadeesh",
       {"meera.pillai": A, "karthik.s": A, "arjun.mehta": A, "neha.gupta": A, "vikram.rao": A}),
    ev("priya_1on1_29", "2026-10-29", "14:00", "14:30", "1:1 Priya Raman / Yadeesh", "priya.raman", {"yadeesh": A}),
    # ---- Mon 2 Nov ----
    ev("rohan_council_2", "2026-11-02", "10:00", "11:30", "Security council", "rohan.kapoor"),
    ev("y_pipeline_2", "2026-11-02", "10:30", "11:00", "Pipeline review", "yadeesh"),
    ev("neha_slo_2", "2026-11-02", "11:00", "12:00", "SLO review", "neha.gupta"),
    ev("karthik_talk_2", "2026-11-02", "12:00", "13:00", "Tech talk", "karthik.s"),
    ev("meera_lunch_2", "2026-11-02", "13:00", "14:00", "Lunch", "meera.pillai"),
    ev("qp_kickoff_2", "2026-11-02", "14:00", "15:00", "Quarterly planning kickoff", "rahul.verma", {"yadeesh": A}),
    ev("rohan_risk_2", "2026-11-02", "15:00", "16:00", "Vendor risk review", "rohan.kapoor"),
    ev("arjun_int_2", "2026-11-02", "16:00", "17:00", "Interview", "arjun.mehta"),
    # ---- Arjun's leave 9–13 Nov (all-day on his calendar) ----
    ev("arjun_ooo", "2026-11-09", None, None, "OOO", "arjun.mehta", all_day_end="2026-11-14", transparency="opaque"),
]

INTERVIEWS = [
    ("int_arvind", "2026-09-24", "15:00", "16:00", "Interview: Arvind Rao (SRE)", "arvind.rao@candidates.example"),
    ("int_divya", "2026-09-29", "11:00", "12:00", "Interview: Divya Menon (Frontend Engineer)", "divya.menon@candidates.example"),
    ("int_karan", "2026-09-30", "15:00", "16:00", "Interview: Karan Shah (SRE)", "karan.shah@candidates.example"),
    ("int_lakshmi", "2026-10-01", "12:00", "13:00", "Interview: Lakshmi Iyer (Backend Engineer)", "lakshmi.iyer@candidates.example"),
    ("int_rakesh", "2026-10-05", "14:00", "15:00", "Interview: Rakesh Pillai (Backend Engineer)", "rakesh.pillai@candidates.example"),
]

# ---------------------------------------------------------------------------
# Docs (world.md §5). Blocks: paragraph strings or {"table": rows}.
# ---------------------------------------------------------------------------

DOCS = [
    ("doc_q4plan", "Q4 Planning — Platform", "2026-09-30", [
        "Q4 Planning — Platform",
        "Owner: Yadeesh T · Last updated: 30 Sep 2026",
        "Projects",
        "Service Mesh Migration — owner: Meera Pillai — launch: 30 Nov 2026 — status: on track",
        "Billing Revamp — owner: Karthik Subramanian — launch: 30 Nov 2026 — status: at risk",
        "Observability v2 — owner: Neha Gupta — launch: 15 Dec 2026 — status: on track",
        "Flaky Test Cleanup — owner: Arjun Mehta — launch: 23 Oct 2026 — status: on track",
        "Key dates",
        "16 Nov 2026 — Service Mesh Migration canary",
        "30 Nov 2026 — Service Mesh Migration launch",
        "30 Nov 2026 — Billing Revamp launch",
        "15 Dec 2026 — Observability v2 launch",
        "Risks",
        "The CloudNest dependency may delay the mesh rollout.",
    ]),
    ("doc_q4data", "Q4 Planning — Data Team", "2026-09-28", [
        "Q4 Planning — Data Team",
        "Owner: Data Engineering",
        "Projects",
        "Warehouse Consolidation — owner: Lakshmi Rao — launch: 30 Nov 2026",
        "Streaming Ingest v3 — owner: Omar Sheikh — launch: 18 Dec 2026",
    ]),
    ("doc_agenda", "Platform Offsite Agenda — Draft", "2026-10-05", [
        "Platform Offsite — 15–16 Oct 2026 — Le Pondy, Puducherry",
        "Draft v2 · owner: Isha Bhatt",
        "Day 1 — Thu 15 Oct",
        "09:30 Arrive and coffee",
        "10:00 Roadmap review",
        "12:30 Lunch",
        "14:00 Team working sessions",
        "17:30 Wrap-up",
        "19:30 Team dinner",
        "Day 2 — Fri 16 Oct",
        "09:30 Incident retro",
        "11:00 Team building",
        "13:00 Lunch",
        "15:00 Travel back",
    ]),
    ("doc_pm_payments", "Postmortem — Payments API outage (29 Sep 2026)", "2026-10-01", [
        "Postmortem — Payments API outage (29 Sep 2026)",
        "Author: Neha Gupta · Status: final",
        "Summary",
        "The Payments API returned errors for 47 minutes after a queue backlog triggered cascading retries.",
        "Timeline",
        "14:02 Queue backlog starts; no alert fires",
        "14:19 Retries saturate the payments client",
        "14:49 Failover completed manually",
        "Root cause",
        "No retry budget in the payments client, and no alert on queue depth.",
        "Action items",
        {"table": [
            ["Owner", "Action", "Due", "Tag"],
            ["Neha Gupta", "Add an alert on payment-queue depth", "14 Oct 2026", "[OPS]"],
            ["Karthik Subramanian", "Add a retry budget to the payments client", "23 Oct 2026", "[ENG]"],
            ["Rohan Kapoor", "Rotate the leaked staging credentials", "9 Oct 2026", "[SEC]"],
            ["Meera Pillai", "Load-test the failover path", "28 Oct 2026", "[ENG]"],
            ["Arjun Mehta", "Document the manual failover runbook", "16 Oct 2026", "[OPS]"],
            ["Rohan Kapoor", "Audit service-account permissions", "30 Oct 2026", "[SEC]"],
        ]},
    ]),
    ("doc_pm_search", "Postmortem — Search API latency (12 Aug 2026)", "2026-08-14", [
        "Postmortem — Search API latency (12 Aug 2026)",
        "Author: Arjun Mehta · Status: final",
        "Summary",
        "Search latency rose to 4 s for 25 minutes after a cache eviction storm.",
        "Action items",
        {"table": [
            ["Owner", "Action", "Due", "Tag"],
            ["Arjun Mehta", "Add cache warm-up on deploy", "28 Aug 2026", "[ENG]"],
            ["Vikram Rao", "Alert on cache hit ratio", "4 Sep 2026", "[OPS]"],
        ]},
    ]),
    ("doc_pm_template", "Postmortem Template", "2026-06-10", [
        "Postmortem — <incident name> (<date>)", "Author: · Status: draft", "Summary", "Timeline", "Root cause", "Action items",
    ]),
    ("doc_sync_0921", "Platform Weekly Sync — 21 Sep 2026", "2026-09-21", [
        "Platform Weekly Sync — 21 Sep 2026",
        "Attendees: Yadeesh, Meera, Karthik, Neha, Arjun, Vikram",
        "Notes",
        "Mesh rollout planning started; canary target mid-November.",
        "Flaky tests are blocking two releases a week.",
        "Action items",
        "Meera Pillai: Draft the mesh canary plan",
        "Karthik Subramanian: Capacity model v1",
        "Neha Gupta: Update the on-call runbook",
        "Arjun Mehta: Fix flaky integration tests",
        "Vikram Rao: Evaluate the Observa trial",
    ]),
    ("doc_sync_0928", "Platform Weekly Sync — 28 Sep 2026", "2026-09-28", [
        "Platform Weekly Sync — 28 Sep 2026",
        "Attendees: Yadeesh, Meera, Karthik, Neha, Arjun, Vikram",
        "Notes",
        "Karthik moves to the Billing Revamp, so his capacity-model work passes to Vikram.",
        "Updates on earlier action items",
        "Draft the mesh canary plan (Meera Pillai) — DONE",
        "Capacity model v1 — reassigned from Karthik Subramanian to Vikram Rao — open",
        "Update the on-call runbook (Neha Gupta) — open",
        "Fix flaky integration tests (Arjun Mehta) — DONE",
        "Evaluate the Observa trial (Vikram Rao) — open",
        "New action items",
        "Yadeesh T: Confirm the offsite dates with Isha — DONE",
        "Yadeesh T: Book the Q4 capacity planning meeting — due 16 Oct 2026",
        "Yadeesh T: Share the hiring plan with Rahul — due 12 Oct 2026",
        "Karthik Subramanian: Draft the Billing Revamp migration plan — due 9 Oct 2026",
        "Meera Pillai: Prepare the architecture review deck — due 8 Oct 2026",
    ]),
    ("doc_sync_data", "Data Team Weekly Sync — 28 Sep 2026", "2026-09-28", [
        "Data Team Weekly Sync — 28 Sep 2026",
        "Attendees: Lakshmi, Omar, Tara",
        "Action items",
        "Lakshmi Rao: Finalise the warehouse cut-over plan — due 9 Oct 2026",
        "Omar Sheikh: Benchmark the streaming ingest — due 14 Oct 2026",
    ]),
    ("doc_hiring_h2", "Hiring Plan H2", "2026-09-25", [
        "Hiring Plan H2 2026 — Platform",
        "Owner: Yadeesh T · Status: draft",
        "Summary",
        "We have four open roles this half, two of them urgent.",
        "Open Roles",
        "Senior SRE (urgent) — Bengaluru",
        "Backend Engineer (urgent) — Bengaluru",
        "Frontend Engineer — Remote (India)",
        "Data Engineer — Pune",
        "Interview loop",
        "Phone screen, take-home, onsite (three interviews), debrief.",
    ]),
    ("doc_hiring_h1", "Hiring Plan H1", "2026-03-12", [
        "Hiring Plan H1 2026 — Platform",
        "Owner: Yadeesh T · Status: final",
        "Open Roles",
        "Backend Engineer — Bengaluru (filled)",
        "SRE — Pune (filled)",
    ]),
    ("doc_onboarding", "New Hire Onboarding Checklist — Platform", "2026-09-20", [
        "New Hire Onboarding Checklist — Platform",
        "Day 1 is the new hire's start date. Due dates below are relative to Day 1.",
        "Week 1",
        "IT setup (Day 1): collect the laptop from the IT desk; enable 2-step verification; request GitHub and CloudNest access",
        "HR induction (Day 1)",
        "Read the Platform Architecture Overview (Day 2)",
        "Shadow an on-call handover (Day 3)",
        "First pull request merged (Day 5)",
        "Intro 1:1s (Week 1)",
        "Book three 30-minute intro 1:1s: with the tech lead (Meera Pillai), the SRE lead (Neha Gupta) and the product manager (Farah Khan).",
        "Book them between 14:00 on Day 1 and the end of Day 3, inside working hours, at times the other person is free, and not overlapping each other.",
        "The new hire's calendar is empty before they start. The manager sets these up but does not attend. Invite the new hire and the other person.",
        "Buddy",
        "HR names an onboarding buddy in the welcome email; send the buddy the intro schedule.",
    ]),
    ("doc_prd", "Service Mesh PRD", "2026-10-02", [
        "Service Mesh PRD",
        "Owner: Meera Pillai · Reviewer: Farah Khan · Status: in review",
        "Problem",
        "Service-to-service traffic has no uniform mTLS or retries.",
        "Proposal",
        "Adopt a sidecar-based mesh, rolled out through a canary stage.",
        "Success metrics",
        "p95 latency within 5% of today; zero Sev1 incidents during rollout.",
        "Open questions",
        "Who owns certificate rotation?",
    ]),
    ("doc_prd_v0", "Service Mesh PRD v0 (archived)", "2026-09-10", [
        "Service Mesh PRD v0",
        "Owner: Meera Pillai · Status: archived",
        "Scope",
        "All east-west traffic in every region, including batch jobs.",
        "Proposal",
        "Evaluate three mesh products before committing.",
    ]),
    ("doc_arch", "Platform Architecture Overview", "2026-07-02", [
        "Platform Architecture Overview",
        "Services are deployed on CloudNest in ap-south-1 and eu-west-1.",
        "Traffic enters through the edge gateway; payments and search are the critical paths.",
        "Observability runs on Observa; on-call follows the rotation sheet.",
    ]),
]

# Comments: doc wid -> [(cid, author, content, resolved, replies[(author, content)], created)]
DOC_COMMENTS = {
    "doc_agenda": [
        ("c1", "Rahul Verma", 'Please rename "Roadmap review" to "Roadmap & OKRs".', False, [], "2026-10-05T07:10:00.000Z"),
        ("c2", "Rahul Verma", "Move lunch on Day 1 to 13:00.", False, [], "2026-10-05T07:12:00.000Z"),
        ("c3", "Priya Raman", "Can we add a design critique slot on Day 2?", False, [], "2026-10-05T09:40:00.000Z"),
        ("c4", "Rahul Verma", "Add the venue name to the title line.", True, [("Isha Bhatt", "Added.")], "2026-10-04T11:00:00.000Z"),
        ("c5", "Farah Khan", "Should product join the incident retro?", False, [], "2026-10-06T05:20:00.000Z"),
    ],
}

# ---------------------------------------------------------------------------
# Sheets (world.md §6). Rows are written as typed (USER_ENTERED).
# ---------------------------------------------------------------------------

LINE_ITEMS = [
    ["Vendor", "Category", "Month", "Amount", "Status"],
    ["CloudNest", "Infra", "Jul", "168000", "Approved"],
    ["Observa", "Observability", "Jul", "52000", "Approved"],
    ["Figma", "Tooling", "Jul", "18500", "Approved"],
    ["GitHub", "Tooling", "Jul", "42000", "Approved"],
    ["TravelDesk", "Travel", "Jul", "23400", "Rejected"],
    ["CloudNest", "Infra", "Aug", "170000", "Approved"],
    ["Observa", "Observability", "Aug", "52000", "Approved"],
    ["Figma", "Tooling", "Aug", "18500", "Approved"],
    ["GitHub", "Tooling", "Aug", "42000", "Pending"],
    ["TravelDesk", "Travel", "Aug", "61250", "Approved"],
    ["CloudNest", "Infra", "Sep", "184500", "Pending"],
    ["Observa", "Observability", "Sep", "58750", "Approved"],
    ["Figma", "Tooling", "Sep", "18500", "Approved"],
    ["GitHub", "Tooling", "Sep", "42000", "Pending"],
    ["TravelDesk", "Travel", "Sep", "12800", "Approved"],
    ["Observa", "Observability", "Sep", "9800", "Rejected"],
]
INR = {"type": "CURRENCY", "pattern": "₹#,##0"}

SHEETS = [
    {
        "wid": "sh_budget", "title": "Platform Budget 2026", "modified": "2026-10-03",
        "tabs": [
            {"title": "Line Items", "rows": LINE_ITEMS, "formats": [("D2:D17", INR)],
             "rules": [("D2:D17", "NUMBER_GREATER", ["100000"], "#F4CCCC", None),
                       ("D2:D17", "NUMBER_GREATER", ["25000"], "#FCE8B2", None),
                       ("A2:E17", "CUSTOM_FORMULA", ['=$E2="Rejected"'], None, "#999999")]},
            {"title": "Monthly Budget", "rows": [
                ["Vendor", "Category", "Monthly budget"],
                ["CloudNest", "Infra", "160000"], ["Observa", "Observability", "55000"],
                ["Figma", "Tooling", "18500"], ["GitHub", "Tooling", "42000"], ["TravelDesk", "Travel", "30000"],
            ], "formats": [("C2:C6", INR)]},
            {"title": "Summary", "rows": [
                ["Category", "Approved total", "Q3 budget cap"],
                ["Infra", "", "510000"], ["Observability", "", "165000"], ["Tooling", "", "150000"], ["Travel", "", "90000"],
            ], "formats": [("B2:C5", INR)]},
        ],
    },
    {
        "wid": "sh_budget25", "title": "Platform Budget 2025", "modified": "2026-01-15",
        "tabs": [
            {"title": "Line Items", "rows": [
                ["Vendor", "Category", "Month", "Amount", "Status"],
                ["CloudNest", "Infra", "Oct", "142000", "Approved"], ["Observa", "Observability", "Oct", "48000", "Approved"],
                ["CloudNest", "Infra", "Nov", "145500", "Approved"], ["Figma", "Tooling", "Nov", "16000", "Approved"],
            ], "formats": [("D2:D5", INR)]},
            {"title": "Summary", "rows": [["Category", "Approved total"], ["Infra", "287500"], ["Observability", "48000"], ["Tooling", "16000"]], "formats": [("B2:B4", INR)]},
        ],
    },
    {
        "wid": "sh_rsvp", "title": "Offsite RSVPs", "modified": "2026-10-02",
        "tabs": [{"title": "Responses", "rows": [
            ["Timestamp", "Name", "Email", "Attending", "Dietary", "Travelling from"],
            ["25/09/2026 10:12:00", "Meera Pillai", addr("meera.pillai"), "Yes", "Vegetarian", "Bengaluru"],
            ["25/09/2026 10:40:00", "Karthik Subramanian", addr("karthik.s"), "Y", "Non-vegetarian", "Chennai"],
            ["25/09/2026 11:05:00", "Neha Gupta", addr("neha.gupta"), "yes", "Vegetarian", "Pune"],
            ["25/09/2026 12:30:00", "Arjun Mehta", addr("arjun.mehta"), "TRUE", "Non-vegetarian", "Bengaluru"],
            ["25/09/2026 14:02:00", "Vikram Rao", addr("vikram.rao"), "No", "", "Bengaluru"],
            ["25/09/2026 15:20:00", "Priya Raman", addr("priya.raman"), "Yes", "Vegan", "Bengaluru"],
            ["26/09/2026 09:15:00", "Farah Khan", addr("farah.khan"), "yes", "Jain", "Mumbai"],
            ["26/09/2026 10:00:00", "Rahul Verma", addr("rahul.verma"), "Yes", "Non-vegetarian", "Bengaluru"],
            ["26/09/2026 11:45:00", "Rohan Kapoor", addr("rohan.kapoor"), "N", "Non-vegetarian", "Delhi"],
            ["26/09/2026 16:30:00", "Deepak Joshi", addr("deepak.joshi"), "FALSE", "", "Bengaluru"],
            ["27/09/2026 08:50:00", "Isha Bhatt", addr("isha.bhatt"), "Yes", "Vegetarian", "Bengaluru"],
            ["28/09/2026 09:05:00", "Samantha Lee", addr("samantha.lee"), "yes", "", "Bengaluru"],
            ["29/09/2026 10:20:00", "Vikram Rao", "Vikram.Rao@" + DOMAIN, "yes", "Non-vegetarian", "Bengaluru"],
            ["29/09/2026 13:10:00", "Meera Pillai", addr("meera.pillai"), "Yes", "Vegan", "Bengaluru"],
            ["30/09/2026 18:45:00", "Rohan Kapoor", addr("rohan.kapoor"), "y", "Non-vegetarian", "Delhi"],
            ["01/10/2026 09:30:00", "Priya Nair", addr("priya.nair"), "No", "", "Bengaluru"],
            ["02/10/2026 11:00:00", "Karthik Subramanian", "KARTHIK.S@" + DOMAIN, "no", "Non-vegetarian", "Chennai"],
        ]}],
    },
    {
        "wid": "sh_pipeline", "title": "Hiring Pipeline", "modified": "2026-10-05",
        "tabs": [{"title": "Candidates", "rows": [
            ["Candidate", "Role", "Stage", "Interviewer", "Next step", "Next step date"],
            ["Divya Menon", "Frontend Engineer", "Onsite scheduled", "", "Onsite interview", "29/09/2026"],
            ["Karan Shah", "SRE", "Offer", "Meera Pillai", "Offer call", "09/10/2026"],
            ["Lakshmi Iyer", "Backend Engineer", "Phone screen done", "Karthik Subramanian", "Onsite interview", "01/10/2026"],
            ["Rakesh Pillai", "Backend Engineer", "Onsite scheduled", "", "Onsite interview", "05/10/2026"],
            ["Rakesh Pillay", "Data Engineer", "Phone screen", "Neha Gupta", "Phone screen", "12/10/2026"],
            ["Arvind Rao", "SRE", "Rejected", "Neha Gupta", "—", ""],
            ["Meghna Das", "Frontend Engineer", "Applied", "", "Resume review", "14/10/2026"],
            ["Sanjay Kulkarni", "Senior SRE", "Onsite done", "Neha Gupta", "Debrief", "12/10/2026"],
        ]}],
    },
    {
        "wid": "sh_oncall", "title": "On-call Rotation Q4", "modified": "2026-09-28",
        "tabs": [{"title": "Rotation", "rows": [
            ["Week starting", "Primary", "Secondary"],
            ["05/10/2026", "Karthik Subramanian", "Vikram Rao"],
            ["12/10/2026", "Meera Pillai", "Neha Gupta"],
            ["19/10/2026", "Neha Gupta", "Karthik Subramanian"],
            ["26/10/2026", "Arjun Mehta", "Meera Pillai"],
            ["02/11/2026", "Vikram Rao", "Arjun Mehta"],
            ["09/11/2026", "Karthik Subramanian", "Neha Gupta"],
            ["16/11/2026", "Meera Pillai", "Vikram Rao"],
            ["23/11/2026", "Neha Gupta", "Arjun Mehta"],
            ["30/11/2026", "Arjun Mehta", "Karthik Subramanian"],
            ["07/12/2026", "Vikram Rao", "Meera Pillai"],
            ["14/12/2026", "Karthik Subramanian", "Neha Gupta"],
            ["21/12/2026", "Meera Pillai", "Arjun Mehta"],
            ["28/12/2026", "Neha Gupta", "Vikram Rao"],
        ]}],
    },
    {
        "wid": "sh_oncall_q3", "title": "On-call Rotation Q3", "modified": "2026-07-01",
        "tabs": [{"title": "Rotation", "rows": [
            ["Week starting", "Primary", "Secondary"],
            ["06/07/2026", "Neha Gupta", "Arjun Mehta"], ["13/07/2026", "Vikram Rao", "Meera Pillai"],
            ["20/07/2026", "Meera Pillai", "Karthik Subramanian"], ["27/07/2026", "Arjun Mehta", "Neha Gupta"],
        ]}],
    },
    {
        "wid": "sh_directory", "title": "Team Directory", "modified": "2026-09-01",
        "tabs": [{"title": "People", "rows": [["Name", "Email", "Team", "Role", "Manager", "Location"]]
                  + [[name, addr(local), team, role, manager, loc] for name, local, team, role, manager, loc, listed in PEOPLE if listed]}],
    },
    {
        "wid": "sh_vendors", "title": "Vendor Contacts", "modified": "2026-08-20",
        "tabs": [{"title": "Contacts", "rows": [
            ["Vendor", "Contact", "Email", "Role"],
            ["CloudNest", "Arjun Iyer", "arjun.iyer@cloudnest.example", "Account manager"],
            ["CloudNest", "Billing", "billing@cloudnest.example", "Invoices"],
            ["Observa", "Linh Tran", "linh.tran@observa.example", "Account manager"],
            ["Brightline Retail", "Samuel Okafor", "sam.okafor@brightline.example", "Client, Head of Data"],
        ]}],
    },
]

SHEET_COMMENTS = {
    "sh_pipeline": [
        ("s1", "Samantha Lee", 'Please move Divya Menon to "Offer" and mark Rakesh Pillai as "Rejected". Thanks!', False, [], "2026-10-06T06:00:00.000Z"),
        ("s2", "Priya Raman", "Can we add a design interviewer to the frontend loop?", False, [], "2026-10-05T10:30:00.000Z"),
        ("s3", "Samantha Lee", "Please use dd/mm/yyyy for dates.", True, [("Yadeesh T", "Done")], "2026-09-20T05:00:00.000Z"),
    ],
}

# ---------------------------------------------------------------------------
# Google Tasks (world.md §7). Listed top to bottom as the list shows them.
# ---------------------------------------------------------------------------

W1_NOTES = ("Context: agreed in the 28 Sep sync that the platform team owns the Q4 capacity model for next quarter. "
            "Update 2 Oct: DONE, Meera already sent the final numbers to Rahul.")

TASK_LISTS = [
    ("tl_work", "Work", [
        # wid, title, due (date), status, notes, completed (IST datetime)
        ("w1", "Send Q4 capacity model to Rahul", "2026-10-09", "needsAction", W1_NOTES, None),
        ("w2", "Book offsite venue", None, "needsAction", "Done - Isha confirmed Le Pondy on 30 Sep.", None),
        ("w3", "Review Service Mesh PRD", "2026-10-08", "needsAction", "Wait for Farah's feedback first.", None),
        ("w4", "Renew CloudNest contract", "2026-10-30", "needsAction", "Waiting on the revised quote. Not done yet - don't close.", None),
        ("w5", "Prepare hiring debrief", "2026-10-12", "needsAction", None, None),
        ("w5b", "Prepare hiring debrief", "2026-10-14", "needsAction", None, None),
        ("w6", "Update on-call runbook", "2026-10-16", "needsAction", None, None),
        ("w6b", "Update on-call runbook", "2026-10-09", "needsAction", None, None),
        ("w7", "Approve expense reports", None, "needsAction", None, None),
        ("w10", "Prepare hiring debrief slides", "2026-10-12", "needsAction", None, None),
        ("q1", "Q4 hiring plan draft", None, "needsAction", None, None),
        ("q2", "Q4 OKR draft", "2026-10-02", "needsAction", None, None),
        ("q3", "Draft Q4 budget asks", None, "needsAction", None, None),
        ("q4", "Q4 roadmap comments for Farah", None, "completed", None, "2026-10-01 18:00"),
        ("q5", "Q4 on-call schedule", None, "needsAction", None, None),
        ("c1", "File September timesheet", None, "completed", None, "2026-10-02 17:00"),
        ("c2", "Review PR #881", None, "completed", None, "2026-10-05 16:20"),
        ("c3", "Send interview feedback for Karan Shah", None, "completed", None, "2026-10-06 11:05"),
    ]),
    ("tl_personal", "Personal", [
        ("p1", "Q4 tax planning", None, "needsAction", None, None),
        ("p2", "Renew passport", "2026-11-20", "needsAction", None, None),
        ("p3", "Book dentist appointment", None, "needsAction", None, None),
    ]),
    ("tl_offsite", "Offsite Prep", [
        ("o1", "Confirm headcount with Isha", "2026-10-09", "needsAction", None, None),
        ("o2", "Share travel plan", "2026-10-12", "needsAction", None, None),
        ("o3", "Pack laptop charger", None, "needsAction", None, None),
    ]),
]

# ---------------------------------------------------------------------------
# Per-task seed additions (world.md §9)
# ---------------------------------------------------------------------------

# The pool of addition items, by world id. A task's file lists the ones it uses:
#   "seed_additions": {"emails": ["pn_dinner"]}
SEED_ADDITIONS = {
    "emails": {
        "pn_dinner": mail("pn_dinner", "2026-10-06 16:05", who("priya.nair"), ME, "Re: Offsite dinner: let's do Villa Shanti",
                          "Villa Shanti is over our per-head budget (₹2,500). Can we switch to Le Café instead? Rahul, please confirm.",
                          cc=[who("rahul.verma")], thread="dinner"),
        "rh_moved": mail("rh_moved", "2026-10-06 20:15", who("rahul.verma"), ME, "Offsite moved to 22–23 Oct",
                         "Heads-up: Le Pondy double-booked us, so the offsite moves to 22–23 Oct at Mango Grove, Mahabalipuram. I'll update the agenda doc tomorrow."),
    },
}
