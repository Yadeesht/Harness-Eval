"""Fake Google Sheets API v4: spreadsheets.get/create/batchUpdate, values.get/update/clear."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from . import sheets_calc as calc
from .base import FakeRequest, api_uri, http_error, make_id, quote_id

if TYPE_CHECKING:
    from ..workspace import Workspace

BASE = "https://sheets.googleapis.com"


def _err(status, message, uri):
    return http_error(status, message, uri, detail_style="message")


class Book:
    """Read/write helpers over one spreadsheet's state."""

    def __init__(self, ws: "Workspace", sid: str, data: dict):
        self.ws = ws
        self.sid = sid
        self.data = data
        self._evaluating: set = set()

    # ---- tabs -------------------------------------------------------------
    def tab(self, title: str | None) -> dict | None:
        tabs = self.data["tabs"]
        if title is None:
            return tabs[0] if tabs else None
        for t in tabs:
            if t["title"] == title or t["title"].lower() == title.lower():
                return t
        return None

    def tab_by_id(self, sheet_id: int) -> dict | None:
        return next((t for t in self.data["tabs"] if t["sheetId"] == sheet_id), None)

    def resolve_range(self, range_name: str, uri: str):
        sheet, a1 = calc.split_sheet(range_name)
        if sheet is not None:
            tab = self.tab(sheet)
            if tab is None:
                raise _err(400, f"Unable to parse range: {range_name}", uri)
            box = calc.parse_a1(a1)
        else:
            box = calc.parse_a1(a1)
            tab = self.tab(None)
            if box is None:
                tab = self.tab(a1)
                box = (None, None, None, None)
        if tab is None or box is None:
            raise _err(400, f"Unable to parse range: {range_name}", uri)
        r0, c0, r1, c1 = box
        r0 = 0 if r0 is None else r0
        c0 = 0 if c0 is None else c0
        r1 = tab["rowCount"] - 1 if r1 is None else r1
        c1 = tab["colCount"] - 1 if c1 is None else c1
        return tab, r0, c0, r1, c1

    # ---- cells ------------------------------------------------------------
    @staticmethod
    def key(r: int, c: int) -> str:
        return f"{r},{c}"

    def extent(self, tab) -> tuple[int, int]:
        rows = cols = 0
        for k in tab["cells"]:
            r, c = map(int, k.split(","))
            rows, cols = max(rows, r + 1), max(cols, c + 1)
        return rows, cols

    def number_format(self, tab, r, c) -> dict | None:
        fmt = None
        for rule in tab.get("formats", []):
            g = rule["range"]
            if g.get("startRowIndex", 0) <= r < g.get("endRowIndex", 10**9) and g.get("startColumnIndex", 0) <= c < g.get("endColumnIndex", 10**9):
                if "numberFormat" in rule["format"]:
                    fmt = rule["format"]["numberFormat"]
        return fmt

    def value(self, tab, r, c):
        cell = tab["cells"].get(self.key(r, c))
        if not cell:
            return None
        if "formula" in cell:
            return self.evaluate(tab, r, c, cell["formula"])
        return cell.get("v")

    def evaluate(self, tab, r, c, formula):
        marker = (tab["sheetId"], r, c)
        if marker in self._evaluating:
            return calc.FormulaError("#REF!")
        self._evaluating.add(marker)
        try:
            return calc.Formula(formula[1:], lambda ref: self._ref(tab, ref), self.ws.clock.now().date()).run()
        except calc.FormulaError as err:
            return err
        except (RecursionError, IndexError, TypeError, ValueError, ZeroDivisionError):
            return calc.FormulaError("#ERROR!")
        finally:
            self._evaluating.discard(marker)

    def _ref(self, tab, ref: str):
        sheet, a1 = calc.split_sheet(ref)
        target = self.tab(sheet) if sheet is not None else tab
        if target is None:
            raise calc.FormulaError("#REF!")
        box = calc.parse_a1(a1)
        if box is None:
            raise calc.FormulaError("#NAME?")
        r0, c0, r1, c1 = box
        rows, cols = self.extent(target)
        r0 = 0 if r0 is None else r0
        c0 = 0 if c0 is None else c0
        r1 = max(rows - 1, r0) if r1 is None else r1
        c1 = max(cols - 1, c0) if c1 is None else c1
        if (r0, c0) == (r1, c1) and ":" not in a1:
            v = self.value(target, r0, c0)
            if isinstance(v, calc.FormulaError):
                raise v
            return "" if v is None else v
        grid = []
        for rr in range(r0, r1 + 1):
            row = []
            for cc in range(c0, c1 + 1):
                v = self.value(target, rr, cc)
                row.append("" if v is None or isinstance(v, calc.FormulaError) else v)
            grid.append(row)
        return grid

    def shown(self, tab, r, c) -> str:
        cell = tab["cells"].get(self.key(r, c))
        if not cell:
            return ""
        v = self.value(tab, r, c)
        if isinstance(v, calc.FormulaError):
            return v.code
        fmt = self.number_format(tab, r, c) or cell.get("auto")
        if fmt is None and "formula" in cell and "TODAY(" in cell["formula"].upper():
            fmt = {"type": "DATE", "pattern": "dd/mm/yyyy"}
        return calc.display(v, fmt)


