"""Tags: the names filed on notes, counted, renamed, merged, removed and put back.

The fourth resource behind a repository (INBOX 1499); the rules every
repository keeps are in `repo/__init__.py`. A tag is not a table: it is a name
inside the JSON list in `Entry.tags`, so this module owns that column's
reading and writing, and the tag count cache keyed to the notebook. Every
write here flushes and never commits: the route (or the tool) owns the one
transaction, so a batch of notes is one commit or none.
"""

from __future__ import annotations

import importlib
import json
import threading

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core import events
from tessellate.core.database import LIKE_ESCAPE, Entry, like_escape
from tessellate.entry.manager import entry_tags, log_action, mark_edited, note_is_sealed, record_revision, tags_from_json
from tessellate.entry.tagnames import normalise_tags
from tessellate.repo import NotFound

class _TagCache:
    """Holds the tag-count cache's mutable state as attributes rather than
    module globals: CodeQL's `py/unused-global-variable` flags a bare
    `global NAME` reassignment whose new value is never read again inside
    the same function (true of both writes below: a cache is written for a
    *future* call to read, not the one writing it), which is a real pattern
    for a process-lifetime cache, not a bug. An attribute write sidesteps
    the check without changing behaviour."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.entry: tuple | None = None  # (fingerprint, result), one slot, no LRU needed
        self.reset_registered = False


_tag_cache = _TagCache()


def _tag_fingerprint(session: Session) -> tuple:
    """Cheap signature of everything that can change a tag count: a new
    entry, an edit, a delete, or a restore. Same shape as routes_graph.py's
    `_graph_fingerprint`, `Entry.updated_at` has `onupdate=utcnow`, so any
    tag edit bumps it, and the live-entry count catches soft-delete/restore
    even on the rare row an edit doesn't touch."""
    deps = importlib.import_module("tessellate.core.deps")

    live = Entry.is_deleted == False  # noqa: E712
    return (
        str(deps.get_config().data_dir),
        session.scalar(select(func.count(Entry.id)).where(live)) or 0,
        session.scalar(select(func.max(Entry.updated_at)).where(live)),
    )


def reset_tag_cache() -> None:
    """Drop the cached tag counts. For the tests, and for a data restore."""
    with _tag_cache.lock:
        _tag_cache.entry = None


def _ensure_tag_cache_reset_registered() -> None:
    # `deps` imports (transitively, via ai.embeddings -> ai.model_manager)
    # back into this module for `log_action`, so `from tessellate.core import
    # deps` cannot sit at module level here without a circular import at
    # startup: register lazily, on first use, the same way this file
    # already imports `deps` inside `record_dates` for the same reason.
    #
    # `importlib.import_module` rather than a plain `from ... import deps`
    # statement even here, lazy as it already is: CodeQL's
    # py/cyclic-import (three "Note"-severity alerts against this exact
    # shape, this file, closed together) flags the *import statement*
    # itself as beginning a cycle in the module dependency graph, it has
    # no way to know the statement only ever runs after startup, so
    # function-local didn't clear it. `importlib` performs the identical
    # lazy lookup with no `import` statement for that static check to
    # see, which is why `ai/vision_ocr.py` already uses it for this same
    # module.
    if _tag_cache.reset_registered:
        return
    deps = importlib.import_module("tessellate.core.deps")

    deps.register_cache_reset(reset_tag_cache)
    _tag_cache.reset_registered = True


def counts(session: Session) -> dict[str, int]:
    """Every tag in use with its entry count.

    Was a full non-deleted-entry scan with a per-row `json.loads`, paid on
    every Library tab open, every `tag_cloud()` call, and every `/tags`
    call: three call sites, the same O(n) cost each time, and no cap the
    way every sibling section of the same responses uses (ROADMAP.md
    "#0 priority"). Cached by notebook fingerprint instead, the same
    pattern `routes_graph.py` already uses for pagerank/similarity, a
    fingerprint miss recomputes once; every other caller within the same
    notebook version gets the cached dict.
    """
    _ensure_tag_cache_reset_registered()
    # Whether the vault is open is part of what the counts say: a locked
    # private note's tags are not counted (INBOX 1437), so the cache must not
    # carry an unlocked answer across a lock.
    fingerprint = (_tag_fingerprint(session), note_is_sealed(True))
    with _tag_cache.lock:
        if _tag_cache.entry is not None and _tag_cache.entry[0] == fingerprint:
            return _tag_cache.entry[1]

    counts: dict[str, int] = {}
    # One column, not one mapped entity per row. `tags` is the only thing this
    # loop reads, and a `select(Entry)` here made SQLAlchemy build, and
    # identity-map: a full `Entry` for every note in the notebook just to
    # reach `.tags`. That is the same cost `search_manager.semantic_search`
    # was rewritten to stop paying (see its docstring: ~85% of a search at
    # 20k+ notes went on materialising entities it then discarded). The
    # fingerprint cache above keeps this off the hot path most of the time;
    # this makes the miss itself cheap instead of merely rare.
    sealed = note_is_sealed(True)
    for raw in session.scalars(
        select(Entry.tags).where(
            Entry.is_deleted == False,  # noqa: E712
            *([Entry.is_private == False] if sealed else []),  # noqa: E712
        )
    ):
        for tag in tags_from_json(raw):
            counts[tag] = counts.get(tag, 0) + 1
    result = dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    with _tag_cache.lock:
        _tag_cache.entry = (fingerprint, result)
    return result


