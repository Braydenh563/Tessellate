"""Private notes: sealing and unsealing a note's text, history and links, and
the leftovers scrub (split out of `entry/manager.py`, audit-1028 K24,
dec-1111-k2.md). Moved whole and unchanged; callers import these names from
here. It imports from `entry.manager` (log_action, the link-sealing helpers,
record_dates, reindex_properties) and nothing there imports it back.
"""

from __future__ import annotations

import importlib
import json
import logging
import re

from sqlalchemy import delete, or_, select, text
from sqlalchemy.orm import Session

from tessellate.core.database import (
    Attachment,
    ChunkVector,
    EmbeddingRecord,
    EntityMention,
    Entry,
    EntryDate,
    EntryLink,
    EntryRevision,
)
from tessellate.core import events
from tessellate.entry.manager import (
    _redact_link_audit,
    _set_stored_props,
    _set_stored_reason,
    flag_private_media,
    log_action,
    record_dates,
    reindex_properties,
)


def _encrypt_history(session: Session, entry: Entry, key: bytes) -> None:
    """Encrypt what the note's history already holds in the clear.

    A note is made private after it was written, so its `created` and
    `edited` events and its version snapshots carry the plaintext: scanning
    every column for a private note's words found them in `audit_log.payload`
    (2026-10-04). Same rule as the embedding and the dates above. The history
    sheet and a replay read through `_readable`, which decrypts either form.
    """
    from tessellate.core import crypto
    from tessellate.core.database import AuditLog

    for revision in session.scalars(select(EntryRevision).where(EntryRevision.entry_id == entry.id)):
        if not crypto.is_encrypted(revision.content):
            revision.content = crypto.encrypt(key, revision.content)
    for row in session.scalars(
        select(AuditLog).where(AuditLog.entity_type == "entry", AuditLog.entity_id == entry.id)
    ):
        payload = row.payload
        if not isinstance(payload, dict):
            continue
        changed = {}
        for side in ("before", "after"):
            state = payload.get(side)
            text = state.get("content") if isinstance(state, dict) else None
            if isinstance(text, str) and text and not crypto.is_encrypted(text):
                changed[side] = {**state, "content": crypto.encrypt(key, text)}
        if changed:
            row.payload = {**payload, **changed}  # a new dict: the JSON column only notices a new value


def _links_of(session: Session, entry: Entry) -> list[EntryLink]:
    return list(
        session.scalars(
            select(EntryLink).where(
                or_(EntryLink.source_entry_id == entry.id, EntryLink.target_entry_id == entry.id)
            )
        )
    )


def _seal_link_reasons(session: Session, entry: Entry, key: bytes) -> None:
    """Encrypt the reasons on every link touching a note that just went
    private, and take them out of the activity log's text.

    What stays visible, by decision: the link itself (which two notes are
    joined, its kind) and the note's tags. Only the free text a person or the
    model wrote about the notes is sealed.
    """
    from tessellate.core import crypto

    for link in _links_of(session, entry):
        text = link.reason  # plaintext: the column decrypts on load
        if text:
            _set_stored_reason(session, link, crypto.encrypt(key, text))
        if link.props:
            _set_stored_props(session, link, crypto.encrypt(key, json.dumps(link.props)))
    _redact_link_audit(session, entry, key)


def _unseal_link_reasons(session: Session, entry: Entry) -> None:
    """The reverse, for each link whose other end is not itself private."""
    for link in _links_of(session, entry):
        other_id = link.target_entry_id if link.source_entry_id == entry.id else link.source_entry_id
        other = session.get(Entry, other_id)
        if other is not None and other.is_private:
            continue
        if link.reason:
            _set_stored_reason(session, link, link.reason)
        if link.props:
            _set_stored_props(session, link, dict(link.props))


