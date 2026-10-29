"""The graph view's data: every note and its connections in
one call, so the frontend can draw an Obsidian-style map.

Nodes are non-deleted entries; edges come from three places:
- manual links (the link button / link_notes tool),
- train-of-thought threads (parent_id),
- optionally, semantic similarity between stored vectors (?similarity=true)
  - computed on demand from the embeddings we already have, never stored.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from typing import Annotated
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai.embeddings import bytes_to_vector, similar_pairs
from tessellate.api import bounds
from tessellate.core import deps
from tessellate.core.database import Attachment, Document, EmbeddingRecord, Entry, EntryLink, EntryProperty, NoteType
from tessellate.core.deps import get_session
from tessellate.entry import manager, paths
from tessellate.entry import topics as topic_finder
from tessellate.search import search_manager

router = APIRouter(tags=["graph"])



def _age_days(created_at, now) -> int:  # noqa: ANN001  # datetime, kept off the signature for the import
    """Whole days since the note was written, never negative."""
    if created_at is None:
        return 0
    stamp = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    return max(0, int((now - stamp).total_seconds() // 86400))


def _tags_of(entry: Entry) -> list[str]:
    """The note's tags as a list, whatever shape the column holds. Empty for a
    private note while the vault is locked: they are as private as its text."""
    if manager.note_is_sealed(entry.is_private):
        return []
    try:
        tags = json.loads(entry.tags or "[]")
    except (TypeError, ValueError):
        return []
    return [str(t) for t in tags if isinstance(t, (str, int))]

# Below this cosine similarity two notes aren't "about the same thing"
# enough to draw a line between them.
SIMILARITY_EDGE_THRESHOLD = 0.55
# A hard cap keeps a dense notebook from becoming a hairball (and the
# O(n²) comparison from mattering, it's personal-notebook scale).
MAX_SIMILARITY_EDGES = 200
#: GRAPH_PLAN 518 (4): each note's closest matches, kept by `similar_pairs`
#: as it goes. The map draws two per note (`gcPruneSimilarity`); every pair
#: above the cutoff was up to n^2/2 tuples (an embedding model scores most of
#: a notebook as a little alike) before the cap above threw all but 200 away.
SIMILAR_PER_NODE = 4


# --- caching the two expensive derivations (ROADMAP §40, items 4 and 5) ----------
#
# Similarity edges are an all-pairs vector comparison and PageRank is fifteen
# passes over every node and edge. Both were recomputed from scratch on every
# request, which made `/graph` the most expensive endpoint in the app and made
# `/graph/local`, "focus mode", which is supposed to be the *cheap* one, pay
# the full notebook cost to draw a neighbourhood.
#
# Neither can be made local. Centrality is a global property by definition, and
# a similarity edge can join two notes at opposite ends of the notebook, so
# restricting either to the visited set would return different, wrong numbers.
# What they can be is computed once per version of the notebook.
#
# The version is a fingerprint of cheap aggregates rather than a counter
# someone has to remember to bump, a counter is a thing to forget, and a
# forgotten one serves a stale graph indefinitely. `updated_at` moves on any
# note edit, and the two counts move on anything created or destroyed.
#
# A link removed and another added between two requests leaves the count
# identical, so the newest link's time is in it too (GRAPH_PLAN 518 (3)): any
# add moves it, any removal moves the count. Not the newest id: SQLite hands
# a deleted top id to the next row, so remove-then-add kept it (measured).
_cache_lock = threading.Lock()
_cache: dict[str, tuple] = {}
#: KG6: topic summaries by their members and versions, newest last, capped.
_summaries: dict[tuple, str] = {}
SUMMARY_CACHE_MAX = 200


def _graph_fingerprint(session: Session) -> tuple:
    live = Entry.is_deleted == False  # noqa: E712
    return (
        # Which notebook. The cache is process-global while the counts below
        # are emphatically not unique, two notebooks holding three notes each
        # collide trivially, and so do two tests. Without this, restoring a
        # backup or pointing TESSELLATE_DATA_DIR somewhere else could be served
        # the previous notebook's centrality.
        str(deps.get_config().data_dir),
        # Which space. Every count below is already narrowed to it (the
        # session's workspace filter), but two spaces with equal counts and
        # an equal newest edit would otherwise share one centrality.
        str(session.info.get("workspace_id") or ""),
        tuple(sorted(session.info.get("hidden_workspaces") or ())),
        session.scalar(select(func.count(Entry.id)).where(live)) or 0,
        session.scalar(select(func.max(Entry.updated_at)).where(live)),
        session.scalar(select(func.count(EntryLink.id))) or 0,
        session.scalar(select(func.max(EntryLink.created_at))),
    )


def _cached(name: str, fingerprint: tuple, build):  # noqa: ANN001
    """`build()`'s result for this version of the notebook, computed once.

    One slot per name, not an LRU: only the current version is ever asked for,
    and keeping the previous one alive holds a whole graph's worth of floats
    for nobody.
    """
    with _cache_lock:
        hit = _cache.get(name)
        if hit is not None and hit[0] == fingerprint:
            return hit[1]
    value = build()
    with _cache_lock:
        _cache[name] = (fingerprint, value)
    return value


def reset_graph_cache() -> None:
    """Drop everything. For the tests, and for a data restore."""
    with _cache_lock:
        _cache.clear()
        _text_memo.clear()
        _summaries.clear()


#: GRAPH_PLAN 518 (2): each note's label and word count, per version of the
#: note. `/graph` read and cleaned every note's whole text on every call (90 ms
#: at 2,018 notes); the rest of a node is columns. Keyed by notebook and id,
#: checked against `updated_at` (any edit moves it); a private note is never
#: kept, its text depends on whether the vault is open.
_text_memo: dict[tuple[str, int], tuple] = {}


#: What a private note is called on the map while the vault is locked.
SEALED_LABEL = "Private note"


def _label(entry: Entry, length: int = 40) -> str:
    """A node's one-line label through the vault gate: the node stays on the
    map, its words do not (INBOX 1437)."""
    if manager.note_is_sealed(entry.is_private):
        return SEALED_LABEL
    return _preview(manager.readable_content(entry), length)


def _words(entry: Entry) -> int:
    """A node's length in words; nothing to count while the note is sealed."""
    if manager.note_is_sealed(entry.is_private):
        return 0
    return _word_count(manager.readable_content(entry))


def _note_texts(entries: list) -> dict[int, tuple[str, int]]:
    """{id: (preview, words)} for these notes, reading only what changed."""
    notebook = str(deps.get_config().data_dir)
    out: dict[int, tuple[str, int]] = {}
    fresh: dict[tuple[str, int], tuple] = {}
    with _cache_lock:
        memo = dict(_text_memo)
    for e in entries:
        key = (notebook, e.id)
        hit = memo.get(key)
        if hit is not None and hit[0] == e.updated_at and not e.is_private:
            out[e.id] = hit[1]
        else:
            if manager.note_is_sealed(e.is_private):
                out[e.id] = (SEALED_LABEL, 0)
            else:  # one read for both numbers
                text = manager.readable_content(e)
                out[e.id] = (_preview(text), _word_count(text))
            if not e.is_private:
                fresh[key] = (e.updated_at, out[e.id])
                continue
        if hit is not None:
            fresh[key] = hit
    with _cache_lock:
        # Only this notebook's live notes stay, so a deleted note's text goes.
        for key in [k for k in _text_memo if k[0] == notebook]:
            del _text_memo[key]
        _text_memo.update(fresh)
    return out


# Registered rather than imported by the container. `deps.reset_app_state`
# used to reach up into this module to call the line above, which is the wrong
# direction: `core/` is the bottom layer. This says "empty me when the
# singletons go" without `core` needing to know this file exists.
deps.register_cache_reset(reset_graph_cache)


_HEADING_MD = re.compile(r"^\s{0,3}#{1,6}\s+", re.M)
# A callout's own opening line, `> [!tip] Remember`, is a blockquote marker
# plus the `[!kind]` tag (editor.js's mdCalloutElement parses the same shape).
# Left unstripped, a note that opens with a callout showed as a graph node
# label reading literally "Review > [!tip] Remem…", reported directly, and
# the fix is the callout equivalent of what _HEADING_MD already does for `#`.
_CALLOUT_MD = re.compile(r"^\s{0,3}>\s*\[!\w+\]\s*", re.M)
_WIKI_LINK = re.compile(r"\[\[([^\[\]]{1,120})\]\]")


def _preview(text: str, length: int = 40) -> str:
    """One line of a note as plain words, markers stripped, not rendered.

    Mirrors the frontend's notePreviewText: these labels are clipped to ~40
    characters, and a clip that lands mid-`**` shows scaffolding
    ("**Seraphine…") instead of the note. Inline marker stripping is
    `manager.strip_inline_markdown`, heading/wiki-link handling stays here
    since those are specific to what a graph label is for.

    The first line with words in it (INBOX 446 (5)): every line used to be
    joined, so "# Tomato soup" over a paragraph was labelled "Tomato soup A
    few lin…", its title run into its body, while a longer title happened
    to clip before the body and read correctly. A line that strips to
    nothing (a picture, a bare rule) is passed over for the next one.
    """
    from tessellate.entry.properties import strip as strip_properties

    #: KG4: a note's properties block is never its label.
    for line in strip_properties(text).splitlines():
        words = _preview_line(line)
        if words:
            return words if len(words) <= length else words[: length - 1] + "…"
    return ""


def _preview_line(line: str) -> str:
    """One line as plain words: the marker stripping `_preview` applies."""
    line = _HEADING_MD.sub("", line)
    line = _CALLOUT_MD.sub("", line)
    line = _WIKI_LINK.sub(lambda m: manager.wiki_shown(m.group(1)), line)
    line = manager.strip_inline_markdown(line)
    return " ".join(line.split())


