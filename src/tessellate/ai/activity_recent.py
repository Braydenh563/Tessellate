"""What was I working on, what did I change today: the notes most recently
touched (L161 b, INBOX 1841).

`ai/activity.py` recaps a window by what was made, edited or binned. These two
shapes ask for the newest edits themselves: with no window ("what was I working
on", "what did I last edit") the five notes touched last, and with "today" or
"yesterday" the notes touched that day. A note counts as touched at its last
edit, or at its making when it was never edited, so a note written this morning
is today's work. A question that names a subject ("what did I change in the
harbor plan") is a search and is left to it, as is the present tense ("what am I
working on" reads the notes that say so, `composer_overview`).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import activity
from tessellate.ai.notebook_stats import StatAnswer

SHOWN = 5
_LEAD = r"^\W*(?:(?:so|ok|okay|hey)[ ,]+)?"
_END = r"\W*$"
#: "what was I working on", "what have I been working on", "what did I last edit".
_WORKING = re.compile(
    _LEAD + r"what (?:was|were) i (?:last |just |most recently )?(?:working on|editing|changing)(?: (?:last|most recently|before|just now))?" + _END
    + r"|" + _LEAD + r"what have i been (?:working on|editing)" + _END
    + r"|" + _LEAD + r"what did i (?:last|most recently) (?:edit|change|work on|touch|update)" + _END,
    re.I,
)
#: "what did I change today", "which notes did I edit yesterday": the day is
#: left in `tail` for the one date reader (`activity._window`).
_CHANGED = re.compile(
    _LEAD + r"(?:what|which notes?) (?:did|have) i (?:change[d]?|edit(?:ed)?|touch(?:ed)?|update[d]?|work(?:ed)? on)(?P<tail>.*?)" + _END,
    re.I,
)


def _touches(session: Session, zone) -> list[tuple[datetime, str, int, str]]:  # noqa: ANN001
    """Each note as (when it was last touched on the person's clock, edited or
    made, id, title), newest first."""
    from tessellate.core.database import Entry

    rows = session.scalars(
        select(Entry).where(
            Entry.is_private == False,  # noqa: E712
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_draft == False,  # noqa: E712
            Entry.map_topic == False,  # noqa: E712
            Entry.is_board == False,  # noqa: E712
        )
    ).all()
    out = []
    for entry in rows:
        edited = activity._local(entry.edited_at, zone)  # noqa: SLF001
        made = activity._local(entry.created_at, zone)  # noqa: SLF001
        at, doing = (edited, "edited") if edited else (made, "made")
        if at:
            out.append((at, doing, entry.id, activity._note_name(entry.content)))  # noqa: SLF001
    return sorted(out, key=lambda row: (row[0], row[2]), reverse=True)


def _line(row: tuple[datetime, str, int, str], today: date) -> str:
    at, doing, ident, title = row
    return f"- {activity._link('note', ident, title)} ({doing} {activity._day_words(at.date(), today).lower()})"  # noqa: SLF001


def _one_day(tail: str, today: date) -> tuple[str, date] | None:
    """The single past day `tail` names ("today", "yesterday"), read by the
    one date reader, with the words it was said in."""
    window = activity._window(tail.strip(), today)  # noqa: SLF001
    if window is None or window[1][0] != window[1][1] or window[0].lower() != tail.strip().lower():
        return None
    return window[0].lower(), window[1][0]


def _quiet_day(rows: list, said: str, target: date, today: date) -> StatAnswer:
    #: The nearest touch before the day, else the first one after it.
    last = next((r for r in rows if r[0].date() < target), rows[-1])
    return StatAnswer(
        kind="activity",
        text=f"No note was changed {said}. The nearest one was:\n\n{_line(last, today)}",
        facts=[{"id": last[2], "doing": last[1]}],
    )


def _listed(lead: str, shown: list, more: str, today: date) -> StatAnswer:
    body = "\n".join(_line(r, today) for r in shown)
    return StatAnswer(kind="activity", text=f"{lead}\n\n{body}{more}", facts=[{"id": r[2], "doing": r[1]} for r in shown])


def _on_day(rows: list, said: str, target: date, today: date) -> StatAnswer:
    inside = [r for r in rows if r[0].date() == target]
    if not inside:
        return _quiet_day(rows, said, target, today)
    lead = f"{activity._n(len(inside)).capitalize()} {'note was' if len(inside) == 1 else 'notes were'} changed {said}:"  # noqa: SLF001
    more = f"\n\nAnd {activity._n(len(inside) - SHOWN)} more." if len(inside) > SHOWN else ""  # noqa: SLF001
    return _listed(lead, inside[:SHOWN], more, today)


def answer(question: str, session: Session, now: datetime) -> StatAnswer | None:
    """The newest edits as a list, or None when `question` is neither shape."""
    text = " ".join((question or "").split())
    if len(text) > 120:
        return None
    today, zone = now.date(), now.tzinfo or timezone.utc
    changed = _CHANGED.match(text)
    day = _one_day(changed.group("tail"), today) if changed and changed.group("tail").strip() else None
    if not ((changed and not changed.group("tail").strip()) or day or _WORKING.match(text)):
        return None
    rows = _touches(session, zone)
    if not rows:
        return StatAnswer(kind="activity", text="You have no notes yet.", facts=[])
    if day:
        return _on_day(rows, day[0], day[1], today)
    shown = rows[:SHOWN]
    lead = "The note you touched last:" if len(shown) == 1 else f"The {activity._n(len(shown))} notes you touched last, newest first:"  # noqa: SLF001
    return _listed(lead, shown, "", today)
