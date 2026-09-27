"""Compare a fake-workspace probe run with a real one, call by call.

Both logs come from probe_tools.py (the fake one with --fake). Calls are paired
by (tool, note, occurrence). IDs, timestamps, addresses, probe tags and
latency are masked, so what remains is the text the agent would see.

    .venv/Scripts/python.exe eval/probe/compare.py [real.jsonl] [fake.jsonl]

Defaults: the newest full real log and the newest fake log.
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).parent / "out"

MASKS = [
    (re.compile(r"prb[a-z]{6}", re.I), "<tag>"),
    (re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"), "<email>"),
    (re.compile(r"https?://\S+?(?=[\s\"',)\]}]|$)"), "<url>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?"), "<ts>"),
    (re.compile(r"\w{3}, \d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2} [+-]\d{4}"), "<date>"),
    (re.compile(r"\b(Label_\d+|r-?\d{6,}|AAA[A-Za-z0-9_-]{7,9}|kix\.[a-z0-9]+)\b"), "<id>"),
    (re.compile(r"\b[A-Za-z0-9_-]{20,}\b"), "<id>"),
    (re.compile(r"\b[0-9a-f]{16}\b"), "<id>"),
    (re.compile(r"\b[0-9a-v]{26}\b"), "<id>"),
    (re.compile(r"\b\d{9,10}\b"), "<n>"),
]


def mask(text: str) -> str:
    for pattern, repl in MASKS:
        text = pattern.sub(repl, text)
    return text


def load(path: Path) -> dict:
    out, seen = {}, defaultdict(int)
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        key = (r["app"], r["tool"], r["note"])
        seen[key] += 1
        res = r["result"] if r["result"] is not None else f"RAISED {r['raised']}"
        text = res if isinstance(res, str) else json.dumps(res, ensure_ascii=False, sort_keys=True)
        try:  # JSON strings: normalise key order
            text = json.dumps(json.loads(text), ensure_ascii=False, sort_keys=True)
        except (ValueError, TypeError):
            pass
        out[key + (seen[key],)] = mask(text.replace("\\n", "\n"))
    return out


def newest(pattern: str, skip_fake: bool) -> Path:
    logs = [p for p in OUT.glob(pattern) if not (skip_fake and p.name.startswith("fake_"))]
    logs = [p for p in logs if sum(1 for _ in p.open(encoding="utf-8")) > 150] if skip_fake else logs
    return max(logs, key=lambda p: p.stat().st_mtime)


def main() -> int:
    real_path = Path(sys.argv[1]) if len(sys.argv) > 1 else newest("prb*.jsonl", True)
    fake_path = Path(sys.argv[2]) if len(sys.argv) > 2 else newest("fake_prb*.jsonl", False)
    real, fake = load(real_path), load(fake_path)
    print(f"real: {real_path.name}  fake: {fake_path.name}\n")
    same = differ = 0
    by_app = defaultdict(lambda: [0, 0])
    for key in sorted(set(real) & set(fake), key=lambda k: (k[0], k[1], k[2], k[3])):
        if real[key] == fake[key]:
            same += 1
            by_app[key[0]][0] += 1
            continue
        differ += 1
        by_app[key[0]][1] += 1
        print(f"--- {key[0]}.{key[1]} [{key[2]}] #{key[3]}")
        for line in difflib.unified_diff(real[key].splitlines(), fake[key].splitlines(), "real", "fake", lineterm="", n=0):
            if not line.startswith(("---", "+++", "@@")):
                print("   " + line[:220])
    only_real = sorted(set(real) - set(fake))
    only_fake = sorted(set(fake) - set(real))
    print(f"\nidentical: {same}   different: {differ}   only in real: {len(only_real)}   only in fake: {len(only_fake)}")
    for app, (s, d) in sorted(by_app.items()):
        print(f"  {app:9s} identical {s:3d}  different {d:3d}")
    for key in only_real:
        print("  only real:", key)
    for key in only_fake:
        print("  only fake:", key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
