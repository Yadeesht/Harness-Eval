# World spec: Kestrel Analytics

The one fake company all 40 tasks run against. The seed files are generated from this spec, so it has to be exact wherever a grader checks something.

**Companion files:**
- `catalogue.md`: the 40 tasks (prompts, correct end states, traps).
- `tool_reference.md`: how the real tools present all of this: output formats, search matching, displayed sheet values.

## Rules for this world

1. **One consistent base seed.** Facts that exist only to confuse one task live in that task's `seed_additions` (§9), never in the base.
2. **Every fact a task needs is findable with the tools.** No world knowledge is needed: time-zone offsets, rules and names are all written somewhere in the seed.
3. **Nothing sits on a cut-off** (30 days old, ₹5,000, exactly half accepted) unless it is a named trap and the prompt states the rule.
4. **"Used by"** on every seeded item lists the tasks that depend on it. After changing an item, re-validate those tasks.
5. **Each person's calendar is derived from one event list:** an event appears on the calendar of every internal attendee, with that person's response.

---

## 1. Frame

| | |
|---|---|
| Company | Kestrel Analytics, domain `kestrel.test` |
| User | Yadeesh T, Engineering Manager, Platform team, `yadeesh@kestrel.test` |
| Now (frozen) | **Wednesday 7 October 2026, 09:30 IST** (Asia/Kolkata, UTC+05:30) |
| Locale | en_GB (sheets show dates as dd/mm/yyyy) |

Context line used by every task:

> You are an assistant acting for Yadeesh T (yadeesh@kestrel.test), Engineering Manager of the Platform team at Kestrel Analytics. The current date and time is Wednesday, 7 October 2026, 09:30 IST (Asia/Kolkata, UTC+05:30). Weeks start on Monday. Working hours are 10:00–18:00 IST, Monday to Friday.

### Key dates

| Week (Mon–Fri) | Name used in prompts | Notes |
|---|---|---|
| 28 Sep – 2 Oct | last week | Fri 2 Oct: company holiday (Gandhi Jayanti) |
| 5 – 9 Oct | this week | now = Wed 7 Oct 09:30 |
| 12 – 16 Oct | next week | Mon 12: Ananya Das starts. **Thu 15 – Fri 16: Platform Team Offsite** |
| 19 – 23 Oct | | Mon 19 (Mahanavami / Ayudha Pooja) and Tue 20 (Vijayadashami / Dussehra): company holidays |
| 26 – 30 Oct | | |
| 2 – 6 Nov | | |
| 9 – 13 Nov | | Arjun Mehta on leave |

30 days before now is 7 Sep 09:30. Nothing time-windowed sits between 4 Sep and 10 Sep.

---

## 2. People

| Name | Email | Team | Role | Manager | Location |
|---|---|---|---|---|---|
| Yadeesh T | yadeesh@kestrel.test | Platform | Engineering Manager | Rahul Verma | Bengaluru |
| Meera Pillai | meera.pillai@kestrel.test | Platform | Senior Engineer (Tech Lead) | Yadeesh T | Bengaluru |
| Karthik Subramanian | karthik.s@kestrel.test | Platform | Engineer | Yadeesh T | Chennai |
| Arjun Mehta | arjun.mehta@kestrel.test | Platform | Engineer | Yadeesh T | Bengaluru |
| Neha Gupta | neha.gupta@kestrel.test | Platform | SRE Lead | Yadeesh T | Pune |
| Vikram Rao | vikram.rao@kestrel.test | Platform | Engineer | Yadeesh T | Bengaluru |
| Rahul Verma | rahul.verma@kestrel.test | Engineering | Director of Engineering | Kavita Menon | Bengaluru |
| Farah Khan | farah.khan@kestrel.test | Product | Product Manager, Platform | Anil Kumar | Mumbai |
| Priya Raman | priya.raman@kestrel.test | Design | Design Lead | Anil Kumar | Bengaluru |
| Priya Nair | priya.nair@kestrel.test | Finance | Finance Business Partner | Suresh Iyer | Bengaluru |
| Samantha Lee | samantha.lee@kestrel.test | People | People Partner | Suresh Iyer | Bengaluru |
| Rohan Kapoor | rohan.kapoor@kestrel.test | Security | Security Engineer | Rahul Verma | Delhi |
| Deepak Joshi | deepak.joshi@kestrel.test | IT | IT Operations | Suresh Iyer | Bengaluru |
| Isha Bhatt | isha.bhatt@kestrel.test | Operations | Office & Events Coordinator | Suresh Iyer | Bengaluru |
| Ananya Das | ananya.das@kestrel.test | Platform | Engineer (joins Mon 12 Oct) | Yadeesh T | Bengaluru |

- **Ananya's address appears only in Samantha's welcome email** (`sl_welcome`), not in the Team Directory. Used by cal_01, x_02.
- **Direct reports** (Manager = Yadeesh T in the Team Directory): Meera, Karthik, Arjun Mehta, Neha, Vikram.
- **External people:**
  - Samuel Okafor (`sam.okafor@brightline.test`, Head of Data, Brightline Retail, Lagos)
  - Arjun Iyer (`arjun.iyer@cloudnest.test`, Account Manager, CloudNest)
  - CloudNest Billing (`billing@cloudnest.test`), Support (`support@cloudnest.test`), Status (`status@cloudnest.test`)
  - Linh Tran (`linh.tran@observa.test`, Observa)
- **Name collisions (deliberate):**

| Collision | People |
|---|---|
| Two Priyas | Priya Raman (Design) / Priya Nair (Finance) |
| Two Sams | Samuel Okafor (Brightline) / Samantha Lee (HR) |
| Two Arjuns | Arjun Mehta (team) / Arjun Iyer (CloudNest) |
| Two candidates | Rakesh Pillai / Rakesh Pillay |

Email display names follow `Name <address>`. Priya Nair signs `Priya Nair | Finance Business Partner`; Priya Raman signs `Priya Raman | Design Lead`.

---

## 3. Calendars

### 3.1 Calendar list (`list_calendars`)

| id | summary | accessRole |
|---|---|---|
| yadeesh@kestrel.test | Yadeesh T | owner (primary) |
| c_interviews_kestrel@group.calendar.google.com | Interviews | writer |
| c_holidays_kestrel@group.calendar.google.com | Kestrel Holidays (India) | reader |
| meera.pillai@ / karthik.s@ / neha.gupta@ / arjun.mehta@ / vikram.rao@ / rahul.verma@ / farah.khan@ / rohan.kapoor@ (kestrel.test) | the person's name | reader |

### 3.2 Conventions
- **Organizer:** events Yadeesh organizes list him as an attendee, `accepted`, marked organizer. That's what makes "(organizer)" show (`tool_reference` §3.1). The same applies to events other people organize.
- **Busy:** an attendee is busy for an event unless their response is `declined`. `tentative` and `needsAction` count as busy.
- **Offsite:** the offsite is an all-day event on Thu 15 and Fri 16 Oct (organizer Isha, all Platform staff + Rahul + Farah + both Priyas + Samantha + Isha invited). No task needs a slot on those days.
- **Recurring series:** stored as individual instances (the tools only ever see instances). Instance IDs look like `<series>_<yyyymmdd>`.
- **Events organized by Yadeesh have a description only where listed below.**

