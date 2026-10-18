# mindmap-1018 (Sonnet, MINDMAP_PLAN section 13 and 12.1 to 12.3)

Branch: this worktree (cut from claude/trusting-cannon-wrf8s5). Port 8795, data /tmp/mm-mm1018.

## Step 0: what is built, by grep of code and HISTORY.md (2026-10-18)

| Plan item | State | Evidence |
| --- | --- | --- |
| 13a, 13a-open, 13a-view (render, drag, cull) | Built | plan strikethroughs; HISTORY 2026-09-21, 09-23 |
| 13b strip sized like a topic, 13c one vocabulary, 13d export of cross-links, 13e map theme, 13f doors | Built | plan strikethroughs; HISTORY |
| 13g middle-button pan on the owner's machine | Open, needs the owner (windowed Chromium autoscroll, not reproducible headless) | plan 13g |
| 13 "Not verified": dark mode, 820 wide strip | Open, measurable | plan "Not verified" |
| 12.1 controls | Closed 2026-10-05 | plan 12.1 |
| 12.2 items 1 to 10 | Built (item 4 "tags on a topic" is the XMind labels, canvasdepth2: `data.labels`, HISTORY line 49112) | plan 12.2; HISTORY |
| 12.2 boundary round a lasso'd set that is not one branch | Open, small | plan 12.2 item 1 |
| 12.3 item 1 nodes are notes | Built piecewise (decision 18 note behind a topic; `wbMapAddReference`; generate maps title lines to note nodes) | HISTORY 42308 |
| 12.3 item 2 Suggest branches, Summarise this branch | Built (`routes_map_suggest.py`) | HISTORY op3-1005 |
| 12.3 item 2 **Expand from my notes** | **Open, taken first**: no code (grep `expand` in map code 0 hits) | Phase G list |
| 12.3 item 2 ghost topics on the canvas | Open, waits on boot CSS room (the picker dialog is the shape) | Phase G list |
| 12.3 item 3 chat "Make a map" opening as floating topics | Open, large (chat plus map editor); `propose_map` writes a new board today | plan 12.3 item 3 |
| 12.3 item 5 study: the note behind a topic as the answer | Open | plan 12.3 item 5 |
| 14.4 topic effect and Phosphor icon in PNG and SVG | Built (HISTORY line 1313, `wbExportTopicEffect`, `wbExportTopicGlyph`); plan line is stale | HISTORY |
| 14.4 linked stickers | Open, needs a reversal of WHITEBOARD_PLAN decision 25 (owner) | plan 14.4 |
| 14.4 reaction stamps on a board card | Open, WHITEBOARD territory | plan 14.4 |
| VC12 Harper on node labels | Open, S | OPEN.md 250 |

Order taken: (1) Expand from my notes; (2) the dark and 820 measurements of section 13; (3) the rest as time allows.

## Log

- done: 95eb617 Expand from my notes (`/expand`, `wbMapExpandFromNote`, shared picker) and the study note answer (`wbMapStudyQuestions` note questions, `wbPresentCaption`). 12/12 sweeps each at 1440 and 390.
- decided not to build: a boundary round a lasso'd non-branch set (MINDMAP_PLAN decision 19 excludes it).
- done: the dark and 820 reads of section 13, recorded in MINDMAP_PLAN "Not verified". mapedgelag passes; maptheme and mapnarrow fail identically in light and dark (stale sweeps); one real finding below.

## Remaining (one line each)

- done (left-1018): the 820 strip over the "Branch 1" handle (0 of 192), the three stale sweeps (maptheme 24/24, mapnarrow 3/3, mapstrip 43/43), the chevron under the grip at 390; see HISTORY "left-1018".
- Open question: a Plain topic that is filled (or filled by its level) keeps its tint, because `.wb-map-filled` (07-whiteboard-misc.css:8111) is drawn after `[data-shape="none"]` (:8084) at equal specificity; mapstrip.js now asserts the tint stays. If the owner means Plain to be no box at all, put `:not([data-shape="none"])` on the filled rule and flip the sweep.
- 12.3 item 2 ghost topics on the canvas (waits on boot CSS room); item 3 chat "Make a map" as floating topics (large).
- 13g middle-button pan, 14.4 linked stickers and reaction stamps: need the owner.
- VC12 Harper on node labels (OPEN.md 250).
