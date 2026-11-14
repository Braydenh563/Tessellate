"""What `GET /insights/remarks` says (CHAT_PLAN "Proactive", L-chat-54 and 57):
the voice's remarks narrowed to real signals, plus the ones that need the
whole notebook (a plan left open, a tension, a dated plan with no reminder, a
question a note answers). No model; private and binned notes are never read.
The words are `ai/composer_proactive.py` and `ai/composer_voice.py`'s."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from tessellate.ai import composer_proactive, composer_voice, resurface
from tessellate.repo import reminders as reminder_repo, voice

#: How many recent notes are read for a dated plan, and how many newest ones
#: can answer a question.
SCAN_NOTES = 300
NEWEST = 5


def _with_fact(remark: dict) -> dict:
    """The fact a remark is about, for the page's seen store: its kind and
    the note or reminder it names, else its words' key."""
    if "fact" in remark:
        return remark
    about = remark.get("note_id") or remark.get("reminder_id") or remark["key"]
    return {**remark, "fact": f"{remark['kind']}:{about}", "ttl_days": composer_proactive.FACT_TTL_DAYS}


def _tension_pairs(session: Session) -> list[tuple[int, int, str]]:
    from tessellate.ai import tensions

    rows, _counts = tensions.listing(session, status="open", limit=5)
    return [(r.earlier_id, r.later_id, r.pair) for r in rows]


def _open_questions(session: Session) -> list[dict]:
    from tessellate.ai import questions

    return questions.listing(session, state="open", limit=50)["items"]


def _voice_remarks(session: Session, today: date, now: datetime) -> tuple[list[dict], list[dict]]:
    """The voice's remarks (due now, one back note, this day, patterns, open
    items) and the notes they were read from."""
    recent = voice.recent(session)
    ids = {e.id for e in recent}
    back = [e for e in resurface.for_day(session, today, limit=1) if not e.is_private and not e.is_deleted][:1]
    extra = [*(e for e in voice.this_day_before(session, today) if e.id not in ids), *(e for e in back if e.id not in ids)]
    notes = voice.as_notes(session, [*recent, *extra])
    held = composer_proactive.due_now(reminder_repo.due_by(session, today), now)
    return composer_voice.remarks(notes, today=today, reminders=held, resurfaced=[e.id for e in back]), notes


def _views_of(session: Session, rows) -> list:  # noqa: ANN001
    return composer_voice._views(voice.as_notes(session, rows))


def _answered(session: Session, notes: list[dict], today: date) -> list[dict]:
    questions = _open_questions(session)
    found = (composer_proactive.answered(view, questions, today) for view in composer_voice._views(notes[:NEWEST]))
    return [a for a in found if a][:1]


def _tension(session: Session, today: date) -> list[dict]:
    pairs = _tension_pairs(session)
    views = {v.id: v for v in _views_of(session, voice.by_ids(session, [i for p in pairs for i in p[:2]]))}
    return composer_proactive.tension(views, pairs, today)


def build(session: Session, today: date, now: datetime) -> list[dict]:
    """The remarks, best first: due now, a dated plan with no reminder, an
    answered question, a new tension, then the voice's own, then drift."""
    said, notes = _voice_remarks(session, today, now)
    every = [{"id": r.id, "entry_id": r.entry_id, "done": r.done} for r in reminder_repo.every(session)]
    plan = composer_proactive.upcoming(_views_of(session, voice.recent(session, SCAN_NOTES)), every, now)
    stale = composer_proactive.drift(_views_of(session, voice.stale_plans(session, today)), today)
    due = [r for r in said if r["kind"] == "due"]
    rest = [r for r in said if r["kind"] != "due"]
    return [_with_fact(r) for r in [*due, *plan, *_answered(session, notes, today), *_tension(session, today), *rest, *stale]]


def on_this_day(session: Session, today: date) -> dict | None:
    """The first note written on today's date in an earlier year (or one,
    three or six months back), said as the dashboard's line (P3)."""
    notes = voice.as_notes(session, voice.this_day_before(session, today))
    found = composer_voice._on_this_day(composer_voice._views(notes), today)
    return found[0] if found else None
