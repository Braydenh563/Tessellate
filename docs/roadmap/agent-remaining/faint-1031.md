# faint-1031 (INBOX 1489, faint box behind heads and pills)

Done
- 454d212: Categories head, Contents and Timeline group heads, the note and capture Save feet are bare at rest and take an opaque ground only while stuck (one `scroll-state` recipe, 08-consistency.css, end of file; `@supports not` keeps the old ground). The minimised panel pill's two buttons, a toast's close and its action no longer keep the base button's accent glow. Lint `tests/test_nested_surfaces_1489.py`, recipe row in docs/DESIGN.md.
- Measured (Classic look, pngpixel, element's paint against the same pixel forced bare): Categories head light +16, +14, +2 (dark -1, +1, -4), pill label below the button dark +2, +3, +6, light -6, -6, 0; every one 0 after. Computed: head background `color(srgb ... / 0.549)` inside a card of the same value, now `rgba(0, 0, 0, 0)`; pill buttons `box-shadow` accent 25% 0 2px 10px, now none.

Left
- `.timeline-table thead th` (06-timeline-dialogs.css, near line 397) still paints a composited `--card` ground; frozen in `FROZEN_STICKY_CARD_GROUND`. Sticky table cells with `container-type: scroll-state` were not measured; needs a Timeline table with rows.
- `.modal-card > .dialog-head` (08-consistency.css, "Sticky in a scrolling card") paints `--modal-bg-opaque` on a card of `--modal-bg` (alpha 0.96 to 0.97): at most 3% of the backdrop, not seen in any pixel; left as is. Settings (opaque card) measured equal, (24, 27, 37) both.
- A bare `button` that blanks its background and keeps the glow elsewhere cannot be found statically beyond the pill, chip and toast families; a runtime scan (buttons with a shadow and no fill, in a glass look, across the tabs, Settings and a minimised pill) found only the four fixed. Dialogs and menus not opened by the scan (chat attach chips, saved searches) were not run.
- `.contents-heading` in the quiet look keeps its `inset 0 -2px` underline shadow; the stuck ground's `::before` (z-index -1) paints over an inset shadow of the head itself, so while stuck in that look the underline is covered. Not measured (needs a Library Contents with groups).

Found
- The quiet default look (utilitarian: glass off, opaque `--card`) hid the whole class: head and card were the same colour. Sweeps for this class must run with `LOOK=default` (Classic), not the default look.
- `scratchpad/ui-sweeps/lib.js` blocks `addStyleTag` (CSP); force a style with `el.style.setProperty(name, value, "important")`.
- `tests/test_boot_budget.py`: boot CSS had 2 bytes of room after the recipe; the cap was not raised (the `.contents-heading` glass-off entry, a blank line and the stuck hover rule's shorthand paid for it).
