"""PASS/FAIL for every tool bug fixed on 2026-09-27, read from a probe log.

Run after probe_tools.py (reads the newest eval/probe/out/prb*.jsonl, or the path given):
    .venv/Scripts/python.exe eval/probe/checks.py [path/to/prbxxxxxx.jsonl]
Exits non-zero if any check fails or its probe step is missing.
"""

import json
import re
import sys
from pathlib import Path

OUT_DIR = Path(__file__).parent / "out"


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def parsed(record: dict):
    """The tool result as a dict when it is JSON, else the raw value."""
    result = record["result"]
    if isinstance(result, str):
        try:
            return json.loads(result)
        except ValueError:
            return result
    return result


def text(record: dict) -> str:
    value = parsed(record)
    if isinstance(value, dict):
        return value.get("message") or json.dumps(value, ensure_ascii=False)
    return value or ""


def ok(record: dict) -> bool:
    value = parsed(record)
    if record["raised"] or not isinstance(value, dict):
        return False
    return value.get("status") == "success" or value.get("success") is True


def main() -> int:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        logs = sorted(OUT_DIR.glob("prb*.jsonl"), key=lambda p: p.stat().st_mtime)
        if not logs:
            print("No probe logs found. Run probe_tools.py first.")
            return 1
        path = logs[-1]
    records = load(path)
    tag = path.stem.removeprefix("fake_")

    def find(tool: str, note: str | None = None, startswith: bool = False) -> list[dict]:
        out = []
        for r in records:
            if r["tool"] != tool:
                continue
            if note is None or r["note"] == note or (startswith and r["note"].startswith(note)):
                out.append(r)
        return out

    def rules(message: str) -> list[str]:
        return re.findall(r"\[\d+\] [^\n]+", message)

    checks = []

    def check(label: str, found: list[dict], predicate):
        if not found:
            checks.append((label, None))
            return
        try:
            checks.append((label, bool(predicate(found))))
        except Exception:
            checks.append((label, False))

    # Gmail
    check("delete_label deletes", find("delete_label", "cleanup via tool"), lambda rs: all(ok(r) for r in rs))
    check("search_by_label finds the labelled mail", find("search_by_label", ""), lambda rs: parsed(rs[0])["count"] >= 1)
    check(
        "read_email keeps ₹ and spaces between lines",
        find("read_email", ""),
        lambda rs: "₹1,84,500" in parsed(rs[0])["content"] and "2026 Regards" in parsed(rs[0])["content"],
    )

    check(
        "list_filters shows an existing filter",
        find("list_filters", "after direct create"),
        lambda rs: parsed(rs[0])["count"] >= 1,
    )

    # Calendar
    check("reminders as a JSON string", find("create_event", "reminders as JSON string", startswith=True), lambda rs: ok(rs[0]))
    check("modify_event: attendees only", find("modify_event", "attendees replaced"), lambda rs: ok(rs[0]))
    check(
        "attendees replaced, times kept",
        find("get_events", "after attendee replace"),
        lambda rs: f"+{tag}a@" in text(rs[0])
        and f"+{tag}b@" not in text(rs[0])
        and "Starts: 2026-11-10T15:00:00" in text(rs[0]),
    )
    check("modify_event: description only", find("modify_event", "description only"), lambda rs: ok(rs[0]))
    check(
        "description replaced, attendees kept",
        find("get_events", "after description change"),
        lambda rs: "Replaced text" in text(rs[0]) and f"+{tag}a@" in text(rs[0]),
    )
    check("modify_event: Meet setting only", find("modify_event", "remove meet"), lambda rs: ok(rs[0]))

    # Tasks
    check("get_task_list returns details", find("get_task_list"), lambda rs: ok(rs[0]) and "Task List Details" in text(rs[0]))
    check("update_task reports success", find("update_task", "complete"), lambda rs: ok(rs[0]))
    check("update_task_list reports success", find("update_task_list"), lambda rs: ok(rs[0]))
    check(
        "list_tasks bad ID returns an error string",
        find("list_tasks", "bogus list"),
        lambda rs: not rs[0]["raised"] and text(rs[0]).startswith("API error") and "start_google_auth" not in text(rs[0]),
    )

    # Docs
    check(
        "search_docs finds the new doc",
        find("search_docs", "index check") + find("search_docs", "index check retry"),
        lambda rs: any(parsed(r)["count"] >= 1 for r in rs),
    )
    check("search_docs by title words", find("search_docs", "title words"), lambda rs: parsed(rs[0])["count"] >= 1)
    check("list_docs_in_folder lists docs", find("list_docs_in_folder", "after create"), lambda rs: parsed(rs[0])["count"] >= 1)
    check("modify_doc_text formatting", find("modify_doc_text", "format range"), lambda rs: ok(rs[0]))
    check("inspect_doc_structure basic", find("inspect_doc_structure", ""), lambda rs: ok(rs[0]))
    check(
        "inspect_doc_structure basic, with table",
        find("inspect_doc_structure", "basic, with table"),
        lambda rs: ok(rs[0]) and "table_details" in parsed(rs[0])["structure"],
    )
    check(
        "inspect_doc_structure detailed, with table",
        find("inspect_doc_structure", "detailed, with table"),
        lambda rs: ok(rs[0]) and "tables" in parsed(rs[0])["structure"],
    )
    check("header and footer created", find("update_doc_headers_footers"), lambda rs: len(rs) == 2 and all(ok(r) for r in rs))
    check("batch_update_doc", find("batch_update_doc"), lambda rs: ok(rs[0]))
    check("insert_doc_image with width only", find("insert_doc_image"), lambda rs: ok(rs[0]))
    check("export_doc_to_pdf", find("export_doc_to_pdf"), lambda rs: ok(rs[0]) and parsed(rs[0])["pdf_id"])
    check(
        "comment output has real line breaks",
        find("create_document_comment"),
        lambda rs: "\n" in rs[0]["result"] and "\\n" not in rs[0]["result"],
    )

    # Sheets
    check("create_spreadsheet fills its ID field", find("create_spreadsheet"), lambda rs: parsed(rs[0])["spreadsheet_id"])
    check("list_spreadsheets finds the new sheet", find("list_spreadsheets", "after create"), lambda rs: f"Probe {tag} Budget" in text(rs[0]))
    check(
        "get_spreadsheet_info shows every tab",
        find("get_spreadsheet_info", "with rules"),
        lambda rs: all(f'"{name}"' in text(rs[0]) for name in ("Line Items", "Summary", "Extra")),
    )
    check(
        "printed rule order matches the sheet",
        find("add_conditional_formatting", "custom formula") + find("get_spreadsheet_info", "with rules"),
        lambda rs: len(rs) == 2 and rules(text(rs[0])) == rules(text(rs[1])),
    )

    failed = 0
    print(f"Checks for {path.name}\n")
    for label, result in checks:
        status = "PASS" if result else ("MISSING" if result is None else "FAIL")
        failed += status != "PASS"
        print(f"  {status:7s} {label}")
    print(f"\n{len(checks) - failed}/{len(checks)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
