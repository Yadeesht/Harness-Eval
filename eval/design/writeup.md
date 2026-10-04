# Routed LangGraph harness vs Hermes on a current cheap model

**Question.** Does my routed LangGraph harness (a supervisor plus Gmail, Calendar/Tasks, Docs and Sheets workers) let a cheap model perform well on realistic workspace tasks, and how does it compare to Hermes Agent, a generic agent harness?

**Answer.** On 30 held-out tasks with GPT-6 Luna, the two harnesses are **tied on success**: graph 79/90 runs (88%), Hermes 80/90 (89%), with overlapping 95% confidence intervals. The graph does it with **2.5x fewer input tokens, about half the cost per successful run ($0.0022 vs $0.0041) and 14% less wall time**. It also made more unwanted changes on the test set (mass emails with stale facts, one deletion), so it is cheaper but not safer.

---

## 1. Setup

| | |
|---|---|
| Harnesses | (1) my LangGraph graph: a supervisor routes to 4 app workers with `route_to_agent(agent, context, lookup)`, and workers report back with `work_completion`. (2) Hermes Agent at commit `d0288be5b3`, run as shipped (tool search on). |
| Model | GPT-6 Luna (`gpt-6-luna-2026-09-22`) on Azure's Responses API, reasoning effort `medium`, no temperature sent. A current-generation cheap model, not a frontier one. |
| Environment | A fake Google Workspace MCP server under the real tool code. Search, truncation and formatting behaviour were copied from probes of a real dummy account. One shared fake company seed. |
| Tasks | 40 tasks: email, calendar, tasks, docs, sheets, cross-app, ambiguous and impossible. Each is medium, hard or extreme, measured from its golden path. 10 dev, 30 test. |
| Runs | 30 test tasks × 2 harnesses × 3 runs = 180 runs, frozen at tag `phase5-freeze` (commit `4795ae9`). |
| Grading | State checks against the seed diff (any change outside the allowed objects fails), then trajectory checks. An LLM judge (Luna) grades the final message, only on ambiguous and impossible tasks. |

Every task was validated before any agent ran: the golden path PASSes, doing nothing FAILs, and taking the trap on purpose FAILs (120/120 expectations met).

## 2. Fairness

Only the harness differed. Both harnesses had:
- the same tools (names, parameters and descriptions verbatim), the same MCP server and the same seed per run;
- the same model, endpoint, reasoning effort, step limit, tool timeout and 60-call cap (enforced in the server);
- the same frozen clock and user context.

Isolation:
- no memory across runs: a fresh `HERMES_HOME`; the graph's memory layer off, a fresh in-memory checkpointer and a new thread per run;
- one shared config file, with a settings hash checked on every record;
- an LLM relay that holds the key, logs every call and audits the wire parameters.

All 180 records have the same settings hash, commit, Hermes pin and seed. Reasoning effort `medium` reached the API on every call, and there were no fairness warnings, errors or infrastructure failures.

Known harness differences (documented, not removed):
- Hermes asks for reasoning summaries (`summary: auto`).
- Hermes checks tool arguments inside its `tool_call` bridge, so rejected calls never reach the server (2.4 per run), while all the graph's calls do.
- Hermes hides tools behind tool search, as shipped.

## 3. Results (test set)

| | Graph | Hermes |
|---|---|---|
| Runs passed | **79/90 (88%)**, CI 79–93% | **80/90 (89%)**, CI 81–94% |
| Tasks passed on all 3 runs | 24/30 | 23/30 |
| Cost per run / per successful run | $0.0019 / **$0.0022** | $0.0036 / $0.0041 |
| Total cost, 90 runs | $0.17 | $0.32 |
| Input tokens per run (89% / 88% cached) | **48.5k** | 120k |
| Output tokens per run (of which reasoning) | 1.6k (0.56k) | 1.6k (0.52k) |
| Model calls per run | 10.0 | 11.8 |
| Workspace calls attempted / reached the server | 9.2 / 9.2 | 11.8 / 9.5 |
| Lab LLM latency / wall time per run | 32.4 s / 36.6 s | 39.8 s / 42.6 s |

- The graph used fewer input tokens on 29 of 30 tasks, up to 4.9x fewer. Its workers see only their own app's tools and results, while Hermes carries the whole task in one context.

| Difficulty | Graph | Hermes |
|---|---|---|
| medium (7 tasks) | 95% | 95% |
| hard (16) | 96% | 98% |
| extreme (7) | 62% | 62% |

| Category | Graph | Hermes |
|---|---|---|
| calendar | 73% | 93% |
| docs | 100% | 83% |
| impossible | 50% | 67% |
| ambiguous | 83% | 83% |
| cross-app | 92% | 88% |
| email / sheets / tasks | 96% | 96% |

Medium and hard tasks are near the ceiling for both. The extreme tasks decide the result.

## 4. Failures

21 failed runs, each labelled and checked against its trace (`phase5_failure_labels.csv`). No grader or environment errors were found.

| Failure | Graph | Hermes |
|---|---|---|
| Wrong result (work done, wrong content) | 5 | 6 |
| Did the impossible / conflicting task anyway | 3 | 2 |
| Unwanted change | 2 | 0 |
| Asked, but not about the real options (disputed, see §6) | 1 | 0 |
| Acted instead of asking | 0 | 1 |
| Finished early | 0 | 1 |

**Changes outside the task:**
- graph: 3 mass emails with stale offsite details (imp_03), 2 deletions of a meeting that wasn't a 1:1 (cal_04), and 2 events on a company holiday (x_09);
- Hermes: 2 mass emails (imp_03) and 1 event created on an ambiguous request (amb_03).

