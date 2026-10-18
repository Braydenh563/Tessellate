"""A mind map built from the graph's own structure (INBOX 607).

The owner, 2026-10-05: "I made a mind map from the graph but the notification
included no link to it", and "this is how it made the map, surely there's a
better and more dynamic way it can build the map based off the connections and
links and relevancy etc??". The graph's selection dock made one topic named
after the map and put every selected note under it, so 33 notes were one root
with 33 children in a single column, and the links the person had drawn, the
whole reason the notes were on a graph, were thrown away.

`POST /whiteboard/maps/from-notes` takes the notes and the links between them
as the graph shows them, and builds the tree the links describe:

- **The root** is the note the person picked, or the most connected note; with
  no links at all it is a topic named after the map.
- **Linked notes hang under the note they link to**: a breadth-first spanning
  tree from the root, the better-connected neighbour first, so a hub keeps its
  spokes and a chain stays a chain.
- **What the links do not reach** (other clusters, loose notes) is grouped by
  category, a branch per category, each cluster's own tree under it.
- **No node keeps more than `MAX_FANOUT` children** when the notes say how to
  split them: by category, then by a tag they share, then alphabetically,
  which is the one grouping every set of titles has.
- **Every link the tree could not hold is a cross-link**, drawn the way an
  imported map's are, so nothing the graph showed is lost.

Laid out on both sides of the root, branches given to whichever side is
lighter by weight (the client's own tree-both rule, `wbMapTidyPositions`), so
the map opens readable even before the client's tidy refines it on Open.
"""

from __future__ import annotations

import json
import re
from collections import Counter, deque

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core.database import Category, Entry
from tessellate.core.deps import get_session
from tessellate.entry.properties import strip as strip_properties

router = APIRouter(prefix="/whiteboard", tags=["whiteboard"])

#: The most children a node keeps before its notes are grouped. Seven or
#: eight is where a column of siblings stops reading as a set and starts
#: reading as a list (Miller's number is the folk version; Coggle's own
#: templates rarely pass eight).
MAX_FANOUT = 8
#: Bounds on one request: the graph's selection is a lasso, and a lasso over a
#: dense graph can catch hundreds of notes and thousands of lines.
MAX_NOTES = 300
MAX_EDGES = 3000
#: Cross-links past this many are dropped: a map drawn over by a hundred
#: lines is a graph again, which is the view the person just left.
MAX_CROSS_LINKS = 60
#: The layout's grid, in board units: a column per depth (a topic is 200
#: wide, so 300 leaves the branch its run) and a row per leaf (56 tall).
LAYOUT_COL = 300.0
LAYOUT_ROW = 84.0
UNCATEGORISED = "Uncategorised"


def _key_category(info: dict, note_id: int) -> str:
    return (info[note_id].get("category") or "").strip() or UNCATEGORISED


