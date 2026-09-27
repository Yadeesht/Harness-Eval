"""Call the app_tools tools against the dummy Google account and record what comes back.

The records are the reference for writing the 40 tasks and for making the fake
server return what the real tools return. Raw results go to
eval/probe/out/<tag>.jsonl (gitignored); the written summary lives in
eval/design/tool_reference.md.

Safety:
- Refuses to run unless every token belongs to the account confirmed by auth.py.
- Only touches objects it creates. Each carries a unique tag and is deleted at the end.
- Email goes only to the dummy account itself; calendar guests are +aliases of it.
- open_email is skipped: it opens a browser window.

Run from the repo root:
    .venv/Scripts/python.exe eval/probe/probe_tools.py                  # all apps
    .venv/Scripts/python.exe eval/probe/probe_tools.py --apps gmail,tasks
    .venv/Scripts/python.exe eval/probe/probe_tools.py --sweep prbabcdef  # clean up a crashed run
"""

import argparse
import asyncio
import json
import logging
import random
import re
import string
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import langchain_core.tools.base  # noqa: E402

# Same compatibility patch main.py applies before importing the tools.
if not hasattr(langchain_core.tools.base, "TOOL_MESSAGE_BLOCK_TYPES"):
    langchain_core.tools.base.TOOL_MESSAGE_BLOCK_TYPES = ("text",)

from google.auth.transport.requests import Request  # noqa: E402
from google.oauth2.credentials import Credentials  # noqa: E402

from app_tools.tools.google import calendar_tools as cal  # noqa: E402
from app_tools.tools.google import gdocs_tools as gd  # noqa: E402
from app_tools.tools.google import gmail_tools as gm  # noqa: E402
from app_tools.tools.google import gsheet_tools as gs  # noqa: E402
from app_tools.tools.google import gtask_tools as tk  # noqa: E402

logging.getLogger().setLevel(logging.WARNING)

OUT_DIR = Path(__file__).parent / "out"
ACCOUNT_FILE = OUT_DIR / "account.json"
CRED_DIR = REPO / "app_tools" / "cred"
TOKEN_FILES = [
    "gmail_token.json",
    "calendar_token.json",
    "gdrive_token.json",
    "gdocs_token.json",
    "gsheet_token.json",
    "gtask_token.json",
]

# A quiet week well in the future, so probe events never sit among real ones.
WEEK = ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"]

DOC_COMMENTS = gd._comment_tools
SHEET_COMMENTS = gs._comment_tools


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


def text_of(result) -> str:
    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)


def find(pattern: str, result, group: int = 1):
    match = re.search(pattern, text_of(result) or "")
    return match.group(group) if match else None


class Probe:
    """Calls one tool, times it and appends the full record to the JSONL file."""

    def __init__(self, out_path: Path):
        self.out_path = out_path
        self.out = open(out_path, "a", encoding="utf-8")
        self.n = 0

    async def call(self, app: str, fn, note: str = "", **kwargs):
        self.n += 1
        start = time.perf_counter()
        raised = None
        try:
            result = await fn(**kwargs)
        except Exception as error:  # record it; the probe keeps going
            result = None
            raised = f"{type(error).__name__}: {error}"
        latency_ms = round((time.perf_counter() - start) * 1000)
        chars = len(text_of(result)) if result is not None else 0
        record = {
            "step": self.n,
            "app": app,
            "tool": fn.__name__,
            "note": note,
            "args": kwargs,
            "latency_ms": latency_ms,
            "chars": chars,
            "raised": raised,
            "result": result,
        }
        self.out.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self.out.flush()
        line = f"[{self.n:3d}] {app:8s} {fn.__name__:32s} {latency_ms:6d} ms {chars:7d} ch  {note}"
        print(line + (f"  RAISED {raised}" if raised else ""), flush=True)
        return result

    def close(self):
        self.out.close()


async def quietly(label: str, fn, *args, **kwargs):
    """Cleanup call that must never stop the rest of the cleanup."""
    try:
        return await asyncio.to_thread(fn, *args, **kwargs)
    except Exception as error:
        print(f"   cleanup: {label} failed: {error}", flush=True)


def plus(address: str, suffix: str) -> str:
    local, domain = address.split("@")
    return f"{local}+{suffix}@{domain}"


# ---------------------------------------------------------------------------
# Account check
# ---------------------------------------------------------------------------


def verify_account() -> str:
    """Every token must be valid (refreshing without a browser) and belong to the confirmed account."""
    if not ACCOUNT_FILE.exists():
        sys.exit("No confirmed account. Run eval/probe/auth.py --account <dummy-address> first.")
    expected = json.loads(ACCOUNT_FILE.read_text(encoding="utf-8"))["account"]

    for name in TOKEN_FILES:
        path = CRED_DIR / name
        if not path.exists():
            sys.exit(f"Missing {path}. Run eval/probe/auth.py first.")
        creds = Credentials.from_authorized_user_file(str(path))
        if not creds.valid:
            try:
                creds.refresh(Request())
            except Exception as error:
                sys.exit(f"{name} can't be refreshed ({error}). Run eval/probe/auth.py again.")
            path.write_text(creds.to_json(), encoding="utf-8")

    actual = gm.get_service().users().getProfile(userId="me").execute()["emailAddress"].lower()
    if actual != expected:
        sys.exit(f"Token belongs to {actual}, but the confirmed dummy account is {expected}. Stopping.")
    print(f"Account check passed: {actual}", flush=True)
    return actual


