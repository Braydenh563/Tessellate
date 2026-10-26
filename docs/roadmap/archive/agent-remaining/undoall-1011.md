# undoall-1011: remaining (INBOX 898, undo and redo everywhere)

Ratchets: `tests/test_undo_coverage.py` (EXEMPT only shrinks; no GAP class left; `test_every_step_on_the_stack_has_a_redo`, `NO_REDO` empty). Helpers: `frontend/js/undo-kit.js` (lazy), `wbPushCall` and `wbRecordGesture` (board history), `core/undo_bin.py` (the server's undo bin).

Numbers: GAP entries 89 to 0. EXEMPT keeps only auth, read, send, settings, telemetry, job, inverse, board and purge, a reason each.

Live: `scratchpad/ui-sweeps/undoall.js`, 21 acts on a fresh data dir (port 8797), Ctrl+Z, Ctrl+Shift+Z or Ctrl+Y, again: 21 pass. 13 press the control, 8 call the handler the control calls. Not driven live: chat edit and resend, graph pins, the lightbox reading delete, a Forget everything, map branch cuts (their steps are held by the coverage test and the route tests). A board "call" step is not persisted across a reload by design.

undo3 (this round):
- Accepting a link type or a merge: the accept answers `correction_id`; Undo deletes that correction, Redo teaches it again (`tests/test_suggestions_inbox_kg9.py`).
- Making a space no longer reloads: the menu refreshes in place, one Undo step (Undo moves anything put in it to the default space, then deletes it), "Open it" on the notice. `spaces-find.js:initSpaceSwitcher` left EXEMPT.
- Settings, Recent changes: no row is "can't be undone". A never-set key is undone by `unset` on `PUT /preferences`; a value over the 12,000-byte entry cap is held in memory (undoes until the page reloads, then the row says so).
- Live, `scratchpad/ui-sweeps/undoall2.js` (19 acts, `ONLY=<regex>` runs a group; port 8788; Ctrl+Z, Ctrl+Shift+Z or Ctrl+Y, twice each, server rows compared): 19 of 19 pass, run in groups because Chromium crashed on a loaded host. Pressing the real control: wiki rename toast button, a file dropped into a note box, a space made (no reload), the lightbox reading trash, recording rename and delete (row menu), board library file import. Calling the handler the control calls: Forget everything, recording trim, chat edit-and-resend (tail swap and whole-chat swap; the model-free half: cut, new tail, the real `chatEditUndo`), graph pin (`gcTogglePin`), map Sever, Remove keeping the branch, turn a line around, reverse a cross-link, cross-link to a branch, board library delete (the panel menu item's own `run`). The map's step sits on the board's history, so the first run of the library acts with no board open failed Undo (correct: they need an open board).

Left, found while doing it:
- `tests/test_no_import_cycles.py` fails on main too (`question_noise` -> `spelling` -> `question_noise`), not from this work.
- A value over the history entry cap loses its Redo and Undo after a page reload (held in memory only).
