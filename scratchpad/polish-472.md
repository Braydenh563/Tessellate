# Polish sweep, INBOX 472 ("official, not a demo")

Base f261111. Server on :8855, data /tmp/mm-a855, seeded notebook (13 notes, 1 board).

## Method

- grep of `frontend/index.html` and `frontend/js/*.js` for to-do markers, coming soon, not implemented, lorem, foo, demo, beta, placeholder emails and URLs, console.log/debug/info, "!" and em-dash escapes in strings, and every place a failed response becomes a message.
- Playwright walk (`lib.js` boot): every tab (dashboard, notes with its four sub-tabs, library with all seven sub-tabs, chat, graph, timeline, reminders, documents, whiteboard), the welcome overlay, and every Settings section (21). For each surface the visible text, `title`, `aria-label`, `placeholder` and input values were scanned for `undefined|null|NaN|[object|ISO timestamp|to-do markers|coming soon|lorem|Oops|!|em-dash|HTTP nnn|JSON|API|endpoint|localhost|demo|beta`, then a second pass for `Invalid Date`, bad pluralisation (`1 notes`), `None/True/False`, `${`, `{{`, doubled words. Browser console was captured for log/info/warning.
- A browser probe of `apiJson` against real 422, 404, 405 and a refused connection, before and after.

## Fixed (3 commits)

1. **Error toasts read as sentences** (e3db2ff). Every error toast prints `error.message`, which was the server's `detail` untouched.
   - Before: a validation failure toasted `[{"type":"missing","loc":["body","content"],"msg":"Field required","input":{}}]`; a server fault "Internal error"; a missing route "Not Found"; a dropped connection "Failed to fetch"; chat-agent/documents/capture-ask threw `detail.detail`, which is `[object Object]` when it is a list; upload, import, export, transcription and attach paths said "Upload failed (500)", "Import failed (413)", "Export failed (500)".
   - After (measured in the browser): 422 "Check the content and try again."; a 404 or 405 with no sentence "That could not be found. It may have been deleted." / "That was not accepted. Try again."; 5xx "Something went wrong inside MemoryMap. Try again; if it keeps happening, Settings > Logs has the details."; refused connection "MemoryMap is not answering. Is it still running?". A sentence the server wrote ("Entry not found", "Already downloading x") passes through exactly, because a few callers read it (`/already downloading/i`, `/no checker/`). Callers that know what they were doing pass a fallback ("The upload did not work. Try again.").
   - The raw text and status still go to Settings > Logs (`rawMsg` in `api()`).
   - Where: `plainHttpError` in `status.js` (app.js is 42,944 of 43,000 gzip bytes, so it could not live there), call sites in app.js, chat-agent.js, documents.js (two), capture-ask.js, media.js (two), settings-data.js (two), library.js, settings-wiring.js, lightbox.js, settings.js (support bundle).
   - Ratchet: `tests/test_plain_errors.py`.
2. **Copy** (7cac363).
   - `boot-guard.js` start-up failure notices carried two escaped em-dashes (`—`), which `test_no_em_dashes.py` cannot see because it reads the character. Rewritten with a comma and a full stop.
   - Toasts "Linked!" and "Focus session complete: nice work!" (also the desktop notification) lost the exclamation marks.
   - Settings > Web search read "Settings and the JSON API are configured automatically." and its help said the same; now "SearXNG is set up for you, so there is nothing to edit."
3. **About** (this commit set). Version was already shown (`#about-version`); the licence was nowhere in the UI. Added "Free software, licensed under the GNU Affero General Public License v3." under the version, same recipe (a `.muted` paragraph in the existing hero group). A failed `/health` read used to print "Version ?"; now "Version not available right now". Measured: the hero still fits its box.

## Checked and clean

- Rendered text of every surface above: no `undefined`, `null`, `NaN`, `[object`, raw ISO timestamps, "Invalid Date", `1 notes`-style plurals, template leftovers, "Oops", exclamation marks or em-dashes (Settings > Logs excluded: it is a log viewer and prints uvicorn access lines by design).
- `console.log/debug/info`: none in app code (only inside the vendored harper and codemirror bundles, and a code-snippet string in `documents-code.js:529` that the editor offers as a completion).
- Browser console during the walk: no log, info or warning lines.
- `console.warn/error` that remain (tour.js, whiteboard.js, documents.js, settings-panes.js, settings-wiring.js, attachment-actions.js) are deliberate diagnostics that `recordBrowserLog` mirrors into Settings > Logs.
- To-do markers / coming soon / not implemented / foo / lorem / demo / beta: none in user copy. `lorem` is a typed expansion in the document editor (a feature), "To do" is a note kind, "beta" is the Greek letter picker.
- `<title>`, manifest name and description are product copy.

## Open (not fixed)

- `frontend/js/dashboard.js:297` `withDisplayName`: the greeting accepts `!` as its closing mark from the server (`src/memorymap/api/routes_insights.py:108,124` documents "Morning, Sam!"). CLAUDE.md section 6 says no exclamation marks. A one-line change (always "."), left because the owner may want the warmer greeting; say which.
- Server-written `detail` strings that reach toasts verbatim and use developer words, for example `src/memorymap/api/routes_whiteboard.py:495` "A {kind} object needs content", `:504` "needs a ref_id, the id of the ... it stands for", `routes_whiteboard.py:2890,2996` "No node with id N on this board". Plain enough to read, but they name a field. A sweep of `detail=` across `src/memorymap/api/` for wording would be a Sonnet task.
- `frontend/js/settings.js:977` `stream failed (status)`: shown nowhere (it feeds the live-log retry), left.
- Settings > Logs prints raw uvicorn access lines (`GET /entries ... 200`). Intentional for diagnostics; a "Show server requests" filter that defaults off would make the default view read as a product log.
- Settings > Models and Privacy show `http://localhost:11434` as the backend address, and the Models/Web search inputs use `http://localhost:11434` and `http://localhost:8888` as placeholders. Legitimate (it is the setting), listed because a first-time reader meets it.
- "Export JSON / Import JSON" buttons in Personas, Skills and Import & export: file-format names, kept.
- The greeting "Rise and shine" family and other dashboard microcopy were not re-read line by line for tone; only scanned for the patterns above.
- Lint gap: `tests/test_no_em_dashes.py` reads characters only; the escaped form `—` is now ratcheted for boot-guard.js alone (`tests/test_plain_errors.py`), not repo-wide, because `documents-prose.js:1430` and `markdown.js:111` use it legitimately (typing `--` produces a dash; a quote's attribution parses one).

## Not verified

- A real server fault (a true 500) was not provoked; the 5xx wording was checked by calling `plainHttpError(500, "Internal error")` directly, and the 422/404/405/network paths through `apiJson` in Chromium.
- Dark theme, phone widths and the guided tour copy were not walked for this sweep (copy does not change with them; the tour was not opened).
- Every error toast site was not triggered one by one; they all read `error.message`, which `api()` now sets.
