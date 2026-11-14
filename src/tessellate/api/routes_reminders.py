"""Reminders: create, list, tick off, delete.

Local-only: the browser fires the notification while the app is open;
nothing runs in the cloud.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile

from tessellate.api import paging
from tessellate.api.downloads import attachment_headers
from tessellate.api.schemas import not_blank
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session
from typing import Annotated, Literal
from urllib.parse import quote, urlencode

from tessellate.ai import recognise as rec
from tessellate.ai import recognise_reminders
from tessellate.core import deps, ics_import, reminder_token
from tessellate.core.database import PRIVATE_SPACES, Entry, utcnow
from tessellate.core.deps import get_session
from tessellate.entry import private_space
from tessellate.entry.manager import log_action
from tessellate.entry.manager_text import extract_title, plain_label, readable_content
from tessellate.entry.properties import strip as strip_properties
from tessellate.repo import content as content_repo
from tessellate.repo import documents as documents_repo
from tessellate.repo import reminders as reminder_repo

router = APIRouter(prefix="/reminders", tags=["reminders"])
#: The one route outside the unlock gate: a notification's Done and Snooze,
#: which act with a token scoped to that reminder (`core/reminder_token.py`),
#: not a session. Included without `locked` in app.py; the reason is in
#: `tests/test_every_route_is_locked.py`'s open list.
open_router = APIRouter(prefix="/reminders", tags=["reminders"])

#: What Snooze on a notification moves the time on by.
NOTIFICATION_SNOOZE = timedelta(minutes=10)

Priority = Literal["low", "normal", "high"]
#: The three words, or a rule the reader keeps as itself (every weekday,
#: every 2 weeks, the last Friday of the month: TIMELINE_PLAN 11 row 8).
Recurring = Annotated[
    str,
    Field(max_length=80, pattern=r"^(?:none|daily|weekly|monthly|" + recognise_reminders.STORED_RULE.pattern + r")$"),
]
#: Up to thirty days ahead, in minutes.
AlertMinutes = Annotated[int, Field(ge=1, le=43200)]


class ReminderCreate(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    due_at: datetime
    entry_id: int | None = None
    #: A document instead of a note (row 15); never both.
    document_id: int | None = None
    priority: Priority = "normal"
    recurring: Recurring = "none"
    alert_minutes: AlertMinutes | None = None
    #: Undo's door (INBOX 537): a deleted reminder made again as it was, its
    #: due time in the past and its done mark included, which the past-date
    #: rule below otherwise refuses.
    restore: bool = False
    done: bool = False

    @model_validator(mode="after")
    def _text_is_not_blank(self) -> "ReminderCreate":
        #: Undo brings a reminder back as it was, a blank one made before the
        #: rule included; only a new one is held to it.
        if not self.restore:
            not_blank(self.text, "reminder")
        return self


class MagicAddBody(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    # Minutes east of UTC, as the browser reports it. "Tomorrow evening" has to
    # be resolved against the user's clock, not the server's: without this the
    # model was told the time in UTC and every relative time landed hours out.
    tz_offset_minutes: int | None = Field(default=None, ge=-840, le=840)
    #: The note the words were selected in, so the reminder links back to it
    #: (the owner, 2026-10-27: a selection in a note becomes a reminder).
    entry_id: int | None = None


class ReminderUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=500)
    due_at: datetime | None = None
    done: bool | None = None
    priority: Priority | None = None
    recurring: Recurring | None = None
    #: 0 clears the alert (None leaves it as it is).
    alert_minutes: int | None = Field(default=None, ge=0, le=43200)
    #: Undo's door for a snooze (WORLD_CLASS_PLAN row 32): the time it goes
    #: back to is the old one, which is usually already past (an overdue
    #: reminder is what gets snoozed), so the past-date rule must not refuse it.
    restore: bool = False

    @field_validator("text")
    @classmethod
    def _text_is_not_blank(cls, text: str | None) -> str | None:
        return not_blank(text, "reminder")


def _reject_if_in_the_past(due_at: datetime) -> None:
    """A reminder due before now will never usefully fire, it's either an
    accidental past date (a slipped year, an AM/PM mix-up in the picker) or
    a "reminder" that isn't reminding of anything upcoming. A minute of
    slack covers submit latency and clock skew, not a real mistake.
    """
    now = utcnow()  # the module's one clock, so a test fixes both checks at once
    compare_at = due_at if due_at.tzinfo else due_at.replace(tzinfo=timezone.utc)
    if compare_at < now - timedelta(minutes=1):
        raise HTTPException(
            status_code=422,
            detail="That reminder's due time is in the past. Pick a time that hasn't happened yet.",
        )


def _target(session: Session, reminder) -> tuple[str | None, str | None]:
    """What the reminder is about, as (kind, title): "note", "board", "map"
    or "document", so the row says "Open its board" rather than calling every
    target a note (row 15). (None, None) when it is about nothing, or about
    something since deleted."""
    if reminder.document_id is not None:
        document = documents_repo.find(session, reminder.document_id)
        if document is None or getattr(document, "deleted_at", None) is not None:
            return None, None
        return "document", document.title or "Untitled"
    if reminder.entry_id is None:
        return None, None
    entry = reminder_repo.its_note(session, reminder)
    if entry is None or entry.is_deleted:
        return None, None
    text = strip_properties(readable_content(entry))
    title = extract_title(text) or plain_label(text, 60)
    if entry.is_board:
        from tessellate.api.routes_whiteboard import _board_settings

        kind, _layout = _board_settings(entry)
        return ("map" if kind == "map" else "board"), title
    return "note", title


#: A private space's reminder in a notification (INBOX 1727); the desktop
#: notifier says the same (`reminder_notifier.PRIVATE_REMINDER`).
PRIVATE_REMINDER = "A private reminder"


def _notice(session: Session, reminder) -> dict | None:  # noqa: ANN001
    private = session.info.get(PRIVATE_SPACES)
    if private is None:
        private = private_space.private_space_ids(session)
    return {"text": PRIVATE_REMINDER, "target_title": None} if reminder.workspace_id in private else None


def _to_out(session: Session, reminder) -> dict:
    entry_preview = None
    #: About a private note: the lock screen's list (INBOX 1553) leaves such a reminder out.
    private = False
    target_kind, target_title = _target(session, reminder)
    if reminder.entry_id is not None:
        entry = reminder_repo.its_note(session, reminder)
        private = bool(entry is not None and entry.is_private)
        if entry is not None and not entry.is_deleted:
            # `readable_content`, not the raw column: a private note's
            # `content` is ciphertext at rest, and this preview showed that
            # ciphertext blob (or, once unlocked, otherwise skipped the
            # locked-vault placeholder every other preview surface uses), 
            # the same class of bug as the digest's, just local to this UI
            # rather than sent to a model.
            content = strip_properties(readable_content(entry)).lstrip()
            entry_preview = content if len(content) <= 60 else content[:59] + "…"
    return {
        "id": reminder.id,
        "text": reminder.text,
        "due_at": reminder.due_at.isoformat(),
        "done": reminder.done,
        "entry_id": reminder.entry_id,
        "entry_preview": entry_preview,
        "private": private,
        #: Laid over the row where it is announced (a notification, the toast,
        #: the centre): a private space's reminder without its words or what
        #: it is about (INBOX 1727); null for any other.
        "notice": _notice(session, reminder),
        "document_id": reminder.document_id,
        "target_kind": target_kind,
        "target_title": target_title,
        "priority": reminder.priority,
        "recurring": reminder.recurring,
        "alert_minutes": reminder.alert_minutes,
        #: How the repeat and the alert read back, from the reader that read them.
        "repeat_words": _repeat_words(reminder.recurring),
        "alert_words": rec.alert_words(reminder.alert_minutes) if reminder.alert_minutes else None,
    }


def _repeat_words(recurring: str) -> str | None:
    """"every 2 weeks", "every last Friday of the month": a stored repeat said back."""
    if not recurring or recurring == "none":
        return None
    return recurring if recurring in ("daily", "weekly", "monthly") else _rule_words(recurring)


_DAY_NAMES = {"MO": "Monday", "TU": "Tuesday", "WE": "Wednesday", "TH": "Thursday", "FR": "Friday", "SA": "Saturday", "SU": "Sunday"}
_NTH_WORDS = {"-1": "last", "1": "first", "2": "second", "3": "third", "4": "fourth"}


def _rule_words(rule: str) -> str:
    parts = dict(item.split("=", 1) for item in rule.split(";") if "=" in item)
    unit = {"DAILY": "day", "WEEKLY": "week", "MONTHLY": "month", "YEARLY": "year"}.get(parts.get("FREQ", ""), "time")
    n = int(parts.get("INTERVAL", 1))
    byday = parts.get("BYDAY", "")
    if byday == "MO,TU,WE,TH,FR":
        return "every weekday"
    if byday == "SA,SU":
        return "every weekend"
    if byday[:1] in "-1234" and byday[-2:] in _DAY_NAMES and len(byday) > 2:
        return f"every {_NTH_WORDS.get(byday[:-2], byday[:-2])} {_DAY_NAMES[byday[-2:]]} of the month"
    every = "every other" if n == 2 else f"every {n}" if n > 1 else "every"
    if byday in _DAY_NAMES:
        return f"{every} {_DAY_NAMES[byday]}"
    return f"{every} {unit}{'s' if n > 2 else ''}"


def _existing(session: Session, reminder_id: int):  # noqa: ANN202
    return reminder_repo.get(session, reminder_id)


def _writable(session: Session, reminder_id: int):  # noqa: ANN202
    """A write's row: 404 for none, 409 for one in the bin (`repo/content`)."""
    return content_repo.REMINDERS.writable(session, reminder_id)


