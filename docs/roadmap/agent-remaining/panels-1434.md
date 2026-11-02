# panels-1434: remaining

- Follow-up (out of scope, coordinator): Odysseus's docked side panel reserves space so the page reflows beside it (body class plus a width variable). Ours overlays the page. `frontend/js/panel-movable.js` `panelDock`.
- Pre-dock size is kept in memory only; after a reload an undock returns to the panel's natural size (`panelUndock`, `st.pre`).
- Grip resize of a docked panel undocks and keeps the rect (the simplest accepted form); anchored-edge resize is not built.
- `data-panel-zones` is built and unused: Settings was measured at half width (section 412px, no horizontal scroll), so no panel is restricted yet.
- Touch and phones: unchanged (sheets, no docking).
- Snap ease (coordinator item 6, about 200ms) not built: `tests/test_cheap_animations.py` refuses transitions on width and height and `tests/test_motion_tokens.py` wants duration and curve tokens; a transform-only (FLIP) glide of the panel would need a scale of its box. `panelDock` is where it goes.
