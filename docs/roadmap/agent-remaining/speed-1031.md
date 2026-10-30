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
