# autocorrect-skeleton-1017: INBOX 904 B04 (beyond the popup) and the new chat page skeleton

Sonnet agent, worktree agent-ac5546dc4514e7c41, port 8791. Sweeps: `scratchpad/ui-sweeps/autocorrectmenu.js`, `chatemptypaint.js`, `chatemptysettle.js`, `computeddump.js`. Tests: `tests/test_autocorrect.py`, `tests/test_ui_1017b.py`.

Done:
- c8da4bc B04: hover on the underline opens the Keep, Put back, Edit menu; the document editor draws the underline too (`autocorrectShow`).
- Boot CSS: sixteen pure `.ocr-*` rules to library-lazy.css (computed styles identical at 1440, 1024, 390).
- New chat page: mark and heading at once, skeleton starters in `#chat-suggest`.

Left (one line each):
- B04, "autocorrect with Harper": the table and dictionary corrector is what runs; Harper (vendored, `harper-worker.js`) is the grammar linter and does not auto-apply. Autocorrect on reminders and the composer's output (INBOX 1299) is placed in BACKLOG.
- Hover is mouse only; touch keeps the tap. Not driven with a real touch device.
- Ctrl+Z in the document right after a correction with the underline showing: relied on the document's own history step (unchanged), not re-driven.
