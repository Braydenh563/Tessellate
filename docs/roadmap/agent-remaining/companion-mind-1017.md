# Companion mind and Atlas frame cost (Opus, 2026-10-17)

The Opus companion brief: B87c (behaviour, actions, lifelike decisions), B88b (Atlas's throwing stars), B88c (more movement and transitions), B62 (the profile avatar's popup has no life), and the frame cost `companion-physics-1017.md` left (Atlas 25 to 28 fps at 4x during carry and flight). Owner's words in `bugs-1017.md` B62, B87, B88.

Steps, one commit each:
1. Atlas frame cost: no forced restyle per frame (`atlasRigFrame`, `atlasBreathFrame`, `atlasPropsFrame` read only after a wake), idle loops held while carried or thrown. Sweeps: `scratchpad/ui-sweeps/throwframes.js` (now with `air`), `atlasrecalc.js`, `atlasinval.js`, `atlasselectors.js`.
2. Lifelike decisions: when and what from mood, idle time, place and what you are doing; anticipation and settle; more acts (lazy, `companion-menu.js`).
3. Throwing stars on the rig (`atlas-motion.js`, the rig's own loop), juggling and when thrown; reduced motion keeps the drawn stars.
4. Perch re-verify (`perchloss.js`) and B62 (the popup's face reacts).

done: 52efa72 (step 1); next: step 3 throwing stars, atlas-motion.js atlasRigFrame, 08-consistency.css 8040.
done: b3d2971 (step 3); next: step 2 the mind, companion-menu.js `NMB_MIND`, avatars.js hooks (Decide, Schedule, Tick, Act).
done: 06797e5 (step 2); next: step 4 B62 (companion-menu.js `nameMarkViewerFace`), perchloss.js, final A/B fps.
done: 7d9c563 (step 4); final A/B (throwframes.js, before = the three atlas files at be09ce8, two interleaved rounds, load 3 to 4.5): 4x carry 47.1/31.6 to 38.6/38.1 fps, style 6.6 to 4.7-5.8 ms a frame; 4x flight 32.3/26.7 to 28.1/27.0 (after includes the new star spill); 1x carry 57.0/57.8 to 57.5/59.1, flight 56.5/55.4 to 54.4/56.7. fps at 4x is inside the noise; the trace counts in CHANGELOG are the measure.
open: the release and landing frames (about 350 ms at 4x: `nameMarkBuddyShown` layout via `nameMarkBuddyPopups`, `nameMarkBuddyBlend` getAnimations, avatars.js); the right arm joint and the popup-actions audit (BACKLOG row).
