"""Category management: the list with counts, rename, delete and the reassign pass.

Moved whole out of `entry/manager.py` (audit K24, BK11), unchanged. It sits above `entry/manager.py`, which never imports it back. Callers import these names from here.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tessellate.core.database import Category, EmbeddingRecord, Entry
from tessellate.entry.cleantext import is_blank, name_key
from tessellate.entry.manager import BROKEN_BAR, UNCATEGORISED, category_label, category_space, get_or_create_category, log_action, note_filter


# --- category management (rename / delete) -----------------------------------


def all_categories(session: Session) -> list[dict]:
    """Every category with how many live entries sit in it, biggest first.

    The number is the Notes list's own under that category, so it counts
    exactly what the list shows: not binned, not archived, not a draft (the
    list keeps drafts in their own view), not a board. It used to exclude
    only the bin, and two numbers for one category disagreed on screen:
    Health 4 in the sidebar and 5 in Manage categories with one archived
    note, Work 5 and 6 with one draft (measured 2026-10-03). The where-clause
    is `_list_entries_filter`'s, the same one `GET /entries` uses, so the two
    cannot drift apart again by one of them gaining a filter.
    """
    rows = list(session.scalars(select(Category).order_by(Category.name)))
    query = note_filter(select(Entry.category_id, func.count(Entry.id)), include_archived=False)
    counts = {
        category_id: total
        for category_id, total in session.execute(query.group_by(Entry.category_id))
    }
    out = [
        {"id": c.id, "name": c.name, "count": counts.get(c.id, 0), "colour": c.colour}
        for c in rows
    ]
    out.sort(key=lambda c: (-c["count"], c["name"].lower()))
    return out


# **A category's name is part of what its notes embed, so renaming one makes
# every vector under it stale.**
#
# `ai/embeddings.embedding_text` folds the category name and the note's tags
# into the embedded text, that change is itself the fix for a reported
# problem ("I have a whole category called hobbies but basically none came up
# in the semantic search"). The consequence nobody wired up: rename "Games"
# to "Hobbies", or merge it into an existing "Hobbies", and every note that
# moved still has a vector built from the *old* name. Semantic search then
# keeps missing exactly the notes the user just tidied, which is the same
# symptom again, produced by the fix for it.
#
# The vectors are dropped rather than recomputed here. Re-embedding is a model
# call per note and this runs inside a rename the user is waiting on; dropping
# is instant, and the search path already treats a missing vector as "fall
# back to keywords for this note" rather than as an error. They are rebuilt by
# the next re-index (`POST /models/reindex`, or the periodic backfill), so the
# worst case is keyword-quality results for those notes until then, instead of
# semantic results that are quietly wrong.
def _restale_category_vectors(session: Session, category_id: int) -> int:
    """Drop the embeddings of every note in a category whose name just
    changed. Returns how many were dropped."""
    entry_ids = [
        row[0]
        for row in session.execute(
            select(Entry.id).where(Entry.category_id == category_id)
        ).all()
    ]
    if not entry_ids:
        return 0
    dropped = (
        session.query(EmbeddingRecord)
        .filter(EmbeddingRecord.entry_id.in_(entry_ids))
        .delete(synchronize_session=False)
    )
    session.commit()
    return int(dropped or 0)


def rename_category(session: Session, category_id: int, new_name: str) -> dict:
    """Rename a category; renaming onto an existing name merges the two.

    Merging is the useful behaviour rather than an error, "Work" and "work"
    turning up as separate categories is exactly the mess this is here to fix.
    """
    category = session.get(Category, category_id)
    if category is None:
        raise ValueError("That category no longer exists.")
    if is_blank(new_name):
        raise ValueError("A category needs a name.")
    new_name = category_label(new_name)
    if new_name == category.name:
        return {"renamed": False, "merged": False, "moved": 0}

    # Only a same-named category in *this one's own space* is a merge. By
    # name alone, renaming uni's "Lectures" to "Garden" from the "All spaces"
    # view merged it into the default space's "Garden" and both uni notes
    # then read as Uncategorised in uni (measured 2026-10-03). In another
    # space the name is simply free, so this is a plain rename.
    wanted = name_key(new_name)
    existing = next(
        (
            other
            for other in session.scalars(
                select(Category)
                .where(
                    Category.workspace_id == category_space(session, category.workspace_id),
                    Category.id != category.id,
                )
                .order_by(Category.id)
            )
            if name_key(other.name) == wanted
        ),
        None,
    )
    if existing is not None:
        # Merge: move the entries across, then drop the now-empty category.
        moved = _reassign(session, category.id, existing.id)
        log_action(session, "edited", "category", existing.id, f"merged {category.name} → {new_name}")
        session.delete(category)
        session.commit()
        _restale_category_vectors(session, existing.id)
        return {"renamed": True, "merged": True, "moved": moved}

    old = category.name
    category.name = new_name
    log_action(session, "edited", "category", category.id, f"{old} → {new_name}")
    session.commit()
    _restale_category_vectors(session, category.id)
    return {"renamed": True, "merged": False, "moved": 0}


def delete_category(session: Session, category_id: int) -> dict:
    """Remove a category. Its notes are kept and become Uncategorised.

    Deleting a category must never delete notes, that would make an organising
    action destructive, which is never what anyone means by "delete category".
    """
    category = session.get(Category, category_id)
    if category is None:
        raise ValueError("That category no longer exists.")
    if category.name == UNCATEGORISED:
        raise ValueError("Uncategorised is where notes go, so it can't be removed.")

    # The deleted category's own Uncategorised, not the view's: a note must
    # stay filed in a category its own space can list.
    fallback = get_or_create_category(
        session, UNCATEGORISED, workspace_id=category_space(session, category.workspace_id)
    )
    moved = _reassign(session, category.id, fallback.id)
    log_action(session, "deleted", "category", category.id, category.name)
    session.delete(category)
    session.commit()
    return {"deleted": True, "moved": moved}


def _reassign(session: Session, from_id: int, to_id: int) -> int:
    """Point every entry in one category at another. Returns how many moved."""
    entries = list(session.scalars(select(Entry).where(Entry.category_id == from_id)))
    for entry in entries:
        entry.category_id = to_id
    return len(entries)


def mend_broken_bar_names(session) -> int:
    """A category saved with a broken bar for "&" before `category_label`
    mended it (LEDGER L803) is renamed once; a clash merges, as a rename
    does. A clean notebook matches nothing. Returns how many were mended."""
    hit = session.query(Category.id, Category.name).filter(Category.name.contains(BROKEN_BAR)).all()
    for category_id, name in hit:
        rename_category(session, category_id, name)
    if hit:
        session.commit()
    return len(hit)