### 3.3 Recurring series (instances generated from 21 Sep to 13 Nov)

| Series | When | Organizer | Guests | Skipped on |
|---|---|---|---|---|
| Platform Standup | Mon–Fri 10:00–10:15 | Neha | Yadeesh, Meera, Karthik, Arjun M, Vikram (all accepted) | holidays, offsite days |
| 1:1 Yadeesh / Neha | Tue 11:30–12:00 | Yadeesh | Neha (accepted) | holidays |
| 1:1 Yadeesh / Meera | Wed 12:00–12:30 | Yadeesh | Meera (accepted) | |
| 1:1 Yadeesh / Rahul | Thu 10:30–11:00 | Yadeesh | Rahul (accepted) | Thu 15 Oct |
| 1:1 Yadeesh / Karthik | Fri 11:00–11:30 | Yadeesh | Karthik (accepted) | Fri 2 Oct, Fri 16 Oct |
| Brightline weekly sync | Thu 15:30–16:00 | Yadeesh | Samuel Okafor (accepted) | Thu 15 Oct instance moved to **Wed 14 Oct 15:30–16:00** |
| 1:1 Farah / Yadeesh | every other Tue 12:00–13:00 (29 Sep, 13 Oct, 27 Oct, 10 Nov) | Farah | Yadeesh (accepted) | |

### 3.4 Key days (every event, all calendars)

Status letters: a = accepted, t = tentative, n = needsAction, d = declined.

**Thu 8 Oct.** Used by: cal_01, cal_03, amb_02, imp_02, x_10.

| Time | Event | Organizer | Guests |
|---|---|---|---|
| 10:00–10:15 | Platform Standup | Neha | series |
| 10:30–11:00 | 1:1 Yadeesh / Rahul | Yadeesh | Rahul a |
| 11:00–12:00 | **Architecture Review** | Yadeesh | Meera a, Karthik a, Arjun M a, Neha a, Farah a. No Meet link |
| 12:30–13:30 | Lunch | Meera | — |
| 13:00–14:00 | Interview panel | Karthik | — |
| 13:00–14:30 | Leadership sync | Rahul | — |
| 14:00–14:45 | **PRD Review** | Yadeesh | Farah a, Meera a, Karthik n. Description: `Review of the Service Mesh PRD before sign-off.` |
| 15:00–15:30 | **Sprint demo prep** | Yadeesh | Meera a, Karthik a |
| 15:30–16:00 | **Brightline weekly sync** | Yadeesh | Samuel Okafor a (external) |
| 16:00–16:30 | Mesh canary check | Meera | — |
| 16:00–18:00 | Board prep | Rahul | — |
| 16:30–17:30 | Customer call | Farah | — |
| 17:00–17:30 | **HR sync: Ananya onboarding** | Samantha | Yadeesh a |

**Fri 9 Oct.** Used by: imp_02.

| Time | Event | Organizer | Guests |
|---|---|---|---|
| 10:00–10:15 | Platform Standup | Neha | series |
| 11:00–11:30 | 1:1 Yadeesh / Karthik | Yadeesh | Karthik a |
| 12:30–13:00 | Lunch with Priya | Priya Raman | Yadeesh a |
| 13:30–14:30 | Hiring sync | Samantha | Yadeesh a, Rahul a |
| 14:00–15:00 | Interview | Meera | — |
| 15:00–17:00 | Customer calls | Farah | — |
| 16:00–16:30 | Sprint demo | Yadeesh | Meera, Karthik, Arjun M, Neha, Vikram, Farah, Rahul (all a) |

**Wed 7 Oct** (today, after 09:30): Platform Standup 10:00; 1:1 Yadeesh / Meera 12:00–12:30; **Architecture Review — prep** 16:00–16:30 (organizer Yadeesh, Meera a). Used by: cal_01 (look-alike title).

**Mon 12 Oct.** Used by: cal_02, cal_05, cal_06, x_02, x_09.

| Time | Event | Organizer | Guests |
|---|---|---|---|
| 10:00–10:15 | Platform Standup | Neha | series |
| 10:15–11:00 | Interview: backend candidate | Karthik | — |
| 10:30–11:30 | **CloudNest vendor sync** | Yadeesh | Neha a, Arjun Iyer a (external) |
| 11:30–12:30 | Mesh rollout review | Meera | — |
| 12:00–13:00 | **Welcome Ananya** | Yadeesh | Ananya n, Samantha a |
| 13:00–13:30 | Lunch | Yadeesh | — (no guests) |
| 13:00–14:00 | Lunch | Meera | — |
| 13:30–14:30 | 1:1 Karthik / Farah | Farah | Karthik a |
| 14:00–15:00 | Incident review | Neha | — |
| 14:30–16:00 | **Hiring debrief: Senior SRE** | Yadeesh | Meera a, Karthik **d**, Neha t, Vikram n. Description: `Debrief for the Senior SRE loop. Scorecards are in the Hiring Pipeline sheet.` |
| 15:30–17:00 | PRD review prep | Farah | — |
| 16:00–17:00 | Design sync | Priya Raman | Meera a |
| 16:30–18:00 | On-call handover prep | Neha | — |
| 17:00–18:00 | Focus time | Karthik | — |

**Tue 13 Oct.** Used by: cal_02, cal_05, cal_06, x_02.

| Time | Event | Organizer | Guests |
|---|---|---|---|
| 10:00–10:15 | Platform Standup | Neha | series |
| 10:15–11:15 | SLO review | Neha | — |
| 10:30–12:00 | Customer interviews | Farah | — |
| 11:00–12:00 | Capacity model working session | Karthik | Meera a |
| 11:30–12:00 | 1:1 Yadeesh / Neha | Yadeesh | Neha a |
| 12:00–13:00 | 1:1 Farah / Yadeesh | Farah | Yadeesh a |
| 12:30–13:30 | Lunch | Neha | — |
| 13:00–14:00 | Lunch | Meera | — |
| 13:30–14:30 | Interview: SRE candidate | Karthik | — |
| 14:00–14:30 | **Budget check-in** | Yadeesh | Priya Nair **d** |
| 14:30–15:30 | Mesh office hours | Meera | — |
| 15:00–16:00 | Runbook review | Neha | — |
| 15:30–16:00 | Code review block | Karthik | — |
| 17:00–18:00 | Focus | Meera | — |

**Wed 14 Oct.** Used by: cal_06, x_02, x_08.

| Time | Event | Organizer | Guests |
|---|---|---|---|
| 10:00–10:15 | Platform Standup | Neha | series |
| 10:30–12:00 | Customer interviews | Farah | — |
| 12:00–12:30 | 1:1 Yadeesh / Meera | Yadeesh | Meera a |
| 13:00–14:00 | Vendor call: Observa | Neha | Linh Tran a (external) |
| 15:30–16:00 | Brightline weekly sync (moved) | Yadeesh | Samuel Okafor a |
| 16:00–17:00 | **Q4 roadmap pre-read** | Yadeesh | Farah t, Meera a, Karthik n, Arjun M n, Vikram d. No description |

