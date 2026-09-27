"""Gmail search-query matching, modelled on what the real account showed.

Observed on the dummy account (eval/design/tool_reference.md §2.1):
- words match whole tokens, any case; part of a word does not match
- a hyphen splits tokens ("2291" finds "INV-2291"); "184500" does not find "1,84,500"
- quoted phrases, OR, {a b}, -word, subject:, from:, to:, in:, is:, label:,
  after:/before:, older_than:/newer_than:, category:, has:attachment
- label: takes the label *name* ("Parent/Child", "parent-child"), never the ID
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import getaddresses
from typing import Any, Callable

# Gmail interprets after:/before: dates at midnight Pacific time.
PACIFIC = timezone(timedelta(hours=-7))

TOKEN = re.compile(r"[0-9a-z]+")


def tokens(text: str) -> list[str]:
    return TOKEN.findall((text or "").lower())


@dataclass
class Term:
    op: str  # "word", "phrase", or an operator name
    value: str
    negate: bool = False


@dataclass
class Group:
    """OR over alternatives; each alternative is an AND list."""

    alternatives: list[list[Any]]
    negate: bool = False


def _lex(query: str) -> list[str]:
    out, i = [], 0
    while i < len(query):
        ch = query[i]
        if ch.isspace():
            i += 1
        elif ch in "(){}":
            out.append(ch)
            i += 1
        elif ch == '"':
            j = query.find('"', i + 1)
            j = len(query) if j == -1 else j
            out.append(query[i : j + 1])
            i = j + 1
        else:
            j = i
            while j < len(query) and not query[j].isspace() and query[j] not in "(){}":
                if query[j] == '"':  # operator with a quoted value, e.g. label:"A B"
                    k = query.find('"', j + 1)
                    j = len(query) if k == -1 else k + 1
                else:
                    j += 1
            out.append(query[i:j])
            i = j
    return out


def parse(query: str) -> Group:
    toks = _lex(query)
    pos = 0

    def parse_seq(stop: set[str]) -> Group:
        nonlocal pos
        alternatives: list[list[Any]] = [[]]
        while pos < len(toks) and toks[pos] not in stop:
            tok = toks[pos]
            pos += 1
            if tok == "OR":
                alternatives.append([])
                continue
            negate = False
            if tok.startswith("-") and len(tok) > 1:
                negate, tok = True, tok[1:]
            if tok in ("(", "{"):
                close = ")" if tok == "(" else "}"
                inner = parse_seq({close})
                pos += 1  # skip closer
                if tok == "{":  # braces mean OR of the members
                    members = [item for alt in inner.alternatives for item in alt]
                    inner = Group([[m] for m in members])
                inner.negate = negate
                alternatives[-1].append(inner)
                continue
            if tok.startswith('"'):
                alternatives[-1].append(Term("phrase", tok.strip('"'), negate))
                continue
            if ":" in tok:
                op, _, value = tok.partition(":")
                if value == "" and pos < len(toks) and toks[pos] in ("(", "{"):
                    # operator applied to a group, e.g. subject:(expense approval)
                    opener = toks[pos]
                    pos += 1
                    inner = parse_seq({")" if opener == "(" else "}"})
                    pos += 1
                    grouped = _apply_op(inner, op.lower(), any_of=opener == "{")
                    grouped.negate = negate
                    alternatives[-1].append(grouped)
                    continue
                alternatives[-1].append(Term(op.lower(), value.strip('"'), negate))
                continue
            alternatives[-1].append(Term("word", tok, negate))
        return Group([a for a in alternatives if a] or [[]])

    return parse_seq(set())


def _apply_op(group: Group, op: str, any_of: bool = False) -> Group:
    """Push an operator into a group: subject:(a b) = subject:a AND subject:b."""
    def convert(node):
        if isinstance(node, Term):
            if node.op == "word":
                return Term(op, node.value, node.negate)
            if node.op == "phrase":
                return Term(op, node.value, node.negate)
            return node
        return _apply_op(node, op)

    alts = [[convert(item) for item in alt] for alt in group.alternatives]
    if any_of:
        alts = [[item] for alt in alts for item in alt]
    return Group(alts, group.negate)


def _relative(value: str, now: datetime) -> datetime | None:
    m = re.fullmatch(r"(\d+)([dmy])", value.lower())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    days = {"d": 1, "m": 30, "y": 365}[unit] * n
    return now - timedelta(days=days)


def _date(value: str) -> datetime | None:
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=PACIFIC)
        except ValueError:
            pass
    if value.isdigit():
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    return None


def _norm_label(name: str) -> str:
    return re.sub(r"[\s/\-_]+", "-", name.strip().lower())


class MessageView:
    """What the matcher needs to know about one message."""

    def __init__(self, msg: dict, labels_by_id: dict[str, dict], user_email: str):
        self.msg = msg
        self.label_ids = set(msg.get("labelIds", []))
        self.label_names = {_norm_label(labels_by_id[l]["name"]) for l in self.label_ids if l in labels_by_id}
        self.subject_tokens = tokens(msg.get("subject", ""))
        self.body_tokens = tokens(msg.get("body", ""))
        self.from_raw = msg.get("from", "")
        self.to_raw = ", ".join(x for x in (msg.get("to", ""), msg.get("cc", "")) if x)
        self.from_addrs = getaddresses([self.from_raw])
        self.to_addrs = getaddresses([self.to_raw])
        self.user = user_email.lower()
        self.when = datetime.fromisoformat(msg["internalDate"])

    def all_tokens(self) -> set[str]:
        people = []
        for name, addr in self.from_addrs + self.to_addrs:
            people += tokens(name) + tokens(addr)
        return set(self.subject_tokens) | set(self.body_tokens) | set(people)


def _addr_match(value: str, addrs: list[tuple[str, str]], user: str) -> bool:
    value = value.lower()
    if value == "me":
        return any(a.lower() == user for _, a in addrs)
    for name, addr in addrs:
        addr = addr.lower()
        if "@" in value or "." in value:
            if value == addr or addr.endswith("@" + value) or addr.endswith("." + value) or value in addr:
                return True
        want = tokens(value)
        have = tokens(name) + tokens(addr)
        if want and all(w in have for w in want):
            return True
    return False


def _phrase_in(want: list[str], have: list[str]) -> bool:
    if not want:
        return True
    n = len(want)
    return any(have[i : i + n] == want for i in range(len(have) - n + 1))


def _term(term: Term, m: MessageView, now: datetime) -> bool:
    op, value = term.op, term.value
    lv = value.lower()
    if op == "word":
        want = tokens(value)
        pool = m.all_tokens()
        return bool(want) and all(w in pool for w in want)
    if op == "phrase":
        want = tokens(value)
        return _phrase_in(want, m.subject_tokens) or _phrase_in(want, m.body_tokens)
    if op == "subject":
        want = tokens(value)
        return bool(want) and all(w in m.subject_tokens for w in want)
    if op == "from":
        return _addr_match(value, m.from_addrs, m.user)
    if op in ("to", "cc", "deliveredto"):
        return _addr_match(value, m.to_addrs, m.user)
    if op == "in":
        if lv == "anywhere":
            return True
        mapping = {"inbox": "INBOX", "sent": "SENT", "trash": "TRASH", "spam": "SPAM", "drafts": "DRAFT", "draft": "DRAFT", "starred": "STARRED", "important": "IMPORTANT"}
        if lv in mapping:
            return mapping[lv] in m.label_ids
        return _norm_label(value) in m.label_names
    if op == "is":
        if lv == "unread":
            return "UNREAD" in m.label_ids
        if lv == "read":
            return "UNREAD" not in m.label_ids
        if lv in ("starred", "important"):
            return lv.upper() in m.label_ids
        return False
    if op == "label":
        return _norm_label(value) in m.label_names
    if op == "category":
        cat = {"primary": "CATEGORY_PERSONAL", "personal": "CATEGORY_PERSONAL", "social": "CATEGORY_SOCIAL", "promotions": "CATEGORY_PROMOTIONS", "updates": "CATEGORY_UPDATES", "forums": "CATEGORY_FORUMS"}.get(lv)
        return cat in m.label_ids if cat else False
    if op == "has":
        return lv == "attachment" and bool(m.msg.get("attachments"))
    if op in ("after", "newer"):
        when = _date(value)
        return when is not None and m.when >= when
    if op in ("before", "older"):
        when = _date(value)
        return when is not None and m.when < when
    if op == "newer_than":
        when = _relative(value, now)
        return when is not None and m.when >= when
    if op == "older_than":
        when = _relative(value, now)
        return when is not None and m.when < when
    if op == "filename":
        return False
    # Unknown operator: Gmail treats "word:thing" as plain text.
    want = tokens(f"{op} {value}")
    return all(w in m.all_tokens() for w in want)


def _eval(node: Any, m: MessageView, now: datetime) -> bool:
    if isinstance(node, Term):
        result = _term(node, m, now)
    else:
        result = any(all(_eval(item, m, now) for item in alt) for alt in node.alternatives)
    return not result if node.negate else result


def compile_query(query: str | None, now: datetime) -> Callable[[MessageView], bool]:
    """Matcher for a query. Trash and spam are excluded unless the query asks for them."""
    tree = parse(query or "")
    lowered = (query or "").lower()
    wants_hidden = any(k in lowered for k in ("in:trash", "in:spam", "in:anywhere"))

    def match(m: MessageView) -> bool:
        if not wants_hidden and ({"TRASH", "SPAM"} & m.label_ids):
            return False
        return _eval(tree, m, now)

    return match
