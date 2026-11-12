"""Links between notes: reasons, deduced reasons, props, types, two-way flags, audit redaction, create, remove and list.

Moved whole out of `entry/manager.py` (audit K24, BK11), unchanged. It sits above `entry/manager.py` (it logs through `log_action`), which never imports it back. Callers import these names from here.
"""

from __future__ import annotations

import importlib
import json
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session
from tessellate.core import events
from tessellate.core.database import EmbeddingRecord, Entry, EntryLink, LIKE_ESCAPE
from tessellate.entry import link_facts
from tessellate.repo import relation_types
from tessellate.entry.manager import _placeholder_link, entry_dates_bulk, log_action, sealed_stand_ins


# How close two notes' embeddings must be, cosine-wise, before a link left
# with no reason gets one deduced for it. The same bar `/entries/link-
# suggestions` ranks by, so a link made from approving a suggestion and a
# link the AI made unprompted read the same way if they're equally close.
AUTO_REASON_THRESHOLD = 0.55
AUTO_REASON_TEXT = "similar in meaning"
AUTO_REASON_TEXT_TEMPORAL = "similar in meaning, and around the same time"
#: How much a shared date pushes a borderline embedding score over
#: AUTO_REASON_THRESHOLD. Asked for directly (ROADMAP.md Tier 2 item 9):
#: two notes both mentioning "next Tuesday", or written the same day, should
#: read as related even when their topics don't overlap semantically enough
#: on their own. Deliberately small and a *rescue*, not a second path to a
#: link: see the `score >= AUTO_REASON_THRESHOLD` early return below, which
#: keeps every pair that already clears the bar on meaning alone exactly as
#: it was (the reason text, the confidence, and every existing test).
TEMPORAL_RESCUE_BOOST = 0.15


def _shares_a_date(session: Session, source_id: int, target_id: int) -> bool:
    """True when the two notes resolve to the same calendar day.

    Two ways in, both day-precision only (a coarser phrase like "last week"
    isn't specific enough to call two notes related on its own): a recorded
    time phrase in both (`EntryDate`, "next Tuesday" in one note and
    "next Tuesday" in another, each resolved against the day it was
    written), or simply being written on the same day, phrase or not.
    """
    dates_by_entry = entry_dates_bulk(session, [source_id, target_id])
    day_sets = {
        entry_id: {d.at.date() for d in dates if d.precision in ("day", "minute")}
        for entry_id, dates in dates_by_entry.items()
    }
    if day_sets.get(source_id, set()) & day_sets.get(target_id, set()):
        return True

    entries = {
        e.id: e
        for e in session.scalars(
            select(Entry).where(Entry.id.in_((source_id, target_id)))
        )
    }
    source, target = entries.get(source_id), entries.get(target_id)
    if source is None or target is None:
        return False
    return source.created_at.date() == target.created_at.date()


def _deduce_reason(
    session: Session, source_id: int, target_id: int
) -> tuple[str | None, float | None]:
    """Guess why two notes might be linked from how close their embeddings
    are, with a shared date as a tie-breaker for a borderline pair. Returns
    `(None, None)`, "no reason", when it can't: no embedding for one or
    both notes, a mid-reindex width mismatch, or a score under
    `AUTO_REASON_THRESHOLD` even after the date check. That's deliberately
    the same pair `reason` already had for "nobody gave one", so a weak
    guess never outranks silence, see `EntryLink.reason_confidence`.

    A private note has no embedding (`set_private` deletes it), so this is
    naturally a no-op for one rather than needing its own guard.

    Deliberately cheap: no model call. This used to also ask the AI for a
    specific reason here, synchronously, which meant `create_link` (and so
    every note-linking request, human or agent) stalled on a chat round-trip.
    Wording a *specific* reason is the background audit's job now
    (`ai.links.audit_vague_links`, driven from `ai.autonomous`): this always
    returns immediately with the embedding score's own verdict, the generic
    `AUTO_REASON_TEXT`, and leaves the wording to be upgraded later without
    the person who made the link ever waiting on it.
    """
    # `importlib`, same reason as `_ensure_tag_cache_reset_registered`'s own
    # `deps` lookup above: a plain `from tessellate.ai.embeddings import ...`
    # is CodeQL py/cyclic-import's other flagged site in this file (Note
    # severity: `tessellate.ai.embeddings` imports back into this module by
    # the same `deps` -> `ai.model_manager` chain), and deferring the import
    # to call time doesn't clear it; only dropping the `import` statement
    # itself does.
    embeddings = importlib.import_module("tessellate.ai.embeddings")

    rows = session.scalars(
        select(EmbeddingRecord).where(EmbeddingRecord.entry_id.in_((source_id, target_id)))
    ).all()
    vectors = {row.entry_id: embeddings.bytes_to_vector(row.embedding) for row in rows}
    if source_id not in vectors or target_id not in vectors:
        return None, None
    if vectors[source_id].shape != vectors[target_id].shape:
        return None, None  # mid embedding-model change, see search.similar_pairs
    score = embeddings.cosine_similarity(vectors[source_id], vectors[target_id])
    #: **What the two notes share, in words, when they share something a
    #: person can check** (INBOX 691): a tag, a name, one naming the other,
    #: the same category in the same week (`link_wording`). The score stays
    #: in `reason_confidence` either way; "similar in meaning" is what is left
    #: when the vectors are all there is.
    if score >= AUTO_REASON_THRESHOLD:
        return link_facts.reason_for(session, source_id, target_id) or AUTO_REASON_TEXT, round(score, 2)
    if score + TEMPORAL_RESCUE_BOOST >= AUTO_REASON_THRESHOLD and _shares_a_date(
        session, source_id, target_id
    ):
        specific = link_facts.reason_for(session, source_id, target_id)
        return specific or AUTO_REASON_TEXT_TEMPORAL, round(score, 2)
    return None, None


