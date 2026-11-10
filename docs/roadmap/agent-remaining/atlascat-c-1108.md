# atlascat Batch C (C2, C3, C5), agent/atlascat-c-1108

Done: the nine tail poses and eight lower-body states, both sides, each with a trigger; catalogue rows marked built; NEITHER_CAP 109 to 92.

Remaining:
- `tail.coil_hold` on the desk and in the app has no prop to coil round yet (the plant pot, INBOX 1696 aa): `behaviour.py` TAIL_BY_STATE "lounge"; `atlas-life.js` ATLAS_TAIL_BY_STATE lounge.
- `tail.balance` in the app fires on a glide (no perch state exists in the app); on the desk it fires on a window's top (`Engine._tail_cue`). A real "walking an edge" signal in the app would be `avatars.js` perch class.
- `tail.pillow` on the desk shows while drowsy and sitting (the layer does not draw over the nap frames); a baked nap tail would be `sprites.py` TAIL_FRAMES.
- `tail.tip_twitch` has no "thinking" trigger on the desk: think acts do not carry the layered tail (`Engine._tail_view` stand and sit only); it is a stand idle pick.
- `lower.billow` on the desk reads the walking speed or the dash pace, not a window-opened event (no `react.window_opened` yet).
- Not verified in a real browser or on a real desktop (no sweep run): only vm and fake-engine tests.
