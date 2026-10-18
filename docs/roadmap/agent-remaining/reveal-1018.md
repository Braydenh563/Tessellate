# reveal-1018 (Sonnet, worktree agent/reveal-1018-1018)

Brief: cut the first-reveal style cost of the Library and Notes pages, no visual change.

- done: Library cards off screen take `content-visibility: auto` (library-lazy.css). First recalc after reveal 1,335 to 209 elements, 183-225 ms to 86-108 ms at 4x (5-run medians, 500 notes, `tabtrace.js TABS=library`); `tests/test_tab_entry_cost.py`.
- tried, dropped: a 25-card first paint topped up to 60 on frames (Library only, plus a pump change in boot `renderIncrementally`). Settled grid identical (60 cards, scroll 1200 kept), but no gain at the reveal: the Library keeps its 60 cards between visits, so the reveal restyles the old DOM (JS-only run: 1,335 el, 247 ms median). The code was not kept.
- found-not-fixed (Notes): the first recalc (701 and 917 el, 66 and 104 ms) is already `content-visibility: auto` rows plus the sidebar. A 13-row first paint with no top-up cut it 26 percent in elements, but it changes the settled list (60 rows to about 13), and Select all and Ctrl+F read the rendered rows; with a top-up the reveal sees 60 rows again. Boot JS has 147 bytes of headroom.
- found-not-fixed: cv:auto paints text in cards at fractional y up to 1 px differently (3.6k of 1.3M pixels at 1440x900, rows 4+); settled scroll height +56 px until cards are seen.
- next: nothing queued.
