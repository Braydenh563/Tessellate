# worldclass-1018: WORLD_CLASS_PLAN rows 32 (INBOX 301) and 29 (section 10 flaws)

Cut short by the coordinator on 2026-10-18 before any fix. No source changed; this file is the audit so far and the list left.

## Step 0: what is built (grep, 2026-10-18)

| Item | State |
| --- | --- |
| F1 `prefs` | Reads and writes through `prefs.js` (one raw `localStorage.setItem` left: `app.js:722`, the auth token, before prefs loads). Row 29's "left: the writes" is done bar that line. |
| F5 `api.stream`, `api.upload`, lint | Built (HISTORY, "Moved from the plans, 2026-10-05 (F1, F5, F12)"). |
| F7 threads onto the pool | Ratchet built; left: model downloads, embedding warm-up (kept apart on purpose), scheduler, searxng and update threads. M, not started. |
| F10 `readings` | Table, route, indexing built; left: one renderer in the Files card reading `GET /files/readings`. Not started. |
| F12 store | `notes` slice built; further slices are L, skipped by the brief. |
| Row 32 undo contract (1.8) | `pushUndo` and the board, map, reminders, timeline selection coverage are built (WHITEBOARD_PLAN "Undo coverage"). |

## Row 32 audit, measured 2026-10-18 on port 8795, fresh data dir, 1440x900 light

Sweeps (session scratchpad, not committed): an Escape sweep over 30 openers, a navigation sweep (21 visits, app Back through all, Forward through all, reload on each address), a browser-Back-with-overlay sweep, and the existing `ui-sweeps/undo.js`.

### Escape closes what opened

| Surface | Action | Result |
| --- | --- | --- |
| Shell | palette (Ctrl+K and status button), finder, shortcuts (?), Guide, agent palette, quick note, quick sketch, nav history menu, other-devices popover | closed by one Escape, 10 of 10 |
| Shell | focus after Escape | back on the opener for the five opened by click (palette, finder, Guide, nav history, other devices); BODY for the agent palette opened by `#status-agent` click (found, not fixed) |
| Dashboard, Notes, Chat, Library, Graph, Timeline, Reminders | help popover (`data-help-for`), 7 of 7 | closed, focus back on the toggle |
| Notes, Library, Graph, Timeline, Reminders, Library boards | dock details menu, 6 of 6 | closed, focus on the summary |
| Dashboard, Notes, Chat, Library | kebab menu, 4 of 4 | closed, focus on the opener |
| Chat input, Notes capture | `/` menu | closed; focus stays in the field |
| Settings | opened by function | closed |
| Not reached (selector misses, not failures) | Dashboard and Chat dock menu (none), Graph, Timeline and Reminders kebab (none or covered), image lightbox (no image in the fresh notebook), reminders add form, notes edit entry (no overlay), graph node panel | open |

### Back and Forward (app buttons), 21 visits

- Every recorded visit came back in order with the right tab and section, and every address reloaded to the same view: dashboard, notes (browse, capture, ask, a note), chat, library (all, documents, images, files, boards, a board), a document, graph, timeline, reminders. 16 of 16 on Back, 16 of 16 on Forward, 16 of 16 on reload.
- By design, not failures: a tab opened and then its sub-section is one step (`recordTabVisit` refines in place); closing Settings records no step.
- Found, not fixed (A): Escape on Settings rewrites the settings entry's address to the tab underneath (`#/reminders`), so Forward onto it shows the wrong hash although the dialog is right; a reload on that entry would open the tab, not Settings. Low impact.
- Found, not fixed (B), the real one: browser Back (`history.back()`) with an overlay open steps the tab history and leaves the overlay open on the other tab. Palette, finder, Guide, shortcuts and quick note: 5 of 5 left the overlay open and moved Timeline to Notes. Settings is right (closes, stays, 1 of 1). On a phone, where Back is the way out of a sheet, this matters more. Not measured at 390.
- Not covered: chat conversation step (the sweep's create call failed), graph focus step, lightbox on Back.

### Undo (Ctrl+Z), existing `undo.js`, 14 surfaces

Per surface, actions found / undoable: notes list 0/0, note editor 1/1, documents 3/2, whiteboard 2/2, mind map 2/0, graph 0/0, timeline 1/1, library 3/3, settings 13/0, dashboard 0/0, chat 2/1, reminders 3/3, agent 1/0, timeline selection 7/6. Total 38 actions, 19 undoable (the run is `undo.js`'s own heuristic, over-inclusive).

- Documents: "Start a new document" is not undone (a create, not a destructive act; the contract covers deletes, moves, filings, imports).
- Settings 0 of 13 and agent 0 of 1: preferences are not edits to the notebook; the 1.8 contract does not list them. Not a failure without a decision.
- Mind map 0 of 2 and chat 1 of 2: not triaged; read `undo.js`'s per-act lines (rerun it with `ONLY="mind map,chat"`) before treating as bugs, since the mind map's own history is not on the app's stack by design.

## Left, in order

1. Fix B: close the topmost overlay on `popstate` before stepping the tab history (palette, finder, Guide, shortcuts, quick note, sheets, lightbox). Test first in `tests/` plus a sweep at 1440 and 390. File: `frontend/js/router.js:221` (the `popstate` listener), `navigation.js:1034` (`goToTabHistory`). No new top-level `let`: a field of an existing state const.
2. Focus return for the agent palette opened from `#status-agent` (`toggleAgentPalette`).
3. Fix A: Escape on Settings should not rewrite the entry's address (`router.js:250`).
4. Rerun the Escape sweep with the six selector misses fixed and the lightbox (needs an image note), then the chat conversation and graph focus Back steps.
5. Triage the mind map and chat undo lines from `undo.js`.
6. Row 29: F10's one Files-card renderer; F7's remaining threads (M); the `app.js:722` token write.
7. Then fold the table above into WORLD_CLASS_PLAN row 32 and INBOX 301's state line; CHANGELOG lines (both files) and `python scripts/codemap.py` with any fix.