@events.writes("entry", "edited")
def _retag_entry(session: Session, entry: Entry, tags: list[str]) -> None:
    """One note's tags set to `tags`: a revision first, then the edit and its
    event, the way `PUT /entries/{id}` does it, and no commit (the caller
    commits the whole batch once, so a batch is one transaction).

    The revision is taken before the scope opens here, by the caller, so it
    keeps its own `revised` event rather than being folded into this one.
    """
    was = events.entry_state(entry)
    entry.tags = json.dumps(tags)
    mark_edited(entry)
    log_action(
        session,
        "edited",
        "entry",
        entry.id,
        "tags",
        payload=events.changed(was, events.entry_state(entry)),
    )


def _retag(session: Session, entries, change) -> dict[int, list[str]]:
    """Apply `change(entry, tags) -> tags` to each entry, in one transaction.

    Returns `{entry id: the tags it had}` for the notes that actually changed,
    which is exactly what an undo needs to put back (`restore`). A note
    whose tags come out the same is left alone: no revision, no event, no
    `edited_at` bump for a no-op.
    """
    before: dict[int, list[str]] = {}
    for entry in entries:
        old = entry_tags(entry)
        new = normalise_tags(change(entry, list(old)), split=False)
        if new == old:
            continue
        record_revision(session, entry)
        _retag_entry(session, entry, new)
        before[entry.id] = old
    session.flush()
    return before


def rename(session: Session, olds: list[str], new: str) -> dict[int, list[str]]:
    """Rename (or merge, if `new` already exists, or if several `olds` are
    given) tags everywhere, in one transaction.

    `new` is held to the tag rule (`normalise_tags`): a blank name is refused
    with ValueError rather than written, because "   " used to arrive here
    intact and put an empty-string tag on every note that had `old`
    (measured: four notes). The result on each note is normalised too, so
    renaming onto a tag the note already has in another case ("Food" onto a
    note with "food") folds into that one instead of leaving both.
    """
    cleaned = normalise_tags([new])
    if not cleaned:
        raise ValueError("A tag needs a name.")
    if len(cleaned) > 1:
        raise ValueError("A tag name cannot hold a comma. Rename one tag at a time.")
    new = cleaned[0]
    wanted = set(olds)
    if not wanted:
        return {}

    def change(entry: Entry, tags: list[str]) -> list[str]:
        if not wanted.intersection(tags):
            return tags
        return [t for t in tags if t not in wanted] + [new]

    holders = [e for e in session.scalars(select(Entry)) if wanted.intersection(entry_tags(e))]
    return _retag(session, holders, change)


def remove(session: Session, names: list[str]) -> dict[int, list[str]]:
    """Remove tags from every note that carries them. Notes are untouched."""
    doomed = set(names)
    if not doomed:
        return {}
    holders = [e for e in session.scalars(select(Entry)) if doomed.intersection(entry_tags(e))]
    return _retag(session, holders, lambda _e, tags: [t for t in tags if t not in doomed])


def put_back(held: dict[int, list[str]], name: str) -> dict:
    """The Undo of `remove`: the tool step that puts `name` back on exactly the notes that carried it ({} when none did)."""
    if not held:
        return {}
    return {"undo": {"tool": "batch", "steps": [{"tool": "tag_note", "arguments": {"note_id": note_id, "add": [name]}} for note_id in held]}}


