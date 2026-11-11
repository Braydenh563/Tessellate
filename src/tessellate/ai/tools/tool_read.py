"""The tools that read the notebook: search, get, graph and related notes, lists, counts, structure, time, the guide.

Moved whole from `__init__.py` (audit AR3, gods-2): the code is unchanged, and
`__init__` re-exports every name here that anything reads. Imports run one way,
down the layer list in `__init__.py`'s docstring, never back to `__init__`.
"""

from __future__ import annotations

from tessellate.core.database import Category, Entry, LIKE_ESCAPE, like_escape
from tessellate.ai.tools._common import DEFAULT_CONTEXT_TOKENS, DEFAULT_LIST_LIMIT, FULL_NOTE_CHARS, MAX_LIST_LIMIT, PREVIEW_CHARS, SEARCH_CONTEXT_SHARE, SUMMARY_NOTE_LIMIT, _READ_MORE, _category_clause, _clip, _limit_arg, _note_summary, _readable, _require_note, _since_clause, _since_days, _span_not_category, _visible
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_, select
from tessellate.core import deps
from tessellate.entry import link_wording, manager, paths
from tessellate.ai import note_rank
from tessellate.search import search_manager
from tessellate.entry.properties import strip as strip_properties
from datetime import timedelta
from tessellate.ai.tools.tool_list_page import describe_filters, page_of_notes, unknown_category_hint

# --- handlers (session, args) -> result dict -----------------------------------
# Results always include a human "label" on success; the UI shows it
# inline in the chat ("Created “Milk and eggs” in Shopping").


def _named(entry: Entry) -> str:
    """A note as a tool label says it: its title in quotes, never its id
    (audit 1029 C47: "Done: added to Favourites: note #29")."""
    return f"“{link_wording.title(entry.content or '', limit=48) or 'Untitled note'}”"


def _search_notes(session: Session, args: dict) -> dict:
    # A big window earns more results than the flat five this used to return, 
    # a 32k model reading five previews is the tool being timid, and the model
    # then pages through with repeated calls it does not need.
    #
    # But it earns *more*, not *unbounded*. The first version of this scaled
    # the ceiling with the window too (`max_limit = default * 2`), so a 128k
    # model's search could return 768 previews, about 38k tokens of notes for
    # one call, which is not a search result, it is the notebook. Only the
    # default moves; MAX_LIST_LIMIT stays the ceiling it was written to be.
    ctx = args.get("__context_tokens__") or DEFAULT_CONTEXT_TOKENS
    earned = int((ctx * SEARCH_CONTEXT_SHARE * CHARS_PER_TOKEN) / PREVIEW_CHARS)
    default = min(max(5, earned), MAX_LIST_LIMIT)
    limit = _limit_arg(args, default=default)
    found = search_manager.retrieve_detailed(
        session, str(args["query"]), deps.get_embeddings(), limit=limit
    )
    notes = []
    #: The same order Ask lists in (audit 1029 C20), unless the search gave the newest.
    entries = found.entries if found.mode == "recent" else note_rank.lead(found.entries, str(args["query"]))
    for entry in entries:
        summary = _note_summary(session, entry)
        if entry.id in found.connected_ids:
            # **Why this note is here.** It did not match the search, it is
            # connected to something that did. Without saying so the model
            # reports it as a result, which is a quiet fabrication: the user
            # asked about X and is told a note about Y "came up", when what
            # actually happened is that they once linked the two.
            summary["why"] = "not a match: connected to one of the matches above"
        notes.append(summary)
    result = {
        "found": len(found.entries),
        "search_mode": found.mode,
        "notes": notes,
        "how_to_read_more": _READ_MORE,
        "label": f"ph:magnifying-glass Searched notes for “{_clip(str(args['query']), 40)}”",
    }
    if found.when_phrase:
        # The question carried a date range and it was applied. Said out loud
        # so the model does not answer "you have no notes about that" when the
        # truthful answer is "none in that week".
        result["filtered_by_date"] = (
            f"Only notes written {found.when_phrase} were considered"
            + (f" ({found.since} to {found.until})" if found.since else "")
            + ". Say so if the answer is that there are none in that period."
        )
    return result


def _get_note_tool(session: Session, args: dict) -> dict:
    """One note, in full. The only tool that returns whole text, which is
    exactly why it takes an id and reads one note at a time."""
    entry = _require_note(session, args)
    result = _note_summary(session, entry, chars=FULL_NOTE_CHARS)
    result["links"] = [
        other.id for _link, other in manager.links_for_entry(session, entry)
    ]
    result["label"] = f"ph:file-text Read {_named(entry)} in full"
    return result


