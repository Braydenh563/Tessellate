"""Tag suggestions kept on a note at filing (INBOX 440), out of the route file.

Both suggesters (a note filed before saving, a note refiled afterwards) read
the same vocabulary and the same engine, so they cannot drift apart.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from tessellate.ai import librarian
from tessellate.core import deps
from tessellate.entry import manager, manager_text
from tessellate.repo import tags as tags_repo

logger = logging.getLogger("tessellate.api.entries")


def json_tags(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [str(tag) for tag in value if tag] if isinstance(value, list) else []


def keep_suggestions(session: Session, entry, filed_by: str | None) -> None:  # noqa: ANN001
    """Make the note's tag suggestions at filing and keep them on it (INBOX
    440). The model's when it is the one that filed (it is up and answering);
    otherwise the notebook's own: the tags its nearest notes carry, and the
    vocabulary tags the note names. Best effort, never fails the filing.

    **A private note gets none made.** Its tags are the person's own (nothing
    derives them from its text), and a suggestion is derived from the text, so
    one made here would put a summary of a private note into a plain column,
    from ciphertext or the locked placeholder when the vault is shut. What it
    already holds (a note made private after filing) is handled like its
    tags: kept, shown where they are, nowhere else."""
    if getattr(entry, "is_private", False) or getattr(entry, "tag_suggest_off", False):
        return
    have = manager.entry_tags(entry)
    discarded = {tag.casefold() for tag in json_tags(getattr(entry, "discarded_tags", "[]"))}
    suggested: list[str] = []
    if filed_by == "llm":
        try:
            suggested = librarian.suggest_tags(
                entry.content, have, deps.get_model_manager(), deps.get_ollama(),
                vocabulary=tag_vocabulary(session),
            )
        except Exception:
            logger.info("tag suggestions from the model failed; using the notebook's own", exc_info=True)
    content = manager_text.readable_content(entry)
    keep = [tag for tag in engine_tags(session, content, have, suggested, entry.id) if tag.casefold() not in discarded]
    from tessellate.ai import tagging

    entry.suggested_tags = json.dumps(keep[: tagging.TAG_LIMIT])


def keep_suggestions_safely(session: Session, entry, entry_id: int, filed_by: str | None) -> None:  # noqa: ANN001
    """`keep_suggestions` in a savepoint: a database error in it (a failed
    flush, a locked table) rolls back the suggestions alone, so the commit
    after it still settles the filing (PR 242 review: the session was left
    in a failed transaction and the whole filing was marked failed)."""
    try:
        with session.begin_nested():
            keep_suggestions(session, entry, filed_by)
    except Exception:
        logger.warning("couldn't keep tag suggestions for entry %s", entry_id, exc_info=True)


def engine_tags(session: Session, content: str, have: list[str], model: list[str], entry_id: int | None) -> list[str]:
    """One engine on every path (INBOX 781): a model's tags kept only where
    the note has a word for them (WORLD_CLASS 23, decision 5: its reply to
    "prefer one of those" was the first two, whatever the note said, the
    Study bug), then the notebook's own (`ai/tagging.suggest`) filling the
    rest, so a model that offers one tag no longer hides two good ones. Room
    still left goes to a subject the note names that the notebook has never
    tagged (`tagging.filled`, B80)."""
    from tessellate.ai import tagging

    own = tagging.suggest(session, content, have=have, exclude_entry_id=entry_id)
    return tagging.filled(session, content, tagging.merged(tagging.grounded(content, model), own, have), have)


def tag_vocabulary(session: Session) -> list[str]:
    """The notebook's own tags, most used first.

    Both tag suggesters read this, so a note filed before saving and a note
    refiled afterwards are offered the same vocabulary and cannot drift
    apart. `tags_repo.counts` is cached by notebook fingerprint, so this is
    a dictionary lookup rather than a scan on the common path.
    """
    counts = tags_repo.counts(session)
    return [tag for tag, _count in sorted(counts.items(), key=lambda row: (-row[1], row[0]))]


def open_suggestions(entry) -> list[str]:  # noqa: ANN001
    """The kept suggestions still worth showing: not on the note already and
    not discarded (a tag added by hand since filing drops out by itself).
    None while the note is set to "Don't suggest tags" (brief 89); what was
    kept is still on the row and comes back when that is cleared. None while
    a private note is locked, like its tags (INBOX 1437)."""
    if getattr(entry, "tag_suggest_off", False) or manager.note_is_sealed(getattr(entry, "is_private", False)):
        return []
    have = {tag.casefold() for tag in manager.entry_tags(entry)}
    gone = {tag.casefold() for tag in json_tags(getattr(entry, "discarded_tags", "[]"))}
    return [
        tag for tag in json_tags(getattr(entry, "suggested_tags", "[]"))
        if tag.casefold() not in have and tag.casefold() not in gone
    ]
