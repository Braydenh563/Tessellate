# composer6-1031 (INBOX 1487, 1490): remaining

Branch agent/composer6-1031, port 8836, data /tmp/claude-0/composer6-data. Probes (not in the repo): a Playwright driver and a seed script in the session scratchpad `c6/`.

## Done

- 1487, notes that mention a word: `commands._word_notes` reads "notes mentioning/containing/with X" (and "any notes with the word X") as a find; `tool_say.matched` and `_total` make the count said equal the notes matched; `chat_extra.mentioning` counts through the same search so the offered count and the list agree. Commit f9b53a2. tests/test_mentions_1487.py.
- 1490, an unplaced message is never sent to the web: `composer_unplaced` (worthy, unplaced, bare_word, clarify, chips); `_web_first` needs an asked web or a lookup when no note matched; the question back carries "Search my notes for X" and "Search the web for X" (second chip "What can you do?" with the web off). Commit f9b53a2. tests/test_unplaced_1490.py.
- 1490 addendum, a language as a note property: `note_language` (Unicode script, Latin-script languages by everyday words that beat English and every rival), `chat_extra.language_events`; a notes-naming miss offers the web as a chip. Commit 4c3293a. tests/test_note_language_1490.py.
- 1490 addendum, SearXNG down: `composer_web.down_buttons` and `search_down`: Start SearXNG (only when the app can launch it), Set it up in Settings, Open the web panel, Use another provider; no docker command. `digestOffer` handles `searxng-start` and the `web-panel` surface. Help (websearch and search topics) updated. tests/test_searxng_down_1490.py.

- Coordinator follow-ups after the merge: an ask naming a notebook thing, a first-person message, an instruction or a feature word the composer answered is never unplaced (b8d4aee, 69ee2ae); `test_the_composed_turn_is_saved_with_its_rows` pins its clock and the note's date (40150a1); "what about X" is a topic nudge, not general knowledge (a87f633); `question_noise.drop_filler` keeps line breaks, so a numbered list after a colon is steps (f14fc85); `_event_lead` leaves a set-for-later line ("Booked for 14 November") to the plain day (596a5e1); "start it" gives the SearXNG buttons, the docker literal stays only in the Guide's web search topic.

## Next

Nothing left of the brief. Not verified: a real model on (only the fake-transport parity test), a machine where SearXNG starts (here the start route answered 503, the button came back), Windows webview.

## Found, not fixed

- "do you like me" and "what do you think" fall to the newest-notes fallback; the "who" pool in composer_social still says "the assistant".
- tests/test_complexity.py: re-check after the merge (it was red at the base for 7 functions over 15 and the lazy import cycle).
