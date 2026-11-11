# Atlas and narrow or zoomed windows (INBOX 1111), what is left

Measured with `getBoundingClientRect` and pixel diffs (companion hidden vs shown) at 360, 390, 768, 1280, 1920 and 2560 wide, browser zoom 100, 125, 150 and 200% (viewport = width / zoom), light and dark, Notes and Graph.

- **Fixed: a resting figure no longer reaches into a bar.** `nameMarkBuddyAloft.rest` clips the band at the top bar's lower edge (hang) or the bottom bar's upper edge (bar perches) in whole px; a pull, a throw or a glide lifts it. Pixel diff, 24 configs (360 to 2560 wide, 100 to 200%): before 20 failing, max 35 rows; after 2 failing, max 5 rows (the status bar's breathing emblem, not the figure). Not changed: the figure in flight and the dock, corner and pinned perches; a few widths (768 at 150% and 200%) have no free spot on the bar, so only the peek stance was sampled there. `tests/test_companion_rest_bars_1111.py`.
- **Top bar wider than 281 css px of window.** At 260 (390 at 150%), 240 and 195 wide the top bar's content is 21px wider than the window (`document.documentElement.scrollWidth` 281). Below the 320 px reflow floor, so left.
- **Companion menu is 200px wide (`min-width: 12.5rem`) in a 180 or 195 px window**: it lands 13 to 28px off the left edge. Same floor.
- **`docToolPref is not defined` page error**: fixed. documents-ide.js set the minimap box at its top level and can run before documents.js declares `docToolPref`; the line now runs in documents-view.js after the bundle (`tests/test_ide_minimap_pref_after_bundle_1111.py`).
- Not verified: real-device scrollbars and the phone's own zoom; the menu was unmeasured in a few rows where the figure moved between measuring and the click (reopened by hand at 390: opens).
