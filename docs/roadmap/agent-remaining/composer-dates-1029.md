# Composer dates 1029 (rank 21), remaining

Done: one window reader (`composer_plan.window`), lookback via activity, unit spans, before/by/until, overdue block, plan counts every item. Test: tests/test_composer_dates_1029.py.

Left:
- C24 tail: a bare "the 25th" does not inherit the month of the last answer; it reads the nearer 25th (composer_plan.py `_dated_phrase`). Weekday-with-year for a non-current year is not printed in the lookback (activity.py `_say_day` does print the year).
- C27 tail: "what reminders do I have" still calls an overdue reminder "waiting" (composer_lists.py reminders list).
- C28 tail: tasks beyond OPEN_LIMIT (40) are cut silently (composer_plan.py `_tasks`).
- Lookbacks use the day a note was made (activity.py), not dates written inside notes (audit-1028 E6).
