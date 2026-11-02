# dupfetch-1031 remaining

- done: step 1 duplicate requests (auth/status, ask-history/stats, models/status); sweep in agent scratch (reqs.js), not committed
- done: step 2 avatar fallback (lazy-entries.js plainHead, emblemHead, charactersLost; tests/test_characters_lazy.py)
- done: step 3 no change: the last Notes sub-tab is already restored within a session (measured: Capture kept across Dashboard, Chat and a reload; Ask likewise); a new session landing on Your notes is deliberate (navigation.js `resetNavigationForNewSession`, owner-reported 2026-10, sessionStorage). Not reproduced; ask the owner which path (palette, link, reopen after closing the window) reopens on Your notes
- done: step 4 `_density` skipped on cursor pages (routes_timeline.py, tests/test_timeline.py)
- found, not fixed: /conversations vs /conversations?limit=1 and /reminders?include_done=false vs ?limit=200 at boot are different queries, not shared; /models/status and /tasks twice on Settings are the poll tick (3 s), not a duplicate
