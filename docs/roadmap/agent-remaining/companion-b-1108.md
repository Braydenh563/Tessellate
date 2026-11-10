Remaining after catalogue Batch B (`atlascat-1108.md` rows B1 to B5), branch `agent/companion-b-1108`.

Done: B1 adadb958, B2 0099f464, B3 13cfcba2, B4 8ab94886, B5 (the last commit on the branch).

- `lower.drift` on the desk (row B3 names it): the carried figure's legs have no flow offsets of their own; the kick, cross and sigh are body poses over the held picture. Needs `behaviour.Flow` offsets while held (`engine.py` `_carry_pose`, `FLOW_FROZEN` holds `held` still today).
- Faces while carried: `faces.FACE_FRAMES` has no `held` or `spin24`, so the carry stages and the upside-down figure wear no expression; a face on those frames needs `_match` anchors for them.
- Not verified: real Windows (every desk test is a fake clock and a fake drag), the look of the turned carry (spin24 at angle pi, mirrored grab point) and of the carry poses on the real sprite, a real browser tap on the in-app nose box (the fractions 0.18 to 0.42 of the figure's box are a guess for the generic figure; Atlas's head may sit differently).
- B4 note: faces are drawn by Pillow over the frame, so `scripts/render_desk_frames.js` has no face frames to add; the row's mention of it does not apply.
- Found, not mine: `tests/test_poses_1681.py::test_each_pose_is_reachable_from_the_decide_path_in_its_poses_only` fails on the merged base too (node: `Cannot read properties of undefined (reading 'weigh')`), probably since Batch A's `avatars.js` change.
- Caps: `APP_ONLY_CAP` 69 to 60 (B1 to B4 nine entries built on both sides), `NEITHER_CAP` 111 to 109 (`int.tickle`, `int.boop_nose`); no cap rose. `GLOBAL_NAMES_CAP` untouched: the in-app half is one scope, `nmb.touch`.
