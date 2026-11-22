"""The boards' own routes: list, images, create, duplicate, rename.

Moved whole from `routes_whiteboard.py` (audit AR3, gods-2): the code is unchanged, and
`routes_whiteboard` re-exports every name here that anything reads. Imports run one way,
down the layer list in `routes_whiteboard.py`'s docstring, never back to `routes_whiteboard`.
"""

from __future__ import annotations

import json

from tessellate.repo import whiteboard as whiteboard_repo
from tessellate.repo.content import BOARDS
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from tessellate.core.database import Entry, WhiteboardNode, WhiteboardObject, WhiteboardSketch
from sqlalchemy.orm import Session
from tessellate.entry.manager import update_entry
from tessellate.entry.manager_text import apply_title, extract_title
from datetime import datetime
from tessellate.core import deps, events
from sqlalchemy import func, select
from tessellate.core.deps import get_session
from tessellate.api import paging
from tessellate.api.wb_model import BOARD_TYPES, DEFAULT_BOARD_TYPE
from tessellate.api.wb_board import BoardBackground, BoardCreate, BoardLayer, BoardOut, BoardTypeMixin, MAX_BOARD_LAYERS, _board_background, _board_filter, _board_layers, _board_numbered, _board_settings, _board_theme, _is_link_sketch, _require_board, _store_board_background, _store_board_layers, _store_board_numbered, _store_board_settings, _store_board_theme
from tessellate.api.wb_preview import _preview_fields

router = APIRouter()


#: A page of boards, and a page of board images. Both lists grow with the
#: notebook rather than with anything the app controls, which is the rule
#: `tests/test_list_endpoints_page.py` enforces. 200 because it is the number
#: every other paged list here already uses, and because a board row carries a
#: preview (up to `PREVIEW_POINTS` points): at 200 that is a response of tens
#: of kilobytes instead of one that grows forever.
BOARDS_PAGE_SIZE = 200
BOARDS_PAGE_SIZE_MAX = 1000


def _board_stats(db: Session) -> tuple[dict, dict, dict, dict, dict[int | None, datetime]]:
    """Per-board counts of cards, sketches, objects and link sketches, and each board's last write."""
    node_counts = dict(
        db.execute(
            select(WhiteboardNode.board_id, func.count())
            .where(WhiteboardNode.board_id.is_not(None))
            .group_by(WhiteboardNode.board_id)
        ).all()
    )
    sketch_counts = dict(
        db.execute(
            select(WhiteboardSketch.board_id, func.count())
            .where(WhiteboardSketch.board_id.is_not(None))
            .group_by(WhiteboardSketch.board_id)
        ).all()
    )
    object_counts = dict(
        db.execute(
            select(WhiteboardObject.board_id, func.count())
            .where(WhiteboardObject.board_id.is_not(None))
            .group_by(WhiteboardObject.board_id)
        ).all()
    )
    link_counts = dict(
        db.execute(
            select(WhiteboardSketch.board_id, func.count())
            .where(WhiteboardSketch.board_id.is_not(None), _is_link_sketch())
            .group_by(WhiteboardSketch.board_id)
        ).all()
    )
    #: The last write to anything on each board, keyed like the counts
    #: above (None is the default board). One grouped query per table rather
    #: than one per board, for the same reason the counts are.
    touched: dict[int | None, datetime] = {}
    for table in (WhiteboardNode, WhiteboardSketch, WhiteboardObject):
        for board_id, last in db.execute(
            select(table.board_id, func.max(table.updated_at)).group_by(table.board_id)
        ).all():
            if last is not None and (board_id not in touched or last > touched[board_id]):
                touched[board_id] = last
    return node_counts, sketch_counts, object_counts, link_counts, touched


