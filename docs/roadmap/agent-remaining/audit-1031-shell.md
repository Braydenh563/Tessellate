# Deep audit 2026-10-31: shell (lock, tabs, dashboard, notes list, library, timeline, reminders, settings, search, palette, notifications, import, export, backup, tour, phone shell)

Fable suite, surface 3 of 12. Server on 8852, 206 notes, fake Ollama.
Drives hs1 to hs3 (Playwright, 1440 and 390, dark; fresh contexts for the
lock screen), an API probe (counts, search operators, reminders, imports,
exports, backups, unlock throttle). Observed unless marked code.

## Rows

| Row | Sev | Kind | Finding | Evidence | Where | Verified | Fix | Size |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SH1 | high | perf | **The command palette blocks on open and on every letter.** Opening with Ctrl+K and typing "activ" logged 29 long tasks: 281, 199, 185, 354, 428, 175, 153, 153, 163, 142, 194 ms and more; 116 rows ("112 results") are built on open before a letter is typed. | hs3 palette `lt` | `palette.js`, `app-palette.js` | run | Build rows for the visible 20 and the rest on scroll; filter on `input` with a 50 ms debounce and reuse row nodes. | M |
| SH2 | med | a11y | **The Notifications dialog never takes focus.** `#notif-panel` (role dialog, "Notifications") opens with focus on BODY; two Tabs stay on BODY, outside the panel; no `aria-modal`. Its twelve rows' "Mark as unread" and "Remove" buttons are unreachable by keyboard; Escape closes it. | hs3 notifications `focus: BODY`, `tabbed.inside: false` | `notifications.js:94` | run | Focus the first row (or Close) on open, trap Tab, restore focus to `#notif-btn` on close. | S |
| SH3 | med | ux | **Notifications are every AI request.** Twelve items: "Chat followups, answered in 9 ms", "Model bench", "Create entry"; the bell counts them ("Notifications: 3 unread"). Same class as HR4 (the Tasks history). | hs3 notifications `first`, `badge` | notifications feed, `jobs.py` labels | run | Notify on things a person acts on (a reminder, a finished import, a failed job); keep request logs in Activity. | S |
| SH4 | med | a11y | **Library card titles are clickable `strong` elements whose name hides the visible text.** `.library-card-title.card-open` reads "which tags do I use most" but is named "Chat: which tags do I use most. 1 turn."; axe label-content-name-mismatch (serious) on 2 cards at 1440 and 1 at 390; 14 such titles are 22 px tall. | hs1 tab-library axe; hs2 library-mismatch, library-ctl | `library.js:1471` | run | Make the title a button whose accessible name starts with the visible text ("which tags do I use most, chat, 1 turn"); 24 px minimum height. | S |
| SH5 | med | a11y | **Closing a dialog drops focus on BODY.** Settings (opened by `#settings-btn` or by API, closed with Escape), the command palette (after Enter and after Escape), Notifications and the tour all leave `document.activeElement` on BODY. 1028 S58 still open. | hs1 settings-escape-focus; hs3 palette `focusAfterEsc`, notifications `focus`, tour `after` | `settings.js:646` `closeSettingsModal`, palette close, `notifications.js`, `tour.js` | run | One `openerFor(dialog)` record on open and `focus()` on close, in the modal kit. | S |
| SH6 | med | bug | **The lock screen hides the throttle.** The second wrong password earns 429 "Too many wrong passwords. Try again in 2 seconds." from `/auth/unlock`, but `#lock-error` keeps "That password is wrong."; the right password inside the window is refused with the same line, so a person who just typed it correctly is told it is wrong. | hs2 lock2 `limited.err`; curl: attempt 2 to 10 and the right one all 429 | `settings-wiring.js:248` `lockFail` | run | Show the server's message with its countdown and disable Unlock until it passes. | S |
| SH7 | med | perf | **Notes on a phone render every note.** Page size defaults to "All notes": 206 rows, 2,711 nodes; switching to Notes blocks 239 and 387 ms at 390 and 211 ms at 1440. | hs2 phone-notes `lt`; hs1 notes-list `size: "all"`, tab-notes | `notes-list.js` page size default | run | Default 40 per page under 600 px (keep "All" as a choice); render below the fold on idle. | S |
| SH8 | med | bug | **Four counts of the notebook.** `/entries/count` 206, `/entries` 207, search `counts.note` 207, `/export/json` and CSV 210. The three export-only entries (76 "Harbor launch board", 77 "Portugal trip", 209 "summarise my baking notes", Uncategorised) are board and map companion entries the list hides; an export carries them as plain notes. | API probe, ids diffed | `routes_settings.py:2721` `export_json`, `:3414` `export_csv`; count route in `routes_entries.py` | run | One `visible_entries()` query shared by count, list, search and export; export companions under their board, or mark them. | S |
| SH9 | low | copy | Dashboard sub-line "So far today: 206 notes." gives the total, not today's; the greeting heading is the model's text as is ("Ok." from a model that answered "ok"). | hs1 dashboard | `dashboard.js` greeting, `routes_insights.py` greeting | run | "206 notes, 3 today"; reject a greeting under 3 words. | S |
| SH10 | low | ux | "?" opens nothing; Shift+/ fires the "/" shortcut and lands in the Library search box. 1028 S24 open. | hs1 question-mark `focus: INPUT#note-search` | `settings-wiring.js:729` | run | A "?" sheet listing the bound shortcuts; ignore "/" when Shift is held. | S |
| SH11 | low | a11y | Small targets: rail link actions 21 x 21 (7), to-do checkboxes 15 x 15 at 1440 and 18 x 18 at 390, Privacy "See the full list" 86 x 17, About `a#about-github` 199 x 16, Preferences "Animation, the corner…" 499 x 20, Reminders list and calendar view buttons 28 x 24. | hs1 notes-list, settings-*; hs2 phone-notes | note-cards, `index.html` privacy and about | run | 24 px minimum via padding; checkboxes 20 px with a 24 px label hit area. | S |
| SH12 | low | perf | Settings panes block on open: Shortcuts 234 ms (275 nodes, 42 controls), Appearance 150, Templates 141, Data 135; one General open logged 873 ms (not reproduced: 98 to 158 on retry). | hs1 settings-*; hs3 settings-open-general-fresh | `settings-panes.js`, `settings-controls.js` | run | Build each pane on first show; the Shortcuts table from a template. | S |
| SH13 | low | ux | A reminder due in the past is sent to the server first: a 422 in the console, then the inline error "That reminder's due time is in the past." | hs3 reminders-add `pastErr`, CONSOLE-ERR 422 | `shell-reminders.js` add | run | Check the time before the request. | S |
| SH14 | low | ux | `#status-tray` ("Tray, empty") is a button that opens nothing when empty. | hs2 tray-and-notifications `menu: none` | `status.js` tray | run | Hide the zone when empty, or open a line saying what the tray holds. | S |
| SH15 | low | copy | Timeline header "230 items · 7 weeks" for 206 notes: the count includes reminders, boards and documents without saying so. | hs1 timeline; hs3 timeline-plural | `timeline.js:453` | run | "230 items (206 notes, 15 reminders, …)" or a kinds line. | S |
| SH16 | low | ux | `#backup-status` is empty although the daily backup exists (15:24, 696 KB, listed). 1028 S35 remainder. | hs1 exports `backup.status: ""`; API `/backups` | `settings-data.js` | run | "Last backup today at 15:24 (automatic)". | S |
| SH17 | low | ux | The tour card carries eight buttons for a four-step tour: Move the app aside, Put back, Minimise panel, Close, Skip, Back, Next, Move or resize. | hs3 tour `btns` | `tour.js` | run | Drop the panel chrome from the tour card. | S |
| SH18 | low | perf | The finder opened with a query logs a 412 ms long task (22 suggestions); the Library tab at 1440 opens with 5,713 nodes and tasks of 164, 121 and 151 ms. | hs1 finder `lt`, tab-library | `search.js:652`, `library.js` | run | Suggest after idle; paginate Library cards (60 on open). | S |
| SH19 | low | ux | An unnamed visible button reaches 84 px past the viewport on Notes and inside Settings at 390 (`button r=474`); not identified. | hs2 phone-notes, phone-settings-nav `o.out` | unknown | run (partly) | Find it (`[...document.querySelectorAll('button')].find(b => b.getBoundingClientRect().right > 400)`) and clip or name it. | S |

