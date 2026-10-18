"""Grow a map topic from the notebook (the features audit FEAT-13; MINDMAP_PLAN
§12.3 item 2, "Suggest branches"; WHITEBOARD_PLAN decision 36).

A mind mapper's AI invents children for a topic. This one proposes them from
the person's own notes, and says which note each came from, because the plan's
differentiator is that a map here is made of the notebook rather than of text
that looks like it. Two endpoints, the preview-before-commit convention
`POST /whiteboard/boards/propose` already follows:

- `POST /whiteboard/boards/{board_id}/nodes/{node_id}/suggest` writes nothing:
  up to five child topics, each with the note it is grounded in.
- `POST /whiteboard/boards/{board_id}/nodes/{node_id}/branches` makes the ones
  the person ticked, under the topic, in one transaction, each with its own
  `created` event and its source written into the topic's note, so the client
  records the lot as one Undo step.
- `POST /whiteboard/boards/{board_id}/nodes/{node_id}/summary` writes nothing:
  a few sentences that say what the branch holds (the features audit, Phase
  G, "Summarise this branch"), which the map puts into the topic's note for
  the person to read and keep.

**Grounded by construction.** The notes come from the search engine first
(the topic's words, with its parent's for context); the model is only asked to
name a topic for each, by number, and a line that names no listed note is
dropped. With no model, or a reply that is prose, the notes' own titles are the
suggestions, which is never wrong and says so (`source: "notebook"`). The
standing caveat applies: the model is a fake transport in every test.
"""

from __future__ import annotations

import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core import deps, events
from tessellate.core.database import Entry, EntryLink, WhiteboardObject
from tessellate.core.deps import get_session

router = APIRouter(prefix="/whiteboard", tags=["whiteboard"])

#: How many suggestions, and how many notes the model chooses among.
SUGGESTIONS = 5
CANDIDATES = 8
#: Characters of each note the model sees: enough to name a topic from.
NOTE_CHARS = 280
#: A note found by meaning alone has to be this near to count. The engine
#: joins the nearest notes by meaning to every keyword search, so on a small
#: notebook every note comes back for every topic (measured: a topic of a
#: made-up word was offered a note that shared nothing with it).
MIN_MEANING = 0.5
TOPIC_KINDS = ("topic", "note", "document", "board", "file")


def _topic_text(db: Session, obj: WhiteboardObject) -> str:
    try:
        data = json.loads(obj.data or "{}")
    except (TypeError, ValueError):
        data = {}
    text = str(data.get("content") or "").strip()
    if not text and data.get("ref_id"):
        entry = db.get(Entry, data["ref_id"])
        if entry is not None and not entry.is_private:
            from tessellate.entry import manager

            text = (manager.extract_title(manager.readable_content(entry)) or "").strip()
    return text[:200]


def _node_or_404(db: Session, board_id: int, node_id: int) -> WhiteboardObject:
    obj = db.get(WhiteboardObject, node_id)
    if obj is None or obj.board_id != board_id or obj.kind not in TOPIC_KINDS:
        raise HTTPException(status_code=404, detail="That topic is not on this map.")
    return obj


def _candidates(db: Session, board_id: int, query: str, skip_titles: set[str]) -> list[tuple[Entry, str, str]]:
    """The notes the topic's words find, best first: not private, not a board,
    not already a topic on this map, not this map's own note."""
    from tessellate.entry import manager
    from tessellate.search import engine

    try:
        hits = engine.search(db, query, limit=CANDIDATES * 3)
    except Exception:  # an index being rebuilt is a reason to suggest less, not to fail
        logging.getLogger("tessellate.whiteboard").warning("Branch suggestions: search failed", exc_info=True)
        hits = []
    on_map = set()
    for obj in db.scalars(select(WhiteboardObject).where(WhiteboardObject.board_id == board_id)):
        try:
            ref = json.loads(obj.data or "{}").get("ref_id")
        except (TypeError, ValueError):
            ref = None
        if ref:
            on_map.add(ref)
    out: list[tuple[Entry, str, str]] = []
    for hit in hits:
        if hit.kind != "note" or hit.ref_id in on_map or hit.ref_id == board_id:
            continue
        if hit.scores.get("bm25", 0) <= 0 and hit.scores.get("cosine", 0) < MIN_MEANING:
            continue
        entry = db.get(Entry, hit.ref_id)
        if entry is None or entry.is_deleted or entry.is_private or entry.is_board:
            continue
        text = manager.readable_content(entry)
        title = (manager.extract_title(text) or text.strip().split("\n")[0] or "Untitled").strip()[:100]
        if title.casefold() in skip_titles:
            continue
        body = " ".join(text.replace(title, "", 1).split())[:NOTE_CHARS]
        out.append((entry, title, body))
        if len(out) >= CANDIDATES:
            break
    return out


