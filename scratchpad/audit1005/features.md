# Audit 2026-10-05: feature completeness (whiteboard, mind map, documents)

Area: "features". Read-only on the code. Server: `:8835`, data `/tmp/mm-audit-features`.
Head audited: `64ddf14`. Probes written to this session's scratchpad (not the repo):
`wb1.js`, `map1.js`, `kb100.js`, `lat.js`, `lat2.js`, `fm.js`, `typeahead.js`,
`doc1.js`, `doc2.js`, `md1.js`, `bg1.js`. Each number below comes from one of them
or from a file:line.

Scope widened twice by the owner (INBOX 558, "take everything from draw.io",
"the ability to save custom elements"). Sections 5, 6, 8, 9 and 11 answer that.

## 1. Summary: the five worst things

1. **A FreeMind round trip loses the central topic** (FEAT-01). A one-root map
   exported to `.mm` comes back with its root gone and its children as loose
   roots. Every `.mm` from Freeplane or XMind arrives the same way. This breaks
   MINDMAP_PLAN §12.0's "the exports round-trip". The test passes only because
   it starts from an import that had already dropped the root.
2. **Adding a topic is slow, and slower on bigger maps** (FEAT-02). From
   Tab/Enter to an editable topic: 250 to 800ms at 6 topics, 520 to 1,640ms at
   101, 870 to 2,000ms at 301. One Tab at 101 topics costs two full renders,
   528ms and 304ms. Typing 100 topics by keyboard took 92s.
3. **Footnotes print as raw markup** (FEAT-03). `[^1]` renders only in Live. In
   Read, Print/PDF and the HTML export it shows as literal `[^1]` text, and
   every exported comment shows as `[^c1]: remark`. Phase 5's "comments travel
   as footnotes" is built on that broken render.
4. **A board's look lives in the browser, not on the board** (FEAT-06). The
   background colour is one localStorage key shared by every board. The
   background image is a per-board localStorage key. Neither syncs, neither is
   in backups, and the desktop window and a browser tab show different boards.
   The image upload is also listed as an orphan (`used_by: []`), so "clean up
   orphaned media" deletes it.
5. **The board still lacks most of draw.io's core**: an object library, layers,
   version history, elbow connectors, flowchart shapes and Mermaid in or out
   (sections 4 and 5). On top of that, the z-order buttons labelled "Bring
   forward" and "Send backward" jump to the very front or back (FEAT-07).

Counts: High 3, Medium 10, Low 6 (19 findings).

## 2. Findings, by severity

### High

**FEAT-01. FreeMind import drops the root topic, so a single-root map does not round-trip.** FIXED cc89dcb
- Evidence:
  - `fm.js` exports Root>{A>{A1}, B} as `<map><node TEXT="Root">…`.
  - Re-imported, it comes back as roots `[A>{A1}, B]` and Root is gone.
  - `kb100.js`, 101-topic map: Markdown 101/101 back, OPML 101/101, FreeMind 100 back with 11 parent edges lost.
  - Cause: `_parse_freemind` (`routes_whiteboard.py:4263-4268`) takes a single top node as the board title.
  - `_export_freemind`'s docstring (`:3856-3860`) promises that "a single-root map is written as itself, so the common case round-trips unchanged".
  - `tests/test_mindmap.py:573` starts from an import that has already dropped its root, so it never tests a map made in the app.
- Impact:
  - Every `.mm` from Freeplane, XMind or FreeMind loses its central idea: the map arrives as N loose trunks.
  - The app's own `.mm` backups lose the centre.
- Severity: High. NEW. Claimed built (MINDMAP_PLAN §12.0, "FreeMind and OPML round-trip").
- Fix (S):
  - Import a single top `<node>` as the root topic, and take the board title from the file name or the root text.
  - Replace `test_freemind_imports_with_its_root_as_the_maps_name` (it pins the wrong behaviour; flag to the owner as a decision change).
  - Add a test: a map made in the app with one root survives export and import.

**FEAT-02. Add-topic latency grows with the map. The whole map is re-rendered on every Tab.** FIXED 46a5fa0 (100ms gate not met here: median 224ms at 301 under load 9-14); second pass 1e361d5 (render per add 21-63ms against 122-421; key to editable median 177-276ms against 265-351 for the base on the same runs at load 7-10; the 100ms gate still not met here)
- Evidence:
  - `lat.js`, tree-right, time from key to `document.activeElement.wb-map-text`:

    | Topics | Six adds (ms) |
    | --- | --- |
    | 6 | 665, 259, 542, 803, 249, 472 |
    | 101 | 836, 982, 727, 521, 1642, 1549 |
    | 301 | 1997, 1336, 1249, 1554, 944, 868 |

  - `lat2.js` at 101 topics, one Tab: 1,461ms to editable. The server took POST 18ms and move-many 72ms. `renderWhiteboardNow` ran twice, at 528ms and 304ms.
  - `kb100.js` (10 branches of 9, fast typist): 101 topics in 91.9s, editor latency median 604ms, p90 978ms.
  - Type-ahead is buffered and nothing was lost (`typeahead.js`, 6/6 labels correct), so this is slowness, not data loss.
- Impact: the map's core gesture lags. XMind and MindNode answer Tab in one frame, and the owner already called the map "slow" (INBOX 305).
- Severity: High. NEW. MINDMAP_PLAN 13a-open claims "renderWhiteboard 47.8ms after one topic moves" at 500 topics. That holds for a move; the add path was never gated.
- Fix (M):
  - Profile the add path in `wbMapAddChild`/`wbMapAddSibling` (`whiteboard.js`) through the branch tidy.
  - Paint the new topic optimistically before the POST.
  - Run the branch tidy without a full `renderWhiteboard`, using the 13a-view culled join.
  - Gate: key to editable at or under 100ms at 300 topics, in a new `mapaddlatency.js`.

**FEAT-03. Markdown footnotes render only in Live. Read, Print/PDF and HTML export show them raw.** FIXED 7b5547e
- Evidence:
  - `md1.js`: `renderMarkdown(d, "Text[^1].\n\n[^1]: A footnote.")` gives `<p>Text[^1].</p><p>[^1]: A footnote.</p>`. `markdown.js` has no footnote handling at all.
  - `doc2.js`: the render a print triggers (`docPrintComments = true`) reads `A claim[^1] and this phrase[^c1] here. … [^1]: The footnote text. [^c1]: check the source`.
  - `exportDocumentHtml` clones `#doc-preview` (`documents.js:9580`), so the HTML export inherits the same text.
  - The "/" menu offers "Footnote" (`editor.js`).
  - HISTORY.md:27038 records footnotes as built in Live only.
- Impact:
  - A writer's footnotes, and every exported comment, print as markup.
  - PDF is the main way a document leaves the app.
- Severity: High. NEW. Claimed built (DOCUMENTS_PLAN §13 and Phase 5 item 1: "comments travel as footnotes, exactly as they do in the PDF export").
- Fix (S/M):
  - Add footnote rendering to `markdown.js`: references become `<sup><a>`, definitions are collected into an `<ol class="footnotes">` at the end, and back-links are included.
  - Test the renderer in node (the `test_doc_math.py` pattern) and extend `doccomments.js` to assert no `[^` in the print render.

### Medium

**FEAT-04. Rich paste into a document loses all formatting, including link URLs.** FIXED ad14b76
- Evidence:
  - `doc1.js` pastes `text/html` `<h2>Pasted title</h2><p><b>bold</b> and a <a href=…/x>link</a></p><ul><li>item one</li></ul>`.
  - The document receives the plain text `Pasted title\nbold and a link\nitem one`, and the URL is lost.
  - The only HTML paste handler is for tables (`docTablePasteEvent`, `documents.js:4576-4614`).
- Impact: copying from a web page, Word or Google Docs (the most common way text gets into a writing app) loses headings, emphasis, lists and links.
- NEW. Fix (M):
  - Convert sanitized HTML to Markdown on paste, through an allowlist walker over a `DOMParser` tree (h1-h6, p, b/strong, i/em, a[href] with safe schemes, ul/ol/li, blockquote, code/pre, img with `/media` or http src, table goes through the existing grid path).
  - Shift+Ctrl+V keeps plain text.
  - No library needed; tests in node.

**FEAT-05. Imported and generated maps open in the Free layout, so keyboard adds pile up.** FIXED cc89dcb
- Evidence:
  - `import_board` passes `layout=DEFAULT_BOARD_LAYOUT` ("free") (`routes_whiteboard.py`, import route), while `createNewBoard` makes `tree-right` (`whiteboard.js:12048`).
  - `kb100.js` on an imported map: 101 topics with **240 overlapping on-screen pairs**. The same run on tree-right: **0**.
  - Imported topics are placed on a diagonal staircase (x 0/320/640, y 0/170/340; `fm.js`).
- Impact: anyone who brings a map in (Markdown, OPML, FreeMind, or "make a map of these notes") gets an overlapping mess at the first Tab.
- NEW. Fix (S):
  - Import into `tree-right`, or into the layout named in the file's `_layout`.
  - Run one tidy after import.
  - Check whether `/boards/generate` and the AI's `create_mindmap` share the default.