**Final messages that misreported the result:** Hermes 2 (doc_01, doc_04), graph 1 (a cal_06 handoff claimed an event had no description).

**Typical failure of each harness:**
- **Graph:** a check that needs two apps at once belongs to no worker. In imp_03 the supervisor routed Docs → Sheets → Gmail, and the Gmail worker sent the doc's dates without ever searching mail for Rahul's later change. Hermes's passing run searched mail second.
- **Hermes:** losing a constraint it had already seen. In x_07 it read "Quarterly planning kickoff" and "SLO review" on the calendars and booked over them in all 3 runs. The graph's planning worker found the one free slot every time.

Traces: `phase5_findings.md`.

## 5. How the graph got here (dev set)

All tuning happened on the 10 dev tasks; the test tasks were never seen before the freeze.

| Run | Graph | Hermes |
|---|---|---|
| dev4 (Luna) | 20/30 | 18/30 (dev5) |
| dev6, after fixes A–D | 28/30 | not re-run (nothing shared changed) |

Changes, all at the graph level (prompts and routing):
- workers get the user's exact words instead of a supervisor paraphrase;
- an "act, report or ask" rule;
- a multiple-match rule (ask, naming every match);
- recurring events count as one meeting;
- open cut-off items before deciding;
- formulas for derived sheet totals;
- cross-app look-ups: `lookup` handoffs and `NEED:` hand-backs;
- a bulk-change count check;
- copy rewritten sheet rows from one source row each.

**The dev lead did not transfer.** The graph led by 10 runs on dev and is tied on test. The tuning fixed the failures it targeted (missing information, recurring events, cut-off text) but not new kinds of failure, such as contradicting sources. Tuning on 10 tasks overstates a harness's advantage, and only the held-out set measures it.

GPT-4.1-mini was dropped after dev: it hit a floor (graph 1/30, Hermes 4/30 on the first dev run, before most graph changes). Those numbers explain the decision; they are not a result.

## 6. Judge

The judge sees only the rubric, the request and the final message, and doesn't know which harness wrote it.
- **Calibration:** on 24 dev messages hand-labelled blind (20 by me, 4 filled in from my labels on near-identical messages), it agreed 21/24 = 88% (target 80%).
- **Direction:** it never passed a message I failed. All disagreements were it failing questions that didn't name the real options, which the task rule also fails.
- **On Phase 5:** 18 judge calls, 17 PASS.
- **Disputed verdict:** graph amb_03 r3 is FAIL. The message names both restaurants and the conflict, but its question sentence doesn't, and the judge read the rubric literally. As graded the score is 79/90; if this run counted as a pass, the graph would be 80/90 and exactly tied.

## 7. Limitations

- **Small sample.** 30 tasks × 3 runs per harness; the confidence intervals are about ±7 points, so differences under about 10 points are noise. Per-pattern results are mostly 1 task.
- **One model.** All results are for GPT-6 Luna at effort medium. Weaker models were not tested in the final setup.
- **Unequal tuning.** I tuned the graph on dev; Hermes ran as shipped.
- **Same author.** I designed the tasks and built the graph, which may favour the graph's design, though the test set did not.
- **Last prompt changes barely tested.** The final changes after dev6 were checked only by debug runs on two tasks; there was no final graph dev run.
- **Dev-only hint.** One dev-time prompt example was copied from a dev task's sheet (sh_03). It was removed before the freeze; no test task uses that sheet.
- **Lab only.** The workspace is a fake server modelled on real probes. The field layer (real dummy accounts) was not run, so latency is lab LLM latency only, without real tool latency.
- **Single turn.** Agents could not ask follow-ups. On ambiguous tasks the right move is a question that names the options; a reasonable "confirm the time?" counts as a fail.
- **Judge is Luna,** the agents' own model. It is harness-blind and calibrated, but leans strict.
- **Tool-call counts aren't fully comparable,** because of Hermes's argument check inside its bridge.

## 8. After the test run

After seeing the Phase 5 results, I changed the graph's prompts for its two weak spots:
- check for newer emails before sending facts taken from a doc or sheet, and ask if they conflict;
- calendar rules for holidays, overlaps, kinds of meetings and appending descriptions.

I also fixed the app's recursion limit. These changes were designed from the test failures, so any later run on the test tasks is reported here only as a post-test check, never in place of §3.

**Post-test check (graph, the 4 failed tasks × 3 runs): 8/12, against 4/12 in Phase 5.**
- imp_03 went from 0/3 to 3/3: it reported the conflict and sent nothing.
- cal_04 went from 1/3 to 3/3.
- cal_06 went from 1/3 to 2/3.
- **x_09 went from 1/3 to 0/3.** The new rules over-applied:
  - the free-time rule skipped a handover at the 11:00 time the user had fixed;
  - the check-before-sending rule treated an unconfirmed swap request as a contradiction and asked instead of acting.

Rules written from a few failures fix those failures and create new ones elsewhere, the same lesson as the dev-to-test gap. These changes were not checked for regressions on the dev tasks.

## 9. Reproducing

```powershell
git checkout phase5-freeze
.venv\Scripts\python.exe eval\validate.py                       # 120 task expectations
.venv\Scripts\python.exe eval\harness\runner.py --tasks <30 test ids> --harnesses graph hermes --models gpt-6-luna --runs 3 --out eval\runs\<new> --yes
.venv\Scripts\python.exe eval\harness\report.py eval\runs\<new>\records.jsonl
.venv\Scripts\python.exe eval\harness\analyze.py eval\runs\<new>\records.jsonl
```

Design notes: `eval/design/harness_notes.md` (harness differences and history), `tool_reference.md` (real-tool probes), `world.md` (the seed).
