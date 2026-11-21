"""Writes shared by typed acts and the starter acts: the end-of-note append
in the note's own shape, today's note by its heading, and the two settlements
a confirmed step gets before and after it runs. One module both callers read,
so `commands` (which runs the steps) never imports `starter_acts` (which
builds cards from `commands`): CodeQL 2103 flagged that cycle.
"""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import Entry

_CHECK_LINE = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s")
_BULLET_LINE = re.compile(r"^\s*[-*+]\s+(?!\[)")
_ITEM_LEAD = re.compile(r"^\s*(?:[-*+]\s+)?(?:\[[ xX]\]\s+)?")
#: What "add to today's note" says when it must start the note.
NEW_DAILY = re.compile(r"(# \d{4}-\d{2}-\d{2})\n\n(.+)", re.DOTALL)


def appended(content: str, text: str) -> str:
    """`content` with `text` added at the end in the note's own shape: an item
    after a checklist is `- [ ] item`, after bullets `- item`, else a new
    paragraph (audit 1029 C42). One helper, so every add keeps the structure."""
    body = content.rstrip()
    last = next((line for line in reversed(body.split("\n")) if line.strip()), "")
    item = _ITEM_LEAD.sub("", text.strip(), count=1) or text.strip()
    if _CHECK_LINE.match(last):
        return f"{body}\n- [ ] {item}"
    if _BULLET_LINE.match(last):
        return f"{body}\n- {item}"
    return f"{body}\n\n{text}"


def already_open(content: str, text: str) -> bool:
    """Whether `text` is already an unticked checklist line of `content` (R9-12: "oat milk" on the list)."""
    want = _ITEM_LEAD.sub("", text.strip(), count=1).strip().lower().rstrip(".")
    return bool(want) and any(m.group(1).strip().lower().rstrip(".") == want for m in re.finditer(r"^\s*[-*+]\s+\[ \]\s+(.+)$", content or "", re.M))


def daily_note(session: Session, heading: str) -> Entry | None:
    rows = session.scalars(
        select(Entry).where(Entry.is_deleted == False, func.substr(Entry.content, 1, len(heading)) == heading)  # noqa: E712
        .order_by(Entry.id)
    ).all()
    return next((e for e in rows if (e.content or "").split("\n", 1)[0].strip() == heading), None)


def settle_step(session: Session, name: str, args: dict) -> tuple[str, dict]:
    """A card that would start today's note, run when the note is there by now
    (another card confirmed first made it), adds to that note instead: two
    cards confirmed in turn made two notes headed the same day."""
    found = NEW_DAILY.fullmatch(str(args.get("content") or "")) if name == "create_note" else None
    existing = daily_note(session, found.group(1)) if found else None
    if existing is None:
        return name, args
    from tessellate.api.edit_conflicts import content_hash  # lazy: `ai` sits below `api`

    text = appended(existing.content or "", found.group(2))
    return "edit_note", {"note_id": existing.id, "content": text, "base_hash": content_hash(existing.content)}


def lock_undo(session: Session, name: str, args: dict, undo: object) -> object:
    """The undo of a write locked to the text it read (`base_hash`), locked in
    turn to the text that write left: text typed after the act is not lost to
    an Undo that puts the whole old text back; it is refused as stale."""
    if name != "edit_note" or not args.get("base_hash") or not isinstance(undo, dict) or undo.get("tool") != "edit_note":
        return undo
    from tessellate.api.edit_conflicts import content_hash  # lazy: `ai` sits below `api`

    entry = session.get(Entry, int(args["note_id"]))
    return undo if entry is None else {**undo, "arguments": {**undo.get("arguments", {}), "base_hash": content_hash(entry.content)}}


def text_hash(text: str | None) -> str:
    """The `base_hash` of a text a card read, for the edit-conflict lock."""
    from tessellate.api.edit_conflicts import content_hash  # lazy: `ai` sits below `api`

    return content_hash(text)


def locked_edit(note_id: int, read: str | None, content: str) -> dict:
    """An `edit_note` step that writes `content` over the text `read`, locked to
    it: a note changed after the card was made is refused, not overwritten (L124)."""
    return {"name": "edit_note", "arguments": {"note_id": note_id, "content": content, "base_hash": text_hash(read)}}