# How far `related_notes` will walk, and how much it may bring back. A
# neighbourhood is only useful if it fits in the prompt beside everything else,
# and the second hop of a well-connected note can be most of the notebook.
MAX_GRAPH_DEPTH = 2
MAX_GRAPH_NOTES = 12


# How much of a neighbour's text comes back. Shorter than `PREVIEW_CHARS`
# deliberately: a graph walk returns up to twelve notes at once, and its job is
# to say *what connects to what*, the model calls `get_note` on the one that
# turns out to matter. At 200 characters each, twelve neighbours cost ~1,230
# tokens, a third of a 4k window for a single tool result.
GRAPH_PREVIEW_CHARS = 90


def _graph_summary(session: Session, entry: Entry, how: str, hops: int, via: int | None) -> dict:
    """One neighbour, in the smallest shape that is still useful.

    A trimmed `_note_summary` rather than the whole thing, and every field left
    out was left out for a reason:

    - **`created_at`**, a 32-character ISO timestamp on every row, to answer a
      question ("when was this written?") that a graph walk is not asking.
    - **`pinned`, `truncated`**, a boolean each, true for almost none of them.
    - **`via` when it is `None`**, every one-hop result carried a null field
      naming the note it hung off, which for one hop is the note you asked
      about.
    - **`tags` when empty**: an empty list per row is pure structure.

    Together these were roughly half the payload. What remains is what the
    model needs to decide which neighbour to read in full.
    """
    text = _readable(entry)
    summary = {
        "id": entry.id,
        "preview": _clip(strip_properties(text).lstrip(), GRAPH_PREVIEW_CHARS),
        "category": manager.category_name_for(session, entry),
        "how": how,
        "hops": hops,
    }
    tags = manager.entry_tags(entry)
    if tags:
        summary["tags"] = tags
    if via is not None:
        summary["via"] = via
    return summary


def _graph_neighbours(session: Session, entry: Entry) -> list[tuple[Entry, str]]:
    """This note's direct neighbours, each with *how* it is connected.

    The "how" is the whole point, and it is what the app had and the model
    didn't. The graph view has drawn typed edges, an explicit link, a reply
    thread, a similarity line, since it was built, but the only thing the
    agent could see was `get_note`'s bare list of connected ids: a set of
    numbers with no indication of what any of them meant, one note at a time.

    Three kinds, deliberately, and no fourth:

    - **linked**: someone (or the model) said these two belong together. The
      strongest signal in the notebook, because it was a decision.
    - **thread**: a reply, so the two are one train of thought.
    - **tag**: a shared tag, named in the answer, so "shares #recipes" reads
      differently from "you linked these".

    *Same category* is not here. Nearly every note shares a category with
    dozens of others, so including it would drown the two signals that mean
    something under one that means "these are both notes".
    """
    seen: dict[int, str] = {}
    out: list[tuple[Entry, str]] = []

    def add(other: Entry, how: str) -> None:
        # First reason wins, and the order below is strongest-first, so a note
        # that is both linked and tagged reports the link.
        if other.id == entry.id or other.id in seen or other.is_deleted:
            return
        seen[other.id] = how
        out.append((other, how))

    for link, other in manager.links_for_entry(session, entry):
        # A link's own reason, when someone gave one, "a note about uni and
        # gym might still be related if they're both about scheduling"
        # (user-reported) is exactly the kind of connection that reads as
        # arbitrary without it. Optional, so "linked" alone is still the
        # honest answer for the (more common) case nobody explained.
        add(other, f"linked ({link.reason})" if link.reason else "linked")

    if entry.parent_id:
        parent = session.get(Entry, entry.parent_id)
        if parent is not None:
            add(parent, "thread: this is a reply to it")
    for child in session.scalars(
        select(Entry).where(Entry.parent_id == entry.id, Entry.is_deleted == False)  # noqa: E712
    ):
        add(child, "thread: it is a reply to this")

    tags = set(manager.entry_tags(entry))
    if tags:
        # `_related_notes` calls this once per node in its BFS frontier (up
        # to ~12 at depth 2), and it used to fetch every non-deleted `Entry`
        #, the whole table, `content` included, on every one of those
        # calls just to check its tags (ROADMAP.md Tier 1 item 8). `tags` is
        # a JSON text column with no per-tag index, so a SQL filter can only
        # narrow candidates, not resolve the match exactly, `ilike` (same
        # pre-filter `list_tags`/`_count_notes` already use elsewhere in this
        # file) rules out rows whose raw JSON can't possibly contain the tag,
        # and the exact per-entry check below removes any substring false
        # positive it lets through ("art" also matching "cart").
        #
        # Matching is case-insensitive throughout, and *consistently* so. An
        # earlier version keyed an index by `tag.lower()` but then
        # intersected the lowercased tags of the candidate with this note's
        # tags at their original case, so two notes sharing "#Work" matched
        # the index, produced an empty intersection, and were reported as
        # unrelated. Lowercase is the key; `folded` keeps a display form.
        folded = {t.lower(): t for t in tags}
        candidates = select(Entry).where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.id != entry.id,
            or_(*(Entry.tags.ilike(f"%{like_escape(t)}%", escape=LIKE_ESCAPE) for t in tags)),
        )
        for other in session.scalars(candidates):
            shared = {
                folded[t.lower()]
                for t in manager.entry_tags(other)
                if t.lower() in folded
            }
            if shared:
                add(other, f"shares {', '.join('#' + s for s in sorted(shared))}")
    return out


