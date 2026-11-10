# laglist-1108 remaining

Branch `agent/laglist-1108`. Port 8796, data `/tmp/laglist-data`.

## Done
- Item 2, list styles: `mdList.item` (markdown.js, MD-LISTS block) is the one list-line parser for the renderer. The list gets the class `md-<key>` (`md-ul-circle`, `md-ol-1-paren`, ...); `01-forms-settings.css` and `DOC_EXPORT_CSS` turn the class into the marker. `*`, `+`, a two-space dash, `1)`, `a.` and `i.` are read; letters only as a run and never inside a paragraph; a change of marker starts a new list. Tests: `tests/test_md_lists_1108.py`. Checked in a browser with `getComputedStyle` (list-style-type and `::marker` content), in the app and in the export iframe (12 lists, all as expected).
- Gzip: the parser cost 488 bytes against a ratchet with 18 spare, so `toggleEntryPrivacy`, `generateEntryTitle` and `removeEntryTitle` moved from menus.js to entry-menu.js (lazy, their only caller). Total 251,634 of 251,980.

## Left
- `a)` and `i)` (bracket letters) are text in the renderer; the editor never writes them (it parses them). Add only if the editor starts writing them (needs `.md-ol-a-paren` rules in both stylesheets).
- Roman numerals past 59 stop continuing a run (`roman` in `mdList.item`).
- Item 1, settings search lag: `getClientRects` in `settingsIndexHeads` pays the section's pending style (155 to 219 ms at 4x CPU) after a large DOM insert. The layout-free signature lead gave no reliable gain in 3 interleaved A/B pairs, so settings-find.js is unchanged. A real fix has to avoid reading layout in the build at all: build the index from the DOM tree without `getClientRects`, or build it in idle slices after first paint.

## DOCUMENTS_PLAN section 23, rows L1 to L5 (scouted, not built)
- L1 (S): `docListEnter` (documents-prose.js:1863) already leaves an empty item, but Enter on a filled `a.`, `i.` or dash item uses the markdown keymap, which continues only CommonMark markers. Needs a continue step in the Enter handler (documents-cm.js near 2126) that calls `docLists.parse` and writes the next marker (`docLists` already has `toAlpha`, `toRoman` and the renumber filter), plus a harness case in `tests/_doc_lists_harness.js`.
- L2 (S): prose has no `closeBrackets`; `docCodePairs(ext)` (documents-code.js:6099) feeds it for code files only. Needs a prose pairs list (`(`, `[`, backtick; `*` only with a selection), an exclusion inside code spans, and care that `[[` still opens the link menu (documents-prose.js:1799 notes the `[]` case).
- L3 (M): folds exist as `docHeadingFold` and `docCalloutFold` (documents.js:16992, 17289, previewable files only). A list-item fold is a third `foldService` that folds the deeper-indented lines below an item; the fold gutter (documents.js:16886) is already on, so it is the service, the chevron styling and a test.
- L4 (S): `Mod-g` runs `gotoLine` for code and returns false in prose (documents.js:16224); the palette row is `code: true` (documents.js:3126). Dropping the `previewable` guard loses the find-next binding in prose, so it needs another key (for example `Mod-Alt-g`) and a palette row without `code: true`.
- L5 (M): prose autocompletion offers only the `[[` picker; the bundled `autocomplete` is only configured for code and IDE files (documents-code.js:4809, documents-ide.js:391). Needs a `#tag` source that reads the tag list the tag fields use (`tag-suggest.js`, lazy) and an `override` for prose; check it does not fire in headings (`# `) or code.
