# dgmlive-1108: remaining

Branch `agent/dgmlive-1108` (not pushed). Port 8894 was used (8794 was held by another agent's server). Sweeps are in the agent scratch dir, untracked.

Done: items 1 to 5 driven in Chromium; two failures fixed (rename blur stole focus from the dialog title: 9c379da9; Keep leaked through the reused pane's `sidewaysAsked` flag: next commit). Items 1, 4 and 5 passed unchanged. Numbers are in dgmrev-1108.md.

Left:
- Kebab keyboard check covered the block menu and "More for this diagram" in the flowchart and sequence builders; not the embed dialog's own "More" and not the Library rows.
- Live editor click: a double click and a drag across the embed were not driven.
- `tests/test_complexity.py` fails on `src/tessellate/ai/composer_digest.py::answer` (not touched here; came with the merged base), so `gate.sh --staged` reports staged-lints red.

## Measured later (dgmlive2-1108, Chromium, port 8899)

- Library rows' ⋯ (the Library tab's diagram cards): Enter and Space open, arrows/Home/End move, Escape closes and focus returns to the opener (aria-expanded true to false). Rename, Delete (confirm opens on Cancel, Tab to Delete), Archive, Save as SVG, Show in graph, Remind me all ran from the keyboard. Failures fixed: focus fell to BODY after the grid reloaded; Undo (toast, Ctrl+Z) did not redraw the Library; an archived diagram stayed in Everything (`/library` listed it as a diagram and as shelved). There is no Open or Duplicate row on a card's menu (open is Enter on the title).
- Embed dialog "More for this diagram": Enter and Space open, arrows/Home/End move, Escape closes with focus back and the dialog still open; Clear then Ctrl+Z restored the source; Save to Library toasted. Failure fixed: a look row remounted the pane and focus went to BODY.
- Live editor embed: a drag starting on the picture selects nothing and moves nothing (DOM selection 0, CodeMirror [0,0], text unchanged); a double click opened the diagram once but left a 297-character selection on the opened page; fixed (0).