# ---------------------------------------------------------------------------
# Gmail
# ---------------------------------------------------------------------------


async def probe_gmail(p: Probe, me: str, tag: str):
    service = gm.get_service()
    messages, labels, drafts, filters = [], [], [], []
    try:
        # Read-only baseline on whatever the account already has.
        await p.call("gmail", gm.list_labels)
        await p.call("gmail", gm.list_folders)
        await p.call("gmail", gm.list_filters)
        await p.call("gmail", gm.list_drafts)
        await p.call("gmail", gm.get_unread_emails, date=7, max_results=3)
        await p.call("gmail", gm.search_emails, note="baseline", query="in:inbox", max_results=3)
        await p.call("gmail", gm.list_archived, max_results=3)

        # Probe mail, sent to the dummy account itself.
        mails = [
            (
                f"[{tag}] Invoice INV-2291 for September",
                "Hi Yadeesh,\n\nPlease find the invoice for September.\n"
                "Amount due: ₹1,84,500\nDue date: 15 Oct 2026\n\nRegards,\nPriya Nair\nFinance",
            ),
            (
                f"[{tag}] Re: Q4 OKR drafts",
                "Here's my draft. It's rough & still missing the <latency> targets, "
                'so treat the "stretch" goal as tentative.\n'
                + "Objective 1: reduce p95 latency on the payments API. " * 8
                + "\nLink: https://example.com/okr?team=platform&q=4",
            ),
            (
                f"[{tag}] Weekly digest",
                "Top stories this week\n- Kubernetes 1.34 released\n- Service mesh benchmarks\n",
            ),
        ]
        for subject, body in mails:
            sent = await p.call("gmail", gm.send_email, recipient_id=me, subject=subject, message=body)
            if isinstance(sent, dict) and sent.get("message_id"):
                messages.append(sent["message_id"])

        await asyncio.sleep(10)  # search index lags a few seconds behind sends
        found = await p.call("gmail", gm.search_emails, note="index check", query=tag)
        if isinstance(found, dict) and found.get("count", 0) < len(messages):
            await asyncio.sleep(15)
            await p.call("gmail", gm.search_emails, note="index check retry", query=tag)

        # Search semantics.
        today = time.strftime("%Y/%m/%d")
        queries = [
            (f"{tag} invoice", "subject word"),
            (f"{tag} Kubernetes", "body word"),
            (f"{tag} kubernetes", "case"),
            (f"{tag} kuber", "partial word"),
            (f'{tag} "due date"', "quoted phrase"),
            (f"{tag} 2291", "part of INV-2291"),
            (f"{tag} INV-2291", "hyphenated token"),
            (f"{tag} 184500", "number without grouping"),
            (f"{tag} Nair", "name in body"),
            (f"{tag} subject:invoice", "subject:"),
            (f"{tag} from:me", "from:me"),
            (f"{tag} to:me", "to:me"),
            (f"{tag} in:sent", "in:sent"),
            (f"{tag} in:inbox", "in:inbox"),
            (f"{tag} is:unread", "is:unread"),
            (f"{tag} newer_than:1d", "newer_than"),
            (f"{tag} older_than:1d", "older_than"),
            (f"{tag} after:{today}", "after: today"),
            (f"{tag} invoice OR digest", "OR"),
            (f"{tag} {{invoice digest}}", "braces OR"),
            (f"{tag} -invoice", "negation"),
            (f"{tag} category:primary", "category:primary"),
            (f"{tag} has:attachment", "has:attachment"),
            (f"{tag} zzqqxxnomatch", "empty result"),
        ]
        for query, note in queries:
            await p.call("gmail", gm.search_emails, note=note, query=query)
        await p.call("gmail", gm.search_emails, note="max_results=1", query=tag, max_results=1)
        await p.call("gmail", gm.search_emails, note="empty query", query="")

        # Reading and unread state.
        await p.call("gmail", gm.get_unread_emails, note="after send", date=1, max_results=10)
        if messages:
            await p.call("gmail", gm.read_email, email_id=messages[0])
            await p.call("gmail", gm.read_email, note="long body", email_id=messages[1])
            await p.call("gmail", gm.mark_email_as_read, email_id=messages[2])
        await p.call("gmail", gm.search_emails, note="unread after read_email", query=f"{tag} is:unread")

        # Labels, including nested names and label: query syntax.
        nested = f"Probe{tag}/Billing"
        made = await p.call("gmail", gm.create_label, name=nested)
        label_id = made.get("label_id") if isinstance(made, dict) else None
        if label_id:
            labels.append(label_id)
        await p.call("gmail", gm.create_label, note="duplicate name", name=nested)
        await p.call("gmail", gm.list_labels, note="after nested create")
        if label_id and messages:
            await p.call("gmail", gm.apply_label, email_id=messages[0], label_id=label_id)
            await asyncio.sleep(3)
            await p.call("gmail", gm.search_by_label, label_id=label_id)
            for query, note in [
                (f"label:{nested}", "label: with slash"),
                (f"label:probe{tag}-billing", "label: dashed lowercase"),
                (f'label:"{nested}"', "label: quoted"),
                (f"label:{label_id}", "label: by id"),
            ]:
                await p.call("gmail", gm.search_emails, note=note, query=query)
            await p.call("gmail", gm.remove_label, email_id=messages[0], label_id=label_id)
            await p.call("gmail", gm.rename_label, label_id=label_id, new_name=f"Probe{tag}/Invoices")

        folder = await p.call("gmail", gm.create_folder, name=f"Probe{tag}Folder")
        folder_id = folder.get("folder_id") if isinstance(folder, dict) else None
        if folder_id:
            labels.append(folder_id)
        await p.call("gmail", gm.list_folders, note="after create")
        if folder_id and len(messages) > 2:
            await p.call("gmail", gm.move_to_folder, email_id=messages[2], folder_id=folder_id)
            await p.call("gmail", gm.search_emails, note="inbox after move", query=f"{tag} in:inbox")
            await p.call("gmail", gm.restore_to_inbox, email_id=messages[2])
        if len(messages) > 1:
            await p.call("gmail", gm.archive_email, email_id=messages[1])
        await p.call("gmail", gm.batch_archive, query=f"{tag} digest", max_emails=5)
        await p.call("gmail", gm.batch_archive, note="no match", query=f"{tag} zzqqxxnomatch", max_emails=5)
        await p.call("gmail", gm.list_archived, note="after archive", max_results=5)
        await p.call("gmail", gm.search_emails, note="inbox after archive", query=f"{tag} in:inbox")

        # Drafts.
        draft = await p.call(
            "gmail", gm.create_draft, recipient_id=me, subject=f"[{tag}] Draft check", message="Draft body line."
        )
        if isinstance(draft, dict) and draft.get("draft_id"):
            drafts.append(draft["draft_id"])
        await p.call("gmail", gm.list_drafts, note="after create")

        # Filters: the tools can't create one, so make a harmless one directly, then read and delete it.
        try:
            body = {
                "criteria": {"from": f"{tag}@example.invalid"},
                "action": {"addLabelIds": [label_id] if label_id else [], "removeLabelIds": ["INBOX"]},
            }
            created = await asyncio.to_thread(
                service.users().settings().filters().create(userId="me", body=body).execute
            )
            filters.append(created["id"])
            await p.call("gmail", gm.list_filters, note="after direct create")
            await p.call("gmail", gm.get_filter, filter_id=created["id"])
            await p.call("gmail", gm.delete_filter_tool, filter_id=created["id"])
            filters.remove(created["id"])
        except Exception as error:
            print(f"   filter create skipped: {error}", flush=True)

        # Error shapes. None of these can change anything.
        await p.call("gmail", gm.read_email, note="bogus id", email_id="0000bogus0000")
        await p.call("gmail", gm.trash_email, note="bogus id", email_id="0000bogus0000")
        await p.call("gmail", gm.get_filter, note="bogus id", filter_id="bogusfilter")
        await p.call("gmail", gm.delete_label, note="bogus id", label_id="Label_bogus")
        await p.call("gmail", gm.send_email, note="invalid address", recipient_id="not-an-email", subject="x", message="x")
        if messages:
            await p.call("gmail", gm.apply_label, note="bogus label", email_id=messages[0], label_id="Label_bogus")
            await p.call("gmail", gm.trash_email, email_id=messages[0])
    finally:
        for message_id in messages:
            await quietly("delete message", service.users().messages().delete(userId="me", id=message_id).execute)
        for draft_id in drafts:
            await quietly("delete draft", service.users().drafts().delete(userId="me", id=draft_id).execute)
        for filter_id in filters:
            await quietly("delete filter", service.users().settings().filters().delete(userId="me", id=filter_id).execute)
        for label_id in labels:
            # Delete through the tool; fall back to the API if the tool fails.
            deleted = await p.call("gmail", gm.delete_label, note="cleanup via tool", label_id=label_id)
            if not (isinstance(deleted, dict) and deleted.get("success")):
                await quietly("delete label", service.users().labels().delete(userId="me", id=label_id).execute)


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------


