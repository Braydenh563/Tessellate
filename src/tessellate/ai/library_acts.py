"""Acts on the notebook as a whole (L-chat-46 to 49, decision 3 of the owner's call, 2026-11-14): archive and
unarchive notes, tag every note from a month with one tag, start a board and read it back.

Same shape as `surface_acts`: the reader finds the sentence, the planner resolves it against the notebook and
draws the card that waits for Confirm (or a typed yes), over tools the agent already has (`archive_note`,
`tag_note`, `create_mindmap`). A bulk act names its count on the card first and runs as ONE step, so its Undo is
one step too. Nothing here writes. `commands.py` lends its card and note helpers (`_parity_helpers`).
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import recognise

INTENTS = frozenset({"archive", "unarchive", "tag_many", "make_board"})

_LEAD = r"^(?:(?:please|pls|can you|could you|would you)\s+)*"
_ARCHIVE = re.compile(rf"{_LEAD}(?P<verb>archive|un-?archive)\s+(?P<t>.+)$", re.I)
_BRING_BACK = re.compile(rf"{_LEAD}(?:bring|get|take|put)\s+(?P<t>.+?)\s+(?:back\s+)?(?:out of|from)\s+(?:the |my )?archive$", re.I)
_TO_ARCHIVE = re.compile(rf"{_LEAD}(?:move|put|file|send)\s+(?P<t>.+?)\s+(?:to|in|into)\s+(?:the |my )?archive$", re.I)
_NEW_BOARD = re.compile(
    rf"{_LEAD}(?:make|create|start|build|add)\s+(?:me\s+)?(?:a |the )?(?:new |blank |empty )?(?:white)?board\s+(?:called|named|titled|for|about)\s+(?P<t>.+)$", re.I)
_EVERYTHING = r"(?:everything|all (?:of )?(?:my )?(?:the )?(?:notes|entries)|(?:the |my )?(?:notes|entries))"
_TAG_MANY = re.compile(
    rf"{_LEAD}(?:tag|label)\s+{_EVERYTHING}\s+(?:(?:i |that i )?(?:wrote|made|saved|created|written)\s+)?(?:from|in|during|within|of|since)\s+(?P<scope>.+?)\s+(?:with|as)\s+(?P<tags>.+)$", re.I)
_NO_NAME = frozenset({"a", "an", "the", "my", "any", "one", "this", "that", "it", "all", "every"})
_OLD = re.compile(r"^(?:(?:the|my|every|all(?: of)?) )*(?:old|older|oldest|stale|finished|done|past|former)\s+", re.I)
_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
_MONTH = re.compile(rf"^(?:the )?(?:month of )?(?:(?P<m>{'|'.join(_MONTHS)}|{'|'.join(m[:3] for m in _MONTHS if m != 'may')})\.?)(?:\s+(?P<y>\d{{4}}))?$", re.I)
_MAX_NOTES = 100


def _name(text: str) -> str:
    return " ".join(text.split()).strip(" .!?\"'“”‘’")


def _target(text: str, one_target) -> dict | None:  # noqa: ANN001
    """The notes a phrase names ("the old trip notes", "the wifi note", "these"), or None."""
    said = _name(text)
    found = one_target(_OLD.sub("the ", said, count=1), bare=True)
    return found if found and (found.get("these") or found.get("note_id") is not None or (found.get("about") or "").strip()) else None


def _read_tag_many(found: re.Match) -> dict | None:
    scope = _name(found.group("scope"))
    tags = [t.strip(" .'\"") for t in re.split(r",| and ", found.group("tags").replace("#", "")) if t.strip(" .'\"")]
    return {"intent": "tag_many", "scope": scope, "tags": tags} if scope and tags else None


def _read_archive(text: str, one_target) -> dict | None:  # noqa: ANN001
    for pattern, intent in ((_BRING_BACK, "unarchive"), (_TO_ARCHIVE, "archive")):
        if (found := pattern.match(text)) and (target := _target(found.group("t"), one_target)):
            return {"intent": intent, **target}
    if found := _ARCHIVE.match(text):
        target = _target(found.group("t"), one_target)
        return {"intent": "unarchive" if found.group("verb").lower().startswith("un") else "archive", **target} if target else None
    return None


def read(text: str, one_target) -> dict | None:  # noqa: ANN001
    """The act `text` is, or None."""
    if found := _NEW_BOARD.match(text):
        name = re.sub(r"^(?:the|my|our)\s+", "", _name(found.group("t")), flags=re.I)
        return {"intent": "make_board", "title": name[:1].upper() + name[1:]} if name and name.lower() not in _NO_NAME else None
    if found := _TAG_MANY.match(text):
        return _read_tag_many(found)
    return _read_archive(text, one_target)


# --- plan -------------------------------------------------------------------------------


def _shown_name(entry) -> str:  # noqa: ANN001
    """A note as a card names it: the one reader (`composer_frame.note_title`), cut short, with the caller's own "Untitled"."""
    from tessellate.ai.composer_frame import note_title

    return note_title(entry.content, size=48) or "Untitled note"


