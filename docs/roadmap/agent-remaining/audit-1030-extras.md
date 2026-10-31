## File-to-agent map (so nothing is left out)

Method: `ls frontend/js src/tessellate/api src/tessellate/core` on this head (merged with `claude/sharp-thompson-45hngp`, 665a58d), compared with the 1029 map: 187 JS files (was 183), 74 api modules (was 72), 79 core modules (was 77). Every file is assigned to exactly one feature agent of the 13 in `.claude/skills/deep-audit/SKILL.md`; `deep-audit-backend` also owns every Python module as a blanket, `deep-audit-ux` and `deep-audit-perf` cross every surface. No file is unowned and none has two owners. The 1029 map stands; only the eight files below are new on this head and are assigned here.

New since 1029 (not in the old map): `notes-lazy.js` (notes: row expand and bell nudges moved out of notes-list.js), `appearance-panel.js` (extras: theme and background art, the Appearance quick panel), `load-failed.js` (shell: the failed-load state of navigation.js), `diag-report.js` (extras: next to lag-watch), `api/routes_diag.py` (extras: `GET /diagnostics`), `api/bounds.py` (backend: request caps), `core/deadline.py` (harness: model deadlines per route), `core/diagring.py` (extras: ring buffers behind /diagnostics).

### frontend/js (187 files)

| agent | files | file list |
| --- | --- | --- |
| extras | 36 | account-recovery, appearance-panel, batch-space, bg-art, boot-guard, captions, chord-guide, clip, diag-report, first-run, lag-watch, lan-watch, margin-reader, media, meetings, ocr-engine, offline, offline-split, panel-movable, questions-view, quick-access, reveal-targets, semantic-notice, shared-intake, sketch-pad, spaces-find, statistics, theme-boot, tour, translate, translate-worker, update-dialogs, usage-ledger, utility-tools, web-clip, writing-desk |
| notes | 45 | attach-to, attachment-actions, autocorrect, capture, capture-ask, categories-panel, chip-menus, connections, dash-orphans, drag-edge, edit-conflict, editor, embed-choices, entity-page, file-drop, library-pick, lightbox, lightbox-actions, lightbox-view, link-types, markdown, math-editor, meaning, nav-history, note-cards, note-edit-panels, note-history, note-panels, note-pick-preview, note-properties, note-templates, notes-lazy, notes-list, notes-rail-spy, pick-row, quick-note, quickadd, rich-picker, search, search-suggest, selection, suggestions-inbox, tag-manager, tag-suggest, tidy |
| graph | 3 | graph, graph-canvas, graph-worker |
| harness | 12 | activity-panel, agent-activity, ai-tools, chat-agent, chat-tasks, feature-model-sheet, model-bench, personas-pane, settings-models, settings-packages, skills, task-steps |
| code | 6 | documents-code, documents-codekit, documents-ide, run-core, run-debug, run-tests |
| board | 11 | dash-boards, icon-picker, mermaid-draw, whiteboard, whiteboard-commands, whiteboard-format, whiteboard-history, whiteboard-interchange, whiteboard-library, whiteboard-map, whiteboard-templates |
| docs | 9 | documents, documents-prose, documents-word, harper-worker, improve-panel, mermaid-frame, standalone-undo, undo-kit, undo-store |
| ai | 22 | ask-chart, ask-compose, ask-history, assistant-avatar, atlas, atlas-life, atlas-micro, atlas-motion, avatars, chat, chat-attach, chat-edit, chat-time, chat-undo, companion-menu, companion-throw, companion-travel, gesture-kit, help-chat, manual, reply-kit, screen-context |
| shell | 43 | app, app-features, app-import, app-palette, dash-day, dash-night, dashboard, date-field, field-clear, lazy-entries, library, load-failed, menus, navigation, notifications, onboarding, palette, phone-more, phone-shell, prefs, reminder-notify, router, router-overlays, settings, settings-controls, settings-data, settings-find, settings-health, settings-panes, settings-rows, settings-wiring, sheets-selects, shell-reminders, status, status-panels, store, timeline, timeline-cal-add, timeline-calendar, timeline-detail, timeline-ticks, vault-unlock, wiring |

