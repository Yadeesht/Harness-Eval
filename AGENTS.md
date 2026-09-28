# AGENTS.md — Harness Evaluation Project

## Objective

Answer one question with numbers:

> **Does my routed LangGraph harness let a cheap model perform well, and how does it compare to Hermes, a generic agent harness, on realistic workspace tasks?**

This is an evaluation project, not a feature project. The deliverable is a trustworthy measurement plus a write-up. Trustworthiness beats speed: if a shortcut could make results unfair or unreproducible, don't take it.

## Experimental design

- **Harnesses (the variable):** (1) my LangGraph routed/supervisor graph, (2) Hermes Agent (NousResearch), pinned to one commit.
- **Models:** GPT-4.1-mini (old cheap model) and GPT-6 Luna (current-generation cheap model; Azure deployment `gpt-6-luna`, snapshot `gpt-6-luna-2026-09-22`). Framing is "old cheap vs current generation", NOT "cheap vs frontier". Never label Luna as frontier.
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

Success rate per harness × model · consistency (tasks passed on all 3 runs) · cost per *successful* task · steps and tool calls per task · latency (lab LLM latency + measured real tool latency × tool calls) · results by category and difficulty · failure distribution · judge agreement.

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
- [ ] **4. Dev run:** 10 dev tasks × 2 harnesses × GPT-4.1-mini × 3 runs (60 runs). Check ceiling effect, build failure categories from traces, measure cost.
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
  - **Graph change after dev1, at the user's request:** the supervisor reviews a worker's plain-text reply before the user sees it (`harness_notes.md` item 9c). dev1 graph runs used the old routing.
- [ ] **5. Test run:** freeze everything; 30 test tasks × 2 harnesses × 2 models × 3 runs (360 runs). Verify Luna's reasoning setting on its first run.
- [ ] **6. Analysis:** metrics above + 2–3 illustrative traces.
- [ ] **7. Field layer (optional):** 10 tasks on dummy accounts; add observed faults to the fake; test recovery.
- [ ] **8. Regression gate:** baseline comparison script (optional manual GitHub Actions trigger).
- [ ] **9. Write-up:** question, setup, fairness rules, results, failures, traces, cost, limitations.

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