def _by_words(session: Session, parsed: dict, c: dict) -> list:
    from tessellate.core.database import Entry

    words = c["words"](parsed.get("about") or "")
    if not words:
        return []
    query = select(Entry).where(Entry.is_deleted.is_(False), Entry.is_private.is_(False), Entry.is_board.is_(False)).order_by(Entry.id.desc())
    rows = [e for e in session.scalars(query) if all(re.search(rf"\b{re.escape(w)}", f"{e.content or ''} {e.tags or ''}".lower()) for w in words)]
    if parsed.get("single") and len(rows) > 1:
        titled = [e for e in rows if all(re.search(rf"\b{re.escape(w)}", _shown_name(e).lower()) for w in words)]
        rows = titled if len(titled) == 1 else rows
    return rows


def _found(session: Session, parsed: dict, note_ids: list[int] | None, archived: bool, c: dict) -> list:
    """The notes the sentence names that are (not) in the Archive: every word in the text or tags; a single
    note is the one whose title holds them, or the only one."""
    from tessellate.core.database import Entry

    if parsed.get("these"):
        rows = c["attached"](session, note_ids)
    elif parsed.get("note_id") is not None:
        row = session.get(Entry, int(parsed["note_id"]))
        rows = [row] if row is not None else []
    else:
        rows = _by_words(session, parsed, c)
    return [e for e in rows if not e.is_deleted and not e.is_private and bool(e.archived_at) == archived]


def _nothing_to_archive(session: Session, parsed: dict, note_ids: list[int] | None, c: dict, archive: bool) -> dict:
    """The line when no note is in the state the act needs: already there, or not found."""
    if other := _found(session, parsed, note_ids, archive, c):
        return {"line": f"{'That note is' if len(other) == 1 else 'Those notes are'} already {'in' if archive else 'out of'} the Archive."}
    about = parsed.get("about") or "those notes"
    return {"line": f"I found no note {'about “' + about + '”' if not parsed.get('these') else 'attached'}{'' if archive else ' in the Archive'}."}


def _archive_label(shown: list, parsed: dict, archive: bool) -> str:
    lead = "Archive" if archive else "Bring back"
    tail = "" if archive else " from the Archive"
    if len(shown) == 1:
        return f"{lead} the note “{_shown_name(shown[0])}”{tail}"
    of = "you attached" if parsed.get("these") else f"about “{parsed.get('about') or 'those notes'}”"
    return f"{lead} {len(shown)} notes {of}{tail}"


def _plan_archive(session: Session, parsed: dict, note_ids: list[int] | None, c: dict) -> dict:
    archive = parsed["intent"] == "archive"
    rows = _found(session, parsed, note_ids, not archive, c)
    if not rows:
        return _nothing_to_archive(session, parsed, note_ids, c, archive)
    if parsed.get("single") and len(rows) > 1:
        return {"line": "Which one: " + " or ".join(f"“{_shown_name(e)}”" for e in rows[:3]) + "?"}
    shown = rows[:_MAX_NOTES]
    label = _archive_label(shown, parsed, archive)
    step = {"name": "archive_note", "arguments": {"note_ids": [e.id for e in shown], "archived": archive}}
    more = f" That is {_MAX_NOTES} of {len(rows)}; say it again for the rest." if len(rows) > _MAX_NOTES else ""
    return {"line": c["confirm"](label) + more, "card": c["card"](label, [step], [], [_shown_name(e) for e in shown])}


def _month_back(today: date, month: int) -> date:
    """The first of `month` most recently begun on or before `today`."""
    year = today.year if month <= today.month else today.year - 1
    return date(year, month, 1)


def _month_span(found: re.Match, today: date) -> tuple[date, date, str]:
    month = next(i for i, m in enumerate(_MONTHS, 1) if m.startswith(found.group("m").lower()[:3]))
    start = date(int(found.group("y")), month, 1) if found.group("y") else _month_back(today, month)
    end = date(start.year + (month == 12), month % 12 + 1, 1)
    return start, end, f"{_MONTHS[month - 1].title()}" + (f" {start.year}" if start.year != today.year or found.group("y") else "")


