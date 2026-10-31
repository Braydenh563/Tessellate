## File-to-agent map (so nothing is left out)

Method: `ls frontend/js src/tessellate/api src/tessellate/core` on this head (branch `agent/audit-1031`, ea47c8b), diffed against the 1030 map (`audit-1030-extras.md`): 207 JS files (was 187), 74 api modules (unchanged), 81 core modules (was 79). The 1030 map stands for every file it names; the 22 files new since then are assigned below. Every file has exactly one feature owner among the 13 agents in `.claude/skills/deep-audit/SKILL.md`; `deep-audit-backend` also owns every Python module as a blanket, and `deep-audit-ux` and `deep-audit-perf` cross every surface. No file is unowned.

New since 1030 (20 JS, 2 core), with the owner given here:

| file | owner | why |
| --- | --- | --- |
| attachment-peek.js, extract-preview.js, chat-private.js, characters-ready.js | ai | the chat's citation peek, extract cards, private chat switch, companion arrival |
| capture-card.js, capture-card-more.js, image-layout.js, math-field.js | notes | the Notes tab capture card (INBOX 1479), picture width and alignment (1465), equation fields (1473) |
| model-menu.js | harness | the model picker (1477) |
| popup-glyph.js, reminder-edit.js | shell | popup heads (1478), the reminder edit form |
| obj-ref.js, obj-order.js, obj-drag.js, obj-reorder.js, obj-clip.js, obj-carry.js, obj-tray.js | extras | the object move system (INBOX 1467): drag to reorder, carry across pages, copy and paste, the tray. No other agent's scope line names it, so it is audited here (first time) |
| desk-companion.js, desk-env.js, core/desk_companion.py | extras | the desktop companion window (INBOX 1464); the drawing files it loads stay ai's |
| core/private_turn.py | harness | the server side of a private chat turn |

### frontend/js (207 files)

| agent | files | file list |
| --- | --- | --- |
| extras | 45 | account-recovery, appearance-panel, batch-space, bg-art, boot-guard, captions, chord-guide, clip, desk-companion, desk-env, diag-report, first-run, lag-watch, lan-watch, margin-reader, media, meetings, obj-carry, obj-clip, obj-drag, obj-order, obj-ref, obj-reorder, obj-tray, ocr-engine, offline, offline-split, panel-movable, questions-view, quick-access, reveal-targets, semantic-notice, shared-intake, sketch-pad, spaces-find, statistics, theme-boot, tour, translate, translate-worker, update-dialogs, usage-ledger, utility-tools, web-clip, writing-desk |
| notes | 49 | attach-to, attachment-actions, autocorrect, capture, capture-ask, capture-card, capture-card-more, categories-panel, chip-menus, connections, dash-orphans, drag-edge, edit-conflict, editor, embed-choices, entity-page, file-drop, image-layout, library-pick, lightbox, lightbox-actions, lightbox-view, link-types, markdown, math-editor, math-field, meaning, nav-history, note-cards, note-edit-panels, note-history, note-panels, note-pick-preview, note-properties, note-templates, notes-lazy, notes-list, notes-rail-spy, pick-row, quick-note, quickadd, rich-picker, search, search-suggest, selection, suggestions-inbox, tag-manager, tag-suggest, tidy |
| graph | 3 | graph, graph-canvas, graph-worker |
| harness | 13 | activity-panel, agent-activity, ai-tools, chat-agent, chat-tasks, feature-model-sheet, model-bench, model-menu, personas-pane, settings-models, settings-packages, skills, task-steps |
| code | 6 | documents-code, documents-codekit, documents-ide, run-core, run-debug, run-tests |
| board | 11 | dash-boards, icon-picker, mermaid-draw, whiteboard, whiteboard-commands, whiteboard-format, whiteboard-history, whiteboard-interchange, whiteboard-library, whiteboard-map, whiteboard-templates |
| docs | 9 | documents, documents-prose, documents-word, harper-worker, improve-panel, mermaid-frame, standalone-undo, undo-kit, undo-store |
| ai | 26 | ask-chart, ask-compose, ask-history, assistant-avatar, atlas, atlas-life, atlas-micro, atlas-motion, attachment-peek, avatars, characters-ready, chat, chat-attach, chat-edit, chat-private, chat-time, chat-undo, companion-menu, companion-throw, companion-travel, extract-preview, gesture-kit, help-chat, manual, reply-kit, screen-context |
| shell | 45 | app, app-features, app-import, app-palette, dash-day, dash-night, dashboard, date-field, field-clear, lazy-entries, library, load-failed, menus, navigation, notifications, onboarding, palette, phone-more, phone-shell, popup-glyph, prefs, reminder-edit, reminder-notify, router, router-overlays, settings, settings-controls, settings-data, settings-find, settings-health, settings-panes, settings-rows, settings-wiring, sheets-selects, shell-reminders, status, status-panels, store, timeline, timeline-cal-add, timeline-calendar, timeline-detail, timeline-ticks, vault-unlock, wiring |

