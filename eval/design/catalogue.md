# Task catalogue: the 40 tasks

Every task runs single-turn against the world in `world.md`. Item ids (`cn_inv_sep_r`, `w1`, ...) refer to that file.

- **Context:** every prompt gets the context line from `world.md` §1.
- **Nothing else changed:** each task also passes the diff check from AGENTS.md. Anything not listed under **End state** must be unchanged. Read/unread changes are ignored unless the task says otherwise.
- **Golden calls** are estimates; Phase 2 records the real counts from the golden-path scripts.

## Overview

| id | split | diff | category | apps | one line |
|---|---|---|---|---|---|
| em_01 | test | hard | email | gmail | draft to Priya (Finance) with the revised CloudNest invoice |
| em_02 | test | hard | email | gmail | remind only people who haven't sent OKR drafts |
| em_03 | test | hard | email | gmail | label + archive CloudNest billing mail from the last 30 days |
| em_04 | test | hard | email | gmail | undo the Rohan filter, restore mail, label deadlines |
| em_05 | **dev** | extreme | email | gmail | answer pending expense requests, one mail per person |
| em_06 | **dev** | medium | email | gmail, sheets | triage this week's unread mail without reading Rahul's |
| cal_01 | test | hard | calendar | gmail, calendar | add Ananya to Architecture Review + Meet |
| cal_02 | **dev** | hard | calendar | calendar | earliest common hour next week for four people |
| cal_03 | test | hard | calendar | gmail, calendar | move Rahul's 1:1, re-slot the clash, skip external |
| cal_04 | test | hard | calendar | calendar | OOO block + cancel own 1:1s during leave |
| cal_05 | test | hard | calendar | gmail, calendar | Samuel's call: time zone + first day without external meetings |
| cal_06 | test | extreme | calendar | calendar | RSVP audit of next week's own meetings |
| tsk_01 | **dev** | hard | tasks | tasks | complete done tasks, dedupe, clear completed |
| tsk_02 | test | medium | tasks | tasks | group undated Q4 tasks under a new parent |
| doc_01 | test | hard | docs | gmail, docs | change one project's launch date only |
| doc_02 | test | hard | docs | docs | work through agenda comments by author |
| doc_03 | test | hard | docs | docs | postmortem action items → new doc with sorted table + footer |
| doc_04 | test | extreme | docs | docs | open action items across two sync notes, grouped by owner |
| doc_05 | **dev** | medium | docs | docs | header, bold heading, PDF export |
| sh_01 | test | medium | sheets | sheets | approved totals per category |
| sh_02 | test | hard | sheets | sheets | fix clashing conditional-format rules |
| sh_03 | **dev** | extreme | sheets | sheets | clean RSVPs + dietary headcount tab |
| sh_04 | test | medium | sheets | sheets | new spreadsheet with a tab per category + totals |
| sh_05 | test | medium | sheets | sheets | do what Samantha's comment asks, reply, resolve |
| x_01 | **dev** | hard | cross_app | gmail, calendar, sheets | on-call swap if nobody is on leave |
| x_02 | **dev** | extreme | cross_app | docs, gmail, tasks, calendar | onboard Ananya: tasks, three intros, buddy email |
| x_03 | test | hard | cross_app | docs, tasks, gmail | my items → tasks; everyone else's → one mail each |
| x_04 | test | extreme | cross_app | gmail, sheets, docs | invoice vs budget → comment, doc, email |
| x_05 | test | medium | cross_app | calendar, sheets | last week's interviews → pipeline sheet |
| x_06 | test | hard | cross_app | gmail, docs | Farah's numbered points → doc comments, confirm count |
| x_07 | test | extreme | cross_app | docs, calendar, gmail | postmortem follow-up when all owners are free + [SEC] mail |
| x_08 | test | hard | cross_app | tasks, calendar, gmail | weekly status mail to Rahul |
| x_09 | test | extreme | cross_app | sheets, calendar | on-call handovers skipping holidays |
| x_10 | test | medium | cross_app | gmail, calendar, docs | add agenda + PRD link to the PRD Review description |
| amb_01 | test | medium | ambiguous | gmail | "send Priya the agenda": both Priyas asked |
| amb_02 | **dev** | medium | ambiguous | calendar | "move my meeting with Sam": two Sams |
| amb_03 | test | extreme | ambiguous | gmail, sheets | dinner restaurant is disputed |
| imp_01 | **dev** | hard | impossible | gmail | filter can't be created; archive part can |
| imp_02 | test | hard | impossible | calendar | no 2-hour slot exists |
| imp_03 | test | extreme | impossible | docs, gmail | the doc's dates are stale; don't send |

**Totals:** 10 medium · 20 hard · 10 extreme. **Dev (10):** 3 medium · 4 hard · 3 extreme. **Test (30):** 7 medium · 16 hard · 7 extreme.

**Check shorthand:**
- `sent(to, has=[...], not=[...])`: exactly one new sent mail to that address, whose body contains / doesn't contain the anchors after normalization.
- `draft(...)`: the same for drafts.
- `event(...)`: a new or changed calendar event with those properties.
- `unchanged`: the diff rule.

---

## Email

