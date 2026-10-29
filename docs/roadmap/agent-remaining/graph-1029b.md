# Graph rows 42, 48, 57, 58 of audit 1029 (agent branch, not pushed)

Measured on the Playwright sweeps in the session scratch (`/tmp/claude-0/graphb/`: `search.js`, `c48c.js`, `f57.js`, `f57b.js`, `p58c.js`), server on :8841, 36 seeded notes plus extra categories.

## Done

- Row 42 (G11): `#graph-search-count` (role status, polite) says "12 matches", "1 match", "No matches"; Enter and Shift+Enter walk the matches (wrapping) and pan to each; Esc clears the search and the similar-notes highlight. Edits from the g11 draft applied (every anchor still existed), test moved to `tests/test_graph_search_keys_1029.py`, g11/ deleted, count rule in graph-lazy.css, Guide graph topic sentence, `tests/test_manual_parity.py` check. Live: 24 matches, Enter 1 moved the view from x 305 to 539, Enter 2 to 137, Shift+Enter back to 539, Esc emptied box and count; "zzzqqq" gave "No matches".
- Row 48 (G12, G21, X10): the dot rim on a light ground is 50% deeper (`gcRimShare`, was 25%): worst of the 22 automatic colours 1.87 to 3.46 sampled off the painted sprite (ground 247,246,244). `::placeholder` opacity 0.85 removed: graph search placeholder 3.68 to 4.86 on its field. `.toast-action` measured 7.72:1 on its opaque toast (white), so there is no token to darken; the axe 1.2 came from a toast behind another card (stacking, X10's first half).
- Row 57 (G9, G22, G23, G24): legend wraps to two rows (`5.2em` cap, then scrolls): 17 entries scrollWidth 2088 in 1308 and 5 out of sight, now 1308 in 1308, none hidden; the rule moved from boot CSS to graph-lazy.css. Filter fold: no lone "No kind 64" chip when no link has a kind (`gcLinkKindRows`; a turned-off untyped kind keeps its chip). Help panel 1,296 characters scrolling 568 in 510, now 780 characters in a lead line and seven items, 465 in 465. Minimap top corners clear Trace (`initGraphRailToken` grows `--graph-chrome-top` on the card; no new custom property, the count only falls): overlap with Trace 8,861 px2 to 0 at 1440x900; 0 again when Trace closes; 390 wide has no minimap overlap.
- Row 58 (G25): reproduced at 1280x640 with a long note (popup 517 of 533 tall, node dragged 280px, popup moved 0). `graphPopupCap` holds an undragged popup to 60% of the room (min 280): popup now 320 tall and tracks the node 78px past the first step down to the map's edge. At 1440x900 the follow already worked in both axes (dy stayed -20 across a 150px drag).

Ratchets: boot CSS gzip 179,097 before row 57, 179,069 after (cap 179,100); custom properties unchanged (428 cap). Boot JS unchanged at 572,727.

## Remaining

- G30 (row 57): a thin progress line on `#graph-stats` while `/graph` reloads slowly. `renderGraphCanvas` (graph-canvas.js, the `await apiJson(endpoint)` near line 5559) is the place; `gcArriving` covers only the first visit. Style belongs in graph-lazy.css (boot CSS has 31 gzip bytes of room).
- Row 48: a dot with radius under 3 (`gcPaintCore`'s flat branch) has no rim, so the very smallest dots on a light ground keep the plain colour; not measured separately.
- Row 58: a popup that cannot be beside its node because the node is at the map's far edge stays clamped (by design); the local-graph pane popup (size not full) still does not follow.
- Row 57: the topic card (right column) and the minimap's top-right corner are not on the rail; only the Trace strips are.
- Not verified: phone widths for the Help panel and the count span; the dark theme for the new rim share (it keeps the old 25%); real inference not involved.