Count check: 45 + 49 + 3 + 13 + 6 + 11 + 9 + 26 + 45 = 207. `onboarding.js` is shell's by the map but the brief names onboarding for this agent, so it was driven here too (row Z15). Judgement calls the next audit can move are the ones the 1030 map lists, plus: `image-layout` (notes, but it draws on boards, the timeline and documents too), `obj-*` (extras, but the Notes list, Library and Timeline cards all carry them).

### src/tessellate/api (74 modules)

Unchanged from the 1030 map: extras 21 (asset_strip, paging, routes_captions, routes_debug, routes_diag, routes_lag, routes_meetings, routes_questions, routes_recordings, routes_resurface, routes_spaces, routes_statistics, routes_translate, routes_update, routes_usage, routes_utilities, routes_vision, routes_voice, routes_webclip, this_computer, versioning); notes 17; graph 1; composer 1; harness 9; ai 4; board 5; docs 1; code 3; shell 8; backend 4. Count check 74.

### src/tessellate/core (81 modules)

The 1030 map plus `desk_companion` (extras) and `private_turn` (harness): extras 34 (desk_companion, desktop_dialog, diagring, diskspace, extra_downloads, extras, filetypes, first_password, hardware, imagesize, lagwatch, lancert, lanlive, lanserve, lantrust, launch_status, media_gc, media_process, netbind, netid, ocr, password_reset, pdfpages, qrsvg, quit_hook, reading_bin, readings, recordings, reset_code, startup_status, transcript, usage, webclip, window_hook); notes 1; harness 15; board 1; docs 3; code 1; shell 9; backend 17. Count check 81.

Gap in the skill text: `deep-audit-extras`'s scope line should name "object move (drag, carry, copy, tray)", "desktop companion window", "diagnostics report" and "appearance quick panel", which are all its files but none is in the line.

## Audit 2026-10-31: extras (run 1 of 14)

Head ea47c8b on `agent/audit-1031`. Port 8840, data dir `/tmp/claude-0/audit-data`: the showcase seed (71 notes, 3 documents, 2 boards, reminders) plus 130 filler notes, 19 boards and 7 documents: 207 notes, 22 boards, 10 documents at the end. Scripts and logs in `/tmp/claude-0/-home-user-Tessellate/93f12151-a3fd-5155-a0c9-bd94105196f9/scratchpad/aud` (`s1` to `s10.js`, `p1.py`, `p2.py`). No model, no embedding package, no speech, OCR, translation or caption engine is installed, so every provider path is unreached (CLAUDE.md 4: provider tests run on a fake transport; real inference is unverified). `run` = driven in a browser or over HTTP and measured; `code` = read only. Builds on `audit-1030-extras.md` (Y1 to Y18, re-verified below) and `audit-1029-extras.md` (X rows). New ids are Z1 and up.

## Coverage