def _seal_reason(reason: str | None) -> str | None:
    """A link reason, encrypted for storage, for a link that touches a private
    note. `None` when there is nothing to seal or the vault is closed: a
    private note cannot be written while the vault is locked, and a reason
    that cannot be sealed is dropped rather than stored in the clear.
    """
    from tessellate.core import crypto, vault

    key = vault.key()
    if not reason or key is None:
        return None
    return crypto.encrypt(key, reason)


def _set_stored_reason(session: Session, link: EntryLink, stored: str | None) -> None:
    """Write `entry_links.reason` exactly as given, bypassing the attribute.

    The column decrypts on load (`database.LinkReason`), so the attribute
    holds plaintext whenever the vault is open, and assigning the plaintext
    back would look like "no change" to the ORM and write nothing. A Core
    update puts the real stored string in, and the expire makes the next
    read of the attribute go back through the decrypting load.
    """
    session.execute(update(EntryLink).where(EntryLink.id == link.id).values(reason=stored))
    session.expire(link, ["reason"])


def _seal_props(props: dict | None) -> str | None:
    """`_seal_reason` for link properties: the encrypted JSON of the object,
    or `None` (dropped) when there is nothing to seal or the vault is closed.
    """
    from tessellate.core import crypto, vault

    key = vault.key()
    if not props or key is None:
        return None
    return crypto.encrypt(key, json.dumps(props))


def _set_stored_props(session: Session, link: EntryLink, stored: str | dict | None) -> None:
    """`_set_stored_reason` for `entry_links.props`: a Core update writes the
    stored form as given (ciphertext string, plain object or null) and the
    expire sends the next read back through the decrypting load."""
    session.execute(update(EntryLink).where(EntryLink.id == link.id).values(props=stored))
    session.expire(link, ["props"])


def _touches_private(session: Session, link: EntryLink) -> bool:
    ends = session.scalars(
        select(Entry.is_private).where(
            Entry.id.in_((link.source_entry_id, link.target_entry_id))
        )
    ).all()
    return any(ends)


def _redact_link_audit(session: Session, entry: Entry, key: bytes) -> None:
    """Take a private note's link reasons out of the activity log.

    The "linked" and "relinked" rows spell the reason in `detail` and carry
    it in `payload.after.reason`, both in the clear when the link was made
    before the note went private. The detail loses its parenthesis (the
    reason is the only part that is about the notes' meaning; the ids stay
    so the log still reads), and the payload's copy is encrypted like the
    content next to it.
    """
    from tessellate.core import crypto
    from tessellate.core.database import AuditLog

    own = f"-> entry {entry.id}"
    rows = session.scalars(
        select(AuditLog).where(
            AuditLog.entity_type == "entry",
            AuditLog.action.in_(("linked", "relinked")),
            or_(
                AuditLog.entity_id == entry.id,
                AuditLog.detail.like(f"{own} (%", escape=LIKE_ESCAPE),
            ),
        )
    )
    for row in rows:
        if row.detail and " (" in row.detail:
            row.detail = row.detail.split(" (", 1)[0]
        payload = row.payload
        state = payload.get("after") if isinstance(payload, dict) else None
        text = state.get("reason") if isinstance(state, dict) else None
        if isinstance(text, str) and text and not crypto.is_encrypted(text):
            row.payload = {**payload, "after": {**state, "reason": crypto.encrypt(key, text)}}


