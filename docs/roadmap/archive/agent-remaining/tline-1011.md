# tline-1011: Timeline, reminders and notifications (ledger rows 969 to 1038, batches B57 to B61)

Branch agent/tline-1011, worktree scratchpad/wt-tline, port 8803. `id | status | evidence or commit`. Commits: 33ed15723 (the calendar and written-out dates), c0b761f21 (the batch after it: reminders, toasts, notifications, packages, quit and restart fixes). Two owner bugs came first (HISTORY, "INBOX resolved" c1 and c2).

969 | done-already | TIMELINE_PLAN section 9 gates say Built 2026-10-11 (Brief 55, HISTORY); this run fixed the day-cell press and note chips (commit A)
970 | deferred-next-PR | touch drag has no HTML DnD on a phone (the calendar is the agenda below 768); day-page drop and a 1,000-note month not driven under load 45 to 60
971 | done | errors: 0 PAGEERROR/CONSOLE-ERR in 5 calendar runs (1440 dark and light, 390); contrast: chips 12px text on --surface-2 over --chip-bg, dark fg 236,235,232 and light fg 28,28,26, no overflow (scrollHeight<=clientHeight, 0 cells)
972 | built | 927698eac: the feed range keeps a note by the day it is about, as the calendar does
973 | built | reminder_notifier.stop_running() called by the app's lifespan before jobs.shutdown; tests/test_reminder_notifier.py
974 | done-already | reminder-notify.js mints a per-reminder token (POST /reminders/<id>/notification-token, core/reminder_token.py); the worker's data holds that token, not the session's
975 | deferred-next-PR | a timing at 329 vs 300 ms is meaningless at load average 45 to 60; needs a quiet machine
976 | decided | #reminders-new is the phone FAB (.dock-fab, phone-shell.js FAB_IDS); a floating button over a scrolling list is by design, and .dock-fab pages add the end clearance (10-responsive.css 2450 to 2460); the browser measure of the list end did not finish under load
977 | built | reminderEditForm gains an early-alert select (0/5/15/60/1440 and a kept odd value); tests/test_reminders_reschedule.py
978 | not-reproduced | no code path sets #timeline-days from a stored preference (grep: only the Options select, the year chip at timeline.js:627 and calendar open-day)
979 | built | timelineLoadMore asks again when a range change made its page stale (timeline.js stale flag)
980 | deferred-next-PR | needs a 200-topic whiteboard map fixture and timing; not measurable at this load
981 | decided | no backfill: a tick before done_at existed has no known moment; inventing one would put it in a week it was not done in (notebook_stats docstring keeps it in neither)
982 | deferred-next-PR | L row, no work
983 | deferred-next-PR | tour measurement of Timeline Options and reminders More at 1440; browser runs here take 5 to 10 minutes each at this load
984 | built | reminderNoticeKey(): reminder:<id>@<due_at>, so a snoozed reminder overdue again is a new row; tests/test_notif_dismiss.py
985 | decided | no streak surface: the dock is at its grammar and .dock-chip-row is held at zero uses; recorded in TIMELINE_PLAN decisions (21)
986 | deferred-next-PR | 24 toast sites each need a judgement whether the condition is expected; one batch with 993
987 | not-reproduced | 401s on boot while sweeps unlock: not seen in 8 boots on this run's server log
988 | built | settings-packages.js: a refusal the server words is an info notice, a failed request stays red; tests/test_no_report_on_expected.py
989 | built | ai-tools.js: the missing-models notice is a toast with an Open Settings, Models button (toastAction); tests/test_no_report_on_expected.py
990 | not-reproduced | tline-misc at 1440: #reminder-presets display none, rect 0x0 while the menu is closed, so it cannot overlap the chips
991 | done | SESSION_BRIEFS Brief 5 marked built (TIMELINE_PLAN exists, ui-sweeps/timeline.js)
992 | done | SESSION_BRIEFS Brief 6 marked: built under test_entries_keyset_paging.py, test_list_paging_f2.py, test_gallery_paging.py; the named file was never written
993 | deferred-next-PR | 24 sites, each a Try again bound to its own function (LOGS_ACTION_CAP 24 stays)
994 | deferred-next-PR | 338 sites; a per-site retry is a design pass
995 | done-already | Add: reminderMadeUndo (shell-reminders.js); Mark done: reminderPutUndoably 'Completed a reminder'; also edit, snooze, bin, clear completed, reschedule
996 | done-already | status.js appStackIsNewer (DOCUMENTS 24 row 1): Ctrl+Z walks whichever of the app stack and the editor history is newer, so a delete (deleteDocumentWithUndo, pushUndo) is undone first; Archive and a new document still push nothing (left in OPEN.md)
997 | done-already | routes_reminders.Recurring accepts rec.STORED_RULE (RRULE: every weekday, every 2 weeks, last Friday, yearly); quickadd.js QA_RULE keeps them; fixtures recurrence_1010.json
998 | built | saveQuickNote's held branch says the reminder was not set; tests/test_no_report_on_expected.py
999 | deferred-next-PR | waits on Brief 67's act registry (the row says so)
1000 | decided | a chip wrapping to two lines with no overflow is the intended behaviour; #timeline-count is hidden at 390 (0x0)
1001 | not-verified | needs a 1 to 3B model; scratchpad/llama-dev.sh not run here
1002 | done-already | pushDocAiUndo already calls pushUndo, the row itself says nothing to fold
1003 | deferred-next-PR | L row, no work
1004 | done-already | a status report in room101-1011.md (counts and what moved), nothing to build
1005 | done-already | ownerfix3-1011.md: 0 actions share the close button's row at 1440 and 390
1006 | built | apiJson: a silent write that gets a 401 draws the lock screen once (app.js); tests/test_no_report_on_expected.py
1007 | built | addReminder names the missing part; tests/test_no_report_on_expected.py
1008 | built | POST /models/warm-filing queues the warm-up only when the model runner answers; tests/test_models_api.py
1009 | done-already | grep found no toast built outside status.js; the bell's rows are changed in commit for 811 by another agent
1010 | built | 06-timeline-dialogs.css: border-collapse separate + radius on the first and last cell of a hovered or selected row; measured 2.4px at all four corners
1011 | built | #toast-box z-index 2150 (above the confirm overlay 2100); measured: a toast action under an open confirm is hit by elementFromPoint at 1440
1012 | blocked | the code is on agent/voiceup-1011, not on this base
1013 | decided | TIMELINE_PLAN decision 27: no events table; meetings, reminders and dated notes are the events
1014 | done-already | agent.py:423 'The user can already see which tools you ran, in order. Do not narrate'
1015 | built | toastName(): bin and restore toasts name the thing (reminders, documents, library and graph notes)
1016 | built | reminder-notify.js and the bell say 'About <note>' from target_title
1017 | deferred-next-PR | composer work (skipped by the brief)
1018 | deferred-next-PR | composer work (skipped by the brief)
1019 | done-already | settings-controls.js:778 shows the first-run line only while the host state is 'Not installed'
1020 | deferred-next-PR | composer work (skipped by the brief)
1021 | waits-on-owner | built in 543, waits on the owner's look
1022 | done | SESSION_BRIEFS Briefs 2 to 6 each carry a Status line with evidence
1023 | not-reproduced | tline-misc: the rail mark centre is 0.5 px below the first line's centre on 8 rows at 1440 and at 390 (sub-pixel rounding), not a visible offset
1024 | done-already | decision 14: month at 1024, week at 768, agenda below; verified 1440/390 this run
1025 | done-already | decision 15: reminders and meetings as rows, day page in the head; notes were dots, now chips where the cell has room
1026 | done-already | decision 16: timelineCalDrop, timelineCalMoveReminder, timelineCalMovePage (undo bar)
1027 | done-already | decision 17: Add all to calendar (.ics) and Import a calendar (.ics) in the reminders More menu; tests/test_reminders_ics.py
1028 | done-already | decision 18: timelineCalKeys (T, arrows, PageUp/Down, Enter, N); Enter and Space now open the day
1029 | done-already | decision 19: renderReminderCalendar is gone; the reminders Calendar button opens the Timeline calendar filtered to reminders
1030 | deferred-next-PR | d3.v7.min.js is 280 KB; loading it for date labels the timeline already makes with Intl.DateTimeFormat contradicts the boot diet
1031 | deferred-next-PR | design pass (one first-run queue): needs Opus design and a fresh-profile measurement
1032 | deferred-next-PR | L row, no work
1033 | deferred-next-PR | design pass over every bar (one select, one filter trigger); a lint counts each
1034 | deferred-next-PR | an audit of every destructive action; tracked as row 1082
1035 | deferred-next-PR | needs a Settings control and a shared formatter across ~100 sites
1036 | done-already | #toast-box sits at bottom: status-bar-h + space-3 with is-yielding over the focused control (01-forms-settings.css)
1037 | not-verified | needs a seeded notebook sweep of every widget
1038 | deferred-next-PR | composer/engine spec (skipped by the brief)

