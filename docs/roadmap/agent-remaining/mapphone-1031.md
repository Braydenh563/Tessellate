# mapphone-1031 (agent/mapphone-1031): remaining

Source: blind-1031 item 11, blindfix-1031 "left (item 11)". Measured at 390x844 touch, port 8811.

Done (one commit): phone frame floor (whiteboard.js `wbMapFrameScales`, `wbFrameMapOnOpen`; whiteboard-map.js `wbMapTidy` spill frames the same way), boards picker face (sheets-selects.js `selectFaceText`, whiteboard.js `faceNarrow`, 07-whiteboard-misc.css chip), Notes list end padding (10-responsive.css).

Left:
- The back-to-top button (`.scroll-top`, 04-chat-dock-appearance.css:2650, z 40) sits under the New note fab (z 44) on Notes at 390: the arrow at x 310-352, y 710 is half covered. Not in the brief; lifting it needs a `body[data-tab]` rule like the toast box's (10-responsive.css ~1700), not a root `:has()`.
- A long map name still ends in an ellipsis at 90px; the full row is in the opener's tooltip, which a touch screen never shows.
- The Map chip is hidden below 600, so the kind is only in the picker's rows and tooltip; if that reads wrong, move the chip into the picker face as an icon.
- Not verified: a real device keyboard after double-tapping a topic at 0.72; the Notes fab clearance with a long last note (scroll end measured on 3-line cards only).