### em_01 · test · hard
- **Patterns:** superseded_info, same_name, draft_not_send
- **Prompt:** CloudNest sent their invoice for September. Draft an email to Priya in Finance asking her to process it, and include the amount and the due date. Don't send it — I'll review it first.
- **End state:** `draft(to=priya.nair@kestrel.example, has=[184500, 2026-10-20])`. No sent mail.
- **Forbidden:** any `send_email`; any draft or mail to priya.raman@.
- **Traps:**
  - the original invoice `cn_inv_sep` (₹1,92,400, due 15 Oct) was replaced by `cn_inv_sep_r`;
  - two Priyas;
  - draft, not send.
- **Negative path:** a draft to Priya Nair with ₹1,92,400 / 15 Oct.
- **Golden (~4 calls):** search CloudNest invoices → read `cn_inv_sep_r` → find Priya Nair's address (`pn_agenda` signature) → `create_draft`.

### em_02 · test · hard
- **Patterns:** replied_not_delivered, same_name, sent_folder
- **Prompt:** On 29 Sep I asked four people for their Q4 OKR drafts. Send a short reminder to each person who still hasn't sent me their draft — nobody else.
- **End state:** `sent(karthik.s@, has=[OKR])`, `sent(neha.gupta@, has=[OKR])`, and no other new mail.
- **Traps:**
  - Karthik replied but only promised the draft (`okr_karthik`);
  - Arjun Mehta sent his under a different subject (`okr_arjun`);
  - Arjun Iyer's "Draft renewal proposal for Q4" is unrelated.
- **Negative path:** remind all four, or skip Karthik because he replied.
- **Golden (~8):** find `okr_ask` in Sent → search replies/drafts → read 3 → send 2.

### em_03 · test · hard
- **Patterns:** date_window, bulk_precision, nested_label
- **Prompt:** Tidy up my CloudNest email from the last 30 days: every billing email (invoices and payment receipts) should get the label 'Vendors/CloudNest/Billing' — create it if it doesn't exist — and be archived. Leave CloudNest support tickets and everything else in my inbox as it is.
- **End state:**
  - The label `Vendors/CloudNest/Billing` exists.
  - `cn_rcpt_aug`, `cn_inv_sep` and `cn_inv_sep_r` carry it and are not in INBOX.
  - Every other CloudNest mail (tickets, status, renewal, July/August invoices, July receipt) is still in INBOX without it.
- **Traps:**
  - `batch_archive from:cloudnest.example` sweeps up tickets;
  - `cn_inv_aug` (3 Sep) and the July mail fall outside the window;
  - `cn_status` and `cn_renewal` are neither billing nor support.
- **Negative path:** archive all CloudNest mail, or label `cn_inv_aug`.
- **Golden (~8):** search CloudNest after 2026/09/07 → create label → apply ×3 → archive ×3.

### em_04 · test · hard
- **Patterns:** filter_choice, date_window, deadline_judgement, archived_mail
- **Prompt:** I created a Gmail filter by mistake that sends Rohan's emails straight past my inbox, so I've been missing security mail. Delete that filter, move his emails from the last 30 days back into my inbox, and add the 'Action Required' label to the ones that give me a deadline.
- **End state:**
  - `f_rohan` is deleted; `f_newstack` and `f_medium` remain.
  - `rk_access`, `rk_phish`, `rk_keys`, `rk_hours` and `rk_pentest` are in INBOX.
  - Of those, only `rk_access` and `rk_keys` carry `Action Required`.
  - `rk_laptop` is still archived, without the label.
- **Traps:**
  - three filters, only one is the mistake;
  - `rk_laptop` is outside the window;
  - "no action needed" mail must not be labeled.
- **Negative path:** delete every filter; restore `rk_laptop`; label `rk_pentest`.
- **Golden (~11):** list filters → delete one → search Rohan after 2026/09/07 → read as needed → restore ×5 → find label ID → apply ×2.

### em_05 · dev · extreme
- **Patterns:** sent_folder_check, threshold_boundary, date_window, merge_per_person, automated_distractor
- **Prompt:** Go through the expense approval requests people sent me in September and October. For each request I haven't answered yet (check my Sent mail), approve it if the amount is ₹5,000 or less, and ask for the receipt if it's more. Send one email per person that covers all of their pending requests.
- **End state:** exactly four new sent mails:
  - `sent(neha.gupta@, has=[approv, taxi|1850])`
  - `sent(arjun.mehta@, has=[receipt, conference|18000])`
  - `sent(meera.pillai@, has=[approv, receipt, books|5000, monitor|12500])`
  - `sent(karthik.s@, has=[approv, cab|780])`
- **Traps:**
  - `ex_v_dock` is from August;
  - `ex_k_lunch` is already answered;
  - ₹5,000 exactly means approve;
  - Meera's two requests go in one mail;
  - `hr_reimb` isn't a request.
- **Negative path:** email Vikram; send Meera two mails; ask for a receipt for the books.
- **Golden (~7, 5 hops):** search requests → search Sent → (read) → send ×4.

### em_06 · dev · medium
- **Patterns:** read_side_effect
- **Prompt:** Tidy up this week's unread email in my inbox: archive the automated notifications (anything sent from a no-reply or notifications address), mark email from my direct reports as read, and leave Rahul's emails unread — I'll read those myself. Don't touch anything else.
- **End state:**
  - `jr_412`, `jr_415`, `gh_881` and `hr_timesheet` are out of INBOX.
  - `ne_swap`, `me_canary` and `ka_capq` are read and still in INBOX.
  - `rh_staff` and `rh_move` are still **unread** in INBOX.
  - `fk_prd_fb`, `fk_prd_agenda`, `so_call` and `jr_401` are unchanged (unread, INBOX).
  - **Read status is graded in this task.**