def _link_between(session: Session, source: Entry, target: Entry) -> EntryLink | None:
    """The link joining the two notes, in either direction."""
    return session.scalar(
        select(EntryLink).where(
            or_(
                (EntryLink.source_entry_id == source.id)
                & (EntryLink.target_entry_id == target.id),
                (EntryLink.source_entry_id == target.id)
                & (EntryLink.target_entry_id == source.id),
            )
        )
    )


def _link_reason(
    session: Session, source: Entry, target: Entry, reason: str | None, reason_confidence: float | None
) -> tuple[str | None, float | None]:
    """The reason to store and its confidence: the given one, else a deduced one."""
    reason = (reason or "").strip() or None
    #: A reason the suggestions' signals wrote keeps their confidence (KG9);
    #: a person's own words have none, as before.
    confidence = None if reason is None or reason_confidence is None else max(0.0, min(1.0, reason_confidence))
    if reason is None:
        reason, confidence = _deduce_reason(session, source.id, target.id)
    return reason, confidence


def _log_linked(
    session: Session, link: EntryLink, source: Entry, target: Entry, reason: str | None, shown_reason: str | None
) -> None:
    detail = f"-> entry {target.id}" + (f" ({shown_reason})" if shown_reason else "")
    log_action(
        session,
        "linked",
        "entry",
        source.id,
        detail,
        payload={
            "after": {
                "link_id": link.id,
                "source_entry_id": source.id,
                "target_entry_id": target.id,
                "reason": reason,  # as stored: ciphertext on a private link
                "link_type": link.link_type,
            }
        },
    )


@events.writes("entry", "linked")
def create_link(
    session: Session,
    source: Entry,
    target: Entry,
    reason: str | None = None,
    link_type: str | None = None,
    origin: str | None = None,
    reason_confidence: float | None = None,
    props: dict | None = None,
) -> EntryLink | None:
    """Manually connect two entries. Returns None if the link already
    exists (either direction) or the user tried to link an entry to
    itself. Commits on success.

    `reason` is optional free text, "why are these connected?", the thing
    a shared tag or a reply thread says on its own and a link doesn't. Not
    required: most links are still obviously why (two notes about the same
    trip), and forcing an explanation on every one would make linking
    slower for the common case to help the uncommon one. When nobody gives
    one, `_deduce_reason` gets a try instead of leaving the link mute.
    """
    if source.id == target.id:
        return None
    # **A draft cannot be linked to a committed note.** Asked for directly:
    # "draft notes shouldnt be able to connect with actual notes, they need to
    # be separate."
    #
    # Drafts are already excluded from every other view in the app, the
    # sidebar counts, the category lists, the Ask box's retrieval: precisely
    # because an unfinished note is not part of the notebook yet. A link is the
    # one thing that was still crossing that line, and it crossed it in the
    # worst direction: the link outlives the draft's own invisibility, so a
    # committed note quietly grew an edge to something the reader cannot see
    # from anywhere else.
    #
    # Guarded here rather than in the picker because every route in reaches
    # this function: the UI's link button, the AI's linking tool, the
    # auto-linker and the graph, and a rule enforced in one caller is a rule
    # three other callers do not have.
    #
    # Draft-to-draft is allowed, and that is the literal reading of the
    # request: drafts are to be separate *from real notes*, not from each
    # other. Two drafts of the same idea are exactly the pair worth connecting
    # before either is saved. (A link made that way and then half-committed, 
    # one draft saved, the other not, is left alone: it was legitimate when it
    # was made, and deleting a person's link on their behalf because they
    # finished one end of it first is a bigger claim than this rule supports.)
    if bool(source.is_draft) != bool(target.is_draft):
        return None
    if _link_between(session, source, target) is not None:
        return None
    reason, confidence = _link_reason(session, source, target, reason, reason_confidence)
    # A reason is a sentence about the two notes, so on a link with a private
    # end it is stored encrypted and kept out of the activity log's text
    # (`entry_links.reason` decrypts on load, `database.LinkReason`).
    private_link = bool(source.is_private or target.is_private)
    shown_reason = None if private_link else reason
    if private_link:
        reason = _seal_reason(reason)
        stored_props = _seal_props(props)
    else:
        stored_props = dict(props) if props else None
    # An unrecognised kind is stored as null rather than rejected: the column
    # is advisory (it styles an edge and weights a traversal), and refusing an
    # otherwise-valid link because a caller sent a typo would trade a working
    # connection for a validation error nobody asked for.
    kind = link_type if is_link_type(session, link_type) else None
    link = EntryLink(
        source_entry_id=source.id,
        target_entry_id=target.id,
        reason=reason,
        reason_confidence=confidence,
        link_type=kind,
        origin=origin,
        props=stored_props,
        # **The link belongs to the space its notes are in, whoever made it.**
        # A new row usually takes its space from `session.info["workspace_id"]`
        # (the before-flush hook in core/database.py), which is set from the
        # request's `X-Workspace-ID` header. A background pass has no request
        # and no header: `ai/autonomous.py` opens a plain session, so every
        # link the librarian created was written with the column default,
        # "default". Measured: two notes in `space-b`, a link made the way the
        # night shift makes one, and the space that owns both notes could see
        # zero links.
        #
        # Taken from the source note rather than from the session, because
        # that is the fact that is true in both cases: in a request the note
        # is already in the session's space, and in a background pass the note
        # is the only thing that knows.
        workspace_id=source.workspace_id or "default",
    )
    session.add(link)
    session.flush()
    if private_link:
        # The attribute holds the ciphertext just stored; make the next read
        # go back through the decrypting load (`expire_on_commit` is off).
        session.expire(link, ["reason", "props"])
    _log_linked(session, link, source, target, reason, shown_reason)
    session.commit()
    return link