def event_ids(result, tag: str) -> dict:
    """Map probe event titles to IDs from a basic get_events listing."""
    try:
        message = json.loads(result).get("message", "")
    except Exception:
        return {}
    pairs = re.findall(r'- "\[' + tag + r'\] (.*?)" \(Starts: .*?\) ID: (\S+) \|', message)
    return {title: event_id for title, event_id in pairs}


async def probe_calendar(p: Probe, me: str, tag: str):
    service = cal.get_service()
    guest_a, guest_b = plus(me, f"{tag}a"), plus(me, f"{tag}b")
    created = set()
    window = {"time_min": f"{WEEK[0]}T00:00:00", "time_max": f"{WEEK[-1]}T23:59:00"}
    try:
        listing = await p.call("calendar", cal.list_calendars)
        await p.call("calendar", cal.get_events, note="default window", max_results=5)
        await p.call("calendar", cal.get_events, note="next 14 days detailed", max_results=10, detailed=True)

        # A read-only calendar (e.g. public holidays), if the account has one.
        read_only = None
        try:
            for entry in json.loads(listing).get("calendars", []):
                if entry.get("accessRole") in ("reader", "freeBusyReader"):
                    read_only = entry["id"]
                    break
        except Exception:
            pass
        if read_only:
            await p.call(
                "calendar", cal.get_events, note="read-only calendar",
                calendar_id=read_only, time_min="2026-10-01", time_max="2026-12-31", max_results=5,
            )
            blocked = await p.call(
                "calendar", cal.create_event, note="write to read-only calendar",
                calendar_id=read_only, summary=f"[{tag}] should fail",
                start_time=f"{WEEK[0]}T09:00:00", end_time=f"{WEEK[0]}T09:30:00",
            )
            if "success" in (text_of(blocked) or ""):
                print("   unexpected: write to read-only calendar succeeded", flush=True)

        await p.call(
            "calendar", cal.create_event, note="guests + meet + reminders",
            summary=f"[{tag}] Architecture Review", start_time=f"{WEEK[1]}T15:00:00", end_time=f"{WEEK[1]}T16:00:00",
            attendees=[guest_a, guest_b], description="Agenda:\n1. Mesh rollout\n2. Budget", location="Room 4B",
            add_google_meet=True, reminders=[{"method": "popup", "minutes": 15}],
        )
        await p.call(
            "calendar", cal.create_event, note="reminders as JSON string (docstring allows it)",
            summary=f"[{tag}] Reminder string", start_time=f"{WEEK[0]}T09:00:00", end_time=f"{WEEK[0]}T09:15:00",
            reminders='[{"method": "popup", "minutes": 15}]',
        )
        await p.call(
            "calendar", cal.create_event, note="self listed as guest",
            summary=f"[{tag}] 1:1 with Meera", start_time=f"{WEEK[1]}T11:00:00", end_time=f"{WEEK[1]}T11:30:00",
            attendees=[me, guest_a],
        )
        await p.call(
            "calendar", cal.create_event, note="all-day, end exclusive, transparent",
            summary=f"[{tag}] OOO", start_time=WEEK[2], end_time=WEEK[4], transparency="transparent",
        )
        await p.call(
            "calendar", cal.create_event, note="explicit +01:00 offset",
            summary=f"[{tag}] Brightline call", start_time=f"{WEEK[3]}T10:00:00+01:00",
            end_time=f"{WEEK[3]}T10:45:00+01:00",
        )
        await p.call(
            "calendar", cal.create_event, note="no guests",
            summary=f"[{tag}] Focus block", start_time=f"{WEEK[0]}T14:00:00", end_time=f"{WEEK[0]}T16:00:00",
        )
        await p.call(
            "calendar", cal.create_event, note="end before start",
            summary=f"[{tag}] Broken", start_time=f"{WEEK[0]}T12:00:00", end_time=f"{WEEK[0]}T11:00:00",
        )

        listed = await p.call("calendar", cal.get_events, note="probe week basic", query=tag, max_results=20, **window)
        ids = event_ids(listed, tag)
        created.update(ids.values())
        await p.call(
            "calendar", cal.get_events, note="probe week detailed",
            query=tag, max_results=20, detailed=True, include_attachments=True, **window,
        )
        await p.call("calendar", cal.get_events, note="date-only bounds", query=tag, time_min=WEEK[0], time_max=WEEK[-1])

        review = ids.get("Architecture Review")
        if review:
            await p.call("calendar", cal.get_events, note="single basic", event_id=review)
            await p.call("calendar", cal.get_events, note="single detailed", event_id=review, detailed=True)
            for query, note in [
                ("Architecture", "title word"),
                ("Archi", "partial word"),
                ("Room 4B", "location"),
                ("Mesh rollout", "description words"),
                (guest_a, "attendee address"),
            ]:
                await p.call("calendar", cal.get_events, note=f"query: {note}", query=query, max_results=10, **window)

            await p.call("calendar", cal.modify_event, note="attendees replaced", event_id=review, attendees=[guest_a])
            await p.call("calendar", cal.get_events, note="after attendee replace", event_id=review, detailed=True)
            await p.call("calendar", cal.modify_event, note="description only", event_id=review, description="Replaced text")
            await p.call("calendar", cal.get_events, note="after description change", event_id=review, detailed=True)
            await p.call(
                "calendar", cal.modify_event, note="move time",
                event_id=review, start_time=f"{WEEK[1]}T16:00:00", end_time=f"{WEEK[1]}T17:00:00",
            )
            await p.call("calendar", cal.modify_event, note="remove meet", event_id=review, add_google_meet=False)
            await p.call("calendar", cal.modify_event, note="no fields", event_id=review)

        await p.call("calendar", cal.get_events, note="bogus id", event_id="bogus0000event")
        await p.call("calendar", cal.modify_event, note="bogus id", event_id="bogus0000event", summary="x")
        await p.call("calendar", cal.delete_event, note="bogus id", event_id="bogus0000event")
        await p.call(
            "calendar", cal.get_events, note="empty range",
            time_min="2031-01-01T00:00:00", time_max="2031-01-02T00:00:00",
        )
        for event_id in list(created):
            await p.call("calendar", cal.delete_event, event_id=event_id)
            created.discard(event_id)
    finally:
        # Anything still tagged in the probe week (including a stray create on a read-only calendar).
        leftover = await asyncio.to_thread(
            lambda: service.events()
            .list(calendarId="primary", q=tag, timeMin=f"{WEEK[0]}T00:00:00Z", timeMax="2026-11-14T00:00:00Z", singleEvents=True)
            .execute()
        )
        for item in leftover.get("items", []):
            await quietly("delete event", service.events().delete(calendarId="primary", eventId=item["id"]).execute)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


