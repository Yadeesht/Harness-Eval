"""Fake Google Calendar API v3 (calendarList.list, events.list/get/insert/patch/update/delete).

One event list is the single source of truth (world.md §3.2): an event shows on
its home calendar and on the calendar of every attendee whose calendar exists.
Times are shown in the calendar's zone (Asia/Kolkata, +05:30).
"""

from __future__ import annotations

import base64
import copy
import re
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from .base import IST, FakeRequest, api_uri, http_error, quote_id

if TYPE_CHECKING:
    from ..workspace import Workspace

BASE = "https://www.googleapis.com"
TOKEN = re.compile(r"[0-9a-z]+")


def _cal_error(status, message, uri, reason, domain="global", extra=None):
    err = {"domain": domain, "reason": reason, "message": message}
    err.update(extra or {})
    return http_error(status, message, uri, errors=[err])


def parse_rfc3339(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    if "T" not in value:
        return datetime.fromisoformat(value).replace(tzinfo=IST)
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=IST)


def event_bounds(ev: dict) -> tuple[datetime, datetime]:
    def one(part):
        if "date" in part:
            return datetime.fromisoformat(part["date"]).replace(tzinfo=IST)
        return parse_rfc3339(part["dateTime"])

    return one(ev["start"]), one(ev["end"])


def _normalize_time(part: dict) -> dict:
    """Store and show times in the calendar zone, as Google does."""
    if "date" in part and part.get("date"):
        return {"date": part["date"]}
    dt = parse_rfc3339(part["dateTime"]).astimezone(IST)
    return {"dateTime": dt.strftime("%Y-%m-%dT%H:%M:%S+05:30"), "timeZone": "Asia/Kolkata"}


class Calendar:
    def __init__(self, ws: "Workspace"):
        self.ws = ws
        self._http = None  # create_event checks service._http before building a Drive client

    def calendarList(self):
        return _CalendarList(self.ws)

    def events(self):
        return _Events(self.ws)


class _CalendarList:
    def __init__(self, ws):
        self.ws = ws

    def list(self, **_):
        def run():
            items = []
            for cal_id, cal in self.ws.state["calendar"]["calendars"].items():
                item = {
                    "kind": "calendar#calendarListEntry",
                    "id": cal_id,
                    "summary": cal["summary"],
                    "timeZone": cal.get("timeZone", "Asia/Kolkata"),
                    "accessRole": cal["accessRole"],
                }
                if cal.get("description"):
                    item["description"] = cal["description"]
                if cal.get("primary"):
                    item["primary"] = True
                items.append(item)
            return {"kind": "calendar#calendarList", "items": items}

        return FakeRequest(run, api_uri(BASE, "/calendar/v3/users/me/calendarList"))


