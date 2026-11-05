# blink-e2e-1104 remaining

- done 5bb45b1: INBOX 1644, idle blink act animated only the first `.nm-blinks` (avatars.js `nameMarkIdleAct`); now every group. Test: tests/test_atlas_blink_both_eyes_1644.py.
- done: editor-keys.spec.js:190 race fixed (read re-finds the card and scrolls to it per try).
- next (orchestrator): INBOX 1644 and the E2E item to HISTORY, CHANGELOG line (not edited here).
- next: the layered lids blink (atlas-motion.js `atlasBlink`) was measured symmetric in both looks (18% to 18% of each eye's box changed, six poses); not touched.
- not verified: the owner's exact surface (large viewer vs list face); the fix covers every caller of the idle act.
- found, not fixed: tests/test_plan_hygiene.py INBOX tray count is 20 (limit under 20) on the base; CI's BACKLOG 4506 vs cap 4500 and codemap staleness were on an earlier head.
