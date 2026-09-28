# Tool reference: what the real tools return

Probed against the dummy Google account on 2026-09-27. Covers 74 of the 75 tools in `app_tools/`; `open_email` is skipped because it opens a browser (per its code it returns `{"success": true, "error": null}`).

- **How:** `eval/probe/probe_tools.py` calls every tool on objects it creates, records each result, then deletes everything. `eval/probe/checks.py` turns the latest record into PASS/FAIL for every bug fixed so far.
- **Raw records:** `eval/probe/out/*.jsonl` (gitignored: real account data).
- **Re-run after any tool change:**
  ```
  .venv/Scripts/python.exe eval/probe/probe_tools.py
  .venv/Scripts/python.exe eval/probe/checks.py
  ```
  The last run on 2026-09-27 passed 29/29 checks.
- **Masking:** `<me>` is the signed-in account and `<id>` any Google ID.

This file serves two uses:
1. **Writing tasks:** every task must be solvable with these tools as they really behave.
2. **Building the fake server:** it must return exactly these formats, quirks included.

---

## 1. Fixed on 2026-09-27

The first probe found 17 tools broken or misreporting. All were fixed in `app_tools/` (and `utils/helper.py`) **without changing any tool name, parameter or description**. That was checked by diffing all 75 tool schemas before and after.

| Tool(s) | Was | Cause → fix |
|---|---|---|
| `search_docs`, `list_docs_in_folder`, `export_doc_to_pdf`, `list_spreadsheets` | always failed | Drive call on the Docs/Sheets client → use the Drive client. `export_doc_to_pdf` also passed `supportsAllDrives` to `files.export`, which only takes `fileId`/`mimeType` → dropped |
| `delete_label` | always failed | read a nonexistent field → uses the validated ID |
| `search_by_label` | always 0 for user labels | searched `label:<ID>` (Gmail search matches names only) → filters by `labelIds` |
| `update_task`, `update_task_list` | raised an error **after** applying the change | response model required an ID nobody passed → ID optional and filled on success |
| `get_task_list` | returned `task_list: null`, no text | response model had no `message` field → added |
| `list_tasks` (bad list ID) | raised, told the model to call a nonexistent `start_google_auth` tool | returns an `API error: ...` string |
| `modify_event` | failed unless start **and** end were passed; a guest-list change would have wiped all guests | full-replace `update` → partial `patch`. The field-preserve helper (which also wrote attendee emails in the wrong shape) is removed. Changing only the Meet setting now counts as a change |
| `create_event`, `modify_event` `reminders` | JSON string rejected despite the docstring | string parsed before validation |
| `modify_doc_text` (formatting) | always failed | validator called with 7 args, took 5 → accepts the two colour args |
| `batch_update_doc` | always failed | manager got models instead of dicts → converted |
| `inspect_doc_structure` | basic mode always failed; detailed mode returned the basic view, or `null` once a table existed | mis-indented branches → restructured |
| `update_doc_headers_footers` | failed unless a header/footer already existed | now creates it first. Also targets the header's own segment (it would have written into the body) and skips an empty delete |
| `insert_doc_image` | width without height sent height 0 | 0 now means "not given" |
| `get_spreadsheet_info` | listed only the first tab | return moved out of the per-tab loop |
| `add_conditional_formatting` | printed the new rule last while Google inserted it first | always sends the index, so the sheet matches what's printed |
| `create_spreadsheet` | `spreadsheet_id` field was `null` | filled |
| `read_email`, `get_unread_emails` (`clean_email_body`) | deleted line breaks (lines glued together) and every non-ASCII character (`₹`, `—`, accents) | only invisible/control characters removed; lines are joined with a space |
| comment tools | literal `\n` text instead of line breaks | real line breaks |

**Deliberately kept.** These are real Google behavior or deliberate tool limits, and they make tasks realistically hard:
- whole-word search
- values shown as displayed text
- task notes cut at 100 characters
- 50 rows per sheet read
- tables flattened in doc text
- no event ID from `create_event`
- the "(organizer)" flag rule
- date-only task dues rejected
- "no events" reported as an error
- the `from_` key
- `list_archived` including sent mail

