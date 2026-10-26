# throw-1011 (INBOX 882, then Brief 88 folded in)

INBOX 882, the owner: "I try throwing the companion across the screen and it just goes back to the same side, the companion physics just isnt there and needs to be upgraded and fixed."

Reproduced (scratchpad/ui-sweeps/throw.js, 1440x900, Notes with 24 seeded notes, base avatars.js via OVERRIDE_JS): thrown right from x 44 at 1.47 px/ms and left from x 1168 at 0.97 px/ms, both came down on the same dock perch at x 763 (`nameMarkBuddyToss` slid 260 ms, then `nameMarkBuddyChoose` near the aim picked the tab's preferred perch). Empty notebook: 270 to 937 and 1183 to 524 (worked there). Phone: the toss did not fire at 0.92 px/ms (drops).

Built: `nameMarkBuddyReleaseVelocity` (last 80 ms, clamp 4.5), `nameMarkBuddyFlightStep` (gravity 0.0032, air 0.0011, ground 0.006, bounce 0.4, side rebound capped 0.12 px/ms, tilt by vx, 1.2 s cap), `nameMarkBuddyWorld` (ledges = panel tops), `nameMarkBuddyThrow` (one rAF, transform + rotate, squash on impact, pauses hidden, Reduce motion crossfade), `nameMarkBuddyThrowLand` (`nameMarkBuddyDrop` at the landing point, kept as the tab's spot). Tests: tests/test_companion_throw.py.

After (same sweep, 24 notes): desk right 89 to 933, left 1182 to 570; hard (150px moves) right 96 to 1299, left 1213 to 84; phone left 283 to 28, right 26 to 314; Reduce motion 94 to 726, 1296 to 682. Unchanged after 10 s and after a tab switch away and back in every run.

Not verified: a real phone; the sweep's phone right flick is sometimes a drop here because the let-go reaches the page over 100 ms after the last move on this loaded machine (load 21).

Found, not fixed (pre-existing on the base): test_companion_motion.py::test_every_way_to_a_note_counts_as_opening_it (flashEntry lost its typeof guard); test_frontend_wake_sources.py dashboard.js raf 3 to 4, search-suggest.js 0 to 2; test_global_scope_ratchet.py 705 > 699.

Next: Brief 88 and the coordinator's three items (eased starts/stops, expanded panel resting pose, click raises one arm).
- done d3c759ed5 throw flight; next: per-throw feel (Brief 88 b), avatars.js nameMarkBuddyThrowFeel
- done 2b3840584 throw feel; next: click-arm (atlas-motion.js atlasRigGesture), panel resting pose, eased starts/stops
- done 9d1c69832 click-arm (clickarm.js: hand y 47..56 to 16, 0 bad); large view resting limbs (viewerpose.js: arms 150/-151 deg at 300 ms to their float targets 28/-50); next: eased walk/act starts and stops (jolts.js)
- done (next commit) eased starts and stops (jolts.js: walk start leg 5.5px and head 4.8px, cut-short body 5.1px, act over a walk 3.2 deg; after: Atlas and me PASS, max 0.4px) and three manners per act, three strides per walk or float (variety.js PASS, both kinds); next: Brief 88 (a) prop contrast, more Atlas actions, the large view actions
- done (next commit) Brief 88 (a) props: atlasprops.js before 8 of 9 props under 3:1 (1.78 to 2.27), the moon 9px; after all 4.02:1 or more, moon 15x14, both themes; tooltip names the prop; next: more Atlas actions, large view actions, screen entries
- done (next commit) Atlas juggle/map/meditate wired (atlasacts.js PASS, prop shown 1.0) and the large view act chips (viewacts.js: 9 for Atlas floating, 6 for me, all play; fits at 1440 and 390); next: screen entries, idle variety
- done a998b1e4b screen entries: fall (Atlas drifts down) and tumble; entries.js PASS both kinds, every way within 1px of its perch, mid 3 ways, left 4, bar 3, 0 repeats; next: idle variety check (Brief 88 c), emotion variants (d)
- done 77bddee7b Brief 88 (d) lower-body poses: lie, think, sad, startle 2 to 3 variants, hair and nebula 2 to 3 in six states; a state entered again never repeats its last (in-browser: sit 1 2 0 2 1 0, gesture 0 1 0 2 1 0, 0 errors). (c) checked present: breathing (atlasBreathFrame), tail and hair follow-through (lag), idle act never the last (nmb.lastAct)
- final sweeps: jolts.js PASS both kinds, entries.js PASS both kinds, errors.js 0 errors and 0 layout findings at 1440, 1024, 820, 390.

Remaining: none in scope. Not verified: a real phone, timing on an unloaded machine, real visual feel. Atlas lying still mirrors two ways only (head left or right); its lower body, hair and nebula give a third look.
