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

- Live scroll worst frame 132 ms on the 8,221-word document (Source 29 ms): decoration cost on long Live documents.
- docs-1025:5 More menu third row at 600 px not re-measured.
- dog3d-1026:7 lone-span HTML paste still arrives as plain text (rare).
- Owner decisions still open: docs-1025:4 live default for a stored Source choice; table cell merge; find in selection.

## Not verified

- Comments, delete and restore, version history, templates, wiki links, math, outline, Live/Source switching and the dark theme were not driven this run.
- Real-clipboard Ctrl+V from Word or a browser, and real touch on the phone bar (headless only).