def build_tree(
    notes: list[dict], edges: list[tuple[int, int]], root_id: int | None = None, name: str = "Map"
) -> dict:
    """The map as a nested outline: `{"note", "text", "ref", "children",
    "links"}` per node, `note` None for a topic. `notes` are
    `{"id", "title", "category", "tags"}` in the order the person chose them;
    `edges` are pairs of note ids, either direction."""
    info = {n["id"]: n for n in notes}
    order = {n["id"]: i for i, n in enumerate(notes)}
    adj: dict[int, set[int]] = {i: set() for i in info}
    for a, b in edges:
        if a != b and a in info and b in info:
            adj[a].add(b)
            adj[b].add(a)

    def rank(i: int) -> tuple[int, int]:
        return (-len(adj[i]), order[i])

    refs = iter(range(1, 10**9))

    def topic(text: str) -> dict:
        return {"note": None, "text": text[:100], "ref": f"t{next(refs)}", "children": [], "links": []}

    def note(i: int) -> dict:
        title = (info[i].get("title") or "").strip() or "Untitled"
        return {"note": i, "text": title[:100], "ref": f"n{i}", "children": [], "links": []}

    placed: dict[int, dict] = {}
    tree_edges: set[frozenset] = set()

    def span(center: int) -> dict:
        """The breadth-first tree of `center`'s cluster, hubs first."""
        head = placed[center] = note(center)
        queue = deque([center])
        while queue:
            current = queue.popleft()
            for nxt in sorted(adj[current], key=rank):
                if nxt in placed:
                    continue
                placed[nxt] = note(nxt)
                placed[current]["children"].append(placed[nxt])
                tree_edges.add(frozenset((current, nxt)))
                queue.append(nxt)
        return head

    linked = any(adj.values())
    if root_id in info:
        root_note = root_id
    elif linked:
        root_note = min(info, key=rank)
    else:
        root_note = None
    root = span(root_note) if root_note is not None else topic(name or "Map")

    #: The clusters the root's links do not reach, each as its own tree,
    #: grouped by the category of its centre.
    groups: dict[str, list[dict]] = {}
    for i in sorted(info, key=rank):
        if i in placed:
            continue
        cluster = span(i)
        groups.setdefault(_key_category(info, i), []).append(cluster)
    if len(groups) == 1 and (root_note is None or len(next(iter(groups.values()))) <= 3):
        root["children"].extend(next(iter(groups.values())))
    else:
        for category, trees in groups.items():
            if len(trees) == 1:
                root["children"].append(trees[0])
            else:
                branch = topic(category)
                branch["children"].extend(trees)
                root["children"].append(branch)

    def grouping(kids: list[dict]) -> dict[str, list[dict]] | None:
        """How to split an overfull set of note children, or None."""
        notes_only = [k for k in kids if k["note"] is not None]
        by_category: dict[str, list[dict]] = {}
        for kid in notes_only:
            by_category.setdefault(_key_category(info, kid["note"]), []).append(kid)
        if sum(1 for g in by_category.values() if len(g) > 1) >= 2:
            return by_category
        #: A tag the children share, but not all of them: the most common one
        #: each child carries.
        counts = Counter(t for k in notes_only for t in set(info[k["note"]].get("tags") or []))
        useful = {t for t, c in counts.items() if 1 < c < len(notes_only)}
        if useful:
            by_tag: dict[str, list[dict]] = {}
            for kid in notes_only:
                tags = [t for t in info[kid["note"]].get("tags") or [] if t in useful]
                key = max(tags, key=lambda t: (counts[t], t)) if tags else ""
                by_tag.setdefault(key, []).append(kid)
            if sum(1 for k, g in by_tag.items() if k and len(g) > 1) >= 2:
                return {(f"#{k}" if k else "Other"): g for k, g in by_tag.items()}
        if len(notes_only) <= 2 * MAX_FANOUT:
            return None
        #: The last resort every set of titles has: alphabetical runs.
        ordered = sorted(notes_only, key=lambda k: k["text"].casefold())
        size = -(-len(ordered) // -(-len(ordered) // MAX_FANOUT))
        runs: dict[str, list[dict]] = {}
        for start in range(0, len(ordered), size):
            run = ordered[start : start + size]
            first, last = run[0]["text"][:1].upper(), run[-1]["text"][:1].upper()
            label = first if first == last else f"{first} to {last}"
            while label in runs:
                label += " "
            runs[label] = run
        return runs

    def split(node: dict) -> None:
        kids = node["children"]
        if len(kids) > MAX_FANOUT:
            groups_here = grouping(kids)
            if groups_here:
                grouped = {id(k) for g in groups_here.values() if len(g) > 1 for k in g}
                rebuilt = [k for k in kids if id(k) not in grouped]
                for label, members in groups_here.items():
                    if len(members) > 1:
                        branch = topic(label.strip())
                        branch["children"] = members
                        rebuilt.append(branch)
                node["children"] = rebuilt
        for child in node["children"]:
            split(child)

    split(root)

    crossed = 0
    for a, b in sorted({frozenset(e) for e in edges if e[0] != e[1]}, key=sorted):
        pair = frozenset((a, b))
        if pair in tree_edges or a not in placed or b not in placed:
            continue
        if crossed >= MAX_CROSS_LINKS:
            break
        lo, hi = sorted(pair)
        placed[lo]["links"].append(placed[hi]["ref"])
        crossed += 1
    return root


def _weight(node: dict) -> int:
    return 1 + sum(_weight(child) for child in node["children"])


def layout_both_sides(tree: dict) -> dict[str, tuple[float, float]]:
    """Top-left board positions per `ref`, the root at 0,0, its branches on
    both sides, each side a tidy column of leaves centred on the root."""
    right: list[dict] = []
    left: list[dict] = []
    weights = [0, 0]
    for kid in tree["children"]:
        side = 0 if weights[0] <= weights[1] else 1
        (right if side == 0 else left).append(kid)
        weights[side] += _weight(kid)
    positions: dict[str, tuple[float, float]] = {tree["ref"]: (0.0, 0.0)}
    for kids, sign in ((right, 1.0), (left, -1.0)):
        slots: dict[str, tuple[int, float]] = {}
        leaf = [0]

        def assign(node: dict, depth: int) -> float:
            if node["children"]:
                value = sum(assign(c, depth + 1) for c in node["children"]) / len(node["children"])
            else:
                value = float(leaf[0])
                leaf[0] += 1
            slots[node["ref"]] = (depth, value)
            return value

        for kid in kids:
            assign(kid, 1)
        middle = (leaf[0] - 1) / 2 if leaf[0] else 0
        for ref, (depth, value) in slots.items():
            positions[ref] = (sign * depth * LAYOUT_COL, (value - middle) * LAYOUT_ROW)
    return positions


class MapFromNotes(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    note_ids: list[int] = Field(min_length=1, max_length=MAX_NOTES)
    #: The links between them, as the graph draws them (explicit links and
    #: whatever else the graph's lens shows). Pairs whose ends are not both
    #: in `note_ids` are ignored rather than refused.
    edges: list[list[int]] = Field(default_factory=list, max_length=MAX_EDGES)
    #: The note to put in the middle, when the person picked one.
    root_id: int | None = None


@router.post("/maps/from-notes", status_code=201)
def map_from_notes(body: MapFromNotes, db: Session = Depends(get_session)):
    from tessellate.api import routes_whiteboard as wb
    from tessellate.entry import manager

    wanted = list(dict.fromkeys(body.note_ids))
    found = {
        entry.id: entry
        for entry in db.scalars(select(Entry).where(Entry.id.in_(wanted))).all()
        if not entry.is_deleted and not entry.is_board
    }
    category_ids = {e.category_id for e in found.values() if e.category_id}
    category_names = dict(db.execute(select(Category.id, Category.name).where(Category.id.in_(category_ids))).all()) if category_ids else {}
    rows = []
    for note_id in wanted:
        entry = found.get(note_id)
        if entry is None:
            continue
        #: A private note is on the map by reference only: its title is not
        #: copied into the map's own text, the node shows it as the app shows
        #: any private note, from the note.
        title = "Private note" if entry.is_private else manager.extract_title(manager.readable_content(entry)) or ""
        try:
            tags = json.loads(entry.tags or "[]")
        except (TypeError, ValueError):
            tags = []
        rows.append({"id": entry.id, "title": title, "category": category_names.get(entry.category_id, ""), "tags": tags if isinstance(tags, list) else []})
    if not rows:
        raise HTTPException(status_code=422, detail="None of those notes can go on a map.")
    edges = [(int(e[0]), int(e[1])) for e in body.edges if len(e) == 2]
    name = body.name.strip()[:100] or "Mind map"
    tree = build_tree(rows, edges, root_id=body.root_id, name=name)
    positions = layout_both_sides(tree)

    entry = Entry(content=f"# {name}", is_board=True)
    wb._store_board_settings(entry, "map", "tree-both")
    db.add(entry)
    db.flush()
    created = wb._place_map_nodes(db, entry.id, [tree])
    flat: list[dict] = []
    stack = [tree]
    while stack:
        node = stack.pop()
        flat.append(node)
        stack.extend(reversed(node["children"]))
    for node, obj in zip(flat, created):
        obj.x, obj.y = positions.get(node["ref"], (obj.x, obj.y))
    crossed = wb._restore_import_links(db, entry.id, [tree], created)
    wb._record_map_creation(
        db,
        entry.id,
        name,
        f"map from {len(rows)} notes, {len(created)} nodes",
        {"notes": len(rows), "cross_links": crossed},
        created,
    )
    db.commit()
    db.refresh(entry)
    return wb.BoardOut(
        id=entry.id,
        title=name,
        node_count=0,
        sketch_count=0,
        object_count=len(created),
        type="map",
        layout="tree-both",
        **wb._preview_fields(db, entry.id),
    )


#: The most topics one `map_from_note` places: a map is meant to fit a screen,
#: and a note longer than this is read by its headings, not every line.
MAX_NOTE_MAP_NODES = 60

#: One quantifier each, and the rest trimmed in Python: nothing here can
#: backtrack over a long line of spaces.
_NOTE_LIST = re.compile(r"^(\s*)(?:[-*+]|\d{1,9}[.)])\s(.*)$")
_NOTE_HEADING = re.compile(r"^(#{1,6})\s(.*)$")
_NOTE_TICK = re.compile(r"^\[[ xX]\]\s")
#: A link's words keep no bracket and its target no bracket or parenthesis, so
#: each match attempt stops at the next "[" (CodeQL: "[" or "[](" repeated was
#: quadratic with `[^\]]*` and `[^)]*`).
_NOTE_LINK = re.compile(r"!?\[([^\[\]]*)\]\([^()\[\]]*\)")


def _clip(text: str, length: int) -> str:
    return text if len(text) <= length else text[: length - 1] + "…"


def _topic_text(text: str) -> str:
    """A line of Markdown as a topic's words: no emphasis, code, link or
    task marks, nor a heading's closing hashes."""
    text = _NOTE_TICK.sub("", text.strip()).rstrip("#").strip()
    text = _NOTE_LINK.sub(r"\1", text)
    text = re.sub(r"[*_`~]+", "", text).strip()
    return _clip(text, 120)


def _paragraph_topics(paragraphs: list[str], title: str) -> list[dict]:
    """A note with no headings or list items: one topic per paragraph, from its first sentence."""
    topics = []
    for para in paragraphs[:MAX_NOTE_MAP_NODES]:
        first = _topic_text(re.split(r"(?<=[.!?])\s", para, maxsplit=1)[0])
        if first and first != title:
            topics.append({"text": first, "children": []})
    return topics


def _outline_line(raw: str):
    """A note line as `(kind, level, text)`: "heading" or "item" with its level and words,
    or ("text", 0, line) for anything else."""
    heading = _NOTE_HEADING.match(raw.strip())
    item = None if heading else _NOTE_LIST.match(raw)
    if heading:
        return "heading", len(heading.group(1)), _topic_text(heading.group(2))
    if item:
        return "item", 10 + len(item.group(1).expandtabs(4)), _topic_text(item.group(2))
    return "text", 0, raw.strip()


def _hang_topic(stack: list, roots: list, level: int, text: str) -> None:
    """Add a topic under the nearest shallower one on the path, or as a root."""
    node = {"text": text, "children": []}
    while stack and stack[-1][0] >= level:
        stack.pop()
    (stack[-1][1]["children"] if stack else roots).append(node)
    stack.append((level, node))


def _outline_lines(lines: list[str]):
    """The classified lines of a note, code fences and blank lines left out."""
    fenced = False
    for raw in lines:
        if raw.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and raw.strip():
            yield _outline_line(raw)


def note_outline(content: str) -> tuple[str, list[dict]]:
    """A note as a map's outline: (title, the topics under it). Headings are
    branches by level, list items hang under the heading above them by
    indent; a note with neither gives one topic per paragraph."""
    title, roots, count = "", [], 0
    #: (level, node): headings down the current path; list items sit below
    #: the deepest heading at 10 + indent so they never outrank one.
    stack: list[tuple[int, dict]] = []
    paragraphs: list[str] = []
    for kind, level, text in _outline_lines(strip_properties(content or "").splitlines()):
        if kind == "heading" and not title and not roots:
            title = text
        elif kind == "text":
            paragraphs.append(text)
        elif count >= MAX_NOTE_MAP_NODES:
            break
        elif text:
            _hang_topic(stack, roots, level, text)
            count += 1
    if not roots:
        roots.extend(_paragraph_topics(paragraphs, title))
    if not title:
        title = _topic_text(paragraphs[0]) if paragraphs else ""
        roots = [r for r in roots if r["text"] != title]
    return title, roots


def map_from_note_entry(db: Session, entry: Entry, name: str = "") -> tuple[Entry, int]:
    """One note as a mind map (OPEN row 566): its title the centre, a topic
    that opens the note, its headings and lists the branches. Shared by the
    note menu's Make a mind map and the agent's `map_from_note`. Raises
    ValueError when the note has nothing to map."""
    from tessellate.api import routes_whiteboard as wb

    title, branches = note_outline(entry.content or "")
    if not branches:
        raise ValueError(f"Note #{entry.id} has no headings, list or paragraphs to make a map from.")
    name = _clip(name.strip() or title or f"Note {entry.id}", 100)
    board = Entry(content=f"# {name}", is_board=True)
    wb._store_board_settings(board, "map", "tree-right")
    db.add(board)
    db.flush()
    created = wb._place_map_nodes(db, board.id, [{"text": title or name, "note": entry.id, "children": branches}])
    wb._record_map_creation(db, board.id, name, f"map from note #{entry.id}, {len(created)} nodes", {"note_id": entry.id}, created)
    db.commit()
    db.refresh(board)
    return board, len(created)


@router.post("/maps/from-note/{note_id}", status_code=201)
def map_from_note(note_id: int, db: Session = Depends(get_session)):
    """The note menu's Make a mind map."""
    from tessellate.api import routes_whiteboard as wb

    entry = db.get(Entry, note_id)
    if entry is None or entry.is_deleted or entry.is_board:
        raise HTTPException(status_code=404, detail="No note with that id.")
    if entry.is_private:
        #: A map's topics are plain text on a board anyone with the notebook
        #: reads; a private note's words stay in the note.
        raise HTTPException(status_code=422, detail="A private note's words stay in the note: make it public to map it.")
    try:
        board, count = map_from_note_entry(db, entry)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return wb.BoardOut(
        id=board.id, title=board.content[2:], node_count=0, sketch_count=0, object_count=count,
        type="map", layout="tree-right", **wb._preview_fields(db, board.id),
    )


class MapFromText(BaseModel):
    name: str = Field(default="", max_length=100)
    #: A chat answer or a whole conversation, as the chat shows it (Markdown).
    text: str = Field(min_length=1, max_length=60000)


@router.post("/maps/from-text", status_code=201)
def map_from_text(body: MapFromText, db: Session = Depends(get_session)):
    """Chat's Make a mind map: an answer or a conversation, outlined like a
    note (headings and lists become branches, plain prose one topic per
    paragraph). The same build as `map_from_note_entry`, with no note behind
    the centre topic."""
    from tessellate.api import routes_whiteboard as wb

    title, branches = note_outline(body.text)
    if not branches:
        raise HTTPException(status_code=422, detail="There is nothing here to make a map from.")
    name = _clip(body.name.strip() or title or "Chat map", 100)
    board = Entry(content=f"# {name}", is_board=True)
    wb._store_board_settings(board, "map", "tree-right")
    db.add(board)
    db.flush()
    created = wb._place_map_nodes(db, board.id, [{"text": title or name, "children": branches}])
    wb._record_map_creation(db, board.id, name, f"map from chat text, {len(created)} nodes", {}, created)
    db.commit()
    db.refresh(board)
    return wb.BoardOut(
        id=board.id, title=board.content[2:], node_count=0, sketch_count=0, object_count=len(created),
        type="map", layout="tree-right", **wb._preview_fields(db, board.id),
    )


__all__ = ["MAX_FANOUT", "build_tree", "layout_both_sides", "map_from_note_entry", "note_outline", "router"]
