# smallc-1108 remaining

Built (one commit each, see git log): T10 pick one of options, T13 week/quarter/day of year/tomorrow's date, Time and date row (week of a date, leap year, days left), T6 text transforms on pasted text, T1 factorial/half/double/sqrt. All in `ai/composer_chance.py`, `composer_clock.py`, `composer_text.py`, `composer_sums.py`, reached through `composer_quick.py` from `composer_extra.answer` (the route's `chat_extra` already calls it, no route edit).

Survey notes (CHAT_PLAN open `| S |` rows are often already built; the plan text is stale):
- Already built, row still open in the plan: T11 dice and coin and "pick a number" (`utilities.py:100`), T5 word count (`composer_calc._word_count`), C6 identity ("Atlas's assistant", `composer_tables.py:1123`), X4 to X18 verbs. Not moved; each needs its own check.
- C1 return-after-a-gap greeting: needs the last chat's date from the route (`routes_chat.py`, at its cap) and `welcome_line` in `api/chat_extra.py`; not pure composer work. Left.
- A17 "then and now": `timetravel.py` is wired in `routes_chat.py:332` to 352 (as-of answers), but the "then and now" line needs revision data from the session; left.
- T6 left: acting on a named note ("uppercase the passport note") needs the confirm-first draft path; join/split on commas; count characters.
- T1 left: round, floor, ceil, min, max, log, ln, pow as words; "2(3+4)".
- Time and date left: Unix epoch.
- Not run: the full composer suite and the full gate (targeted tests and `gate.sh --staged` only). Real-model parity is by design (decision 75: with a model up the model leads; these readers only answer with no model or From your notes); no real-model check was made.
- Gate lesson: `gate.sh --staged` runs ruff over the worktree, so an untracked half-finished file fails it; keep unfinished files outside the repo.