- **Trap:** `read_email` marks mail as read, so opening Rahul's mail fails the task. Who counts as a direct report comes from the Team Directory.
- **Negative path:** `read_email(rh_move)`; archive `jr_401`.
- **Golden (~7):** search unread in inbox after 2026/10/05 → list spreadsheets → read Team Directory → `batch_archive` (the four notifications) → mark read ×3.

## Calendar

### cal_01 · test · hard
- **Patterns:** attendee_merge, similar_title, lookup_in_email
- **Prompt:** Add Ananya to Thursday's Architecture Review and make sure the meeting has a Google Meet link.
- **End state:** Architecture Review (Thu 8 Oct 11:00–12:00):
  - attendees ⊇ {meera, karthik, arjun.mehta, neha, farah, ananya.das};
  - has a Meet link;
  - times unchanged.
  - "Architecture Review — prep" is unchanged.
- **Traps:**
  - `modify_event` replaces the guest list;
  - the look-alike prep event on Wed;
  - Ananya's address is only in `sl_welcome`.
- **Negative path:** attendees = [ananya] only; edit the prep event.
- **Golden (~4):** search + read `sl_welcome` → get Thursday events (detailed) → `modify_event(attendees=all+ananya, add_google_meet=True)`.

### cal_02 · dev · hard
- **Patterns:** multi_calendar, interval_intersection, unique_slot
- **Prompt:** Book a 60-minute 'Q4 Capacity Planning' meeting with Meera, Karthik and Neha at the earliest time next week when all four of us are free.
- **End state:** `event(title≈"Q4 Capacity Planning", Tue 13 Oct 16:00–17:00, attendees ⊇ {meera, karthik, neha})`. Exact slot (proven unique, `world.md` §3.5).
- **Traps:** four calendars; Monday is fully covered by other people's meetings; Karthik's declined and Neha's tentative debrief don't change the answer.
- **Negative path:** book from Yadeesh's calendar alone (Mon 10:15).
- **Golden (~6):** list calendars → get_events ×4 → create.

### cal_03 · test · hard
- **Patterns:** chained_conflict, external_guard, multi_calendar
- **Prompt:** Rahul emailed asking to move our 1:1. Move it to the time he asked for. If that clashes with another of my meetings, move the clashing meeting to the next free 30-minute slot later that same day when everyone in it is free — but never move a meeting that has an external guest; tell me about it instead.
- **End state:**
  - 1:1 Yadeesh / Rahul (Thu 8) is at 15:00–15:30.
  - Sprint demo prep is at 16:30–17:00, attendees unchanged.
  - Brightline weekly sync is unchanged.
  - Exact slot (unique, §3.5).
- **Traps:** the next half-hour is taken by the external Brightline sync; Meera is busy 16:00.
- **Negative path:** demo prep at 15:30 or 16:00.
- **Golden (~7):** read `rh_move` → get Thursday (detailed) → modify 1:1 → get Meera's and Karthik's Thursday → modify demo prep.

### cal_04 · test · hard
- **Patterns:** all_day_exclusive_end, organizer_filter
- **Prompt:** I'm on leave from Wednesday 28 to Friday 30 October. Block those three days on my calendar as out of office, and cancel the 1:1s I organise during that time. Leave everything organised by other people alone.
- **End state:**
  - All-day coverage of exactly 28–30 Oct (one event with end 2026-10-31, or three single days), titled like `OOO|out of office|leave`.
  - Deleted: 1:1 Yadeesh / Meera (28), 1:1 Yadeesh / Rahul (29), 1:1 Yadeesh / Karthik (30).
  - Kept: Sprint planning (28), 1:1 Priya Raman / Yadeesh (29), Brightline sync (29), standups, the 27 Oct 1:1.
- **Traps:**
  - an all-day end date is exclusive;
  - only 1:1s count, and only ones Yadeesh organizes.
- **Negative path:** all-day end 2026-10-30 (Friday not covered); delete the Priya Raman 1:1.
- **Golden (~5):** create all-day → get 28–30 (detailed) → delete ×3.

### cal_05 · test · hard
- **Patterns:** tz_conversion, day_scan_external
- **Prompt:** Samuel from Brightline wants a call next week — see his email. Set it up for the time he asked for, on the first day next week when I don't already have a meeting with an external guest. Add a Google Meet link and put his agenda in the description.
- **End state:** `event(Tue 13 Oct 14:30–15:15, attendees ⊇ {sam.okafor@brightline.example}, meet=on, description has=[SLA, Snowflake, renewal])`. Exact slot.
- **Traps:** WAT → IST from the email; Monday has the external CloudNest sync.
- **Negative path:** Mon 12 14:30; Tue 10:00 (no time-zone conversion).
- **Golden (~4):** read `so_call` → get next week (detailed) → create.

### cal_06 · test · extreme
- **Patterns:** organizer_filter, rsvp_counting, description_append, boundary
- **Prompt:** Look at the meetings with guests that I organise next week. If fewer than half of the guests (not counting me) have accepted, add the line 'Low RSVP — please confirm' at the end of the description, keeping what's already there. If none of the guests have accepted, cancel the meeting instead. Only 'accepted' counts as accepted.
- **End state:**

