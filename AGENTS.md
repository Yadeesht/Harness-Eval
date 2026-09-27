# AGENTS.md — Harness Evaluation Project

## Objective

Answer one question with numbers:

> **Does my routed LangGraph harness let a cheap model perform well, and how does it compare to Hermes, a generic agent harness, on realistic workspace tasks?**

This is an evaluation project, not a feature project. The deliverable is a trustworthy measurement plus a write-up. Trustworthiness beats speed: if a shortcut could make results unfair or unreproducible, don't take it.

## Experimental design

- **Harnesses (the variable):** (1) my LangGraph routed/supervisor graph, (2) Hermes Agent (NousResearch), pinned to one commit.
- **Models:** GPT-4.1-mini (old cheap model) and GPT-5.6 Luna (current-generation cheap model). Framing is "old cheap vs current generation".
- **Tasks:** 40 workspace tasks (email, calendar, docs, sheets, cross-app). 10 **dev**, 30 **test**.
- **Runs:** 3 runs per task per harness per model.
- **Two layers:**
  - **Lab:** fake workspace MCP server. The full matrix runs here.
  - **Field (optional, small):** ~10 tasks on real Google accounts, sequential, with a reset script. Measures real latency and real-world failures only.

## Fairness rules (never break these)

Only the harness may differ between compared runs. Everything else is identical:

- same tools (same names, parameters, descriptions), same MCP server
- same model, same endpoint, same temperature (both send the same value, or both send none), same reasoning effort for Luna
- same step limit, same tool timeout, same tool-call cap (enforced in the server, not the harness)
- same starting state (fresh seed every run), same frozen date and user context (read from the task file)
- **no memory across runs:** Hermes memory/skills/background review off with a fresh `HERMES_HOME` per run; **my graph's memory layer (episodic RAG + KuzuDB) disabled or wiped before every run**

All shared settings live in **one config file both adapters read**. Never hardcode a setting in one adapter only.

Hermes' default **tool search** (MCP tools hidden behind `tool_search` / `tool_describe` / `tool_call`) stays **ON** in the main experiment: we compare harnesses as they ship. Tool search OFF is an optional ablation on dev tasks only.

## Dev/test discipline

- All debugging, prompt tweaks and calibration happen on **dev** tasks only.
- **Test tasks are frozen** tasks, prompts, settings, Hermes commit. Do not edit them.
- If anything changes after test results are seen, it must be recorded in the write-up.

## Components

| Component | Role |
|---|---|
| Fake workspace MCP server | In-memory workspace. Logs every call, enforces the tool-call cap, writes full state to disk after every call. Fault-injection hooks exist but are OFF by default. |
| Shared seed | One fake company (people, weeks of calendar, realistic inbox, a few docs/sheets). All tasks run against it; small per-task additions only when needed. |
| Task files | One file per task (format below). |
| Golden-path scripts | Per task: call the tools directly in the correct order; the grader must PASS. |
| Do-nothing check | Per task: no tool calls; the grader must FAIL. |
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
  "difficulty": "easy | medium | hard",
  "category": "email | calendar | docs | sheets | cross_app | ambiguous | impossible",
  "field": false,
  "context": "You are an assistant acting for <user> (<email>). The current date and time is <frozen date>.",
  "prompt": "...",
  "seed_additions": {},
  "expect": { "state": {}, "forbidden": [] }
}
```

Every piece of information the agent needs must be **discoverable through the tools** (the prompt may point to an email; the answer must be findable by searching/reading).

Hard-task patterns to include: long horizon (10–15 tool calls), cross-app chains, distractors (two people with the same first name, similar event titles, large inbox with pagination), constraints and exceptions ("everyone except…", "no double-booking"), ambiguous requests (correct behavior: ask), impossible or conflicting requests (correct behavior: report, not force).

## Per-run record (JSONL, one line per run)

`task_id, split, harness, model, run, settings_hash, trajectory (messages, tool calls with args, tool results), final_state, passed, failed_checks, input_tokens, output_tokens, cache_read_tokens, reasoning_tokens, cost_usd, llm_latency_s, wall_s, n_tool_calls, n_steps, errors, failure_category`

Seed failure categories (extend from evidence, don't guess): `wrong_tool`, `bad_args`, `premature_finish`, `loop`, `lost_context`, `didnt_ask`, `forced_impossible`, `env_error` (field layer only).

## Metrics to report

Success rate per harness × model · consistency (tasks passed on all 5 runs) · cost per *successful* task · steps and tool calls per task · latency (lab LLM latency + measured real tool latency × tool calls) · results by category and difficulty · failure distribution · judge agreement.

## Hermes facts (verified in the spike)

- Driven via `AIAgent` from `run_agent.py`, not the CLI. **One Hermes process per run** (its MCP client is process-wide).
- Separate venv (Hermes pins its own `openai`/`mcp` versions); install with the `[mcp]` extra or MCP is silently skipped.
- Isolation settings: `skip_memory=True`, `skip_context_files=True`, `skip_background_review=True`, `enabled_toolsets=["mcp-workspace"]`, fresh temp `HERMES_HOME`, `HERMES_TIMEZONE`, frozen `hermes_time.now`, `session_id` built from the frozen date, context via `ephemeral_system_prompt`.
- Reasoning effort via `reasoning_config`; temperature via `request_overrides`.
- `register_mcp_servers` lives in `tools.mcp_tool_discovery` (older commits: `tools.mcp_tool`).
- Tools are exposed as `mcp__workspace__<tool>`; with tool search on, the model initially sees only `tool_search`, `tool_describe`, `tool_call`.
- **Circuit breaker:** after 3 consecutive tool errors Hermes tells the model the server is unreachable (60s cooldown). Matters for fault injection; document how each harness handles it.
- Spike result: all isolation checks passed. Spike tasks are discarded; do not reuse them.

## Phases and status

- [x] **Spike:** Hermes runs isolated and fair against a fake server
- [ ] **1. Environment:** realistic search, real tool schemas copied, shared seed. *Done when a golden path passes on the new server.*
- [ ] **2. Validate 40 tasks:** golden path PASS + do-nothing FAIL for every task. *Fix or drop failures.*
- [ ] **3. Adapters:** both harnesses behind one interface and one config; graph memory disabled. *Done when both produce identical-format records on one dev task.*
- [ ] **4. Dev run:** 10 dev tasks × 2 harnesses × GPT-4.1-mini × 5 runs. Check ceiling effect, build failure categories from traces, measure cost.
- [ ] **5. Test run:** freeze everything; 30 test tasks × 2 harnesses × 2 models × 5 runs. Verify Luna's reasoning setting on its first run.
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
