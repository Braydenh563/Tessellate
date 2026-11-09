# dgmseq-1109: INBOX 1702 (sequence diagram in the builder)

Agent dgmseq, branch agent/dgmseq-1109 off claude/next-queue-1102. Sweeps are untracked, in the session scratch dir (m.js, base.js, rows.js, tog.js, pic.js, flow.js).

## Done (1440 px, dark, real scrollbars)

- 1 list: label and meta both start at x 188 (card 140 to 340), meta under the label; rows 46 px; Participants and Messages headings; `activate K` as "Worker is active"; loop and else in words under the row.
- 2 shelf: folds to one button (`diagram.shelf`), picture starts below it (overlapping boxes 1 to 0), caret closes on a second press (open 2nd press before, closed after).
- 3 fold button: right edge 1301 (client edge 1296) to 1291.
- 4 selection: a click on a sequence picture picked nothing (letgo listener lifted it); fixed with `S.hitAt`; a pick scrolls the other half (box in view, row visible). Flowchart checked, already worked.
- 5 views: list 224 px (Picture) or 587 px (List) of 1174, each view keeps its own dragged width; line beside the seg names the view.

## Left

- Folded shelf is still a 38 px button over the picture's top left corner (1 box covered at 1440); the owner chose collapse, so it was kept.
- Guide topic `diagram-blocks` is at its budget (1900), so the new sentences are in the dialog's help only (diagram-embed.js `helpLines`).
- tests/test_plan_hygiene.py::test_inbox_is_a_tray_not_a_backlog failed before this work (22 INBOX items against a cap of 20).
- Not verified: phone widths, real touch, real Windows scrollbar width (17 px; headless gave 12).
