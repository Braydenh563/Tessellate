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

## Round 2 (pspace2-1110)

- Chat: `private_space.chat_notes` matches the open space's sealed notes by
  the question's words (they are in no index) for a chat opened inside it;
  `deps` marks that turn private (`private_turn.IN_PRIVATE_SPACE`).
  Conversation title and messages, AskTurn question and answer and
  Reminder text are `SealedText` while their space is private, kept out of
  the search index, and redacted in the audit log.
- Links: `manager.sealed_stand_ins` gives a link to a note in a locked
  private space an "A private note" stand-in (no title, reason or
  properties) in the note view, the list, Connections, backlinks and the
  graph (a muted dashed `private:<id>` node, not clickable).
- Reminders: `notice` on every reminder row; status.js announces it.
- Delete and restore of a private space are 423 unless open; a restore
  seals everything that comes back (a note made ordinary meanwhile too).
- Found and fixed: the idle lock's toast never showed (the unlock left the
  window's state closed); `due_now` read `workspace_id` off fakes without
  it (round 1, tests/test_reminder_notifier.py); the auth check's session
  ran the private-space read (perf budget).
- Drive on 8794: locked, no secret or title in dashboard, notes, timeline,
  reminders, library, graph, the notifications panel or the palette (it
  echoes only the typed words); graph shows "A private note"; note view
  link preview "A private note"; counts 0/0. Inside: the menu row "Private
  in this space" drawn (span 131x22; its button carries aria-disabled per
  menus.js:1344, not measured); the centre recorded "A private reminder".
  Idle at 1 minute: 78 s still, a click, status open false, toast "Private
  spaces locked." with Unlock, no secret left in the page.

## Left

- Windows Hello (next batch).
- Recordings, bookmarks and files made inside a private space are not
  sealed (only notes, documents, boards, chats, Ask turns and reminders).
- Deleting a locked private space from the window shows the 423 message;
  it does not offer the unlock prompt.

## Not verified

- The desk companion while locked.
- The real OS keyring PIN path (only the fake store).
- A real model answering in a private-space chat (fake transport only).