## 1028 shell rows re-verified

| Row | Now | Evidence |
| --- | --- | --- |
| S1 jump beyond the rendered rows | fixed | `flashEntry(29)`: toast "Showing note: …", focus on the row |
| S4 lock focus and dialog | fixed | focus `#lock-password` on load, `role=dialog aria-modal=true`, labelled "Unlock Tessellate" |
| S5 palette combobox | fixed | `#palette-input` combobox, `aria-controls=palette-list`, listbox, `aria-activedescendant` moves, live "5 results" |
| S16 notes list grows forever | fixed | paged ("Page 1 of 1", size select) |
| S19 toasts ignore hover | fixed | held 7 s under the pointer, gone 6 s after leaving; close button |
| S21 Select folded away | resolved | "Select" is the first item of the Notes More menu |
| S24 "?" sheet | open, SH10 | |
| S25 lock feedback | partly, SH6 | inline error, `aria-invalid`, focus kept; throttle hidden |
| S35 backup status | partly, SH16 | schedule and list exist; status line empty |
| S41 small targets | partly, SH11 | |
| S50 search operators | fixed | `tag:recipes` hits; finder suggests "tag:recipes things tagged recipes" |
| S56 toasts over the phone nav | fixed | toast 658 to 723, bar 787 to 844 |
| S57 New note button over the composer | not re-run | the textarea focus step failed |
| S58 return focus | open, SH5 | |
| S59 skip link | fixed | first Tab lands on `#skip-link`; the tab bar is 4th |
| S2, S3, S6 to S15 | fixed per HISTORY | not re-run |
| S17, S18, S20, S22, S23, S26 to S34, S36 to S40, S42 to S49, S51, S52, S54, S55, S60 to S80 | code rows, not re-run | mostly feature wishes; see the ranked file |