async def probe_tasks(p: Probe, me: str, tag: str):
    lists = []
    try:
        await p.call("tasks", tk.list_task_lists)
        first = await p.call("tasks", tk.create_task_list, title=f"Probe {tag}")
        second = await p.call("tasks", tk.create_task_list, title=f"Probe {tag} B")
        list_a, list_b = find(r"ID: ([\w-]+)", first), find(r"ID: ([\w-]+)", second)
        lists = [x for x in (list_a, list_b) if x]
        if not (list_a and list_b):
            return

        await p.call("tasks", tk.get_task_list, task_list_id=list_a)
        await p.call("tasks", tk.update_task_list, task_list_id=list_b, title=f"Probe {tag} Renamed")

        long_notes = (
            "Context: agreed in the 28 Sep sync that the platform team owns the capacity model for Q4. "
            "Update from Meera on 2 Oct: this is DONE, she already sent the numbers to Rahul."
        )
        parent = await p.call(
            "tasks", tk.create_task, note="notes > 100 chars, due with time",
            task_list_id=list_a, title="Q4 capacity model", notes=long_notes, due="2026-10-30T18:30:00Z",
        )
        parent_id = find(r"ID: ([\w-]+)", parent)
        child = await p.call("tasks", tk.create_task, note="subtask", task_list_id=list_a, title="Collect numbers", parent=parent_id)
        child_id = find(r"ID: ([\w-]+)", child)
        dated = await p.call("tasks", tk.create_task, note="date-only due", task_list_id=list_a, title="Q4 budget draft", due="2026-10-30T00:00:00Z")
        await p.call("tasks", tk.create_task, note="date-only due", task_list_id=list_a, title="Date only", due="2026-10-30")
        dated_id = find(r"ID: ([\w-]+)", dated)
        done = await p.call("tasks", tk.create_task, task_list_id=list_a, title="Book offsite venue")
        done_id = find(r"ID: ([\w-]+)", done)

        await p.call("tasks", tk.list_tasks, task_list_id=list_a)
        await p.call("tasks", tk.get_task, note="full notes?", task_list_id=list_a, task_id=parent_id)
        await p.call("tasks", tk.update_task, note="complete", task_list_id=list_a, task_id=done_id, status="completed")
        await p.call("tasks", tk.update_task, note="new due", task_list_id=list_a, task_id=dated_id, due="2026-11-02T00:00:00Z")
        await p.call("tasks", tk.list_tasks, note="with completed", task_list_id=list_a)
        await p.call("tasks", tk.list_tasks, note="show_completed=False", task_list_id=list_a, show_completed=False)
        await p.call(
            "tasks", tk.list_tasks, note="due window",
            task_list_id=list_a, due_min="2026-10-29T00:00:00Z", due_max="2026-10-31T00:00:00Z",
        )
        await p.call("tasks", tk.clear_completed_tasks, task_list_id=list_a)
        await p.call("tasks", tk.list_tasks, note="after clear", task_list_id=list_a)
        await p.call("tasks", tk.list_tasks, note="after clear, show_hidden", task_list_id=list_a, show_hidden=True)
        await p.call("tasks", tk.move_task, note="make subtask", task_list_id=list_a, task_id=dated_id, parent=parent_id)
        await p.call("tasks", tk.list_tasks, note="after move under parent", task_list_id=list_a)
        await p.call(
            "tasks", tk.move_task, note="to other list",
            task_list_id=list_a, task_id=dated_id, destination_task_list=list_b,
        )
        await p.call("tasks", tk.list_tasks, note="other list", task_list_id=list_b)
        await p.call("tasks", tk.delete_task, task_list_id=list_a, task_id=child_id)
        await p.call("tasks", tk.get_task, note="bogus id", task_list_id=list_a, task_id="bogusTask000")
        await p.call("tasks", tk.list_tasks, note="bogus list", task_list_id="bogusList000")
        for list_id in list(lists):
            await p.call("tasks", tk.delete_task_list, task_list_id=list_id)
            lists.remove(list_id)
    finally:
        service = tk.get_service()
        for list_id in lists:
            await quietly("delete task list", service.tasklists().delete(tasklist=list_id).execute)


