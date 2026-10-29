# Appearance panel (INBOX 1435): built, what is left

Built: `frontend/js/appearance-panel.js`, `frontend/css/appearance-panel-own-lazy.css`, the generated `frontend/css/appearance-panel-lazy.css` (`scripts/appearance_panel_css.py`), recipe `appearancePanel` in DESIGN.md, tests in `tests/test_appearance_panel.py`.

Left, one line each:

- Deep links while popped out: `openSettingsModal("appearance", "<id>")` (a help badge, the companion's menu) lands on Settings' "Appearance is open in its own panel" note, not on the control; it should focus the control in the panel (`frontend/js/appearance-panel.js`, `appearanceHost`; `frontend/js/settings.js:263` `openSettingsModal`).
- The top-bar theme button opens the panel only by right-click (`frontend/js/settings.js` next to `$("theme-btn")`); a visible door (a second small button or a split) was not built because the boot scripts have few gzipped bytes of room under `TOTAL_CAP` (`tests/test_static_compression.py`).
- A committed browser sweep: the scratchpad is at its 766-file cap (`tests/test_scratchpad_size.py`), so the Playwright sweeps that measured this are not tracked; the numbers are in the commit and CHANGELOG.
- Peek follows the decision (the ground fades, controls stay at full strength); Settings' own Peek also dims the body to 32% (06-timeline-dialogs.css). If the panel reads poorly over a busy page, dim the strip and body the same way, one rule in `appearance-panel-own-lazy.css`.
- Settings' search index (`settings-find.js`) and "On this page" read the page's headings; while the panel holds them they find nothing in Settings. Searching a setting while popped out should open the panel at that setting.
- The panel is 33rem wide and as tall as the window allows (788 px at 900); a shorter default height on tall windows may read better.
