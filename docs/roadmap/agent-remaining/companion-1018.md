# Companion frame cost, arm joint, popup actions (Sonnet, 2026-10-18)

From `companion-mind-1017.md` and `companion-physics-1017.md` found-not-fixed: (1) release and landing frames at 4x, (2) the Atlas right arm joint, (3) the BACKLOG popup-actions audit.

- done: step 1 (reads before writes in `release` and the flight's last frame). Measured with `scratchpad/ui-sweeps/releasetrace.js` (restyle counts, interleaved A/B with BEFORE_DIR): Atlas drop at 4x 3 restyles / 253 ms to 2 / 180 ms; at 1x release 87 to 56 ms; throw release 199 to 68 ms; landing frame 2 big restyles to 1. A same-value write costs nothing (`samevalue.js`); what remains is real state change (class `nm-buddy-dragging` off 43 to 106 ms, pose change in `nameMarkBuddyMoveTo` 90 ms at 4x), which `nameMarkBuddyBlend`'s getAnimations only exposes (it flushes the restyle the writes already owe).
- next: step 2, the right arm joint (atlas-motion.js, atlas.js armRig), then step 3 (BACKLOG row popup-actions audit).
