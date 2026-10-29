"""The notebook asked about itself (audit 1029 C32): "what is new", "what
changed", "what have I added lately", "what is my longest streak", "how many
days in a row have I written".

These were answered as a search (no note says "longest streak") or as the
assistant's intro. They are counts of the app's own rows, so they are
answered from them with no model: the notes (and documents, boards, maps)
made and edited in a window, and the longest run of consecutive days with a
note. With a model up the same sentence goes to it as facts (CHAT_PLAN
decision 75), so it can only phrase what was counted.

**The class, not the case.** A question is one of these shapes only when every
word of it is the frame of such a question (what, is, there, any, my, lately,
a doing word, a kind word, a window) and at least one word asks for the shape.
A word that is neither is a subject ("what changed in the harbor plan", "what
is the new year's resolution note"), which is a search, so it is left to one.
Dates are said only when the question asks about time (INBOX 1441).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import activity
from tessellate.ai import when as when_words
from tessellate.ai.notebook_stats import StatAnswer

#: What each doing word asks for: a thing made, a thing edited, or either.
#: "write" stays with the notes recall ("what did I write about chess"); "newest"
#: with the order of notes ("my newest note", `note_order`); a bare "updates"
#: is the app's.
_MADE = re.compile(r"^(?:added?|adds|made|make|creat(?:e|ed|es))$")
_EDITED = re.compile(r"^(?:edit(?:ed|s)?|modified|modify|tweaked|revised|touched)$")
_EITHER = re.compile(r"^(?:new|fresh|changed?|changes|changing|working|worked|happened|going)$")
#: A word that is the frame of the question, not its subject.
_FRAME = frozenset(
    "what whats which when is are was were has have had did do does there any anything something nothing everything show me my i ive "
    "tell give list the of in on at for to since this last past so far lately recently ago "
    "stuff things thing been got get up with again please pls s notes note entries entry documents document docs boards board "
    "maps map mind to from can could you please pls everything all".split()
)
_STREAK_FRAME = frozenset(
    "longest best biggest greatest current longer most ever record writing note taking daily many long consecutive days day "
    "row running straight run streak streaks stretch of on end written write wrote ive a an how".split()
)
_STREAK = re.compile(r"\bstreaks?\b|\b(?:days?|weeks?) (?:in a row|running|straight|on end)\b|\bconsecutive days?\b|\brun of days\b", re.I)
_LEADS = frozenset("what whats which anything any something is are has have did do there show tell give list".split())
_OWN_EDIT = re.compile(r"^(?:chang\w*|updat\w*)$")
_FRESH = frozenset(("new", "fresh"))
_FLUFF = re.compile(r"[?!.,]")
_QUIET = timedelta(days=6)


@dataclass(frozen=True)
class Asked:
    """`shape` is "new" or "streak"; `doings` what counts as new ("made",
    "edited"); `kinds` the kinds kept (empty: notes, documents, boards, maps)."""

    shape: str
    doings: frozenset[str] = frozenset()
    kinds: frozenset[str] = frozenset()


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z]+", _FLUFF.sub(" ", text.lower().replace("'s", "s").replace("'", "")))


def _kind_of(word: str) -> str | None:
    return next((k for k, pattern in activity._KINDS if pattern.match(word)), None)


def _doing_of(word: str, ahead: str, own: bool) -> set[str]:
    """What one word asks for. "New notes" are the ones made; "what changed" is
    either; "what did I change" is an edit, since the person made the change."""
    if _MADE.match(word) or (word in _FRESH and _kind_of(ahead)):
        return {"made"}
    if _EDITED.match(word) or (own and _OWN_EDIT.match(word)):
        return {"edited"}
    return {"made", "edited"} if _EITHER.match(word) else set()


def _is_doing(word: str) -> bool:
    return any(p.match(word) for p in (_MADE, _EDITED, _EITHER, _OWN_EDIT))


def _doings(words: list[str]) -> frozenset[str] | None:
    own = bool({"i", "ive", "my"} & set(words))
    found: set[str] = set()
    for word, ahead in zip(words, [*words[1:], ""]):
        found |= _doing_of(word, ahead, own)
    return frozenset(found) or None


def _new(words: list[str]) -> Asked | None:
    if not _LEADS & set(words):
        return None
    doings = _doings(words)
    if doings is None or any(w not in _FRAME and not _is_doing(w) for w in words):
        return None
    return Asked("new", doings, frozenset(k for k in map(_kind_of, words) if k and k != "reminder"))


def _streak(question: str, words: list[str]) -> Asked | None:
    if not _STREAK.search(question) or any(w not in _FRAME and w not in _STREAK_FRAME for w in words):
        return None
    #: "what is a streak" is the Guide's; it is the person's own run that is asked.
    own = {"my", "i", "ive", "longest", "best", "current", "biggest", "many", "long", "row"} & set(words)
    return Asked("streak") if own else None


def read(question: str) -> Asked | None:
    """The shape `question` asks for, or None when it is not one (a subject
    is named, or nothing asks for new, changed or a streak)."""
    text = (question or "").strip()
    if not text or len(text) > 160:
        return None
    #: A window phrase is not a subject: it is removed before the words are read.
    for _, _, phrase in when_words.find(text)[:1]:
        text = re.sub(re.escape(phrase), " ", text, flags=re.I)
    words = _words(text)
    return _streak(text, words) or _new(words)


def _window(question: str, today: date) -> tuple[str, date, date]:
    """(phrase, first day, last day): the window the question names, else the
    last seven days, which is what "new" means here."""
    named = activity._window(question, today)
    if named is not None:
        phrase, span = named
        return phrase, span[0], min(span[1], today)
    return "last 7 days", today - _QUIET, today


def _fresh(rows: list, asked: Asked) -> list:
    """The made and edited rows, an edited one dropped when the same thing was
    made inside the window (it is new, not changed)."""
    kinds = asked.kinds or {"note", "document", "board", "map"}
    kept = [r for r in rows if r[1] in asked.doings and r[2] in kinds]
    made = {r[3] for r in kept if r[1] == "made"}
    return [r for r in kept if r[1] == "made" or r[3] not in made]


def _quiet_line(asked: Asked, phrase: str, said: str) -> str:
    what = " or ".join(sorted(asked.doings)) if len(asked.doings) == 1 else "made or edited"
    word = " or ".join(sorted(activity._KIND_WORD[k] + "s" for k in asked.kinds)) if asked.kinds else "notes"
    return f"Nothing new: no {word} were {what} {said}." if phrase else f"No {word} were {what}."


def new(question: str, asked: Asked, session: Session, now: datetime, timed: bool) -> StatAnswer:
    """The notes made and edited in the window, newest first."""
    today, zone = now.date(), now.tzinfo or timezone.utc
    phrase, start, end = _window(question, today)
    window = activity.Asked(start, end, phrase, "all", asked.kinds)
    rows = _fresh(activity._events(session, start, end, zone), asked)
    said = activity._window_said(window)
    if not rows:
        return StatAnswer(kind="activity", text=_nothing(asked, said, session, window, today, zone), facts=[])
    head = f"{said[:1].upper()}{said[1:]}" + (f" ({activity._span(start, end, today)})" if timed and start != end else "")
    lines = _recap(rows, window, today, timed)
    if len(rows) > activity._LIMIT:
        lines.append(f"And {len(rows) - activity._LIMIT} more.")
    facts = [{"when": r[0].isoformat(), "doing": r[1], "kind": r[2], "what": r[3]} for r in rows[: activity._LIMIT]]
    return StatAnswer(kind="activity", text="\n".join([f"{head} you {activity._summary(rows)}:", *lines]), facts=facts)


def _recap(rows: list, window: "activity.Asked", today: date, timed: bool) -> list[str]:
    if timed:
        return activity._recap_lines(rows, window, today)
    return [f"- {c[:1].upper()}{c[1:]}." for c in (activity._clause(d, k, s) for _, d, k, s in rows[: activity._LIMIT])]


def _nothing(asked: Asked, said: str, session: Session, window: "activity.Asked", today: date, zone) -> str:  # noqa: ANN001
    before, after = activity._nearest(session, window.start, window.end, zone)
    lead = _quiet_line(asked, window.phrase, said)
    if before:
        return f"{lead} The last thing before it was made on {activity._say_day(before, today)}."
    return lead


def _local_days(session: Session, zone) -> set[date]:  # noqa: ANN001
    """The days (on the person's clock) a note was made. Private notes count,
    as the welcome's streak counts them: only a day is read, never a word."""
    from tessellate.core.database import Entry

    stamps = session.scalars(
        select(Entry.created_at).where(
            Entry.is_deleted == False, Entry.is_draft == False, Entry.is_board == False, Entry.map_topic == False  # noqa: E712
        )
    ).all()
    return {local.date() for local in (activity._local(s, zone) for s in stamps) if local}


def runs(days: set[date]) -> list[tuple[date, date]]:
    """Every run of consecutive days, as (first, last), oldest first."""
    out: list[tuple[date, date]] = []
    for day in sorted(days):
        if out and day - out[-1][1] == timedelta(days=1):
            out[-1] = (out[-1][0], day)
        else:
            out.append((day, day))
    return out


def _span_days(run: tuple[date, date]) -> int:
    return (run[1] - run[0]).days + 1


def _days(count: int) -> str:
    return f"{activity._n(count)} {'day' if count == 1 else 'days'}"


def _now_line(current: int, longest: int) -> str:
    if not current:
        return "You have no run going now."
    if current == longest:
        return "You are on it now."
    return f"Your run now is {_days(current)}."


def streak(session: Session, now: datetime, timed: bool) -> StatAnswer:
    """The longest run of consecutive days with a note, and the run now."""
    today, zone = now.date(), now.tzinfo or timezone.utc
    found = runs(_local_days(session, zone))
    if not found:
        return StatAnswer(kind="streak", text="You have no notes yet, so there is no streak.", facts=[])
    best = max(found, key=lambda r: (_span_days(r), r[1]))
    last = found[-1]
    current = _span_days(last) if last[1] >= today - timedelta(days=1) else 0
    where = f", {activity._span(best[0], best[1], today)}" if timed and best[0] != best[1] else ""
    text = f"Your longest streak is {_days(_span_days(best))} in a row{where}. {_now_line(current, _span_days(best))}"
    facts = [{"longest_days": _span_days(best), "current_days": current}]
    return StatAnswer(kind="streak", text=text, facts=facts)


def answer(question: str, session: Session, now: datetime) -> StatAnswer | None:
    """The answer to a new, changed or streak question, or None."""
    from tessellate.ai import composer, question_noise

    text = question_noise.repair(question_noise.tidy(question or ""))
    asked = read(text)
    if asked is None:
        return None
    timed = composer.asks_time(question)
    if asked.shape == "streak":
        return streak(session, now, timed)
    return new(text, asked, session, now, timed)