owner | built | Calendar Month/Week/Day strip slides: the head and the strip are kept between paints (`timelineCalMount`, `timelineCal.spanSeg`), so `glideStrip` has a position to slide from; `tests/test_timeline_cal_span_glide.py`. Chromium 1440: indicator transform at 30 ms steps matrix tx -5.0, -2.6, -0.2, then none; before the fix it was none throughout (moving the strip cancelled the animation). Reduced motion: no mid-glide transform sampled (jumps)
994a | built | reminders bulk delete/restore: a failure toast offers Try again for just the rows that failed (shell-reminders.js)

Pre-existing red on the base, not touched: `tests/test_error_toasts.py` (stale `skills.js` EXPECTED entry, `settings-controls.js:1538` toast not in FAULTS).

## Not verified
- Every browser run was at a load average of 45 to 60 (ten agents gating at once): timings are not claimed anywhere.
- Real inference, a 1,000-note month, a touch drag on a tablet, the desktop launcher's notification body (it does not yet say what the reminder is about), and the floating New at the end of the reminders list at 390.
- The full suite was not run. Failing on the base commit 1da846803 and not touched by this work: see the report (test_error_toasts.py) and `tests/test_reminder_notifier.py::test_a_reminder_fires_once_with_no_window_and_done_from_it_marks_it_done`, which failed once at 5.03 s against its 5 s bound under that load.

## Found, not fixed
- The feed's Last-year range filters by when a note was written while the calendar filters by where it sits (row 972); a note saved before the dates fix is read again only when it is edited (no backfill job).
- A note naming two dates sits on the first only (the feed has one row per note); the calendar could show it on both.
- `scratchpad/ui-sweeps/calendar.js` still asserts at most three rows a cell; the month cell now holds as many as its height allows.
- `help_chat.py` carried the reminders edit-form sentence in the first commit; the form itself landed in the second.
