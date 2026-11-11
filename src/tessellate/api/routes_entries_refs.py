"""What points at a note: the reference-row scan (notes, documents, boards, maps) behind the Referenced-by row.

Moved whole out of routes_entries.py (K24). Nothing here reads routes_entries, so the pair stays
acyclic: routes_entries, routes_entries_links and routes_entries_history import from this module.
"""

from __future__ import annotations

import json
import re

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from tessellate.core.database import (
    LIKE_ESCAPE,
    Entry,
    WhiteboardNode,
    WhiteboardObject,
    like_escape,
)
from tessellate.entry import manager_purge
from tessellate.entry import manager_text
from tessellate.entry.mentions import MENTION_MIN_TITLE_CHARS, names_label
from tessellate.repo import documents as documents_repo


#: How many candidate sources a references scan will read, and how many rows
#: it will answer with. The same two caps `routes_documents._backlinks` uses,
#: and for the same reason: the scan is a LIKE over the notes and documents
#: tables, which is fine at any notebook size and is not free at every one.
REFERENCE_SOURCES_MAX = 400
REFERENCE_ROWS_MAX = 60


def _board_reference_rows_batch(session: Session, entry_ids: list[int]) -> dict[int, list[dict]]:
    """The boards and maps each of these notes is on, one row per board,
    boards and maps told apart. Two statements for the whole page.

    Two tables hold "this note is on that board", and a reader that knows
    one of them is wrong half the time (INBOX 246's first gap). A whiteboard
    card is a `WhiteboardNode` row. A mind map's note is a `WhiteboardObject`
    of kind "note" whose `data.ref_id` is the note (`MAP_REFERENCE_KINDS` in
    routes_whiteboard), and nothing else in `data` says which table the id
    belongs to: the kind does. So the object read filters on the kind first
    and only then on the id, the way routes_graph learnt to (a document and
    a note both numbered 1 exist in any notebook with one of each).

    `json_extract` because SQLite has JSON1 built in and the column is JSON;
    the verify-after in Python stays because a row written before the
    schema was tightened can hold anything. Shared by the Referenced-by row,
    the Connections dialog and the card's counts, so the three cannot
    disagree about what a board reference is.

    **A page at a time** (the performance pass, 2026-10-03). This was a pair
    of statements per note, so sixty cards were a hundred and twenty trips,
    each scanning `whiteboard_nodes` (no index on `entry_id`) and every
    `note` object of every map. `IN (...)` over the page is the same two
    scans once. Rows are read in id order, which is the order the per-note
    reads happened to return them in, and which makes the order a fact
    rather than the planner's choice.
    """
    from tessellate.entry.manager_text import plain_label

    wanted = set(entry_ids)
    seen_boards: dict[int, set[int]] = {i: set() for i in wanted}
    found: dict[int, list[tuple[int, Entry]]] = {i: [] for i in wanted}
    if not wanted:
        return {}
    for entry_id, board_id, board in session.execute(
        select(WhiteboardNode.entry_id, WhiteboardNode.board_id, Entry)
        .join(Entry, Entry.id == WhiteboardNode.board_id)
        .where(
            WhiteboardNode.entry_id.in_(wanted),
            Entry.is_deleted.is_(False),
        )
        .order_by(WhiteboardNode.id)
    ).all():
        if board_id is None or board_id in seen_boards[entry_id]:
            continue
        seen_boards[entry_id].add(board_id)
        found[entry_id].append((board_id, board))
    for board_id, board, raw in session.execute(
        select(WhiteboardObject.board_id, Entry, WhiteboardObject.data)
        .join(Entry, Entry.id == WhiteboardObject.board_id)
        .where(
            WhiteboardObject.kind == "note",
            func.json_extract(WhiteboardObject.data, "$.ref_id").in_(wanted),
            Entry.is_deleted.is_(False),
        )
        .order_by(WhiteboardObject.id)
    ).all():
        try:
            ref_id = (json.loads(raw or "{}") or {}).get("ref_id")
        except (ValueError, AttributeError):
            continue
        if board_id is None or not isinstance(ref_id, int) or ref_id not in wanted:
            continue
        if board_id in seen_boards[ref_id]:
            continue
        seen_boards[ref_id].add(board_id)
        found[ref_id].append((board_id, board))

    out: dict[int, list[dict]] = {}
    for entry_id, boards in found.items():
        rows: list[dict] = []
        for board_id, board in boards:
            #: `board_settings` says whether this is a whiteboard or a mind map,
            #: and the owner asked for both by name, so the row says which.
            #: Through `manager_purge.board_type_of` rather than parsed here: this app
            #: already reads that column in four places and CodeQL caught the
            #: fifth arriving with a bare `except: pass`, which is fair. One
            #: reader, one decision about what a malformed value means.
            kind = manager_purge.board_type_of(board)
            rows.append({
                "kind": kind,
                "id": board_id,
                "label": plain_label(board.content, 60) or ("Untitled map" if kind == "map" else "Untitled board"),
                "how": "on it",
            })
        out[entry_id] = rows[:REFERENCE_ROWS_MAX]
    return out