def _boards_for_page(
    db: Session, type: str | None, node_counts: dict, sketch_counts: dict, object_counts: dict
) -> tuple[list[Entry | None], dict[int, tuple[str, str]]]:
    """The boards the list covers (None is the default board) and each one's type and layout."""
    # The default scratch board has no note behind it, so it has nowhere to
    # store settings and is always an ordinary board, which is why it is
    # excluded by `?type=map` rather than being special-cased into it.
    # The page is decided before any preview is built: `None` stands for the
    # default board, and every other row is an `Entry` that passed the type
    # filter. Building `BoardOut`s first and slicing afterwards would pay for
    # a preview query per board in the notebook to answer a request for
    # twenty of them.
    page_rows: list[Entry | None] = [None] if type in (None, DEFAULT_BOARD_TYPE) else []
    # `is_board` entries are included even at zero counts, see its own
    # comment on the model and on `_require_board` above: a board that is
    # currently empty (just created, or cleared back to empty) is still a
    # board, and used to vanish from this list the moment its count hit
    # zero, which read as the board having deleted itself.
    board_ids = set(node_counts) | set(sketch_counts) | set(object_counts)
    board_ids |= set(
        db.scalars(
            select(Entry.id).where(Entry.is_board.is_(True), Entry.is_deleted.is_(False))
        ).all()
    )
    settings: dict[int, tuple[str, str]] = {}
    if board_ids:
        entries = db.scalars(
            select(Entry)
            .where(Entry.id.in_(board_ids), Entry.is_deleted.is_(False))
            .order_by(Entry.id)
        ).all()
        for entry in entries:
            board_type, layout = _board_settings(entry)
            # The type lives inside a JSON settings blob, so this filter is
            # Python either way (the docstring above says why); doing it here
            # rather than inside the page loop is what makes `total` the size
            # of the selection rather than of the table.
            if type is not None and board_type != type:
                continue
            settings[entry.id] = (board_type, layout)
            page_rows.append(entry)
    return page_rows, settings


