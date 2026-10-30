# Audit 1028 ranked open rows

Open audit-1028 rows (38 fixed rows left out, 12 in progress marked), ranked by severity, then security and data loss, broken features, UX and accessibility, performance and polish. A row is planned when a plan, BACKLOG or INBOX line matches its keywords and a hand check agrees; the rest are new.

| rank | id | severity | summary | planned at | size |
|---|---|---|---|---|---|
| 1 | D4 | high | unsaved draft with full text in localStorage, never expires | fixed (23fcf45, reconciled 2026-10-30) | S |
| 2 | D5 | high | single draft slot overwrites a failed save of another document | fixed (23fcf45, reconciled 2026-10-30) | M |
| 3 | E6 | high | what-is-on-date questions use creation day, not mentioned date | fixed (490e3c3, reconciled 2026-10-30) | M |
| 4 | E7 | high | act grammar needs the literal word note | fixed (490e3c3, reconciled 2026-10-30) | M |
| 5 | E10 | high | no task intents: add to checklist, tick item, complete reminder | built (add, complete, cancel, snooze, Undo, Guide topic) | M |
| 6 | E11 | high | wrong or partial answers on due and reading asks | fixed (490e3c3, reconciled 2026-10-30) | M |
| 7 | E12 | high | no-match fallback quotes newest notes as relevant | fixed (490e3c3, reconciled 2026-10-30) | M |
| 8 | E30 | high | search-by-meaning loading message shown indefinitely | fixed (490e3c3, reconciled 2026-10-30) | S |
| 9 | U4 | high | no discovered non-drag reparent path for mind map topics | fixed (c288482, reconciled 2026-10-30) | M |
| 10 | U6 | high | code editor undiscoverable, not under the New menu | fixed (c288482, reconciled 2026-10-30) | S |
| 11 | U8 | high | new document opens in Read mode on phone | fixed (673039d, reconciled 2026-10-30) | S |
| 12 | U9 | high | find and replace panel is unstyled CodeMirror default | fixed (styling 673039d; match count this batch) | M |
| 13 | U10 | high | image menu inserts bare stub with no picker | fixed (673039d, reconciled 2026-10-30) | M |
| 14 | B3 | high | every render clears caches and rebuilds all map nodes | new | L |
| 15 | B4 | high | full board render per frame with no dirty set | new | L |
| 16 | D7 | high | prose spell pass walks whole document every pause | fixed (673039d, reconciled 2026-10-30) | M |
| 17 | S2 | high | graph layout blocks the main thread at about 2,000 notes | fixed 2026-10-30 (graph-1030: 25 to 9-10 s, long tasks 149 to 20) | L |
| 18 | S3 | high | 1.1 MB index.html with comments and mascot code in boot path | left (large, shell-1031.md) | M |
| 19 | B1 | high | whiteboard.js is 25k lines; initWhiteboard is one 4,064-line closure | docs/roadmap/WORLD_CLASS_PLAN.md:3755 | L |
| 20 | B2 | high | whiteboard-map.js is 10,810 lines and 350 functions | docs/roadmap/WORLD_CLASS_PLAN.md:3255 | L |
| 21 | U7 | high | code text is proportional, not monospace | fixed (673039d, reconciled 2026-10-30) | S |
| 22 | B9 | med | undo during an in-flight delete can restore a deleted object | fixed (c288482, reconciled 2026-10-30) | M |
| 23 | D11 | med | replace-in-all undo writes old text with no hash check | fixed 2026-10-30: per-item base_hash, a stale item refuses the batch | M |
| 24 | K1 | med | POST /auth/reset needs no credential and seals private notes | fixed (31f2a83, reconciled 2026-10-30) | S |
| 25 | K4 | med | body cap is 320 MB on every route, JSON included | fixed 2026-10-30: JSON and untyped bodies capped at 16 MB, uploads and `/files/` keep 320 MB | M |
| 26 | K5 | med | installer run silently with no signature or pinned hash | docs/roadmap/BACKLOG.md:398 | M |
| 27 | K6 | med | SearXNG installed from unpinned master tarball | fixed in part (commit and tree digest pinned; requirements not hash-pinned) | M |
| 28 | K19 | med | restore disposes the engine with jobs in flight | fixed 2026-10-30: restores hold the job pool, 409 while a job still runs | M |
| 29 | E42 | med | pasted note text reaches write tools with no confirm | fixed (1029 H2: edit_note parks via CHANGE_TOOLS) | M |
| 30 | E66 | med | delete all notes silently reduces to one match | fixed | S |
| 31 | E70 | med | regenerate and resend repeat web search and write tools | fixed (E2: Run again confirm on a writing answer) | M |
| 32 | B7 | med | delete handlers recreated each render and stashed in module refs | fixed | M |
| 33 | B10 | med | no native PDF export, relies on browser print | new | M |
| 34 | B11 | med | no focus mode for mind map branches | docs/roadmap/MINDMAP_PLAN.md:229 | M |
| 35 | B14 | med | map branch export and board export use two dialogs | fixed | M |
| 36 | B19 | med | arrows bind only at draw time, no reroute on shape change | fixed | L |
| 37 | D9 | med | edit-conflict modal steals focus during autosave | fixed (8e2bea8) | M |
| 38 | D10 | med | take-theirs leaves title box stale, next save resends old title | fixed 2026-10-30 | S |
| 39 | D13 | med | POST documents/contents skips media hook and payload cap | fixed 2026-10-30: media hook, archived refused, JSON cap 16 MB (K4) | S |
| 40 | D17 | med | blank title autosaved as Untitled document N | fixed (this batch) | S |
| 41 | D26 | med | comments have no author, time, replies or resolved view | new | L |
| 42 | D27 | med | no image resize handles or alt-text prompt on paste | fixed (61089b9) | M |
| 43 | D28 | med | no continuous zoom, text size in three steps | won't fix (browser zoom gives continuous zoom; three prose sizes kept, 2026-10-30) | S |
| 44 | D29 | med | replace dialog lacks whole-word and match preview | fixed (this batch) | M |
| 45 | D30 | med | spellcheck is English only, no per-document language | new | L |
| 46 | E13 | med | bare undo after an answer gets help text, not undo | fixed 1030 | S |
| 47 | E14 | med | follow-ups like pin that note lose their referent | new | M |
| 48 | E15 | med | stats route steals questions that name a note subject | fixed 1030 | S |
| 49 | E16 | med | compare gives identical lists for both sides | new | M |
| 50 | E17 | med | digest says newest a day ago when written today | new | S |
| 51 | E18 | med | composer invents speech acts the notes do not contain | new | S |
| 52 | E19 | med | source lists mangled, author lowercased and split | new | S |
| 53 | E20 | med | weekday words in log notes treated as due dates | new | M |
| 54 | E21 | med | lowercase month in computed days-until answer | new | S |
| 55 | E22 | med | instruction words reported as missing evidence | new | S |
| 56 | E24 | med | generative requests answered with quotes, no needs-a-model reply | new | S |
| 57 | E25 | med | quoted note titles stored as body text | new | S |
| 58 | E26 | med | reminder with no subject; impossible dates accepted | fixed 1030 | S |
| 59 | E31 | med | guide answers the wrong topic for realistic questions | fixed (490e3c3, reconciled 2026-10-30) | M |
| 60 | E32 | med | ChatGPT question gets local model not running answer | fixed 1030 | S |
| 61 | E33 | med | guide answers are verbatim topic chunks, no lead path | new | M |
| 62 | E39 | med | model download has no timeout or disk check | new | S |
| 63 | E48 | med | edit and resend destroys later replies, no branches | new | L |
| 64 | E57 | med | context overflow drops early turns with no inline notice | new | M |
| 65 | S11 | med | server greeting lines can contradict dashboard state | fixed (b8cfb46) | S |
| 66 | S25 | med | lock form gives little error feedback, no throttle hint | fixed (already: inline error, role alert, 429 names the wait; reconciled 2026-10-30) | S |
| 67 | S27 | med | no backlinks panel in the note editor | fixed (already built; reconciled 2026-10-30) | M |
| 68 | S28 | med | no wiki-style [[ ]] autocomplete in notes | already built ([[ ]] autocomplete, measured) | M |
| 69 | S29 | med | no note templates | already built (Templates, measured) | M |
| 70 | S30 | med | no pin-to-top for notes in the list | fixed (already built; reconciled 2026-10-30) | M |
| 71 | S31 | med | no bulk move or bulk tag from the selection bar | already built (selection bar Move/Tag, measured) | M |
| 72 | S32 | med | no Trash view with restore, existing state unverified | already built (Trash view with restore, measured) | M |
| 73 | S33 | med | no saved searches or smart folders | already built (saved searches, measured) | M |
| 74 | S34 | med | no single-note export from the overflow menu | fixed (already built; reconciled 2026-10-30) | M |
| 75 | S35 | med | no scheduled automatic backup or last-backup status | fixed (already built; reconciled 2026-10-30) | M |
| 76 | S36 | med | import does not preview what it will create | won't fix (design: import is one step with Undo plus a report, DESIGN.md recipe) | M |
| 77 | S47 | med | no keyboard j/k movement in the notes list | fixed (already: arrow keys, Home, End and Enter walk the list; reconciled 2026-10-30) | S |
| 78 | S48 | med | no tag rename or merge in the tags UI | fixed (already built; reconciled 2026-10-30) | M |
| 79 | S49 | med | no note version history view | fixed (already built; reconciled 2026-10-30) | L |
| 80 | S50 | med | no search operators such as tag: and before: | already built (search operators, measured; negated -tag: not supported) | M |
| 81 | B12 | med | same keys mean different things by mode | new | M |
| 82 | B13 | med | shortcuts hidden in menu subtitles, no cheat sheet | fixed (already built; reconciled 2026-10-30) | S |
| 83 | B20 | med | lock state shown only on hover, no persistent badge | fixed | S |
| 84 | D31 | med | Mod-h unreachable on macOS, Ctrl+1-3 collide with browser | fixed in part (Mac Replace chord; Ctrl+1 to 3 headings kept, 2026-10-30) | S |
| 85 | D32 | med | Mod-g means go to line in code and find-next in prose | fixed | S |
| 86 | D33 | med | replace-in-all and find-in-all separate from CM find panel | new | M |
| 87 | D34 | med | autosave failure is tiny status text, no banner or retry | fixed (this batch) | S |
| 88 | E23 | med | quiz cloze questions cut the subject off | new | M |
| 89 | E27 | med | act summaries have lowercase verbs, ids and stale notice | new | S |
| 90 | E28 | med | show my reminders not handled in the chat path | fixed 1030 | S |
| 91 | E29 | med | identical reminders printed twice, no duplicate check | new | S |
| 92 | E35 | med | chat transcript is not a live region for screen readers | new | S |
| 93 | E36 | med | saved-chat rows are li with click and no keyboard path | new | S |
| 94 | E38 | med | no-model Models page hides suggested cards and pickers | new | M |
| 95 | E40 | med | two search-by-meaning toasts stack over Settings | new | S |
| 96 | E50 | med | phone no-model banner and source cards take too much room | new | M |
| 97 | S12 | med | Duplicate sits under Add in the entry overflow menu | fixed (this batch) | S |
| 98 | S13 | med | placeholder-only inputs have no visible or aria label | fixed | S |
| 99 | S14 | med | tab-documents aria-labelledby points at wrong element | fixed (this batch) | S |
| 100 | S15 | med | only one forced-colors rule in the whole CSS | fixed (b8cfb46) | M |
| 101 | S18 | med | support email hard-coded in toast code | fixed (one string, tests/test_support_email.py keeps it equal) | S |
| 102 | S19 | med | toasts dismiss on a fixed timer, no pause on hover | fixed (this batch) | S |
| 103 | S21 | med | select button folded away at narrow widths | fixed (b8cfb46) | M |
| 104 | S22 | med | filter, sort and view toggle use three control styles | fixed (b8cfb46, already one dock grammar; menu overflow fixed) | M |
| 105 | S23 | med | palette lacks recent-first order and shortcut hints | fixed (already: most used first at rest, learned order as you type, the key in the preview) | S |
| 106 | S24 | med | no in-app cheat sheet reached with the ? key | fixed (already built; reconciled 2026-10-30) | S |
| 107 | S26 | med | fresh-install Ask tab stacks banner and toast at phone width | fixed (aef5a83, S26: banner one in-flow line 111px, toast only when the question is owed; its phone size 178px to 152px, covering the Ask button 32px to 6px at 390x667; 360x640 still covers, see shellux-1030.md) | S |
| 108 | S39 | med | focus ring contrast inconsistent across custom controls | fixed (measured, already holds: contrastui.js, 40 surfaces, 1037 focused controls per theme, 0 under 3:1 in light and dark; 11 custom controls 5.47 to 5.9:1 light and 6.24 to 7.33:1 dark; 51 of 54 outline colours are `var(--accent)`, the rest tokens) | S |
| 109 | S40 | med | icon-only buttons rely on title for accessible names | fixed (b8cfb46, lint; all icon buttons already named) | S |
| 110 | S41 | med | touch targets under 24px in dense rows | fixed (measured, already holds: notes row chips min 24x24, row icon buttons 28x28 (44x32 touch), 9 surfaces at 1280 and 390: 0 failing WCAG 2.5.8 except one library title beside the status bar; the 14px suggested-tag take has a 44px band) | S |
| 111 | S42 | med | first run has no sample notes, lists look empty | left (large, shell-1031.md) | M |
| 112 | S43 | med | help split across popovers, Guide and Settings | fixed (b8cfb46) | S |
| 113 | S45 | med | no palette deep link to each Settings pane | fixed (already built; reconciled 2026-10-30) | S |
| 114 | S46 | med | no back stack after following a note link | fixed (already: back and forward in the status bar, nav-history.js; reconciled 2026-10-30) | M |
| 115 | S51 | med | dashboard has no resume where you left off | fixed (already built; reconciled 2026-10-30) | S |
| 116 | S52 | med | graph has no find box on the main bar | fixed (#graph-search on the graph bar, 1029 rank 39) | S |
| 117 | S53 | med | timeline and notes list page separately | left (shell-1031.md) | M |
| 118 | U11 | med | two menus both named Insert with different contents | fixed (673039d, reconciled 2026-10-30) | S |
| 119 | U12 | med | insert menu hides key hints for most tools | new | S |
| 120 | U13 | med | two buttons labelled Library on the board | fixed (this batch) | S |
| 121 | U14 | med | delete tool 2px from undo and redo | new | S |
| 122 | U15 | med | arrange menu has 23 items and clips at smaller heights | new | M |
| 123 | U16 | med | side tabs 28px, below phone parity size | new | S |
| 124 | U17 | med | object grip glyph 1.87:1 contrast | new | S |
| 125 | U21 | med | tools sheet items icon-only, toast covers heading | new | S |
| 126 | U22 | med | board phone header 104px and title clipped | new | M |
| 127 | U23 | med | mind map on phone not panned to new node | new | M |
| 128 | U24 | med | newest node 5px from canvas right edge | new | S |
| 129 | U26 | med | template strip clipped at right edge | new | S |
| 130 | U27 | med | layout menu is text-only, two clicks | new | M |
| 131 | U28 | med | font size stepper mixes 22px and M | new | S |
| 132 | U29 | med | two New document buttons on the empty state | fixed | S |
| 133 | U31 | med | formatting toolbar hidden by default | skipped (decision PLAN.md D1: the strip starts collapsed, chrome 171 to 89px; the Formatting button already says Show or Hide formatting toolbar and carries aria-pressed) | S |
| 134 | U32 | med | export three clicks deep in More menu | fixed (efa1ffd) | S |
| 135 | U33 | med | new document prompt lacks heading and placeholder | fixed | S |
| 136 | U34 | med | titled blank creation leaves a stray empty document | fixed (efa1ffd) | M |
| 137 | U35 | med | small targets in document list and header | fixed (efa1ffd; the suggest switch sits in a 228x34.5 row, .card-open's overlay covers its whole card, library search inputs are the Library's) | S |
| 138 | U36 | med | low contrast on doc AI label and submenu arrow | fixed (measured 14.01:1 dark on doc-ai-label; the arrow is a glyph, 3:1 applies) | S |
| 139 | U37 | med | disabled Run reason link is low contrast | fixed (#doc-code-run-why is .linklike in --accent-text, clamped to L 0.8 in dark; only the disabled button is dim, which is exempt; measured 7.7:1 light, 8.8:1 dark) | S |
| 140 | B5 | med | 14+ separate pointermove listeners, several unthrottled | fixed (9e83452, reconciled 2026-10-30) | M |
| 141 | B17 | med | link-sketch lookups parse every sketch JSON | fixed | M |
| 142 | B18 | med | item and map size caches cleared per render, forcing layout reads | fixed | M |
| 143 | D12 | med | replace-in-all re-downloads every document on each keystroke | docs/roadmap/DOCUMENTS_PLAN.md:1324 | M |
| 144 | D18 | med | live view rebuilds decorations per change, table copies text | new | L |
| 145 | D19 | med | docText toString called 35 times, each O(n) | fixed (7add0bf) | M |
| 146 | D20 | med | five whole-document renders per pause even when hidden | fixed (7add0bf) | M |
| 147 | D21 | med | four document-wide listeners run on every tab | fixed (already: 4000 mouseover + 2000 click events on the dashboard tab cost 5.5 ms and 24 ms in all of documents.js, 1.4 and 12 microseconds per event) | S |
| 148 | D22 | med | 1.1 MB documents.js plus CodeMirror bundle loaded eagerly | new | L |
| 149 | K30 | med | link-suggestions loads every entry per request, no cache | fixed 2026-10-30: kept until a session write, 300 s backstop | M |
| 150 | K31 | med | GET /entities reads every mention then slices in Python | fixed 2026-10-30: counted in SQL | S |
| 151 | E34 | med | live markdown re-renders whole answer every 66 ms | new | M |
| 152 | S16 | med | notes list never recycles rows, DOM grows unbounded | left (large; notes list already windowed, shell-1031.md) | L |
| 153 | S37 | med | list filter re-renders without debounce | fixed (already: the notes filter waits 150 ms, settings-wiring.js) | S |
| 154 | S38 | med | many timers run independent intervals | fixed (b8cfb46) | S |
| 155 | U18 | med | long tasks up to 225 ms on board interactions | new | M |
| 156 | U19 | med | mind map sibling add long tasks up to 509 ms | new | M |
| 157 | U20 | med | code file open long task of 305 ms | new | M |
| 158 | B6 | med | 319 addEventListener vs 7 remove; re-init double-fires handlers | fixed | M |
| 159 | B15 | med | four overlapping drag mechanisms plus synthetic MouseEvent bridge | new | L |
| 160 | D23 | med | hot-spot functions and 255 shared lets in one file | new | L |
| 161 | D24 | med | document paste upload lives in settings-wiring.js | new | S |
| 162 | D25 | med | document styles scattered across 11 CSS files | new | M |
| 163 | K24 | med | god modules, whiteboard router 6,123 lines | new | L |
| 164 | K25 | med | 18 functions over 150 lines, _start_tray at 346 | new | L |
| 165 | E44 | med | chatSendTurn is one 1,164-line function | new | L |
| 166 | E45 | med | five AI surfaces with separate stream consumers | new | L |
| 167 | S17 | med | four copies of the relative-time helper | fixed | S |
| 168 | S20 | med | cache prefix still carries the old product name | fixed (already built; reconciled 2026-10-30) | S |
| 169 | S44 | med | mixed button heights and radii across toolbars | fixed (b8cfb46, lint; toolbar sizes already tokens) | M |
| 170 | U25 | med | collapse chevrons overlap node edges | new | S |
| 171 | U30 | med | editor toolbar heights inconsistent | new | S |
| 172 | B40 | low | catch blocks swallow save and delete errors silently | docs/roadmap/WORLD_CLASS_PLAN.md:3877 | S |
| 173 | K11 | low | llm_api_key stored in plain text in preferences.json | new | M |
| 174 | K13 | low | MCP server has no auth and offers write tools | docs/roadmap/BACKLOG.md:4396 | M |
| 175 | K14 | low | backup restore has no per-file size or entry count cap | new | S |
| 176 | K15 | low | xmind import trusts header file_size before reading member | new | S |
| 177 | K16 | low | workspace isolation is an ORM filter, not a boundary | new | S |
| 178 | E43 | low | tools execute runs any tool after confirm, unsigned | new | M |
| 179 | B22 | low | eight console calls are the only error surfacing | fixed (this batch) | S |
| 180 | B25 | low | minimap redraws all items on any render | docs/roadmap/WHITEBOARD_PLAN.md:1219 | M |
| 181 | B28 | low | image paste lacks URL and HTML paste and size cap | new | S |
| 182 | B29 | low | inline rich text in map topics unverified | new | S |
| 183 | B33 | low | 24 NaN guards suggest NaN has leaked before | new | M |
| 184 | D35 | low | openDocument silently returns when the fetch fails | new | S |
| 185 | D36 | low | failed DELETE in docDropIfUntouched is swallowed | fixed (this batch) | S |
| 186 | D37 | low | anonymous observers never disconnected | docs/roadmap/DOCUMENTS_PLAN.md:1500 | S |
| 187 | D38 | low | run heartbeat interval created after await, can outlive run | new | S |
| 188 | D41 | low | selection-only word count missing | docs/roadmap/UI_MODERNISATION_PLAN.md:1482 | S |
| 189 | D42 | low | no spreadsheet grid view for CSV documents | new | L |
| 190 | D43 | low | no real-time collaboration or presence | docs/roadmap/MINDMAP_PLAN.md:535 | L |
| 191 | D44 | low | no page breaks, headers, footers or margin preview | new | M |
| 192 | D52 | low | code editor has no tabs, workspace or split panes | new | L |
| 193 | K18 | low | put_thumbnail is async with sync DB and file write | fixed (this batch) | S |
| 194 | K20 | low | malformed folder sidecar raises KeyError and aborts import | fixed (already: a record with no file is skipped; reconciled 2026-10-30) | S |
| 195 | K21 | low | DDL default with an apostrophe breaks startup | fixed (this batch) | S |
| 196 | K22 | low | server-local date.today used for streak, not user_now | fixed in part (journal streak and utilities; composer.py's own date.today() calls are the composer agent's) | M |
| 197 | K23 | low | token and ticket dicts mutated from several threads | new | S |
| 198 | K38 | low | media-link tickets reusable and in URL query string | new | S |
| 199 | E46 | low | chat sidebar sort covers only the first page | docs/roadmap/BACKLOG.md:1148 | S |
| 200 | E47 | low | no search of chats in the chat sidebar | new | S |
| 201 | E49 | low | editAndResend derives turn from DOM bubble index | new | S |
| 202 | E55 | low | untag with no tag named falls through to Q&A | new | S |
| 203 | E56 | low | app-control phrases like timer and pomodoro parse to nothing | new | M |
| 204 | E59 | low | no per-answer thumbs feedback | new | M |
| 205 | E60 | low | no regenerate with another model, no continue after Stop | new | M |
| 206 | E62 | low | regenerate rewords but cannot widen retrieval | new | M |
| 207 | E64 | low | internal ids and test notes in student-facing text | new | S |
| 208 | E71 | low | read aloud has no stop or speed control, unverified | new | S |
| 209 | S70 | low | no note count per tag chip | already built (tag chip counts, measured) | S |
| 210 | S71 | low | no drag and drop of files into the list | new | M |
| 211 | S72 | low | no quick-capture hint on first run | fixed (b8cfb46) | S |
| 212 | S73 | low | no word count or reading time in editor footer | already built (editor footer word count, measured) | S |
| 213 | S74 | low | no outline or table of contents for long notes | new | M |
| 214 | S75 | low | no daily note shortcut | already built (daily note, measured) | S |
| 215 | S76 | low | no hover preview for linked notes | new | M |
| 216 | S77 | low | no manual sort order | new | L |
| 217 | B26 | low | context menu builder is 453 lines with one-use items | new | M |
| 218 | B27 | low | resize and rotation handle hit size unverified | docs/roadmap/WHITEBOARD_PLAN.md:1698 | S |
| 219 | B34 | low | empty-board hint lost after dismiss, no inline cue | new | S |
| 220 | D39 | low | typo autocorrect rewrites silently with a 5s undo only | new | S |
| 221 | D40 | low | no selection word count in the status bar | fixed (already: the caret line counts selected words; reconciled 2026-10-30) | S |
| 222 | D48 | low | controls hidden in dock-menu flyouts reparented to body | new | M |
| 223 | D53 | low | code run output truncated silently at 4,000 chars | new | S |
| 224 | E37 | low | AI status control reads as an error, red circle with x | new | S |
| 225 | E41 | low | models pane jargon and redundant Use this model button | new | S |
| 226 | E51 | low | citation mark lands mid-sentence, date-only source | docs/roadmap/CHAT_PLAN.md:1810 | S |
| 227 | E52 | low | coaching tip appended inside answer text | new | S |
| 228 | E53 | low | double greeting and last-time line from app-made note | new | S |
| 229 | E54 | low | identity muddled between Atlas and Tessellate | docs/roadmap/CHAT_PLAN.md:460 | S |
| 230 | E61 | low | disabled Plan and Agent explain need only on hover | new | S |
| 231 | E63 | low | three clauses joined as a run-on, no list | new | S |
| 232 | E67 | low | next chip row offers a single chip | new | S |
| 233 | E68 | low | typing dots role=status, no aria-busy on transcript | new | S |
| 234 | E69 | low | chat autocorrect runs on names and codes unseen | new | S |
| 235 | E72 | low | Why trail shows timing lines and a wrong nothing matched | new | S |
| 236 | S55 | low | settings labels mix case against sentence case | new | S |
| 237 | S56 | low | toast stack covers bottom nav at phone width | new | S |
| 238 | S58 | low | modal return-focus target is not consistent | new | S |
| 239 | S59 | low | no skip link to main content | fixed (already built; reconciled 2026-10-30) | S |
| 240 | S60 | low | reduced-motion not applied to every animation | docs/roadmap/BACKLOG.md:1290 | S |
| 241 | S61 | low | muted text contrast near threshold in dark theme | new | S |
| 242 | S62 | low | palette empty state offers no suggestion | new | S |
| 243 | S63 | low | palette lacks note results with a preview | new | M |
| 244 | S68 | low | import panel is long and dense | new | M |
| 245 | S69 | low | backup restore has no verify-before-restore summary | new | M |
| 246 | S82 | low | segmented view toggle has no labels | new | S |
| 247 | S83 | low | filter state not summarised when the menu is closed | new | S |
| 248 | S84 | low | onboarding cannot be re-opened from Help | new | S |
| 249 | S85 | low | error toasts say what failed but not what to do | new | M |
| 250 | S86 | low | library to note takes three clicks | new | S |
| 251 | S87 | low | dashboard counts do not link to filtered views | new | S |
| 252 | S88 | low | search results lack term highlighting | new | S |
| 253 | S89 | low | export has no format picker | new | S |
| 254 | S91 | low | document title and language do not update per view | new | S |
| 255 | S92 | low | no live region for list loading and counts | new | S |
| 256 | S94 | low | offline indicator does not say what still works | new | S |
| 257 | U38 | low | duplicate document titles allowed silently | new | S |
| 258 | U41 | low | new-board toast persists and stacks with others | new | S |
| 259 | U46 | low | hidden native board select is 1px wide | new | S |
| 260 | U48 | low | export defaults to On screen, not whole board | new | S |
| 261 | U49 | low | board toolbar has 33 tab stops | new | M |
| 262 | B23 | low | export SVG built from live DOM, blocks main thread | new | M |
| 263 | B31 | low | timers and frames not cancelled on board switch | fixed | M |
| 264 | B32 | low | whiteboard-map.js rAF and timers never cancelled | new | S |
| 265 | B38 | low | single-object PUTs may still serve multi-select nudge | new | S |
| 266 | D45 | low | 871 KB wordlist fetched and dictionary built on main thread | new | M |
| 267 | K32 | low | tabs poll all reminders every minute for a due check | won't fix (the poll already asks only open reminders; the timer, badge and early alerts need the rows, 2026-10-30) | S |
| 268 | K33 | low | token sweep runs on every authenticated request | new | S |
| 269 | K34 | low | 200 MB uploads read into memory as bytes | new | M |
| 270 | K35 | low | startup PRAGMA table_info for every table each launch | new | S |
| 271 | K36 | low | list_boards and list_images run per-board queries | new | M |
| 272 | E58 | low | saved chat list rebuilt every checkpoint round | new | S |
| 273 | E65 | low | NoteView not cached, notes re-read per question | new | M |
| 274 | S64 | low | mascot and avatar assets load even when disabled | new | S |
| 275 | S65 | low | service worker precache not trimmed to critical assets | new | M |
| 276 | S90 | low | palette rebuilds 103 commands on each open | new | S |
| 277 | B24 | low | plan-history markers and decision numbers in code comments | new | S |
| 278 | B30 | low | library, interchange and templates load up front | new | M |
| 279 | B37 | low | routes_whiteboard.py is 6,123 lines in one router | new | M |
| 280 | B39 | low | module-level singletons with no reset on board switch | new | M |
| 281 | D46 | low | comment-to-code ratio of 32% with historical narration | new | M |
| 282 | D47 | low | textarea fallback surface duplicated through aliases | new | L |
| 283 | K26 | low | two schema systems, ad hoc DDL and alembic | docs/roadmap/WORLD_CLASS_PLAN.md:3878 | M |
| 284 | K27 | low | dead routes with no frontend caller | new | S |
| 285 | K28 | low | duplicated containment helpers and LOOPBACK_HOSTS | new | S |
| 286 | K29 | low | async routes mixed with sync, blocking calls stall SSE | new | S |
| 287 | K37 | low | no ANALYZE or PRAGMA optimize | fixed (this batch) | S |
| 288 | S57 | low | floating New note button overlaps content at 390px | new | S |
| 289 | S66 | low | 27 global scripts with no duplicate-global lint | new | M |
| 290 | S67 | low | duplicate plural and count helpers across views | new | S |
| 291 | S78 | low | empty states differ in tone and illustration | docs/roadmap/DOCUMENTS_PLAN.md:1512 | M |
| 292 | S79 | low | icon stroke weights mixed across nav and toolbars | new | S |
| 293 | S80 | low | card shadows and borders vary between views | new | S |
| 294 | S81 | low | long Settings panes with no sticky section index | new | M |
| 295 | S93 | low | no test for the flashEntry not-in-DOM path | new | S |
| 296 | U39 | low | template dialog check mark overlaps description | new | S |
| 297 | U40 | low | empty-board thumbnail shows mind-map placeholder | new | S |
| 298 | U42 | low | off-scale spacing values | docs/roadmap/BACKLOG.md:3319 | S |
| 299 | U43 | low | off-scale radius on tick and find panel | fixed (673039d, reconciled 2026-10-30) | S |
| 300 | U44 | low | find panel labels 11.776px, off the type scale | new | S |
| 301 | U45 | low | board font sizes and radii mostly acceptable | docs/roadmap/UI_MODERNISATION_PLAN.md:1332 | S |
| 302 | B35 | info | present, not a finding: themes, collapse, drag-reparent, markdown export | n/a (present) | - |
| 303 | B36 | info | present, not a finding: align, snap, group, lock, export | n/a (present) | - |
| 304 | D49 | info | no innerHTML of user text, keep the lint | n/a (present) | S |
| 305 | D50 | info | present: find, replace, outline, tables, export | n/a (present) | - |
| 306 | D51 | info | present: code editor multi-cursor, folding, format | n/a (present) | - |
| 307 | S54 | info | duplicate id exists only in an HTML comment, false positive | n/a (present) | S |
| 308 | U47 | info | copy rules pass, no em-dashes or exclamation marks | n/a (present) | - |
| 309 | U50 | info | focus ring consistent across board controls | n/a (present) | - |
| 310 | U51 | info | icon buttons named and help targets resolve | n/a (present) | - |
| 311 | U52 | info | core board tasks are short | n/a (present) | - |
| 312 | U53 | info | no horizontal overflow at 390px | n/a (present) | - |
| 313 | U54 | info | syntax colour contrast passes in both themes | n/a (present) | - |