Count check: 36 + 45 + 3 + 12 + 6 + 11 + 9 + 22 + 43 = 187. Judgement calls the next audit can move: `icon-picker` board (also docs and spaces), `screen-context` and `gesture-kit` ai, `drag-edge` notes, `date-field`, `field-clear`, `reminder-notify`, `settings-health`, `settings-find`, `load-failed` shell, `task-steps` harness, `lazy-entries` shell, `panel-movable`, `chord-guide`, `reveal-targets` and `appearance-panel` extras but cross-surface (the ux agent looks too), `settings-rows.js` shell (Settings panes build; owns the 211 ms onload in Y5).

### src/tessellate/api (74 modules)

| feature agent | modules |
| --- | --- |
| extras | asset_strip, paging, routes_captions, routes_debug, routes_diag, routes_lag, routes_meetings, routes_questions, routes_recordings, routes_resurface, routes_spaces, routes_statistics, routes_translate, routes_update, routes_usage, routes_utilities, routes_vision, routes_voice, routes_webclip, this_computer, versioning |
| notes | edit_conflicts, routes_bookmarks, routes_categories, routes_drafts, routes_duplicates, routes_editor, routes_entities, routes_entries, routes_files, routes_import, routes_inbox, routes_mentions, routes_properties, routes_relations, routes_search, routes_tags, routes_tidy |
| graph | routes_graph |
| composer | routes_read |
| harness | routes_bench, routes_capabilities, routes_chat, routes_insights, routes_learned, routes_models, routes_night, routes_tasks, routes_websearch |
| ai | chat_extra, routes_ask_history, routes_conversations, routes_help |
| board | routes_board_history, routes_board_library, routes_map_from_notes, routes_map_suggest, routes_whiteboard |
| docs | routes_documents |
| code | routes_code_assist, routes_code_snippets, run_sandbox |
| shell | routes_auth, routes_backups, routes_library, routes_maintenance, routes_privacy, routes_reminders, routes_settings, routes_timeline |
| backend | __init__, app, bounds, schemas |

Count check: 21 + 17 + 1 + 1 + 9 + 4 + 5 + 1 + 3 + 8 + 4 = 74. `routes_auth` still has no single owner: the lock card is shell, recovery and LAN are extras (re-checked below).

### src/tessellate/core (79 modules)

| feature agent | modules |
| --- | --- |
| extras | desktop_dialog, diagring, diskspace, extra_downloads, extras, filetypes, first_password, hardware, imagesize, lagwatch, lancert, lanlive, lanserve, lantrust, launch_status, media_gc, media_process, netbind, netid, ocr, password_reset, pdfpages, qrsvg, quit_hook, reading_bin, readings, recordings, reset_code, startup_status, transcript, usage, webclip, window_hook |
| notes | embedfind |
| harness | activity, bgtasks, deadline, embedmodels, embedswitch, filejobs, jobruns, jobs, jobstore, lookahead, model_gate, passes, subproc, taskhistory |
| board | board_thumbs |
| docs | docexport, docmeta, docview |
| code | syntaxcheck |
| shell | background, backup, backup_bundle, doctor, ics_import, maintenance, reminder_notifier, reminder_token, undo_bin |
| backend | __init__, atomic_io, config, crypto, database, deps, egress, envnames, events, instance_lock, logbuffer, native_imports, origin, pinstore, privacy_http, security, vault |

Count check: 33 + 1 + 14 + 1 + 3 + 1 + 9 + 17 = 79. Gaps found in the skill: none for files. One for the skill text: `deep-audit-extras` should list "diagnostics report" and "appearance quick panel" in its scope line (both are extras files that were added after the scope text was written).

## Audit 2026-10-30: extras

Head: worktree merged with `claude/sharp-thompson-45hngp` (665a58d). Port 8794, data dir `/tmp/claude-0/da-extras`, 13 to 21 notes, scripts in `/tmp/claude-0/da-extras-scr`. No model, no embedding package, no speech, OCR, translation or caption engine is installed here, so every provider path is unreached (CLAUDE.md 4: every provider test runs on a fake transport; real inference is unverified). Mode: `run` = driven in a browser or over HTTP and measured; `code` = read only. Builds on `audit-1029-extras.md` (ids X1 to X28): each is re-verified in "Re-verified" and none is re-listed unless it still reproduces. New ids here are Y1 and up.

