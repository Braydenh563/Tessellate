# speed-1031 (agent speed-1031, branch agent/speed-1031)

Done: step 1 (this commit): INBOX 1465 items 1, 2, 3 and the boot select pass. Measured on a 300-note notebook, fake transport, loaded 4-core machine (load 10 to 20), so read the ratios, not the milliseconds.
- Keydown: layout reads moved behind the typing return and the matching bare key. Keydown with dirty layout 1.75 to 9.95 ms became 0.05 to 0.17 ms; typing 1.5 to 3.7 ms became 0.04 ms.
- Scroll-top button: only its own scroller wakes it (capture heard every scroller).
- Constellation resync: width from the ResizeObserver entry, no `clientWidth` read after writes.
- Boot select enhancement: 148 ms (267 ms in one run) became 8 to 21 ms; rows build on open, label clone only for an unnamed select.
- Keyboard inset no longer measured at boot.
Next: graph open, then unlock.

Found, not fixed:
- Graph open: `graph-canvas.js` onload is 260 ms with 207 ms forced layout (top-level wiring, `onDomReady(graphPaneWire)` near line 6799 and `graphPaneFollow` near 6685 are the candidates; not bisected). The owner's lag log did not list it; it came from the sweep.
- Item 4, notes-list 143 ms task: reproduced as a first-call compile of the windowed render; moving the work only shifts it. A warm-up attempt cost +91 gzip bytes against a cap with 17 spare, so it was reverted. Needs a lazy split or a byte budget move (owner call).
- Item 5, `/auth/unlock` 3.9 s: pure key derivation, bcrypt cost 12 about 65 percent, scrypt unwrap about 30 percent, the rest negligible. Running the two in parallel threads would cut it by about the smaller share, but verifying that needs a quiet machine. `routes_auth.py` near line 924.
- Item 5, `/models/status` 3.2 s: 7 to 40 ms here without a runner. The time is the model-list flight waiting on a busy real runner (budgets `INSTALLED_REFRESH_BUDGET` 0.25, `INSTALLED_COLD_BUDGET` 1.0 in `routes_models.py`). Needs a real runner to reproduce.
- Item 2, the owner's 64 to 89 ms resync and item 1's 311 ms forced layout did not reproduce on a fresh notebook; the fixes remove the reads by construction, not by a before/after of the owner's numbers.
- Boot: `spaces-find` initAuth, `phone-shell.js` header-height and notes-subtab `write` forced layouts (about lines 551 and 575), `settings.js` `measureLabelOptics` (a test pins its shape), ICU first use in `tickClocks`, Library bundle compile. Each is under 50 ms alone; none fits the byte caps without a lazy split.
- Byte caps: boot JS gzip total stands at 320581 against 320600, so any further fix must be byte-neutral or lazy.
- Real inference and runner behaviour are unverified (CLAUDE.md section 4).

## Pass 2 (agent speed2-1031, branch agent/speed2-1031), measured on 300 and 2,000 notes, load 8 to 12, so read the ratios
- [x] Graph open (1b91df4): the 207 ms of forced layout did not reproduce as one flush at `onload`; it is several style passes (tokens read, then size read after DOM writes, d3 zoom `clientWidth`, dock and rail reads at parse). Fixed: size from the observer entry, tokens and size read together, d3 `.extent`, no parse-time `write()` for the dock and rail tokens. Forced flushes over 3 ms: 15 to 8 in three runs (220 to 91 ms). What is left is one flush in `gcFitInsets` (the canvas rect after the observer's own canvas write; the cost is the card's custom-property recalculation, unavoidable once) and `revealActiveTab`'s `scrollIntoView` (13 to 33 ms, shared by every tab switch; its comment says deferring measured no faster).
- [x] Library and Timeline open: no long task in script. Timeline: 74 to 92 ms tasks are the frame lifecycle (style 18, layout 16, paint 17, layerize 35); script 14 ms. Library: 63 to 75 ms style recalculation of 65 built cards; `libraryColumnCount` 2 to 5 ms. Both already render a window (300 timeline rows of 2,000, 65 library cards). Nothing over 50 ms to fix in JS; `timelineScrollToToday` is a read, write, read loop by design ("rows below Today change height as they are scrolled past").
- [x] Notes list 143 ms: not a compile on a current head. The costly thing at 2,000 notes is `paintEntriesProgress` (27 to 46 ms, eight times, growing with the list); its gap now grows with the list (250 ms times list size over 800, at least 250): 8 repaints (about 225 ms) to 5 (about 140 ms). `shellFor` for 2,000 rows is 13 ms a repaint; a cloned template saved 10 percent, not done.
- [x] `.ai-status-popup` fade reads `--ui-fast` (was `--motion-fast`); with Interface animations off the computed duration is 0s (was 0.12s). `tests/test_motion_tokens.py` no longer exempts it.
- [x] Boot flushes: `tabFromTop` focus (31 to 58 ms down to under 2 ms, first Tab still the skip link), tab-strip glide reads before it writes, `setDocView` skips the hidden editor (27 ms). 
- Not done: `spaces-find` initAuth, `settings.js` `measureLabelOptics` (a test pins its shape), ICU first use in `tickClocks`, `renderNotesRail` rect (3 to 5 ms), `/auth/unlock` and `/models/status` (need a quiet machine and a real runner).
- Found: software canvas (`CanvasRenderingContext2D::FinalizeFrame`, 400 to 900 ms of the graph's settle in this sandbox) is the rest of the graph's long tasks; it is the sandbox, not the code.
