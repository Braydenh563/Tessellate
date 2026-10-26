# The documents editor: a professional dev plan

**Status: written by direct instruction; to be executed after the plans in
[UI_MODERNISATION_PLAN.md](UI_MODERNISATION_PLAN.md),
[AGENT_SKILLS_REFORM.md](AGENT_SKILLS_REFORM.md),
[MINDMAP_PLAN.md](MINDMAP_PLAN.md), [PLAN.md](PLAN.md) and
[REDESIGN.md](REDESIGN.md) are done, in the order
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

Three options. The plan below is written for **B**; A is its first step
either way; C is recorded so the next session does not re-derive it.

**A: Keep the textarea, add a backdrop (one session).** The
"highlight-within-textarea" technique: a `div` behind a transparent-ink
textarea, same font, same padding, same wrapping, holding the text with
`<mark>`s where the findings are. Underlines appear in Source; a click
lands in the textarea, sets the caret, and the existing findings menu opens
for the finding at that offset (`docFindingAtOffset` already does this).
Cheap, offline, and it answers the sentence in the instruction directly.
What it does not give: inline widgets, block handles, a single model for
Live and Source, decent tables. **Do this first regardless**, it is the
bridge, and it is measurable in a day.

**B: CodeMirror 6, vendored (recommended).** MIT-licensed, no build step
needed (a single prebuilt bundle under `frontend/vendor/`, ~350 KB, the
licence file beside it, the same way `d3.v7.min.js` and `p5` are vendored
today). It gives, natively and offline: decorations (underlines that are
clickable, widgets, block backgrounds), a real undo history, search and
replace, folding, syntax highlighting for every file type this editor
already opens, line numbers, IME and mobile input that a hand-rolled
contenteditable never gets right, and a plugin API. **Live preview becomes
decorations over the markdown source**, headings rendered as headings,
`**bold**` shown bold with the markers hidden until the caret enters them,
links as chips, images and embeds as widgets, which is exactly Obsidian's
architecture and the one with the most published prior art. Markdown stays
the single source of truth; every existing endpoint, revision, export and
AI action keeps working unchanged. Source view is the same editor with the
decoration set switched off. Split and Read stay as they are.
Cost: the D2/D3 work in flight is partly superseded (CM6 has its own undo
and selection API: D2's toolbar is kept as the *UI*, re-pointed at CM6's
`dispatch`), and `EDITOR_SURFACES`' textarea assumptions in `editor.js`
have to be re-pointed at one adapter (`docSurface()`: get/set text,
selection, replace range): which is also what finally lets the note
composer and the documents editor share one implementation.

**C: A block editor over `contenteditable` (Notion's model).** Rejected
for this app. It needs a second document model (blocks) beside the
markdown one, a serialiser both ways, and it makes every existing feature
that reads offsets (selection → chat, revisions, the AI edit, exports)
a translation problem. The Notion-style features people actually want
(a `/` menu, drag handles, callouts, toggles, columns) are all achievable
as decorations and widgets in B.

**Made in this document: B, with A as Phase 0.** The ROADMAP entry should
not be started until a session has read CM6's licence into
`frontend/vendor/` and confirmed the bundle loads under this app's CSP
(no `eval`, no inline styles: CM6 injects a stylesheet through the CSSOM,
which the CSP allows; verify before building on it).

## 5. The phases

Each phase ends green, measured, pushed, with a HANDOVER.md entry that
says what was not verified. Measurements use the Chromium sandbox; the
editor sweep is `scratchpad/ui-sweeps/editor.js` (from the D2/D3 branch),
extended per phase.

### Phase 0: the bridge: click an underline, see suggestions (1 session)

1. **Backdrop underlines in Source** (§4 A). Findings from `docProseFound`
   drawn as `<mark class="doc-finding doc-finding-{kind}">` behind the
   textarea; the mark's kind decides the underline (spelling: wavy red;
   style: wavy blue; repeated word: dotted), the same three the Live view
   already uses so the two views agree.
2. **One click opens the suggestions.** `click` (not only double- or
   right-click) on a finding opens the existing menu at the caret, with the
   suggestions **ranked**: the dictionary's nearest words by edit distance,
   then the notebook's own vocabulary (`docCompleteWords`), then "Add to
   dictionary" and "Ignore in this document". Keyboard: `Alt+Enter` on a
   finding opens the same menu (the VS Code gesture).
3. **A findings count that is a control.** The status bar's "No
   suggestions" becomes a chip, `3 suggestions`, that opens the panel;
   `F8` / `Shift+F8` step through findings (VS Code again). The switches
   (Autocorrect, Suggestions) leave the status bar for Settings → Documents
   and the ⋯ menu; a status bar states, it does not configure.
4. **Suggestions explain themselves.** Every finding carries a one-line
   *why* ("'their' here is probably 'there'": only when a rule is certain;
   "this sentence is 61 words") and the panel groups by kind with counts.
   Acceptance: in Chromium, type a misspelt word in Source → an underline
   appears within 300 ms → one click opens a menu whose first item replaces
   the word → `F8` moves to the next finding; the same in Live.