@router.get("/boards", response_model=list[BoardOut])
def list_boards(
    response: Response,
    type: str | None = None,
    limit: int = Query(default=BOARDS_PAGE_SIZE, ge=1, le=BOARDS_PAGE_SIZE_MAX),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    db: Session = Depends(get_session),
) -> list[BoardOut]:
    """Boards actually in use, not, as the client used to build this list
    itself, every note in the notebook.

    Reported directly: "the different board options confuse me." The cause
    wasn't a bug so much as a design choice nobody had reckoned with yet, a
    board being *just a note* (this file's own opening comment) is right for
    the data model, but the picker took that literally and listed every
    single note as a "board", the vast majority of which had never been used
    as one. A notebook with 50 notes had a 50-item "Switch board" dropdown
    with no way to tell which one, if any, was actually a board someone had
    drawn on. This lists only notes with at least one card or sketch on them,
    plus the always-present default board.

    `?type=map` (or `board`) narrows it to one kind, the Library's Maps
    chip. Filtered in Python rather than in SQL because a board's type lives
    inside a JSON settings blob (`Entry.board_settings`), and because this
    function already materialises every board to build its preview: the list
    is tens of rows long, not thousands. An unknown value returns nothing
    rather than everything: a filter that silently ignores itself reads as
    "you have no maps" only after the user has read every row.

    **Paged.** `limit`, `offset` and an `X-Total-Count` counted over the same
    type filter as the page, so a caller that wants every board asks for the
    next page until it has them all (`apiPagedList` in the frontend). The
    default board is row one of page one and is counted like any other. The
    order is the default board, then entry id ascending, which is the order
    this list already came back in; the tiebreaker matters more here than
    elsewhere, because two boards created in the same second would otherwise
    be free to swap places between two pages and hide one of themselves.

    The page boundary is also where the cost is: `_preview_fields` is a query
    per board, and it now runs for the rows in the page rather than for every
    board in the notebook.
    """
    offset = paging.start(cursor, offset)
    if type is not None and type not in BOARD_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Pick one of these board types: " + ", ".join(sorted(BOARD_TYPES)) + ".",
        )
    node_counts, sketch_counts, object_counts, link_counts, touched = _board_stats(db)
    default_nodes = db.scalar(
        select(func.count()).select_from(WhiteboardNode).where(WhiteboardNode.board_id.is_(None))
    )
    default_sketches = db.scalar(
        select(func.count()).select_from(WhiteboardSketch).where(WhiteboardSketch.board_id.is_(None))
    )
    default_objects = db.scalar(
        select(func.count()).select_from(WhiteboardObject).where(WhiteboardObject.board_id.is_(None))
    )
    page_rows, settings = _boards_for_page(db, type, node_counts, sketch_counts, object_counts)
    response.headers["X-Total-Count"] = str(len(page_rows))
    paging.finish(response, offset, limit, len(page_rows))
    boards = []
    page = page_rows[offset:offset + limit]
    stamps = whiteboard_repo.preview_stamps(db, page)
    for entry in page:
        if entry is None:
            # The default scratch board has no note behind it, so it has
            # nowhere to store settings and is always an ordinary board, which
            # is why it is excluded by `?type=map` rather than special-cased
            # into it.
            boards.append(
                BoardOut(
                    id=None,
                    title="Default board",
                    node_count=default_nodes,
                    sketch_count=default_sketches,
                    link_count=db.scalar(
                        select(func.count()).select_from(WhiteboardSketch)
                        .where(WhiteboardSketch.board_id.is_(None), _is_link_sketch())
                    ) or 0,
                    object_count=default_objects,
                    updated_at=touched.get(None),
                    **_preview_fields(db, None, stamps[None]),
                )
            )
            continue
        board_type, layout = settings[entry.id]
        title = extract_title(entry.content) or entry.content.strip()[:40] or f"Note {entry.id}"
        boards.append(
            BoardOut(
                id=entry.id,
                title=title,
                node_count=node_counts.get(entry.id, 0),
                sketch_count=sketch_counts.get(entry.id, 0),
                link_count=link_counts.get(entry.id, 0),
                object_count=object_counts.get(entry.id, 0),
                updated_at=max(
                    (t for t in (entry.updated_at, touched.get(entry.id)) if t is not None),
                    default=None,
                ),
                type=board_type,
                layout=layout,
                background=_board_background(entry),
                layers=_board_layers(entry),
                **_preview_fields(db, entry.id, stamps[entry.id]),
            )
        )
    return boards


class BoardImageOut(BaseModel):
    id: int
    board_id: int | None
    board_title: str
    url: str


@router.get("/images", response_model=list[BoardImageOut])
def list_images(
    response: Response,
    limit: int = Query(default=BOARDS_PAGE_SIZE, ge=1, le=BOARDS_PAGE_SIZE_MAX),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    db: Session = Depends(get_session),
) -> list[BoardImageOut]:
    """A page of the image objects across every board, asked for directly
    ("what about uploaded images" in the Library). Whiteboard images already
    have a real row (`WhiteboardObject`, unlike an image pasted into a note's
    own markdown, which has none, see ROADMAP item 20a for that still-open
    gap), so this is a flat query, not new plumbing.

    **Superseded in the Library by `/media`**, which lists every uploaded
    file rather than only the ones that happen to be on a board, so nothing
    in `frontend/js/*.js` names this any more (INBOX 261, found by
    `scratchpad/probe_dead_routes.py`). Kept as the board-scoped view, which
    `/media` does not offer; this paragraph is here so the next scan does not
    re-open the question.

    **Paged**, with `X-Total-Count` over the same selection as the page and
    the row id as the order, which is also the tiebreaker two rows created in
    the same second need to stop them swapping places between pages.

    The one thing worth knowing about the shape below: the "does this row
    actually carry a url" test cannot be a SQL filter, because the url is a
    key inside a JSON blob. So the ids and blobs are read first and filtered
    in Python, and the page is taken from *that* list. Counting every image
    row instead and skipping the empty ones per page would make
    `X-Total-Count` bigger than the number of rows a caller can ever collect,
    and `apiPagedList` walks until it has that many: it would never stop.
    """
    offset = paging.start(cursor, offset)
    rows = db.execute(
        select(WhiteboardObject.id, WhiteboardObject.board_id, WhiteboardObject.data)
        .where(WhiteboardObject.kind == "image")
        .order_by(WhiteboardObject.id)
    ).all()
    usable = []
    for obj_id, board_id, data in rows:
        try:
            url = json.loads(data).get("url")
        except (TypeError, ValueError):
            url = None
        if url:
            usable.append((obj_id, board_id, url))
    response.headers["X-Total-Count"] = str(len(usable))
    paging.finish(response, offset, limit, len(usable))
    page = usable[offset:offset + limit]
    if not page:
        return []
    board_ids = {board_id for _, board_id, _ in page if board_id is not None}
    titles: dict[int | None, str] = {None: "Default board"}
    if board_ids:
        for entry in db.scalars(select(Entry).where(Entry.id.in_(board_ids), Entry.is_deleted.is_(False))):
            titles[entry.id] = extract_title(entry.content) or entry.content.strip()[:40] or f"Note {entry.id}"
    return [
        BoardImageOut(
            id=obj_id,
            board_id=board_id,
            board_title=titles.get(board_id, f"Note {board_id}"),
            url=url,
        )
        for obj_id, board_id, url in page
    ]


