# chips-1031 (branch agent/chips-1031)

## Done
- INBOX 1476: staged chips are the one `.att-chip-pill` (see CHANGELOG, DESIGN.md "A file waiting on the next message"); selection, OCR and web-page chips go through `attachmentChip`; the upload bar CSS moved to `chip-bar-lazy.css`.
- INBOX 1477: the Chat, Ask and Writing model pickers open as search, Pinned, Recent, per-source groups with counts and pins (`frontend/js/model-menu.js`, `model-menu-lazy.css`, `tests/test_model_menu.py`); rows are `richPickerRow`, the hook is `enhanceSelect.richMenu`, help is the `chat-model-picker` topic.

## Next
- INBOX 1478: popup anatomy (glyph head, glyph tab row with counts, bordered cards, Appearance dot tiles and Peek, glass values compared with Tessellate's tokens). Not started: no time left after 1 and 2. Files to start from: `docs/DESIGN.md` (glass-off list), `frontend/css/appearance-panel-lazy.css`, `frontend/js/appearance-panel.js`, `frontend/css/panel-movable-lazy.css`. Leave the minimise button to snapgraph-1031.

## Found-not-fixed
- A model's source is read from its name (`modelSource` in model-menu.js: `-cloud`, `hf.co/`, else local) because the status reports one provider at a time; a second provider's models would need a `source` on each `installed_models` row (routes_models.py `_installed_models`).
- The composer's model select is not shown at 360px wide (its opener never became visible in a sweep), so the picker was measured at 1440 only.
- Pins and recent picks live in localStorage with the `MIRRORED_UI_EXTRAS` mirror (device-independent via the notebook), not in a preferences key of their own.
- The staged pills sit in the existing strips above the composer, not in its tool row as the reference does; moving them is a layout change to `#chat-attachments`, `#chat-image-attachments`, `#chat-selection-attachment`.
- `scratchpad/ui-sweeps/attachchips.js` now expects the `[Word]` facts on staged chips; it was edited but not re-run in this session.
