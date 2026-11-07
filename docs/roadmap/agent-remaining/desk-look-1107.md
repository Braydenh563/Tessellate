# desk-look-1107 (INBOX 1692 i: "You, from your name" ticked, desk figure stayed Atlas)

Done: the figure is re-read up to `FIGURE_READS` times while unsettled (`desk_companion.py` `_settled`); `_explain_figure` logs why your own companion has no frames; the Companion panel shows `note` from `frames_note` (drawing, or failed); help line in the desktop-companion topic.

Measured at 8798 (Chromium, `syncNameMarkBuddy` after `prefs.set`): the figure is drawn synchronously, `me` gives atlas:false (sig differs from Atlas), `persona` gives atlas:true (default persona), so candidates (1) read-before-redraw and (3) me-classed-as-Atlas did not reproduce.

Left:
- Windows, minimised app window: confirm `desk-frames.js` capture completes while the WebView2 page is hidden (requestAnimationFrame and image decode may be throttled; `TOTAL_WAIT` 180 s). The log line "could not draw the companion's frames (...)" or "drew 48 frames" in the launcher log tells which. If it stalls, capture needs the page visible (candidate 2/4), `core/overlay/capture.py` `fetch_frames`.
- A failed draw retries only after `RENDER_RETRY` (300 s) and only on the next restart; no timer re-triggers it. Consider a retry from the panel note.
- The desk tooltip does not carry the drawing line; only the Companion panel does.

INBOX 1692 (k) done: `_start_overlay` falls back to Atlas when a drawn companion's frames will not start, records `overlay_why`, and `_retry_overlay` re-arms the overlay at the next minimise (`OVERLAY_TRIES` 3); the card menu note names the reason; the card's `draw()` keys on name plus `nameMarkOwnFor(name)` (it kept the bare figure when only the look changed).
Owner's log (23:31:48): the host waited 3.0 s, the sprites (50 frames) finished ~1 s later; the give-up left a ghost window running and `overlay_failed` stuck. Fixed: start timeout 10 s (`overlay/host.py`, `runner.py`), a thread that comes up after `stop` closes itself, a due sync retries after `OVERLAY_RETRY_GAP` (20 s).
Left (k):
- The card drag log (placed stays at the end point while asked walks): not looked at, `_place` / `place_on_screen` in `desk_companion.py`.
- 48 vs 50 frames: `capture.CAPTURED` is 48 drawn names; the runner's 50 is `len(sprites.FRAME_NAMES)` (the two cards are composed in `write_set`, `card0`/`card1`); not a mismatch in files written, unconfirmed on disk.
- Windows: the true cause of the first failed start is unverified (the log line "the overlay could not start (...)" names it); measure how long `runner.start` takes after a `_stop_runner` on Windows (3 s default timeout, `overlay/runner.py` `start`).
- The card page reads `/preferences` once per visibility change; a look saved in the app while the card is up shows at the next visibility change.
- "Disappeared after showing" (overlay died) is handled by the card fallback plus the retry, but its cause (`overlay: the window thread ended on its own`) is not found.