@router.post("/boards", response_model=BoardOut, status_code=201)
@events.writes("board", "created")
def create_board(body: BoardCreate, db: Session = Depends(get_session)) -> BoardOut:
    """A fresh, empty board, a plain note whose whole job is to be one.

    Named directly (`# {name}` as its first line, the same heading convention
    every note's own title already reads), rather than the previous only way
    in: create an ordinary note somewhere else first, then find it again in a
    dropdown that listed the entire notebook.
    """
    name = body.name.strip()
    entry = Entry(content=f"# {name}", is_board=True)
    # Written before the first commit rather than in a second UPDATE after
    # it: a map created as a board and turned into one a moment later is a
    # window in which the Library, the board list and any other reader see it
    # as an ordinary whiteboard.
    board_type, layout = _store_board_settings(entry, body.type, body.layout)
    db.add(entry)
    db.flush()  # so the event can name the board's id
    # This route builds the note itself rather than going through
    # `manager.create_entry`, so without this line a board was the one thing
    # in the app that could appear with nothing anywhere saying it had.
    events.record(
        db,
        "created",
        "board",
        entry.id,
        name[:80],
        payload={"after": {"title": name, "type": board_type, "layout": layout}},
    )
    db.commit()
    db.refresh(entry)
    return BoardOut(
        id=entry.id,
        title=name,
        node_count=0,
        sketch_count=0,
        type=board_type,
        layout=layout,
    )


