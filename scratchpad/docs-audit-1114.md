# DOCUMENTS_PLAN audit, 2026-11-14

Branch `agent/docs-audit-1114` (worktree). Plan read in full, base `40ce39fc` (1484 lines). Plan line numbers are the BASE file's (`~` = approximate).
Grain: one item per owner row, plan row or named bullet; the 1679 gap audit is split into its six numbered gaps.

## 1. Open work (verdict open): 20 = the recomputed LEDGER "Plan file open" for documents (was hand-written 70)

| Plan line | Item | Verdict | Evidence | LEDGER row |
| --- | --- | --- | --- | --- |
| 322 | 1566 sweep of every surface for bordered ghost buttons: Reminders filter chips, icon pickers, add-widget tiles, dark, 390, high contrast unmeasured ("the item stays open") | open | no closing record: `grep -i 'bordered ghost'` in HISTORY and CHANGELOG finds nothing | none |
| 1138 | 24 row 5: cold open under 800 ms at 1440 and 390 | open (partly) | `documents.js:15482` warm-on-idle exists but skips under 720px; no re-measurement in HISTORY | none |
| 1141 | 24 row 8: the long-form choice at first run (comments, highlights, link cards are built) | open | no first-run note-style choice in `onboarding.js` or `settings.js`; HISTORY:52249 only records the brief | none |
| 1143 | 24 row 10 and the owner's idea (~1236): labelled and linked sections with an embedded local graph | open | `documents-graph.js` is the y=f(x) graph block, not section labels | none |
| 1180 | 25 row 4: linters (ruff-wasm, a JS linter) "stay open" | open (partly) | `ls frontend/vendor` has no ruff or eslint; only in-house diagnostics (`documents-code.js:4951` `docCodeScan`) | none |
| 1274 | VC17 Emmet stylesheet syntaxes (scss, sass, stylus, pug, haml, slim) | open (low) | `core/filetypes.py:135-136` aliases scss and sass to css; no stylus, pug, haml, slim types | none |
| 1278 | Brief 60: no frame measurement of the editor (14 rAF, 7 scroll, 3 RO, 4 MO sites) | open | no documents frame sweep in `scratchpad/ui-sweeps`; typing cost is L342 and L-documents-26 | L342 (partly) |
| 1297 | 1308 item 6: board and calendar views of the `base` block | open | `documents-base.js:4` "board and calendar views are not built" | none |
| 1308 | 1308 item 17: note capture gets the Live / Source / Read switch, Live by default | open | no view switch near `#entry-content` (`index.html:1735`); no HISTORY or CHANGELOG record of "notecap" | none |
| 1313 | INBOX 1325: page-shaped card (heading, first lines, first image) in the Library Documents list ("Next: build") | open | no cover or page-card code in `library.js`; only `routes_documents._preview` | none |
| 1456 | 1679 gap (1b): `classDef`/`class` styling beyond fill, `click` links, icons | open | `documents-mermaid.js:54` `DGM_KEPT` keeps `style classDef class linkStyle click` as locked text lines | none |
| 1456 | 1679 gap (2): sequence `autonumber`, `box`, `create`/`destroy`, `rect` colour | open | `diagram-kinds.js:218` returns null for `box|create|destroy` (Source only) | none |
| 1456 | 1679 gap (3): Gantt, pie, state, class, ER as block kinds | open | `diagram-ops.js:20` `DGB_PLAIN` lists state, class, pie as Source only | none |
| 1456 | 1679 gap (4): per-edge label position, link `id@` animation (curve style is built, HISTORY:445 W18 R13) | open (partly) | no `id@` or label-position code in `diagram-*.js` | none |
| 1456 | 1679 gap (5): markdown strings and `<br>` in a name | open | `documents-mermaid.js:102` keeps a markdown string, no editing | none |
| 1456 | 1679 gap (6): flowchart sub-direction inside a subgraph | open | `direction` is a kept line (`documents-mermaid.js:54`) | none |
| 1456 | 1679 (l): pan with momentum, input-to-paint under 16 ms measured | open | no momentum or inertia in `diagram-view.js` or `diagram-touch.js` | none |
| 1452 | Audit 160 D23: split `docLivePlugin` by responsibility | open | `documents-cm.js:27` to `:1933`, 1,906 lines in one function (plan said 1,720) | none |
| 1301, 1479, 1484 | Per-instance whiteboard so a board lives in the page's text flow | open (blocked on a whiteboard refactor) | `documents-board.js` lends the one whiteboard to a dialog; `wbState` is page-wide | L-documents-11 |
| 311 | INBOX 1731 (f): LanguageTool with the real program | open | `documents-languagetool.js` exists; real binary unverified | L-documents-6 |

