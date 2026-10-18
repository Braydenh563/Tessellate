# documents-1018: Sonnet agent, DOCUMENTS_PLAN open work (Brief 42 remainder, bugs-1017 B18 B19 B20 B23 B39, Brief 75 VC rows)

Worktree agent-ac526d0d9067dc04a, server :8792 (data /tmp/mm-docs1018). Boot JS gzip is at its cap: every JS change is in a lazy bundle (documents*.js, harper-worker.js); `tests/test_boot_budget.py` after each JS edit.

## Step 0 audit (grep of code and HISTORY, 2026-10-18)

| Item | State | Evidence | Size |
| --- | --- | --- | --- |
| Brief 42 indent guides, active line gutter | built | DOCUMENTS 25 row 3; `.cm-activeLineGutter` bold, markers measured (HISTORY "DOCUMENTS 24 and 25, Brief 76") | - |
| Brief 42 code completion and snippets per language | built | `DOC_CODE_SNIPPETS` documents-code.js:437, `docNativeSnippets`, Emmet, `doccomplete.js` | - |
| Brief 42 minimap, merge view, lint panel, fold all, diff and Dockerfile modes, VB | built | documents-ide.js:48 (minimap pref), :108 (`foldAll`), filetypes.py:75,78,94,95 | - |
| Brief 42 comments, highlights | built | `doccomments.js` sweep; `==x==` and `%%x%%` | - |
| Brief 42 link cards with a viewer, labelled and linked sections with a local graph (24 rows 8, 10) | open | no `linkcard`, no section labels in documents*.js | L, design |
| Brief 42 linters (ruff-wasm, a JS linter) (25 row 4, OPEN 1071) | open | no vendored linter; size decision | L |
| VC6 Harper dialects | open, built this run | harper-worker.js `DIALECTS`; the select had 3 values | S |
| VC6 Harper personal dictionary | not needed | `DOC_GRAMMAR_SKIP_KINDS` drops every Harper spelling lint; the app's own dictionary decides spelling | - |
| VC5 FlashText link and tag offers | open | FlashText only in `ai/taxonomy.py` | M |
| B18 template library: curated text sections for general documents | open | `DOC_TEMPLATES` documents.js:1557 is 7 whole-page prose templates and 10 code ones; no insert-a-section library for prose | M |
| B19 snippets: click inserts (built); drag with a ghost cursor and edge autoscroll | open | documents-codekit.js `docSnippetRow` has click and menu only, no `draggable` | M |
| B19 run and debug tools for other document types | partly built | Run/Debug for js, ts, py, html, sql (HISTORY Briefs 69 to 71); no more languages | L, per language |
| B20 manage mode for lined documents (rearrange by line or element) | open | Alt+Arrow move line absent from keymap; the block bar says "a drag handle was left out" documents.js:21442 | L, design |
| B23 live-view tables: right-click menu, row and column edges, selection, drag | open | one kebab at the header row end (`DocTableMenuWidget` documents.js:7628); no contextmenu, no row or column grips | M |
| B39 Jupyter in the document editor | open | only a `# %%` Python "Notebook" template (documents.js:1794); no `.ipynb` read or write | L, owner decision |
| OPEN 1054 (24 row 11): one '?' per documents section | open | 78 ids, 0 popovers of their own | S |

## Order

1. VC6 dialects (S).  2. B19 drag with ghost cursor and autoscroll (M).  3. B23 right-click and row/column grips (M).  4. B18 text sections library (M).  5. B20 as a smaller step only if the keymap lacks move line (S); the full manage mode is L and needs the owner.

## Owner questions

- B39: build `.ipynb` import and export as a converter to the `# %%` notebook document (no Jupyter kernel, no vendored Jupyter; cells run in the Python sandbox), or leave notebooks as `# %%` files? Recommendation: converter only.
- B20: is "manage mode" a drag handle on every line and block in Live view (heavy), or Alt+Up and Alt+Down moving the line or block plus a keyboard "Move block" row in the palette? Recommendation: the second.
- Linters (25 row 4): vendor ruff-wasm (about 8 MB wasm) lazily behind the Packages system, or skip? Recommendation: a Packages extra, not bundled.

## Log

- done 9561081: step 1 VC6.
- step 2 B19 drag: documents-codekit.js (docSnippetDragStart, docSnippetScrollSpeed, docSnippetDragFrame), library-lazy.css .doc-drop-ghost; sweep snippetdrag1018.js 13/13 (ghost within 2px of the caret; bottom edge scrolled 0 to 1,319px in 0.7 s). Chromium's synthetic drag sends no repeat dragover while still, so the sweep nudges 1px. Not verified: a real mouse drag in the desktop webview, Firefox (draggable buttons).
- done 38ffce5: step 2 B19 drag (above).
- step 3 B23 part 1: right-click or hold on a Live cell opens the table menu at the pointer (docTableMenuAtPoint, one contextmenu listener ahead of the suggestion), nine new commands (move row/column, sort A-Z and Z-A, select row/column/table); pure model in the DOC-TABLE region, tests/test_doc_table_manage.py (25 checks), sweep tablemanage1018.js 20/20 at 1440 and 390. Menu is 19 items, 546px tall at 1440x900. Not verified: a real touch hold on a device.
- next: B23 part 2, edge grips (select, menu, drag reorder, plus) in a lazy bundle; then B18 sections library.
- (history) step 1 VC6: five dialects in the worker, select, preference and pair table (documents.js DOC_VARIANT_FAMILY), help line. Sweep spellingdialects1018.js 12/12.