def backfill_link_reasons(session: Session) -> dict:
    """Give `_deduce_reason` a try on every existing link that has none.

    Asked directly: *"none of my notes have a linked reason yet, is there
    an easy way to give them all a reason?"* There wasn't one: `_deduce_reason`
    only ever ran at the moment `create_link` made a *new* link, so a
    notebook full of links made before that existed (or made without an
    embedding backend running at the time) stays mute forever with no way to
    revisit it. This is that revisit, run once over every link rather than
    one at a time.

    Same rule as a fresh link: a reason a person already gave is never
    touched, and a link that still can't be deduced (no embedding for one or
    both notes, or a score under the threshold) is left exactly as it was, 
    "no reason" is still the honest answer, not a false one manufactured to
    fill the field.
    """
    reasonless = list(
        session.scalars(select(EntryLink).where(EntryLink.reason.is_(None)))
    )
    updated = 0
    for link in reasonless:
        reason, confidence = _deduce_reason(
            session, link.source_entry_id, link.target_entry_id
        )
        if reason is not None:
            link.reason = reason
            link.reason_confidence = confidence
            updated += 1
    if updated:
        log_action(session, "backfilled", "entry", detail=f"reasons for {updated} link(s)")
        session.commit()
    return {"checked": len(reasonless), "updated": updated}


def remove_link(session: Session, source: Entry, target: Entry) -> bool:
    """Disconnect two entries, whichever way round the link was made.

    Returns False when there was nothing to remove, so a caller can say "those
    aren't linked" rather than reporting a success that changed nothing.

    Direction-agnostic on purpose, matching `create_link`: a link is a
    connection rather than an arrow, and requiring the caller to know which
    note was the source would make removal fail for half of them depending on
    who made the link.
    """
    link = session.scalar(
        select(EntryLink).where(
            or_(
                (EntryLink.source_entry_id == source.id)
                & (EntryLink.target_entry_id == target.id),
                (EntryLink.source_entry_id == target.id)
                & (EntryLink.target_entry_id == source.id),
            )
        )
    )
    if link is None:
        return False
    delete_link(session, link)
    return True


def set_link_reason(session: Session, link: EntryLink, reason: str | None) -> EntryLink:
    """A person setting, changing, or clearing a link's reason by hand.

    Always wins over whatever `_deduce_reason` guessed: `reason_confidence`
    is cleared here because a person's words aren't a similarity score, and
    null already means "not deduced", so an edited link and a freshly
    auto-reasoned one that hasn't been touched stay tellable apart.
    """
    text = (reason or "").strip() or None
    link.reason_confidence = None
    if _touches_private(session, link):
        # Encrypted, and not spelled in the activity log (see `create_link`).
        _set_stored_reason(session, link, _seal_reason(text))
        detail = f"-> entry {link.target_entry_id}"
    else:
        link.reason = text
        detail = f"-> entry {link.target_entry_id}" + (f" ({text})" if text else "")
    log_action(session, "relinked", "entry", link.source_entry_id, detail)
    session.commit()
    return link


def is_link_type(session: Session, key: str | None) -> bool:
    """A built-in or a custom type's key (KG3)."""
    if not key:
        return False
    return key in relation_types.kinds(session)


