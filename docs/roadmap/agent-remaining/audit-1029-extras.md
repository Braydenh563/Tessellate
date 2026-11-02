## File-to-agent map (so nothing is left out)

Method: every file in `frontend/js` (183), `src/tessellate/api` and `src/tessellate/core` was assigned to exactly one feature agent from `.claude/skills/deep-audit/SKILL.md`; `deep-audit-backend` also owns every Python module as a blanket, and `deep-audit-ux` and `deep-audit-perf` cross every surface. Files marked extras are this audit's scope. No frontend file is unowned and none has two owners.

### frontend/js (183 files, 6702 functions in CODEMAP)

| agent | files | functions | file list |
| --- | --- | --- | --- |
| extras | 34 | 453 | account-recovery, batch-space, bg-art, boot-guard, captions, chord-guide, clip, first-run, lag-watch, lan-watch, margin-reader, media, meetings, ocr-engine, offline, offline-split, panel-movable, questions-view, quick-access, reveal-targets, semantic-notice, shared-intake, sketch-pad, spaces-find, statistics, theme-boot, tour, translate, translate-worker, update-dialogs, usage-ledger, utility-tools, web-clip, writing-desk |
| notes | 44 | 834 | attach-to, attachment-actions, autocorrect, capture, capture-ask, categories-panel, chip-menus, connections, dash-orphans, drag-edge, edit-conflict, editor, embed-choices, entity-page, file-drop, library-pick, lightbox, lightbox-actions, lightbox-view, link-types, markdown, math-editor, meaning, nav-history, note-cards, note-edit-panels, note-history, note-panels, note-pick-preview, note-properties, note-templates, notes-list, notes-rail-spy, pick-row, quick-note, quickadd, rich-picker, search, search-suggest, selection, suggestions-inbox, tag-manager, tag-suggest, tidy |
| graph | 3 | 392 | graph, graph-canvas, graph-worker |
| harness | 12 | 271 | activity-panel, agent-activity, ai-tools, chat-agent, chat-tasks, feature-model-sheet, model-bench, personas-pane, settings-models, settings-packages, skills, task-steps |
| code | 6 | 273 | documents-code, documents-codekit, documents-ide, run-core, run-debug, run-tests |
| board | 11 | 1344 | dash-boards, icon-picker, mermaid-draw, whiteboard, whiteboard-commands, whiteboard-format, whiteboard-history, whiteboard-interchange, whiteboard-library, whiteboard-map, whiteboard-templates |
| docs | 9 | 836 | documents, documents-prose, documents-word, harper-worker, improve-panel, mermaid-frame, standalone-undo, undo-kit, undo-store |
| ai | 22 | 732 | ask-chart, ask-compose, ask-history, assistant-avatar, atlas, atlas-life, atlas-micro, atlas-motion, avatars, chat, chat-attach, chat-edit, chat-time, chat-undo, companion-menu, companion-throw, companion-travel, gesture-kit, help-chat, manual, reply-kit, screen-context |
| shell | 42 | 1567 | app, app-features, app-import, app-palette, dash-day, dash-night, dashboard, date-field, field-clear, lazy-entries, library, menus, navigation, notifications, onboarding, palette, phone-more, phone-shell, prefs, reminder-notify, router, router-overlays, settings, settings-controls, settings-data, settings-find, settings-health, settings-panes, settings-rows, settings-wiring, sheets-selects, shell-reminders, status, status-panels, store, timeline, timeline-cal-add, timeline-calendar, timeline-detail, timeline-ticks, vault-unlock, wiring |

Judgement calls on shared files (so the next audit can move them): `icon-picker` board (also used by docs and spaces), `screen-context` and `gesture-kit` ai, `drag-edge` notes, `date-field`, `field-clear`, `reminder-notify` shell, `settings-health` and `settings-find` shell, `task-steps` harness, `lazy-entries` shell (it only registers lazy bundles), `panel-movable`, `chord-guide`, `reveal-targets` extras but cross-surface (ux agent should also look).

### src/tessellate/api (72 modules)

