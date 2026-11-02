"""The agent's starters with no model (AGENT_SKILLS_REFORM "Deepened
2026-10-10", row 1): every starter the popup agent offers is answered by the
engine when no model is connected, so the panel is never a wall of disabled
buttons. Readings come from the notebook's own rows (the day digest, the
reminders, the open note's counts and outline, the conversation's turns);
writes are act cards whose steps are `commands.RUNNABLE` tools, so they go
through the act registry's Confirm, run and Undo like a typed act (CHAT_PLAN
decisions 47 and 53). A request that needs a model still says so.

`tests/fixtures/composer/agent_starters_1010.json` is the starter set;
`tests/test_starter_acts.py` holds it at 1.0.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai import commands, day_digest, lexical_filing, realise, recognise, tagging, utilities
from tessellate.ai.composer_frame import note_title
from tessellate.core.database import Document, Entry, EntryLink, Reminder

#: Each starter's reading, first match wins. The text is folded to lower case
#: with the closing punctuation off before it is matched.
_READS = (
    ("append_today", re.compile(r"^(?:add|append) to (?:today'?s|the daily|my daily) (?:note|journal)[:,]?\s+(?P<words>.+)$")),
    #: The time words are the recogniser's (`_since_a_day`), never a list here.
    ("changed", re.compile(r"^what (?:has )?changed(?: in (?:my|the) notebook)?(?: (?P<when>.+))?$")),
    ("loose_ends", re.compile(r"\bloose ends?\b|^what should i (?:pick up|do) next$")),
    ("due", re.compile(r"^what(?:'s| is) (?:due|overdue)(?: today| soon| next)?$")),
    ("conversation", re.compile(r"^(?:summari[sz]e|sum up) (?:this|the|our) (?:conversation|chat)$")),
    ("open_note", re.compile(
        r"^(?:summari[sz]e|sum up) (?:the|this) (?:note|document|doc|board|document or board)"
        r"(?: (?:i have|i've got|that is|that's) open| on screen)?$")),
    ("tag_untagged", re.compile(r"^tag (?:my |all |all my |the )?untagged notes$")),
    #: The other tabs' starters (palette.js AGENT_TAB_STARTERS, OPEN row 562).
    ("tag_open", re.compile(r"^(?:suggest tags for|tag) (?:the|this) note(?: i have open| i've got open| on screen)?$")),
    ("save_answer", re.compile(r"^(?:save|file|keep) (?:the|that|your) (?:last )?answer(?: as a note)?$")),
    ("open_links", re.compile(r"^what(?:'s| is) linked to (?:the|this) note(?: i have open| on screen)?$")),
    ("open_board", re.compile(r"^what(?:'s| is) (?:in|on) (?:the|this) (?:board|map|board or map|mind map)(?: i have open| on screen)?$")),
    ("open_note", re.compile(
        r"^(?:list|give me|what are) the key points (?:of|in) (?:the|this) (?:document|doc|note)"
        r"(?: i have open| on screen)?$")),
    ("link_related", re.compile(r"^link (?:the )?(?:related notes|notes that (?:belong|go) together)$")),
)

LINK_PAIRS = 8
LINK_FLOOR = 0.35
LINK_SCAN = 300
TAG_NOTES = 20


def read(text: str) -> tuple[str, dict] | None:
    """The starter `text` is, as `(kind, slots)`, or None."""
    low = re.sub(r"\s+", " ", str(text or "")).strip().lower().rstrip(".?!")
    if not low or len(low) > 300:
        return None
    for kind, pattern in _READS:
        found = pattern.search(low)
        if found:
            slots = found.groupdict()
            if kind == "changed" and not _since_a_day(slots.pop("when")):
                continue
            if "words" in slots:
                slots["words"] = _original_tail(str(text).strip().rstrip("."), len(slots["words"]))
            return kind, slots
    return None


#: A fixed Wednesday the 5th, so "this week" or "this month" never reads as
#: a day on a Monday or the 2nd: the answer covers the last day, nothing more.
_A_WEDNESDAY = datetime(2000, 1, 5, 12)


def _since_a_day(when: str | None) -> bool:
    """No time words, or ones meaning today or since yesterday."""
    return when is None or recognise.days_since(when, _A_WEDNESDAY) in (0, 1)


def _original_tail(text: str, length: int) -> str:
    """The person's own words, case kept, for what the folded match found."""
    return text[-length:].strip() if length else ""