**Wed 28 – Fri 30 Oct** (besides standups). Used by: cal_04.

| Day | Time | Event | Organizer | Guests |
|---|---|---|---|---|
| Wed 28 | 12:00–12:30 | 1:1 Yadeesh / Meera | Yadeesh | Meera a |
| Wed 28 | 14:00–15:00 | Sprint planning | Yadeesh | Meera, Karthik, Arjun M, Neha, Vikram (a) |
| Thu 29 | 10:30–11:00 | 1:1 Yadeesh / Rahul | Yadeesh | Rahul a |
| Thu 29 | 14:00–14:30 | 1:1 Priya Raman / Yadeesh | Priya Raman | Yadeesh a |
| Thu 29 | 15:30–16:00 | Brightline weekly sync | Yadeesh | Samuel Okafor a |
| Fri 30 | 11:00–11:30 | 1:1 Yadeesh / Karthik | Yadeesh | Karthik a |

Also Tue 27 Oct 11:30 1:1 Yadeesh / Neha (outside the leave window) and Tue 27 Oct 16:00–17:00 "Dentist" (Arjun Mehta, own calendar).

**Mon 2 Nov.** Used by: x_07.

| Time | Event | Organizer | Guests |
|---|---|---|---|
| 10:00–10:15 | Platform Standup | Neha | series |
| 10:00–11:30 | Security council | Rohan | — |
| 10:30–11:00 | Pipeline review | Yadeesh | — |
| 11:00–12:00 | SLO review | Neha | — |
| 12:00–13:00 | Tech talk | Karthik | — |
| 13:00–14:00 | Lunch | Meera | — |
| 14:00–15:00 | Quarterly planning kickoff | Rahul | Yadeesh a |
| 15:00–16:00 | Vendor risk review | Rohan | — |
| 16:00–17:00 | Interview | Arjun M | — |

**Arjun Mehta leave:** all-day "OOO" 9–13 Nov on his calendar. Used by: x_01 (a distractor outside the swap weeks).

### 3.5 Checked properties

Verified by brute force over 15-minute starts; the Phase 2 seed check repeats this on the generated seed.

| Claim | Result | Task |
|---|---|---|
| Earliest 60-min slot Mon 12–Wed 14, 10:00–18:00, when Yadeesh, Meera, Karthik and Neha are all free | **Tue 13 Oct 16:00**, unique (next: Wed 10:15) | cal_02 |
| Thu 8, with the Rahul 1:1 moved to 15:00: first 30-min slot after 15:00 when Yadeesh, Meera and Karthik are free | **16:30** (15:30 blocked by Brightline, 16:00 by Meera) | cal_03 |
| Yadeesh free Tue 13 Oct 14:30–15:15; Mon 12 has an external meeting, Tue 13 none | yes | cal_05 |
| Any 2-hour slot Thu 8 or Fri 9, 12:00–18:00, when Yadeesh, Rahul, Farah and Meera are free | **none** | imp_02 |
| 30-min slots Mon 2 Nov when Yadeesh, Neha, Karthik, Rohan, Meera and Arjun M are all free | only **17:00, 17:15, 17:30** | x_07 |
| 30-min slots Mon 12 14:00 – Wed 14 18:00 when Meera / Neha / Farah is free | 37 / 39 / 45 options | x_02 |

### 3.6 Interviews calendar

Organizer `recruiting@kestrel.test`; Yadeesh accepted; the candidate is an external guest.

| Date | Time | Title | Used by |
|---|---|---|---|
| Thu 24 Sep | 15:00–16:00 | Interview: Arvind Rao (SRE) | x_05 (before last week) |
| Tue 29 Sep | 11:00–12:00 | Interview: Divya Menon (Frontend Engineer) | x_05 |
| Wed 30 Sep | 15:00–16:00 | Interview: Karan Shah (SRE) | x_05 (already Offer) |
| Thu 1 Oct | 12:00–13:00 | Interview: Lakshmi Iyer (Backend Engineer) | x_05 |
| Mon 5 Oct | 14:00–15:00 | Interview: Rakesh Pillai (Backend Engineer) | x_05 (this week) |

### 3.7 Kestrel Holidays calendar (all-day)

| Date | Title |
|---|---|
| Fri 2 Oct | Gandhi Jayanti — office closed |
| Mon 19 Oct | Mahanavami / Ayudha Pooja — office closed |
| Tue 20 Oct | Vijayadashami (Dussehra) — office closed |
| Fri 25 Dec | Christmas — office closed |

Used by: x_09 (Mon 19 and Tue 20 → the handover moves to Wed 21).

### 3.8 Filler

The weeks of 21 Sep and 28 Sep, and 19 Oct onward, get the recurring series plus 2–4 ordinary internal meetings per weekday. Filler never touches the key days above and never uses the titles Architecture Review, PRD Review, Budget, Brightline, Interview or Capacity.

---

## 4. Gmail

### 4.1 User labels

`Vendors`, `Vendors/Observa`, `Security`, `Newsletters`, `Reading`, `Action Required`, `Clients`, `Clients/Brightline`, `Hiring`, `Receipts`.

System labels behave as in `tool_reference` §2.4. Notifications (Jira, GitHub, HR portal, CloudNest status) carry `CATEGORY_UPDATES`; human mail carries `CATEGORY_PERSONAL` (primary).

### 4.2 Filters

| id | Criteria | Action | Used by |
|---|---|---|---|
| f_rohan | from `rohan.kapoor@kestrel.test` | add `Security`, remove `INBOX` | em_04 (the mistake) |
| f_newstack | from `digest@thenewstack.test` | add `Newsletters`, remove `INBOX` | em_04 (keep) |
| f_medium | from `noreply@medium.test` | add `Reading`, remove `INBOX` | em_04 (keep) |

### 4.3 Needle emails

**Column conventions:**
- **When** is IST, 2026.
- **State:** I = in INBOX, U = unread, A = archived (not in INBOX), S = SENT.
- **Body text:** each body is given as the sender wrote it (line breaks shown as ` / `). `read_email` shows it flattened to one line.

**CloudNest.** Used by em_01, em_03, x_04.

