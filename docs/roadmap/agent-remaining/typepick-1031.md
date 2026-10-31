# typepick-1031 (INBOX 1482, the file type picker)

Done: the grouped type picker (Documents, Data, Code, glyph per row, filter field) as `docTypeMenu` in documents.js, drawn by the status bar's type button and by New's caret; `group` and `icon` on `core/filetypes.py`; `docCmChanged` memo so an open re-sends the editor's language, wrap, code tools and spellcheck only when they changed.

Left (one line each):
- The Library's own New document button (`library-docs-new`, library.js:10542) still starts markdown only; it could take the same caret (`docTypeMenu`).
- An empty code document shows the markdown placeholder "# Start writing ... Markdown works here" (documents.js openDocument, `docSetPlaceholder`); pre-existing, now more visible because New can start a code file.
- `syncDocFileType` still spends about 7 ms per open, nearly all in `applyDocGutter` > `docGutters` (a `querySelectorAll` that pays for the style recalc the class toggles above it queued); batching the toggles after the read would cut it.
- Not verified: dark theme, the picker under a screen reader, and the phone action sheet's focus behaviour with a real touch keyboard.
