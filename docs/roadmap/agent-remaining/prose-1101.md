# prose-1101: typing in a long document reads the paragraph it edited

- done: this commit (docProse.near and settle in documents.js, window cut at a line end, docSuggestParse early out, tests/test_prose_near_1101.py). 4x, 50 keys, 5,000 lines: prose pass 2,823 and 3,719 ms to 1,499 and 1,546 ms (blank lines), 14,612 ms to 1,438 ms (none).
- next: none open. Left, not mine to settle: the findings plugin still rebuilds from stale offsets on every docChanged (documents.js `docFindingsPlugin`, ~19300), so underlines after the caret drop until the next render; mapping `docProseFound` through `update.changes` would remove that and the second repaint dispatch (about 9 ms at 4x, 97 renders for 50 keys). Enter, a dash, a backtick or a paste take the full pass by design (`docProse.near`).
- not verified: a real IME, a code file (its own window, `docCodeSpellFindings`), the notes editor's grammar plugin (shares `docProseSkipMask.memo`, which only costs it a recompute).