#: A page of the reminder list, not a ceiling on how many reminders may
#: exist: `X-Total-Count` says the real size and `offset` reaches the rest,
#: the same shape `GET /entries` uses. 200 because the Reminders tab groups
#: what it gets by due date and a person with more than two hundred live
#: reminders is not reading past the first screen of them; at the measured
#: row cost (about 180 bytes) a page is about 35 KB rather than a response
#: that grows with the table forever (300 rows measured at 52.5 KB).
REMINDERS_PAGE_SIZE = 200
REMINDERS_PAGE_SIZE_MAX = 1000


#: How many notes one reminder-count call may cover, the same ceiling and the
#: same reason as `REFERENCE_COUNT_IDS_MAX` in routes_entries.py: a page of
#: the note list is fifty cards, and anything past this is a report rather
#: than a row of chips.
REMINDER_COUNT_IDS_MAX = 60


@router.get("/counts")
def reminder_counts(
    ids: str = Query(default="", description="Comma-separated note ids"),
    include_done: bool = False,
    session: Session = Depends(get_session),
) -> dict:
    """How many live reminders each of these notes has, for one page at once.

    INBOX 309, the owner's second sentence: "or to link reminders to notes".
    The link itself has always existed (`Reminder.entry_id`, and the
    `set_reminder` tool has taken a `note_id` since it was written), and one
    end of it was drawn: a reminder says which note it came from. The other
    end was not. A note that caused three reminders looked exactly like a
    note that caused none, which is the same gap INBOX 246 closed for boards
    and documents, so this is the same shape of answer: one batched count per
    page of cards, never a request per card.

    Done reminders are left out by default. A note whose one reminder was
    ticked off last month is finished with, and a chip that keeps counting it
    is a chip that never goes away.

    A static path declared before `/{reminder_id}` routes so FastAPI, which
    matches in declaration order, does not try "counts" as an int and 422.
    """
    wanted: list[int] = []
    for part in ids.split(","):
        part = part.strip()
        if part.isdigit():
            wanted.append(int(part))
    wanted = wanted[:REMINDER_COUNT_IDS_MAX]
    if not wanted:
        return {"counts": {}}
    found = reminder_repo.counts_for_notes(session, wanted, include_done=include_done)
    #: Every id asked about is answered for, zeros included: a caller that
    #: caches "this note has none" must be able to tell that from "the
    #: server did not mention it", or it asks again on every render.
    counts = {str(entry_id): 0 for entry_id in wanted}
    for entry_id, count in found.items():
        counts[str(entry_id)] = count
    return {"counts": counts}


