# perfbuddy-1108 (audit 1108 perf rows P1, P5, P8, P11)

Done:
- P11: catalogue fetched at idle, parsed in slices of 40 entries (104 ms task to 8 ms or less at 4x).

Findings that change how P1 should be attacked (measured, bare pages in the same Chromium 1243):
- 20 composited transform animations on a page cost 0 style recalcs. The same page with any `requestAnimationFrame` loop (or one main-thread animation) costs one style recalc per frame (239 in 4 s). So every frame the app asks for restyles all ~76 animated elements of the figure; the lever is how many frames the companion asks for at rest, not which animation runs.
- `compositeFailed` in the trace names only the blink lids and irises; the breath, shimmer, sway and neb/skirt animations are composited.
- Pacing the breath, shimmer and tail sway through `nameMarkBuddyTempo` at 10Hz was tried and measured worse (style recalcs 177 against 109 per 5 s at rest, style time 1,054 against 606 ms): each paced step is a frame of its own. Reverted.
- The buddy sits in `wave` for about 44 s after Settings changes it (busy, every animation at full rate), so a short wait measures that, not rest. Measure after 50 s and record `nmb.act`.
- At a truly quiet moment the base is 31 recalcs in 5 s; the 100 to 300 per 5 s windows are blinks, looks (`nmb-attend`), the live tail (`atlas-life.js:491`, `:555`) and tempo beats.
- Probes (not committed): scratchpad of the session, `steady2.js`, `win.js`, `inv.js`, `bare2.js`.

Not done:
- P1: nothing landed. Next: count frame requests at rest by owner (win.js lists them) and drop the ones with no visible effect: `atlas-life.js:555` rAF in the calm tail path, `avatars.js` tempo `afterFrames` per beat.
- P5, P8: see the log below.