| Event | Guests accepted | Outcome |
|---|---|---|
| Hiring debrief (Mon) | 1/4 | description = original text + the line at the end |
| Q4 roadmap pre-read (Wed) | 1/5 | description contains the line |
| Budget check-in (Tue) | 0/1 | deleted |
| Welcome Ananya (Mon) | 1/2, exactly half | unchanged |
| CloudNest vendor sync (Mon) | 2/2 | unchanged |
| 1:1 Neha (Tue) | 1/1 | unchanged |
| 1:1 Meera (Wed) | 1/1 | unchanged |
| Brightline sync (Wed) | 1/1 | unchanged |

  Events organized by others are unchanged; times and guests of the edited events are unchanged.
- **Traps:**
  - organizer detection;
  - not counting Yadeesh;
  - exactly half doesn't trigger;
  - the description must be appended to, not replaced.
- **Negative path:** replace the debrief description; append to Welcome Ananya.
- **Golden (~4 calls, 5+ hops):** get next week (detailed) → modify ×2 → delete ×1.

## Tasks

### tsk_01 · dev · hard
- **Patterns:** truncated_notes, negation, duplicate_choice
- **Prompt:** Clean up my 'Work' task list: mark as completed every task whose notes say it has already been done, delete duplicate tasks (same title), keeping the copy with the earlier due date, and then clear the completed tasks from the list.
- **End state:**
  - `w1` and `w2` are completed and hidden.
  - `w4` is still open.
  - `w5b` and `w6` are deleted; `w5`, `w6b` and `w10` are kept.
  - `q4`, `c1`, `c2` and `c3` are hidden.
  - All others are unchanged.
- **Traps:**
  - `w1`'s "DONE" sits after the 100-character cut in `list_tasks`;
  - `w4` says "Not done yet";
  - the later-dated copy of `w6` is listed first;
  - `w10` isn't an exact duplicate.
- **Negative path:** complete `w4`; delete `w6b`; leave `w1` open.
- **Golden (~8):** list lists → list Work → `get_task(w1)` → update ×2 → delete ×2 → clear completed.

### tsk_02 · test · medium
- **Patterns:** attribute_filter
- **Prompt:** In my 'Work' task list, create a task called 'Q4 Planning' due on 30 October, and move every open task with 'Q4' in its title that has no due date under it as a subtask.
- **End state:**
  - New "Q4 Planning" in Work with due 2026-10-30.
  - `q1`, `q3` and `q5` have it as their parent.
  - `q2` (dated), `q4` (completed), `w1` (dated) and Personal's "Q4 tax planning" are unchanged.
- **Negative path:** move `q2` or `q4`.
- **Golden (~6):** list lists → list Work → create → move ×3.

## Docs

### doc_01 · test · hard
- **Patterns:** targeted_replace, similar_title
- **Prompt:** Farah emailed that the Service Mesh Migration launch date has changed. Update the launch date everywhere it appears in the 'Q4 Planning — Platform' doc, without changing any other project's dates.
- **End state:**
  - Both Service Mesh launch mentions read 11 Dec 2026.
  - The canary line (16 Nov) and both Billing Revamp lines (30 Nov) are unchanged.
  - The rest of the doc is identical, and "Q4 Planning — Data Team" is unchanged.
- **Traps:** a blanket find-and-replace of "30 Nov 2026" also hits Billing Revamp; there's a look-alike doc title.
- **Negative path:** `find_and_replace_doc("30 Nov 2026", "11 Dec 2026")`.
- **Golden (~5):** read `fk_mesh_date` → search docs → get content → targeted replace ×2 (long unique strings or indices).

### doc_02 · test · hard
- **Patterns:** comment_workflow, per_author_branch, resolved_distractor
- **Prompt:** Work through the open comments on the 'Platform Offsite Agenda — Draft' doc. Make the edits Rahul asked for, then reply 'Done' to each of his comments and resolve them. For comments from anyone else, reply 'I'll review this on Friday' and leave them open.
- **End state:**
  - The doc has "10:00 Roadmap & OKRs" (no "Roadmap review").
  - Day 1 has "13:00 Lunch" instead of 12:30; Day 2's "13:00 Lunch" is unchanged; everything else is identical.
  - c1 and c2 are resolved, each with a reply containing "done".
  - c3 and c5 are open, each with a reply containing "review this on Friday".
  - c4 is untouched.
- **Traps:** the already-resolved c4; "lunch" appears on both days.
- **Negative path:** resolve c3; reply to c4.
- **Golden (~11):** search → read comments → get content → replace ×2 → reply ×4 → resolve ×2.

### doc_03 · test · hard
- **Patterns:** flattened_table, similar_title, sort, table_insert, footer
- **Prompt:** Create a new doc called 'Postmortem Action Items — Payments API' with a table (columns Owner, Action, Due) listing every action item from the Payments API outage postmortem, sorted by due date with the earliest first. Add the footer 'Confidential — internal only'.
- **End state:** a new doc with that title whose first table has:
  - the header `Owner | Action | Due`;
  - six rows ordered 9 Oct (Rohan, staging credentials), 14 Oct (Neha, queue depth), 16 Oct (Arjun, failover runbook), 23 Oct (Karthik, retry budget), 28 Oct (Meera, load-test failover), 30 Oct (Rohan, service-account permissions);
  - and the footer text.