# ---------------------------------------------------------------------------
# Docs
# ---------------------------------------------------------------------------


async def probe_docs(p: Probe, me: str, tag: str):
    drive = gd.drive_get_service()
    files = []
    try:
        await p.call("docs", gd.search_docs, note="before create", query=tag)
        await p.call("docs", gd.list_docs_in_folder, page_size=3)

        content = (
            "Q4 Planning — Platform\n"
            "Projects\n"
            "Service Mesh Migration — owner: Meera — target: 30 Nov\n"
            "Billing Revamp — owner: Karthik — target: 30 Nov\n"
            "Open Roles\n"
            "Senior SRE (URGENT)\n"
            "Backend Engineer\n"
        )
        made = await p.call("docs", gd.create_doc, title=f"Probe {tag} Q4 Planning — Platform", content=content)
        doc_id = made.get("document_id") if isinstance(made, dict) else None
        if not doc_id:
            return
        files.append(doc_id)

        await p.call("docs", gd.get_doc_content, document_id=doc_id)
        await p.call("docs", gd.inspect_doc_structure, document_id=doc_id)
        await p.call("docs", gd.inspect_doc_structure, note="detailed", document_id=doc_id, detailed=True)
        # Drive's name index can lag a few seconds behind a create.
        found = await p.call("docs", gd.search_docs, note="index check", query=tag)
        if not (isinstance(found, dict) and found.get("count")):
            await asyncio.sleep(10)
            await p.call("docs", gd.search_docs, note="index check retry", query=tag)
        await p.call("docs", gd.list_docs_in_folder, note="after create", page_size=10)
        for query, note in [
            (f"Probe {tag}", "title prefix"),
            ("Q4 Planning", "title words"),
            (f"{tag} Q4 Planning — Platform", "with em dash"),
            (f"{tag} Q4 Planning - Platform", "with hyphen"),
            (f"{tag.upper()}", "case"),
            (f"Probe {tag} Plan", "partial word"),
            (f"{tag} Service Mesh", "body words only"),
        ]:
            await p.call("docs", gd.search_docs, note=note, query=query)

        await p.call("docs", gd.find_and_replace_doc, note="hits both projects", document_id=doc_id, find_text="30 Nov", replace_text="11 Dec")
        await p.call("docs", gd.find_and_replace_doc, note="no match", document_id=doc_id, find_text="zzqqxx", replace_text="y")
        await p.call("docs", gd.modify_doc_text, note="insert at 1", document_id=doc_id, start_index=1, text="DRAFT NOTES\n")
        await p.call(
            "docs", gd.modify_doc_text, note="format range",
            document_id=doc_id, start_index=1, end_index=12, bold=True, font_size=14,
        )
        await p.call("docs", gd.modify_doc_text, note="index out of range", document_id=doc_id, start_index=99999, text="x")

        structure = await p.call("docs", gd.inspect_doc_structure, note="before table", document_id=doc_id, detailed=True)
        total = find(r'"total_length"\D*(\d+)', structure)
        if total:
            await p.call(
                "docs", gd.insert_doc_elements, note="list at end",
                document_id=doc_id, element_type="list", index=int(total) - 1, list_type="UNORDERED", text="Action item A",
            )
            structure = await p.call("docs", gd.inspect_doc_structure, note="before table 2", document_id=doc_id, detailed=True)
            total = find(r'"total_length"\D*(\d+)', structure)
            table = [["Owner", "Action", "Due"], ["Meera", "Fix alert routing", "12 Oct"], ["Neha", "Write runbook", "14 Oct"]]
            placed = await p.call(
                "docs", gd.create_table_with_data, note="index = total_length",
                document_id=doc_id, table_data=table, index=int(total),
            )
            if not (isinstance(placed, dict) and placed.get("status") == "success"):
                await p.call(
                    "docs", gd.create_table_with_data, note="index = total_length - 1",
                    document_id=doc_id, table_data=table, index=int(total) - 1,
                )
            await p.call("docs", gd.debug_table_structure, document_id=doc_id, table_index=0)
            await p.call("docs", gd.inspect_doc_structure, note="basic, with table", document_id=doc_id)
            await p.call("docs", gd.inspect_doc_structure, note="detailed, with table", document_id=doc_id, detailed=True)
            await p.call("docs", gd.insert_doc_elements, note="page break", document_id=doc_id, element_type="page_break", index=1)

        await p.call("docs", gd.update_doc_headers_footers, document_id=doc_id, section_type="header", content="DRAFT — not for distribution")
        await p.call("docs", gd.update_doc_headers_footers, document_id=doc_id, section_type="footer", content="Confidential — internal only")
        await p.call(
            "docs", gd.batch_update_doc, document_id=doc_id,
            operations=[
                {"type": "insert_text", "index": 1, "text": "Batch line\n"},
                {"type": "format_text", "start_index": 1, "end_index": 11, "italic": True},
            ],
        )
        await p.call(
            "docs", gd.insert_doc_image, document_id=doc_id, index=1, width=100,
            image_source="https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png",
        )
        await p.call("docs", gd.get_doc_content, note="after all edits", document_id=doc_id)
        await p.call("docs", gd.inspect_doc_structure, note="after all edits", document_id=doc_id, detailed=True)

        await p.call("docs", DOC_COMMENTS["read_comments"], note="none yet", document_id=doc_id)
        made = await p.call("docs", DOC_COMMENTS["create_comment"], document_id=doc_id, comment_content="Please move lunch to 13:00.")
        comment_id = find(r"Comment ID: ([\w-]+)", made)
        await p.call("docs", DOC_COMMENTS["create_comment"], document_id=doc_id, comment_content="Second comment, left open.")
        if comment_id:
            await p.call("docs", DOC_COMMENTS["reply_to_comment"], document_id=doc_id, comment_id=comment_id, reply_content="Done")
            await p.call("docs", DOC_COMMENTS["resolve_comment"], document_id=doc_id, comment_id=comment_id)
        await p.call("docs", DOC_COMMENTS["read_comments"], note="after reply + resolve", document_id=doc_id)

        pdf = await p.call("docs", gd.export_doc_to_pdf, document_id=doc_id, pdf_filename=f"Probe {tag} Plan — v2")
        pdf_id = find(r'"pdf_id"\W*([\w-]+)', pdf)
        if pdf_id:
            files.append(pdf_id)
        await p.call("docs", gd.search_docs, note="pdf not a doc", query=f"Probe {tag} Plan — v2")
        await p.call("docs", gd.get_doc_content, note="bogus id", document_id="bogusDoc000")
    finally:
        for file_id in files:
            await quietly("delete file", drive.files().delete(fileId=file_id, supportsAllDrives=True).execute)


