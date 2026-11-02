# Deep audit 2026-10-31: ux (cross-surface: widths 360 to 2560, both themes, keyboard only, touch, reduced motion, recipes and tokens)

Fable suite, surface 9 of 12. Server on 8852, about 530 notes. Drives hu1 to
hu5 (Playwright; widths 360, 768, 1024, 1440, 2560; dark, with light at 360
and 1440; axe-core wcag2a/aa, 2.1, 2.2 and best-practice; keyboard only;
`reducedMotion: reduce`; touch at 390 with `isMobile`) and CSS greps.
Observed unless marked code. The 1028 ux rows (U1 to U40) live on the
board, map, document and code surfaces; the ones those 1031 audits re-ran are
listed at the end.

## Rows

| Row | Sev | Kind | Finding | Evidence | Where | Verified | Fix | Size |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UX1 | med | a11y | **51 Tab presses from the composer to the first note.** The sequence runs the header (9 stops), the activity panel (6), the rail and then every category twice (name, then "Actions for …": 62 stops in `#category-list` for 31 categories) before `#entry-list`. There is no roving tab stop in the category list and no skip past it; the skip link at the top works (lands on the tab). | hu5 kb-stops-to-list `stops: 51`, `categoryStops: 62`; hu4 kb-to-first-note | `#category-list` rows; `#entry-list` | run | Arrow keys inside the category list with one tab stop (`tabindex="-1"` on the rest, the WAI tree pattern); a "Skip to notes" link after the composer; the activity panel's six buttons out of the order while it is folded. | S |
| UX2 | med | a11y | **Targets under 24 px on the notes list.** Ten "Actions for the linked note" buttons are 21 x 21, the done checkboxes 15 x 15, "Show more" 69 x 14 (12.8 px text, 0.8 px padding); on the library every card title is a 22 px tall button (37 per view); on a phone the per-note action rows are 44 x 24. WCAG 2.5.8 asks 24 x 24 or clear spacing. | hu2 1440-notes-small; hu1 `library-card-title:97x22`; hu3 touch-entry-actions `44x24` | `.ghost.small` in `#entry-list`; `.entry-more`; `.library-card-title` | run | `min-height: var(--control-h-dense)` on the three, 18 px checkboxes with a 24 px hit box, 44 px rows on coarse pointers. | S |
| UX3 | med | perf, a11y | **70 animations run while nothing happens.** On the notes tab at rest, 70 animations are running (67 infinite): the companion's `atl-orbit`, `atl-orbit-back`, `atl-orbit-depth` (7 each), nebula drift and flow, `emblem-lift` (3), two spinners. In 8 s of idle that is 2 long tasks (65 and 53 ms); with `data-motion="reduced"` or the companion hidden, none. Under the OS `prefers-reduced-motion: reduce` 18 still run (`emblem-breathe`, `emblem-lift-soft`, `emblem-shadow-breathe`, `spinner-turn`) because the still sheet exempts `#nm-buddy`, `.name-mark`, `.nm-atlas`, `.nm-figure` and `.emblem-art *` (code). | hu2 idle-cost; hu4 idle-motion-on `n: 2, sum: 118`, idle-motion-reduced `n: 0, anims: 4`; hu1 motion-reduce `idle: 18` | `motion-still.css:37`; `03-dashboard-widgets.css:3080` to `:3127`; the companion's sheet | run | Pause the companion's orbits after 20 s without input and whenever it is off screen (`IntersectionObserver`, `document.hidden`); under the OS preference leave the emblem on its still pose and keep `data-ui-motion="on"` as the explicit opt-in. | S |
| UX4 | low | legibility | `--text-xs` (0.7rem, 11.2 px) carries content: the timeline's time column (62 per view), tab labels below 1280 (11.2 px at 360 to 1024, 16 px at 1440), shortcut keys (`.status-key`), tab badges, activity counts, library chip counts; the dashboard's SVG chart labels are 4.92 px ("Car…", 2 in `#dash-grid`, a 306 px wide svg). | hu1 `tinyIds` on every width; hu4 dash-svg-text | `06-timeline-dialogs.css:212`; `10-responsive.css:47`, `:119`; `00-tokens-shell.css:442`, `:3419` | run | `--text-xs: 0.75rem` (12 px floor), chart labels as HTML beside the svg rather than scaled text. | S |
| UX5 | low | consistency | Eight button heights on the notes view at 1440 (14, 21, 26, 28 x102, 32 x17 tabs, 36 x14 header, 44, 52) and six radii (0, 2.4, 4.8, 8, 8.8, 999 px) where the tokens define four control heights (`--control-h-dense` 28, `--control-h-lg` 32, `--control-h-body` 36, `--control-h-touch` 40). Raw colours sit mostly in the token and theme sheets (180 and 498) with 74 in `08-consistency.css` and 37 in `02-chat-graph.css` (code). | hu2 1440-notes-small `heights`; hu1 `btnH`, `radii`; CSS greps | `01-forms-settings.css:715` (`.small` floor), `.entry-more` | run | The three off-scale heights (14, 21, 26) onto the dense height; a lint counting distinct visible button heights per view (allow four). | S |
| UX6 | low | ux | Horizontal strips at 360 give no sign they scroll: the dashboard launch row holds 760 px in 338 (2 of 5 cards off screen), `#library-subtabs` 829 px in 334 (9 tabs, "Contents" at 842 px), `#library-filters` 1,234 px in 334; none has an edge fade or a scroll hint, and the chosen tab is not scrolled into view. | hu5 360-quick-visible; hu4 360-library-subtabs; hu2 360-library-over | `.launch-row`, `#library-subtabs`, `#library-filters` | run | `mask-image` edge fades on every `overflow-x: auto` strip (one utility), `scrollIntoView({inline: "nearest"})` on the chosen tab, the launch cards wrapping to two rows. | S |
| UX7 | low | a11y | `#tab-btn-reminders` has `aria-label="Reminders"` over visible "Reminders 1" (the one axe violation across 20 runs, both themes); the AI status popup is a `role="tooltip"` opened by hover and tap from `#ai-status`, a button without `aria-haspopup` or `aria-expanded`, so a keyboard user has no cue it opens. | hu1 axe-1440-*; hu3 aiTap `popup: true`; hu4 ai-status-keyboard | `index.html:172`; `.ai-status-wrap` | run | Drop the `aria-label` (the text and badge already name it); `aria-expanded` on `#ai-status` and Escape to close. | S |
| UX8 | low | perf | The theme button takes 858 ms with two long tasks (119 and 161 ms) on the notes view at 1440. | hu2 theme-switch | `applyThemeChoice` `settings.js:2459` | run | Swap the `data-theme` attribute only and let the tokens repaint; defer any re-render of lists to the next idle. | S |