def _similarity_edges(
    session: Session, node_ids: set[int], taken: set[frozenset[int]]
) -> list[dict]:
    """Pairwise cosine over stored vectors of the current backend.

    Pairs already joined by a real link/thread edge are skipped, the stronger
    relationship wins.

    The comparison itself is cached per version of the notebook; only the
    `taken` filter and the cap are re-applied, because `taken` differs between
    callers (the full graph has already claimed its link and thread pairs;
    focus mode has not). The backend id is part of the key: vectors from two
    embedding models live in different spaces, so a model switch has to
    invalidate this even when no note changed.
    """
    backend = deps.get_embeddings().backend_id()
    fingerprint = (*_graph_fingerprint(session), backend)

    #: **One sweep, over the map's notes, whoever asks** (GRAPH_PLAN, 2026-10-05).
    #: The build used to read the caller's `node_ids` while the slot's key did
    #: not, so the map (no drafts, no boards) and focus mode (every live note)
    #: were served each other's sweep, whichever came first. The sweep is now
    #: over the notes a similarity line means something for (live, not a
    #: draft, not a board, whose text is its title), and each caller keeps the
    #: pairs inside its own set: one sweep per version of the notebook, and
    #: the same answer in any order.
    def build() -> list[tuple[int, int, float]]:
        wanted = set(
            session.scalars(
                select(Entry.id).where(
                    Entry.is_deleted == False,  # noqa: E712
                    Entry.is_draft == False,  # noqa: E712
                    Entry.is_board == False,  # noqa: E712
                )
            )
        )
        records = session.scalars(
            select(EmbeddingRecord).where(EmbeddingRecord.model_version == backend)
        )
        vectors = {
            r.entry_id: bytes_to_vector(r.embedding)
            for r in records
            if r.entry_id in wanted
        }
        return similar_pairs(vectors, SIMILARITY_EDGE_THRESHOLD, per_node=SIMILAR_PER_NODE)

    # Already sorted best-first, so the cap below keeps the strongest edges.
    scored = [
        {"source": a, "target": b, "kind": "similar", "score": round(score, 2)}
        for a, b, score in _cached("similarity", fingerprint, build)
        if a in node_ids and b in node_ids and frozenset((a, b)) not in taken
    ]
    return scored[:MAX_SIMILARITY_EDGES]


def _centrality(session: Session, similarity: bool, maps: bool) -> dict:
    """PageRank over the map's own picture, once per version of the notebook.

    **One number per note, the map's** (GRAPH_PLAN, "Decision made,
    2026-10-05: one PageRank, the map's"). `/graph` and `/graph/local` used to
    hand this their own index and share one slot keyed only by the notebook
    and the similarity switch, but the two indexes were different graphs (the
    map leaves drafts out, and boards unless Maps is on; focus mode indexed
    every live note), so whichever call came first was served to the other,
    and turning Maps on was served the no-maps ranking. Now the graph ranked
    is always the map's: live, non-draft notes, boards only with `maps`, their
    links, threads and shared tags, and similarity edges when `similarity` is
    on, built here from columns (`paths.build_light`) and never from a
    caller's index. A note is the same size in focus mode as on the map.

    Not a PageRank of the focus neighbourhood: centrality is a global
    property, and a local one would make the centre of every focus view its
    biggest dot whatever the notebook says about it.
    """
    use_similarity = similarity and not deps.get_config().get_preference("battery_efficient_mode")
    fingerprint = (*_graph_fingerprint(session), use_similarity, maps)
    if use_similarity:
        fingerprint = (*fingerprint, deps.get_embeddings().backend_id())

    def build() -> dict:
        extra: list[dict] = []
        if use_similarity:
            ids = set(
                session.scalars(
                    select(Entry.id).where(
                        Entry.is_deleted == False,  # noqa: E712
                        Entry.is_draft == False,  # noqa: E712
                        *(() if maps else (Entry.is_board == False,)),  # noqa: E712
                    )
                )
            )
            extra = _similarity_edges(session, ids, set())
        index = paths.build_light(session, extra_edges=extra, drafts=False, boards=maps)
        return paths.pagerank(index)

    return _cached(f"centrality_{int(use_similarity)}_{int(maps)}", fingerprint, build)


@router.get("/graph/match")
def graph_match(q: str = Query(default="", max_length=200), session: Session = Depends(get_session)) -> dict:
    """The note ids a group's words match (GRAPH_PLAN Phase 3).

    A group is a saved search painted one colour, resolved on every render
    so a note written tomorrow joins it by itself. `/entries?q=` only filters
    when `semantic=true` (the list is filtered client-side by keyword), so a
    group needs the keyword engine directly: the same `keyword_search` the
    Notes tab uses, ids only, capped so a one-word group over a big notebook
    is one small reply rather than five thousand previews.
    """
    words = q.strip()
    if not words:
        return {"ids": []}
    hits = search_manager.keyword_search(session, words, limit=5000)
    return {"ids": [entry.id for entry in hits]}

#: Co-mention edges between entities (KG5): named together this often, in
#: notes naming no more than the cap.
COMENTION_MIN = 2
COMENTION_NOTE_CAP = 12


def _add_entity_nodes(
    session: Session, nodes: list[dict], edges: list[dict], node_ids: set[int]
) -> None:
    """The entities the notes mention, as their own nodes and edges.

    Lifted out of `graph` unchanged (WORLD_CLASS_PLAN A5): the route was
    355 lines, of which three opt-in blocks like this one were 130. An
    entity node's id is prefixed (`entity:5`) so it can never collide with
    an Entry id, which is what lets this be opt-in without breaking a
    consumer that assumes every node id is a note.
    """
    from tessellate.core.database import Entity, EntityMention

    mentions = list(
        session.execute(
            select(EntityMention.entity_id, EntityMention.entry_id).where(
                EntityMention.entry_id.in_(node_ids)
            )
        )
    )
    entity_ids = {m.entity_id for m in mentions}
    if entity_ids:
        entities = {
            e.id: e for e in session.scalars(select(Entity).where(Entity.id.in_(entity_ids)))
        }
        for entity_id, entity in entities.items():
            nodes.append(
                {
                    "id": f"entity:{entity_id}",
                    "type": "entity",
                    "preview": entity.name,
                    "category": "Entity",
                    "created_at": entity.created_at.isoformat(),
                    "entity_kind": entity.kind,
                }
            )
        by_note: dict[int, list[int]] = {}
        for mention in mentions:
            if mention.entity_id in entities:
                by_note.setdefault(mention.entry_id, []).append(mention.entity_id)
                edges.append(
                    {
                        "source": f"entity:{mention.entity_id}",
                        "target": mention.entry_id,
                        "kind": "entity",
                    }
                )
        # GRAPH_PLAN KG5: two entities named together in two notes or more
        # are joined, weighted by how many. Once is coincidence ("thanks Sam,
        # Priya and Jo"); a note naming more than twelve says nothing about
        # any one pair and costs the most, so it is left out.
        together: dict[tuple[int, int], int] = {}
        for named in by_note.values():
            named = sorted(set(named))
            if len(named) > COMENTION_NOTE_CAP:
                continue
            for i, a in enumerate(named):
                for b in named[i + 1:]:
                    together[(a, b)] = together.get((a, b), 0) + 1
        for (a, b), count in together.items():
            if count >= COMENTION_MIN:
                edges.append(
                    {"source": f"entity:{a}", "target": f"entity:{b}", "kind": "comention", "weight": count}
                )


GRAPH_DOCUMENT_CAP = 500


def _add_document_nodes(
    session: Session, nodes: list[dict], edges: list[dict], node_ids: set[int]
) -> None:
    """The documents attached to the notes, as their own nodes and edges.

    Lifted out of `graph` unchanged (WORLD_CLASS_PLAN A5). Same shape and
    same reason as `_add_entity_nodes`: a prefixed id, an edge per real
    `DocumentLink`, and nothing wired into centrality or the path index,
    both of which are built entirely around Entry.
    """
    from tessellate.core.database import Document, DocumentLink

    doc_links = list(
        session.execute(
            select(DocumentLink.document_id, DocumentLink.entry_id).where(
                DocumentLink.entry_id.in_(node_ids)
            )
        )
    )
    #: **Every live document, not only the attached ones** (the owner: "the
    #: documents toggle in the graph doesnt do anything"). It used to add a
    #: document only when a note was linked to it, so a notebook whose
    #: documents stand alone, which is most of them, got no document nodes
    #: at all and the switch changed nothing on screen. An unattached
    #: document is drawn alone (the "Hide unlinked" switch hides it like any
    #: other lone node); the attached ones keep their edges. Capped, newest
    #: first, so a large library cannot swamp the map or the payload.
    documents = {
        d.id: d
        for d in session.scalars(
            select(Document)
            .where(Document.archived_at.is_(None))
            .order_by(Document.updated_at.desc())
            .limit(GRAPH_DOCUMENT_CAP)
        )
    }
    for extra in {link.document_id for link in doc_links} - set(documents):
        linked = session.get(Document, extra)
        if linked is not None and linked.archived_at is None:
            documents[extra] = linked
    if documents:
        for document_id, document in documents.items():
            nodes.append(
                {
                    "id": f"document:{document_id}",
                    "type": "document",
                    "preview": document.title,
                    "category": "Document",
                    "created_at": document.created_at.isoformat(),
                    "graph_pin_x": document.graph_pin_x,
                    "graph_pin_y": document.graph_pin_y,
                }
            )
        edges.extend(
            {
                "source": f"document:{link.document_id}",
                "target": link.entry_id,
                "kind": "document",
            }
            for link in doc_links
            if link.document_id in documents
        )