# How alike two notes must read before the graph calls them *potentially*
# connected. Deliberately higher than the graph view's own threshold: a picture
# can afford a speculative line the eye discards, and a tool result cannot, 
# the model treats whatever it is handed as fact worth acting on.
SUGGESTED_LINK_THRESHOLD = 0.62
MAX_SUGGESTED_LINKS = 5


def _suggested_neighbours(session: Session, entry: Entry, exclude: set[int]) -> list[dict]:
    """Notes that *read* like this one but were never connected to it.

    The connections above are facts, somebody made them. These are guesses,
    and they are labelled as guesses all the way to the model, because the
    interesting use of this tool is "what have I written that belongs together
    and isn't linked yet" and the answer to that must not come back looking
    like an answer to "what is linked".

    Costs one embedding comparison per note, so it is opt-in per call rather
    than always-on: an ordinary "what connects to this" question should not pay
    for a similarity sweep it did not ask for.
    """
    from tessellate.ai.embeddings import bytes_to_vector, cosine_similarity
    from tessellate.core.database import EmbeddingRecord
    from tessellate.core import deps

    embeddings = deps.get_embeddings()
    backend = embeddings.backend_id()
    stored = {
        record.entry_id: record.embedding
        for record in session.scalars(
            select(EmbeddingRecord).where(EmbeddingRecord.model_version == backend)
        )
    }
    # No vector for this note means it was never embedded (the backend was off
    # when it was written, or has changed since). Nothing to compare against,
    # and guessing from keywords here would quietly change what the tool means.
    if entry.id not in stored:
        return []
    vector = bytes_to_vector(stored[entry.id])

    # Score against the raw vectors first, pure numpy, no database at all , 
    # and only fetch an `Entry` for a candidate that already cleared the
    # threshold. The old order fetched every embedded note's `Entry` before
    # checking its score, which is a `session.get()` per note in the whole
    # notebook regardless of how few ever pass; ANALYSIS.md §34's scale-test
    # measured that as the dominant cost of this call at 10k notes (~4s for
    # one tool invocation). Same filtering, same threshold, same order, 
    # just cheap-check-before-expensive-fetch.
    scored = []
    for other_id, blob in stored.items():
        if other_id == entry.id or other_id in exclude:
            continue
        score = cosine_similarity(vector, bytes_to_vector(blob))
        if score >= SUGGESTED_LINK_THRESHOLD:
            scored.append((score, other_id))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    results = []
    for score, other_id in scored:
        other = session.get(Entry, other_id)
        if other is None or other.is_deleted or other.is_private:
            continue
        results.append(
            _graph_summary(
                session, other, f"reads similarly ({score:.0%}): NOT linked yet", 0, None
            )
        )
        if len(results) >= MAX_SUGGESTED_LINKS:
            break
    return results


def _walk_neighbourhood(session: Session, entry: Entry, depth: int) -> tuple[list[dict], set[int]]:
    """Breadth-first out from `entry`, nearest first, stopping at the cap: the summaries and the ids seen."""
    frontier = [entry]
    visited = {entry.id}
    found: list[dict] = []
    for distance in range(1, depth + 1):
        next_frontier: list[Entry] = []
        for node in frontier:
            for other, how in _graph_neighbours(session, node):
                if other.id in visited:
                    continue
                visited.add(other.id)
                next_frontier.append(other)
                found.append(
                    _graph_summary(
                        session,
                        other,
                        how,
                        distance,
                        # Which note it hangs off, so a two-hop result is not
                        # mysteriously floating. Omitted at one hop, where the
                        # answer is always the note you asked about.
                        via=node.id if node.id != entry.id else None,
                    )
                )
                if len(found) >= MAX_GRAPH_NOTES:
                    break
            if len(found) >= MAX_GRAPH_NOTES:
                break
        if len(found) >= MAX_GRAPH_NOTES:
            break
        frontier = next_frontier
        if not frontier:
            break
    return found, visited