def events(session: Session, kind: str, slots: dict, now: datetime, note_ids: list[int] | None,
           history: list[dict], document_ids: list[int] | None = None, board_ids: list[int] | None = None) -> list[dict]:
    """The stream events for one starter: an answer line, then a card when
    the starter writes."""
    handler = _HANDLERS[kind]
    line, card = handler(session, slots=slots, now=now, note_ids=note_ids or [], history=history or [],
                         document_ids=document_ids or [], board_ids=board_ids or [])
    out = [{"type": "answer", "delta": line}]
    if card:
        out.append(card)
    return out


# --- readings --------------------------------------------------------------------


def _digest_lines(session: Session, now: datetime, parts: tuple[str, ...]) -> list[str]:
    lines = day_digest.compose(session, now)["lines"]
    return [line["text"] for line in lines if line["part"] in parts]


def _list_answer(head: str, rows: list[str]) -> str:
    return head if not rows else head + "\n\n" + "\n".join(f"- {row}" for row in rows)


def _changed(session: Session, *, now: datetime, **_: object) -> tuple[str, None]:
    lines = _digest_lines(session, now, ("changed",))
    if not lines:
        return "Nothing was written or edited since this time yesterday.", None
    return _list_answer(lines[0], lines[1:]), None


def _loose_ends(session: Session, *, now: datetime, **_: object) -> tuple[str, None]:
    lines = _digest_lines(session, now, ("due", "questions", "quiet"))
    if not lines:
        return "No loose ends: nothing is due, no question in your notes is open and no topic has gone quiet.", None
    return _list_answer("Worth picking up:", lines), None


def _due(session: Session, *, now: datetime, **_: object) -> tuple[str, None]:
    lines = _digest_lines(session, now, ("due",))
    if lines:
        return _list_answer(lines[0], lines[1:]), None
    upcoming = session.scalars(
        select(Reminder)
        .where(Reminder.done == False, Reminder.deleted_at.is_(None))  # noqa: E712
        .order_by(Reminder.due_at)
        .limit(3)
    ).all()
    if not upcoming:
        return "Nothing is due, and no reminder is waiting.", None
    rows = [f"“{realise.cut_title(r.text, 90)}”, {commands.reminder_when(r.due_at, now.replace(tzinfo=None))}" for r in upcoming]
    return _list_answer("Nothing is due today. Next:", rows), None


def _conversation(session: Session, *, history: list[dict], **_: object) -> tuple[str, None]:
    turns = [turn for turn in history if str(turn.get("question") or "").strip()]
    if not turns:
        return "There is nothing in this conversation yet to summarise.", None
    rows = []
    for turn in turns[-8:]:
        answer = day_digest._first_line(str(turn.get("answer") or "")) or "no answer"
        rows.append(f"You asked “{realise.cut_title(turn['question'], 70)}”: {realise.cut_title(answer, 90)}")
    head = f"This conversation has {realise.count_noun(len(turns), 'question')}."
    return _list_answer(head, rows), None


def _outline_answer(title: str, text: str) -> str:
    counts = utilities.counts(text)
    rows = [f"{realise.count_noun(counts['words'], 'word')}, {utilities.reading_time(counts['words'])}"]
    heads = [h["text"] for h in utilities.outline(text, max_level=3, limit=7) if h["text"] != title][:6]
    if heads:
        rows.append("Sections: " + ", ".join(heads))
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", re.sub(r"^#.*$", "", text, flags=re.M).strip()) if s.strip()]
    rows.extend(f"“{realise.cut_title(s, 140)}”" for s in sentences[:2])
    return _list_answer(f"“{title}”:", rows)


def _open_document_or_board(session: Session, document_ids: list[int], board_ids: list[int]):
    """The open document's outline, or the open board's answer, when no note is open; else None."""
    if document_ids:
        doc = session.get(Document, document_ids[0])
        if doc is not None and not getattr(doc, "deleted_at", None):
            return _outline_answer(realise.cut_title(doc.title or "Untitled", 80), doc.content or ""), None
    if board_ids:
        return _open_board(session, board_ids=board_ids)
    return None


def _open_note(session: Session, *, note_ids: list[int], document_ids: list[int] = (), board_ids: list[int] = (),
               **_: object) -> tuple[str, None]:
    """The open note, document or board: what it holds, without a model."""
    if not note_ids:
        answer = _open_document_or_board(session, document_ids, board_ids)
        if answer is not None:
            return answer
    entry = session.get(Entry, note_ids[0]) if note_ids else None
    if entry is None or entry.is_deleted or entry.is_private:
        return ("Nothing is open to summarise. Open a note and tick “Use the open note”, "
                "or name it: “summarise my notes about the boiler”."), None
    if entry.is_board:
        return _open_board(session, board_ids=[entry.id])
    text = entry.content or ""
    title = realise.cut_title(day_digest._first_line(text), 80) or f"Note #{entry.id}"
    return _outline_answer(title, text), None


