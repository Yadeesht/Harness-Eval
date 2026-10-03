# Harness setup: how both harnesses are run fairly

Phase 3 (2026-09-28). Code: `eval/harness/`. Shared settings: `eval/harness/config.json`.

## One run

```
runner ─► fake MCP server  (task seed + seed_additions, 60-call cap, logs every tool call)
       ─► LLM relay        (the only process with the Azure key; logs every model call)
       ─► adapter process  (graph: .venv   |   Hermes: eval/venvs/hermes)
       ─► grader           (final state + tool log + final message) ─► one JSONL record
```

Every run gets fresh processes. The runner starts both adapters with identical arguments and never looks inside a harness. Adapter processes get an environment with secrets removed, and they run from the run folder.

```
.venv/Scripts/python.exe eval/harness/runner.py --tasks cal_02 --harnesses graph hermes --models gpt-4.1-mini --runs 1 --out eval/runs/phase3
.venv/Scripts/python.exe eval/harness/runner.py ... --rebuild            # re-grade saved runs, no model calls
.venv/Scripts/python.exe eval/harness/graph_adapter.py ... --dry-run    # build everything, no model call (same for hermes_adapter.py)
```

More than 4 runs need `--yes`. The runner refuses to run Hermes from a checkout other than the pinned commit.
It also refuses to re-run a run that already has a record in `--out` (in `records.jsonl` or its folder's `record.json`). `--overwrite` re-runs it, replacing its folder and its record line. This was added after dev6: a second command into the same folder re-ran amb_02 r1, which left two record lines and overwrote the folders. `report.py` warns about duplicate lines and counts only the last.

## Shared settings and how each harness gets them

| Setting | Value | Graph | Hermes |
|---|---|---|---|
| Endpoint | relay → Azure `/openai/v1` | `ChatOpenAI(base_url=relay)` in place of `AzureChatOpenAI`'s deployment URL | `AIAgent(base_url=relay, provider="azure-foundry")` |
| API, per model | GPT-4.1-mini: chat completions; GPT-6 Luna: Responses API | `use_responses_api` false / true | `api_mode` `chat_completions` / `codex_responses` |
| Model | deployment from config | `model=` | `model=` |
| Temperature | none (decided 2026-09-28) | not set | not set |
| Reasoning effort (Luna: medium) | config value | chat: `reasoning_effort=`; Responses: `reasoning={"effort": …}` | chat: `request_overrides={"reasoning_effort": …}`, because the azure-foundry profile never sends `reasoning_config`. Responses: `reasoning_config={"effort": …}`, which Hermes sends as `reasoning.effort` plus `summary: "auto"`. |
| Step limit | 100 model calls | callback counter stops the run; LangGraph `recursion_limit` 310, so it never binds first | `max_iterations=100` (Hermes then makes one summary call) |
| Tool-call cap | 60 | enforced in the MCP server | same |
| Tool timeout | 60 s | FastMCP client `call_tool(timeout=)` | MCP server config `timeout` |
| Model request timeout | 120 s | `ChatOpenAI(timeout=)` | `providers.azure-foundry.request_timeout_seconds` in the run's `HERMES_HOME/config.yaml` |
| Retries | 3 | OpenAI SDK `max_retries` | `agent.api_max_retries` (Hermes-level; the SDK below it retries too) |
| Clock | seed "now", Wed 7 Oct 2026 09:30 IST | `get_current_time` patched | `hermes_time.now` patched; session id stamped with the frozen time |
| Task context | task file `context` | appended to all 5 system prompts (supervisor + 4 workers) after a blank line (decided 2026-09-28) | `ephemeral_system_prompt`, which Hermes appends after a blank line |
| Memory | none across runs | fresh `InMemorySaver` + new thread; `data/checkpoints.db` never opened; `.env` never read | fresh `HERMES_HOME` in the run folder; `skip_memory`, `skip_context_files`, `skip_background_review`, no checkpoints; `~/.hermes` checked for writes |
| Tools | the 75 MCP tools | split across the 4 workers by the app_tools registries, as in `main.py` (26 / 17 / 18 / 14) | `enabled_toolsets=["mcp-workspace"]`, tool search on (Hermes' default) |

## Measurement

- **Model calls, tokens, cost, latency:** measured at the relay, the same way for both harnesses.
  - On the first cal_02 runs the relay's numbers equalled each harness's own: graph 5,454 / 154 tokens; Hermes 34,418 / 846 with 18,176 cached.
  - Cost uses the per-model prices in the config.
  - `n_steps` counts successful model calls.
  - A harness whose own call count differs from the relay's gets a fairness warning (that is how hidden calls would show).
- **Wire audit:** checks every model call's parameters (model, temperature, reasoning effort, any OpenRouter-style `reasoning` field) against the config.
- **Tool calls:** taken from the server log, so the measurement point is the same for both.
  - `n_tool_calls` counts what reached the server.
  - `n_model_tool_calls` counts what the model asked for.

## Differences between the harnesses, as shipped (for the write-up)

1. **How tools are presented.**
   - Each graph worker sees its app's tools directly (LangChain drops JSON-schema `title` keys).
   - Hermes shows three bridge tools (`tool_search`, `tool_describe`, `tool_call`) plus a name-and-description listing, and the model calls workspace tools through `tool_call`.
2. **Where tool arguments are checked.**
   - The graph passes arguments straight to the server. Invalid calls are rejected there, logged, and counted toward the cap.
   - Hermes validates inside its `tool_call` bridge, so an invalid call never reaches the server and isn't counted. On cal_02 the model's first four calls used `calendarId`/`timeMin`, were refused by Hermes, and were then corrected.
3. **Streaming.** Hermes streams (with `include_usage`); the graph doesn't. This doesn't affect what the model returns.
4. **Prompt caching.** Hermes resends one growing conversation, so Azure serves much of it from cache (18k of 34k tokens on cal_02). The graph's supervisor and workers use different prompts and rarely share a prefix.
5. **Endpoint probing.**
   - The relay is on localhost, so Hermes also tries local-server endpoints (LM Studio, Ollama, llama.cpp, vLLM) and reads `/models`. That's about 9 metadata requests; they are listed as `other_requests` and aren't model calls.
   - The probes only feed context-length detection, which lands on Hermes' own catalog value (1,047,576 for gpt-4.1-mini), the same as for a remote custom endpoint.
6. **At the step limit.** Hermes asks the model for a summary (one extra call). The graph stops: a worker raises, and the supervisor turns the error into an `[ERROR]` reply.
7. **Tool errors.** The graph's ToolNode wraps the tool's error text (`Error: ToolException(...) Please fix your mistakes.`); Hermes returns its own error JSON. The error text from the tool itself is identical.
8. **Hermes circuit breaker.** After 3 consecutive tool errors, Hermes tells the model the server is unreachable (60 s cooldown). The graph has no equivalent.
9. **Graph context trim: removed on 2026-09-28, before the dev run.** The graph now keeps each agent's full history within a turn, as Hermes does.
   - **What it was.** The product's `core/agent.py` (present since the repo's first commit) trimmed each worker's history to its last 10,000 tokens and the supervisor's to 30,000, starting from a human message. Within one task a worker's only human message is the handoff. So once tool results passed 10k tokens (one detailed calendar week is about 12k), the handoff fell out of the window and the worker was left with only its system prompt. On Luna it happened sooner, because encrypted reasoning inside the message content was counted as text.
   - **What it did on cal_02.** After fetching five calendars, the planning agent's next call held only its system prompt and tools (4,760 tokens). It reported "No actionable user request", or asked "What would you like me to help you plan?".
   - **The change.** The user had both caps removed. The summarizer stays: `route_start` condenses the history when it passes 8,000 tokens at the start of a turn. It therefore never runs within a single-turn eval run; it bounds multi-turn chats in the product.
   - **The re-run** (`eval/runs/phase3_nocap`). Worker prompts now grow within a task: GPT-4.1-mini 533 → 18,838 tokens. Luna passed cal_02 (Tue 13 Oct 16:00). GPT-4.1-mini fetched all four calendars and then summarized them instead of booking, which is an agent failure unrelated to context.
9b. **Graph parallel-handoff crash: fixed on 2026-09-28, during the first dev run (runs thrown away and restarted).**
   - **The crash.** On imp_01, GPT-4.1-mini's supervisor sent two `route_to_agent` calls in one message ("create the filter", "archive the mail"). Each handoff returns a `Command` setting `current_agent`, a single-value channel, so LangGraph raised `InvalidUpdateError` and the run ended with nothing done. It happened on all 3 graph runs.
   - **The fix (in the product code).** The supervisor's model binding sends `parallel_tool_calls=False` (`core/graph.py`), so it hands off one piece at a time. `current_agent` also got a last-value reducer (`core/state.py`), so no double update can crash the graph again. Checked offline with a scripted model (the old code raises, the new code finishes with the worker handling both handoffs), then in a real imp_01 run (no crash; the supervisor's calls carry `parallel_tool_calls: false`).
   - **Adapter.** A graph crash is now recorded as the graph's `error`, keeping whatever state exists, instead of an adapter error.
