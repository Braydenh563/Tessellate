# value-field-1107 (INBOX 1694 b) remaining

Done: value-field.js and .css (the recipe), DESIGN.md row, lint `test_a_zoom_readout_is_a_value_field`, lightbox, diagram view, board and map zoom, present page number, Guide lines.

Left:
- OCR workspace zoom level: library.js:6521 `ocr-zoom-level` (a button that toggles Fit and 100%; needs Fit as a preset and a null state in the field).
- Settings percentage sliders' readouts (settings.js:2742-2758, settings-controls.js:906-3969, settings-panes.js:1021 the app zoom, whiteboard-format.js:989-1002): frozen in the lint, may only fall; each is a range input with a number beside it.
- Documents word-goal, graph confidence, suggestions-inbox percent: read-only figures, not adjustments; judge before converting.
- Present page field has no chevron: the page picker beside it already lists every page with its title.
- Diagram view zoom not driven in a browser (no diagram document opened); lightbox and board were.

Fixed (vf2-1107): keyboard focus fetches the module (`[type=range]`, pointerover and focusin; boot gzip 260,858 to 260,848 under the 260,860 cap, bytes won back by inlining chatMessagesEl and layoutIsTablet); readouts written in code are re-read on reach and by `valueField.refresh()` (settings.js, setZoom, sketch setSize, wbHistSync); Escape reverts first; the board history scrubber is a field ("3 of 12").
Left (vf2-1107):
- graph-time-slider (graph-canvas.js:6763): not converted. Its value is an epoch in milliseconds on a 100-step grid and its label reads "Up to <date>", so a typed date snaps to the nearest of 100 cut-offs (a grid that moves with the notebook) and shows a different date than was typed; a date field needs a date parser and a free-step slider (`step="any"` breaks the arrow keys). Needs a design call: a date input beside the slider.
- Sketch size slider is hidden at 390 wide (offsetParent null; not driven further); mind map Format sliders share whiteboard-format.js, not driven separately (a mindmap board type was refused by the board API in the sweep).
- After Escape leaves a field in a panel the focus is on the page, not the slider.