@router.get("/due")
def reminders_due(session: Session = Depends(get_session)) -> dict:
    """The page's minute look, small: `open`, `next_due_at` and a `stamp` that
    changes whenever the open list the page paints from does. The page asks
    `GET /reminders` only when the stamp moved (audit 1028 K32), so an idle
    notebook costs about a hundred bytes a minute instead of a page of rows.
    A static path, declared before `/{reminder_id}`, as `/counts` is."""
    return reminder_repo.open_stamp(session, REMINDERS_PAGE_SIZE)


# --- .ics export (WORLD_CLASS_PLAN section 17, row 7) --------------------------
#
# The one way a reminder reaches a phone's calendar without a server in the
# middle: a file. Written by hand rather than with a library, because the
# format is small and the rules a calendar app is strict about are few and
# all here: CRLF line ends, lines folded at 75 octets (bytes, so a folded
# line never splits a UTF-8 character), backslash, `;`, `,` and newlines escaped, times
# in UTC with a `Z`, and a UID that stays the same across exports so a second
# import updates the event instead of duplicating it.

_ICS_PRIORITY = {"high": 1, "normal": 5, "low": 9}
_ICS_RRULE = {"daily": "DAILY", "weekly": "WEEKLY", "monthly": "MONTHLY"}


def _ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _ics_fold(line: str) -> str:
    """One content line, folded at 75 octets with CRLF + space."""
    out: list[str] = []
    current = ""
    size = 0
    for char in line:
        width = len(char.encode("utf-8"))
        # 75 on the first line; continuation lines start with a space, which
        # counts, so their text gets 74.
        if size + width > (75 if not out else 74):
            out.append(current)
            current, size = "", 0
        current += char
        size += width
    out.append(current)
    return "\r\n ".join(out) + "\r\n"


