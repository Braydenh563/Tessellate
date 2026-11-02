# basered2-1031 (agent/basered2-1031)

## Done
- 1 CONTRIBUTING mirror: already green on the merged head (0777c7b re-copied it); nothing to change.
- 2 emblemHead turns again (broken by 9a78292).
- 3 test_get_started_1301 reads `firstStepsRead` (79c7e07 moved the marked-done check there; the behaviour held).
- 4 map edge grips have focus twins (broken by dec5b0b); the waypoint grip rules moved to library-lazy.css to stay under the boot gzip cap.
- 5 #status-tray is `icon-only`, with `has-count` widening it: 28x28 empty, 33.4x28 with a count (measured at 1440x900, port 8844).
- 6 capture-card-lazy.css and math-field-lazy.css listed in tests/_css_paths.py; test_lazy_css recognises `.map(lazyScript)`. Linting them found a dead `--input-bg` fallback and a duplicate `z-index: 2500`, both removed.
- 7 alpha preset buttons carry aria-label (22cc1f2).
- 8 test_wb_line_ends: 22cc1f2 inserted "strokealpha" in the arrow's row; "caps" (the ends) are still offered, the test literal follows.

## Left
- Nothing from the brief.

## Found
- Both lazy sheets were outside the CSS lints since they landed; the two fixes above show the list is worth checking when a lazy sheet is added (a lint that fails if a lazy-loaded sheet is not in `_css_paths` already exists: test_lazy_css, it just could not see the `.map` form).