---

## 2. Gmail (26 tools)

### 2.1 Search (`search_emails`)

```json
{"count": 1, "emails": [{"id": "<id>", "thread_id": "<id>",
  "subject": "Invoice INV-2291 for September", "from": "<me>",
  "date": "Sun, 27 Sep 2026 07:18:30 +0000",
  "snippet": "Hi Yadeesh, Please find the invoice for September. Amount due: ₹1,84500 Due date: 15 Oct 2026 ..."}],
 "error": null}
```

- Newest first. With no `max_results`, the API default applies (100; not probed with more).
- `from` is the raw header: `Name <addr>` for normal mail, a bare address for mail sent through `send_email`. `date` is the raw RFC 2822 header in the sender's offset (two mails a second apart came back `-0400` and `+0000`).
- `snippet` is Gmail's, **HTML-escaped** (`&#39;`, `&amp;`, `&lt;`, `&quot;`), about 200 characters, and not always identical to the body (`₹1,84,500` came back as `₹1,84500`).
- No body, labels or read/unread flag in results.

**Matching (observed):**

| Query | Result |
|---|---|
| a word from subject or body, any case | matches |
| part of a word (`kuber` for Kubernetes) | **no match** |
| `2291` for `INV-2291` | matches (hyphen splits tokens) |
| `184500` for `1,84,500` | **no match** |
| `"due date"` (quoted phrase) | matches |
| `subject:`, `from:me`, `to:me`, `in:sent`, `in:inbox`, `is:unread`, `newer_than:1d`, `older_than:1d`, `after:YYYY/MM/DD`, `category:primary`, `has:attachment` | behave as Gmail documents |
| `a OR b`, `{a b}`, `-word` | work |
| `a OR b c` (OR next to other terms) | means `(a OR b) c`: OR binds tighter than the implicit AND. Probed 2026-09-28: `in:inbox OR in:sent is:read` returned exactly the same messages as `(in:inbox OR in:sent) is:read` (1,009), not `in:inbox OR (in:sent is:read)` (3,500+). The fake had it the other way round until then (dev1 em_06 graph run 2). |
| `label:Parent/Child`, `label:parent-child`, `label:"Parent/Child"` | match |
| `label:Label_3` (label **ID**) | **no match** (use `search_by_label` for IDs) |
| no hits | `{"count": 0, "emails": [], "error": null}` |
| empty query | validation error ("String should have at least 1 character") |

### 2.2 Reading

- **`read_email`** → `{"content", "subject", "from_", "to", "date", "error"}`. **Marks the mail as read.** No thread ID, CC or attachments.
  - The body is flattened to one line: line breaks become single spaces, and runs of `---`/`***`/`===` become a space.
  - HTML entities are unescaped; `₹`, `—` and accents are kept. Example: `"Amount due: ₹1,84,500 Due date: 15 Oct 2026 Regards, Priya Nair Finance"`.
  - A numbered list `1. A\n2. B` reads `1. A 2. B`.
- **`get_unread_emails`** → `{"count", "emails": [{"id", "thread_id", "snippet", "subject", "from_", "date", "to"}]}`.
  - The key is `from_`, not `from`, and the snippet goes through the same cleanup.
  - Query: `in:inbox is:unread category:primary after:<today − date days>`, using the **real clock** (the fake must use the frozen one).
- **`list_drafts`** → `{"count", "drafts": [{"id", "subject", "to"}]}`. No body; no tool can read, send or delete a draft. Slow (~3.2 s: one API call per draft).

### 2.3 Sending

- `send_email` / `create_draft` → `{"success": true, "message_id" | "draft_id": "<id>", "error": null}`.
  - One address only; `"not-an-email"` returns a validation error and sends nothing.
  - The From header is the bare address (no display name).
- Mail sent to yourself lands in INBOX **unread** and in SENT, as one message ID.

### 2.4 Labels, folders, archive