def span(scope: str, today: date) -> tuple[date, date, str] | None:
    """(first day, day after the last, how it is said) for "March", "March 2025", "last week", "this month",
    "the last 14 days", "yesterday"; None when the words name no span."""
    said = _name(scope)
    if found := _MONTH.match(said):
        return _month_span(found, today)
    # Relative spans ("last week", "past 10 days", "yesterday") are read by the one reader, `recognise.span`; its
    # last day is inclusive, a span here ends the day after.
    got = recognise.span(said, today, "past")
    if not got:
        return None
    # "the last 10 days" is ten days counting today; the recogniser's run starts one earlier.
    first = got[0] + timedelta(days=1) if got[2] == "day" and got[0] != got[1] else got[0]
    return first, got[1] + timedelta(days=1), said.lower()


def _plan_tag_many(session: Session, parsed: dict, c: dict) -> dict:
    from datetime import datetime

    from tessellate.core.database import Category, Entry

    scope = parsed["scope"]
    window = span(scope, c["today"]())
    query = select(Entry).where(Entry.is_deleted.is_(False), Entry.is_private.is_(False), Entry.is_board.is_(False), Entry.archived_at.is_(None)).order_by(Entry.id)
    if window:
        start, end, said = window
        query = query.where(Entry.created_at >= datetime.combine(start, datetime.min.time()), Entry.created_at < datetime.combine(end, datetime.min.time()))
        said = f"from {said}"
    else:
        category = next((x for x in session.scalars(select(Category)) if x.name.casefold() == re.sub(r"^(?:the |my )", "", scope, flags=re.I).casefold()), None)
        if category is None:
            return {"line": f"I could not read “{scope}” as a month, a week or one of your categories. Say it like: tag everything from March with spring."}
        query = query.where(Entry.category_id == category.id)
        said = f"in {category.name}"
    rows = list(session.scalars(query))
    if not rows:
        return {"line": f"I found no notes {said}."}
    shown = rows[:_MAX_NOTES]
    tags = " ".join(f"#{t}" for t in parsed["tags"])
    label = f"Tag {len(shown)} note{'' if len(shown) == 1 else 's'} {said} {tags}"
    step = {"name": "tag_note", "arguments": {"note_ids": [e.id for e in shown], "add": parsed["tags"]}}
    more = f" That is {_MAX_NOTES} of {len(rows)}; say it again for the rest." if len(rows) > _MAX_NOTES else ""
    return {"line": c["confirm"](label) + more, "card": c["card"](label, [step], [], [_shown_name(e) for e in shown])}


def plan(session: Session, parsed: dict, note_ids: list[int] | None, c: dict) -> dict:
    """The line and card for one of `INTENTS`. `c` is `commands`' lending (`commands._parity_helpers`)."""
    intent = parsed["intent"]
    if intent == "make_board":
        label = f"Make a board called “{parsed['title']}”"
        return {"line": c["confirm"](label), "card": c["card"](label, [{"name": "create_mindmap", "arguments": {"title": parsed["title"], "kind": "board"}}])}
    if intent == "tag_many":
        return _plan_tag_many(session, parsed, c)
    return _plan_archive(session, parsed, note_ids, c)


def board_readback(session: Session, board_id: int | None) -> str:
    """The board a run made, read back from the notebook as the answer (L-chat-49): its name, what kind, how
    many cards and shapes it holds. "" when it cannot be read, so the run says only what it did."""
    from tessellate.core.database import Entry, WhiteboardNode, WhiteboardObject
    from sqlalchemy import func

    board = session.get(Entry, int(board_id)) if board_id else None
    if board is None or not board.is_board:
        return ""
    cards = session.scalar(select(func.count()).select_from(WhiteboardNode).where(WhiteboardNode.board_id == board.id)) or 0
    shapes = session.scalar(select(func.count()).select_from(WhiteboardObject).where(WhiteboardObject.board_id == board.id)) or 0
    holds = "nothing on it yet" if not (cards or shapes) else f"{cards} card{'' if cards == 1 else 's'} and {shapes} shape{'' if shapes == 1 else 's'}"
    return f"I read it back: the board “{_shown_name(board)}” is there, with {holds}. Open it from Library, Boards and maps."


def with_readbacks(session: Session, summary: str, done: list[tuple[str, dict, dict]]) -> str:
    """`summary` with the read-back of each board the run made (L-chat-49) after it."""
    backs = [board_readback(session, r.get("board_id")) for n, a, r in done if n == "create_mindmap" and a.get("kind") == "board"]
    return " ".join([summary, *[b for b in backs if b]])
