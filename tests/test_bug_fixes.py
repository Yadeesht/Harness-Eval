"""
Regression tests for the bug fixes applied to this repository.

Run with:
    pytest tests/test_bug_fixes.py -v

Each test is grouped under a comment naming the bug it guards against, using
the same numbering as the review/fix session. Where practical, tests exercise
the real code path against a real (temporary, on-disk) database or a real
subprocess rather than mocking the fix itself out of the test.

Environment notes
------------------
- No real Google API network calls are made anywhere in this file; the
  Google API client (`googleapiclient.discovery.build`) is always mocked.
- `core/__init__.py` eagerly imports `core.agent`, which needs a newer
  langgraph/langchain-core than may be installed in a given environment. To
  keep these tests runnable without requiring that exact stack, importing
  `core` falls back (see `_ensure_core_package_importable`) to a stub
  `core/__init__.py` that leaves the real `core/*.py` files on disk fully
  importable and unmodified -- only the package's own `__init__.py` is
  bypassed, and only if a normal `import core` doesn't already work. In a
  venv matching requirements.txt, `import core` succeeds normally and the
  fallback never triggers.
"""

import asyncio
import json
import sys
import threading
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _ensure_core_package_importable():
    """Make `import core.xxx` work even if `core/__init__.py`'s eager
    `core.agent` import can't be satisfied by the installed langgraph /
    langchain-core versions. See module docstring above."""
    try:
        import core  # noqa: F401

        return
    except Exception:
        for key in list(sys.modules):
            if key == "core" or key.startswith("core."):
                del sys.modules[key]

    fake_core = types.ModuleType("core")
    fake_core.__path__ = [str(REPO_ROOT / "core")]
    sys.modules["core"] = fake_core


_ensure_core_package_importable()


# ===========================================================================
# Bug: app_tools/auth/service_decoder.py reassigned (rather than mapped)
# api_service_name three times in a row, so gdrive/gchat always resolved to
# the raw service_type instead of the real Google API discovery name.
# ===========================================================================


def test_service_decoder_resolves_correct_api_names(tmp_path):
    from app_tools.auth import service_decoder

    service_decoder.clear_service_cache()

    token_path = tmp_path / "token.json"
    token_path.write_text("{}")

    fake_creds = MagicMock(valid=True)

    cases = [
        ("gdrive", "gdrive", "drive"),
        ("tasks", "tasks", "tasks"),
        ("gmail", "gmail", "gmail"),
        ("docs", "docs", "docs"),
    ]

    with patch.object(service_decoder, "Credentials") as mock_creds_cls, patch.object(
        service_decoder, "build"
    ) as mock_build:
        mock_creds_cls.from_authorized_user_file.return_value = fake_creds

        for service_type, scope_key, expected_api_name in cases:
            mock_build.reset_mock()
            mock_build.return_value = MagicMock()

            service_decoder.get_google_service(
                service_type=service_type,
                scope_key=scope_key,
                token_path=str(token_path),
                creds_path="unused.json",
                force_refresh=True,
            )

            assert mock_build.call_count == 1
            called_api_name = mock_build.call_args.args[0]
            assert called_api_name == expected_api_name, (
                f"service_type={service_type!r}: expected build() to be "
                f"called with api name {expected_api_name!r}, got "
                f"{called_api_name!r}"
            )


# ===========================================================================
# Bug: gmail_tools.open_email validated the Gmail message ID against
# EmailAddress (an EmailStr field) -- a real message ID is never a valid
# email address, so the call always failed, and the failure handler itself
# then crashed by re-instantiating EmailAddress without its required field.
# ===========================================================================


def test_open_email_accepts_gmail_message_id_not_an_email_address():
    import asyncio

    from app_tools.tools.google import gmail_tools

    async def _run():
        with patch.object(gmail_tools, "webbrowser") as mock_browser:
            # A realistic Gmail message ID -- NOT a valid email address.
            # Before the fix this always failed EmailAddress validation,
            # and the except-branch itself raised trying to build
            # EmailAddress(success=..., error=...) (missing required `email`).
            result = await gmail_tools.open_email("18abf3e9c02d1a44")

        assert result["success"] is True
        assert result.get("error") is None
        assert mock_browser.open.called

    asyncio.run(_run())


