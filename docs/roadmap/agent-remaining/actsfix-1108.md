# actsfix-1108: review of the chat acts (X17, X5, X8, X10)

## Log

- A (findings 1, 2, 11): a tag or category rename refuses a merge hidden by binned or locked private rows; the private hold covers the old and the new tag; `object_acts.guard` runs the same checks at `/chat/command/run`. A rename still changes binned rows (a restored note must not come back with the old tag); a test pins that Undo restores them exactly.
- B+C (3, 4, 6, 7, 8): note-number rename keeps its id; names holding "to" (quoted, or the longest old name that names something); a second request after "and" is said back; get back and recover need the bin said; restore all asks; restore treats private as missing, skips boards (the confirmed step refuses one too), whole words.
- D (5, 9): Undo of add to today carries `base_hash` of the text the act left (stale when the note changed); a create-today card finding the note already made adds to it; the typed words are read with a case-insensitive pattern on the original; a pointer ("it", "that") is asked about.
- E (10): "no, cancel that", "wait cancel", "no cancel it" (the follow-up reader had rewritten the question) close the card; the reply carries the label and the page closes only that card (`closeOpenActCard`); the stale comment is fixed; node-run tests reach `data-pending-act`.
- F (12): `_state` in test_acts.py compares the category id and its name (the id alone cannot see rename_category: the strict id form failed, so both are compared); the capability-line check no longer skips the rename acts.

## Left

- "put it in today's note" is read by the move reader first (asks to attach notes), not by the starter; left as the convention.
- Route auth: `/chat/command/run` has no route-level login or CSRF token of its own, like the other routers; the app-wide `OriginCheckMiddleware` refuses a cross-origin page (test added) and `VaultScope` carries the vault grants. Not verified: a LAN-mode session with a login.