# ---------------------------------------------------------------------------
# Sheets
# ---------------------------------------------------------------------------


async def probe_sheets(p: Probe, me: str, tag: str):
    drive = gd.drive_get_service()
    files = []
    try:
        await p.call("sheets", gs.list_spreadsheets, max_results=3)
        made = await p.call("sheets", gs.create_spreadsheet, title=f"Probe {tag} Budget", sheet_names=["Line Items", "Summary"])
        sheet_id = find(r"ID: ([\w-]+)", made)
        if not sheet_id:
            return
        files.append(sheet_id)
        await p.call("sheets", gs.list_spreadsheets, note="after create", max_results=5)

        await p.call("sheets", gs.get_spreadsheet_info, spreadsheet_id=sheet_id)
        rows = [
            ["Vendor", "Category", "Month", "Amount", "Status", "Date"],
            ["CloudNest", "Infra", "Sep", "184500", "Approved", "2026-10-15"],
            ["Datadog", "Observability", "Sep", "₹52,000", "Approved", "15 Oct 2026"],
            ["Figma", "Design", "Sep", "12000.5", "Pending", "10/15/2026"],
            ["CloudNest", "Infra", "Aug", "1,70,000", "Approved", "TRUE"],
            ["Total", "", "", "=SUM(D2:D5)", '=SUMIFS(D2:D5,E2:E5,"Approved")', "=TODAY()"],
        ]
        await p.call("sheets", gs.modify_sheet_values, note="mixed types + formulas", spreadsheet_id=sheet_id, range_name="Line Items!A1:F6", values=rows)
        await p.call("sheets", gs.read_sheet_values, note="as typed", spreadsheet_id=sheet_id, range_name="Line Items!A1:F6")
        await p.call("sheets", gs.read_sheet_values, note="default range", spreadsheet_id=sheet_id)
        await p.call(
            "sheets", gs.format_sheet_range, note="INR currency",
            spreadsheet_id=sheet_id, range_name="Line Items!D2:D6", number_format_type="CURRENCY",
            number_format_pattern="₹#,##,##0", background_color="#FFF2CC",
        )
        await p.call("sheets", gs.format_sheet_range, note="date", spreadsheet_id=sheet_id, range_name="Line Items!F2:F6", number_format_type="DATE")
        await p.call("sheets", gs.read_sheet_values, note="after formatting", spreadsheet_id=sheet_id, range_name="Line Items!A1:F6")

        summary = json.dumps([
            ["Category", "Total"],
            ["Infra", "=SUMIFS('Line Items'!D:D,'Line Items'!B:B,A2,'Line Items'!E:E,\"Approved\")"],
            ["Count approved", "=COUNTIF('Line Items'!E:E,\"Approved\")"],
        ])
        await p.call("sheets", gs.modify_sheet_values, note="values as JSON string", spreadsheet_id=sheet_id, range_name="Summary!A1:B3", values=summary)
        await p.call("sheets", gs.read_sheet_values, spreadsheet_id=sheet_id, range_name="Summary!A1:B3")
        await p.call(
            "sheets", gs.modify_sheet_values, note="RAW input",
            spreadsheet_id=sheet_id, range_name="Summary!A5:B5", values=[["raw formula", "=1+1"]], value_input_option="RAW",
        )
        await p.call("sheets", gs.read_sheet_values, note="RAW readback", spreadsheet_id=sheet_id, range_name="Summary!A5:B5")

        many = [[f"row {i}", str(i)] for i in range(1, 61)]
        await p.call("sheets", gs.modify_sheet_values, note="60 rows", spreadsheet_id=sheet_id, range_name="Summary!D1:E60", values=many)
        await p.call("sheets", gs.read_sheet_values, note="60 rows readback", spreadsheet_id=sheet_id, range_name="Summary!D1:E60")
        await p.call("sheets", gs.modify_sheet_values, note="clear", spreadsheet_id=sheet_id, range_name="Summary!D1:E60", clear_values=True)
        await p.call("sheets", gs.read_sheet_values, note="empty range", spreadsheet_id=sheet_id, range_name="Summary!D1:E60")

        await p.call("sheets", gs.create_sheet, spreadsheet_id=sheet_id, sheet_name="Extra")
        await p.call("sheets", gs.create_sheet, note="duplicate name", spreadsheet_id=sheet_id, sheet_name="Extra")

        await p.call(
            "sheets", gs.add_conditional_formatting, note="rule 0",
            spreadsheet_id=sheet_id, range_name="Line Items!D2:D5", condition_type="NUMBER_GREATER",
            condition_values=["50000"], background_color="#F4CCCC",
        )
        await p.call(
            "sheets", gs.add_conditional_formatting, note="rule 1",
            spreadsheet_id=sheet_id, range_name="Line Items!D2:D5", condition_type="NUMBER_GREATER",
            condition_values=["25000"], background_color="#FCE8B2",
        )
        await p.call(
            "sheets", gs.add_conditional_formatting, note="custom formula",
            spreadsheet_id=sheet_id, range_name="Line Items!A2:F5", condition_type="CUSTOM_FORMULA",
            condition_values=['=$E2="Pending"'], text_color="#999999",
        )
        await p.call("sheets", gs.get_spreadsheet_info, note="with rules", spreadsheet_id=sheet_id)
        await p.call(
            "sheets", gs.update_conditional_formatting, note="threshold change",
            spreadsheet_id=sheet_id, rule_index=1, condition_values=["30000"], sheet_name="Line Items",
        )
        await p.call("sheets", gs.delete_conditional_formatting, note="indices shift?", spreadsheet_id=sheet_id, rule_index=0, sheet_name="Line Items")
        await p.call("sheets", gs.delete_conditional_formatting, note="bad index", spreadsheet_id=sheet_id, rule_index=9, sheet_name="Line Items")

        await p.call("sheets", SHEET_COMMENTS["read_comments"], note="none yet", spreadsheet_id=sheet_id)
        made = await p.call("sheets", SHEET_COMMENTS["create_comment"], spreadsheet_id=sheet_id, comment_content="Please update Figma to Approved.")
        comment_id = find(r"Comment ID: ([\w-]+)", made)
        if comment_id:
            await p.call("sheets", SHEET_COMMENTS["reply_to_comment"], spreadsheet_id=sheet_id, comment_id=comment_id, reply_content="Updated")
            await p.call("sheets", SHEET_COMMENTS["resolve_comment"], spreadsheet_id=sheet_id, comment_id=comment_id)
        await p.call("sheets", SHEET_COMMENTS["read_comments"], note="after resolve", spreadsheet_id=sheet_id)

        await p.call("sheets", gs.read_sheet_values, note="bogus id", spreadsheet_id="bogusSheet000")
        await p.call("sheets", gs.read_sheet_values, note="bad tab", spreadsheet_id=sheet_id, range_name="Nope!A1:B2")
        await p.call("sheets", gs.modify_sheet_values, note="no values", spreadsheet_id=sheet_id, range_name="Line Items!A1:B2")
    finally:
        for file_id in files:
            await quietly("delete file", drive.files().delete(fileId=file_id, supportsAllDrives=True).execute)