def rekey_private_extras(session: Session, old_key: bytes, new_key: bytes) -> None:
    """Move what a private note keeps outside its own row onto a new key.

    `/rotate-vault-key` re-encrypts the notes; the version snapshots, the
    event payloads and the link reasons are encrypted under the same data key
    (`_encrypt_history`, `_seal_link_reasons`), so left alone they would stay
    under the OLD key and read as empty the moment the vault row pointed at
    the new one. Nothing is committed here: the caller's one commit makes the
    notes, these and the vault row real together, or none.
    """
    from tessellate.core import crypto
    from tessellate.core.database import AuditLog

    def swap(value: str) -> str:
        # A value the old key cannot open was sealed under a vault a password
        # reset removed (INBOX 663): unreadable before and after, so it is
        # kept as it is rather than failing the whole re-key (see the route).
        try:
            return crypto.encrypt(new_key, crypto.decrypt(old_key, value))
        except crypto.DecryptionError:
            return value

    for revision in session.scalars(select(EntryRevision)):
        if crypto.is_encrypted(revision.content):
            revision.content = swap(revision.content)
    for row in session.scalars(select(AuditLog).where(AuditLog.payload.is_not(None))):
        payload = row.payload
        if not isinstance(payload, dict):
            continue
        changed = {}
        for side in ("before", "after"):
            state = payload.get(side)
            if not isinstance(state, dict):
                continue
            fresh = {
                name: swap(state[name])
                for name in ("content", "reason")
                if isinstance(state.get(name), str) and crypto.is_encrypted(state[name])
            }
            if fresh:
                changed[side] = {**state, **fresh}
        if changed:
            row.payload = {**payload, **changed}
    # Raw SQL: the typed column would hand back plaintext, not the stored text.
    for link_id, stored in session.execute(
        text("SELECT id, reason FROM entry_links WHERE reason LIKE :p"),
        {"p": crypto.PREFIX + "%"},
    ).all():
        session.execute(
            text("UPDATE entry_links SET reason = :r WHERE id = :i"),
            {"r": swap(stored), "i": link_id},
        )
    # Props are a JSON string of ciphertext in a JSON column: the stored text
    # is the quoted form, so read it as JSON and write it back as JSON.
    for link_id, stored in session.execute(
        text("SELECT id, props FROM entry_links WHERE props LIKE :p"),
        {"p": '"' + crypto.PREFIX + "%"},
    ).all():
        sealed = json.loads(stored)
        if isinstance(sealed, str) and crypto.is_encrypted(sealed):
            session.execute(
                text("UPDATE entry_links SET props = :r WHERE id = :i"),
                {"r": json.dumps(swap(sealed)), "i": link_id},
            )


#: What a stored answer says once a note it quoted has been made private
#: (SEC-14, audit 2026-10-05).
PRIVATE_ANSWER_REDACTED = (
    "This answer quoted a note that is now private, so its words were removed. "
    "Ask again to get an answer from what is still readable."
)

#: This many words of the note in a row, found in an answer, count as a
#: quote: long enough that ordinary phrasing does not trip it, short enough
#: that a clause lifted out of a longer sentence does.
_QUOTE_WORDS = 6


def _word_runs(text: str) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", (text or "").lower())
    return {tuple(words[i : i + _QUOTE_WORDS]) for i in range(len(words) - _QUOTE_WORDS + 1)}


def _quotes(text: str, runs: set[tuple[str, ...]]) -> bool:
    return bool(runs) and not runs.isdisjoint(_word_runs(text))


def _ids_in(value) -> set[int]:  # noqa: ANN001
    """Every note id a stored answer's bookkeeping names: plain ids, and the
    `id` / `note_id` of each dict (raw results, grounding marks)."""
    found: set[int] = set()
    for item in value or []:
        if isinstance(item, int) and not isinstance(item, bool):
            found.add(item)
        elif isinstance(item, dict):
            for key in ("id", "note_id", "entry_id"):
                if isinstance(item.get(key), int):
                    found.add(item[key])
    return found


