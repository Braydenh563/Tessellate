# Deep audit 2026-10-31: docs (document editor, slash menu, prose checks, find and replace, templates, autosave, undo, export, print, mermaid, AI edit)

Fable suite, surface 5 of 12. Server on 8852, fake model on 11600. Drives hd1
to hd5 (Playwright, 1440 and 390, dark; every `/documents` request counted per
step) and an API probe. Documents: the seeded four, a 58,740-character "Audit
big document" (2), templates and throwaways made during the run. Observed
unless marked code.

## Rows

| Row | Sev | Kind | Finding | Evidence | Where | Verified | Fix | Size |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DC1 | high | security | **Locking leaves the document's words on the page.** After `lockNow()` the editor state is emptied and the title cleared, but the text survives in `#doc-ai-diff` (1,385 characters of the AI diff, headings and body), `#doc-replace-list` (match excerpts), `#doc-outline` (every heading, also in `title` attributes), `#doc-crumbs` (the title), `#doc-list` and `#doc-sidebar-list` (titles and previews), `#doc-prose-panel` (finding lines quote the words around each typo) and the dashboard's recent-documents card (`#dash-grid`). | hd4 lock-panels `hits`, `attrs`; hd3 lock-where (`doc-prose-panel` held "zebraword") | `app.js:860` `LOCK_PURGE_IDS` names only `doc-live`, `doc-preview` and `library-docs-list` of the document surface | run | Add the eight ids to the list, or purge by a `data-holds-notebook` attribute so new panels are covered by default; a test that locks with every document panel open and greps `document.body` for a sentinel word. | S |
| DC2 | high | bug | **The AI assistant panel sits on top of the lock screen.** With `#doc-ai-panel` open, lock: the element under the Unlock button is `#doc-ai-instruction`, under the password field `#doc-ai-scope`; a 3 s click on `#lock-submit` never lands and only Enter unlocks. The panel (and its diff, DC1) stays readable while locked. Modal dialogs and popovers are stashed and reopened correctly (the replace dialog was). | hd5 lock-with-ai `probe.submitAt`, `clickable`; lock-with-replace for the good case | `app.js:781` stashes `dialog:modal, :popover-open`; the AI panel is a non-modal `role=dialog` | run | Stash non-modal panels too (`[role=dialog]:not(.hidden)`), or give the lock overlay a z-index above every panel; same sweep for the writing desk and the help sheet. | S |
| DC3 | med | perf | A big document with many findings makes typing stutter: 58,740 characters, 3,633 suggestions; a one-character dispatch costs 14 to 37 ms of synchronous work with 204 ms long tasks behind it, and with the suggestions panel open five keystrokes logged twelve long tasks up to 130 ms (the panel re-renders 121 rows per keystroke). Two scroll jumps cost 162 ms each. First open took 0.4 s on one run and about 4 s on another (not stable). The findings pass itself is 10 ms; the render is the cost. 1028 D7 windowed the pass; the paint is next. | hd3 big-latency `dispatchMs`, `lt`, panel; big-scroll; hd1 big-doc `typeLT` 209, 215 | `renderDocProse` `documents.js:18230`, `docCmRepaintFindings`, the prose panel renderer | run | Decorate only the viewport's findings (CodeMirror `ViewPlugin` with `view.viewport`), render the panel at idle and only when it is open, cap the panel at the nearest 50 with a "more" row. | M |
| DC4 | med | ux | Replace in every document: after "Replace all" (one match, one document) Ctrl+Z in the editor does nothing, because the document is reloaded (`GET /documents/3` twice) and the history starts again; only the toast's Undo works. One replacement costs eight requests (`POST contents`, `GET /documents/3` x2, the 200-row list, backlinks, bookmarks, link-offers, `PUT /documents/3`). With 357 matches in 3 documents it runs straight away; undo is the only guard. | hd3 replace-run `r`, `undo`; hd4 replace-list-open | `runDocReplace` `documents.js:14185`, `openDocReplace` `:14089` | run | Apply the current document's replacement through the editor as one transaction (history keeps it) and reload only the others; a confirm line when more than one document changes. | S |
| DC5 | med | a11y | `#doc-type-button` reads "File type of this document" while showing "Markdown" (label-content-name-mismatch, serious, 1440 and 390). At 390 `#doc-counts` fails target-size and the Read view's `#doc-preview` is a scrollable region nothing can focus. | hd1 axe-doc; hd2 phone-axe; hd5 phone-axe-edit | `documents.js:221` (opener), Read view container | run | Label "File type: Markdown" from the text; `tabindex="0"` on the preview; 24 px on the counts button. | S |
| DC6 | med | ai | A two-character model answer replaced a 1,272-character document: the diff said "Change 1 of 1 · +1 -37", the button "Replace with this", no warning, one click. The AI edit log keeps a revert, but nothing says "this answer is a hundred times shorter than the text". | hd1 ai-panel (`afterLen: 2`), hd4 ai-diff-open | `acceptDocAiEdit` `documents.js:13237`; `routes_documents.py:1139` returns the answer as is | run (fake model answers "ok") | A size and shape check before the diff: an answer under a tenth of the target, or one that drops every heading, shows "The model sent much less than the text. Replace anyway?" and never a primary button. | S |
| DC7 | med | perf | Opening the Documents tab loads the last document and then the one asked for: `GET /documents/4` then `GET /documents/3` (six requests, twelve long tasks up to 185 ms); every return to the tab refetches the 200-row list; using a template refetches it twice. | hd1 open-3 `reqs`, `lt`; templates `reqs`; hd3 switch-away-and-back | `loadDocumentsNow` `documents.js:1015` opens `docs[0]` before the asked-for id lands; `app.js:1200` | run | Skip the default open when an id is pending; keep the list for the session and patch it from save answers; one refetch per change. | S |
| DC8 | low | bug | The API edits an archived document (`PUT` on an archived id answers 200 with the new text) and maps an unknown `file_type` (`exe`, `../../etc`) to `md` silently rather than refusing it. | API probe | `routes_documents.py:727`, file-type coercion | run | 409 for an archived document unless `unarchive` is asked; 422 naming the valid types. | S |
| DC9 | low | ux | Word goal: `-5` fails the field's own validity ("Value must be greater than or equal to 0") yet the submit closes the dialog with no goal and no message; the field has no maximum. | hd3 word-goal-neg | `documents.js:15407` (`Math.max(0, …)`) | run | `reportValidity()` before closing; `max="1000000"`. | S |
| DC10 | low | arch | The fallback find bar (`#doc-find-bar`, `#doc-find-input`, `#doc-find-count`, `#doc-replace-one`, `#doc-replace-all`) and its handlers (`documents.js:2681` to `2740`) exist only for the textarea that CodeMirror has replaced; with the engine mounted the toggle opens CodeMirror's own search panel and the bar never shows. | hd1 find (`bar: false`, focus `cm-textfield`, count ""), code | `index.html` find bar, `documents.js:2755` | run | Remove the bar and its handlers with the textarea path, or keep one find UI and wire it to the engine. | S |
| DC11 | low | a11y | The templates dialog opens with focus on a ghost button rather than the chosen template; the list is a `radiogroup` whose arrow keys do move the preview. The suggestions panel reads "Fix 991" and the chip "3633 suggestions nearby" (what is nearby?). | hd1 templates `focusOnOpen`; hd3 big-latency `panel.head` | `openDocTemplateDialog` `documents.js:2265`; `documents.js:18266` | run | Focus the selected radio; "Fix all 991"; "3,633 suggestions in view". | S |
| DC12 | low | perf | Typing one line sent three `POST /documents/link-offers` (136-byte bodies), one per 700 ms pause; a steady typist sends one every pause of every paragraph. | hd1 type-pause; hd3 link-offers-body | `documents-prose.js:328` `DOC_LINK_OFFER_QUIET_MS` | run | Ask at the sentence end (`.`, Enter) or after 2 s, and not for a paragraph already answered. | S |
| DC13 | low | arch | Sizes: `documents.js` 24,437 lines, 673 functions, 232 `addEventListener` against 7 `removeEventListener`, `docLivePlugin` 1,602 lines, `docCmTheme` 1,076, `renderDocOutline` 298. | counts | files | code | Split: engine mount and theme, live decorations, prose, find and replace, export and print, AI panel. | L |

