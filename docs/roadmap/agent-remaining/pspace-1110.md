# pspace-1110: private spaces (INBOX 1727 part 2)

Branch `agent/pspace-1110` from `claude/next-queue-1102`. Port 8794.

## Plan

Membership is the privacy; the existing private-note sealing is the one
crypto path (`entry/manager.set_private`, the vault DEK). Three layers:

1. **Ciphertext at rest.** A note or board in a private space is a private
   note (`set_private`). Documents get `is_private` and the same DEK:
   `core/sealed.py` adds a `SealedText` column type (decrypts on load, as
   `LinkReason` does) on `documents.title/content/threads`,
   `document_revisions.title/content`, `document_ai_edits.before/after`,
   `whiteboard_sketches.data`, `whiteboard_objects.data`; a `before_flush`
   hook encrypts any write to a row whose owner (the document, the board
   entry) is private, and refuses one when no key is loaded. Search rows,
   embeddings and dates follow `set_private`'s rules.
2. **Membership gate.** `spaces.is_private`. `core/spacelock.py` holds which
   sessions opened the private spaces, with an idle timeout (preference
   `private_space_idle_minutes`, 10) and a close on lock and page close.
   While a request's session has not opened them, `deps._open_session` puts
   every private space id in `session.info["sealed_workspaces"]` and the
   workspace filter (`database._add_workspace_filter`) drops their rows from
   every ORM read, for "All spaces", the space itself and no header alike;
   a write naming a locked private space is 423. Background work has no
   request and reads only non-private rows already.
3. **Moves.** `entries.sealed_by_space` and `documents.sealed_by_space`
   record that the space sealed it, so "Make it ordinary" unseals only those
   (a note private before it came in stays private). Turning Private on
   seals every member in one transaction (never half-sealed); the sweep
   `seal_space_members` is idempotent and runs again on unlock and on every
   move, so a crashed or partial run finishes itself.

Schema: one Alembic revision (four columns, additive, reversible).
UI: `.setting-check` switch in New space and Edit space, lock glyph in the
switcher, a locked panel with password and PIN, the note editor's Private
switch locked on with "Move it out of this space to share it", the move-out
two-way question, Settings auto-lock minutes. Help: help_chat, help topics,
manual parity.

## Done

## Left

## Not verified