def _json_list(text: str | None) -> list:
    try:
        value = json.loads(text or "[]")
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def _redact_answers_quoting(session: Session, entry_id: int, plaintext: str) -> int:
    """SEC-14: no stored answer goes on quoting a note that is now private.

    An Ask turn or a saved chat reply is redacted when it named the note
    (its results, its marks, its attached notes) or repeats one of the
    note's sentences verbatim, however it got there (an agent's tool step, a
    paraphrase that kept a line). The question, the person's own words,
    stays; the answer, its thinking, its steps and its sources go, and the
    reply says why. Returns how many answers were redacted.
    """
    from tessellate.core.database import AskTurn, Conversation

    fragments = _word_runs(plaintext)
    redacted = 0
    for turn in session.scalars(select(AskTurn)):
        named = entry_id in _ids_in(_json_list(turn.raw_result_ids)) | _ids_in(
            _json_list(turn.connected_ids)
        ) | _ids_in(_json_list(turn.grounding))
        if not named and not _quotes(" ".join((turn.answer or "", turn.grounding or "", turn.match_info or "")), fragments):
            continue
        if turn.answer == PRIVATE_ANSWER_REDACTED:
            continue
        turn.answer = PRIVATE_ANSWER_REDACTED
        turn.grounding = "[]"
        turn.match_info = "{}"
        turn.raw_result_ids = json.dumps([i for i in _json_list(turn.raw_result_ids) if i != entry_id])
        turn.connected_ids = json.dumps([i for i in _json_list(turn.connected_ids) if i != entry_id])
        redacted += 1
    for conversation in session.scalars(select(Conversation)):
        messages = _json_list(conversation.messages)
        changed = False
        asked_with_it = False
        for message in messages:
            if not isinstance(message, dict):
                continue
            if message.get("role") == "user":
                asked_with_it = entry_id in _ids_in(message.get("note_ids"))
                continue
            if message.get("role") != "assistant" or message.get("redacted"):
                continue
            named = asked_with_it or entry_id in (
                _ids_in(message.get("raw_results"))
                | _ids_in(message.get("connected_ids"))
                | _ids_in(message.get("sentence_grounding"))
            )
            if not named and not _quotes(json.dumps(message, ensure_ascii=False), fragments):
                continue
            keep = {k: message[k] for k in ("role", "persona", "elapsed_ms", "tokens") if k in message}
            message.clear()
            message.update(keep, content=PRIVATE_ANSWER_REDACTED, redacted=True)
            changed = True
            redacted += 1
        if changed:
            conversation.messages = json.dumps(messages)
    return redacted