def _add_map_edges(
    session: Session,
    entries: list,
    nodes: list[dict],
    edges: list[dict],
    node_ids: set[int],
    taken: set[frozenset[int]],
) -> None:
    """Which notes each mind map is made of, as edges to the board node.

    Lifted out of `graph` unchanged (WORLD_CLASS_PLAN A5). **No new node
    is created**, which is what separates this from the two above: a board
    *is* an `Entry`, so it is already in `nodes`; what was missing was that
    the node never said it was a map and its membership was invisible.
    `taken` is the route's own pair ledger, passed in so a map edge cannot
    duplicate a link edge the note already had.
    """
    from tessellate.api.routes_whiteboard import _board_settings
    from tessellate.core.database import WhiteboardObject

    board_ids = {e.id for e in entries if getattr(e, "is_board", False)}
    if board_ids:
        by_id = {n["id"]: n for n in nodes}
        maps: set[int] = set()
        for entry in entries:
            if entry.id not in board_ids:
                continue
            board_type, _layout = _board_settings(entry)
            node = by_id.get(entry.id)
            if node is None:
                continue
            # `board` and `map` both, because the graph's own reason for
            # marking these is that a board of any kind is not a note the
            # way every other node here is, and a whiteboard that says so
            # is more honest than one drawn as a note with a heading.
            node["type"] = board_type
            if board_type == "map":
                maps.add(entry.id)
        if maps:
            #: **`kind == "note"` only, and this is not a tidiness
            #: preference.** The first version queried every
            #: `MAP_REFERENCE_KINDS` row and filtered on `ref_id in
            #: node_ids` afterwards, reasoning that a document/file/
            #: bookmark id simply would not be an entry id. It is: these
            #: are four independent autoincrement sequences, so document 1
            #: and note 1 both exist in any notebook with one of each.
            #: `tests/test_mindmap.py` caught it emitting `{source: 1,
            #: target: 1}`, a map joined to *itself* through a document
            #: node: on the second row it was ever given. An id is only
            #: meaningful with its table, and the kind is the table.
            rows = session.execute(
                select(WhiteboardObject.board_id, WhiteboardObject.data).where(
                    WhiteboardObject.board_id.in_(maps),
                    WhiteboardObject.kind == "note",
                )
            )
            for board_id, raw in rows:
                try:
                    ref_id = (json.loads(raw or "{}") or {}).get("ref_id")
                except (TypeError, ValueError):
                    # A row edited by hand, or written before `data` was
                    # JSON. A map node nobody can read points at nothing.
                    continue
                # A note that has since been deleted, or a private one the
                # caller's `entries` query never returned: an edge naming a
                # node the client did not receive is silently dropped by
                # d3, which is an invisible failure rather than a visible
                # one.
                if not isinstance(ref_id, int) or ref_id not in node_ids:
                    continue
                # A map that somehow points at itself is not a connection.
                if ref_id == board_id:
                    continue
                pair = frozenset((board_id, ref_id))
                if pair in taken:
                    continue
                taken.add(pair)
                edges.append({"source": board_id, "target": ref_id, "kind": "map"})


def _add_tag_nodes(nodes: list[dict], edges: list[dict]) -> None:
    """GRAPH_PLAN 514 (2): each tag a node (`tag:<name>`), joined to its notes."""
    seen: dict[str, dict] = {}
    for node in [n for n in nodes if n.get("kind") == "note"]:
        for tag in dict.fromkeys(t.strip() for t in node["tags"] if t.strip()):
            key = f"tag:{tag.lower()}"
            if key not in seen:
                seen[key] = {"id": key, "type": "tag", "preview": f"#{tag}", "category": "Tag", "created_at": node["created_at"]}
            elif node["created_at"] < seen[key]["created_at"]:
                seen[key]["created_at"] = node["created_at"]
            edges.append({"source": key, "target": node["id"], "kind": "tagged"})
    nodes.extend(seen.values())


def _add_unresolved_nodes(
    session: Session, entries: list, nodes: list[dict], edges: list[dict]
) -> None:
    """GRAPH_PLAN 514 (3): a `[[name]]` no note answers to, as a faint node.

    Resolved the way `manager.find_by_wiki_name` resolves (a vault file's
    stem, or a note's opening line starting with the name; private notes are
    never targets), against one in-memory index rather than two queries per
    link: the name's place in the sorted openings says whether one starts
    with it.
    """
    from bisect import bisect_left

    live = session.execute(
        select(Entry.content, Entry.source_path).where(
            Entry.is_deleted == False, Entry.is_private == False  # noqa: E712
        )
    ).all()
    openings = sorted(manager.wiki_opening(content) for content, _ in live)
    stems = {
        (path or "").rsplit("/", 1)[-1].lower().removesuffix(".md").removesuffix(".markdown")
        for _, path in live
        if path
    }
    ghosts: dict[str, dict] = {}
    for entry in entries:
        for name in manager.wiki_link_targets(manager.readable_content(entry)):
            wanted = name.strip().lower()
            at = bisect_left(openings, wanted)
            if wanted in stems or (at < len(openings) and openings[at].startswith(wanted)):
                continue
            key = f"unresolved:{wanted}"
            if key not in ghosts:
                ghosts[key] = {
                    "id": key, "type": "unresolved", "preview": name.strip(),
                    "category": "Unresolved", "created_at": entry.created_at.isoformat(),
                }
            edges.append({"source": entry.id, "target": key, "kind": "unresolved"})
    nodes.extend(ghosts.values())


def _add_attachment_nodes(
    session: Session, nodes: list[dict], edges: list[dict], node_ids: set[int]
) -> None:
    """GRAPH_PLAN 514 (6): each file or picture on a note, as its own node."""
    rows = session.scalars(
        select(Attachment)
        .where(Attachment.entry_id.in_(node_ids))
        .order_by(Attachment.created_at.desc())
        .limit(GRAPH_DOCUMENT_CAP)
    )
    for row in rows:
        key = f"attachment:{row.id}"
        nodes.append(
            {
                "id": key, "type": "attachment", "preview": row.filename, "mime": row.mime,
                "category": "Attachment", "created_at": row.created_at.isoformat(),
            }
        )
        edges.append({"source": key, "target": row.entry_id, "kind": "attachment"})


def _word_count(text: str | None) -> int:
    """Words in a note's text, for the map's size-by-length rule."""
    return len((text or "").split())


#: What `/graph` reads of a note: the node's fields, the label's text (the
#: memo below decides whether it is read), and what the opt-in layers need
#: (a board's settings, a vault file's path for unwritten links).
_GRAPH_COLUMNS = (
    Entry.id,
    Entry.content,
    Entry.tags,
    Entry.workspace_id,
    Entry.category_id,
    Entry.created_at,
    Entry.updated_at,
    Entry.edited_at,
    Entry.access_count,
    Entry.pinned,
    Entry.graph_pin_x,
    Entry.graph_pin_y,
    Entry.parent_id,
    Entry.is_board,
    Entry.is_private,
    Entry.board_settings,
    Entry.source_path,
)


def _payload_key(session: Session, similarity: bool, include_maps: bool, include_tags: bool) -> tuple:
    """Everything the default `/graph` payload is made of, as one digest.

    GRAPH_PLAN "Still open": the payload at 5,000 notes is 0.7 to 1.0 s warm
    and 3 MB, and the fingerprint the centrality cache uses (counts and the
    newest edit) misses what moves a node without editing a note: a pin, an
    access count, an attachment, a note put on a map, a link's reason, the
    vault opening. So every column the payload reads is hashed instead, row
    by row: a few small-column reads against the build's dozen queries, the
    content itself left out because `updated_at` moves with it. Read through
    the ORM so the space filter applies, as the payload's own reads do.
    """
    from tessellate.core import vault
    from tessellate.core.database import Category, WhiteboardObject

    digest = hashlib.blake2b(digest_size=16)

    def feed(rows) -> None:  # noqa: ANN001
        for row in rows:
            digest.update(repr(tuple(row)).encode())
        digest.update(b"|")

    feed(
        session.execute(
            select(
                Entry.id, Entry.updated_at, Entry.access_count, Entry.pinned, Entry.graph_pin_x,
                Entry.graph_pin_y, Entry.category_id, Entry.tags, Entry.is_private, Entry.workspace_id,
                Entry.parent_id, Entry.is_board, Entry.board_settings, Entry.source_path, Entry.created_at,
            )
            .where(Entry.is_deleted == False, Entry.is_draft == False)  # noqa: E712
            .order_by(Entry.id)
        )
    )
    feed(session.execute(select(Category.id, Category.name).order_by(Category.id)))
    feed(
        session.execute(
            select(
                EntryLink.id, EntryLink.source_entry_id, EntryLink.target_entry_id, EntryLink.reason,
                EntryLink.reason_confidence, EntryLink.link_type, EntryLink.two_way,
            ).order_by(EntryLink.id)
        )
    )
    feed(session.execute(select(Attachment.entry_id).distinct().order_by(Attachment.entry_id)))
    feed(
        session.execute(
            select(WhiteboardObject.id, WhiteboardObject.board_id, WhiteboardObject.data)
            .where(WhiteboardObject.kind == "note")
            .order_by(WhiteboardObject.id)
        )
    )
    digest.update(repr(sorted(manager.relation_types(session).items())).encode())
    config = deps.get_config()
    with_similarity = similarity and not config.get_preference("battery_efficient_mode")
    if with_similarity:
        feed(session.execute(select(func.count(EmbeddingRecord.id), func.max(EmbeddingRecord.created_at))))
        #: Vectors from two models live in different spaces: a switch is a new
        #: payload though no note changed.
        digest.update(str(deps.get_embeddings().backend_id()).encode())
    #: A note type's name and colour paint the "Note type" rule (`type_colours`).
    feed(session.execute(select(NoteType.id, NoteType.name, NoteType.colour).order_by(NoteType.id)))
    vault_key = vault.key()
    return (
        _graph_fingerprint(session),
        digest.hexdigest(),
        with_similarity,
        include_maps,
        include_tags,
        # A node's `age_days` counts from today.
        datetime.now(timezone.utc).date().isoformat(),
        # A private note's label is its text while this request may read it,
        # a placeholder otherwise; a new key reads differently again.
        hashlib.blake2b(vault_key, digest_size=8).hexdigest() if vault_key else None,
    )


