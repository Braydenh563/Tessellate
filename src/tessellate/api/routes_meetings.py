"""Meeting notes (INBOX 644): make one, read its action items, turn one into
a reminder, add lines to a section, and summarise it with its sources.

**Every write goes through the notes' own routes.** A new meeting is
`routes_entries.create_entry` with the meeting shape as its text, and an
addition is `routes_entries.update_entry`, so filing, the revision history,
the wiki sync, the vector refresh and the two-windows conflict guard are the
same for a meeting as for any note. Nothing here stores a meeting anywhere a
note does not already live (`entry/meetings.py` says why).

**It works with no model.** Making, reading and reminding need none: an
action item's due is read by the same rules Magic Add uses before it ever
asks a model ("by Friday", "tomorrow at 3pm", "in 2 days"). Summarise reads
decisions and actions by rules first and lets a model reword them when there
is one (WORLD_CLASS 28.5 row 2).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.api import routes_entries, routes_reminders
from tessellate.api.schemas import EntryCreate, EntryOut, EntryUpdate
from tessellate.core import activity, deps
from tessellate.core.database import utcnow
from tessellate.repo import reminders as reminder_repo
from tessellate.core.deps import get_session
from tessellate.entry import manager
from tessellate.entry import manager_text
from tessellate.entry import meetings as shape

router = APIRouter(tags=["meetings"])


class MeetingCreate(BaseModel):
    title: str = Field(default="", max_length=shape.MAX_TITLE)
    #: `YYYY-MM-DDTHH:MM` from a datetime field, or a date, or nothing: the
    #: writer's own clock, written into the note as they read it.
    when: str = Field(default="", max_length=20, pattern=r"^$|^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2})?$")
    attendees: list[str] = Field(default_factory=list, max_length=shape.MAX_ATTENDEES)
    agenda: list[str] = Field(default_factory=list, max_length=50)
    notes: str = Field(default="", max_length=200_000)
    #: A category picked by hand; none lets filing decide, as Capture does.
    category: str | None = Field(default=None, max_length=120)


@router.post("/meetings", response_model=EntryOut, status_code=201)
def create_meeting(body: MeetingCreate, session: Session = Depends(get_session)) -> EntryOut:
    """A new meeting note in the one shape, tagged `meeting` and typed
    Meeting, filed like any note (in the background, so the sheet never waits on a
    model)."""
    content = shape.compose(
        body.title, body.when.replace("T", " "), body.attendees, body.agenda, body.notes
    )
    return routes_entries.create_entry(
        EntryCreate(
            content=content,
            tags=[shape.MEETING_TAG],
            #: Not `note_type`: that writes the type's other fields empty into
            #: the block ("project –" on every card), and the Properties sheet
            #: offers a type's fields as rows whether or not they are written.
            category=body.category or None,
            defer_filing=not body.category,
        ),
        session,
    )


def _meeting_entry(session: Session, entry_id: int):  # noqa: ANN202
    entry = routes_entries._existing_entry(session, entry_id)
    if entry.is_deleted:
        raise HTTPException(status_code=404, detail="That note could not be found.")
    return entry


def _reminders_for(session: Session, entry_id: int) -> dict:
    """The note's reminders by their text, so an item already turned into
    one says so instead of offering to make a second."""
    rows = reminder_repo.on_note(session, entry_id)
    return {(r.text or "").strip().lower(): r for r in rows}


@router.get("/entries/{entry_id}/meeting")
def read_meeting(entry_id: int, session: Session = Depends(get_session)) -> dict:
    """What the meeting sheet draws: when, who, the decisions and the action
    items, each item with the reminder it already has."""
    entry = _meeting_entry(session, entry_id)
    content = manager_text.readable_content(entry)
    made = _reminders_for(session, entry.id)
    actions = []
    for item in shape.action_items(content):
        reminder = made.get(shape.reminder_text(item).lower())
        actions.append(
            {
                **item,
                "reminder_id": reminder.id if reminder else None,
                "reminder_due": reminder.due_at.isoformat() if reminder else None,
            }
        )
    return {
        "id": entry.id,
        "is_meeting": shape.is_meeting(content, manager.entry_tags(entry)),
        "date": shape.meeting_date(content),
        "attendees": shape.attendees(content),
        "decisions": shape.section_items(content, shape.DECISIONS),
        "actions": actions,
        "has_notes": bool(shape.section_text(content, shape.NOTES)),
    }


class RemindBody(BaseModel):
    line: int = Field(ge=0)
    #: Minutes east of UTC, the browser's, so "by Friday" is the reader's
    #: Friday (Magic Add's `tz_offset_minutes`).
    tz_offset_minutes: int = Field(default=0, ge=-840, le=840)
    #: When the item says no time: the person's answer to "When?", read by
    #: the same rules.
    when: str = Field(default="", max_length=120)


def _read_due(text: str, local_now: datetime) -> datetime | None:
    from tessellate.ai import reminder_parser, when

    parsed = reminder_parser.parse_relative(text, local_now) or when.parse_reminder_text(text, local_now)
    return parsed["due_at"] if parsed else None


@router.post("/entries/{entry_id}/meeting/remind", status_code=201)
def remind_action(entry_id: int, body: RemindBody, session: Session = Depends(get_session)) -> dict:
    """An action item as a real reminder, linked to its meeting, due when the
    line says (or when `when` says). Pressed twice, the same reminder."""
    entry = _meeting_entry(session, entry_id)
    content = manager_text.readable_content(entry)
    item = next((i for i in shape.action_items(content) if i["line"] == body.line), None)
    if item is None:
        raise HTTPException(status_code=409, detail="That action item has changed. Open the meeting again.")
    text = shape.reminder_text(item)
    existing = _reminders_for(session, entry.id).get(text.lower())
    if existing is not None:
        return routes_reminders._to_out(session, existing)
    zone = timezone(timedelta(minutes=body.tz_offset_minutes))
    local_now = utcnow().astimezone(zone)
    due = _read_due(body.when, local_now) if body.when.strip() else _read_due(item["text"], local_now)
    if due is None:
        raise HTTPException(
            status_code=422,
            detail="Say when, like “tomorrow at 9am” or “by Friday”.",
        )
    if due.tzinfo is None:
        due = due.replace(tzinfo=zone)
    due = due.astimezone(timezone.utc)
    routes_reminders._reject_if_in_the_past(due)
    reminder = reminder_repo.create(session, text=text, due_at=due, entry_id=entry.id, priority="normal")
    session.commit()
    return routes_reminders._to_out(session, reminder)


class AppendBody(BaseModel):
    section: str = Field(pattern=r"^(Agenda|Notes|Decisions|Action items)$")
    lines: list[str] = Field(min_length=1, max_length=60)
    #: The text this addition was made against, so a meeting edited in
    #: another window since is not written over (`update_entry`'s guard).
    base_hash: str | None = Field(default=None, max_length=64)


@router.post("/entries/{entry_id}/meeting/append", response_model=EntryOut)
def append_to_meeting(
    entry_id: int, body: AppendBody, response: Response, session: Session = Depends(get_session)
) -> EntryOut:
    """Lines added at the end of one section (a summary's decisions, a
    recording's transcript), the person's own lines untouched."""
    entry = _meeting_entry(session, entry_id)
    content = manager_text.readable_content(entry)
    lines = [str(line)[:20_000] for line in body.lines]
    updated = shape.append_to_section(content, body.section, lines)
    return routes_entries.update_entry(
        entry.id, EntryUpdate(content=updated, base_hash=body.base_hash), response, session, None
    )


#: What the sheet says under the list, one line each way (28.5 row 2).
RULES_NOTE = "Found by reading the words (decided, agreed, action, a name and a day); the local AI is off."
FAILED_NOTE = "The local AI could not reword these just now, so they were found by reading the words."


def _model_pass(source: str, found: dict) -> tuple[dict, str, str]:
    """The model's words on top of the rules' list, or the list as it is
    with a line saying why: Summarise never answers with nothing to press."""
    from tessellate.ai import meeting_summary

    ollama = deps.get_ollama()
    if not ollama.is_running():
        return found, "rules", RULES_NOTE
    try:
        #: Listed while the model writes (OPEN 1095), as a Chat answer is.
        with activity.track("generation", "Summarising a meeting", stoppable=False):
            written = meeting_summary.summarise(source, deps.get_model_manager(), ollama)
    except Exception:  # noqa: BLE001  # any model failure leaves the rules' list
        logging.getLogger("tessellate.meetings").warning("meeting summary failed", exc_info=True)
        return found, "rules", FAILED_NOTE
    return meeting_summary.merge(found, written), "model", ""


def _not_yet_written(content: str, result: dict) -> dict:
    """Drop what the Decisions and Action items sections already hold, so a
    second Summarise does not offer the same lines again."""
    sections = {"decisions": shape.DECISIONS, "actions": shape.ACTIONS}
    return {
        **result,
        **{
            kind: [i for i in result.get(kind, []) if not shape.already_written(content, section, i["text"])]
            for kind, section in sections.items()
        },
    }


def _held_at(content: str) -> datetime | None:
    """The meeting's own date: "tomorrow" in its notes is the day after it
    was held, not the day after Summarise was pressed."""
    try:
        return datetime.fromisoformat(shape.meeting_date(content).replace(" ", "T"))
    except ValueError:
        return None


@router.post("/entries/{entry_id}/meeting/summarise")
def summarise_meeting(entry_id: int, session: Session = Depends(get_session)) -> dict:
    """Decisions and action items read out of the meeting's notes, each with
    the words it came from. The rules read them first, with no model
    (`entry/meetings.find_items`); a model, when there is one, rewords the
    same list. Nothing is written: the sheet shows them and the person adds
    them (through `/meeting/append`, with Undo)."""
    from tessellate.ai import meeting_summary

    entry = _meeting_entry(session, entry_id)
    content = manager_text.readable_content(entry)
    #: The Notes section is what was said; the whole body when a meeting
    #: was written without the shape.
    source = shape.section_text(content, shape.NOTES) or shape.note_properties.strip(content)
    if len(source.strip()) < 20:
        raise HTTPException(status_code=422, detail="Write some notes first: there is nothing to summarise yet.")
    found = shape.find_items(source, shape.attendees(content), _held_at(content))
    result, by, note = _model_pass(source, found)
    result = _not_yet_written(content, result)
    return {**result, "by": by, "note": note, "lines": meeting_summary.as_lines(result)}