**FEAT-06. The board's background is stored per browser, not per board. Its image counts as an orphan.** FIXED 013375b
- Evidence:
  - `wb-bg-color` is one global key (`whiteboard.js:8952-8976`).
  - The image is stored under `wb-bg-image-${boardId}` in localStorage (`:964-971`, `:9205`).
  - The board row carries no background (`wb1.js`: keys id, title, counts, type, layout, previews).
  - `bg1.js`: after setting a board image, `GET /media/orphans` lists it with `used_by: []`.
  - `media_gc._referenced_filenames` scans objects, documents and entries only.
  - HISTORY.md:33529 claims "per-board background".
- Impact:
  - Backgrounds vanish on another device, in the desktop window (its own webview profile), after a cache clear and in backups.
  - The "clean up orphaned media" button deletes the file.
- NEW. Fix (S):
  - Store `background: {color, image}` in `board_settings` beside `type`, `layout` and `theme`.
  - Migrate the localStorage values once on open.
  - Have `media_gc` read board settings.
  - Keep grid and snap as device preferences.

**FEAT-07. "Bring forward" and "Send backward" go to the very front or back. No single-step z-order exists.** FIXED 93bbb62
- Evidence:
  - `wbSetZOrder` writes `max+1` or `min-1` (`whiteboard.js:4285-4288`).
  - The Arrange menu says "Bring forward ]" and "Send backward [" (`index.html:5914-5915`), and the context bar uses the same words (`:6558-6559`). The right-click menu calls the same function "Bring to front" and "Send to back" (`whiteboard.js:5283-5284`).
  - `wb1.js`: with A z1, B z2, C z3, one "Bring forward" on A gives `A:4 B:2 C:3`, so A went from bottom to top.
- Impact:
  - Three names for one action, and the step-wise action every competitor has is missing.
  - In draw.io, Figma, Miro and PowerPoint, `]` / `[` mean one step, and Ctrl+Shift+F / Ctrl+Shift+B mean to front / to back.