class Sheets:
    def __init__(self, ws: "Workspace"):
        self.ws = ws
        self._http = None

    def spreadsheets(self):
        return _Spreadsheets(self.ws)


class _Spreadsheets:
    def __init__(self, ws):
        self.ws = ws
        self.books = ws.state["sheets"]

    def _book(self, sid, uri) -> Book:
        data = self.books.get(sid)
        f = self.ws.state["drive"]["files"].get(sid)
        if data is None or f is None or f.get("trashed"):
            raise _err(404, "Requested entity was not found.", uri)
        return Book(self.ws, sid, data)

    def _view(self, book: Book) -> dict:
        sheets = []
        for tab in book.data["tabs"]:
            entry = {
                "properties": {
                    "sheetId": tab["sheetId"],
                    "title": tab["title"],
                    "index": tab["index"],
                    "sheetType": "GRID",
                    "gridProperties": {"rowCount": tab["rowCount"], "columnCount": tab["colCount"]},
                }
            }
            if tab.get("conditionalFormats"):
                entry["conditionalFormats"] = copy.deepcopy(tab["conditionalFormats"])
            sheets.append(entry)
        return {
            "spreadsheetId": book.sid,
            "properties": {"title": book.data["title"], "locale": book.data.get("locale", "en_GB"), "timeZone": "Asia/Kolkata", "autoRecalc": "ON_CHANGE"},
            "sheets": sheets,
            "spreadsheetUrl": f"https://docs.google.com/spreadsheets/d/{book.sid}/edit",
        }

    def get(self, spreadsheetId=None, fields=None, ranges=None, includeGridData=None, **_):
        uri = api_uri(BASE, f"/v4/spreadsheets/{spreadsheetId}", fields=fields)
        return FakeRequest(lambda: self._view(self._book(spreadsheetId, uri)), uri)

    def create(self, body=None, fields=None, **_):
        def run():
            body_ = body or {}
            sid = self.ws.ids.new("sheet", 44, "b64")
            titles = [s.get("properties", {}).get("title") for s in body_.get("sheets", [])] or ["Sheet1"]
            self.ws.add_sheet(sid, body_.get("properties", {}).get("title", "Untitled spreadsheet"), [{"title": t} for t in titles], origin="agent")
            return self._view(Book(self.ws, sid, self.books[sid]))

        return FakeRequest(run, api_uri(BASE, "/v4/spreadsheets", fields=fields), "POST")

    def values(self):
        return _Values(self.ws, self)

    def batchUpdate(self, spreadsheetId=None, body=None, **_):
        uri = api_uri(BASE, f"/v4/spreadsheets/{spreadsheetId}:batchUpdate")

        def run():
            book = self._book(spreadsheetId, uri)
            trial = copy.deepcopy(book.data)
            tbook = Book(self.ws, spreadsheetId, trial)
            replies = []
            for i, request in enumerate((body or {}).get("requests", [])):
                (kind, payload), = request.items()
                handler = getattr(self, "_" + kind, None)
                if handler is None:
                    raise _err(400, f"Invalid requests[{i}]: Unsupported request {kind} in the lab.", uri)
                try:
                    replies.append(handler(tbook, payload or {}))
                except _ReqError as err:
                    raise _err(400, f"Invalid requests[{i}].{kind}: {err}", uri)
            book.data.clear()
            book.data.update(trial)
            self.ws.touch_file(spreadsheetId)
            return {"spreadsheetId": spreadsheetId, "replies": replies}

        return FakeRequest(run, uri, "POST")

    # ---- batchUpdate handlers ---------------------------------------------
    def _addSheet(self, book: Book, req):
        props = req.get("properties", {})
        title = props.get("title") or f"Sheet{len(book.data['tabs']) + 1}"
        if book.tab(title) is not None:
            raise _ReqError(f"A sheet with the name ‘{title}’ already exists. Please enter another name.")
        tab = new_tab(title, len(book.data["tabs"]), f"{book.sid}:{title}:{self.ws.clock.stamp().isoformat()}")
        book.data["tabs"].append(tab)
        return {"addSheet": {"properties": {"sheetId": tab["sheetId"], "title": title, "index": tab["index"], "sheetType": "GRID", "gridProperties": {"rowCount": 1000, "columnCount": 26}}}}

    def _grid_tab(self, book, grid):
        tab = book.tab_by_id(grid.get("sheetId", 0))
        if tab is None:
            raise _ReqError(f"No grid with id: {grid.get('sheetId', 0)}")
        return tab

    def _repeatCell(self, book, req):
        grid = req.get("range", {})
        tab = self._grid_tab(book, grid)
        fmt = (req.get("cell") or {}).get("userEnteredFormat", {})
        fields = [f.strip() for f in (req.get("fields") or "").split(",") if f.strip()]
        flat = {}
        for field in fields:
            path = field.split(".")[1:] if field.startswith("userEnteredFormat") else field.split(".")
            if path and path[0] == "numberFormat":
                flat["numberFormat"] = fmt.get("numberFormat")
            elif path and path[0] == "backgroundColor":
                flat["backgroundColor"] = fmt.get("backgroundColor")
            elif path and path[0] == "textFormat":
                flat["textFormat"] = fmt.get("textFormat")
        tab.setdefault("formats", []).append({"range": {k: v for k, v in grid.items() if k != "sheetId"}, "format": flat})
        return {}

    def _rules(self, book, sheet_id):
        tab = book.tab_by_id(sheet_id)
        if tab is None:
            raise _ReqError(f"No grid with id: {sheet_id}")
        return tab.setdefault("conditionalFormats", [])

    def _addConditionalFormatRule(self, book, req):
        rule = req.get("rule", {})
        ranges = rule.get("ranges") or [{}]
        rules = self._rules(book, ranges[0].get("sheetId", 0))
        index = req.get("index", 0)
        if index > len(rules):
            raise _ReqError(f"The index {index} is out of bounds.")
        rules.insert(index, copy.deepcopy(rule))
        return {}

    def _updateConditionalFormatRule(self, book, req):
        rules = self._rules(book, req.get("sheetId", 0))
        index = req.get("index", 0)
        if not 0 <= index < len(rules):
            raise _ReqError(f"No conditional format on sheet: {req.get('sheetId', 0)} at index: {index}")
        if "rule" in req:
            rules[index] = copy.deepcopy(req["rule"])
        if "newIndex" in req:
            rule = rules.pop(index)
            rules.insert(req["newIndex"], rule)
        return {}

    def _deleteConditionalFormatRule(self, book, req):
        rules = self._rules(book, req.get("sheetId", 0))
        index = req.get("index", 0)
        if not 0 <= index < len(rules):
            raise _ReqError(f"No conditional format on sheet: {req.get('sheetId', 0)} at index: {index}")
        rule = rules.pop(index)
        return {"deleteConditionalFormatRule": {"rule": rule}}


