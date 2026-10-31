# Audit 1028: shell, notes, library, dashboard, graph, timeline, settings, import/export, backup, search

Clean-eye audit, read-only. "verified" is run (driven in Playwright on a scratch data dir, measured) or code (read, not driven). Line numbers are from the head audited; rows without a line cite the file and area only.

| id | sev | kind | finding | evidence | verified | fix | effort |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | high | bug | Jump-to-note (palette, graph, links) silently does nothing when the target card is not yet in the DOM (beyond the first 60 rendered rows); flashEntry returns without scrolling or loading | frontend/js/capture-ask.js:889-932; notes-list.js:1890-1960 | run | Resolve the page first (resolveNotePage), render through the target, then flash; toast if not found | M |
| S2 | high | perf | Graph layout blocks the main thread at about 2000 notes (long tasks during open) | frontend/js/graph.js, graph-canvas.js | run | Move layout to a worker or chunk per frame with a time budget, cap iterations by node count | L |
| S3 | high | perf | Boot ships a very large index.html (1.1MB) with big comment blocks and mascot/avatar/atlas code in the boot path | frontend/index.html (15427 avatars.js, 15430 atlas.js) | run | Strip comments at serve time, lazy-load avatars and atlas via LAZY_MODULES | M Fixed 1031 (second half, lazy `characters` bundle): boot bytes 574,619 to 441,991 (0.77), lock FCP 454 to 324 ms (0.71), unlock to notes list 1461 to 1215 ms (0.83), long tasks before unlock 4 to 1; serve-time comment stripping not done. |
| S4 | high | a11y | Lock screen: focus is not reliably placed on the password field after show, and the overlay lacks dialog semantics | frontend/index.html:322; app.js:806-840 | run | role=dialog, aria-modal, aria-labelledby, focus #lock-password on show, restore on unlock | S |
| S5 | high | a11y | Command palette dialog is not a proper combobox: no aria-activedescendant, results not announced | frontend/index.html:14787-14792; app-palette.js paletteKeydown | code | role=combobox plus listbox, aria-activedescendant, live count | M |
| S6 | high | bug | Ask button clipped off-screen at 390px width (right edge 428 > viewport 390) | frontend/index.html:2200 (#ask-btn); measured rect [369,330,59,44] | run | Let the Ask row wrap or shrink the model select at narrow widths | S |
| S7 | high | bug | Timeline header count and "days" plural are wrong for 1 and for paged data | frontend/js/timeline.js:787-789, :504 | code | Count from total not loaded page; pluralise via one helper | S |
| S8 | high | bug | Dashboard insight counts capped by a fixed limit, so totals under-report on large notebooks | src/tessellate/api/routes_insights.py:430 (.limit(120)) | code | Count in SQL, limit only the sample rows | S |
| S9 | high | bug | Import success toast reports the raw server count with no skipped or duplicate breakdown and no link to the result | frontend/js/app-import.js:~48 | code | Show imported, skipped, failed; open the Notes list filtered to the import | S |
| S10 | high | bug | Theme change wipes the page background choice (applyThemeChoice resets page-bg) | frontend/js/settings.js:2440-2460 | code | Keep page-bg per theme or only reset when the preset demands it | S |
| S11 | med | bug | Server greeting lines can contradict state (composer line selection) | src/tessellate/ai/composer_lines.py:256, :262 | code | Gate lines on the same facts the dashboard shows; add a test | S |
| S12 | med | ux | Duplicate lives under "Add" in the entry overflow menu | frontend/js/menus.js:1786 | code | Move Duplicate next to Edit/Copy in the primary group | S |
| S13 | med | a11y | Placeholder-only inputs with no label | frontend/index.html:1312, :10901, :15046 | code | Add visible or aria-label text | S |
| S14 | med | a11y | tab-documents aria-labelledby points at the wrong or missing element | frontend/index.html:4687 | code | Point it at the tab button id | S |
| S15 | med | a11y | Only one forced-colors rule exists in the whole CSS | frontend/css/sketch-pad.css:229 | run | Add forced-colors rules for buttons, focus ring, selected tab, chips | M |
| S16 | med | perf | Notes list never recycles rows: 60 then chunks of 40 appended forever, DOM grows without bound | frontend/js/notes-list.js:1890-1960 | code | Window the list (virtualise) or cap rendered rows with placeholders | L |
| S17 | med | arch | Four copies of the relative-time helper | dashboard.js:4506, sheets-selects.js:1716, shell-reminders.js:1251, note-cards.js:1187 | code | One shared helper in an early script | S |
| S18 | med | ux | Support email constant hard-coded in toast code | frontend/js/status.js:927 | code | Read from config or settings | S |
| S19 | med | a11y | Toast timers dismiss on a fixed delay with no pause on hover or focus (WCAG 2.2.1) | frontend/js/status.js:1128 | code | Pause on hover/focus, keep errors until dismissed | S |
| S20 | med | arch | Cache prefix still carries the old product name | frontend/sw.js:36 | code | Rename with a migration that deletes old caches | S |
| S21 | med | ux | Select button is folded away at narrow widths with no alternative path | frontend/index.html:2468 | run | Expose selection via long-press or the overflow menu | M |
| S22 | med | ux | Filter menu, sort select and view toggle are three separate control styles in one bar | frontend/index.html:2435-2466 | code | Unify under the toolbar recipe (kebabMenu plus segmented control) | M |
| S23 | med | nav | Palette has about 103 commands but no recent-first ordering or per-command shortcut hints | settings-panes.js:1275; app-palette.js | code | Show bound shortcut, sort recent first | S |
| S24 | med | nav | Shortcut set is fixed defaults plus rebinding; no in-app cheat sheet reachable by "?" | settings-wiring.js:956-1060 | code | Add a "?" overlay generated from DEFAULT_SHORTCUTS | S |
| S25 | med | bug | Lock form submit path: wrong password handling gives little feedback and no throttle hint | frontend/js/settings-wiring.js:246-256 | code | Inline error, aria-live, retry delay message | S |
| S26 | med | ux | Fresh-install Ask tab shows a model error banner plus a semantic-search toast stacked over the content at phone width | ask390.png (390x844) | run | Collapse into one status line; stop toast covering the composer | S |
| S27 | med | missing | No true backlinks panel in the note editor (links exist in graph only) | notes editor, graph.js | code | Add a "Linked from" section | M |
| S28 | med | missing | No wiki-style [[ ]] autocomplete while typing in notes | editor | code | Trigger a note picker on [[ | M |
| S29 | med | missing | No note templates | notes, capture.js | code | Template picker on New note | M |
| S30 | med | missing | No pin-to-top for notes in the list | notes-list.js | code | Pin flag plus sort rule | M |
| S31 | med | missing | No bulk move to category or bulk tag from the selection bar | notes-list.js selection | code | Add to selection dock | M |
| S32 | med | missing | No undo for delete beyond the toast timer window on slow reads | status.js toasts | code | Keep Trash view with restore (verify existing) | M |
| S33 | med | missing | No saved searches or smart folders | search UI | code | Save filter combos as named views | M |
| S34 | med | missing | No export of a single note to Markdown or PDF from the overflow menu | menus.js:1532 | code | Add Export entries | M |
| S35 | med | missing | No scheduled automatic backup with visible last-backup status | backup UI, settings.js | code | Schedule plus status line | M |
| S36 | med | missing | Import does not preview what will be created before committing | app-import.js, index.html:13053-13317 | code | Dry-run preview step | M |
| S37 | med | perf | Re-render of list sections on each filter keystroke without debounce in places | notes-list.js | code | Debounce and diff render | S |
| S38 | med | perf | Many timers (toasts, reminders, relative-time refresh) run independent intervals | status.js:1128; shell-reminders.js | code | One shared tick | S |
| S39 | med | a11y | Focus ring contrast and visibility inconsistent across custom controls | css (focus rules) | code | One :focus-visible token | S |
| S40 | med | a11y | Icon-only buttons rely on title only for names in several toolbars | index.html toolbars | code | aria-label on each | S |
| S41 | med | a11y | Touch targets under 24px in dense rows (WCAG 2.2 target size) | notes rows, chips | code | min 24px hit area | S |
| S42 | med | ux | First-run has no guided sample content, so lists and graph look empty | onboarding | run | Offer sample notes or import | M |
| S43 | med | ux | Help is split between data-help-for popovers, Guide topics and Settings with no single search | ai/help_chat.py | code | Palette entry "Help: search topics" | S |
| S44 | med | design | Mixed button heights and radii between toolbars (not all on tokens) | css | code | Lint for token use on toolbar buttons | M |
| S45 | med | nav | Reaching Settings sections takes three clicks; palette lacks deep links to each pane | settings.js | code | One palette command per pane | S |
| S46 | med | nav | No "go back" for jump-to-note after following a link | notes-list.js focusNoteRow :62 | code | Back stack for note navigation | M |
| S47 | med | missing | No keyboard way to reorder or move between notes with j/k in the list | notes-list.js | code | j/k plus Enter bindings | S |
| S48 | med | missing | No tag rename or merge in the tags UI | tags UI | code | Rename and merge actions | M |
| S49 | med | missing | No note version history view | editor | code | History drawer over stored revisions | L |
| S50 | med | missing | No full-text search operators (tag:, in:, before:) surfaced | search | code | Parse and document operators | M |
| S51 | med | utility | Dashboard shows greeting and counts but no actionable "resume where you left off" | dashboard.js | code | Recent notes strip plus last-open note | S |
| S52 | med | ux | Graph has no search-to-focus node field on the main bar | graph.js | code | Add a find box | S |
| S53 | med | ux | Timeline paging is a separate mechanism from the Notes list paging | timeline.js:504 vs notes-list.js | code | Share one incremental renderer | M |
| S54 | low | bug | Duplicate-looking id was flagged but exists only in an HTML comment | index.html | code | None (false positive, dropped from fixes) | S |
| S55 | low | ux | Settings labels use mixed case in places against sentence-case rule | settings panes | code | Sweep strings | S |
| S56 | low | ux | Toast stack can cover the bottom nav at phone width | ask390.png | run | Offset above nav safe area | S |
| S57 | low | design | Floating "New note" button overlaps content at 390px | ask390.png | run | Hide while a composer is focused | S |
| S58 | low | a11y | Modal focus trap works for the main dialog but return-focus target is not consistent | modal.js run | run | Restore to the opener everywhere | S |
| S59 | low | a11y | Skip link to main content absent | index.html | code | Add skip link | S |
| S60 | low | a11y | Reduced-motion handling not applied to every animation | css | code | Global prefers-reduced-motion block | S |
| S61 | low | a11y | Colour contrast of muted text in dark theme near threshold on chips | contrast.js run | run | Raise muted token | S |
| S62 | low | ux | Palette empty state offers no suggestion | app-palette.js | code | Show "Search notes for ..." fallback | S |
| S63 | low | nav | Palette lacks "go to note by title" with live preview | app-palette.js | code | Add note results with snippet | M |
| S64 | low | perf | Mascot and avatar assets load even when disabled | index.html:15427 | code | Gate on setting | S |
| S65 | low | perf | Service worker precache list not trimmed to boot-critical assets | sw.js | code | Split critical vs lazy | M |
| S66 | low | arch | 27 global-scope scripts raise collision risk; no lint for duplicate top-level names across lazy modules | index.html script order | code | Add duplicate-global lint covering LAZY_MODULES | M |
| S67 | low | arch | Duplicate plural and count helpers across timeline, dashboard, notes | timeline.js:787 | code | Shared pluralise | S |
| S68 | low | ux | Import UI is long and dense on one panel | index.html:13053-13317 | code | Stepper | M |
| S69 | low | ux | Backup restore flow lacks a verify-before-restore summary | backup UI | code | Show counts and date first | M |
| S70 | low | missing | No note count per tag in tag chips | tags UI | code | Show counts | S |
| S71 | low | missing | No drag and drop of files into the list to import | notes list | code | Drop target | M |
| S72 | low | missing | No quick-capture global shortcut hint on first run | capture.js | code | Hint in onboarding | S |
| S73 | low | missing | No word count or reading time in the editor footer | editor | code | Footer stats | S |
| S74 | low | missing | No outline or table of contents for long notes | editor | code | Heading outline | M |
| S75 | low | missing | No daily note shortcut | capture.js | code | Command "Open today's note" | S |
| S76 | low | missing | No note linking preview on hover | note-cards.js | code | Hover card | M |
| S77 | low | missing | No sort by manual order | notes-list.js | code | Drag reorder in a category | L |
| S78 | low | design | Empty states differ in tone and illustration across views | views | run | One empty-state recipe | M |
| S79 | low | design | Icon set mixes stroke weights between nav and toolbars | index.html | code | Normalise icon weight | S |
| S80 | low | design | Card shadows and borders vary between Library and Notes | library.js, note-cards.js | code | Use card token | S |
| S81 | low | design | Settings has dense long panes with no sticky section index | settings.js | code | Sticky in-pane nav | M |
| S82 | low | ux | Segmented view toggle lacks labels for first-time users | index.html:2452-2466 | code | Tooltip plus aria-label | S |
| S83 | low | ux | Filter menu state not summarised once closed | index.html:2435-2446 | code | Show active filter chips | S |
| S84 | low | ux | Onboarding cannot be re-opened from Help | onboarding | code | Help entry "Replay tour" | S |
| S85 | low | ux | Error toasts say what failed but not what to do | status.js | code | Add action buttons | M |
| S86 | low | nav | Library to notes round trip needs 3 clicks | library.js | code | Direct "open note" on cards | S |
| S87 | low | nav | Dashboard cards do not all deep link to the filtered Notes view | dashboard.js | code | Link counts to filters | S |
| S88 | low | utility | Search results lack match highlighting in snippets | search | code | Highlight terms | S |
| S89 | low | utility | Export lacks a format choice summary (JSON, Markdown, zip) | app-import.js | code | Format picker | S |
| S90 | low | perf | Palette builds all 103 commands on each open | settings-panes.js:1275 | run | Cache (measured 4ms, so low value) | S |
| S91 | low | a11y | Page language and title do not update on view change | index.html | code | Update document.title per view | S |
| S92 | low | a11y | Live region for list loading and counts missing | notes-list.js | code | aria-live status | S |
| S93 | low | arch | Test coverage for the flashEntry not-in-DOM path absent | capture-ask.js:889-932 | code | Add a test with a 100-note fixture | S |
| S94 | low | ux | Offline indicator exists (verified), but no explanation of what still works | status.js | run | Link to help text | S |

## Dropped as false positives (not rows)

- Duplicate id: only inside an HTML comment.
- Inline #tags not recognised: the API flag is opt-in.
- No offline indicator: it exists.
- Palette performance: measured 4 ms.

## Caveats

- Rows marked code were read, not driven. Missing-feature rows were judged against Notion, Obsidian, Apple Notes and Bear by feature, and I did not re-grep every one for an existing implementation; grep before building (CLAUDE.md section 1). S32, S27 and S75 especially may exist in part.
- Real inference was not exercised (standing caveat). Only the fake-transport state was visible on the Ask tab.
- Whiteboard, documents and chat/agent surfaces were skipped as instructed.
