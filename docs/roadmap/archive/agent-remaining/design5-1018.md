# design5-1018: INBOX 1301 D2, D3

Status: done (D2, D3). Port 8799, data dir /tmp/mm-design5.

Decisions (recorded, DESIGN.md first):
- D2 names "the splash" and says "still": it follows C02 (fixed 03b6bf4, the Windows launch splash growing down the screen). Both were built: the launch splash (`scripts/splash.ps1`) keeps one size, and the dashboard's Get started card (the brief's reading) is a compact checklist.
- Hide and Mark all as done are this browser's preferences (`getStartedHidden`, `getStartedDone`), as `firstStepsHidden` always was; the way back is Customise, Show Get started (Settings not needed: the brief allowed either).
- The card's doors (sample notebook, Bring notes in, tour, manual) moved into its ... menu: a row that came and went with the sample notes changed the card's height.

- done: e18cca3 dashboard card and D3 (card 350 to 114 px at 1440, 658 to 275 px at 390; same height at 0, 1, 2 done; Hide, Mark all done, reload, Show measured).
- done: 1c2f2ff splash.ps1 fixed size (static tests only; not run on Windows).
- next: nothing in this brief.

Found, not fixed:
- `tests/test_lazy_css.py::test_a_lazy_stylesheet_is_not_also_linked_and_is_linted` fails on the base: `sidebar-folds-lazy.css` (06e97a1, C43) is not in `tests/_css_paths.py`.
- At 390 the hero grows 82 to 118 px when the name lands (the greeting wraps), moving everything under it 36 px; not the card.