class _ReqError(Exception):
    pass


class _Values:
    def __init__(self, ws, parent: _Spreadsheets):
        self.ws = ws
        self.parent = parent

    def get(self, spreadsheetId=None, range=None, valueRenderOption=None, **_):
        uri = api_uri(BASE, f"/v4/spreadsheets/{spreadsheetId}/values/{quote_id(range)}")

        def run():
            book = self.parent._book(spreadsheetId, uri)
            tab, r0, c0, r1, c1 = book.resolve_range(range, uri)
            rows_used, cols_used = book.extent(tab)
            r1, c1 = min(r1, rows_used - 1), min(c1, cols_used - 1)
            out_rows = []
            for r in _range(r0, r1):
                row = []
                for c in _range(c0, c1):
                    if valueRenderOption == "UNFORMATTED_VALUE":
                        v = book.value(tab, r, c)
                        row.append("" if v is None else (v.code if isinstance(v, calc.FormulaError) else v))
                    elif valueRenderOption == "FORMULA":
                        cell = tab["cells"].get(book.key(r, c), {})
                        row.append(cell.get("formula", cell.get("v", "")))
                    else:
                        row.append(book.shown(tab, r, c))
                while row and row[-1] == "":
                    row.pop()
                out_rows.append(row)
            while out_rows and not out_rows[-1]:
                out_rows.pop()
            label = calc.a1_label(tab["title"], r0, c0, max(r1, r0), max(c1, c0))
            result = {"range": label, "majorDimension": "ROWS"}
            if out_rows:
                result["values"] = out_rows
            return result

        return FakeRequest(run, uri)

    def update(self, spreadsheetId=None, range=None, valueInputOption=None, body=None, **_):
        uri = api_uri(BASE, f"/v4/spreadsheets/{spreadsheetId}/values/{quote_id(range)}", valueInputOption=valueInputOption)

        def run():
            if valueInputOption not in ("RAW", "USER_ENTERED"):
                raise _err(400, "Invalid valueInputOption: must be RAW or USER_ENTERED", uri)
            book = self.parent._book(spreadsheetId, uri)
            sheet, a1 = calc.split_sheet(range)
            box = calc.parse_a1(a1) if a1 else None
            tab, r0, c0, r1, c1 = book.resolve_range(range, uri)
            values = (body or {}).get("values", [])
            explicit_end = box is not None and ":" in a1
            for i, row in enumerate(values):
                for j, _ in enumerate(row):
                    if explicit_end and (r0 + i > r1 or c0 + j > c1):
                        raise _err(400, f"Requested writing within range [{range}], but tried writing to {'row' if r0 + i > r1 else 'column'} [{(r0 + i + 1) if r0 + i > r1 else calc.index_to_col(c0 + j)}]", uri)
            cells = 0
            for i, row in enumerate(values):
                for j, value in enumerate(row):
                    key = book.key(r0 + i, c0 + j)
                    cell = calc.parse_input(value, valueInputOption == "RAW")
                    if cell:
                        tab["cells"][key] = cell
                    else:
                        tab["cells"].pop(key, None)
                    cells += 1
            self.ws.touch_file(spreadsheetId)
            ncols = max((len(r) for r in values), default=0)
            end_r, end_c = r0 + max(len(values), 1) - 1, c0 + max(ncols, 1) - 1
            return {
                "spreadsheetId": spreadsheetId,
                "updatedRange": calc.a1_label(tab["title"], r0, c0, end_r, end_c),
                "updatedRows": len(values),
                "updatedColumns": ncols,
                "updatedCells": cells,
            }

        return FakeRequest(run, uri, "PUT")

    def clear(self, spreadsheetId=None, range=None, body=None, **_):
        uri = api_uri(BASE, f"/v4/spreadsheets/{spreadsheetId}/values/{quote_id(range)}:clear")

        def run():
            book = self.parent._book(spreadsheetId, uri)
            tab, r0, c0, r1, c1 = book.resolve_range(range, uri)
            for key in list(tab["cells"]):
                r, c = map(int, key.split(","))
                if r0 <= r <= r1 and c0 <= c <= c1:
                    del tab["cells"][key]
            self.ws.touch_file(spreadsheetId)
            return {"spreadsheetId": spreadsheetId, "clearedRange": calc.a1_label(tab["title"], r0, c0, r1, c1)}

        return FakeRequest(run, uri, "POST")


def _range(a, b):
    return range(a, b + 1) if b >= a else range(0)


def new_tab(title: str, index: int, seed: str) -> dict:
    sheet_id = int(make_id("sheetId", seed, 12), 16) % 2_000_000_000
    return {"sheetId": sheet_id, "title": title, "index": index, "rowCount": 1000, "colCount": 26, "cells": {}, "conditionalFormats": [], "formats": []}