@router.get("/graph")
def graph(
    similarity: bool = False,
    include_entities: bool = False,
    include_documents: bool = False,
    include_maps: bool = False,
    include_tags: bool = False,
    include_unresolved: bool = False,
    include_attachments: bool = False,
    slim: bool = False,
    session: Session = Depends(get_session),
) -> Response:
    """The notebook as nodes and edges, served from a cache of the encoded
    payload while nothing it is made of has moved (`_payload_key`).

    Only the common shape is cached: entities, documents, unresolved links
    and attachments as nodes read tables the key does not hash, so a request
    for any of them is built every time, as before.
    """
    build = lambda: _build_graph(  # noqa: E731
        similarity=similarity,
        include_entities=include_entities,
        include_documents=include_documents,
        include_maps=include_maps,
        include_tags=include_tags,
        include_unresolved=include_unresolved,
        include_attachments=include_attachments,
        slim=slim,
        session=session,
    ).body
    if include_entities or include_documents or include_unresolved or include_attachments:
        return Response(content=build(), media_type="application/json")
    key = _payload_key(session, similarity, include_maps, include_tags)
    body = _cached(f"payload:{bool(similarity)}:{include_maps}:{include_tags}:{slim}", key, build)
    return Response(content=body, media_type="application/json")


def _iso_or_none(value):  # noqa: ANN001
    return value.isoformat() if value else None


def _build_graph(
    similarity: bool = False,
    include_entities: bool = False,
    include_documents: bool = False,
    include_maps: bool = False,
    include_tags: bool = False,
    include_unresolved: bool = False,
    include_attachments: bool = False,
    session: Session | None = None,
    slim: bool = False,
) -> JSONResponse:
    # A draft is unfinished by definition, and the Notes tab already keeps
    # every draft out of the notebook it draws from, the graph is a map of
    # your notes and their connections, not a staging area, and a half-typed
    # draft has nothing worth connecting yet. Reported directly alongside the
    # same gap in Library (routes_library.py's `_notes()`).
    #: **Columns, not notes** (GRAPH_PLAN, 2026-10-05, measured at 5,000
    #: notes): every field a node or an opt-in layer reads, as plain rows. The
    #: whole `Entry` objects this loaded (and the 10,000 `EntryLink` objects
    #: below) were half of a warm call's time in the ORM's instance
    #: bookkeeping alone; a row answers `e.id`, `e.content`, `e.is_board` the
    #: same way, so every helper below takes it unchanged.
    entries = list(
        session.execute(
            select(*_GRAPH_COLUMNS).where(
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_draft == False,  # noqa: E712
            )
        )
    )
    #: **A board is an `Entry`, so "off" has to mean "not on the map at all".**
    #: Reported (INBOX 185, the owner): "Things that I have turned off in the
    #: graph for not showing them like the mindmap and entities still show
    #: anyway". Reproduced before it was touched, on a notebook with two mind
    #: maps: with the switch off the graph drew 74 nodes of which two were
    #: those maps, drawn as ordinary notes; with it on it drew the same 74, two
    #: of them now typed `map`. `include_entities` and `include_documents` add
    #: nodes that do not otherwise exist, so off really does mean absent for
    #: those two; a board has been a node here since boards existed (§2: a
    #: board *is* an Entry whose content is `# My map`), and all the switch did
    #: was mark it and draw its membership edges. A switch that changes how a
    #: thing is labelled while it stays on screen is not a switch the reader
    #: can read, so the filter is here, at the source: no board in `entries`
    #: means no board node, no board edge, and no board in the centrality pass
    #: or the path index either.
    if not include_maps:
        entries = [e for e in entries if not getattr(e, "is_board", False)]
    node_ids = {e.id for e in entries}
    category_names = manager.bulk_category_names(session, entries)
    # GRAPH_PLAN Phase 3: "colour by" is a rule picker (category, cluster,
    # kind, age, space, tag, has a file), so every note carries the fields
    # each rule reads. One query for the file rule rather than a join per
    # node; tags are the column's JSON list, never the raw string.
    with_files = set(session.scalars(select(Attachment.entry_id).distinct()))
    # GRAPH_PLAN Phase 5: which mind maps a note is on, from the map nodes'
    # own data (a note node stores `ref_id`), one query for the whole
    # payload. `map_ids` is what "has a map" colours by and what the local
    # pane will list; it is here whether or not maps are drawn as nodes.
    maps_of: dict[int, list[int]] = {}
    from tessellate.core.database import WhiteboardObject

    for board_id, raw in session.execute(
        select(WhiteboardObject.board_id, WhiteboardObject.data).where(
            WhiteboardObject.kind == "note", WhiteboardObject.board_id.is_not(None)
        )
    ):
        try:
            ref_id = (json.loads(raw or "{}") or {}).get("ref_id")
        except (TypeError, ValueError):
            continue
        if isinstance(ref_id, int) and board_id is not None:
            maps_of.setdefault(ref_id, []).append(board_id)
    now = datetime.now(timezone.utc)
    #: Each note's label and word count, read once per version (`_note_texts`).
    labels = _note_texts(entries)
    #: WORLD_CLASS_PLAN row 10 (D5): a note's type, for the "Note type" colour
    #: rule, read from the properties index KG4 keeps (one query, the `type`
    #: key's first value per note), never by parsing every note's block. A
    #: private note has no index rows, so it carries none.
    #: A note may spell its type in its own case ("type: book"); the node
    #: carries the type's own name when Note types has it, so "book" and
    #: "Book" are one colour and one legend row, not two.
    type_colours: dict[str, str] = {}
    canonical: dict[str, str] = {}
    for name, colour in session.execute(select(NoteType.name, NoteType.colour)):
        canonical[name.casefold()] = name
        if colour:
            type_colours[name] = colour
    type_of: dict[int, str] = {}
    for entry_id, value in session.execute(
        select(EntryProperty.entry_id, EntryProperty.value)
        .where(EntryProperty.key == "type")
        .order_by(EntryProperty.id)
    ):
        if entry_id in node_ids and value:
            type_of.setdefault(entry_id, canonical.get(value.casefold(), value))
    nodes = [
        {
            "id": e.id,
            "kind": "note",
            "note_type": type_of.get(e.id),
            "tags": _tags_of(e),
            "space_id": e.workspace_id,
            "has_file": e.id in with_files,
            "map_ids": sorted(set(maps_of.get(e.id, []))),
            "age_days": _age_days(e.created_at, now),
            # Through the manager, never off the column: a private note's
            # `content` is ciphertext at rest, so `_preview(e.content)` labelled
            # it with a base64 blob. `readable_content` names the graph in its
            # own docstring as one of the places that must not break on a
            # private note: it decrypts while the vault is open and hands back
            # "Private note: unlock to read it." while it is locked.
            "preview": labels[e.id][0],
            "category": category_names.get(e.category_id, manager.UNCATEGORISED),
            "access_count": e.access_count,
            "pinned": e.pinned,
            # Where a double-click hold (graph.js) left this node, if it was
            # ever pinned in place, both null or both set, never one alone.
            # Distinct from `pinned` just above: that means "float to the
            # top of lists", this means "hold still at this point on the
            # map". Read on load so a pin survives a page reload, which is
            # the gap ROADMAP §87.1's own audit named.
            "graph_pin_x": e.graph_pin_x,
            "graph_pin_y": e.graph_pin_y,
            # A note's reply-to, so the tree layouts can nest a train of
            # thought under the note that started it instead of laying every
            # note out as a sibling (§9).
            "parent_id": e.parent_id if e.parent_id in node_ids else None,
            # `+ "Z"` predates `core/database.DateTime`, which now always
            # hands back a timezone-AWARE (UTC) datetime: so `.isoformat()`
            # alone already ends in `+00:00`, and appending "Z" on top
            # produced `...+00:00Z`: two timezone markers in one string,
            # which `new Date(...)` in JavaScript cannot parse at all
            # (silently `Invalid Date`, not an error). Every node's
            # `created_at` on the graph was affected, which is why the time
            # filter slider could never move, the frontend's own bounds
            # calculation filters out unparseable dates, so `min` and `max`
            # always collapsed to `Date.now()` regardless of any note's
            # actual date, on every single note in the notebook, not a rare
            # case. `/entries`, `/timeline` and everywhere else serialise
            # through Pydantic directly and were never affected, this was
            # the graph's own two hand-built dicts.
            "created_at": e.created_at.isoformat(),
            # What the map's size rule can read besides connections (INBOX
            # 430, View > Size: connections, length, recency or none): the
            # note's length in words, through the same readable text as the
            # preview so a private note is counted as its placeholder while
            # locked, and when it was last edited.
            "words": labels[e.id][1],
            "updated_at": (e.updated_at or e.created_at).isoformat(),
            # When a person last changed it (the hover card's Edited, INBOX
            # 1300 C11): `updated_at` also moves on the app's own writes.
            "edited_at": _iso_or_none(e.edited_at),
        }
        for e in entries
    ]

    edges: list[dict] = []
    taken: set[frozenset[int]] = set()  # pairs already connected

    types = manager.relation_types(session)
    for link in session.execute(
        select(
            EntryLink.id,
            EntryLink.source_entry_id,
            EntryLink.target_entry_id,
            EntryLink.reason,
            EntryLink.reason_confidence,
            EntryLink.link_type,
            EntryLink.two_way,
        )
    ):
        if link.source_entry_id in node_ids and link.target_entry_id in node_ids:
            pair = frozenset((link.source_entry_id, link.target_entry_id))
            if pair not in taken:
                taken.add(pair)
                edges.append(
                    {
                        "source": link.source_entry_id,
                        "target": link.target_entry_id,
                        "kind": "link",
                        # The link row's own id: asked for directly (a way
                        # to manage a reason from the graph itself, not only
                        # a note card's link chip). Without it, editing or
                        # removing a link from here had no id to act on.
                        "id": link.id,
                        "reason": link.reason,
                        # Set only when `reason` was deduced from embedding
                        # similarity rather than said in words, see
                        # EntryLink.reason_confidence.
                        "reason_confidence": link.reason_confidence,
                        # What kind of connection, when one was chosen. Fed
                        # through the same channel the render-time `kind`
                        # above already uses rather than a second one: the
                        # graph has always invented a kind per edge, and a
                        # real stored type belongs beside it, not parallel
                        # to it. Null on every link made before link types
                        # existed, which reads as the flat "related" the
                        # graph has always shown.
                        "link_type": link.link_type,
                        # INBOX 693: no arrow on a link that runs both ways
                        # (its own choice, else its type's direction).
                        "two_way": manager.is_two_way_link(link.two_way, link.link_type, types),
                    }
                )
                #: KG3: a typed link carries its name and inverse, for the
                #: map's words; an untyped one carries nothing more.
                kind = types.get(link.link_type or "")
                if kind:
                    edges[-1]["type_name"] = kind["name"]
                    edges[-1]["type_inverse"] = kind["inverse"]

    for e in entries:
        if e.parent_id is not None and e.parent_id in node_ids:
            pair = frozenset((e.parent_id, e.id))
            if pair not in taken:
                taken.add(pair)
                edges.append({"source": e.parent_id, "target": e.id, "kind": "thread"})

    config = deps.get_config()
    with_similarity = similarity and not config.get_preference("battery_efficient_mode")
    if with_similarity:
        edges.extend(_similarity_edges(session, node_ids, taken))

    #: The map's PageRank, shared with focus mode (`_centrality`); a warm call
    #: no longer builds an index at all.
    centrality_scores = _centrality(session, similarity, include_maps)

    # Stable category order so the frontend assigns stable colours.
    # Phase 5: degree per node, from the edges this payload carries, so a
    # client never has to count them itself (the colour rule, the label
    # priority and the local pane all read it).
    degree: dict[int, int] = {}
    for edge in edges:
        degree[edge["source"]] = degree.get(edge["source"], 0) + 1
        degree[edge["target"]] = degree.get(edge["target"], 0) + 1
    for node in nodes:
        node["degree"] = degree.get(node["id"], 0)
    categories = sorted({n["category"] for n in nodes})
    
    # Attach PageRank centrality to nodes for dynamic sizing
    for n in nodes:
        n["centrality"] = centrality_scores.get(n["id"], 0)

    # ROADMAP.md item 34: off by default (the frontend has to ask for it),
    # since every existing consumer of this endpoint assumes every node id
    # is an Entry id. An entity node's id is prefixed ("entity:5") so it can
    # never collide with one; the frontend's own node-shape code is what
    # tells the two apart, not a numeric range.
    if include_entities:
        _add_entity_nodes(session, nodes, edges, node_ids)

    # Tier 2 item 16: "documents in the graph", off by default, same reason
    # and same shape as include_entities just above (a document id is
    # prefixed so it can never collide with an Entry id, and every existing
    # consumer of this endpoint that assumes every node id is an Entry id
    # keeps working unasked). Edges come from DocumentLink, the many-to-many
    # note-document attachment table (§43/routes_documents.py): a document
    # already has a real connection to the notes it draws on; this is that
    # relationship rendered, not a new one invented for the graph.
    #
    # Deliberately not wired into centrality, similarity, or the trace-path
    # BFS (paths.build/_centrality) this pass: both are built entirely
    # around Entry, and extending either to a second node type is a
    # materially bigger, separate change from making a document visible and
    # connected in the first place.
    if include_documents:
        _add_document_nodes(session, nodes, edges, node_ids)
    #: **A mind map, and the notes it is made of** (MINDMAP_PLAN.md §5 item
    #: 13). This is the "decide once" call §3.3 makes and §5 item 13 restates:
    #: *a map's membership is a link; a node's position is not.* So the only
    #: thing added here is one edge per `note`-kind object on a map, never an
    #: x, never a y, never a parent-child edge between two topics (a topic is
    #: not a note and has no place in a graph of notes).
    #:
    #: **No new node is created**, and that is the difference between this and
    #: `include_entities` / `include_documents` just above. A board *is* an
    #: `Entry` (§2), so it is already in `nodes`, it has been on the graph
    #: since maps existed, drawn as an ordinary note whose text is `# My map`
    #: and connected to nothing. Adding a second `map:<id>` node would put the
    #: same object on the map twice. What was missing was that the node never
    #: said it was a map and its membership was invisible, so this marks the
    #: node and adds the edges.
    #:
    #: Opt-in for the reason the two above are: an existing consumer that
    #: assumes every edge joins two notes it retrieved is not wrong, and a map
    #: with forty notes on it would add forty edges to a picture nobody asked
    #: to change.
    if include_maps:
        _add_map_edges(session, entries, nodes, edges, node_ids, taken)
    # GRAPH_PLAN 514: opt-in, prefixed ids, outside centrality, as above.
    if include_tags:
        _add_tag_nodes(nodes, edges)
    if include_unresolved:
        _add_unresolved_nodes(session, entries, nodes, edges)
    if include_attachments:
        _add_attachment_nodes(session, nodes, edges, node_ids)

    #: A type's own colour, so "Note type" paints a Person the colour the
    #: person gave Person rather than the next one in the scheme.
    type_colours = {row.name: row.colour for row in session.scalars(select(NoteType)) if row.colour}
    # **Encoded here, on the worker thread** (audit 2026-10-05, ARCH-14).
    # A sync route's returned dict is encoded by FastAPI on the event loop
    # (py-spy: `serialize_response`), so a 2.4 MB graph at 5,000 notes held
    # every other request while it was turned into JSON. A response built
    # in the route is encoded where the route runs; `jsonable_encoder` is
    # what FastAPI would have applied, so the body is byte for byte the same.
    #: `type_colours`, read with the types above: a type's own colour (Note
    #: types), so the "Note type" rule paints a Meeting the colour the person
    #: gave it; a type without one falls to the calm scheme in the page.
    if slim:
        _slim(nodes, edges)
    payload = {"nodes": nodes, "edges": edges, "categories": categories, "type_colours": type_colours}
    #: **As it is first** (GRAPH_PLAN, the first build after a change). The
    #: payload is plain dicts, lists, strings and numbers, which
    #: `jsonable_encoder` walked value by value only to hand back unchanged:
    #: 213,459 calls, 0.96 s of a 1.95 s cold build at 5,000 notes (cProfile).
    #: `JSONResponse` encodes it as it stands, the same bytes; a value JSON
    #: cannot take (a date an optional layer left as an object) falls back to
    #: the encoder, as before.
    try:
        return JSONResponse(payload)
    except (TypeError, ValueError):
        return JSONResponse(jsonable_encoder(payload))


