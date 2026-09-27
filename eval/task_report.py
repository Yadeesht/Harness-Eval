"""Task-set report from the last validation run (eval/runs/validate).

    .venv/Scripts/python.exe eval/task_report.py

Checks every task file for the shared format (context sentence, fields, split and
difficulty totals) and compares each task's `apps` with the apps its golden path
actually called. Prints golden tool-call counts next to the difficulty rubric
(AGENTS.md: medium 4-8, hard 8-15 or 3 hops, extreme 15+ or 4+ hops); hops are
judged by hand, so a count outside the band is flagged for review, not failed.
Exits non-zero on format or apps mismatches.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

EVAL = Path(__file__).resolve().parent
TASKS = EVAL / "tasks"
RUNS = EVAL / "runs" / "validate"
CONTEXT_END = "Weeks start on Monday. Working hours are 10:00–18:00 IST, Monday to Friday."
FIELDS = ["id", "split", "difficulty", "category", "apps", "patterns", "field", "context", "prompt", "seed_additions", "expect"]
BANDS = {"medium": (4, 8), "hard": (8, 15), "extreme": (15, 99)}
EXPECTED = {"total": {"medium": 10, "hard": 20, "extreme": 10}, "dev": {"medium": 3, "hard": 4, "extreme": 3}}


MODULE_APP = {"gmail_tools": "gmail", "gdocs_tools": "docs", "gtask_tools": "tasks", "gsheet_tools": "sheets", "calendar_tools": "calendar"}


def tool_apps() -> dict[str, str]:
    """Tool name -> app, from the module each real tool lives in (comment tools by name)."""
    sys.path.insert(0, str(EVAL))
    from lab.bind import all_tools

    out = {}
    for t in all_tools():
        module = t.coroutine.__module__.rsplit(".", 1)[-1]
        out[t.name] = MODULE_APP.get(module) or ("sheets" if "spreadsheet" in t.name else "docs")
    return out


def main() -> int:
    apps_of = tool_apps()
    problems, rows = [], []
    by_split = {"dev": Counter(), "test": Counter(), "total": Counter()}
    for path in sorted(TASKS.glob("*.json")):
        task = json.loads(path.read_text(encoding="utf-8"))
        tid = task["id"]
        missing = [f for f in FIELDS if f not in task]
        if missing:
            problems.append(f"{tid}: missing {missing}")
        if tid != path.stem:
            problems.append(f"{tid}: file name {path.name}")
        if not task["context"].endswith(CONTEXT_END):
            problems.append(f"{tid}: context does not end with the shared sentence")
        by_split[task["split"]][task["difficulty"]] += 1
        by_split["total"][task["difficulty"]] += 1
        log = RUNS / tid / "golden" / "calls.jsonl"
        calls = [json.loads(l) for l in log.open(encoding="utf-8")] if log.exists() else []
        used = sorted({apps_of.get(c["tool"], "?") for c in calls})
        if sorted(task["apps"]) != used:
            problems.append(f"{tid}: apps {sorted(task['apps'])} but golden used {used}")
        lo, hi = BANDS[task["difficulty"]]
        flag = "" if lo <= len(calls) <= hi else f"outside {lo}-{hi}"
        rows.append((tid, task["split"], task["difficulty"], task["category"], len(calls), len(task["patterns"]), flag))
    print(f"{'task':8s} {'split':5s} {'difficulty':10s} {'category':11s} calls traps  note")
    for r in rows:
        print(f"{r[0]:8s} {r[1]:5s} {r[2]:10s} {r[3]:11s} {r[4]:5d} {r[5]:5d}  {r[6]}")
    for split in ("total", "dev"):
        got = {d: by_split[split][d] for d in BANDS}
        if got != EXPECTED[split]:
            problems.append(f"{split} split {got} != {EXPECTED[split]}")
    print(f"\ndev {dict(by_split['dev'])}  test {dict(by_split['test'])}  total {dict(by_split['total'])}")
    print("\n" + ("\n".join(problems) if problems else "format, apps and split totals OK"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
