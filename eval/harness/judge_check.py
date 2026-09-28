"""Sanity check for the LLM judge: golden final messages must PASS, negative ones must FAIL.

    .venv/Scripts/python.exe eval/harness/judge_check.py

Uses the final messages written by eval/validate.py (eval/runs/validate/<task>/<path>/grade.json)
for every task with a judge rubric. This is not the calibration AGENTS.md asks for (that uses
~20 hand-labelled messages from real runs); it only proves the judge can tell the scripted
right answer from the scripted trap. Exits non-zero on any disagreement.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import EVAL, TASKS_DIR, load_config, load_json  # noqa: E402
from runner import Judge  # noqa: E402


def main() -> int:
    config = load_config()
    out = EVAL / "runs" / "judge_check"
    judge = Judge(config, out)
    bad = 0
    try:
        for path in sorted(TASKS_DIR.glob("*.json")):
            task = load_json(path)
            if not task["expect"].get("judge"):
                continue
            for name, want in (("golden", "PASS"), ("negative", "FAIL")):
                graded = EVAL / "runs" / "validate" / task["id"] / name / "grade.json"
                if not graded.exists():
                    print(f"{task['id']:7s} {name:8s} no validate output (run eval/validate.py first)")
                    bad += 1
                    continue
                message = load_json(graded).get("final_message", "")
                run_dir = out / task["id"] / name
                run_dir.mkdir(parents=True, exist_ok=True)
                got = judge.verdict(run_dir, task, message)
                ok = got["verdict"] == want
                bad += not ok
                print(f"{task['id']:7s} {name:8s} want {want} got {got['verdict']:5s} {'ok ' if ok else 'BAD'} {got.get('reason', '')[:110]}")
    finally:
        judge.stop()
    print(f"\n{'judge agrees with every scripted answer' if not bad else f'{bad} disagreement(s)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
