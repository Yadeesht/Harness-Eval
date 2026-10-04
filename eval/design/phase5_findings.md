# Phase 5 findings (test set, GPT-6 Luna)

Source: `eval/runs/phase5/records.jsonl` (180 runs, tag `phase5-freeze`). Numbers come from
`eval/harness/report.py` and `eval/harness/analyze.py`. Failure labels and notes are in
`phase5_failure_labels.csv`. Judge calibration is still open (`judge_calibration/`).

## Headline

| | Graph | Hermes |
|---|---|---|
| Runs passed | 79/90 (88%; 95% CI 79–93%) | 80/90 (89%; 95% CI 81–94%) |
| Tasks passed on all 3 runs | 24/30 | 23/30 |
| Input tokens per run | 48.5k | 120k |
| Cost per run / per pass | $0.0019 / $0.0022 | $0.0036 / $0.0041 |
| Wall time per run | 36.6 s | 42.6 s |
| Workspace calls attempted / reached the server | 9.2 / 9.2 | 11.8 / 9.5 |
| Harness overhead calls (routing / tool search) | 3.7 | 3.3 |

- **Success is a statistical tie.** The confidence intervals overlap almost entirely, and the gap is one run.
- **The graph is cheaper on 29 of 30 tasks.** Hermes uses 1.0–4.9x the graph's input tokens per task, for example amb_01 (11k vs 55k), cal_06 (29k vs 144k) and sh_04 (65k vs 272k).
- **The dev lead did not transfer.** The graph led on dev (28/30 vs 18/30) after tuning on those tasks; on the frozen test set it does not lead.
- **One disputed judge verdict.** Graph amb_03 r3 is graded FAIL. The message names both restaurants and the conflict, but its question sentence doesn't; the judge read the rubric literally. As a PASS, the graph would be 80/90.

## Where the runs are lost

| Difficulty | Graph | Hermes | Tasks |
|---|---|---|---|
| medium | 20/21 (95%) | 20/21 (95%) | 7 |
| hard | 46/48 (96%) | 47/48 (98%) | 16 |
| extreme | 13/21 (62%) | 13/21 (62%) | 7 |

Medium and hard tasks are near the ceiling for both harnesses; the extreme tasks decide the result.

| Category | Graph | Hermes |
|---|---|---|
| calendar | 11/15 (73%) | 14/15 (93%) |
| docs | 12/12 | 10/12 (83%) |
| impossible | 3/6 (50%) | 4/6 (67%) |
| ambiguous | 5/6 | 5/6 |
| cross_app | 22/24 | 21/24 |
| email, sheets, tasks | 26/27 | 26/27 |

- **Graph's weak spots:**
  - calendar organizer and holiday rules (cal_04, cal_06, x_09);
  - conflicting sources (imp_03 0/3).
- **Hermes's weak spots:**
  - booking a slot it had seen as busy (x_07 0/3; the `next_working_day`, `tag_filter` and `multi_calendar` rows are low only because they belong to x_07);
  - doc edits that were incomplete or misreported (doc_01, doc_04).
- Most trap patterns cover only one task (3 runs), so pattern rows are examples, not rates.

## Failures by type (final labels)

| Label | Graph | Hermes |
|---|---|---|
| wrong_result | 5 | 6 |
| forced_impossible | 3 | 2 |
| unwanted_change | 2 | 0 |
| wrong_options (disputed) | 1 | 0 |
| didnt_ask | 0 | 1 |
| premature_finish | 0 | 1 |

- **Changes outside the task:**
  - graph: 3 mass sends (imp_03), 2 deletions (cal_04) and 2 events on a holiday (x_09);
  - Hermes: 2 mass sends (imp_03) and 1 event created on an ambiguous request (amb_03).
- **Misreported results (the final message says something that didn't happen):**
  - Hermes doc_01 r3 claimed both dates were updated;
  - Hermes doc_04 r2 claimed completed items were excluded;
  - the graph's cal_06 handoff claimed the event had no description.

## Trace 1: imp_03, a conflict that falls between workers

Request: *"Email everyone who's attending the offsite the dates and venue from the 'Platform Offsite Agenda — Draft' doc."* The doc is stale: Rahul's email moved the offsite to 22–23 Oct at Mango Grove. The right answer is to report the conflict and send nothing.

- **Graph r1 (all 3 runs alike):**
  1. supervisor → `document_agent`: reads the doc (15–16 Oct, Le Pondy) and hands back, since it has no email tools;
  2. → `data_agent`: reads the RSVP sheet and returns 10 attendees;
  3. → `communication_agent` with the doc details and attendees in `context`: sends 10 emails.
  - No worker ever searched mail.
  - Each worker only saw its part. The doc worker can't check email, and the email worker was told what to send, so it had no reason to doubt the doc.
- **Hermes r1 (passed):**
  1. `search_docs`, then `search_emails` second, before reading the doc;
  2. finds Rahul's change and asks: *"the draft doc says 15–16 Oct at Le Pondy … a newer email says 22–23 Oct at Mango Grove … Which dates and venue should I send?"*
  - Hermes runs r2 and r3 also searched mail but still sent; r2 sent the newer details.
- **Lesson:** a routed graph splits the work by app, so a check that needs two apps at once ("is this doc still current?") belongs to no worker unless the supervisor asks for it. The dev fixes taught the workers to look up *missing* information, not to look for *contradicting* information.

## Trace 2: x_07, seeing the clash and booking over it (Hermes)

Request: book a 30-minute follow-up with every action-item owner on the first working day after the latest due date (Mon 2 Nov), when everyone is free. Only 17:00–17:30 fits.

- **Hermes r1:**
  - read your calendar for 2 Nov, which showed "Quarterly planning kickoff";
  - read Neha's, which showed "SLO review";
  - read the other four calendars and the holidays calendar;
  - booked **14:00**, during the kickoff.
  - r2 booked 14:00 again, and r3 booked 11:30 (Neha busy).
  - The final messages of r1 and r3 said the slot was free on the calendars checked.
- **Graph r1:** made the same reads in the planning worker and booked **17:00**; passed 3/3.
- **Lesson:** it had all the information and the overlap check still failed. One possible reason, not tested: Hermes keeps every tool result of the task in one context, while the graph's planning worker sees only calendar results.

## Trace 3: cal_04, a deletion the user didn't ask for (graph)

Request: block 28–30 Oct as out of office, cancel the 1:1s you organise in that time, and leave everything organised by others alone.

- **Graph r1 and r2:**
  - created the out-of-office block correctly;
  - cancelled the three 1:1s (Meera, Rahul, Karthik);
  - also deleted "Brightline weekly sync", a two-person external sync and not a 1:1, then reported it as "the two-person Brightline weekly sync".
- **Graph r3 and all Hermes runs** kept it.
- **Lesson:** "1:1" was read as "two attendees". This is the kind of unrequested destructive change the guardrails care about most, and on test it came only from the graph.
