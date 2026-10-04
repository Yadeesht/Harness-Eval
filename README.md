# Harness Eval: a routed LangGraph agent vs Hermes

Does a routed multi-agent harness let a cheap model do real workspace work well, and how does it compare to a generic agent harness?

This repo measures that. It runs my agent's graph (from **[Personal-Assistant-Agent](https://github.com/Yadeesht/Personal-Assistant-Agent)**) and [Hermes Agent](https://github.com/NousResearch/hermes-agent) on the same 30 held-out Google Workspace tasks, with the same model, tools, data and limits. Only the harness differs.

## Result

GPT-6 Luna (reasoning effort medium), 30 test tasks × 3 runs per harness, frozen at tag `phase5-freeze`:

| | Routed graph | Hermes |
|---|---|---|
| **Runs passed** | **79/90 (88%)** | **80/90 (89%)** |
| Tasks passed on all 3 runs | 24/30 | 23/30 |
| Cost per successful run | **$0.0022** | $0.0041 |
| Input tokens per run | **48.5k** | 120k |
| Wall time per run | **36.6 s** | 42.6 s |

- **Tied on success.** The 95% confidence intervals (79–93% and 81–94%) overlap almost completely.
- **The graph is about 2x cheaper.** It used fewer input tokens on 29 of 30 tasks, because each worker sees only its own app's tools and results.
- **Different failures:**
  - the graph missed checks that span two apps (it sent emails with a doc's dates that a newer email had changed) and some calendar rules;
  - Hermes booked over clashes it had already read, and misreported two doc edits.
- **Tuning on dev did not transfer.** After tuning on the 10 dev tasks the graph led 28/30 to 18/30 there, but not on the held-out test set.
- **Extreme tasks decide it.** Both harnesses score 95% or more on medium and hard tasks and 62% on extreme ones.

Full numbers, failures and limitations: **[eval/design/writeup.md](eval/design/writeup.md)**. Example traces: [phase5_findings.md](eval/design/phase5_findings.md).

## Approach

- **A fake Google Workspace, built to behave like the real one.** An MCP server runs my agent's real Gmail, Calendar, Tasks, Docs and Sheets tool code over an in-memory workspace. Search, truncation and formatting were copied from probes of a real dummy account. Every run starts from the same seeded fake company.
- **40 tasks, 10 dev and 30 test**, all medium, hard or extreme.
  - They cover multi-step and cross-app work, plus traps: two people with the same name, cut-off notes, stale docs, holidays, ambiguous and impossible requests.
  - Each task is proven before any agent runs: its scripted correct path passes, doing nothing fails, and taking the trap fails.
- **Fairness.** One shared config and a settings hash on every record.
  - A local relay holds the API key, logs every model call and audits what reaches the API.
  - No memory carries over between runs; the tool-call cap is enforced in the server.
  - Hermes runs as shipped, pinned to one commit.
- **Grading.**
  - State checks against a diff of the starting state: any change the task doesn't allow fails the run.
  - An LLM judge (Luna) grades only the final message, on ambiguous and impossible tasks. It is calibrated at 88% agreement with hand labels.
- **Discipline.** All tuning happened on the dev tasks. The test tasks were frozen and tagged before the test run, and every change made after it is reported separately.

## Repo map

| Path | What it is |
|---|---|
| `eval/design/` | **Start here.** The write-up, findings, the fake company spec (`world.md`), the task catalogue, the real-tool probes (`tool_reference.md`), harness setup and differences (`harness_notes.md`) and judge calibration. |
| `eval/tasks/`, `eval/golden/` | The 40 task files, and the scripted correct and trap paths for each. |
| `eval/seed/` | Builds and checks the fake company the tasks run against. |
| `eval/lab/` | The fake Workspace server and Google API fakes. |
| `eval/probe/` | Probes of the real dummy account, used to make the fake behave like Google. |
| `eval/grade/` | Grader, state diff, shared normalizer, LLM judge and calibration. |
| `eval/harness/` | Shared config, LLM relay, the two adapters, runner, report and analysis. |
| `core/`, `config/`, `app_tools/`, `main.py` | The agent under test: a trimmed copy of [Personal-Assistant-Agent](https://github.com/Yadeesht/Personal-Assistant-Agent). |
| `AGENTS.md` | Project rules and the full phase-by-phase log. |

## Run it

```powershell
.venv\Scripts\python.exe eval\validate.py                                   # prove all 40 tasks
.venv\Scripts\python.exe eval\harness\runner.py --tasks <ids> --harnesses graph hermes --models gpt-6-luna --runs 3 --out eval\runs\<name> --yes
.venv\Scripts\python.exe eval\harness\report.py  eval\runs\<name>\records.jsonl
.venv\Scripts\python.exe eval\harness\analyze.py eval\runs\<name>\records.jsonl
```

The Azure endpoint and key come from environment variables only (see `.env.example`). Hermes needs its own venv and the pinned checkout; see `eval/design/harness_notes.md`.
