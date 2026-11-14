"""Two windows, one note: the optimistic check on a save (WORLD_CLASS_PLAN 22.1 item 5).

Every read of a note or a document carries `content_hash`, the hash of the
text it shows. An editor that saves sends back the hash of the text it
started from as `base_hash`; if the text on the server is no longer that
text (another window, another device on the LAN or the agent saved in
between), the save is refused with 409 and the text that is there, so the
editor can offer "keep mine", "take theirs" or "compare" instead of the
later save silently overwriting the earlier one.

The text, not `updated_at`, because `Entry.updated_at` moves on every
write to the row (a pin, the AI filing the note, a link resolved) and each
of those would read as a conflict with the person typing. Two saves of the
same text are not a conflict either: nothing would be lost.

A save that sends no `base_hash` is not checked, so every writer that does
not edit from an open copy (the agent's tools, undo, a restore, a checkbox
ticked on a card) behaves exactly as before.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

#: The error's machine name, which the frontend keys its prompt on.
EDIT_CONFLICT = "edit_conflict"


def content_hash(text: str | None) -> str:
    """A short, stable fingerprint of a text: 16 hex characters of SHA-256.

    Sixty-four bits is far past what two versions of one note could collide
    in, and short enough to ride on every list row for free.
    """
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def refuse_if_stale(
    *,
    base_hash: str | None,
    current_text: str | None,
    new_text: str | None,
    current: Callable[[], Any],
    noun: str,
    base_threads_hash: str | None = None,
    current_threads: str | None = None,
    new_threads: str | None = None,
) -> None:
    """Raise 409 when a save started from text that is no longer there.

    `current` builds the object as a read would return it (a Pydantic model
    or a dict), sent back so the editor can show or take it without a second
    request; a callable, so a save that passes costs no second read.

    A document's comment threads are a second thing a save can overwrite (the
    PUT replaces the list whole), so they get the same check on their own:
    `base_threads_hash` is the hash of the stored threads text the editor
    started from, `current_threads` what is stored now and `new_threads` what
    the save would store (None: the save sends none, so nothing is replaced).
    """
    if _text_is_stale(base_hash, current_text, new_text) or _threads_are_stale(
        base_threads_hash, current_threads, new_threads
    ):
        _refuse(409, current, noun)


def refuse_if_tags_stale(
    *,
    base_tags: list[str] | None,
    current_tags: list[str],
    new_tags: list[str] | None,
    current: Callable[[], Any],
    noun: str,
) -> None:
    """Raise 409 when a tag edit started from tags that are no longer there.

    The same refusal as a stale text (the graph's "tag these notes" sets the
    whole list from the node it drew). Order does not matter; saving the tags
    that are already there is not a conflict.
    """
    if base_tags is None or new_tags is None:
        return
    if set(current_tags) == set(base_tags) or set(current_tags) == set(new_tags):
        return
    _refuse(409, current, noun)


def _text_is_stale(base_hash: str | None, current_text: str | None, new_text: str | None) -> bool:
    if not base_hash or new_text is None:
        return False
    return not (content_hash(current_text) == base_hash or (current_text or "") == new_text)


def _threads_are_stale(base: str | None, current: str | None, new: str | None) -> bool:
    if not base or new is None:
        return False
    return not (content_hash(current) == base or (current or "") == new)


#: The error's machine name for a refused `If-Match` (412), the HTTP form.
PRECONDITION_FAILED = "precondition_failed"


def entity_tag(text_hash: str) -> str:
    """A note's version as an HTTP entity tag (WORLD_CLASS_PLAN B7).

    Strong, quoted, and the same hash as `content_hash` so the two ways of
    asking "is it still this version" (`base_hash` in a body, `If-Match` on a
    request) can never disagree about the answer.
    """
    return f'"{text_hash}"'


def refuse_unless_match(
    if_match: str | None,
    *,
    current_hash: str,
    current: Callable[[], Any],
    noun: str,
) -> None:
    """Raise 412 when `If-Match` names versions none of which is the current one.

    No header, or `*`, is no precondition. A weak tag (`W/"..."`) never
    matches, as RFC 9110 has it for `If-Match`, since a weak tag cannot
    promise the bytes are the same.
    """
    if not if_match or not if_match.strip() or if_match.strip() == "*":
        return
    wanted = {tag.strip() for tag in if_match.split(",") if tag.strip()}
    if entity_tag(current_hash) in wanted:
        return
    _refuse(412, current, noun, code=PRECONDITION_FAILED)


def _refuse(status: int, current: Callable[[], Any], noun: str, code: str = EDIT_CONFLICT) -> None:
    body = current()
    body = body.model_dump(mode="json") if hasattr(body, "model_dump") else body
    raise HTTPException(
        status_code=status,
        detail={
            "code": code,
            "message": f"This {noun} was changed in another window since you started editing it.",
            "current": body,
        },
    )
