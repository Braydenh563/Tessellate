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
done: step 4 (the commit after 06797e5); next: final A/B fps (measure.sh), status rows in bugs-1017.md and BACKLOG.