| feature agent | modules |
| --- | --- |
| extras | asset_strip, paging, routes_captions, routes_debug, routes_lag, routes_meetings, routes_questions, routes_recordings, routes_resurface, routes_spaces, routes_statistics, routes_translate, routes_update, routes_usage, routes_utilities, routes_vision, routes_voice, routes_webclip, this_computer, versioning |
| notes | edit_conflicts, routes_bookmarks, routes_categories, routes_drafts, routes_duplicates, routes_editor, routes_entities, routes_entries, routes_files, routes_import, routes_inbox, routes_mentions, routes_properties, routes_relations, routes_search, routes_tags, routes_tidy |
| graph | routes_graph |
| composer | routes_read |
| harness | routes_bench, routes_capabilities, routes_chat, routes_insights, routes_learned, routes_models, routes_night, routes_tasks, routes_websearch |
| ai | chat_extra, routes_ask_history, routes_conversations, routes_help |
| board | routes_board_history, routes_board_library, routes_map_from_notes, routes_map_suggest, routes_whiteboard |
| docs | routes_documents |
| code | routes_code_assist, routes_code_snippets, run_sandbox |
| shell | routes_auth, routes_backups, routes_library, routes_maintenance, routes_privacy, routes_reminders, routes_settings, routes_timeline |
| backend | __init__, app, schemas |

### src/tessellate/core (77 modules)

| feature agent | modules |
| --- | --- |
| extras | desktop_dialog, diskspace, extra_downloads, extras, filetypes, first_password, hardware, imagesize, lagwatch, lancert, lanlive, lanserve, lantrust, launch_status, media_gc, media_process, netbind, netid, ocr, password_reset, pdfpages, qrsvg, quit_hook, reading_bin, readings, recordings, reset_code, startup_status, transcript, usage, webclip, window_hook |
| notes | embedfind |
| harness | activity, bgtasks, embedmodels, embedswitch, filejobs, jobruns, jobs, jobstore, lookahead, model_gate, passes, subproc, taskhistory |
| board | board_thumbs |
| docs | docexport, docmeta, docview |
| code | syntaxcheck |
| shell | background, backup, backup_bundle, doctor, ics_import, maintenance, reminder_notifier, reminder_token, undo_bin |
| backend | __init__, atomic_io, config, crypto, database, deps, egress, envnames, events, instance_lock, logbuffer, native_imports, origin, pinstore, privacy_http, security, vault |

All of the above are also in `deep-audit-backend`'s blanket scope. Gaps found in the skill: none for files; but `routes_auth` (lock, recovery, LAN) has no single owner (shell for the lock card, extras for recovery and LAN), and the `ranked` file still lists K1 as open although it is fixed on this head (see findings).

## Coverage table (extras scope)

| file | funcs | mode | what was done |
| --- | --- | --- | --- |
| account-recovery.js | 19 | run | lock card forgot flow both panes, wrong key, mismatch, reset code request |
| batch-space.js | 3 | code | batch move not driven |
| bg-art.js | 28 | run | toggled on and off, frames at 1x and 4x |
| boot-guard.js | 0 | code | boot script |
| captions.js | 15 | code | speech helper not installable here; dock states read |
| chord-guide.js | 4 | run | opened by accident from typed letters, seen |
| clip.js | 0 | run | clip.html opened with fragment and saved |
| first-run.js | 14 | run | Get started card: name step |
| lag-watch.js | 11 | run | its own log read through /logs/lag |
| lan-watch.js | 19 | run | status chip and popover (off state); a second device not reached |
| margin-reader.js | 7 | code | needs a document with the model; /editor/read probed by API |
| media.js | 11 | run | sketch opened; dictation and TTS need a mic and voices, not reached |
| meetings.js | 97 | run | new meeting sheet, voice note, record, pause, marker, close while recording, recovery; transcribe not reached (no speech model) |
| ocr-engine.js | 9 | run | OCR workspace and reader menu with no engine |
| offline.js | 0 | run | offline.html at 1440 and 390, light and dark |
| offline-split.js | 2 | code | only drawn with a model offline |
| panel-movable.js | 21 | run | grip keys, persistence, narrow window |
| questions-view.js | 8 | run | empty state only |
| quick-access.js | 9 | run | Edit quick access mode opened |
| reveal-targets.js | 19 | code | catalogue rows not each opened |
| semantic-notice.js | 5 | code | seen only as the Fix it toast |
| shared-intake.js | 2 | code | needs a share-sheet launch |
| sketch-pad.js | 0 | run | open, draw, Esc confirm, axe, toast stacking, phone |
| spaces-find.js | 26 | run | switcher, create, edit, delete, keyboard, axe, phone |
| statistics.js | 24 | run | open, ask, close, phone, panel resize |
| theme-boot.js | 0 | code | boot script |
| tour.js | 47 | run | open, keyboard, Escape, phone, axe |
| translate.js | 6 | code | package not installed |
| translate-worker.js | 5 | code | package not installed |
| update-dialogs.js | 5 | code | update check disabled here; dialogs read |
| usage-ledger.js | 6 | run | Settings usage box seen, API probed |
| utility-tools.js | 12 | run | timer and stopwatch through the palette |
| web-clip.js | 11 | code | web is off; reader and analyse read only |
| writing-desk.js | 8 | run | no model: save empty, chips, save with text; model on not reached |