@router.post("/boards/{board_id}/duplicate", response_model=BoardOut, status_code=201)
@events.writes("board", "created")
def duplicate_board(board_id: int, db: Session = Depends(get_session)) -> BoardOut:
    """Copy a board: every card, sketch and object, at the same positions.

    ROADMAP.md item 8 ("managing concept maps"): creating a map works and so
    do listing and renaming, but duplicating did not exist on either side.
    It is the one that makes a map reusable, a map you have laid out is a
    template for the next one, and without this the only way to reuse a shape
    is to rebuild it card by card.

    **A card is a real note**, which is the app's own premise and the reason this is not a shallow row copy: the
    duplicate gets *new* notes with the same text, so editing a card on the
    copy cannot rewrite the original's. The alternative: pointing both boards
    at one set of notes, looks identical the moment it is made and diverges
    into data loss the first time someone edits the copy.

    Sketches and objects carry no separate identity, so those rows are copied
    as they are.
    """
    # `_require_board` validates and returns nothing, so the Entry is fetched
    # separately: the title has to come from the board note's own heading,
    # which is where a board's title lives (see `rename_board`).
    _require_board(db, board_id)
    source = deps.get_or_404(db, Entry, board_id, "That board could not be found.")
    title = extract_title(source.content) or "Untitled board"
    copy = Entry(content=f"# {title} (copy)", is_board=True)
    # A copy of a map is a map. Copying the settings blob wholesale (rather
    # than reading the two fields and writing them back) is what keeps that
    # true for every board-level setting added after this line was written.
    copy.board_settings = source.board_settings
    db.add(copy)
    db.flush()  # the new board needs its id before anything can point at it

    nodes = db.scalars(
        select(WhiteboardNode).where(_board_filter(WhiteboardNode, board_id))
    ).all()
    for node in nodes:
        original = db.get(Entry, node.entry_id)
        if original is None:
            continue  # a stale row: skip rather than copy a dangling card
        card = Entry(content=original.content, is_private=original.is_private)
        db.add(card)
        db.flush()
        db.add(
            WhiteboardNode(
                board_id=copy.id,
                entry_id=card.id,
                x=node.x,
                y=node.y,
                z=node.z,
                width=node.width,
                height=node.height,
                comments=node.comments,
            )
        )

    for sketch in db.scalars(
        select(WhiteboardSketch).where(_board_filter(WhiteboardSketch, board_id))
    ).all():
        #: With its z: a stroke stacks with the cards (WHITEBOARD_PLAN
        #: decision 43), so a copy at z 0 could go under a card it was over.
        db.add(WhiteboardSketch(board_id=copy.id, data=sketch.data, x=sketch.x, y=sketch.y, z=sketch.z))

    # **The copy's tree has to point at the copy.** A row-by-row copy carries
    # `parent_id` verbatim, which would leave every node in the duplicate
    # parented to the *original's* rows: a map that looks right in the object
    # list and renders as a flat pile of roots, because the tree walk on this
    # board finds no parent of its own on it. So: copy first, then re-wire by
    # the old id → new id map, which needs the new ids and therefore a flush.
    copied_by_source: dict[int, WhiteboardObject] = {}
    sources = db.scalars(
        select(WhiteboardObject).where(_board_filter(WhiteboardObject, board_id))
    ).all()
    for obj in sources:
        clone = WhiteboardObject(
            board_id=copy.id,
            kind=obj.kind,
            data=obj.data,
            x=obj.x,
            y=obj.y,
            z=obj.z,
            width=obj.width,
            height=obj.height,
        )
        db.add(clone)
        copied_by_source[obj.id] = clone
    db.flush()
    for obj in sources:
        if obj.parent_id is not None and obj.parent_id in copied_by_source:
            copied_by_source[obj.id].parent_id = copied_by_source[obj.parent_id].id

    # One event, not one per copied row: a duplicate is one action, and the
    # copy's own items each replay from the state recorded here.
    events.record(
        db,
        "created",
        "board",
        copy.id,
        f"copy of board {board_id}",
        payload={
            "after": {"title": f"{title} (copy)", "copied_from": board_id},
            "cards": len(nodes),
            "objects": len(sources),
        },
    )
    db.commit()
    db.refresh(copy)
    board_type, layout = _board_settings(copy)
    return BoardOut(
        id=copy.id,
        title=f"{title} (copy)",
        node_count=len(nodes),
        sketch_count=0,
        object_count=len(sources),
        type=board_type,
        layout=layout,
        **_preview_fields(db, copy.id),
    )


