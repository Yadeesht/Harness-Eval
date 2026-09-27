"""Fake Google Docs API v1: documents.get / create / batchUpdate.

A segment (body, header, footer) is a flat list of index units, the way Docs
counts indices:
  {"c": ch, "s": {...}}                 one character (the "\n" ending a paragraph
                                         also carries paragraph props in "p")
  {"k": "pb"} / {"k": "img", "id": ...}   page break / inline image (1 unit each)
  {"k": "ts"} {"k": "rs"} {"k": "cs"} {"k": "te"}   table/row/cell start, table end
Body indices start at 1 (index 0 is the section break); header/footer at 0.
The API JSON (paragraphs, textRuns, tables with start/end indices) is rebuilt
from this list on every read, so indices always agree with real Docs:
a cell ends at start + 1 + its content, a table ends one past its last cell.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from .base import FakeRequest, api_uri, http_error

if TYPE_CHECKING:
    from ..workspace import Workspace

BASE = "https://docs.googleapis.com"
STRUCT = {"ts", "rs", "cs", "te"}
PARA_DEFAULT = {"namedStyleType": "NORMAL_TEXT", "direction": "LEFT_TO_RIGHT"}


class BatchError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def is_struct(tok: dict) -> bool:
    return tok.get("k") in STRUCT


def is_text(tok: dict) -> bool:
    return "c" in tok or tok.get("k") in ("pb", "img")


# ---------------------------------------------------------------------------
# Building segments (seed data)
# ---------------------------------------------------------------------------


def text_tokens(text: str, style: dict | None = None) -> list[dict]:
    out = []
    for ch in text:
        tok = {"c": ch}
        if style:
            tok["s"] = dict(style)
        if ch == "\n":
            tok["p"] = dict(PARA_DEFAULT)
        out.append(tok)
    return out


def table_tokens(rows: list[list[str]]) -> list[dict]:
    out = [{"k": "ts"}]
    for row in rows:
        out.append({"k": "rs"})
        for cell in row:
            out.append({"k": "cs"})
            out.extend(text_tokens(cell + "\n"))
        # a cell always keeps its closing newline
    out.append({"k": "te"})
    return out


def build_body(blocks: list[Any]) -> list[dict]:
    """blocks: paragraph strings, or {"table": [[...], ...]}. Ends with an empty paragraph."""
    tokens: list[dict] = []
    for block in blocks:
        if isinstance(block, dict) and "table" in block:
            tokens.extend(table_tokens(block["table"]))
        elif isinstance(block, dict) and "text" in block:
            tokens.extend(text_tokens(block["text"] + "\n", block.get("style")))
        else:
            tokens.extend(text_tokens(str(block) + "\n"))
    # Docs always ends the body with a paragraph after a table
    if not tokens or tokens[-1].get("k") == "te":
        tokens.extend(text_tokens("\n"))
    return tokens


# ---------------------------------------------------------------------------
# JSON view
# ---------------------------------------------------------------------------


def _style_json(style: dict | None) -> dict:
    return copy.deepcopy(style) if style else {}


def _paragraph_json(tokens, lo, hi, off, doc) -> dict:
    """tokens[lo:hi] is one paragraph ending in "\n"."""
    elements = []
    i = lo
    while i < hi:
        tok = tokens[i]
        if tok.get("k") == "pb":
            elements.append({"startIndex": off + i, "endIndex": off + i + 1, "pageBreak": {"textStyle": {}}})
            i += 1
            continue
        if tok.get("k") == "img":
            elements.append({"startIndex": off + i, "endIndex": off + i + 1, "inlineObjectElement": {"inlineObjectId": tok["id"], "textStyle": {}}})
            i += 1
            continue
        j = i
        style = tok.get("s")
        text = ""
        while j < hi and "c" in tokens[j] and tokens[j].get("s") == style:
            text += tokens[j]["c"]
            j += 1
        elements.append({"startIndex": off + i, "endIndex": off + j, "textRun": {"content": text, "textStyle": _style_json(style)}})
        i = j
    newline = tokens[hi - 1]
    props = dict(newline.get("p") or PARA_DEFAULT)
    bullet = props.pop("bullet", None)
    para = {"elements": elements, "paragraphStyle": props}
    if bullet:
        para["bullet"] = bullet
    return {"startIndex": off + lo, "endIndex": off + hi, "paragraph": para}


def _content_json(tokens, lo, hi, off, doc) -> list[dict]:
    out = []
    i = lo
    while i < hi:
        if tokens[i].get("k") == "ts":
            table, i = _table_json(tokens, i, off, doc)
            out.append(table)
            continue
        j = i
        while j < hi and not (tokens[j].get("c") == "\n"):
            j += 1
        j = min(j + 1, hi)
        out.append(_paragraph_json(tokens, i, j, off, doc))
        i = j
    return out


def _table_json(tokens, ts, off, doc):
    rows = []
    j = ts + 1
    ncols = 0
    while tokens[j].get("k") == "rs":
        row_start = j
        j += 1
        cells = []
        while tokens[j].get("k") == "cs":
            cell_start = j
            j += 1
            k = j
            while tokens[k].get("k") not in ("cs", "rs", "te"):
                if tokens[k].get("k") == "ts":  # nested tables are not modelled
                    raise BatchError("Nested tables are not supported by the lab.")
                k += 1
            cells.append(
                {
                    "startIndex": off + cell_start,
                    "endIndex": off + k,
                    "content": _content_json(tokens, j, k, off, doc),
                    "tableCellStyle": {"rowSpan": 1, "columnSpan": 1},
                }
            )
            j = k
        ncols = max(ncols, len(cells))
        rows.append({"startIndex": off + row_start, "endIndex": off + j, "tableCells": cells, "tableRowStyle": {"minRowHeight": {"unit": "PT"}}})
    table = {"startIndex": off + ts, "endIndex": off + j + 1, "table": {"rows": len(rows), "columns": ncols, "tableRows": rows, "tableStyle": {}}}
    return table, j + 1


def body_json(doc: dict) -> dict:
    tokens = doc["segments"]["body"]
    section = {"endIndex": 1, "sectionBreak": {"sectionStyle": {"columnSeparatorStyle": "NONE", "contentDirection": "LEFT_TO_RIGHT", "sectionType": "CONTINUOUS"}}}
    return {"content": [section] + _content_json(tokens, 0, len(tokens), 1, doc)}


def _segments_json(doc: dict, kind: str) -> dict:
    out = {}
    for seg_id in doc[kind]:
        tokens = doc["segments"][seg_id]
        key = "headerId" if kind == "headers" else "footerId"
        out[seg_id] = {key: seg_id, "content": _content_json(tokens, 0, len(tokens), 0, doc)}
    return out


def document_json(doc: dict, include_tabs: bool) -> dict:
    style = {"pageSize": {"height": {"magnitude": 792, "unit": "PT"}, "width": {"magnitude": 612, "unit": "PT"}}}
    if doc.get("defaultHeaderId"):
        style["defaultHeaderId"] = doc["defaultHeaderId"]
    if doc.get("defaultFooterId"):
        style["defaultFooterId"] = doc["defaultFooterId"]
    parts = {
        "body": body_json(doc),
        "headers": _segments_json(doc, "headers"),
        "footers": _segments_json(doc, "footers"),
        "documentStyle": style,
        "namedStyles": {"styles": []},
        "lists": copy.deepcopy(doc.get("lists", {})),
        "inlineObjects": copy.deepcopy(doc.get("inlineObjects", {})),
    }
    for key in ("headers", "footers", "lists", "inlineObjects"):
        if not parts[key]:
            parts.pop(key)
    base = {"documentId": doc["documentId"], "title": doc["title"], "revisionId": f"rev{doc.get('revision', 1)}", "suggestionsViewMode": "SUGGESTIONS_INLINE"}
    if include_tabs:
        base["tabs"] = [{"tabProperties": {"tabId": "t.0", "title": "Tab 1", "index": 0}, "documentTab": parts}]
        return base
    base.update(parts)
    return base


def plain_text(doc: dict) -> str:
    """Body text in reading order (used for Drive exports and fullText search)."""
    return "".join(t["c"] for t in doc["segments"]["body"] if "c" in t)


# ---------------------------------------------------------------------------
# batchUpdate
# ---------------------------------------------------------------------------


class _Batch:
    def __init__(self, ws: "Workspace", doc: dict):
        self.ws = ws
        self.doc = doc

    def segment(self, seg_id: str | None):
        if not seg_id:
            return self.doc["segments"]["body"], 1
        if seg_id not in self.doc["segments"]:
            raise BatchError(f"The segment ID {seg_id} was not found.")
        return self.doc["segments"][seg_id], 0

    # ---- request handlers -------------------------------------------------
    def insertText(self, req):
        tokens, off, p = self._insert_position(req, "insertText")
        text = req.get("text", "")
        if not text:
            return {}
        style = self._style_at(tokens, p)
        para = self._para_props(tokens, p)
        new = []
        for ch in text:
            tok = {"c": ch}
            if style:
                tok["s"] = dict(style)
            if ch == "\n":
                tok["p"] = dict(para)
            new.append(tok)
        tokens[p:p] = new
        return {}

    def deleteContentRange(self, req):
        rng = req.get("range", {})
        tokens, off = self.segment(rng.get("segmentId"))
        lo, hi = rng.get("startIndex", 0) - off, rng.get("endIndex", 0) - off
        end = len(tokens) + off
        if hi <= lo:
            raise BatchError("The range should not be empty.")
        if rng.get("endIndex", 0) > end:
            raise BatchError(f"Index {rng.get('endIndex')} must be less than the end index of the referenced segment, {end}.")
        if lo < 0:
            raise BatchError("The range should not include the section break at index 0.")
        if hi >= len(tokens) and tokens[-1].get("c") == "\n":
            raise BatchError("The range cannot include the newline character at the end of the segment.")
        chunk = tokens[lo:hi]
        depth = 0
        for tok in chunk:
            if tok.get("k") == "ts":
                depth += 1
            elif tok.get("k") == "te":
                depth -= 1
                if depth < 0:
                    raise BatchError("Invalid deletion range. Cannot delete the requested range.")
            elif tok.get("k") in ("rs", "cs") and depth == 0:
                raise BatchError("Invalid deletion range. Cannot delete the requested range.")
        if depth != 0:
            raise BatchError("Invalid deletion range. Cannot delete the requested range.")
        # Every table cell must still end with its newline after the deletion.
        after = tokens[:lo] + tokens[hi:]
        for i, tok in enumerate(after):
            if tok.get("k") in ("cs", "rs", "te") and i > 0 and after[i - 1].get("k") == "cs":
                raise BatchError("Invalid deletion range. Cannot delete the requested range.")
        del tokens[lo:hi]
        return {}

    def updateTextStyle(self, req):
        rng = req.get("range", {})
        tokens, off = self.segment(rng.get("segmentId"))
        lo, hi = rng.get("startIndex", 0) - off, rng.get("endIndex", 0) - off
        end = len(tokens) + off
        if rng.get("endIndex", 0) > end:
            raise BatchError(f"Index {rng.get('endIndex')} must be less than the end index of the referenced segment, {end}.")
        if hi <= lo:
            raise BatchError("The range should not be empty.")
        style = req.get("textStyle", {})
        fields = [f.strip() for f in (req.get("fields") or "*").split(",")]
        if fields == ["*"]:
            fields = list(style.keys())
        for tok in tokens[max(lo, 0) : hi]:
            if "c" not in tok:
                continue
            current = dict(tok.get("s") or {})
            for field in fields:
                if field in style:
                    current[field] = copy.deepcopy(style[field])
                else:
                    current.pop(field, None)
            if current:
                tok["s"] = current
            else:
                tok.pop("s", None)
        return {}

    def replaceAllText(self, req):
        contains = req.get("containsText", {})
        needle = contains.get("text", "")
        if not needle:
            raise BatchError("The text to search for must not be empty.")
        match_case = bool(contains.get("matchCase"))
        replacement = req.get("replaceText", "")
        count = 0
        for seg_id, tokens in self.doc["segments"].items():
            count += self._replace_in(tokens, needle, replacement, match_case)
        return {"replaceAllText": {"occurrencesChanged": count}} if count else {"replaceAllText": {}}

    def insertTable(self, req):
        rows, cols = int(req.get("rows", 0)), int(req.get("columns", 0))
        if rows < 1 or cols < 1:
            raise BatchError("The table must have at least one row and one column.")
        tokens, off, p = self._insert_position(req, "insertTable", allow_end=True)
        para = self._para_props(tokens, p)
        new = [{"c": "\n", "p": dict(PARA_DEFAULT)}] + table_tokens([[""] * cols for _ in range(rows)])
        del para
        tokens[p:p] = new
        return {}

    def insertPageBreak(self, req):
        tokens, off, p = self._insert_position(req, "insertPageBreak")
        tokens[p:p] = [{"k": "pb"}, {"c": "\n", "p": dict(self._para_props(tokens, p))}]
        return {}

    def insertInlineImage(self, req):
        size = req.get("objectSize") or {}
        for dim in ("height", "width"):
            if dim in size and (size[dim] or {}).get("magnitude", 0) <= 0:
                raise BatchError(f"Invalid object size: {dim} must be greater than 0 if specified.")
        uri = req.get("uri", "")
        if not uri.startswith(("http://", "https://")) or " " in uri:
            raise BatchError("There was a problem retrieving the image. The provided image should be publicly accessible, within size limit, and in supported formats.")
        tokens, off, p = self._insert_position(req, "insertInlineImage")
        obj_id = "kix." + self.ws.ids.new("inline", 12, "b32hex")
        self.doc.setdefault("inlineObjects", {})[obj_id] = {
            "objectId": obj_id,
            "inlineObjectProperties": {"embeddedObject": {"imageProperties": {"sourceUri": uri, "contentUri": uri}, "size": size}},
        }
        tokens[p:p] = [{"k": "img", "id": obj_id}]
        return {"insertInlineImage": {"objectId": obj_id}}

    def createParagraphBullets(self, req):
        rng = req.get("range", {})
        tokens, off = self.segment(rng.get("segmentId"))
        lo, hi = rng.get("startIndex", 0) - off, rng.get("endIndex", 0) - off
        list_id = "kix." + self.ws.ids.new("list", 12, "b32hex")
        preset = req.get("bulletPreset", "BULLET_DISC_CIRCLE_SQUARE")
        glyph = {"glyphType": "DECIMAL"} if "NUMBERED" in preset or "DECIMAL" in preset else {"glyphSymbol": "●"}
        self.doc.setdefault("lists", {})[list_id] = {"listProperties": {"nestingLevels": [glyph]}}
        # every paragraph that overlaps [lo, hi)
        i = max(lo, 0)
        while i < len(tokens) and i <= max(hi - 1, lo):
            j = i
            while j < len(tokens) and tokens[j].get("c") != "\n":
                j += 1
            if j < len(tokens):
                props = dict(tokens[j].get("p") or PARA_DEFAULT)
                props["bullet"] = {"listId": list_id, "textStyle": {}}
                tokens[j]["p"] = props
            i = j + 1
        return {}

    def createHeader(self, req):
        return self._create_segment(req, "headers", "defaultHeaderId", "header")

    def createFooter(self, req):
        return self._create_segment(req, "footers", "defaultFooterId", "footer")

    # ---- helpers ---------------------------------------------------------
    def _create_segment(self, req, kind, default_key, word):
        seg_type = req.get("type", "DEFAULT")
        if seg_type != "DEFAULT":
            raise BatchError(f"Only a DEFAULT {word} can be created with this request.")
        if self.doc.get(default_key):
            raise BatchError(f"A default {word} already exists.")
        seg_id = "kix." + self.ws.ids.new(word, 12, "b32hex")
        self.doc["segments"][seg_id] = text_tokens("\n")
        self.doc[kind].append(seg_id)
        self.doc[default_key] = seg_id
        key = "headerId" if word == "header" else "footerId"
        return {"create" + word.capitalize(): {key: seg_id}}

    def _insert_position(self, req, name, allow_end=False):
        loc = req.get("location")
        if loc is None and "endOfSegmentLocation" in req:
            tokens, off = self.segment(req["endOfSegmentLocation"].get("segmentId"))
            return tokens, off, len(tokens) - 1
        loc = loc or {}
        tokens, off = self.segment(loc.get("segmentId"))
        index = loc.get("index", 0)
        end = len(tokens) + off
        if allow_end and index == end:
            index = end - 1
        if index >= end:
            raise BatchError(f"Index {index} must be less than the end index of the referenced segment, {end}.")
        p = index - off
        if p < 0 or not is_text(tokens[p]):
            raise BatchError("The insertion index must be inside the bounds of an existing paragraph. You can still create new paragraphs by inserting newlines.")
        return tokens, off, p

    @staticmethod
    def _style_at(tokens, p):
        if p > 0 and "c" in tokens[p - 1] and tokens[p - 1]["c"] != "\n":
            return tokens[p - 1].get("s")
        if "c" in tokens[p] and tokens[p]["c"] != "\n":
            return tokens[p].get("s")
        return None

    @staticmethod
    def _para_props(tokens, p):
        j = p
        while j < len(tokens) and tokens[j].get("c") != "\n":
            j += 1
        if j < len(tokens):
            props = dict(tokens[j].get("p") or PARA_DEFAULT)
            props.pop("bullet", None)
            return props
        return dict(PARA_DEFAULT)

    @staticmethod
    def _replace_in(tokens, needle, replacement, match_case):
        count = 0
        i = 0
        target = needle if match_case else needle.lower()
        while i < len(tokens):
            # paragraph text from i up to its newline (text tokens only)
            j = i
            while j < len(tokens) and "c" in tokens[j] and tokens[j]["c"] != "\n":
                j += 1
            run = "".join(tokens[k]["c"] for k in range(i, j))
            hay = run if match_case else run.lower()
            pos = hay.find(target)
            if pos != -1 and j > i:
                start = i + pos
                style = tokens[start].get("s")
                new = [{"c": ch, **({"s": dict(style)} if style else {})} for ch in replacement]
                tokens[start : start + len(needle)] = new
                count += 1
                i = start + len(new)
                continue
            i = j + 1
        return count


class Docs:
    def __init__(self, ws: "Workspace"):
        self.ws = ws
        self._http = None

    def documents(self):
        return _Documents(self.ws)


class _Documents:
    def __init__(self, ws):
        self.ws = ws
        self.docs = ws.state["docs"]

    def _doc(self, doc_id, uri):
        doc = self.docs.get(doc_id)
        f = self.ws.state["drive"]["files"].get(doc_id)
        if doc is None or f is None or f.get("trashed"):
            raise http_error(404, "Requested entity was not found.", uri, detail_style="message")
        return doc

    def get(self, documentId=None, includeTabsContent=False, **_):
        uri = api_uri(BASE, f"/v1/documents/{documentId}", includeTabsContent=includeTabsContent or None)
        return FakeRequest(lambda: document_json(self._doc(documentId, uri), bool(includeTabsContent)), uri)

    def create(self, body=None, **_):
        def run():
            title = (body or {}).get("title", "Untitled document")
            doc_id = self.ws.ids.new("doc", 44, "b64")
            self.ws.add_doc(doc_id, title, text_tokens("\n"), origin="agent")
            return document_json(self.docs[doc_id], False)

        return FakeRequest(run, api_uri(BASE, "/v1/documents"), "POST")

    def batchUpdate(self, documentId=None, body=None, **_):
        uri = api_uri(BASE, f"/v1/documents/{documentId}:batchUpdate")

        def run():
            doc = self._doc(documentId, uri)
            trial = copy.deepcopy(doc)
            batch = _Batch(self.ws, trial)
            replies = []
            for i, request in enumerate((body or {}).get("requests", [])):
                if not isinstance(request, dict) or len(request) != 1:
                    raise http_error(400, f"Invalid requests[{i}]: exactly one request kind is required.", uri, detail_style="message")
                (kind, payload), = request.items()
                handler = getattr(batch, kind, None)
                if handler is None:
                    raise http_error(400, f"Invalid requests[{i}]: Unsupported request {kind} in the lab.", uri, detail_style="message")
                try:
                    replies.append(handler(payload or {}))
                except BatchError as err:
                    raise http_error(400, f"Invalid requests[{i}].{kind}: {err.message}", uri, detail_style="message")
            trial["revision"] = doc.get("revision", 1) + 1
            doc.clear()
            doc.update(trial)
            self.ws.touch_file(documentId)
            return {"documentId": documentId, "replies": replies, "writeControl": {"requiredRevisionId": f"rev{doc['revision']}"}}

        return FakeRequest(run, uri, "POST")