def relation_label(types: dict[str, dict], link_type: str | None, outgoing: bool) -> str | None:
    """What a link of this type is called from one end: its name from the
    source, its inverse from the target (when it has one). None for an
    untyped link or a type no longer known."""
    kind = types.get(link_type or "")
    if kind is None:
        return None
    if not outgoing and kind["directed"] and kind["inverse"]:
        return kind["inverse"]
    return kind["name"]


def set_link_props(session: Session, link: EntryLink, props: dict | None) -> EntryLink:
    """Replace a link's properties (KG3); an empty object clears them."""
    if _touches_private(session, link):
        _set_stored_props(session, link, _seal_props(props))
    else:
        _set_stored_props(session, link, dict(props) if props else None)
    log_action(session, "relinked", "entry", link.source_entry_id, f"-> entry {link.target_entry_id} (properties)")
    session.commit()
    return link


def set_link_two_way(session: Session, link: EntryLink, two_way: bool | None) -> EntryLink:
    """Make a link run both ways or one way (INBOX 693), or null to let its
    type decide again (`is_two_way_link`)."""
    link.two_way = two_way
    log_action(
        session,
        "relinked",
        "entry",
        link.source_entry_id,
        f"-> entry {link.target_entry_id} ({'two-way' if two_way else 'one-way' if two_way is False else 'direction by type'})",
    )
    session.commit()
    return link


def is_two_way_link(link_two_way: bool | None, link_type: str | None, types: dict[str, dict]) -> bool:
    """Whether a link is drawn with no arrow: its own choice when it has
    one, else its type's (a type with no inverse has no direction), else one
    way (INBOX 693)."""
    if link_two_way is not None:
        return bool(link_two_way)
    kind = types.get(link_type or "")
    return bool(kind) and not kind["directed"]


def set_link_type(session: Session, link: EntryLink, link_type: str | None) -> EntryLink:
    """Give a link a kind, built-in or custom (KG3), or none (GRAPH_PLAN KG9:
    the inbox's type suggestions, and the link menu's Type). The caller has
    checked the key; an unknown one here is a bug, so it raises."""
    if link_type is not None and not is_link_type(session, link_type):
        raise ValueError(f"unknown link type {link_type!r}")
    before = link.link_type
    link.link_type = link_type
    log_action(
        session,
        "relinked",
        "entry",
        link.source_entry_id,
        f"-> entry {link.target_entry_id} ({link_type or 'untyped'})",
        payload={"before": {"link_type": before}, "after": {"link_id": link.id, "link_type": link_type}},
    )
    session.commit()
    return link


def apply_audited_reason(link: EntryLink, reason: str) -> None:
    """Set a link's reason from the background audit, field mutation only,
    no commit, no audit-log row.

    `set_link_reason` is right for a person editing one link: they did one
    thing, so one commit and one "relinked" row is an honest record. The
    background audit (`ai.links.audit_vague_links`) is the opposite shape, 
    up to a `limit` of links rewritten in one pass, and calling
    `set_link_reason` per link there was the bug: a 500-link backfill did 500
    commits and left 500 near-identical "relinked" rows in the user's
    activity log, drowning out the log entries a person actually made. This
    just sets the fields; the caller commits once for the whole batch and
    writes one summary log row.

    Same field-level meaning as `set_link_reason`: `reason_confidence` is
    cleared because a reason the AI wrote out in words is no longer a guess
    from embedding similarity: see `EntryLink.reason_confidence`.
    """
    link.reason = (reason or "").strip() or None
    link.reason_confidence = None


def delete_link(session: Session, link: EntryLink) -> None:
    log_action(
        session,
        "unlinked",
        "entry",
        link.source_entry_id,
        f"-> entry {link.target_entry_id}",
    )
    session.delete(link)
    session.commit()


def links_for_entry(session: Session, entry: Entry) -> list[tuple[EntryLink, Entry]]:
    """All links touching this entry, with the entry on the other end."""
    links = session.scalars(
        select(EntryLink).where(
            or_(
                EntryLink.source_entry_id == entry.id,
                EntryLink.target_entry_id == entry.id,
            )
        )
    )
    result = []
    pending = []
    for link in links:
        other_id = (
            link.target_entry_id
            if link.source_entry_id == entry.id
            else link.source_entry_id
        )
        other = session.get(Entry, other_id)
        if other is not None:
            result.append((link, other))
        else:
            pending.append((link, other_id))
    stand_ins = sealed_stand_ins(session, {other_id for _link, other_id in pending})
    result += [(_placeholder_link(link), stand_ins[other_id]) for link, other_id in pending if other_id in stand_ins]
    return result
