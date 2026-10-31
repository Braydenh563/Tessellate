# boardfill-1031 (INBOX 1486)

Done (hash filled at the end): cursor under drawing tools; press inside a selection's box drags it; fill and line opacity (Format panel, exports, draw.io).

Left, one line each:
- The owner's screenshot was a Mermaid sequence diagram (a `diagram` object): its boxes and activation bars take a 16% and 8% accent mix over the ground (`mermaidTheme`, `frontend/js/mermaid-draw.js:196-240`), which a fill opacity on a shape does not reach. A per-diagram "fill strength" would pass an amount into `mermaidTheme` and the cache key. Not built.
- Text boxes, stickies and cards keep `bg` as a bare colour: no opacity slider for them (`data.bg`, `whiteboard.js` 23441 and 23670). Server model `WhiteboardObjectData` would need `bg_alpha`.
- Touch: a finger on empty canvas inside a selection's box still pans (`wbZoomFilter`), only the mouse drags the selection.
- A map board (`wbIsMap()`) is excluded from the inside-the-box drag; topics drag by their own branch rule.
- A link (connector) selected alone has no box, so it has no inside.