def _related_notes(session: Session, args: dict) -> dict:
    """The neighbourhood around one note, as context rather than as a picture.

    Breadth-first so the nearest notes arrive first and the cap cuts the
    furthest, which is the right thing to lose. Every result says how far away
    it is and how it got there, so the model can weigh "you linked these" above
    "these share a tag two hops out" instead of treating a flat list as equally
    relevant.
    """
    entry = _require_note(session, args)
    depth = max(1, min(MAX_GRAPH_DEPTH, int(args.get("depth") or 1)))

    found, visited = _walk_neighbourhood(session, entry, depth)

    result = {
        "note_id": entry.id,
        "related": found,
        # Deliberately no `how_to_read_more` paragraph here. Every other
        # reading tool carries one, and repeating it in a result that already
        # holds twelve rows spends tokens restating something the previews
        # themselves imply: each row is 90 characters and an id.
        "label": (
            f"ph:graph Found {len(found)} note{'' if len(found) == 1 else 's'} "
            f"connected to #{entry.id}"
        ),
    }
    # Potential connections, on request. Kept in their own list rather than
    # mixed into `related`, because they are a different kind of claim: those
    # are connections somebody made, these are ones nobody has. Flattening the
    # two would let "reads similarly" be reported back to the user as "these
    # are linked", which is the one way this feature could mislead.
    if args.get("include_suggestions"):
        suggestions = _suggested_neighbours(session, entry, visited)
        result_note = (
            "These are NOT connections, they are notes that read similarly and "
            "have never been linked. Say so if you mention them, and use "
            "link_notes if the user wants any of them joined up."
        )
        if suggestions:
            result["might_connect"] = suggestions
            result["about_might_connect"] = result_note

    if not found:
        result["note"] = (
            "Nothing is connected to this note yet, it has no links, no "
            "replies and no shared tags. link_notes and tag_note are how "
            "connections get made. Ask again with include_suggestions to see "
            "notes that read similarly but were never linked."
        )
    elif len(found) >= MAX_GRAPH_NOTES:
        result["truncated"] = (
            f"Stopped at {MAX_GRAPH_NOTES} notes, nearest first. There may be more."
        )
    return result


def _find_similar_notes(session: Session, args: dict) -> dict:
    """A dedicated semantic traversal tool to find conceptually related notes."""
    entry = _require_note(session, args)
    suggestions = _suggested_neighbours(session, entry, exclude=set())
    if not suggestions:
        return {
            "note_id": entry.id,
            "similar": [],
            "note": "No unlinked semantically similar notes were found for this note."
        }
    return {
        "note_id": entry.id,
        "similar": suggestions,
        "label": f"ph:sparkle Found {len(suggestions)} similar notes to #{entry.id}",
        "how_to_read_more": (
            "These notes share conceptual similarities based on their semantic "
            "embeddings, even if they don't share exact keywords. Use link_notes "
            "to connect them if they belong together."
        )
    }


#: How many clusters and orphans come back. A structural answer is a summary by
#: definition: "you have 43 unconnected notes, here are the first eight" is
#: the useful shape, and listing all 43 spends the window on a list nobody
#: reads to the end.
MAX_STRUCTURE_ROWS = 8


def _notebook_structure(session: Session, args: dict) -> dict:
    """What the notebook *looks like*, clusters, hubs, and what is adrift.

    The gap this closes is bigger than it sounds. The model could count notes,
    list categories and list tags, all of which describe the **filing**. Nothing
    described the **structure**: which notes are actually joined up, where they
    cluster, which one everything hangs off, and which are connected to nothing
    at all. So "tidy up my notebook" was answered by looking at category names,
    which is the one view of a notebook that says nothing about how its ideas
    relate.

    This is the tool behind an honest answer to "what should I link?", the
    orphan list is the answer, and it is a fact rather than a guess.
    """
    index = paths.build(session, include_private=False)

    def category_of(entry) -> str:  # noqa: ANN001  # Entry, kept off the signature
        return manager.category_name_for(session, entry)

    groups = paths.clusters(index, category_of)
    big = [c for c in groups if len(c.ids) >= paths.MIN_CLUSTER_NOTES]
    loose = paths.orphans(index)

    def row(note_id: int, extra: dict | None = None) -> dict:
        entry = index.entries[note_id]
        out = {
            "id": note_id,
            "preview": _clip(strip_properties(_readable(entry)).lstrip(), GRAPH_PREVIEW_CHARS),
        }
        out.update(extra or {})
        return out

    result = {
        "notes": len(index.entries),
        "connected": len(index.entries) - len(loose),
        "orphan_count": len(loose),
        "cluster_count": len(groups),
        "clusters": [
            {
                "size": len(cluster.ids),
                "categories": cluster.categories[:3],
                # The best-connected member, named rather than numbered. A
                # cluster the model can only call "cluster 2" is one the user
                # cannot picture.
                "centre": row(cluster.core_id),
            }
            for cluster in big[:MAX_STRUCTURE_ROWS]
        ],
        "hubs": [
            row(note_id, {"connections": count})
            for note_id, count in paths.hubs(index, MAX_STRUCTURE_ROWS)
        ],
        "orphans": [row(note_id) for note_id in loose[:MAX_STRUCTURE_ROWS]],
        "label": (
            f"ph:graph {len(index.entries)} notes, {len(groups)} cluster"
            f"{'' if len(groups) == 1 else 's'}, {len(loose)} unconnected"
        ),
        "how_to_read_more": (
            "A cluster is a group of notes all reachable from each other by "
            "links, replies or shared tags. An orphan has none of the three. "
            "Use path_between to explain how two notes connect, related_notes "
            "to explore around one, and link_notes to join two up. Name notes "
            "by their text as well as their id."
        ),
    }
    if index.hub_tags:
        result["ignored_tags"] = index.hub_tags[:5]
        result["about_ignored_tags"] = (
            f"Tags on more than {paths.HUB_TAG_NOTES} notes are treated as "
            "filing rather than as connections, otherwise every note sharing "
            "one would count as connected to every other. Notes joined only by "
            "these are still reported as unconnected here."
        )
    if not loose and len(groups) <= 1:
        result["note"] = "Every note is connected, in one web. That is unusual and good."
    return result


