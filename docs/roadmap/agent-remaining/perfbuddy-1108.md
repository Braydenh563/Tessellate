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
- P5: not fixed. Tried: a typed letter in a field no longer wakes the follow loop on keydown, and its dodge look waits 300 ms with no late 700 ms look. Measured 49 keys at 4x, Atlas, after 50 s: 412 to 430 layouts against 403 to 424 before, none forced. No gain, so reverted. The layouts are the frames the rig asks for during the ~10 s of typing (same cause as P1), not the key handlers.
- P8: not fixed. Profile of the first chat answer at 4x: avatars.js self time is 135 ms of 12 s; the one real cost is `nameMarkBuddyBlend`'s `getAnimations({subtree})`, which settles the answer's 500 to 860 new nodes (266 ms from the 1.5 s cue timer's `nameMarkBuddyAct`, avatars.js:8226 via 9217; 138 to 380 ms from `setAtlasMood`'s blend, atlas.js:3738). Tried deferring the cue's act to `requestIdleCallback` plus `nmb.afterClean`: the same read took 450 ms, so reverted. Next: skip or snap the blend while a chat turn is still rendering (`#chat-send` busy), or read the parts without a subtree style flush.