#: `routes_chat._attached_boards`, set by routes_chat when it loads (it
#: imports this module, so importing it here would be a cycle).
ATTACHED_BOARDS = lambda session, ids: []  # noqa: E731


def _open_board(session: Session, *, board_ids: list[int] = (), note_ids: list[int] = (), **_: object) -> tuple[str, None]:
    """The open board or map's topics, from the outline Chat attaches."""
    found = ATTACHED_BOARDS(session, list(board_ids or note_ids)[:1])
    if not found:
        return "No board or map is open. Open one and tick “Use the open board”.", None
    head, _, outline = found[0]["content"].partition("\n\n")
    rows = [line.strip() for line in outline.splitlines() if line.strip()][:12]
    return _list_answer(head.replace("\n", " "), rows), None


def _open_links(session: Session, *, note_ids: list[int], **_: object) -> tuple[str, None]:
    entry = session.get(Entry, note_ids[0]) if note_ids else None
    if entry is None or entry.is_deleted or entry.is_private:
        return "Nothing is open. Open a note and tick “Use the open note”.", None
    from tessellate.entry import manager

    others = [other for _link, other in manager.links_for_entry(session, entry)
              if not other.is_deleted and not other.is_private]
    title = note_title(entry.content, size=48)
    if not others:
        return f"Nothing is linked to “{title}” yet.", None
    rows = [f"#{other.id} {note_title(other.content, size=48)}" for other in others[:12]]
    return _list_answer(f"{realise.count_noun(len(others), 'note').capitalize()} linked to “{title}”:", rows), None


# --- writes, as act cards ------------------------------------------------------------


def _listed():
    return select(Entry).where(Entry.is_deleted == False, Entry.is_private == False,  # noqa: E712
                               Entry.is_board == False, Entry.is_draft == False)  # noqa: E712


def _tags_of(entry: Entry) -> list[str]:
    try:
        tags = json.loads(entry.tags or "[]")
    except (TypeError, ValueError):
        return []
    return [str(tag) for tag in tags if tag] if isinstance(tags, list) else []


def _tag_untagged(session: Session, **_: object) -> tuple[str, dict | None]:
    bare = [e for e in session.scalars(_listed().order_by(Entry.id.desc())).all() if not _tags_of(e)]
    if not bare:
        return "Every note has a tag already.", None
    steps, items, unsure = [], [], 0
    for entry in bare:
        tags = tagging.suggest(session, entry.content or "", [], exclude_entry_id=entry.id)
        if not tags:
            unsure += 1
            continue
        steps.append({"name": "tag_note", "arguments": {"note_id": entry.id, "add": tags}})
        items.append(f"#{entry.id} {note_title(entry.content, size=48)}: {', '.join(tags)}")
        if len(steps) >= TAG_NOTES:
            break
    left = f" {realise.count_noun(unsure, 'note')} had no word that matches a tag you use, so they are left as they are." if unsure else ""
    if not steps:
        return f"{realise.count_noun(len(bare), 'note').capitalize()} without a tag, and none has a word that matches a tag you use.", None
    label = f"Tag {realise.count_noun(len(steps), 'untagged note')} with tags you already use"
    return commands._confirm(label) + left, commands._card(label, steps, items=items)


def _tag_open(session: Session, *, note_ids: list[int], **_: object) -> tuple[str, dict | None]:
    entry = session.get(Entry, note_ids[0]) if note_ids else None
    if entry is None or entry.is_deleted or entry.is_private:
        return "Nothing is open. Open a note and tick “Use the open note”.", None
    have = _tags_of(entry)
    tags = [t for t in tagging.suggest(session, entry.content or "", have, exclude_entry_id=entry.id) if t not in have]
    title = note_title(entry.content, size=48)
    if not tags:
        return f"No tag you already use fits “{title}”; it keeps {', '.join(have) or 'no tags'}.", None
    label = f"Tag “{commands._clip(title, 60)}” {', '.join(tags)}"
    steps = [{"name": "tag_note", "arguments": {"note_id": entry.id, "add": tags}}]
    return f"{label}. Confirm to do it.", commands._card(label, steps, items=[f"#{entry.id} {title}"])