#: **The slim payload** (`/graph?slim=1`, the map's own read; GRAPH_PLAN
#: "Still open after KG1 to KG9", a slimmer node). Measured at 5,000 notes
#: (`scratchpad/kg1005_graph_bench.py`): 3.1 MB, of which about a third was
#: a value every note carries at its default and an unreasoned link's three
#: nulls, plus timestamps to the microsecond. A note node leaves out each key
#: at its default (the map's `graphFill`, graph.js, puts them back on
#: arrival, so nothing after the fetch reads a different shape), its times
#: are to the second and its centrality to six figures. Only note nodes and
#: link edges: an entity's, a document's or a tag's node keeps its own keys.
_NOTE_DEFAULTS = {
    "kind": "note",
    "note_type": None,
    "graph_pin_x": None,
    "graph_pin_y": None,
    "parent_id": None,
    "has_file": False,
    "pinned": False,
    "map_ids": [],
    "tags": [],
    "access_count": 0,
    "edited_at": None,
}
_LINK_DEFAULTS = ("reason", "reason_confidence", "link_type")


def _slim(nodes: list[dict], edges: list[dict]) -> None:
    for node in nodes:
        if node.get("kind") != "note":
            continue
        for key, default in _NOTE_DEFAULTS.items():
            if key in node and node[key] == default and type(node[key]) is type(default):
                del node[key]
        for key in ("created_at", "updated_at", "edited_at"):
            if isinstance(node.get(key), str) and "." in node[key]:
                head, _, tail = node[key].partition(".")
                node[key] = head + tail.lstrip("0123456789")
        if isinstance(node.get("centrality"), float):
            node["centrality"] = float(f"{node['centrality']:.6g}")
    for edge in edges:
        if edge.get("kind") == "link":
            for key in _LINK_DEFAULTS:
                if key in edge and edge[key] is None:
                    del edge[key]

def _load_entries(session: Session, ids) -> dict[int, Entry]:  # noqa: ANN001
    """The live notes with these ids, read in chunks (SQLite's variable cap)."""
    wanted = list(ids)
    found: dict[int, Entry] = {}
    for start in range(0, len(wanted), 500):
        rows = session.scalars(
            select(Entry).where(Entry.id.in_(wanted[start : start + 500]), Entry.is_deleted == False)  # noqa: E712
        )
        found.update((e.id, e) for e in rows)
    return found