- NEW. Fix (S):
  - Add `wbStepZOrder(dir)`, which swaps with the next overlapping peer.
  - Map `]`/`[` to one step and Ctrl+]/Ctrl+[ to front and back, with four labelled items in Arrange and the right-click menu.
  - Update the board help and the `wb-empty-hint` key list in the same commit (order 13).

**FEAT-08. Mermaid fences render as code. BACKLOG 29c assumes they render.** FIXED ad14b76 (claim corrected), flowchart fences drawn FIXED a02d045 (own parser, no vendored Mermaid)
- Evidence:
  - `md1.js`: a ```mermaid fence renders as `<div class="code-block">…<code data-lang="mermaid">`.
  - "Mermaid diagram" exists only as a language label (`documents-code.js`).
  - BACKLOG 29c: "this app already renders Mermaid fences in note/doc markdown (grep `mermaid` in app.js)". It does not.
- Impact: the Markdown world's diagram lingua franca (GitHub, Obsidian, Notion import) shows as code in notes and documents, and boards cannot take it in either.
- NEW (corrects a BACKLOG assumption). Fix (M/L): see brief W5. Vendor mermaid (MIT, about 3 MB, lazy) or write a flowchart-subset parser into board objects. Recommend the parser, for the CSP and size reasons the math renderer gave (`documents.js:6362`).

**FEAT-09. Pasting text onto a board or a map does nothing.** FIXED 595db03 (the map half: POST /boards/{id}/nodes/outline; the board half is the whiteboard agent's)

**FEAT-09. Pasting text onto a board or a map does nothing.** FIXED 8320ea2 (the board; a map's outline paste is the mind map agent's)
- Evidence:
  - The canvas paste listener takes files only (`whiteboard.js:11485-11488`).
  - There is no `navigator.clipboard` read (`:4829` comment).
  - `wb1.js`: 3 items before a `- one\n- two\n- three` paste, 3 after.
  - `map1.js`: 4 topics before pasting a nested list onto a selected topic, 4 after.
- Impact:
  - tldraw, Miro, FigJam and Excalidraw make a paste of text into a text item or sticky.
  - XMind, MindNode and SimpleMind make an indented list into a branch.
  - Here the clipboard from any other app is dead on both canvases.
- NEW. Fix (S/M):
  - On a map, `text/plain` with list or indent structure goes through `_parse_markdown_outline` as children of the selection, as one recorded gesture.
  - On a board, one paragraph becomes a text box, several lines become a grid of stickies, and a URL becomes a link card.

**FEAT-10. No board version history, though the data to rebuild one is already recorded.**
- Evidence:
  - All 13 item-write routes are wrapped in `@events.writes("whiteboard_{node,sketch,object}", …)` (`routes_whiteboard.py:2259-3401`), and `events.states_at` exists (`core/events.py:319`).
  - The only reader is `/entries/{id}/history` (`routes_entries.py:2639`), which replays the board's note text (`# name`), not its items.
- Impact: there is no "the board as it was yesterday". Undo dies on reload (WHITEBOARD_PLAN "Open").
- KNOWN (BACKLOG 29c, "needs a design decision"). The decision is now cheap: the change log already exists. Fix (M): brief W2.

**FEAT-11. The command palette has no board or map commands.** FIXED 46a5fa0 (map rows; the board's are the whiteboard agent's)

**FEAT-11. The command palette has no board or map commands.** FIXED 93bbb62 (boards; map rows come with the map's own table)
- Evidence:
  - `palette.js` mentions `wb` only to name the open board as the AI's subject (`:262-265`).
  - Documents have `DOC_COMMANDS`, 47 entries (`documents.js:2337`).
- Impact: on the two most control-dense surfaces, nothing can be found by typing its name, and a keyboard user has no index of what exists.
- NEW. Fix (M): one `WB_COMMANDS` table feeding the palette, the menus, the shortcut sheet and the help (section 8).

**FEAT-12. The AI can add to a board but cannot change, move, restyle or delete anything.** FIXED (Phase G: seven tools, test_ai_board_edit.py)
- Evidence:
  - The board and map tools are `read_whiteboard`, `search_whiteboard`, `add_whiteboard_card`, `add_whiteboard_link`, `generate_diagram`, `read_mindmap`, `create_mindmap`, `add_map_node` and `link_map_nodes` (`ai/tools/__init__.py:2814-2998`).
  - None renames a topic, moves or reparents one, deletes, restyles, adds a sticky, shape, text or frame, or groups.
- Impact: "tidy this board", "rename these three topics" or "put these stickies into frames by theme" cannot be done by the agent.
- NEW. Fix (M): `edit_board_item`, `move_map_node`, `delete_board_item` and `add_board_shape`, each one event and one undo entry, read-before-write. Write-ups belong in AGENT_SKILLS_REFORM's tool budget.

**FEAT-13. Map and board AI growth is missing.**
- The topic menu (27 rows, `map1.js`) had no AI row when audited; "Branches from my notes", "Expand from my notes" and "Summarise this branch" were added later (FEAT-13, HISTORY).
- KNOWN (MINDMAP_PLAN §12.3 item 2). Spec in section 10 (idea M3).

### Low

**FEAT-14.** PNG export is 1x. Board units become pixels (`wbRasterizeSvg(svg, width, height)`, `whiteboard.js:8016`). There is no scale or transparent-background option, and the file is always `whiteboard-whole.png` or `whiteboard-selection.png`, never the board's name (`:8017`). Plan §12.2 item 10 asks for "PNG at 2x". NEW. Fix (S): add scale (1x, 2x, 3x), a transparent switch and a title-based name to the export dialog's PNG row. FIXED b21ae81

**FEAT-15.** FIXED 46a5fa0 A typed topic takes two undo steps (one create, one rename). `kb100.js`: 5 Ctrl+Z took 101 topics to 99. XMind treats add-and-type as one. NEW. Fix (S): fold the first label commit into the create's undo entry when it follows within the same edit session.

**FEAT-16.** FIXED 46a5fa0 After a topic label is committed, focus lands on `<body>` (`kb1.js`: `after type+Enter: BODY`). Keys still work because they are read on the document, but a screen reader loses its place and announces nothing. NEW. Fix (S): return focus to the canvas and call `wbAnnounce(label)`.

**FEAT-17.** FIXED 46a5fa0 The map topic's menu has an "Order" group, "Bring to front" and "Send to back" (`map1.js`), which mean nothing in a tidied tree. NEW. Fix (S): hide it on map topics (keep it for free-layout maps only, or drop it).

**FEAT-17.** The map topic's menu has an "Order" group, "Bring to front" and "Send to back" (`map1.js`), which mean nothing in a tidied tree. NEW. Fix (S): hide it on map topics (keep it for free-layout maps only, or drop it). FIXED 93bbb62

**FEAT-18.** The Word export drops images: `docexport._inline` writes no picture (`core/docexport.py`, no `add_picture`). It also needs an optional extra that is absent here (`import docx` fails in `.venv`), so the default install gets a 501. The extra is KNOWN and decided; the images are NEW. Fix (S): `add_picture` for `/media` images, read from the media dir.

**FEAT-19.** Surfaces disagree about what they offer. FIXED 93bbb62 (the Arrange and Edit menus)
- The Arrange menu has align, distribute and z-order but no Group, Ungroup, Same size or Lock. Those live only on the context bar, Ctrl+G or the right-click menu.
- Lock, comment, shape text, connector label and "export this frame" have no menu entry at all; they are only on right-click, double-click or a key (section 8).
- NEW. Fix: section 8's single command table.

## 3. Claimed built but not

| Claim | Where | What is true |
| --- | --- | --- |
| "Everything the map shows … the FreeMind and OPML exports round-trip" | MINDMAP_PLAN §12.0 | A one-root map loses its root through FreeMind (FEAT-01). OPML and Markdown hold. |
| "renderWhiteboard 47.8ms after one topic moves … open under 1s" (13a-open) | MINDMAP_PLAN §13 phases | True for a move. One add costs 832ms of render at 101 topics (FEAT-02). |
| "Comments travel as footnotes, exactly as in the PDF export" | DOCUMENTS_PLAN §13, Phase 5 item 1 | They travel as literal `[^c1]` text, because footnotes never render outside Live (FEAT-03). |
| "Mermaid fences already render in note/doc markdown" | BACKLOG 29c | They render as a code block (FEAT-08). |
| "per-board background" | HISTORY.md:33529 | The colour is global per browser; the image is per board in localStorage only (FEAT-06). |
| Old spec C13 "dead `wb-search`" | master spec | Already fixed (wired search, `wbBoardSearchRun`). Correctly closed. |

## 4. Whiteboard: the old spec's gap matrix, re-checked row by row

Status: done / partial / missing / decided out (decision N, WHITEBOARD_PLAN §4 unless named).
Priority is for a local-first notebook whiteboard (P1 core, P2 valuable, P3 later, "-" nothing to do).

### C1. Canvas and structure

| Feature | Now | Evidence | Pri |
| --- | --- | --- | --- |
| Infinite pan and zoom | done | `handleWbZoom`, navigator | - |
| Multiple boards | done | Library gallery, `createNewBoard` | - |
| Background colour or image | partial | per-browser only (FEAT-06) | P1 |
| Grid (lines, dots, iso) and snap | done | `wbApplyGrid`, `wb-snap` | - |
| Rulers | missing | no `ruler` in either file | P3 |
| Manual drag guides | missing | smart guides cover it | P3 |
| Frames or pages within a board | done (frames) / missing (pages) | decisions 14, 16, 18 | P2 pages |
| Folders for boards | partial | gallery type filter and sort (`boardTypeFilter`); spaces exist app-wide | P3 |
| Board templates | missing for boards; done for maps (5 templates, `WB_MAP_TEMPLATES`) | BACKLOG 4b open | P1 (library spec) |

### C2. Selection

| Feature | Now | Evidence | Pri |
| --- | --- | --- | --- |
| Click, marquee, lasso | done | rail V/K | - |
| Shift-click | done | `wbHandleItemClick` | - |
| Select all | done | Edit menu Ctrl+A, `wbSelectAllItems` | - |
| Tab cycles items | done | decision 10, `wbWalkItems` | - |
| Select same kind or style | missing | none | P2 |
| Cards-only, links-only, sketches-only | missing | none | P3 |
| Anchor-level vector selection | decided out (Illustrator tier, spec D3) | - | - |
| Isolation mode | missing | groups are flat | P3 |

### C3. Transforms

| Feature | Now | Evidence | Pri |
| --- | --- | --- | --- |
| Move, resize, rotate by handles | done | decision 6 | - |
| Arrow nudge and Shift | done | `wbNudgeSelection` | - |
| Shift keeps proportions | done | `wbKeepAspect` (`:12287`) | - |
| Resize from centre (Alt) | missing | none | P3 |
| Numeric X, Y, W, H, angle | missing | no inputs in `index.html` | P2 (Format panel) FIXED (Phase B) |
| Flip horizontal or vertical | missing | none | P2 |
| Skew | decided out (spec D3) | - | - |
| Alt-drag duplicate | done | `wbFinishDrag(…, altCopy)` (`:4745`) | - |
| Repeat last transform | missing | none | P3 |

### C4. Alignment and snap

| Feature | Now | Evidence | Pri |
| --- | --- | --- | --- |
| Grid snap, Alt bypass | done | - | - |
| Smart guides, colour-coded | done | `wbAlignmentGuides`, guide colours | - |
| Align and distribute commands | done | 6 aligns, 2 distributes, same width and height (`#wb-context`) | - |
| Align to key object or board | missing | aligns to the selection box | P3 |
| Snap toggle | done | `#wb-snap-toggle` | - |

### C5. Drawing and ink

| Feature | Now | Evidence | Pri |
| --- | --- | --- | --- |
| Pen, highlighter, eraser | done | decision 7 | - |
| Shape recognition (beautify) | missing | none | P2 |
| Handwriting to text | decided out (spec D3; no-torch rule) | - | - |
| Math ink | decided out (spec D3) | - | - |
| Ink replay | missing | none | P3 |
| Ruler tool | missing | none | P3 |
| Pen focus view | partial | full screen and Present exist | P3 |
| Pressure sensitivity | missing | no `pressure` read in `whiteboard.js` | P2 (stylus users) |

### C6. Shapes and connectors

| Feature | Now | Evidence | Pri |
| --- | --- | --- | --- |
| Basic shapes | done | line, arrow, rect, circle, triangle, diamond (`#wb-shape-menu`) | - |
| Domain shape libraries | missing | 6 shapes total | **P1 (owner, INBOX 558)** |
| Custom or importable libraries | missing | - | **P1 (owner)** |
| Auto-attach connectors that re-route | done | 8 fixed anchors (`WB_FIXED_ANCHORS`, `:2070`), rotation-aware | - |
| Arrowhead variety | done | none, arrow, circle, square, multi-line | - |
| Connector labels | done | decision 13 | - |
| Swimlanes, containers | partial | frames carry what they hold (decision 14); no lanes | P2 |
| Hover auto-connect ("+" arrows) | missing | none | P2 |
| Auto-layout for a general diagram | partial | tree or radial over linked cards (`wbArrangeMindMap`); no layered or organic layout | P2 |
| Diagram from text (AI) | done | `generate_diagram` | - |
| Diagram from Mermaid syntax | missing | FEAT-08 | P2 |

### C7. Vector path editing

- Every row: decided out (spec D3, Illustrator tier).
- Exception: custom shapes saved from a drawn path, which the owner asked for (INBOX 558). That is section 8.2 (kind 2), not path editing.

### C8. Layers, grouping, z-order

| Feature | Now | Evidence | Pri |
| --- | --- | --- | --- |
| Bring to front or back | done | mislabelled (FEAT-07) | - |
| Forward or backward one step | missing | FEAT-07 | P1 |
| Group and ungroup | done | one `group_id` per item | - |
| Nested groups | missing | regrouping overwrites `group_id` (`:1239`) | P2 |
| Layers panel | missing | INBOX 557b | **P1 (owner)** |
| Per-object lock | done | decision 15, `whiteboard_nodes.locked` | - |
| Layer opacity or blend | missing | - | P3 |

### C9. Colour, fill, stroke

| Feature | Now | Evidence | Pri |
| --- | --- | --- | --- |
| Stroke colour, width, style, none | done | `#wb-prop-*` | - |
| Fill colour, opacity, none | done | `#wb-fill-opacity` | - |
| Whole-object opacity | missing | only fill opacity | P2 |
| Gradients | missing | - | P3 |
| Pattern fills | decided out (spec D3) | - | - |
| Swatches and saved palettes | missing | every colour is a native `<input type=color>` (`index.html:6390, 6476, 6482, 6650`) | **P1 (owner: saved styles and palettes, 8.2 kind 3)** |
| Eyedropper | partial | copy style and paste style; no colour picker from canvas (`EyeDropper` unused) | P3 |
| Caps and joins on outlines | partial | line caps only | P3 |
| Shadow or glow | missing | no `shadow` in `whiteboard.js` | P2 (draw.io Style tab) |

### C10. Text and typography

| Feature | Now | Evidence | Pri |
| --- | --- | --- | --- |
| Text boxes | done | T | - |
| Font size | done | `#wb-prop-fontsize` | - |
| Font family | missing on boards; done on maps (map theme font) | `wbMapFontStack` | P2 |
| Bold and italic | done | `#wb-prop-bold`, `#wb-prop-italic` | - |
| Text alignment | done | `#wb-prop-align` | - |
| Line or letter spacing | missing | - | P3 |
| Lists in a text box | done | `#wb-prop-bullets`, `wbBulletTextLines` | - |
| Rendered markdown in cards | done | `renderMarkdown` (`:14439`); text boxes opt in with `#wb-prop-md` | - |
| Hyperlinks on shapes | missing on board items; done on map topics (`data.link`) | `:5123` | P2 |
| Find and replace on a board | partial | find (`wbBoardSearchRun`); no replace | P2 |
| Text in shapes | done | decision 12, deliberately with no font controls | - |

### C11. Images and media

| Feature | Now | Evidence | Pri |
| --- | --- | --- | --- |
| Insert, paste or drop an image | done | `:11485` | - |
| Crop | missing | - | P2 |
| Filters | missing | - | P3 |
| Video embed | missing | - | P3 |
| Documents or files as objects | done | cards are any note or document; Library drop | - |
| Image trace | decided out (spec D3) | - | - |
| Orphaned media GC | done for objects | `media_gc.py`; misses board backgrounds (FEAT-06) | P1 bug |

### C12. Templates and components

| Feature | Now | Pri |
| --- | --- | --- |
| Pre-built board templates | missing (maps have 5) | P1 (library) |
| Save a board as a template | missing | P1 (library, "Yours") |
| Reusable linked components | missing | P3: section 8.4 recommends independent copies |

### C13. Panels and chrome

| Feature | Now | Evidence | Pri |
| --- | --- | --- | --- |
| Insert, properties, context bar | done | decisions 1 and 2 | - |
| Layers panel | missing | - | P1 |
| Swatches panel | missing | - | P1 |
| Workspace presets | missing | - | P3 |
| Status bar | partial | app status bar shows the undo pair "on this board"; zoom group bottom right; no item count | P3 |
| Contextual quick bar | done | `.wb-context` | - |
| Shortcut overlay | partial | keys listed in `#wb-empty-hint`; no "?" sheet and no palette (FEAT-11) | P1 |
| `wb-search` dead | fixed | - | - |
| Synced background | missing | FEAT-06 | P1 |

### C14 to C18

| Feature | Now | Evidence | Pri |
| --- | --- | --- | --- |
| Multi-cursor, share links | decided out (spec D3; MINDMAP §12.4) | - | - |
| Comments | done | decision 17 | - |
| Autosave | done | every gesture writes | - |
| Version history | missing | FEAT-10 | P1 |
| Named versions, diff before restore | missing | - | P2 |
| Undo and redo | done | decisions 17 and 18, 100 steps per board (spec said 20) | - |
| Undo across reload | missing | WHITEBOARD_PLAN "Open"; version history covers it | P2 |
| SVG, PNG, PDF export | done | `WB_EXPORT_FORMATS`; PNG 1x (FEAT-14) | - |
| HTML embed export | missing | - | P3 |
| Markdown or outline export of a free board | missing | text formats are `map: true` only (`:8110-8125`) | P2 |
| Mermaid export | missing | - | P2 |
| Keyboard coverage | done | decision 8 | - |
| Touch | done | - | - |
| Screen reader | partial | `#wb-announcer` plus Tab walk; no tree view of items (9.3 Layers fixes this); FEAT-16 | P2 |

## 5. draw.io catalogue against the board (INBOX 558)

draw.io is Apache-2.0: take the features, copy no code or stencils. The built-in sets below are drawn fresh. Icons come from the vendored Phosphor set (MIT, `frontend/vendor/phosphor/LICENSE`; it is a font only, see 8.3).

| Area | draw.io feature | Board now | Evidence or note |
| --- | --- | --- | --- |
| Sidebar | Shape libraries by category (General, Misc, Advanced, Basic, Arrows, Flowchart, Entity Relation, UML, BPMN, network, cloud) | missing | 6 shapes on the rail |
| Sidebar | Search shapes | missing | - |
| Sidebar | Scratchpad (drag to save, reuse) | missing | owner "Yours" (8.2) |
| Sidebar | Favourites, recently used | missing | - |
| Sidebar | Custom libraries, import and export of `.xml` libraries | missing | - |
| Sidebar | "More shapes" to switch sets on and off | missing | - |
| Format panel | Style tab: fill, gradient, line, opacity, shadow, rounded, glass, sketch style, Edit style (raw) | partial | fill, line, opacity of fill; no gradient, shadow, rounded toggle, raw style |
| Format panel | Text tab: font, size, colour, B/I/U, alignment, position, spacing, wrap, background, border, HTML formatting | partial | size, B/I, alignment on text boxes; shapes get none (decision 12) |
| Format panel | Arrange tab: to front or back, forward or backward, size, position, angle, flip, align, distribute, group, lock | partial | align, distribute, same size, group; no numbers, flip or one-step order |
| Format panel | Diagram tab with nothing selected: grid, page view, background, shadows | partial | View menu: grid, background (local only) |
| Connectors | Straight, orthogonal (elbow), curved, isometric, entity relation | partial | straight and curved only (C, Shift+C) |
| Connectors | Waypoints, several per edge, drag to add | partial | one bend per link (`data.bend`, `:12913`) |
| Connectors | Fixed connection points vs floating (to the outline) | partial | 8 fixed anchors plus outline intersection (`wbBoxRayIntersection`); no custom points per shape |
| Connectors | Line jumps (arc, gap, sharp) where edges cross | missing | - |
| Connectors | Labels on edges, several, movable | partial | one label, middle only (decision 13) |
| Connectors | ER caps (crow's foot, one, many) | partial | circle, square, multi-line caps; no crow's foot set |
| Connectors | Hover arrows to clone and connect | missing | - |
| Data | Edit Data (custom properties per shape) | missing | - |
| Data | Placeholders (`%name%`) | missing | - |
| Data | Tooltips on shapes | missing | - |
| Data | Links on shapes (URL or page) | missing on board; done on map topic | `data.link` |
| Pages | Several pages per file, tabbed | missing | frames are the substitute (decisions 14, 16) |
| Layers | Named layers with show, hide, lock, move selection to layer | missing | INBOX 557b |
| Grid and guides | Grid, guides, snapping | done | - |
| Grid and guides | Rulers | missing | - |
| Grid and guides | Page view (print pages) | missing | - |
| Arrange | Align and distribute | done | - |
| Arrange | Layout algorithms: tree (vertical, horizontal), radial, organic, circle, flow, parallel edges | partial | tree and radial over linked cards; map layouts separate |
| Arrange | Autosize to text | done | `wbFitToText` |
| Arrange | Edit style (raw text) | decided out (recommend): the Format panel plus saved styles cover it without a second syntax | - |
| Style | Copy and paste style | done | Ctrl+Alt+C, Ctrl+Alt+V |
| Style | Default style for new shapes, set from selection | missing | saved styles (8.2 kind 3) |
| Edit | Duplicate with offset (Ctrl+D), clone by Alt-drag | done | - |
| Edit | Find and replace across labels | partial | find only |
| Edit | Select vertices, edges, all | partial | Select all only |
| Keys | Shortcut sheet (Ctrl+Shift+?) | partial | key list in the help card; no sheet |
| Keys | Ctrl+Shift+F / B front or back, Ctrl+] / [ step | partial | FEAT-07 |
| Keys | Alt+Shift+arrows to clone and connect | missing | - |
| Keys | Ctrl+Enter duplicate, F2 or Enter edit label, Ctrl+K link, Ctrl+M edit data, Ctrl+L lock | partial | Enter edits shape text; Ctrl+Shift+L locks |
| Export | PNG with transparent background, zoom, border | partial | PNG 1x, no transparency (FEAT-14) |
| Export | SVG, PDF (selection, page, all) | done | scope segment |
| Export | Embed diagram data in PNG or SVG (re-editable) | missing | recommend P2: put the board JSON in a `<metadata>` / PNG `tEXt` chunk so a dropped export re-opens as a board |
| Export | HTML, XML, VSDX | missing | P3 |
| View | Outline window (minimap) | done | navigator |
| View | Zoom in, out, fit, 100% | done | - |
| View | Format panel toggle (Ctrl+Shift+P) | missing | FIXED (Phase B) |

## 6. Mind map catalogue and gap matrix

Sources: XMind, MindNode, MindMeister, Miro mind maps, SimpleMind, Coggle.
MINDMAP_PLAN decisions are binding. Priority as in section 4.

| Area | Feature (who has it) | Now | Evidence | Pri |
| --- | --- | --- | --- | --- |
| Structure | Central topic, children, siblings | done | Tab, Enter | - |
| Structure | Several roots, floating topics | done | §12.0 | - |
| Structure | Drag to reparent, to reorder | done | transplant; Ctrl+Shift+arrows (`data.order`) | - |
| Structure | Relationships, labelled | done | cross-links with ring, label, reverse | - |
| Structure | Boundaries, summaries | done | decisions 19, 20 | - |
| Structure | Boundary round a non-branch set | missing | §12.2 item 1 remainder | P3 |
| Layout | Map (both sides), right, left, down (org chart), radial | done | `BOARD_LAYOUTS` | - |
| Layout | Logic chart, fishbone, timeline, tree table, matrix (XMind) | missing | §12.0 lists fishbone and timeline | P2 |
| Layout | Per-branch layout override | missing | §12.0 promises it | P2 |
| Layout | Free placement with pinning | done | `pinned` | - |
| Layout | Compact or balanced spacing | missing | fixed `WB_MAP_GAP_*` | P3 |
| Style | Per-topic shape, fill, border, font, colour | done | strip's 3 doors | - |
| Style | Map themes, palettes, font | done | 13e | - |
| Style | Line shape, width, dash, arrow, taper | done | - | - |
| Style | Saved custom themes | missing | owner "saved styles" (8.2 kind 3) | P2 |
| Keyboard | Tab, Enter, Shift+Enter, F2, Delete, arrows, C fold, Shift+F10 | done | §12.0, §12.5 | - |
| Keyboard | Add-and-type speed | **slow** | FEAT-02 | P1 |
| Keyboard | Fold to level (Alt+1 to 9), fold all | partial | "Open every folded branch"; no fold-to-level | P2 |
| Keyboard | Focus after edit | bug | FEAT-16 | P2 |
| Outline | Outline view beside the map, edit both ways | missing | §12.2 item 8 | **P1** |
| Outline | Paste an outline into a topic | missing | FEAT-09 | P1 |
| Presentation | Present by branch | done | decision 21 | - |
| Presentation | Focus on a branch | done | Focus here, depth (`#wb-map-focus-*`) | - |
| Export | PNG, SVG, PDF, Markdown, OPML, FreeMind | done | FreeMind loses the root (FEAT-01); PNG 1x (FEAT-14) | P1 bug |
| Export | Plain text outline, Mermaid `mindmap`, Word or document | missing | §12.2 item 10 (text); none for Mermaid | P2 |
| Import | Markdown, OPML, FreeMind | done | lands in Free layout (FEAT-05) | P1 bug |
| Import | XMind `.xmind` (content.json), Mermaid mindmap, drop a file on the canvas | missing | §12.2 item 10 | P2 |
| Content | Notes on topics | done (plain) | decision 18 | - |
| Content | Note topic shows its note, editable both ways | missing | §12.2 item 5, second half | P2 |
| Content | Hyperlinks, images, attachments (as references) | done | `data.link`, `data.image`, From the library | - |
| Content | Icons and markers | partial | one icon of 11 (`#wb-map-strip-icon`); no priority, progress, flags or several markers | P2 |
| Content | Tasks with roll-up | done | decision 15 | - |
| Content | Priority, due date, labels or tags, filter by marker | missing | §12.2 item 4 | P2 |
| Content | Equations, code in topics | missing | - | P3 |
| Navigation | Search the map | done | board search | - |
| Navigation | Minimap | done | navigator | - |
| Navigation | Statistics | done | "What this map is made of" | - |
| Reuse | Templates | done (5) | `WB_MAP_TEMPLATES` | - |
| Reuse | Save a branch, reuse it anywhere | missing | owner (8.2 kind 5) | P1 |
| Reuse | Save a map as a template | missing | BACKLOG 4b | P1 |
| AI | Generate a map from notes | done | `/boards/propose` | - |
| AI | Suggest branches, expand, summarise (grounded) | missing | §12.3 item 2 (FEAT-13) | P1 |
| Notebook | Map to document outline and back | missing | no conversion in either file | P1 (idea M2) |
| Notebook | Study or recall mode | missing | §12.3 item 5 | P2 |
| Notebook | Graph sync of cross-links | missing | §12.3 item 4 | P3 |
| Reliability | 100 keyboard topics, labels and parents correct | done | `kb100.js`: 101/101, 0 missing, 0 extra, 0 console errors | - |
| Reliability | Undo and redo of adds | done | 2 steps per typed topic (FEAT-15) | P3 |
| Reliability | Survives reload | done | server topics 101 = canvas 101 | - |

### Mind map usability pass, measured (owner ask 4)

| Step | Result | Evidence |
| --- | --- | --- |
| 100 topics by keyboard, fast typist (10 x 9 plus root) | 101/101 correct, 0 lost keystrokes, **91.9s**; key to editor median 604ms, p90 978ms | `kb100.js` LAYOUT=tree-right GAP=80 |
| Same on an imported map | correct, but **240 overlapping topic pairs** | `kb100.js` (Free layout) |
| Latency against size | 6: 249 to 803ms; 101: 521 to 1642; 301: 868 to 1997 | `lat.js` |
| Where the time goes | 2 renders, 528 + 304ms at 101 topics; server 90ms | `lat2.js` |
| Type ahead of the editor | 6 of 6 words land in the right topics | `typeahead.js` |
| Undo 5, redo 5 | 101, 99, 101 (two steps per topic) | `kb100.js` |
| Round trips | MD 101/101, OPML 101/101, FreeMind 100, central topic lost | `kb100.js`, `fm.js` |
| Paste a list onto a topic | nothing happens | `map1.js` |
| Focus after a commit | `<body>` | `kb1.js` |
| Console errors across the run | 0 | `kb100.js` |

**Not run:** drag-reparent and collapse were not driven by pointer in this pass. Existing sweeps (`mapbranchdrag.js`, `maprelink.js`, `boardundo.js` 43/43) cover them, but they were not re-run here.

## 7. Documents catalogue and gap matrix

Sources: Word, Google Docs, Notion, Obsidian, iA Writer.

| Area | Feature | Now | Evidence | Pri |
| --- | --- | --- | --- | --- |
| Format | Bold, italic, strike, code, highlight, sub and sup | done | `DOC_COMMANDS`, slash menu | - |
| Format | Headings, outline, fold, drag sections | done | Phase 4 item 3 | - |
| Format | Tables with cell menu, paste from spreadsheet | done | `DOC_TABLE_COMMANDS` | - |
| Format | Merged cells, cell colour | decided out by the Markdown model (§4) | - | - |
| Images | Insert, paste, caption, size and align by syntax | done | `![[x|300|center]]` | - |
| Images | Drag to resize or align in Live | missing | no resize code | P2 |
| Links | Links, wikilinks, backlinks with context, unlinked mentions, block refs, embeds | done | Phase 4 | - |
| Review | Comments | done | Phase 5 item 1 | - |
| Review | Suggestions (track changes) | done | `docSuggest*` (`documents-prose.js:399`) | - |
| Review | Comments and footnotes in exports | **broken** | FEAT-03 | P1 |
| Proofing | Spelling (English, UK and US), grammar (Harper), autocorrect, dictionary | done | `/vendor/wordlist/en.txt`, `harper-worker.js` | - |
| Proofing | Other languages | missing | one English word list | P2 |
| Proofing | Thesaurus, readability score | missing | 0 hits | P3 |
| Find | Find and replace, regex and case, find in every document | done | `docFind*`, `docFindInDocuments` | - |
| Counts | Words, reading time, selection words, word goal | done | `renderDocCounts` (`:13267`) | - |
| Counts | Session goal, writing streak | missing | - | P3 |
| Focus | Focus, typewriter, dim others, serif, read aloud | done | Phase 5 item 4, `docReadAloud*` | - |
| Templates | 7 templates, daily document | done | Phase 4 item 5 | - |
| History | Revisions, diff, restore, AI edit log | done | Phase 5 item 2 | - |
| History | Named versions, compare two documents | missing | - | P3 |
| Export | MD, HTML, zip bundle, PDF by print | done | Phase 7 | - |
| Export | DOCX | partial | optional extra; drops images (FEAT-18) | P2 |
| Print | Page size, margins, page numbers, header and footer, page break command | partial | `@page { margin: 2cm }` only (`09-editor.css:1083`); no `counter(page)`; "Section break" prints no break | P2 |
| Notation | Footnotes | partial | Live only (FEAT-03) | P1 |
| Notation | Math | done | own TeX-to-MathML | - |
| Notation | Code blocks, run Python, code tools | done | `documents-code.js` | - |
| Notation | Mermaid and diagrams | partial | board or map embed done; Mermaid fence as code (FEAT-08) | P2 |
| Notation | Citations and bibliography | missing | - | P3 |
| Input | Rich paste (HTML to Markdown) | missing | FEAT-04 | P1 |
| Input | Import DOCX, PDF and more as text | done | `/documents/import`, `docview.py` | - |
| Shortcuts | Palette and shortcut sheet from one table | done | Phase 4 item 4 | - |
| Phone | Phone formatting bar, sheet sidebar | done | Phase 6 | - |
| AI | AI edit with per-hunk diff, check with AI, extract notes | done | Phase 5 item 3 | - |

## 8. The object library, with "Yours" (INBOX 557c, 558)

### 8.1 What it is

- A **Library tab** in a new left board sidebar (9.2 places the sidebar; 8.6 covers placement).
- It offers three groups:
  - **Recent** (the last 12 placed).
  - **Favourites** (starred).
  - **Libraries**: built-in sets plus the person's own libraries ("Yours" by default, and any they create or import).
- A **search field** at the top searches names and tags across every set.
- Each entry is a tile with a thumbnail, a name and a star. A press opens the full name and tags; the kebab offers Rename, Edit, Duplicate, Move to library, Delete and Export.

### 8.2 What can be saved ("Yours", first class)

| # | Kind | Saved from | What is stored | Placed as |
| --- | --- | --- | --- | --- |
| 1 | Element | "Save to library…" on any selection (right-click, context bar "...", Ctrl+Shift+S on a board), or drag a selection onto the sidebar | the items with positions relative to their box, links between them (ids local to the payload), group ids remapped, frame contents, comments stripped | new rows, one undo step |
| 2 | Custom shape | "Save as a shape…" on one pen stroke or closed sketch | the path normalised to a 0..1 box, default fill and stroke, connection points (default: the 8 anchors; editable in the shape editor), a label area (default: the inscribed box) | a resizable sketch whose `data.shape` holds the path, so it scales, takes text (decision 12) and connects |
| 3 | Style | "Save this style…" on any item | `{fill, fillOpacity, color, width, dash, caps, font_size, bold, italic, align}` for its kind; connector styles carry shape (straight, elbow, curved) and caps | applied in one press to the selection, or set as "Default for new …" |
| 3b | Palette | "Save these colours as a palette" (from a selection or by hand, up to 16) | `{name, colours[]}` | becomes the row of swatches in every colour control (replaces the bare native picker as the first thing shown; "Custom…" still opens it) |
| 4 | Preset | "Save as a sticky, card, text or topic preset" | that kind's style plus default text and size | the rail's sticky and text tools offer the presets on their flyout |
| 5 | Branch | Topic menu "Save this branch to the library" | the subtree as nested `{text, style, data}` (the import model, `_parse_markdown_outline`'s shape), cross-links inside the branch | added under the selected topic through `/boards/{id}/nodes` in one transaction |
| 6 | Template | Board menu "Save as a template…" | the whole board or map: items, links, settings (type, layout, theme, background) | "New board" and "New mind map" open a gallery: Blank, the built-ins, then Yours (BACKLOG 4b answered here) |

Editing a saved item:
- **Rename, tags and move** are inline in the details popover.
- **Edit** opens a scratch board holding just that element. "Save back to the library" writes it and bumps `version`.
- **Duplicate** copies the row.
- **Delete** moves it to a library bin with Undo, matching the app's bin convention.

### 8.3 Built-in sets (drawn fresh; no draw.io stencils)

- **General:** rectangle, rounded rectangle, ellipse, triangle, diamond, parallelogram, hexagon, cylinder, cloud, callout, document, star, text, sticky (6 colours).
- **Flowchart:** process, decision, terminator, data (in/out), predefined process, manual input, document, multi-document, database, delay, off-page reference, on-page connector, preparation. Each has connection points and a label area.
- **Arrows:** block right, left, up, down, both ways, chevron, notched, U-turn.
- **UML basics:** class (3 compartments), interface, note, actor, use case, package, lifeline, activation.
- **Entity:** entity table (header plus rows, each row a connection point), weak entity, plus four ER cap pairs for connectors (one, many, zero-or-one, one-or-many).
- **Network and cloud, generic:** server, database, laptop, phone, cloud, firewall, router, user, storage, queue. Drawn as a labelled box with a Phosphor glyph.
- **Icons:** the vendored Phosphor set, 1,530 glyphs (`style.css`), searchable by name.
  - Trap: the vendor copy is a font. Placing a glyph as `<text>` will not survive SVG or PNG export.
  - Vendor Phosphor's SVG paths (MIT, licence beside them) for the icon set, or convert glyphs to paths at build time.
- **Frames:** Kanban (3 columns), retrospective (4), SWOT (2x2), timeline lane. These are templates too.

### 8.4 Linked or independent copies: recommend independent

- A placed element becomes ordinary rows that remember where they came from (`data.library_ref = {id, version}`) but do not follow later edits.
- Reasons:
  - Undo stays per board (decision 17).
  - Exports and the AI read plain items.
  - A deleted library item breaks nothing.
  - draw.io's own library behaves this way.
- Later, "Update from library" on a placed copy (shown when `version` moved) replaces it in one undo step. A live symbol system stays out until asked (C12 row, P3).

### 8.5 Storage and API

- **Tables** (alembic migration):
  - `libraries(id, name, kind ['yours'|'imported'|'custom'], sort, created_at, updated_at)`.
  - `library_items(id, library_id FK, kind ['element'|'shape'|'style'|'palette'|'preset'|'branch'|'template'], name, tags JSON, payload JSON, thumbnail TEXT (an SVG string, sanitised on write; no upload), favourite BOOL, use_count INT, last_used_at, version INT, created_at, updated_at, deleted_at)`.
  - Built-in sets are static JSON shipped in `src/memorymap/data/library/*.json`, read-only, never in the DB, so an upgrade can improve them.
- **Payload limits:** at most 500 items, 512 KB, images by `/media/` url only (the `MEDIA_URL_RE` allowlist). `media_gc._referenced_filenames` must scan `library_items.payload` (the FEAT-06 lesson).
- **Routes** (`routes_library_items.py`; note `routes_library.py` already exists for the Library tab):
  - `GET /board-library?kind=&q=&library_id=&favourites=1&recent=1` lists built-ins plus rows.
  - `POST /board-library` creates (from `{kind, name, tags, payload}`; the client builds the payload from the selection).
  - `PUT /board-library/{id}` covers rename, tags, payload and favourite.
  - `DELETE /board-library/{id}` is a soft delete with undo; `POST /board-library/{id}/restore`.
  - `POST /board-library/{id}/duplicate`.
  - `POST /whiteboard/boards/{board_id}/place` with `{item_id | builtin_key, x, y, parent_id?}` creates every row in one transaction, under one `events.writes` scope. It bumps `use_count` and `last_used_at`. The client pushes one undo batch, as `WB_RECORDED` does.
  - `GET /board-library/export?library_id=` returns `memorymap-library-1.json` (`{format: "memorymap-library", version: 1, library, items[]}`).
  - `POST /board-library/import` validates the schema and size, assigns new ids and lands the items in a new library named from the file. Media urls not in this install are dropped with a count in the response.
- **Events:** `library_item` created, edited or deleted through `@events.writes`, so the History sheet and Recent activity see them.
- **AI:** `list_library` and `place_library_item` tools (read-only plus place), so "add a decision diamond between these" works.

### 8.6 Placing, including from the keyboard

- **Pointer:** drag a tile onto the canvas (it lands under the pointer), or click it (it lands centred in view, offset 24 per repeat so repeated clicks fan out).
- **Keyboard:**
  - The sidebar list is a `listbox` with type-to-search.
  - Enter places at the centre of the view, selected, and `#wb-announcer` says "Placed Decision".
  - Shift+Enter places it connected to the selected item, to its right (draw.io's clone-and-connect).
  - Alt+arrows then nudge as usual.
- **On a map:** the Library tab shows Branches and map templates only. Enter adds the branch under the selected topic.

## 9. Controls redesign, board and map (usability, utility, accessibility, learnability)

### 9.1 How controls are reached today (board), measured from markup and `wb1.js`

| Action | Rail | Top menus | Context bar | Right-click | Key | Problem |
| --- | --- | --- | --- | --- | --- | --- |
| Z-order | - | Arrange: "Bring forward ]" | "Bring forward" | "Bring to front" | ] [ | 3 names, 1 behaviour, wrong one (FEAT-07) |
| Group or ungroup | - | not in Arrange | yes | no | Ctrl+G | missing from the menu that names arranging |
| Same width or height | - | no | yes | no | none | context bar only |
| Lock | - | no | no | yes | Ctrl+Shift+L | hidden |
| Comment | - | no | no | yes, plus mark | none | hidden |
| Shape text, link label | - | no | no | yes | Enter, double-click | no visible control |
| Export a frame | - | no | no | frame menu | none | hidden |
| Present frames | - | View | no | no | none | no key |
| Copy or paste style | - | Edit | "..." | no | Ctrl+Alt+C/V | ok |
| Duplicate | - | Edit | yes | no | Ctrl+D, Alt-drag | Alt-drag not in the help card |
| Delete | X tool | Edit | yes | yes | Del | ok |
| Find | top bar | no | no | no | (search toggle) | no replace |
| Every action by name | - | - | - | - | - | no palette (FEAT-11) |

Map (from §12.5 and `map1.js`):
- Ring (6 slots), strip (3 doors, 314x38), dock, and a topic menu of **27 rows** in 5 groups, reached by "More" or Shift+F10 because right-click opens the ring.
- No palette entries, no Outline. Layout and Tidy are in the top bar; theme, numbering and colour-by are in View.

### 9.2 One coherent model (proposed)

1. **One command table**, `WB_COMMANDS` (id, label, icon, key, kinds it applies to, group, run, enabled). Menus, the context bar's "...", the right-click menu, the palette, the shortcut sheet and the help popovers are all built from it. A lint fails a hand-built menu row that is not in the table (extends `tests/test_ui_recipes.py`). This is standing order 13 made structural.
2. **Left sidebar** (`.dock`-family panel, collapsible to a 44px rail, remembered per device), with tabs:
   - **Library** (section 8).
   - **Layers** (9.3).
   - **Outline** on a map (MINDMAP §12.2 item 8). This is the outline view: Tab and Shift+Tab re-parent, and an edit on either side shows on the other.
3. **Format panel** on the right (Ctrl+Shift+P, and "..." on the context bar), hidden by default, with tabs:
   - **Style:** fill, stroke, opacity, shadow, saved styles, palette.
   - **Text:** font, size, B/I/U, alignment, colour.
   - **Arrange:** X, Y, W, H, angle, flip, order (4 steps), align, distribute, size, group, lock, layer.
   - On a map, the three tabs are **Text**, **Shape** and **Branch line** (the strip's three doors, moved), plus **Topic**: task, note, link, picture, markers.
4. **Context bar** stays the quick bar: at most 7 controls per kind (decision 11), plus "..." that opens the Format panel.
5. **Command palette:** Ctrl+K on a board lists `WB_COMMANDS` that apply now.
6. **Shortcut sheet:** "?" on the canvas, generated from the table, grouped like the menus.
7. **Right-click** is the table filtered to the target. On a map, right-click keeps the ring (§12.5); the ring's "More" and Shift+F10 open the table-built menu.

### 9.3 Layers (INBOX 557b, tightened)

- **Phase 1:** a tree of the board in z-order (frames, then groups, then items).
  - Each row has show/hide (new `hidden` field on the three tables), lock (the existing decision 15 flag) and rename (a `name` in data).
  - A press selects and zooms; a drag restacks (writes z); Delete deletes.
  - `role="tree"` with `aria-level`, so a screen reader reaches every item without a pointer (this closes C18's row).
  - Hidden items are skipped by export, search hits and the Tab walk, and are drawn nowhere.
  - Pen strokes become ordinary rows in the order, which lifts ink's fixed place under cards.
- **Phase 2:** named layers (`layer_id` on the three tables, a `board_layers` list in board settings) with show, hide, lock and "move selection to layer" (BACKLOG 29c).

### 9.4 Learnability and empty states

- **Empty board:** one card with three choices: "Start from a template", "Open the Library (shapes)" and "Paste or drop anything". It replaces the long key list (that moves to "?").
- **Empty map:** "Type the central idea. Tab adds a child, Enter a sibling." (§12.5 already decides one line; keep it.)
- **First use of each tool:** one quiet line at the rail, once per tool per install, kept in settings rather than localStorage so the desktop window and a tab agree. For example: "Hold Shift for a straight line." "Enter adds text to a shape."
- **Locked items:** INBOX 557a's faded lock on hover.

### 9.5 Decisions this conflicts with (flag for the owner; the owner's newer words win where they conflict)

| Old decision | Conflict | Recommendation |
| --- | --- | --- |
| WHITEBOARD_PLAN decision 2: "One context bar replaces `.wb-selection-bar` and `#wb-properties-panel` … the long tail in a '...' popover" | a Format panel is a properties panel again | keep decision 2's bar; the "..." opens a docked Format panel instead of a popover. Record as decision 2 revised. |
| Decision 12: shape text has "no size, font or alignment controls" | the Format panel's Text tab | allow them in the Format panel only; the context bar keeps its seven |
| Decision 13: one label per connector, at the middle | draw.io has several, movable | keep one label, but let it slide along the line (`label_t`); several labels stay out |
| Decision 14: frames are the only pages | draw.io pages | keep frames as pages; add a "Pages" view in the sidebar listing frames (no second concept) |
| MINDMAP §12.5: three surfaces, one job each (ring, strip, dock); decision 5 "nothing added to the canvas" | the Format panel and sidebar are new surfaces | the sidebar and panel sit off-canvas; the strip's three doors move into the panel's tabs, so the topic carries the ring only. One place per action is kept. |
| `test_freemind_imports_with_its_root_as_the_maps_name` (a code decision) | FEAT-01 | reverse it |
| BACKLOG 4b question ("where the template mark lives") | section 8.5 | templates are `library_items` of kind `template`, not a mark on the board |

## 10. Five gaps per surface, as briefs, and three new ideas each

### Whiteboard: five gaps

1. **W1, object library and Yours** (Phase A below).
2. **W2, board version history.**
   - Goal: open History on a board to get a time slider over its event log, preview the board at any event, then restore the whole board or only the selection, as one undo step.
   - Files:
     - `routes_whiteboard.py`: `GET /boards/{id}/history?before=` grouping events into sessions of at most 2 minutes, and `GET /boards/{id}/at/{event_id}` replaying every item through `events.states_at`.
     - `whiteboard.js`: a read-only overlay render.
     - `note-history.js`: the entry point.
   - Tests: first, a board edited 3 times replays to each state; restore creates, deletes and updates to match.
   - Risks: compacted events (`events.is_compacted`); the item count on big boards (page by session).
3. **W3, Layers tab plus z-order.** FEAT-07 fix; 9.3 Phase 1.
4. **W4, connectors and flowchart shapes.**
   - Elbow (orthogonal) routing with several waypoints. Line jumps are optional.
   - The flowchart and General sets from 8.3 as built-in library entries, with connection points.
   - ER caps.
   - FIXED (Phase B): elbow routing with waypoints, ER caps, sliding labels, clone-and-connect. Line jumps came later (WHITEBOARD_PLAN decision 31).
   - Gate: a 12-shape flowchart drawn by keyboard, with no edge crossing a shape box.
5. **W5, interchange.**
   - Paste text (FEAT-09).
   - Mermaid flowchart in (a parser for the `graph TD/LR` subset into shapes and connectors) and out.
   - Markdown outline export of a free board (by frame, then reading order).
   - PNG 2x and transparent (FEAT-14).
   - Re-editable exports (board JSON in SVG `<metadata>`).

### Whiteboard: three ideas no competitor has

- **Board time machine with "what changed".**
  - The slider of W2, plus a plain-words summary between two points by the local model: "Added 6 stickies to Risks, moved Launch into Done".
  - It reads the event log, so it works offline and costs nothing at rest.
  - Miro's history is cloud-side and has no narrative.
- **Notebook-bound shapes.**
  - A shape or card can be bound to a note property (status, due, owner).
  - Dropping it into a frame named after a value writes that value to the note ("Kanban that edits your notebook").
  - The note's change moves the card. One field per frame (`binds: {property, value}`).
  - No whiteboard edits a notebook's structured data in place.
- **Grounded affinity sort.**
  - Select 30 stickies, then "Group by theme".
  - The local model proposes frames with names. Each sticky shows the notes in your notebook that back its placement.
  - You accept per frame, and it is one undo step.
  - FigJam's sort is cloud-only and ungrounded.

### Mind map: five gaps

1. **M1, add speed (FEAT-02).**
   - Optimistic paint, then POST.
   - A branch tidy without a full render.
   - Gate: at or under 100ms key to editable at 300 topics, and 100 keyboard topics in under 30s (`kb100.js` shape).
2. **M2, import and export reliability.**
   - FEAT-01 (FreeMind root).
   - FEAT-05 (imports in tree-right plus one tidy).
   - FEAT-15 (one undo per typed topic).
   - FEAT-16 (focus and announce).
   - Paste of an outline (FEAT-09).
   - Tests first: a single-root `.mm` round trip; a pasted 3-level list makes 4 topics under the selection.
3. **M3, Outline tab** (§12.2 item 8) in the board sidebar. FIXED 0ae92b5
   - The tree as an editable indented list, sharing `wbMapBySiblingOrder`.
   - Tab and Shift+Tab re-parent, Enter adds a sibling, edits are live both ways.
   - Gate: 50 topics edited from the outline show on the canvas within a frame.
4. **M4, markers and filter** (§12.2 item 4). FIXED 9e20ef2
   - Priority 1 to 5, progress, flag, due date (offering a reminder), tags.
   - Several markers per topic.
   - A View "Filter by marker" that dims the rest.
   - Round-trips as `_priority` and the like in OPML and FreeMind; not in Markdown, by decision 12's rule (Markdown carries only what readers draw).
5. **M5, map and document twins.** FIXED 5fb59d3 (map to document) and 885dd3b (headings to map)
   - "Write this map as a document" builds headings by depth to level 3, then lists, with topic notes as paragraphs.
   - "Map this document's headings" goes the other way.
   - Both are one-shot conversions first, with a back-link in each.

### Mind map: three ideas no competitor has

- **Recall mode from your own notes** (§12.3 item 5, made concrete).
  - Hide everything below the root. Each step asks "what's under Risks?". You type or think, then reveal.
  - Topics backed by a note use that note's text as the answer and feed the app's spaced-repetition state per topic.
  - MindNode and XMind have no recall; Anki has no maps.
- **Map ↔ document twin, kept in sync.**
  - Phase 2 of M5: a map and a document share one tree (the document's headings carry topic ids in hidden `^block` refs, already a syntax here).
  - Editing either updates the other.
  - No mind mapper keeps a live prose twin.
- **Grounded branch growth with ghost topics.**
  - "Grow" on a topic shows 3 to 5 faded child suggestions from notebook search plus the local model, each with its source note.
  - Tab accepts one, Esc dismisses them all, and nothing is written until accepted (§12.3 item 2).

### Documents: five gaps

1. **D1, footnotes everywhere (FEAT-03).**
   - Files: `markdown.js` (footnote pass), `documents.js` print path.
   - Tests: node render tests; `doccomments.js` asserts no `[^` in the print render.
2. **D2, rich paste (FEAT-04).** An allowlist HTML-to-Markdown walker in `documents.js`, wired into the CodeMirror `paste` domEventHandler beside `docTablePasteEvent`. Ctrl+Shift+V pastes plain text.
3. **D3, Mermaid and diagrams (FEAT-08).** FIXED a02d045 (flowcharts; Open as a board is W5)
   - Render a flowchart-subset fence as SVG in Read and Live (own parser, no vendor), falling back to code on anything unparsed.
   - "Open as a board" turns it into W5's board import.
4. **D4, print and page setup.** FIXED 0ae2e18 (page break) and 8f03f76 (page size, margins, page numbers; a blank print fixed)
   - Page size (A4, Letter), margins and orientation in the print dialog's pre-step.
   - Page numbers and a running title through `@page` margin boxes where supported, with a fallback note.
   - A "Page break" slash item (`<div class="md-page-break">`, `break-before: page`).
5. **D5, images in Live.** FIXED 1ac3928 (handles and align; Word pictures followed in 568ed51)
   - Resize handles and an align popover on an image widget, writing back the `|300|center` options.
   - The Word export carries pictures (FEAT-18).

### Documents: three ideas no competitor has

- **Claim check against your notebook.**
  - A writing aid that underlines sentences your own notes contradict or never support, with the note cited on hover.
  - Local RAG over the notebook (search exists), findings in the existing prose panel as a fourth kind.
  - Grammarly checks grammar; nobody checks your claims against your own sources offline.
- **Board to draft.**
  - From a board's frames and stickies, "Draft a document" makes a heading per frame and a paragraph per cluster.
  - Each section links back to its frame, and the frame shows "drafted in …".
  - Writing grows out of the whiteboard without copy and paste.
- **Revision narrative.**
  - Between any two revisions, the local model writes three lines on what changed and why it matters (cut the risks section, softened the claim in paragraph 4), over the existing diff.
  - Word and Docs show diffs, not meaning.

## 11. Phased execution briefs (one Opus agent each)

Every brief:
- Read CLAUDE.md, WHITEBOARD_PLAN §4 and MINDMAP_PLAN §12.0, §12.5 and §13 decisions first.
- Enter any new decision into the plan in the same commit.
- Commit at least every 20 minutes with the session trailers; run `scripts/gate.sh --staged` and targeted tests only.
- Update help surfaces (order 13: `data-help-for`, `ai/help_topics_more.py`, `tests/test_manual_parity.py`) in the same commit as any control.
- Build from DESIGN.md recipes (order 11).
- Own port and data dir.

### Phase 0, reliability (S, Sonnet-able except the perf item)

- Goal: FEAT-01, 05, 06, 07, 14, 15, 16, 17 and 03.
- Steps:
  1. A test per bug, written first.
  2. FreeMind root import.
  3. Imports land in tree-right and tidy.
  4. Background into `board_settings`, plus one-time migration, plus `media_gc` reads it.
  5. `wbStepZOrder` and the four labels, help updated.
  6. Export scale, transparency and name.
  7. Fold the first label into the create's undo step.
  8. Focus and announce after a commit.
  9. Hide "Order" on map topics.
  10. Footnotes in `markdown.js`.
- Acceptance:
  - `fm.js` round trip keeps Root.
  - `kb100.js` on an import shows 0 overlaps.
  - `bg1.js` orphans list empty.
  - `wb1.js` z order is `A:2.5`, or A swaps with B, in one step.
  - `doc2.js` print text has no `[^`.
- Risks: the background migration must not overwrite a board that already has settings; z-order steps must skip locked and hidden items consistently.

### Phase A, Library and sidebar (L, Opus): BUILT 5e84253 (Layers phase 1 with it)

- Goal: section 8 (all six "Yours" kinds; built-in General, Flowchart, Arrows; others in A2) and the sidebar shell with the Library tab.
- Files:
  - New `src/memorymap/api/routes_board_library.py`, an alembic migration, `src/memorymap/data/library/*.json`.
  - `whiteboard.js` (placement, save from selection).
  - New `frontend/js/whiteboard-library.js` (lazy, like the map).
  - `index.html` sidebar markup; `07-whiteboard-misc.css` tokens only.
- Tests first:
  - API CRUD, import and export schema, size limits.
  - Place is one transaction, one event scope.
  - `media_gc` counts library payloads.
  - A node test of payload normalisation (relative coordinates, link and group remap).
- Steps:
  1. Tables plus API.
  2. Sidebar shell (collapsible, keyboard listbox).
  3. Built-in sets plus search.
  4. Save selection.
  5. Place by drag, click and Enter.
  6. Styles and palettes (swatch row in colour controls).
  7. Presets.
  8. Branches.
  9. Templates in the New board and New map dialogs.
  10. Import and export.
  11. Recent and Favourites.
- Acceptance: new sweep `wblibrary.js`.
  - Save 3 linked shapes, place twice: 6 items, 4 links, 2 undo steps.
  - Export, delete, import: same.
  - Keyboard-only placement announced.
  - 0 console errors at 1440, 820 and 390.
- Risks: the Phosphor font is not exportable (vendor SVGs, with licence); payload XSS (sanitise thumbnails; text only through existing escapes); the sidebar's effect on the canvas width at 820 (measure).

### Phase B, Format panel and connectors (L, Opus): BUILT 2026-10-05 (the map's Format tabs are the map agent's)

- Goal: section 9.2 items 1, 3, 4, 5 and 6 (command table, Format panel, palette, "?") and W4 (elbow connectors with waypoints, ER caps, hover clone-and-connect, Shift+Enter connect from the library).
- Decision changes to record: decision 2 revised, decision 12 relaxed in the panel (9.5).
- Tests first: the command table drives every menu (a lint); elbow route avoids the endpoints' boxes (pure function tests); numeric X, Y, W, H round-trip.
- Acceptance: `wbformat.js` (each tab changes the selection, one undo each); `wbelbow.js`; palette lists at least 40 board commands; "?" sheet equals the table.

### Phase C, layers and pages (M, Opus): BUILT 2026-10-05 (Layers in 5e84253; Pages and the hover lock after it; named layers stay C2)

- Goal: 9.3 Phase 1 (`hidden`, tree, restack, accessible tree), then Pages view (frames listed, reorder equals presentation order).
- Named layers stay in Phase C2 only if the owner confirms (BACKLOG 29c).
- Acceptance:
  - A hidden item is absent from PNG, SVG, search and the Tab walk.
  - The drag restack writes z.
  - The screen reader names every row (axe).

### Phase D, mind map usability (L, Opus): the Outline tab's first cut (read and walk) BUILT 2026-10-05; editing in it, M1, fold-to-level and the strip's doors are the mind map agent's

- Goal: M1 (latency), M3 (Outline tab), FEAT-09 map paste, the strip's doors moved into the Format panel (9.5), saved branches from Phase A in the topic menu, fold-to-level (Alt+1 to 9).
- Gate:
  - `lat.js` at or under 100ms at 300 topics.
  - `kb100.js` under 30s with 0 errors and 0 overlaps.
  - The Outline edits both ways.
  - `mapplaces.js` still finds one place per action.
- Risks: the render-pass rework touches `renderWhiteboard` shared with boards (run `boardundo.js`, `mapperf.js` and `mapedgelag.js`).

### Phase E, interchange and history (M, Opus): W5 BUILT 2026-10-05 (Mermaid in and out, the free-board outline, the board in its SVG, XMind import); W2, the board time machine, and D3, Mermaid in documents, open

- Goal: W2 (board time machine), W5 (Mermaid in and out, free-board outline export, embedded data), D3 (Mermaid in documents), XMind `.xmind` import (content.json, read-only).

### Phase F, documents (M, Opus)

- Goal: D2 rich paste, D4 page setup and page break, D5 image handles plus DOCX images, other-language word lists (install-time optional, like the docx extra).

### Phase G, AI depth (M, Opus): FEAT-12 tools BUILT 2026-10-05 (FEAT-13 ghosts, the affinity sort and the claim check open)

- Goal:
  - FEAT-12 tools (edit, move, delete, add shape or frame, place library item).
  - FEAT-13 grow-branch ghosts.
  - The affinity sort.
  - The claim check.
- Each tool: one event, one undo entry, faked-transport tests, prompt budget (`agent.PROSE_BUDGET_CHARS`).

## 12. What I could not verify

- Real devices: no stylus, no real phone keyboard, no desktop webview. The background mismatch between the desktop window and a tab is reasoned from separate profiles (CLAUDE.md §5), not observed.
- Latency on the owner's machine. The figures are headless Chromium with no GPU, one run each (the 101 and 301 rows were six adds each). The shape (it grows with size; two renders per add) is the finding, not the absolute numbers.
- Drag-reparent and collapse by pointer were not re-driven in this pass. I relied on the existing sweeps without re-running them.
- The empty-canvas right-click on a board returned no visible menu in `wb1.js` at (1000,700). I did not check whether the press landed on the canvas, so it is not reported.
- Whether `/boards/generate` and the AI's `create_mindmap` also land in the Free layout (FEAT-05 is measured for import only).
- DOCX export behaviour: python-docx is not installed here. FEAT-18 is read from `docexport.py`.
- Mermaid, rich paste and footnotes were checked in documents. Note composers share `markdown.js`, so they are presumed affected, not measured.
- Competitor feature lists are from product knowledge; no competitor app was run in this sandbox.