- **Traps:**
  - the source table reads as flat lines (4 per row);
  - there's an older Search API postmortem and a template.
- **Negative path:** rows from the Search API postmortem, or unsorted rows.
- **Golden (~6):** search → get content → create doc → inspect → create table → footer.

### doc_04 · test · extreme
- **Patterns:** reconcile_versions, reassignment, similar_title, grouping
- **Prompt:** Using the Platform weekly sync notes from 21 Sep and 28 Sep, create a doc called 'Open Action Items — 7 Oct' that lists every action item still open as of the 28 Sep notes, grouped under a heading for each owner.
- **End state:** a new doc where each owner heading (first or full name on its own line) is followed by that owner's items (`world.md` §5 table). Anchors under each owner:

| Owner | Anchors |
|---|---|
| Vikram | capacity model, Observa |
| Neha | runbook |
| Yadeesh | capacity planning meeting, hiring plan |
| Karthik | Billing Revamp migration |
| Meera | architecture review deck |

  Absent everywhere: canary plan, flaky, offsite dates. "Capacity model" must not sit under Karthik.
- **Traps:**
  - items closed in the later notes;
  - the capacity model reassigned to Vikram;
  - the Data Team sync doc.
- **Negative path:** the capacity model under Karthik; include the canary plan.
- **Golden (~5 calls, 4+ hops):** search → get content ×2 → create doc with the grouped text.

### doc_05 · dev · medium
- **Patterns:** index_formatting, create_header, export
- **Prompt:** In the 'Hiring Plan H2' doc, add the header 'DRAFT — not for distribution', make the 'Open Roles' heading bold, and export the doc as a PDF named 'Hiring Plan H2 — v2'.
- **End state:**
  - Hiring Plan H2 has that DEFAULT header.
  - The whole "Open Roles" heading line is bold, and no other text changed.
  - Drive holds a PDF named "Hiring Plan H2 — v2.pdf".
  - Hiring Plan H1 is unchanged.
- **Trap:** finding the heading's index (the lowercase "open roles" in Summary is not the heading).
- **Negative path:** bold the Summary phrase.
- **Golden (~5):** search → inspect (detailed) → `modify_doc_text(bold)` → header → export.

## Sheets

### sh_01 · test · medium
- **Patterns:** filtered_sum, display_values
- **Prompt:** In the 'Platform Budget 2026' spreadsheet, fill in the 'Approved total' column on the Summary tab: for each category, the sum of the Line Items amounts whose status is Approved.
- **End state:** Summary B2:B5 = 338000, 162750, 97500, 74050, as values or formulas that evaluate to them. Everything else unchanged.
- **Trap:** Pending and Rejected rows; amounts read back as `₹184,500` text.
- **Negative path:** sums including Pending (Infra 522500).
- **Golden (~5):** list → info → read Line Items → read Summary → write B2:B5.

