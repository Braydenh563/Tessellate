# design2-1018 (graph: C37, C41, C11, C27 from bugs-1018b.md)

Seed: `<session scratchpad>/d2/seed.js` (57 notes, 6 categories, 80 links, two "Ice Breakers:"); probe `d2/probe.js` (LAYOUT, ZOOM, VW); baseline server on :8799 from the base commit.

## Done
- C37 (7b1aa9a): treemap header ellipsis (`gcEllipsize`), size by links in the treemap (radii 1 to 6 distinct), no accent ring on computed layouts (rim px (68,107,213) to the category's), legend size key (`gcLegendSizeKey`), help panel line.

- C41: `gcPlaceLabels` refuses a place nearer another dot (ambiguous 6 to 0 at the fit), `gcOverlayBoxes` (under overlays 6 to 0 at 1.8x), quiet bridges in every Force shape (`_bridgeCat`, alpha 0.40 to 0.20), duplicate titles get "(category)" or the date (dupTexts 1 to 0). Edge crossings 39 and separation (median other/same nearest 3.05 to 3.28) unchanged: forces not touched.

## Next
- C11 hover card: graph-canvas.js native title ~3753 (now moved), `gcTooltip`.
