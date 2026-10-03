"""Summary of a records.jsonl: pass rates, consistency, cost and behaviour per harness x model.

    .venv/Scripts/python.exe eval/harness/report.py eval/runs/dev1/records.jsonl

Undecided runs (judge error) count as not passed and are listed separately. Runs whose server or
relay never started (failure_category infra_error) are left out and listed. Consistency is
the number of tasks passed on every run. Cost per success is total cost / passed runs.
A run recorded twice (the same task, harness, model and run number) is counted once, from its
last line, with a warning.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def mean(xs: list) -> float:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else 0.0


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "eval/runs/dev1/records.jsonl")
    lines = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    latest = {}  # one record per run: a later line for the same run replaces the earlier one
    for r in lines:
        latest[(r["task_id"], r["harness"], r["model"], r["run"])] = r
    all_recs = list(latest.values())
    if len(all_recs) < len(lines):
        dupes = sorted(k for k, n in Counter((r["task_id"], r["harness"], r["model"], r["run"]) for r in lines).items() if n > 1)
        print(f"WARNING: {len(lines) - len(all_recs)} duplicate record line(s); counting only the last line for {dupes}\n")
    infra = [r for r in all_recs if r.get("failure_category") == "infra_error"]
    recs = [r for r in all_recs if r.get("failure_category") != "infra_error"]
    if infra:
        print(f"Left out, the harness never ran (server/relay didn't start; re-run with runner.py --redo-infra): "
              f"{[(r['task_id'], r['harness'], r['model'], r['run']) for r in infra]}\n")
    cells = defaultdict(list)
    for r in recs:
        cells[(r["harness"], r["model"])].append(r)
    tasks = sorted({r["task_id"] for r in recs})

    print(f"{len(recs)} runs from {path}\n")
    print(f"{'harness':7s} {'model':13s} {'pass':>9s} {'consist.':>9s} {'steps':>6s} {'tools':>6s} {'in tok':>8s} {'out tok':>8s} {'$/run':>8s} {'$/pass':>8s} {'wall s':>7s}")
    for (harness, model), rs in sorted(cells.items()):
        passed = sum(r["passed"] is True for r in rs)
        by_task = defaultdict(list)
        for r in rs:
            by_task[r["task_id"]].append(r["passed"] is True)
        consistent = sum(all(v) for v in by_task.values())
        costs = [r["cost_usd"] for r in rs if r["cost_usd"] is not None]
        total = sum(costs) if costs else None
        per_run = f"{total / len(costs):.4f}" if costs else "?"
        per_pass = f"{total / passed:.4f}" if costs and passed else "-"
        print(f"{harness:7s} {model:13s} {passed:>3d}/{len(rs):<3d}{100 * passed / len(rs):3.0f}% {consistent:>3d}/{len(by_task):<3d}   "
              f"{mean([r['n_steps'] for r in rs]):6.1f} {mean([r['n_tool_calls'] for r in rs]):6.1f} {mean([r['input_tokens'] for r in rs]):8.0f} "
              f"{mean([r['output_tokens'] for r in rs]):8.0f} {per_run:>8s} {per_pass:>8s} {mean([r['wall_s'] for r in rs]):7.1f}")

    print("\nPer task (runs passed):")
    keys = sorted(cells)
    print(f"{'task':8s} {'diff':8s} " + " ".join(f"{h[:6]}/{m[:9]:9s}" for h, m in keys))
    for t in tasks:
        diff = next(r["difficulty"] for r in recs if r["task_id"] == t)
        row = []
        for k in keys:
            rs = [r for r in cells[k] if r["task_id"] == t]
            row.append(f"{sum(r['passed'] is True for r in rs)}/{len(rs)}".ljust(16) if rs else "-".ljust(16))
        print(f"{t:8s} {diff:8s} " + " ".join(row))

    print("\nStop reasons:", dict(Counter((r["harness"], r["stop_reason"]) for r in recs)))
    warn = [r for r in recs if not r["fairness"]["ok"]]
    print(f"Fairness warnings: {len(warn)} run(s)")
    for r in warn[:10]:
        print(f"  {r['task_id']} {r['harness']} {r['model']} r{r['run']}: {r['fairness']['warnings'][:2]}")
    errs = [r for r in recs if r["errors"]]
    print(f"Runs with errors: {len(errs)}")
    for r in errs[:10]:
        print(f"  {r['task_id']} {r['harness']} {r['model']} r{r['run']}: {r['errors'][0][:150]}")
    undecided = [r for r in recs if r["passed"] is None]
    if undecided:
        print(f"Undecided (judge error): {[(r['task_id'], r['harness'], r['run']) for r in undecided]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
