# dgfold-1110 remaining

- Done: INBOX 1738 (list head outside the scroller, fold button on the dock edge), review 5850946759 (gap + by key, glyphs by id).
- Not verified: 17px classic scrollbars (CSP refuses an injected scrollbar style; measured with 10px real bars; logic offsets the button when bar + 4 exceeds the dock inset 20px); the phone list sheet (`diagram-touch.js`) was not driven, only the 390 layout; the unshelved case was forced by removing `dgm-shelved` (unshelved fold right 1355 vs dock 1357, 2px).
- Found, not fixed: `tests/test_diagram_review_1108.py::test_keep_on_the_tall_chart_offer...` (getComputedStyle undefined in its node harness, diagram-outline.js:66) and `tests/test_help_controls.py` graph-controls (1915 chars near the reply budget) fail on this branch independent of these edits.
