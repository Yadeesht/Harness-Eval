"""The one shared normalizer (AGENTS.md grading rules).

Anchors in task files are matched against agent-written text after normalizing:
- text:   dashes (- – —), whitespace and case
- amount: {"amount": 184500} matches 184500, 1,84,500, 184,500, ₹1,84,500, Rs. 184500, 1.845 lakh
- date:   {"date": "2026-10-20"} matches 20 Oct, 20 October 2026, October 20, 20/10/2026, 2026-10-20, 20th Oct
- time:   {"time": "15:00"} matches 15:00, 3 PM, 3:00 pm, 3pm
- number: {"number": 4} matches 4 or four
- a list of anchors means any one of them
"""

from __future__ import annotations

import re
from datetime import date

DASHES = re.compile(r"[‐-―−-]")
WORDS = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}


def norm(text: str) -> str:
    text = DASHES.sub("-", text or "")
    text = text.replace(" ", " ")
    return " ".join(text.split()).lower()


def _amount_forms(n: int) -> list[str]:
    western = f"{n:,}"
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        indian = ",".join(groups) + "," + tail
    else:
        indian = s
    forms = {s, western, indian}
    if n >= 100000 and n % 1000 == 0:
        forms.add(f"{n / 100000:g} lakh")
    return list(forms)


def _date_forms(iso: str) -> list[str]:
    d = date.fromisoformat(iso)
    day, mon, month, year = d.day, d.strftime("%b").lower(), d.strftime("%B").lower(), d.year
    suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return [
        f"{day} {mon}", f"{day}{suffix} {mon}", f"{day} {month}", f"{day}{suffix} {month}",
        f"{mon} {day}", f"{month} {day}", f"{month} {day}{suffix}", f"{mon} {day}{suffix}",
        f"{day:02d}/{d.month:02d}/{year}", f"{day}/{d.month}/{year}", iso, f"{day}-{mon}-{year}",
        f"{day:02d} {mon}",
    ]


def _time_forms(hhmm: str) -> list[str]:
    h, m = map(int, hhmm.split(":"))
    h12 = h % 12 or 12
    ampm = "am" if h < 12 else "pm"
    forms = [f"{h:02d}:{m:02d}", f"{h}:{m:02d}", f"{h12}:{m:02d} {ampm}", f"{h12}:{m:02d}{ampm}"]
    if m == 0:
        forms += [f"{h12} {ampm}", f"{h12}{ampm}", f"{h:02d}{m:02d} hrs", f"{h:02d}:00 hrs"]
    return forms


def _contains_number(text: str, form: str) -> bool:
    """Match a number form without matching inside a longer number."""
    return re.search(rf"(?<![\d,.]){re.escape(form)}(?![\d]|,\d)", text) is not None


def matches(text: str, anchor) -> bool:
    """True when normalized text contains the anchor (see module docstring)."""
    t = norm(text)
    if isinstance(anchor, list):
        return any(matches(text, a) for a in anchor)
    if isinstance(anchor, dict):
        if "amount" in anchor:
            return any(_contains_number(t, f) for f in _amount_forms(int(anchor["amount"])))
        if "date" in anchor:
            return any(re.search(rf"(?<![\d]){re.escape(f)}(?![\d])", t) for f in _date_forms(anchor["date"]))
        if "time" in anchor:
            return any(re.search(rf"(?<![\d]){re.escape(f)}(?![\d])", t) for f in _time_forms(anchor["time"]))
        if "number" in anchor:
            n = int(anchor["number"])
            return _contains_number(t, str(n)) or bool(re.search(rf"\b{WORDS.get(n, '#')}\b", t))
        if "regex" in anchor:
            return re.search(anchor["regex"], t) is not None
        raise ValueError(f"unknown anchor {anchor}")
    return norm(str(anchor)) in t


def same(a: str, b: str) -> bool:
    return norm(a) == norm(b)
