# panels-1028 remaining (INBOX 1427, built in c0fe4fd)

- Anchored popovers with no `.dialog-head` cannot be dragged (no handle): `PANEL_FIXED_HTML` (10 ids) and `PANEL_FIXED_JS` (21 files) in tests/test_ui_recipes.py, with reasons. Owner's "all popup panels" is met for every headed panel only. Next: give the chat model panel, month picker and context pop a head, or a move handle on the panel itself.
- Edge resize handles (left, top, right, bottom) not built; corner grip only. frontend/js/panel-movable.js `panelGripDown`.
- Not driven in a real browser: the agent command palette (`command-palette-overlay`), an `openSheet` card, the Guide sheet, a corner sheet (`sheet-corner`, bottom-right anchored by CSS). Settings, Find anything, Notifications and a native `dialog` (`doc-stats-dialog`) were driven, light and dark.
- Panels opened in the first 3 s after boot are not movable until the lazy file lands (it rides in with drag-edge.js).
- Touch laptops: `(pointer: fine)` is false on a device whose primary pointer is touch, so a hybrid reports as phone-like.
