"""Judge calibration (AGENTS.md: ~20 hand labels, target >= 80% agreement). Dev runs only.

    .venv/Scripts/python.exe eval/grade/calibrate.py sheet     # build the labelling sheet
    .venv/Scripts/python.exe eval/grade/calibrate.py score     # after you fill in the "label" column

Items are the final messages of dev runs on tasks with a judge rubric (amb_02, imp_01), one per
distinct message. In grading the judge only sees messages that passed every code check, and on
the dev runs it said PASS to all of those, so the sheet also takes messages from failed runs
and judges them here (the same judge, settings and prompt), to test the FAIL side too.

The sheet (eval/design/judge_calibration/sheet.csv) shows the rubric, the request and the
message, never the judge's verdict; the verdicts are in key.json next to it. Label each row
PASS or FAIL by the rubric alone, then run "score".
"""

from __future__ import annotations

import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
from common import EVAL, TASKS_DIR, load_config, load_json, write_json  # noqa: E402
from runner import Judge  # noqa: E402

OUT = EVAL / "design" / "judge_calibration"
SHEET, KEY = OUT / "sheet.csv", OUT / "key.json"
WORK = EVAL / "runs" / "judge_calibration"  # judge calls and their cache
NOT_DEV = {"phase5", "validate", "judge_check", "judge_calibration"}
PER_VERDICT = 12  # up to 12 judge-PASS and 12 judge-FAIL items


def judge_tasks() -> dict[str, dict]:
    tasks = {}
    for path in TASKS_DIR.glob("*.json"):
        task = load_json(path)
        if task["split"] == "dev" and task["expect"].get("judge"):
            tasks[task["id"]] = task
    return tasks


def collect(tasks: dict[str, dict]) -> list[dict]:
    seen, items = set(), []
    for rec_path in sorted((EVAL / "runs").glob("*/*/*/*/run*/record.json")):
        if rec_path.parts[-6] in NOT_DEV:
            continue
        rec = load_json(rec_path)
        message = (rec.get("final_message") or "").strip()
        if rec["task_id"] not in tasks or not message or message in seen:
            continue
        seen.add(message)
        items.append({"source": str(rec_path.parent.relative_to(EVAL / "runs")), "task_id": rec["task_id"],
                      "harness": rec["harness"], "model": rec["model"], "run_passed": rec["passed"], "message": message})
    return items


def make_sheet() -> int:
    tasks = judge_tasks()
    items = collect(tasks)
    judge = Judge(load_config(), WORK)
    try:
        for i, item in enumerate(items):
            run_dir = WORK / "items" / f"{i:03d}"
            run_dir.mkdir(parents=True, exist_ok=True)
            v = judge.verdict(run_dir, tasks[item["task_id"]], item["message"])
            item["judge"], item["judge_reason"] = v["verdict"], v.get("reason", "")
    finally:
        judge.stop()
    by_verdict = defaultdict(list)
    for item in items:
        by_verdict[item["judge"]].append(item)
    rng = random.Random(20261004)
    chosen = []
    for verdict in ("PASS", "FAIL"):
        group = by_verdict[verdict]
        rng.shuffle(group)
        chosen += group[:PER_VERDICT]
    rng.shuffle(chosen)  # so the order gives nothing away
    OUT.mkdir(parents=True, exist_ok=True)
    with SHEET.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "task", "rubric", "user_request", "final_message", "label", "comment"])
        for n, item in enumerate(chosen, 1):
            task = tasks[item["task_id"]]
            item["id"] = f"c{n:02d}"
            w.writerow([item["id"], item["task_id"], task["expect"]["judge"], task["prompt"], item["message"], "", ""])
    write_json(KEY, chosen)
    other = {k: len(v) for k, v in by_verdict.items() if k not in ("PASS", "FAIL")}
    print(f"{len(items)} distinct dev messages; judge PASS {len(by_verdict['PASS'])}, FAIL {len(by_verdict['FAIL'])}"
          + (f", other {other}" if other else ""))
    print(f"sheet: {SHEET.relative_to(EVAL.parent)} ({len(chosen)} rows). Fill 'label' with PASS or FAIL, then run: calibrate.py score")
    return 0


def score() -> int:
    key = {item["id"]: item for item in load_json(KEY)}
    with SHEET.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    labelled = [r for r in rows if r["label"].strip().upper() in ("PASS", "FAIL")]
    if not labelled:
        print("no labels yet: fill the 'label' column with PASS or FAIL")
        return 1
    agree, confusion = 0, defaultdict(int)
    for r in labelled:
        item, human = key[r["id"]], r["label"].strip().upper()
        confusion[(human, item["judge"])] += 1
        if human == item["judge"]:
            agree += 1
        else:
            print(f"DISAGREE {r['id']} {item['task_id']} ({item['harness']}, {item['model']}): you {human}, judge {item['judge']}")
            print(f"    judge: {item['judge_reason']}")
            print(f"    message: {item['message'][:300]}")
    rate = agree / len(labelled)
    print(f"\nagreement {agree}/{len(labelled)} = {rate:.0%} (target >= 80%); {len(rows) - len(labelled)} row(s) unlabelled")
    print("you/judge counts:", {f"{h}/{j}": n for (h, j), n in sorted(confusion.items())})
    return 0 if rate >= 0.8 else 2


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "sheet":
        sys.exit(make_sheet())
    if command == "score":
        sys.exit(score())
    print(__doc__)
    sys.exit(1)