class BoardRename(BoardTypeMixin):
    #: A patch on the map's theme (MINDMAP_PLAN.md §13e). Only the fields
    #: sent are touched, and a field sent as `null` is a field the map stops
    #: theming: see `_store_board_theme`. Unknown fields and values outside
    #: their set are dropped by `_clean_theme` rather than refused, because
    #: this is a look, and a picker one version ahead should leave a map
    #: plainer rather than unsaveable.
    theme: dict | None = None
    #: Number the map's branches by their place in the outline, 1, 1.1, 1.2
    #: (MINDMAP_PLAN.md decision 17). `None` leaves it as it is.
    numbered: bool | None = None
    #: A patch on the board's look (decision 24). `None` leaves it as it is.
    background: BoardBackground | None = None
    #: The whole list of named layers (canvasdepth). `None` leaves them.
    layers: list[BoardLayer] | None = Field(default=None, max_length=MAX_BOARD_LAYERS)
    #: Optional since maps: `PUT` used to be rename-only and required a
    #: title, so a client changing the *layout* had to resend the name it was
    #: not touching: which is how a rename made in another tab gets silently
    #: overwritten by a stale one. `None` means "leave the title alone".
    title: str | None = Field(default=None, min_length=1, max_length=100)


def _apply_board_look(db: Session, entry: Entry, body: BoardRename) -> None:
    """The board's background and named layers, each recorded as its own
    edit when it changed (split from `rename_board` to keep it readable)."""
    if body.background is not None:
        before_background = _board_background(entry)
        stored_background = _store_board_background(entry, body.background)
        if stored_background != before_background:
            events.record(
                db,
                "edited",
                "board",
                entry.id,
                "background",
                payload={"after": stored_background, "before": before_background},
            )
    if body.layers is not None:
        before_layers = _board_layers(entry)
        stored_layers = _store_board_layers(entry, body.layers)
        if stored_layers != before_layers:
            events.record(db, "edited", "board", entry.id, f"layers, {len(stored_layers)}",
                          payload={"after": {"layers": stored_layers}, "before": {"layers": before_layers}})


@router.put("/boards/{board_id}", response_model=BoardOut)
def rename_board(board_id: int, body: BoardRename, db: Session = Depends(get_session)) -> BoardOut:
    """A board's title is its underlying note's own first `#` heading line
    (`list_boards`'s own `extract_title` read, above): so renaming a board
    is the same `apply_title` edit any other note's title goes through, not
    a second stored field. The default scratch board (`board_id=None`) has
    no underlying note to rename; `board_id=0` and negative ids can't
    resolve to a real note either, so both 404 the same way a stale or
    guessed id does.

    Also where a board becomes a map and back (`type`), and where a map's
    `layout` is chosen. Every field is optional and only what was sent is
    applied: the same shape `PATCH` would have, kept as `PUT` because the
    route, the client call and this function's name already existed.
    """
    entry = BOARDS.writable(db, board_id)
    entry.is_board = True
    if body.type is not None or body.layout is not None:
        before = dict(zip(("type", "layout"), _board_settings(entry)))
        stored = _store_board_settings(entry, body.type, body.layout)
        # **Deliberately not wrapped in `@events.writes`.** A title change
        # here goes through `manager.update_entry`, which records the note's
        # own `edited` event; a write scope on this route would fold that
        # into the board's event and take the edit out of the note's history,
        # which is where a person looks for it and where its replay needs it.
        # So the board's settings, which the manager knows nothing about, get
        # their own event beside the note's rather than instead of it.
        events.record(
            db,
            "edited",
            "board",
            entry.id,
            f"{stored[0]}, {stored[1]}",
            payload={"after": dict(zip(("type", "layout"), stored)), "before": before},
        )
    if body.theme is not None:
        before_theme = _board_theme(entry)
        stored_theme = _store_board_theme(entry, body.theme)
        if stored_theme != before_theme:
            events.record(
                db,
                "edited",
                "board",
                entry.id,
                f"map theme, {len(stored_theme)} field" + ("" if len(stored_theme) == 1 else "s"),
                payload={"after": stored_theme, "before": before_theme},
            )
    if body.numbered is not None:
        before_numbered = _board_numbered(entry)
        _store_board_numbered(entry, body.numbered)
        if body.numbered != before_numbered:
            events.record(
                db,
                "edited",
                "board",
                entry.id,
                "branches numbered" if body.numbered else "branches not numbered",
                payload={"after": {"numbered": body.numbered}, "before": {"numbered": before_numbered}},
            )
    _apply_board_look(db, entry, body)
    if body.title is not None:
        title = body.title.strip()
        update_entry(db, entry, content=apply_title(entry.content, title))
    else:
        # `update_entry` commits for us; without a title change nothing else
        # would, and the settings above would be lost on session close.
        db.commit()
        title = extract_title(entry.content) or entry.content.strip()[:40] or f"Note {entry.id}"
    board_type, layout = _board_settings(entry)
    node_count = db.scalar(
        select(func.count()).select_from(WhiteboardNode).where(WhiteboardNode.board_id == board_id)
    )
    sketch_count = db.scalar(
        select(func.count()).select_from(WhiteboardSketch).where(WhiteboardSketch.board_id == board_id)
    )
    object_count = db.scalar(
        select(func.count()).select_from(WhiteboardObject).where(WhiteboardObject.board_id == board_id)
    )
    return BoardOut(
        id=board_id,
        title=title,
        node_count=node_count,
        sketch_count=sketch_count,
        link_count=db.scalar(
            select(func.count()).select_from(WhiteboardSketch)
            .where(WhiteboardSketch.board_id == board_id, _is_link_sketch())
        ) or 0,
        object_count=object_count,
        type=board_type,
        layout=layout,
        background=_board_background(entry),
        layers=_board_layers(entry),
        **_preview_fields(db, board_id),
    )