| id | When | From | Subject | Body (key text) | State | Used by |
|---|---|---|---|---|---|---|
| cn_inv_jul | 4 Aug 10:05 | CloudNest Billing | CloudNest invoice CN-2026-07 (July 2026) | Invoice CN-2026-07 for July 2026. / Amount due: ₹1,68,000 / Due date: 18 Aug 2026 | I | em_03 (outside the window) |
| cn_rcpt_jul | 20 Aug 09:10 | CloudNest Billing | Payment receipt for invoice CN-2026-07 | We received ₹1,68,000 for invoice CN-2026-07. Thank you. | I | em_03 (outside) |
| cn_inv_aug | 3 Sep 10:02 | CloudNest Billing | CloudNest invoice CN-2026-08 (August 2026) | Amount due: ₹1,70,000 / Due date: 18 Sep 2026 | I | em_01 (distractor), em_03 (outside) |
| cn_rcpt_aug | 12 Sep 09:40 | CloudNest Billing | Payment receipt for invoice CN-2026-08 | We received ₹1,70,000 for invoice CN-2026-08. | I | em_03 (billing) |
| cn_tkt_1 | 15 Sep 14:22 | CloudNest Support | Ticket #48213: Elevated latency in ap-south-1 | We are investigating elevated latency... | I | em_03 (support) |
| cn_tkt_1b | 18 Sep 11:05 | CloudNest Support | Ticket #48213 update: resolved | The latency issue is resolved... | I | em_03 (support) |
| cn_status | 28 Sep 08:00 | CloudNest Status | Scheduled maintenance on 10 Oct, 02:00–04:00 IST | Planned maintenance of the ap-south-1 control plane... | I | em_03 (neither) |
| cn_tkt_2 | 29 Sep 16:40 | CloudNest Support | Ticket #48377: Snapshot restore failing | We have reproduced the snapshot restore failure... | I | em_03 (support) |
| cn_renewal | 30 Sep 17:15 | Arjun Iyer | Draft renewal proposal for Q4 | Hi Yadeesh, attaching our draft renewal proposal for Q4 — happy to walk through it at our 12 Oct sync. / Arjun Iyer, CloudNest | I | em_02 (Arjun distractor), em_03 (neither) |
| cn_inv_sep | 1 Oct 10:00 | CloudNest Billing | CloudNest invoice CN-2026-09 (September 2026) | Invoice CN-2026-09 for September 2026. / Amount due: ₹1,92,400 / Due date: 15 Oct 2026 | I | em_01, x_04 (superseded), em_03 (billing) |
| cn_inv_sep_r | 3 Oct 12:30 | CloudNest Billing | Revised: CloudNest invoice CN-2026-09R (September 2026) | This invoice replaces CN-2026-09 sent on 1 Oct, which double-counted storage. / Amount due: ₹1,84,500 / Due date: 20 Oct 2026 / Please disregard CN-2026-09. | I | **em_01, x_04 (the one to use)**, em_03 (billing) |

**Q4 OKR drafts.** Used by em_02.

| id | When | From → To | Subject | Body | State |
|---|---|---|---|---|---|
| okr_ask | 29 Sep 11:02 | Yadeesh → Meera, Karthik, Arjun Mehta, Neha | Q4 OKR drafts — due Fri 2 Oct | Hi all, please send me your draft Q4 OKRs by Friday 2 Oct. One page is fine. / Thanks, Yadeesh | S |
| okr_meera | 1 Oct 18:20 | Meera → Yadeesh | Re: Q4 OKR drafts — due Fri 2 Oct | Here's my draft: / O1 Finish the mesh migration with zero Sev1s / O2 Halve p95 latency on the payments API | I |
| okr_arjun | 2 Oct 15:30 | Arjun Mehta → Yadeesh | My Q4 OKR draft | Hi Yadeesh, my draft OKRs: / O1 Cut the flaky-test rate below 1% / O2 Own the failover runbook | I |
| okr_karthik | 2 Oct 19:05 | Karthik → Yadeesh | Re: Q4 OKR drafts — due Fri 2 Oct | Sorry, I'm running behind — I'll send my draft on Monday. | I |

Neha never replied. Karthik hasn't sent his draft (Monday 5 Oct has passed).

**Expense approvals.** Used by em_05. All are in the inbox and read.

| id | When | From | Subject | Answered? |
|---|---|---|---|---|
| ex_v_dock | 28 Aug 17:30 | Vikram | Expense approval: USB-C dock (₹2,000) | no (outside Sep–Oct) |
| ex_k_lunch | 8 Sep 12:10 | Karthik | Expense approval: team lunch (₹3,200) | **yes**: Sent 9 Sep 10:00 "Re: Expense approval: team lunch (₹3,200)", body "Approved." |
| ex_n_taxi | 22 Sep 09:45 | Neha | Expense approval: on-call taxi (₹1,850) | no → approve |
| ex_a_conf | 25 Sep 14:05 | Arjun Mehta | Expense approval: conference ticket (₹18,000) | no → receipt |
| ex_m_books | 29 Sep 11:30 | Meera | Expense approval: technical books (₹5,000) | no → approve (boundary, stated in prompt) |
| ex_m_monitor | 2 Oct 10:15 | Meera | Expense approval: monitor (₹12,500) | no → receipt |
| ex_k_cab | 5 Oct 17:40 | Karthik | Expense approval: cab to client site (₹780) | no → approve |
| hr_reimb | 3 Oct 09:00 | no-reply@kestrel.test (Kestrel HR Portal) | Your expense report ER-1182 has been reimbursed | not a request |

Each request body: `Hi Yadeesh, please approve my expense: <item>, <amount>. Receipt available on request.`

**Rohan (security).** Used by em_04. All carry the `Security` label and are archived by f_rohan (not in the inbox), all read.

| id | When | Subject | Deadline? |
|---|---|---|---|
| rk_laptop | 20 Aug 10:00 | Laptop encryption audit — due 31 Aug | (outside the 30-day window) |
| rk_access | 10 Sep 11:00 | Quarterly access review — due 12 Oct | **yes** |
| rk_phish | 18 Sep 15:20 | FYI: phishing campaign targeting finance teams | no ("no action needed") |
| rk_keys | 25 Sep 10:40 | Rotate your team's service-account keys by 9 Oct | **yes** |
| rk_hours | 2 Oct 09:30 | Security office hours move to Thursdays | no |
| rk_pentest | 5 Oct 16:00 | Pen test results for Platform — no action needed | no |

**Rahul.**

| id | When | Subject | Body | State | Used by |
|---|---|---|---|---|---|
| rh_dinner | 4 Oct 11:15 | Offsite dinner: let's do Villa Shanti | For the team dinner on 15 Oct, let's book Villa Shanti at 19:30. — Rahul (to Yadeesh, Isha) | I | amb_03 |
| rh_staff | 6 Oct 09:00 | Staff meeting agenda — Thursday | Agenda for Thursday's staff meeting: hiring, Q4 budget, offsite logistics. | I, U | em_06 (stays unread) |
| rh_move | 6 Oct 18:40 | Can we move our 1:1? | Hi Yadeesh, I'm travelling on Thursday morning. Can we move our 1:1 this Thursday to 15:00, same length? / Thanks, Rahul | I, U | cal_03, em_06 (stays unread) |

**Farah.**

| id | When | Subject | Body | State | Used by |
|---|---|---|---|---|---|
| fk_prd_v0 | 29 Sep 17:00 | Early thoughts on the PRD v0 | Two quick notes on v0: / 1. The scope section is too broad. / 2. Add a glossary. | I | x_06 (distractor) |
| fk_mesh_date | 5 Oct 11:20 | Service Mesh launch date change | Heads-up: the Service Mesh Migration launch moves from 30 Nov to 11 Dec 2026 because of the CloudNest dependency. Everything else in the Q4 plan stays as it is. | I | doc_01 |
| fk_prd_fb | 5 Oct 16:05 | Feedback on the Service Mesh PRD | Hi Yadeesh, here is my feedback on the Service Mesh PRD: / 1. Add rollback criteria for the canary stage. / 2. Name an owner for mTLS certificate rotation. / 3. Include a cost estimate for the sidecars. / 4. Link the SLO dashboard in the success-metrics section. / Thanks, Farah | I, U | x_06, em_06 (untouched) |
| fk_prd_agenda | 6 Oct 12:30 | Agenda for Thursday's PRD Review | Agenda for Thursday's PRD Review: / 1. Open questions on the canary rollout / 2. Sidecar cost model / 3. Sign-off owners | I, U | x_10, em_06 (untouched) |