# ---------------------------------------------------------------------------
# Sweep: remove anything a crashed run left behind
# ---------------------------------------------------------------------------


async def sweep(tag: str):
    gmail = gm.get_service()
    found = await asyncio.to_thread(gmail.users().messages().list(userId="me", q=f"{tag} in:anywhere").execute)
    for msg in found.get("messages", []):
        await quietly("delete message", gmail.users().messages().delete(userId="me", id=msg["id"]).execute)
    drafts = await asyncio.to_thread(gmail.users().drafts().list(userId="me", q=tag).execute)
    for draft in drafts.get("drafts", []):
        await quietly("delete draft", gmail.users().drafts().delete(userId="me", id=draft["id"]).execute)
    labels = await asyncio.to_thread(gmail.users().labels().list(userId="me").execute)
    for label in labels.get("labels", []):
        if tag in label["name"].lower():
            await quietly("delete label", gmail.users().labels().delete(userId="me", id=label["id"]).execute)
    filters = await asyncio.to_thread(gmail.users().settings().filters().list(userId="me").execute)
    for item in filters.get("filter", []):
        if tag in json.dumps(item.get("criteria", {})):
            await quietly("delete filter", gmail.users().settings().filters().delete(userId="me", id=item["id"]).execute)

    calendar = cal.get_service()
    events = await asyncio.to_thread(
        lambda: calendar.events()
        .list(calendarId="primary", q=tag, timeMin="2026-11-01T00:00:00Z", timeMax="2026-12-01T00:00:00Z", singleEvents=True)
        .execute()
    )
    for item in events.get("items", []):
        await quietly("delete event", calendar.events().delete(calendarId="primary", eventId=item["id"]).execute)

    tasks = tk.get_service()
    task_lists = await asyncio.to_thread(tasks.tasklists().list(maxResults=100).execute)
    for item in task_lists.get("items", []):
        if tag in item["title"]:
            await quietly("delete task list", tasks.tasklists().delete(tasklist=item["id"]).execute)

    drive = gd.drive_get_service()
    files = await asyncio.to_thread(
        drive.files().list(q=f"name contains '{tag}' and trashed=false", fields="files(id,name)").execute
    )
    for item in files.get("files", []):
        await quietly("delete file", drive.files().delete(fileId=item["id"]).execute)
    print(f"Sweep for {tag} done.", flush=True)


