# The documents editor: a professional dev plan

**Status: written by direct instruction; to be executed after the plans in
[UI_MODERNISATION_PLAN.md](UI_MODERNISATION_PLAN.md),
the retired agent-skills plan,
[MINDMAP_PLAN.md](MINDMAP_PLAN.md), the retired plan doc and
the retired redesign doc are done, in the order
[ROADMAP.md](../ROADMAP.md) gives.** One decision (§4) has to be made before
any of it is built.

## 1. The instruction, verbatim

> Id like you re redesign and reimagine the documents editor, and Id like you
> to expand the documents editor help and suggestions, if something gets
> underlined, I want to be able to click on that and see suggestions. The
> whole documents page and editor needs a professional redesign and
> imagination because it is still reallllly annoying to use, and the ui and
> ux just isn't there, it's missing soooo many features and I need you to
> lay out a full professional dev plan for it so that it takes features from
> top editors like notion, obsidian, onenote, kortex.co etc and even beats
> them. The whole documents editor feels chucked together and then polished
> but from being chucked together and it doesn't feel professionally or
> designed for the modern day user. So many features I expect it to have
> are either downright missing or don't show themselves how they should.

The last sentence is the diagnosis to keep in view: **the gap is as much
features that exist and do not show themselves as features that are
missing.** §2 lists what exists precisely so §3 can say which of those the
plan fixes by *exposure* rather than by building again.

## 2. What exists (checked in the code, not assumed)

`frontend/js/documents.js` (~5,000 lines), the `.doc-dock` markup in
`index.html` (lines ~2200–2620) and `05-sidebars-themes.css` /
`07-whiteboard-misc.css`.

| Area | What is there | Where |
| --- | --- | --- |
| Views | Live (per-paragraph textareas rendered in place), Source (one textarea), Split, Read | `#doc-view-seg`, `docSetView` |
| Chrome | header (title, file-type select, save status, view segment, formatting toggle, AI edit, extract, ⋯ menu), a 26-control formatting strip (collapsed by default since D1), a status bar (Ln/Col, chars, words, reading time, goal, suggestions, Autocorrect and Suggestions switches), a left sidebar (Documents / Outline tabs, Recent, backlinks) | `.doc-dock-head`, `#doc-toolbar`, `#doc-statusbar`, `#doc-sidebar` |
| Structure | outline from headings, backlinks, `[[` wikilinks with autocomplete, `/` slash menu, connections dialog | `editor.js` `EDITOR_SURFACES`, `doc-outline`, `doc-backlinks` |
| Writing aids | prose checks (repeated words, long sentences, a confident spelling list) with a findings menu at the caret on double/right-click in Source and real underlines in Live (`docMarkLiveFindings`), inline completion from the document's and notebook's own vocabulary, autocorrect, a dictionary, "Check with AI", a word goal | documents.js ~3665–4700 |
| Editing | find & replace (D5), line-number gutters (7.2), indent/dedent/comment toggles, native undo kept through `execCommand('insertText')`, tables/quote/code/divider via the Insert menu (as markdown text) | `docReplaceRange`, `#doc-find-bar`, `mountGutterFor` |
| AI | AI edit (rewrite in place), selection → chat context with offset re-validation, AI review | `doc-ai`, `wrapDocSelection` |
| Files | any text/code file opens in the same editor with syntax highlighting and language detection; PDF/Office open read-only with extracted text; HTML preview pane; export text/markdown/PDF (print) | `docview.py`, `/files/{id}/html-preview` |
| History | revisions stored server-side; a history dialog | `doc-history`, `GET /documents/{id}/revisions` |
| Templates | new from template with `{{date}}`/`{{title}}` | documents.js ~594 |

**In flight as this is written:** D2 (a selection-driven floating toolbar)
and D3 (a document-local undo stack across Live and Source) on a subagent
branch: see HANDOVER.md. Both are absorbed by §5 Phase 1/2 rather than
redone.

## 3. The diagnosis

Three separate problems, and they need three separate answers. Conflating
them is how the editor ended up "chucked together and then polished".

### 3.1 The surface is a `<textarea>`, and everything the user misses follows from that

A textarea's value is a string. It cannot carry a mark, so nothing in
Source view can be underlined, which is why "click the underlined word" is
answered today with "double-click and we look up the caret offset", the
comment at documents.js ~4626 says so honestly. Live view works around it
with one textarea per paragraph, which is why the caret is lost on a mode
switch, why undo was two stacks (D3), why a selection cannot span two
paragraphs in Live, why there is no drag handle, no block selection, no
inline widget (a chip for a linked note, an embedded map, a rendered
formula), and why tables are markdown text you edit by hand.

Every mainstream editor the instruction names solved this the same way:
**a real editing surface with decorations.** Obsidian's editor is
CodeMirror 6 with the markdown rendered as decorations over the source
("live preview"); Notion is a block model over `contenteditable`; Kortex
and OneNote are contenteditable block editors. None of them edits in a
textarea. §4 is the decision about which of those this app becomes.

### 3.2 The chrome is an inventory, not a design

Measured at 1440 (`scratchpad/…/docks.js`, screenshots
`dock-documents*.png`): the header carries seven kinds of thing in one row
(identity, file type, save status, a four-way view segment, a formatting
toggle, AI edit, extract, a ⋯ menu); the formatting strip has **26
controls in two wrapping rows** even after D1 collapsed it by default; the
status bar mixes measurements (Ln 7, Col 45 · 129 chars · 22 words) with
two settings switches and an action (Set a goal). At 820px (iPad) the strip
becomes three rows and the sidebar clips its own "Recent" label and New
button. It is every control the editor has, laid end to end.

A professional editor's chrome answers three questions and nothing else:
*what am I looking at* (title, where it lives, whether it is saved), *how
am I looking at it* (the view), and *what can I do to what I have selected*
(a toolbar that appears **for a selection**, and a `/` menu for blocks).
Everything else is a menu, a palette or a setting.

### 3.3 Features that exist and do not show themselves

- The findings menu exists and is reachable only by double-click or
  right-click in Source: nothing on screen says so.
- The `/` menu, `[[` links, the connections dialog, revisions, templates,
  the word goal and the dictionary are all behind a key or a ⋯ item with no
  discoverable entry.
- Backlinks render as a list of titles with no context line, so they read
  as a lookup, not as knowledge.
- Split view and Read view are a segment button each, next to Live and
  Source, so a four-way toggle competes with the title for the eye.

## 4. The decision to make first: the editing surface

Decided and built (CodeMirror 6 under the editor). The text moved to HISTORY.md "Moved from the plans, 2026-11-04 (DOCUMENTS_PLAN sections 4 and 5, phases 0 to 2)".

## 5. The phases

Each phase ends green, measured, pushed, with a HANDOVER.md entry that
says what was not verified. Measurements use the Chromium sandbox; the
editor sweep is `scratchpad/ui-sweeps/editor.js` (from the D2/D3 branch),
extended per phase.

### Phases 0 to 2: built 2026-09-09

The bridge, the chrome and the engine. The text, with every acceptance line, moved to HISTORY.md "Moved from the plans, 2026-11-04 (DOCUMENTS_PLAN sections 4 and 5, phases 0 to 2)".

### Phase 3: blocks and structure: built, 2026-09-12

All five items. The record, with every measurement and every decision, is in
HISTORY.md ("From DOCUMENTS_PLAN.md Phase 3", items 1 to 3 and items 4 and 5);
what the phase left open is in `documents-phase4.md` (git history).

**The syntax this phase decided, kept here because later phases read it**:
`:::columns` opens a columns block, `:::column` starts the next column, `:::`
closes; an image's options are pipe-separated and read by shape, so
`![[river.jpg|300|center]]` and `![A river|300|center](/media/river.jpg)` mean
the same thing.

### Phase 4: the connected document (1 session)

