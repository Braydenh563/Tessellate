"""Three notes a day that are slipping out of reach (WORLD_CLASS_PLAN 15, I4).

Two routes, and the split between them is the point: `POST /resurface/compute`
does the scan and writes `note_scores`, `GET /resurface` sorts what is already
stored. The read has to be fast enough to sit on a dashboard that paints on
every visit, which it cannot be if it counts every link in the notebook first.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from tessellate.ai import resurface
from tessellate.core import jobruns
from tessellate.core.database import NoteScore
from tessellate.core.deps import get_session
from tessellate.entry import manager

router = APIRouter(prefix="/resurface", tags=["resurface"])


def _card(session: Session, entry) -> dict:  # noqa: ANN001
    """One card: enough to recognise the note, and why it is being shown.

    The reason travels with the card because a panel that cannot say why it
    chose something is a panel people learn to distrust: "120 days old, no
    links, never opened" is checkable, "0.82" is not.
    """
    content = manager.readable_content(entry)
    row = session.get(NoteScore, entry.id)
    return {
        "id": entry.id,
        # A note that never wrote itself a heading still needs a label: most
        # notes here are a paragraph with no `#` line, and `extract_title`
        # returns None for every one of them, so a card without this fallback
        # is a blank card.
        #
        # The *first line*, not the first sixty characters of the flattened
        # note: flattening reads "Note 4 Something written down a while ago
        # about subj", which is a title and its body run together with the
        # break that separated them removed. A person's own first line is the
        # closest thing to a title a note without one has.
        "title": _name(manager.plain_label(content)) or "Untitled note",
        "preview": " ".join(content.split())[:200],
        "created_at": entry.created_at,
        # The three facts the score is made of, in the card, because a panel
        # that cannot say why it chose something is a panel people learn to
        # distrust. `reason` is the sentence; the numbers travel beside it so
        # a caller can phrase it differently without recomputing anything.
        "age_days": row.age_days if row else None,
        "link_count": row.link_count if row else None,
        "access_count": row.access_count if row else None,
        "reason": _reason(row, entry),
    }


def _name(label: str, words: int = 6) -> str:
    """A label as a name of at most six words, never cut mid-word (G12: an
    untitled note's first 80 characters ended "... get a suica card inste")."""
    parts = label.split()
    return label if len(parts) <= words else " ".join(parts[:words]).rstrip(",;:") + "…"


_MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
_COUNT_WORDS = ("zero", "once", "twice", "three times", "four times", "five times", "six times", "seven times", "eight times", "nine times", "ten times")


def _reason(row, entry=None) -> str:  # noqa: ANN001
    """Why a note came back, as a sentence that can be checked: when it is
    from, and whether it has been opened since. "From August; you have not
    opened it since." says more than "72 days old, no links, never opened"
    said on every row (the numbers travel beside it as `age_days`, ...)."""
    if row is None:
        return ""
    made = getattr(entry, "created_at", None)
    if not row.age_days:
        start = "Written today"
    elif made is not None:
        start = f"From {_MONTH_NAMES[made.month - 1]}" + ("" if row.age_days < 330 else f" {made.year}")
    else:
        start = f"{row.age_days} days old"
    if not row.access_count:
        tail = "you have not opened it since" if row.age_days else "not opened yet"
    elif row.access_count < len(_COUNT_WORDS):
        tail = f"opened {_COUNT_WORDS[row.access_count]}"
    else:
        tail = f"opened {row.access_count} times"
    links = "" if row.link_count else ", with no links"
    return f"{start}{links}; {tail}."


@router.post("/compute")
def compute(session: Session = Depends(get_session)) -> dict:
    """Refresh every note's fading score. Cheap enough to run on demand,
    meant to run nightly."""
    with jobruns.job_run("resurface") as run:
        written = resurface.compute_scores(session)
        session.commit()
        run.result = f"scored {written} note{'' if written == 1 else 's'}"
    return {"scored": written}


@router.get("")
def today(
    as_of: str = Query(default=""),
    limit: int = Query(default=resurface.DAILY, ge=1, le=20),
    session: Session = Depends(get_session),
) -> dict:
    """The day's cards. `as_of=YYYY-MM-DD` asks for another day's set, which
    is what makes "stable within a day, different across days" testable rather
    than a claim."""
    day: date | None = None
    if as_of:
        try:
            day = date.fromisoformat(as_of)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Write the date as year-month-day, like 2026-10-04.") from exc
    # Once a day, whichever read gets here first. `ensure_fresh` says why the
    # read is allowed to do this rather than a night shift: the night shift
    # only runs with the AI on, and this feature needs no model.
    resurface.ensure_fresh(session)
    entries = resurface.for_day(session, day=day, limit=limit)
    return {"items": [_card(session, entry) for entry in entries]}


@router.get("/all")
def ranked(
    limit: int = Query(default=200, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict:
    """The whole ranking, most faded first, for the Notes tab's "Forgotten"
    sort (WORLD_CLASS_PLAN 15, I4).

    Separate from `GET /resurface` rather than a bigger `limit` on it: that
    one answers "what are today's three", which is a rotation over the top of
    this list and is deliberately stable within a day. A sort wants the order
    itself, with no rotation and no daily seed, and folding the two together
    would mean one of them quietly getting the other's behaviour.

    Ids and reasons only. The Notes list already holds every note it is
    showing, so sending their content back would be sending it twice.
    """
    resurface.ensure_fresh(session)
    entries = resurface.ranked(session, limit=limit)
    rows = []
    for entry in entries:
        row = session.get(NoteScore, entry.id)
        rows.append({"id": entry.id, "reason": _reason(row)})
    return {"items": rows}


@router.get("/near/{entry_id}")
def near(entry_id: int, limit: int = Query(default=resurface.DAILY, ge=1, le=20),
         session: Session = Depends(get_session)) -> dict:
    """The faded notes closest to the one being read. Never that note itself."""
    resurface.ensure_fresh(session)
    entries = resurface.for_context(session, context_entry_id=entry_id, limit=limit)
    return {"items": [_card(session, entry) for entry in entries]}
