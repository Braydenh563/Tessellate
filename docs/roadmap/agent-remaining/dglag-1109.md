# dglag-1109: the Diagram builder's slow open and the close that did not close

- done: the single-flight door (diagram-embed.js `open`), the Quick access tile's working ring (dashboard.js `quickLinkButton`), tests/test_diagram_open_lag_1109.py.
- Measured (Playwright, fresh start, port 8791, 300 notes, real fastembed model): 3 presses made 3 dialogs and took 3 X presses (8x CPU), now 1 and 1 (174 ms press to gone); open 3.5 to 3.9 s at 8x, 0.47 to 0.67 s at 1x, before and after.
- Ruled out: the search model's load and a 200-note backfill (health probe at most 314 ms, open 553 ms during the backfill, GIL gaps at most 29 ms).
- Swept: all 71 Quick access tiles; 3 (OCR workspace, New board, Library bin) are still busy at 2.5 s and settle by 12 s, none stays busy.
- left: INBOX 1722, the open waits on the 5 MB Library bundle (documents-mermaid.js holds `diagramModel`); the owner's 10 s is not reproduced here.