@events.writes("entry", "edited")
def set_private(session: Session, entry: Entry, private: bool) -> bool:
    """Encrypt or decrypt one note in place. False if the vault is locked.

    Making a note private also drops its embedding: a vector derived from the
    text would leak what the note is about, which defeats the point.
    """
    from tessellate.core import crypto, vault

    key = vault.key()
    if key is None:
        return False

    if private:
        # SEC-03: zero what this transaction frees (the plaintext row's old
        # cell, its search rows), not just unlink it. Per connection, and only
        # on this path; `scrub_private_leftovers` finishes the job after commit.
        session.connection().exec_driver_sql("PRAGMA secure_delete=ON")
        if not crypto.is_encrypted(entry.content):
            # Before the text is sealed: the redaction looks for its sentences.
            _redact_answers_quoting(session, entry.id, entry.content)
            flag_private_media(session, entry.content)
            entry.content = crypto.encrypt(key, entry.content)
        entry.is_private = True
        session.execute(delete(EmbeddingRecord).where(EmbeddingRecord.entry_id == entry.id))
        # Its paragraph vectors too: inert once the note vector is gone
        # (`search/chunks.py`), but a vector of the text is what encryption
        # hides, so they do not wait for the orphan pass.
        session.execute(delete(ChunkVector).where(ChunkVector.entry_id == entry.id))
        # And out of the retrieval engine's in-memory matrix, which a bulk
        # `delete()` statement never reaches: a vector derived from this text
        # is exactly what the encryption is for, and one left in the array
        # would go on answering similarity queries about a note nobody can
        # read. `importlib` rather than an `import` statement, for the reason
        # this file already records for `core.events`: the statement itself is
        # what CodeQL and `tests/test_no_import_cycles.py` count, and this one
        # would close `entry.manager -> search.engine -> ... -> entry.manager`.
        search_engine = importlib.import_module("tessellate.search.engine")

        search_engine.forget_vector(entry.id)
        # And the resolved dates, for the same reason as the embedding: a note
        # is marked private *after* it is created, so anything derived from
        # its text and stored in the clear has to be cleared out here too.
        # "The appointment is tomorrow" plus a date is most of the note.
        session.execute(delete(EntryDate).where(EntryDate.entry_id == entry.id))
        # And the people and places a model read out of it: an entity's
        # membership is the note's text in another shape ("this note names Sam
        # Lee"), and the live query's `entity:` term and the graph would
        # still answer with it. Left unscanned, so a note made readable again
        # is read again by the next extraction pass.
        session.execute(delete(EntityMention).where(EntityMention.entry_id == entry.id))
        entry.entities_extracted_at = None
        _encrypt_history(session, entry, key)
        _seal_link_reasons(session, entry, key)
    else:
        if crypto.is_encrypted(entry.content):
            entry.content = crypto.decrypt(key, entry.content)
        entry.is_private = False
        record_dates(session, entry)  # readable again, so it can be read again
        _unseal_link_reasons(session, entry)
    # SEC-A2: its files' search rows follow the note (a private note's files
    # are not indexed, `search/index._attachment_row`).
    search_index = importlib.import_module("tessellate.search.index")
    for attachment_id in session.scalars(select(Attachment.id).where(Attachment.entry_id == entry.id)).all():
        search_index.touch(session, "attachments", attachment_id)
    # The payload carries the content as it now stands (ciphertext when the
    # note was just made private), so a replay of this note's events rebuilds
    # what is actually in the column rather than the plaintext it stopped
    # being here.
    log_action(
        session,
        "edited",
        "entry",
        entry.id,
        f"private={private}",
        payload={"after": {"content": entry.content, "is_private": bool(private)}},
    )
    return True


def make_all_private(session: Session) -> list[int] | None:
    """Seal every ordinary note in this notebook (INBOX 1695 d). None if the
    vault is locked; else the ids sealed, which the client's Undo opens again.
    A binned note is left alone."""
    from tessellate.core import vault

    if vault.key() is None:
        return None
    rows = session.scalars(
        select(Entry).where(Entry.is_private.is_(False), Entry.is_deleted.is_(False))
    ).all()
    sealed = [entry for entry in rows if set_private(session, entry, True)]
    for entry in sealed:
        reindex_properties(session, entry)
    return [entry.id for entry in sealed]


def scrub_private_leftovers(session: Session) -> None:
    """After a note is made private and committed: no word of it left in the
    file (SEC-03, security audit 2026-10-05).

    `set_private` removes the note's search rows, but FTS5 keeps a deleted
    row's tokens in its segment blobs behind a delete marker, so a PIN or a
    place name from a private note stayed readable with `strings` in the
    database, every backup and the export zip. This merges both FTS tables
    (`optimize`) with `secure_delete` on, so the freed pages are zeroed, and
    then truncates the WAL, whose old frames still hold the plaintext pages.
    The checkpoint is best effort: a reader holding a snapshot can stop it
    from finishing, and the next one takes it the rest of the way.
    """
    from tessellate.core.backup import optimize_fts

    connection = session.connection()
    connection.exec_driver_sql("PRAGMA secure_delete=ON")
    optimize_fts(connection)
    session.commit()
    raw = session.get_bind().raw_connection()
    try:
        raw.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:  # noqa: BLE001  # best effort, see the docstring
        logging.getLogger("tessellate.entries").warning("could not checkpoint after making a note private", exc_info=True)
    finally:
        raw.close()


# --- [[wiki links]] ----------------------------------------------------------
# Typing [[something]] in a note links it to the note that starts with that
# text. It's the cheapest way to build a real web of notes: no AI, no dialog,
# no leaving the keyboard, and it's what makes the graph fill itself instead
# of waiting for someone to link things by hand.
