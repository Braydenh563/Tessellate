# objmove-1031 (INBOX 1467, move, copy and carry objects, the tray)

Done, all five parts, measured in the running app (`scratchpad/ui-sweeps/objmove.js reorder|copy|tray`):
- One reference `{kind, id, title, url}` (`frontend/js/obj-ref.js`: `objRefFromCard`, `objRender`), brought by drag-edge.js, so app.js has no row. Cards carry `data-obj` (Library, Notes, boards, finder rows, Dashboard); Timeline and Library All cards are read from `data-key` and `data-stop-key`.
- Reorder (`obj-drag.js`, `obj-reorder.js`, `obj-order.js`): Notes, Library documents, boards and maps, images and files; "Custom order" in each sort; Undo; Alt+Up/Down; same-index drop and Escape change nothing.
- Copy and paste (`obj-clip.js`): Ctrl/Cmd+C on a focused card, Copy in a card's menu (`kebabMenu` calls `objKebabRows`), paste in chat, reminder box, board, and text editors (browser paste of the link).
- Carry and the tray (`obj-carry.js`, `obj-tray.js`): ghost, outlined targets, 500 ms tab hover, tray in the status bar (sheet on a phone through the header menu).

Left:
- Touch: a finger on a card is a scroll, so drag and the tray's drag-out are mouse and pen only; the tray opens as a sheet on a phone and Copy plus Add to tray in the menu work, but a long-press drag was never driven on a touch device.
- The Windows desktop window: no drag was tried in it (the OS drag and drop of files into it is a separate path).
- Library "All" (masonry) is not reorderable by design; its cards can be carried and copied.
- A mind map takes no paste or drop of a card (it says so); a topic that points at a note is `wbMapAddChosenBranches` territory.
- A pasted board, map, image or file on a whiteboard is a text box holding its link, not an embedded card; only notes are node cards.
- A phone has no Ctrl+C; its Copy row exists in the menu and pastes into the chat box.
- Not unit-tested in a real clipboard: the `copy` and `paste` events are driven by Playwright's Ctrl+C and Ctrl+V and by node stubs, not by a second application.
- Reminder box drop writes the title (the reminder parser reads words), never a link.
- `tests/test_global_scope_ratchet.py::test_cross_file_guards_only_go_down` (277 against a cap of 276) and `tests/test_lazy_css.py` (desk-companion-lazy.css, forced-colors-lazy.css, semantic-notice-lazy.css not listed in `tests/_css_paths.py` or loaded) fail on the working branch without this work.