def _ask_model(topic: str, parent: str, rows: list[tuple[Entry, str, str]]) -> list[tuple[str, int]]:
    """The model names a child topic for the notes it picks, by number. Pure
    of the database; raises when the model does."""
    system = (
        "You suggest branches for a mind map topic, from the person's own notes. "
        "Reply with ONLY lines of the form '- <short topic> [n]', where n is the "
        "number of the note it comes from. At most five lines, two to six words "
        "each, no preamble, no note that is not listed, no invented facts."
    )
    listing = "\n".join(f"[{i + 1}] {title}: {body}" for i, (_, title, body) in enumerate(rows))
    where = f'"{topic}"' + (f' (under "{parent}")' if parent else "")
    reply = deps.get_ollama().chat(
        deps.get_model_manager().utility_model(),
        [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Topic: {where}\n\nNotes:\n{listing}"},
        ],
    )
    out = []
    for line in str(reply.get("content") or "").splitlines():
        m = re.match(r"^\s*[-*+]\s*(.+?)\s*\[(\d+)\]\s*$", line)
        if m and 1 <= int(m.group(2)) <= len(rows):
            out.append((m.group(1).strip().strip('"')[:80], int(m.group(2)) - 1))
    return out


@router.post("/boards/{board_id}/nodes/{node_id}/suggest")
def suggest_branches(board_id: int, node_id: int, db: Session = Depends(get_session)) -> dict:
    """Up to five children for this topic, each grounded in one of the
    person's notes, and nothing written."""
    node = _node_or_404(db, board_id, node_id)
    topic = _topic_text(db, node)
    if not topic:
        raise HTTPException(status_code=422, detail="Give the topic some words first: they are what the notes are found by.")
    parent = None
    if node.parent_id is not None:
        up = db.get(WhiteboardObject, node.parent_id)
        parent = _topic_text(db, up) if up is not None else None
    children = db.scalars(select(WhiteboardObject).where(WhiteboardObject.parent_id == node.id)).all()
    have = {_topic_text(db, child).casefold() for child in children} | {topic.casefold()}
    rows = _candidates(db, board_id, f"{topic} {parent or ''}".strip(), have)
    if not rows:
        return {"topic": topic, "suggestions": [], "source": "notebook", "reason": "nothing"}
    picked: list[tuple[str, int]] = []
    source, reason = "notebook", "offline"
    if deps.get_ollama().is_running():
        try:
            picked = _ask_model(topic, parent or "", rows)
            reason = "unusable"
        except Exception:
            logging.getLogger("tessellate.whiteboard").warning("Branch suggestions: the model failed", exc_info=True)
            picked, reason = [], "failed"
        if picked:
            source, reason = "model", "model"
    if not picked:
        picked = [(title, i) for i, (_, title, _) in enumerate(rows)]
    out, seen = [], set(have)
    for text, index in picked:
        if not text or text.casefold() in seen:
            continue
        seen.add(text.casefold())
        entry, title, _ = rows[index]
        out.append({"text": text, "note_id": entry.id, "note_title": title})
        if len(out) >= SUGGESTIONS:
            break
    return {"topic": topic, "suggestions": out, "source": source, "reason": reason}


#: **Expand from my notes** (MINDMAP_PLAN 12.3 item 2, Phase G). A topic that is
#: a note, grown one level from that note itself rather than from a search: its
#: headings, then the notes it is linked to. Nothing to rank and nothing for a
#: model to invent, so it is the same with no model running. Headings first, at
#: most `EXPAND_HEADINGS`, so a long note does not crowd its links out.
EXPAND_HEADINGS = 8
EXPAND_MAX = 12


def _title_of(text: str) -> str:
    from tessellate.entry import manager

    return (manager.extract_title(text) or text.strip().split("\n")[0] or "Untitled").strip()[:100]


def _refs_on_map(db: Session, board_id: int) -> set[int]:
    out: set[int] = set()
    for obj in db.scalars(select(WhiteboardObject).where(WhiteboardObject.board_id == board_id)):
        try:
            ref = json.loads(obj.data or "{}").get("ref_id")
        except (TypeError, ValueError):
            ref = None
        if ref:
            out.add(ref)
    return out


def _note_behind(db: Session, node: WhiteboardObject) -> Entry | None:
    try:
        ref = json.loads(node.data or "{}").get("ref_id")
    except (TypeError, ValueError):
        ref = None
    # A document topic's ref_id is a Document id, not an Entry id.
    entry = db.get(Entry, ref) if ref and node.kind == "note" else None
    if entry is None or entry.is_deleted or entry.is_private or entry.is_board:
        return None
    return entry


