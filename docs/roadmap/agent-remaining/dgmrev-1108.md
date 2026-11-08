# dgmrev-1108: remaining

Branch `agent/dgmrev-1108` (not pushed). All seven "Diagram" findings of review-1108-dgm-buddy.md are done, one commit each; the in-app companion item was out of scope.

- Real browser (dgmlive-1108, Chromium, port 8894): sequence-first Ctrl+Z steps the sequence history in place (6 lines to 5, same document id, builder still open, redo restores 6), from a tile and from the pane. The dialog's Ctrl+Z: pane focus 3 blocks to 2; source box 6 lines to 3 and redo back to 6; Done button focus one step only; title field undoes only its typing (after the dgmlive 2 fix; before it a block rename pulled focus off the title and Ctrl+Z removed the block). Keep across two tall documents leaked (second showed 0 offers; fixed in dgmlive 3, now 1, and the first stays answered).
- Live editor click (mermaid-draw.js box handler), measured: caret at 3 stays [3,3] in the CM state at mousedown, mouseup and click, the DOM selection stays empty, openDocument is called once and the target document opens (current id 22 to 21).
- Guide `diagram-blocks` gave up "or Start from an example" in the empty-state sentence and three wordier phrases to fit 1900 (now 1886); `data-help-for` was not needed.
- `test_diagram_dgmfix2_1108.py` source checks moved with the code (historyKey to the kind bar, `answered` keyed by `whose(S)`); the intent is unchanged.
- `io.key` (the document id) is new on the document builder's `io`; the embed dialog has none, so its host stays the key there.