## 1028 docs rows re-verified

| Row | Now | Evidence |
| --- | --- | --- |
| D1, D2 autosave in flight, dirty during typing | fixed | hd3 type-during-save-8s: a 2.5 s PUT, typing behind it, second PUT lands, "Saved" and `dirty: false` at the end, server holds all the text |
| D4 `doc-edit-draft` on lock | partly | hd1: a 57-character `doc-edit-drafts` record remained after lock; hd3: none; content not read. `doc-positions` (scroll places) remains |
| D6 history persisted per keystroke | fixed (code) | `docHistoryPersist` serialises at the store's 600 ms pause (`undo-store.js:28`); the store is empty after lock |
| D7 prose pass over the whole document | fixed (window), paint open as DC3 | chip says "nearby"; findings 10 ms on 58,740 characters |
| D8 ASCII-only spelling | fixed | "café", "Zürich", "naïve", "Māori", "kōrero" not flagged; "Teh", "quikc" flagged |
| D13 contents cap | fixed | `POST /documents` with 600,000 characters: 422 in 9 ms (`MAX_CONTENT` 500,000) |
| D14, D15 link safety | fixed (code) | `safeHref` drops controls; `docOpenLink` goes through it |
| D17 blank title | fixed (code) | `docFillBlankTitle` |
| D3, D5, D9 to D12, D16, D18 to D40 | not re-run | |