def _save_answer(session: Session, *, history: list[dict], **_: object) -> tuple[str, dict | None]:
    turns = [t for t in history if str(t.get("answer") or "").strip()]
    if not turns:
        return "There is no answer in this conversation yet to save.", None
    last = turns[-1]
    question = str(last.get("question") or "").strip()
    body = str(last["answer"]).strip()
    content = (f"# {realise.cut_title(question, 80)}\n\n" if question else "") + body
    label = f"Save the last answer as a note{f' titled “{realise.cut_title(question, 60)}”' if question else ''}"
    steps = [{"name": "create_note", "arguments": {"content": content}}]
    return f"{label}. Confirm to do it.", commands._card(label, steps)


def _vectors(entries: list[Entry]) -> dict[int, dict[str, float]]:
    words = {e.id: Counter(lexical_filing.tokens(e.content or "")) for e in entries}
    seen = Counter(word for bag in words.values() for word in bag)
    total = max(len(words), 1)
    return {
        entry_id: {w: n * math.log(total / seen[w]) for w, n in bag.items() if seen[w] > 1 and seen[w] < total}
        for entry_id, bag in words.items()
    }


def _linked(session: Session) -> set[frozenset[int]]:
    return {frozenset((link.source_entry_id, link.target_entry_id)) for link in session.scalars(select(EntryLink))}


def _best_pairs(entries: list[Entry], vectors: dict[int, dict[str, float]], linked: set[frozenset[int]]) -> list[tuple]:
    pairs = []
    for i, first in enumerate(entries):
        for second in entries[i + 1:]:
            key = frozenset((first.id, second.id))
            if key in linked:
                continue
            score = lexical_filing._cosine(vectors[first.id], vectors[second.id])
            if score >= LINK_FLOOR:
                pairs.append((score, first, second))
    pairs.sort(key=lambda p: -p[0])
    chosen, used = [], set()
    for score, first, second in pairs:
        if first.id in used or second.id in used:
            continue
        chosen.append((score, first, second))
        used.update((first.id, second.id))
        if len(chosen) >= LINK_PAIRS:
            break
    return chosen


def _link_related(session: Session, **_: object) -> tuple[str, dict | None]:
    entries = session.scalars(_listed().order_by(Entry.id.desc()).limit(LINK_SCAN)).all()
    chosen = _best_pairs(entries, _vectors(entries), _linked(session))
    if not chosen:
        return "No two unlinked notes share enough words to link them.", None
    steps = [{"name": "link_notes", "arguments": {"note_id": a.id, "other_note_id": b.id}} for _, a, b in chosen]
    items = [f"#{a.id} {note_title(a.content, size=48)} and #{b.id} {note_title(b.content, size=48)}" for _, a, b in chosen]
    label = f"Link {realise.count_noun(len(chosen), 'pair')} of notes that share the most words"
    return commands._confirm(label), commands._card(label, steps, items=items)


def _today_note(session: Session, now: datetime) -> Entry | None:
    heading = f"# {now.date().isoformat()}"
    rows = session.scalars(
        select(Entry).where(Entry.is_deleted == False, func.substr(Entry.content, 1, len(heading)) == heading)  # noqa: E712
        .order_by(Entry.id)
    ).all()
    return next((e for e in rows if (e.content or "").split("\n", 1)[0].strip() == heading), None)


def _append_today(session: Session, *, slots: dict, now: datetime, **_: object) -> tuple[str, dict | None]:
    words = commands._cap(str(slots.get("words") or "").strip(" '\"“”"))
    if not words:
        return "What should go in today's note? Say it after the colon.", None
    entry = _today_note(session, now)
    said = commands._clip(words, 80)
    if entry is None:
        steps = [{"name": "create_note", "arguments": {"content": f"# {now.date().isoformat()}\n\n{words}"}}]
        label = f"Start today's note with “{said}”"
        items = []
    else:
        steps = [{"name": "edit_note", "arguments": {"note_id": entry.id, "content": (entry.content or "").rstrip() + "\n\n" + words}}]
        label = f"Add “{said}” to the end of today's note"
        items = [f"#{entry.id} {note_title(entry.content, size=48)}"]
    return commands._confirm(label), commands._card(label, steps, items=items)


_HANDLERS = {
    "changed": _changed,
    "loose_ends": _loose_ends,
    "due": _due,
    "conversation": _conversation,
    "open_note": _open_note,
    "open_board": _open_board,
    "open_links": _open_links,
    "tag_open": _tag_open,
    "save_answer": _save_answer,
    "tag_untagged": _tag_untagged,
    "link_related": _link_related,
    "append_today": _append_today,
}

#: For the tests and the Guide: what each starter reading is, in a few words.
KINDS = tuple(_HANDLERS)
