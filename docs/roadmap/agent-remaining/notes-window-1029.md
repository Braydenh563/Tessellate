# notes-window-1029 (audit 1029 rank 37, N9)

Brief: window the Notes list (viewport plus a margin), cheaper card, keep keyboard, selection,
batch select, focus, screen-reader order, scroll restore and the phone shell. Measure 300 notes at 4x.

- Built: `renderWindowed` (notes-list.js). Every note is an `li.row-shell` (hidden inline, holding
  its last height); rows within 1,200 px of the scroller are built in runs of 6 (direction aware),
  rows more than 30 from the window are emptied when the scroll settles (300 ms), which is also
  when the count chips are asked for. `noteWindow.fill` builds a row before the keyboard focuses it.
  Range select runs over ids (`selectNoteRange`, navigation.js). Rail spy observes only changed rows
  (notes-rail-spy.js). `flashEntry` jumps instantly over long distances, then re-centres.
- Paid for in the gzip ratchet: `renderIncrementally` moved to library.js (lazy, its one caller);
  `toggleRowExpanded` and the two bell nudges moved to lazy notes-lazy.js (`notesLazy`).
- Sweeps (scratch, not committed; /tmp/claude-0/.../scratchpad/sw): `measure.js` (A/B against
  HEAD by routing the changed files), `func.js` (keyboard, aria, redraw, jump, range, expand, phone).

## Measured (300 notes, 4x CPU, synthesized wheel scroll at 3,000 px/s; machine load 15 on 4 cores)
- List elements at end of scroll: 12,126 HEAD, 2,074 now. Page: 24,363 vs 13,515.
- Down scroll p50 frame: 67 to 83 ms HEAD, 17 to 117 ms now (noisy). Up scroll p95: about 330 HEAD,
  350 to 470 now (HEAD has every card built on the way back; rows here are rebuilt).
- Open the oldest long note from the end: HEAD not open after 8 s, now 1.2 to 1.4 s, on screen.

## Remaining
- Upward scroll p95 is not better than HEAD: each run of 6 rebuilt cards is a long frame at 4x.
  The cost is style resolution of about 30 elements a card, not script.
- Cheaper card: cards are 29 to 60 elements (median about 30). The link row's kebab builds its
  menu eagerly (11 elements per link, `kebabMenu`, sheets-selects.js); a lazily built menu is the
  next cut, app-wide.
- Pre-existing at HEAD 447fb2a, not this change: `tests/test_has_invalidation.py::
  test_no_has_is_keyed_only_on_a_class_everything_wears` fails on
  `.space-option:has([aria-checked="true"]) .ph:first-child` (07-whiteboard-misc.css).
