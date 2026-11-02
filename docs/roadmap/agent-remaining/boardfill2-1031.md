# boardfill2-1031 (INBOX 1486 follow-up)

Brief: the owner, on a whiteboard with a sequence diagram: "I should be able to make the fill actually opaque and not partially transparent, transparency should be easily changable as with colour".

Done: d559296 (diagram objects: fill colour, fill opacity, line opacity); step 2 (text boxes, stickies, cards: fill opacity) in the commit after it. Nothing left in the brief.

Left, one line each:
- A diagram's picture carries its own opaque ground (`mermaidFrameSized`), so a fill at 0% shows the ground colour, not the board behind it. Real see-through boxes would need a ground-less picture.
- Diagram line colour is not offered, only its opacity (the owner asked for fill colour, fill opacity and line opacity).
- Note cards (`.node-card`, kind `node`) have no fill at all, so no opacity row; only text objects (text box, sticky, card templates) do.
- A sticky's folded corner (`.wb-sticky::after`, `--wb-paper`) stays at the full paper colour when the fill is made see-through (`frontend/js/whiteboard.js` `wbPaintObject`, the `--wb-paper` line).
- Draw.io import does not read `fillOpacity` back onto text boxes (export writes it).
