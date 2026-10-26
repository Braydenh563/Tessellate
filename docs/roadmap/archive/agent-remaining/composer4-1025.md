# composer4 (1025)

Done: composer3 leftovers (turn it on for every off tool, "the second one" and "why" after a plan, cached note dates), flashcards from a category, what did I write about X this week, outline, date counts (until, since, weeks, N before), dog2 composer findings 1, 2, 3, 4, 10 (code and dash), 19 (quiz openings), 23 (unreachable app message), search skipped for app-answered turns.
Measured on 300 notes through /chat/stream (scratchpad/bench_composer4.py, `/tmp/claude-0/rb.py` shape): p95 193 ms, first cold call 800 ms (date cache fill), compare 303 ms warm (old engine).

Remaining:
- compare N-way and as a table (composer.py `_compare`, `compare_sides` is two-sided; not cheap, left).
- Quiz on a whole category (state is the header's topic, one note; composer_study.py `_start_quiz`).
- dog2 10: "Remind you to ..." tails and the "Since you have been in X lately" closing on unrelated answers (composer_digest.py:77, composer_tone.closing).
- dog2 19: "Sources: N notes · meaning + keywords" line on every answer (frontend/js/chat-agent.js:2232; boot JS gzip is full).
- "Heads up: I could not find 14 in your notes" on "how long ago was 1 september" (non-notes-only path, source_check; not an app_first answer).
- Not verified: no real browser run of the Chat "can't be reached" message (node --check only); quiz chips render as offers (route-tested, not looked at).