def _ics_time(value: datetime) -> str:
    moment = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _event_details(session: Session, reminder) -> str:
    """The note's opening as an event's description, or "". A private note's
    words never leave in a file or a link: the calendar gets the reminder's
    own text and nothing of the note behind it."""
    if reminder.entry_id is None:
        return ""
    entry = reminder_repo.its_note(session, reminder)
    if entry is None or entry.is_deleted or entry.is_private:
        return ""
    return " ".join(readable_content(entry).split())[:280]


def _ics_event(session: Session, reminder, stamp: str) -> list[str]:
    lines = [
        "BEGIN:VEVENT",
        f"UID:reminder-{reminder.id}@memorymap.local",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{_ics_time(reminder.due_at)}",
        f"DTEND:{_ics_time(reminder.due_at + timedelta(minutes=15))}",
        f"SUMMARY:{_ics_text(reminder.text)}",
        f"PRIORITY:{_ICS_PRIORITY.get(reminder.priority, 5)}",
    ]
    opening = _event_details(session, reminder)
    if opening:
        lines.append(f"DESCRIPTION:{_ics_text(opening)}")
    rule = _ICS_RRULE.get(reminder.recurring)
    if rule:
        lines.append(f"RRULE:FREQ={rule}")
    elif reminder.recurring.startswith("FREQ="):
        lines.append(f"RRULE:{reminder.recurring}")
    if reminder.done:
        lines.append("STATUS:COMPLETED")
    lines += [
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_ics_text(reminder.text)}",
        f"TRIGGER:-PT{reminder.alert_minutes}M" if reminder.alert_minutes else "TRIGGER:PT0M",
        "END:VALARM",
        "END:VEVENT",
    ]
    return lines


def _ics_response(session: Session, reminders: list, filename: str) -> Response:
    stamp = _ics_time(utcnow())
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Tessellate//Reminders//EN", "CALSCALE:GREGORIAN"]
    for reminder in reminders:
        lines += _ics_event(session, reminder, stamp)
    lines.append("END:VCALENDAR")
    body = "".join(_ics_fold(line) for line in lines)
    return Response(
        content=body.encode("utf-8"),
        media_type="text/calendar; charset=utf-8",
        headers=attachment_headers(filename),
    )


@router.get("/export.ics")
def export_ics(include_done: bool = False, session: Session = Depends(get_session)) -> Response:
    """Every reminder in this space as one calendar file; ticked-off ones
    only when asked, since a calendar is for what is coming."""
    rows = reminder_repo.every(session, include_done=include_done)
    return _ics_response(session, rows, "tessellate-reminders.ics")


@router.get("/{reminder_id}/export.ics")
def export_one_ics(reminder_id: int, session: Session = Depends(get_session)) -> Response:
    """One reminder as a calendar file."""
    reminder = _existing(session, reminder_id)
    return _ics_response(session, [reminder], f"reminder-{reminder.id}.ics")


@router.get("/{reminder_id}/calendar-links")
def calendar_links(reminder_id: int, session: Session = Depends(get_session)) -> dict:
    """Where "Add to Google Calendar" and "Add to Outlook" open: the provider's
    add-event page with this reminder filled in. Only addresses are built here;
    the browser opens one when the person presses the item, so nothing is sent
    before then. The details follow the .ics file's rule (`_event_details`)."""
    reminder = _existing(session, reminder_id)
    details = _event_details(session, reminder)
    end = reminder.due_at + timedelta(minutes=15)
    google = {
        "action": "TEMPLATE",
        "text": reminder.text,
        "dates": f"{_ics_time(reminder.due_at)}/{_ics_time(end)}",
    }
    if details:
        google["details"] = details
    rule = _ICS_RRULE.get(reminder.recurring)
    if rule:
        google["recur"] = f"RRULE:FREQ={rule}"
    elif reminder.recurring.startswith("FREQ="):
        google["recur"] = f"RRULE:{reminder.recurring}"
    outlook = {
        "path": "/calendar/action/compose",
        "rru": "addevent",
        "subject": reminder.text,
        "startdt": _outlook_time(reminder.due_at),
        "enddt": _outlook_time(end),
    }
    if details:
        outlook["body"] = details
    return {
        "google": f"https://calendar.google.com/calendar/render?{urlencode(google, quote_via=quote)}",
        "outlook": f"https://outlook.live.com/calendar/0/deeplink/compose?{urlencode(outlook, quote_via=quote)}",
    }


def _outlook_time(value: datetime) -> str:
    """Outlook's deep link reads ISO 8601 with its separators."""
    moment = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- .ics import (TIMELINE_PLAN section 9, decision 17) -----------------------