## Coverage

| scope | rows | run | code | not reached |
| --- | --- | --- | --- | --- |
| extras frontend files | 36 (525 functions in CODEMAP) | 18 | 16 (captions, translate, translate-worker and shared-intake need an engine or a share-sheet launch) | 2 (clip.js, offline.js: covered by 1029) |
| extras api modules | 21 | 14 (HTTP probed with and without a token) | 7 (asset_strip, paging, resurface, update, vision, this_computer, versioning) | 2 operations (update apply, captions audio: need a network or a mic engine) |
| extras core modules | 33 | 6 through their routes | 25 | 2 (lanserve, window_hook: need a second device or the desktop shell) |
| routes, unauthenticated | 629 operations from /openapi.json | 629 | | |
| surfaces driven at 1440x900 and 390x844, light and dark | sketch, new meeting, voice note, recordings, statistics, tour, onboarding, space create, space menu, notifications, OCR workspace, writing room, questions, Appearance panel, Settings (12 sections), lock card and forgot flow | | | |

Per-file status (functions from CODEMAP):

| file | funcs | mode | what was done |
| --- | --- | --- | --- |
| account-recovery.js | 19 | run | lock card wrong password, forgot flow opened, Account pane read |
| appearance-panel.js | 16 | run | open, tab order, Peek, Esc, reopen Settings afterwards, axe, 4x timing |
| batch-space.js | 5 | run | delete-space dialog: safe option preselected, count, focus |
| bg-art.js | 36 | code | timer and pause logic read (interval cleared on restart) |
| boot-guard.js | 0 | code | boot script |
| captions.js | 15 | code | engine not installable here |
| chord-guide.js | 4 | run | typed letters in the voice title: no chord fired |
| clip.js | 0 | not reached | covered by 1029 (clip.html with a fragment) |
| diag-report.js | 11 | code | read; the data it copies checked through `/diagnostics` |
| first-run.js | 14 | run | name step: blank, markup, long, focus |
| lag-watch.js | 22 | run | its own log read through `/logs/lag` after the walk |
| lan-watch.js | 19 | code | loops pause while hidden (checked); no second device |
| margin-reader.js | 9 | code | needs a model |
| media.js | 11 | run | sketch card; dictation and speech not reached |
| meetings.js | 99 | run | new meeting sheet, Enter, voice note, record, pause, chunk failure, close |
| ocr-engine.js | 9 | run | workspace opened on a picture: focus, buttons, copy |
| offline.js | 0 | not reached | covered by 1029 |
| offline-split.js | 2 | code | |
| panel-movable.js | 36 | run | grip, reset button present on every dialog opened |
| questions-view.js | 8 | run | empty state, counts |
| quick-access.js | 9 | code | keyboard move (Alt+Arrow) and Move left/right menu items read |
| reveal-targets.js | 19 | code | |
| semantic-notice.js | 5 | run + code | the offer toast on phone; handlers read |
| shared-intake.js | 2 | code | text assembly read; needs a share-sheet launch |
| sketch-pad.js | 0 (1,799 lines, no top-level functions in map) | run | draw, undo and redo, caption, save, reopen, Esc |
| spaces-find.js | 25 | run | switcher keys, create, Enter, duplicate, delete, row markup |
| statistics.js | 25 | run | text read, axe, timing |
| theme-boot.js | 0 | code | |
| tour.js | 47 | run | 24 of about 40 steps sampled at 1440 and 18 at 390: no card off screen, no card over its spotlight |
| translate.js, translate-worker.js | 6, 5 | code | package not installed (`/translate/status` read) |
| update-dialogs.js | 5 | code | `update_choice_made` is server-owned and already true here; Escape path read |
| usage-ledger.js | 6 | run | Statistics usage block and `/usage` probes |
| utility-tools.js | 17 | code | timer logic read in full (Y6) |
| web-clip.js | 11 | code | reader builds with textContent only; API probed with web off |
| writing-desk.js | 8 | run | no-model state, screenshot |

