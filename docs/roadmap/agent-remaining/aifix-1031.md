# aifix-1031 (branch agent/aifix-1031, port 8858)

## Done
- AI1 + HR1: away pauses every loop (running animations 64 to 6 on a non-home tab), `atlasFrameBudget` lite set (4x CPU idle 5 s: task 4.94 s to 2.18 s, style 2.52 s to 0.48 s), probe by events, blend skips planets (agent turn getAnimations 260 ms to 140 ms at 1x; the audit's 1,003 ms is not reproduced on this profile: 65 animations here against about 130 there).

## Next
- AI3 + AI16 (inert while faded or collapsed), then the high and medium rows in order.

## Left
- wake_sources_seed.json atlas-life.js::raf 3 to 4: the frame budget's one rAF site times 3 s of frames beside animations that already force frames; it cannot be the tail's rAF (the tail rests on a timer).
