# composer6-1031 (INBOX 1487, 1490): remaining

Branch agent/composer6-1031, port 8836, data /tmp/claude-0/composer6-data. Probes (not in the repo): a Playwright driver and a seed script in the session scratchpad `c6/`.

## Done

- 1487, notes that mention a word: `commands._word_notes` reads "notes mentioning/containing/with X" (and "any notes with the word X") as a find; `tool_say.matched` and `_total` make the count said equal the notes matched; `chat_extra.mentioning` counts through the same search so the offered count and the list agree. Commit f9b53a2. tests/test_mentions_1487.py.
- 1490, an unplaced message is never sent to the web: `composer_unplaced` (worthy, unplaced, bare_word, clarify, chips); `_web_first` needs an asked web or a lookup when no note matched; the question back carries "Search my notes for X" and "Search the web for X" (second chip "What can you do?" with the web off). Commit f9b53a2. tests/test_unplaced_1490.py.
- 1490 addendum, a language as a note property: `note_language` (Unicode script, Latin-script languages by everyday words that beat English and every rival), `chat_extra.language_events`; a notes-naming miss offers the web as a chip. Commit 4c3293a. tests/test_note_language_1490.py.
- 1490 addendum, SearXNG down: `composer_web.down_buttons` and `search_down`: Start SearXNG (only when the app can launch it), Set it up in Settings, Open the web panel, Use another provider; no docker command. `digestOffer` handles `searxng-start` and the `web-panel` surface. Help (websearch and search topics) updated. tests/test_searxng_down_1490.py.

## Next

Nothing left of the brief. Not verified: a real model on (only the fake-transport parity test), a machine where SearXNG starts (here the start route answered 503, the button came back), Windows webview.

## Found, not fixed

- composer_extra.py "I can not start it for you" and its "how do I start searxng" how-to still show the docker command (tests/test_composer_study_1025.py:293 and tests/test_composer_four_1025.py:59 assert it); the buttons are only on a failed search.
- "do you like me" and "what do you think" fall to the newest-notes fallback; the "who" pool in composer_social still says "the assistant".
- tests/test_complexity.py fails at the base for 7 functions over 15 and the lazy import cycle (none in files this branch added); tests/test_composer_route_688.py::test_the_composed_turn_is_saved_with_its_rows uses the real clock.