def _scope_filters(args: dict) -> list:
    """The `untagged` and `since` clauses, shared by `_list_notes` and
    `_count_notes` so that counting a scope and listing it can never disagree.

    **"Tag my untagged notes" is a filter, not a research project.**

    Reported after watching a skill run fail twice in a row: *"skills are too
    hard for small ais and things go wrong often"*, with a screenshot of the
    model saying "due to the conversation context budget, I couldn't access
    all of them" and giving up without tagging anything.

    That is not a model failing at tagging. It is the app asking a 3B model to
    page through the whole notebook, hold every note's tags in its head,
    subtract one set from another, and only then start working, and to do it
    inside a context budget the app itself enforces. §R5's rule for this is the
    whole point of the section: *do not ask a small model to be careful; make
    it structurally hard for it to be wrong.* One boolean turns the enumeration
    into a query the database was always going to be better at.
    """
    filters: list = []
    clause = _since_clause(args.get("since"))
    if clause is not None:
        filters.append(clause)
    if args.get("untagged"):
        #: Three shapes for "no tags", and all three are real rows. `tags` is
        #: a JSON string (`entry/manager.py` writes `json.dumps(tags or [])`),
        #: so a note saved today is `"[]"`; a row from before that column was
        #: always written is `NULL`; and one whose tags were cleared by hand
        #: is `""`. A filter that checked only the shape in front of it would
        #: be right on a fresh notebook and wrong on a restored backup, the
        #: same trap `_visible` and the media-usage query already sidestep.
        filters.append(or_(Entry.tags.is_(None), Entry.tags == "", Entry.tags == "[]"))
    return filters


def _scope_label(args: dict) -> str:
    """What a filtered count says it counted, for the tool card."""
    parts = ["untagged notes" if args.get("untagged") else "notes"]
    category = str(args.get("category") or "").strip()
    if category:
        parts.append(f"in {category}")
    days = _since_days(args.get("since"))
    if days is not None:
        parts.append(f"from the last {days} days")
    return " ".join(parts)


def _list_notes(session: Session, args: dict) -> dict:
    """Walk the notebook: filter, page, previews only.

    This is what makes a large notebook answerable at all. It reports the
    total against the filter and where the next page starts, so the model can
    tell the difference between "that's all of them" and "there's more".
    """
    args = _span_not_category(session, args)  # "this week" in `category` is a `since`
    limit = _limit_arg(args, default=DEFAULT_LIST_LIMIT)
    offset = max(0, int(args.get("offset") or 0))

    filters = []
    category = str(args.get("category") or "").strip()
    if category:
        filters.append(_category_clause(session, category))
    tag = str(args.get("tag") or "").strip()
    if tag:
        # Tags are stored as a delimited string, so this over-matches
        # ("work" would hit "homework"); the exact check happens below.
        filters.append(Entry.tags.ilike(f"%{like_escape(tag)}%", escape=LIKE_ESCAPE))
    since_days = _since_days(args.get("since"))
    filters.extend(_scope_filters(args))

    rows, total, has_more = page_of_notes(session, filters, tag, offset, limit)
    described = describe_filters(category, tag, since_days)
    dates_by_id = manager.entry_dates_bulk(session, [e.id for e in rows])
    result = {
        "notes": [_note_summary(session, e, dates=dates_by_id.get(e.id, [])) for e in rows],
        "returned": len(rows),
        "total_matching": total,
        "offset": offset,
        "has_more": has_more,
        "previews_only": True,
        "how_to_read_more": _READ_MORE,
        "label": f"ph:books Listed notes{f' ({described})' if described else ''}",
    }
    if has_more:
        result["next_offset"] = offset + len(rows)
        result["note_to_model"] = (
            f"Showing {len(rows)} of {total}. Call list_notes again with "
            f"offset={offset + len(rows)} for the next page, do not assume "
            "these are all the notes."
        )
    elif category and not total and (hint := unknown_category_hint(session, category)):
        result["note_to_model"] = hint
    return result