def _reference_rows_batch(session: Session, entries: list[Entry]) -> dict[int, list[dict]]:
    """Everything that points at each of these notes: documents, notes,
    boards, maps. Four statements for the whole page, whatever its size.

    INBOX 246, the owner's second sentence: "I want it to show in notes if
    they are attached to or referenced in/by a document, note, whiteboard, or
    mindmap."

    **Two kinds of pointing, and they are found two different ways.** A board
    or a map carries a note as a real row (`WhiteboardNode.entry_id`), so that
    half is a join and is exact. A document or another note carries it as
    text, either a `[[wiki link]]` or a bare mention of its label, so that
    half is the same LIKE-then-verify scan `routes_documents._backlinks`
    runs, and it says which of the two it found because "it links to this"
    and "it happens to say these words" are different facts about a note.

    A note with no label to be named by (an image-only note, a note that
    starts with a heading marker and nothing else) still gets its board rows:
    a card on a board is a reference whether or not the note has a name.

    **One scan for the page, not one per note** (the performance pass,
    2026-10-03, INBOX 441). The text half used to be two LIKE scans per note,
    each reading every note's and document's text: sixty cards at boot were
    two hundred and forty statements and 172 ms on 500 notes, growing with
    the notebook. Now each table is read once, with one `LIKE` flag column per
    distinct label, so SQLite still decides what matches (same ASCII case
    folding, same escaped wildcards, nothing re-implemented in Python) and
    only rows that match some label come back. The per-label caps and the
    order are the old ones: documents newest-updated first, notes newest
    first, `REFERENCE_SOURCES_MAX` each, the note itself never its own source.
    """
    from tessellate.entry.manager_text import plain_label

    result = _board_reference_rows_batch(session, [entry.id for entry in entries])
    label_of: dict[int, str] = {}
    for entry in entries:
        label = plain_label(entry.content, 60).strip()
        if label:
            label_of[entry.id] = label
    distinct = sorted(set(label_of.values()))
    document_hits = _document_mentions(session, distinct)
    note_hits = _note_mentions(session, distinct)
    for entry in entries:
        rows = list(result.get(entry.id, []))
        label = label_of.get(entry.id)
        if label is not None:
            rows += _mention_rows(entry.id, label, document_hits[label], note_hits[label])
            #: Links before mentions, so the rows someone chose come first, and the
            #: boards before both because they are exact.
            rows.sort(key=lambda row: {"on it": 0, "links to it": 1, "mentions it": 2}[row["how"]])
        result[entry.id] = rows[:REFERENCE_ROWS_MAX]
    return result


def _document_mentions(session: Session, distinct: list[str]) -> dict[str, list[tuple[int, str, str]]]:
    """Per label, the documents (newest-updated first) that name it."""
    hits: dict[str, list[tuple[int, str, str]]] = {label: [] for label in distinct}
    if not distinct:
        return hits
    #: `like`, not `ilike`: on SQLite a plain LIKE already folds ASCII case
    #: (the pragma that turns that off is never set here), and `ilike`
    #: compiles to `lower(x) LIKE lower(?)`, which copies every row's text
    #: once per label. Measured over 60 labels on 500 notes, same answers:
    #: 74 ms per call with `ilike`, 35 ms with `like`
    #: (`test_a_mention_matches_whatever_the_case...` pins the folding).
    for row in documents_repo.mention_rows(session, [_mention_like(label) for label in distinct]):
        for i, label in enumerate(distinct):
            if row[3 + i] and len(hits[label]) < REFERENCE_SOURCES_MAX and _names(row[2], label):
                hits[label].append((row[0], row[1] or "Untitled", row[2] or ""))
    return hits


def _note_mentions(session: Session, distinct: list[str]) -> dict[str, list[tuple[int, str]]]:
    """Per label, the notes (newest first) that name it."""
    hits: dict[str, list[tuple[int, str]]] = {label: [] for label in distinct}
    if not distinct:
        return hits
    #: Two groups (audit 2026-10-05, ARCH-11: 1.1 s for sixty cards at
    #: 5,000 notes, all of it SQLite running sixty LIKEs over every
    #: note). A label with an interior word has a phrase the full-text
    #: index can find, so its LIKE only reads the notes holding that
    #: phrase; a short label still reads every note. Each label is in
    #: one group, each group is read newest first, so a label's hits come
    #: back in the order they always did.
    narrowed = {label: _interior_phrase(label) for label in distinct}
    groups = [
        [label for label in distinct if narrowed[label] is None],
        [label for label in distinct if narrowed[label] is not None],
    ]
    for group in groups:
        if group:
            _scan_note_group(session, group, narrowed, hits)
    return hits


