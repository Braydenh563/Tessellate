# motion-1101 remaining (INBOX 1506)

Part A done (8e1fdf0): the Motion setting (Follow the system, Always on, Off) and one resolved `data-motion` (theme-boot.js `MOTION.apply`, `reducedMotionWanted()`); every `@media (prefers-reduced-motion)` block and `matchMedia` read moved onto it; lint `tests/test_motion_resolved.py`.

Part B done (next commit): durations 120/180/240 ms, `--ease-spring` retuned to the one gentle overshoot (1.3), a menu's spring and eight-row stagger (10-responsive.css `ui-row`), chevron retimes plus a zero-weight caret rule (08-consistency.css "one vocabulary"), `.ui-pm` plus-to-minus (library-lazy.css, used by the documents Insert menu), extras stilled in motion-still.css; DESIGN.md row plus `test_the_motion_vocabulary_is_one_set`; `scratchpad/ui-sweeps/motionvocab.js` and `motionvocab-idle.js`.

Left:
- Resolve INBOX 1506 (`python scratchpad/inbox_resolve.py <n>`) and move its Built block to HISTORY at the merge; it covers both parts.
- `.ui-pm` has one consumer (documents Insert summary); the whiteboard Insert toggle (`.wb-menu-toggle`, plus-square icon, shown below 56rem only) could adopt it.
- The graph's toolbar chevron (`doc-toolbar-menu-caret` in graph.js) does not turn open: the rule is in library-lazy.css; graph-lazy.css would need the same line.
- Boot CSS has 5 gzipped bytes of room under `BOOT_CSS_CAP`: the next boot rule goes in a lazy file.
- Stale "Reduce motion" wording in code comments (settings.js, status.js, 02-chat-graph.css near the spinner comment).
- `__main__.py`'s launcher page keeps its own raw reduced-motion query (outside frontend/, so the lint does not see it).
- Known changes to report: under Follow the system a browser that asks for calm now holds the faces and the app mark still (they used to run calmer); Always on keeps them moving. `--ease-spring` went from 1.56 to 1.3 for the knob and Atlas's lean as well.