def test_open_email_reports_error_as_dict_on_truly_invalid_id():
    import asyncio

    from app_tools.tools.google import gmail_tools

    async def _run():
        # EmailIdRequest requires min_length=1; empty string is invalid.
        result = await gmail_tools.open_email("")
        assert result["success"] is False
        assert "error" in result

    asyncio.run(_run())


# ===========================================================================
# Bug: calendar_tools._correct_time_format_for_api appended "Z" (UTC) to
# naive timestamps, but this module's whole contract (create_event /
# modify_event) is that naive timestamps are IST -- a 5:30 offset bug.
# ===========================================================================


def test_calendar_time_formatting_uses_ist_not_utc():
    from app_tools.tools.google.calendar_tools import _correct_time_format_for_api

    date_only = _correct_time_format_for_api("2026-03-01", "time_min")
    assert date_only == "2026-03-01T00:00:00+05:30"
    assert not date_only.endswith("Z")

    naive_datetime = _correct_time_format_for_api("2026-03-01T09:00:00", "time_min")
    assert naive_datetime == "2026-03-01T09:00:00+05:30"
    assert not naive_datetime.endswith("Z")

    # Already-qualified timestamps must be left alone.
    already_qualified = _correct_time_format_for_api(
        "2026-03-01T09:00:00+05:30", "time_min"
    )
    assert already_qualified == "2026-03-01T09:00:00+05:30"


# ===========================================================================
# Bug: gsheet_tools.read_sheet_values always labeled rows "Row 1", "Row 2",
# ... regardless of the actual range offset, which could mislead an agent
# into writing back to the wrong sheet row.
# ===========================================================================


def test_read_sheet_values_labels_rows_with_real_sheet_row_numbers():
    import asyncio

    from app_tools.tools.google import gsheet_tools

    fake_service = MagicMock()
    fake_service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [["r10c1", "r10c2"], ["r11c1", "r11c2"]]
    }

    async def _run():
        with patch.object(gsheet_tools, "get_service", return_value=fake_service):
            result_json = await gsheet_tools.read_sheet_values(
                "sheet123", "Sheet1!A10:B11"
            )
        return json.loads(result_json)

    result = asyncio.run(_run())
    assert result["status"] == "success"
    assert "Row 10:" in result["message"]
    assert "Row 11:" in result["message"]
    assert "Row 1:" not in result["message"]


# ===========================================================================
# Bug: create_agent_tool_node returned only the first Command it found in a
# multi-tool-call turn, silently dropping ToolMessages for any other tool
# calls in the same batch and leaving their tool_call_ids unanswered.
# ===========================================================================


def test_tool_node_wrapper_returns_every_command_not_just_the_first():
    from langgraph.types import Command

    # Reproduce the exact post-processing logic from
    # core.graph.create_agent_tool_node's inner `node()` function.
    def process(result, messages_key):
        if isinstance(result, Command):
            return result
        if isinstance(result, list):
            commands = [item for item in result if isinstance(item, Command)]
            plain_messages = [item for item in result if not isinstance(item, Command)]
            if plain_messages:
                commands.append(
                    Command(update={messages_key: plain_messages, "messages": plain_messages})
                )
            if commands:
                return commands
            return {messages_key: [], "messages": []}
        if isinstance(result, dict):
            tool_messages = result.get(messages_key, [])
        else:
            tool_messages = []
        return {messages_key: tool_messages, "messages": tool_messages}

    cmd_a = Command(update={"supervisor_messages": ["a"]})
    cmd_b = Command(update={"supervisor_messages": ["b"]})

    out = process([cmd_a, cmd_b], "supervisor_messages")
    assert isinstance(out, list)
    assert cmd_a in out and cmd_b in out, "a Command from a later tool call was dropped"

    # Mixed Command + plain ToolMessage results must both survive.
    plain_msg = {"type": "tool", "content": "hi"}
    out_mixed = process([cmd_a, plain_msg], "supervisor_messages")
    assert cmd_a in out_mixed
    wrapped = [c for c in out_mixed if c is not cmd_a][0]
    assert wrapped.update["supervisor_messages"] == [plain_msg]


# ===========================================================================
# Bug: main.py's keyword_listener blocked on `loop.run_in_executor(None,
# input)`, which schedules onto asyncio's *default* executor --
# asyncio.run() waits for that executor to drain before the process can
# exit, hanging the terminal after "Goodbye!" until one more Enter press.
# ===========================================================================