def _local_topology(session: Session, similarity: bool) -> tuple[paths.Connections, dict, bool]:
    """Who is joined to whom, and which way each line runs, once per version.

    BACKLOG 29b item 4: focus mode loaded every note as an ORM object, built
    the whole notebook's index and walked every link again for direction, on
    every call, to draw a dozen notes. This is the same index built from
    columns only (`paths.build_light`) and kept like centrality and the
    similarity sweep are: one slot per `similarity` setting, keyed by the
    notebook fingerprint (and the embedding model when similarity is on, its
    edges being a function of both). A call then reads only the notes it draws.

    Neither the index nor the direction map is touched after it is built, so
    one value can be handed to concurrent requests.
    """
    use_similarity = similarity and not deps.get_config().get_preference("battery_efficient_mode")
    key = (*_graph_fingerprint(session), use_similarity)
    if use_similarity:
        key = (*key, deps.get_embeddings().backend_id())

    def build() -> tuple[paths.Connections, dict, bool]:
        extra_edges: list[dict] = []
        if use_similarity:
            node_ids = set(
                session.scalars(select(Entry.id).where(Entry.is_deleted == False))  # noqa: E712
            )
            extra_edges = _similarity_edges(session, node_ids, set())
        index = paths.build_light(session, extra_edges=extra_edges)
        #: Which way each link and thread runs. The index keeps one step per
        #: direction, so the stored row says which end wrote it (a thread runs
        #: from the note to its reply, as on `/graph`); tags and similarity
        #: have no direction and pass either switch.
        directed: dict[frozenset, tuple[int, int]] = {}
        for source, target in session.execute(
            select(EntryLink.source_entry_id, EntryLink.target_entry_id)
        ):
            directed.setdefault(frozenset((source, target)), (source, target))
        for entry in index.entries.values():
            if entry.parent_id in index.entries and entry.parent_id != entry.id:
                directed.setdefault(frozenset((entry.parent_id, entry.id)), (entry.parent_id, entry.id))
        return index, directed, bool(extra_edges)

    return _cached(f"local_topology_{use_similarity}", key, build)


@router.get("/graph/local/{entry_id}")
def graph_local(
    entry_id: int,
    # Unbounded before this: `?depth=999999999` ran the BFS loop below that
    # many times on a bare Python range(), no per-note work once the
    # frontier empties, but the loop itself still costs real wall-clock time
    # per iteration, and this server is single-worker (deps.py), so it stalls
    # every other request for however long that takes. 6 hops covers any
    # notebook a "local neighbourhood" view is meant for; Focus Mode never
    # asks for more than 2-3 today.
    depth: int = Query(default=2, ge=1, le=6),
    similarity: bool = False,
    # GRAPH_PLAN 514 (1), Obsidian's local graph switches: follow links into
    # the note, out of it, and draw the lines between notes at one distance.
    incoming: bool = True,
    outgoing: bool = True,
    neighbours: bool = True,
    session: Session = Depends(get_session)
) -> dict:
    """Focus Mode API: Gets the local neighborhood up to N degrees."""
    index, directed, _with_similarity = _local_topology(session, similarity)

    if entry_id not in index.entries:
        raise HTTPException(status_code=404, detail="No such note.")

    def oriented(a: int, b: int, kind: str) -> tuple[int, int]:
        if kind not in ("link", "thread"):
            return (a, b)
        return directed.get(frozenset((a, b)), (a, b))

    def allowed(a: int, ends: tuple[int, int], kind: str) -> bool:
        if kind not in ("link", "thread"):
            return incoming or outgoing
        return outgoing if ends[0] == a else incoming

    # BFS up to `depth`, keeping each note's distance from the centre.
    distance = {entry_id: 0}
    queue = [entry_id]
    edges = []
    taken = set()

    for level in range(depth):
        next_queue = []
        for n in queue:
            for neighbor, step in index.neighbours(n).items():
                ends = oriented(n, neighbor, step.kind)
                if not allowed(n, ends, step.kind):
                    continue
                pair = frozenset((n, neighbor))
                if pair not in taken:
                    taken.add(pair)
                    edges.append({"source": ends[0], "target": ends[1], "kind": step.kind})
                if neighbor not in distance:
                    distance[neighbor] = level + 1
                    next_queue.append(neighbor)
        queue = next_queue
        if not queue:
            break  # nothing left to expand, further iterations would be no-ops

    visited = set(distance)
    if neighbours:
        # The lines between notes at one distance that the walk never crossed
        # (two notes on the outer ring), whichever way they run.
        for n in visited:
            for neighbor, step in index.neighbours(n).items():
                pair = frozenset((n, neighbor))
                if neighbor in visited and pair not in taken and distance[n] == distance[neighbor]:
                    taken.add(pair)
                    ends = oriented(n, neighbor, step.kind)
                    edges.append({"source": ends[0], "target": ends[1], "kind": step.kind})
    else:
        edges = [e for e in edges if distance[e["source"]] != distance[e["target"]]]

    # The only notes read in full: the ones drawn (the index holds columns,
    # not text).
    drawn = _load_entries(session, visited)
    category_names = manager.bulk_category_names(session, list(drawn.values()))
    nodes = [
        {
            "id": e_id,
            "preview": _label(drawn[e_id]),
            "category": category_names.get(drawn[e_id].category_id, manager.UNCATEGORISED),
            "access_count": drawn[e_id].access_count,
            "pinned": drawn[e_id].pinned,
            # Same pin-restore field as the top-level /graph, see that
            # endpoint's own comment. Focus Mode is the other real place a
            # double-click pin can be made or seen, so it needs the same
            # persistence, not just the top-level map.
            "graph_pin_x": drawn[e_id].graph_pin_x,
            "graph_pin_y": drawn[e_id].graph_pin_y,
            "parent_id": drawn[e_id].parent_id if drawn[e_id].parent_id in visited else None,
            # See the other node-list above: `created_at` is already
            # timezone-aware (`core/database.DateTime` guarantees it), so
            # `+ "Z"` on top of `.isoformat()`'s own `+00:00` produced an
            # unparseable double-suffixed string in JavaScript.
            "created_at": drawn[e_id].created_at.isoformat(),
            # The size rule's numbers, as on the whole map (see `graph`).
            "words": _words(drawn[e_id]),
            "updated_at": (drawn[e_id].updated_at or drawn[e_id].created_at).isoformat(),
        }
        for e_id in visited
        if e_id in drawn
    ]
    
    #: The map's numbers, not this neighbourhood's (`_centrality`).
    centrality_scores = _centrality(session, similarity, False)
    for n in nodes:
        n["centrality"] = centrality_scores.get(n["id"], 0)

    categories = sorted({n["category"] for n in nodes})
    return {"nodes": nodes, "edges": edges, "categories": categories}


def _path_node(entry: Entry, category_names: dict[int | None, str]) -> dict:
    """One note on a path or in a structural list. The same shape the graph's
    nodes use, so the view can highlight by id without a second lookup, plus
    enough text to read a chain as a sentence when the graph is not on screen."""
    return {
        "id": entry.id,
        "preview": _label(entry, 60),
        "category": category_names.get(entry.category_id, manager.UNCATEGORISED),
    }


@router.get("/graph/structure")
def graph_structure(
    topics: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> dict:
    """The shape of the notebook: clusters, hubs and orphans (§9).

    One call, because all three come off the same index and the view wants them
    together: colouring by cluster and listing the orphans are the same
    question asked twice. `cluster_of` is what makes the colouring a lookup
    rather than a second traversal in JavaScript.
    """
    # GRAPH_PLAN Phase 5: computed once per version of the notebook. The
    # colour rule "cluster" asks for this on every render, and community
    # detection over a big notebook is the slowest thing the graph does.
    fingerprint = _graph_fingerprint(session)
    structure = _cached("structure", fingerprint, lambda: _build_structure(session))
    if not topics:
        return structure
    #: GRAPH_PLAN KG6: named topics inside the islands, asked for separately
    #: so the colour rule "cluster" pays nothing for them.
    found = _cached("topics", fingerprint, lambda: _build_topics(session))
    #: INBOX 547: the names the person gave, laid over after the cache, so a
    #: rename shows at once without recomputing a single topic.
    named = topic_finder.apply_names(
        found["topics"], deps.get_config().get_preference(TOPIC_NAMES_KEY, [])
    )
    return {**structure, **found, "topics": named}


#: The preference holding renamed topics: `[{"ids": [...], "name": "..."}]`.
TOPIC_NAMES_KEY = "graph_topic_names"


#: How many notes one `/graph/topics/of` asks about: a page of cards.
TOPICS_OF_IDS_MAX = 200


@router.get("/graph/topics/of")
def graph_topics_of(
    ids: str = Query(default="", description="Comma-separated note ids"),
    members: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> dict:
    """Each asked-for note's topic, named, for a note card's topic chip (the
    owner, 2026-10-10: "Should topics from the graph be more integrated app
    wide??"). The same cached topics as `/graph/structure?topics=1` with the
    renames laid over; a note in no topic is absent. Answered under `topics`
    in the shape the cards' batched counts read (`CARD_COUNT_SOURCES`)."""
    wanted = [int(part) for part in ids.split(",") if part.strip().isdigit()][:TOPICS_OF_IDS_MAX]
    if not wanted:
        return {"topics": {}}
    fingerprint = _graph_fingerprint(session)
    found = _cached("topics", fingerprint, lambda: _build_topics(session))
    named = topic_finder.apply_names(
        found["topics"], deps.get_config().get_preference(TOPIC_NAMES_KEY, [])
    )
    by_id = {topic["id"]: topic for topic in named}
    out = {}
    for note in wanted:
        topic = by_id.get(found["topic_of"].get(str(note)))
        if topic is not None:
            row = {"id": topic["id"], "name": topic["name"], "size": topic["size"]}
            #: A note's panel renames its topic, which is stored by the notes.
            if members:
                row["ids"] = topic["ids"]
            out[str(note)] = row
    return {"topics": out}


class TopicNameBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=5000)
    name: str = Field(default="", max_length=80)


@router.put("/graph/topics/name")
def name_topic(body: TopicNameBody) -> dict:
    """Give a topic a name of your own, or clear it to get the found one back
    (INBOX 547). Stored by the topic's notes, which are all a recomputed
    topic can be recognised by (`topics.apply_names`)."""
    name = " ".join(body.name.split())
    config = deps.get_config()
    stored = config.get_preference(TOPIC_NAMES_KEY, [])
    config.set_preference(TOPIC_NAMES_KEY, topic_finder.store_name(stored, body.ids, name))
    return {"name": name}


class TopicSummaryBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=5000)
    name: str = Field(default="", max_length=200)
    terms: list[Annotated[str, Field(max_length=200)]] = Field(default_factory=list, max_length=10)