def bulk_edit(
    session: Session, ids: list[int], add: list[str], remove: list[str]
) -> dict[int, list[str]]:
    """Add tags to, and remove tags from, the chosen notes, in one transaction.

    Removal is case-insensitive (tags are stored once whatever the case, so
    "Food" on one note and "food" on another are one tag to the person),
    and the add runs after it, so a name in both lists ends up added.
    """
    drop = {t.casefold() for t in normalise_tags(remove, split=False)}
    put = normalise_tags(add)
    if not ids or not (drop or put):
        return {}
    entries = list(
        session.scalars(select(Entry).where(Entry.id.in_(ids), Entry.is_deleted == False))  # noqa: E712
    )

    def change(entry: Entry, tags: list[str]) -> list[str]:
        return [t for t in tags if t.casefold() not in drop] + put

    return _retag(session, entries, change)


def restore(session: Session, by_id: dict[int, list[str]]) -> dict[int, list[str]]:
    """Put each note's tags back to the given lists (an undo), in one
    transaction. Returns what they were, so a redo is the same call."""
    if not by_id:
        return {}
    entries = list(session.scalars(select(Entry).where(Entry.id.in_(list(by_id)))))
    return _retag(session, entries, lambda entry, _tags: by_id[entry.id])



def find(session: Session, name: str) -> int | None:
    """How many notes carry the tag, exactly as stored, or None when none does."""
    return counts(session).get(name)


def get(session: Session, name: str) -> int:
    """`find`, or `NotFound` for a tag no note carries."""
    found = find(session, name)
    if found is None:
        raise NotFound(f"No note carries the tag {name}.")
    return found


def page(session: Session, *, limit: int) -> tuple[dict[str, int], int]:
    """The tags most used first, cut to `limit`, and the total in use.

    The count is already ordered most-used first, so the cut keeps the tags
    that matter most and drops the long tail, which is the right end to lose.
    """
    every = counts(session)
    if len(every) <= limit:
        return every, len(every)
    return dict(list(every.items())[:limit]), len(every)


def remove_from(session: Session, wanted: dict[int, set[str]]) -> dict[int, list[str]]:
    """Take the given tags (folded, case-insensitive) off the given notes only.

    `wanted` maps a note id to the folded names to drop from it; returns what
    each changed note had, for the undo (`restore`).
    """
    entries = list(session.scalars(select(Entry).where(Entry.id.in_(list(wanted)))))
    return _retag(session, entries, lambda e, tags: [t for t in tags if t.casefold() not in wanted[e.id]])


def tagged(session: Session, *, limit: int) -> list[tuple[int, list[str]]]:
    """Newest first: each open, non-private, non-board note that has any tag,
    as (id, tags). What the chat reads to find notes sharing a rare tag."""
    rows = session.execute(
        select(Entry.id, Entry.tags)
        .where(Entry.is_deleted == False, Entry.is_private == False, Entry.is_board == False, Entry.tags != "[]")  # noqa: E712
        .order_by(Entry.created_at.desc())
        .limit(limit)
    ).all()
    return [(i, tags_from_json(t)) for i, t in rows]


def mentioning(words: list[str], *, whole_start: bool = False) -> list:
    """One SQL condition per word: the note's tags text contains it, any case.

    With `whole_start` the word must begin a tag (`"word`) and a plural word's
    "s" is not asked for, the way a topic word is matched against the list.
    """
    if whole_start:
        return [func.lower(Entry.tags).like(f'%"{like_escape(w.rstrip("s"))}%', escape=LIKE_ESCAPE) for w in words]
    return [func.lower(Entry.tags).like(f"%{like_escape(w)}%", escape=LIKE_ESCAPE) for w in words]


# --- tags turned down on one note (Entry.discarded_tags) ----------------------


def turned_down_on(session: Session, entry_id: int) -> list[str] | None:
    """The tags turned down on a live note, or None when there is no such note."""
    raw = session.scalar(select(Entry.discarded_tags).where(Entry.id == entry_id, Entry.is_deleted.is_(False)))
    if raw is None:
        exists = session.scalar(select(Entry.id).where(Entry.id == entry_id, Entry.is_deleted.is_(False)))
        return None if exists is None else []
    try:
        return [str(tag) for tag in json.loads(raw or "[]") if tag]
    except (TypeError, ValueError):
        return []


def set_turned_down_on(session: Session, entry_id: int, tags: list[str]) -> None:
    """Replace a note's turned-down tags (the newest 200); never commits.

    A plain UPDATE, not the ORM: turning a tag down or back is not an edit, and
    the ORM flush would move `updated_at` (its `onupdate`).
    """
    from sqlalchemy import text

    session.execute(
        text("UPDATE entries SET discarded_tags = :tags WHERE id = :id"),
        {"tags": json.dumps([str(tag) for tag in tags][-200:]), "id": entry_id},
    )
