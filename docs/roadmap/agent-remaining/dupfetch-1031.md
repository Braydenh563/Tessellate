# dupfetch-1031 remaining

- done: step 1 duplicate requests (auth/status, ask-history/stats, models/status); sweep in agent scratch (reqs.js), not committed
- done: step 2 avatar fallback (lazy-entries.js plainHead, emblemHead, charactersLost; tests/test_characters_lazy.py)
- next: step 3 Notes sub-tab restore (navigation.js showNotesSection, initNotesSubtabs)
- next: step 4 `_density` on cursor pages (grep CODEMAP)
- found, not fixed: /conversations vs /conversations?limit=1 and /reminders?include_done=false vs ?limit=200 at boot are different queries, not shared; /models/status and /tasks twice on Settings are the poll tick (3 s), not a duplicate