def _heading_suggestions(entry: Entry, title: str, have: set[str]) -> list[dict]:
    from tessellate.ai.utilities import outline
    from tessellate.entry import manager

    seen, out = set(have) | {title.casefold()}, []
    for heading in outline(manager.readable_content(entry), max_level=4):
        words = heading["text"].strip()
        if not words or words.casefold() in seen:
            continue
        seen.add(words.casefold())
        out.append({"text": words, "note_id": entry.id, "note_title": title, "kind": "heading"})
        if len(out) >= EXPAND_HEADINGS:
            break
    return out


def _link_suggestions(db: Session, entry: Entry, board_id: int, have: set[str]) -> list[dict]:
    """Linked notes, ones this note points at before ones that point at it."""
    from sqlalchemy import or_

    from tessellate.entry import manager

    links = db.scalars(
        select(EntryLink)
        .where(or_(EntryLink.source_entry_id == entry.id, EntryLink.target_entry_id == entry.id))
        .order_by(EntryLink.id)
    ).all()
    ids = [link.target_entry_id for link in links if link.source_entry_id == entry.id]
    ids += [link.source_entry_id for link in links if link.target_entry_id == entry.id]
    on_map, seen, out = _refs_on_map(db, board_id), set(have), []
    for other_id in dict.fromkeys(ids):
        other = db.get(Entry, other_id)
        if other is None or other.id == entry.id or other.id in on_map:
            continue
        if other.is_deleted or other.is_private or other.is_board:
            continue
        title = _title_of(manager.readable_content(other))
        if title.casefold() in seen:
            continue
        seen.add(title.casefold())
        out.append({"text": title, "note_id": other.id, "note_title": title, "kind": "link"})
    return out


@router.post("/boards/{board_id}/nodes/{node_id}/expand")
def expand_from_note(board_id: int, node_id: int, db: Session = Depends(get_session)) -> dict:
    """What the note behind this topic holds that is not on the map yet: its
    headings and its linked notes, and nothing written."""
    node = _node_or_404(db, board_id, node_id)
    entry = _note_behind(db, node)
    if entry is None:
        raise HTTPException(
            status_code=422,
            detail="Only a topic that is one of your notes can be expanded from it. Use Branches from my notes for any other topic.",
        )
    from tessellate.entry import manager

    title = _title_of(manager.readable_content(entry))
    children = db.scalars(select(WhiteboardObject).where(WhiteboardObject.parent_id == node.id)).all()
    have = {_topic_text(db, child).casefold() for child in children}
    found = _heading_suggestions(entry, title, have)
    found += _link_suggestions(db, entry, board_id, have | {s["text"].casefold() for s in found})
    return {
        "topic": title,
        "suggestions": found[:EXPAND_MAX],
        "source": "note",
        "reason": "note" if found else "nothing",
    }


