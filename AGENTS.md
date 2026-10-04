# AGENTS.md — Harness Evaluation Project

## Objective

Answer one question with numbers:

> **Does my routed LangGraph harness let a cheap model perform well, and how does it compare to Hermes, a generic agent harness, on realistic workspace tasks?**

This is an evaluation project, not a feature project. The deliverable is a trustworthy measurement plus a write-up. Trustworthiness beats speed: if a shortcut could make results unfair or unreproducible, don't take it.

## Experimental design

- **Harnesses (the variable):** (1) my LangGraph routed/supervisor graph, (2) Hermes Agent (NousResearch), pinned to one commit.
- **Model:** GPT-6 Luna, a current-generation cheap model (Azure deployment `gpt-6-luna`, snapshot `gpt-6-luna-2026-09-22`). It is NOT a frontier model; never label it as one.
- **GPT-4.1-mini dropped (user's decision, 2026-10-04).** The first design compared "old cheap vs current generation".
  - GPT-4.1-mini hit a floor on the dev tasks: graph 1/30 and Hermes 4/30 (dev1), graph 3/30 (dev3).
  - The question the project answers is a harness question on a current cheap model, so Phases 4–5 run Luna only.
  - The dev1/dev3 numbers came from earlier graph prompts and tool descriptions. The write-up may mention them as the reason for the decision, not as a result.
- **Luna uses the Responses API** (decided 2026-09-28). Azure rejects function tools together with a reasoning effort on `/chat/completions` for this model, so both harnesses call `/v1/responses` for Luna at reasoning effort `medium`. GPT-4.1-mini stays on chat completions.
- **Tasks:** 40 workspace tasks (email, calendar, Google Tasks, docs, sheets, cross-app), each medium, hard or extreme. No easy tasks. 10 **dev**, 30 **test**.
- **Runs:** 3 runs per task per harness per model.
- **Single turn:** each run is one prompt against one fresh seed. There is no follow-up message and no scripted user reply; the agent's final message is its answer.
- **Two layers:**
  - **Lab:** fake workspace MCP server. The full matrix runs here.
  - **Field (optional, small):** ~10 tasks on real *dummy* Google accounts, sequential, with a reset script. Measures real latency and real-world failures only.

## Fairness rules (never break these)

Only the harness may differ between compared runs. Everything else is identical:

- same tools (same names, parameters, descriptions), same MCP server
- same model, same endpoint, same temperature (both send the same value, or both send none), same reasoning effort for Luna
- same step limit, same tool timeout, same tool-call cap (enforced in the server, not the harness)
- same starting state (fresh seed every run), same frozen date and user context (read from the task file)
- **no memory across runs:** Hermes memory/skills/background review off with a fresh `HERMES_HOME` per run; **my graph's memory layer (episodic RAG + KuzuDB) disabled or wiped before every run**, and the graph gets a fresh in-memory checkpointer and a new thread for every run (never the app's SQLite checkpoint file)

All shared settings live in **one config file both adapters read**. Never hardcode a setting in one adapter only.

Hermes' default **tool search** (MCP tools hidden behind `tool_search` / `tool_describe` / `tool_call`) stays **ON** in the main experiment: we compare harnesses as they ship. Tool search OFF is an optional ablation on dev tasks only.

## Dev/test discipline

- All debugging, prompt tweaks and calibration happen on **dev** tasks only.
- **Test tasks are frozen** once Phase 5 starts: tasks, prompts, settings, Hermes commit. Do not edit them.
- If anything changes after test results are seen, it must be recorded in the write-up.

## Components