## Audit 2026-10-29: extras (meetings, media, OCR, captions, clip, writing room, statistics, spaces, tour, first run, LAN, offline, updates, recovery, timers, panels)

Head: worktree merged with `claude/sharp-thompson-45hngp`. Port 8800, own data dir, 8 to 208 notes. Every provider runs against a fake transport (CLAUDE.md 4); no real inference, speech, OCR, translation or caption model was reached. Each row is marked `run` (driven in a browser or over HTTP) or `code` (read only).

## Coverage

- Extras frontend files: 34 (`frontend/js`), 21 driven (`run`), 13 read only (`code`); 453 functions in CODEMAP for them.
- Routes: 171 extras route+method rows probed unauthenticated (all 401 or 403 except the 5 guarded exceptions below); about 45 probed with input and a token.
- Not reached: see "What could not be verified".

## Findings

Severity: high (a person loses data or is blocked), med (wrong or unsafe behaviour a person meets), low (polish or hardening). Kind: bug, a11y, ux, perf, copy, sec, data.

| id | sev | kind | finding | evidence | verified | fix (the class) | effort |
| --- | --- | --- | --- | --- | --- | --- | --- |
| X1 | high | bug | The voice note dialog opens with focus on `#meeting-record`. Typing a title (a space) starts mic recording, and the other letters fire global single-key chords (t opens the chord guide, a opens the Guide). | Typed a title in a fresh dialog; recording started, chord guide and Guide opened over it. Screenshot `record-typed.png`. | run | A dialog's first focus goes to its first field, never to an action button; single-key chords must be inert while any modal is open (one check in the chord dispatcher). | S |
| X2 | high | data | Closing or reloading the tab during a recording gives no warning. `hasUnsavedWork` ignores a live recording; the beforeunload guard covers only document, note form and chat stream. | `navigation.js` ~1729-1757; closed the page mid-recording with no prompt. | run + code | Treat "recording or paused" as unsaved work in the one guard. | S |
| X3 | high | data | Up to 10 s of audio is lost: `MEETING_CHUNK_MS` is 10000 and pause does not call `requestData`, so audio since the last chunk is dropped on pause or stop-by-crash. A recording with size 0 stayed in state "recording" while the status said "Saved as it goes". | `meetings.js`; recorded, paused and recovered: tail missing; zero-size row stuck. Recovery of earlier chunks worked. | run + code | Flush on pause and on stop, shorten the chunk, and show the real saved size instead of a fixed claim. | M |
| X4 | high | a11y | Space menu fails axe: `aria-required-children` (critical) and `nested-interactive` (serious, 8 to 16 nodes), light and dark. `role=option` buttons contain `span role=button` actions; the listbox holds non-option children. Arrow keys do not move through it (ArrowDown twice moved focus to the search field outside the menu). | axe on the open switcher; keyboard run. `spaces-find.js` `spaceMenuOption`. | run | Use the `kebabMenu` recipe (DESIGN.md), or make row actions siblings of the option, and give the list roving arrow keys. | M |
| X5 | high | data | Deleting a space permanently deletes its notes, with the destructive option preselected ("Delete everything in it"), no count of what goes, no undo (restore body is null when the space has rows). Focus goes to BODY after Escape. | Drove the delete dialog and `DELETE /spaces/{id}`, then restore. | run | Preselect the safe option, show "N notes, M documents", and keep the deleted space in the undo bin for the standard window. (Owner decided permanent delete; the preselect and the missing count are the gap.) | M |
| X6 | med | bug | Space names accept anything: zero-width `​`, `a\nb`, "ALL", "all", "default", "Default Space" (collides with the built-in), and duplicates. Renaming to a duplicate returns 200. Re-verified W12 (still open). | POST and PATCH `/spaces` probes; "Work" gave work-2, "work " gave work-3. | run | One name normaliser (trim, strip invisible, collapse whitespace, case-fold) with a uniqueness and reserved-word check, used by create and edit. | S |
| X7 | med | ux | "Start and record" on a new meeting does not record: it opens a second dialog with another Record button. The library "Record" button also opens a dialog first. | Drove both entries. | run | Label by outcome ("Open recorder") or make the click do what it says. | S |
| X8 | med | a11y | `.panel-grip` is 16x16 on every movable dialog (axe target-size, serious: statistics, new meeting, tour, sketch, space create). | axe on five dialogs. | run | Raise the hit area to the token (24 px minimum, 44 on touch) with a pseudo-element, in `panel-movable` once. | S |
| X9 | med | ux | A panel shrunk to 280x188 persists across reopens (`tessellate.panels`); the only way back is a double-click on the head or Home on the grip, which nothing tells a person. | Resized, reopened, read localStorage. | run | Reset-size affordance in the head menu, or clamp to a minimum content size. | S |
| X10 | med | ux | The sketch card stacks above toasts (toast `z-index` auto), so a toast fired from the sketch is hidden or ghosted behind it. axe also flags `.toast-action` contrast at 1.2. | `sketch-toast-1440light.png`; axe. | run | Toasts take the top layer token; fix the action colour in light theme. | S |
| X11 | med | sec | `/auth/reset-code/open-logs` returns the logs path in its error detail to an unauthenticated this-computer caller, although the docstring says no path leaks. | `routes_auth.py` ~2098-2180; HTTP probe. | run + code | Return a fixed message; log the path server-side only. | S |
| X12 | med | bug | Update dialogs: copy says "closes Tessellate AI" (wrong product name); `applyUpdateNow` loops forever on `if (!state) continue` after a transient miss; Escape on the update-choice dialog saves "Don't check" permanently. | `update-dialogs.js` read. | code | Bounded poll with a failure exit; Escape means "decide later", not a stored choice; fix the copy. | S |
| X13 | med | ux | Statistics counts 7 of 8 notes and says nothing: private notes are excluded silently. Copy "6 more than last week (0)" is awkward. | Statistics with one private note. | run | A one-line "Private notes are not counted" under the numbers; reword the comparison. | S |
| X14 | med | bug | Utility timer: a second start silently replaces the first; it uses `setInterval(...,1000)`, throttled in hidden tabs, so the done notice can be late; nothing survives a reload. | `utility-tools.js` read; palette run. | run + code | Store the end time, compute remaining from the clock, allow several, restore on boot. | M |
| X15 | med | perf | Dashboard has about 13,250 DOM nodes with six notes, 16.6k to 19.9k after opening settings and dialogs. At 4x CPU: idle 27 fps with 18 long tasks in 4 s (p95 83 ms); statistics open 779 ms; space menu 1171 ms (tasks to 227 ms); Settings Extras 2567 ms; Appearance 2756 ms (a 365 ms task); tour 1909 ms; voice note 1257 ms. Many tasks repeat 3 to 5 times, which looks like duplicate observers or doubled renders. App's own lag log: `settings.js INPUT#bg-art-toggle.onchange 224 ms (forced layout 133 ms)`. | `d29.js`, `/logs/lag`, PerformanceObserver. | run | Build panes lazily on first open; find the repeated tasks (one observer or listener registered twice); batch layout reads in the toggle handler. | L |
| X16 | med | copy | First-run copy says "Change it in Settings, General"; the name field is in the Profile pane. | First-run card, then Settings. | run | Point to the real pane; add the path to the `reveal-targets` catalogue so a test catches drift. | S |
| X17 | med | data | About health: DB "4.0 KB" is the main file only (WAL is 2.9 MB on disk); "Together 684 KB" versus "Data folder 9.3 MB" are unexplained. | `routes_debug.py` line 89; About panel. | run + code | Sum main + WAL + shm, and label what each total covers. | S |
| X18 | low | copy | Notification detail is built as `${error}. Settings...`, giving ".." when the error ends in a period (embedding error notice). | `status.js` ~2496; seen in the panel. | run + code | Strip a trailing period before joining, in the one builder. | S |
| X19 | low | bug | Digest quotes `"---"` for a note that starts with frontmatter (the meeting note). | Digest after a recording. | run | Skip a leading frontmatter block when taking the quote. | S |
| X20 | low | ux | Writing room with no model: the six quick-start chips (Write up my notes ... Translate) do nothing visible; status stays empty and no toast, while Copy and Insert say "There's no draft to..." and Refine is aria-disabled with its reason only in the title. | `d30.js` on the Writing room. | run | A chip that cannot run says why in the status line, using the same string as the Refine title. | S |
| X21 | low | ux | OCR workspace opens with focus on BODY; the disabled "Read this image" explains itself only in its title. | OCR open, `activeElement`. | run | Focus the first control; put the reason in visible text. | S |
| X22 | low | a11y | Targets and names: `#recordings-search` is 20px high; Settings toggles are 32x18 (hit area not measured); axe `label-content-name-mismatch` on the statistics range select and `#onboarding-skip`; at 390 the space row actions are 16x20 and rows 33px high (44px rule). | axe; rects. | run | Token heights on inputs; names that contain the visible label. | S |
| X23 | low | a11y | Focus is dropped to BODY after: wrong-key recovery failure, space menu Escape after delete. W9 re-verified: lock screen has no autofocus, `aria-invalid` or `aria-describedby`, the wrong text stays in the field and focus stays on submit. | Keyboard runs. | run | One failure helper that sets `aria-invalid`, links the message and returns focus to the field. | S |
| X24 | low | ux | "Search by meaning is not working" toast appears on every boot when no embedder is present (auto-dismiss about 6 to 8 s). | Toast capture over 30 s (`d28.js`). | run | Show once per session, or only when a person searches. | S |
| X25 | low | copy | Greeting name is cut at 60 characters mid-word with no ellipsis; raw markup is shown as text (safe). | Name of 80 characters. | run | Cut at a word and add an ellipsis. | S |
| X26 | low | sec | Media upload accepts any bytes named `.png`, a zero-byte file, a 400-character filename and `../../evil.png` as the original name. Served safely (nosniff, CSP), so hardening only. | `media.py` probes. | run | Sniff the type, reject empty files, cap and sanitise the stored name. | S |
| X27 | low | ux | Margin reader: `catch {}` swallows errors; "Not this" on a date card is not remembered (no `source_entry_id`), so it returns. | `margin-reader.js` read. | code | Log to the lag buffer; send the source id with the dismissal. | S |
| X28 | low | copy | Service worker cache prefix is the legacy `memorymap-assets-` (harmless, noted for the rename). | `frontend/sw.js`. | code | Leave; rename with a cleanup of the old cache name when the rename lands. | S |

