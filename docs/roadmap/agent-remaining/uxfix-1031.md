# uxfix-1031 (the independent UX review of 1031, items 1 to 18)

Done (agent/uxfix-1031, five commits, none pushed):
- Pictures (items 3 to 6, 9, 10, 13): image-layout.js wires the grip and align button on hover, on `focusin` anywhere in a card, at layout on a coarse pointer, and in the timeline note view after each draw (`imageWireAll`); the key that had the control gets it back after the save (`imageRefocus`; the Live editor's `docImageLive` holds `{at, kind}`); the align menu names its button as the focus's home and opens under it; the button has a `--card` ground; the grip's hit area is 24px with the 12px drawing on `::before`; the Inline row has its own glyph.
- Companion window (2, 11, 17) and previews (8): `html:has(> .desk-page)` clears the root background; two-line title and snippet clamps, the snippet drops the title it repeats; the menu takes the arrow keys; `strip_inline_markdown`, `stripMarkdownPreview`, `flattenNoteMarkdown` and the companion's `plain()` drop a picture's `|300|right`.
- Settings row (1): `#settings-modal .help-head > .check-row` shrinks (settings-controls-lazy.css).
- Attachment cards (7, 18): hover tone `--ghost-btn-bg`, the open button's aria-label is its title and facts.
- Recipe (12): DESIGN.md row and `test_the_shared_picture_control_is_in_the_index_and_the_guide`.

Left, with the review's words:
- Item 14 (not asked): "Width set on a note card does nothing visible": a card thumbnail ignores width by design (`options.width = null`, image-layout.js `imageLayout`); the grip's title could say "applies in the note and the timeline" (the grip is not drawn on a thumbnail at all, so only the timeline's and the note view's title matter; nothing was changed).
- Item 15 (older, out of scope): "Settings help popovers: Escape closes the whole Settings dialog, not the popover" (`desktop-companion-help`, `update-channel-help`); stop Escape at the popover and return focus to its `data-help-for` button.
- Item 16 (older, not new): Dashboard revisit layout shift 0.21 (three `.dash-widget` cards, single column to three) measures the same on 63e7303 (before the 1031 merges): 0.21 on every revisit there and at head. Not fixed; the cause is in the dashboard's redraw on revisit, not the 4px page rise.
- tests/test_global_scope_ratchet.py::test_cross_file_guards_only_go_down fails on the branch head before this work (277 guards, cap 276); not from these commits.