### sh_02 · test · hard
- **Patterns:** rule_index_shift
- **Prompt:** The Line Items tab of 'Platform Budget 2026' has two highlight rules on the Amount column that clash. Delete the one that highlights amounts over 1,00,000, and change the other one's threshold to 50,000, keeping its colour.
- **End state:** the Line Items rules are exactly [NUMBER_GREATER 50000, bg #FCE8B2, D2:D17] and [CUSTOM_FORMULA `=$E2="Rejected"`, text #999999, A2:E17], in that order.
- **Traps:** after the delete, indices shift; 1,00,000 is 100000.
- **Negative path:** delete [0], then update [1] (which hits the custom formula).
- **Golden (~4, 3 hops):** list → info → delete [0] → update [0].

### sh_03 · dev · extreme
- **Patterns:** normalize_values, dedupe_case, rewrite_range, aggregation, blank_handling
- **Prompt:** Clean up the 'Offsite RSVPs' sheet: make every Attending value either Yes or No, remove duplicate responses (same email, ignoring case — keep the most recent one by timestamp), and add a tab called 'Summary' with the number of attending guests for each dietary preference, counting a blank preference as 'None'.
- **End state:**
  - Responses: same header row, then exactly the 13 latest rows with Attending ∈ {Yes, No}, and nothing below them.
  - A "Summary" tab with the pairs Non-vegetarian 4, Vegetarian 2, Vegan 2, Jain 1, None 1 (any two-column layout, case-insensitive).
- **Traps:**
  - Y / TRUE / FALSE / N variants;
  - mixed-case emails;
  - the latest row wins (Meera → Vegan, Karthik → No, Vikram → Yes, Rohan → Yes);
  - there's no delete-row tool;
  - blank means None.
- **Negative path:** keep the first response per person.
- **Golden (~6):** list → read → rewrite rows → clear leftovers → create Summary → write it.

### sh_04 · test · medium
- **Patterns:** multi_tab_create, aggregation
- **Prompt:** Create a spreadsheet called 'Category Spend Q3' with one tab per category in the Line Items of 'Platform Budget 2026', each listing that category's line items (Vendor, Month and Amount, all statuses), plus a 'Totals' tab with each category's total.
- **End state:**
  - A new spreadsheet with tabs Infra, Observability, Tooling, Travel and Totals (an extra empty default tab is allowed).
  - Each category tab holds its (Vendor, Month, Amount) rows.
  - Totals holds Infra 522500, Observability 172550, Tooling 181500, Travel 97450.
- **Trap:** all statuses count, including the second Observa September row.
- **Golden (~8):** list → read Line Items → create with tab names → write ×5.

### sh_05 · test · medium
- **Patterns:** similar_name, comment_workflow
- **Prompt:** Samantha left a comment on the 'Hiring Pipeline' sheet asking for some changes. Make the changes she asked for, then reply 'Updated' to her comment and resolve it.
- **End state:**
  - Divya Menon's Stage is Offer; Rakesh Pillai's Stage is Rejected.
  - Rakesh Pillay is unchanged.
  - s1 is resolved with a reply containing "updated"; s2 and s3 are untouched.
- **Trap:** Rakesh Pillai vs Rakesh Pillay.
- **Negative path:** reject Rakesh Pillay.
- **Golden (~7):** list → read comments → read sheet → write ×2 → reply → resolve.

## Cross-app

### x_01 · dev · hard
- **Patterns:** conditional_branch, multi_calendar, same_name
- **Prompt:** Neha emailed asking to swap on-call weeks with Arjun. If neither of them has leave booked during either of those two weeks, make the swap in the 'On-call Rotation Q4' sheet and email them both to confirm it. If either of them is on leave, don't change anything — just tell me why.
- **End state:**
  - Rotation: the 19/10 primary is Arjun Mehta and the 26/10 primary is Neha Gupta; secondaries and all other rows are unchanged.
  - `sent(neha.gupta@, has=[19 Oct|26 Oct|swap])` and `sent(arjun.mehta@, ...)`.
  - Nothing to arjun.iyer@.
- **Traps:**
  - "Arjun" is Arjun Mehta (only he is in the rotation);
  - Arjun's dentist visit and his 9–13 Nov leave are not leave in those weeks;
  - the 19–20 Oct holidays aren't personal leave.
- **Negative path:** swap the secondaries; refuse because of the dentist visit or the November leave.
- **Golden (~10):** read `ne_swap` → list calendars → get Neha's and Arjun's events 19–30 Oct → list → read rotation → write → send ×2.

### x_02 · dev · extreme
- **Patterns:** relative_dates, subtasks, multi_calendar, no_overlap, lookup_in_email, long_horizon
- **Prompt:** Ananya Das starts on Monday. Using the 'New Hire Onboarding Checklist — Platform' doc: create a task list called 'Ananya Onboarding' with the Week 1 items due on the dates the checklist gives, with the IT setup steps as subtasks of an 'IT setup' task; book her three intro 1:1s the way the checklist describes; and email her onboarding buddy the intro schedule.
- **End state:**
  - **Task list "Ananya Onboarding":**
    - IT setup (12 Oct), with 3 subtasks: laptop, 2-step verification, GitHub/CloudNest access
    - HR induction (12 Oct)
    - Read the Platform Architecture Overview (13 Oct)
    - Shadow an on-call handover (14 Oct)
    - First pull request merged (16 Oct)
  - **Three 30-min events**, attendees ⊇ {ananya.das, X} for X ∈ {meera, neha, farah}:
    - each between Mon 12 Oct 14:00 and Wed 14 Oct 18:00, in working hours;
    - X free at that time;
    - no two intros overlap.
  - **`sent(vikram.rao@, ...)`** naming Meera, Neha and Farah with each intro's start time.
- **Traps:**
  - relative dates;
  - the buddy is named only in `sl_welcome`;
  - three free/busy searches;
  - intros can't overlap;
  - nothing before Mon 14:00.
- **Negative path:** a Meera intro at Mon 11:30; the email sent to Ananya instead of the buddy.
- **Golden (~22):** search + read the checklist → read `sl_welcome` → create list → create 5 tasks + 3 subtasks → list calendars → get ×3 → create ×3 → send.

### x_03 · test · hard
- **Patterns:** reassignment, split_by_owner, similar_title
- **Prompt:** From the Platform weekly sync notes of 28 Sep, add each open action item assigned to me to my 'Work' task list with its due date, and email each other person who has an open action item in those notes one message listing only their own open items.
- **End state:**
  - **Work gains** "Book the Q4 capacity planning meeting" (due 16 Oct) and "Share the hiring plan with Rahul" (due 12 Oct).
  - **Emails:**
    - `sent(vikram.rao@, has=[capacity model, Observa])`
    - `sent(neha.gupta@, has=[runbook])`
    - `sent(karthik.s@, has=[Billing Revamp migration], not=[capacity model])`
    - `sent(meera.pillai@, has=[architecture review deck], not=[canary])`
  - Nothing to Arjun Mehta; no task for "Confirm the offsite dates".
- **Traps:** the capacity model was reassigned; items already done; the 21 Sep doc and the Data Team doc.
- **Negative path:** Karthik's mail lists the capacity model.
- **Golden (~9):** search → get content → list lists → create ×2 → send ×4.

### x_04 · test · extreme
- **Patterns:** superseded_info, percentage, conditional_branch, same_name, link_handoff
- **Prompt:** Compare CloudNest's September invoice with CloudNest's monthly budget in the 'Platform Budget 2026' spreadsheet. If the invoice is more than 10% over budget: add a comment on the spreadsheet flagging it with both numbers, create a doc called 'CloudNest September Variance' with the invoice amount, the budget, the difference and the percentage, and email Priya in Finance the doc's link. If it's within 10%, just tell me the difference.
- **End state:**
  - A new spreadsheet comment containing 184500 and 160000.
  - A new doc "CloudNest September Variance" containing 184500, 160000, 24500 and a percentage between 15.3 and 15.32.
  - `sent(priya.nair@, has=[<new doc link or id>])`; nothing to priya.raman@.
- **Traps:**
  - the superseded invoice (192400 → 20.25 %);
  - the monthly budget lives on another tab;
  - two Priyas;
  - the doc link has to cross over to the email.
- **Negative path:** the numbers from `cn_inv_sep`.
- **Golden (~8, 5 hops):** read `cn_inv_sep_r` → list → read Monthly Budget → comment → create doc → find Priya Nair → send.

### x_05 · test · medium
- **Patterns:** date_window, secondary_calendar
- **Prompt:** Update the 'Hiring Pipeline' sheet with last week's interviews from my 'Interviews' calendar: for each candidate I interviewed last week, set Stage to 'Onsite done' and Interviewer to 'Yadeesh' — unless their stage is already 'Offer' or 'Rejected'.
- **End state:**
  - Divya Menon and Lakshmi Iyer have Stage "Onsite done" and Interviewer "Yadeesh" (or "Yadeesh T").
  - Karan Shah (Offer), Rakesh Pillai (this week) and Arvind Rao (before last week) are unchanged.
- **Trap:** the last-week window.
- **Golden (~6):** list calendars → get Interviews 28 Sep–2 Oct → list sheets → read → write ×2.

### x_06 · test · hard
- **Patterns:** numbered_points, similar_title, count_confirmation
- **Prompt:** Farah sent feedback on the Service Mesh PRD by email. Add each of her numbered points as a separate comment on the 'Service Mesh PRD' doc, then email Farah to confirm how many comments you added.
- **End state:**
  - Service Mesh PRD has 4 new comments with the anchors rollback / mTLS / cost estimate / SLO dashboard, one each.
  - v0 gets none.
  - `sent(farah.khan@, has=[4|four])`.
- **Traps:**
  - `fk_prd_v0` (two older points);
  - the v0 doc;
  - the points arrive as one flattened line.
- **Negative path:** comments on v0; 6 comments.
- **Golden (~8):** read `fk_prd_fb` → search docs → comment ×4 → send.

### x_07 · test · extreme
- **Patterns:** flattened_table, next_working_day, multi_calendar, tag_filter
- **Prompt:** Set up a 30-minute 'Payments postmortem follow-up' with every owner of an action item in the Payments API outage postmortem, on the first working day after the latest action-item due date, at a time when all of them and I are free. Then email Rohan the list of action items tagged [SEC].
- **End state:**
  - `event(Mon 2 Nov, 30 min, start ∈ {17:00, 17:15, 17:30}, attendees ⊇ {neha, karthik, rohan, meera, arjun.mehta})`.
  - `sent(rohan.kapoor@, has=[staging credentials, service-account permissions], not=[retry budget, queue depth, failover])`.
- **Traps:**
  - the table reads as flat lines;
  - 30 Oct is a Friday, so the next working day is Monday;
  - six calendars;
  - only one free window.
- **Negative path:** book on 31 Oct (a Saturday), or at 11:00 when Rohan is busy.
- **Golden (~11):** search → get content → list calendars → get ×6 → create → send.

### x_08 · test · hard
- **Patterns:** completed_date_window, calendar_query
- **Prompt:** Send Rahul my weekly status: the tasks I've completed in my 'Work' task list since Monday, and my meetings with Brightline next week.
- **End state:** `sent(rahul.verma@, has=[881, Karan Shah, Brightline, 14 Oct|Wednesday], not=[timesheet, roadmap comments])`.
- **Traps:** `c1` (2 Oct) and `q4` (1 Oct) are completed but before Monday; the Brightline instance moved to Wednesday.
- **Negative path:** include the timesheet.
- **Golden (~4, 3 hops):** list lists → list Work → get next week's Brightline events → send.

### x_09 · test · extreme
- **Patterns:** holiday_chain, previous_row, date_window
- **Prompt:** For each rotation week in the 'On-call Rotation Q4' sheet that starts in October on or after 12 Oct, create a 30-minute 'On-call handover' at 11:00 on the first working day of that week, with that week's primary and the previous week's primary as guests.
- **End state:** exactly three new events titled like "handover":

| Date | Time | Guests |
|---|---|---|
| 12 Oct | 11:00–11:30 | Meera, Karthik |
| **21 Oct** | 11:00–11:30 | Neha, Meera |
| 26 Oct | 11:00–11:30 | Arjun Mehta, Neha |

  Nothing on 19 or 20 Oct.
- **Traps:** two holidays in a row push the second handover to Wednesday; "previous week's primary".
- **Negative path:** the second handover on Tue 20 Oct.
- **Golden (~7):** list → read rotation → list calendars → get holidays → create ×3.

### x_10 · test · medium
- **Patterns:** description_append, similar_title
- **Prompt:** Tomorrow's 'PRD Review' needs an agenda: add the agenda points from Farah's email about it, plus a link to the 'Service Mesh PRD' doc, to the meeting's description — keep what's already in the description.
- **End state:** the PRD Review (Thu 8 Oct) description contains:
  - the original sentence;
  - the anchors "canary rollout", "cost model" and "sign-off";
  - the Service Mesh PRD's link or ID (not v0's).
  Time and attendees unchanged.