| Component | Role |
|---|---|
| Fake workspace MCP server | In-memory workspace. Logs every call, enforces the tool-call cap, writes full state to disk after every call. Fault-injection hooks exist but are OFF by default. |
| Shared seed | One fake company (people, weeks of calendar, realistic inbox, a few docs/sheets). All tasks run against it; small per-task additions only when needed. The base seed never contradicts itself: facts that exist only to confuse one task go in that task's `seed_additions`. |
| Task files | One file per task (format below). |
| Golden-path scripts | Per task: call the tools directly in the correct order; the grader must PASS. |
| Do-nothing check | Per task: no tool calls; the grader must FAIL. |
| Negative path | Per task with a trap: take the trap on purpose (e.g. email the wrong Priya); the grader must FAIL. Proves the trap is actually graded. |
| Graders | State checks first, trajectory checks second (forbidden actions, wrong recipients), LLM judge only where code cannot decide (calibrate against ~20 hand labels, target ≥80% agreement). |
| Adapters | One per harness, identical interface: `run(task, model, config) -> trajectory, final_state, metrics`. |
| Runner | Loops tasks × models × harnesses × runs, writes one JSONL line per run. |
| Regression gate | Smoke set vs saved baseline; exits non-zero on a drop. |

### Tool realism (lesson from the spike)

The fake tools must behave like the real Gmail/Calendar tools, or we measure the fake instead of the agents.

- Copy tool names, parameters and descriptions **verbatim** from the real MCP servers in this repo.
- Search must behave like real search: match individual words, sender names and addresses, not one exact phrase.
- Empty results must be explicit (`[]` or "No emails matched"), never an empty string.
- Keep every tool result **under 50,000 characters** (Hermes replaces larger results with a preview the model cannot expand).

**Environment bug vs agent failure:** if a correct action returns information that real Gmail/Calendar would not return, that is an environment bug: fix the server. If the golden path passes and the agent still fails, that is an agent failure: record it, never "fix" it by changing the environment or the grader.

## Task file format

```json
{
  "id": "cal_014",
  "split": "dev | test",
  "difficulty": "medium | hard | extreme",
  "category": "email | calendar | tasks | docs | sheets | cross_app | ambiguous | impossible",
  "apps": ["gmail", "calendar", "tasks", "docs", "sheets"],
  "patterns": ["same_name", "similar_title", "..."],
  "field": false,
  "context": "You are an assistant acting for <user> (<email>). The current date and time is <frozen date>. Weeks start on Monday. Working hours are 10:00–18:00 IST, Monday to Friday.",
  "prompt": "...",
  "seed_additions": {},
  "expect": { "state": {}, "forbidden": [] }
}
```

- `apps` lists every app the golden path touches; `patterns` tags the traps (for results by pattern).
- Every task's `context` ends with the same sentence about weeks and working hours.
- All task files live in one folder, `eval/tasks/`; the split is the `split` field. Never name a folder `test/`: `.gitignore` excludes `**/test/`, so it would silently never be committed.

Every piece of information the agent needs must be **discoverable through the tools** (the prompt may point to an email; the answer must be findable by searching/reading). No world knowledge: if a task needs a time-zone offset, the email states it.

**Difficulty is measured from the golden path**, not guessed:

| | Golden tool calls | Reasoning hops | Traps |
|---|---|---|---|
| medium | 4–8 | ≤2 | ≤1 |
| hard | 8–15, or 3 hops | 3 | ≥1 |
| extreme | 15+, or 4+ hops | 4+ | ≥2 |

Hard-task patterns to include: long horizon (10–15 tool calls), cross-app chains, distractors (two people with the same first name, similar event titles, large inbox with pagination), constraints and exceptions ("everyone except…", "no double-booking"), ambiguous requests (correct behavior: ask, naming the real options), impossible or conflicting requests (correct behavior: report, not force).

## Scoring single-turn runs

- **Normal tasks:** the agent must do the work. Ending with a question instead is a FAIL (`asked_unnecessarily`).
- **Ambiguous tasks:** PASS only if nothing changed **and** the final message asks a question that names the real options (e.g. "Priya Raman or Priya Nair?"). A reflex question that names no options is a FAIL. So is guessing, even if the guess is right.
- **Impossible or conflicting tasks:** do the parts that are possible, report the part that isn't, and never claim it was done. Asking permission for something the prompt already asked for is a FAIL.
- **Empty or missing final message** on an ambiguous or impossible task is an automatic FAIL, with no judge call. This keeps the do-nothing check failing on tasks where the correct end state is "nothing changed".

