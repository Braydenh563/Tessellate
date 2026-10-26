# docpaste-1026 remaining

Done: paste options chip, Paste special (menu row, 6 palette commands), URL over selection, multi-line/TSV chip, Guide topic `documents-paste`, `tests/test_doc_paste.py`, sweep `scratchpad/ui-sweeps/docpaste.js`.

- Right-click Paste special: the editor has no context menu of its own (only tables and findings); adding one would replace the browser's. Owner's call. documents.js `contextmenu` listener (~18740).
- A spreadsheet copy with no HTML table (TSV only) is not auto-tabled: `docTablePasteEvent` still requires the HTML table; the chip offers "As a table" instead.
- Note boxes (capture, note edit) do not get the chip: only the document editor's paste chain.
- Paste special "Match surrounding" and "Markdown source" have no palette rows (menu only).
- Not verified: real-clipboard Ctrl+V from Word or a browser (events were dispatched ClipboardEvents); phone touch (no Ctrl key: tap the chip).