def _count_notes(session: Session, args: dict) -> dict:
    """Cheap aggregate: numbers only, never note content.

    Tag counts still need a Python-side pass because tags are stored as a
    JSON text column: SQL can't GROUP BY individual tag values without a
    virtual table or full-text index. Everything else uses SQL aggregation
    so no rows are transferred to Python at all.

    **`untagged` and `since` are here so a skill can declare its own
    postcondition** (CHAT_PLAN decision 10b, and the open item
    `archive/agent-remaining/brief-13-harness.md` 3): "Auto-tag my notes"
    claims it leaves no untagged note behind, and a claim like that is only
    worth making if the app can read it back out of the notebook as one
    integer. `list_notes` has had both filters since the tagging skill was
    written, but it returns notes, and a verifier that has to page through
    notes to count them is the thing `count_notes` exists to avoid. The two
    filters are the same code as `_list_notes`'s, deliberately: a
    postcondition that counted "untagged" differently from the tool that
    found them would pass runs that left work undone.
    """
    args = _span_not_category(session, args)
    tag = str(args.get("tag") or "").strip()
    wanted = str(args.get("category") or "").strip()
    extra = _scope_filters(args)

    if extra:
        #: A filtered count, whatever the other filters say. The tag branch
        #: below cannot answer this one in SQL (tags are a JSON string), so
        #: when a tag is asked for as well it falls through to that branch
        #: with these clauses added to it.
        if not tag:
            filters = list(_visible(*extra))
            if wanted:
                filters.append(_category_clause(session, wanted))
            count = session.scalar(select(func.count(Entry.id)).where(*filters)) or 0
            return {
                "category": wanted or None,
                "count": count,
                "label": f"ph:list-numbers Counted {_scope_label(args)}",
            }

    if tag:
        # ilike pre-filters (fast), Python exact-match removes false hits
        # ("work" matching "homework"). Count with a generator to avoid
        # materialising a list when we only need the number.
        filters = list(
            _visible(Entry.tags.ilike(f"%{like_escape(tag)}%", escape=LIKE_ESCAPE), *extra)
        )
        if wanted:
            filters.append(_category_clause(session, wanted))
        count = sum(
            1
            for e in session.scalars(select(Entry).where(*filters))
            if tag.lower() in {t.lower() for t in manager.entry_tags(e)}
        )
        return {
            "tag": tag,
            "category": wanted or None,
            "count": count,
            "label": f"ph:list-numbers Counted notes tagged #{tag}",
        }

    if wanted:
        # Category-filtered count: resolve the id, then aggregate in SQL.
        cat_clause = _category_clause(session, wanted)
        count = session.scalar(
            select(func.count(Entry.id)).where(*_visible(cat_clause))
        ) or 0
        return {
            "category": wanted,
            "count": count,
            "label": f"ph:list-numbers Counted notes in {wanted}",
        }

    # Total + per-category breakdown entirely in SQL.
    rows = session.execute(
        select(Category.name, func.count(Entry.id))
        #: The same notes `_visible` counts everywhere else: boards and maps
        #: counted here said "Uni (5)" beside /categories' "Uni (3)" (INBOX 1357).
        .outerjoin(Entry, and_(Entry.category_id == Category.id, *_visible()))
        .group_by(Category.name)
    ).all()
    # Uncategorised entries (category_id IS NULL) aren't in the join above.
    uncategorised = session.scalar(
        select(func.count(Entry.id)).where(
            *_visible(Entry.category_id.is_(None))
        )
    ) or 0
    counts: dict[str, int] = {name: cnt for name, cnt in rows if cnt > 0}
    if uncategorised:
        counts[manager.UNCATEGORISED] = uncategorised
    total = sum(counts.values())
    return {"total": total, "by_category": counts, "label": "ph:list-numbers Counted your notes"}


