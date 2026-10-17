"""Reminders: create, list, tick off, delete.

Local-only: the browser fires the notification while the app is open;
nothing runs in the cloud.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile

from tessellate.api import paging
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from typing import Annotated, Literal

from tessellate.ai import recognise as rec
from tessellate.core import deps, ics_import, reminder_token
from tessellate.core.database import Document, Entry, Reminder, utcnow
from tessellate.core.deps import get_session
from tessellate.entry.manager import extract_title, log_action, plain_label, readable_content
from tessellate.entry.properties import strip as strip_properties

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
    Field(max_length=80, pattern=r"^(?:none|daily|weekly|monthly|" + rec.STORED_RULE.pattern + r")$"),
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


class MagicAddBody(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    # Minutes east of UTC, as the browser reports it. "Tomorrow evening" has to
    # be resolved against the user's clock, not the server's: without this the
    # model was told the time in UTC and every relative time landed hours out.
    tz_offset_minutes: int | None = Field(default=None, ge=-840, le=840)


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


def _reject_if_in_the_past(due_at: datetime) -> None:
    """A reminder due before now will never usefully fire, it's either an
    accidental past date (a slipped year, an AM/PM mix-up in the picker) or
    a "reminder" that isn't reminding of anything upcoming. A minute of
    slack covers submit latency and clock skew, not a real mistake.
    """
    now = datetime.now(timezone.utc)
    compare_at = due_at if due_at.tzinfo else due_at.replace(tzinfo=timezone.utc)
    if compare_at < now - timedelta(minutes=1):
        raise HTTPException(
            status_code=422,
            detail="That reminder's due time is in the past. Pick a time that hasn't happened yet.",
        )


def _target(session: Session, reminder: Reminder) -> tuple[str | None, str | None]:
    """What the reminder is about, as (kind, title): "note", "board", "map"
    or "document", so the row says "Open its board" rather than calling every
    target a note (row 15). (None, None) when it is about nothing, or about
    something since deleted."""
    if reminder.document_id is not None:
        document = session.get(Document, reminder.document_id)
        if document is None or getattr(document, "deleted_at", None) is not None:
            return None, None
        return "document", document.title or "Untitled"
    if reminder.entry_id is None:
        return None, None
    entry = session.get(Entry, reminder.entry_id)
    if entry is None or entry.is_deleted:
        return None, None
    text = strip_properties(readable_content(entry))
    title = extract_title(text) or plain_label(text, 60)
    if entry.is_board:
        from tessellate.api.routes_whiteboard import _board_settings

        kind, _layout = _board_settings(entry)
        return ("map" if kind == "map" else "board"), title
    return "note", title


def _to_out(session: Session, reminder: Reminder) -> dict:
    entry_preview = None
    target_kind, target_title = _target(session, reminder)
    if reminder.entry_id is not None:
        entry = session.get(Entry, reminder.entry_id)
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


def _existing(session: Session, reminder_id: int) -> Reminder:
    return deps.get_or_404(session, Reminder, reminder_id, "That reminder could not be found.")


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
    filters = [Reminder.entry_id.in_(wanted)]
    if not include_done:
        filters.append(Reminder.done.is_(False))
    rows = session.execute(
        select(Reminder.entry_id, func.count(Reminder.id))
        .where(*filters)
        .group_by(Reminder.entry_id)
    ).all()
    #: Every id asked about is answered for, zeros included: a caller that
    #: caches "this note has none" must be able to tell that from "the
    #: server did not mention it", or it asks again on every render.
    counts = {str(entry_id): 0 for entry_id in wanted}
    for entry_id, count in rows:
        if entry_id is not None:
            counts[str(entry_id)] = int(count)
    return {"counts": counts}


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


def _ics_event(session: Session, reminder: Reminder, stamp: str) -> list[str]:
    lines = [
        "BEGIN:VEVENT",
        f"UID:reminder-{reminder.id}@memorymap.local",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{_ics_time(reminder.due_at)}",
        f"DTEND:{_ics_time(reminder.due_at + timedelta(minutes=15))}",
        f"SUMMARY:{_ics_text(reminder.text)}",
        f"PRIORITY:{_ICS_PRIORITY.get(reminder.priority, 5)}",
    ]
    if reminder.entry_id is not None:
        entry = session.get(Entry, reminder.entry_id)
        # A private note's words never leave in a file: the calendar gets the
        # reminder's own text and nothing of the note behind it.
        if entry is not None and not entry.is_deleted and not entry.is_private:
            opening = " ".join(readable_content(entry).split())[:280]
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


def _ics_response(session: Session, reminders: list[Reminder], filename: str) -> Response:
    stamp = _ics_time(utcnow())
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Tessellate//Reminders//EN", "CALSCALE:GREGORIAN"]
    for reminder in reminders:
        lines += _ics_event(session, reminder, stamp)
    lines.append("END:VCALENDAR")
    body = "".join(_ics_fold(line) for line in lines)
    return Response(
        content=body.encode("utf-8"),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export.ics")
def export_ics(include_done: bool = False, session: Session = Depends(get_session)) -> Response:
    """Every reminder in this space as one calendar file; ticked-off ones
    only when asked, since a calendar is for what is coming."""
    filters = [] if include_done else [Reminder.done.is_(False)]
    rows = list(session.scalars(select(Reminder).where(*filters).order_by(Reminder.due_at, Reminder.id)))
    return _ics_response(session, rows, "tessellate-reminders.ics")


@router.get("/{reminder_id}/export.ics")
def export_one_ics(reminder_id: int, session: Session = Depends(get_session)) -> Response:
    """One reminder as a calendar file."""
    reminder = _existing(session, reminder_id)
    return _ics_response(session, [reminder], f"reminder-{reminder.id}.ics")


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


def _import_one(session: Session, event: ics_import.IcsReminder) -> tuple[str, Reminder]:
    reminder = session.get(Reminder, event.own_id) if event.own_id else None
    verb = "updated"
    if reminder is None or reminder.deleted_at is not None:
        reminder, verb = Reminder(), "added"
        session.add(reminder)
    reminder.text = event.text
    reminder.due_at = event.due_at.replace(tzinfo=timezone.utc)
    reminder.priority = event.priority
    reminder.recurring = event.recurring
    reminder.alert_minutes = event.alert_minutes
    reminder.done = event.done
    return verb, reminder


@router.post("/import.ics")
async def import_ics(
    file: UploadFile = File(...),
    tz_offset_minutes: int = Form(default=0, ge=-840, le=840),
    session: Session = Depends(get_session),
) -> dict:
    """Reminders from a calendar file, with what was skipped and why."""
    raw = await file.read(ics_import.MAX_BYTES + 1)
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
        verb, reminder = _import_one(session, event)
        session.flush()
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
    filters = []
    if entry_id is not None:
        filters.append(Reminder.entry_id == entry_id)
    if document_id is not None:
        filters.append(Reminder.document_id == document_id)
    if not include_done:
        filters.append(Reminder.done.is_(False))
    total = session.scalar(select(func.count(Reminder.id)).where(*filters)) or 0
    rows = session.scalars(
        select(Reminder)
        .where(*filters)
        .order_by(Reminder.due_at, Reminder.id)
        .limit(limit)
        .offset(offset)
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
        document = session.get(Document, body.document_id)
        if document is None or getattr(document, "deleted_at", None) is not None:
            raise HTTPException(status_code=404, detail="That document could not be found.")
    reminder = Reminder(
        text=body.text,
        due_at=body.due_at,
        entry_id=body.entry_id,
        document_id=body.document_id,
        priority=body.priority,
        recurring=body.recurring,
        alert_minutes=body.alert_minutes,
        done=body.restore and body.done,
    )
    session.add(reminder)
    session.flush()
    log_action(session, "created", "reminder", reminder.id, body.text[:80])
    session.commit()
    return _to_out(session, reminder)


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


@router.post("/parse", status_code=201)
def magic_add_reminder(body: MagicAddBody, session: Session = Depends(get_session)) -> dict:
    """Magic Add: parse natural language into a reminder and create it.

    The time is read by rules first ("in 20 minutes", then `ai/when`'s
    wall-clock phrases), with no model; the model is asked only for what
    neither reads, and a 503 when it is off points the user at the form.
    """
    from tessellate.ai import reminder_parser

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
    text = reminder_parser.heard(body.text)
    parsed = reminder_parser.parse_relative(text, local_now)
    if parsed is None:
        # Wall-clock phrases ("tomorrow at 5pm", "next Friday", "tonight") are
        # read by `when` with no model too (audit 2026-10-05, UX-01): the model
        # is only for what neither reader understands.
        from tessellate.ai import when

        parsed = when.parse_reminder_text(text, local_now)
    if parsed is None:
        if not ollama.is_running():
            raise HTTPException(
                status_code=503,
                detail=(
                    "The local AI isn't running, and I couldn't read a time from "
                    "that. Try “tomorrow at 5pm” or “in 20 minutes”, or use the form."
                ),
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
    reminder = Reminder(
        text=parsed["text"],
        due_at=due_at,
        priority=parsed["priority"],
        # "water the plants every tuesday" repeats (engine probe: it was saved
        # once, as "Water the plants every").
        recurring=parsed.get("recurring", "none"),
        alert_minutes=parsed.get("alert_minutes"),
    )
    session.add(reminder)
    session.flush()
    log_action(session, "created", "reminder", reminder.id, parsed["text"][:80])
    session.commit()
    return _to_out(session, reminder)


def _naive_utc(moment: datetime) -> datetime:
    """A moment as naive UTC, to tell whether an edit moved the due time."""
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


@router.put("/{reminder_id}")
def update_reminder(
    reminder_id: int, body: ReminderUpdate, session: Session = Depends(get_session)
) -> dict:
    reminder = _existing(session, reminder_id)
    if body.text is not None:
        reminder.text = body.text
    if body.due_at is not None:
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


@router.post("/{reminder_id}/complete")
def complete_reminder(
    reminder_id: int,
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840),
    session: Session = Depends(get_session),
) -> dict:
    """Done, or for a repeating reminder its next time: the rule is rolled on
    from the due time (`recognise.next_occurrence`) until it is ahead of now,
    so a weekday reminder ticked on Friday lands on Monday. The rule's days
    are the person's (`tz_offset_minutes`, minutes east of UTC): 9am Monday
    in Auckland is Sunday evening in UTC. The answer keeps the time it was
    due, for the undo."""
    reminder = _existing(session, reminder_id)
    was = reminder.due_at.isoformat()
    _complete(session, reminder, tz_offset_minutes)
    session.commit()
    return {**_to_out(session, reminder), "was_due_at": was}


def _complete(session: Session, reminder: Reminder, tz_offset_minutes: int) -> None:
    """Done, or the next time of a repeating one (see `complete_reminder`)."""
    if reminder.recurring and reminder.recurring != "none":
        shift = timedelta(minutes=tz_offset_minutes)
        due = reminder.due_at.replace(tzinfo=None) + shift
        now = utcnow().replace(tzinfo=None) + shift
        # A 31st clamped to the 28th remembers it was a 31st (Brief 101b).
        anchor = reminder.repeat_day or due.day
        for _ in range(1000):
            due = rec.next_occurrence(reminder.recurring, due, anchor)
            if due > now:
                break
        reminder.repeat_day = anchor if anchor > 28 else None
        reminder.due_at = due - shift
        reminder.done = False
        log_action(session, "edited", "reminder", reminder.id, "rolled on")
    else:
        reminder.done = True
        log_action(session, "edited", "reminder", reminder.id, "done")


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
    reminder = _existing(session, reminder_id)
    if body.action == "done":
        _complete(session, reminder, body.tz_offset_minutes)
    else:
        reminder.due_at = utcnow() + NOTIFICATION_SNOOZE
        reminder.done = False
        log_action(session, "edited", "reminder", reminder.id, "snoozed")
    session.commit()
    return {"ok": True, "action": body.action}


@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: int, session: Session = Depends(get_session)) -> dict:
    """To the recycle bin (WORLD_CLASS_PLAN 5 item 10): hidden, not fired,
    restorable with its id and its target until purged."""
    reminder = _existing(session, reminder_id)
    log_action(session, "deleted", "reminder", reminder.id)
    reminder.deleted_at = utcnow()
    session.commit()
    return {"deleted": True, "binned": True}


def _binned(session: Session, reminder_id: int) -> Reminder:
    from tessellate.entry import bin as other_bin

    with other_bin.including_binned(session):
        reminder = session.get(Reminder, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail="That reminder could not be found.")
    return reminder


@router.post("/{reminder_id}/restore")
def restore_reminder(reminder_id: int, session: Session = Depends(get_session)) -> dict:
    reminder = _binned(session, reminder_id)
    if reminder.deleted_at is not None:
        reminder.deleted_at = None
        log_action(session, "restored", "reminder", reminder.id)
        session.commit()
    return _to_out(session, reminder)


@router.delete("/{reminder_id}/purge")
def purge_reminder(reminder_id: int, session: Session = Depends(get_session)) -> dict:
    """For good; only a binned reminder."""
    reminder = _binned(session, reminder_id)
    if reminder.deleted_at is None:
        raise HTTPException(status_code=409, detail="Only a reminder in the bin can be deleted for good.")
    log_action(session, "purged", "reminder", reminder.id)
    session.delete(reminder)
    session.commit()
    return {"purged": reminder_id}
