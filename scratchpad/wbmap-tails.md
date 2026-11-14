# Whiteboard and mind map tails, ranked (2026-10-04)

Ranked by what a person making boards and maps notices first, then cost
(S under an hour, M a few hours, L a session). Every row was checked against
the running app on this head (`serve.sh 8850`), not against the docs: four of
the five tails the brief named were already built.

## Named in the brief, checked first

| Item | State on this head | Measured by |
| --- | --- | --- |
| WHITEBOARD_PLAN decision 7's other half (one highlighter table, two renderers) | built 2026-09-20 | `sketchparity.js` 10/10 |
| The phone context bar comparison | decided and built (it pins) | `wbcontextphone.js` 6/6 at 390x844 |
| Sketch handles at zoom | built | `wbhandlezoom.js` 17/17 |
| The arrange panel items (INBOX 12) | built; the probe was stale | `wbinbox12.js` 4/6 to 6/6: it read the first of four `data-wb-ctx="arrange"` groups and reported the other ten missing |
| The mapux leftover list | bend-grip right-click built 2026-09-26, marquee Escape built 2026-09-23; the connect-drag cue built here (row 5) | `maptwokinds.js`, `wbmarqueeescape.js`, `maplinkcue.js` |

## Ranked, with what this run did

| # | Item | Impact | Cost | Source | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Map: Tab, a name and Enter typed at speed saved two empty topics (a required sweep red on the base, `wbkeywalk.js` 8/10) | high | S | found here | **built** f9109ff |
| 2 | Board: text inside a shape (tldraw, Excalidraw, Miro, FigJam) | high | M | competitor, decision 12 | **built** |
| 3 | Map: a topic can be a task, counted up the branch (MindNode, XMind) | high | M | §12.2 item 4 + competitor, decision 15 | **built** d5aaabb |
| 4 | Board: a label on a connector (Miro, FigJam, Excalidraw) | medium | M | competitor, decision 13 | **built** e81b329 |
| 5 | Map: which kind a connect drag will make, while in flight | medium | S to M | MINDMAP_PLAN 13c | **built** 837d759, with a found bug (the menu's Connect row threw) |
| 6 | Quick sketch bar wraps at 820 on Large text (INBOX 276) | medium | S | plan | **half** 761e65f: Large text one row; Large plus Spacious 41px short, open |
| 7 | Map: a note behind a topic (§12.2 item 5; XMind, MindNode notes) | medium | M | plan | **built** (decision 18); a note node's own text in place is open |
| 8 | Map: outline view beside the map (§12.2 item 8) | high | L | plan | open |
| 9 | Map: branch numbering toggle (§12.2 item 7) | low | S to M | plan | **built** (decision 17) |
| 10 | Map: branch palette and font at map level (13e remainder; drawn in two places) | medium | M | MINDMAP_PLAN 13e | open |
| 11 | Map: Insert and Arrange markup still in a map's top bar (20 hidden controls) | low | S | mapux2 | **kept** (decision 16: the board's own); a found bug fixed, the toggles drawn on a map after an escaped menu |
| 12 | Map: boundaries, summaries, presentation mode, comments (§12.2 items 1, 2, 9, 6); board frames and lock | medium each | L each | plan | open |
| 13 | Owner-only checks (BACKLOG, "Device and owner checks from the mindmap plan"): 13g middle-button pan, INBOX 419 (WebView2 menus), right-drag pan (a decision), the AI half (fake transports only) | n/a | n/a | plan | open |