- `list_labels` → `{"count", "labels": [{"id", "name", "type"}]}`, system labels included (`INBOX`, `SENT`, `CATEGORY_UPDATES`, ...). User label IDs look like `Label_3`.
- `create_label` accepts nested names (`Vendors/CloudNest/Billing`); a duplicate returns `"Label name exists or conflicts"` (409). `create_folder` is the same call. `list_folders` = user labels only, `{"count", "folders": [{"id", "name"}]}`.
- `apply_label`, `remove_label`, `archive_email`, `restore_to_inbox`, `move_to_folder`, `mark_email_as_read`, `trash_email`, `delete_label` → `{"success": true, "error": null}`. Bad label: `"labelId not found"`; bad message ID: `"Invalid id value"` (both 400).
- `search_by_label` → `{"count", "messages": [{"id", "threadId"}]}`: bare IDs, no subject or sender. It fetches **every** page, so a busy system label (e.g. `INBOX`) can return a very long list.
- `rename_label` → `{"success", "label_id", "name"}`.
- `batch_archive` → `{"success", "archived_count", "total_found", "message"}`; no hits gives `message: "No emails found matching the query."`
- `list_archived` = `search_emails("-in:inbox")`, so it also lists **sent mail**.

### 2.5 Filters

- `list_filters` → `{"count", "filters": [...]}`.
- `get_filter` → the raw filter: `{"id", "criteria": {"from": ...}, "action": {"addLabelIds": [...], "removeLabelIds": ["INBOX"]}}`.
- `delete_filter_tool` → `{"success": true}`. Unknown ID: 404 `"Requested entity was not found."`
- No tool can **create** a filter.

---

## 3. Calendar (5 tools)

### 3.1 Reading (`get_events`)

Basic listing (JSON with the text in `message`):

```
Successfully retrieved 4 events from calendar 'primary':
- "Focus block" (Starts: 2026-11-09T14:00:00+05:30, Ends: 2026-11-09T16:00:00+05:30) ID: <id> | Link: <url>
- "OOO" (Starts: 2026-11-11, Ends: 2026-11-13) ID: <id> | Link: <url>
```

Detailed listing adds per event:

```
  Description: Agenda:\n1. Mesh rollout\n2. Budget
  Location: Room 4B
  Attendees: <guest>, <me>
  Attendee Details: <guest>: needsAction
    <me>: needsAction (organizer)
```

