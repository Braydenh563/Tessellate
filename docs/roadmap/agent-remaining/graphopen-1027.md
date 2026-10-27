# graphopen-1027: the graph opens settled and flows to rest (the owner, 2026-10-27)

"a bunch of nodes started individually rearranging themselves sliding instantly into position one after the other and then it juststayed like that" / "I want tit to be smooth and flowy". Sweeps in the session scratchpad: `graphopen.js` (per-frame sampler: first paint, largest per-frame move, frames over 20 px, time to rest, frame time over the first 3 s), `graphopen-boot.js` (cold boot), `matrix.sh` (before/after, interleaved), `workeropen.js` (node: crossings and notes on lines), `touch3.py` (12 seeds of test_graph_layout's map), `seed300.py`.

## Cause
- Each untangle pass waited for rest, then glided its moves in 12 steps whose first step closed a quarter of the way, then relaxed; then the next pass, then the cleanup's own glide, then a freeze with no tick after it. On screen: bursts of single notes sliding (36 notes: a 113 px frame, 35 frames over 20 px), a still map, and an abrupt stop. The playback before it ran from the spiral at full heat.

## Done
- The worker settles, untangles and cleans out of sight in 12 ms slices before its first post (`pending`, `settleUntangled`, faster hidden cooling), then plays one smoothstep flow into that map (`introInto`: a slight bloom at alpha 0.1, or from the map on screen at 0.3). A correction after paint is one 45-frame smoothstep glide of every note together (`settleGlideFrom`). Less motion waits for the settled map (cap 2.4 s) and paints it once; the canvas reveals its first fit after the balance pass, so no camera hop (36 notes: 22 px to 0). The canvas draws from the playback's first frame (`gcFrameIntro` start).
- Cleanup: no pass begins that would leave the cleanup no time before the cap; a moved note within 2 px of another is parted, else put back (`untangleUntouch`; touching 3 of 12 seeds to 0, a link through a note 0 to 1). `clearanceForce` scans per chord box; `untangleInside` has a hair of slack at the hub ring's edge.
- Browser, cold open, median of 3 (matrix2): 36 notes 113 to 8 px max per frame, 35 to 0 frames over 20 px, rest 3.2 to 1.1 s after paint; 300 notes 257 to 10 px, 24 to 0, rest 7.5 to 2.8 s.

done: 901868c, bd6e67a, c13e378, b7a852e, and the reveal/still-cap commit.

## Left
- Not verified: the feel on a real device, the return-to-tab path (from the map on screen) by eye, maps of 2000 notes.
- First paint is later: 36 notes 1.3 to 1.7 s, 300 notes 1.5 to 2.2 s, 300 notes with less motion 0.9 to about 3 s (but at rest 7.2 to 3.2 s after opening).
- 300 notes with motion: after paint the camera's end fit still eases about 24 px (k 0.77 to 0.79), pre-existing.

next: none open from this brief.
