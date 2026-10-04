"""Read-only analysis of a records.jsonl for the write-up (never changes a verdict).

    .venv/Scripts/python.exe eval/harness/analyze.py eval/runs/phase5/records.jsonl

1. Tool calls per harness: the workspace calls each model *attempted* versus the calls that
   *reached* the server. Hermes checks arguments inside its `tool_call` bridge, so a rejected
   call never reaches the server and never counts toward the cap; the graph's calls all reach
   it (harness_notes.md item 2). Harness overhead (routing, tool search) is counted separately.
2. Passing normal-task runs whose final message ends with a question. Reported only: the
   grader fails "asked instead of doing the work" through the state checks, and a question
   after finished work is an offer, not a failure.
3. Failure pre-labels: a proposed failure_category for every failed run, from its failed
   checks and final message, written to failure_labels.csv next to the records. These are
   suggestions to confirm against the traces (column "final_label"), not results.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROUTING = {"route_to_agent", "work_completion"}  # graph overhead
DISCOVERY = {"tool_search", "tool_describe"}  # Hermes overhead
INCOMPLETE = ("is still", "is unread", "not changed", "no new", "no row matches", "missing", "lacks", "status needsaction",
              "hidden=false", "expected 1", "data rows, expected")


def load(path: Path) -> list[dict]:
    latest = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            latest[(r["task_id"], r["harness"], r["model"], r["run"])] = r
    return [r for r in latest.values() if r.get("failure_category") != "infra_error"]


def tool_counts(r: dict) -> tuple[int, int]:
    """(attempted workspace calls, overhead calls) from the model's own tool calls."""
    attempted = overhead = 0
    for m in r["trajectory"]["messages"]:
        for tc in m.get("tool_calls") or []:
            name = tc["name"]
            if name in ROUTING or name in DISCOVERY:
                overhead += 1
            elif name == "tool_call":  # Hermes bridge: one call can carry several workspace calls
                calls = (tc.get("args") or {}).get("calls")
                attempted += len(calls) if isinstance(calls, list) else 1
            else:
                attempted += 1
    return attempted, overhead


def prelabel(r: dict) -> tuple[str, str]:
    checks = [c.lower() for c in r["failed_checks"]]
    message = (r.get("final_message") or "").strip()
    # "<mail> is read" means mail the task said to leave unread was marked read
    unwanted = [c for c in checks if c.startswith("[unexpected change]") or "forbidden" in c or c.startswith("[sent]")
                or c.endswith(" is read")]
    if r["stop_reason"] != "completed" or any("capped" in c or "cap " in c for c in checks):
        return "loop", f"stopped: {r['stop_reason']}"
    if r["category"] == "ambiguous":
        if unwanted:
            return "didnt_ask", "changed something on an ambiguous task (guessed)"
        if not message.endswith("?") and "?" not in message:
            return "didnt_ask", "no question in the final message"
        return "wrong_options", "asked, but did not name the real options"
    if r["category"] == "impossible":
        if unwanted:
            return "forced_impossible", "made a change the task does not allow"
        return "misreported_impossible", "the judge or a message check failed the report"
    if unwanted:
        return "unwanted_change", "changed or sent something outside the task"
    if message.endswith("?"):
        return "asked_unnecessarily", "ended with a question and the work is not done"
    if checks and all(any(k in c for k in INCOMPLETE) for c in checks):
        return "premature_finish", "required changes missing; nothing extra changed"
    return "wrong_result", "a required item has wrong content (values, times, rows)"


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "eval/runs/phase5/records.jsonl")
    recs = load(path)
    print(f"{len(recs)} runs from {path}\n")

    print("1. Workspace tool calls per run (mean)")
    print(f"   {'harness':8s} {'attempted':>9s} {'reached':>8s} {'not reached':>11s} {'overhead':>9s}")
    by_h = defaultdict(list)
    for r in recs:
        by_h[r["harness"]].append(r)
    for h, rs in sorted(by_h.items()):
        att = [tool_counts(r) for r in rs]
        a = sum(x for x, _ in att) / len(rs)
        reached = sum(r["n_tool_calls"] for r in rs) / len(rs)
        o = sum(y for _, y in att) / len(rs)
        print(f"   {h:8s} {a:9.1f} {reached:8.1f} {a - reached:11.1f} {o:9.1f}")

    print("\n2. Passing normal-task runs whose final message ends with a question")
    for h, rs in sorted(by_h.items()):
        q = [r for r in rs if r["passed"] and r["category"] not in ("ambiguous", "impossible")
             and (r.get("final_message") or "").strip().endswith("?")]
        normal = sum(1 for r in rs if r["passed"] and r["category"] not in ("ambiguous", "impossible"))
        print(f"   {h:8s} {len(q)} of {normal}" + "".join(f"\n      {r['task_id']} r{r['run']}: ...{r['final_message'].strip()[-120:]}" for r in q))

    failed = [r for r in recs if r["passed"] is False]
    out = path.with_name("failure_labels.csv")
    counts = defaultdict(lambda: defaultdict(int))
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task", "harness", "run", "category", "proposed_label", "why", "failed_checks", "final_message_end", "final_label"])
        for r in sorted(failed, key=lambda r: (r["task_id"], r["harness"], r["run"])):
            label, why = prelabel(r)
            counts[r["harness"]][label] += 1
            w.writerow([r["task_id"], r["harness"], r["run"], r["category"], label, why, " | ".join(r["failed_checks"])[:600],
                        (r.get("final_message") or "").strip()[-200:], ""])
    print(f"\n3. Failure pre-labels ({len(failed)} failed runs) -> {out}")
    for h, c in sorted(counts.items()):
        print(f"   {h:8s} " + ", ".join(f"{k} {v}" for k, v in sorted(c.items(), key=lambda kv: -kv[1])))
    print("   Proposed labels only: confirm each against its trace in the final_label column.")

    print("\n4. Pass rate by category, difficulty and trap pattern (runs passed / runs)")
    tasks_dir = Path(__file__).resolve().parents[1] / "tasks"
    patterns = {r["task_id"]: json.loads((tasks_dir / f"{r['task_id']}.json").read_text(encoding="utf-8"))["patterns"] for r in recs}
    harnesses = sorted(by_h)
    for title, keys_of in (("category", lambda r: [r["category"]]), ("difficulty", lambda r: [r["difficulty"]]),
                           ("pattern", lambda r: patterns[r["task_id"]])):
        cells = defaultdict(lambda: defaultdict(lambda: [0, 0, set()]))
        for r in recs:
            for k in keys_of(r):
                c = cells[k][r["harness"]]
                c[0] += r["passed"] is True
                c[1] += 1
                c[2].add(r["task_id"])
        print(f"   {title:22s} " + " ".join(f"{h:>14s}" for h in harnesses) + "   tasks")
        for k in sorted(cells):
            row = cells[k]
            n_tasks = len(set().union(*(row[h][2] for h in harnesses)))
            print(f"   {k:22s} " + " ".join(f"{row[h][0]:>5d}/{row[h][1]:<3d}{100 * row[h][0] / row[h][1]:4.0f}%" if row[h][1] else f"{'-':>14s}" for h in harnesses)
                  + f"   {n_tasks}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