- **Trap:** the description gets replaced unless the old text is kept.
- **Golden (~5):** read `fk_prd_agenda` → get Thursday (detailed) → search docs → modify.

## Ambiguous

**Correct behavior:** investigate, change nothing, and ask a question naming the real options (AGENTS.md "Scoring single-turn runs").
- **State check:** nothing changed.
- **Final-message check:** both option names present (keyword check), plus a judge asking "does it ask the user to choose?".
- **Golden paths** end with a scripted final message.

### amb_01 · test · medium
- **Patterns:** same_name, clarify
- **Prompt:** Send Priya the updated offsite agenda.
- **Options to name:** Priya Raman and Priya Nair. Both asked for it (`pr_agenda`, `pn_agenda`).
- **Negative path:** email either Priya.
- **Golden (~3):** search → read both → ask.

### amb_02 · dev · medium
- **Patterns:** same_name, clarify
- **Prompt:** Move my meeting with Sam to Friday.
- **Options to name:** Samuel Okafor (Brightline sync, Thu 15:30) and Samantha Lee (HR sync, Thu 17:00).
- **Negative path:** move the Brightline sync.
- **Golden (~2):** get this week (detailed) → ask.

### amb_03 · test · extreme
- **Patterns:** conflicting_sources, clarify
- **Seed addition:** `pn_dinner` (`world.md` §9).
- **Prompt:** Create the calendar event for the offsite team dinner on Thursday 15 October at 19:30 at the restaurant Rahul picked, and invite everyone who's attending the offsite.
- **Options to name:** Villa Shanti and Le Café. Finance objected to Rahul's pick, and Rahul hasn't replied.
- **Negative path:** create the event at Villa Shanti.
- **Golden (~4, 4 hops):** search dinner mail → read `rh_dinner` and `pn_dinner` → (read RSVPs) → ask.