def _extractive_summary(session: Session, rows: list, readable: list, terms: list[str]) -> str:
    """The no-model summary: shared terms, the date span, and the opening
    lines of the two most-linked readable notes (a private note lends nothing)."""
    stamps = [e.created_at for e in rows if e.created_at]
    leads: list[str] = []
    if readable:
        index = paths.build_light(session)
        ranked = sorted(readable, key=lambda e: (-paths.degree(index, e.id), e.id))
        leads = [manager.plain_label(e.content, 60) for e in ranked[:2]]
    return topic_finder.extractive_sentence(
        len(rows), terms, min(stamps) if stamps else None, max(stamps) if stamps else None, leads
    )


@router.post("/graph/topics/summary")
def topic_summary(body: TopicSummaryBody, session: Session = Depends(get_session)) -> dict:
    """One sentence about a topic's notes, on demand (GRAPH_PLAN KG6).

    The local model reads the titles and opening lines of a dozen of its
    readable notes; the answer is cached by the members and their versions,
    so an edit to one asks again and nothing else does. With no model, or a
    model that fails, the answer is the terms the notes share
    (`topics.terms_sentence`), never an error, and that answer is not cached,
    so the model is asked again next time. Cancelling is the browser's: an
    abandoned request still caches what it got, for the next ask.
    """
    rows = list(
        session.scalars(select(Entry).where(Entry.id.in_(body.ids), Entry.is_deleted.is_(False)))
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Those notes could not be found.")
    readable = sorted((e for e in rows if not e.is_private), key=lambda e: e.id)
    key = tuple((e.id, str(e.updated_at or e.created_at)) for e in readable)
    with _cache_lock:
        hit = _summaries.get(key)
    if hit:
        return {"summary": hit, "source": "model", "cached": True}
    ollama = deps.get_ollama()
    if not readable or not ollama.is_running():
        return {"summary": _extractive_summary(session, rows, readable, body.terms), "source": "terms", "cached": False}
    lines = []
    for entry in readable[: topic_finder.SUMMARY_NOTES]:
        text = " ".join(manager.readable_content(entry).split())
        lines.append(f"- {text[: topic_finder.SUMMARY_CHARS]}")
    hint = f"They share: {', '.join(body.terms[:5])}.\n" if body.terms else ""
    try:
        reply = ollama.chat(
            deps.get_model_manager().utility_model(),
            [
                {"role": "system", "content": topic_finder.SUMMARY_SYSTEM},
                {"role": "user", "content": f"{hint}The notes:\n" + "\n".join(lines)},
            ],
        )
        summary = " ".join(str(reply.get("content") or "").split()).strip("\"' ")
    except Exception:  # noqa: BLE001  # any model failure reads as "no model"
        summary = ""
    if not summary:
        return {"summary": _extractive_summary(session, rows, readable, body.terms), "source": "terms", "cached": False}
    summary = summary[:300]
    with _cache_lock:
        _summaries[key] = summary
        while len(_summaries) > SUMMARY_CACHE_MAX:
            _summaries.pop(next(iter(_summaries)))
    return {"summary": summary, "source": "model", "cached": False}


_TITLE_WORD = re.compile(r"[^\W\d_][\w'-]{3,}")


def _build_topics(session: Session) -> dict:
    """`entry/topics.build` over the same index as the clusters, with each
    readable note's tags, entities and title words as the naming terms. A
    private note is in a topic (its links are not secret) and lends no word."""
    from tessellate.core.database import Entity, EntityMention
    from tessellate.search.query import STOPWORDS

    index = paths.build(session)
    terms_of: dict[int, set[tuple[str, str]]] = {}
    titles: dict[int, str] = {}
    for entry in index.entries.values():
        if entry.is_private:
            continue
        terms = {("tag", tag.lower()) for tag in _tags_of(entry)}
        titles[entry.id] = manager.plain_label(entry.content, 80)
        for word in _TITLE_WORD.findall(titles[entry.id].lower()):
            if word not in STOPWORDS:
                terms.add(("word", word))
        terms_of[entry.id] = terms
    for name, entry_id in session.execute(
        select(Entity.name, EntityMention.entry_id).join(Entity, Entity.id == EntityMention.entity_id)
    ):
        if entry_id in terms_of and name and name.strip():
            terms_of[entry_id].add(("entity", name.strip()))
    found = topic_finder.build(index, terms_of, titles)
    topic_of = {str(node): topic["id"] for topic in found for node in topic["ids"]}
    return {"topics": found, "topic_of": topic_of}


def _build_structure(session: Session) -> dict:
    index = paths.build(session)
    category_names = manager.bulk_category_names(session, list(index.entries.values()))

    def category_of(entry: Entry) -> str:
        return category_names.get(entry.category_id, manager.UNCATEGORISED)

    groups = paths.clusters(index, category_of)
    cluster_of: dict[str, int] = {}
    for position, cluster in enumerate(groups):
        for note_id in cluster.ids:
            # String keys: this is JSON, where an object's keys are strings
            # whatever they started as, and a client reading `cluster_of[id]`
            # with a numeric id gets undefined. Being explicit here beats
            # discovering it in the browser.
            cluster_of[str(note_id)] = position

    loose = paths.orphans(index)
    return {
        "notes": len(index.entries),
        "connected": len(index.entries) - len(loose),
        "clusters": [
            {
                "size": len(cluster.ids),
                "core": _path_node(index.entries[cluster.core_id], category_names),
                "categories": cluster.categories[:3],
                "ids": cluster.ids,
            }
            for cluster in groups
            if len(cluster.ids) >= paths.MIN_CLUSTER_NOTES
        ],
        # Counted separately rather than listed: a notebook with thirty pairs
        # is a different shape from one with two big clusters, and that fact is
        # worth a number even though the pairs are not worth thirty rows.
        "small_clusters": sum(
            1 for cluster in groups if len(cluster.ids) < paths.MIN_CLUSTER_NOTES
        ),
        "cluster_of": cluster_of,
        "hubs": [
            {**_path_node(index.entries[note_id], category_names), "links": count}
            for note_id, count in paths.hubs(index)
        ],
        "orphans": [_path_node(index.entries[note_id], category_names) for note_id in loose[:20]],
        "orphan_count": len(loose),
        "hub_tags": index.hub_tags,
    }


@router.get("/graph/path")
def graph_path(
    source: int,
    target: int,
    similarity: bool = False,
    routes: int = paths.MAX_ALTERNATE_PATHS,
    session: Session = Depends(get_session),
) -> dict:
    """The chain of connections between two notes (§9).

    The one question a graph answers better than a list, and the one the view
    could not answer: *how are these two related?* Returns the notes in order
    with the reason for each step, or `found: false` and: this is the part
    that makes it usable, **why** there is no path, since "no" is only a
    useful answer when it says what to do about it.

    Deliberately a GET with two ids: it reads nothing but the notebook's own
    structure, so it is cacheable, linkable and safe to re-issue.

    `similarity=true` additionally lets the chain hop along "these read alike"
    edges, which finds a route between notes nothing actually connects. It is
    opt-in and off by default for two reasons: it costs a full vector sweep of
    the notebook, which is not what "cacheable and safe to re-issue" above
    describes; and a path made of similarity edges answers a weaker question
    than the one asked, `SIMILAR_WEIGHT` makes them the last resort within a
    route, but a route made only of them is "these are both about cooking"
    dressed up as a connection the user made.
    """
    extra_edges = []
    if similarity and not deps.get_config().get_preference("battery_efficient_mode"):
        node_ids = set(
            session.scalars(
                select(Entry.id).where(Entry.is_deleted == False)  # noqa: E712
            )
        )
        extra_edges = _similarity_edges(session, node_ids, set())

    index = paths.build(session, extra_edges=extra_edges)
    missing = [
        note_id for note_id in (source, target) if note_id not in index.entries
    ]
    if missing:
        return {
            "found": False,
            "source": source,
            "target": target,
            "reason": (
                "That note isn't in the map, it may have been deleted."
                if len(missing) == 1
                else "Neither note is in the map."
            ),
        }
    if source == target:
        return {
            "found": False,
            "source": source,
            "target": target,
            "reason": "Those are the same note.",
        }

    #: Asked for directly: "allow for multiple paths to be displayed if they
    #: exist." `find_many`'s first entry *is* `find`'s answer: they share one
    #: Dijkstra: so the single-path shape below is unchanged and the extras
    #: ride alongside it. `routes=1` gets the old behaviour exactly, for a
    #: caller that does not want to pay for the alternatives.
    wanted = max(1, min(int(routes or 1), paths.MAX_ALTERNATE_PATHS))
    chains = paths.find_many(index, source, target, limit=wanted)
    chain = chains[0] if chains else None
    if chain is None:
        ends = [
            (note_id, paths.degree(index, note_id)) for note_id in (source, target)
        ]
        lonely = [note_id for note_id, count in ends if count == 0]
        if lonely:
            reason = (
                "Neither note is connected to anything yet."
                if len(lonely) == 2
                else "One of these notes isn't connected to anything yet."
            )
        else:
            reason = (
                "They're both connected to other notes, but there's no route "
                f"between them within {paths.MAX_PATH_HOPS} steps."
            )
        if index.hub_tags:
            # Said plainly, because otherwise this reads as a wrong answer: the
            # two notes may well share a tag and still get "no path" back.
            listed = ", ".join("#" + tag for tag in index.hub_tags[:3])
            reason += (
                f" Tags on more than {paths.HUB_TAG_NOTES} notes ({listed}) are "
                "treated as filing rather than as a connection."
            )
        return {
            "found": False,
            "source": source,
            "target": target,
            "reason": reason,
        }

    #: Every note on *any* of the routes, named once. `bulk_category_names` is
    #: a query, so calling it per route would issue three where one does.
    everywhere: list[int] = []
    for one in chains:
        for note_id in [source] + [step.target for step in one]:
            if note_id not in everywhere:
                everywhere.append(note_id)
    category_names = manager.bulk_category_names(
        session, [index.entries[note_id] for note_id in everywhere]
    )

    also = _hop_reasons(session, index, [(step.source, step.target) for one in chains for step in one])

    def rendered(one: list) -> dict:
        order = [source] + [step.target for step in one]
        return {
            "hops": len(one),
            "cost": sum(step.weight for step in one),
            "nodes": [
                _path_node(index.entries[note_id], category_names) for note_id in order
            ],
            "steps": [
                {
                    "source": step.source,
                    "target": step.target,
                    "kind": step.kind,
                    "how": step.how,
                    "also": also.get((step.source, step.target), []),
                }
                for step in one
            ],
        }

    routes_out = [rendered(one) for one in chains]
    best = routes_out[0]
    return {
        "found": True,
        "source": source,
        "target": target,
        #: The best route, spelled at the top level exactly as it always was, 
        #: every existing caller and test reads `nodes`/`steps`/`hops` from
        #: here, and moving them into `routes[0]` would be a breaking change
        #: for no gain.
        "hops": best["hops"],
        "nodes": best["nodes"],
        "steps": best["steps"],
        #: …and all of them, best first. Always at least one element when
        #: `found` is true, so the UI has one shape to render rather than two.
        "routes": routes_out,
    }


def _hop_reasons(session: Session, index: paths.Connections, pairs: list[tuple[int, int]]) -> dict:
    """GRAPH_PLAN KG8: every structural reason each hop's two notes relate,
    beside the edge the route took (`relations.explain_pair`, the sentences
    the link suggestions use). Nothing for a hop with a private end: its tags
    and entities come from its text."""
    from tessellate.ai import relations
    from tessellate.core.database import Entity, EntityMention

    readable = {
        node: entry for node, entry in index.entries.items() if not entry.is_private
    }
    wanted = {node for pair in pairs for node in pair if node in readable}
    if not wanted:
        return {}
    notes = {
        node: relations.NoteFacts(
            label=manager.plain_label(entry.content, 40) or "Untitled note",
            tags=frozenset(tag.lower() for tag in _tags_of(entry)),
        )
        for node, entry in readable.items()
    }
    neighbours: dict[int, set[int]] = {}
    for node, steps in index.edges.items():
        for other, step in steps.items():
            if step.kind in ("link", "thread"):
                neighbours.setdefault(node, set()).add(other)
    entity_ids = set(session.scalars(select(EntityMention.entity_id).where(EntityMention.entry_id.in_(wanted))))
    entity_notes: dict[str, set[int]] = {}
    if entity_ids:
        for name, entry_id in session.execute(
            select(Entity.name, EntityMention.entry_id)
            .join(Entity, Entity.id == EntityMention.entity_id)
            .where(EntityMention.entity_id.in_(entity_ids))
        ):
            entity_notes.setdefault((name or "").strip(), set()).add(entry_id)
    return {
        (a, b): relations.explain_pair(a, b, notes, neighbours, entity_notes)
        for a, b in pairs
        if a in readable and b in readable
    }


class PinBody(BaseModel):
    # Both set or both null, never one alone. `x`/`y` rather than reusing
    # `graph_pin_x`/`graph_pin_y` verbatim: the column names carry "graph_"
    # because they live on the shared `Entry` table, but this endpoint is
    # already scoped to the graph by its own path.
    #: No NaN or infinity: SQLite keeps an infinity, and the graph's response
    #: then cannot be encoded, so one bad pin broke the whole tab.
    x: bounds.PinCoord | None = None
    y: bounds.PinCoord | None = None


def _pin_target(node_id: object) -> tuple[str, int] | None:
    """`("", note id)` or `("document", id)` for a drawn node id, else None.
    ASCII digits only and a length an id can have: `str.isdigit` is true for
    "²" and `int` then raises, and a 30-digit number overflows SQLite."""
    kind, _, number = str(node_id).rpartition(":")
    if kind not in ("", "document") or not number.isascii() or not number.isdigit() or len(number) > 15:
        return None
    return kind, int(number)


@router.put("/graph/pin/{node_id}")
def pin_node(
    node_id: str, body: PinBody, session: Session = Depends(get_session)
) -> dict:
    """Hold a node in place, or release it, the persistence half of the
    Graph tab's double-click pin (graph.js), which used to live only on the
    in-memory D3 node object and vanish the moment `/graph` was refetched
    (ROADMAP §87.1's own audit named this gap directly).

    `node_id` is the id the graph draws: a note's number, or `document:N`
    for a document node (B78: `PUT /graph/pin/document:2` was a 422 because
    the path was an integer). Those are the two with a row to keep a pin on;
    a tag, an entity or a file is refused with a plain 404 rather than
    accepted and forgotten.

    `x`/`y` both null clears the pin; both set pins it there. One set and
    one null is refused rather than silently coerced, a lone coordinate is
    not a position, and guessing which axis was meant would be worse than
    asking again.
    """
    if (body.x is None) != (body.y is None):
        raise HTTPException(
            status_code=400, detail="A pin needs both x and y, or neither."
        )
    target = _pin_target(node_id)
    if target is None:
        raise HTTPException(status_code=404, detail="That node cannot be pinned.")
    kind, number = target
    if kind == "document":
        document = session.get(Document, number)
        if document is None or document.deleted_at is not None:
            raise HTTPException(status_code=404, detail="No such document.")
        document.graph_pin_x = body.x
        document.graph_pin_y = body.y
        session.commit()
        return {"id": node_id, "graph_pin_x": document.graph_pin_x, "graph_pin_y": document.graph_pin_y}
    entry = session.get(Entry, number)
    if entry is None or entry.is_deleted:
        raise HTTPException(status_code=404, detail="No such note.")
    entry.graph_pin_x = body.x
    entry.graph_pin_y = body.y
    session.commit()
    return {"id": entry.id, "graph_pin_x": entry.graph_pin_x, "graph_pin_y": entry.graph_pin_y}


class PinRow(BaseModel):
    #: A note's number, or `document:N` for a document node (B78); the topic
    #: "Document" is a ring of them, so a drag of it carries both kinds.
    id: int | str
    x: bounds.PinCoord
    y: bounds.PinCoord


class PinsBody(BaseModel):
    pins: list[PinRow] = Field(min_length=1, max_length=5000)


@router.put("/graph/pins")
def pin_nodes(body: PinsBody, session: Session = Depends(get_session)) -> dict:
    """Pin several nodes in one write: a topic dragged by its name moves and
    pins every member (the owner, 2026-10-10: "I want to be able to drag
    whole topics around on the graph"), which was one `PUT /graph/pin` a
    member. Both coordinates are required here (a release is `pin_node` or
    Unpin all), and a node that is gone, or has no row to keep a pin on, is
    skipped rather than failing the rest."""
    notes: dict[int, PinRow] = {}
    documents: dict[int, PinRow] = {}
    for row in body.pins:
        target = _pin_target(row.id)
        if target is None:
            continue
        kind, number = target
        (notes if kind == "" else documents)[number] = row
    entries = (
        session.query(Entry)
        .filter(Entry.id.in_(notes), Entry.is_deleted == False)  # noqa: E712
        .all()
    )
    for entry in entries:
        entry.graph_pin_x = notes[entry.id].x
        entry.graph_pin_y = notes[entry.id].y
    held = (
        session.query(Document)
        .filter(Document.id.in_(documents), Document.deleted_at.is_(None))
        .all()
    )
    for document in held:
        document.graph_pin_x = documents[document.id].x
        document.graph_pin_y = documents[document.id].y
    session.commit()
    return {"pinned": len(entries) + len(held)}


@router.post("/graph/unpin-all")
def unpin_all_nodes(session: Session = Depends(get_session)) -> dict:
    """Release every pinned node at once, direct instruction: "I want to be
    able to unroot and reset the graph to free float if I want with a
    button." `pin_node` above only ever clears one note at a time, which is
    fine for the drag-to-place gesture it serves but not for "start over,"
    which would otherwise mean tracking down and double-clicking every
    pinned node individually.

    Scoped by the ordinary session (the same `WorkspaceMixin` scoping every
    other query in this app already gets) rather than an explicit
    workspace filter here: this route has no more reason to reach across
    spaces than `pin_node` above does.
    """
    pinned = (
        session.query(Entry)
        .filter(Entry.is_deleted == False, Entry.graph_pin_x.is_not(None))  # noqa: E712
        .all()
    )
    held = (
        session.query(Document)
        .filter(Document.deleted_at.is_(None), Document.graph_pin_x.is_not(None))
        .all()
    )
    # Every pin cleared, documents and nodes a filter hides included, so the
    # Undo puts back exactly what this released (K9, K10).
    released = [{"id": e.id, "x": e.graph_pin_x, "y": e.graph_pin_y} for e in pinned]
    released += [{"id": f"document:{d.id}", "x": d.graph_pin_x, "y": d.graph_pin_y} for d in held]
    for row in (*pinned, *held):
        row.graph_pin_x = None
        row.graph_pin_y = None
    session.commit()
    return {"unpinned": len(released), "released": released}
