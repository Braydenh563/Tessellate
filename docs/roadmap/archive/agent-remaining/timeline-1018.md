# timeline-1018 (Sonnet): TIMELINE_PLAN sections 9 to 12 audit and the open rows

Port 8788, data `/tmp/mm-tl1018` (48 back-dated notes, 12 reminders). Measured 2026-10-18 with
`scratchpad/ui-sweeps/timeline1018.js` (day heads, small targets, rail dot) and
`remindersqa1018.js` (quick add chips) against the served worktree.

## Audit (step 0)

| Item | State | Evidence |
| --- | --- | --- |
| 9 Phase 5 gates 1 to 4 (grid, week and day, agenda, drag and undo, ICS) | built | HISTORY.md:924 and the "Moved from the plans, 2026-10-11 (TIMELINE Brief 55)" block |
| 10 row 1, 3, 4, 7, 8 | built | HISTORY "Brief 85" and "Brief 55" blocks (pointers in the plan table) |
| 10 row 2, day head button beside its date, targets 24/44 | built (measured now) | `timeline1018.js`: head overlaps 0 at 1440 and 390 over 59 heads; day-head buttons 32 px high at 1440, 44 px at 390 (coarse); the only sub-24 control is `#timeline-search` 408x20, the app-wide `.search-field` recipe whose wrapper is the 32 px target |
| 10 row 5, typed entries land on the day they name | built, unpinned | `entry/timewords.py` + `routes_timeline.py` (`placed_by: mentioned`); 20 of 20 phrases in `tests/test_timeline_typed_day.py` land on the named day over HTTP against a fixed Sunday (the test fails at another "now", so the clock is honoured); 3 other phrases found wrong need a decision (see questions) |
| 10 row 6, scrubber and month ticks from D3's time scale | built this run | before: `drawTimelineScrubber` (`timeline.js:1849`) drew a density path only, no labels or tick lines; now `frontend/js/timeline-ticks.js` (lazy), tests/test_timeline_ticks.py, `timelineticks1018.js` |
| 11 row 7, live chips in the quick-add row and the row at 390 | built (measured now) | `remindersqa1018.js`: "dentist friday at 9am" chip in 65 ms at 1440, 129 ms at 390 (inside the 150 ms line); at 390 the row is in the FAB sheet (`#reminders-new`), 304 px wide, inside the viewport; Brief 66 / F2 in HISTORY |
| 11 rows 1 to 6, 8, 9 | built | HISTORY "Brief 85", "Brief 86", "Brief 55" blocks |
| 12 rows 1 to 6 | built | HISTORY "Brief 55" and "B72" blocks |
| Placed bug: rail circle not on the first line's centre | built, re-measured | `timeline1018.js`: `.timeline-row-mark` centre minus the title's first line centre = 0 px for 12 rows at 1440 and at 390 (day scale) |
| Placed INBOX 561 (day strip rework) | owner | waits on the owner's look (plan line 207) |
| Phase 5 not verified: dot density at 1,000 notes in a month, week grid at 1024 coarse | measured this run | `calstress1018.js`: 0 overflow, 168 dots, month 1,247 ms; week hour cells >= 56 px; found and fixed the count chip overwrite (`timelineLoadMore`) |
| Phase 5 not verified: touch drag, 5,000-note month | open | no touch drag exists; 5,000 not seeded |

## Done / next

- done: 9a6c59f audit table, typed-day test, plan rows 2, 5, 7 pointed at HISTORY.
- done: c794253 row 6, D3 labels on the density strip.
- done: Phase 5 stress measures, and the calendar count chip overwrite fixed (this commit).
- done: final sweeps on the timeline tab, light and dark: errors.js 1440 0 errors 0 findings, 390 timeline 0 (2 findings are the Notes tab, below); contrast.js timeline "ok (204 text elements)" both themes; touch.js 0 findings both themes; docks.js timeline dock 3 controls at 1440.
- left (not mine, untouched): OPEN.md rows 330 (On this day row moves the list 44 px at 390), 341 (the table has no meeting mark), 850 (a map under the Boards chip); `timeline.js` sweep's "a bucket head stays pinned after scrolling" fails 1 to 3 times a run on the base too (the week-ahead heads, flaky by run: 1440, 390 then 1440, 1024); errors.js at 390 reports 4 off-screen `button.ghost.small` on the Notes tab (both themes), not the Timeline.

OPEN.md line 2527 ("The rail-dot alignment at 390") is answered: 0 px at 390, `timeline1018.js`.

## Questions for the owner

- Should a bare weekday read with a past verb ("called mum on friday", "on monday we shipped", written on a Sunday) resolve to the last such day? Today it resolves to the coming one (`entry/timewords.py` `_weekday`, "on" and "this"), so both land a few days ahead of what happened. Recommendation: yes for a note, with the past-verb list in `timewords.py`; no change for reminders. Needs your call because a wrong guess moves a row.
- "book club on the 12th" (a day number with no month) stays on its written day, unplaced. Recommendation: place it on the nearest 12th to the note's day, as "3 March" is (`_written_date`).
