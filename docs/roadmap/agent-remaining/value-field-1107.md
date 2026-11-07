# value-field-1107 (INBOX 1694 b) remaining

Done: value-field.js and .css (the recipe), DESIGN.md row, lint `test_a_zoom_readout_is_a_value_field`, lightbox, diagram view, board and map zoom, present page number, Guide lines.

Left:
- OCR workspace zoom level: library.js:6521 `ocr-zoom-level` (a button that toggles Fit and 100%; needs Fit as a preset and a null state in the field).
- Settings percentage sliders' readouts (settings.js:2742-2758, settings-controls.js:906-3969, settings-panes.js:1021 the app zoom, whiteboard-format.js:989-1002): frozen in the lint, may only fall; each is a range input with a number beside it.
- Documents word-goal, graph confidence, suggestions-inbox percent: read-only figures, not adjustments; judge before converting.
- Present page field has no chevron: the page picker beside it already lists every page with its title.
- Diagram view zoom not driven in a browser (no diagram document opened); lightbox and board were.

Left: a keyboard-only reach (Tab to a slider before any hover) does not fetch the value field, because the boot byte ratchet (260,860 gzipped) had no room for a second `warmOnFirst("focusin", ...)`; a lazy bundle that already carries the field (lightbox, Library) upgrades them. The hover warm uses `input[max]`, so a number box also fetches the 3 KB module. The module key is `vf`.