# ---------------------------------------------------------------------------


PROBES = {
    "gmail": probe_gmail,
    "calendar": probe_calendar,
    "tasks": probe_tasks,
    "docs": probe_docs,
    "sheets": probe_sheets,
}


async def main():
    parser = argparse.ArgumentParser(description="Probe app_tools against the dummy account.")
    parser.add_argument("--apps", default=",".join(PROBES), help="comma-separated subset of: " + ", ".join(PROBES))
    parser.add_argument("--sweep", metavar="TAG", help="only delete leftovers of the run with this tag")
    args = parser.parse_args()

    me = verify_account()
    if args.sweep:
        await sweep(args.sweep)
        return

    apps = [a.strip() for a in args.apps.split(",") if a.strip()]
    unknown = [a for a in apps if a not in PROBES]
    if unknown:
        sys.exit(f"Unknown app(s): {unknown}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tag = "prb" + "".join(random.choices(string.ascii_lowercase, k=6))
    probe = Probe(OUT_DIR / f"{tag}.jsonl")
    print(f"Probe tag: {tag}  (if the run dies, clean up with --sweep {tag})", flush=True)
    try:
        for app in apps:
            print(f"--- {app} ---", flush=True)
            try:
                await PROBES[app](probe, me, tag)
            except Exception as error:
                print(f"!! {app} section stopped: {type(error).__name__}: {error}", flush=True)
    finally:
        probe.close()
    print(f"Recorded {probe.n} calls in {probe.out_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