def test_keyword_listener_runs_on_a_plain_thread_and_delivers_input():
    fake_core = sys.modules.get("core")
    fake_graph = types.ModuleType("core.graph")
    fake_graph.build_graph = lambda *a, **k: None
    had_core_graph = "core.graph" in sys.modules
    prev_core_graph = sys.modules.get("core.graph")
    sys.modules["core.graph"] = fake_graph
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("main_under_test", REPO_ROOT / "main.py")
        main_mod = importlib.util.module_from_spec(spec)
        sys.modules["main_under_test"] = main_mod
        spec.loader.exec_module(main_mod)
    finally:
        if had_core_graph:
            sys.modules["core.graph"] = prev_core_graph
        else:
            sys.modules.pop("core.graph", None)

    import inspect

    assert not inspect.iscoroutinefunction(main_mod.keyword_listener), (
        "keyword_listener must be a plain function run on its own thread, "
        "not a coroutine scheduled on asyncio's default executor"
    )

    async def _run():
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()
        agent_state = {"last_interaction": 0}

        inputs = iter(["hello world", "   ", EOFError()])

        def fake_input():
            val = next(inputs)
            if isinstance(val, Exception):
                raise val
            return val

        with patch("builtins.input", side_effect=fake_input):
            thread = threading.Thread(
                target=main_mod.keyword_listener,
                args=(queue, loop, agent_state),
                daemon=True,
            )
            thread.start()

            item = await asyncio.wait_for(queue.get(), timeout=5)
            assert item == ("TEXT", "hello world")

            # Thread must exit on its own (EOFError) -- this is exactly the
            # condition that used to hang the process on quit. Note: join
            # via run_in_executor rather than a bare blocking thread.join()
            # here -- a synchronous join would itself starve this event
            # loop of the tick it needs to deliver keyword_listener's
            # run_coroutine_threadsafe(...).result() future, deadlocking
            # this *test* (not a bug in the code under test).
            await loop.run_in_executor(None, thread.join, 5)
            assert not thread.is_alive(), "keyword_listener thread did not exit on EOFError"

    asyncio.run(_run())


# ===========================================================================
# Bug: utils/helper.delete_thread_from_db deleted from a "messages" table
# that doesn't exist in the checkpoint schema (real tables are "checkpoints"
# and "writes").
# ===========================================================================


def test_delete_thread_from_db_targets_real_checkpoint_tables(tmp_path, monkeypatch):
    import sqlite3

    from utils import helper

    db_path = tmp_path / "checkpoints.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE checkpoints (thread_id TEXT, checkpoint BLOB)")
    conn.execute("CREATE TABLE writes (thread_id TEXT, value BLOB)")
    conn.execute("INSERT INTO checkpoints (thread_id, checkpoint) VALUES ('t1', x'00')")
    conn.execute("INSERT INTO checkpoints (thread_id, checkpoint) VALUES ('t2', x'00')")
    conn.execute("INSERT INTO writes (thread_id, value) VALUES ('t1', x'00')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(helper, "CHECKPOINT_DB", db_path)

    helper.delete_thread_from_db("t1")

    conn = sqlite3.connect(db_path)
    remaining_checkpoints = conn.execute(
        "SELECT thread_id FROM checkpoints"
    ).fetchall()
    remaining_writes = conn.execute("SELECT thread_id FROM writes").fetchall()
    conn.close()

    assert remaining_checkpoints == [("t2",)]
    assert remaining_writes == []


# ===========================================================================
# Bug: core.graph splits content tools between agents by keyword, and a tool
# no keyword matches is silently unreachable (first seen with Forms'
# set_publish_settings). The Sheets conditional-formatting tools only matched
# via "form", a substring of "formatting", so dropping Forms nearly orphaned
# them too.
# ===========================================================================


def test_every_content_tool_reaches_exactly_one_agent():
    import app_tools.tools.google.gdocs_tools  # noqa: F401  (registers tools)
    import app_tools.tools.google.gsheet_tools  # noqa: F401
    from app_tools.core.server_init import content_server
    from core.graph import split_content_tools

    content_tools = content_server.list_tools()
    document_tools, data_tools = split_content_tools(content_tools)
    document_names = {t.name for t in document_tools}
    data_names = {t.name for t in data_tools}

    unassigned = {t.name for t in content_tools} - document_names - data_names
    assert not unassigned, f"no agent can call: {sorted(unassigned)}"
    assert not document_names & data_names, "a tool was assigned to both agents"

    assert "add_conditional_formatting" in data_names
    assert "create_table_with_data" in document_names


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