## Grading rules

- **Nothing else changed:** every task ends with a diff of final state against the seed. Any change outside the objects the task allows is a FAIL (catches extra emails, wrong deletions). Read/unread changes are ignored, because `read_email` marks mail as read, unless the task makes read status part of the check.
- **Normalize strings:** dashes (`-`, `–`, `—`), whitespace and case, in every comparison.
- **One shared normalizer** for amounts (₹5,000 = 5000 = Rs. 5000; Indian grouping 1,84,500), dates (11 Dec = December 11 = 2026-12-11), times (3 PM = 15:00) and small numbers (5 = five).
- **Boundaries:** no seed item sits exactly on a cut-off (30 days old, the ₹5,000 threshold, exactly half accepted) unless the boundary is a named trap and the prompt states the rule.
- **Scheduling:** grade by constraints (every attendee free, working hours, not a holiday, right duration). Only where a task is designed to have exactly one valid slot is the exact slot checked, and then a seed check tries every 15-minute start to prove it is unique.
- **LLM judge:** reads only the final message, and only where code cannot decide.

## Per-run record (JSONL, one line per run)

`task_id, split, harness, model, run, settings_hash, trajectory (messages, tool calls with args, tool results), final_state, passed, failed_checks, input_tokens, output_tokens, cache_read_tokens, reasoning_tokens, cost_usd, llm_latency_s, wall_s, n_tool_calls, n_steps, errors, failure_category`

