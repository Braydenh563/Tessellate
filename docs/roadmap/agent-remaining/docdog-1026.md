# docdog-1026: document editor dogfood (INBOX 1358)

Driven as a student at 1440x900 and 390x844, mouse and keyboard; scripts live in the session scratch dir, not the repo. Not pushed.

## Done (by class)

- Block-prefix toggles stacked (f967074): H1 to H6, List, Numbered, Task, Quote now switch (`mdLinePrefixEdit`, 19 cases).
- Paired controls split by wrapping (f967074): Undo at y=124 and Redo at y=160 at 1440; pairs are one flex item each.
- Missing universal shortcuts (8e1a7d3): Ctrl+U was dead, Ctrl+H missing; pre/post marks toggle off; hiding the toolbar kept no focus.
- Block continuation and exit (1e5310d): Enter on an empty quote now exits; Tab on an ordered item renumbers for its level.
- Feature lost in the CodeMirror move (3ae9cf1): image paste and drop did nothing; Word list paste arrived as flat text.
- Leftover rows (2bf4a29): an emptied new document stayed in the list after a tab switch (dog3d-1026:8).

## Measured, fine

- 8,221-word document: Live dispatch-to-frame median 23 ms (p90 51), Source 31 ms (p90 62); 20 real keys 773 ms Live, 877 ms Source.
- Phone 390: phone bar 53 px, every button 44x44, no horizontal overflow beyond the off-canvas sidebar.
- Text size reaches Live headings (h1 23 / 26.5 / 33.1 px at small / medium / large); line spacing reaches body lines (18 / 21 / 26 px compact, 24 / 28 / 35 relaxed) and deliberately not headings (fixed 1.25). docs3-1026:11 is not a bug.
- Export: `.md` prepends `# Title` only when the first heading differs from the document title (`docexport.with_title`); by design.
- Verified working: persistence, rename, caret restore, kept-edit toast after reload, table Tab, slash menu, rich paste cases, md/html/zip/docx exports.

## Found, not fixed

- Live scroll worst frame (dogfix-1026, profiled, not fixed): `doclivescroll.js`, 8,200 words, 80 jumps of about 400px at 40ms, 1440x900. Three runs: Live worst 67 / 117 ms with 1 and 6 long tasks (53 and 441 ms), Source worst 50 / 67 ms with 1 and 2 (52 and 122 ms); median 17 ms both. CPU profile (200us): Live native `(program)` (style, layout, paint) 2795 ms against Source 1456 ms; CodeMirror's own `measure` is 168 against 284 ms, so the cause is not script and not the decoration build (it already walks `view.visibleRanges`). `closeActionMenusOnScroll` (182 / 147 ms), `syncEdgeFade` (117 / 163) and `keepOutlineRowInView` (108 / 81) are the first forced layout after each scroll, charged to whoever reads first, in Live and Source alike. Next step is layout cost of the Live DOM (`contain` on `.cm-line`, fewer wrapper spans), measured with the same script.
- [x] docs-1025:5 re-measured (dogfix-1026), not broken: `docmorerows.js`, row mode, More open, 600 wide: 27 controls on 4 rows (the strip row plus three of folded tools), strip 486x191, row pitch 42/48/48px, none outside the strip, no sideways scroll. At 360 it is 6 rows, 300x263, still inside (a phone uses its own bar).
- [x] dog3d-1026:7 lone-span HTML paste: done in dogfix-1026 (`docHtmlIsRich`): a bold or italic span style now counts unless the copy is monospace or `white-space: pre`. `mmdoc1005-richpaste.js`: `**Heavy words**`, `*Soft words*`, and a Consolas copy with a bold token stays `const x = 1;` (8 of 8 cases).
- Owner decisions still open: docs-1025:4 live default for a stored Source choice; table cell merge; find in selection.

## Not verified

- Smoke-driven in dogfix-1026 (`docsmoke1026.js`, dark theme, 1440x900, 0 console or page errors): Live, Source, Split and back switch with the editor present each time; outline 7 rows; version history and the templates dialog (19 buttons) open inside the window; the `[[` typeahead opens a menu. Still not driven: comments, delete and restore, math, and the finer behaviour behind each of these (this was open-and-close, not use). One thing to look at: after Live > Source > Split > Live the heading line read `# Smoke notes` (the caret line's marks, probably by design; not checked).
- Real-clipboard Ctrl+V from Word or a browser, and real touch on the phone bar (headless only).