**Samuel (Brightline).** Sent from `+0100`.

| id | When (IST) | Subject | Body | State | Used by |
|---|---|---|---|---|---|
| so_thanks | 1 Oct 20:40 | Thanks for today's sync | Thanks for the sync today, Yadeesh — notes to follow. | I | filler |
| so_call | 5 Oct 18:40 | Call next week? | Hi Yadeesh, could we set up a 45-minute call next week? 10:00 my time works best (I'm in Lagos, WAT = UTC+1). / Agenda: / 1. Q4 data-pipeline SLAs / 2. Snowflake migration timeline / 3. Contract renewal / Best, Samuel | I, U | cal_05, em_06 (untouched) |

**People and team.**

| id | When | From | Subject | Body (key text) | State | Used by |
|---|---|---|---|---|---|---|
| sl_welcome | 2 Oct 16:20 | Samantha Lee | New joiner: Ananya Das starts Mon 12 Oct | Hi Yadeesh, Ananya Das joins the Platform team as an Engineer on Monday 12 October. Her work email is ananya.das@kestrel.test. Her onboarding buddy will be Vikram Rao. HR induction runs 10:00–13:00 on her first day. / Thanks, Samantha | I | cal_01, x_02 |
| ne_swap | 5 Oct 19:10 | Neha Gupta | On-call swap? | Hi Yadeesh, could I swap my on-call week of 19 Oct with Arjun's week of 26 Oct? I have a family function on the 20th. Arjun is fine with it. / — Neha | I, U | x_01, em_06 (mark read) |
| me_canary | 6 Oct 17:30 | Meera Pillai | Mesh canary looks good | Canary at 5% for 24h, error rate flat. Planning 25% on Monday. | I, U | em_06 (mark read) |
| ka_capq | 6 Oct 11:45 | Karthik Subramanian | Question on the capacity model | Should the capacity model include the Observa trial nodes? | I, U | em_06 (mark read) |
| dj_jira | 2 Oct 14:00 | Deepak Joshi | Jira migration to the cloud this weekend | Jira will be read-only from Saturday 10:00 to Sunday 18:00 during the move. | I | imp_01 (not a notification) |

**Offsite.**

| id | When | From → To | Subject | Body (key text) | State | Used by |
|---|---|---|---|---|---|---|
| ib_offsite | 22 Sep 10:00 | Isha → Platform team, Rahul, Farah, both Priyas, Samantha | Platform offsite: 15–16 Oct at Le Pondy, Puducherry | The offsite is confirmed for Thu 15 – Fri 16 Oct at Le Pondy, Puducherry. Please RSVP in the "Offsite RSVPs" sheet by 2 Oct. | I | imp_03, amb_03 |
| ib_agenda | 5 Oct 12:00 | Isha → Yadeesh (cc Rahul, Priya Raman, Priya Nair) | Offsite agenda v2 — feedback please | The draft agenda is in the doc "Platform Offsite Agenda — Draft". Comments welcome. | I | amb_01, doc_02 |
| pr_agenda | 6 Oct 10:15 | Priya Raman → Yadeesh | Re: Offsite agenda v2 — feedback please | Could you send me the updated agenda once it's final? I want to plan the design critique slot. / Priya Raman \| Design Lead | I | amb_01 |
| pn_agenda | 6 Oct 14:50 | Priya Nair → Yadeesh | Re: Offsite agenda v2 — feedback please | Please send me the updated agenda so I can check the catering costs. / Priya Nair \| Finance Business Partner | I | amb_01 |

**Notifications.** All `CATEGORY_UPDATES`, in the inbox.

| Sender | Count | Unread ones | Used by |
|---|---|---|---|
| Jira `notifications@jira.kestrel.test` | 12 (14 Sep – 7 Oct), subjects `[JIRA] PLAT-3xx/4xx ...` | jr_401 (1 Oct, last week), jr_412 (5 Oct 09:12), jr_415 (7 Oct 08:10) | imp_01 (archive all 12), em_06 (jr_412, jr_415) |
| GitHub `noreply@github.test` | 10 | gh_881 (6 Oct 13:05, "[kestrel/platform] PR #881 merged") | em_06 |
| HR portal `no-reply@kestrel.test` | 4 (incl. hr_reimb) | hr_timesheet (6 Oct 09:00, "Reminder: submit your timesheet") | em_06 |

**Unread mail this week, for em_06.**

| Group | Mail | Outcome |
|---|---|---|
| Automated | jr_412, jr_415, gh_881, hr_timesheet | archive |
| Direct reports | ne_swap, me_canary, ka_capq | mark read |
| Rahul | rh_staff, rh_move | stay unread |
| Everyone else | fk_prd_fb, fk_prd_agenda, so_call | untouched |

Nothing else dated 5–7 Oct is unread. jr_401 (1 Oct) is unread but last week.

### 4.4 Filler (~120 messages, generated with a fixed random seed)

- **Internal threads (~50):** status updates, questions and FYIs among the people above, 14 Sep – 7 Oct, read.
- **Newsletters (~20):** `digest@thenewstack.test` (label Newsletters) and `noreply@medium.test` (label Reading), archived by their filters.
- **Other vendors (~10):** Observa (`linh.tran@observa.test`), a recruiting agency (`talent@hirewell.test`); Brightline filler (label `Clients/Brightline`).
- **Sent mail (~15):** Yadeesh's replies.
- **Filler must never:**
  - add another expense approval, CloudNest invoice or receipt, OKR draft, Rohan mail or Jira notification;
  - add unread mail dated 5–7 Oct;
  - use the subjects of any needle above.

**Size limit:** a bare search returns at most 100 results at ~350 characters each (~35k), under the 50k limit.

---

## 5. Docs

All owned by Yadeesh unless noted. Line breaks are paragraphs. Graded docs are given in full.

| Title | Used by | Notes |
|---|---|---|
| Q4 Planning — Platform | doc_01 | below |
| Q4 Planning — Data Team | doc_01 (distractor) | another team's plan, also dated 30 Nov items |
| Platform Offsite Agenda — Draft | doc_02, amb_01, imp_03 | below, with comments |
| Postmortem — Payments API outage (29 Sep 2026) | doc_03, x_07 | below (action items in a table) |
| Postmortem — Search API latency (12 Aug 2026) | doc_03 (distractor) | older postmortem with its own action items |
| Postmortem Template | doc_03 (distractor) | empty headings |
| Platform Weekly Sync — 21 Sep 2026 | doc_04 | below |
| Platform Weekly Sync — 28 Sep 2026 | doc_04, x_03 | below |
| Data Team Weekly Sync — 28 Sep 2026 | doc_04, x_03 (distractor) | other owners and items |
| Hiring Plan H2 | doc_05 | below |
| Hiring Plan H1 | doc_05 (distractor) | older plan, also has an "Open Roles" heading |
| New Hire Onboarding Checklist — Platform | x_02 | below |
| Service Mesh PRD | x_06, x_10 | below |
| Service Mesh PRD v0 (archived) | x_06, x_10 (distractor) | older draft |
| Platform Architecture Overview | filler | referenced by the checklist |

**Q4 Planning — Platform**
```
Q4 Planning — Platform
Owner: Yadeesh T · Last updated: 30 Sep 2026
Projects
Service Mesh Migration — owner: Meera Pillai — launch: 30 Nov 2026 — status: on track
Billing Revamp — owner: Karthik Subramanian — launch: 30 Nov 2026 — status: at risk
Observability v2 — owner: Neha Gupta — launch: 15 Dec 2026 — status: on track
Flaky Test Cleanup — owner: Arjun Mehta — launch: 23 Oct 2026 — status: on track
Key dates
16 Nov 2026 — Service Mesh Migration canary
30 Nov 2026 — Service Mesh Migration launch
30 Nov 2026 — Billing Revamp launch
15 Dec 2026 — Observability v2 launch
Risks
The CloudNest dependency may delay the mesh rollout.
```

**Platform Offsite Agenda — Draft** (owner Isha Bhatt)
```
Platform Offsite — 15–16 Oct 2026 — Le Pondy, Puducherry
Draft v2 · owner: Isha Bhatt
Day 1 — Thu 15 Oct
09:30 Arrive and coffee
10:00 Roadmap review
12:30 Lunch
14:00 Team working sessions
17:30 Wrap-up
19:30 Team dinner
Day 2 — Fri 16 Oct
09:30 Incident retro
11:00 Team building
13:00 Lunch
15:00 Travel back
```

Comments (author display names):

| id | Author | Status | Content |
|---|---|---|---|
| c1 | Rahul Verma | open | Please rename "Roadmap review" to "Roadmap & OKRs". |
| c2 | Rahul Verma | open | Move lunch on Day 1 to 13:00. |
| c3 | Priya Raman | open | Can we add a design critique slot on Day 2? |
| c4 | Rahul Verma | resolved (reply from Isha Bhatt: "Added.") | Add the venue name to the title line. |
| c5 | Farah Khan | open | Should product join the incident retro? |

**Postmortem — Payments API outage (29 Sep 2026)** (author Neha Gupta). The action items are a real 4-column table, which `get_doc_content` flattens (`tool_reference` §5).
```
Postmortem — Payments API outage (29 Sep 2026)
Author: Neha Gupta · Status: final
Summary
The Payments API returned errors for 47 minutes after a queue backlog triggered cascading retries.
Timeline
14:02 Queue backlog starts; no alert fires
14:19 Retries saturate the payments client
14:49 Failover completed manually
Root cause
No retry budget in the payments client, and no alert on queue depth.
Action items
[table]
Owner | Action | Due | Tag
Neha Gupta | Add an alert on payment-queue depth | 14 Oct 2026 | [OPS]
Karthik Subramanian | Add a retry budget to the payments client | 23 Oct 2026 | [ENG]
Rohan Kapoor | Rotate the leaked staging credentials | 9 Oct 2026 | [SEC]
Meera Pillai | Load-test the failover path | 28 Oct 2026 | [ENG]
Arjun Mehta | Document the manual failover runbook | 16 Oct 2026 | [OPS]
Rohan Kapoor | Audit service-account permissions | 30 Oct 2026 | [SEC]
```
All due dates differ. The latest is Fri 30 Oct, so the next working day is Mon 2 Nov.

**Platform Weekly Sync — 21 Sep 2026**
```
Platform Weekly Sync — 21 Sep 2026
Attendees: Yadeesh, Meera, Karthik, Neha, Arjun, Vikram
Notes
Mesh rollout planning started; canary target mid-November.
Flaky tests are blocking two releases a week.
Action items
Meera Pillai: Draft the mesh canary plan
Karthik Subramanian: Capacity model v1
Neha Gupta: Update the on-call runbook
Arjun Mehta: Fix flaky integration tests
Vikram Rao: Evaluate the Observa trial
```

**Platform Weekly Sync — 28 Sep 2026**
```
Platform Weekly Sync — 28 Sep 2026
Attendees: Yadeesh, Meera, Karthik, Neha, Arjun, Vikram
Notes
Karthik moves to the Billing Revamp, so his capacity-model work passes to Vikram.
Updates on earlier action items
Draft the mesh canary plan (Meera Pillai) — DONE
Capacity model v1 — reassigned from Karthik Subramanian to Vikram Rao — open
Update the on-call runbook (Neha Gupta) — open
Fix flaky integration tests (Arjun Mehta) — DONE
Evaluate the Observa trial (Vikram Rao) — open
New action items
Yadeesh T: Confirm the offsite dates with Isha — DONE
Yadeesh T: Book the Q4 capacity planning meeting — due 16 Oct 2026
Yadeesh T: Share the hiring plan with Rahul — due 12 Oct 2026
Karthik Subramanian: Draft the Billing Revamp migration plan — due 9 Oct 2026
Meera Pillai: Prepare the architecture review deck — due 8 Oct 2026
```

**Open items as of 28 Sep** (the answer for doc_04; x_03 uses the same list):

| Owner | Open items |
|---|---|
| Vikram Rao | Capacity model v1; Evaluate the Observa trial |
| Neha Gupta | Update the on-call runbook |
| Yadeesh T | Book the Q4 capacity planning meeting (due 16 Oct); Share the hiring plan with Rahul (due 12 Oct) |
| Karthik Subramanian | Draft the Billing Revamp migration plan (due 9 Oct) |
| Meera Pillai | Prepare the architecture review deck (due 8 Oct) |

Closed: the mesh canary plan, flaky tests, and confirming the offsite dates.

**Hiring Plan H2**
```
Hiring Plan H2 2026 — Platform
Owner: Yadeesh T · Status: draft
Summary
We have four open roles this half, two of them urgent.
Open Roles
Senior SRE (urgent) — Bengaluru
Backend Engineer (urgent) — Bengaluru
Frontend Engineer — Remote (India)
Data Engineer — Pune
Interview loop
Phone screen, take-home, onsite (three interviews), debrief.
```
No header or footer. `Open Roles` appears once as its own line; the lowercase "open roles" in Summary is not the heading.

**New Hire Onboarding Checklist — Platform** (owner Samantha Lee)
```
New Hire Onboarding Checklist — Platform
Day 1 is the new hire's start date. Due dates below are relative to Day 1.
Week 1
IT setup (Day 1): collect the laptop from the IT desk; enable 2-step verification; request GitHub and CloudNest access
HR induction (Day 1)
Read the Platform Architecture Overview (Day 2)
Shadow an on-call handover (Day 3)
First pull request merged (Day 5)
Intro 1:1s (Week 1)
Book three 30-minute intro 1:1s: with the tech lead (Meera Pillai), the SRE lead (Neha Gupta) and the product manager (Farah Khan).
Book them between 14:00 on Day 1 and the end of Day 3, inside working hours, at times the other person is free, and not overlapping each other.
The new hire's calendar is empty before they start. The manager sets these up but does not attend. Invite the new hire and the other person.
Buddy
HR names an onboarding buddy in the welcome email; send the buddy the intro schedule.
```
For Ananya, Day 1 = Mon 12 Oct, Day 2 = Tue 13, Day 3 = Wed 14, Day 5 = Fri 16.

**Service Mesh PRD** (owner Meera Pillai)
```
Service Mesh PRD
Owner: Meera Pillai · Reviewer: Farah Khan · Status: in review
Problem
Service-to-service traffic has no uniform mTLS or retries.
Proposal
Adopt a sidecar-based mesh, rolled out through a canary stage.
Success metrics
p95 latency within 5% of today; zero Sev1 incidents during rollout.
Open questions
Who owns certificate rotation?
```
No comments at seed time. "Service Mesh PRD v0 (archived)" has similar headings and a "Scope" section.

---

## 6. Sheets

Well under 25 spreadsheets, so one `list_spreadsheets` call shows them all. Amounts are stored as numbers. Amount columns use the display format `₹#,##0`, which the tools show as `₹184,500` (`tool_reference` §6). Dates are real date cells, shown `dd/mm/yyyy`.

| Title | Tabs | Used by |
|---|---|---|
| Platform Budget 2026 | Line Items, Monthly Budget, Summary | sh_01, sh_02, sh_04, x_04 |
| Platform Budget 2025 | Line Items, Summary | distractor |
| Offsite RSVPs | Responses | sh_03, amb_03, imp_03 |
| Hiring Pipeline | Candidates | sh_05, x_05 |
| On-call Rotation Q4 | Rotation | x_01, x_09 |
| On-call Rotation Q3 | Rotation | distractor |
| Team Directory | People | people lookup (em_01, em_06, ...) |
| Vendor Contacts | Contacts | filler |

**Platform Budget 2026 → Line Items** (A Vendor, B Category, C Month, D Amount, E Status)

| Row | Vendor | Category | Month | Amount | Status |
|---|---|---|---|---|---|
| 2 | CloudNest | Infra | Jul | 168000 | Approved |
| 3 | Observa | Observability | Jul | 52000 | Approved |
| 4 | Figma | Tooling | Jul | 18500 | Approved |
| 5 | GitHub | Tooling | Jul | 42000 | Approved |
| 6 | TravelDesk | Travel | Jul | 23400 | Rejected |
| 7 | CloudNest | Infra | Aug | 170000 | Approved |
| 8 | Observa | Observability | Aug | 52000 | Approved |
| 9 | Figma | Tooling | Aug | 18500 | Approved |
| 10 | GitHub | Tooling | Aug | 42000 | Pending |
| 11 | TravelDesk | Travel | Aug | 61250 | Approved |
| 12 | CloudNest | Infra | Sep | 184500 | Pending |
| 13 | Observa | Observability | Sep | 58750 | Approved |
| 14 | Figma | Tooling | Sep | 18500 | Approved |
| 15 | GitHub | Tooling | Sep | 42000 | Pending |
| 16 | TravelDesk | Travel | Sep | 12800 | Approved |
| 17 | Observa | Observability | Sep | 9800 | Rejected |

Conditional rules on Line Items. Used by sh_02.

| Index | Rule | Format | Range |
|---|---|---|---|
| [0] | NUMBER_GREATER 100000 | bg #F4CCCC | D2:D17 |
| [1] | NUMBER_GREATER 25000 | bg #FCE8B2 | D2:D17 |
| [2] | CUSTOM_FORMULA `=$E2="Rejected"` | text #999999 | A2:E17 |

**Monthly Budget** (A Vendor, B Category, C Monthly budget): CloudNest Infra **160000**; Observa Observability 55000; Figma Tooling 18500; GitHub Tooling 42000; TravelDesk Travel 30000.

**Summary** (A Category, B Approved total, C Q3 budget cap): Infra / (blank) / 510000; Observability / (blank) / 165000; Tooling / (blank) / 150000; Travel / (blank) / 90000.

**Derived answers:**

| Task | Answer |
|---|---|
| sh_01: Approved totals | Infra 338000 · Observability 162750 · Tooling 97500 · Travel 74050 |
| sh_04: per-category totals, all statuses | Infra 522500 · Observability 172550 · Tooling 181500 · Travel 97450 |
| x_04: revised invoice vs budget | 184500 − 160000 = 24500, **15.31 %** over. The superseded 192400 would give 20.25 % |

**Offsite RSVPs → Responses** (A Timestamp, B Name, C Email, D Attending, E Dietary, F Travelling from)

| Row | Timestamp | Name | Email | Attending | Dietary | From |
|---|---|---|---|---|---|---|
| 2 | 25/09/2026 10:12 | Meera Pillai | meera.pillai@kestrel.test | Yes | Vegetarian | Bengaluru |
| 3 | 25/09/2026 10:40 | Karthik Subramanian | karthik.s@kestrel.test | Y | Non-vegetarian | Chennai |
| 4 | 25/09/2026 11:05 | Neha Gupta | neha.gupta@kestrel.test | yes | Vegetarian | Pune |
| 5 | 25/09/2026 12:30 | Arjun Mehta | arjun.mehta@kestrel.test | TRUE | Non-vegetarian | Bengaluru |
| 6 | 25/09/2026 14:02 | Vikram Rao | vikram.rao@kestrel.test | No | | Bengaluru |
| 7 | 25/09/2026 15:20 | Priya Raman | priya.raman@kestrel.test | Yes | Vegan | Bengaluru |
| 8 | 26/09/2026 09:15 | Farah Khan | farah.khan@kestrel.test | yes | Jain | Mumbai |
| 9 | 26/09/2026 10:00 | Rahul Verma | rahul.verma@kestrel.test | Yes | Non-vegetarian | Bengaluru |
| 10 | 26/09/2026 11:45 | Rohan Kapoor | rohan.kapoor@kestrel.test | N | Non-vegetarian | Delhi |
| 11 | 26/09/2026 16:30 | Deepak Joshi | deepak.joshi@kestrel.test | FALSE | | Bengaluru |
| 12 | 27/09/2026 08:50 | Isha Bhatt | isha.bhatt@kestrel.test | Yes | Vegetarian | Bengaluru |
| 13 | 28/09/2026 09:05 | Samantha Lee | samantha.lee@kestrel.test | yes | | Bengaluru |
| 14 | 29/09/2026 10:20 | Vikram Rao | Vikram.Rao@kestrel.test | yes | Non-vegetarian | Bengaluru |
| 15 | 29/09/2026 13:10 | Meera Pillai | meera.pillai@kestrel.test | Yes | Vegan | Bengaluru |
| 16 | 30/09/2026 18:45 | Rohan Kapoor | rohan.kapoor@kestrel.test | y | Non-vegetarian | Delhi |
| 17 | 01/10/2026 09:30 | Priya Nair | priya.nair@kestrel.test | No | | Bengaluru |
| 18 | 02/10/2026 11:00 | Karthik Subramanian | KARTHIK.S@kestrel.test | no | Non-vegetarian | Chennai |

**Latest answer per person** (sh_03), 13 people:
- **Attending (10):** Meera (Vegan), Neha (Vegetarian), Arjun (Non-vegetarian), Vikram (Non-vegetarian), Priya Raman (Vegan), Farah (Jain), Rahul (Non-vegetarian), Rohan (Non-vegetarian), Isha (Vegetarian), Samantha (blank → None).
- **Not attending (3):** Karthik, Deepak, Priya Nair.
- **Headcount by diet:** Non-vegetarian 4 · Vegetarian 2 · Vegan 2 · Jain 1 · None 1.

**Hiring Pipeline → Candidates** (A Candidate, B Role, C Stage, D Interviewer, E Next step, F Next step date)

| Candidate | Role | Stage | Interviewer | Next step | Date |
|---|---|---|---|---|---|
| Divya Menon | Frontend Engineer | Onsite scheduled | | Onsite interview | 29/09/2026 |
| Karan Shah | SRE | Offer | Meera Pillai | Offer call | 09/10/2026 |
| Lakshmi Iyer | Backend Engineer | Phone screen done | Karthik Subramanian | Onsite interview | 01/10/2026 |
| Rakesh Pillai | Backend Engineer | Onsite scheduled | | Onsite interview | 05/10/2026 |
| Rakesh Pillay | Data Engineer | Phone screen | Neha Gupta | Phone screen | 12/10/2026 |
| Arvind Rao | SRE | Rejected | Neha Gupta | — | |
| Meghna Das | Frontend Engineer | Applied | | Resume review | 14/10/2026 |
| Sanjay Kulkarni | Senior SRE | Onsite done | Neha Gupta | Debrief | 12/10/2026 |

Comments on Hiring Pipeline:

| id | Author | Status | Content | Used by |
|---|---|---|---|---|
| s1 | Samantha Lee | open | Please move Divya Menon to "Offer" and mark Rakesh Pillai as "Rejected". Thanks! | sh_05 |
| s2 | Priya Raman | open | Can we add a design interviewer to the frontend loop? | sh_05 (leave) |
| s3 | Samantha Lee | resolved (reply from Yadeesh T: "Done") | Please use dd/mm/yyyy for dates. | sh_05 (leave) |

**On-call Rotation Q4 → Rotation** (A Week starting, B Primary, C Secondary)

| Week starting | Primary | Secondary |
|---|---|---|
| 05/10/2026 | Karthik Subramanian | Vikram Rao |
| 12/10/2026 | Meera Pillai | Neha Gupta |
| 19/10/2026 | Neha Gupta | Karthik Subramanian |
| 26/10/2026 | Arjun Mehta | Meera Pillai |
| 02/11/2026 | Vikram Rao | Arjun Mehta |
| 09/11/2026 | Karthik Subramanian | Neha Gupta |
| 16/11/2026 | Meera Pillai | Vikram Rao |
| 23/11/2026 | Neha Gupta | Arjun Mehta |
| 30/11/2026 | Arjun Mehta | Karthik Subramanian |
| 07/12/2026 | Vikram Rao | Meera Pillai |
| 14/12/2026 | Karthik Subramanian | Neha Gupta |
| 21/12/2026 | Meera Pillai | Arjun Mehta |
| 28/12/2026 | Neha Gupta | Vikram Rao |

**Team Directory → People:** columns Name, Email, Team, Role, Manager, Location. One row per internal person in §2 **except Ananya Das**.

---

## 7. Google Tasks

**Work.** Used by tsk_01, tsk_02, x_03, x_08. 18 tasks, under the default page of 20.

| id | Title | Due | Status | Notes |
|---|---|---|---|---|
| w1 | Send Q4 capacity model to Rahul | 9 Oct | open | `Context: agreed in the 28 Sep sync that the platform team owns the Q4 capacity model for next quarter. Update 2 Oct: DONE, Meera already sent the final numbers to Rahul.` (the word DONE sits after character 100) |
| w2 | Book offsite venue | | open | `Done - Isha confirmed Le Pondy on 30 Sep.` |
| w3 | Review Service Mesh PRD | 8 Oct | open | `Wait for Farah's feedback first.` |
| w4 | Renew CloudNest contract | 30 Oct | open | `Waiting on the revised quote. Not done yet - don't close.` |
| w5 | Prepare hiring debrief | 12 Oct | open | |
| w5b | Prepare hiring debrief | 14 Oct | open | |
| w6 | Update on-call runbook | 16 Oct | open | |
| w6b | Update on-call runbook | 9 Oct | open | |
| w7 | Approve expense reports | | open | |
| w10 | Prepare hiring debrief slides | 12 Oct | open | |
| q1 | Q4 hiring plan draft | | open | |
| q2 | Q4 OKR draft | 2 Oct | open | |
| q3 | Draft Q4 budget asks | | open | |
| q4 | Q4 roadmap comments for Farah | | completed 1 Oct 18:00 | |
| q5 | Q4 on-call schedule | | open | |
| c1 | File September timesheet | | completed 2 Oct 17:00 | |
| c2 | Review PR #881 | | completed 5 Oct 16:20 | |
| c3 | Send interview feedback for Karan Shah | | completed 6 Oct 11:05 | |

- **Personal** (tsk_02 distractor): "Q4 tax planning" (open, no due), "Renew passport" (due 20 Nov), "Book dentist appointment" (open).
- **Offsite Prep** (filler): "Confirm headcount with Isha", "Share travel plan", "Pack laptop charger".

---

## 8. Drive

No PDFs or other files at seed time besides the docs and sheets above.

---

## 9. Per-task seed additions

| Task | Adds | Why not in the base |
|---|---|---|
| amb_03 | Email `pn_dinner`, 6 Oct 16:05, Priya Nair → Yadeesh (cc Rahul), "Re: Offsite dinner: let's do Villa Shanti": `Villa Shanti is over our per-head budget (₹2,500). Can we switch to Le Café instead? Rahul, please confirm.` Rahul has not replied. | an open disagreement that exists only to make the restaurant ambiguous |
| imp_03 | Email `rh_moved`, 6 Oct 20:15, Rahul → Yadeesh, "Offsite moved to 22–23 Oct": `Heads-up: Le Pondy double-booked us, so the offsite moves to 22–23 Oct at Mango Grove, Mahabalipuram. I'll update the agenda doc tomorrow.` | contradicts the agenda doc, the calendar and Isha's email |

---

## 10. IDs and formats

Generated deterministically from each item's id above, in the shapes the real tools return (`tool_reference`):

| Object | ID shape |
|---|---|
| Gmail message / thread | 16 hex chars |
| User label | `Label_<n>` |
| Filter | 40-char base64url |
| Draft | `r<digits>` |
| Calendar event | 26 lowercase base32hex chars; recurring instances `<series>_<yyyymmdd>` |
| Doc / sheet | 44 chars |
| Task list / task | 22-char base64url |
| Comment / reply | `AAAB` + 7 chars |
| Sheet tab | numeric `sheetId` |

Email `Date` headers use the sender's offset (`+0530` internal, `+0100` Samuel, `+0000` CloudNest).