## 1028 ux rows re-verified

| Row | Now | Evidence |
| --- | --- | --- |
| U1 to U5, U12 to U28, U40 (board and mind map) | see `audit-1031-board.md` | not re-run here |
| U6 code editor under New | partly | `audit-1031-code.md` |
| U7 proportional code font | fixed | `audit-1031-code.md` |
| U8, U10, U11, U29 to U39 (documents) | see `audit-1031-docs.md` | not re-run here |
| U9 unstyled find panel | mostly fixed | `audit-1031-code.md` CE4 |
| U35 small targets in the document header | open | `audit-1031-docs.md` DC5 |

## Coverage

| Area | Driven | Notes |
| --- | --- | --- |
| Seven tabs at 360, 768, 1024, 1440, 2560 (dark): overflow, clipped text, targets, fonts, families, heights, radii | run | no horizontal page scroll at any width; one font family per view (plus monospace) |
| axe at 360 and 1440, dark and light, five tabs | run | one violation (UX7); contrast passes in both themes |
| Keyboard: skip link, 45 stops with visible rings, a menu (Enter, arrows, Escape returns focus), the palette (focus held, Escape) | run | every stop had a ring and a name |
| Reduced motion (OS) against no preference | run | UX3; transitions stay 0.1 to 0.2 s (383 of 400 controls) |
| Touch at 390: menu items 44 px, outside tap closes, nav 78 x 57, hover-only reveals shown on coarse pointers | run | 63 `:hover` reveal rules all have a coarse-pointer path |
| Theme switch, scroll position across tab switches (kept at 600 px) | run | |
| Settings panel, dialogs at 360, forced colours, 200% zoom, RTL, screen-reader announcements, print | not driven | |

## Already good

- No horizontal page scroll at any width from 360 to 2560; the body clips and every strip scrolls on its own.
- axe is clean in both themes but for one label; every keyboard stop shows a focus ring and carries a name; the skip link works; menus follow the WAI pattern; the palette holds focus.
- Touch targets in menus and the phone nav are 44 px; hover-revealed controls are shown on touch.
- Tokens are used for spacing and type (two literal font sizes and ten literal gaps in 80,000 lines of CSS).

## Not verified

- Forced colours and 200% zoom; screen-reader output (names were read from the DOM); `applyThemeChoice("light", false)` leaves `data-mode="dark"` (so `color-scheme` stays dark) but the theme button updates both, so no user path was found; the companion's idle cost on a phone.