Phase 4 items 1 (backlinks with context) and 2 (block references) are built, 2026-09-12 (`tests/test_doc_blockrefs.py`); decisions are in section 11. Moved to HISTORY.md, "Moved from the plans, 2026-11-09 (book5-1109: DOCUMENTS_PLAN)".
3. **Outline drag-to-reorder** (PLAN D6), breadcrumbs, sticky outline: built,
   2026-09-20. The record is in HISTORY.md ("Moved from the plans,
   2026-09-20", DOCUMENTS_PLAN.md Phase 4 item 3).
4. **Command palette and shortcut sheet from one table**: built, 2026-09-20.
   The record, including the `Ctrl+K` decision the plan left open, is in
   HISTORY.md ("Moved from the plans, 2026-09-20", DOCUMENTS_PLAN.md Phase 4
   item 4).
Phase 4 item 5 (daily notes and the templates gallery) is built, 2026-09-20; the decision is section 14. Moved to HISTORY.md, "Moved from the plans, 2026-11-09 (book5-1109: DOCUMENTS_PLAN)".

### Phase 5: review, history and AI (1 session)

1. **Comments and annotations**: built 2026-09-13. Moved to HISTORY.md
   ("Moved from the plans, 2026-09-13", DOCUMENTS_PLAN.md); listed in the
   sidebar's Outline tab rather than in a right panel, with the measurement
   that decided it.
2. **Version history UI**: built (revisions, diff, Restore, the "AI edits"
   filter). Re-run 2026-10-04, `dochistory.js` (removed 2026-10-12, recoverable from git history) all pass; see HISTORY.md
   ("Moved from the plans, 2026-10-04 (the documents phone pass)").
3. **AI edit with a diff preview, per hunk; Check with AI as findings**:
   built (the per-hunk diff; INBOX 410's in-place findings). Re-run
   2026-10-04, `docaidiff.js` (removed 2026-10-12, recoverable from git history) all pass; same HISTORY entry.
4. **Focus and typewriter modes, reading typography, a print stylesheet**:
   built. The record is in HISTORY.md ("Moved from the plans, 2026-09-20",
   DOCUMENTS_PLAN.md Phase 5 item 4).

### Phase 6: responsive by device: done

Every item built or decided (the bands, the phone formatting bar, the keyboard inset fix, the outline sheet decided against, the 820 to 1100 rail a recorded no-op). Moved to HISTORY.md, "Moved from the plans, 2026-10-11 (DOCUMENTS Phase 6 and Phase 8, docs-1011)".

### Phase 8: one editor everywhere (1 session, the owner's ask, 2026-09-09)

The owner: "plan for the note capture and editors in the notes tab, making
a new note from the graph, and anywhere there is a note related capture,
edit or view area with a text box to integrate features similar to the
documents upgrade. The editors need to be consistent in form and
function." Today the app has nineteen textareas in the page and seventeen
more made in script, and five of them are note editors with five
different feature sets: the capture box (`#entry-content`: formatting
strip, `[[` autocomplete, attachments, dictate, improve), the inline note
edit (`app.js` ~3988 and ~15256: a bare textarea), the graph's note popup
and new-note box (`#graph-popup-content`, `#graph-new-content`: bare), the
Write with the AI panes (`#draft-thoughts`, `#draft-text`: bare, the draft
in monospace) and the document (`#doc-content`: the engine after Phase 2).

**Decisions (made here, not remade).**
- One factory, `noteSurface(host, options)`, built on Phase 2's
  `docSurface()` adapter and the same CodeMirror bundle, replaces every
  note editor. Options: `size` (`inline` for a card, `box` for capture
  and popups, `page` for the document), `live` (decorations on or off),
  `strip` (the formatting strip, opt-in as in Phase 1), `findings`,
  `attachments`. The textarea stays as the fallback and as the form value
  carrier (the surface mirrors into it on change), so every existing
  save path, test and handler keeps working unchanged.
- The same features in every surface: Live decorations, `[[` note
  autocomplete, the `/` menu, the selection toolbar (bold, italic, code,
  link, list, ask the AI), undo history, Ctrl+S, `==highlight==`, task
  boxes, paste of images and files into the attachments row where the
  surface has one. What differs is size and chrome, never behaviour.
- One recipe in `09-editor.css`: `.note-surface` with the three size
  variants, the tokens' radius, `--control-h` for the strip, the same
  focus ring; a lint (`tests/test_note_surface.py`) that every note
  textarea in the page carries `data-note-surface` and is mounted through
  the factory (grep the ids), and that no new `<textarea>` for note text
  appears without it.
- The engine loads on the first focus of any surface, once per page.
- The chat composer is not a note editor: it gets `[[` and `/` only, and
  keeps its own recipe (send on Enter).

All of 8a, 8b and 8c is built (capture, the inline edit, the graph's popups, Write with the AI, the skill steps box, the board's note card). Moved to HISTORY.md, "Moved from the plans, 2026-10-11 (DOCUMENTS Phase 6 and Phase 8, docs-1011)".

### Phase 7: export and interchange: **built 2026-09-13**

Moved to HISTORY.md ("Moved from the plans, 2026-11-02 (a28w: DOCUMENTS Phase 7 record)") on 2026-11-02: a plan holds open work only.

## 6. Competitor matrix (what the plan takes from whom)

| Feature | Notion | Obsidian | OneNote | Kortex | Here today | Plan |
| --- | --- | --- | --- | --- | --- | --- |
| `/` block menu | ✓ | ✓ (plugin) | – | ✓ | ✓ (hidden) | P1 exposes, P3 extends |
| Live preview over markdown | – | ✓ | – | – | partial | P2 |
| Selection toolbar | ✓ | – | ✓ | ✓ | D2 in flight | P1 |
| Click a squiggle → suggestions | ✓ (browser) | ✓ (browser) | ✓ | ✓ | Live only | **P0** |
| Tables editor | ✓ | ✓ | ✓ | ✓ | markdown text | P3 |
| Callouts / toggles | ✓ | ✓ | – | ✓ | partial | P3 |
| Math | ✓ | ✓ | ✓ | – | – | P3 |
| Embeds of other objects | ✓ | ✓ | – | ✓ | – | P3 |
| Properties / frontmatter | ✓ | ✓ | – | ✓ | – | P3 |
| Backlinks with context | – | ✓ | – | ✓ | titles only | P4 |
| Block references | ✓ | ✓ | – | – | – | P4 |
| Command palette | ✓ | ✓ | – | ✓ | – | P4 |
| Daily notes / templates | ✓ | ✓ | – | ✓ | templates | P4 |
| Comments | ✓ | – | – | ✓ | – | P5 |
| Version history with diff | ✓ | ✓ (sync) | ✓ | – | list only | P5 |
| AI edit with diff | ✓ | – | ✓ | ✓ | replace in place | P5 |
| Focus / typewriter | – | ✓ | – | ✓ | – | P5 |
| Works with the plug pulled | – | ✓ | partial | – | ✓ | kept |
| The AI reads *your* notes, locally | – | – | – | – | ✓ | kept, the thing that beats them |

## 7. Files this will touch

`frontend/js/documents.js` (split into `documents/{surface,chrome,findings,
blocks,connections}.js`, served as-is, `test_frontend_load_order.py`
enforces order), `frontend/js/editor.js` (the adapter), `frontend/vendor/
codemirror/`, `index.html` (`.doc-dock`), `05-sidebars-themes.css`,
`07-whiteboard-misc.css`, `src/tessellate/api/routes_documents.py`
(properties, comments, block ids), `core/docview.py` (export), tests
under `tests/test_documents_*.py`, `scratchpad/ui-sweeps/editor.js`.

## 8. Acceptance for the whole plan

- The instruction's sentence, literally: an underlined word is clickable
  and shows suggestions, in every view, measured in Chromium.
- Header ≤ 5 controls; chrome above the first line ≤ 96px at 1280; one
  control height in every dock row; 0 `errors.js` findings at 390/820/1024.
- Every row of §6's "Plan" column has a test or a sweep assertion.
- `python -m pytest tests/` green; `ruff`; `node --check` on every file.
- HANDOVER.md says what was not verified, a real vision model, a real
  on-screen keyboard and a real iPad are three things the sandbox cannot
  supply.

## 9. Risks

- **CM6 under the CSP.** Verify first (§4). If it cannot inject its
  stylesheet, ship its CSS as a static file and set `EditorView.styleModule`
  off.
- **The note composer diverging.** The adapter (`docSurface`) is what
  keeps the capture box, the note edit form and the documents editor on
  one implementation; a phase that adds a feature to one and not the
  others has failed the learnability rule in UI_MODERNISATION_PLAN Phase 8.
- **Two undo stacks again.** D3's stack and CM6's history must not both
  be live; Phase 2 retires D3's the day CM6 lands.
- **Prompt budget.** Properties and comments reach the AI as context;
  `agent.PROSE_BUDGET_CHARS` is asserted and stays that way.

---

## 21. The code editor against VS Code, and writing checks everywhere (INBOX 646)

Built (found by audit 2026-11-14), moved to HISTORY.md ("Moved from the plans, 2026-11-14 (documents-plan audit: found built)"). PHP stays out (its size, section 9 decision).

## Built, Phases 0 to 2 (the chrome, the engine, the editor), 2026-09-09
Moved to HISTORY.md ("Moved from the plans, 2026-09-09", DOCUMENTS_PLAN.md): a plan holds open work only.

## Built, Phase 3 (tables, blocks, embeds, properties, columns), 2026-09-12

Moved to HISTORY.md ("From DOCUMENTS_PLAN.md Phase 3", two entries) on
2026-09-12: a plan holds open work only. What the phase left behind is in
`documents-phase4.md` (git history).

## Placed from INBOX, 2026-11-10 (selection to a note)

- Group selection row (screenshot of a flowchart with "Customer" and "Warehouse" groups): built 2026-11-10 (dgroup-1110). Moved to HISTORY.md "Moved from the plans, 2026-11-10 (dgroup-1110: group selection)".
- Owner, 2026-11-10, diagram builder ("have you integrated the ai into the diagram builder yet??"): built 2026-11-10 (dgai-1110). Moved to HISTORY.md "Moved from the plans, 2026-11-10 (dgai-1110: the AI in the diagram builder)".
- Diagram AI left: built (Ask and Suggestions for every kind), see HISTORY.md, "Moved from the plans, 2026-11-14 (documents-plan audit: found built)". Real-model output stays unverified (LEDGER L893).
- INBOX 1731 (spelling second opinion): built 2026-11-10 (spell-1110), (a) to (e). Moved to HISTORY.md "Moved from the plans, 2026-11-10 (spell-1110: the spelling second opinion)". (f) LanguageTool as an optional download: built 2026-11-10 (lag1726-1110), CHANGELOG line; the real program is unverified.
- INBOX 1728 (selection to a note): built 2026-11-12 (notesel-1112). Moved to HISTORY.md "Moved from the plans, 2026-11-12 (documents-plan: selection to a note, INBOX 1728)".

## Placed from INBOX, 2026-11-02 (the owner: the calculator, equations, insert panels and a diagram builder)

Each row is the owner's words and the recommendation taken; built rows move to HISTORY.md.

Built and moved: 1542 to 1545 (insert panels: first-frame place, the minimise pill, every door, icon shortcodes in documents), HISTORY.md "Moved from the plans, 2026-11-02 (insert panels, INBOX 1542 to 1545)".

1621. Built (section 22 rows R1 to R10 and the 1546 phases P1 to P5, audit 2026-11-14); the owner's words and the recommendation taken moved to HISTORY.md, "Moved from the plans, 2026-11-14 (documents-plan audit: owner rows found built)".

1566. **Owner, 2026-11-03, verbatim (screenshots: the Calculator and equations panel, Equation tab):** "I want you to redesign this quick jump scroll menu, also it doesnt have a horizontal scrollbar" (the row of boxed group buttons, Fraction to Bracket) and "can you also redesign that pill selector?? it looks awkward, the whole equations panel needs a slight better modern and professional redesign" (the Inline / Display segmented well under the Sum, Units, Equation tabs). Step 1 (this commit): the jump row is a `.tabs-line.edge-fade` strip with a thin scrollbar and wheel-to-sideways scroll, not measured in a browser yet. Rest, for an agent with the recipes: the Inline / Display choice as the `.seg` recipe at the dock height (or one row with the lede, Pin and LaTeX), the lede and its two boxed buttons as one quiet toolbar row, the tile grid's tiles quieter (inset fill, no ink edge, glyphs centred and larger), group heads on the type scale, the foot ("Insert writes into the note once there is an equation." plus Copy and Insert) as the dialog foot recipe with the one filled button last, spacing on tokens; measured at the panel's default and narrowest sizes, light and dark. Then, verbatim: "also I dont like excessive use of these glowy grey styled buttons, they feel vibe coded, its alright ot still use them but just not excessively yk?? use them intentionally and in a modern and professional way. also with that toggle pill for inline/display, small toggles like that where they ar eon their own line and the only thing on their line and they are just there on the right, it just feels liek the pill has been chuckedc there with no thought, like at least make it extend the full width or redesign it some other way" (screenshots: the calculator keypad, twenty bordered grey keys; the equation tiles; Pin and LaTeX boxed). Class: a bordered grey ghost button used for every control in a grid or row; and a lone `.seg` on its own line. Recommendation: a DESIGN rule and lint: a grid of keys or tiles takes the quiet inset fill with no edge (operators tinted, `=` the one filled key), a toolbar's secondary actions are icon or text buttons without an edge, the bordered ghost stays for a lone secondary action beside a filled one; a `.seg` alone on its line spans the row (equal segments) or joins the row of the control it governs. Sweep every surface for both, after the equations panel. **Panel built 6c08378** (the sweep of the other surfaces remains, `a30n-1103.md` (git history)): seg 492 of a 492px row (320px: 284 of 284), keys and tiles border 0, keypad glyphs 18.4px, group heads 12px/600 on the eyebrow, jump row scrollWidth 1311 over 492 with a thin bar, foot right edge at the row's, no horizontal overflow at 1440 and 320, light and dark; the Radical tiles' x cleared the sign by 0 and 0.5px before, 1.5px after (an ink-component count on a 4x capture), no tile has ink at its edge. **Sweep a30q (6894c02, 56c97cb, c7d9119, c911fec, 246ee43):** bordered ghosts 80 to 15 across the tabs and Settings, 23 to 9 across the deeper states (1440, light); every lone seg spans its row (prompt 438 of 438, Forgot password 418 of 418, 300 of 300 and 336.8 of 336.8 narrow); radicand gap 0 to 0.5px before, at least 2.5px after in Live, Read and the tiles. Left in `a30q-1103.md` (git history) (Reminders filter chips, icon pickers and add-widget tiles, dark, 390 and high contrast unmeasured), so the item stays open.

1615. Built (section 22 rows R1 to R10 and the 1546 phases P1 to P5, audit 2026-11-14); the owner's words and the recommendation taken moved to HISTORY.md, "Moved from the plans, 2026-11-14 (documents-plan audit: owner rows found built)".

1614. Built (section 22 rows R1 to R10 and the 1546 phases P1 to P5, audit 2026-11-14); the owner's words and the recommendation taken moved to HISTORY.md, "Moved from the plans, 2026-11-14 (documents-plan audit: owner rows found built)".

1546. Built (section 22 rows R1 to R10 and the 1546 phases P1 to P5, audit 2026-11-14); the owner's words and the recommendation taken moved to HISTORY.md, "Moved from the plans, 2026-11-14 (documents-plan audit: owner rows found built)".

**1546 design** (a28w, the judge rung, 2026-11-02, read from the code at f63881c). Every decision is taken (standing order 3); a build row cites it as "1546 D<n>". Nothing here was run: it is design, measured only where a row says so.

- **What exists.** Drawing: `mermaidRequest` (mermaid-draw.js:352) posts a source to the hidden frame (`/mermaid-frame`, api/app.py:1532; its own policy `MERMAID_FRAME_CSP`, core/security.py:547; `securityLevel: "strict"`, `htmlLabels: false`, mermaid-frame.js:82) and gets SVG text back, shown as a blob `<img>` (`mermaidShow`, :391); Mermaid 12.2.0 is vendored. Readers: `mermaidFlowParse` and `mermaidFlowLayout` (documents-mermaid.js:100, :151; six bracket shapes, six link kinds, 120 nodes at most; no caller in the app, only tests/test_doc_mermaid.py and tests/test_code_documents.py:828) and the board's `wbMermaidParse` (whiteboard-interchange.js:110, subgraphs as frames; one caller, :906) beside its state, class and sequence readers (:392, :457, :517) and its writer `wbBoardToMermaid` (:42). The board object: kind `diagram`, `data.mermaid` (api/wb_model.py:242, 20,000 characters), edited in a textarea dialog (`wbOpenDiagramDialog`, whiteboard-interchange.js:1456; a 300 ms preview, :1525; Turn into shapes, :1508). Documents: the Live figure (`DocMermaidWidget`, documents-mermaid.js:343) moves the caret into the fence on a press (:374); the "/" row Flowchart (editor.js:940). Composer: `composer_mermaid.drafted` (composer_mermaid.py:367) draws a flowchart, a timeline or a mind map by rule from steps, a checklist, dated lines or a heading with bullets, 16 boxes at most; with a model, the `DIAGRAM` prompt (ai/drafter.py:140); both behind `POST /drafts/compose` with `kind: "diagram"` (routes_drafts.py:78, `drafter.composed` at :94).
- **D1 The model.** One model per kind, plain data, no coordinates. Flowchart: `{kind, dir, nodes: [{id, text, shape, group}], edges: [{from, to, label, style, arrow}], subgraphs: [{id, title, parent}], kept: [{at, line}]}`, the board reader's own shape (so `wbMermaidLayout`, :209, and the board import take it unchanged) with the document reader's shapes and link kinds. The arrays keep the order written, and that order is what Reorder changes (Mermaid lays out in declaration order). No x and y because Mermaid source has none: a position set by hand would be lost on the first round trip. Free placement is the board's, one press away (Turn into shapes).
- **D2 Two-way sync.** `parse(source)` and `print(model)`. Every block gesture is one model change printed to the whole source (canonical: the header, subgraphs with their nodes, nodes, edges, then the `kept` lines verbatim), so the source is the only state and undo is the history of sources (an `.mmd` document's own CodeMirror history; a list of sources in the dialog). A source edit re-parses after 300 ms (the board dialog's debounce) and keeps the selection by node id. A line the reader cannot place (v11 `@{ }` shapes, markdown-string labels, `%%` comments, `style`, `classDef`, `click`) is a `kept` line drawn as a locked text block where it stood: nothing is ever dropped. Labels are quoted with the composer's escapes (composer_mermaid.py:16 to 19), so a typed quote or bar cannot end one. Invariants, tested per kind: `print(parse(print(m))) === print(m)`, and `parse(s)` and `parse(print(parse(s)))` hold the same nodes, edges and groups for every fence in the corpus.
- **D3 Flowchart first.** Two readers and the composer already speak it, it is the "/" Flowchart row, and its three structures (node, edge, subgraph) are the three gestures (place, join, nest). Phase 4: mind map and timeline (the composer writes both, :248 and :264; nesting is indentation), then sequence (the board reads it, :517; messages are an ordered list). State and class only when asked (the board's UML set covers them); pie, gantt, journey, ER and C4 open in Source with one line saying blocks do not draw that kind.
- **D4 One reader.** The model replaces `mermaidFlowParse` and `mermaidFlowLayout` (dead in the app) and the board's `wbMermaidParse` and `wbMermaidText` (:33): one flowchart grammar, not three. tests/test_wb_interchange.py (seven calls) changes its call, not its assertions; the board's one reader of `dashed` reads `style === "dotted"`.
- **D5 Its own kind is a document.** A diagram is a document with `file_type: "mmd"` (one `FileType` row in core/filetypes.py's table, :71, group "Documents", glyph `flow-arrow`, `line_comment="%%"`): history, versions, search, links, the bin, autosave and export come with it and nothing migrates. The Library's New type menu lists it with no new control (`docTypeMenu`, library.js:3447). The server tells it apart as it does boards (`_documents`, routes_library.py:236, `kind: "diagram"`; a Diagrams chip in `LIBRARY_KINDS`, library.js:362, after Mind maps). Views: Blocks (the builder where `#doc-preview` is), Split (source beside the builder: the optional third view) and Source; `setDocView` (documents.js:875) treats `mmd` as previewable with the builder as its preview, and the prose passes (spelling, outline, writing checks) skip it as they skip code.
- **D6 Embedded: one component, two mounts.** `openDiagramBuilder({source, kind, onDone})` mounts the same builder in a dialog with the dialog head, so `panelMovable` moves and sizes it. The Live figure gets an Edit as blocks icon button (documents-mermaid.js:360; `onDone` replaces the fence's range). The board's diagram object opens it on a double-click (`wbBuildDiagram`, whiteboard-interchange.js:1408) and the textarea dialog goes (replace, not layer; Turn into shapes moves to the builder's menu). A reply's fence in Chat or Ask gets Open as a diagram (it makes an `.mmd` document). A note links to one with `[[` (editor.js:948 already picks documents) and `![[diagram]]` draws its picture through `mermaidDrawIn`. Pictures inside nodes are refused: the frame takes only `data:` images and a source is capped at 20,000 characters (mermaid-frame.js:16).
- **D7 Export.** SVG is the frame's text through `saveFile` (skills.js:975). PNG draws that SVG on a canvas at 2x inside the builder's closure: Mermaid's SVG holds no outside pictures, so the board's `wbRasterizeSvg` (whiteboard.js:13877, which inlines board pictures) and its bundle are not pulled in. Copy as Mermaid and Copy as SVG sit beside them in the builder's `kebabMenu` (sheets-selects.js:1363).
- **D8 Suggestions land as blocks.** Templates are Mermaid sources in `frontend/board-library/diagram-templates.json`, fetched on first open with `lazyAssetStamp` as the board library fetches its sets (whiteboard-library.js:182), picked in the dialog-of-choices recipe (`.doc-template-choice`) with each preview drawn by `mermaidRequest`. From my notes and Describe it call `POST /drafts/compose` (`kind: "diagram"`; the notes as `source_ids`; a document's text as `draft`, which takes 20,000 characters where `thoughts` takes 8,000, routes_drafts.py:36 to 38): no new route. The fence that comes back is parsed by the model: on an empty diagram it becomes the diagram; otherwise its blocks arrive as ghosts (the Ghost topics recipe, `wbMapBranchPicker`, whiteboard-map.js:10874: Tab takes, Enter adds, Escape drops), ids renumbered past the diagram's own, one undo step, with the composer's or the model's one line (`said`). A fence the frame refuses shows its one-line reason and opens Source; nothing a model wrote is inserted as markup (text nodes only).
- **D9 The block pane is a tree, not a canvas.** `role="tree"` on the Layers recipe (`#wb-layers-tree`): a node is a `treeitem` card (shape glyph, label, its joins as chips "-> Check, yes" under it); a subgraph is a card whose children are its nodes. Joins are not drawn as lines in the pane (the picture beside it draws them), so the board's elbow router (`wbElbowRoute`, whiteboard.js:4702) is not reused, and the pane stays readable at 120 nodes where crossing lines would not.
- **Interaction, flowchart (P4 gives each kind its palette).** Palette: the six shapes, a group, and the six link kinds as the join chip's menu, in one `.dock` row over the pane (`data-dock-name="diagram"`, the sketch pad's one-row dock); the direction (TD, LR, BT, RL) a `.seg`. Drag: obj-drag.js's one gesture (a 250 ms still hold, a 350 ms finger hold, at once from `[data-obj-grip]`) with a new mode `OBJ_MODES.diagram`, grabbing only `.dgm-block` and registered ahead of `carry` (obj-carry.js:117, whose grab takes every card). A palette tile dropped places a block; a block dropped between blocks reorders (obj-reorder.js's `.obj-gap`), on a group nests, on another block's join well joins; drag-edge.js scrolls the pane at its edges. Relabel in place: a double-click or Enter makes the label `contenteditable="plaintext-only"` (the `wbBeginTextEdit` pattern), Enter commits, Escape reverts. A press on a drawn node in the picture selects its block, from boxes read off the SVG text with `DOMParser` (never inserted, so no policy moves) by Mermaid's `flowchart-<id>-<n>` ids.
- **Keyboard only.** Arrows walk the tree; Enter relabels; Insert or N adds a block after, of the last shape used; Alt+Up and Alt+Down reorder (obj-reorder.js's keys); Alt+Right nests into the group above, Alt+Left lifts out; J joins through a rich-picker.js list of the other blocks, typed to filter; Delete removes (its joins with it, said in the announcement); Shift+F10 opens the block's `kebabMenu` (shape, link kind, label, delete); Ctrl+Z and Ctrl+Shift+Z step the source history. Every change is said in one polite live region ("Joined Start to Check").
- **Touch.** The finger hold lifts a block; a hold that does not move is the block's menu (`wireLongPress`, navigation.js:24); below 600 the palette is a sheet (the canvas-on-a-phone recipe), the picture sits above the blocks, and two fingers pan and zoom the picture.
- **D10 Budgets.** Boot bytes: none. The model lives in documents-mermaid.js's closure (already in the lazy Library bundle, app.js:1654) and exports one name, `diagramModel`. The builder is a new bundle, `diagramBuilder: ["/css/diagram-lazy.css", "/js/diagram-builder.js"]`, registered by `Object.assign(LAZY_MODULES, ...)` at that file's foot, not in app.js (APP_JS_CAP 14,300) or the boot file lazy-entries.js (TOTAL_CAP 260,350, tests/test_static_compression.py:127); every caller is in the Library bundle or opens a document first, so there is no stand-in. Global names: `diagramModel` and `openDiagramBuilder` in, `wbMermaidParse` and `wbMermaidText` out, net 0 against 9,714 (tests/test_global_scope_ratchet.py:62); diagram-builder.js is one closure, under 12 KB gzipped (PIECE_CAP 32,000). CSP: nothing changes. The page shows only blob `<img>`s (as `mermaidShow` does) and builder DOM made with `createElement` and `textContent`, sized by `el.style` or classes; the frame keeps `default-src 'none'` with `data:` images only; the builder never loads Mermaid itself (tests/test_mermaid_frame.py:42).
- **1546 P1, the model and two-way sync (flowchart).** Built 2026-11-02 (a30a-1102). Moved to HISTORY.md "Moved from the plans, 2026-11-02 (a30a-1102: 1546 P1, the diagram model)".
- **1546 P2, the block pane.** Built 2026-11-03 (a30l-1103, 7122184 and f89ae3e). Moved to HISTORY.md "Moved from the plans, 2026-11-03 (a30l-1103: 1546 P2, the block pane)". The touch pan and zoom and the phone palette sheet closed in a30y-1103 (HISTORY.md, same heading as P5).
- **1546 P3, templates and from my notes.** Built 2026-11-03 (a30o-1103). Moved to HISTORY.md "Moved from the plans, 2026-11-03 (a30o-1103: 1546 P3, templates and from my notes)". Left, both closed by P4: mind maps and timelines landing as source plus picture, and a non-flowchart suggestion that could not merge into a non-blank diagram (`a30o-1103.md` (git history)).
- **1546 P4, the other kinds.** Built 2026-11-03 (a30u-1103). Moved to HISTORY.md "Moved from the plans, 2026-11-03 (a30u-1103: 1546 P4, the other kinds)". The 12 KB size target is met (11,995 bytes gzipped).
- **1546 P5, everywhere Mermaid draws.** Built 2026-11-03 (a30y-1103). Moved to HISTORY.md "Moved from the plans, 2026-11-03 (a30y-1103: 1546 P5, the P2 leftovers and D3)". Left: the dock is two rows at 390, not one (`a30y-1103.md` (git history)).
- **Risks.** (1) A small edit can reshuffle Mermaid's layout (it reads declaration order); the pane is the stable view, and no row measures the picture's positions. (2) The picture's hit boxes depend on Mermaid's internal ids: pinned by a test on the vendored 12.2.0, and dropped quietly (no select from the picture) when absent. (3) Canonical printing rewrites hand spacing and trailing `%%` comments the first time a block changes; said once ("Tidied the source"). (4) A model's fence can be long or wrong: the 20,000-character cap and the frame's one-line reason bound it. (5) `mmd` as previewable touches every `previewable` check (documents.js:195 to 231); P1 lists each and gives `mmd` its answer. (6) The model grows documents-mermaid.js; if a size lint objects, the model moves to its own file in the Library bundle and wins back its app.js bytes in that commit. **Not verified:** Mermaid 12.2.0's node ids and reading a transform through `DOMParser` are from the library's conventions, not measured.

DX24t. Built 2026-11-03 (a30h-1102, 65c01c4, e3aae86): see HISTORY.md, "Moved from the plans, 2026-11-03 (comment threads DX24t, find in all D33)".

## Placed from INBOX: 107d, the segmented mini bars

INBOX 1482 (the file type picker) is built and moved to HISTORY.md ("Moved from the plans, 2026-10-31 (file type picker 1482)") on 2026-10-31: a plan holds open work only.

The segmented mini bars (107d) are done, 2026-09-12; the rule is in `docs/DESIGN.md` ("A choice control's selected segment is `--accent-surface` behind `--on-accent`"). Moved to HISTORY.md, "Moved from the plans, 2026-11-09 (book5-1109: DOCUMENTS_PLAN)".

## Placed from INBOX, 2026-09-09 (the owner's evening batch)

Verbatim, with the reading each one gets.

**All five were worked on 2026-09-09 and all five are done.** The built
record, with every measurement, is in HISTORY.md, "Built, the owner's
evening batch (DOCUMENTS_PLAN's INBOX items), 2026-09-09". What is left of
each below is the owner's sentence, the one-line answer, and anything the
work found and did *not* fix, which is the part that is still open.

- "the documents edit and read toggle options dont fit in the toggle and go
  out of it at the bottom". Done: the pills fit inside their segment at 1440
  and 1280. The cause was not the `padding-block: 0` this entry used to
  guess at; see HISTORY.
- "md formatting should go invisible unless i click back on that word or
  section or navigate with backspace, delete or arrow keys etc to where
  those formatting markers are." Done: the cursor-in-range test was already
  built and works; `---` and a callout's `[!kind]` were the two markers it
  had never been run on, and both hide now.
  **The caret jump is fixed, and the fix is a decision** (recorded here so it
  is not remade). Revealing a marker used to shift the caret 28.4px to the
  *right* on a leftward keystroke, because the reveal put four characters
  immediately to its left: measured with `coordsAtPos` walking left through
  `A **bold** word here.` as x 560.3, 554, 544.2, 531.1, then 559.5.
  `EditorView.atomicRanges` is the usual answer and is the wrong one here, as
  it would step *over* the marker rather than into it and entering it is what
  this sentence asks for. **A marker now reveals when the caret is on its
  line, not when it is inside its range** (`rangeRevealed` in
  `docLivePlugin`). Phase 2 item 3 said "when the caret enters the range";
  this supersedes that phrase and nothing else about it. The reasons: the line
  is what holds still, so horizontal movement inside one causes no reflow at
  all and the caret walk is now strictly monotonic (measured, fourteen steps,
  642.2 down to 529.4 with no reversal); the one reflow left happens when the
  caret *arrives* on a line, which is a click or a vertical move and both
  relocate the caret anyway; and `HeaderMark`, `QuoteMark` and `TaskMarker`
  already worked this way, so the eight constructs now agree instead of
  splitting into two behaviours. `scratchpad/ui-sweeps/cm-reveal.js` asserts
  the monotonic walk, so the jump cannot come back unnoticed.
- "I want to be able to use the documents tab as a plain text editor like
  before as a view option (not the default though)", "and also if I select
  a txt document, and/or other code file document, and these can have line
  numbers as well", "for code files, include code syntax and make it a
  proper code editor like vs code." Done: the edit menu is Live (default),
  Source, Split, Plain, with Line numbers as a row under them.
  **The missing modes are settled, with the numbers** (a decision, not an
  oversight; measured 2026-09-09 by building the bundle four ways).
  Baseline 787,401 raw / 269,374 gzipped.
  - **`swift`, `r` and `ini` added.** Together +7,658 raw and **+2,476
    gzipped**, under 1%. All three are ordinary legacy stream modes. `ini` is
    CodeMirror's `properties` mode, which is what that format is called there;
    it marks sections bold, keys at 600 and comments muted italic, and leaves
    values plain, which is the whole of an INI file's syntax.
    (An earlier note here said "`r` has no CodeMirror mode at all". That was
    wrong: `@codemirror/legacy-modes/mode/r` exists. It was written from
    memory rather than from the package, which is the same failure as the two
    entries above it.)
  - **`php` built as a lazy file**, not refused: see L-documents-63 in HISTORY (`php.min.js`, 28,381 gzipped, fetched on the first .php open).
  - **`csv` refused, permanently.** There is no CSV mode in CodeMirror and
    there should not be: a CSV has no syntax, so a highlighter would colour
    its commas and nothing else. What a CSV wants is a table view, which is a
    different feature.
  `scratchpad/ui-sweeps/docviews.js` asserts all five, including that `csv`
  highlights *nothing* and `php` highlights after its lazy file loads, so adding a mode later has to come with an
  update to this decision rather than silently.
- "i still cant click on a grammar or misspeled underlined word and see a
  popup like in a realworld editor like obsidian, word, notion, vs code."
  **It already worked**, and this entry's previous claim that "the click
  target and its popover never landed" was a reading of the source without a
  browser. `scratchpad/ui-sweeps/docsuggest.js` is now the standing check.
  **What would still read as "cant click":** Read view has no editing
  surface and so no marks, and a code file suppresses findings entirely. If
  the report comes back, ask which view it was in before touching the code.
- "redesign and refine the outlines section of the documents tab as well"
  (two screenshots). Done: all five problems in them.
  The empty column above References is fixed: both sections carried
  `flex: 1 1 auto`, so with a two-heading document the outline was 312.4px of
  box around 68.3px of content and References 296.5px around 46px, leaving
  243.1px of nothing between them. `flex: 0 1 auto` on both; now 85.3px around
  68.3px and 69.4px around 46px, and `docoutline.js` fails on any section more
  than 40px taller than what is in it. Found while measuring that: `.linklike`
  cancels the filled button's background and border and never cancelled its
  `box-shadow`, so all fifteen text links in the app drew an accent halo
  behind their words.
- "the whole documents sidebar and ui needs fixing and the document editor
  still needs a lot of refinement and cleaning but its still in development
  so just make sure you cover it all."
Reopened 2026-11-14 by the hub (no owner decision behind it): LEDGER L-documents-63 (PHP mode, lazy).

## 10. The spelling check: decided 2026-09-12

**The problem, stated once.** The spelling rule looked each word up in
`DOC_AUTOCORRECT`, a hand-written table of 42 typos, and treated every word
absent from it as correctly spelled. "tets" was never flagged and neither
was anything else a person mistypes. The owner's two reports are that one
cause seen twice: "spelling errors and grammar arent picked up all the
time", and "no edit suggestions popup panel appears when I click on
underlined words", the second because the underline being clicked was the
browser's native squiggle (the editor set `spellcheck="true"`), which the
app cannot see and has no finding under.

**Decision: ship a real word list (option a), not an honest retreat
(option b).** The panel, the popup, the ranked suggestions, the dictionary
and the ignore list were all already built and all of them were starved of
the one thing that makes them worth opening. Retreating to "we only check
grammar and style" would have left the owner with a checker that still
cannot answer a click on a misspelling, because the browser's squiggle is
not ours to open a menu on. The list is the cheaper half of the work and it
is the half that makes the other half true.

**What was chosen, and the numbers.**
- The English Speller Database (SCOWL's successor), tier 60, US and UK
  spellings both, plus its "hacker" special list. `frontend/vendor/wordlist/`
  with its `LICENSE` and a `build.sh` that records the exact parameters.
- Licence: permissive, notice-retention only. It asks that the copyright
  notice travel with any list built from it, which `LICENSE` does. Safe
  under this project's AGPL-3.0 (the retired analysis doc's licence constraint).
- 92,972 words. 871,173 bytes raw, 252,926 over the wire under this app's
  own gzip, one fetch, lazily on the first prose pass, never on first paint.
- `DOC_EXTRA_WORDS` in documents.js carries 75 words the app is written in
  that a general list does not have yet (json, backend, webhook). It is in
  the app rather than appended to the vendored file so that file stays
  exactly what its build script produces.

**The rules that keep it from crying wolf**, each one measured rather than
assumed: code fences, inline code, addresses, markdown link destinations,
reference definitions, html tags, `[[note links]]` and frontmatter are
masked out of every prose rule, not only the spelling one; acronyms
(`HTTP`), internal capitals (`Tessellate`, `docSurface`) and letter runs
touching a digit, a slash, an `@` or a dotted name (`utf-8`, `app.js`) are
never checked. Measured on 8,000 characters of this project's own README:
six findings, five distinct words, every one of them a product name or a
coinage rather than a false positive.

**The browser's own spellcheck is now off while ours is on**, and
conditional rather than deleted: `docCmParts.spell` turns it back on if the
word list fails to load. Two underlines under one word, only one of which
answers a click, is worse than either alone.

**Suggestions and autocorrect come from the same generator.** The candidate
set is the edits one step from the typed word, filtered against the list
(Norvig's shape: a few hundred Set lookups rather than 93,000 edit-distance
computations), ranked by how specific the edit is, because there are n-1
transpositions of a word against 25n substitutions. Autocorrect fires only
on a *unique* transposition, or a unique dropped letter when there is no
transposition, on a word of four letters or more; everything else is a menu.

**Measured cost.** `docProseFindings` over an 8,000-character document: 2.8ms
cold, 0.9ms warm, against a 300ms keystroke-to-underline budget. The
candidate list is computed when the menu opens, not during the pass: doing
it per unknown word per pass measured 29ms on a 276-character document.

**Found while doing this, not fixed:** built, the grammar check is Harper (HISTORY.md, "Moved from the plans, 2026-11-14 (documents-plan audit: found built)").

## 11. Phase 4 decisions, made 2026-09-12

The plan asked for five things and left four choices inside them unmade. They
are made here, with the reason, so no later session re-derives them.

**Backlinks are scanned on the server.** The browser holds every note
(`allEntries`) but no other document's *content*: `_summary()` deliberately
sends a preview, because a document runs to thousands of words. A client-side
scan would have found note backlinks and silently missed every document one.
One endpoint (`GET /documents/{id}/backlinks`) answers for both kinds and
defines "a mention" exactly once.

**The panel's two actions mean one thing each.** "Link back", on a row that
already links here, inserts `[[Source]]` **at the caret**, because that is
where every other insert in this editor writes (the `/` menu, the table
command, the properties command); an action that alone appended to the end of
the document would be the one place "insert" means something else. "Link", on
an unlinked mention, rewrites the mention **in the source that wrote it**,
through that kind's own update route, so the note's revision, its `[[link]]`
sync and its search vector happen exactly as they do for a hand edit.

**A source that links is not also an unlinked mention**, and a title under
four characters is never hunted as one. The second list means "not connected
yet"; a source in both says the opposite of what each list is for, and "AI"
or "Q3" as a mention would match a third of a notebook. A *linked* mention is
an exact `[[name]]` and is found at any title length.

**Block references are Obsidian's syntax, and the id is generated.** A block
carries `^an-id` at the end of its last line; the link is
`[[Document title#^an-id]]` and the embed is the same with a leading `!`,
which is the form Phase 3's embeds already parse the left half of. The id is
generated by the command that copies the link, never asked for: a person
naming their own ids is a person maintaining them, and the one thing a block
reference must survive is the paragraph being rewritten around it. The id
shape is narrower than Obsidian's (`[A-Za-z0-9][A-Za-z0-9-]{0,31}`) because
ids are generated here, so the only reason to accept more is to read somebody
else's file, and a `^` followed by punctuation is far more likely to be
arithmetic (`2^31`) than a block id.

**A block is the run of non-blank lines around the caret, except in a list,
where it is the item's own line**, and a position inside a fenced code block
has no block at all: the text in a fence is code, and appending an id to it
changes what the code says.

**A block reference points at a document, not at a note.** The id has to be
written into the target's text by the command that copies the link, and a
note has no editor here to put one in. A note is still linkable by `[[name]]`,
which is what it has always been.

**An embedded block is drawn as quoted markdown, not as a card.** Every other
embed draws an *object* through the renderer that owns it (a note card, a map
chip, a file tile). A block is a paragraph of this notebook's own writing, so
it is drawn as what it is, with a source line that opens the document at the
block.

## 12. The writing intelligence as one feature: decided 2026-09-13

Moved to HISTORY.md ("Moved from the plans, 2026-09-13", DOCUMENTS_PLAN.md)
on 2026-09-13: decisions D1 to D5 are built and measured, and a plan holds
open work only. The rules that outlive the pass are two rows in
`docs/DESIGN.md`'s recipe index (a viewport popup, and one feature drawn on
several surfaces), kept by `tests/test_ui_recipes.py`. What is left open is
in `editor-intelligence.md` (git history).

## 13. What a self-contained HTML export is: decided 2026-09-13

The decision this plan owed since Phase 7 was written, taken here so it is not
re-derived: **the file is rendered in the browser, from the pane that is
already rendered, with a stylesheet of its own and its images as `data:` URIs.**

**Why not on the server.** There is no markdown-to-HTML renderer in
`src/tessellate/` (checked again before this was written) and this plan forbids
adding a dependency for one. Writing a second renderer in Python would mean two
renderers that have to agree about tables, callouts, columns, embeds, block ids
and comments-as-footnotes, and the one on the server would be the one nobody
looks at. The browser already holds the only faithful rendering of a document,
in `#doc-preview`, so the export takes it from there. It is the same route the
whiteboard's PNG export takes for the same reason: the drawing exists, export
what is drawn.

**What "self-contained" is taken to mean**, because the word is doing all the
work: the file opens on a machine with no network, no Tessellate and no account.
That is one assertion and everything below follows from it.

- **The stylesheet is written out, not borrowed.** The app's eleven sheets are
  four hundred kilobytes of tokens, docks, dialogs and responsive bands for a
  page that has none of those in it, and half of it resolves against custom
  properties that would not be there. `DOC_EXPORT_CSS` is a reading stylesheet:
  measure, rhythm, headings, code, tables, quotes, and a `prefers-color-scheme`
  block, because a file has no settings in it and the reader's system is the
  only preference there is.
- **Images become `data:` URIs**, fetched through the app's own token, with an
  8MB budget. Past the budget, or when a file cannot be read, the image becomes
  its alt text in words: a page that says "[image: the floor plan]" is honest,
  a broken frame is not.
- **Controls are dropped, and their words are not.** Buttons, selects, icon
  elements and the code block's copy/save group only work inside a running app.
  A `[[wikilink]]`, though, renders here as a `button.wiki-link`, so removing it
  with the rest took the document's own words out of the sentence (measured: "A
  link into the app: ."). A wiki link keeps its text; everything else goes.
- **A link back into this app loses its `href` and keeps its text**; an
  `https:`, `mailto:` or same-page link is untouched. `data-` attributes are
  stripped with them, one of which is a note id: data about somebody's notebook
  travelling inside a document they meant to share.
- **Headings shift up by two.** The rendered pane starts at `h3` because the
  app's page already has an `h1` above it; a file on its own has no such page,
  so `h3` becomes `h1` and `h6` stops at `h4`.
- **No `h1` of the title is added**: the pane already prints the document's
  title as its first heading, and the name also travels in `<title>`, which is
  what names a tab, a bookmark and the saved file.
- **Comments travel as footnotes**, exactly as they do in the PDF export: a
  document handed to somebody carries what was said about it. (Audit
  2026-10-05, FEAT-03: footnotes rendered only in Live, so this travelled as
  literal `[^c1]` text until `mdFootnotePrepare`/`mdFootnotesFinish` in
  markdown.js drew them in Read, print and the HTML export the same day.)

**What holds the line**: `tests/test_document_export_html.py` runs the document
shell in node and fails on a host name, a `<link>`, an `@import`, a `url()` or a
`<script>` anywhere in it, and `scratchpad/ui-sweeps/docexporthtml.js` (removed 2026-10-12, recoverable from git history) exports a
real document, opens the saved file in a second browser context with every
network request refused, and measures what renders: 0 network attempts, 1
decoded inline image, the table, the disabled task boxes and the reading
measure.

**Closed 2026-10-05 (docs hygiene before 0.4.0):** DOCX both ways, Markdown
with its assets and import of `.html` are all built (Phase 7; HISTORY.md,
"Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: DOCUMENTS_PLAN)").

## 14. What a document daily note is: decided 2026-09-20

Phase 4 item 5 asks for "daily notes" on a surface that already has them
somewhere else, so this is the decision that had to come before the code, and
it is taken here rather than deferred a fourth time (standing order 3).

**Read first, both surfaces.** The Timeline built the whole of it and wrote the
reason down: a daily note is an ordinary note whose first line is the ISO day,
`# 2026-09-20` (`dailyNoteTitle` in `app.js`, TIMELINE_PLAN Phase 4,
WORLD_CLASS_PLAN D6). On top of that convention sit `GET`/`POST
/entries/daily/{day}` (create or return), `GET /entries/daily` with a month of
`written` flags for a calendar strip and a streak, the today bucket's "Start
today's note" button, which opens the composer rather than writing the note,
and the agent's own "add to today's note" tool. None of that is duplicated.

**The measurement that decided it.** On the branch head, a document titled
`2026-09-20` is already in the Timeline's own feed as a `document` row (it is
one of the four kinds `/timeline` returns), and the day bucket beside it still
offered "Start today's note". So the app already lets a day be written as a
document, and then does not believe it: the writer gets a second offer for a
day they have already begun, and pressing it splits the day across two stores.
That, not a missing feature, is what was wrong.

**The decision.** *One day, one page, and which store holds it is the writer's
choice, not the app's.*

- Documents gets the **"Daily" template** its own item-5 list names, and
  nothing else new. The document it makes is titled with the ISO day, the
  exact string `dailyNoteTitle` writes, so the two surfaces agree by spelling
  rather than by a shared table.
- **No second endpoint, no second streak, no second calendar strip.** A
  create-or-return `/documents/daily/{day}` would be the second implementation
  of the same idea this item was told to avoid, and the streak and the strip
  read `/entries/daily`, which is where a journal's own history belongs.
- **The Timeline learns to recognise either.** `timelineDailyNote` and
  `timelineIsDailyNote` accept a `note` or a `document` whose title is the day,
  so a day written as a document gets the calendar glyph and the bucket offers
  to open it instead of starting a second one. The button names the kind it
  found, because "today's note" pointing at a document is a small lie.
- **What a document daily note adds, and why it is worth having at all**: the
  outline, backlinks, block references, comments, version history, tables and
  the export set, for a day that grew past a capture. That is a real difference
  in kind, not a second copy of the feature, and it costs one template row.

Built 2026-11-14: a Today button in the Library Documents dock opens the day's document or starts it from the Daily template (HISTORY.md, "Moved from the plans, 2026-11-14 (documents Today)").

## 15. The code block's own bar, and where it belongs: measured 2026-09-20

INBOX 232's brief for the live view asked for three things, of which two were
built and checked (the fence's emptied marker rows, 706e2af, and the check of
tables, blockquotes and task lists, 2026-09-19). The third, "a header row with
the language and a copy button", was measured here before any of it was
written, and **it already exists in the Read pane**: `renderMarkdown` in app.js
has drawn a `.code-block` with a `.code-bar` carrying the language, Copy and
Save since INBOX 172. Measured on the branch head at 1440x900, a document
holding a `python` fence and an unlabelled one: 2 bars, `python Copy Save` and
`code Copy Save`, 4 buttons, the language taken from the fence and "code" where
there is none. Writing it again would have been the fourth rebuild this
project's CLAUDE.md warns about.

**The decision the measurement forces: the bar stays in Read, and the live view
keeps the corner label with no button.** Three reasons, in order of weight:

1. A control inside a `contenteditable` is a caret trap and a selection
   hazard. The live view already pays for one (`DocTableMenuWidget` carries
   `ignoreEvent`), and each one is a thing the arrow keys can walk into,
   `Ctrl+A` can carry and a paste can take with it.
2. The row it would hang from is **8px tall on purpose**, against a 36px line
   (measured). The whole of the 2026-09-19 fix was to stop the fence spending
   full rows on things that are not code; a header row put back is that fix
   undone.
3. The live view is editable text. The code is already under a caret that can
   select it, and Read is one tap away on every band including the phone.
Built after all in Live as an overlay Copy button (L-documents-65): HISTORY.md, "Moved from the plans, 2026-11-14 (docs65)".

**What the measurement did find, and what was fixed here**: the bar's Copy
button read `⧉ Copy`, a typed U+29C9 standing where an icon belongs, in an app
that ships `ph:copy` and draws five other Copy buttons with it. Two call sites,
the chat's table bar and every rendered code block, both now through `setLabel`
with `ph:copy`; Save beside it takes `ph:download-simple`, the icon the app
already puts on "save this to your computer", because an icon beside one label
and nothing beside the other reads as two kinds of control in one bar. The
glyph is in `tests/test_no_glyph_icons.py`'s banned list so it cannot come
back, and `scratchpad/ui-sweeps/doccodecopy.js` holds the whole measurement,
11 of 11.

## 16. The engine's three omissions, and the table menu: decided 2026-09-20

Phase 2 named three things it deliberately did not build, and the sidebar work
left a fourth beside them. Each is decided here rather than carried again, and
each decision rests on a number from `scratchpad/ui-sweeps/doctoolbarstate.js`
(21 of 21) rather than on how the item was described.

Section 16 item 1 (the toolbar's own state) is built (`renderDocToolbarState`). Moved to HISTORY.md, "Moved from the plans, 2026-11-09 (book5-1109: DOCUMENTS_PLAN)".
**2. Atomic ranges: decided against, and the decision rests on a
measurement that contradicts the note that asked for them.** The engine file
records the symptom as "a hidden marker can still be walked into with the
arrow keys ... the caret appears to jump two characters". Walked on the branch
head across `**a bold run**`, the caret visits offsets 29 to 36 in order,
skipping none, and moves 10, 5, 9, 8, 11, 5 and 12 pixels between them: single
characters throughout, with no two-character jump anywhere.

What *is* measurable is a different thing, and a bigger one: **the reveal is
per line, not per range.** With the caret on another line the word "italic"
sits at x=779; with the caret inside the bold run it sits at x=820, so
entering that line moves everything after the first hidden marker along it by
41px. Atomic ranges would not touch that, because they govern where the caret
may be placed and not what is revealed; and they would take away the one thing
Phase 2 item 3 deliberately built, a marker you can put the caret between in
order to edit it. So they are the wrong tool for the only symptom that
reproduces. **If the line's shift is ever reported, the fix is a narrower
reveal (the range under the caret rather than the whole line), not atomic
ranges**, and that is the work item, not this one.

**3. The `Mod+click` affordance.** Built 2026-11-14: a held Ctrl or Meta thickens the link chip's underline (HISTORY.md, "Moved from the plans, 2026-11-14 (link modifier cue)").

Section 16 item 4 (the table cell menu, `kebabMenu` item `group`) is built. Moved to HISTORY.md, "Moved from the plans, 2026-11-09 (book5-1109: DOCUMENTS_PLAN)".

## 17. The live view for professional use: measured 2026-09-21, phases open

The owner, INBOX 294: "can you improve the ui and ux of the live view and
make it better for professional use and impressive as both a tool, utility
and aesthetic?"

**What it is for, decided here so the phases do not drift.** This is a
notebook's editor, not a development environment. The person using it is
writing a report, a plan or a set of notes, and the live view's whole claim
is that the document looks like itself while it is being written. So
"professional" here means the page a writer would be content to show
somebody, not a denser instrument panel: nothing in these phases adds a
control to the surface that a writer did not ask for, and any new affordance
appears on approach rather than sitting on the page.

**Measured on the branch head, 2026-09-21, at 1440 in the default view**
(one document holding a title, a paragraph, a section, a list, a table, a
fenced code block, a quotation, inline code, a link and a highlight):

| What | Reading |
| --- | --- |
| Editor pane | 794.02px wide, the line box 774.83px |
| Body text | 16px system-ui, line height 25.6px, so 1.6 |
| Line length | about 81 characters, measured against a mixed alphabet rather than a repeated letter |
| Page gutter | 9.6px each side |
| Title | 28.8px at weight 700, so 1.8 times the body |
| Decorations drawn | headings, list items with their own bullet mark, tables with a column count on the row, fences with quiet open and close lines, quotations, inline code, links, highlights |

Two things that reading settles. The typography is not the problem: 81
characters at 1.6 sits inside the comfortable range, and the decoration set
is broad and already drawn rather than left as syntax. And the gutter is:
9.6px puts the first character of every line ten pixels from the edge of its
pane, where a document that reads as a document gives it room. That single
number is the largest gap between this surface and the editors it will be
compared with.

**Decisions made.**

1. The page is a page. The text sits in a measure with real margins rather
   than filling its pane to the edge, and the margin is the same on both
   sides at every width.
2. The measure is capped. A line of prose has a comfortable length and a
   wide monitor is not a reason to abandon it.
3. Nothing is added to the chrome. Every phase below either changes what is
   already drawn or reveals something on approach.
4. No new recipe without its lint, per standing order 11.

**Phases, each with the gate it is finished against.**

- **17a and 17b: built 2026-09-23.** Moved to HISTORY.md ("Moved from the
  plans, 2026-09-23"); `scratchpad/ui-sweeps/docpage17.js` is the gate.
- **17c: built 2026-09-23.** Moved to HISTORY.md ("Moved from the plans,
  2026-09-23"); `scratchpad/ui-sweeps/docblocks17c.js` is the gate.
- **17d and 17e: built 2026-10-04.** Moved to HISTORY.md ("Moved from the
  plans, 2026-10-04 (the documents tails)"); `doccrumbview.js` and
  `contrast.js` with `ONLY=document` are the gates. The "how far through" half of 17d was
  built 2026-11-14 (HISTORY.md, "Moved from the plans, 2026-11-14 (how far through)").

**Not verified, and to be taken first by whoever opens this.** 17a to 17c
are measured at 1280, 1440, 1920 and 2560, light and dark, in the default
look and in Classic (`scratchpad/ui-sweeps/doclooks.sh`); 17d and 17e are
built (see above). The phone is not redesigned from here (UI_MODERNISATION_PLAN
Phase 11's territory, which is why 17a's page margin applies above 600 only),
but it is measured: 2026-10-04 at 390x844, light and dark, `docphonebar.js`
and `doctaskbox.js`, which found and fixed three faults (the status line under
the foot bar, the selection bar off the window, the task box at the target
floor's size); see HISTORY.md ("Moved from the plans, 2026-10-04 (the
documents phone pass)").

## 20. The 2026-10-05 feature audit: decisions

From `scratchpad/audit1005/features.md` (FEAT-03, FEAT-04, FEAT-08, the
documents briefs D1 to D5). Every brief is built: D3 and D4 (decisions 6
and 7), D5's handles (decision 8) and its pictures in the Word export
(FEAT-18, on the existing `docx` extra). The record is in HISTORY.md ("Moved
from the plans, 2026-10-05 (the feature audit's documents and map fixes)");
checked at head 2026-10-05 (op3-1005): `mermaidFlowParse`, the print dialog's
`CSSMarginRule` test and `docImageAltWith` in documents.js. Nothing here is
open; the decisions stay.

**Decisions made.**

1. **Footnotes are drawn by the shared renderer, not by each view**
   (FEAT-03). `mdFootnotePrepare` in markdown.js is pure (node-tested) and
   `mdFootnotesFinish` draws the raised numbers and the notes at the foot;
   a document runs the pass over the whole text before it is cut into
   pieces. Numbered in citing order; an uncited note is still printed, last.
   The back link is the word "Back", not an icon, because an icon is
   stripped from the HTML export.
2. **Rich paste is an allowlist walker, no library** (FEAT-04). HTML goes
   through `DOMParser` (`style` renamed first, which the CSP would refuse)
   and only headings, emphasis, strike, links with http, https, mailto or
   app paths, lists, quotes, code, pictures and tables become Markdown.
   It takes a paste only when the HTML carries one of those, so a code
   editor's coloured copy stays plain. Ctrl+Shift+V is plain text.
3. **Mermaid fences stay code blocks** (FEAT-08). No Mermaid is vendored
   (the fully-local rule: nothing that is not already in `frontend/vendor/`),
   so a ` ```mermaid ` fence renders as code with its language label;
   BACKLOG 29c's "already renders" is corrected. A flowchart-subset parser
   (the audit's D3) is the way in if it is built, not a vendored bundle.
   **Reopened by the owner, 2026-10-06, and built 2026-10-27: mermaid now
   draws.** mermaid.js 12.2.0 is vendored (`frontend/vendor/mermaid/`) and
   lazy-loaded inside a hidden same-origin frame (`/mermaid-frame`, a route
   whose response carries its own policy, so the app's `style-src 'self'` is
   unchanged); every kind draws in Read, Live, a print, the HTML export, chat
   and Ask, as an image of the finished SVG. The BACKLOG's diagram steps 9 to 11 are the diagram builder (section 22), built.
4. **A hidden formatting toolbar always shows its way back** (INBOX 574,
   2026-10-05): the dock's Formatting button while it is hidden (not on a
   phone, which formats from the thumb bar), Ctrl+Shift+X, the ⋯ row and
   the palette row, and one toast the first time it is hidden.
5. **A page break is `\newpage` on its own line** (2026-10-05, the audit's
   D4, first part): the Pandoc and LaTeX spelling, so a document leaves
   for any Markdown-to-PDF tool with its breaks intact. A labelled dashed
   line on screen, the break itself in a print and in the HTML export, the
   "/" menu's Page break in a document (not in a note, which is not
   printed as pages). Page size, margins and page numbers are decision 7.
6. **A flowchart fence draws as one, by a parser of our own** (2026-10-05;
   **superseded 2026-10-27 for drawing: Mermaid draws every kind, flowcharts
   included, see decision 3; `mermaidFlowParse` and `mermaidFlowLayout` stay
   as the pure reader the verifier and board import use, and the SVG-tree and
   `docMermaidSvg` drawing path is gone**; the rest of this item is the
   reader's record,
   the audit's D3, inside decision 3's terms). `mermaidFlowParse`,
   `mermaidFlowLayout` and `mermaidFlowSvgTree` (documents.js, the
   `DOC-MERMAID` region, node-tested): `flowchart` or `graph` in any of the
   four directions, seven node shapes, six link kinds with labels, chains and
   `&` fans, comments, and the styling lines read and ignored. Laid out in
   layers (longest-path ranks with each cycle's return reversed, barycentre
   ordering, each layer centred), a line that would lie on another (a
   return, a second link between one pair, one that skips a rank) bowed
   aside. Drawn in Read (so in a print and the HTML export), and in Live
   while the caret is outside the fence (a state field, the columns block's
   reason); pressing the figure opens its text. Anything else, a subgraph
   and every other diagram type included, stays the code it is, so nothing
   is drawn half right. Text is text (`createElementNS`, `textContent`).
   Not drawn in a note (notes render through markdown.js at boot, and the
   parser stays out of the boot scripts); "Open as a board" is the
   whiteboard's W5.
7. **The printed page is chosen in one step before the browser's dialog**
   (2026-10-05, the audit's D4). Print or save as PDF opens a small dialog:
   page size (A4 or Letter; Letter first where the locale is US or Canada),
   orientation, margins (narrow 12mm, normal 20mm, wide 28mm) and a switch
   for the page number ("n / N" at the foot) with the title at the head,
   remembered on this computer; a plain Ctrl+P prints on the last choice.
   Written as a constructed stylesheet (the CSP refuses a `<style>`), the
   number and title as CSS page-margin boxes, which Chromium draws from 131
   (the desktop window is Chromium); where `CSSMarginRule` is missing the
   switch is off and says the print dialog's own headers can do it. Found
   on the way: the print rule hid every child of `<body>` but the documents
   page, and the page has sat inside `<main id="app-main">` since the shell
   moved, so a print was one blank page; the main is kept now and the
   shell's window-high boxes let go.
8. **A picture is resized and aligned where it is shown** (2026-10-05, the
   audit's D5). In Live, a picture (not one under its revealed source) sits
   in a frame with DESIGN.md's grip on its lower right corner and an align
   button at its top right, both shown on hover and on focus (always on a
   touch screen, the grip at 24px). A drag sets the width between 40px and
   the text column; the grip is a slider to the keys (the arrows 10px, Shift
   50px, Home and End the bounds, Delete back to the picture's own size);
   the align menu is Left, Centre, Right and Inline. Both write the options
   into the alt text (`docImageAltWith`: the name, then the width, then the
   alignment, then the caption's words), one Undo step each, so Read, a print
   and every export draw the same picture.
9. **A narrow sidebar puts its tab strip under the collapse toggle**
   (2026-10-05, audit FE-19). "Documents" and "Outline" need 182px and the
   toggle's lane 46px; at 1024 the sidebar is 192px, and "Outline" ran 7px
   under the toggle. Below a 14rem content box (a 256px sidebar) the strip
   starts one toggle-height down, full width, with `--space-2` of side room
   per tab instead of `--space-5` (a container query on `#doc-sidebar`).
   Not chosen: a wider sidebar at 1024 (the editor's width is the page),
   shorter labels (the strip's words are its only labels). Measured by
   `scratchpad/ui-sweeps/perf2-1005-docside.js`: fits, nothing under the
   toggle, at 1024, 1440 and 390, light and dark.
10. **With no model, the documents' assistants stay visible and disabled
   with the reason, never hidden** (the owner, 2026-10-11: "should the
   assistant features in the regular and code document editor be disabled
   when the ai isnt available??"; taken under standing order 3). The inline
   Ask bar's field is read-only and its Ask is the gate's offer (why, what
   works now, Set up a model); the document assistant's field and Suggest
   are gated the same way; each surface carries one "Needs a model" notice
   with the Settings link. What needs no model stays live: Quick fix,
   Format, Run tests, Find usages, the spelling and grammar fixes. The code
   Assistant's question box stays live because the tools answer what they
   can (CHAT_PLAN decision 75: format, tests, usages, the quick fix, the
   symbols); anything else is offered to needle or says it needs a model.
   A code document is spoken to in code's words ("Explain, simplify, add
   types", "the N lines you selected"); prose wording stays in prose. A
   model connecting gives everything back live (`mm-model-gate`).
11. **Two emoji tables, on purpose** (OPEN 1084): `:smile:` shortcodes are
   GitHub's names so a document round-trips; the picker searches Unicode
   names. One table would break one of the two.
12. **The Python completion table is read from CPython's `inspect`**, not
   Pyodide's (OPEN 1070): the same standard library, no browser in the
   generator; a regeneration on another version is a reviewed diff.
13. **Markdown's inline marks are one table, not one module** (OPEN 1130,
   1132): `MD_INLINE_MARKS` (notes-list.js) is what the toolbars and the "/"
   menu write; `INLINE_MD` stays a hand-written regex, because the renderer
   addresses its capture groups by number, and a test reads every mark back
   through it.

## 18. The slash menus as one system: built 2026-09-21

Moved to HISTORY.md ("Moved from the plans, 2026-10-03 (the documents pass)", DOCUMENTS_PLAN.md section 18) on
2026-10-03: a plan holds open work only. The one thing still open is below.

**Measured on a phone, 2026-10-04** (`docphonebar.js`, 390x844, light and
dark): the document's "/" menu, opened from the foot bar, is 354x386 inside the
window and above the bar, 56 rows at 45px, 8 on screen. 18a (one row shape)
is built, HISTORY.md. **Not verified:** the chat context's commands press
controls in the chat dock, so a change there has to be measured against that
dock rather than assumed.

## 23. The code editor as an IDE: run, preview, test and debug (INBOX 748)

Placed 2026-10-10. Section 21 and Brief 42 give the editor VS Code's
everyday feel. The owner's ask goes past that: "a full debugger", "run and
preview and test more than just python", "the python one needs a lot of
improvements and extensions". What exists: `.js` runs in a worker and `.html`
renders in a frame inside `/documents/run-sandbox` (`api/run_sandbox.py`);
`.py` runs in the sandbox's Python twin once the Pyodide extra is installed
(`core/extras.py`); output is a panel of rows under the editor, ten seconds
and five hundred rows (`documents-code.js`, "Run, and its output"). No
breakpoints, no stepping, no tests, no REPL, no TypeScript, SQL, CSS or SVG.

**What VS Code has that matters here, and what cannot be had offline in a
browser.** VS Code's debugger is a Debug Adapter Protocol client; the work is
in the adapters, which are native processes. The app's rule (ROADMAP policy
1: plain JS or WASM, offline, lazy, licence beside it) rules those out, and
rules in two real debuggers: Python through `bdb` inside Pyodide, and
JavaScript through an interpreter that steps. Both give the four views a
debugger is (breakpoints, call stack, variables, watch) and the five actions
(continue, step over, into, out, stop). Compiled languages (C, Rust, Go,
Java, C#) do not run here and the panel says so in one line, as TypeScript's
row does today.

### Decisions made (do not re-decide)

- D1. **One run protocol for every language**: `{kind, source, path, stdin,
  tests}` in and `{row, level, line, col}` rows out, over `postMessage` to
  the sandbox; a language is a module in `frontend/js/run/` that implements
  `run`, optional `preview`, optional `test`, optional `debug`. The panel,
  the Stop state and the limits are shared, never per language.
- D2. **The Python debugger is `bdb` in the Pyodide worker**, not a
  re-implementation: a `Bdb` subclass posts each stop (frame, line, locals,
  globals, the stack) and blocks on `Atomics.wait` over a `SharedArrayBuffer`
  until the main thread posts the next action. The sandbox pages therefore
  carry `Cross-Origin-Opener-Policy: same-origin` and
  `Cross-Origin-Embedder-Policy: require-corp`; `test_run_sandbox.py` checks
  the headers. Breakpoints are `set_break`, conditions are evaluated there,
  exceptions stop at the raise with the traceback, and the watch list is
  evaluated in the stopped frame. Where `SharedArrayBuffer` is unavailable
  (a webview without the headers), Run still works and Debug says why.
- D3. **The JavaScript debugger is JS-Interpreter** (Neil Fraser, Apache-2.0,
  ES5, about 150 KB minified, pure JS, no network), vendored under
  `frontend/vendor/js-interpreter` with its licence and a `test_vendor_manifest`
  row; ES2015 and later is first lowered by `sucrase` (MIT; measured before
  vendoring, expected about 500 KB gzipped under 200 KB) where it can be,
  and the panel names the construct it cannot step. Plain Run keeps the
  worker's native engine; Debug uses the interpreter. Scripts that use the
  DOM debug against a stub `document` and say so.
- D4. **TypeScript runs**: `sucrase` strips the types (no checking) and the
  row that said "does not compile" becomes "runs without type checking". The
  same pass handles JSX for p5 and plain scripts.
- D5. **SQL runs against SQLite in the browser**: `sql.js` (MIT, SQLite
  compiled to WASM, about 1.3 MB, lazy, measured first) under
  `frontend/vendor/sqljs`; a `.sql` document's Run shows each statement's
  result as a table in the output panel, with an in-memory database per run
  and a "load this CSV document as a table" action. Never the app's own
  database.
- D6. **Previews are a kind of run**: `.css` previews against a sample
  document, `.svg` and `.md` render in the sandbox frame, `.html` as today,
  the p5 kind (INBOX 735) runs in the frame with `p5.min.js`; every preview
  refreshes on save and on a 400 ms idle when "Preview live" is on.
- D7. **Tests are a kind of run**: Python runs `unittest` discovery over the
  document (and `pytest` where the extra carries Pyodide's own pytest
  wheel, measured and decided in Brief 69); JavaScript gets a 150-line
  `describe`, `it`, `expect` harness of the app's own in the worker. The
  Tests panel lists each test with its state, time and failure diff, and a
  failing assertion is a diagnostic on its line in the editor.
- D8. **Two consoles**: a Python REPL (Pyodide, the document's namespace
  after a run) and a JavaScript REPL (the worker's global after a run), as
  one panel tab beside Output, Problems, Tests and Debug. The panels are one
  `.dock` recipe from DESIGN.md with a drag handle, remembered height and a
  keyboard toggle each (Ctrl+J, Ctrl+Shift+M, Ctrl+Shift+Y, Ctrl+Shift+D).
- D9. **The Python improvements are deterministic and local**: `ruff-wasm`
  for lint and format (Brief 42 decides vendoring on its size), stdlib
  completion from a generated table (`scripts/gen_python_completions.py`
  over the vendored Pyodide's `inspect` at install time, not shipped),
  signature help from the same table, `print` and `input` through the
  panel (stdin is a field), matplotlib and numpy only if the extra ships
  them (measured in Brief 69; not by default), and "Run selection" and
  "Run cell" over `# %%` markers.
- D10. **JS debugger watches stay evaluated natively and read-only**
  (standing order 3, 2026-11-12, L313): stepping them in the interpreter
  would need a nested run on its stack and would drop the read-only view
  of the frame, so a watch can never change the program it watches.
- D11. **Comment ratio (D46) stays as built** (standing order 3, 2026-11-12,
  L329): the row carried no written recommendation, so the shipped ratio is
  kept and no setting is added.
- D12. **No separate worker for the prose tools (D45)** (standing order 3,
  2026-11-12, L329): the Harper worker already runs off the main thread; a
  second worker is not built. D47 is decided "Keep it": the textarea
  fallback stays, and only the dead surface aliases (`rect`, `scrollLeft`)
  were removed.
- D13. **Lazy pieces stop at the open path** (L327, 2026-11-14): code that runs on
  a user action loads on first use (dictionary, backlinks, suggest, blockref,
  code format). Code that the editor's open path or every check calls
  synchronously stays where it is: Run and Debug extensions, quick fixes and
  go to definition, the block-id model, the word list, `docMatchCase`. Making
  the open path async to move them would trade a working editor for a riskier
  one for deferred, not removed, bytes. run_sandbox.py (362 lines) stays one file.

### Phases

| Phase | Brief | Deliverable | Measured by |
| --- | --- | --- | --- |
| I1 run, preview, test | 69 | Built 2026-10-10 (HISTORY "DOCUMENTS Brief 69, I1"); what is left is in `ide1-1010.md` (git history) | `scratchpad/ui-sweeps/code-run.js`, 46/46 at 1440 and 47/47 at 390 |
| I2 the debugger | 70 | Built 2026-10-10 (HISTORY "DOCUMENTS Brief 70, I2"); what is left is in `debug70-1010.md` (git history) | `scratchpad/ui-sweeps/code-debug.js`, 32/32 at 1440 and 31/31 at 390 (js, ts, py: breakpoint, three steps, a watch, the exception stop) |
| I3 the IDE shell | 71 | Built 2026-10-10 (HISTORY "DOCUMENTS Brief 71, I3"); what is left is in `shell71-1010.md` (git history) | `code-keys.js` 34/34 keys exercised, palette 61 commands (40/40 and 67 with Brief 70's debugger rows); `ide-shell.js` 19/19 (four heights kept across a reload); `ide-split.js` 10/10 |

Help moves with each phase (standing order 13): the `data-help-for`
popovers on Run, Debug and the panels, the Guide topic `code-run`, and
`test_manual_parity.py`. Pyodide's `bdb` under `Atomics.wait` inside this
sandbox's policy was measured working in Chromium (Brief 70); measured too,
the frame is isolated only when the app's own page carries the two headers,
so every response does. Not verified: whether the app's desktop webview
honours them (where it does not, Debug on Python says so and Run works).

## 24. Deepened 2026-10-10: the documents editor (Brief 72a, decision 71)

Measured with `scratchpad/ui-sweeps/deepen72a.js` on a fresh data dir, no
model configured, Chromium, three runs on a shared four-core machine (ranges
are across runs): a 3,724-word Markdown document of 40 sections.

**What renders today**

| Measure | 1440 | 390 (touch) |
| --- | --- | --- |
| Controls in `#tab-documents` (a list of three or four documents included) | 46 to 50 | 28 to 35 |
| Clicks from the dashboard | 3 (Library, Documents, the row); the palette 1 ("Go to Documents", "New document") | the same through the phone shell |
| Time to the editor | click to painted editor 1,743 ms cold (the lazy bundle); a reopen 155 to 252 ms | 2,823 to 3,013 ms cold |
| Undo | text: Ctrl+Z and Ctrl+Shift+Z round trip (CodeMirror history). Document acts: 2 of 11 undo (delete, AI edit); none for rename, archive, unlink a note, remove or attach a bookmark, restore a version, apply a writing finding, add to the dictionary, create (static read of each handler in `documents.js` for `pushUndo`) | the same |
| Overflow | 0 controls past the viewport, 0 clipped, no page scroll; 8 overlaps, each list row's Actions button over its row button | 11 to 20 overlaps: the closed dock menu list (`.doc-dock-menu-list`, 13 items) lays out over the breadcrumbs; whether it paints is not verified |
| No model | 2 AI controls, both disabled with no reason beside them; the editor palette has 33 commands | the same |

**The professional bar.** Google Docs and Word: every act is one undo step,
a named version restores as one step and undoes, a 4,000-word document opens
in under a second, the phone has the same commands. Notion for blocks and
links, Typora for the live view (section 17).

**The rows, by impact**

| # | Kind | Row | Measure | Rules |
| --- | --- | --- | --- | --- |
| 1 | fix | Built 2026-10-10 (HISTORY "DOCUMENTS 24 and 25, Brief 76"): rename, archive, version restore, a writing fix, dictionary add, link attach and remove, note detach and create each one undo step; Ctrl+Z on an open document walks the newer history | `docacts76.js` undo 10/10, redo 10/10 (2/11 before) | 1, 3 |
| 2 | fix | Built 2026-10-10 (HISTORY "DOCUMENTS 24 and 25, Brief 76"): the closed dock menu list has no box; opened, it sits in the window | `deepen72a.js` 390 overlaps 20 to 0 (code 9 to 0), past the edge 12 to 0 | 7, 8 |
| 3 | fix | Built 2026-10-10 (HISTORY "DOCUMENTS 24 and 25, Brief 76"): AI edit and Extract notes are `aria-disabled` with no model and a press opens why and Set up a model (`data-model-offer`) | no-model probe: 2 dead controls to 0 | 12, 4, 6 |
| 4 | redesign | Built 2026-10-10 (HISTORY "DOCUMENTS 24 and 25, Brief 76"): named versions, a Named filter, Changes side by side, restore as one undo step without a confirm | `dochistory76.js`: restore then Ctrl+Z byte-equal at 1440 and 390 | 1, 3 |
| 5 | optimisation | Cold open 1,743 ms at 1440 and 3,013 ms at 390: fetch the documents bundle on idle after unlock and paint the first screen before the outline and checks | click to painted editor under 800 ms at both widths (25g budget, Brief 53) | 13 |
| 6 | fix | Built (found by audit 2026-11-14): a failed save says why, retries and keeps the words locally (HISTORY.md, "Moved from the plans, 2026-11-14 (documents-plan audit: found built)") | | 3, 4 |
| 7 | redesign | Built 2026-11-13 (the recommendation taken): see HISTORY.md, "Moved from the plans, 2026-11-13 (documents-plan: section 1121 row 7)". | | |
| 8 | expansion | Comments, highlights on pages, link cards with a viewer, the long-form choice at first run (Brief 42 items) | Brief 42's numbers | 6, 13 |
| 9 | expansion | Built 2026-10-10 (HISTORY "DOCUMENTS 24 and 25, Brief 76"): Replace in every document (palette), plain or regex, case, through `POST /documents/contents`, one undo step | `docreplace76.js`: 50 documents, 1 step, one Ctrl+Z restores 50 of 50 | 1, 2 |
| 10 | expansion | Labelled and linked sections with a local graph (the owner's idea; after 8) | Brief 42's last row | 6 |
| 11 | optimisation | Built 2026-10-18 (HISTORY "OPEN.md rows closed, 2026-10-18 (open-1018)"): one `data-help-for` per documents section naming its controls, `tests/test_documents_help.py` | `test_documents_help.py` | 6 |

**Briefs.** 42 (rows 8, 10), 48 (Word round trip), 51 (row 6), 53 (row 5),
76 (rows 1 to 4, 7, 9, 11, with section 25's code rows).

## 25. Deepened 2026-10-10: the code editor (Brief 72a, decision 71)

Section 23's decisions D1 to D9 stand and are not re-decided; these rows are
what the editor needs beside them. Measured with `deepen72a.js` as in
section 24, on a 241-line Python document and a one-line `.js` one.

**What renders today**

| Measure | 1440 | 390 (touch) |
| --- | --- | --- |
| Controls in `#tab-documents` | 45 to 49 | 35 |
| Clicks from the dashboard | 3, as section 24; the editor palette 45 commands once a code document is open | the same |
| Time to the editor (from another open document) | 275 to 675 ms | 2,123 to 2,823 ms |
| Gutters and keys | line numbers, fold gutter and lint gutter present; no minimap; Ctrl+D adds the next match (2 ranges); Ctrl+H opens the replace panel | the same |
| Run | `.js`: one Run button ("Run this file in a sandbox"); `.py` without the Pyodide extra: no Run button and no line saying why | the same |
| Undo | text edits round trip; the document acts as section 24 (2 of 11) | the same |
| Overflow | 0 past the viewport, 0 clipped; the list row overlaps of section 24 | 12 controls past the left edge (`doc-file-type`, "Editor and layout", `doc-connections`, `doc-history`, `doc-copy-link`: the dock menu list at x = -32) and 13 overlaps |
| No model | 2 AI controls, both disabled; Emmet, completion, folding, find, format on demand are local | the same |

**The professional bar.** VS Code: the selected line's number bold with the
line bordered, indent guides, multi-cursor, regex find and replace, go to
symbol, folding, a problems panel, run and debug from one key, a palette that
lists every command with its shortcut.

**The rows, by impact**

| # | Kind | Row | Measure | Rules |
| --- | --- | --- | --- | --- |
| 1 | fix | Built 2026-10-10 (HISTORY "DOCUMENTS 24 and 25, Brief 76"), with section 24 row 2 | 390 code document: past the edge 12 to 0, overlaps 9 to 0 | 7, 8 |
| 2 | fix | Built 2026-10-10 (HISTORY "DOCUMENTS Brief 69, I1"): Run disabled with "Install Python in Settings, Packages" beside it | 1 Run control on every runnable type; 0 types with no line | 12, 4, 6 |
| 3 | redesign | Built (Brief 42; measured 2026-10-10, HISTORY "DOCUMENTS 24 and 25, Brief 76"): the selected line's number bold, the line bordered, indent guides | `font-weight` 700 on `.cm-activeLineGutter`; markers 0, 1, 2, 3 on a three-deep file | 11 |
| 4 | expansion | Brief 42's packages, each sized gzipped before it lands: lint (`ruff-wasm`, a JS linter), a formatter, a diff against the last save. The formatter (js-beautify, lazy, 25,022 bytes gzipped, 0 at boot) and the diff (Compare with a saved version) are built 2026-10-10 (HISTORY "DOCUMENTS Brief 42 remainder"); the linters stay open | a diagnostic on its line in the sweep; sizes in the commit | 12 |
| 5 | expansion | Run, preview, test, debug, consoles: D1 to D9 (Briefs 69 to 71) | section 23's gates | 5, 12 |
| 6 | fix | Built 2026-10-10 (HISTORY "DOCUMENTS Brief 42 remainder" and "DOCUMENTS Brief 71, I3"): 64 commands, 0 without a key or "none"; the keybindings sheet (Ctrl+K Ctrl+S) draws the same table, 34 keys each pressed by `code-keys.js` | 45 commands, 0 without a shortcut or a "none" | 6, 10 |
| 7 | optimisation | Built 2026-10-10 (HISTORY "DOCUMENTS 24 and 25, Brief 76"): `docCodeScan` was 1 to 4 ms; two no-op reconfigures skipped, the findings repainted once, the panels a frame after the text | `deepen72a.js` code open 1440 538 to 240 ms, 390 963 to 649 ms (from the 3,724-word document; load 6 to 7) | 13 |
| 9 | fix | Built 2026-10-10 (HISTORY "DOCUMENTS Brief 69, I1"): a run past 2 s lists in `/activity` and stops from it | the run lists in `/activity` and stops from it | 5 |

**Briefs.** 42 (rows 3, 4; row 8 built), 69 to 71 (row 5), 73 (row 9), 76 (rows 1, 2,
6, 7, with section 24).

## Built, the sidebar redesign (INBOX 115), 2026-09-12

Moved to HISTORY.md ("Moved from the plans, 2026-09-12", DOCUMENTS_PLAN.md) on
2026-09-12: a plan holds open work only. What is left open is in
`doc-sidebar.md` (git history).

## Placed from INBOX, 2026-09-21

294. **The owner, 2026-09-21, verbatim:** "can you improve the ui and ux of
    the live view and make it better for professional use and impressive as
    both a tool, utility and aesthetic?"
    The documents live view (the CodeMirror surface, `frontend/js/documents.js`
    and its theme around the `.cm-md-*` decorations). Scope is a plan
    section rather than an INBOX fix: it wants a measured read of what the
    surface is today against what a professional editor gives, a decision
    about what this one is *for* (it is a notebook's editor, not an IDE), and
    gated phases. Belongs in DOCUMENTS_PLAN. The two faults already found in
    this surface tonight, the table header's phantom row with its unpressable
    kebab (290) and the highlight colours (291, fixed), are evidence that it
    has had features added faster than it has been measured.
    **Placed 2026-09-21 into DOCUMENTS_PLAN section 17**, which carries the
    measured read, the decisions and five gated phases.

## 19. A board or a map as an object in a note, and a note's reminders: built 2026-09-21

Moved to HISTORY.md ("Moved from the plans, 2026-10-03 (the documents pass)", DOCUMENTS_PLAN.md section 19) on
2026-10-03: a plan holds open work only. Nothing in it is open.

## Placed from INBOX, 2026-09-23 (392)

- **The live view's markdown rendering: built 2026-09-23.** Moved to
  HISTORY.md ("Moved from the plans, 2026-09-23"); `doclivemd.js` is the gate.
- **Code documents as a code editor (diagnostics, completions): built
  2026-09-23.** Moved to HISTORY.md ("Moved from the plans, 2026-09-23");
  `doccode.js` and `tests/test_syntax_check.py` are the gate.
- **Code documents as a code editor, part two (pairs, Enter, Format, quick
  fixes): built 2026-09-23.** Moved to HISTORY.md ("Moved from the plans,
  2026-09-23"); `doccodeedit.js` and `tests/test_code_editing.py` are the
  gate. Decided there: quick fixes on Alt+Enter, not Ctrl+. (the app's stop
  chord); no model call and no new endpoint.

## Placed from INBOX, 2026-10-03 (INBOX 409: the AI assistant bar is what stays open)

INBOX 409 is built, 2026-09-24 (editable built-in templates, generated persona marks, the user's own mark on chat bubbles, the code selection bar and indent step); the AI assistant bar is closed by the owner's INBOX 431 (f). Moved to HISTORY.md, "Moved from the plans, 2026-11-09 (book5-1109: DOCUMENTS_PLAN)".

## Placed from INBOX, 2026-10-05 (ledger triage)

- ~~`docRevealForSuggest` will not bring a table-cell word into view~~ Not reproduced at 1440 or 390; the account is in HISTORY.md, "Moved from the plans, 2026-10-05 (small-1005: the small open items)" (`revealcell.js`).
- ~~`editor.js` sweep describes the retired editor~~ Re-pointed at `docSurface()`: 78 of the old 89 checks remain and pass; the account is in HISTORY.md, "Moved from the plans, 2026-10-05 (small-1005)".

## Placed from INBOX, 2026-10-07 (next PR)

- Built 2026-11-10 (s9c-1110): live code blocks in a prose document; see HISTORY.md, "Moved from the plans, 2026-11-10 (s9c-1110 part 2)".

## Placed from the owner's list, 2026-10-10

Entries are the owner's words, then the recommendation. Bugs come first.

### Bugs

- Built 2026-11-12 (documents-plan: Links tab; INBOX 827 L1 to L6 and the stale bookmark icon): see HISTORY.md, "Moved from the plans, 2026-11-12 (documents-plan: Links tab)" (the bookmark icon bug).

### Design requests

- The link-card request (icon and colour per bookmark, a viewer): built, see the pointer under Bugs.
- "on vs code selected lines have their line number bolded, the line subtly bordered and there are also indentation lines on vs code as well"
  Recommendation: match VS Code's selected-line gutter, line border and indent guides in the code editor, measured against the VS Code screenshot set. Also carried by Brief 42 (the code editor to VS Code standard).
- "The document editor and whiteboard and mindmap still have many design issues, functionality bugs, poor usability, lack features, and need improvement."
  Recommendation: audit the document editor against VS Code and wordcraft in DOCUMENTS_PLAN section 21, and take the whiteboard and map rows from Briefs 36. Also carried by Brief 42.
- "And we should massively improve, expand, refine and better integrate long form note taking."
  Recommendation: the long-form path (document editor) gets the same comments, link cards, highlights and slash menu as the rest of the app; the first-run style choice is Brief 42. Also carried by Brief 42 (the long-form preference at first run).

### Ideas

- "Idea: on long form notes and documents, you can define topics, or use special characters, commands etc to label and link sections of documents on the ui, highlight or smth. You can visually connect ideas across the current document and link them, with reasons, you can have a local graph of linked ideas available for the current document and can even embed and render the graph in the document which"
  Recommendation: a Phase row in DOCUMENTS_PLAN for labelled and linked sections with reasons and an embedded local graph, built only after highlights (Brief 42) and the graph's local pane (GRAPH_PLAN Phase 4). Also carried by Brief 42 (the labelled and linked sections idea).

### Vendored capabilities to use, 2026-10-10 (Brief 75)

The owner: "make sure all the vendored repositories are made full use of. I want maximum utility." Ranked by the utility to the surface; `scratchpad/vendor_use.py` prints the counts ("available N, called M") and `tests/test_vendor_utilisation.py` ratchets them, so a row that lands raises its floor in the same commit. Each is a lead from a lower-bound count: grep the call site before building (CLAUDE.md section 1).

- **VC4, CodeMirror's merge view against a chosen version**: built (`documents-ide.js:66`), see HISTORY.md, "Moved from the plans, 2026-11-14 (documents-plan audit: found built)".
- **VC5, FlashText link offers** (rank 5): built 2026-10-18, see HISTORY.md "OPEN.md rows closed, 2026-10-18 (open-1018)". Tag offers were not built (a document has no tags).
- **VC6, Harper's own dictionary and the other three dialects**: built 2026-11-12, see HISTORY.md "Moved from the plans, 2026-11-12 (documents-plan: VC13, VC6, L295, L302)".
- **VC13, the lint panel and fold-all in the palette**: built 2026-11-12, see HISTORY.md "Moved from the plans, 2026-11-12 (documents-plan: VC13, VC6, L295, L302)".
- **VC17, Emmet's stylesheet syntaxes** (L, rank 17, lowest). Emmet is fully used (6 of 6 functions) but 4 of its 10 syntaxes are passed (html, css, xml, jsx); scss, sass, stylus, pug, haml and slim need a file type to apply to, and the matching highlight mode (`@codemirror/lang-sass`) is not vendored. Measure: only after a file type exists; an abbreviation `p10` in a `.scss` document expands to `padding: 10px;`.

## Placed from Brief 60, 2026-10-10 (the measured census)

- `documents.js` holds 14 `requestAnimationFrame` sites, 7 scroll listeners, 3 `ResizeObserver` and 4 `MutationObserver` (WORLD_CLASS 26.5, `scripts/handlers.py --list`): the second-largest wake-source count after `whiteboard.js`. No frame measurement of the editor yet; `frames.js` has no documents surface.

## Placed from INBOX, 2026-10-10 (code as documents)

- INBOX 788 (code templates, snippets library, assistant panel): built, see HISTORY.md, "Moved from the plans, 2026-11-14 (documents-plan audit: found built)".

## Placed from INBOX, 2026-10-11 (Files, Recordings and Links; libraryup)

Built 2026-11-12 (documents-plan: Links tab; INBOX 827 L1 to L6 and the stale bookmark icon): see HISTORY.md, "Moved from the plans, 2026-11-12 (documents-plan: Links tab)".

## Placed from INBOX, 2026-10-19 (INBOX 1308: the gap audit)

Read from the code against Notion and Obsidian. Sizes S, M, L. Nothing here is built yet this run; the app already has callouts, toggles, columns, tables, footnotes, wiki links, backlinks, the slash menu, find and replace, outline and versions.

1. Built 2026-11-11 (F1 run) as a recording embed; video stays out (no player, decision 2): see HISTORY.md, "Moved from the plans, 2026-11-11 (F1 graph block, DOCUMENTS_PLAN 16)".
2. Built 2026-11-11 (bd-1111): `[@key]` citations listed at the foot, the "/" menu's Citation; see CHANGELOG.
3. Built (found by grep, checked 2026-11-10): the / menu's "Link to this block" copies `[[Title#^id]]`; see HISTORY.md, "Moved from the plans, 2026-11-10 (s9c-1110 part 2)".
4. Built 2026-10-26 (docs5-1026): see HISTORY.md, "Moved from the plans, 2026-10-26 (docs5-1026)".
5. Built 2026-11-11 (F1 run 2): the block lives in its source document, an embed edits it in place (DOCUMENTS_PLAN 26, decision 82); HISTORY.md, "F1 run 2".
6. Table built 2026-11-11 (F1 run 2): a ```base block, read-only (HISTORY.md, "F1 run 2"). Board and calendar views stay open - M.
7. Built 2026-11-10 (s9c-1110): the / menu's "Remind me about this"; see HISTORY.md, "Moved from the plans, 2026-11-10 (s9c-1110 part 2)".
8. ~~Page cover and icon picker parity with Notion's gallery - S.~~ Built 2026-11-10 (HISTORY.md, "s9c-1110 part 5").
9. Built 2026-11-11 (F1 run): see HISTORY.md, "Moved from the plans, 2026-11-11 (F1 graph block, DOCUMENTS_PLAN 16)".
10. Built 2026-11-11 (F1 run 2): a board card in a document has Edit here, which lends the whiteboard's one view to a dialog over the document (DOCUMENTS_PLAN 26); a second, per-instance whiteboard stays unbuilt (HISTORY.md, "F1 run 2").
11. Built 2026-11-10 (`\label`, `\eqref`, `\ref`): see HISTORY.md, "Moved from the plans, 2026-11-10 (s9-1110)".
12. Built 2026-11-11 (s9c-1110 part 6): sort, filter rows and `=SUM`/`=AVG`/`=COUNT`/`=MIN`/`=MAX`; see HISTORY.md, "Moved from the plans, 2026-11-11 (s9c-1110 part 6)".
13. Built 2026-10-26 (docs5-1026): the Read view takes a progress line; see HISTORY.md.
14. Built 2026-11-10 (`{{time}}`, `{{cursor}}`): see HISTORY.md, "Moved from the plans, 2026-11-10 (s9c-1110)".
15. Built 2026-11-10 (s9c-1110): Download as slides; see HISTORY.md, "Moved from the plans, 2026-11-10 (s9c-1110 part 2)".
16. **The owner, 2026-10-26, verbatim:** "can you add an easier and guided way to write out mathematical equations and symbols like with word or desmos?" A guided equation editor over the existing TeX renderer (`docMathRender`, documents.js): Insert equation (slash menu, Ctrl+K, a toolbar row, Alt+= as Word), a live-preview box where typing `x^2`, `sqrt`, `/`, `pi`, `>=`, `alpha` becomes structure (Desmos and Word linear format: `a/b` becomes a fraction, the caret moves into slots, Tab to the next slot), a symbol palette in groups (Greek, operators, relations, arrows, sets, calculus, matrices) with a search, structure templates (fraction, root, power, subscript, sum, integral, limit, matrix, cases), inline or display, the TeX written into the note so it stays plain text, editable by clicking the rendered equation. No heavy library: own parser or a small vendored one under its licence, lazy-loaded, measured against the boot cap - M. Owner: docs7 (Opus, design). **Decided by the owner, 2026-10-26:** writing first, then a graph block (y = f(x), sliders, lazy-loaded) as its own step; the editor works in Documents, Notes, whiteboard text and the Chat/Ask box (one shared lazy module, each surface a thin caller). **The writing step is built** (HISTORY, "Moved from the plans, 2026-10-26 (docs7-1026)"). `\begin{equation}` numbers itself in Read view (s9c-1110; Live draws only one-line `$$`). **The graph block is built** (HISTORY, "Moved from the plans, 2026-11-11 (F1 graph block)"); a click on a rendered equation opens the editor (built). The Ctrl+K row "Insert equation" is built (over a note, Chat or a board's text; a document's own row stands in a document).
17. **The owner, 2026-10-26, verbatim (screenshot: Notes "Capture a thought", source view showing `<u>underlined</u>` with line numbers):** "also the note capture doesnt have view options, I want it to use the live view by dafault and then the user can change it if they want." The note composer gets the Documents view switch (Live, Source, Read), Live by default, the choice remembered per device (prefs) - S/M. Owner: notecap (Sonnet), check the running app first.
18. Built 2026-11-10 (s9c-1110): live code blocks, stated language coloured, indented and completed in Live; see HISTORY.md, "Moved from the plans, 2026-11-10 (s9c-1110 part 2)". The title on the fence is drawn and the corner label is a language picker (built 2026-11-11, bd-1111; CHANGELOG).
Built 2026-11-14 (docsvid): video in a document, a player from this origin; see HISTORY.md, "Moved from the plans, 2026-11-14 (docsvid: L-documents-68)".

## Placed from INBOX, 2026-10-19

- INBOX 1325. **The owner, 2026-10-19, verbatim.** "should thumbnails be stores for documents in the document editor as well for the library page??"
     Recommendation (taken): no stored raster for documents. A board is a drawing, so only a picture tells boards apart; a document is text, and its Library row already shows a live 240-character opening (`routes_documents._preview`) that is current on every save, theme-correct and costs no writes. Instead: a page-shaped card (heading, first lines, first embedded image as the cover) drawn from data the list already has. Next: build the page-shaped card in the Library Documents list.


## Placed from INBOX, 2026-10-27

- INBOX 1407 (Harper false positives): built 2026-10-27, see HISTORY.md "Moved from the plans, 2026-10-27 (docs-1027)".
- INBOX 1408 (focus-mode sidebars resizable): built 2026-10-27, see HISTORY.md "Moved from the plans, 2026-10-27 (docs-1027)".

- INBOX 1562: built 2026-11-03, see HISTORY.md "Moved from the plans, 2026-11-03 (a31d-1103)".

## 22. The diagram builder redesign: design note, 2026-11-04 (INBOX 1613 to 1615, 1621)

Design only. Nothing here was run or rendered; the line cites are from a read of HEAD on 2026-11-04 and the disputed ones were re-checked. Every decision is taken (standing order 3); a build row cites it as "1621 D`n`". Two points are decisions this note makes where the owner's words left a gap (D7 and the chat chip); they are listed under Risks so the owner can overturn them. 1621 supersedes 1546 D9 ("the block pane is a tree, not a canvas") and the dialog-only part of D6; R7 records the retraction in HISTORY.

### 22.0 Verified present at HEAD (do not rebuild)

- Ctrl+Z and Ctrl+Y in the blocks list (diagram-builder.js:403-408); Undo and Redo buttons (:508). On a Documents page `io` is `docUndo()` / `docRedo()` (documents.js:4049), so history, versions and the bin come with it (1546 D5). There is one history; this note adds no second.
- Enter and F2 rename (:411), double-click rename (:548-552), Alt+arrow reorder and nest (:409-416).
- Row-to-row connect: dropping a grip on a block's middle makes a join (`dropAt` op `join`, diagram-pointer.js:78-79).
- A Blocks | Source `.seg` in the dialog (diagram-embed.js:121-127).
- The Documents page already mounts the builder inline for `mmd`: Blocks, Split and Source (documents.js:204-212, :4049); Library Open goes there (library.js:1765); Create already goes through the door (library.js:2283-2287).
- A live reference in notes and documents: `![[Title]]` on an `.mmd` document draws through `mermaidFill.embed` (markdown.js:583; test_diagram_embed.py:111). "Open as a diagram" on chat replies (mermaid-draw.js:504-507).
- The shelf: `{key: "diagram", label: "Diagrams"}` (library.js:392), Download .mmd (:1061-1070).
- A splitter recipe: `.sidebar-resize`, `role="separator"`, `tabindex=0`, `trackSeparatorValue` (sheets-selects.js:317, :338-372), `prefs.set` for per-browser memory, arrows 12 px and Shift 40 px (:454).
- Selection bars with "N selected" (library.js:3772, :8799, :10988) and the recipe row "A list you manage" (DESIGN.md:680).

### 22.1 The model a person must hold (1615 f)

Four things, each made in one gesture, in the dialog and on the page:

- **Shapes** (Box, Rounded, Pill, Circle, Decision, Hexagon): drag one from the Add strip onto the canvas, or press N. Change one by pressing its swatch on the row or its handle on the canvas.
- **Connections** (arrows between shapes): drag from the dot on a shape's edge to another shape, or drop a row's grip on another row. The "Connect to" button does the same by menu.
- **Labels** (the words on a shape or an arrow): double-click, or select and press Enter or F2.
- **Direction** (which way the diagram flows): the four arrows in the top row, which get a caption "Direction" (R4).

Empty-state walkthrough, replacing "Start a diagram" (diagram-builder.js:531-534): three numbered lines inside the dialog, each with its button. "1 Add a shape" (drops a Box), "2 Name it" (opens the label), "3 Connect it" (starts a connection from that shape). It leaves once the diagram has a block.

### 22.2 The model in code

- **D1 The Mermaid source stays the single truth; the canvas is a view of it.**
  - Today the source is the only state: blocks are a parse of it (`diagramModel` parse/print, documents-mermaid.js:247 and :222) and every edit prints the whole source back (diagram-builder.js:54-66).
  - Boards store only `data.mermaid`, capped at 20,000 chars (wb_model.py:242-247, validated at :950); notes store a fenced block (documents-mermaid.js:306).
  - Cost: Mermaid owns the layout. The canvas edits structure (add, move, nest, connect, relabel, reshape), not free x/y (Risks).
- **D2 A diagram object is the existing `documents` row with `file_type` "mmd".** The Library lists it as `kind: "diagram"` (routes_library.py:238-239; filetypes.py:76). No new table, no migration.
- **D3 Reference by destination.**
  - Notes and documents: `![[Title]]`, which already draws live. Nothing new in the renderer. A fenced `mermaid` block stays inline text and is never silently turned into a link.
  - Boards: a diagram object keeps `data.mermaid` as a snapshot and gains `data.diagram_id` (int, ge=1, valid for `DIAGRAM_KIND` only). It is not `ref_id`, which is `MAP_REFERENCE_KINDS` only (wb_model.py:500-506), is stripped on board-library save and import (whiteboard-library.js:1231; routes_board_library.py:253), and routes_graph.py:535-548 warns that ids must be keyed by kind.
  - Snapshot rule: the board redraws from the library row when it can, and when the row's source differs it rewrites `data.mermaid` as an ordinary silent object save. If the row is gone it draws the snapshot, says "The linked diagram was deleted", and drops the link on the next edit. The validator does not check existence, because a deleted row is a valid state.
  - Board-library save and import strip `diagram_id` as they strip `ref_id`: a template does not point at a notebook row.
  - Chat: a reference chip that opens the diagram's page. The model sees the source text (D7).
- **D4 Nothing already embedded is rewritten.** Fences, board objects and `.mmd` rows keep drawing. New and opt-in: "Save to Library" on a fence's menu (beside "Edit as blocks", documents-mermaid.js:402) and on a board diagram object (`wbEditDiagram`, whiteboard-interchange.js:1355). It creates the `mmd` row and offers to swap the fence for `![[Title]]`, or the object for a linked one.
- **D5 Entry stays the one door** (`diagramDoor`, documents-mermaid.js:482). Done semantics by mount: the dialog from a fence or board keeps Done, which writes once; the Documents page autosaves (the document's own save). From the door inside an editor, Done creates the `mmd` row and inserts `![[Title]]` (today it writes a fence, documents-mermaid.js:505-510). The slash menu's Flowchart keeps inserting a starter fence (editor.js:958); Edit as blocks and Save to Library lift it into the library.
- **D6 The diagram's own page is the Documents page's `mmd` mount, in a diagram layout.** No new route and no boot bytes (the router and `lazy-entries.js` are at their caps). What the layout changes: default view Canvas, the file chrome that means nothing for a diagram hidden, the title and an Export menu in the head. Library Open keeps going to `openDocumentFromNote`.
- **D7 Decisions this note makes where the owner's words left a gap.** (a) The canvas is structural, not free x/y. (b) Copy as picture puts a PNG on the clipboard; pasting it into a note, document or chat uses the existing image-paste path, and on a board it makes an image object (a frozen picture), not a diagram object. (c) The chat chip gives the model the source text, within the cap chat already applies to an attached document (R9c reads it from the chat code; the board's 20,000 is not that cap).

### 22.3 The builder page

One view `.seg` in both mounts: **Canvas | Blocks | Source**. It replaces the dialog's Blocks | Source seg (diagram-embed.js:121-127), so there are never three overlapping toggles.

- **Canvas (wide):** the stage in the centre, the blocks list kept at the left as the side menu, both driven by the one `S.sel` (diagram-builder.js:105-106) and the row cache (`reconcile` :139-145). Blocks is today's layout (read-only picture beside the list). Source is today's.
- **Stage:** a wrapper `.dgm-stage` holding the figure `S.fig` and an overlay positioned from `picture.boxes` (diagram-picture.js:10) through the image rect. The overlay is a sibling of `S.fig`, not a child: `mermaidFill` and the empty state call `S.fig.replaceChildren` and would wipe it.
- **Paint hooks:** `fig.onpaint` is a single slot (assigned in diagram-touch.js:60, called at diagram-builder.js:89). It becomes a listener list so zoom and overlay both run.
- **Add strip (top, collapsible):** the labelled tiles of diagram-library.js (`FLOW` :29, `build` :46; `.dgm-tile`, diagram-lazy.css:94).
- **Phone:** the seg gives Canvas the whole width (the fixed 26vh stacked picture, diagram-lazy.css:632-636, is for Blocks only). Pinch exists (diagram-touch.js:46). `wireLongPress` (already on the tree, :566) is also put on the stage: long press selects a node and opens the bar. Edge handles are at least 44 px. The splitter is hidden.

Gestures, one each, with the piece reused or the new piece named:

- **Add:** drag a tile onto the stage. `dropAt` returns null outside `S.pane` (diagram-pointer.js:62) and `dropMark` draws in pane scroll coordinates (:21-29), so the stage gets its own target function `canvasTarget` (stage coordinates, node under the point). A drop on a node adds after it and connects; on empty space an unconnected block (`addBlock` :302).
- **Move:** drag a node; it reorders or nests (`stepBlock` :368, `nestBlock` :374) with feedback on the overlay only. The picture redraws once, on drop (`drawPicture` :69).
- **Pan and marquee:** drag on empty space pans; Shift+drag on empty space is the marquee. Space+drag also pans.
- **Select:** click, Shift range, Ctrl add, Ctrl+A. The bar follows DESIGN.md:680 and the Library's "N selected" bars: N selected, Delete, Duplicate, Shape, Group into a box, Undo, Done.
- **Connect:** drag from an edge handle to a node (new recipe), or row to row (present). Both use `joins` (diagram-joins.js).
- **Rename:** an input over the box calling `beginEdit` (:332) and `relabel` (:320).
- **Shape:** the row swatch and the node's handle open the shape menu (`menuAt` :434, `blockItems` :257).
- **Zoom, pan, fit (1614):** Fit is the default. Zoom in, zoom out, Fit and 100% in a `.dock` corner bar. Ctrl+wheel and pinch zoom about the pointer, arrow keys pan when the stage has focus. Range 0.25 to 5 times fit (5 is `MAX_ZOOM`, diagram-touch.js:8). Zoom resets to fit when the diagram kind changes, not on each edit. `zoomable` (diagram-touch.js:46) is not exported and zooms by `img.style.width` plus scroll, not a transform; the new lazy `diagram-view.js` replaces it and keeps that technique (the overlay maps through the image rect either way). It does not call `wbZoom*` (the diagram files are lazy and d3 may be absent).

New keys: Ctrl+A, Shift+arrows extend, +, -, 0 for zoom, Space to pan, Enter on a handle starts a connection, Esc cancels it. Existing keys stay as in section 0.

New recipes (order 11, recipe row and lint in the same commit, `tests/test_ui_recipes.py`):

- **Edge handle** (connect by dragging). None in the builder; the whiteboard's connectors are sketches on a canvas, a different model (whiteboard-commands.js:255-256, :899).
- **Divider between the blocks and the stage:** not new. It reuses `.sidebar-resize`; only a recipe-index row for "a split inside a dialog or page" is added.
- **Zoom bar:** plain `.dock` first; a variant only if it fails.

### 22.4 Phased rows

Each row is one Sonnet-high agent session, ships alone, and is gated with targeted tests plus `scripts/gate.sh`. R1 to R4 are independent in what they need but share diagram-builder.js and diagram-lazy.css, so they merge one at a time. diagram-builder.js is 646 lines and over its 12 KB target: R5 and R8 move code into new lazy files, each a wrapped IIFE with one export on `diagramModel`, a `LAZY_MODULES` row at the foot of documents-mermaid.js, and no new global names (GLOBAL_NAMES_CAP 9706, GUARDS_CAP 270). A boot caller of a lazy bundle gets a stand-in, not a `typeof` guard.

- **R1 (1613), R2 (1614):** built 2026-11-04, moved to HISTORY ("Moved from the plans, 2026-11-04 (DOCUMENTS_PLAN 22, R1 and R2)").
- **R3 (1615 e), R4 (1615 c, d, f) minus the tester:** built 2026-11-04, moved to HISTORY ("Moved from the plans, 2026-11-04 (DOCUMENTS_PLAN 22, R3 and R4)").
- **R4 left (the blind-tester pass):** taken by R6.
- **R5 (1615 a, b):** built 2026-11-04, moved to HISTORY ("Moved from the plans, 2026-11-04 (DOCUMENTS_PLAN 22, R5)").
- **R6 (R4's list, R6.1 to R6.13):** built 2026-11-04, moved to HISTORY ("Moved from the plans, 2026-11-04 (DOCUMENTS_PLAN 22, R6)").
- **R7 (1621 D5, D6):** built 2026-11-04 except the page head, moved to HISTORY ("Moved from the plans, 2026-11-04 (DOCUMENTS_PLAN 22, R7)").
- **R7 (page head):** Built 2026-11-10, moved to HISTORY.md ("Moved from the plans, 2026-11-10 (s9-1110)").
- **R8a (1621):** built 2026-11-04, moved to HISTORY ("Moved from the plans, 2026-11-04 (DOCUMENTS_PLAN 22, R8a)").
- **R8b (1621):** built 2026-11-04, moved to HISTORY ("Moved from the plans, 2026-11-04 (DOCUMENTS_PLAN 22, R8b)").
- **R8c (1621):** built 2026-11-04, moved to HISTORY ("Moved from the plans, 2026-11-04 (DOCUMENTS_PLAN 22, R8c)").
- **R9a (1621):** built 2026-11-04, moved to HISTORY ("Moved from the plans, 2026-11-04 (DOCUMENTS_PLAN 22, R9a)").
- **R9b (1621):** built 2026-11-04, moved to HISTORY ("Moved from the plans, 2026-11-04 (DOCUMENTS_PLAN 22, R9b)").
- **R9c (1621):** built 2026-11-04, moved to HISTORY ("Moved from the plans, 2026-11-04 (DOCUMENTS_PLAN 22, R9c)").
- **R10 (1621):** built 2026-11-04, moved to HISTORY ("Moved from the plans, 2026-11-04 (DOCUMENTS_PLAN 22, R10)").

- **R11 (blind test, 2026-11-04):** built 2026-11-12 and moved to HISTORY.md ("Moved from the plans, 2026-11-12 (documents-plan: R11/R12)"); the rest are LEDGER rows (documents).
- **R12 (blind test of 0931c35):** owner decided 2026-11-12: `/diagram`, Insert and Done from a document or board list the diagrams made (mmd documents) plus "New diagram" in a dialog of choices; a pick is embedded, New opens the empty builder and Done embeds that file, no silent `Diagram <stamp>` file. Built and moved to HISTORY.md (same heading); the rest are LEDGER rows (documents).

- **R12, R13, R14, R16 (1661 B: find, curve and spacing, both-ways arrows and shapes, edge colour, six templates):** Built 2026-11-10, moved to HISTORY.md ("Moved from the plans, 2026-11-10 (s9-1110)"). R15 (a corner minimap) and the head Export: built 2026-11-10, moved to HISTORY.md ("Moved from the plans, 2026-11-10 (s9b-1110)").

Order: R1 to R4, then R5, R6, R7; R8a after R2 and R5, then R8b, R8c; R9a any time, then R9b; R9c after R9a and R7; R10 after R7.

Mapping: 1613 = R1; 1614 = R2; 1615 (a)(b) = R5, (c)(d) = R4 and R6, (e) = R3, (f) = section 1 and R4; 1621 = R7 to R10.

Help moves with each row (order 13): `ai/help_chat.py`, `ai/help_topics_more.py`, `tests/test_manual_parity.py`. Each row adds its CHANGELOG line and resolves its INBOX entry.

### 22.5 Risks and out of scope

- **Layout is Mermaid's (D1).** "Drag things into place" is delivered as structural placement. This is the main reading the owner could overturn; free positions need a stored layout and a renderer, a separate design.
- **The chat chip and Copy as picture (D7)** are this note's decisions, not owner asks.
- **Render latency.** Drawing goes through a hidden frame (`mermaidRequest` mermaid-draw.js:403; `/mermaid-frame`, app.py:1592-1607), so a drag uses the overlay and redraws once on drop (R8b check).
- **Frame policy.** `MERMAID_FRAME_CSP` (security.py:547) was written for the dialog and the fence; R7 needs a real-browser check (CLAUDE.md section 6).
- **Lazy kinds.** Mind map, timeline and sequence keep blocks-first; no canvas gestures promised.
- **Two writers.** A row can be edited while a note shows it; last write wins, as for any document.
- **Size limits.** `DGB_MAX` 120 blocks and 20,000 chars on boards bound the canvas; a larger diagram gets a message, not a silent cut.
- **Unverified.** Every provider test uses a fake transport; real rendering and drag feel are unverified until each row is driven in the app (CLAUDE.md section 5).
- **Out of scope:** free x/y layout; real-time multi-user editing; new diagram engines or import from images; AI generation (`diagram-suggest.js` untouched); version history beyond the document's own; full Mermaid syntax coverage in blocks.

---

Critique points rejected or changed:

- Point 7, "choose Phosphor icons or a lazy menu builder": chose the lazy builder, but R1 first checks whether `makeMenuItem` already takes an element icon. I did not verify that.
- Point 13, "cite the Library bars instead of a fresh `.dock`": kept a `.dock` for the zoom bar only (the corner bar is a different recipe from a selection bar). The selection bar itself follows DESIGN.md:680.
- Point 9, split of R7 into R7a and R7b: not split. Create already goes through the door (library.js:2283-2287) and Open already reaches the Documents page, so the page is one row once D6 drops the new route.
- Point 2, "use key steps 12 and 40, not 16": kept (12, and Shift 40 at sheets-selects.js:454). I did not confirm the Home and double-click reset the critique lists, so the note does not promise them.
- Point 4, "say what the own page changes": adopted with a different answer from the critique's options. It is the Documents mount in a diagram layout, with no new route. The draft's "full page" mount was dropped.
- Point 6, "a new Canvas | Blocks seg makes three toggles": resolved with a single Canvas | Blocks | Source seg instead of dropping the canvas toggle.
- Point 3, "undo": agreed on the shared history. Not verified: `docUndo` behaviour inside the dialog mount, which uses its own `io` (diagram-embed.js:96-97).

- Audit 160 D23 (open, L): docCmTheme is its own file (documents-cm-theme.js, 1,075 lines); docLivePlugin is still one 1,720-line function in documents-cm.js (1,748 lines now), to be split by responsibility (build, patch, widgets) in a later step.

## Placed from INBOX, 2026-11-04

1679. **Owner, 2026-11-04 16:50Z, verbatim (owner: never Fable, 2026-11-12):** "also can you get fable to take a quick look at and do a deep dive on the diagram builder?? it si still not really learnable and is still quite unintuitive and it feels like it lacks key design features and utility and it just feels very demo and not a complete feature or smth that it usable and easy to understand". One read-only deep dive, findings in `diagram-fable-1679.md` (git history; the file name is historical), then ranked slices built by Sonnet. Owner, 2026-11-05 00:25Z, verbatim: "also on the mermaid diagram, it is soo much better now, but the left panel still needs a bit of a redesign to be more intuitive to use and understand, also the panning and zoom of the right panel feels really awkward and unresponsive and it needs a bit of usability, an ux polishing". Recommendation (taken): (k) the left panel (the outline and blocks pane) redesigned for first use: one clear purpose line, the tree of boxes and lines read top to bottom with what each row does on hover and focus, add and connect where the eye is, and a blind-tester pass before and after; (l) the picture pane's pan and zoom: wheel and pinch zoom about the pointer, drag to pan with momentum, zoom on every input in one frame (no wait for a re-render; the SVG transforms and redraws after), fit and 100% buttons, keyboard pan and zoom, measured input-to-paint latency (under 16 ms) and zoom steps that feel even. Then, 2026-11-05: "shouldnt these be from the outer box not the text?" (the connect arrows sat on a pill's label; fixed 2026-11-05, the shape is read before the label group) and "like make tools and features more accessible and aparrent, beef it up, are there any missing features?? what if I need to make like a sequence diagram or box certain elements?? it feels very rudimentary and basic". Recommendation (taken): (m) sequence diagrams and groups exist but are hidden behind the kind menu and the Arrange menu: a visible kind switcher (flowchart, sequence, mind map, timeline) at the top of the builder, "Box the picked blocks" on the selection bar and the block menu, every tool labelled where it sits, and a gap audit against Mermaid (class, state, ER, Gantt and pie open in Source only today; styling per block, notes and activations in a sequence, edge labels and link styles, icons) with the gaps built in order of use. **(m) built 2026-11-05:** the visible kind switcher (Flowchart, Sequence, Mind map, Timeline: `diagram-kindbar.js`, a new empty diagram of the kind, Undo brings the old one back), Box this block (block menu) and Box them (selection bar), sequence Parallel, Critical and Break boxes (U, C, B), and nine editor bugs from a fresh-eyes tester (handles scale with the block, `&quot;` drawn as a quote, emptied name, hint and pending line at once, `Add a box`, steps buttons duplicating the foot, + and wheel top, pan with nothing to pan). **Gap audit against Mermaid, still open, in order of use:** (1) flowchart shapes the blocks cannot read (cylinder `[( )]`, subroutine `[[ ]]`, parallelogram `[/ /]`, flag `>]`; such a diagram opens in Source), then `classDef`/`class` styling beyond the fill colour, `click` links and Font Awesome icons; (2) sequence: `autonumber`, `box` around participants, `create`/`destroy`, `rect` highlight colour (all open in Source today); (3) Gantt, pie and state diagrams as block kinds (the three most asked after sequence), then class and ER (Source only); (4) a per-edge label position, curve style and a link `id@` animation; (5) markdown strings and `<br>` line breaks in a name; (6) flowchart sub-direction inside a subgraph.

## 23. List styles, decision 40 (INBOX 1696 cc, built 2026-11-08)
**Decision 40.** The marker is the style, so the source and the export agree.
Dots: `-` disc, `*` circle, `+` square, `-` plus two spaces dash. Numbers:
`1.`, `1)`, `a.` and `i.` (the last two count only as a run of two, `a.` then
`b.` or `i.` then `ii.`; `h. i. j.` stays letters). One list is one marker at
one level. The List and Numbered menus restyle the list at the caret as one
undo step; a pasted Unicode dash (U+2010 to U+2014), `•`, `◦` or `▪` at a line start becomes `- `.
Block `docLists`, documents-cm.js. Scout of the bundled CodeMirror:
- Already in prose: fold, multiple cursors, rectangular select, brackets, search, merge view.
- Rows L1 (Enter continues `a.`, `i.`, dash lists) built, see HISTORY 2026-11-08 (DOCUMENTS_PLAN 23 L1 to L5).
- Row L2 was already built (`docPairInput`, documents-prose.js; see HISTORY 2026-11-08).
- Row L3 was already built (the markdown grammar folds list items), see HISTORY.
- Row L4 built, see HISTORY. Row L5 built, see HISTORY.


## 26. Synced blocks, decision 82 (row 5, F1 run 2, 2026-11-11)
**Decision 82 (taken on the recommendation).** A block exists once, in the document it was written in (it carries `^id`). Every other place is a window onto it: `![[Doc#^id]]` shows the block, and its pencil edits the text there. Save reads the source afresh, rewrites that one block (the `^id` stays, so every link and embed still resolves) and saves the document through `PUT /documents/{id}` with the document's own `base_hash`, so the change has a revision and an edit of the same document elsewhere stays.
- **Refused, not merged:** a block changed elsewhere since the box opened (the text is kept), and a block made two by a blank line.
- **Not built:** a copy that stays in step in both places (no second source of truth, no sync engine); a pencil in the block's own document (it is edited there as text); live refresh of other open windows after a save (they update when the document is next drawn).
- Code: `frontend/js/documents-synced.js` (lazy, `LAZY_MODULES.docSynced`), the pencil in `docEmbedNode` (documents-embeds.js), `tests/test_doc_blockrefs.py`; Guide topic `document-synced`.
Reopened 2026-11-14 by the hub (no owner decision behind it): LEDGER L-documents-69 to 71 (synced blocks a, b, c).

**Row 10, a board editable from a document (built 2026-11-11).** The whiteboard is one page-wide instance (`wbState`, `#whiteboard-container`, ids all through 25,000 lines), so there is no second one to mount in a document. A board card (`![[board:12]]`) has Edit here, which lends `#library-view-whiteboard` to a dialog over the document (`documents-board.js`, lazy `docBoard`) and puts it back on close. Whiteboard side, two hooks only: `openWhiteboardBoard(id, { stay: true })`, and a cancelable `wb-leave` event before `wbShowBoardsLanding`.
- **Cost:** while the dialog is open the Library has no board window (closing puts the Library back: its open board again with its camera, or its list); the dialog is modal, so the document cannot be typed in meanwhile.
- **Not built:** the board drawn live and editable inside the page's text flow (needs the whiteboard state made per instance first, a refactor of whiteboard.js that the whiteboard owner has to make).
