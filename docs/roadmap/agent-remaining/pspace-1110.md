# pspace-1110: private spaces (INBOX 1727 part 2)

Branch `agent/pspace-1110` from `claude/next-queue-1102`. Port 8794.

## Plan

Membership is the privacy; the existing private-note sealing is the one
crypto path (`entry/manager.set_private`, the vault DEK). Three layers:

1. **Ciphertext at rest.** A note or board in a private space is a private
   note (`set_private`). Documents get `is_private` and the same DEK:
   `core/database.py` adds a `SealedText` column type (decrypts on load, as
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

- b7a7d45e0 server: flags and migration d2f6b8a4c1e7, SealedText columns, the
  join hook (anything made in or moved into a private space is sealed),
  spacelock, routes_private_spaces (status, unlock, lock, touch, PUT private),
  the deps gate (ORM filter, raw search, 423 writes, exports, AI paths),
  private reminders, board and document audit redaction.
- a1aba9fd9 window: Private switch built on first open (boot element cap),
  lock glyph, unlock prompt (password or PIN), input-fed idle touch (no
  timer), pagehide lock, the note menu's locked Private row, the move-out
  question, the idle minutes in Settings, the Guide topic and lead.
- Drive on 8794 (fake in-memory PIN store): created through the dialog
  (switch row 493x57, help '?' present), entered with the password; locked:
  no leak on 12 read routes x 3 headers, note GET 404, counts 0/0, write 423;
  unlocked by password and by PIN 2468 (wrong PIN 401); move out: "Keep it
  private" focused by default, kept private; "Make it ordinary" unsealed.

## Left

- Atlas reads documents in a chat opened inside a private space, but never
  its notes (the `is_private` filters in chat context exclude them).
- Links from ordinary notes to a sealed note: no locked placeholder of their own.
- Browser notifications for a private reminder (the desktop notifier is done).
- A document outside a private space has no Private switch of its own.
- Restoring a deleted private space while locked is untested.
- Windows Hello (next step, out of this batch).

## Not verified

- Dashboard, recents, palette, notifications and the desk companion were not
  driven one by one; they read through the same ORM filter.
- The real OS keyring PIN path (only the fake store).
- The idle lock in a browser over ten real minutes (unit-tested with a clock).
- The note menu's locked Private row was not opened in the browser.
