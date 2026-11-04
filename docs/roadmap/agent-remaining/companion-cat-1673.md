# Companion as a house cat (INBOX 1673, 1670 standing): what is left

Built (branch worktree-wf_ce827097-383-3): phases 1 to 5 of the design in one pass (see git log).

- Navigation moves nothing: `nameMarkBuddyTabChanged` (avatars.js) hides the cat with its tab (`nmb.absent`), no follow timer; `nameMarkBuddyArrive`, `awayTimer`, `NMB_DWELL_*`, `nameMarkBuddyUnheld`, the `Seen` timer and the `fresh` re-choose are gone.
- Its own mind: `NMB_MIND.move` / `lonelyStep` / `floor` / `awayFor` / `walkMs` / `afield` (companion-menu.js); `nameMarkBuddyMind` (avatars.js) is called from the tick; `nameMarkBuddyAppear(buddy, walk)` and `nameMarkBuddyWalkEnter` are the visible walk-in.
- `nameMarkBuddySupported` no longer calls an untestable (scrolled-out) perch gone; `nameMarkBuddyPerchGone` falls, steps or walks.
- Switches `come` and `afield` in NMB_ACTIVITIES; help, Guide topic, Settings copy, tour and app-features text, CHANGELOG.

Left, one line each:

- Owner decisions to log as INBOX entries with a recommendation (standing order 3): going out for a while on by default in Normal only; the chat-streaming errand still pulls the cat from another room (design 9 wanted it only when already in view; not changed, `nameMarkBuddyErrand` avatars.js); the 400ms crossfade as the one fade-into-place left (reduced motion only).
- Design 8 (a ridden cat scrolled fully out is not drawn) holds for riders already (`nmb.ride`, no band edge); a document-scrolled, `glue.held` cat is still held visible at the band edge and, instead of the old 600ms re-place, walks to a perch only when its mind decides (minutes). Not probed: the document-scroll case (the probe's scroller is `#tab-main`).
- Stroll far branch "another free perch in view within 4 widths" is the existing `nameMarkBuddyWander` far branch (60 s idle rule kept); no new branch.
- `nmb.entering` / the `seenFrom` change were not needed: the walk-in is staged by `nameMarkBuddyEnter(.., visit)` from an off-window translate after an instant `MoveTo`, so the poof rule never sees an unseen start; a perch gone while out of sight is owed (`nmb.owed`) and looked at when seen.
- Probes (d) 15 min steady user, (e) perch removed, (f) reduced motion, (c) 12 min idle are not run in a browser (real-time, long); the pure rules are covered by `tests/test_companion_cat_1673.py` with a fixed clock.
- Not probed: real GPU timing, Windows, phone width, Library sub-tab flicking, the chat-streaming errand, "showy entrances" on.
- Fades-only (reduced) motion: the tick runs for a hidden cat only (`nmb.fadeComes`), floor doubled; present cats do nothing on their own there, as before.

Review fixes (second pass): Call back unhides (probe: away/hidden before, visible opacity 1 at 0.5 s after); still mode comes by mind (forced inputs, 25 s); mind fetched at hide; refused stroll uncounted; walkMs cap 12 s; companionpin.js sweep updated.
Decisions logged: Come off means the cat stays on its own page (Call back and Stay here are the ways to see it); Fewer (the default) never goes out and settles 1.5x longer, by the existing Reduce actions rule.
Rejected: finding 3 (opacity 0 on a hang perch): 4 further Dashboard boots, all opacity 1 at 14 s on the same hang, enter-down route; not reproduced, so no change.
Still unverified: wheel run with the cat present, document-scroll glue.held, real 5 to 15 minute come, afield, perch removal, reduced motion, GPU, phone, Windows.

Blind-tester pass (third, no code change; probe `p7b.js` in the session scratchpad, port 8807, 1440x900, "You" companion):
- Tab-away vanish (tester 1): kept. The one-frame cut with the tab is the owner's own decision (08-consistency.css, `.nmb-away` comment, 2026-09-27: a 200ms fade stood on the new tab for eleven frames, "stayed visible, vanished, then came back"); 1673 narrows it only by making the cat stay on its own page. A per-tab dock cat is therefore gone on other tabs until its mind brings it (5 to 15 min), Call back, or its tab. Owner call, for the INBOX with a recommendation: prefer window-level perches (hang, bar) over per-tab docks for a resting cat so most pages show it. Not changed, because it would remake the perch rule.
- Call back lands at a new spot, not where it left: intended (it comes in by the walk-in).
- Double-click (tester 3): not a bug. It opens the enlarged viewer (INBOX 443c, `openNameMarkViewer` visit); the host moved (0,774) to (688,423) within one 100 ms sample, then held. A walk into the viewer is not built; low value.
- Corner drop (tester 4): not reproduced. Drop at (1435,895): splat at x=1376, floor at y=774 within 0.8 s, opacity 1 throughout, settled at x=1296 by 1.1 s (a 79 px slide on landing). No vanish.
- Window resize clamp (tester 5): a user act, refit after 150 ms (`nameMarkBuddyRefit`); left.
- Still not run: 12 min idle, real 5 to 15 min come, go-out, "fades"/"still" in a browser, keyboard access to the cat, phone, GPU, Windows.
