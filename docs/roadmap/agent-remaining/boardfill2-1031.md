# boardfill2-1031 (INBOX 1486 follow-up)

Brief: the owner, on a whiteboard with a sequence diagram: "I should be able to make the fill actually opaque and not partially transparent, transparency should be easily changable as with colour".

Step 1 (diagram objects): done, see git log (commit "Board: diagram fill colour and opacity").
Next: step 2, text boxes, stickies and cards take the Fill opacity (`bg_alpha`), `frontend/js/whiteboard.js` text build and paint (`el.style("background", d.data.bg ...)`), `wbSvgBoxBackdrop` in `frontend/js/whiteboard-format.js`.

Left, one line each:
- A diagram's picture carries its own opaque ground (`mermaidFrameSized`), so a fill at 0% shows the ground colour, not the board behind it. Real see-through boxes would need a ground-less picture.
- Diagram line colour is not offered, only its opacity (the owner asked for fill colour, fill opacity and line opacity).
- Note cards (`.node-card`, kind `node`) have no fill at all, so no opacity row; only text objects (text box, sticky, card templates) do.