9c. **Graph changes after dev1 (2026-09-28, dev tasks only, at the user's request). dev1 graph runs used the earlier version.**
   - **Supervisor review of worker replies: tried, then reverted by the user.**
     - For a while, a worker's plain-text reply went to the supervisor instead of the user.
     - The user removed it: the supervisor got the question without the worker's context. Workers now talk to the user directly again, and a plain-text reply ends the turn (`internal_agent_route` → END).
     - Two runs with it (`eval/runs/debug_review`) both failed.
   - **Prompt changes (`config/prompts.py`).** Two are by the user, the rest by the agent at the user's request.
     - *By the user:*
       - a supervisor "Complete Handoff Rule": handoffs must carry the actual data from earlier workers;
       - a "Worker reply rule" for chaining workers;
       - fuller `work_completion` summaries.
     - *Supervisor:*
       - a multi-app rule: split the request by app and route one worker at a time until every part is done;
       - keep the user's wording and constraints, and add no assumptions of its own;
       - delegate workspace requests instead of asking the user, because the supervisor can't see the workspace.
     - *Workers:*
       - a work rule: carry out every step with tool calls, don't stop on a plan, and don't ask permission for what was requested;
       - a look-up-first rule: find details with the tools before asking, and check whether more than one item matches before changing something named loosely;
       - hand back with the remaining part when another app is needed.
     - *Planning worker:* a "Calendar access" note: shared colleague calendars are visible through `list_calendars` and `get_events`.
     - The old lines "if critical details are missing, ask the user" were replaced.
   - **Why.** In dev1, the graph's own losses came from:
     - cross-app tasks that never reached the other apps' workers (em_06, x_01, x_02);
     - reflex questions from the supervisor (amb_02) and from workers (imp_01, cal_02);
     - ending on a plan.
   - **Debug runs (GPT-4.1-mini, 1 each)** in `eval/runs/debug_prompts` and `debug_prompts2`:
     - **cal_02:** first run booked Mon 16:00 (the trap); the rerun passed (Tue 13 Oct 16:00).
     - **x_01:** the Gmail → Sheets → Gmail chain worked and the sheet was right; failed because the emails lack the dates.
     - **em_06:** it guessed the direct reports without reading the Team Directory sheet.
     - **amb_02:** changed from a vague question to a guess. The keyword search "Sam" matches whole words only, so it found only the Brightline sync and moved it.
   - **Shared tool descriptions also changed** (both harnesses see them): `list_calendars` and `get_events.calendar_id`. See `tool_reference.md` §3.
   - **dev2 check (2 tasks, 2026-09-29) and correction.**
     - *What happened:* the "carry out every step, never ask" rule made the graph force imp_01's impossible step. It deleted an unrelated filter, emailed `noreply@jira…` and `gmail-support@google.com`, left drafts, and falsely said the filter was set up. On amb_02 it moved the only "Sam" meeting it could find.
     - *Prompt fix:* the rule is now "Act, report or ask":
       - act when the tools can do it;
       - report a step the tools can't do, without substituting other actions;
       - ask only when the answer isn't in the workspace or several real options match;
       - send, draft, delete or change only what was asked, and never claim what no tool did.
     - *Tool descriptions (both harnesses):*
       - `send_email`: delivered immediately; only when asked.
       - `create_draft`: not for notes to the user.
       - `list_filters`: filters can be listed, read and deleted, not created or edited.
       - `delete_filter_tool`: permanent; only when asked. Also fixed its wrong reference to `list_filters_tool`.
       - `get_events.query`: whole words, including attendee addresses.
     - *amb_02 seed fix:* see the task's notes and `tool_reference.md`.
   - **Verbatim handoff (2026-09-29, after dev2t, at the user's request).**
     - *Why:* in dev2t the supervisor kept paraphrasing the request and adding its own defaults ("keep the time the same") despite a prompt rule against it.
     - *Change:* `route_to_agent` now builds the worker's first message itself (`core/agent.py`, `WORKER_HANDOFF_TEMPLATE`):
       - the user's latest message, word for word;
       - an optional `context` block, holding only data from earlier steps (the parameter used to be `message`);
       - a fixed instruction: do your part, then call `work_completion`.
     - The supervisor no longer writes instructions to workers; its prompt is updated to match.
     - *Workers:* a "Multiple-match rule (important)" near the top of every worker prompt says that when more than one item matches and a wrong pick could change, delete or send the wrong thing, change nothing and ask, naming every match.
     - *Checks:*
       - offline scripted test: exact request in both handoffs, context only when given, tool schema `agent` + optional `context`;
       - one real amb_02 run (`eval/runs/debug_handoff`) passed: the worker found both Sams, changed nothing, and asked which one.
   - **Fixes A-D after dev4/dev5 (2026-10-03, at the user's request).** dev4 (graph, Luna) scored 20/30 and dev5 (Hermes, Luna) 18/30. The graph's remaining failures had four causes:
     - *A. Recurring meetings counted as several matches (amb_02).* The multiple-match rule now says to check every result's title, description and people. Repeats of one recurring event are one meeting (normally the next occurrence).
     - *B. Decisions made from cut-off previews (tsk_01; Hermes failed too).* Each worker's look-up rule now says to open the full item before deciding from truncated text: `get_task`, `read_email`, a detailed event, a document's content, or every row it relies on.
     - *C. A stale derived total (sh_03 run 3).* The data agent now writes totals as formulas (`COUNTIFS`, `USER_ENTERED`) or recomputes them after the last change. Checked: the fake computes formulas, and the grader reads the computed values.
     - *D. Information that lives in another app (em_06; x_02 run 2).* Three parts:
       - `route_to_agent` has an optional `lookup` field. It builds a separate template, `WORKER_LOOKUP_TEMPLATE`: "find and return only this; do not create, change, send or delete anything".
       - Workers hand back with "NEED: …" instead of guessing or asking the user. A NEED is only for missing information; actions no tool can do are still reported.
       - The supervisor's "Cross-app look-up rule" sends a look-up to the likeliest app (people and lists → Sheets; checklists → Docs; what someone wrote → Gmail; meetings and leave → Calendar), routes the result back in `context`, and asks SIR only if no app has it. Questions about several matches still go to SIR. Steps are ordered by dependency (book first, then email the schedule).
     - *Checks:*
       - offline scripted test of the em_06 shape (NEED, then a look-up to Sheets, then back with context) and the tool schema (`agent`, optional `context` and `lookup`);
       - 4 Luna debug runs (`eval/runs/debug_ad`). em_06, amb_02 and tsk_01 passed. em_06 and tsk_01 had failed every run in both harnesses: em_06 used the look-up path and read the Team Directory, and tsk_01 opened the cut-off task with `get_task`.
       - x_02 failed on a model overlap mistake: Farah was busy 13:30–14:30 in the result it read, and it booked 14:00. The step order was right: the meetings were booked before a single email went out.
   - **dev6: graph, Luna, after A-D (2026-10-04, commit `767d3cb`).**
     - Score: 28/30, with 8/10 tasks passing on all 3 runs. dev4 had 20/30 and Hermes (dev5) 18/30.
     - Fixed: amb_02 1/3 → 3/3, tsk_01 0/3 → 3/3, em_06 0/3 → 2/3 and x_02 2/3 → 3/3. No task got worse.
     - Cost: input tokens per run rose from 55k to 68k (look-ups and opening full items). That is still 2.6x fewer than Hermes (180k). Wall time was unchanged at 44 s.
     - The records say `9be99b4` plus 4 uncommitted files. Those files did not change during the run and were committed unchanged right after it as `767d3cb`.
     - Two failures, both one-off slips:
       - *em_06 r3:* `batch_archive` with `{from:no-reply from:notifications}` archived 3 of the 4 notifications. GitHub's sender is `noreply@…`, and the fake reads `no-reply` as the two words "no reply" (real-Gmail behaviour for this case was not probed). The worker then "verified" with the same query.
       - *sh_03 r2:* no sheet tool deletes rows, so the worker rewrote the tab. For Karthik it combined the old row's timestamp with the new answer, so the latest row was not kept as it was.
   - **Fixes E-F and an example correction after dev6 (2026-10-04, at the user's request):**
     - *E. Gmail worker, "Bulk changes rule":* list the emails meant from the search results, compare a query-based tool's count with that list, change any missed ones by ID, and never re-run the same query as a check.
     - *F. Sheets worker, rewriting rows:* each written row comes from one row read, copied cell for cell, and only the cells the request changes may differ. Never combine rows. Compare the written rows with their sources.
     - *Correction:* fix C's example formula was copied from sh_03's own sheet (`=COUNTIFS(Responses!D:D,"Yes",Responses!E:E,"Vegetarian")`). It is replaced with a neutral `=SUM(C2:C30) or a COUNTIF/COUNTIFS formula`. Only sh_03 (a dev task) uses that sheet, so no test task is affected, but dev6's sh_03 runs had the hint. Record this in the write-up.
     - Check: the prompts format, and the offline look-up test still passes.
     - Debug runs on Luna (`eval/runs/debug_ef`):
       - em_06 3/3. The archive step matched the emails identified each time: exact sender addresses, a query whose count matched a listed set, or archives by ID.
       - sh_03 2/3. No row was combined, but r3 left out a row that was not a duplicate (Priya Raman), so the sheet had 12 rows instead of 13 and Vegan read 1 instead of 2. Its read-back showed 12 rows and it did not notice.
       - Hermes uses the same rewrite approach on sh_03; in dev5 it rewrote rows a second time in 2 of its 3 runs.
     - *F extended (2026-10-04, at the user's request), the last dev tuning before the GPT-4.1-mini dev run:*
       - First name the rows to remove and why; every other row read must be in what is written.
       - After writing, read back and check that the row count equals rows read minus rows removed, and that each written row matches its source.
       - Not given its own debug round: sh_03 runs again in the GPT-4.1-mini dev run.
10. **How the harnesses use the Responses API (Luna).**
    - Hermes sends `store: false`, `reasoning.summary: "auto"`, parallel tool calls and `tool_choice: auto`, streams, and passes Luna's encrypted reasoning back on every turn.
    - The graph (LangChain defaults) sends only `reasoning.effort`, doesn't stream, and keeps reasoning items inside the message content that the product code passes along.
11. **Snapshot reporting.** Chat completions report the snapshot served (`gpt-4.1-mini-2025-04-14`, `gpt-6-luna-2026-09-22`); the Responses API reports only the deployment name (`gpt-6-luna`).

## Luna (GPT-6 Luna)

- **Why the Responses API.** Azure rejects function tools together with any reasoning effort other than `none` on `/chat/completions` for `gpt-6-luna` ("use /v1/responses or set reasoning_effort to 'none'"). Leaving the setting out fails too, because the model's default isn't `none`. On 2026-09-28 the user chose the Responses API at effort `medium` for both harnesses, and renamed the model from "GPT-5.6 Luna" to GPT-6 Luna.
- **Cache writes.** Azure now reports cache-write tokens. The relay records them (`cache_write_tokens`), in case Luna's pricing charges for them.
- **Smoke runs (cal_02, 1 each, both failed as agents):**
  - Graph: 4 model calls and 6 tool calls, 259 reasoning tokens. The context trim wiped the planning agent's history. After the trim was removed (item 9), the graph passed cal_02 on Luna.
  - Hermes: 9 model calls and 8 tool calls, 750 reasoning tokens. It booked Wed 14 Oct 10:15, the second-earliest slot; the unique earliest is Tue 13 Oct 16:00.
  - In both, the relay's token counts equal the harness's own, and the settings check is clean.

## First real runs (cal_02, GPT-4.1-mini, 1 run each)

Both failed, for reasons in the agents themselves; the adapters worked as intended.
- **Graph (2 model calls, 0 tool calls):** the planning agent asked the user for the three email addresses instead of looking them up (`asked_unnecessarily`).
- **Hermes (4 model calls, 5 tool calls):** it took "next week" as 11–17 Oct (a Sunday start), called 11 Oct a Monday, and asked before booking.

## Still open

- **Luna prices:** still needed; `cost_usd` stays empty for Luna until they are in `config.json`.
- **LLM judge:** needed for the amb/imp tasks before the dev run, since amb_02 and imp_01 are dev tasks.
- **Hermes pin:** confirm `d0288be5b3` (it's in the config; the checkout also carries a local `pyproject.toml` edit that relaxes Python-version markers).
