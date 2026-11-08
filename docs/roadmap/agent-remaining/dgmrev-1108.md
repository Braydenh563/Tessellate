# dgmrev-1108: remaining

Branch `agent/dgmrev-1108` (not pushed). All seven "Diagram" findings of review-1108-dgm-buddy.md are done, one commit each; the in-app companion item was out of scope.

- Not run in a real browser: the sequence-first Ctrl+Z, the dialog's Ctrl+Z focus cases, Keep across two diagram documents and the Live editor click were checked in node (a `vm` over the real files) and by reading, not driven in the app (no Playwright run).
- Live editor click (mermaid-draw.js box handler): by reading, `DocEmbedWidget.ignoreEvent()` is true, so CodeMirror never placed a caret from a press on an embed and its own click already opened the target; the box handler is click-only. A real-browser caret check is still open.
- Guide `diagram-blocks` gave up "or Start from an example" in the empty-state sentence and three wordier phrases to fit 1900 (now 1886); `data-help-for` was not needed.
- `test_diagram_dgmfix2_1108.py` source checks moved with the code (historyKey to the kind bar, `answered` keyed by `whose(S)`); the intent is unchanged.
- `io.key` (the document id) is new on the document builder's `io`; the embed dialog has none, so its host stays the key there.