### Phase 1: chrome: three questions, three places (1 session)

1. **Header = identity.** Left: a breadcrumb (`Documents › Design system
   notes`) that is also the title field; right: save state as one word
   with a timestamp on hover, the view control, one ⋯. The file-type select
   moves into the ⋯ (it changes once per document); AI edit and extract
   become items in the selection toolbar and the ⋯. Target: **≤ 5 controls
   in the header**, one height (`--control-h-lg`), one baseline.
2. **View = one segmented control, two options in the row, two behind
   it.** Edit / Read as the segment; Split and Source as choices inside
   Edit's menu (a small chevron), remembered per document. Rationale:
   Live is what people mean by "edit"; Source and Split are modes, not
   destinations. (Obsidian: Edit / Read, with Source as a setting.)
3. **Formatting = for a selection, or by `/`.** The 26-control strip is
   retired as a permanent row. D2's floating toolbar is the formatting UI
   (bold, italic, strikethrough, code, link, highlight ▾, heading ▾, quote,
   list ▾, AI ▾); block insertion is the `/` menu with a visible "＋" at the
   start of an empty line (Notion's affordance). The strip survives as an
   opt-in "Always show formatting" setting for people who want it, which is
   what `#doc-toolbar-mode` already remembers.
4. **Status bar = facts and one action.** `22 words · 5 min` on the left,
   `3 suggestions` (a chip) and the goal ring in the middle, `Ln 7, Col 45`
   on the right. Nothing else.
5. **Sidebar = one list, one outline, one panel width.** Documents / Outline
   / Backlinks as three tabs with counts, a collapse that remembers, and at
   ≤ 1100px it becomes a sheet from the left (§5 Phase 6). "Recent" is the
   default sort of the Documents list, not a section of its own.
   Acceptance: `surfaces.js`'s document family reports header ≤ 44px,
   one control height, chrome above the first line ≤ 96px at 1280
   (PLAN D1's own gate), and at 820px the sidebar's labels are unclipped
   (scrollWidth = clientWidth on every sidebar label).

### Phase 2: the engine: CodeMirror 6 as the surface (2 sessions)

1. Vendor CM6 (`@codemirror/state`, `view`, `commands`, `search`,
   `language`, `lang-markdown`, the languages the file editor already
   detects) as one bundle under `frontend/vendor/codemirror/` with its
   `LICENSE`; a `tests/test_vendor_licences.py` that asserts the licence
   file exists beside every vendored bundle.
2. `docSurface()`, the one adapter every existing feature talks to: text
   get/set, selection get/set, `replaceRange`, `onChange`, `coordsAt`. Every
   `$("doc-content")` read in documents.js and editor.js goes through it.
3. **Live preview as decorations**: headings, emphasis, code, links as
   chips, task checkboxes that toggle, block quotes and callouts with a
   left bar, images and embeds as widgets, hidden markers that reveal when
   the caret enters the range. Source = the same editor with the decoration
   set off.
4. Findings as CM6 decorations (Phase 0's backdrop retired), undo as CM6
   history (D3 retired), find/replace via CM6's search panel restyled onto
   the app's field recipe, folding on headings, the gutters via CM6's line
   numbers. The existing `/` menu, `[[` autocomplete and selection → chat
   re-pointed at the adapter.
   Acceptance: `editor.js` sweep: type in Live, switch to Source, Ctrl+Z
   undoes the Live edit (D3's own gate); a 20k-word document keeps keydown
   → paint < 30 ms (PLAN P4's gate, measurable now); every existing
   documents test passes; `node --check` and the DOM lints green.

### Phase 3: blocks and structure: built, 2026-09-12

All five items. The record, with every measurement and every decision, is in
HISTORY.md ("From DOCUMENTS_PLAN.md Phase 3", items 1 to 3 and items 4 and 5);
what the phase left open is in `archive/agent-remaining/documents-phase4.md`.

**The syntax this phase decided, kept here because later phases read it**:
`:::columns` opens a columns block, `:::column` starts the next column, `:::`
closes; an image's options are pipe-separated and read by shape, so
`![[river.jpg|300|center]]` and `![A river|300|center](/media/river.jpg)` mean
the same thing.

### Phase 4: the connected document (1 session)

1. **Backlinks with context**: built, 2026-09-12. `GET
   /documents/{id}/backlinks` answers for notes and documents at once, the
   panel shows the sentence around each link with "link back", and unlinked
   mentions sit below with "link", which rewrites the mention in the source
   that wrote it. Decisions in section 11.
2. **Block references** (`^block-id`): built, 2026-09-12. A paragraph carries
   `^an-id` at the end of its last line; `[[Doc#^id]]` links to it and
   `![[Doc#^id]]` embeds it, from a note, a map node or a chat. The model is
   `DOC-BLOCKREF-BEGIN`..`END` in `documents.js` (run in node by
   `tests/test_doc_blockrefs.py`), the "/" menu's "Link to this block" writes
   the id and copies the reference, the marker hides in Live and is stripped
   from Read, and `scratchpad/ui-sweeps/docblockref.js` measures the lot
   (25/25). Decisions in section 11.
3. **Outline drag-to-reorder** (PLAN D6), breadcrumbs, sticky outline: built,
   2026-09-20. The record is in HISTORY.md ("Moved from the plans,
   2026-09-20", DOCUMENTS_PLAN.md Phase 4 item 3).
4. **Command palette and shortcut sheet from one table**: built, 2026-09-20.
   The record, including the `Ctrl+K` decision the plan left open, is in
   HISTORY.md ("Moved from the plans, 2026-09-20", DOCUMENTS_PLAN.md Phase 4
   item 4).
5. **Daily notes** and **templates gallery**: built, 2026-09-20. The gallery
   was already there with six templates, each carrying a description
   (`scratchpad/ui-sweeps/doctemplates.js`); daily notes were the row that
   needed the decision first, and it is section 14. What was built from it is
   one template and one recognition: New from a template now offers Daily
   (seven rows), the document it makes is titled with the ISO day, and the
   Timeline's day bucket accepts a note *or* a document with that title, so
   the "Start today's note" offer beside a day already written as a document
   is gone. Measured before and after in `scratchpad/ui-sweeps/docdaily.js`,
   11 of 11: before, 6 templates with no daily and the bucket offering to
   start a second page beside a document titled `2026-09-20`; after, 7
   templates, the created document titled `2026-09-20` with `# 2026-09-20` as
   its first line, 0 "start today's note" offers, 1 "Today's document" offer,
   and the calendar glyph on the row.

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

PDF (the print stylesheet), markdown, self-contained HTML, the markdown bundle
with its images, the Word export behind an optional extra, and import of
`.docx` and `.html` to markdown are all built; see HISTORY.md "Moved from the
plans, 2026-09-13". The python-docx row is closed too: `core/extras.py` has
"Export to Word (python-docx)" and the 501 points at it in Settings (checked
2026-10-04).
   Superseded 2026-10-10 (the owner, INBOX 765): Word files are read and
   written in the browser with Mammoth (read `.docx` to HTML) and docx (write
   `.docx` from the editor's model), both vendored under `frontend/vendor`
   with their notices in THIRD_PARTY.md. The python-docx extra, its route
   and `docexport.to_docx` are retired (Brief 42, docs42b, 2026-10-10).

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

Placed 2026-10-05. Exists: CodeMirror 6 vendored
(`frontend/vendor/codemirror`, `CM6`), with Lezer grammars for JS, Python,
CSS, HTML, JSON, YAML and Markdown and legacy modes for C, C++, C#, Java,
Kotlin, Go, Rust, Ruby, Swift, R, SQL, shell, TOML, XML, diff, Dockerfile and
INI; Emmet (`frontend/vendor/emmet`); Harper grammar in a worker
(`harper-worker.js`); `documents-code.js` (4,400 lines). Open, for one Opus
agent that audits what renders first (section 1 of CLAUDE.md) and then builds:

- Languages missing: Visual Basic (`vb`, `vbScript` legacy modes), p5.js (JS
  plus p5 completions from the vendored `p5.min.js`), PHP stays out (section
  above, the size).
- Per-language completions and snippets: CSS property values for the property
  under the cursor, Python, JS, Java, C#, C, C++ keywords and common forms;
  bracket and tag auto-close, indent guides, fold, multi-cursor, go to line,
  format selection, comment toggle, a keybindings sheet in Help.
- Where each is used: every code surface (documents, code blocks in notes,
  chat code, board code blocks) shares one engine and one set of options;
  every prose surface gets the grammar check.
- Help moves with it (standing order 13). Measure with a Playwright sweep per
  language; no new required dependency (CLAUDE.md, the owner's offline rule).

## Built, Phase 1 (the chrome), 2026-09-09

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", DOCUMENTS_PLAN.md) on 2026-09-09: a plan holds open work only.

## Built, Phase 2 step 1 (the engine, vendored and verified under the CSP), 2026-09-09

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", DOCUMENTS_PLAN.md) on 2026-09-09: a plan holds open work only.

## Built, Phase 2 steps 2 to 4 (the engine under the editor), 2026-09-09

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", DOCUMENTS_PLAN.md) on 2026-09-09: a plan holds open work only. What is left open from this phase is in `archive/agent-remaining/documents-engine.md`.

## Built: Phase 0

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", DOCUMENTS_PLAN.md) on 2026-09-09: a plan holds open work only.

## Built, Phase 3 (tables, blocks, embeds, properties, columns), 2026-09-12

Moved to HISTORY.md ("From DOCUMENTS_PLAN.md Phase 3", two entries) on
2026-09-12: a plan holds open work only. What the phase left behind is in
`archive/agent-remaining/documents-phase4.md`.

## Placed from INBOX: 107d, the segmented mini bars

"Note in the redesign documents and where it is supposed to that I want to get
rid of and redesign these mini menu bars as they are in a couple popups around
the place and they desperately need a modern redesign or alternative", with a
photo of `#doc-ai-verb`, the Edit / Write / Remove bar in this tab's AI
assistant panel.

**Done, 2026-09-12, and the decision is in `docs/DESIGN.md`** ("A choice
control's selected segment is `--accent-surface` behind `--on-accent`"), which
is where it belongs: it is a rule about a recipe, not about this tab. The
short version, so it is not re-litigated here: the two radio-backed bars
(`#doc-ai-verb`, `#graph-layout`) were the app's own segmented control drawn
with a different set of numbers, and the selected option was a 14% accent tint
behind body-coloured text with a drop shadow under it, which is not a selected
state anyone can see across a popup. They read as the other twenty-eight `.seg`
groups now. Measured before and after with
`scratchpad/ui-sweeps/segbars.js`; the numbers are in DESIGN.md and in the
commit.

**The label size this found is closed too** (`9586542`, a later pass the same
day). `.seg button` set no `font-size` at all, so it inherited whatever tab it
was on: measured at three sizes across the app, 16px on the tab strips, 13.6px
on two choice controls and 12.8px on three more. Every choice control is on
`--text-md` now, the tab strips deliberately are not. Re-measured here: all
nine segments across `#doc-ai-verb`, `#doc-view-seg` and `#graph-layout` read
13.6px.

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
  - **`php` refused.** `@codemirror/lang-php` is not a legacy mode but a full
    Lezer grammar that also pulls in `lang-html`, because PHP is embedded in
    HTML. On its own it costs +98,144 raw and **+28,563 gzipped: 10.6% of the
    bundle for one language**, in a local notebook whose documents are notes
    and plans. Revisit if anyone asks for it; the number is here so the answer
    does not have to be re-derived.
  - **`csv` refused, permanently.** There is no CSV mode in CodeMirror and
    there should not be: a CSV has no syntax, so a highlighter would colour
    its commas and nothing else. What a CSV wants is a table view, which is a
    different feature.
  `scratchpad/ui-sweeps/docviews.js` asserts all five, including that `php`
  and `csv` highlight *nothing*, so adding a mode later has to come with an
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
  **Found while measuring and still open:** `enhanceSelect` (app.js ~18427)
  rebuilds every `<select>` as a shell with a `<button>` opener and takes the
  native element out of the tab order, so `select.focus()` anywhere in this
  app focuses nothing and a `keydown` bound to a select never fires. Two
  listeners in this batch were written that way before a sweep caught it.
  The lint exists since 2026-10-04, `tests/test_select_focus.py` (`.focus()`
  or a key listener on a page `<select>`, directly or through a binding; 0
  offences, and proved against drift).
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
  under this project's AGPL-3.0 (ANALYSIS.md's licence constraint).
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

**Found while doing this, not fixed.**
- `scratchpad/ui-sweeps/docviews.js` fails on "the view menu has no
  line-numbers row" and then throws on a null click. Reproduced against the
  branch before any of this landed, so it is an older gap in the view menu
  rather than a regression: either the row goes back or the sweep stops
  asking for it.
- The suggestion menu draws the same check icon on every one of its five
  word rows, so the words read as five identical actions rather than as the
  answer with the actions underneath. The separating rule is there and it is
  doing the work on its own. A real spell menu differentiates them by more.
- The checker still reads only the shape of a sentence. Its/it's, agreement
  and tense are behind "Check with AI", which is a button press rather than
  a pass, for the reason `docProseHeader` records.

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
in `archive/agent-remaining/editor-intelligence.md`.

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

**Not built, deliberately**: a "Today" button in the documents dock. The
template gallery is two clicks from the same place, the Timeline's day view is
the surface that knows about days, and a third door onto one page is what this
decision exists to refuse.

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

**1. The toolbar's own state: built.** This is the one that was only ever
waiting for the tree. Before the engine, deciding whether the caret sat inside
`**bold**` meant counting asterisks from the top of the document on every
keystroke; the tree exists now for the decorations, so `renderDocToolbarState`
resolves one node and walks its ancestors, which costs the depth of the
markdown at the caret and not the length of the document. It runs on the same
beat as the caret readout, which is the beat that already exists.

Measured at eleven stops in a document with one of everything: `h1` in a
heading, nothing in plain prose, `bold`, `italic`, `code`, `h2`, `ul`, `task`,
`ol`, `quote` and `link`, each with no other button lit. 17 of the strip's 41
`data-md` buttons carry `aria-pressed`, and the other 24 are the ones that
always insert something new and have no state to be in: a button that is not a
toggle must not tell a screen reader it is one. The caret resolves with side
`-1`, so a caret just past the final `d` of a bold word still reads as bold,
which is what makes "keep typing in bold" and "the button says bold" the same
answer. A task item lights `task` and not `ul`, although a task list is a
bullet list in the grammar, because the more specific one is the one pressing
the button would turn off.

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

**3. The `Mod+click` affordance: the note is out of date, and nothing is
built.** It says "there is no affordance saying so beyond the tooltip".
Measured, a link chip in Live carries `cursor: pointer` and
`title="Ctrl+click to open https://example.com"`, which is a pointer inviting
the press, the chord named, and the destination shown before it is followed.
That is what Obsidian offers for the same gesture. The one thing that would
improve it is the underline-while-the-modifier-is-held that VS Code draws, and
it costs a window-level key listener with a reset on blur for a hover hint
that is already available by resting on the chip. Left unbuilt on purpose; a
row here rather than a fourth session rediscovering the tooltip.

**4. The table cell's ten-row menu: built, as a change to the shared recipe.**
Rows, columns, alignment and the whole table read as one list of ten, and
finding "Align centre" in it meant knowing the order. The bullet that recorded
this said correctly that `kebabMenu` had no separator and that this was
therefore a change to the recipe and to DESIGN.md rather than a phase item, so
that is what it is: an item may carry `group`, a name, and `kebabMenu` draws a
hairline wherever the name changes. Callers declare meaning, never pixels, and
an item with no `group` behaves exactly as before, so every other menu in the
app is untouched.

The name is not drawn. A heading over every three rows would make this menu
seventeen rows tall, and what makes a list scannable is the break rather than
the word. Measured after: 10 items, 3 hairlines at 1px tall and 172px wide,
`role="separator"` on each so the grouping reaches the accessibility tree,
10 `menuitem` roles and 3 separators, and `wireMenuKeyboard` walks
`[role="menuitem"]`, so a hairline is never a stop on the way down. The recipe
index carries it and `tests/test_ui_recipes.py` holds the ratchet: a command
table past five rows declares its groups, and the separator element and its
stylesheet rule both still exist.

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
  `contrast.js` with `ONLY=document` are the gates. One half of 17d was
  decided against there (a "how far through" figure, the scrollbar and the
  outline mark already say it).

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
   **Reopened by the owner, 2026-10-06**: mermaid.js is to be vendored and
   lazy-loaded; BACKLOG, "Diagrams: mermaid as the interchange format",
   steps 8 to 13.
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
6. **A flowchart fence draws as one, by a parser of our own** (2026-10-05,
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

### Phases

| Phase | Brief | Deliverable | Measured by |
| --- | --- | --- | --- |
| I1 run, preview, test | 69 | Built 2026-10-10 (HISTORY "DOCUMENTS Brief 69, I1"); what is left is in `agent-remaining/ide1-1010.md` | `scratchpad/ui-sweeps/code-run.js`, 46/46 at 1440 and 47/47 at 390 |
| I2 the debugger | 70 | Built 2026-10-10 (HISTORY "DOCUMENTS Brief 70, I2"); what is left is in `archive/agent-remaining/debug70-1010.md` | `scratchpad/ui-sweeps/code-debug.js`, 32/32 at 1440 and 31/31 at 390 (js, ts, py: breakpoint, three steps, a watch, the exception stop) |
| I3 the IDE shell | 71 | Built 2026-10-10 (HISTORY "DOCUMENTS Brief 71, I3"); what is left is in `archive/agent-remaining/shell71-1010.md` | `code-keys.js` 34/34 keys exercised, palette 61 commands (40/40 and 67 with Brief 70's debugger rows); `ide-shell.js` 19/19 (four heights kept across a reload); `ide-split.js` 10/10 |

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
| 6 | fix | A save that fails says why and retries itself; a draft survives a reload and a crash | `test_never_lose.py` documents rows green; keystroke to saved under 1 s | 3, 4 |
| 7 | redesign | The list row: the Actions button beside the title, not over it (8 overlaps at 1440). **Not built, Brief 76: it remakes INBOX 722** (the owner, 2026-10-06: the ⋮ overlays the row and never reserves a column; held by `test_a_rail_rows_title_takes_the_full_width_and_its_menu_overlays_it`); the title already fades under the ⋮ while it shows. Recommendation: keep the overlay and count a row's own ⋮ as no overlap in `deepen72a.js` | overlap 8 to 0; the title's right edge left of the button | 7, 11 |
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
| 8 | expansion | A minimap, off by default, one toggle in View (Brief 42's bar) | toggle present; its width remembered | 11 |
| 9 | fix | Built 2026-10-10 (HISTORY "DOCUMENTS Brief 69, I1"): a run past 2 s lists in `/activity` and stops from it | the run lists in `/activity` and stops from it | 5 |

**Briefs.** 42 (rows 3, 4, 8), 69 to 71 (row 5), 73 (row 9), 76 (rows 1, 2,
6, 7, with section 24).

## Built, the sidebar redesign (INBOX 115), 2026-09-12

Moved to HISTORY.md ("Moved from the plans, 2026-09-12", DOCUMENTS_PLAN.md) on
2026-09-12: a plan holds open work only. What is left open is in
`archive/agent-remaining/doc-sidebar.md`.

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

409. **The owner, 2026-09-24, verbatim, with screenshots of Settings,
    Templates, the persona list, a .json document with the formatting bar
    over it, and the Write tab's AI assistant bar.** "templates cant be
    edited, I want the generation of persona icons to be improved and I also
    want to auto generate other icons in other places like potentially the
    user chat bubbles?? idk. also the degree of indenting is shallow, I think
    it should be more prominent. also this edit/write/remove bar is ugly and
    doesnt suit a modern app, it needs to be restructured/redesigned or
    transformed somehow to be better." Read from the screenshots: built-in
    templates have no edit (only added ones do); the persona marks are a
    blob on a flat disc, too alike at 20px; the prose formatting bubble (B,
    I, S, highlight, code, link, H, quote) draws over a code document, where
    none of it applies; the indent guides step 2 spaces; the AI assistant
    control is a filled segmented pill. Placed: orchestrator, in this order.
    **Built 2026-09-24**: templates editable, built-ins included (3a769ed,
    sweep `templates.js`); persona marks a generated face, closest pair of
    23 at 40px 5.6% before, 29.8% after (259b743, `namemarks.js`); the
    user's own mark on their chat bubbles and the persona picker's
    (0e88b6e, ede4f2a, `chatmarks.js`, bubble box unchanged). The code
    selection bar and the indent step are 7ab7eec. The AI assistant bar
    is closed: the owner's later line (INBOX 431 (f), 2026-09-27) says they
    like that dialog's design and the edit/write/remove pill, so nothing
    is open here.

## Placed from INBOX, 2026-10-05 (OPEN.md triage)

- ~~`docRevealForSuggest` will not bring a table-cell word into view~~ Not reproduced at 1440 or 390; the account is in HISTORY.md, "Moved from the plans, 2026-10-05 (small-1005: the small open items)" (`revealcell.js`).
- ~~`editor.js` sweep describes the retired editor~~ Re-pointed at `docSurface()`: 78 of the old 89 checks remain and pass; the account is in HISTORY.md, "Moved from the plans, 2026-10-05 (small-1005)".

## Placed from INBOX, 2026-10-07 (next PR)

- **Live code blocks in a prose document** (the owner, verbatim: "also I want
  to be able to make special code blocks where the code editor works and code
  autofill and suggestions work for the stated language in that codeblock",
  with a fenced ```html block in Live view). A fenced block with a language
  becomes an embedded code editor in Live: syntax colour, indenting, bracket
  matching and the completion the code documents already have for that
  language (documents-code.js), its language shown and changeable on the
  block, Escape or the arrow keys out of it back into the prose. Stored as the
  same fenced Markdown, so Source, export and print are unchanged.

## Placed from the owner's list, 2026-10-10

Entries are the owner's words, then the recommendation. Bugs come first.

### Bugs

- "I cant two finger trackpad zoom in or out on documents or images on the ocr workspace?"
  Recommendation: pinch zoom (ctrl+wheel from a trackpad) on the PDF and OCR viewer and on images; test with a synthetic wheel event at the viewer. No brief carries it; Brief 42 is the nearest document brief.
- "The note capture subtab formatting toolbar wont open :("
  Recommendation: reproduce from the Notes Capture subtab, then fix the toolbar's open state and measure it. No brief carries it; Brief 42 is the nearest.
- "Gemini might have removed the spell checker??" (the owner's words in the Gemini thread: "you removed spellchecker.py")
  Recommendation: keep src/tessellate/vendor spellchecker.py and make Brief 35 (unused vendoring gone) leave it in, with a test that it loads; writing checks are Brief 42 (DOCUMENTS_PLAN section 21).
- "I saved a website as a bookmark but the icon didnt change"
  Recommendation: a saved bookmark takes the site's icon at save time and refreshes it on the next fetch; the link card in Brief 42 shows it. No brief carries the bug itself; Brief 42 (link cards) is the nearest.

### Design requests

- "on vs code selected lines have their line number bolded, the line subtly bordered and there are also indentation lines on vs code as well"
  Recommendation: match VS Code's selected-line gutter, line border and indent guides in the code editor, measured against the VS Code screenshot set. Also carried by Brief 42 (the code editor to VS Code standard).
- "also I want a better and more cardlike rendering of links or special liks like bookmarks and maybe even the ability to choose special icons or colours for bookmarked websites."
  Recommendation: build link cards for bookmarks and embedded links with an icon and colour choice, and a viewer for them. Also carried by Brief 42 (embedded link cards with a viewer).
- "The document editor and whiteboard and mindmap still have many design issues, functionality bugs, poor usability, lack features, and need improvement."
  Recommendation: audit the document editor against VS Code and wordcraft in DOCUMENTS_PLAN section 21, and take the whiteboard and map rows from Briefs 36. Also carried by Brief 42.
- "And we should massively improve, expand, refine and better integrate long form note taking."
  Recommendation: the long-form path (document editor) gets the same comments, link cards, highlights and slash menu as the rest of the app; the first-run style choice is Brief 42. Also carried by Brief 42 (the long-form preference at first run).

### Ideas

- "Idea: on long form notes and documents, you can define topics, or use special characters, commands etc to label and link sections of documents on the ui, highlight or smth. You can visually connect ideas across the current document and link them, with reasons, you can have a local graph of linked ideas available for the current document and can even embed and render the graph in the document which"
  Recommendation: a Phase row in DOCUMENTS_PLAN for labelled and linked sections with reasons and an embedded local graph, built only after highlights (Brief 42) and the graph's local pane (GRAPH_PLAN Phase 4). Also carried by Brief 42 (the labelled and linked sections idea).

### Vendored capabilities to use, 2026-10-10 (Brief 75)

The owner: "make sure all the vendored repositories are made full use of. I want maximum utility." Ranked by the utility to the surface; `scratchpad/vendor_use.py` prints the counts ("available N, called M") and `tests/test_vendor_utilisation.py` ratchets them, so a row that lands raises its floor in the same commit. Each is a lead from a lower-bound count: grep the call site before building (CLAUDE.md section 1).

- **VC4, CodeMirror's merge view against a chosen version** (M, rank 4). `@codemirror/merge` is not in `codemirror/package.json`; the version diff is hand-built (`docDiffLcs` to `docDiffHunks`, `documents.js` lines 11260 to 11400). With autosave a diff against "the last save" is moments old, so the use is the chosen version: accept or reject one hunk in the editor. Measure: the bytes `codemirror.min.js` grows by (795,151 now), and rejecting one hunk restores exactly that hunk's lines (a node test on a three-hunk fixture).
- **VC5, FlashText link offers** (rank 5): built 2026-10-18, see HISTORY.md "OPEN.md rows closed, 2026-10-18 (open-1018)". Tag offers were not built (a document has no tags).
- **VC6, Harper's own dictionary and the other three dialects** (S, rank 6). The worker uses 3 of 29 `Linter` members; `import_words` and `export_words` take a personal dictionary (names and jargon from the notebook) and `ignore_lints` keeps a dismissed finding dismissed; `Dialect` offers 5 and `docSpellingVariant` passes two (US, UK), leaving Australian, Canadian and Indian. Measure: findings on a fixture of 10 proper nouns drop to 0 with the dictionary loaded; the spelling setting lists five dialects and each flags its own variant of "colour" or "center".
- **VC7, the `diff` and `dockerFile` modes already in the bundle** (S, rank 7). `legacy modes` 15 of 18 called; `diff`, `dockerFile` and the `sql` factory are bundled and no file type offers them (`core/filetypes.py` lists 26 types, none a diff or a Dockerfile). Zero bytes. Measure: two rows in `FILE_TYPES`, and a `.patch` and a `Dockerfile` highlight in the editor (token classes counted in a Playwright run).
- **VC13, the lint panel and fold-all in the palette** (S, rank 13). `lint` is 5 of 12 (gutter and next/previous only; `openLintPanel` and `lintKeymap` unused), `language` has `foldAll`, `unfoldAll` and `toggleFold` unused. A list of every problem in a source file is one panel. Measure: the panel lists the same count as the gutter markers on a file with 5 seeded errors; fold-all folds every top-level block of a 200-line fixture.
- **VC17, Emmet's stylesheet syntaxes** (L, rank 17, lowest). Emmet is fully used (6 of 6 functions) but 4 of its 10 syntaxes are passed (html, css, xml, jsx); scss, sass, stylus, pug, haml and slim need a file type to apply to, and the matching highlight mode (`@codemirror/lang-sass`) is not vendored. Measure: only after a file type exists; an abbreviation `p10` in a `.scss` document expands to `padding: 10px;`.

## Placed from Brief 60, 2026-10-10 (the measured census)

- `documents.js` holds 14 `requestAnimationFrame` sites, 7 scroll listeners, 3 `ResizeObserver` and 4 `MutationObserver` (WORLD_CLASS 26.5, `scripts/handlers.py --list`): the second-largest wake-source count after `whiteboard.js`. No frame measurement of the editor yet; `frames.js` has no documents surface.

## Placed from INBOX, 2026-10-10 (code as documents)

- INBOX 788, the owner: "can you add code templates as document templates as well??", "maybe even add a code modules library like with the whiteboard and mindmap??" and "a way to better interact with the ai as a coding asistant like in vs code??" Owner: an Opus brief after the running ones: code templates in New document, a code snippets library on the whiteboard and mind map library pattern, and an assistant panel beside the code editor (explain, fix, write tests, apply as a diff with undo; Needle or the deterministic tools with no model).

## Placed from INBOX, 2026-10-11 (Files, Recordings and Links; libraryup)

- INBOX 827, the owner 2026-10-11, verbatim (screenshots: a file's "Text extracted from this file" box; the empty Recordings tab; a link's details): "it is also a little hard to read and view the extracted text on the file rows in the files subtab and I think that dropdown area is a little poorly designed. can there also be a better empty state and design for the recordings subtab?? also these link details are poorly designed as well and I want to be able to customise link highlights drag links together to form folders, change the icons on them, and more, the whole links/bookmarks tab needs an upgrade"

Decisions made (the Links half extends WORLD_CLASS D9 and Brief 42; do not re-decide):
- L1. Extracted text: the disclosure is a quiet row (DESIGN "Row actions"), not a bordered button; open, the text sits in a reading column (body size, 1.6 line height, page breaks marked "Page 2"), up to 50vh with a fade, Copy and Open reading as quiet buttons on the disclosure row, and a find box when the text passes one screen.
- L2. Recordings empty state from DESIGN's empty-state recipe: an icon, one line, Record and Import audio, and a second line saying a meeting's recording and its transcript land here.
- L3. A link's details: the card shows icon, title, site and a two-line excerpt; the full extract is behind "Show page text" in the L1 reader, never a wall of raw lines; the URL is a quiet copyable chip.
- L4. Folders: drag a link onto another to make a folder (named "Folder", renamed in place), drag into and out of folders, and New folder in the bar; folders nest one level.
- L5. Each link and folder takes an icon (the site's own, an app icon or an emoji) and a highlight colour from the palette tokens, from its kebab menu and from the details card.
- L6. More from the read of Raindrop, Pocket and browser bookmark managers, ranked by how often a person meets it: sort and view (list, cards), tags, a read-later state, duplicate finding, import and export of browser bookmarks HTML. Built in that order after L1 to L5.

Rows (owner: libraryup, Opus, after canvasdepth3): R1 to R6 build L1 to L6, each a commit with a test, measured at 1440 and 390, help moving with it (standing order 13).

## Placed from INBOX, 2026-10-19 (INBOX 1308: the gap audit)

Read from the code against Notion and Obsidian. Sizes S, M, L. Nothing here is built yet this run; the app already has callouts, toggles, columns, tables, footnotes, wiki links, backlinks, the slash menu, find and replace, outline and versions.

1. Video and audio embed from a link or a local file in a note (Notion "Embed", Obsidian `![[file.mp4]]`) - M.
2. Citations: a reference list built from footnote-style keys (Obsidian citations plugin) - M.
3. A block's own link (heading links exist in documents.js; a paragraph's does not, to verify) - S.
4. Built 2026-10-26 (docs5-1026): see HISTORY.md, "Moved from the plans, 2026-10-26 (docs5-1026)".
5. Synced blocks: one block shown in two notes, edited in either - L.
6. A database view of notes by property (Notion, Obsidian Bases): table, board, calendar - L.
7. Inline date and reminder mention that creates a reminder (Notion "@date") - S.
8. Page cover and icon picker parity with Notion's gallery - S.
9. Web clipper fields on a note's properties - M.
10. Canvas block: a board embedded and editable in place - M.
11. Equation cross-reference (`\eqref`, a number that follows the equation); numbering by `\tag{n}` is built (HISTORY, docs5-1026) - S.
12. Table: column sort, filter row, formulas - M.
13. Built 2026-10-26 (docs5-1026): the Read view takes a progress line; see HISTORY.md.
14. Template variables exist (documents.js, documents-codekit.js); check they cover time and the cursor place - S.
15. Export a note as a slide deck from its headings - M.
16. **The owner, 2026-10-26, verbatim:** "can you add an easier and guided way to write out mathematical equations and symbols like with word or desmos?" A guided equation editor over the existing TeX renderer (`docMathRender`, documents.js): Insert equation (slash menu, Ctrl+K, a toolbar row, Alt+= as Word), a live-preview box where typing `x^2`, `sqrt`, `/`, `pi`, `>=`, `alpha` becomes structure (Desmos and Word linear format: `a/b` becomes a fraction, the caret moves into slots, Tab to the next slot), a symbol palette in groups (Greek, operators, relations, arrows, sets, calculus, matrices) with a search, structure templates (fraction, root, power, subscript, sum, integral, limit, matrix, cases), inline or display, the TeX written into the note so it stays plain text, editable by clicking the rendered equation. No heavy library: own parser or a small vendored one under its licence, lazy-loaded, measured against the boot cap - M. Owner: docs7 (Opus, design).

## Placed from INBOX, 2026-10-19

- INBOX 1325. **The owner, 2026-10-19, verbatim.** "should thumbnails be stores for documents in the document editor as well for the library page??"
     Recommendation (taken): no stored raster for documents. A board is a drawing, so only a picture tells boards apart; a document is text, and its Library row already shows a live 240-character opening (`routes_documents._preview`) that is current on every save, theme-correct and costs no writes. Instead: a page-shaped card (heading, first lines, first embedded image as the cover) drawn from data the list already has. Next: build the page-shaped card in the Library Documents list.