## Findings

Severity: high (data loss or a blocked person), med (wrong or unsafe behaviour a person meets), low (polish or hardening). Kind: bug, ux, ui, a11y, copy, perf, security, data.

| id | sev | kind | finding | evidence | verified | fix (the class) | effort |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Y1 | high | data | **Fixed 881588c.** A recording keeps going while its chunk uploads fail, says nothing, then carries on after the gap. `meetingTakeAppend` stores the error in `meetingTake.failed` and swallows it; nothing shows it until Stop. The status keeps the old byte count and no error state, the failed slice is never retried, and later chunks append, so the saved file has a hole. Server side, `append_chunk` writes with no out-of-space handling (a full disk is a 500), though `core/diskspace.out_of_space` exists for the auth and backup routes. | `/tmp/claude-0/da-extras-scr/s20.js`: Playwright route answered 507 to `/recordings/*/chunk` from t=12 s to t=36 s. Status stayed "Recording. 152 KB saved so far." (12 failed uploads, no toast, status class `status`, no `error`); after uploads came back it read "313 KB saved", i.e. the audio of 24 s was never written. At Stop the status read only "disk full", no toast. `meetings.js:667-683` and `:700`; `routes_recordings.py:159-185`. | run | Class "a live capture says the moment it stops saving": keep unsent chunks in a queue and retry, show "Not saving: <reason>. Retrying" in the status line with the error style on the first failure, offer Stop and Keep what is saved, and map out-of-space to 507 with the same sentence the backup routes use. Same helper for the voice note, meeting, trim and enhance uploads. | M |
| Y2 | med | ux | **Fixed 881588c.** "Search by meaning is not installed yet" is shown as an error in three places on a notebook that has simply not been asked yet, against the owner's 2026-10-27 rule in `semantic-notice.js` ("nothing shown as an error"): a permanent red cross chip at the bottom left (`#ai-status`, `data-level=error`, "AI status: Search AI didn't load"), a toast every session ("Search by meaning is not working. Search is using keywords for now. Fix it", `status.js:2529-2547`), and a bell row of the same title. The calm question toast ("needs a one-time download of about 130 MB ... Download / No thanks") appears too, so a person sees "not working" and a question about the same thing. The "No thanks" close handler also swallows a failed save (`semantic-notice.js:100`). | Screenshots `s3-ocr.png`, `s7-writing.png`; `s23.js` read the chip html (`data-level="error"`, text "AI status: Search AI didn't load"); notifications text lists the row; phone run captured the offer toast. | run | Before the person has answered the question, the chip, toast and bell row read as "Search by meaning: off until you allow the download" in the neutral state; only an install that was allowed and failed is an error. One state function feeds all three. | S |
| Y3 | med | a11y | **Fixed 62d0289.** On a phone the Settings, Packages page has no visible or accessible heading for its collapsible section: the `h3` inside the summary is hidden (`jump-echo`, because the page select already says "Packages"), so the `summary` has only a chevron and a help icon. axe: `summary-name` (serious) at 390 only; the same section is named at 1440. | `s13.js` at 390: `details[data-fold-key="extras-packages"] > summary`; `s14.js`: summary `innerText` is empty; screenshot `s13-extras-390.png` shows a bare chevron row. | run | A hidden echo heading must stay in the accessibility tree: use the visually-hidden class, not `display:none`, in the one `jump-echo` rule, and give a `summary` an explicit `aria-label` when its text is echoed. | S |
| Y4 | med | a11y | **Fixed 881588c.** Every space row has actions named only "Hide this space's contents from All spaces", "Rename this space" and "Delete this space", so with nine spaces the menu holds nine identical "Delete this space" items; a screen reader or voice control cannot say which. The titles carry no name either. | `s5.js` listed the menu items: nine copies of each label for nine spaces. `spaces-find.js:247-306` sets `aria-label = title` with no space name. | run | Name the object in the label ("Delete Work"); same helper for every row-action button in menus (check Library cards and the boards list for the same pattern). | S |
| Y5 | med | perf | Still open (X15, partly fixed): the dashboard builds 12,706 DOM nodes on a 13-note notebook and 11,203 of them are hidden. The Library board view holds 2,480 (the board toolbar alone is 953), Settings 2,832 and the Notes tab 1,534, all built before they are shown. Every dialog then pays a full style pass: at 4x CPU, opening Appearance is a 211 ms long task, space create 201 ms (for 39 new nodes), Settings 118 and 81 ms, sketch 112, statistics 101. The app's own lag log recorded `settings-rows.js onload 211 ms (forced layout 74 ms)`. | `s9.js` (node counts per subtree), `s8.js` (CDP `setCPUThrottlingRate` 4, PerformanceObserver long tasks), `/logs/lag`. | run | Build a pane, the board toolbar and the Settings body from a template on first open (the lazy-pane rule the 1029 row 38 started), so hidden subtrees cost no style work; measure again with the same script. | L | **Open, measured again.** 13,033 nodes at boot, 12,716 hidden (library board view 2,395 with the board toolbar 960, Settings 2,943, Notes 1,943). Tried: the board view in a `<template>` stamped when the Library bundle loads; the bundle is preloaded 3 s after boot (app.js `setTimeout(...ensureModule...)` near line 2242) and whiteboard.js binds its ids at load, so the nodes were back before any dialog opened (no gain; reverted). The way in is splitting the whiteboard files out of the preloaded bundle or binding them on first open; neither is a small change.
| Y6 | low | bug | **Fixed a9f6aea.** The timer's "Time is up" can still be late. X14's fix computes remaining time from the clock, but the one `setInterval(paintUtilityChip, 1000)` is what notices the end, and a hidden tab runs it at most once a second and, after a few minutes hidden, about once a minute, so the toast and the notification can come up to a minute late. | `utility-tools.js:62-78` (the tick) and `:50` (the end is only checked in `paintUtilityChip`). Not reproduced (headless does not throttle); read only. | code | Also schedule one `setTimeout` for the nearest end (re-armed on `visibilitychange`), or let the server send the notification. | S |
| Y7 | low | copy | **Fixed a9f6aea.** Still open (W7): the bell lists the app's own housekeeping as news to a new person: "Warm: warm the spelling lists", "Warm: warm the search model" twice, "Housekeeping, at start", "Reading dates in notes, read 0 notes, 0 placed by a date they name", "Backup, saved tessellate-...db". Badge shows 3. | `s4.js` notifications text. | run | Job notices go in the Background tasks list, not the bell, unless they failed or the person started them; do not word a job as "Warm: warm". | S |
| Y8 | low | bug | **Fixed 881588c.** Space names: "ALL" is accepted (id `all-2`), so the switcher shows "All spaces" and "ALL" side by side; "a\nb" becomes "a b" and "‮evil" becomes "evil" (good). `<b>x</b>` is kept as a name (shown as text, safe). The rest of X6 is fixed (409 on duplicates in any case, 400 on blank or over 60 characters). | `p1.py` against `POST /spaces`. | run | Reserve "all" and "all spaces" in the one normaliser. | S |
| Y9 | low | ux | **Fixed a9f6aea.** First-run name step: a blank name does nothing and says nothing; saving a name drops focus to BODY; the name is not checked, so `<img src=x onerror=alert(1)> Ada...` is accepted, and the greeting and the Settings, Profile section heading (an `h3` reading `<img src=x onerror=alert`) show it as plain text. Safe, but wrong-looking. | `s11.js`; `first-run.js:76-88`; Settings Profile heads from `s13.js`. | run | Reject or strip angle brackets and control characters in the display name at the model, say "Type a name first" on a blank submit, return focus to the field. | S |
| Y10 | low | copy | **Fixed a9f6aea.** Statistics still reads "14 more than last week (0)" and "the same as last week (0)" (X13's wording half was not changed), and its "Not used lately" line names 112 palette commands ("Copy diagnostics, Zoom in, Zoom out...") on a day-old notebook, so the usage block is noise until there is history. | Statistics text in `s4.js`. | run | Say "up from 0 last week"; show the unused list only after 30 days of history and only features a person can choose (tabs, not Zoom out). | S |
| Y11 | low | copy | **Fixed a9f6aea.** The path to a setting is written three ways: "Settings > Models" (5 user-facing strings, `first-run.js:141`, `library.js:9429`, `status.js:1029`), "Settings → Logs" (28) and "Settings, Search and index" (60). The status popup reads "Settings, Search and index" and, two lines later, "Settings → Logs". | grep over `frontend/js` and `index.html` for user-facing strings. | run | One separator, one helper (`settingsPath("models")`) that also checks the pane exists; `tests/test_manual_parity.py` can then check it. | S |
| Y12 | low | ux | **Fixed a9f6aea.** `POST /links/clip-page` with an empty selection and no html still creates a note, "# 127.0.0.1 / Source: <url> / The page had no text to keep.", so a bookmarklet fired on a blank page fills the notebook with hollow notes. (The fetch route `/links/clip` correctly refuses with the web off; SSRF forms all refused.) | `p4.py`: two 201s for `http://127.0.0.1:8794/health` and `http://10.0.0.1/`. | run | Answer 422 "That page has no text to keep" when both are empty. | S |
| Y13 | low | bug | **Fixed 881588c.** `POST /auth/reset-code/open-logs` answers 500 when the file manager cannot open (an expected environment failure) after the X11 fix; it should be a 4xx or 503 so a server fault is not logged. | probe: `500 {"detail":"Couldn't open the logs folder..."}`; `routes_auth.py:2134-2155`. | run | Use 503 for "cannot open here". | S |
| Y14 | low | a11y | **Fixed a9f6aea.** A failed Create in the space dialog (duplicate name) shows the error with `role=alert` and keeps focus, but the field is not `aria-invalid` and not linked to the message; the lock card does both. | `s24.js`: `aria-invalid` null on `#space-create-name`. | run | Use the lock card's failure helper in the dialog forms. | S |
| Y15 | low | security | **Fixed a9f6aea.** Hardening, half of X26: an empty upload is refused (422) and `../../evil.png` is stored as `evil.png`, but 16 bytes of text named `.png` are accepted and served as `image/png` (nosniff and the CSP are on, so it is safe). | `s` curl: `POST /media/upload` of `not a png at all`: 200. | run | Check the magic bytes of the picture types. | S |
| Y16 | low | perf | **Fixed 62d0289.** After unlock on the dashboard the page fetches `whiteboard.js` (176 KB gzip) and `documents.js` (155 KB gzip) within 4 s: 146 requests and 1.94 MB in total; the lock card itself needs 60 requests and 1.0 MB. Confirm this is the intended idle preload; it is the biggest boot cost on a phone. | `s21.js` (response sizes). | run | If intended, preload after first interaction on a metered or slow link only; else drop. | S |
| Y17 | low | ux | **Fixed a9f6aea.** The "Check for updates automatically?" question opens as a modal over whatever is open, including a recorder dialog (it intercepted clicks inside the voice note 5 s after boot). | `s1.js`: `.confirm-card` over the recording dialog. | run | Hold it until no dialog is open. | S |
| Y18 | low | copy | **Fixed a9f6aea.** Writing room with no model still says "No model connected" twice (the model select and the banner), W27 not fixed; and the dashboard greets a notebook made seconds ago with "A productive week." | `s7.js` found two visible nodes; dashboard screenshots. | run | One mention; greeting by facts ("14 notes, all new today"). | S |

## Re-verified (the 1029 extras ids)

Fixed on this head, with the check: X1 (focus lands on the title; typing "Hi t a" fired no chord and left the recorder idle), X2 (a `beforeunload` while recording is prevented), X3 (status shows the real size, 24 KB at 2.5 s and 40 KB after Pause, so the flush works; the new gap case is Y1), X4 (roving arrows work, axe clean, light and dark; names are Y4), X5 (delete dialog preselects "Move everything to Default space" and counts), X6 (except Y8), X7 (button reads "Start and open recorder"), X8 (no target under 24 px in the recorder), X9 (reset button on each panel), X10 (axe clean on the sketch), X11 (fixed message; Y13), X12 (Escape answers undefined, read), X16 (copy now "Settings, Profile"), X18 (read), X21 (OCR focus lands on its close button), X23 (lock card: `aria-invalid`, `aria-describedby`, focus kept), X24 (one toast per session; Y2 for the wording), X25 (greeting cut at a word with an ellipsis).
Not driven: X13's private-note line (no private note), X14 (see Y6), X17, X19, X20, X22 (axe clean at the sizes seen), X26 (see Y15), X27, X28.
Old ids still open: W7 (Y7), W27 (Y18), W9 fixed, W11 fixed (Enter creates a space), W30 fixed ("Default space").
Still open from 1029: X15 (Y5).

## Method notes (what was measured)

- Axe (serious and critical, wcag2a to wcag22aa and best practice) on 12 surfaces at 1440 light and 390 light, and 8 of them at 1440 dark: 0 violations except Y3. Settings pane sweep: 12 panes at 1440, 6 at 390.
- Tour sampled by `s18.js` (Enter plus Next double-advanced, so about every second step was seen): no card outside the viewport and no card over its spotlight in 24 steps at 1440 and 18 at 390.
- Diagnostics report: `GET /diagnostics` after requests carrying `SECRETQUERYWORD`, a secret note title and body, a secret space name and a path segment returned none of them, and no home or data path; 310 bytes, counts and slow routes only. This is the redaction the header of `routes_diag.py` promises.
- Unauthenticated probe of 629 operations: every one is 401 or 403 except the documented open ones (`/auth/status`, `/auth/setup`, `/auth/unlock`, `/auth/recover`, `/auth/reset`, `/auth/reset-code`, `/auth/reset-code/open-logs`, `/auth/lock`, `/auth/lan-certificate.pem`, `/logs/client`, `/documents/run-sandbox` and its python page, `/documents/pyodide/*`, `/translate/files/*`, `/reminders/*/notification-act`, `/health`, `/instance`). `/logs/client` is length-capped and rate-limited (30 a minute) and sanitised at the call site.
- Request caps from 1029 hold on the routes I probed: usage (200 features), statistics question (300), questions limit (200), clip url (2,000), media empty file.

## What is already good

- Recording survives a crash and recovers; Pause flushes the audio since the last slice; the status line shows bytes the server really holds.
- The delete-space dialog preselects the safe move, shows the count, and returns focus to the opener on Escape.
- The sketch pad: draw, undo and redo, caption, save to a note with the picture; an empty reopen starts clean; Esc on an empty canvas closes without asking.
- The lock card names its failures (`aria-invalid`, linked message, focus kept) and the forgot flow opens.
- The diagnostics report leaks no note text, title, query string or path.
- Quick access has two keyboard alternatives to dragging (Alt+Arrow and Move left or right menu items).
- Clip reader builds with `textContent` only; SSRF and `file:` forms are refused.
- axe finds nothing on 12 surfaces in both widths (8 of them also in dark) apart from Y3.

## What could not be verified

Real transcription and the speech model, live captions, translate, the margin reader and the Writing room with a model, OCR with an engine, LAN with a second device, an update download, `update_choice_made` first-run dialog (already answered here and not resettable through the API), the share-sheet intake, the pywebview shell, a real microphone (a fake device was used), touch hardware beyond emulation, screen readers, tab throttling in a hidden tab (Y6), and the Guide parity tests.

## Top five

1. Y1 a recording hides failed uploads and leaves a hole in the audio.
2. Y2 "Search by meaning" is an error (red chip, toast, bell row) before the person has been asked.
3. Y5 11,203 of 12,706 nodes are hidden; every dialog costs a 100 to 211 ms long task at 4x.
4. Y3 and Y4 unnamed section on phone, nine identical "Delete this space" actions.
5. Y7 and Y10 the bell and Statistics talk in the app's own jargon on day one.

## Counts

Findings: 18 new (high 1, med 4, low 13). Kinds: data 1, ux 4, a11y 3, perf 2, copy 4, bug 3, security 1.