def _list_categories(session: Session, args: dict) -> dict:
    # SQL aggregation: no Python-side row iteration needed.
    rows = session.execute(
        select(Category.name, func.count(Entry.id))
        #: The same notes `_visible` counts everywhere else: boards and maps
        #: counted here said "Uni (5)" beside /categories' "Uni (3)" (INBOX 1357).
        .outerjoin(Entry, and_(Entry.category_id == Category.id, *_visible()))
        .group_by(Category.name)
        .having(func.count(Entry.id) > 0)
        .order_by(Category.name)
    ).all()
    uncategorised = session.scalar(
        select(func.count(Entry.id)).where(
            *_visible(Entry.category_id.is_(None))
        )
    ) or 0
    categories = [{"name": name, "notes": cnt} for name, cnt in rows]
    if uncategorised:
        categories.append({"name": manager.UNCATEGORISED, "notes": uncategorised})
    return {
        "categories": categories,
        "total_notes": sum(c["notes"] for c in categories),
        "label": "ph:folders Listed your categories",
    }


def _list_tags(session: Session, args: dict) -> dict:
    """Every tag in use with its count, most-used first.

    Tags are stored as a JSON text array in a single column, so there is no
    SQL-level per-tag aggregation path without a virtual table. One pass over
    the visible entries is unavoidable; what we avoid is materialising the full
    entry objects: `entry_tags` reads only the `tags` column, not `content`.
    """
    counts: dict[str, int] = {}
    # Select only the columns we need to reduce data transfer.
    for (tags_json,) in session.execute(
        select(Entry.tags).where(*_visible())
    ):
        for tag in manager.tags_from_json(tags_json):
            counts[tag] = counts.get(tag, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    return {
        "tags": [{"name": name, "notes": count} for name, count in ordered],
        "label": "ph:tag Listed your tags",
    }


def _notebook_overview(session: Session, args: dict) -> dict:
    """Categories, tags and totals in one call.

    Reported live: a skill wanting "the shape of the notebook" (its own
    phrase: Notebook health check, Tidy suggestions) called
    list_categories, list_tags and count_notes separately to get there, 
    three round trips, three chances for a small model to stop early or
    misfire one of them, for numbers this app already had cheap SQL for.
    This is exactly their three result shapes concatenated, not a new query
    - `count_notes`/`list_categories`/`list_tags` all stay, for a caller
    that only wants one dimension or a filtered count `count_notes` alone
    still does.
    """
    categories = _list_categories(session, {})
    tags = _list_tags(session, {})
    return {
        "total_notes": categories["total_notes"],
        "categories": categories["categories"],
        "tags": tags["tags"],
        "label": "ph:list-numbers Got the notebook's shape",
    }


def _search_help(session: Session, args: dict) -> dict:
    """The app's own help for a feature, so a question about how Tessellate
    works is answered from its guide rather than from the notes or the
    model's guesses (the same block `help_chat` adds to an app question)."""
    from tessellate.ai import composer, help_chat
    query = args.get("query") or ""
    #: A tool call is already the asking: "reminder" is a topic to look up,
    #: not a sentence that has to read as a how-to first (help_block_for's
    #: gate returned nothing for it, O1 probe 2026-10-17).
    text = help_chat.help_block_for(query) or help_chat.help_block_for(f"how do I use {query}")
    line = composer.help_line(query, help_chat.topics_for(query)) if text else None
    return {
        "guide_text": text,
        "answer": line[0] if line else "",
        "label": f"ph:book-open Read the guide on “{_clip(query, 40)}”",
    }


def _get_current_time(session: Session, args: dict) -> dict:
    """Time-aware answers: the model can ask what 'now' is.

    The user's clock, not the server's. They are the same on a laptop running
    both, and hours apart the moment the server sits in UTC, at which point
    every "tomorrow at 9" the model computes is wrong.
    """
    from tessellate.core.config import user_now

    now = user_now(deps.get_config())
    place = " ".join(str(args.get("place") or "").split())[:60]
    if place:
        #: The time somewhere else (INBOX 801): the place read by the same
        #: table Chat's own clock answer uses (`utilities.zone_for`).
        from zoneinfo import ZoneInfo

        from tessellate.ai import utilities

        zone = utilities.zone_for(place)
        if zone is None:
            return {"error": f"I do not know which time zone “{place}” is in. Name a city or a zone such as Europe/Paris."}
        now = now.astimezone(ZoneInfo(zone))
        return {
            "iso": now.isoformat(),
            "human": now.strftime("%A %d %B %Y, %H:%M"),
            "place": place,
            "zone": zone,
            "label": f"ph:clock Checked the time in {zone}",
        }
    return {
        "iso": now.isoformat(),
        "human": now.strftime("%A %d %B %Y, %H:%M"),
        "label": "ph:clock Checked the current time",
    }


# --- the deterministic layer, offered to the model (CHAT_PLAN section 2, the agent row) ---
#
# A 1 to 3B model miscounts days and fumbles a percentage; these hand it the
# app's own answers (the recogniser, the utilities, the validators) so it
# computes nothing itself. Each result says how it read the input, and its
# numbers are a tool result, which `source_check` counts as a source.


def _calculate(session: Session, args: dict) -> dict:
    from tessellate.ai import arithmetic, utilities
    from tessellate.core.config import user_now

    question = str(args.get("question") or "").strip()[:300]
    if not question:
        return {"error": "Say what to work out, for example: 15% of 240."}
    now = user_now(deps.get_config())
    parts = utilities.answer(question, now) or utilities.answer(f"what is {question}", now)
    if not parts:
        try:
            value = arithmetic.spoken(arithmetic.evaluate(question))
        except arithmetic.NotArithmetic:
            return {"error": "That is not a sum, a percentage, a conversion or a date question the app can work out."}
        parts = [("computed", f"{question} is {value}.")]
    text = "".join(t for kind, t in parts if kind == "computed").strip()
    answer, _, read_as = text.partition("\nRead as ")
    return {"answer": answer.strip(), "read_as": read_as.strip().rstrip(".") or question, "label": "ph:calculator Worked it out"}


def _read_text(session: Session, args: dict) -> dict:
    from tessellate.ai import recognise
    from tessellate.core.config import user_now

    text = str(args.get("text") or "")[:2000]
    spans = recognise.recognise(text, now=user_now(deps.get_config()))
    return {
        "read": [{"kind": s.kind, "said": s.text, "read_as": s.read_as, "value": s.json()["value"]} for s in spans if not s.rank][:40],
        "label": "ph:magnifying-glass Read the dates and amounts",
    }


def _check_answer(session: Session, args: dict) -> dict:
    from tessellate.ai import validate

    answer = str(args.get("answer") or "")[:6000]
    sources = [str(s)[:20000] for s in (args.get("sources") or [])][:40]
    checked = validate.check_model_answer(answer, sources)
    return {"unsourced": checked["unbacked"], "ok": checked["ok"], "label": "ph:seal-check Checked the answer"}


def _propose_act(session: Session, args: dict) -> dict:
    """A model's act, through the act registry (CHAT_PLAN decision 53, F3's
    `acts.propose`): the sentence is read by the same grammar a typed act is,
    previewed as its card and left waiting for the person's Confirm. The
    model proposes, the engine decides; nothing is written here."""
    from tessellate.ai import act_registry
    from tessellate.core.config import user_now

    sentence = str(args.get("sentence") or "").strip()[:400]
    planned = act_registry.propose(session, sentence, user_now(deps.get_config()))
    if planned is None:
        return {"error": "That is not an act the app knows. Say it as: remind me to ..., tag the note about ... with ..., pin the note about ..."}
    out = {"line": planned.get("line", ""), "label": "ph:hand-pointing Proposed, waiting for you"}
    if planned.get("card"):
        out["act_card"] = planned["card"]
    return out


def _summarize_notes(session: Session, args: dict) -> dict:
    """Gather recent notes (optionally by category / time window) so the model
    can summarise them in its answer. Read-only."""
    from tessellate.core.database import utcnow

    query = select(Entry).where(*_visible())
    period = "all time"
    days = _since_days(args.get("days"))
    if days is not None:
        query = query.where(Entry.created_at >= utcnow() - timedelta(days=days))
        period = f"last {days} days"
    rows = list(
        session.scalars(
            query.order_by(Entry.created_at.desc()).limit(SUMMARY_NOTE_LIMIT + 1)
        )
    )
    capped = len(rows) > SUMMARY_NOTE_LIMIT
    rows = rows[:SUMMARY_NOTE_LIMIT]
    wanted = args.get("category")
    if wanted:
        rows = [e for e in rows if manager.category_name_for(session, e) == str(wanted)]
        period = f"{period}, {wanted}"
    dates_by_id = manager.entry_dates_bulk(session, [e.id for e in rows])
    result = {
        "period": period,
        "count": len(rows),
        "notes": [_note_summary(session, e, dates=dates_by_id.get(e.id, [])) for e in rows],
        "how_to_read_more": _READ_MORE,
        "label": "ph:note-pencil Gathered notes to summarise",
    }
    if capped:
        result["note_to_model"] = (
            f"Only the {SUMMARY_NOTE_LIMIT} most recent notes are here, there "
            "are older ones. Say your summary covers the recent ones, or use "
            "list_notes to page through the rest."
        )
    return result
CHARS_PER_TOKEN = 4  # close enough for a stop rule; a real tokeniser per model is not