#: The kinds of board object whose `content` is words a name can come from:
#: a map's topics, a frame's title, a text box, a sticky.
_NAMED_KINDS = ("topic", "frame", "text", "sticky")


def _board_words(db: Session, board_id: int) -> str:
    """What is written on a board, a map's centre topic first: the text a name
    is taken from. Pinned cards add their notes' titles; a private note's
    never (its words, title included, stay out of a name the model sees)."""
    rows = whiteboard_repo.objects_of_kinds(db, board_id, _NAMED_KINDS)
    rows = sorted(rows, key=lambda o: (o.parent_id is not None, o.kind != "topic", o.kind != "frame", o.z or 0, o.id))
    lines = []
    for obj in rows:
        try:
            content = (json.loads(obj.data or "{}") or {}).get("content")
        except ValueError:
            continue
        if isinstance(content, str) and content.strip():
            lines.append(content.strip())
    for entry in whiteboard_repo.entries(db, [node.entry_id for node in whiteboard_repo.board_nodes(db, board_id)]):
        if entry.is_private:
            continue
        title = extract_title(entry.content or "")
        if title:
            lines.append(title)
    return "\n".join(lines)


#: How long a board name waits for the model before the board's own words are cut instead.
_TITLE_SECONDS = 20.0


@router.post("/boards/{board_id}/suggest-title")
def suggest_board_title(board_id: int, db: Session = Depends(get_session)) -> dict:
    """A name for this board or map, on request (L280), as a document's is
    (`routes_documents.suggest_document_title`): the model writes it when one
    runs, else the board's own words are cut to a title. Nothing is saved:
    the client renames through the same undoable path as Rename."""
    from tessellate.ai import composer_voice, librarian
    from tessellate.ai.ollama_client import OllamaError

    BOARDS.writable(db, board_id)
    text = _board_words(db, board_id)
    if not text:
        raise HTTPException(status_code=422, detail="There is nothing on this board to name it from yet.")
    if deps.get_ollama().is_running():
        from tessellate.core import jobs

        flight = jobs.future("board title", librarian.generate_title, text[:4000], deps.get_model_manager(), deps.get_ollama())
        try:
            title = flight.result(timeout=_TITLE_SECONDS)
        except (OllamaError, TimeoutError):
            title = ""
        if title:
            return {"title": title, "by": "model"}
    title = composer_voice.title_for(text)
    if not title:
        raise HTTPException(status_code=422, detail="There is no sentence here to take a name from yet.")
    return {"title": title, "by": "composer"}
