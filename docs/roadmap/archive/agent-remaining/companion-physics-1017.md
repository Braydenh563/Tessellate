# Companion physics and perch (stopped mid-run, 2026-10-17)

Done (committed): e4515bf carry and flight no longer restyle the page tree each frame; d675e3c Atlas rig reads style once before writing any (thrown Atlas 29 to 58 fps); the perf agent's branch is merged in (27ec556 --nmb-sway fix).
In the working tree (WIP commit): avatars.js edit and tests/test_companion_throw.py, a failing test written first for the next fix ("failing for the right reason", fix not yet written).

Still to do: finish that fix; the perch-loss repro (resize, scroll, hide the perch element, switch surface, re-render) and re-anchor or fall; re-measure drag and throw frame times with 4x CPU throttle; list the top three app-wide frame costs. Not started: the throwing-stars animation and new actions (an Opus brief, B87c/B88b/c).

- done: step 1 (boot budget, Saved companions pane to companion-menu.js).
- next: perch-loss repro in Chromium (resize, scroll, hide perch, switch surface, re-render), test first, avatars.js nameMarkBuddyRestore/Follow.

- done: step 2 (perch loss: peek/lean supported only while the edge shows, bar watched, rate-limited loss retried; tests/test_companion_perch.py, scratchpad/ui-sweeps/perchloss.js).
- next: frame times at 4x CPU (scratchpad/ui-sweeps/throwframes.js), top three app-wide frame costs.

- done: step 3 (frame times at 4x: scratchpad/ui-sweeps/throwframes.js, appframes.js); CI fix 47d3f10.
- next (not done): Atlas still 25-28 fps at 4x during carry/flight; atlasBreathFrame atlas-life.js:549, atlasRigFrame atlas-motion.js:310, atlasTailDraw atlas-life.js:392 each schedule a style recalc per frame (UpdateLayoutTree 220 passes, 44 elements each, over a 0.7 s carry): merge them into one write per frame. Throwing-stars and new actions stay with the Opus brief (B87c/B88b/c).
- picked up: the Atlas 4x frame cost by `companion-mind-1017.md` step 1 (52efa72).