Open with no LEDGER row (17, not added as instructed): every row above marked "none".

## 2. Built already (verdict built-already): 15

Moved to HISTORY.md ("Moved from the plans, 2026-11-14 (documents-plan audit: found built)" and "... owner rows found built"), pointer left, unless marked "left".

| Plan line | Item | Evidence | Moved |
| --- | --- | --- | --- |
| 274 to 296 | Section 21 code editor to VS Code: p5.js, CSS values, snippets, auto-close, indent guides, fold, multi-cursor, go to line, format selection, comment toggle, keybindings sheet | `documents-code.js:606` (p5), `:976` (CSS values), `:452` (snippets), `:5723` closeBrackets, `:1961` autoCloseTags, `:5741` fold, `:5915` format selection; `documents-ide.js:539` keybindings sheet; `documents.js:4971` comment toggle | yes |
| 310 | Diagram AI left: Ask and Suggestions for mind map, timeline, sequence | `diagram-ai-kinds.js:1` (L-documents-35, HISTORY:55333), `diagram-suggest.js:74` | yes (real-model part stays L893) |
| 516 | Section 10: checker reads only sentence shape; its/it's behind Check with AI | Harper vendored (`frontend/vendor/harper`), `documents-prose.js:24` | yes |
| 1282 | INBOX 788 code templates, snippets library, assistant panel | `documents.js:1940`, `documents-codekit.js:2` | yes |
| 1270 | VC4 merge view against a chosen version | `documents-ide.js:66` `unifiedMergeView({mergeControls})`, `entry.js:47` | yes |
| 1139 | 24 row 6: failed save says why, retries, draft kept | `documents.js:1524` `keepDocEditLocally`, `:2449` to `:2464` | yes |
| 1472 | Diagram builder 251 row listeners | `diagram-builder.js:583` to `:595` delegate on `S.tree`; 13 `addEventListener` in the file | yes |
| 1412 | R9a left: no tray Open row for a diagram | `router.js:30` `diagram` in `ROUTE_OBJECTS` | yes |
| 349 | 1546 P4 left: 1.7 KB over the 12 KB target | `gzip -c diagram-builder.js` = 11,995 bytes | yes |
| 885 | Section 20 decision 3: BACKLOG steps 9 to 13 "stay open" | builder is the editor, PNG/SVG/.mmd export `diagram-embed.js:28` to `:57` | yes (sentence rewritten) |
| 320, 324, 326, 328 | Owner rows 1621, 1615, 1614, 1546 | built by section 22 R1 to R10 and 1546 P1 to P5 (each already pointed to HISTORY) | yes (4 rows) |
| 1456 (1a) | 1679 gap (1a): cylinder and parallelogram shapes now read | `documents-mermaid.js:50` | left (subroutine and flag shapes not verified) |

## 3. Decided-unbuilt (verdict decided-unbuilt): 11, each with a reason in the plan, no change

| Plan line | Item | Reason in plan |
| --- | --- | --- |
| ~392 | PHP mode refused | +28,563 gzipped, 10.6% of the bundle |
| ~395 | CSV mode refused | a CSV has no syntax; a table view is another feature |
| 693 | "Today" button in the documents dock | third door onto one page |
| ~720 | Code bar with Copy in Live fences | caret trap, 8px row; bar stays in Read |
| 745 | Atomic ranges | measured: no two-character jump |
| 765 | Mod+click underline while the key is held | tooltip already shows it |
| 834 | "How far through" figure (17d) | scrollbar and outline mark say it |
| 1271 | Tag offers (VC5) | a document has no tags |
| 1292 | Video in a document (1308 item 1) | decision 2: no player |
| 1479 | Synced block: copy in step in both places; pencil in the block's own document | decision 82: no second source of truth |
| 1484 | Live refresh of other windows after a synced save | decision 82 cost accepted |

## 4. Ledger step

`| documents | 70 | ...` became `| documents | 20 | 14 | 1 | 0 | 20 | 35 |` (`scripts/ledger.py counts` recomputes the total column, 85 to 35, and the `all` row to 503 and 1201). `tests/test_ledger.py tests/test_plan_hygiene.py` pass.

## 5. The 20 `documents` blocked-hardware rows: could they be done here?