class BranchItem(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    note_id: int | None = None


class BranchesBody(BaseModel):
    items: list[BranchItem] = Field(min_length=1, max_length=20)


@router.post("/boards/{board_id}/nodes/{node_id}/branches", status_code=201)
def add_branches(board_id: int, node_id: int, body: BranchesBody, db: Session = Depends(get_session)) -> list[dict]:
    """Make the ticked suggestions under the topic: one transaction, a
    `created` event per topic, and the note each came from in its note."""
    from tessellate.api.routes_whiteboard import MAP_COL, MAP_ROW, WhiteboardObjectData, _object_state, _object_to_out
    from tessellate.entry import manager

    parent = _node_or_404(db, board_id, node_id)
    siblings = db.scalars(select(WhiteboardObject).where(WhiteboardObject.parent_id == parent.id)).all()
    made = []
    for i, item in enumerate(body.items):
        source = None
        if item.note_id is not None:
            entry = db.get(Entry, item.note_id)
            if entry is not None and not entry.is_deleted and not entry.is_private:
                text = manager.readable_content(entry)
                source = (manager.extract_title(text) or text.strip().split("\n")[0] or "Untitled").strip()[:100]
        data = WhiteboardObjectData(content=item.text.strip(), note=f'From your note "{source}".' if source else None)
        obj = WhiteboardObject(
            board_id=board_id,
            kind="topic",
            data=data.model_dump_json(exclude_none=True),
            x=float(parent.x) + MAP_COL,
            y=float(parent.y) + float(len(siblings) + i) * MAP_ROW,
            z=1,
            parent_id=parent.id,
        )
        db.add(obj)
        db.flush()
        events.record(db, "created", "whiteboard_object", obj.id, f"topic on map {board_id} (suggested)",
                      payload={"after": _object_state(obj)})
        made.append(obj)
    db.commit()
    for obj in made:
        db.refresh(obj)
    return [_object_to_out(obj).model_dump(mode="json") for obj in made]


#: **Summarise this branch** (the features audit, Phase G). How much of a
#: branch the model reads: enough for a branch someone would summarise, not a
#: whole map's worth of prompt on a small local model.
SUMMARY_TOPICS = 120
SUMMARY_CHARS = 6000
SUMMARY_REPLY_CHARS = 1200


def _branch_outline(db: Session, node: WhiteboardObject) -> list[tuple[int, str]]:
    """(depth, words) for the topic and everything under it, depth first in
    sibling order, at most `SUMMARY_TOPICS`; a topic with no words is skipped
    but its branch is not."""
    rows = db.scalars(
        select(WhiteboardObject).where(WhiteboardObject.board_id == node.board_id, WhiteboardObject.kind.in_(TOPIC_KINDS))
    ).all()
    children: dict[int, list[WhiteboardObject]] = {}
    for row in rows:
        if row.parent_id is not None:
            children.setdefault(row.parent_id, []).append(row)
    for kids in children.values():
        kids.sort(key=lambda o: (getattr(o, "z", 0) or 0, o.y, o.id))
    out: list[tuple[int, str]] = []
    seen: set[int] = set()
    stack = [(node, 0)]
    while stack and len(out) < SUMMARY_TOPICS:
        obj, depth = stack.pop()
        if obj.id in seen:
            continue
        seen.add(obj.id)
        words = _topic_text(db, obj)
        if words:
            out.append((depth, " ".join(words.split())))
        stack.extend((kid, depth + 1) for kid in reversed(children.get(obj.id, [])))
    return out


def _said_plainly(outline: list[tuple[int, str]]) -> str:
    """The branch from its own topics: the topic, its children, and how many
    topics there are in all. Never wrong, and plainly not a model's."""
    head = outline[0][1]
    kids = [words for depth, words in outline if depth == 1]
    if not kids:
        return f"{head} has nothing under it yet."
    names = kids[0] if len(kids) == 1 else ", ".join(kids[:-1]) + " and " + kids[-1]
    return f"{head}: {names} ({len(outline)} topics in all)."


def _ask_for_summary(outline: list[tuple[int, str]]) -> str:
    """The model's sentences about this outline, or "" when what came back is
    not prose (a list, a heading and nothing else). Raises when the model does."""
    text = "\n".join(f"{'    ' * depth}- {words}" for depth, words in outline)[:SUMMARY_CHARS]
    system = (
        "You summarise one branch of the person's mind map. Reply with two to "
        "four plain sentences that say what the branch covers and how its parts "
        "relate, using only the topics given. No preamble, no list, no heading, "
        "no facts that are not in the topics."
    )
    reply = deps.get_ollama().chat(
        deps.get_model_manager().utility_model(),
        [{"role": "system", "content": system}, {"role": "user", "content": f"The branch:\n{text}"}],
    )
    lines = [line.strip() for line in str(reply.get("content") or "").splitlines() if line.strip()]
    #: A first line that only announces ("Summary:", "Here is a summary:") goes.
    if lines and lines[0].endswith(":") and len(lines[0]) < 60:
        lines = lines[1:]
    if not lines or any(re.match(r"^([-*+]|\d+[.)]|#)\s", line) for line in lines):
        return ""
    prose = " ".join(lines)
    if not re.search(r"[.!?]", prose):
        return ""
    return prose[:SUMMARY_REPLY_CHARS].strip()


@router.post("/boards/{board_id}/nodes/{node_id}/summary")
def summarise_branch(board_id: int, node_id: int, db: Session = Depends(get_session)) -> dict:
    """A few sentences about this topic's branch, and nothing written."""
    node = _node_or_404(db, board_id, node_id)
    outline = _branch_outline(db, node)
    if not outline:
        raise HTTPException(status_code=422, detail="Give the topic some words first: they are what the summary is made of.")
    summary, source, reason = "", "outline", "offline"
    if len(outline) > 1 and deps.get_ollama().is_running():
        try:
            summary = _ask_for_summary(outline)
            reason = "unusable"
        except Exception:
            logging.getLogger("tessellate.whiteboard").warning("Branch summary: the model failed", exc_info=True)
            summary, reason = "", "failed"
        if summary:
            source, reason = "model", "model"
    if not summary:
        summary = _said_plainly(outline)
    return {"topic": outline[0][1], "summary": summary, "source": source, "reason": reason, "topics": len(outline)}
