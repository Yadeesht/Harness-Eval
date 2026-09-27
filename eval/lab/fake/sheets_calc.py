"""Sheets cell semantics: A1 ranges, USER_ENTERED parsing, displayed text, formulas.

Matched to the real account (en_GB locale, tool_reference §6):
- "184500" / "12000.5" -> numbers; "₹52,000" and "1,70,000" stay text
- "2026-10-15" and "15 Oct 2026" -> dates, shown as typed until a DATE format is set
- "10/15/2026" -> text (not a valid dd/mm/yyyy date)
- pattern "₹#,##,##0" shows 184500 as "₹184,500" (no lakh grouping); 12000.5 -> "₹12,001"
- =TODAY() uses the frozen date; RAW input keeps "=1+1" as text
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from typing import Any, Callable

EPOCH = date(1899, 12, 30)

# ---------------------------------------------------------------------------
# A1 notation
# ---------------------------------------------------------------------------


def col_to_index(col: str) -> int:
    n = 0
    for ch in col.upper():
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def index_to_col(i: int) -> str:
    out = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        out = chr(65 + rem) + out
    return out


CELL = re.compile(r"^\$?([A-Za-z]{1,3})?\$?(\d+)?$")


def split_sheet(range_name: str) -> tuple[str | None, str]:
    text = range_name.strip()
    if "!" in text:
        sheet, _, a1 = text.rpartition("!")
        sheet = sheet.strip()
        if sheet.startswith("'") and sheet.endswith("'"):
            sheet = sheet[1:-1].replace("''", "'")
        return sheet, a1
    return None, text


def parse_a1(a1: str) -> tuple[int | None, int | None, int | None, int | None] | None:
    """(row0, col0, row1, col1) inclusive, 0-based; None means open-ended."""
    if a1 == "":
        return (None, None, None, None)
    parts = a1.split(":")
    if len(parts) > 2:
        return None
    parsed = []
    for part in parts:
        m = CELL.match(part.strip())
        if not m or (m.group(1) is None and m.group(2) is None):
            return None
        col = col_to_index(m.group(1)) if m.group(1) else None
        row = int(m.group(2)) - 1 if m.group(2) else None
        parsed.append((row, col))
    if len(parsed) == 1:
        (r, c), = parsed
        return (r, c, r, c)
    (r0, c0), (r1, c1) = parsed
    return (r0, c0, r1, c1)


def a1_label(sheet_title: str, r0: int, c0: int, r1: int, c1: int) -> str:
    quoted = f"'{sheet_title}'" if re.search(r"[^A-Za-z0-9_]", sheet_title) else sheet_title
    start = f"{index_to_col(c0)}{r0 + 1}"
    end = f"{index_to_col(c1)}{r1 + 1}"
    return f"{quoted}!{start}" if start == end else f"{quoted}!{start}:{end}"


# ---------------------------------------------------------------------------
# Parsing typed input
# ---------------------------------------------------------------------------

NUMBER = re.compile(r"^[+-]?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$")
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def to_serial(d: date | datetime) -> float:
    if isinstance(d, datetime):
        base = datetime(EPOCH.year, EPOCH.month, EPOCH.day, tzinfo=d.tzinfo)
        return (d - base).total_seconds() / 86400
    return float((d - EPOCH).days)


def from_serial(x: float) -> datetime:
    return datetime(EPOCH.year, EPOCH.month, EPOCH.day) + timedelta(days=x)


def _parse_date(text: str) -> tuple[date, str] | None:
    t = text.strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))), "yyyy-mm-dd"
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:  # en_GB: day first
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))), "dd/mm/yyyy"
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})", t)
    if m and m.group(2)[:3].lower() in MONTHS:
        try:
            return date(int(m.group(3)), MONTHS[m.group(2)[:3].lower()], int(m.group(1))), "d mmm yyyy"
        except ValueError:
            return None
    return None


def parse_input(value: Any, raw: bool) -> dict:
    """A written value -> stored cell {"v": value, "auto": pattern?, "formula": ...}."""
    if value is None:
        return {}
    if isinstance(value, bool):
        return {"v": value}
    if isinstance(value, (int, float)):
        return {"v": float(value)}
    text = str(value)
    if text == "":
        return {}
    if raw:
        return {"v": text}
    if text.startswith("=") and len(text) > 1:
        return {"formula": text}
    stripped = text.strip()
    if stripped.upper() in ("TRUE", "FALSE"):
        return {"v": stripped.upper() == "TRUE"}
    if NUMBER.match(stripped):
        return {"v": float(stripped.replace(",", ""))}
    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)%", stripped)
    if m:
        return {"v": float(m.group(1)) / 100, "auto": {"type": "PERCENT", "pattern": "0%" if "." not in m.group(1) else "0.00%"}}
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4}) (\d{1,2}):(\d{2})(?::(\d{2}))?", stripped)
    if m:  # en_GB date-time, e.g. a Forms timestamp
        try:
            dt = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), int(m.group(4)), int(m.group(5)), int(m.group(6) or 0))
            return {"v": to_serial(dt), "auto": {"type": "DATE_TIME", "pattern": "dd/mm/yyyy hh:mm:ss"}}
        except ValueError:
            pass
    parsed = _parse_date(stripped)
    if parsed:
        d, pattern = parsed
        return {"v": to_serial(d), "auto": {"type": "DATE", "pattern": pattern}}
    return {"v": text}


# ---------------------------------------------------------------------------
# Displayed text
# ---------------------------------------------------------------------------


def _group(n: str) -> str:
    return f"{int(n):,}" if n else "0"


def _round_half_up(x: float, places: int) -> float:
    q = 10 ** places
    return math.floor(abs(x) * q + 0.5) / q * (1 if x >= 0 else -1)


def _number_pattern(value: float, pattern: str) -> str:
    m = re.search(r"[#0][#0,]*(\.[0#]+)?%?", pattern)
    if not m:
        return pattern
    core = m.group(0)
    prefix, suffix = pattern[: m.start()].replace('"', ""), pattern[m.end() :].replace('"', "")
    percent = core.endswith("%")
    if percent:
        value *= 100
        core = core[:-1]
    decimals = len(m.group(1)) - 1 if m.group(1) else 0
    grouped = "," in core.split(".")[0]
    rounded = _round_half_up(value, decimals)
    whole = f"{abs(rounded):.{decimals}f}"
    int_part, _, frac = whole.partition(".")
    int_text = _group(int_part) if grouped else str(int(int_part))
    body = int_text + (("." + frac) if decimals else "")
    sign = "-" if rounded < 0 else ""
    return f"{sign}{prefix}{body}{'%' if percent else ''}{suffix}"


def _date_pattern(serial: float, pattern: str) -> str:
    """Sheets date codes; "mm" means minutes right after hh or right before ss."""
    dt = from_serial(serial + 1e-9)
    tokens = re.findall(r"yyyy|yy|mmmm|mmm|mm|m|dddd|ddd|dd|d|hh|h|ss|s|am/pm|.", pattern, re.I)
    out = []
    for i, tok in enumerate(tokens):
        low = tok.lower()
        prev = next((t.lower() for t in reversed(tokens[:i]) if t.strip() and t not in "/:-., "), "")
        nxt = next((t.lower() for t in tokens[i + 1 :] if t.strip() and t not in "/:-., "), "")
        minutes = low in ("mm", "m") and (prev in ("hh", "h") or nxt in ("ss", "s"))
        if low == "yyyy":
            out.append(f"{dt.year:04d}")
        elif low == "yy":
            out.append(f"{dt.year % 100:02d}")
        elif minutes:
            out.append(f"{dt.minute:02d}" if low == "mm" else str(dt.minute))
        elif low == "mmmm":
            out.append(dt.strftime("%B"))
        elif low == "mmm":
            out.append(dt.strftime("%b"))
        elif low == "mm":
            out.append(f"{dt.month:02d}")
        elif low == "m":
            out.append(str(dt.month))
        elif low == "dddd":
            out.append(dt.strftime("%A"))
        elif low == "ddd":
            out.append(dt.strftime("%a"))
        elif low == "dd":
            out.append(f"{dt.day:02d}")
        elif low == "d":
            out.append(str(dt.day))
        elif low == "hh":
            out.append(f"{dt.hour:02d}")
        elif low == "h":
            out.append(str(dt.hour))
        elif low == "ss":
            out.append(f"{dt.second:02d}")
        elif low == "s":
            out.append(str(dt.second))
        else:
            out.append(tok)
    return "".join(out)


def general(value: float) -> str:
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    text = f"{value:.10g}"
    return text


def display(value: Any, fmt: dict | None) -> str:
    """The text Sheets shows (what values.get returns by default)."""
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, str):
        return value
    fmt = fmt or {}
    kind = fmt.get("type")
    pattern = fmt.get("pattern")
    if kind in ("DATE", "DATE_TIME", "TIME"):
        default = {"DATE": "dd/mm/yyyy", "DATE_TIME": "dd/mm/yyyy hh:mm:ss", "TIME": "hh:mm:ss"}[kind]
        return _date_pattern(value, pattern or default)
    if kind == "CURRENCY":
        return _number_pattern(value, pattern or "£#,##0.00")
    if kind == "PERCENT":
        return _number_pattern(value, pattern or "0.00%")
    if kind in ("NUMBER",):
        return _number_pattern(value, pattern or "#,##0.00")
    if kind == "SCIENTIFIC":
        return f"{value:.2E}"
    if kind == "TEXT":
        return general(value)
    return general(value)


# ---------------------------------------------------------------------------
# Formulas
# ---------------------------------------------------------------------------


class FormulaError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


FTOKEN = re.compile(
    r"""\s*(?:
      (?P<str>"(?:[^"]|"")*")
    | (?P<ref>(?:(?:'(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_]*)!)?\$?[A-Za-z]{1,3}\$?\d*(?::\$?[A-Za-z]{1,3}\$?\d*)?(?![A-Za-z0-9_(!]))
    | (?P<num>\d+(?:\.\d+)?)
    | (?P<func>[A-Za-z_][A-Za-z0-9_.]*)\s*\(
    | (?P<bool>TRUE|FALSE)(?![A-Za-z0-9_(])
    | (?P<op><>|<=|>=|[-+*/^&=<>(),:%])
    )""",
    re.VERBOSE,
)


def _tokenize(src: str) -> list[tuple[str, str]]:
    out, i = [], 0
    while i < len(src):
        if src[i].isspace():
            i += 1
            continue
        m = FTOKEN.match(src, i)
        if not m:
            raise FormulaError("#ERROR!")
        kind = m.lastgroup
        text = m.group(kind)
        if kind == "ref" and re.fullmatch(r"(?i)true|false", text):
            kind = "bool"
        out.append((kind, text))
        i = m.end()
    return out


class Formula:
    """Recursive-descent evaluator over a resolver for references."""

    def __init__(self, src: str, resolve: Callable[[str], Any], today: date):
        self.toks = _tokenize(src)
        self.pos = 0
        self.resolve = resolve
        self.today = today

    def peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else ("end", "")

    def take(self, text=None):
        tok = self.peek()
        if text is not None and tok[1] != text:
            raise FormulaError("#ERROR!")
        self.pos += 1
        return tok

    def run(self):
        value = self.compare()
        if self.pos != len(self.toks):
            raise FormulaError("#ERROR!")
        if isinstance(value, list):
            value = value[0][0] if value and value[0] else ""
        return value

    def compare(self):
        left = self.concat()
        while self.peek()[1] in ("=", "<>", "<", ">", "<=", ">="):
            op = self.take()[1]
            right = self.concat()
            left = _compare(scalar(left), scalar(right), op)
        return left

    def concat(self):
        left = self.additive()
        while self.peek()[1] == "&":
            self.take()
            left = text_of(scalar(left)) + text_of(scalar(self.additive()))
        return left

    def additive(self):
        left = self.term()
        while self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            a, b = num(scalar(left)), num(scalar(self.term()))
            left = a + b if op == "+" else a - b
        return left

    def term(self):
        left = self.power()
        while self.peek()[1] in ("*", "/"):
            op = self.take()[1]
            a, b = num(scalar(left)), num(scalar(self.power()))
            if op == "/" and b == 0:
                raise FormulaError("#DIV/0!")
            left = a * b if op == "*" else a / b
        return left

    def power(self):
        left = self.unary()
        while self.peek()[1] == "^":
            self.take()
            left = num(scalar(left)) ** num(scalar(self.unary()))
        return left

    def unary(self):
        if self.peek()[1] == "-":
            self.take()
            return -num(scalar(self.unary()))
        if self.peek()[1] == "+":
            self.take()
            return self.unary()
        value = self.atom()
        if self.peek()[1] == "%":
            self.take()
            value = num(scalar(value)) / 100
        return value

    def _guarded(self):
        """Evaluate one argument; on error return the error and skip to the next , or )."""
        start = self.pos
        try:
            return self.compare()
        except FormulaError as err:
            self.pos = start
            depth = 0
            while self.pos < len(self.toks):
                kind, text = self.toks[self.pos]
                if kind == "func" or text == "(":
                    depth += 1
                elif text == ")":
                    if depth == 0:
                        break
                    depth -= 1
                elif text == "," and depth == 0:
                    break
                self.pos += 1
            return err

    def atom(self):
        kind, text = self.take()
        if kind == "num":
            return float(text)
        if kind == "str":
            return text[1:-1].replace('""', '"')
        if kind == "bool":
            return text.upper() == "TRUE"
        if kind == "ref":
            return self.resolve(text)
        if kind == "func":
            name = text.upper()
            args = []
            if self.peek()[1] != ")":
                while True:
                    if name == "IFERROR" and not args:
                        args.append(self._guarded())
                    else:
                        args.append(self.compare())
                    if self.peek()[1] == ",":
                        self.take()
                        continue
                    break
            self.take(")")
            return call(name, args, self.today)
        if text == "(":
            value = self.compare()
            self.take(")")
            return value
        raise FormulaError("#ERROR!")


def scalar(v):
    if isinstance(v, list):
        return v[0][0] if v and v[0] else ""
    return v


def num(v) -> float:
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        raise FormulaError("#VALUE!")


def text_of(v) -> str:
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        return general(v)
    return "" if v is None else str(v)


def _compare(a, b, op):
    if isinstance(a, str) or isinstance(b, str):
        a, b = text_of(a).lower(), text_of(b).lower()
    else:
        a, b = num(a), num(b)
    return {"=": a == b, "<>": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]


def flat(values) -> list:
    out = []
    for v in values:
        if isinstance(v, list):
            for row in v:
                out.extend(row if isinstance(row, list) else [row])
        else:
            out.append(v)
    return out


def _criterion(crit) -> Callable[[Any], bool]:
    if isinstance(crit, (int, float)) and not isinstance(crit, bool):
        return lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) == float(crit)
    text = text_of(scalar(crit))
    m = re.match(r"^(<>|<=|>=|=|<|>)(.*)$", text)
    op, operand = (m.group(1), m.group(2)) if m else ("=", text)
    try:
        target = float(operand.replace(",", ""))
        is_num = True
    except ValueError:
        target, is_num = operand.lower(), False

    def test(v):
        if is_num:
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                return op == "<>"
            return _compare(float(v), target, op)
        if op in ("=", "<>"):
            pattern = "^" + re.escape(target).replace(r"\*", ".*").replace(r"\?", ".") + "$"
            hit = re.match(pattern, text_of(v).lower()) is not None
            return hit if op == "=" else not hit
        return _compare(text_of(v).lower(), target, op)

    return test


def _cells(rng) -> list:
    return [c for row in rng for c in row] if isinstance(rng, list) else [rng]


def call(name: str, args: list, today: date):
    nums = lambda vals: [float(v) for v in flat(vals) if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if name == "SUM":
        return sum(nums(args))
    if name == "AVERAGE":
        values = nums(args)
        if not values:
            raise FormulaError("#DIV/0!")
        return sum(values) / len(values)
    if name == "MIN":
        values = nums(args)
        return min(values) if values else 0.0
    if name == "MAX":
        values = nums(args)
        return max(values) if values else 0.0
    if name == "COUNT":
        return float(len(nums(args)))
    if name == "COUNTA":
        return float(len([v for v in flat(args) if v not in (None, "")]))
    if name in ("SUMIF", "COUNTIF", "AVERAGEIF"):
        rng = _cells(args[0])
        test = _criterion(args[1])
        target = _cells(args[2]) if len(args) > 2 else rng
        picked = [target[i] for i, v in enumerate(rng) if i < len(target) and test(v)]
        if name == "COUNTIF":
            return float(len([v for v in rng if test(v)]))
        values = [float(v) for v in picked if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if name == "AVERAGEIF":
            if not values:
                raise FormulaError("#DIV/0!")
            return sum(values) / len(values)
        return sum(values)
    if name in ("SUMIFS", "COUNTIFS", "AVERAGEIFS"):
        if name == "COUNTIFS":
            target, pairs = None, args
        else:
            target, pairs = _cells(args[0]), args[1:]
        ranges = [_cells(pairs[i]) for i in range(0, len(pairs), 2)]
        tests = [_criterion(pairs[i + 1]) for i in range(0, len(pairs), 2)]
        n = min(len(r) for r in ranges) if ranges else 0
        hits = [i for i in range(n) if all(t(r[i]) for r, t in zip(ranges, tests))]
        if name == "COUNTIFS":
            return float(len(hits))
        values = [float(target[i]) for i in hits if i < len(target) and isinstance(target[i], (int, float)) and not isinstance(target[i], bool)]
        if name == "AVERAGEIFS":
            if not values:
                raise FormulaError("#DIV/0!")
            return sum(values) / len(values)
        return sum(values)
    if name == "ROUND":
        places = int(num(scalar(args[1]))) if len(args) > 1 else 0
        return _round_half_up(num(scalar(args[0])), places)
    if name == "ABS":
        return abs(num(scalar(args[0])))
    if name == "IF":
        cond = scalar(args[0])
        truthy = bool(num(cond)) if not isinstance(cond, str) else bool(cond)
        if truthy:
            return args[1] if len(args) > 1 else True
        return args[2] if len(args) > 2 else False
    if name == "IFERROR":
        first = args[0]
        if isinstance(first, FormulaError):
            return args[1] if len(args) > 1 else ""
        return first
    if name == "AND":
        return all(bool(num(v)) for v in flat(args))
    if name == "OR":
        return any(bool(num(v)) for v in flat(args))
    if name == "NOT":
        return not bool(num(scalar(args[0])))
    if name == "TODAY":
        return to_serial(today)
    if name in ("CONCATENATE", "CONCAT"):
        return "".join(text_of(v) for v in flat(args))
    if name == "LEN":
        return float(len(text_of(scalar(args[0]))))
    if name == "UPPER":
        return text_of(scalar(args[0])).upper()
    if name == "LOWER":
        return text_of(scalar(args[0])).lower()
    if name == "VLOOKUP":
        key, table, col = scalar(args[0]), args[1], int(num(scalar(args[2])))
        exact = len(args) > 3 and not bool(num(scalar(args[3])))
        for row in table if isinstance(table, list) else []:
            if row and _compare(row[0], key, "="):
                return row[col - 1] if col - 1 < len(row) else ""
        raise FormulaError("#N/A") if exact or True else None
    raise FormulaError("#NAME?")