Checked: Chromium only in `/opt/pw-browsers` (no Firefox or WebKit), Playwright and CDP available, `hasTouch`/`isMobile` contexts used by `scratchpad/ui-sweeps/touch.js`, CDP throttling used by `animcost.js`; `java`, `cmake`, `gcc`, `soffice` installed; github release (Pyodide 314.0.7: HTTP 200), huggingface.co (200) and languagetool.org (200) answer through the proxy; no `llama-server` or model (`llama-dev.sh check`); 4 shared cores.

| Row | Truly needs hardware? | Can be done here? | Evidence |
| --- | --- | --- | --- |
| L879 Write with AI, model on | real model | yes, slow: fetch a small GGUF (HF 200), build llama.cpp (cmake, gcc present); small CPU model only | `llama-dev.sh` fetch and build; `check` reports server and model missing |
| L880 Brief 69: desktop webview, dark rows, large SQL result, touch | webview and device | partly: dark rows, large SQL result, touch by emulation yes; desktop webview no | `touch.js` hasTouch; THEME=dark in `lib.js` |
| L881 suggestion mode, touch long-press at phone width | no | yes: emulated touch long-press at 390 | `touch.js`; `docProseFix` is plain JS |
| L882 .docx in Word, Format on large file, non-US chords, docx extra removal | Word only | mostly: Format on a large file, chords via `key` events, extra removal in a scratch dir yes; LibreOffice (`/usr/bin/soffice`) stands in, real Word no | `which soffice` |
| L883 autocorrect with IME on a phone keyboard | real keyboard | partly: CDP `Input.imeSetComposition` drives composition; real phone keyboard no | CDP sessions in `animcost.js` |
| L884 iOS and Android native selection UI | device | no | native selection handles are outside the page |
| L885 IME composition in the engine, blocked-request fallback | no | yes: CDP IME composition plus Playwright `route.abort()` | as L883 |
| L886 breakpoint lane tap size on touch | no | yes: a `getBoundingClientRect` number in a hasTouch context | `touch.js` measures target sizes |
| L887 screen reader on `aria-current=location` | screen reader | no for the claim; the attribute and AX tree can be checked headless | `documents-comments.js:438` sets it |
| L888 Draft it box heights with a real model | no (misfiled) | yes: heights follow text length; fake transport answers of several lengths | CSS layout only |
| L889 writing desk Stop mid-pass, slow backend | no (misfiled) | yes for Stop: a stub backend with a delay; real thinking prompts need a model | row says stand-in answers in 150 ms |
| L890 real-clipboard Ctrl+V from Word and phone | Word, phone | partly: Word-style HTML via the clipboard API in Chromium yes; real Word and phone no | rich-paste walker, plan section 20 decision 2 |
| L891 print dialog, image paste, phone IME, Safari/Firefox, screen reader, Harper cost | mixed | partly: Harper cost (CPU throttle), image paste, `page.pdf` print CSS yes; Safari, Firefox, real dialog, screen reader no | chromium only installed |
| L892 diagram shelf on real touch, 390 shelf kinds hidden | no | yes: hasTouch emulation at 390 | `diagram-touch.js`, `touch.js` |
| L893 diagram: real inference, touch, light 390, over 10 blocks perf, Windows, SR, print | mixed | partly: touch, light 390, perf under throttle, `page.pdf` yes; real model slow; Windows and screen reader no | as above |
| L894 12 ms per key; ClearType greyscale | Windows display | per-key ms yes (CDP throttle; L342 and L-documents-26 already measure it); ClearType no | `key323.js` method in L-documents-26 |
| L-documents-5 model summary of revisions | no (misfiled) | not hardware: unbuilt feature work, build against a fake transport; only quality needs a real model | row: "there is no model-written account of the revisions" |
| L-documents-6 LanguageTool real program | no | yes: `java` present, languagetool.org 200, install through the app's Extra | `extras.py:665` url |
| L-documents-23 code-run.js with the Pyodide extra | no | yes: pyodide-core 314.0.7 answered 200 | `extras.py:593` version |
| L-documents-28 Python runtime timing | no | yes, noisy: needs the extra; 1 s versus 6 s is readable on shared cores | same |

Doable here fully or mostly: L879 (slow), L881, L882 (not Word), L885, L886, L888, L889 (Stop), L892, L-documents-5 (a feature, not hardware), L-documents-6, L-documents-23, L-documents-28. Partly: L880, L883, L890, L891, L893, L894. Device or human only: L884, L887.
