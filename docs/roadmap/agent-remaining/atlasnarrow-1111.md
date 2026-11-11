# Atlas and narrow or zoomed windows (INBOX 1111), what is left

Measured with `getBoundingClientRect` and pixel diffs (companion hidden vs shown) at 360, 390, 768, 1280, 1920 and 2560 wide, browser zoom 100, 125, 150 and 200% (viewport = width / zoom), light and dark, Notes and Graph.

- **Owner call: how far a resting figure may reach into a bar.** On a `hang` perch (top bar) the ring and head reach 10 to 18 css px up into the bar (390 wide at 150%: 27px); on a `bar` perch (dock or status bar) the tail reaches 19 to 22 px into it (pixel diff over 24 levels, 100 to 4500 px). It moves with the animation (2 px at one instant, 17 at another), so it reads as the hands on the edge, but at 1280 it draws over the lower edge of the "Reminders" tab. Not changed: the perches are by design contact with the ledge, and the shutter cut only applies to a panel ride. Decide a cap (for example the figure's own box, not its wisps), then cut it in `nameMarkBuddyRideBox`.
- **Top bar wider than 281 css px of window.** At 260 (390 at 150%), 240 and 195 wide the top bar's content is 21px wider than the window (`document.documentElement.scrollWidth` 281). Below the 320 px reflow floor, so left.
- **Companion menu is 200px wide (`min-width: 12.5rem`) in a 180 or 195 px window**: it lands 13 to 28px off the left edge. Same floor.
- **`docToolPref is not defined` page error**: fixed. documents-ide.js set the minimap box at its top level and can run before documents.js declares `docToolPref`; the line now runs in documents-view.js after the bundle (`tests/test_ide_minimap_pref_after_bundle_1111.py`).
- Not verified: real-device scrollbars and the phone's own zoom; the menu was unmeasured in a few rows where the figure moved between measuring and the click (reopened by hand at 390: opens).