| scope | rows | run | code | not reached |
| --- | --- | --- | --- | --- |
| extras frontend files | 45 (653 functions in CODEMAP; sketch-pad.js contributes 0 because it is one closure) | 24 | 17 | 4 (captions, translate, translate-worker need an engine; desk-companion and desk-env need the desktop shell; clip and shared-intake need a bookmarklet or share-sheet launch: read) |
| extras api modules | 21 (78 routes) | 17 modules, 78 routes probed with a token and edge bodies (`p1.py`, `p2.py`) | 4 (asset_strip, paging, this_computer, versioning) | update apply, captions audio, voice transcribe: need a network or an engine |
| extras core modules | 34 (657 functions) | 8 through their routes (recordings, transcript, webclip, usage, reset_code, password_reset, diagring, lagwatch) | 26 skimmed for risk patterns (subprocess, shell, eval, path joins) and read where a route led there | lanserve, lancert, netbind, window_hook, quit_hook, desktop_dialog, desk_companion need a second device or the desktop shell |
| surfaces driven, 1440x900 and 390x844, light and dark, mouse, keyboard, touch emulation | statistics (with Ask), questions (read, mark answered, drop), sketch (draw, save), new meeting, record, voice note, dictate, recordings, OCR workspace (empty and on a picture), writing room, tour (12 steps at 390, 4 at 1440), Get started and the welcome replay, live captions, count words, translate, appearance panel, theme toggle, other devices (and Turn on), notifications, space switcher, space create, rename, delete, tools and features, Settings Account, Appearance, Packages, About, Health, diagnostics copy, shortcuts, manual, timer, quick access edit, custom order (Alt+Up/Down, mouse drag, undo), copy card and paste into chat, tray (desktop popover, phone sheet, across spaces), recovery key make, lock card wrong password, forgot flow with a malformed and a wrong key | | | |
| axe (serious and critical, wcag2a to wcag22aa and best practice) | 30 surfaces at 1440 (8 of them dark), 30 at 390, plus the tray, space menu, notifications, OCR workspace, recovery dialog, lock card, onboarding: 0 violations | | | |

Per-file status (functions from CODEMAP):

| file | funcs | mode | what was done |
| --- | --- | --- | --- |
| account-recovery.js | 19 | run | Account pane read, Make a recovery key (password prompt, dialog, copy, done), lock card wrong password, forgot flow with a malformed and a well-formed wrong key |
| appearance-panel.js | 16 | run | opened at 1440 and 390, long tasks at 4x, Esc |
| batch-space.js | 5 | run | delete dialog: count, safe default, Undo toast |
| bg-art.js | 36 | run | off by default on this 4-core box; toggled on: script time measured over 5 s; frame-rate and battery logic read |
| boot-guard.js | 0 | code | read in full |
| captions.js | 15 | code | palette entry gives the engine toast; `/voice/captions/*` probed |
| chord-guide.js | 4 | code | read in full |
| clip.js | 0 | code | read: `message` source check, fragment parse, size caps |
| desk-companion.js, desk-env.js | 0 | code | window page read; `core/desk_companion.py` read in full |
| diag-report.js | 11 | run | Copy diagnostics at 1440 and 390 (2.7 KB and 5.0 KB) |
| first-run.js | 16 | code | update-ask gating read (`firstRunTurn`) |
| lag-watch.js | 22 | run | its log read after every walk; node count and flush timer read |
| lan-watch.js | 19 | run | Other devices popover, Turn on (password prompt); loops read |
| margin-reader.js | 9 | code | needs a model |
| media.js | 10 | run | sketch card; dictate (no engine) |
| meetings.js | 101 | run | new meeting, record, voice note, recordings list at both widths; the chunk queue and discard paths read |
| obj-ref.js, obj-order.js, obj-drag.js, obj-reorder.js, obj-clip.js, obj-carry.js, obj-tray.js | 97 | run | read in full; Alt+Up/Down, mouse drag reorder with undo, Ctrl+C on a card and paste into chat, Add to tray, tray popover and phone sheet, tray across a space switch and a reload; touch drag attempted (not reached, see below) |
| ocr-engine.js | 9 | run | workspace on an uploaded picture: focus, Read page without an engine, axe |
| offline.js, offline-split.js | 2 | code | read in full |
| panel-movable.js | 56 | run | grip and reset on every dialog opened |
| questions-view.js | 9 | run | Read notes now, Mark answered chooser, Drop, filter, targets at 390 |
| quick-access.js | 9 | run | Customise, Edit quick access, kebab per tile, Alt+Up/Down read, axe |
| reveal-targets.js | 23 | run | every `reveal:` palette row used in the walks resolved |
| semantic-notice.js | 5 | run | the one calm question toast seen per session |
| shared-intake.js | 2 | code | read in full |
| sketch-pad.js | 0 (1,805 lines, one closure) | run | draw, Save as note |
| spaces-find.js | 25 | run | switcher at both widths, create (Enter), rename, delete, `setActiveSpace` reload |
| statistics.js | 25 | run | opened at both widths, four Ask questions, targets, long tasks |
| theme-boot.js | 0 | code | read in full |
| tour.js | 47 | run | 12 steps at 390 and 4 at 1440: no card off screen or over its spotlight |
| translate.js, translate-worker.js | 11 | code | palette entry; `/translate/status` and `/translate/files/*` probed |
| update-dialogs.js | 6 | run + code | About: Check now on a source install; X12 re-read (fixed) |
| usage-ledger.js | 6 | run | Statistics usage block, `/usage` probes |
| utility-tools.js | 17 | run | timer from the palette, chip at both widths, stop by click |
| web-clip.js | 11 | code | `/links/clip*` probed (web off): SSRF forms refused, empty page 422 |
| writing-desk.js | 10 | run | opened at both widths (no model), long tasks at 4x |