def _scan_note_group(session: Session, group: list[str], narrowed: dict, hits: dict[str, list[tuple[int, str]]]) -> None:
    flags = [Entry.content.like(_mention_like(label), escape=LIKE_ESCAPE) for label in group]
    where = [
        Entry.is_deleted.is_(False),
        #: A private note is encrypted at rest, so its content could not
        #: match the LIKE anyway; the filter is here so that stays true
        #: by decision rather than by side effect. The same sentence
        #: `routes_documents._backlinks` carries, for the same reason.
        Entry.is_private.is_(False),
        or_(*flags),
    ]
    if narrowed[group[0]] is not None:
        where.append(
            Entry.id.in_(
                text(
                    " UNION ".join(
                        f"SELECT rowid FROM entries_fts WHERE entries_fts MATCH :p{i}"
                        for i in range(len(group))
                    )
                ).bindparams(**{f"p{i}": narrowed[label] for i, label in enumerate(group)})
            )
        )
    for row in session.execute(
        select(Entry.id, Entry.content, *[f.label(f"m{i}") for i, f in enumerate(flags)])
        .where(*where)
        .order_by(Entry.id.desc())
    ):
        for i, label in enumerate(group):
            #: One over the cap, because the note itself can be among its
            #: own label's matches and is dropped per note below: the cap
            #: is on sources other than the note, as it always was.
            if row[2 + i] and len(hits[label]) <= REFERENCE_SOURCES_MAX and _names(row[1], label):
                hits[label].append((row[0], row[1] or ""))


def _mention_rows(entry_id: int, label: str, document_hits: list, note_hits: list) -> list[dict]:
    """The document and note rows that point at one note, links before mentions."""
    from tessellate.entry.manager_text import plain_label

    wanted = label.casefold()
    candidates: list[tuple[str, int, str, str]] = []
    for document_id, title, content in document_hits:
        candidates.append(("document", document_id, title, content))
    others = [(nid, content) for nid, content in note_hits if nid != entry_id]
    for note_id, content in others[:REFERENCE_SOURCES_MAX]:
        candidates.append(("note", note_id, plain_label(content, 60) or "Untitled note", content))
    return [
        {
            "kind": kind,
            "id": source_id,
            "label": source_label,
            #: A link is a decision someone made; a mention is a coincidence
            #: until they make it. Saying which is what stops this row being
            #: a list of every note that happens to share a word.
            "how": "links to it" if _links_to(content, wanted) else "mentions it",
        }
        for kind, source_id, source_label, content in candidates
    ]


def _mention_like(label: str) -> str:
    """The LIKE that narrows the scan; `_names` decides. A label too short to
    be mentioned (audit 1029 N1) can still be linked, `[[t]]`, so it only
    narrows to notes with that bracket."""
    if len(label) < MENTION_MIN_TITLE_CHARS:
        return f"%[[{like_escape(label)}%"
    return f"%{like_escape(label)}%"


def _names(content: str | None, label: str) -> bool:
    """Whether the text links to `label` or names it as a whole word: the
    one definition (`entry/mentions.py`) every mention surface shares."""
    return names_label(content, label) or _links_to(content, label.casefold())


#: A run of characters the full-text tokenizer may treat as one word: ASCII
#: letters and digits, and anything outside ASCII (whose class only the
#: tokenizer knows, so it is never assumed to split a word).
_FTS_WORDISH = re.compile(r"[A-Za-z0-9\u0080-\U0010ffff]+")


def _interior_phrase(label: str) -> str | None:
    """An `entries_fts` phrase every note containing `label` also contains.

    A note that holds the label as a substring (the LIKE's question) holds
    its interior words as whole words: the label's second word to its
    second-last are bounded by ASCII separators inside the label, so they are
    bounded the same way in the note, and the index (unicode61, which splits
    on every ASCII non-alphanumeric) tokenizes that span exactly as it
    tokenizes the phrase. The first and last words are left out because the
    note may run on into them ("biweekly reviews" holds "weekly review"), and
    no prefix query is used because porter stems a prefix too ("runn"* finds
    nothing where "running" is). None when there is no interior word, or no
    ASCII letter in it to be sure the phrase is not empty.
    """
    words = list(_FTS_WORDISH.finditer(label))
    if len(words) < 3:
        return None
    interior = label[words[1].start() : words[-2].end()]
    if not re.search(r"[A-Za-z0-9]", interior):
        return None
    return '"' + interior.replace('"', '""') + '"'


def _links_to(content: str | None, wanted: str) -> bool:
    """Whether some text has a `[[wiki link]]` whose target is `wanted` (casefolded)."""
    return any(
        manager_text.wiki_target(match.group(1)).casefold() == wanted
        for match in manager_text.WIKI_LINK.finditer(content or "")
    )


def _reference_rows(session: Session, entry: Entry) -> list[dict]:
    """Everything that points at this note: documents, notes, boards, maps.

    The page reader (`_reference_rows_batch`) asked about one note, so the
    Referenced-by row, the Connections dialog and the card's chip are the
    same code and cannot disagree.
    """
    return _reference_rows_batch(session, [entry])[entry.id]
