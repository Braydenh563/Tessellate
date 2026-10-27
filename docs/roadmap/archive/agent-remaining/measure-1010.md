# measure-1010: not measured, and why

- Every wall time was taken at load average 8 to 10 on 4 cores (other sessions' browsers and servers); re-run `measure-interactions.js` and `measure-cpu.py` (removed 2026-10-12, recoverable from git history) on an idle machine before Brief 53 fixes a budget. `measure-cpu.py` (removed 2026-10-12, recoverable from git history) showed about 0.8 s of server CPU per second even for a static file, so per-request CPU could not be separated from the background load.
- Search latency of the engine alone (without HTTP and background work) is not isolated; `GET /search` p50 1.8 to 5.0 s is the loaded figure. A trivial route took 1.6 to 2.6 s in the same minutes.
- The first server grew to 8.5 GB resident over 35 minutes of seeding and sweeps; after a restart it sat at 0.74 to 2.1 GB. Not reproduced, cause not found (suspect the dashboard widgets at 5,000 notes: 63 to 66% of a core idle with the dashboard open against 2 to 16% on Notes).
- Board open timed from a direct `openWhiteboardBoard(id)` call, not from a click on the Library tile; document open from `openDocument(id)`, not a click. `first editor text` in the doc run is not trustworthy (the textarea already held text) and is not reported.
- Dashboard widgets were counted for interactive elements in a notebook of plain notes (no reminders, bookmarks, tensions, activity); clicks were not exercised, so "acts" means "holds a button, link or row".
- Settings help mapping is a heuristic (`measure-settings-help.py` header says the rule); 31 of 72 keys have no Settings control it could find, and some may have help the script does not see.
- Key checks written as `key.toLowerCase() === "x"` or `switch (e.key)` are not counted.
- Cold boot excludes the service worker and a warm HTTP cache; no phone-width run.