class _Events:
    def __init__(self, ws):
        self.ws = ws
        self.c = ws.state["calendar"]

    # ---- helpers ---------------------------------------------------------
    def _cal_id(self, calendar_id: str) -> str:
        return self.ws.user_email if calendar_id == "primary" else calendar_id

    def _calendar(self, calendar_id: str, uri: str) -> dict:
        cal = self.c["calendars"].get(self._cal_id(calendar_id))
        if cal is None:
            raise _cal_error(404, "Not Found", uri, "notFound")
        return cal

    def _writable(self, calendar_id: str, uri: str) -> None:
        cal = self._calendar(calendar_id, uri)
        if cal["accessRole"] not in ("owner", "writer"):
            raise _cal_error(403, "You need to have writer access to this calendar.", uri, "requiredAccessLevel", domain="calendar")

    def _visible(self, ev: dict, cal_id: str) -> bool:
        if ev.get("status") == "cancelled":
            return False
        if ev["home"] == cal_id:
            return True
        return any(a["email"].lower() == cal_id.lower() for a in ev.get("attendees", []))

    def _find(self, calendar_id: str, event_id: str, uri: str) -> dict:
        cal_id = self._cal_id(calendar_id)
        self._calendar(calendar_id, uri)
        ev = self.c["events"].get(event_id)
        if ev is None or not self._visible(ev, cal_id):
            raise _cal_error(404, "Not Found", uri, "notFound")
        return ev

    def _view(self, ev: dict, cal_id: str) -> dict:
        """The event as the API returns it on calendar cal_id."""
        out = {
            "kind": "calendar#event",
            "id": ev["id"],
            "status": "confirmed",
            "htmlLink": "https://www.google.com/calendar/event?eid="
            + base64.b64encode(f"{ev['id']} {cal_id}".encode()).decode().rstrip("="),
            "created": ev.get("created", "2026-09-01T04:00:00.000Z"),
            "updated": ev.get("updated", "2026-09-01T04:00:00.000Z"),
            "summary": ev.get("summary", ""),
            "creator": {"email": ev["organizer"]},
            "organizer": {"email": ev["organizer"]},
            "start": dict(ev["start"]),
            "end": dict(ev["end"]),
            "iCalUID": f"{ev['id']}@google.com",
            "reminders": ev.get("reminders", {"useDefault": True}),
            "eventType": "default",
        }
        if ev["organizer"].lower() == cal_id.lower():
            out["creator"]["self"] = True
            out["organizer"]["self"] = True
        for key in ("description", "location", "transparency", "recurringEventId", "attachments"):
            if ev.get(key):
                out[key] = copy.deepcopy(ev[key])
        if ev.get("attendees"):
            attendees = []
            for a in ev["attendees"]:
                item = {"email": a["email"], "responseStatus": a.get("responseStatus", "needsAction")}
                if a.get("organizer"):
                    item["organizer"] = True
                if a["email"].lower() == cal_id.lower():
                    item["self"] = True
                if a.get("optional"):
                    item["optional"] = True
                attendees.append(item)
            out["attendees"] = attendees
        if ev.get("conferenceData"):
            out["conferenceData"] = copy.deepcopy(ev["conferenceData"])
            out["hangoutLink"] = ev["conferenceData"]["entryPoints"][0]["uri"]
        return out

    def _meet(self) -> dict:
        code = self.ws.ids.new("meet", 10, "b32hex").replace("0", "a")
        uri = f"https://meet.google.com/{code[:3]}-{code[3:7]}-{code[7:10]}"
        return {
            "entryPoints": [{"entryPointType": "video", "uri": uri, "label": uri[8:]}],
            "conferenceSolution": {"key": {"type": "hangoutsMeet"}, "name": "Google Meet"},
            "conferenceId": uri.rsplit("/", 1)[1],
        }

    def _apply(self, ev: dict, body: dict, calendar_id: str, uri: str, replace: bool) -> None:
        """Apply an insert/patch/update body to ev."""
        if replace:
            if "end" not in body:
                raise _cal_error(400, "Missing end time.", uri, "required")
            if "start" not in body:
                raise _cal_error(400, "Missing start time.", uri, "required")
            for key in ("description", "location", "attendees", "transparency", "conferenceData", "attachments"):
                ev.pop(key, None)
        for key, value in body.items():
            if key in ("start", "end"):
                ev[key] = _normalize_time(value)
            elif key == "attendees":
                old = {a["email"].lower(): a for a in ev.get("attendees", [])}
                new = []
                for a in value or []:
                    email = a["email"]
                    prev = old.get(email.lower(), {})
                    item = {"email": email, "responseStatus": prev.get("responseStatus", "needsAction")}
                    if email.lower() == ev["organizer"].lower():
                        item["organizer"] = True
                    new.append(item)
                ev["attendees"] = new
            elif key == "conferenceData":
                if value is None or value == {}:
                    ev.pop("conferenceData", None)
                elif "createRequest" in value:
                    ev["conferenceData"] = self._meet()
                elif "entryPoints" in value:
                    ev["conferenceData"] = copy.deepcopy(value)
            elif key in ("summary", "description", "location", "transparency", "reminders", "attachments"):
                if value is None:
                    ev.pop(key, None)
                else:
                    ev[key] = copy.deepcopy(value)
        start, end = event_bounds(ev)
        if end <= start:
            raise _cal_error(400, "The specified time range is empty.", uri, "timeRangeEmpty", domain="calendar", extra={"locationType": "parameter", "location": "timeMax"})
        ev["updated"] = self.ws.clock.rfc3339(self.ws.clock.stamp())

    # ---- API -------------------------------------------------------------
    def list(self, calendarId="primary", timeMin=None, timeMax=None, maxResults=250, singleEvents=False, orderBy=None, q=None, **_):
        uri = api_uri(BASE, f"/calendar/v3/calendars/{quote_id(calendarId)}/events", timeMin=timeMin, timeMax=timeMax, maxResults=maxResults, singleEvents=singleEvents, orderBy=orderBy, q=q)

        def run():
            cal = self._calendar(calendarId, uri)
            cal_id = self._cal_id(calendarId)
            lo = parse_rfc3339(timeMin) if timeMin else None
            hi = parse_rfc3339(timeMax) if timeMax else None
            if lo and hi and hi <= lo:
                raise _cal_error(400, "The specified time range is empty.", uri, "timeRangeEmpty", domain="calendar", extra={"locationType": "parameter", "location": "timeMax"})
            want = TOKEN.findall((q or "").lower())
            hits = []
            for ev in self.c["events"].values():
                if not self._visible(ev, cal_id):
                    continue
                start, end = event_bounds(ev)
                if lo and end <= lo:
                    continue
                if hi and start >= hi:
                    continue
                if want:
                    words = " ".join(
                        [ev.get("summary", ""), ev.get("description", ""), ev.get("location", ""), ev["organizer"]]
                        + [a["email"] for a in ev.get("attendees", [])]
                    ).lower()
                    have = set(TOKEN.findall(words))
                    if not all(w in have for w in want):
                        continue
                hits.append((start, ev))
            hits.sort(key=lambda p: (p[0], p[1]["id"]))
            limit = int(maxResults or 250)
            items = [self._view(ev, cal_id) for _, ev in hits[:limit]]
            return {"kind": "calendar#events", "summary": cal["summary"], "timeZone": "Asia/Kolkata", "items": items}

        return FakeRequest(run, uri)

    def get(self, calendarId="primary", eventId=None, **_):
        uri = api_uri(BASE, f"/calendar/v3/calendars/{quote_id(calendarId)}/events/{eventId}")
        return FakeRequest(lambda: self._view(self._find(calendarId, eventId, uri), self._cal_id(calendarId)), uri)

    def insert(self, calendarId="primary", body=None, conferenceDataVersion=None, supportsAttachments=None, sendUpdates=None, **_):
        uri = api_uri(BASE, f"/calendar/v3/calendars/{quote_id(calendarId)}/events", conferenceDataVersion=conferenceDataVersion, supportsAttachments=supportsAttachments)

        def run():
            self._writable(calendarId, uri)
            cal_id = self._cal_id(calendarId)
            now = self.ws.clock.rfc3339(self.ws.clock.stamp())
            ev = {
                "id": self.ws.ids.new("event", 26, "b32hex"),
                "home": cal_id,
                "organizer": cal_id,
                "created": now,
                "origin": "agent",
            }
            body_ = dict(body or {})
            if not conferenceDataVersion:
                body_.pop("conferenceData", None)
            self._apply(ev, {"summary": "", **body_}, calendarId, uri, replace=True)
            self.c["events"][ev["id"]] = ev
            return self._view(ev, cal_id)

        return FakeRequest(run, uri, "POST")

    def patch(self, calendarId="primary", eventId=None, body=None, conferenceDataVersion=None, **_):
        uri = api_uri(BASE, f"/calendar/v3/calendars/{quote_id(calendarId)}/events/{eventId}", conferenceDataVersion=conferenceDataVersion)

        def run():
            self._writable(calendarId, uri)
            ev = self._find(calendarId, eventId, uri)
            body_ = dict(body or {})
            if not conferenceDataVersion:
                body_.pop("conferenceData", None)
            trial = copy.deepcopy(ev)
            self._apply(trial, body_, calendarId, uri, replace=False)
            ev.clear()
            ev.update(trial)
            return self._view(ev, self._cal_id(calendarId))

        return FakeRequest(run, uri, "PATCH")

    def update(self, calendarId="primary", eventId=None, body=None, conferenceDataVersion=None, **_):
        uri = api_uri(BASE, f"/calendar/v3/calendars/{quote_id(calendarId)}/events/{eventId}", conferenceDataVersion=conferenceDataVersion)

        def run():
            self._writable(calendarId, uri)
            ev = self._find(calendarId, eventId, uri)
            body_ = dict(body or {})
            if not conferenceDataVersion:
                body_.pop("conferenceData", None)
            trial = copy.deepcopy(ev)
            self._apply(trial, body_, calendarId, uri, replace=True)
            ev.clear()
            ev.update(trial)
            return self._view(ev, self._cal_id(calendarId))

        return FakeRequest(run, uri, "PUT")

    def delete(self, calendarId="primary", eventId=None, **_):
        uri = api_uri(BASE, f"/calendar/v3/calendars/{quote_id(calendarId)}/events/{eventId}")

        def run():
            self._writable(calendarId, uri)
            self._find(calendarId, eventId, uri)
            del self.c["events"][eventId]
            return ""

        return FakeRequest(run, uri, "DELETE")


def all_day(d: date) -> dict:
    return {"date": d.isoformat()}


def timed(day: date, hhmm: str) -> dict:
    h, m = map(int, hhmm.split(":"))
    dt = datetime(day.year, day.month, day.day, h, m, tzinfo=IST)
    return {"dateTime": dt.strftime("%Y-%m-%dT%H:%M:%S+05:30"), "timeZone": "Asia/Kolkata"}


def add_days(d: date, n: int) -> date:
    return d + timedelta(days=n)
