# ownerfix3-1011 (Brief 93): left, not verified, found-not-fixed

Port note: 8875 was taken by the search86 agent's server; this agent served on 8878.

## Done (one commit each)
- 852 Library sub-tab flicker: layout shift 0.37 to 0.52 became 0.017 (1440) and 0.016 (390).
- 851 Select-mode tick in the gutter: card and row heights unchanged, centre within 1px of the first line.
- 847 Notification actions on their own row: 0 actions share the close button's row at 1440 and 390.
- 853 OCR find marks every match, "n of m", Enter and Shift+Enter, prev and next buttons.
- 854 Filing style is a span like Categories and Tags; lint on every `.setting-label` head.
- 856 Hover-ground lint and sweep (see below); the owner's element was not found.

## Left
- 856: the owner's exact element ("an Ask question link") was not reproduced. `scratchpad/ui-sweeps/hoverradius.js` measured 0 square hover grounds (element, four ancestors, ::before and ::after) on the dashboard, Notes (Your notes, Ask empty and answered, Questions with rows), Chat with conversations, Timeline, Reminders, Library, Graph, the palette, the Guide and Settings, light, 1440. Ask the owner for the screenshot's surface, or run the sweep with their data (`SURFACES=...`), at 390 and under the other looks (`LOOK=`); not run there.
- 856: `tests/test_hover_grounds_have_a_radius.py` is a class-level scan with a reviewed list; it cannot see an element whose corner comes from a parent rule. The sweep is the real measure.

## Not verified
- 852: the Contents, Skills, Boards and Documents renderers were not changed; their shifts measured under 0.02 in the flick loop, with a small seeded notebook (40 notes, 3 files and images, 1 bookmark), not a large one.
- 851: rows view at 390 (the view toggle is hidden there) and the dark theme for the tick's colours were not measured; cards at 390 dark were.
- 853: a multi-region reading and a PDF with many pages (the seeded reading is one region); Tesseract is not installed here, the text was posted to `/media/<id>/ocr`.
- 847: toasts built outside status.js (none found by grep) and the notification bell's rows (not changed).
- The staged gate ran per commit for 852, 851 and 847; 853, 854 and 856 were gated once together on the final staged tree.

## Found, not fixed
- Contents sub-tab's outline shifts 0.013 to 0.016 on first paint (contents-outline 266px to 634px).
- Timeline table rows: the hover ground is `tr:hover td` on a `border-collapse: collapse` table, so the row ends are square (`06-timeline-dialogs.css:459`); fixing it needs the table model changed.
- `library-activity` rows keep their ground in a box-shadow spine, not a background.
