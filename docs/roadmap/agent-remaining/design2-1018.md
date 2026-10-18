# design2-1018 (graph: C37, C41, C11, C27 from bugs-1018b.md)

Seed: `<session scratchpad>/d2/seed.js` (57 notes, 6 categories, 80 links, two "Ice Breakers:"); probe `d2/probe.js` (LAYOUT, ZOOM, VW); baseline server on :8799 from the base commit.

## Done
- C37 (7b1aa9a): treemap header ellipsis (`gcEllipsize`), size by links in the treemap (radii 1 to 6 distinct), no accent ring on computed layouts (rim px (68,107,213) to the category's), legend size key (`gcLegendSizeKey`), help panel line.

- C41 (2dd47bc): `gcPlaceLabels` refuses a place nearer another dot (ambiguous 6 to 0 at the fit), `gcOverlayBoxes` (under overlays 6 to 0 at 1.8x), quiet bridges in every Force shape (`_bridgeCat`, alpha 0.40 to 0.20), duplicate titles get "(category)" or the date (dupTexts 1 to 0). Edge crossings 39 and separation (median other/same nearest 3.05 to 3.28) unchanged: forces not touched.

- C11 (f16e19e): `gcHoverCardFacts`, `gcHoverCardFrame` (graph-canvas.js), `.graph-hovercard` (graph-lazy.css), DESIGN.md row, `test_a_dot_on_the_graph_answers_with_its_hover_card`. Probe `d2/probe-hover.js`: card shown on hover and on keyboard focus (192x191 px, inside the map), hidden on leave and while the popup is open, canvas title empty, aria-describedby set.

## Decisions taken (recommendations, reversible)
- C11 "click pins it": the click keeps opening the note's popup (GRAPH_PLAN Phase 6, decided), which is the pinned form; its info line gains the edit date. The hover card is for reading without opening.

- C27: `renderGraphPopupProps` (graph.js) head row `.graph-popup-props-head` (graph-lazy.css). Probe `d2/probe-popup.js`: button 117x32 at the left, icon at x28, 1px off the text field, to a 420px head with Add/Edit right-aligned (right edge 434 of 448), label "Properties · 3", 9px off the field.

## Next
- C11 follow-up: "Edited" reads `edited_at` (a person's edit), not `updated_at`: routes_graph.py node payload ~929, `gcHoverCardFacts`, `renderGraphPopupInfo`.
