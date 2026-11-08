# restlayout-1108 (audit 1108 perf row P1: layout per frame at rest)

Done: nothing landed. The premise (a layout read after a style write each frame) did not hold; no change measured better.

Measured (Atlas on the dashboard, 4x CPU from boot, 50 s idle, 5 s window; probe in the agent scratch, not committed):
- Forced layouts: 0 of 63 to 131 Layout events in 6 traces (Layout events carrying a JS stack). Layouts equal recalcs because each frame that restyles the figure's SVG also lays it out; nothing reads layout after a write.
- Recalcs per 5 s: 80 to 182 (base runs 126, 107, 80; later runs 90, 126, 129). Style 366 to 967 ms per 5 s. The spread is the cause of "cannot show better": a block of 24 writes measured 81 to 349 recalcs with no write at all (looks, blinks, micro acts are real activity, not a loop).
- `dashboard.js:1967` `afterFrames` at rest: 0 to 24 per 5 s, all from `avatars.js:5965` (tempo's "drawn" flag after a beat that stepped a paced animation) plus 1 to 3 from `afterClean` (`avatars.js:3473`, `atlas-micro.js:285`) and `atlas.js:3769` on a mood. It reads nothing; it only waits a frame. 24 happens only when a prop is held (the coil, `nmp-coil` 3 s breath, `atl-prop` gap 4 = a beat every 200 ms); the other regime is 5 beats (stride 1000 ms).
- With the tempo stopped (NOTEMPO): 63 recalcs per 5 s, 16 of them the tail's calm draw (`atlas-life.js:555` timer 66 ms then the rAF at `:556`), which runs for the 1.6 s settle after each calm act pick (every 5 to 9 s).
- Coil step cost: 24 `currentTime` writes at 250 ms added about 1.3 recalcs a write, buried in a baseline of 81 to 349 per block (4 rounds each: none 140, 133, 81, 349; write 172, 162, 134, 206; write plus rAF plus timer 179, 165, 194, 148).
- Experiment: tempo `drawn = true` set at once instead of `afterFrames` plus timer: runs landed in different regimes (95, 215, 117 recalcs); not comparable, reverted.

Not done (each below the run-to-run spread, so not kept):
- Tail settle at 10 Hz not 15 Hz (`atlas-life.js` `ATLAS_TAIL_CALM_MS`): saves about 5 of 63 recalcs; also a look change.
- Coil breath on the compositor: `ATLAS_PROP_LOOPS` (`atlas-life.js`) animates the `scale` property, which Chromium refuses to composite on an svg box; `transform` would, but an element's own `transform` attribute or CSS would be overridden, so every prop's placement needs checking first (needs the atlas.js props owner). Would drop the 5 Hz coil beats entirely; `tests/test_atlas_shape.py:1337` allows only rotate, scale, opacity and `tests/test_idle_restyle_1101.py` pins the gaps.
- Fewer steps for a slow prop (`NMB_PROP_STEPS` 16 to 8): 5 Hz to 2.7 Hz, a look change.

No stable count exists for a ratchet (recalcs per 5 s vary 80 to 182 with the same code).