## Re-verified (open in the 1028 files, still open)

- W7 partly: the notification panel still lists "Warm: warm the spelling lists", "Housekeeping" and "Model info" rows.
- W9, W12: see X23, X6.
- W11: space create and edit dialogs have no form, so Enter does nothing (still open).
- W24: Live captions shows "0 of 1 installed" with no Install button.
- W27: "No model connected" is shown twice in the Writing room.
- W30: "Default Space" is title case.
- K1: fixed on this head (`/auth/reset` needs the code; wrong code gives 401). The row can leave `audit-1028-ranked.md`.

## What is already good

- 171 extras route+method rows return 401 or 403 without a token, except the 5 guarded ones: reset-code request, its open-logs route, the LAN cert pem, translate files (404), and `/auth/reset` (needs the code; another origin gets 403).
- Server routes stay fast with 200 notes (5 to 56 ms each).
- SSRF, `file://` and `javascript:` clip inputs are rejected; `clip.html` works with its fragment.
- A space name with markup renders as text.
- Esc on the sketch asks before discarding; recordings are recovered after a crash.
- The service worker caches static assets only.
- Tour and onboarding close on Escape; `clip.html` and `offline.html` have no horizontal overflow at 390 or 1440.
- Background art on costs no measurable frame rate.

## What could not be verified

Real transcription and the speech model, live captions, translate, the margin reader with a model, LAN with a second device, update download, the share-sheet intake, the pywebview shell, a real microphone, touch hardware, screen readers, the Writing room with a model, and the Guide parity tests.

## Top five

1. X1 voice note focus on Record starts recording and fires chords.
2. X4 and X5 and X6 space menu a11y, names, and permanent delete with the destructive option preselected.
3. X2 and X3 no recording warning on close, 10 s chunk loss.
4. X8 panel grip 16px on every dialog.
5. X7 "Start and record" does not record.