- A single event with `detailed=True` uses a different layout (`Event Details:\n- Title: ...\n- Starts: ...`).
- **All-day events show the exclusive end date raw:** an event covering 11–12 Nov reads `Ends: 2026-11-13`.
- **"(organizer)" only appears if the organizer is on the attendee list.** Events created in the Calendar UI with guests include the organizer. An event created through the API without listing yourself shows no organizer at all. For events organized by someone else, that person carries the flag.
- **Never shown:** free/busy (transparency), the Meet link, reminders, the creator.
- Recurring events come back as instances with IDs like `<base>_20270823`.
- `query` matches whole words in title, description, location **and attendee addresses**; partial words don't match.
- `time_min` defaults to the **real now** (fake: frozen now). Date-only bounds (`2026-11-09`) are accepted.
- **No results is reported as an error:** `{"status": "error", "error": "No events found in calendar 'primary' for the specified time range."}` (also when a query just doesn't match).
- An unknown event ID via `get_events` → `{"error": "HTTP error occurred: <HttpError 404 ... \"Not Found\" ...>"}` (no `status` key).

### 3.2 Writing

- **`create_event`** → `"Successfully created event 'X'. Link: <url>"` (+ `Google Meet: <url>`). **No event ID is returned**; an agent has to call `get_events` to find it.
  - Times without an offset are read as IST; explicit offsets are honored (`10:00+01:00` is stored and shown as `14:30+05:30`).
  - End before start → `"The specified time range is empty."`
  - `reminders` may be a list or a JSON string.
  - A read-only calendar → 403 `"You need to have writer access to this calendar."`
- **`modify_event`** changes only the fields passed; everything else (times, guests, description, reminders, Meet) stays.
  - Passing `attendees` **replaces** the whole guest list.
  - `add_google_meet=False` alone removes Meet (message ends `(Google Meet removed)`).
  - → `"Successfully modified event 'X' (ID: <id>). Link: <url>"`.
  - Nothing to change: `"No fields provided to modify the event."`
- **`delete_event`** → `"Successfully deleted event (ID: <id>) from calendar 'primary'."` (~1 s: it reads the event first). An unknown ID (also for `modify_event`): `"Event not found during verification. The event with ID '<id>' could not be found..."`
- `list_calendars` → `{"status", "count", "calendars": [{"id", "summary", "description", "timeZone", "accessRole", "primary"}]}`. The dummy account has its primary calendar plus two read-only "Holidays in India" calendars.

---

## 4. Google Tasks (12 tools)

`list_tasks` returns **plain text** (the other task tools return JSON):

```
Tasks in list <id>:
- Q4 capacity model (ID: <id>)
  Status: needsAction
  Due: 2026-10-30T00:00:00.000Z
  Notes: Context: agreed in the 28 Sep sync that the platform team owns the capacity model for Q4. Update fro...
  Updated: 2026-09-27T07:26:54.340Z

  * Collect numbers (ID: <id>)
    Status: needsAction
```

- **Notes are cut at 100 characters** in `list_tasks`; `get_task` shows them in full (plus position and parent).
- Completed tasks are listed by default. After `clear_completed_tasks` they're hidden unless `show_hidden=True`.
- Newest tasks come first. The default page size is 20.
- Empty list: `"No tasks found in task list <id>."` An unknown list ID: `"API error: <HttpError 400 ... Invalid task list ID ...>"`.
- **`create_task`**: `due` must be a timestamp; `"2026-10-30"` fails with `"Request contains an invalid argument."` (400). The time part is dropped: `18:30Z` is stored as `T00:00:00.000Z`. Returns the new ID.
- `update_task` → `{"status": "success", "message": "Task Updated:\n- Title: ...\n- Status: completed ...", "task_id": "<id>"}`. `update_task_list` is similar.
- `get_task_list` → `message: "Task List Details:\n- Title: ...\n- ID: ...\n- Updated: ..."`. The structured `task_list` field stays `null`; the text carries the data.
- `move_task` works, both under a parent and to another list. `create_task_list`, `list_task_lists`, `delete_task` and `delete_task_list` work.

---

## 5. Docs (18 tools)

- **`search_docs`** → `{"count", "query", "docs": [{"id", "name", "created_time", "modified_time", "web_view_link"}]}`.
  - **Titles only**; body words never match.
  - Case-insensitive; matches word prefixes (`Plan` finds "Planning").
  - Punctuation is ignored (em dash and hyphen both match).
  - Only Google Docs: PDFs and other files are excluded.
  - A new doc was findable within the probe's first check.
- **`list_docs_in_folder`** → same shape, for a folder (`root` = My Drive), including other docs the account owns. `created_time` is empty here.
- `create_doc` → `{"status", "document_id", "title", "web_view_link"}` (~2 s).
- **`get_doc_content`** → `{"document_id", "name", "mime_type", "content", "web_view_link"}`.
  - Content starts with `\n--- TAB: Tab 1 ---\n`, then one paragraph per line. Unicode is kept.
  - **Tables are flattened:** each cell on its own line, row by row, with no row/column markers. A 3×3 table reads `Owner\nAction\nDue\nMeera\nFix alert routing\n12 Oct\n...`.
  - **Headers and footers are not included.**
- **`inspect_doc_structure`**:
  - Basic → `{"total_elements", "tables", "paragraphs", "section_breaks", "total_length", "has_headers", "has_footers"}`, plus `total_table_cells`, `largest_table` and `table_details: [{"index", "rows", "columns", "start_index", "end_index"}]` when tables exist.
  - `detailed=True` → `{"title", "total_length", "statistics", "elements": [{"type", "start_index", "end_index", "text_preview"}...], "tables": [{"index", "position", "dimensions", "preview"}]}`.
- `modify_doc_text`: inserting text and formatting (`bold`, `italic`, `underline`, `font_size`, `font_family`, `text_color`, `background_color`) both work → `operations: ["Applied formatting (bold=True, font_size=14) to range 1-12"]`. An index past the end: `"Index 99999 must be less than the end index of the referenced segment, 198."`
- `find_and_replace_doc` → `{"replacements": N}`, replacing **every** occurrence (case-insensitive by default).
- `batch_update_doc` → `{"status": "success", "operations_count": N}`; operation types `insert_text`, `delete_text`, `replace_text`, `format_text`, `insert_table`, `insert_page_break`.
- `insert_doc_elements` (list, page break) works.
- `create_table_with_data` works with `index = total_length` from `inspect_doc_structure`, and takes **~12 s**. Inserting a second table at an out-of-date index writes its text into the first table's cells.
- `debug_table_structure` works: dimensions, each cell's range and content.
- `update_doc_headers_footers` creates the `DEFAULT` header/footer if missing, then sets its text.
- `insert_doc_image` works with a width only (height left to Google).
- `export_doc_to_pdf` → `{"status", "pdf_id", "pdf_filename": "<name>.pdf", "web_view_link"}`: a new PDF file in Drive root (not visible to `search_docs`).

### Comments (docs and sheets alike)

```
Found 2 comments in document <id>:

Comment ID: <id>
Author: Yadeesh T
Created: 2026-09-27T07:20:53.560Z [RESOLVED]
Content: Please move lunch to 13:00.
  Replies (2):
    Reply ID: <id>
    Author: Yadeesh T
    ...
    Content: This comment has been resolved.
```

- `Author` is the account's display name, not an address. No quoted/anchored text is shown.
- Resolving adds a reply `"This comment has been resolved."` and marks the comment `[RESOLVED]`.
- None: `"No comments found in document <id>"`.

---

## 6. Sheets (14 tools)

- **`list_spreadsheets`** → `message: "Successfully listed N spreadsheets:\n- \"Name\" (ID: <id>) | Modified: ... | Link: ..."` plus a structured `spreadsheets` list. Most recently modified first; default 25, no name filter.
- `create_spreadsheet` → `message: "Successfully created spreadsheet 'X'. ID: <id> | URL: <url> | Locale: en_GB"`, `spreadsheet_id: "<id>"`. The account locale is **en_GB**, so dates display as `dd/mm/yyyy`.
- **`get_spreadsheet_info`** lists every tab, each with its conditional rules:
  ```
  Spreadsheet: "Budget" (ID: <id>) | Locale: en_GB
  Sheets (3):
    - "Line Items" (ID: <id>) | Size: 1000x26 | Conditional formats: 3
      Conditional formats for "Line Items" (3):
        [0] NUMBER_GREATER values=['50000'] -> bg #F4CCCC on Line Items!D2:D5
    - "Summary" (ID: <id>) | Size: 1000x26 | Conditional formats: 0
  ```
- **`read_sheet_values`** returns **displayed text**, not raw values:
  ```
  Successfully read 6 rows from range 'Line Items!A1:F6' in spreadsheet <id>:
  Row  1: ['Vendor', 'Category', 'Month', 'Amount', 'Status', 'Date']
  Row  2: ['CloudNest', 'Infra', 'Sep', '₹184,500', 'Approved', '15/10/2026']
  ```
  - Only **50 rows are shown**, then `... and N more rows`; the agent has to read further ranges.
  - Empty: `"No data found in range '...'."`; bad tab: `"Unable to parse range: Nope!A1:B2"`; bad ID: 404.
- **How typed values are stored (USER_ENTERED, en_GB):**

| Typed | Stored as |
|---|---|
| `184500`, `12000.5` | number |
| `₹52,000`, `1,70,000` | **text**: skipped by `SUM`/`SUMIFS` without any warning |
| `2026-10-15`, `15 Oct 2026` | date |
| `10/15/2026` | text (not a valid en_GB date) |
| `=SUM(...)`, `=SUMIFS(...)`, `=COUNTIF(...)`, cross-tab refs | computed |
| `=TODAY()` | the **real** date (fake: frozen) |
| anything with `value_input_option="RAW"` | kept as typed, formulas included |

- After a `CURRENCY` format with pattern `₹#,##,##0`, numbers display as `₹184,500` (no lakh grouping), and `12000.5` displays as `₹12,001`. **Formatting hides decimals** in what the agent reads.
- `modify_sheet_values` → `"Updated: 36 cells, 6 rows, 6 columns."` Values may be a list or a JSON string. Missing values: `"Either 'values' must be provided or 'clear_values' must be True."`
- `create_sheet` works; duplicate name: `"A sheet with the name 'Extra' already exists."`
- **Conditional formats:**
  - `add_conditional_formatting` appends the new rule (or inserts at `rule_index`) and prints the resulting list, which matches the sheet.
  - `update_conditional_formatting` keeps the color when only values change.
  - Deleting shifts later indices down. A bad index gives `"rule_index 9 is out of range for sheet 'Line Items' (current count: 2)."`

---

## 7. Latency (median per call, ms)

Real round-trips from India to Google, for calls that reached the API. These feed the "real tool latency × tool calls" metric.

| App | Typical | Slow outliers |
|---|---|---|
| Gmail | 300–850 | `search_emails` ~700 (grows with hits: one metadata call per result), `get_unread_emails` ~1800, `list_archived` ~1600, `list_drafts` ~3200 |
| Calendar | 380–700 | `delete_event` ~1000 |
| Tasks | 340–860 | `move_task` ~1000 |
| Docs | 360–1000 | `create_doc` ~2200, `create_table_with_data` **~12 200** |
| Sheets | 350–1070 | `create_spreadsheet` ~2400 |

The largest single result seen was 3.6 k characters (a detailed 10-event listing). Everything is far below the 50 k Hermes limit at probe scale; the seed must keep it that way.

---

## 8. What this means

### For task writing
- **Every planned task type is now reachable.** Docs and sheets can be found by title (`search_docs` / `list_spreadsheets`), guests and descriptions can be edited alone, task updates report honestly, and email bodies keep amounts and separators.
- **The kept quirks are where tasks get their realistic difficulty:**
  - finding a doc means knowing a title word (body words don't match);
  - `list_spreadsheets` has no filter, so the seed must keep well under 25 sheets or the agent must page;
  - amounts in sheets read as display text, and currency typed as text is silently skipped by formulas;
  - task notes past 100 characters need `get_task`;
  - an event's ID has to be looked up after creating it;
  - "(organizer)" appears only when the organizer is a listed guest, so seed events Yadeesh organizes must list Yadeesh;
  - guest-list edits replace the whole list;
  - `read_email` flattens bodies to one line;
  - tables in docs read as flat lines.
- **Seed text:** write numbers in sheets as plain numbers and set display formats separately.

### For the fake server
The cheapest way to match all of the above exactly is to **fake the Google API client, not the tools**. The fake server imports the real tool functions from `app_tools/` and swaps each module's `get_service()` / `drive_get_service()` for an in-memory Google client. Then:
- names, parameters, descriptions and every output format are identical by construction;
- the fake only has to reproduce Google's own behavior (search matching, value formatting, exclusive all-day ends, error texts above);
- any later fix in `app_tools/` reaches the fake automatically;
- this probe and `checks.py` can be pointed at the fake to compare it with the real thing.

---

## 9. Lab fidelity (the fake vs this account)

The lab (`eval/lab`) runs the real `app_tools` functions against an in-memory Google API. The probe was run against both, and `eval/probe/compare.py` diffs them call by call with IDs, times and addresses masked.

**Result (2026-09-27):**
- Every probe call that doesn't depend on pre-existing account data returns the same text: Docs indices and tables, comments, sheet display values, conditional rules, Tasks listings, every error message.
- `checks.py` passes 30/30 on both.

**Known differences, all minor and deliberate:**

| Difference | Why it stays |
|---|---|
| Gmail's *snippet* shows `₹1,84,500` as `₹1,84500`; the lab keeps the comma | No clear rule to copy; the full body (`read_email`) is identical |
| Attendee order in event listings | Google itself returned different orders across runs |
| `after:` / `before:` dates are read as Pacific midnight (12:30 IST) | Not confirmed on the real account; the seed keeps needles clear of both readings |
| Drafts don't appear in `search_emails` | No task searches for drafts |
| Nested tables in Docs are rejected | Real Docs allows them; no task needs one |
