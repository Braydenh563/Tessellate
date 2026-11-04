# diagram R2 (INBOX 1614), 1104

Reproduced first, on both mounts (sweep: a Playwright script opening `openDiagramBuilder` for the dialog and an `.mmd` document for the Documents page, an 8-block flowchart, heights by `getBoundingClientRect`, serve.sh on :8824). Cause: `.md-mermaid` (mermaid-lazy.css, loads later) gives every figure `margin: var(--space-4) 0`, which beat the picture's one-class `margin: 0`, so the picture sat 2 margins short of the blocks pane.

| mount and window | container width | picture before | picture after | blocks pane |
| --- | --- | --- | --- | --- |
| dialog 1440x900 | 1174 | 485.6 | 504.8 | 504.8 |
| page 1440x900 | 1024 | 414.4 | 433.6 | 433.6 |
| dialog 1100x700 | 1024 | 356.3 | 370.7 | 370.7 |
| page 1100x700 | 722 | 213.4 | 227.8 | 227.8 |
| dialog 800x600 | 732 | 186.3 | 200.7 | 200.7 |
| page 800x600 | 502 (under 600) | 156.0 | 156.0 | 160.0 (own 26vh kept) |

- done: picture fills the pane height (selector `.dgm .dgm-picture`), tests/test_diagram_view_1614.py.
- done: `frontend/js/diagram-view.js` (lazy, `LAZY_MODULES.diagramView`, one export `diagramModel.view`) replaces `zoomable`; `fig.onpaint` is a list; `.dgm-stage` wraps the figure and holds the `.dock.dgm-zoom` bar; DESIGN.md row plus `test_the_diagram_zoom_bar_is_a_plain_corner_dock`; Guide `diagram-blocks` (1895 of 1,900 chars).
- measured (sweep :8824, 8-11 block flowchart): Fit margin 8 / 8 px top and bottom (dark and light); Ctrl+wheel notch 190.1 to 237.7 px wide (x1.25); 100% is the drawn width (360 px); ArrowDown pans 48 px; key 0 and Fit return to `data-zoom="fit"`; an edit keeps the scale (dialog: 371.4 px before and after, `data-zoom` 1.95 to 2.13 because Fit moved); a kind change (flowchart to mind map) is Fit; narrow (container 502 and 390 window) the stage keeps 26vh (156 of 600, 219.4 of 844).
- left: after an edit the picture scrolls back to the top (the image element is replaced); the zoom bar is 52 px tall in a 156 px phone picture (touch sizes); a real touch pinch and double tap were not driven (ported from `zoomable`, not run); Space+drag is not added (a plain drag pans when the picture is larger than the pane).
