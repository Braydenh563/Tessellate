# graphopen-1027: the graph opens settled and flows to rest (the owner, 2026-10-27)

"a bunch of nodes started individually rearranging themselves sliding instantly into position one after the other and then it juststayed like that" / "I want tit to be smooth and flowy". Sweeps in the session scratchpad: `graphopen.js` (per-frame sampler: first paint, largest per-frame move, frames over 20 px, time to rest, frame time), `graphopen-boot.js` (cold boot), `matrix.sh` (before/after, interleaved), `workeropen.js` (node: crossings and notes on lines), `seed300.py`.

## Cause
- Each untangle pass waited for rest, then glided its moves in 12 steps whose first step closed a quarter of the way, then relaxed; then the next pass, then the cleanup's own glide, then a freeze with no tick after it. On screen: bursts of single notes sliding (36 notes: a 134 px frame, 37 frames over 20 px), a still map, and an abrupt stop. The playback before it ran from the spiral at full heat.

## Done
- The worker settles, untangles and cleans out of sight in 12 ms slices before its first post (`pending`, `settleUntangled`, faster hidden cooling), then plays one smoothstep flow into that map (`introInto`: a slight bloom at alpha 0.1, or from the map on screen at 0.3). A correction after paint is one 45-frame smoothstep glide of every note together (`settleGlideFrom`). Reduced motion gets the settled map as its first and only frame. The canvas draws from the playback's first frame (`gcFrameIntro` start), so no glide from the spiral.
- `clearanceForce` scans the grid per chord box (a quarter less time a tick); `untangleInside` has a hair of slack at the hub ring's edge.

## Left
- Not verified: the feel on a real device, the return-to-tab path (from the map on screen) by eye, maps of 2000 notes.
- 300 notes: first paint about 0.6 s later (the settle out of sight), crossings 812 to 845 and notes on a line 32 to 43 in node (the passes now share the 4 s cap).
