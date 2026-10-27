# atlas1402: INBOX 1402 (Atlas grumpy at rest; a thrown companion flies back)

Port 8790, data in the session scratch area. Sweeps: `scratchpad/ui-sweeps/atlasrest1402.js` (face and arms over a session, or `CASE=moods`), `scratchpad/ui-sweeps/throwsettle1402.js` (throws, then 5s and 15s, then a reload).

- Part A: friendly at rest (brows, determined, thinking's mouth and folded arms, the fold stance, the doze's brows, the rig's winding elbow, brief sulks, generated faces' drift). Tests: `tests/test_atlas_rest_1402.py`.
- Part B: a thrown companion settles where it lands.
- done: 55bea4b part A (92.3% to 1.4% masculine, 100% to 1.3% feminine, atlasrest1402.js).
- next: part B, a floor landing stepped 200 to 320px aside (nameMarkBuddyThrowSpot and nameMarkBuddyDrop, frontend/js/avatars.js:4532 and 6013).
- done: bb2d432 part B (seeded 1280x720 Atlas dashboard: 256 to 8px for a landing over the bar, sum 892 to 396).
- next: full before and after sweep, idle frames, plan 1402 resolve (docs/roadmap/UI_MODERNISATION_PLAN.md:1596).
- done: docs commit (84 seeded throws, furthest landing move 256 to 65px, total 3,875 to 1,487px; frames.js companion rest 0 long tasks before and after, worst 33 to 17ms).
- next: nothing open. Not verified: real mouse flicks (DIRECT=0) at every size; the climb fate still rises 84 to 145px by design.