## Coverage

| Area | Driven | Notes |
| --- | --- | --- |
| Open from the tab, by id, after a tab switch | run | request chains in DC7 |
| Typing: pause, continuous, during a slow save | run | no request mid-typing; one PUT per pause |
| Spelling and prose: typos, diacritics, panel, Fix | run | panel region, "Fix 2" |
| Slash menu: open, filter, insert (TOC) | run | 72 rows, listbox, `aria-activedescendant`; fits at 390 (354 x 386) |
| Find (engine panel), Replace in every document, undo | run | DC4, DC10 |
| Templates: dialog, arrows, use | run | 17 templates in two groups; new document made |
| Statistics, history (revisions), word goal, outline, sidebar tabs | run | |
| Export md, zip, html, docx; print setup | run | 23, 26, 62, 266 ms; print setup dialog opens (`doc-print-go` focused), `window.print` not reached in the run |
| Mermaid in Live view | run | rendered as an `img.md-mermaid-img` by the app's own layout (`mermaidFlowLayout`), no library |
| AI edit (fake model), accept, AI history, revert | run | DC6 |
| Delete, undo toast, restore | run | one DELETE; undo restores |
| Lock with panels open; unlock | run | DC1, DC2 |
| Phone 390: Read view on open, Live view, typing, slash, AI sheet, templates, replace | run | AI sheet full screen; replace dialog 342 x 488 with 44 px buttons and 32 x 18 switches |
| API: caps, bad bodies, 404 ids, revisions, exports, stale `base_hash` (409), archived and deleted edits, list limits | run | DC8 |
| Comments, bookmarks, backlinks, import file, revisions restore, archive from the UI, PDF export, Read-view mermaid, the code editor | not driven | |

## Already good

- Autosave is one request per pause and none mid-typing; typing during a slow save lands in a second save with the right label at the end (D1, D2).
- The slash menu has a listbox with `aria-activedescendant`, filters as you type and inserts in place.
- Spelling ignores diacritics and names; the chip and the panel agree on the count; the panel offers a fix per finding.
- Exports are fast and named after the title; the zip holds the markdown.
- The replace dialog is stashed on lock and reopened on unlock; the undo store and the editor state are emptied on lock.
- The API refuses a 600,000-character body, a 201-character title, a negative offset, a billion-row limit, a stale `base_hash` (409 with the current text) and names the field each time.
- The delete confirm names the document; the toast's Undo restores it.

## Not verified

- Read-view mermaid: in the rendered view `#doc-preview` held no mermaid element and no "graph TD" text in the run (the preview may render lazily); not claimed either way.
- Print output and PDF; docx contents; the import flow; comments and bookmarks; whether the kept-draft record (D4) holds text.
- On a phone a document opens in Read view; which visible control reaches the editor was not found by name (the `[data-doc-view=live]` button was used).
