# design2-1018 (graph: C37, C41, C11, C27 from bugs-1018b.md)

Seed: `<session scratchpad>/d2/seed.js` (57 notes, 6 categories, 80 links, two "Ice Breakers:"); probe `d2/probe.js` (LAYOUT, ZOOM, VW); baseline server on :8799 from the base commit.

## Done
- C37: treemap header ellipsis (`gcEllipsize`), size by links in the treemap (radii 1 to 6 distinct), no accent ring on computed layouts (rim px (68,107,213) to the category's), legend size key (`gcLegendSizeKey`), help panel line.

## Next
- C41 force graph messy: graph-canvas.js label pass (`gcPlaceLabels` ~466, label items ~2700), `gcEdgeLook` ~843.