#
# The way back in: a calendar file becomes reminders, one bad event reported
# and the rest kept (`core/ics_import.py` reads it). An event this app wrote
# (its UID names the reminder) updates that reminder, so exporting and
# importing the same file twice never doubles anything.


def _past_and_open(event: ics_import.IcsReminder) -> bool:
    """A one-off event already gone by that was never ticked off: a calendar
    archive's history, not something to be reminded of."""
    return not event.done and event.recurring == "none" and event.due_at.replace(tzinfo=timezone.utc) < utcnow() - timedelta(minutes=1)


#: A plain `def`, run in the threadpool: the parse and one row per event ran
#: on the event loop and froze every request and stream for the length of a
#: big calendar (audit 1028 K17).
@router.post("/import.ics")
def import_ics(
    file: UploadFile = File(...),
    tz_offset_minutes: int = Form(default=0, ge=-840, le=840),
    session: Session = Depends(get_session),
) -> dict:
    """Reminders from a calendar file, with what was skipped and why."""
    raw = file.file.read(ics_import.MAX_BYTES + 1)
    if len(raw) > ics_import.MAX_BYTES:
        raise HTTPException(status_code=413, detail="That calendar file is over 2 MB. Export only the reminders and try again.")
    text = raw.decode("utf-8", errors="replace")
    if "BEGIN:VCALENDAR" not in text.upper():
        raise HTTPException(status_code=422, detail="That is not a calendar (.ics) file.")
    reading = ics_import.read(text, tz_offset_minutes)
    added: list[int] = []
    updated: list[int] = []
    skipped = list(reading.skipped)
    for event in reading.events:
        if _past_and_open(event):
            skipped.append({"line": event.line, "text": event.text, "reason": f"line {event.line}: already past"})
            continue
        verb, reminder = reminder_repo.import_event(session, event)
        (added if verb == "added" else updated).append(reminder.id)
    if added or updated:
        log_action(session, "created", "reminder", added[0] if added else updated[0], f"imported {len(added)}, updated {len(updated)}")
    session.commit()
    return {"added": added, "updated": updated, "skipped": sorted(skipped, key=lambda row: row["line"])}


@router.get("")
def list_reminders(
    response: Response,
    limit: int = Query(default=REMINDERS_PAGE_SIZE, ge=1, le=REMINDERS_PAGE_SIZE_MAX),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    entry_id: int | None = Query(default=None, description="Only this note's reminders"),
    document_id: int | None = Query(default=None, description="Only this document's reminders"),
    include_done: bool = True,
    due_within_days: int | None = Query(default=None, ge=0, le=3650, description="Only reminders due within this many days (overdue ones included)"),
    session: Session = Depends(get_session),
) -> list[dict]:
    """A page of reminders, soonest first; the frontend groups them.

    `limit`/`offset` page the list and `X-Total-Count` gives the real size
    regardless of the page, so a caller knows when it has everything. The id
    is the tiebreaker on `due_at` so two reminders due at the same minute
    cannot swap places between one page and the next, which is how a paged
    list silently drops a row.

    `entry_id` narrows it to one note's reminders (INBOX 309). The filter is
    in SQL and `X-Total-Count` counts the same filtered set, because a total
    that answers a different question from the rows is worse than no total:
    the Reminders tab pages on it.
    """
    offset = paging.start(cursor, offset)
    due_before = utcnow().replace(tzinfo=None) + timedelta(days=due_within_days) if due_within_days is not None else None
    rows, total = reminder_repo.page(
        session, limit=limit, offset=offset, entry_id=entry_id, document_id=document_id,
        include_done=include_done, due_before=due_before,
    )
    response.headers["X-Total-Count"] = str(total)
    paging.finish(response, offset, limit, total)
    return [_to_out(session, r) for r in rows]


@router.post("", status_code=201)
def create_reminder(body: ReminderCreate, session: Session = Depends(get_session)) -> dict:
    if not body.restore:
        _reject_if_in_the_past(body.due_at)
    if body.entry_id is not None and body.document_id is not None:
        raise HTTPException(status_code=422, detail="A reminder is about a note or a document, not both.")
    if body.entry_id is not None:
        deps.get_or_404(session, Entry, body.entry_id, "That note could not be found.")
    if body.document_id is not None:
        document = documents_repo.find(session, body.document_id)
        if document is None or getattr(document, "deleted_at", None) is not None:
            raise HTTPException(status_code=404, detail="That document could not be found.")
    twin = reminder_repo.twin(session, body.text, body.due_at)
    reminder = reminder_repo.create(
        session,
        text=body.text,
        due_at=body.due_at,
        entry_id=body.entry_id,
        document_id=body.document_id,
        priority=body.priority,
        recurring=body.recurring,
        alert_minutes=body.alert_minutes,
        done=body.restore and body.done,
    )
    session.commit()
    return {**_to_out(session, reminder), "duplicate": twin is not None}


