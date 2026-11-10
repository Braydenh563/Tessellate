# dgmleft-1108 remaining (branch agent/dgmleft-1108, port 8784)

Done:
- 1 e2dff89a bottom-right dead spot: a drop over the zoom bar or the shelf now lands (diagram-canvas.js `over`, diagram-seq-canvas.js `over`). Picture 755x537, points at 4% and 96%: tl, br and 95%/95% were refused before; all five take a drop after.
- 2 7a0efeb1 `openMenuAtPoint` returns the menu; the Kind menu and the shelf caret menu decorate that element. The Kind menu showed 4 glyphs and 1 active row before and after in the app (it is moved to body, `action-menu-escaped`, only after the decorate ran), so the loss was a timing risk, not a reproduced bug.
- 3 77cfe9de coarse handles lean fully out (diagram-edges.js `showHandle`): overlap 10 px to 0 px on all four sides at 390x844 with touch; a mouse keeps 12.
- 4 Guide `diagram-blocks` 1895 of 1900: a shelf drop joins the nearest box, Kind asks before it clears blocks; dialog help (diagram-embed.js) says Kind asks. The Mermaid-document sentence went; every pinned phrase in test_manual_parity.py stays.

Item 5, checked and left (smallest first):
- DD-13 reduced motion in the picture: already holds. Under `prefers-reduced-motion: reduce` the picture's pan and zoom have no transition; 96 controls still fade colour and opacity over 0.12 s, which the app keeps by design (only `data-ui-motion="off"` zeroes them). The look menu half of DD-13 is a design decision (below).
- diagklm "(m) Source view does not fold": needs a decision on where the fold button sits when the source is a textarea (rail or none). Recommend: leave Source unfoldable, it already fills the pane.
- R16 colour in the multi-select bar: already built (diagram-multi.js:40).

Recommendations for the owner (design decisions, not taken):
- DD-5 Source editor: a code surface with line numbers and an error marker is the right fix, but Tab indenting traps keyboard focus. Recommend gutter and error marker only, Tab keeps moving focus, Ctrl+] and Ctrl+[ indent.
- DD-13 Look menu (clean or hand-drawn, spacing) and R13 curve and spacing: one View popover writing the kept `%%{init}%%` line; recommend building R13 first (curve, spacing), hand-drawn after.
- R14 cylinder, parallelogram and double-headed arrows: the print and parse side need new shape ids; recommend a plan step with the model change first (diagramModel parse and print tests), then menu rows.
- Shelf on touch (mouse only now, the Add sheet serves touch): keep as is, the spec cut it on purpose.
- R12 "Done from a document opens the starter and saves a separate file": decide empty builder or pick an existing diagram (recommend pick, with a New row).
- S6 blind tests with the left panel folded and the default fold: need the blind-tester agent, not run here.

Not verified: a real finger on the handles (touch emulation only); the dialog (embed) mount of the Kind menu; the sequence shelf was driven too: a Message tile taken at all five points after the change (not measured before).
