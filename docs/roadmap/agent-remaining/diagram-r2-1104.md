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
