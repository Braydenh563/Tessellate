"""A map made: proposed from notes, generated, or imported from a file.

Moved whole from `routes_whiteboard.py` (audit AR3, gods-2): the code is unchanged, and
`routes_whiteboard` re-exports every name here that anything reads. Imports run one way,
down the layer list in `routes_whiteboard.py`'s docstring, never back to `routes_whiteboard`.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from tessellate.core.database import Entry, WhiteboardObject
from sqlalchemy.orm import Session
from tessellate.core import deps, events
from tessellate.core.deps import get_session
from sqlalchemy import select
from tessellate.repo import whiteboard as wb_repo
from tessellate.api.wb_board import BoardOut, _store_board_numbered, _store_board_settings
from tessellate.api.wb_model import DEFAULT_MAP_LAYOUT
from tessellate.core.events import object_state as _object_state
from tessellate.api.wb_tree import MAX_IMPORT_CHARS
from tessellate.api.wb_import import MapImport, _flatten_parsed, _parse_freemind, _parse_markdown_outline, _parse_opml, _parse_xmind, _place_map_nodes, _restore_import_links
from tessellate.api.wb_map import _outline_from_paste
from tessellate.api.wb_preview import _preview_fields
from tessellate.api.wb_export import _strip_outline_numbers

router = APIRouter()


#: The most notes one proposal is built from. Matches
#: `librarian.MAP_PROPOSAL_NOTES`, and is repeated here rather than imported
#: because a Pydantic field's bound is read at import time and this module is
#: imported by things that have no business pulling in the AI package.
MAP_PROPOSAL_MAX_NOTES = 40


class MapProposal(BaseModel):
    """"Make a map of these notes" (MINDMAP_PLAN.md section 5 item 15): which
    notes, and what to call the result."""

    note_ids: list[int] = Field(min_length=1, max_length=MAP_PROPOSAL_MAX_NOTES)
    name: str | None = Field(default=None, min_length=1, max_length=100)


def _proposal_notes(db: Session, note_ids: list[int]) -> list[Entry]:
    """The chosen notes, in the order they were chosen, minus anything that is
    not a readable note.

    A private note is dropped rather than refused: this is a bulk action over
    a list someone assembled by ticking boxes, and failing the whole thing
    because one of thirty is private would be a dead end with no obvious way
    out. The same boundary every AI-facing read path in this codebase holds
    (search, embeddings, the janitor, chat linking) still holds: its text
    never reaches the model.
    """
    found = {
        entry.id: entry
        for entry in db.scalars(select(Entry).where(Entry.id.in_(note_ids))).all()
        if not entry.is_deleted and not entry.is_private and not entry.is_board
    }
    return [found[note_id] for note_id in note_ids if note_id in found]


def _note_titles(db: Session, notes: list[Entry]) -> list[tuple[Entry, str, str]]:
    """`(entry, title, first line)` for each note, which is everything both
    the prompt and the fallback need and all either of them gets."""
    from tessellate.ai import librarian
    from tessellate.entry import manager_text

    out = []
    for entry in notes:
        text = manager_text.readable_content(entry)
        title = (manager_text.extract_title(text) or text.strip().split("\n")[0] or "Untitled")[:100]
        body = " ".join(text.replace(title, "", 1).split())[: librarian.MAP_PROPOSAL_CHARS]
        out.append((entry, title, body))
    return out


def _outline_from_filing(db: Session, rows: list[tuple[Entry, str, str]], name: str) -> str:
    """The proposal the notebook can make on its own: one branch per category,
    the notes filed under it.

    **Why this exists at all.** The plan asks the agent to propose the tree,
    and it does; but a 4B model asked for an outline answers with a paragraph
    often enough that a feature which only works when the model behaves is a
    feature most people meet broken. This is what the notebook already knows,
    it is never wrong (it is the user's own filing), and the proposal says
    which of the two produced it rather than passing this off as the model's
    work.
    """
    from tessellate.repo import categories as categories_repo

    by_category: dict[str, list[str]] = {}
    for entry, title, _ in rows:
        label = categories_repo.name_of(db, entry.category_id) or "Unfiled"
        by_category.setdefault(label, []).append(title)
    lines = [f"- {name}"]
    for label, titles in by_category.items():
        lines.append(f"  - {label}")
        lines.extend(f"    - {title}" for title in titles)
    return "\n".join(lines) + "\n"


def _outline_covering(outline: str, rows: list[tuple[Entry, str, str]]) -> str:
    """The model's outline with every note it forgot added back.

    A proposal for "map these thirty notes" that quietly contains eleven of
    them is the failure mode worth guarding: it looks like a map, it reads
    like an answer, and the nineteen that are missing are invisible unless you
    count. The strays go under one heading at the end rather than being
    scattered, so what the model did and what this added stay legible.
    """
    seen = {line.strip().lstrip("-*+ ").strip().casefold() for line in outline.splitlines()}
    missing = [title for _, title, _ in rows if title.casefold() not in seen]
    if not missing:
        return outline
    lines = [outline.rstrip("\n"), "  - Other notes"]
    lines.extend(f"    - {title}" for title in missing)
    return "\n".join(lines) + "\n"


@router.post("/boards/propose")
def propose_map(body: MapProposal, db: Session = Depends(get_session)) -> dict:
    """Propose a map of these notes, and write nothing.

    Preview before commit, the convention `generate_diagram` and the note
    extractor already follow in this app: the answer comes back as the outline
    text the user then edits, and `POST /boards/generate` creates the map from
    what they actually saw. A generator that wrote straight to a new board
    would make "undo" mean "find and delete the board it just made".
    """
    from tessellate.ai import librarian

    notes = _proposal_notes(db, body.note_ids)
    if not notes:
        raise HTTPException(
            status_code=404,
            detail="None of those notes can be mapped (deleted, private, or already a board).",
        )
    rows = _note_titles(db, notes)
    name = (body.name or f"Map of {len(rows)} notes").strip()[:100]

    outline = ""
    source = "notebook"
    #: Why the notebook wrote it, when it did. The dialog says this out loud,
    #: and the three cases want three different sentences: "your model is not
    #: running" is a thing the reader can go and fix, "the model answered with
    #: a paragraph" is a thing about the model they chose, and neither should
    #: be reported as the other. `sources`/`reason` rather than one string
    #: because the client also styles on `source`.
    reason = "offline"
    ollama = deps.get_ollama()
    if ollama.is_running():
        try:
            outline = librarian.propose_map_outline(
                [(title, body_text) for _, title, body_text in rows],
                deps.get_model_manager(),
                ollama,
            )
            reason = "unusable"
        except Exception:
            # A model that is running and still fails (a pulled-out model, a
            # timeout) is a reason to fall back, not to lose the action: the
            # notebook's own filing is a proposal too.
            logging.getLogger("tessellate.whiteboard").warning(
                "Map proposal failed, falling back to the notebook's own filing",
                exc_info=True,
            )
            outline = ""
            reason = "failed"
        # A reply with no bullets in it is prose, which is what a small model
        # answers with often enough to plan for; and one bullet is not a map.
        if len([line for line in outline.splitlines() if line.strip()[:1] in "-*+"]) >= 2:
            source = "model"
            reason = "model"
        else:
            outline = ""
    if not outline:
        outline = _outline_from_filing(db, rows, name)
    outline = _outline_covering(outline, rows)
    return {
        "name": name,
        "outline": outline,
        "source": source,
        "reason": reason,
        "note_ids": [entry.id for entry, _, _ in rows],
        "notes": len(rows),
    }


class MapGenerate(BaseModel):
    """The proposal as the user accepted it, possibly edited."""

    name: str = Field(min_length=1, max_length=100)
    outline: str = Field(min_length=1, max_length=MAX_IMPORT_CHARS)
    #: The notes the proposal was built from. A line whose text is one of
    #: their titles becomes a node that *is* that note; everything else is a
    #: topic. Sent back by the client rather than remembered server-side
    #: because nothing was written by the proposal, so there is no proposal to
    #: remember, which is the point of preview-before-commit.
    note_ids: list[int] = Field(default_factory=list, max_length=MAP_PROPOSAL_MAX_NOTES)


def _record_map_creation(
    db: Session,
    board_id: int,
    name: str,
    detail: str,
    extra: dict,
    created: list[WhiteboardObject],
) -> None:
    """The board event, then one event per node it was built with.

    Both map doors used to record a single `board`/`created` event whose
    payload held the outline and a node *count*, so `events.replay` rebuilt
    the board and nothing on it: a generated or imported map replayed empty
    (Brief 7, open item 4). The AI's own `generate_diagram` already records
    one event per item, which is the shape decision 4 asks for; these two
    predate it and now match.

    Written here rather than inside `_place_map_nodes` because of how
    `events.writes` nests: "the outermost write wins", so a decorated helper
    called from inside a decorated route opens no scope of its own and its
    event would be folded into the board's. Both routes therefore drop the
    decorator and record explicitly, in the order replay needs, the board
    first and its objects after.
    """
    events.record(
        db,
        "created",
        "board",
        board_id,
        detail,
        payload={
            "after": events.board_state(name, "map", DEFAULT_MAP_LAYOUT),
            "nodes": len(created),
            **extra,
        },
    )
    for obj in created:
        events.record(
            db,
            "created",
            "whiteboard_object",
            obj.id,
            f"{obj.kind} on board {board_id}",
            payload={"after": _object_state(obj)},
        )


#: How many topics or cards a name is asked for from, and how long the text handed over is.
BOARD_NAME_ITEMS = 40
BOARD_NAME_CHARS = 1500


@router.post("/boards/{board_id}/suggest-title")
def suggest_board_title(board_id: int, db: Session = Depends(get_session)) -> dict:
    """A name for this board or map, on request (L348), saving nothing: the
    client renames through the board's own undoable path. The model writes it
    when one runs; with none, the first words on the board are cut to a title
    (`composer_voice.title_for`, as for a note and a document)."""
    from tessellate.ai import composer_voice, librarian
    from tessellate.ai.ollama_client import OllamaError
    from tessellate.api.wb_board import _board_entry

    _board_entry(db, board_id)
    text = "\n".join(wb_repo.board_words(db, board_id, BOARD_NAME_ITEMS))[:BOARD_NAME_CHARS].strip()
    if not text:
        raise HTTPException(status_code=422, detail="There is nothing on this board to name it from yet.")
    if deps.get_ollama().is_running():
        try:
            title = librarian.generate_title(text, deps.get_model_manager(), deps.get_ollama())
        except OllamaError:
            logging.getLogger("tessellate.whiteboard").warning("board title generation failed", exc_info=True)
            title = ""
        if title:
            return {"title": title, "by": "model"}
    title = composer_voice.title_for(text)
    if not title:
        raise HTTPException(status_code=422, detail="There is no sentence here to take a name from yet.")
    return {"title": title, "by": "composer"}


_Box = tuple[float, float, float, float, str]


def _draft_objects(db: Session, board_id: int) -> tuple[list[_Box], list[_Box]]:
    """The frames and the text boxes of a board as `(x, y, width, height, text)`."""
    import json

    frames: list[_Box] = []
    items: list[_Box] = []
    for obj in wb_repo.board_objects(db, board_id):
        if obj.kind not in ("frame", "text"):
            continue
        try:
            data = json.loads(obj.data or "{}")
        except ValueError:
            continue
        text = str(data.get("content") or "").strip() if isinstance(data, dict) else ""
        if text:
            (frames if obj.kind == "frame" else items).append((obj.x, obj.y, obj.width, obj.height, text))
    return frames, items


def _draft_cards(db: Session, board_id: int) -> list[_Box]:
    """A board's note cards as `[[link]]` boxes; a private or deleted note is
    left out, as everywhere the model could read it."""
    from tessellate.entry import manager_text

    cards: list[_Box] = []
    for node, entry in wb_repo.board_cards(db, board_id):
        if entry is None or entry.is_deleted or entry.is_private:
            continue
        text = manager_text.readable_content(entry)
        title = (manager_text.extract_title(text) or text.strip().split("\n")[0]).strip()
        if title:
            cards.append((node.x, node.y, node.width or 250.0, node.height or 150.0, f"[[{title[:100]}]]"))
    return cards


def _draft_blocks(frames: list[_Box], items: list[_Box]) -> list[str]:
    """Markdown blocks: a heading per frame in reading order, under it what
    lies inside (the smallest frame holding an item's centre), then the rest."""
    frames = sorted(frames, key=lambda f: (round(f[1] / 40), f[0]))
    held: dict[int, list[tuple[float, float, str]]] = {i: [] for i in range(len(frames))}
    loose: list[tuple[float, float, str]] = []
    for x, y, w, h, text in items:
        cx, cy = x + w / 2, y + h / 2
        inside = [i for i, f in enumerate(frames) if f[0] <= cx <= f[0] + f[2] and f[1] <= cy <= f[1] + f[3]]
        target = min(inside, key=lambda i: frames[i][2] * frames[i][3]) if inside else None
        (held[target] if target is not None else loose).append((y, x, text))
    blocks: list[str] = []
    for i, frame in enumerate(frames):
        blocks.append(f"## {' '.join(frame[4].split())}")
        blocks.extend(text for _, _, text in sorted(held[i]))
    if loose and frames:
        blocks.append("## Outside the frames")
    blocks.extend(text for _, _, text in sorted(loose))
    return blocks


@router.post("/boards/{board_id}/draft")
def draft_board_document(board_id: int, db: Session = Depends(get_session)) -> dict:
    """A board's frames as a document draft, saving nothing (L-documents-4): a
    heading per frame, a paragraph per sticky, text box or note card in it, then
    whatever is outside every frame. The client makes the document, so one undo
    removes it."""
    from tessellate.api.wb_board import _board_entry
    from tessellate.entry import manager_text

    entry = _board_entry(db, board_id)
    frames, items = _draft_objects(db, board_id)
    items += _draft_cards(db, board_id)
    if not frames and not items:
        raise HTTPException(status_code=422, detail="There is nothing on this board to draft from yet.")
    title = (manager_text.extract_title(manager_text.readable_content(entry)) or "Board").strip()
    return {"title": title, "body": "\n\n".join(_draft_blocks(frames, items)), "frames": len(frames), "items": len(items)}


@router.post("/boards/generate", response_model=BoardOut, status_code=201)
def generate_map(body: MapGenerate, db: Session = Depends(get_session)) -> BoardOut:
    """Create the map the user accepted.

    The nodes that match one of their notes are `note` nodes carrying that
    note's id, which is the whole difference the plan names between this and
    a mindmapper's "AI generation": the map is made of the user's real notes,
    not of invented text that happens to look like them. Editing such a node
    edits the note, and deleting the map leaves the notes alone (section 5
    item 4).
    """
    _, parsed = _parse_markdown_outline(body.outline)
    if not parsed:
        raise HTTPException(
            status_code=422,
            detail="That outline has no nodes in it: each line starts with '- '.",
        )
    rows = _note_titles(db, _proposal_notes(db, body.note_ids))
    #: Matched on the casefolded title, because the one thing the user is most
    #: likely to change in the outline is capitalisation, and because a model
    #: told to copy a title exactly will still sometimes retitle its case.
    by_title = {title.casefold(): entry.id for entry, title, _ in rows}
    used: set[int] = set()

    def reference_for(text: str):
        note_id = by_title.get(text.strip().casefold())
        # Once each: an outline that repeats a title (a model's habit when it
        # cannot decide where a note belongs) would otherwise put the same
        # note on the board twice, and two nodes editing one note is a
        # confusion that only shows up later.
        if note_id is None or note_id in used:
            return None
        used.add(note_id)
        return ("note", note_id)

    name = body.name.strip()[:100] or "Generated map"
    entry = Entry(content=f"# {name}", is_board=True)
    _store_board_settings(entry, "map", DEFAULT_MAP_LAYOUT)
    db.add(entry)
    db.flush()
    created = _place_map_nodes(db, entry.id, parsed, reference_for)
    _record_map_creation(
        db,
        entry.id,
        name,
        f"generated map, {len(created)} nodes",
        {"outline": body.outline},
        created,
    )
    db.commit()
    db.refresh(entry)
    return BoardOut(
        id=entry.id,
        title=name,
        node_count=0,
        sketch_count=0,
        object_count=len(created),
        type="map",
        layout=DEFAULT_MAP_LAYOUT,
        **_preview_fields(db, entry.id),
    )


@router.post("/boards/import", response_model=BoardOut, status_code=201)
def import_board(body: MapImport, db: Session = Depends(get_session)) -> BoardOut:
    """Create a map from an OPML file or an indented Markdown outline.

    Every node comes in as a `topic`: an imported outline is text written
    somewhere else, and guessing that a line reading "Chapter three" means a
    particular note in *this* notebook is the kind of helpfulness that
    silently attaches the wrong thing. Linking a topic to a note afterwards
    is one action; finding out which of two hundred nodes was mis-linked is
    not.
    """
    parsers = {
        "opml": _parse_opml,
        "freemind": _parse_freemind,
        "markdown": _parse_markdown_outline,
        "xmind": _parse_xmind,
        #: A plain indented outline (§12.2 item 10) is what a paste is, so it
        #: is read the way a paste is read (decision 29), and a single top
        #: line names the map when the client sent no name.
        "text": lambda content: _parse_markdown_outline(_outline_from_paste(content)),
    }
    title, parsed = parsers[body.format](body.content)
    if body.format == "text" and len(parsed) == 1:
        title = parsed[0]["text"]
    name = (body.name or title or "Imported map").strip()[:100] or "Imported map"
    entry = Entry(content=f"# {name}", is_board=True)
    _store_board_settings(entry, "map", DEFAULT_MAP_LAYOUT)
    #: A numbered map's file comes back numbered (decision 17): OPML says so
    #: on its outlines, and Markdown when every topic starts with its place.
    if body.format == "markdown":
        numbered = _strip_outline_numbers(parsed)
    else:
        numbered = any(node.get("numbered") for node in _flatten_parsed(parsed))
    if numbered:
        _store_board_numbered(entry, True)
    db.add(entry)
    db.flush()  # the nodes need the board's id before they can point at it

    created = _place_map_nodes(db, entry.id, parsed)
    crossed = _restore_import_links(db, entry.id, parsed, created)
    _record_map_creation(
        db,
        entry.id,
        name,
        f"imported {body.format} map, {len(created)} nodes",
        {"format": body.format, "cross_links": crossed},
        created,
    )
    db.commit()
    db.refresh(entry)
    return BoardOut(
        id=entry.id,
        title=name,
        node_count=0,
        sketch_count=0,
        object_count=len(created),
        type="map",
        layout=DEFAULT_MAP_LAYOUT,
        **_preview_fields(db, entry.id),
    )