## Findings

Severity: high (data loss, security, a blocked person), med (wrong behaviour a person meets), low (polish or hardening). Kind: bug, missing, ux, ui, a11y, copy, perf, complexity, security, ai.

| id | sev | kind | finding | evidence | verified | fix (the class) | effort |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Z1 | med | ux | The tray cannot carry anything to another space, and a space switch costs a full boot and the Undo stack. The tray is kept in `sessionStorage` under `obj-tray:<space>`, and `setActiveSpace` is `window.location.reload()` (a recorded decision, spaces-find.js:214-218), so a card added in All spaces is gone in Work and back in All, and every switch re-pays the 2 MB boot and empties Undo. "Hold a few objects while you go somewhere else" (obj-tray.js header) excludes the one place that is most "somewhere else". | `s4.js` §4: badge 1 in All, "" in Work (`objTray: []`), 1 again in All; `undoStack` 0 after the switch. obj-tray.js:12-20, spaces-find.js:218. | run | Key the tray by notebook, not by space (a reference is global; a space is a filter), and keep it in the server preferences so a reload and another device keep it. For the switch itself, the decision stands, but the Undo loss and the tray loss should be said once in the decision or fixed by a scoped refresh. | S for the tray; L for the switch |
| Z2 | low | ux | One click on the status-bar timer chip stops it with no confirm, no pause and no Undo: a 25-minute focus timer is lost to a stray click. The toast "Timer stopped with 24:12 left." has no action. Any timer app in its class (the macOS Clock, Forest, Toggl) pauses on the first press and stops on a second or a hold. | `s4.js` §5: chip "25:00", click, `hidden: true`, toast "Timer stopped with 25:00 left.", `undoBtn: []`. utility-tools.js:126-133 and :145. | run | The chip's click opens the one small menu (Pause or Resume, Add 5 minutes, Stop) or pauses; Stop gets `offerUndo` (the stopped clock restored with its remaining seconds). | S |
| Z3 | low | ux | "Tools and features" says "212 things Tessellate can do" and omits about 60 of the palette's own rows: Count words, Translate this, Private chat, Record a meeting or lecture, Dictate a note, New sketch, OCR workspace, Questions your notes ask, Open the bin, Show favourites, Show private notes, Take the guided tour, Health, Activity, Stop the model, Back up now, New workspace, Write a note from rough thoughts. Searching the dialog for "Count words" says "Nothing matches that". The catalogue is the answer to "where is" (checklist, discoverability), so it has to hold everything the palette holds. | `s3.js` §1 ("Nothing matches that: try another word."), `s4.js` §0 (the list of palette-only rows). dashboard.js:1596-1660, app-features.js `featureCatalog`, settings-panes.js:1157-1420. | run | One registry: `featureCatalog` derives its rows from `paletteCommands()` (plus the AI tools), grouped by the row's `group`, and `tests/test_popup_tools.py`'s lint widens from POPUP_TOOLS to every palette row. | S |
| Z4 | low | copy | Y7 is only half fixed: the bell still lists the app's own jobs as news. On a day-old notebook the panel reads "Model info: loaded models", "Resurfacing scored 205 notes", "Night shift read 228 notes, found 55 facts" (the notebook has 207 notes; 228 counts documents and boards as notes). Unread badge 2. | `s4.js` §8 (`notif-list` rows). | run | Job notices go to Background tasks unless they failed or a person started them (Y7's class); a count says what it counted ("228 notes and documents"). | S |
| Z5 | low | a11y | On a phone the Statistics growth chart is twelve adjacent 21 px wide buttons ("November 2025: 0 notes" ... "October 2026: 208 notes"), under the 24 px of WCAG 2.5.8 and the 44 px the checklist asks on a phone; they open the month's notes. | `s7.js` §2: `{"w":21,"h":151}` x12 at 390. statistics.js:100-107, :209-215. | run | Make the bar's hit area the whole column (bar plus gap) or add a "Months" row of 44 px chips under the chart on narrow widths; measure the chart's bars with the same script. | S |
| Z6 | low | ux | Questions, "Drop: it no longer matters": the row vanishes with no toast, no Undo and focus dropped to `body`. It is reversible only by knowing the "Dropped" filter has a Reopen. "Mark answered" is good (a chooser with search). | `s6.js` §4: after Drop `toast: [], undo: [], focus: BODY`. questions-view.js:40 (`move("dropped")`). | run | `offerUndo("Dropped the question", ..., reopen)` and focus to the next row or the filter, as the delete-space dialog does. | S |
| Z7 | low | ux | Sketch "Save as note" closes the pad, toasts "Sketch saved to your notebook." and leaves focus on `body` with the Questions sub-tab still showing; nothing takes you to the note. The space create toast has "Open it"; this one has nothing. | `s6.js` §6: `focus: BODY#`, `hash: #/notes/questions`, toast with no action. sketch-pad.js:494 `saveNote`. | run | One `announceSavedNote` with an Open action for every "saved to your notebook" toast (sketch, voice note, clip, capture), and focus back to the opener. | S |
| Z8 | low | ai | Statistics Ask: "how many reminders are overdue" answers "You have 14 open reminders." (open is not overdue; the notebook has 1 due today); and over HTTP "You have written no notes last week." (should be "You wrote no notes last week"). | `s6.js` §3, `p1.py` `/statistics/ask`. routes_statistics.py:39 and the stats answerer. | run | Add the overdue, due today and this week reminder facts to the stats composer, and refuse rather than substitute when the asked fact is not one it has; past-tense wording for a past week. | S |
| Z9 | low | copy | Y11 leftover: two server strings still write the path as "Settings → About" (routes_update.py:328 and :725), while every other string now reads "Settings, About". The 403 from `POST /update/apply` shows it. | `p1.py` `/update/apply`: `"...in Settings → About first..."`; grep. | run | The same `settings_path` helper the client got, used on the server. | S |
| Z10 | low | complexity | sketch-pad.js is one 1,805-line closure (`(() => { ... })()`), so CODEMAP lists 0 functions for it and the complexity ratchet (`tests/complexity_seed.json`) sees nothing inside it; bg-art.js is 2,803 lines (36 functions) for the background art, tour.js 1,993 and meetings.js 2,686 (101 functions). The same class as B1 (whiteboard's closure). | `grep -c "^function" frontend/js/sketch-pad.js` = 0; CODEMAP; `wc -l`. | code | Name the closure's functions at top level (or in a `const SKETCH = {}` the map can read) so the ratchet and the map cover them; split bg-art.js by style. | M |
| Z11 | med | perf | Still open (Y5, X15): opening a surface pays for the hidden DOM. At 4x CPU on 207 notes: Writing room 1,257 ms of long tasks (304, 298, 588), Settings Packages 755 ms (and one 1,838 ms task at 390 unthrottled), Questions 574, Tools and features 547 (212 rows built on open), Statistics 427, Recordings 372, About 321, Appearance 237. The lag log at boot still reads 12,372 nodes. | `s5-perf.log` (CDP `setCPUThrottlingRate` 4, PerformanceObserver longtask), `s1-390.log` (Settings Packages `lt=[1838,...]`), `/logs/lag`. | run | Y5's class (build panes on first open); for Tools and features, render the first 40 rows and the rest on scroll or on a query; for the Writing room, load CodeMirror only when its box is focused. | L |
| Z12 | low | bug | `meetingTakeDiscard` swallows a failed `DELETE /recordings/{id}` (`catch {}`), so a Discard that fails on the network closes the dialog and leaves the recording in the Library with no word. | meetings.js:1352-1362. | code | Say it (`toast(error.message, true)`) and keep the dialog's Discard enabled; one `try` wrapper for the recorder's writes. | S |
| Z13 | low | ux | On a phone the tray's "paste where you were typing" cannot work from the sheet: the sheet is modal, so nothing is focused when an item is pressed, and the answer is a toast "Click into a chat box, a note or a board first, then choose it." The route is close the sheet, focus a box, reopen the App menu, Tray, press the item. | `s9.js` P1: `use -> true`, toast as quoted. obj-tray.js `objTrayPaste`, `objTrayFrom`. | run | On a phone remember the last destination before the sheet opened (the `focusin` the desktop keeps) and paste there on press, or offer "Attach to the chat" and "Open" as the row's two actions. | S |
| Z14 | low | ui | The Voice note and Record dialogs show a "Live captions" button when no caption engine is installed; pressing it is a toast ("Live captions need a speech helper that isn't set up yet..."). A control that can only explain itself is a dead end on the main path. | 1440 and 390 screenshots of the voice note; `s1` "Live captions" toast. | run | Hide or disable the button with the engine missing and put the explanation in `data-help-for`, as the Writing room does with its model select. | S |
| Z15 | low | a11y | The welcome (onboarding) dialog: Tab from Next lands on Next again seven times, so Skip and Back are not reachable by keyboard while the dialog is open (`role=dialog`, `aria-modal=true`). | `s10.js` D1b: tab order from step 2 `["onboarding-next" x7]`. onboarding.js:437 (focus), no trap code. index.html:15490-15493. | run | Let the dialog's own three buttons take the Tab (the lock prompt recipe does); check the `inert` or `tabindex` that holds the others. Map owner: shell. | S |
| Z16 | low | copy | X19 still open, re-verified: the dashboard Digest quotes `"---"` twice for notes that start with frontmatter (the two meeting notes). | 390 screenshot of the space switcher step (Digest card: `"---"`, `"---"`). | run | Skip a leading frontmatter block when taking the quote. Map owner: shell (dash-day). | S |
| Z17 | low | complexity | settings-panes.js (a boot script) builds the palette rows "Count words" and "Translate this" around `paletteCaught`, a `const` that only exists once the lazy app-palette.js has loaded. Any caller of `paletteCommands()` other than the palette throws `ReferenceError: paletteCaught is not defined` (reproduced by running the row's `act` directly); today only the palette calls it, so nothing visible breaks, but Z3's fix (the features catalogue reading the palette rows) would. | `s1-1440.log` and `s1-390.log`: `THROW ... paletteCaught is not defined`. settings-panes.js:1387-1388, app-palette.js:89. | run | The rows read `window.paletteCaught` through a function (`paletteCaughtText()`) that returns the empty catch when the module is not in. | S |
| Z18 | low | perf | Background art, when on, costs 0.203 s of script per 5 s (about 4 percent of one core) at 20 fps on this 4-core box, all the time the tab is visible, on every tab. It is off by default here and pauses when hidden, so this is a note, not a fault. | `s6.js` §1: CDP `Performance.getMetrics` ScriptDuration 0.000 s off, 0.203 s on. bg-art.js:2300-2310. | run | Already bounded; consider 12 fps when no pointer has moved for 30 s. | S |
| Z19 | low | ux | A card dragged out of the Notes list cannot be dropped on a category in the sidebar, a tag, a space or a reminder row: the carry targets are the chat box, a text field, the reminder box, a board and the tray (`OBJ_DESTS`). Dropping a note on "Cooking" to file it is the first thing a person tries (Apple Notes, Obsidian, Notion all take it). | obj-ref.js:95-101 (`OBJ_DESTS`), obj-carry.js `objCarryTarget`. Mouse drag over the category list showed no `.obj-target`. | run + code | Add `category` and `space` destinations (`#category-list li`, `#space-menu` rows) whose render is the existing move call, with the same outline and the same Undo. | M |

## Re-verified (the 1030 extras ids)

Fixed on this head, with the check: Y1 (the chunk queue, retry and "Not saving" line are in meetings.js:617-724), Y2 (one calm "Search by meaning needs a one-time download..." question toast, no red chip, no error row), Y3 (axe clean on Settings Packages at 390), Y4 (space rows named: "Delete Work", "Rename Personal"), Y6 (read: end computed from the clock), Y8 ("all" and "All spaces" refused with a sentence, 400), Y9 (not re-driven), Y10 (Statistics reads "up from 0 last week" and the unused list is gone on day one), Y11 (client strings; two server strings left: Z9), Y12 (`clip-page` with no text: 422 "This page sent no text to clip"), Y13 (not re-driven), Y14 (not re-driven), Y15 (not re-driven), Y16 (not re-measured), Y17 (`untilNoDialogOpen` read), Y18 (Writing room says "No model connected" once, the select reads "Default (off)").
Still open: Y5 (Z11), Y7 (Z4 for the bell rows). X12 fixed (Escape returns undefined, poll bounded to 10 misses, copy "Tessellate"). X19 still open (Z16).

## Method notes (what was measured)

- Palette walk (`s1.js`): 30 palette rows run through `catalogueRun` at 1440 light (theme toggled to dark half way, so Settings, About, Health, shortcuts and the manual were measured dark) and at 390 touch, each with the open state, focus, toasts, long tasks and axe; 0 serious or critical axe violations, 0 page errors, 0 horizontal scroll.
- Throttled pass (`s5.js`): 16 surfaces at 4x CPU with a PerformanceObserver; a 40-move drag reorder at 4x produced no long task (940 ms wall, under 16 ms a move on 207 rows); 5 s idle on the Notes tab: 0 rAF calls, 3 timeouts.
- HTTP (`p1.py`, `p2.py`): 95 requests across the 78 routes with bad ids, blank and oversize bodies, reserved names, traversal forms, missing tokens: every answer was the expected 4xx with a sentence; no 500. Caps hold (questions limit 200, statistics question 300, usage 200 features, lag 20 events, recording title 200, space name 60).
- The one-pixel PNG upload and the OCR workspace on it; `Read page` without an engine says what to install.

## What is already good

- Custom order: Alt+Up/Down on a focused row moves it, announces "Moved X to place 2 of 207. Ctrl+Z undoes it", the hint line appears, the pref is written, Ctrl+Z restores the sort; a mouse drag shows a ghost and a gap, drops with "Moved" and Undo, and keeps focus on the row.
- Ctrl+C on a focused card copies `[[Title]]` with a toast; Ctrl+V in the chat box stages the note as an attachment.
- Space create, rename and delete: Enter submits, duplicate and reserved names get a sentence, delete preselects the safe move and has Undo, focus returns to the switcher.
- The recovery key flow: password prompt, a 39-character key with Copy and Download, axe clean; the lock card names a malformed key and a wrong key differently and keeps focus.
- Every route probed with a wrong body answered a 4xx sentence; no path, title or note text in `/diagnostics`.
- The tour: no card off screen or over its spotlight in 16 steps across both widths; the welcome replays from Get started.
- The timer survives a reload and shows a 44 px chip on a phone.

## What could not be verified

Touch drag of a card: in Chromium's touch emulation a `click` fires 550 ms into a still hold (no app source for it: only whiteboard.js synthesises a click, and not here), and `objDragNow` is cleared before the 350 ms cue, so hold-to-drag never went live; on a real phone this is unknown. Real transcription, captions, translate, OCR engines and the margin reader (no engine or model); LAN with a second device; an update download; the desktop companion window and the pywebview shell; the share-sheet intake and the bookmarklet page end to end; screen readers; tab throttling in a hidden tab.

## Top five

1. Z1 the tray and Undo do not survive a space switch (a reload), so "carry it somewhere else" stops at the space line.
2. Z11 (Y5 still open) opening the Writing room costs 1.3 s of long tasks at 4x, Settings Packages 1.8 s in one task on a phone.
3. Z3 Tools and features omits about 60 palette rows, so "where is Count words" has no answer there.
4. Z19 a dragged note cannot be dropped on a category or a space.
5. Z2 and Z6: a stray click ends a timer with no Undo; Drop on a question has no feedback or Undo.

## Counts

Findings: 19 new (high 0, med 2, low 17). Kinds: ux 8, a11y 2, copy 3, perf 2, complexity 2, bug 1, ai 1. Re-verified: 17 of the 18 Y rows fixed or read as fixed; Y5 and half of Y7 open; X19 open.