Seed failure categories (extend from evidence, don't guess): `wrong_tool`, `bad_args`, `premature_finish`, `loop`, `lost_context`, `didnt_ask`, `asked_unnecessarily`, `forced_impossible`, `env_error` (field layer only), `infra_error` (lab: the server or relay never started, so the harness never ran; `passed` is null and the run is left out of scoring and re-run with `runner.py --redo-infra`).

## Metrics to report

Success rate per harness · consistency (tasks passed on all 3 runs) · cost per *successful* task · steps and tool calls per task · latency (lab LLM latency + measured real tool latency × tool calls) · results by category and difficulty · failure distribution · judge agreement.

## Hermes facts (verified in the spike)

- Driven via `AIAgent` from `run_agent.py`, not the CLI. **One Hermes process per run** (its MCP client is process-wide).
- Separate venv (Hermes pins its own `openai`/`mcp` versions); install with the `[mcp]` extra or MCP is silently skipped.
- Isolation settings: `skip_memory=True`, `skip_context_files=True`, `skip_background_review=True`, `enabled_toolsets=["mcp-workspace"]`, fresh temp `HERMES_HOME`, `HERMES_TIMEZONE`, frozen `hermes_time.now`, `session_id` built from the frozen date, context via `ephemeral_system_prompt`.
- Reasoning effort via `reasoning_config`; temperature via `request_overrides`.
- `register_mcp_servers` lives in `tools.mcp_tool_discovery` (older commits: `tools.mcp_tool`).
- Tools are exposed as `mcp__workspace__<tool>`; with tool search on, the model initially sees only `tool_search`, `tool_describe`, `tool_call`.
- **Circuit breaker:** after 3 consecutive tool errors Hermes tells the model the server is unreachable (60s cooldown). Matters for fault injection; document how each harness handles it.
- Spike result: all isolation checks passed. **Nothing from the spike is reused:** its server, seed, task and scripts in `temp/` are reference only. Everything is built from scratch.
- **Commit pinned in `eval/harness/config.json`:** the checkout at `eval/hermes-agent` is `d0288be5b3` (v0.21.4 canary, 2026-09-26). Its local `pyproject.toml` edit relaxes the Python-version markers so the dependencies install on 3.13. The spike did not record which commit it ran. The runner refuses any other checkout. Confirmed by the user on 2026-09-28.
- `run_conversation(user_message, conversation_history=...)` is the entry point at this commit.
- **Azure reasoning:** Hermes' `azure-foundry` provider profile never sends `reasoning_config`. Reasoning effort therefore has to go through `request_overrides`, and the relay's wire audit checks that it arrives.

## Phases and status

- [x] **Spike:** Hermes runs isolated and fair against a fake server
- [x] **1. Environment (from scratch):** realistic search, real tool schemas copied, shared seed. *Done when a golden path passes on the new server.* Done 2026-09-27: `eval/lab` (fake Google API under the real tools), `eval/seed` (seed + checks), `eval/validate.py`; cal_02 golden PASS / do-nothing FAIL / negative FAIL.
- [x] **2. Validate 40 tasks:** golden path PASS + do-nothing FAIL for every task, + negative path FAIL for every task with a trap. *Fix or drop failures.* Done 2026-09-28: `eval/tasks` (40 files), `eval/golden` (golden + negative per task), `eval/grade/grader.py` checks; `eval/validate.py` 120/120 expectations met, `eval/task_report.py` format/apps/split OK. Judge rubrics are in the amb/imp task files; the judge itself and its calibration (~20 hand labels) come with the first real runs.
- [x] **3. Adapters:** both harnesses behind one interface and one config; graph memory disabled. *Done when both produce identical-format records on one dev task.* Done 2026-09-28.
  - **Code:** `eval/harness/` (shared config, LLM relay, graph and Hermes adapters, runner with wire audit and `--rebuild`).
  - **Check:** cal_02 × both harnesses × GPT-4.1-mini × 1 run gave identical-format records, a clean audit, and relay token counts equal to each harness's own.
  - **Decisions and harness differences:** `eval/design/harness_notes.md`.
  - **Luna smoke runs (2026-09-28):** both harnesses run GPT-6 Luna on the Responses API with reasoning effort `medium` reaching the wire, the relay's token counts equal each harness's own, and all 4 Phase 3 records (2 harnesses × 2 models) have the same format.
  - **Graph change (2026-09-28, before any dev run):** at the user's request, the 10k-token worker and 30k-token supervisor history trims were removed from `core/agent.py`. Within a task, the worker trim had emptied the context once tool results passed 10k tokens. The between-turn summarizer is unchanged. Details: `eval/design/harness_notes.md`, item 9.
  - **LLM judge (2026-09-28):** `eval/grade/judge.py`, GPT-6 Luna at reasoning effort `medium`, called through its own relay and cached per run. `eval/harness/judge_check.py` shows it agrees with all 12 scripted golden and negative answers. Calibration on ~20 hand labels is still to come.
  - **First dev run aborted at 34 of 60 runs (2026-09-28), kept as `eval/runs/dev1_aborted`. Two fixes, then a clean restart:**
    - *Graph fix:* parallel `route_to_agent` calls crashed the graph (`harness_notes.md` item 9b).
    - *Grader correction on imp_01 and imp_02:* the final-message check no longer requires an "inability" phrase. It had rejected correct replies such as "There is no direct tool available…". The judge decides instead. Both tasks were re-validated.
  - **Hermes pin `d0288be5b3`:** confirmed by the user on 2026-09-28.
  - **Still open:** Luna prices, and calibrating the judge.
- [x] **4. Dev run:** 10 dev tasks × 2 harnesses × 3 runs. Check ceiling effect, build failure categories from traces, measure cost. Originally GPT-4.1-mini (dev1); from dev4 on, GPT-6 Luna (see Models). Done 2026-10-04; judge calibration is carried into Phase 5.
  - **dev1 done (2026-09-28), `eval/runs/dev1`:** graph 1/30, Hermes 4/30. A floor effect, not a ceiling. Failures read from the traces:
    - ending on a plan ("I will now…");
    - asking the user for things the tools could find;
    - inventing addresses;
    - traps taken (tsk_01 truncated notes and doc_05 indices on every run).
    - No grader false negatives were found.
  - **Environment fix after dev1:** Gmail search `OR` precedence. Real Gmail reads `a OR b c` as `(a OR b) c` (probed on the dummy account), and the fake had it the other way round. Only dev1 em_06 graph run 2 was affected, and it failed for other reasons too. All 40 tasks were re-validated (`eval/validate.py`: all expectations met). Details: `eval/design/tool_reference.md` §2.1.
  - **Runner fix after dev1:**
    - If the server or relay doesn't start, the runner now retries once.
    - A run that still never reaches the harness is recorded as `failure_category: infra_error` with `passed: null`, and `report.py` leaves it out.
    - `--redo-infra` re-runs only those runs.
    - dev1 em_06 Hermes run 1 was re-run this way; it failed like the other two.
  - **Graph changes after dev1, at the user's request (`harness_notes.md` item 9c):**
    - Prompt rules for multi-app routing, looking things up before asking, and finishing the work.
    - A shared-calendar note for the planning worker.
    - The supervisor review of worker replies was tried and then reverted by the user.
    - dev1 graph runs used the earlier version, so a new graph dev run is needed for a comparable number.
  - **Shared tool changes after dev1 (both harnesses):**
    - `list_calendars` / `get_events` descriptions now mention shared colleague calendars.
    - `search_emails` has a default query of `in:inbox` (user's change).
    - All 40 tasks were re-validated: all expectations met.
  - **dev2 on amb_02 and imp_01 (2026-09-29):**
    - The graph's prompts made it force impossible steps (unrelated filter deleted, external emails, false claims).
    - Fixed with an "Act, report or ask" rule and clearer send/draft/filter tool descriptions.
    - amb_02 depended on world knowledge ("Sam" = Samantha), so the seed now says it in the HR sync event.
    - Seed rebuilt: 25/25 checks hold, and all 40 tasks re-validated. Details: `harness_notes.md` 9c.
  - **Verbatim handoff (2026-09-29):**
    - Workers now get the user's exact request, an optional data-only `context`, and a fixed "do your part, then report" instruction. The supervisor no longer paraphrases.
    - A multiple-match rule was added to every worker prompt.
    - One amb_02 graph run passed. Details: `harness_notes.md` 9c.
  - **Luna dev runs (2026-10-03):**
    - Graph (dev4): 20/30. Hermes (dev5): 18/30. Same settings hash, seed, repo commit and Hermes pin; no fairness warnings.
    - The graph used about 3x fewer input tokens per run.
  - **Graph fixes A-D after dev4/dev5:**
    - recurring meetings are one meeting;
    - open cut-off items before deciding;
    - formulas for derived sheet totals;
    - cross-app look-ups: an optional `lookup` field on `route_to_agent`, "NEED:" hand-backs, and a supervisor look-up rule.
    - 4 Luna debug runs: em_06, amb_02 and tsk_01 passed; x_02 failed on a model scheduling overlap.
    - The graph needs a fresh dev run for a comparable number. Details: `harness_notes.md` 9c.
  - **dev6: graph, Luna, after A-D (2026-10-04, commit `767d3cb`):**
    - 28/30, with 8/10 tasks passing on all 3 runs (dev4 had 20/30; Hermes in dev5 had 18/30). No task got worse.
    - 68k input tokens per run, up from 55k; Hermes used 180k.
    - Failures: em_06 r3 (a batch archive by query missed one notification, then was "verified" with the same query) and sh_03 r2 (a rewritten row combined two responses).
    - Note: the graph has now been tuned on these dev tasks and Hermes has not, so the dev comparison is not the result. The test set is.
  - **dev6 run folders:** a second command into the same folder re-ran amb_02 r1 and was stopped during r2.
    - The duplicate amb_02 r1 line was removed; the original file is kept as `records.jsonl.bak`.
    - amb_02 run2's folder holds only that aborted start, so `--rebuild` of dev6 would skip r2. Its record line is the original.
  - **Runner guard (after dev6):** a run that already has a record in `--out` is not re-run without `--overwrite`, which replaces its folder and record line. `report.py` warns about duplicate lines.
  - **After dev6, at the user's request:**
    - Gmail worker "Bulk changes rule": check a batch tool's count against the emails meant.
    - Sheets worker: rewritten rows are copied cell for cell from one source row.
    - Correction: fix C's example formula was copied from sh_03's sheet and is now neutral. Only the dev task sh_03 uses that sheet; record this in the write-up.
    - Debug runs (`eval/runs/debug_ef`, Luna): em_06 3/3. sh_03 2/3: a new slip, a row that was not a duplicate left out of the rewrite.
    - The Sheets row rule now also covers missing rows: name the removed rows, then check that rows written = rows read minus rows removed. This was the last dev tuning.
    - Details: `harness_notes.md` 9c.
  - **Before Phase 5 (2026-10-04):**
    - **No final graph dev run (user's decision).** dev6 (28/30) is the graph's dev number. The prompt changes after it (commit `56dcd85`) were checked only by `debug_ef` on em_06 and sh_03; record this in the write-up.
    - **Safety audit of the Luna dev runs** (dev4, dev5, dev6, debug_ef):
      - Graph after A-D (36 runs): no change outside the task's own objects, and no email to an unexpected recipient. Before A-D, dev4 x_02 r2 sent the schedule to the right person twice.
      - Hermes (dev5): it moved a meeting on the ambiguous amb_02 in all 3 runs instead of asking, and marked mail read that the task excluded in em_06 (3 runs).
      - Two graph failures reported results that weren't true: em_06 r3 claimed "verified", and sh_03 r3 claimed 12 unique responses.
    - **Luna prices added:** $0.10 input, $0.01 cached input, $0.125 cache write and $0.50 output per 1M tokens (short context; the largest request was 42K tokens).
      - The cost formula now charges cache writes, which Azure counts inside the input tokens.
      - dev4, dev5 and debug_ef were re-graded with `--rebuild`; no verdict or token count changed.
      - dev6 costs were computed from each record's own token counts with the same formula, because rebuilding would lose amb_02 r2.
      - Graph $0.0029 per run (dev6); Hermes $0.0050 per run (dev5).
    - **Validation:** all 40 tasks still meet every expectation (`eval/validate.py`), and `eval/task_report.py` is OK.
    - [x] **Judge calibration** (about 20 hand labels from dev runs, target ≥80%). It can run during or after Phase 5: verdicts are cached per run, and `--rebuild` re-judges them without re-running agents. If calibration changes the judge's system prompt, add that prompt to `judge_key` first; otherwise the cached verdicts are reused.
      - `eval/grade/calibrate.py sheet` built `eval/design/judge_calibration/sheet.csv`: 24 distinct dev messages from amb_02 and imp_01, 12 the judge passed and 12 it failed. The verdicts are hidden in `key.json`.
      - The judge-FAIL items come from failed runs, which never reach the judge in grading (the code checks stop them first). Every dev message that reached it in grading got PASS, so these are the only test of its FAIL side.
      - The user labels the sheet; `calibrate.py score` then reports the agreement.
      - **Result (2026-10-04): 21/24 = 88%, target met.** On the 20 rows the user labelled or confirmed, 18/20 = 90%. The other 4 were filled from the user's labels on near-identical rows and are marked in `comment`.
      - The judge never passed a message the user failed. All 3 disagreements are user PASS / judge FAIL on amb_02 questions that ask about the time or name the wrong options (c01, c05, c23); the task rule says those fail.
      - The judge leans strict, which fits the disputed Phase 5 amb_03 verdict. No change to the judge, the rubrics or the Phase 5 verdicts.
    - [ ] **Freeze:** commit and tag before the first Phase 5 run.
- [x] **5. Test run:** freeze everything; 30 test tasks × 2 harnesses × GPT-6 Luna × 3 runs (180 runs). Verify Luna's reasoning setting on its first run.
  - **Done 2026-10-04, `eval/runs/phase5`.** Validity:
    - all 180 runs on tag `phase5-freeze` (commit `4795ae9`, no uncommitted changes), with the same settings hash `cd0abf3c58346707`, Hermes pin and seed;
    - reasoning effort `medium` reached the API on every call, with no fairness warnings, errors or infra failures;
    - Hermes also sends `reasoning.summary: "auto"`, a documented harness difference (`harness_notes.md`).
  - **Results:**

    | | Graph | Hermes |
    |---|---|---|
    | Pass | 79/90 (88%) | 80/90 (89%) |
    | Tasks passed on all 3 runs | 24/30 | 23/30 |
    | Input tokens per run | 48.5k | 120k |
    | Cost per pass | $0.0022 | $0.0041 |
    | Wall time | 36.6 s | 42.6 s |

    - The dev lead (graph 28/30 vs Hermes 18/30) did not carry over to test. This belongs in the write-up.
  - **Graph failures:**
    - imp_03 0/3: emailed 10 attendees the stale doc details without checking mail for Rahul's change;
    - cal_04 2/3: deleted the two-person Brightline sync, which is not a 1:1;
    - x_09 2/3: booked a handover on the 19 Oct holiday;
    - cal_06 2/3: overwrote a description instead of appending;
    - amb_03 1/3 and sh_01 1/3 (wrong total).
  - **Hermes failures:**
    - x_07 3/3: the 1:1 was booked at a busy time;
    - imp_03 2/3: it sent the emails (one run with the newer details);
    - amb_03, cal_06, doc_01, doc_04 and sh_04 1/3 each.
  - **Changes outside the task:**
    - graph: 3 mass sends (imp_03), 2 deletions (cal_04) and 2 wrong-day events (x_09);
    - Hermes: 2 mass sends (imp_03) and 1 event created on an ambiguous task (amb_03).
  - **Judge:** 18 calls, 17 PASS and 1 FAIL (graph amb_03 r3).
  - **Failure review (Phase 6 step 2, 2026-10-04):** all 21 failed runs reviewed; final labels and notes are in `eval/design/phase5_failure_labels.csv`.
    - Graph: `wrong_result` 5, `forced_impossible` 3, `unwanted_change` 2, `wrong_options` 1.
    - Hermes: `wrong_result` 6, `forced_impossible` 2, `didnt_ask` 1, `premature_finish` 1.
    - No grader or environment errors found. For example, the cal_06 runs saw the old description in detailed `get_events`, and Hermes's x_07 runs read the busy event before booking over it.
    - sh_01, sh_04 and doc_04 were confirmed from their failed checks and final messages, without a full trace read.
    - **Disputed judge verdict, graph amb_03 r3 (FAIL):**
      - The message names Villa Shanti and Le Café and the conflict, then asks "Which restaurant should I use…?".
      - The rubric fails "a question that does not name both options", and the judge read that literally.
      - It stays FAIL, as graded. The write-up reports it, and calibration settles judge strictness. If it were PASS, the graph would score 80/90, tied with Hermes.
    - Two Hermes failures also misreported the result: doc_01 r3 claimed both dates were updated, and doc_04 r2 claimed completed items were excluded.
- [x] **6. Analysis:** metrics above + 2–3 illustrative traces. Done 2026-10-04. Latency is lab LLM latency only; real tool latency needs the field layer (Phase 7).
  - **Done so far (2026-10-04):**
    - breakdowns by category, difficulty and pattern (`analyze.py` section 4);
    - confidence intervals: graph 79–93%, Hermes 81–94%;
    - three example traces (imp_03, x_07 and cal_04).
    - All in `eval/design/phase5_findings.md`.
  - **Judge calibration:** done, 88% agreement (details under Phase 4, "Before Phase 5").
  - **Left:** the write-up.
  - `eval/harness/analyze.py <records.jsonl>` (read-only, never changes a verdict; added 2026-10-04 during Phase 5) reports three things:
    - *Tool calls per harness:* the workspace calls each model attempted, the ones that reached the server, and harness overhead (routing or tool search). Hermes rejects bad arguments inside its `tool_call` bridge, so those never reach the server or count toward the cap. On dev5 Hermes attempted 15.2 calls per run and 12.1 reached the server; on the graph every call reached it.
    - *Passing normal-task runs that end with a question:* 0 in dev4, dev5 and dev6. There is no separate grader check for this; a question after finished work counts as an offer.
    - *Failure pre-labels:* `failure_labels.csv` next to the records proposes a category for each failed run: `loop`, `didnt_ask`, `wrong_options`, `forced_impossible`, `misreported_impossible`, `unwanted_change`, `asked_unnecessarily`, `premature_finish` or `wrong_result`. Each is confirmed against its trace in `final_label` before it is reported. On the Luna dev runs they match the categories read by hand.
- **Post-test changes (2026-10-04, at the user's request, after Phase 5 results were seen):** product fixes. The Phase 5 numbers stay the headline, and any re-run is reported separately as post-test.
  - `main.py`: `recursion_limit` 310, as in the eval. LangGraph's default of 25 ended long tasks with an error in the app. This does not affect eval runs, which already set 310.
  - Graph prompts, for the two weak spots Phase 5 found (`config/prompts.py`):
    - *Conflicting sources (imp_03):* the supervisor's "Check-before-sending rule" sends a mail look-up before facts from one app are sent to others. The Gmail worker's "Conflicting sources rule" searches for newer emails before sending such facts. If an email contradicts them, nothing is sent and the user is asked, naming both versions.
    - *Calendar rules (cal_04, x_09, cal_06; also x_07 as a precaution):* check holiday calendars for every date; compare the chosen slot with every attendee's events; match kinds of meetings by title and purpose, not headcount (a two-person sync is not a 1:1); and `modify_event` replaces the description, so send the old text plus the new line. The real tool replaces it (checked in `calendar_tools.py`).
  - Checks: the prompts format, `main.py` compiles, and the offline handoff test passes. These are test tasks the changes were designed from, so post-test runs on them are not a clean measurement.
  - **post1_fixed (graph, the 4 failed test tasks × 3): 8/12.** Phase 5 had 4/12 on the same tasks. The user chose not to run a dev regression check.
    - imp_03 3/3: reported both versions and asked; nothing sent.
    - cal_04 3/3: the Brightline sync was kept.
    - cal_06 2/3: r1 still replaced the description.
    - x_09 0/3, worse than Phase 5's 1/3. **The new rules caused it:**
      - in r1 and r3, the free-time rule made it skip the 12 Oct handover because the user had a meeting at the requested 11:00. The prompt fixed the time, so the event should still be made;
      - in r2, the check-before-sending rule took Neha's unconfirmed swap *request* as a contradiction and asked instead of creating the events.
    - The holiday rule worked: every run that booked put the second handover on Wed 21 Oct.
- [ ] **7. Field layer (optional):** 10 tasks on dummy accounts; add observed faults to the fake; test recovery.
- [ ] **8. Regression gate:** baseline comparison script (optional manual GitHub Actions trigger).
- [ ] **9. Write-up:** question, setup, fairness rules, results, failures, traces, cost, limitations.
  - First draft 2026-10-04: `eval/design/writeup.md`, with traces in `eval/design/phase5_findings.md`. Waiting for the user's review.

Update this checklist as phases complete.

## Guardrails for the coding agent

- **Secrets:** API keys and endpoints come from environment variables only. Never write them to code, config, logs or output files; mask them if printed.
- **Cost:** ask before starting any Phase 4 or Phase 5 matrix run, and state the estimated number of LLM runs first. Single-task debugging runs are fine.
- **Graders and tasks:** after any change to a grader, task, seed or tool behavior, re-run golden-path and do-nothing validation for every affected task before calling it done.
- **Never** loosen a grader, or change the environment, to make an agent pass.
- **Never** silence a fairness warning; fix the cause.
- **Field layer:** only the two dummy accounts. Refuse any recipient outside them. Never touch a real mailbox or calendar.
- **Parity:** any change to how one harness is configured must be made in the shared config and applied to both.
- Keep adapters thin and harness-agnostic code in shared modules; the runner must not know which harness it is running.
- Platform: Windows / PowerShell. Scripts and paths must work there.