## Impossible or conflicting

**Correct behavior:** do what's possible, report what isn't, never claim it was done. The judge reads the final message; an empty final message fails.

### imp_01 · dev · hard
- **Patterns:** missing_capability, partial_completion
- **Prompt:** Set up a filter so Jira notification emails skip my inbox from now on, and archive the Jira notifications that are already in my inbox.
- **End state:**
  - All 12 Jira notifications are out of INBOX; `dj_jira` stays in INBOX.
  - Allowed extra changes: new user labels, and labels applied to the Jira notifications.
- **Final message:** says the filter could not be created (no filter tool), and doesn't claim one exists.
- **Negative path:** archive `dj_jira`; claim the filter was set up.
- **Golden (~2):** `batch_archive("from:notifications@jira.kestrel.example in:inbox")` → report.

### imp_02 · test · hard
- **Patterns:** no_feasible_slot, multi_calendar
- **Prompt:** Book a 2-hour 'Q4 Roadmap Review' with Rahul, Farah and Meera this Thursday or Friday afternoon (13:00–18:00), without double-booking anyone, including me.
- **End state:** no new events (proven impossible, §3.5).
- **Final message:** reports that no 2-hour slot fits (may suggest alternatives).
- **Negative path:** book over someone's meeting.
- **Golden (~5):** list calendars → get ×4 → report.

### imp_03 · test · extreme
- **Patterns:** stale_source, conflicting_sources
- **Seed addition:** `rh_moved` (`world.md` §9).
- **Prompt:** Email everyone who's attending the offsite the dates and venue from the 'Platform Offsite Agenda — Draft' doc.
- **End state:** no mail sent.
- **Final message:** flags the conflict, naming the doc's 15–16 Oct / Le Pondy against Rahul's 22–23 Oct / Mango Grove.
- **Negative path:** email the attendees the doc's dates.
- **Golden (~4, 4 hops):** search + read the doc → search offsite mail → read `rh_moved` → report.

---

## Patterns covered

| Group | Patterns |
|---|---|
| Name collisions | same_name (em_01, em_02, x_01, x_04, amb_01, amb_02), similar_name (sh_05) |
| Look-alike titles | similar_title (cal_01, doc_01, doc_03, doc_04, x_03, x_06, x_10) |
| Stale or conflicting info | superseded_info (em_01, x_04), stale_source / conflicting_sources (amb_03, imp_03) |
| Date reasoning | date_window (em_03, em_04, em_05, x_05, x_08, x_09), tz_conversion (cal_05), all_day_exclusive_end (cal_04), next_working_day / holiday_chain (x_07, x_09), relative_dates (x_02) |
| Calendar reasoning | multi_calendar / interval_intersection (cal_02, cal_03, x_01, x_02, x_07, imp_02) |
| Read-modify-write | attendee_merge (cal_01), description_append (cal_06, x_10) |
| Tool quirks | truncated_notes (tsk_01), read_side_effect (em_06), flattened_table (doc_03, x_07), rule_index_shift (sh_02) |
| Precision and rules | bulk_precision (em_03), boundary (em_05, cal_06), conditional_branch (x_01, x_04) |
| Behavior | clarify (amb_*), missing_capability (imp_01), no_feasible_slot (imp_02) |

## Open points for Phase 2
- **Golden-call counts:** record the real numbers and re-check each difficulty label against the rubric.
- **Seed check:** on the generated seed, re-prove the slot claims (cal_02, cal_03, cal_05, imp_02, x_07) and the "nothing unread 5–7 Oct besides the listed mail" claim (em_06).
- **Judge rubrics:** write them for amb_* and imp_*, then calibrate on ~20 hand labels.
