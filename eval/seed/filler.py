"""Deterministic background data: ordinary mail and meetings around the needles.

Rules (world.md §3.8, §4.4): filler never
- adds expense requests, CloudNest billing, OKR drafts, Rohan mail or Jira notifications,
- adds unread mail dated 5–7 Oct,
- uses needle subjects or the words the tasks search for,
- touches the key calendar days (7–16 Oct, 2 Nov) or adds 1:1s.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from world_data import EXTERNAL, HOLIDAYS, OFFSITE_DAYS, mail, who

RNG_SEED = 20261007

TEAM_SENDERS = ["meera.pillai", "karthik.s", "arjun.mehta", "neha.gupta", "vikram.rao", "farah.khan", "deepak.joshi", "isha.bhatt", "priya.raman", "samantha.lee", "rahul.verma"]

INTERNAL_TOPICS = [
    ("Load test results for the gateway", "The gateway held 4k rps with p95 under 180 ms. Graphs are in the usual dashboard."),
    ("Lunch-and-learn next Friday", "I'm running a short session on eBPF tracing next Friday at 13:00. All welcome."),
    ("Heads-up: VPN maintenance", "The VPN concentrator gets patched on Saturday night; expect two short drops."),
    ("Code freeze reminder", "Reminder that the code freeze for the release train starts Thursday evening."),
    ("Question about the release train", "Are we still cutting the release branch on Wednesdays, or did that move?"),
    ("Kubernetes upgrade window", "Proposing Tuesday 22:00 for the node pool upgrade. Shout if that clashes with anything."),
    ("Postgres minor upgrade done", "Primary and replicas are on the new minor version. No errors in the logs."),
    ("Hackathon ideas", "Collecting ideas for the November hackathon. Reply with anything you want to build."),
    ("Weekly metrics snapshot", "Deploys up 12% week on week; change failure rate flat at 4%."),
    ("Latency graphs from yesterday", "Sharing the latency graphs from yesterday's spike; it lines up with the batch job."),
    ("New laptop models", "IT has two new laptop models available for refreshes. Details on the intranet page."),
    ("Team photo", "Photos from last week's team lunch are in the shared album."),
    ("Parking update", "Level B2 will be closed for resurfacing next week."),
    ("Book club pick", "This month's pick is 'Accelerate'. We meet on the last Thursday."),
    ("Staging cleanup", "I removed the stale staging namespaces older than 60 days."),
    ("Terraform module bump", "Bumped the network module; plan shows no changes outside tags."),
    ("Alert noise this week", "Most pages this week came from the disk-space alert. Tuning it today."),
    ("Draining old cluster", "The old cluster is drained; I'll delete it after one more week."),
    ("Canary dashboard link", "Pinned the canary dashboard in the team channel for easy access."),
    ("Design system update", "The component library has new table and badge components."),
]

NEWSTACK = ["This week in cloud native", "Platform engineering roundup", "Observability trends", "The state of service meshes", "Kubernetes release notes digest", "Developer productivity weekly"]
MEDIUM = ["Stories for Yadeesh: distributed tracing", "Stories for Yadeesh: SRE practices", "Stories for Yadeesh: Go performance", "Stories for Yadeesh: team leadership"]
OBSERVA = [("Observa: monthly usage summary", "Your September usage summary is available in the Observa console."),
           ("Observa: new log retention options", "You can now choose 7, 30 or 90-day retention per index."),
           ("Observa: webinar on SLO alerts", "Join our webinar on multi-window SLO alerts next week.")]
HIREWELL = [("Candidate profiles for Senior SRE", "Sharing three profiles for your Senior SRE opening."),
            ("Following up on the Frontend role", "Checking whether you would like more Frontend profiles this month.")]
BRIGHTLINE = [("Notes from our sync", "Thanks for the productive sync. Notes attached in the shared folder."),
              ("Dashboard access for our analysts", "Could two of our analysts get read access to the pipeline dashboard?")]
SENT_REPLIES = ["Thanks, looks good.", "Noted, thanks for the heads-up.", "Sounds good to me.", "Thanks for sharing.", "Let's discuss at standup."]

MEETING_TITLES = ["Platform sync", "Code review session", "Design discussion", "Tech debt triage", "Incident drill", "Roadmap check-in", "Team retro", "Runbook walkthrough", "Release readiness", "Knowledge share"]


def _stamp(rng: random.Random, day: date, lo: int = 9, hi: int = 19) -> str:
    return f"{day.isoformat()} {rng.randint(lo, hi - 1):02d}:{rng.choice([0, 5, 12, 20, 34, 41, 47, 55]):02d}"


def _days(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def filler_emails() -> list[dict]:
    rng = random.Random(RNG_SEED)
    out = []
    days = list(_days(date(2026, 9, 14), date(2026, 10, 4)))
    for i, (subject, body) in enumerate(INTERNAL_TOPICS * 2 + INTERNAL_TOPICS[:10]):
        sender = rng.choice(TEAM_SENDERS)
        subj = subject if i < len(INTERNAL_TOPICS) else f"Re: {subject}"
        out.append(mail(f"fill_int_{i:02d}", _stamp(rng, rng.choice(days)), who(sender), who("yadeesh"), subj, body + f"\n— {who(sender).split(' <')[0].split()[0]}"))
    for i in range(12):
        day = date(2026, 9, 14) + timedelta(days=2 * i)
        out.append(mail(f"fill_newstack_{i:02d}", _stamp(rng, day, 6, 8), EXTERNAL["newstack"], who("yadeesh"), NEWSTACK[i % len(NEWSTACK)],
                        "Top stories this week from the cloud native world. Read online for the full issue.", inbox=False, labels=["Newsletters"], cat="updates", tz="+00:00"))
    for i in range(8):
        day = date(2026, 9, 15) + timedelta(days=3 * i)
        out.append(mail(f"fill_medium_{i:02d}", _stamp(rng, day, 6, 8), EXTERNAL["medium"], who("yadeesh"), MEDIUM[i % len(MEDIUM)],
                        "Today's highlights picked for you. Become a member for unlimited reading.", inbox=False, labels=["Reading"], cat="updates", tz="+00:00"))
    for i, (subject, body) in enumerate(OBSERVA):
        out.append(mail(f"fill_observa_{i}", _stamp(rng, days[4 + 5 * i]), EXTERNAL["linh"], who("yadeesh"), subject, body, labels=["Vendors/Observa"], tz="+00:00"))
    for i, (subject, body) in enumerate(HIREWELL):
        out.append(mail(f"fill_hirewell_{i}", _stamp(rng, days[6 + 6 * i]), EXTERNAL["hirewell"], who("yadeesh"), subject, body, tz="+05:30"))
    for i, (subject, body) in enumerate(BRIGHTLINE):
        out.append(mail(f"fill_brightline_{i}", _stamp(rng, days[3 + 7 * i]), EXTERNAL["samuel"], who("yadeesh"), subject, body, labels=["Clients/Brightline"], tz="+01:00"))
    for i in range(15):
        topic = INTERNAL_TOPICS[i]
        to = rng.choice(TEAM_SENDERS)
        out.append(mail(f"fill_sent_{i:02d}", _stamp(rng, rng.choice(days)), who("yadeesh"), who(to), f"Re: {topic[0]}", rng.choice(SENT_REPLIES), sent=True, inbox=False))
    return out


def notification_emails() -> list[dict]:
    from world_data import GITHUB, GITHUB_UNREAD, HR_PORTAL, JIRA, JIRA_UNREAD

    out = []
    for wid, when, subject in JIRA:
        out.append(mail(wid, when, EXTERNAL["jira"], who("yadeesh"), subject, f"{subject.replace('[JIRA] ', '')}. View the issue in Jira.",
                        unread=wid in JIRA_UNREAD, cat="updates"))
    for wid, when, subject in GITHUB:
        out.append(mail(wid, when, EXTERNAL["github"], who("yadeesh"), subject, "View it on GitHub. You are receiving this because you are watching the repository.",
                        unread=wid in GITHUB_UNREAD, cat="updates", tz="+00:00"))
    for wid, when, subject, unread in HR_PORTAL:
        out.append(mail(wid, when, EXTERNAL["hr_portal"], who("yadeesh"), subject, f"{subject}. See the HR portal for details.", unread=unread, cat="updates"))
    return out


def filler_events() -> list[dict]:
    """Ordinary meetings on days no task inspects closely."""
    from world_data import ev

    rng = random.Random(RNG_SEED + 1)
    blocked = {h for h, _ in HOLIDAYS} | set(OFFSITE_DAYS)
    blocked |= {(date(2026, 10, 7) + timedelta(days=i)).isoformat() for i in range(10)}  # 7–16 Oct
    blocked.add("2026-11-02")
    people = ["meera.pillai", "karthik.s", "arjun.mehta", "neha.gupta", "vikram.rao", "farah.khan"]
    ranges = [(date(2026, 9, 28), date(2026, 10, 6)), (date(2026, 10, 19), date(2026, 11, 6))]
    out = []
    n = 0
    for lo, hi in ranges:
        for day in _days(lo, hi):
            if day.isoformat() in blocked:
                continue
            for _ in range(rng.choice([1, 2])):
                hour = rng.choice([13, 14, 15, 16, 17])
                start = f"{hour:02d}:{rng.choice(['00', '30'])}"
                end_h = hour + 1 if start.endswith("00") else hour + 1
                end = f"{end_h:02d}:{start[-2:]}"
                if end > "18:00":
                    end = "18:00"
                organizer = rng.choice(people)
                guests = {p: "accepted" for p in rng.sample([p for p in people if p != organizer], rng.choice([1, 2]))}
                rng.random()  # keep the random stream stable; Yadeesh is never a filler guest
                out.append(ev(f"fill_ev_{n:03d}", day.isoformat(), start, end, rng.choice(MEETING_TITLES), organizer, guests))
                n += 1
    return out