class WhenBody(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    tz_offset_minutes: int | None = Field(default=None, ge=-840, le=840)


@router.post("/when")
def read_when(body: WhenBody) -> dict:
    """A typed date or time ("next friday", "3pm") as wall-clock parts.

    The date and time pickers' typed entry (UI_MODERNISATION_PLAN Phase 12
    decision 5): `ai/when` reads it with no model, on the person's clock, and
    nothing is made. 422 when the words are not a time.
    """
    from tessellate.ai import when

    zone = timezone(timedelta(minutes=body.tz_offset_minutes or 0))
    at = when.resolve(body.text, utcnow().astimezone(zone))
    if at is None:
        raise HTTPException(status_code=422, detail="I couldn't read a date or time from that.")
    if at.tzinfo is not None:
        at = at.astimezone(zone)
    return {"date": at.strftime("%Y-%m-%d"), "time": at.strftime("%H:%M")}


class SuggestBody(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    tz_offset_minutes: int | None = Field(default=None, ge=-840, le=840)


@router.post("/suggest")
def suggest_reminder(body: SuggestBody) -> dict:
    """The reminder a chat message reads as, or `{"suggestion": null}`.

    Makes nothing: the chat shows a chip from this and a press on it posts to
    `POST /reminders`. Rules only (`ai/reminder_suggest`), on the person's
    clock, so "on Friday" is their Friday."""
    from tessellate.ai import reminder_suggest

    zone = timezone(timedelta(minutes=body.tz_offset_minutes or 0))
    found = reminder_suggest.suggest(body.text, utcnow().astimezone(zone))
    if found is None:
        return {"suggestion": None}
    due = found["due_at"]
    if due.tzinfo is None:
        due = due.replace(tzinfo=zone)
    return {
        "suggestion": {
            "text": found["text"],
            "due_at": due.astimezone(timezone.utc).isoformat(),
            "priority": found.get("priority", "normal"),
            "recurring": found.get("recurring", "none"),
            "alert_minutes": found.get("alert_minutes"),
            "guess": bool(found.get("guess")),
        }
    }


@router.post("/parse", status_code=201)
def magic_add_reminder(body: MagicAddBody, session: Session = Depends(get_session)) -> dict:
    """Magic Add: parse natural language into a reminder and create it.

    The time is read by rules first ("in 20 minutes", then `ai/when`'s
    wall-clock phrases), with no model; the model is asked only for what
    neither reads, and a 503 when it is off points the user at the form.
    """
    from tessellate.ai import reminder_parser

    if body.entry_id is not None:
        deps.get_or_404(session, Entry, body.entry_id, "That note could not be found.")
    offset = timedelta(minutes=body.tz_offset_minutes or 0)
    # The user's clock, labelled with the offset it actually has.
    #
    # This line is the bug behind "play league of legends in half an hour" being
    # scheduled for 10am the next day. It used to be `utcnow() + offset`, which
    # produces an aware datetime TAGGED UTC that really holds local wall-clock, 
    # so the model was told "now is 2026-08-01T23:30:00+00:00" when the +00:00
    # was a fiction. A model that then answered with an offset of its own (the
    # natural thing to do, having been given one) landed in the `else` branch
    # below, was trusted, and skipped the correction, putting the reminder out
    # by exactly the user's UTC offset. For the reporter, ten hours: half an
    # hour away became 10am tomorrow.
    #
    # A real tzinfo makes the frame true, so both branches below are now
    # answering the same question.
    user_zone = timezone(offset)
    local_now = utcnow().astimezone(user_zone)

    ollama = deps.get_ollama()
    # A phrase the rules can read needs no model at all, and refusing to add
    # "remind me in 20 minutes" because Ollama is off would break design
    # principle 2 for a request that needs nothing but arithmetic.
    #: Read as the composer hears it (O8, INBOX 904 B03): "tmrw" is tomorrow,
    #: so the day is read, and the saved words are the task, put right.
    #: Rules first (`reminder_parser.read_by_rule`): the sentence as heard,
    #: the "in ..." reader, then the wall-clock reader; the model only for
    #: what neither understands.
    parsed = reminder_parser.read_by_rule(body.text, local_now)
    if parsed is None:
        if not ollama.is_running():
            raise HTTPException(
                status_code=503,
                detail=(
                    "I couldn't read a time from that. "
                    "Try “tomorrow at 5pm” or “in 20 minutes”, or use the form."
                ),
            )
        if reminder_parser.says_no_time(body.text):
            raise HTTPException(
                status_code=422,
                detail="I couldn't read a time from that. Try “tomorrow at 5pm” or “in 20 minutes”, or use the form.",
            )
        parsed = reminder_parser.parse_reminder(
            body.text, ollama, deps.get_model_manager(), local_now
        )
    parsed["text"] = reminder_parser.worded(parsed["text"])

    due_at = parsed["due_at"]
    if due_at.tzinfo is None:
        # Answered in the user's wall-clock time, as asked.
        due_at = due_at.replace(tzinfo=user_zone)
    due_at = due_at.astimezone(timezone.utc)
    reminder = reminder_repo.create(
        session,
        text=parsed["text"],
        due_at=due_at,
        priority=parsed["priority"],
        # "water the plants every tuesday" repeats (engine probe: it was saved
        # once, as "Water the plants every").
        recurring=parsed.get("recurring", "none"),
        alert_minutes=parsed.get("alert_minutes"),
        entry_id=body.entry_id,
    )
    session.commit()
    return _to_out(session, reminder)


def _naive_utc(moment: datetime) -> datetime:
    """A moment as naive UTC, to tell whether an edit moved the due time."""
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def _is_its_own_time(new: datetime, current: datetime) -> bool:
    """The time a reminder already has, as the edit form hands it back: its
    datetime field is cut to the minute, so "unchanged" is the same minute.
    An overdue reminder saved with its own past time is not a new past date
    (INBOX 1468: it was refused, so no overdue reminder could be edited)."""
    return abs(_naive_utc(new) - _naive_utc(current)) < timedelta(minutes=1)


@router.put("/{reminder_id}")
def update_reminder(
    reminder_id: int, body: ReminderUpdate, session: Session = Depends(get_session)
) -> dict:
    reminder = _writable(session, reminder_id)
    if body.text is not None:
        reminder.text = body.text
    #: Its own time handed back (the edit form's minute) changes nothing, so a
    #: rule's chosen day (`repeat_day`) and its seconds stay.
    if body.due_at is not None and (body.restore or not _is_its_own_time(body.due_at, reminder.due_at)):
        if not body.restore:
            _reject_if_in_the_past(body.due_at)
        if _naive_utc(body.due_at) != _naive_utc(reminder.due_at):
            reminder.repeat_day = None
        reminder.due_at = body.due_at
    if body.priority is not None:
        reminder.priority = body.priority
    if body.recurring is not None:
        if body.recurring != reminder.recurring:
            reminder.repeat_day = None
        reminder.recurring = body.recurring
    if body.alert_minutes is not None:
        reminder.alert_minutes = body.alert_minutes or None
    if body.done is not None and body.done != reminder.done:
        reminder.done = body.done
        log_action(
            session,
            "edited",
            "reminder",
            reminder.id,
            "done" if body.done else "reopened",
        )
    session.commit()
    return _to_out(session, reminder)


def _same_instant(text: str, stored: datetime) -> bool:
    """Whether the sent time is the stored due time; an unreadable one is not (409, not a guess)."""
    try:
        sent = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    utc = lambda d: (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)  # noqa: E731
    return utc(sent) == utc(stored)


@router.post("/{reminder_id}/complete")
def complete_reminder(
    reminder_id: int,
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840),
    expected_due_at: str | None = Query(default=None, max_length=40),
    session: Session = Depends(get_session),
) -> dict:
    """Done, or for a repeating reminder its next time: the rule is rolled on
    from the due time (`recognise.next_occurrence`) until it is ahead of now,
    so a weekday reminder ticked on Friday lands on Monday. The rule's days
    are the person's (`tz_offset_minutes`, minutes east of UTC): 9am Monday
    in Auckland is Sunday evening in UTC. The answer keeps the time it was
    due, for the undo. `expected_due_at` is the occurrence the person saw: if
    the rule has moved on since (a double-click, a second tab) the answer is
    409 and nothing rolls, so one occurrence is never skipped. The 409 carries
    the reminder as it is now, so the caller can say where it went."""
    reminder = _writable(session, reminder_id)
    if expected_due_at and not _same_instant(expected_due_at, reminder.due_at):
        raise HTTPException(status_code=409, detail={
            "message": "That reminder already moved on. Reload to see it.",
            "reminder": _to_out(session, reminder),
        })
    was = reminder.due_at.isoformat()
    reminder_repo.complete(session, reminder, tz_offset_minutes)
    session.commit()
    return {**_to_out(session, reminder), "was_due_at": was}


class OutcomeBody(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=500)]

    @field_validator("text")
    @classmethod
    def _words(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Write what came of it.")
        return value


@router.post("/{reminder_id}/outcome")
def reminder_outcome(
    reminder_id: int, body: OutcomeBody, response: Response, session: Session = Depends(get_session)
) -> dict:
    """What came of a reminder, one line at the end of the note it is about
    (L-general-10), so the note keeps the result and not only the task. Goes
    through `update_entry`, so a private note needs its space unlocked and
    the edit is in the note's history like any other."""
    from tessellate.api import routes_entries
    from tessellate.api.edit_conflicts import content_hash
    from tessellate.api.schemas import EntryUpdate

    reminder = _writable(session, reminder_id)
    line = f"Outcome of {' '.join(reminder.text.split())}: {body.text}"
    #: Read and written under one lock, from a fresh read (review): two
    #: outcomes at once both read the old text and the second save dropped
    #: the first's line. `base_hash` also refuses an ordinary edit that lands
    #: between the read and the write, rather than overwriting it.
    with _outcome_lock:
        session.expire_all()
        entry = reminder_repo.its_note(session, reminder)
        if entry is None or entry.is_deleted or entry.is_board:
            raise HTTPException(status_code=400, detail="This reminder is not about a note.")
        content = readable_content(entry).rstrip()
        update = EntryUpdate(content=f"{content}\n\n{line}", base_hash=content_hash(readable_content(entry)))
        routes_entries.update_entry(entry.id, update, response, session, None)
    return {"entry_id": entry.id, "line": line}


_outcome_lock = threading.Lock()


@router.get("/{reminder_id}/brief")
def reminder_brief(reminder_id: int, session: Session = Depends(get_session)) -> dict:
    """A meeting-prep brief (L-general-11): when a reminder fires, the last
    notes its words point at (a person, a topic), so the meeting starts with
    what was written last time. Keyword search, so it works with no model;
    it already leaves out private notes and boards. The reminder's own note
    is the one being opened anyway, so it is left out too. Newest first."""
    from tessellate.search import search_manager

    reminder = _existing(session, reminder_id)
    hits = [e for e in search_manager.keyword_search(session, reminder.text, limit=8) if e.id != reminder.entry_id]
    hits.sort(key=lambda e: e.updated_at or e.created_at, reverse=True)
    return {"notes": [{"id": e.id, "title": plain_label(readable_content(e), 60)} for e in hits[:3]]}


@router.post("/{reminder_id}/notification-token")
def notification_token(reminder_id: int, session: Session = Depends(get_session)) -> dict:
    """A token for this reminder's notification: Done and Snooze for the next
    24 hours, for this reminder only (`core/reminder_token.py`). The page asks
    when it shows the notification and hands the token to the service worker,
    so the person's session token never sits in the notification's data."""
    _existing(session, reminder_id)
    return reminder_token.mint(reminder_id, data_dir=deps.get_config().data_dir)


class NotificationAct(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    action: Literal["done", "snooze"]
    #: Minutes east of UTC, for the next day of a repeating reminder.
    tz_offset_minutes: int = Field(default=0, ge=-840, le=840)


@open_router.post("/{reminder_id}/notification-act")
def act_from_notification(
    reminder_id: int, body: NotificationAct, session: Session = Depends(get_session)
) -> dict:
    """Done or Snooze 10 minutes from a notification, with no session.

    Outside the unlock gate on purpose: the service worker presses it after
    the tab is gone and holds only the scoped token the page asked for
    (`notification_token`). The token is checked **before the reminder is
    looked at**, names this one reminder and these two actions, and expires in
    a day; anything else answers 401 with the same words, so a stranger learns
    nothing about which reminders exist. The answer carries no reminder."""
    if not reminder_token.verify(body.token, reminder_id, body.action, data_dir=deps.get_config().data_dir):
        raise HTTPException(status_code=401, detail="That notification can no longer do this.")
    reminder = _writable(session, reminder_id)
    if body.action == "done":
        reminder_repo.complete(session, reminder, body.tz_offset_minutes)
    else:
        reminder_repo.snooze(session, reminder, NOTIFICATION_SNOOZE)
    session.commit()
    return {"ok": True, "action": body.action}


@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: int, session: Session = Depends(get_session)) -> dict:
    """To the recycle bin (WORLD_CLASS_PLAN 5 item 10): hidden, not fired,
    restorable with its id and its target until purged."""
    reminder_repo.move_to_bin(session, _writable(session, reminder_id))
    session.commit()
    return {"deleted": True, "binned": True}


@router.post("/{reminder_id}/restore")
def restore_reminder(reminder_id: int, session: Session = Depends(get_session)) -> dict:
    reminder, _was_binned = content_repo.restore(session, "reminder", reminder_id)
    session.commit()
    return _to_out(session, reminder)


@router.delete("/{reminder_id}/purge")
def purge_reminder(reminder_id: int, session: Session = Depends(get_session)) -> dict:
    """For good; only a binned reminder."""
    reminder_repo.purge(session, reminder_repo.get_any(session, reminder_id))
    session.commit()
    return {"purged": reminder_id}
