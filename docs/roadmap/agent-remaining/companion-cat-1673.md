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
