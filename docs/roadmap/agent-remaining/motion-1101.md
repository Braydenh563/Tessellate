# motion-1101 remaining (INBOX 1506)

Part A done: the Motion setting (Follow the system, Always on, Off) and one resolved `data-motion` (theme-boot.js `MOTION.apply`, `reducedMotionWanted()`); every `@media (prefers-reduced-motion)` block and `matchMedia` read moved onto it; lint `tests/test_motion_resolved.py`.

Left:
- Part B, one motion vocabulary: tokens (`--ui-fast/base/slow` to 120/180/240 ms, one ease-out, one overshoot), chevrons, plus and minus, kebabMenu origin and stagger, popovers, dialogs, tab switches; DESIGN.md recipe and lint; idle long-task and rAF numbers before and after.
- INBOX 1506 stays open until B lands (`python scratchpad/inbox_resolve.py` then).
- Known change to report: under Follow the system a browser that asks for calm now holds the faces and the app mark still (they used to run calmer); Always on is the way to keep them moving.
