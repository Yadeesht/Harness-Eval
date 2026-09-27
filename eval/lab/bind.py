"""Point the real app_tools functions at a fake workspace.

Only the Google connection is swapped: each tool module's get_service() /
drive_get_service() returns a fake client, the clock is frozen, and the Drive
media helpers used for PDF export are replaced. Tool names, parameters,
descriptions and output formatting stay exactly as in app_tools.
"""

from __future__ import annotations

import datetime as _dt
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import langchain_core.tools.base  # noqa: E402

# Same compatibility patch main.py applies before importing the tools.
if not hasattr(langchain_core.tools.base, "TOOL_MESSAGE_BLOCK_TYPES"):
    langchain_core.tools.base.TOOL_MESSAGE_BLOCK_TYPES = ("text",)

from app_tools.core.server_init import communication_server, content_server, planning_server  # noqa: E402
from app_tools.tools.google import calendar_tools, gdocs_tools, gmail_tools, gsheet_tools, gtask_tools  # noqa: E402
from app_tools.tools.google import workspace_comment_base  # noqa: E402

from .fake.calendar import Calendar  # noqa: E402
from .fake.docs import Docs  # noqa: E402
from .fake.drive import Drive  # noqa: E402
from .fake.gmail import Gmail  # noqa: E402
from .fake.sheets import Sheets  # noqa: E402
from .fake.tasks import Tasks  # noqa: E402
from .workspace import Workspace  # noqa: E402

TOOL_MODULES = [gmail_tools, calendar_tools, gtask_tools, gdocs_tools, gsheet_tools, workspace_comment_base]


class _FakeDownload:
    """Replaces MediaIoBaseDownload: writes the fake file bytes in one chunk."""

    def __init__(self, fh, request, chunksize=None):
        self.fh = fh
        self.request = request

    def next_chunk(self, num_retries=0):
        self.fh.write(self.request.execute())
        return None, True


class _FakeUpload:
    """Replaces MediaIoBaseUpload: keeps the bytes so the fake Drive can record size."""

    def __init__(self, fh, mimetype=None, chunksize=None, resumable=False):
        fh.seek(0)
        self._fake_bytes = fh.read()
        self._fake_source = None
        self.mimetype = mimetype


def _frozen_datetime_class(now_aware: _dt.datetime):
    class FrozenDatetime(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return cls.fromtimestamp(now_aware.timestamp(), tz=now_aware.tzinfo).replace(tzinfo=None)
            return cls.fromtimestamp(now_aware.timestamp(), tz=tz)

        @classmethod
        def utcnow(cls):
            return cls.now(_dt.timezone.utc).replace(tzinfo=None)

        @classmethod
        def today(cls):
            return cls.now()

    return FrozenDatetime


_bound: Workspace | None = None


def bind(ws: Workspace) -> Workspace:
    """Route every tool module at `ws`. Call again to switch workspaces."""
    global _bound
    _bound = ws
    gmail, cal, tasks, docs, drive, sheets = Gmail(ws), Calendar(ws), Tasks(ws), Docs(ws), Drive(ws), Sheets(ws)

    gmail_tools.get_service = lambda: gmail
    calendar_tools.get_service = lambda: cal
    gtask_tools.get_service = lambda: tasks
    gdocs_tools.get_service = lambda: docs
    gdocs_tools.drive_get_service = lambda: drive
    gsheet_tools.get_service = lambda: sheets
    gsheet_tools.drive_get_service = lambda: drive
    workspace_comment_base.get_service = lambda: drive

    gdocs_tools.MediaIoBaseDownload = _FakeDownload
    gdocs_tools.MediaIoBaseUpload = _FakeUpload

    frozen = _frozen_datetime_class(ws.clock.now())
    gmail_tools.datetime = frozen
    calendar_tools.datetime = types.SimpleNamespace(
        datetime=frozen, timezone=_dt.timezone, timedelta=_dt.timedelta, date=_dt.date
    )
    return ws


def bound() -> Workspace:
    if _bound is None:
        raise RuntimeError("No workspace bound; call bind(ws) first.")
    return _bound


def all_tools() -> list:
    """The 75 registered LangChain tools (name, description, args schema, coroutine)."""
    return communication_server.list_tools() + planning_server.list_tools() + content_server.list_tools()