## Coverage

| Area | Driven | Notes |
| --- | --- | --- |
| Lock screen (desktop, phone), wrong password, throttle, unlock | run | unlock 3.5 s to the dashboard; phone input 16 px, 45 px tall, no overflow |
| Tabs: dashboard, notes, library, timeline, reminders, graph, chat at 1440 and 390 | run | `role=tab`, `aria-selected`, `tabpanel`; axe clean except SH4 |
| Dashboard widgets, customise, quick access | run | 11 widgets; "Activity heatmap" 390 nodes |
| Notes list: paging, jump, select mode, More menu, rail | run | 194 controls on the tab |
| Library: tabs, cards, search | run | 9 tabs, 60 cards on open |
| Timeline: controls, days, month | run | |
| Reminders: add blank, past, HTML text, magic sentence | run | HTML renders as text; magic "call the dentist next tuesday at 3pm" showed no status |
| Finder, palette, settings search | run | settings search "activity": "6 settings in 4 sections", no combobox semantics |
| Notifications, tray, tour | run | |
| Settings panes: general, appearance, privacy, shortcuts, templates, data, searchindex, about, preferences, account, extras | run | axe clean; no title-case copy beyond theme names |
| Theme and page background | run | `page-bg-dark` survives light and dark switches (S10 fixed) |
| Export JSON, CSV, Markdown zip; backup now; import of a bad file | run | 104 KB in 44 ms, 32 KB in 241 ms, 62 KB in 47 ms; backup 239 ms; "No Tessellate notes in what you chose. See the report" |
| Unlock throttle, search operators, reminder validation, export contents | run (API) | reminder text cap 500; `in:` and `before:` return no hits (not checked whether they are operators) |
| Service worker, onboarding first run, phone settings nav structure, New note button over the composer | not driven | |

## Already good

- Lock screen semantics, focus and copy; unlock in 3.5 s; a 16 px input on the phone.
- Skip link first in the tab order; tab bar fourth; every tab has tab and tabpanel roles.
- Palette: combobox, listbox, live count, an empty state that offers "Search everything for …".
- Toasts hold under the pointer and carry a close button; phone toasts clear the nav bar.
- Reminder form: inline error, `aria-invalid`, focus kept, HTML rendered as text, 500-character cap.
- Exports are fast and complete; a bad import names the report.
- Jump to a note beyond the first page lands on the row with a toast.

## Not verified

- Service worker caching, first-run onboarding, the New note button over a focused composer at 390, the phone Settings nav structure, the dashboard quick-access strip's horizontal scroll affordance at 390.
- Whether `in:` and `before:` are search operators (both returned no hits).
