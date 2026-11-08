# animrecalc-1108 remaining list

Branch agent/animrecalc-1108. Probe (untracked, session scratch): idle dashboard, Atlas companion on, 36 notes, 4x CPU, 8 s trace, 6 runs.

## Done
- Lag log (lag-watch.js `lagRafInstall`): a slow frame callback (4 ms or more) is kept in a 16-entry ring (`LAG_RAF.note`); a long-frame row whose script is the wrapper names the callback that started inside the script's window (`LAG_RAF.at`), not `FrameRequestCallback @lag-watch.js`. No new global names; no extra clock read in the wrapper. Test: tests/test_anim_recalc_1108.py.

## Findings (target 4)
- Every loop on the list is composited: `getAnimations()` shows transform, rotate, scale and opacity on HTML spans (the orbit arms, glows, swirls, ring spins and ring frames are Web Animations from `atlasRingLoops`, atlas-life.js:20, so a CSS kill-switch does not touch them). Compositor refusals in 8 s: 2 to 5, all on the blink's svg groups (`g.atl-head`, `g.atl-lids`, `g.atl-iris`), short.
- What costs is the frame count. Each main frame restyles every running animation's element: 69 to 79 elements, 13 to 20 ms a recalc at 4x (4 to 5 ms with every animation paused). Baseline 6 runs: 8.8 to 17.1 recalcs a second (mean 11.7), 120 to 263 ms of recalc a second (mean 182), main thread 420 to 750 ms a second.
- Wake sources at rest over 10 s at 1x: the pacer's coil beat 85 (the sitting coil, `atl-prop`, 200 ms stride, each beat followed by an `afterFrames` rAF), the tail's calm draw 40 (66 ms for the 1.6 s settle after each act), the rig 30, the budget probe 58 only in the first 3 s.
- `g.nmb-torso` layout: the breath (`atl-breath`, atlas-life.js:793) shows `Style changed` layout invalidations on the svg group; pausing it takes layouts from 14 to 6.6 a second. A restart under trace gave no compositor refusal for it, so it is a main-thread effect of the svg group, not a refusal.

## Not done (needs the owner's call: each changes the look at rest)
- Pause the planets' loops (orbit, glow, swirl, ring sway and spin; about 40 of the 75 animations) when `:root.is-idle` (two minutes without input), as the emblem does. Measured ceiling: recalc cost 13 to 20 ms falls to about 5 ms a frame. Planets would freeze after two idle minutes.
- Raise `NMB_PROP_GAP_MAX` (avatars.js:5555) so the coil steps every 400 ms, in step with the tail's rest beat: halves the pacer's wakes; the coil's 3% scale then steps about 0.3 px.
- Re-run `atlasFrameBudget` (atlas-life.js:440) once more after the first idle minute so a machine that slows later goes to `data-atlas-lite`; today it samples only at boot.
- Fake model (`scratchpad/fake_answer_server.py`) was not started: the idle dashboard does not call it. Port 8799 was already answered by another process, so the probe used 8779.
