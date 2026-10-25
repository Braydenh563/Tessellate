# OPEN: everything still open from the agent files, in one place

## From the 22-10 bug doc (owner, not fixed in 0.6.1)

Whiteboard
- **Fixed f0de1da.** Format bar (Fill / Border / Width / ends / order row): the two rows clash at a half window; a line and an arrow cannot be turned into each other from the bar (setting End to None should make it a line, a mark an arrow; check `wbFmtKind` and `wbSketchTakesCaps`, reproduce first).
- **Fixed 40fa9f4 (wb-1025; 0.6.1's fix covered only a box-less well on a reopen).** Fill sub-tab in the popup moves the popup to the top left. (wb1025-colourtabs.js: 310px and 754px moves to 0 for every pair.)
- **Fixed 25e1005.** Frame upright (double-click the rotate node) resets the frame but not its contents. (wb1025-frameup.js: 88/88 to 0/0, one Undo back.)
- **Fixed b875a0d.** Emojis do not scale with their box; the size numbers show on draw but not on resize; anchors and selection border lag the resize until release. (wb1025-resize.js: glyph 46 to 154px in a 214px box; shape box 164 to 284 on a 280 path; readout shown.)

Documents and CodeMirror
- Hide all Harper/edit suggestions temporarily, plus a list of dismissed ones to restore. Fixed 134a7a4.
- Read mode: tick list checkboxes; comfortable width too narrow in full screen. Fixed 3d5ccb4.
- Full screen: the selection toolbar and meatball do not appear; top layout at half width; overflow at the top under half width. Fixed 3d5ccb4 (measured at 700 and 420).
- History popup clashes, needs a redesign. Highlight colour: picking blue on yellow text should switch colour, not show markdown; the highlight dropdown does not close on an outside press. Fixed f4c2211 (history), 3d5ccb4 and 46ae317 (colour, dropdown).
- Line-number gutter too wide at this size; wrapped lines should hang-indent; table meatball overflows and the + sits far off; the slash menu should close on an outside press and remove its slash. Fixed 745e5b1 (gutter, table), 46ae317 (hang indent, slash menu).

Composer and Guide
- Aware of the screen and recent actions; varied, shorter, warmer replies with a closing line or next step; length adjustable; personas disabled when no model. **Partly done 7072808** (no-model closing line from the newest note, Length picker applies, persona noted in Help; not done: awareness of the screen, a disabled persona picker in the dock, because boot JS and CSS are at their ratchet caps). Real-model behaviour unverified.
- Ask tab replies are identical across notes and list dates and links instead of answering; redesign Ask at half width. **Fixed 67ef381** for an open note (composer_open.py); the half-width redesign is not done.
- Open-ended requests ("open a note") should ask what, with similar-action suggestions by lexical and cosine similarity when an action is not understood. **Fixed f6c7600** (composer_suggest.py).
- Reminders magic add failed on "remind me to do my tax return when I get home tonight, probably around 7pm"; the edit buttons differ in height and have no gap. **Fixed 133c589** (25 phrasings as tests; edit form controls one height).
- Web search with no model needs SearXNG on 127.0.0.1:8888, which was not running (log in the doc); offer to start it or say how. **Fixed 33f7a0b** (says so, links the setting; starting the service from a button is not done).
- Analyse a page in the web panel: key points, section list with jump links. **Fixed 133c589** (POST /websearch/analyse, Analyse button).
- Ask tab: the owner reports the "You asked: ..." line above the answer is gone. It was removed on purpose in INBOX 1301 (tests/test_composer_form_1301.py pins it as a duplicate of the box). Confirm whether to bring it back; if so, change that test with the reason, and note the boot JS cap now has about 20 KB spare (bg-art.js went lazy, composer2).
- **Owner, 2026-10-22: the Composer and the needle (small local model) need a lot of improvement and expansion.** Open requests, web search, reading a pasted link, failure messages and the items above are examples, not the whole list. Treat as a top-priority theme for the next PR: measure a set of everyday requests against the Composer and a small model, then widen what each can do.
- Composer (no model) cannot answer open requests: "do smth cool" got "I couldn't find anything on cool. Could you say it another way?" from a notes search, and "search the web" is not handled. Ask what was meant, offer the closest actions, and for the web say it needs search. **Fixed f6c7600.**
- Composer with no model, "Read <url> and tell me about it" (a thesaurus.com page): searched the notes for "read", "www", "thesaurus" and answered with unrelated notes. A pasted link should offer to fetch and summarise the page (or say fetching needs the web tool on), not search notes. **Fixed 33f7a0b.**
- When a tool fails or a service is off (web search not connected, SearXNG down), say so in the reply, link to the setting that turns it on, and offer to turn it on (a button), instead of a dead end. Check what the Composer and the Agent do today first (owner, 2026-10-22). **Fixed 33f7a0b** for web search; other tools not checked.

Lint debt (from the 0.6.1 CI log)
- `complexity.yml` runs `ruff check src --select C901,PERF --exit-zero`, so it always passes and lists about 100 findings (C901 over 15, PERF401/403/101/102) as red annotations. Decide: a tracked cleanup (worst first: `docx_to_markdown` 55, `_optimization_pass` 37, `build_tree` 35, `provider.extract_text_tool_calls` 31, `relations.recognise` 31), or drop `--exit-zero` behind a baseline.
- `_start_tray` went 20 to 23 with the tray start-up logging: split menu building from start-up. Test on Windows.
- Reminder edit form: the time field keeps its bottom margin and may sit about 0.2rem high against the selects; the boot JS cap left no room (588,400 gz; fixed by moving a boot surface lazy).

Shell
- More-actions button on notes half off the corner under half width; Settings, Models blank bar at the top; a blank bar at the bottom; chat suggestions fade with no wrap; companion hard to throw and scrolls the page; a half-window, part-window and phone pass over the whole app; button styles in the Skills and Sources rows look out of place.
- A desktop companion (pet) outside the window, as ChatGPT desktop's: quick open, new note, reminders.
- Custom domain instead of localhost: see the owner's answer in the 0.6.1 PR; not built.

## Everything open, 2026-10-11

One list of all open work, built 2026-10-11 by the ledger agent from INBOX, every agent-remaining file (head and unmerged branches), SESSION_BRIEFS, the nine plans, ROADMAP and BACKLOG. Nothing was fixed. Rows run owner first (running, then queued), then unassigned in batch order, so the batch ranges below are id ranges.

How to read it, and what it cannot promise:

- A row is one open line from its source, cut to one sentence. The source column is `file:line` at this commit; OPEN.md lines already include the shift made by this section. Branch ledgers show `branch:file:line`.
- Plan and BACKLOG rows come from the sections that hold open work (Placed from INBOX, Still open, Not verified, canvasdepth, the numbered open lists). Rows whose first 260 characters say built, fixed, done or closed were dropped, and rows with those words only later may be built already: check the code before building (CLAUDE.md section 1).
- Size is S (under an hour, one named fix or one check), M (a session, one surface) or L (several steps or a design pass). It comes from the source's own tag when it has one and from a text rule otherwise, so treat it as a first guess.
- The same fact can appear in two sources (a plan row and an OPEN row); exact repeats were merged, near repeats were not.
- Sections whose built state the plans do not mark row by row (WORLD_CLASS_PLAN dossiers, UI Phase 11, DOCUMENTS sections 10 to 17) are one `Section:` row each, not split.
- Briefs 2 to 33 are unmarked in SESSION_BRIEFS although HISTORY moved some of them; they are grouped rows to verify, then close or build.
- Branch ledgers of agents merging now (mergetrain) are listed from the branches, since their remaining files are not on this head yet; their rows have owner unassigned where the leftover is not part of a queued agent.

The older per-agent sections stay below this one, unchanged, as the long form of the OPEN rows (their text is the full detail behind each cut line).

Totals: 1667 rows, 183 with an owner (running or queued), 1484 unassigned.

| Source | Assigned | Unassigned | Total |
| --- | --- | --- | --- |
| Brief assignments (this run) | 21 | 0 | 21 |
| agent-remaining files on unmerged branches | 136 | 87 | 223 |
| Plans and ROADMAP.md | 20 | 469 | 489 |
| INBOX.md | 5 | 18 | 23 |
| SESSION_BRIEFS.md | 1 | 24 | 25 |
| agent-remaining/OPEN.md | 0 | 643 | 643 |
| agent-remaining per-agent files (head) | 0 | 83 | 83 |
| BACKLOG.md | 0 | 160 | 160 |
| All | 183 | 1484 | 1667 |

Plan and ROADMAP rows by file: WORLD_CLASS_PLAN 114, UI_MODERNISATION_PLAN 91, CHAT_PLAN 87, MINDMAP_PLAN 70, DOCUMENTS_PLAN 54, WHITEBOARD_PLAN 37, AGENT_SKILLS_REFORM 12, GRAPH_PLAN 11, TIMELINE_PLAN 9, ROADMAP 4.

| id | item | source | size | owner |
| --- | --- | --- | --- | --- |
| 1 | INBOX 899: composer and agents pull from the notes' time words and time references | INBOX 899 (atlas branch) | M | atlas (running) |
| 2 | Later rows for the queue: B20 to B27, B40. | agent/atlas-1011:docs/roadmap/agent-remaining/atlas-1011.md:10 | S | atlas (running) |
| 3 | Not verified: any real model; the non-stream /chat route (routes_chat.py ~1571) does not answer capability questions from the list. | agent/atlas-1011:docs/roadmap/agent-remaining/atlas-1011.md:12 | S | atlas (running) |
| 4 | Found, not fixed: a chat title keeps a trailing backslash ("what is there about a gaming mouse?\"); a digest answer has no Ask next chips except B9's... | agent/atlas-1011:docs/roadmap/agent-remaining/atlas-1011.md:14 | L | atlas (running) |
| 5 | B10 rest: a document or board open in the Library (agentOpenSubject knows it; the Ask body sends only the note and category). B12 rest: flashcards... | agent/atlas-1011:docs/roadmap/agent-remaining/atlas-1011.md:6 | M | atlas (running) |
| 6 | B30 rest: the Chat tab's bubble draws the why event too. B31/B32 rest: decision 68's audit (not built) is to retire claims overlapping a wrong row... | agent/atlas-1011:docs/roadmap/agent-remaining/atlas-1011.md:7 | M | atlas (running) |
| 7 | INBOX 895: the composer as a legitimately smart chatbot, gold answers (semester example), Atlas answers | brief assignment; INBOX 895 (atlas branch) | L | atlas (running) |
| 8 | CHAT_PLAN decisions 65 to 70 and rows A1 to A8, B1 to B12, B30 to B32: Atlas as the app's assistant (A5 tool-result cards, A6 query clean-up, A3 history records, A7 background uses, A8 ghost text) | docs/roadmap/CHAT_PLAN.md:1765 | L | atlas (running) |
| 9 | A question about Atlas is answered about Atlas. Questions about capability ("can you", "do you", "are you able", "what can I do here") route to the... | docs/roadmap/CHAT_PLAN.md:1776 | M | atlas (running), then queued: composer |
| 10 | Web results are a source panel, and a page is read in place. A web search shows its results in a collapsible block, the thinking box's recipe: title... | docs/roadmap/CHAT_PLAN.md:1781 | S | atlas (running), then queued: composer |
| 11 | A fact is learned only in its context. A note tagged joke, quote, fiction, test or draft, or a sentence inside a quote, a list of jokes or a Q-and-A... | docs/roadmap/CHAT_PLAN.md:1787 | M | atlas (running), then queued: composer |
| 12 | The learned store audits itself. "Check what it learned" is a runnable pass. It runs as a scheduled background job (Settings, Schedules), as a skill... | docs/roadmap/CHAT_PLAN.md:1793 | M | atlas (running), then queued: composer |
| 13 | Completions are ghost text from the person's own words. In the capture box, the chat box and search: a greyed suggestion after the caret, Tab or... | docs/roadmap/CHAT_PLAN.md:1800 | L | atlas (running), then queued: composer |
| 14 | The answer is judged against gold answers, not rule counts (INBOX 812: "you keep saying youve improved it but i still cant see much. I feel like Im... | docs/roadmap/CHAT_PLAN.md:1807 | L | atlas (running), then queued: composer |
| 15 | Length adapts. The question's kind sets the answer's shape: a fact is one line, an overview is decision 70's shape, a compare is a table, a count is... | docs/roadmap/CHAT_PLAN.md:1853 | S | atlas (running), then queued: composer |
| 16 | Voice is a setting. The presets are Warm and concise (the default), Neutral, Playful and Plain. One table of openings, joins and closings per preset... | docs/roadmap/CHAT_PLAN.md:1858 | M | atlas (running), then queued: composer |
| 17 | Volunteered insight is a switch, and dynamic. Off, one line, or as found. At "one line" the engine adds at most one gap, bridge, change or offer... | docs/roadmap/CHAT_PLAN.md:1862 | S | atlas (running), then queued: composer |
| 18 | All four areas, in this order of build: answers (B1 to B12), trust (B30 to B32), utilities (rows A1 to A4), then the composer everywhere (B20 to... | docs/roadmap/CHAT_PLAN.md:1866 | M | atlas (running), then queued: composer |
| 19 | Model up: it leads, the composer's facts are only labelled context (a test per surface); model down: the composer covers every act (the owner... | docs/roadmap/CHAT_PLAN.md:1870 | S | atlas (running), then queued: composer |
| 20 | INBOX placed log: INBOX 895 smart chatbot placed with atlas, then the composer agent (Briefs 104 and 97) | docs/roadmap/INBOX.md:277 | S | atlas, queued: composer |
| 21 | Not verified: a real phone; the sweep's phone right flick is sometimes a drop here because the let-go reaches the page over 100 ms after the last... | agent/throw-1011:docs/roadmap/agent-remaining/throw-1011.md:11 | S | throw (running) |
| 22 | Found, not fixed (pre-existing on the base): test_companion_motion.py::test_every_way_to_a_note_counts_as_opening_it (flashEntry lost its typeof... | agent/throw-1011:docs/roadmap/agent-remaining/throw-1011.md:13 | M | throw (running) |
| 23 | INBOX 902 and Brief 88: companion physics (throw flight and feel, click arm, eased starts, resting pose) | docs/roadmap/SESSION_BRIEFS.md:1748 | L | throw (running) |
| 24 | scripts/rebrand.py (idempotent; --check; --repo-url, default Braydenh563/Tessellate; --brand-only). The orchestrator re-runs it after every merge... | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:12 | S | rebrand (running) |
| 25 | INBOX 903: rename the product to Tessellate, formerly MemoryMap AI (step 2: internal identifiers; docs; pages site) | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:13 | L | rebrand (running) |
| 26 | Former name noted: README top, Settings, About, the Guide's "name" topic, the Pages footer, both CHANGELOGs. | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:15 | S | rebrand (running) |
| 27 | Kept on purpose, with brand: keep beside each: the LAN certificate subject, the bcrypt-input salt (memorymap-bcrypt-input), the stored caption... | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:17 | M | rebrand (running) |
| 28 | Shortcuts are renamed; the old ones go on upgrade and on uninstall. | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:22 | S | rebrand (running) |
| 29 | /health says Tessellate; every check accepts both names (instance_lock.APP_NAMES, start/uninstall .sh/.bat). | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:23 | S | rebrand (running) |
| 30 | Package src/tessellate; src/memorymap is a shim (a meta-path alias to the same module objects, and python -m memorymap). The memorymap console script... | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:28 | S | rebrand (running) |
| 31 | TESSELLATE_* settings; core/envnames.py reads MEMORYMAP_* as the fallback; launchers, compose and CI do the same. | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:31 | S | rebrand (running) |
| 32 | Data folder: an existing MemoryMap AI folder is used where it is (never moved); a new install gets Tessellate (config._default_data_dir... | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:33 | S | rebrand (running) |
| 33 | Browser: memorymap.ocr.* keys move once when library.js loads, beside their only reader (the app head is at its size ratchet); the undo store... | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:36 | S | rebrand (running) |
| 34 | Kept, as names on disk or on the wire: memorymap.db, backups memorymap-*.db, the memorymap_media cookie, export and import formats (memorymap-folder... | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:39 | M | rebrand (running) |
| 35 | Windows: the installer, an upgrade from a pre-rename release, the .bat fallbacks and the package-check workflow. No Windows here; CI runs them. | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:47 | S | rebrand (running) |
| 36 | A packaged (PyInstaller) build after the package rename. | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:49 | S | rebrand (running) |
| 37 | The icons' own <title> (favicon.svg, icon-maskable.svg) still say the old name: the owner's logo pass owns them. | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:50 | S | rebrand (running) |
| 38 | Branches cut before the rename: merge, then python scripts/rebrand.py (rewrites memorymap. imports, MEMORYMAP_ names and copy), then git mv any new... | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:55 | S | rebrand (running) |
| 39 | New logo (favicon.svg and icon-maskable.svg titles still carry the old name) | agent/rebrand-1011:docs/roadmap/agent-remaining/rebrand-1011.md:30 | M | logo (running) |
| 40 | Not verified in a browser: the Alert menu, Undo the run then Ctrl+Z, the timeline range change (source and node tests only). | agent/data101b-1011:docs/roadmap/agent-remaining/data101b-1011.md:6 | S | data101b (running) |
| 41 | tests/test_activity.py::test_every_thread_site_is_registered_with_activity fails on the base: core/lanserve.py starts a thread nothing lists. | agent/data101b-1011:docs/roadmap/agent-remaining/data101b-1011.md:7 | S | data101b (running) |
| 42 | Stop mid-call covers skill runs and write tools only; a plain Chat agent turn has no budget, so Stop there still lands at the next yield. | agent/data101b-1011:docs/roadmap/agent-remaining/data101b-1011.md:8 | S | data101b (running) |
| 43 | reminder_token.key sits beside the notes in the data folder: check backups and strip_leftovers do not need to leave it out. | agent/data101b-1011:docs/roadmap/agent-remaining/data101b-1011.md:9 | S | data101b (running) |
| 44 | Brief 101b: data fixes (import bin clock, monthly anchor day, Alert menu, timeline load-more, token key) and its leftovers | docs/roadmap/SESSION_BRIEFS.md:1823 | M | data101b (running) |
| 45 | Brief 101: the found-not-fixed ledger of 41 unplaced rows (room101 is 101a; data101b running; first101c queued) | docs/roadmap/SESSION_BRIEFS.md:1823 | L | data101b (running), queued: first101c |
| 46 | INBOX placed log: INBOX 898 undo and redo universal sent to undoall | docs/roadmap/INBOX.md:275 | S | undoall2 |
| 47 | whiteboard.js:createNewBoard POST /board-library/new-board | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:100 | S | undoall2 (running) |
| 48 | whiteboard.js:finish PUT /whiteboard/boards/${boardId} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:101 | S | undoall2 (running) |
| 49 | whiteboard.js:initWhiteboard POST /media/upload | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:102 | S | undoall2 (running) |
| 50 | whiteboard.js:uploadToLibrary POST /media/upload | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:103 | S | undoall2 (running) |
| 51 | whiteboard.js:wbClearBoard DELETE ${base}/${item.id} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:104 | S | undoall2 (running) |
| 52 | whiteboard.js:wbCloneConnect POST /whiteboard/sketches | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:105 | S | undoall2 (running) |
| 53 | whiteboard.js:wbCreateBlankBoard POST /whiteboard/boards | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:106 | S | undoall2 (running) |
| 54 | whiteboard.js:wbImportOutlineFile POST /whiteboard/boards/import | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:107 | S | undoall2 (running) |
| 55 | whiteboard.js:wbNewUntitledBoard PUT /whiteboard/boards/${boardId} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:108 | S | undoall2 (running) |
| 56 | whiteboard.js:wbPlaceUploadedImage POST /media/upload | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:109 | S | undoall2 (running) |
| 57 | Open design: stand-alone capture.js and clip.js windows have no stack; the board library 'new library' and 'delete library'; board objects the board... | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:11 | S | undoall2 (running) |
| 58 | whiteboard.js:wbRestoreLinks POST /whiteboard/sketches | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:110 | S | undoall2 (running) |
| 59 | ask-history.js:clearAskHistory DELETE /ask-history | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:16 | S | undoall2 (running) |
| 60 | ask-history.js:deleteAskHistoryTurn DELETE /ask-history/${id} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:17 | S | undoall2 (running) |
| 61 | ask-history.js:forgetRecentQuestion DELETE /chat/recent?question=${encodeURIComponent(quest | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:18 | S | undoall2 (running) |
| 62 | attach-to.js:renderAttachToBoard POST /whiteboard/nodes | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:19 | S | undoall2 (running) |
| 63 | attachment-actions.js:remove DELETE /files/${spec.attachment.id} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:20 | S | undoall2 (running) |
| 64 | capture-ask.js:renderAnswerGrounding POST /learned/corrections | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:21 | S | undoall2 (running) |
| 65 | capture.js:save POST /entries | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:22 | S | undoall2 (running) |
| 66 | categories-panel.js:drawCategoryTidy POST /tidy-proposals/dismiss | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:23 | S | undoall2 (running) |
| 67 | chat-agent.js:answer POST /memory/${proposal.id}/answer | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:24 | S | undoall2 (running) |
| 68 | chat-edit.js:editAndResend POST /conversations/${chatConv.id}/truncate | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:25 | S | undoall2 (running) |
| 69 | clip.js:save POST /links/clip-page | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:26 | S | undoall2 (running) |
| 70 | dashboard.js:nightFactRow POST /entries/tensions/accept | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:27 | S | undoall2 (running) |
| 71 | dashboard.js:paintFadedNotes POST /learned/corrections | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:28 | S | undoall2 (running) |
| 72 | documents.js:runDocAiEdit POST /documents/${currentDoc.id}/ai-edit | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:29 | S | undoall2 (running) |
| 73 | INBOX 898: undo and redo universal, 89 GAP entries left in tests/test_undo_coverage.py EXEMPT | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:3 | L | undoall2 (running) |
| 74 | editor.js:inlineAiSubmit POST /documents/${currentDoc.id}/ai-edit | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:30 | S | undoall2 (running) |
| 75 | graph-canvas.js:gcDragEnd PUT /graph/pins | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:31 | S | undoall2 (running) |
| 76 | graph-canvas.js:gcSaveTopicName PUT /graph/topics/name | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:32 | S | undoall2 (running) |
| 77 | graph-canvas.js:gcTogglePin PUT /graph/pin/${node.id} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:33 | S | undoall2 (running) |
| 78 | graph-canvas.js:gcWireSelectionDock PUT /entries/${node.id} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:34 | S | undoall2 (running) |
| 79 | graph.js:renderGraphSvg PUT /graph/pin/${d.id} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:35 | S | undoall2 (running) |
| 80 | library.js:bulkDeleteLibraryMedia DELETE endpoint | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:36 | S | undoall2 (running) |
| 81 | library.js:filterLibraryImagesGallery DELETE endpoint | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:37 | S | undoall2 (running) |
| 82 | library.js:finish PUT /graph/topics/name | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:38 | S | undoall2 (running) |
| 83 | library.js:libraryActions PUT /conversations/${item.id}/pin | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:39 | S | undoall2 (running) |
| 84 | library.js:noteRead PUT /bookmarks/${bookmark.id} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:40 | S | undoall2 (running) |
| 85 | lightbox-view.js:readingDelete POST /media/${id}/${source === vision ? vision-ocr : | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:41 | S | undoall2 (running) |
| 86 | lightbox-view.js:run PUT /media/${item.id} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:42 | S | undoall2 (running) |
| 87 | meetings.js:meetingTakeBegin POST /recordings | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:43 | S | undoall2 (running) |
| 88 | meetings.js:meetingTakeDiscard DELETE /recordings/${id} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:44 | S | undoall2 (running) |
| 89 | meetings.js:meetingTakeFinish POST /recordings/${meetingTake.id}/finish | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:45 | S | undoall2 (running) |
| 90 | note-cards.js:entryItem PUT /entries/${entry.id} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:46 | S | undoall2 (running) |
| 91 | notes-list.js:offerWikiRename POST /entries/${entryId}/wiki-rename | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:47 | S | undoall2 (running) |
| 92 | quick-note.js:flushNoteOutbox POST /entries | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:48 | S | undoall2 (running) |
| 93 | settings.js:learnedBulk POST /learned/bulk | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:49 | S | undoall2 (running) |
| 94 | settings.js:learnedDelete DELETE /learned/${fact.id} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:50 | S | undoall2 (running) |
| 95 | settings.js:learnedForget DELETE /learned | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:51 | S | undoall2 (running) |
| 96 | skills.js:saveFile POST /files/save | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:52 | S | undoall2 (running) |
| 97 | spaces-find.js:initSpaceSwitcher POST /spaces | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:53 | S | undoall2 (running) |
| 98 | suggestions-inbox.js:inboxCorrection POST /learned/corrections | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:54 | S | undoall2 (running) |
| 99 | suggestions-inbox.js:inboxTypeRow POST /suggestions/types/accept | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:55 | S | undoall2 (running) |
| 100 | suggestions-inbox.js:tensionCard POST /entries/tensions/accept | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:56 | S | undoall2 (running) |
| 101 | tidy.js:tidyDismiss POST ${path}/dismiss | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:57 | S | undoall2 (running) |
| 102 | wiring.js:applyPendingChatTitle PUT /conversations/${conversationId} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:58 | S | undoall2 (running) |
| 103 | chat-attach.js:commitStagedImages POST /media/upload | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:62 | S | undoall2 (running) |
| 104 | documents-word.js:docWordUploadPicture POST /media/upload | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:63 | S | undoall2 (running) |
| 105 | library.js:(anonymous /media/upload) POST /media/upload | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:64 | S | undoall2 (running) |
| 106 | media.js:saveSketch POST /media/upload | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:65 | S | undoall2 (running) |
| 107 | settings-wiring.js:commitCaptureImages POST /media/upload | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:66 | S | undoall2 (running) |
| 108 | settings-wiring.js:handleFileUpload POST /media/upload | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:67 | S | undoall2 (running) |
| 109 | Not verified: nothing here was driven in a browser (Playwright); every helper is checked by node --check and the scanner only. Undo of a board step... | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:7 | S | undoall2 (running) |
| 110 | whiteboard-interchange.js:post POST /whiteboard/sketches | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:71 | S | undoall2 (running) |
| 111 | whiteboard-interchange.js:wbDrawioPlace POST /whiteboard/sketches | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:72 | S | undoall2 (running) |
| 112 | whiteboard-interchange.js:wbImportBoardRows POST /whiteboard/sketches | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:73 | S | undoall2 (running) |
| 113 | whiteboard-interchange.js:wbImportMermaid POST /whiteboard/sketches | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:74 | S | undoall2 (running) |
| 114 | whiteboard-interchange.js:wbMermaidPlaceNode POST /whiteboard/sketches | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:75 | S | undoall2 (running) |
| 115 | whiteboard-library.js:run DELETE /board-library/libraries/${lib.id} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:76 | S | undoall2 (running) |
| 116 | whiteboard-library.js:wbLibImportFile POST /board-library/import | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:77 | S | undoall2 (running) |
| 117 | whiteboard-library.js:wbLibNewBoardFrom POST /board-library/new-board | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:78 | S | undoall2 (running) |
| 118 | whiteboard-library.js:wbLibNewLibrary POST /board-library/libraries | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:79 | S | undoall2 (running) |
| 119 | whiteboard-library.js:wbLibPlace POST /whiteboard/boards/${boardId}/place | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:80 | S | undoall2 (running) |
| 120 | whiteboard-library.js:wbLibReplace PUT /board-library/${entry.ref.slice(5)} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:81 | S | undoall2 (running) |
| 121 | whiteboard-map.js:wbMapAdoptProvisional POST /whiteboard/boards/${row.board_id}/nodes | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:82 | S | undoall2 (running) |
| 122 | whiteboard-map.js:wbMapClearEveryTopic POST /whiteboard/boards/${boardId}/nodes/clear-style | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:83 | S | undoall2 (running) |
| 123 | whiteboard-map.js:wbMapClearToOneTopic DELETE /whiteboard/objects/${root.id} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:84 | S | undoall2 (running) |
| 124 | whiteboard-map.js:wbMapCrossLinkToBranch DELETE /whiteboard/sketches/${sketchId} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:85 | S | undoall2 (running) |
| 125 | whiteboard-map.js:wbMapCutCrossLink DELETE /whiteboard/sketches/${sketchId} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:86 | S | undoall2 (running) |
| 126 | whiteboard-map.js:wbMapFromDocument POST /whiteboard/boards/import | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:87 | S | undoall2 (running) |
| 127 | whiteboard-map.js:wbMapPasteText POST /whiteboard/boards/${boardId}/nodes/outline | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:88 | S | undoall2 (running) |
| 128 | whiteboard-map.js:wbMapRemoveKeepingBranch PUT /whiteboard/boards/${boardId}/nodes/move-many | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:89 | S | undoall2 (running) |
| 129 | Needs the server (no restore route): media/file deletes and uploads, ask-history delete/clear, learned delete/forget, tidy and tension dismiss... | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:9 | S | undoall2 (running) |
| 130 | whiteboard-map.js:wbMapRestoreRows POST /whiteboard/boards/${boardId}/nodes | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:90 | S | undoall2 (running) |
| 131 | whiteboard-map.js:wbMapReverseCrossLink PUT /whiteboard/sketches/${sketchId} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:91 | S | undoall2 (running) |
| 132 | whiteboard-map.js:wbMapReverseEdge PUT /whiteboard/boards/${boardId}/nodes/${id}/move | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:92 | S | undoall2 (running) |
| 133 | whiteboard-map.js:wbMapSetLayout PUT /whiteboard/boards/${boardId} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:93 | S | undoall2 (running) |
| 134 | whiteboard-map.js:wbMapSetNumbered PUT /whiteboard/boards/${boardId} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:94 | S | undoall2 (running) |
| 135 | whiteboard-map.js:wbMapSetTheme PUT /whiteboard/boards/${boardId} | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:95 | S | undoall2 (running) |
| 136 | whiteboard-map.js:wbMapSever PUT /whiteboard/boards/${boardId}/nodes/${id}/move | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:96 | S | undoall2 (running) |
| 137 | whiteboard-map.js:wbMapTakePicture POST /media/upload | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:97 | S | undoall2 (running) |
| 138 | whiteboard-map.js:wbMapWriteDocument POST /documents | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:98 | S | undoall2 (running) |
| 139 | whiteboard.js:createConceptMap POST /whiteboard/boards | agent/undoall-1011:docs/roadmap/agent-remaining/undoall-1011.md:99 | S | undoall2 (running) |
| 140 | INBOX placed log: INBOX 871 help search bar below the welcome tour sent to chattime; 872 restart fixed; 873 smooth transition placed | docs/roadmap/INBOX.md:280 | S | mergetrain (chattime) |
| 141 | INBOX placed log: INBOX 897 sizes per device sent to devsize | docs/roadmap/INBOX.md:276 | S | mergetrain (devsize) |
| 142 | Merge train: cifix2, chattime, phonegraph, phone2, room101, lansafe, restart, scan, ownerfix3, meaning94, voiceup, tags89, graph100, devsize, wbfix, small, themes95, wbcolour, secscan (19 branches) | git branch --list 'agent/*' | L | mergetrain (running) |
| 143 | INBOX 828, the owner 2026-10-11, verbatim (the Voice note dialog: transcribing, then "couldn't be transcribed"): "also if I record a meeting or audio... | docs/roadmap/UI_MODERNISATION_PLAN.md:1568 | L | mergetrain (voiceup) |
| 144 | INBOX 829, the owner 2026-10-11, verbatim (the Focus timer widget): "can you redesign the focus timer as well??" (board and map previews are in... | docs/roadmap/UI_MODERNISATION_PLAN.md:1569 | L | mergetrain (voiceup) |
| 145 | V2. Input: a device picker (every microphone the browser lists, remembered), noise suppression, echo cancellation and automatic gain as switches (the... | docs/roadmap/UI_MODERNISATION_PLAN.md:1575 | M | mergetrain (voiceup) |
| 146 | V3. Enhancement on save, local: a high-pass and loudness normalise pass on the kept audio, a switch, on by default; the original is kept until the... | docs/roadmap/UI_MODERNISATION_PLAN.md:1576 | S | mergetrain (voiceup) |
| 147 | V4. The level line draws the analyser's real signal and is measured to move; with reduced motion it is a static meter. | docs/roadmap/UI_MODERNISATION_PLAN.md:1577 | S | mergetrain (voiceup) |
| 148 | V5. Live transcription: while recording, the captions pipeline writes the words into the dialog as they are spoken; the full pass replaces them after. | docs/roadmap/UI_MODERNISATION_PLAN.md:1578 | L | mergetrain (voiceup) |
| 149 | V6. Live captions are reachable where a person looks: a Captions button in the voice note dialog and the Recordings bar, a row in the shell's tools... | docs/roadmap/UI_MODERNISATION_PLAN.md:1579 | S | mergetrain (voiceup) |
| 150 | V7. The dialog redesigned from DESIGN recipes: name field, one large record control with the timer, the level line, the device chip, Pause, Stop and... | docs/roadmap/UI_MODERNISATION_PLAN.md:1580 | L | mergetrain (voiceup) |
| 151 | V8. The focus timer: a ring with the time large, presets as a segmented control plus a custom stepper, Start and Pause as one primary, a chime and a... | docs/roadmap/UI_MODERNISATION_PLAN.md:1581 | M | mergetrain (voiceup) |
| 152 | frontend/js/whiteboard.js:8685: Undo of a delete re-creates the item with POST and a payload passed through wbKeepOwnLayer. | agent/wbfix-1011:docs/roadmap/agent-remaining/wbfix-1011.md:24 | S | mergetrain (wbfix) |
| 153 | frontend/js/whiteboard-library.js:1653-1662, wbKeepOwnLayer: for a sketch it parses data and, when there is no truthy layer, writes layer: "". For an... | agent/wbfix-1011:docs/roadmap/agent-remaining/wbfix-1011.md:25 | M | mergetrain (wbfix) |
| 154 | src/memorymap/api/routes_whiteboard.py:1328, _on_current_layer: on every create, if "layer" is absent it stamps the current layer. If the key is... | agent/wbfix-1011:docs/roadmap/agent-remaining/wbfix-1011.md:26 | M | mergetrain (wbfix) |
| 155 | Recommended: make "" mean "no layer" on the server. In _on_current_layer, when data.get("layer") == "", return the data with the layer key removed... | agent/wbfix-1011:docs/roadmap/agent-remaining/wbfix-1011.md:32 | M | mergetrain (wbfix) |
| 156 | Do not fix it by changing the sweep's comparator to ignore layer. That hides a real change to stored data. | agent/wbfix-1011:docs/roadmap/agent-remaining/wbfix-1011.md:33 | S | mergetrain (wbfix) |
| 157 | Objects: the same layer:"" is written for text boxes (wbKeepOwnLayer line 1654). wbtrash660.js does not show it, because boardState() prints only... | agent/wbfix-1011:docs/roadmap/agent-remaining/wbfix-1011.md:34 | M | mergetrain (wbfix) |
| 158 | Add a targeted test first, in the file that covers _on_current_layer (grep _on_current_layer under tests/): create with layer: "", assert the stored... | agent/wbfix-1011:docs/roadmap/agent-remaining/wbfix-1011.md:38 | M | mergetrain (wbfix) |
| 159 | Restart the server after the Python change (uvicorn does not reload). | agent/wbfix-1011:docs/roadmap/agent-remaining/wbfix-1011.md:39 | S | mergetrain (wbfix) |
| 160 | Rerun ONLY=board node scratchpad/ui-sweeps/wbtrash660.js (expect 39/39) and scripts/gate.sh --changed. Never the full suite. | agent/wbfix-1011:docs/roadmap/agent-remaining/wbfix-1011.md:40 | L | mergetrain (wbfix) |
| 161 | scratchpad/ui-sweeps/wbphone.js (fixed by the sweep commit, not an app issue): intermittent. Across about 12 runs it failed 2 times. One failure was... | agent/wbfix-1011:docs/roadmap/agent-remaining/wbfix-1011.md:44 | M | mergetrain (wbfix) |
| 162 | INBOX 896: LAN status-bar icon and popup, palette hotkey, live open/close on network change | INBOX 896 (docs/roadmap/INBOX.md:252) | L | queued: lanbar |
| 163 | INBOX 892: hotspot, re-issue the certificate when the address set changes | INBOX 896 (docs/roadmap/INBOX.md:252) | M | queued: lanbar |
| 164 | INBOX 894: each phone connection on the privacy receipt as an incoming row | INBOX 896 (docs/roadmap/INBOX.md:252) | S | queued: lanbar |
| 165 | INBOX 900: toggle LAN on or off from the status-bar icon, no restart | INBOX 896 (docs/roadmap/INBOX.md:252) | M | queued: lanbar |
| 166 | A network change takes up to 30 s (lanserve.REFRESH_SECONDS) to close or open the port. | agent/mergetrain-1011:docs/roadmap/agent-remaining/lansafe-1011.md:39 | S | queued: lanbar |
| 167 | MEDIUM: PUT /preferences let a phone set searxng_url (SSRF to any LAN/localhost host, path /search), export_save_dir (where files land), auto-update... | agent/secscan-1011:docs/roadmap/agent-remaining/secscan-1011.md:25 | M | queued: lanbar |
| 168 | MEDIUM (lansafe's lines, not edited here): POST /auth/lan-options lets a phone with the password turn "Allow on any network" on and "Ask before a new... | agent/secscan-1011:docs/roadmap/agent-remaining/secscan-1011.md:35 | M | queued: lanbar |
| 169 | MEDIUM: QUT wifi. Base has no allowed-network gate: once LAN mode is on, the https port listens on every network the laptop joins, protected by the... | agent/secscan-1011:docs/roadmap/agent-remaining/secscan-1011.md:36 | M | queued: lanbar |
| 170 | LOW, not fixable without remaking a decision: semantic auto-install (default on, the owner's choice) can be started by a failed embed that a phone's... | agent/secscan-1011:docs/roadmap/agent-remaining/secscan-1011.md:37 | M | queued: lanbar |
| 171 | secscan decision 1: a phone-triggered auto-install is refused (semantic auto-install failed embed from a phone save) | agent/secscan-1011:docs/roadmap/agent-remaining/secscan-1011.md:44 | S | queued: lanbar |
| 172 | secscan decision 2: LAN auto-off after 14 days unused | brief assignment (secscan) | M | queued: lanbar |
| 173 | INBOX placed log: INBOX 892 and 894 placed with 896 (lanbar) | docs/roadmap/INBOX.md:278 | S | queued: lanbar |
| 174 | Not verified: a real iPhone (profile install, trust steps), Windows' Public/Private category (parsed from fixture JSON only), macOS readers (parsed... | agent/mergetrain-1011:docs/roadmap/agent-remaining/lansafe-1011.md:34 | S | queued: iPhone sweep |
| 175 | 887 keyboard: verify on a real iPhone in Safari. Sandbox only stubs visualViewport (scratchpad/ui-sweeps/kbinset.js); the owner's "covers the text... | agent/mergetrain-1011:docs/roadmap/agent-remaining/phone2-1011.md:6 | S | queued: iPhone sweep |
| 176 | Not verified: a real iPhone Safari (the select picker opening on script focus is Chromium emulation evidence plus the owner's report); the compact... | agent/mergetrain-1011:docs/roadmap/agent-remaining/phonegraph-1011.md:7 | S | queued: iPhone sweep |
| 177 | iPhone sweep: verify the phone fixes on a real iPhone (keyboard 887, pinch 888, select picker 885, LAN profile install) | agent/phone2-1011 and agent/phonegraph-1011 ledgers | M | queued: iPhone sweep |
| 178 | Not verified: a real phone on a real LAN (iPhone Safari); lansafe merged on top. | agent/secscan-1011:docs/roadmap/agent-remaining/secscan-1011.md:40 | S | queued: iPhone sweep |
| 179 | Brief 101c: the found-not-fixed ledger, third agent | docs/roadmap/SESSION_BRIEFS.md:1823 | M | queued: first101c |
| 180 | INBOX 895 part 2: the composer as a smart chatbot after atlas | brief assignment | L | queued: composer |
| 181 | UK and US spelling equivalence in search (colour/color, organise/organize) | brief assignment | S | queued: composer |
| 182 | Brief 97: the composer as the place to go, the graph maker (INBOX 860) | docs/roadmap/SESSION_BRIEFS.md:1799 | L | queued: composer |
| 183 | Brief 104: typos read in context, not as slang (INBOX 869) | docs/roadmap/SESSION_BRIEFS.md:1845 | M | queued: composer |
| 184 | Not driven: the code IDE, the OCR workspace, the phone More sheet, the lock screen, the board's tools and Present. | docs/roadmap/agent-remaining/OPEN.md:2277 | S | unassigned |
| 185 | Not verified: a real Needle engine on leftover turns; a real chat model on a one-option ask_user. | docs/roadmap/agent-remaining/OPEN.md:2284 | S | unassigned |
| 186 | Not driven: dark theme for the hand-drawn look, tables, the Data tab and the current layer; a real touch double-tap into a table cell; an .xmind... | docs/roadmap/agent-remaining/OPEN.md:2293 | S | unassigned |
| 187 | No real model here: skill_rates.json ships empty, the small-class gate, time to first step and DEFAULT_CALLS_PER_STEP are unmeasured. | docs/roadmap/agent-remaining/OPEN.md:2314 | S | unassigned |
| 188 | Not verified: printed manual output, real-model answers, iOS zoom on the 13.6px name field. | docs/roadmap/agent-remaining/OPEN.md:2333 | S | unassigned |
| 189 | Not verified: a real model or Needle answering the assistant's prompts; the tablet layout beyond one measure at 1024. | docs/roadmap/agent-remaining/OPEN.md:2350 | S | unassigned |
| 190 | Not verified: real Whisper segments, a real model's rewording and speaker naming, "Name the speakers" driven in the page. | docs/roadmap/agent-remaining/OPEN.md:2358 | S | unassigned |
| 191 | Not verified: the path with a real model running (its grounded tags first, then the engine's); dark theme. | docs/roadmap/agent-remaining/OPEN.md:2372 | S | unassigned |
| 192 | Not verified: the owner's screen, Saved views, local and global switching, reduced motion in a browser. | docs/roadmap/agent-remaining/OPEN.md:2398 | S | unassigned |
| 193 | Not verified: a real embedder, the professional voice in a browser, 390px, the picture notice in a browser. | docs/roadmap/agent-remaining/OPEN.md:2442 | S | unassigned |
| 194 | Not verified: a Chat tap 700 ms after boot at 390 on an idle machine; the Highlight API in the macOS webview. | docs/roadmap/agent-remaining/OPEN.md:2452 | S | unassigned |
| 195 | Not verified: real Whisper on a kept recording; a real microphone, Safari (mp4) and Firefox (ogg). | docs/roadmap/agent-remaining/OPEN.md:2483 | S | unassigned |
| 196 | Not verified: under 1 s through the sheet on an unloaded machine; a real network install inside the app; WebView2 and Safari. | docs/roadmap/agent-remaining/OPEN.md:2492 | S | unassigned |
| 197 | Not verified: any real whisper-server or microphone, Firefox and Safari capture, Chromium's fake-mic start offset. | docs/roadmap/agent-remaining/OPEN.md:2510 | S | unassigned |
| 198 | Not verified against a real model: whether it plans act-shaped steps plan_writes can preview and uses the narrowed tools a planned step is offered... | docs/roadmap/agent-remaining/OPEN.md:2514 | S | unassigned |
| 199 | Not verified in the browser: Chat's own path for the plan card and per-write undo (chat-attach.js onTool); an edit's diff under a step (pytest only). | docs/roadmap/agent-remaining/OPEN.md:2515 | S | unassigned |
| 200 | Not verified: Firefox and Safari permission help, the webview's denied state, firing in a hidden tab (falls to the minute poll), a real non-UTC... | docs/roadmap/agent-remaining/OPEN.md:2534 | S | unassigned |
| 201 | Not verified: the dictionary spelling offer in a live empty result; the server's own correction answered every typo tried, so finderSpellingOffer was... | docs/roadmap/agent-remaining/OPEN.md:2538 | S | unassigned |
| 202 | Not verified: an act row against a running model; with no model it opens Chat with the act's opening words at 1440 and 390 and sends nothing... | docs/roadmap/agent-remaining/OPEN.md:2539 | S | unassigned |
| 203 | Brief 84, not verified: the Guide's new first line and act topics in a browser (API and unit tests only); no real model. | docs/roadmap/agent-remaining/OPEN.md:2615 | S | unassigned |
| 204 | Brief 34, not verified: the arm angle over a walk cycle; 104 px faces (2 to 3 of 15 distinct in light); no real WebView2 or WebKitGTK; all timings... | docs/roadmap/agent-remaining/OPEN.md:2644 | S | unassigned |
| 205 | Brief 69, not verified: the desktop webview; dark theme for the new panel rows; a large SQL result; touch.js on the other surfaces. | docs/roadmap/agent-remaining/OPEN.md:2668 | S | unassigned |
| 206 | Not measured by Brief 56: 1024 and 820 widths, dark-theme counts, a Chat with a conversation, the document AI panel, a board with a selection. | docs/roadmap/agent-remaining/OPEN.md:2677 | S | unassigned |
| 207 | The launchers want one run on a real Windows machine: start.bat, start.bat --doctor, start.bat --shortcut and uninstall.bat --dry-run, watching the... | docs/roadmap/agent-remaining/OPEN.md:2747 | M | unassigned |
| 208 | backend-0926.md: F7's thread modules onto core/jobs.py (13 left, tests/test_flaw_class_lints.py's ratchet). Not verified: the receipt against a real... | docs/roadmap/agent-remaining/OPEN.md:2776 | S | unassigned |
| 209 | Every provider test runs against a fake transport (CLAUDE.md section 4), and that covers more open work than any other single line here: no real... | docs/roadmap/agent-remaining/OPEN.md:3179 | S | unassigned |
| 210 | Not verified: whether the closed .doc-dock-menu-list at 390 paints (it lays out, 13 items, x = -32 on a code document); open it and measure before... | docs/roadmap/agent-remaining/OPEN.md:3291 | S | unassigned |
| 211 | Not verified: the map grip that overlaps "Add a child to" (its accessible name was not read; it shows only with a topic selected after adding... | docs/roadmap/agent-remaining/OPEN.md:3292 | S | unassigned |
| 212 | Not driven: Summarise's 503 with no model (read from routes_meetings.py), pinch zoom in the OCR workspace, the phone path of any board or map... | docs/roadmap/agent-remaining/OPEN.md:3294 | S | unassigned |
| 213 | CHAT: the evals gate runs on a 3B model (hours on these cores) and waits on a real-model run. (from op3-1005.md) | docs/roadmap/agent-remaining/OPEN.md:3308 | S | unassigned |
| 214 | Not verified in a browser: the another-device notice on the recovery card (the sweep server binds loopback only); a real phone and a screen reader on... | docs/roadmap/agent-remaining/OPEN.md:3369 | S | unassigned |
| 215 | Not verified: a real model's greeting in the new layout (a long AI line widens the left column up to its 45% cap; measured with handwritten phrases... | docs/roadmap/agent-remaining/OPEN.md:3371 | S | unassigned |
| 216 | Not verified: a real model load for the new built-in embedding models (no sentence-transformers here); Pull a model by name is tested against a... | docs/roadmap/agent-remaining/OPEN.md:3383 | S | unassigned |
| 217 | Not measured at 390: the Documents sidebar and the board zoom pill are not on screen there (the sidebar is a sheet), so both were measured at 1440... | docs/roadmap/agent-remaining/OPEN.md:3387 | S | unassigned |
| 218 | Not measured: the chat dock's controls, the board's context bar, the stepper and the map strip, named in PILL_CONTROLS with full-round rules. (from... | docs/roadmap/agent-remaining/OPEN.md:3388 | S | unassigned |
| 219 | Not verified: suggestion mode switched on while a candidate is chosen (the replacement goes through docProseFix), a touch long-press on a suggested... | docs/roadmap/agent-remaining/OPEN.md:3393 | S | unassigned |
| 220 | Not verified: the phone's action sheet (openKebabSheet) and touch below 600 (its dismissal was not pressed twice), a real screen reader, and the... | docs/roadmap/agent-remaining/OPEN.md:3396 | S | unassigned |
| 221 | Not verified: the contrast of the accent count on the broom (contrast.js), a browser run of the automatic pass after filing (pytest only), and a real... | docs/roadmap/agent-remaining/OPEN.md:3405 | S | unassigned |
| 222 | Not verified: Summarise against a real small model (the fake model only; its pipe format and quoting are unknown), and transcription (no... | docs/roadmap/agent-remaining/OPEN.md:3408 | S | unassigned |
| 223 | Not verified: the other 100 toast(..., true) call sites were not each triggered. A lint covers them; their situations (a formatter refusing a file... | docs/roadmap/agent-remaining/OPEN.md:3412 | S | unassigned |
| 224 | Not measured: dark theme for axe target-size and scrollable-region-focusable; the 1024 width. (from a11yfix-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3462 | S | unassigned |
| 225 | Decision 45: the readings are listed (composer._readings, src/memorymap/ai/composer.py:2693); a running model does not yet pick among them (needs a... | docs/roadmap/agent-remaining/OPEN.md:3493 | S | unassigned |
| 226 | Not verified: Ollama's real keep_alive: 0 and /api/ps (a slow fake in the agent's scratch dir stood in), the desktop window, WebKit. | docs/roadmap/agent-remaining/OPEN.md:3526 | S | unassigned |
| 227 | Not verified: the .docx opened in Word itself (its XML and Mammoth's reading only); Format on a large real file; the list chords on a non-US layout... | docs/roadmap/agent-remaining/OPEN.md:3540 | S | unassigned |
| 228 | Not verified by either: a real model's path; a screen reader toggling a chip; a browser locale other than en-US; the full suite. [f1-1010, f2-1010] | docs/roadmap/agent-remaining/OPEN.md:3581 | S | unassigned |
| 229 | Not verified: real-model answers through the validators (fake transport and the route test only); dark mode. [f3-1010] | docs/roadmap/agent-remaining/OPEN.md:3592 | S | unassigned |
| 230 | Not verified: hybrid ranking cost at 5,000 notes with a real embedding model (keyword plus the fake backend only); the saved-search ⋯ menu opened in... | docs/roadmap/agent-remaining/OPEN.md:3600 | S | unassigned |
| 231 | Not verified: tests elsewhere that relied on blank lines removed from CSS files 00, 01, 02, 05, 06, 07 and 10 to pay for the CSS budget; the picker... | docs/roadmap/agent-remaining/OPEN.md:3673 | S | unassigned |
| 232 | Not driven with a real model: a live streamed answer getting its time when the meta row lands (driven with addAssistantBubble plus messageMetaLine in... | agent/mergetrain-1011:docs/roadmap/agent-remaining/chattime-1010.md:5 | S | unassigned |
| 233 | Not verified: dark theme and phone width for the moved rules (only errors.js at 390: 0 findings); the first press of the bell on a slow link (the... | agent/mergetrain-1011:docs/roadmap/agent-remaining/room101-1011.md:10 | S | unassigned |
| 234 | Autocorrect with an IME, on a real phone keyboard (its own suggestions fire insertReplacementText, which this leaves alone), and in the graph's and... | agent/mergetrain-1011:docs/roadmap/agent-remaining/meaning94-1011.md:12 | S | unassigned |
| 235 | A real model (Ollama or llama.cpp): every filing, Ask and Chat result above is against a stand-in server or no model. "Filing catches up once a model... | agent/mergetrain-1011:docs/roadmap/agent-remaining/scan-1011.md:15 | S | unassigned |
| 236 | Enhancement on a real voice: measured on synthetic tones through Chromium's fake microphone (RMS 0.054 to 0.082, peak 0.158 to 0.254); takes over 30... | agent/voiceup-1011:docs/roadmap/agent-remaining/voiceup-1011.md:15 | M | unassigned |
| 237 | Not verified: any real model's behaviour in the handoff (choosing among numbered readings, "reorder, do not add"); the taxonomy pack's size as a... | docs/roadmap/agent-remaining/assistant-1010.md:15 | S | unassigned |
| 238 | Not verified: Saved views and local/global switches through the view-change sweep (layouts, Refresh and a return to the tab were measured); the... | docs/roadmap/agent-remaining/graphfeel-1010.md:23 | S | unassigned |
| 239 | Boot gzip budget, what the 2026-10-05 split did not take (792,754 to 758,418 bytes, notes-list.js 63,548 to 57,929; test_static_compression.py has... | docs/roadmap/agent-remaining/OPEN.md:1882 | L | unassigned |
| 240 | The budgets spec flaps in CI (a different budget each run: list, search, board, first_interaction) while it shares the runner with the other specs... | docs/roadmap/agent-remaining/OPEN.md:2219 | M | unassigned |
| 241 | App scripts at 320,589 of 320,600 gzipped (11 bytes); seven typeof guards removed on eager functions, each path not driven by hand. | docs/roadmap/agent-remaining/OPEN.md:2227 | S | unassigned |
| 242 | Decisions 12 (layers, 115 literals), 13 (19 drop shadows), 16 (128 .important) are ratchets only; 13.R not started. | docs/roadmap/agent-remaining/OPEN.md:2250 | S | unassigned |
| 243 | The run's budget usage is on the result event but not drawn in chat-agent.js's result box. | docs/roadmap/agent-remaining/OPEN.md:2316 | S | unassigned |
| 244 | Right-click and long-press on a snippet row do not open its menu (needs navigation.js ROW_MENU_HOSTS, a boot file, and TOTAL_CAP had 35 bytes). | docs/roadmap/agent-remaining/OPEN.md:2348 | S | unassigned |
| 245 | First interaction (about 4.4 s) is the slowest number; decision 54's 5,000-note list and search not re-measured; no Settings UI shows the budgets. | docs/roadmap/agent-remaining/OPEN.md:2389 | S | unassigned |
| 246 | Guide topics whiteboard-controls (1915 of 1920) and mind-map-features are at the reply budget. | docs/roadmap/agent-remaining/OPEN.md:2416 | S | unassigned |
| 247 | TOTAL_CAP (all app scripts) has 32 bytes of headroom; the next lever is the meeting overlay's listeners in settings-wiring.js. | docs/roadmap/agent-remaining/OPEN.md:2458 | S | unassigned |
| 248 | confirmDialog and promptDialog mount on <body>, so one asked from inside a modal opens beneath it; app.js is at its gzip ratchet. | docs/roadmap/agent-remaining/OPEN.md:2500 | S | unassigned |
| 249 | timelinepaging.js: the strip-click check fails on the base too; its 100 ms frame check passed once and failed twice under load. | docs/roadmap/agent-remaining/OPEN.md:2532 | S | unassigned |
| 250 | VC12 (Harper on node labels) not started: the budget went to rows 1 to 9. MINDMAP_PLAN "Vendored capabilities to use" still holds it. | docs/roadmap/agent-remaining/OPEN.md:2550 | S | unassigned |
| 251 | maplayouts.js "tree-left carries the branch bar on the edge the parent is on" fails on the base too (1px against 1px). | docs/roadmap/agent-remaining/OPEN.md:2555 | S | unassigned |
| 252 | Step 5 not built: one curve table for every joint (120 to 400 ms), the idle pool's never-within-five rule and a reaction budget a minute beyond the... | docs/roadmap/agent-remaining/OPEN.md:2630 | M | unassigned |
| 253 | tests/test_icon_conventions.py::test_the_vertical_kebab_is_only_at_the_end_of_a_vertical_list_row_or_in_a_narrow_column fails on this branch's head... | docs/roadmap/agent-remaining/OPEN.md:2653 | M | unassigned |
| 254 | Brief 77, found: the shape flyout opens only from its 10 px caret or a long-press, too small for a finger on a phone; boot CSS is within 12 bytes... | docs/roadmap/agent-remaining/OPEN.md:2669 | S | unassigned |
| 255 | A flaky timing test: tests/test_relations_kg2.py's 10k timing is flaky under load (the typo, message-wording, thread-ratchet and list-paging tests... | docs/roadmap/agent-remaining/OPEN.md:3067 | S | unassigned |
| 256 | The behaviour model (Brief 34, second part): a state machine with blended transitions, idle variation from a weighted pool, reactions to every app... | docs/roadmap/agent-remaining/OPEN.md:3271 | M | unassigned |
| 257 | Timings: two runs at 1440, one at 390, the second 1440 run under a concurrent sweep; ranges, not budgets. (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3423 | S | unassigned |
| 258 | The boot CSS cap (tests/test_boot_budget.py, 183,300) had 3 bytes of room; this work spent it with blank-line collapses in 00-tokens-shell.css and... | docs/roadmap/agent-remaining/OPEN.md:3459 | M | unassigned |
| 259 | app.js is within 14 bytes of its ratchet (tests/test_static_compression.py, 14,300): makeUnlinkAccessible moved out to note-cards.js to stay under... | docs/roadmap/agent-remaining/OPEN.md:3460 | S | unassigned |
| 260 | Decision 8's bar, "below 0.8 top-1 without a model the step is not done": 0.417 (tests/test_filing_accuracy.py, strict xfail). Forced to choose, the... | docs/roadmap/agent-remaining/OPEN.md:3463 | M | unassigned |
| 261 | **Already fixed (passes at head, 2026-10-19).** Found, not mine: tests/test_ask_answer_object.py::test_ask_is_never_disabled_when_the_model_is_off fails on the base too (the chat skills trigger's... | docs/roadmap/agent-remaining/OPEN.md:3499 | S | unassigned |
| 262 | **Already fixed (tests/test_reading.py asks "What time on Friday ..."; 2026-10-19).** ai/reading.py reads "review budget friday" (reminder surface) as sure at 09:00 while quickadd.js asks "What time on ...?" (decision 50); the reading... | docs/roadmap/agent-remaining/OPEN.md:3577 | S | unassigned |
| 263 | Dashboard: the digest is in dashboard.js (a boot file, about 700 bytes gzipped); a lazy home would delay the first paint of the widget it opens. The... | docs/roadmap/agent-remaining/OPEN.md:3606 | M | unassigned |
| 264 | Boot JS 582,371 to 583,240 bytes gzipped (+869: the digest, the Library and Graph filters, the palette rows, the voice table, textCounts; cap... | docs/roadmap/agent-remaining/OPEN.md:3616 | M | unassigned |
| 265 | The 68 broad excepts that log nothing and return a fallback (89 minus the 21 seeded) are not ratcheted; decide whether decision 57 means them.... | docs/roadmap/agent-remaining/OPEN.md:3644 | S | unassigned |
| 266 | Graph at rest (1 to 10 long tasks) and the companion (4 to 6 at rest) are the two surfaces over the zero target (frames.js REST_BUDGET).... | docs/roadmap/agent-remaining/OPEN.md:3648 | S | unassigned |
| 267 | The constellation fades in; its stars do not glide in from a first position (dashboard.js is a boot script with 11 bytes of gzip headroom). | agent/graph100-1011:docs/roadmap/agent-remaining/graph100-1011.md:23 | S | unassigned |
| 268 | tests/test_complexity.py fails on spelling.py, utilities.py, activity.py. | agent/graph100-1011:docs/roadmap/agent-remaining/graph100-1011.md:32 | S | unassigned |
| 269 | Boot CSS 177,905 to 176,370 bytes gzipped (cap 183,300, unchanged): room 5,395 to 6,930. 89 Library-only rules moved to library-lazy.css, ahead of... | agent/mergetrain-1011:docs/roadmap/agent-remaining/room101-1011.md:3 | S | unassigned |
| 270 | 381 more Library-only CSS rules could move (633 qualify by selector, 470 pass the file ratchets, 89 moved). The rest tie on specificity with a rule... | agent/mergetrain-1011:docs/roadmap/agent-remaining/room101-1011.md:6 | M | unassigned |
| 271 | Found, not fixed: scratchpad/ui-sweeps/wbtrash660.js "shape: Undo restores the board identically" fails on the base too... | agent/mergetrain-1011:docs/roadmap/agent-remaining/phone2-1011.md:10 | S | unassigned |
| 272 | QR code of the address: not built (scripts gzip budget had 1 byte left before the merge; frontend/js/status.js startReminderWatch hook). Would go in... | agent/mergetrain-1011:docs/roadmap/agent-remaining/lansafe-1011.md:31 | S | unassigned |
| 273 | Tool results accumulate within a turn (already capped by TOOL_RESULT_BUDGET_CHARS, but the cap is generous at 24k characters). | docs/roadmap/BACKLOG.md:909 | S | unassigned |
| 274 | Budgeted the same way everything else is (ai/context.py), with its own share, so a long guide crowds out notes visibly rather... | docs/roadmap/BACKLOG.md:2531 | S | unassigned |
| 275 | Internal navigation is one lazy file, settings-find.js (loaded with the first open of Settings, so outside the boot gzip budget, which sits 842 bytes... | docs/roadmap/UI_MODERNISATION_PLAN.md:1162 | L | unassigned |
| 276 | Generation measured 2.0 to 2.7 s wall at load average 12 to 15 on four cores (2026-10-10); no unloaded figure was taken, and the 3 s lint budget is... | docs/roadmap/agent-remaining/codemap-1010.md:8 | S | unassigned |
| 277 | found-1010: reader count ratchet (6 files outside the allowed two), five date readers and no unit reader, probe tables (23 when.resolve rows wrong on... | docs/roadmap/agent-remaining/found-1010.md:7 | M | unassigned |
| 278 | The desktop webview (pywebview) and a slow machine: the 450 ms warm-up budget on a slow CPU records fewer ticks, so the playback is shorter. | docs/roadmap/agent-remaining/graphfeel-1010.md:12 | S | unassigned |
| 279 | tests/test_global_scope_ratchet.py: 278 typeof x === "function" guards against a cap of 277. | docs/roadmap/agent-remaining/graphfeel-1010.md:17 | S | unassigned |
| 280 | Every wall time was taken at load average 8 to 10 on 4 cores (other sessions' browsers and servers); re-run measure-interactions.js and... | docs/roadmap/agent-remaining/measure-1010.md:3 | M | unassigned |
| 281 | Performance budget (import under 0.5 s, compose under 150 ms for 20 notes) and the model-dies-mid-answer route bug (routes_chat.py near 1963). | docs/roadmap/agent-remaining/spec39-1010.md:15 | S | unassigned |
| 282 | Tool schemas at 32,762 of 32,768 characters for a 32k window (tests/test_prompt_budget.py): the next tool added trims every description. | docs/roadmap/agent-remaining/triage-1010.md:26 | S | unassigned |
| 283 | Boot CSS 3 bytes under its cap, boot JS about 100 bytes under (tests/test_boot_budget.py, tests/test_static_compression.py): the cited-name code went... | docs/roadmap/agent-remaining/triage-1010.md:27 | S | unassigned |
| 284 | The tracks table: track 11 audio, 12 packaging (Docker image, installer optional packages), 14 learnability (docs/ROADMAP.md) | docs/ROADMAP.md:113 | L | unassigned |
| 285 | The Windows grammar worker failure not reproduced (now names its reason). | docs/roadmap/agent-remaining/OPEN.md:2253 | S | unassigned |
| 286 | No live sync between two open windows; a change shows in the other after a reload. | docs/roadmap/agent-remaining/OPEN.md:2307 | S | unassigned |
| 287 | Windows and macOS not run: both need a check by hand. On Windows a toast pressed in the Action Center after 600 s does nothing (needs a COM... | docs/roadmap/agent-remaining/OPEN.md:2364 | M | unassigned |
| 288 | The packaged helper: a Download pin per platform (URL, sha256, size) for whisper-server and a model in core/extras.py (id="captions"; the release... | docs/roadmap/agent-remaining/OPEN.md:2505 | M | unassigned |
| 289 | Utilities row 5, "every utility has ... a data-help-for popover": the timer, stopwatch and Count words are palette rows with no surface of their own... | docs/roadmap/agent-remaining/OPEN.md:2562 | M | unassigned |
| 290 | Nothing Windows was executed: splash.ps1 has never been drawn (layout, the marquee, the Details toggle, Clipboard::SetText from a hidden host, the... | docs/roadmap/agent-remaining/OPEN.md:3186 | M | unassigned |
| 291 | installer.iss's ISPP version reader (#sub, #for, RPos) compiles only on Windows; it is not verified until a Windows CI run passes. (from... | docs/roadmap/agent-remaining/OPEN.md:3321 | S | unassigned |
| 292 | The upgrade step downloads the latest release with gh and github.token; a fork or a repo without releases fails it loudly. (from... | docs/roadmap/agent-remaining/OPEN.md:3322 | S | unassigned |
| 293 | The traceback check in the smoke step reads the app's whole output; a benign logged traceback on Windows would fail it. (from... | docs/roadmap/agent-remaining/OPEN.md:3323 | S | unassigned |
| 294 | The installer's optional packages (owner, 2026-10-07: "there's no indicator for the optional packages install and I cant minimise or close the... | docs/roadmap/agent-remaining/OPEN.md:3324 | M | unassigned |
| 295 | Brief 17 (launchers, splash): agent-remaining/OPEN.md:405 names the rest of Brief 17 as open. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3447 | S | unassigned |
| 296 | INBOX 743, "atlas goes out of the border": not reproduced (figure within 4 px of its svg, no oval frame drawn at this head); recheck the welcome card... | docs/roadmap/agent-remaining/OPEN.md:3509 | S | unassigned |
| 297 | Rule 14: /health stays the launcher's open probe (instance_lock.py, __main__.py read it unauthenticated, and it answers on the LAN); the fields are... | docs/roadmap/agent-remaining/OPEN.md:3524 | M | unassigned |
| 298 | .diff, .patch, .vb and .vbs are not in docview.CODE_SUFFIXES, so a Library import of one is refused (415); a Dockerfile has no suffix at all... | docs/roadmap/agent-remaining/OPEN.md:3536 | M | unassigned |
| 299 | Documents: the status bar shows characters, words and reading time; lines (wc -l) are counted by textCounts but shown nowhere. "find with the same... | docs/roadmap/agent-remaining/OPEN.md:3607 | M | unassigned |
| 300 | 502c138d5: core/netid.py (Linux /proc, macOS route/arp, Windows one PowerShell call with a route print + arp fallback; every command timed; failure... | agent/mergetrain-1011:docs/roadmap/agent-remaining/lansafe-1011.md:12 | M | unassigned |
| 301 | cb46444e0: the gate in lanserve and the launcher, the routes, the held unlock, netbind.describe ordering; real-socket and launcher e2e tests. | agent/mergetrain-1011:docs/roadmap/agent-remaining/lansafe-1011.md:16 | S | unassigned |
| 302 | Update channels (stable/beta/dev): Next: the installers ship now (release.yml), so this is unblocked; api/routes_update.py... | docs/roadmap/BACKLOG.md:1715 | M | unassigned |
| 303 | MCP tool support: Pointer: WORLD_CLASS_PLAN B8 "Extensions" and PLAN.md harness row A7 ("MCP in and out"); the consume half waits... | docs/roadmap/BACKLOG.md:1845 | L | unassigned |
| 304 | Reuse the system Python's packages. Recommendation: offer it, never default it. start.sh line 1070 and start.bat line 602 run... | docs/roadmap/BACKLOG.md:4211 | L | unassigned |
| 305 | Brief 17: launchers, uninstallers and the splash made impressive (Opus): unmarked | docs/roadmap/SESSION_BRIEFS.md:549 | L | unassigned |
| 306 | Brief 40: research and placement (done; docker build, phone repro and parity-row browser checks left in research-1010) | docs/roadmap/SESSION_BRIEFS.md:1315 | S | unassigned |
| 307 | Brief 43: the expert audit and the nine probes (release 0.5 gate) | docs/roadmap/SESSION_BRIEFS.md:1406 | L | unassigned |
| 308 | Release artifact naming: <name>-<version>-<platform>-<arch>.<ext>, one scheme across every installer. INBOX 266 asked for version, platform and... | docs/roadmap/WORLD_CLASS_PLAN.md:1826 | L | unassigned |
| 309 | 0.5.0, "the notebook that thinks": the night shift's review UI, the margin reader (I2), open questions (I3), resurfacing (I4), the web clipper's... | docs/roadmap/WORLD_CLASS_PLAN.md:2435 | S | unassigned |
| 310 | 1.0.0: a stable API (B7), a screen-reader-audited UI, the installer and update path proven on clean Windows machines, and the docs complete. | docs/roadmap/WORLD_CLASS_PLAN.md:2440 | S | unassigned |
| 311 | The owner, 2026-09-23, with the Gemini/Antigravity pass on fix/gemini-fixes-5 (1e63d87, 2c3e16e): "fix and refine the changes attempted by gemini ...... | docs/roadmap/WORLD_CLASS_PLAN.md:2500 | L | unassigned |
| 312 | "Should we integrate it as a docker build and image and make it available as a docker app as well??" Recommendation: a Dockerfile and compose file... | docs/roadmap/WORLD_CLASS_PLAN.md:3105 | M | unassigned |
| 313 | "Does the mcp server work or need to be improved?? I don’t think it has been properly integrated as a feature yet." Recommendation: run the MCP... | docs/roadmap/WORLD_CLASS_PLAN.md:3109 | M | unassigned |
| 314 | "what is this app file installer?? can this app use it and is it free??" Recommendation: answer it in the Brief 40 research with the licence and... | docs/roadmap/WORLD_CLASS_PLAN.md:3113 | M | unassigned |
| 315 | The Windows firewall profile (Public blocks, Private allows) answering the first request and not the next; the launchers add no rule. | docs/roadmap/WORLD_CLASS_PLAN.md:3182 | S | unassigned |
| 316 | Add a Windows Defender Firewall rule at the opt-in (private profile only), or print the one-line netsh command when turning the switch on. | docs/roadmap/WORLD_CLASS_PLAN.md:3211 | S | unassigned |
| 317 | Docker image not built: docker is on PATH but docker info reports no daemon here. docker/Dockerfile and docker/compose.yaml are unbuilt; the first... | docs/roadmap/agent-remaining/packaging-1010.md:3 | M | unassigned |
| 318 | Docker behind a reverse proxy: host_allowed answers 421 for a Host that is a name other than the container's own; a proxy forwarding... | docs/roadmap/agent-remaining/packaging-1010.md:4 | M | unassigned |
| 319 | MCP: no resources (notes) or prompts (skills); startup still loads the embedder (mcp_server.serve, deps.init_app_state); stdio only, so no... | docs/roadmap/agent-remaining/packaging-1010.md:5 | M | unassigned |
| 320 | MCP Settings row (#mcp-config-group, renderMcpSnippet in frontend/js/skills.js) was not opened in a browser; the lints and API test pass, the layout... | docs/roadmap/agent-remaining/packaging-1010.md:6 | S | unassigned |
| 321 | System site-packages: shell launcher only (env variable MEMORYMAP_SYSTEM_SITE_PACKAGES=1, not a --flag, because the flag-order lint requires... | docs/roadmap/agent-remaining/packaging-1010.md:7 | S | unassigned |
| 322 | Section: Phase 11: the phone, done properly (412-line phase; many built marks, status per row unverified) | docs/roadmap/UI_MODERNISATION_PLAN.md:601 | L | unassigned |
| 323 | Section: Section 12: security review items (each names its file) | docs/roadmap/WORLD_CLASS_PLAN.md:917 | M | unassigned |
| 324 | Nav history on a phone: the popup was measured by calling openNavHistoryMenu directly (the status-bar button is not drawn at 390), so its placement... | docs/roadmap/agent-remaining/OPEN.md:1873 | S | unassigned |
| 325 | Sign-in off, not driven: the desktop window's persistent profile, a real second device on the LAN, the prompt card in dark, and whether a restored... | docs/roadmap/agent-remaining/OPEN.md:1939 | S | unassigned |
| 326 | The citation mark's touch box overlaps the lines above and below (a decision to note, not a bug): the ::after box is 44px tall around a 13px glyph... | docs/roadmap/agent-remaining/OPEN.md:2035 | M | unassigned |
| 327 | errors.js at 390 stops on its own second login check (#lock-password reads visible after the unlock); 1440, 1024 and 820 report 0 errors. | docs/roadmap/agent-remaining/OPEN.md:2120 | S | unassigned |
| 328 | Two icon-gap outliers, both judged deliberate: 10 meta chips at 3.6px (.chip.when, .map-chip) against the app's 242 controls at 6.4px, and... | docs/roadmap/agent-remaining/OPEN.md:2194 | M | unassigned |
| 329 | The reminder action token's key is per process (the app has no persisted signing secret): a restart ends open notifications' buttons. | docs/roadmap/agent-remaining/OPEN.md:2340 | S | unassigned |
| 330 | Timeline at 390: the On this day row moves the list down 44 px; a phone may want it folded (#timeline-recall). | docs/roadmap/agent-remaining/OPEN.md:2527 | S | unassigned |
| 331 | deepen72b.js's timeline row at 390 waits for .timeline-rows but the phone keeps the table view, so it times out (deepen72b.js:61). | docs/roadmap/agent-remaining/OPEN.md:2528 | S | unassigned |
| 332 | errors.js at 390 stops at its login: a second fill and click (errors.js:86) race an unlock slower than its fixed 2.5 s wait; reproduced on the base... | docs/roadmap/agent-remaining/OPEN.md:2543 | M | unassigned |
| 333 | companion-r5.md: the toss on a phone (a quick swipe on the companion tosses it) was not tried on a device; test_unlock_throttle_per_client.py failed... | docs/roadmap/agent-remaining/OPEN.md:2791 | M | unassigned |
| 334 | Phone selection menus and the selection bar (documents): iOS and Android draw Cut, Copy and Paste above a selection, where the bar also goes; if a... | docs/roadmap/agent-remaining/OPEN.md:2903 | S | unassigned |
| 335 | docs/CHANGELOG.md, docs/CONTRIBUTING.md and docs/SECURITY.md are mirrors that nothing reads now (the old site fetched them). Keeping or retiring them... | docs/roadmap/agent-remaining/OPEN.md:3325 | S | unassigned |
| 336 | A ring on a control in a body-level fixed sheet that touches the viewport edge (the phone Writing room's draft textarea) is treated as scroll... | docs/roadmap/agent-remaining/OPEN.md:3348 | S | unassigned |
| 337 | The icon-only chat-dock toggles are checked by text content and title only; no keyboard or screen-reader pass was run. The phone (under 600) sheet... | docs/roadmap/agent-remaining/OPEN.md:3364 | M | unassigned |
| 338 | The Focused hero is taller than before: 157px at 900 to 1920 (was 71), 278px at 390 (was 71 to 87). If the owner finds it too tall on a phone, the... | docs/roadmap/agent-remaining/OPEN.md:3370 | M | unassigned |
| 339 | Phone (390, touch): the first frames of a toggle take 50 to 80ms in headless emulation, so the first frame of the height animation can jump about 40%... | docs/roadmap/agent-remaining/OPEN.md:3391 | S | unassigned |
| 340 | Phone: a collapsed row's always-shown buttons sit in the details line's scrolled lane, off the row's right edge (right -87.8px, measured; unchanged... | docs/roadmap/agent-remaining/OPEN.md:3392 | S | unassigned |
| 341 | **Fixed 2026-10-19.** The Timeline's table view (a phone's default) has no mark column, so a meeting reads as a Note there; the feed view shows the meeting mark. (from... | docs/roadmap/agent-remaining/OPEN.md:3407 | S | unassigned |
| 342 | The phone paths through the More sheet: the agent (toggleAgentPalette() leaves the overlay hidden at 390), the Guide, the timeline and reminders were... | docs/roadmap/agent-remaining/OPEN.md:3418 | S | unassigned |
| 343 | The reminders quick-add row at 390 (not visible; the phone compose not driven). (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3419 | S | unassigned |
| 344 | The palette is never shown on a phone (toggleAgentPalette goes to Chat), so its 390px notice is unmeasured by design. (from notice-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3480 | S | unassigned |
| 345 | A notice's go: { settings, focus } scrolls Settings to the control at 1440 (Back up now at y 499 of 900) but not at 390 (y 1527 of 900): the phone... | docs/roadmap/agent-remaining/OPEN.md:3659 | M | unassigned |
| 346 | 889 OCR workspace: stacked columns, 44px targets and no sideways scroll already held at 390 and 320 before this work (ocrphone.js); only the source... | agent/mergetrain-1011:docs/roadmap/agent-remaining/phone2-1011.md:8 | M | unassigned |
| 347 | Text size "Small" puts phone tap targets under 44 px. --target-min: 2.75rem (00-tokens-shell.css:530 and the 820 band) is in rem and the root is 14.5... | agent/mergetrain-1011:docs/roadmap/agent-remaining/scan-1011.md:8 | L | unassigned |
| 348 | Other icon-only rows on the phone with no labels (not touched): the whiteboard toolbar and the selection dock; sweep with touch.js for tooltip-only... | agent/mergetrain-1011:docs/roadmap/agent-remaining/phonegraph-1011.md:9 | S | unassigned |
| 349 | f940fad8d: LAN port refuses a client not on this network (private, shared, link-local, this computer's own addresses, its global IPv6 /64s). | agent/mergetrain-1011:docs/roadmap/agent-remaining/lansafe-1011.md:10 | S | unassigned |
| 350 | The desktop webview (pywebview), the tour on a phone, voice and recordings, OCR, the web clipper (no network), update checking, backups restore... | agent/mergetrain-1011:docs/roadmap/agent-remaining/scan-1011.md:16 | M | unassigned |
| 351 | 1b96f48cf: renderLanAddresses (one renderer, Settings and the receipt), lan-watch.js (Allow/Deny toast and bell), Settings lists and options, the... | agent/mergetrain-1011:docs/roadmap/agent-remaining/lansafe-1011.md:18 | S | unassigned |
| 352 | The phone's lock screen does not retry by itself after Allow: the server holds the request 45 s, then says to press Unlock again. | agent/mergetrain-1011:docs/roadmap/agent-remaining/lansafe-1011.md:44 | S | unassigned |
| 353 | HIGH: a notebook with no password answered every device. After /auth/reset (or a restored backup with no password) the LAN listener stays up until... | agent/secscan-1011:docs/roadmap/agent-remaining/secscan-1011.md:23 | M | unassigned |
| 354 | HIGH: /health said desktop: true to the phone, so the phone wrote exports onto the computer's disk (/files/save, any bytes, any extension) and its... | agent/secscan-1011:docs/roadmap/agent-remaining/secscan-1011.md:24 | M | unassigned |
| 355 | MEDIUM: model and embedding-model downloads (any Ollama name or Hugging Face repo, GBs to disk) and removal from a phone. Host-only. | agent/secscan-1011:docs/roadmap/agent-remaining/secscan-1011.md:26 | S | unassigned |
| 356 | MEDIUM: recovery-key save opened a native Save dialog on the computer from a phone; LAN switch on, certificate regenerate, password-on-open off... | agent/secscan-1011:docs/roadmap/agent-remaining/secscan-1011.md:27 | S | unassigned |
| 357 | LOW: no HSTS on the https port; added (https only, never on loopback). | agent/secscan-1011:docs/roadmap/agent-remaining/secscan-1011.md:28 | S | unassigned |
| 358 | LOW: phone Quit showed "MemoryMap has stopped" when the server had refused; now toasts the refusal. Phone full screen POSTed to the desktop toggle... | agent/secscan-1011:docs/roadmap/agent-remaining/secscan-1011.md:29 | L | unassigned |
| 359 | It works with no network at all. Already true and almost never said. The notebook_stats work in this session is the shape to... | docs/roadmap/BACKLOG.md:3789 | S | unassigned |
| 360 | Library verdicts to carry into Brief 35's stripping: drop networkx (write the 60 lines notebook_stats.py uses), whoosh, pint... | docs/roadmap/BACKLOG.md:4260 | M | unassigned |
| 361 | Live refresh across devices (INBOX 881, the owner 2026-10-11: "what if I make a change on my phone?? does it live update??"). A... | docs/roadmap/BACKLOG.md:4293 | M | unassigned |
| 362 | Briefs 25 to 31 (TIMELINE 1 to 4, CHAT 2 and 3, UI Phase 11 phone, DOCUMENTS 5 to 8, GRAPH 4 part two, MINDMAP 12, SKILLS D): unmarked; phases partly built per the plans | docs/roadmap/SESSION_BRIEFS.md:767 | L | unassigned |
| 363 | The status bar at 320: taken, the first way. Measured 2026-09-12, after the header was made to fit: at 320 x 844 the page still scrolled sideways... | docs/roadmap/UI_MODERNISATION_PLAN.md:886 | L | unassigned |
| 364 | The bottom tab bar exists and is five columns (#phone-tab-dock, 10-responsive.css; dockTabBar, app.js). Measured at 390, 360 and 320: five columns... | docs/roadmap/UI_MODERNISATION_PLAN.md:904 | M | unassigned |
| 365 | The sheets: one recipe, two in place, and the boundary between them is now written down (2026-09-13). openSheet builds a *modal bottom* sheet out of... | docs/roadmap/UI_MODERNISATION_PLAN.md:914 | L | unassigned |
| 366 | Gates. scratchpad/ui-sweeps/phone.js exists (2026-09-13) and holds four of them per tab at 390x844 and 430x932: no horizontal scroll (page and inside... | docs/roadmap/UI_MODERNISATION_PLAN.md:937 | L | unassigned |
| 367 | Download another model takes an Ollama name or a Hugging Face link or hf.co/ name, says what it is before anything downloads (POST /models/inspect... | docs/roadmap/UI_MODERNISATION_PLAN.md:1186 | M | unassigned |
| 368 | Density and rhythm. Cards carry 24px of padding and 17px body text at every width; on a laptop the list reads like a phone app scaled up. | docs/roadmap/WORLD_CLASS_PLAN.md:2383 | S | unassigned |
| 369 | 0.6.0, "many devices": LAN polish for tablets, local-first sync design (B6) made real, extensions (B8). | docs/roadmap/WORLD_CLASS_PLAN.md:2438 | S | unassigned |
| 370 | The owner, 2026-09-23 night, verbatim. "what is left in the world class plan?? can you poke more holes in the application for bugs, security, poor... | docs/roadmap/WORLD_CLASS_PLAN.md:2445 | L | unassigned |
| 371 | The owner, 2026-09-23, verbatim, for after 391: "poke holes in the application as in find bugs, security flaws places where there is unintuitive... | docs/roadmap/WORLD_CLASS_PLAN.md:2533 | L | unassigned |
| 372 | "this didnt work "https://192.168.0.107:8443", on my phone it said the page was unsecure, and then I clicked continue, and it said "safari can't open... | docs/roadmap/WORLD_CLASS_PLAN.md:3088 | M | unassigned |
| 373 | "it says the connection isnt secure and the page cant be reached" / "on brave browser on my phone" Recommendation: the same trust flow as the entry... | docs/roadmap/WORLD_CLASS_PLAN.md:3090 | M | unassigned |
| 374 | "Also I still cant access the application on my phone, the connection just doesn’t go through and there are security issues with a not trustworthy... | docs/roadmap/WORLD_CLASS_PLAN.md:3092 | M | unassigned |
| 375 | "is it possible to customise the domain name on the network accessible url??" Recommendation: an optional local host name for the LAN address (a mDNS... | docs/roadmap/WORLD_CLASS_PLAN.md:3103 | M | unassigned |
| 376 | "I want to deep analyse this repo and see if we can cake a use/replicate/take a lot from it https://github.com/haifengl/smile.git" Recommendation... | docs/roadmap/WORLD_CLASS_PLAN.md:3128 | M | unassigned |
| 377 | TLS 1.2 and 1.3 both negotiate (TLS_AES_256_GCM_SHA384, a 256-bit key); no ALPN, so HTTP/1.1 only. Neither is a plausible cause. | docs/roadmap/WORLD_CLASS_PLAN.md:3146 | S | unassigned |
| 378 | The certificate names the LAN address as an IP SAN and a request to a name it does not carry fails (curl: no alternative certificate subject name... | docs/roadmap/WORLD_CLASS_PLAN.md:3148 | M | unassigned |
| 379 | The leaf is self-issued, 825 days, with SAN, basicConstraints and EKU serverAuth but no keyUsage. Apple limits certificates that chain to a trusted... | docs/roadmap/WORLD_CLASS_PLAN.md:3156 | M | unassigned |
| 380 | The front end uses NDJSON over fetch, not WebSocket or EventSource (capture-ask.js line 2544, settings.js line 1018), so a WebSocket over an... | docs/roadmap/WORLD_CLASS_PLAN.md:3160 | M | unassigned |
| 381 | HostCheckMiddleware lets any numeric Host through, so the rebinding guard is not refusing the phone. | docs/roadmap/WORLD_CLASS_PLAN.md:3166 | S | unassigned |
| 382 | The phone's per-connection trust: Safari opens several parallel connections and a clicked-through exception on a self-signed leaf is per-session, so... | docs/roadmap/WORLD_CLASS_PLAN.md:3172 | M | unassigned |
| 383 | A stale name (above), after a DHCP change, shown the same way as a plain untrusted warning. | docs/roadmap/WORLD_CLASS_PLAN.md:3176 | S | unassigned |
| 384 | AdGuard on the phone: a DNS profile does not touch an IP address, but the AdGuard app's local VPN mode and iOS 14's Local Network permission for... | docs/roadmap/WORLD_CLASS_PLAN.md:3178 | M | unassigned |
| 385 | A local CA, mkcert style, made with cryptography (already a dependency): an EC P-256 CA kept in lan-tls/ (0600), a leaf signed by it for 397 days... | docs/roadmap/WORLD_CLASS_PLAN.md:3186 | S | unassigned |
| 386 | Settings, Other devices, "Trust this notebook on your phone": a QR code to http://<ip>:8000/lan/trust (a plain-http route that serves only the public... | docs/roadmap/WORLD_CLASS_PLAN.md:3192 | M | unassigned |
| 387 | A plain-http option for the home network, off by default, with the password warning in one sentence ("anyone on this Wi-Fi can read it") and the... | docs/roadmap/WORLD_CLASS_PLAN.md:3201 | M | unassigned |
| 388 | A diagnostics line in Settings, Network: the addresses now, the names the certificate carries (green when every address is covered, amber with... | docs/roadmap/WORLD_CLASS_PLAN.md:3206 | M | unassigned |
| 389 | (Odysseus, fourth read 2026-10-10) | docs/roadmap/WORLD_CLASS_PLAN.md:3215 | S | unassigned |
| 390 | Staged gate: ruff check . fails on vendored src/memorymap/vendor/whoosh (1,140 findings, same on the base checkout); test_plan_hygiene (vendor... | docs/roadmap/agent-remaining/codemap-1010.md:9 | M | unassigned |
| 391 | UML and "network" libraries. Upstream has no UML stencil library (UML is drawn by Shapes.js classes); networks.xml stood in for network. The... | docs/roadmap/agent-remaining/drawio-1010.md:38 | S | unassigned |
| 392 | Cold boot excludes the service worker and a warm HTTP cache; no phone-width run. | docs/roadmap/agent-remaining/measure-1010.md:10 | S | unassigned |
| 393 | Triage-agent lints still red on this branch: README tool count (67) and the networkx conflict marker. | docs/roadmap/agent-remaining/packaging-1010.md:8 | S | unassigned |
| 394 | bash scripts/gate.sh --staged fails here on lints that predate this work: ruff over src/memorymap/vendor/ (1140 errors, whoosh), the networkx... | docs/roadmap/agent-remaining/proofing-1010.md:6 | S | unassigned |
| 395 | Road to 1.0: 0.5 Reliable, 0.6 Engine, 0.7 Surfaces, 0.8 Design, 0.9 Public beta, 1.0 exit criteria (docs/ROADMAP.md) | docs/ROADMAP.md:171 | L | unassigned |
| 396 | Section: Phase 5: the composer after INBOX 725 (open) | docs/roadmap/CHAT_PLAN.md:385 | L | unassigned |
| 397 | Section: Phase 6: the deterministic engine, steps 1 to 10, measured gates (Brief 39; spec39 lists untested decisions) | docs/roadmap/CHAT_PLAN.md:405 | L | unassigned |
| 398 | Section: The deterministic foundation F0 to F5 phases with gates and its Not verified list | docs/roadmap/CHAT_PLAN.md:1565 | L | unassigned |
| 399 | Attach: at 390 #attach-image reads a 999px radius while #attach-note reads 4.8px in the chat composer row (the owner's 841 asked for one corner; only... | docs/roadmap/agent-remaining/OPEN.md:1870 | M | unassigned |
| 400 | The guide topic ask-chat is at 1916 of 1919 characters (tests/test_help_controls.py), so Agent-with-no-model could not be named in the Guide without... | docs/roadmap/agent-remaining/OPEN.md:1871 | M | unassigned |
| 401 | Ask's answer object was measured on the offline branch only. The sweep runs against a server with no model, so sentences was empty in every... | docs/roadmap/agent-remaining/OPEN.md:2042 | M | unassigned |
| 402 | The evals marker and its fixture set (Brief 13's done-when). At least 80% of the built-in skills complete with zero invalid tool calls under... | docs/roadmap/agent-remaining/OPEN.md:2061 | L | unassigned |
| 403 | Not engine-readable, left out of the fixture: "corder" (corner; a one-letter swap in a six-letter word is refused on purpose, it reads "coder")... | docs/roadmap/agent-remaining/OPEN.md:2212 | S | unassigned |
| 404 | The Guide's no-model system answer (help_chat.system_answer) does not say "I took that to mean"; only composer.compose answers do. | docs/roadmap/agent-remaining/OPEN.md:2233 | S | unassigned |
| 405 | A real word missing from both word lists can be mis-repaired; add it to common_words.py and LEFT_ALONE. | docs/roadmap/agent-remaining/OPEN.md:2234 | S | unassigned |
| 406 | The asking-word nearest rule turns an all-caps token ("NASA") into "has" unless the whole text is capitals. | docs/roadmap/agent-remaining/OPEN.md:2235 | S | unassigned |
| 407 | Readings guessed: "liks" (like), "mut" (must), "odf" (of), "ro" (or). Brief 90 is standing: each new prompt's typos join owner_typos.json. | docs/roadmap/agent-remaining/OPEN.md:2236 | S | unassigned |
| 408 | **Fixed 2026-10-19.** Mechanical: the header's six buttons lose 0.5px of their ring at the window top; the Library active sub-tab's border is cut 2.3px at 390; the chat... | docs/roadmap/agent-remaining/OPEN.md:2275 | S | unassigned |
| 409 | "What do I know about X" still quotes one sentence unless its notes are tagged with the subject (the 725 and 741 evals pin it). | docs/roadmap/agent-remaining/OPEN.md:2440 | S | unassigned |
| 410 | Single-note answers still end with "[your note, date]"; some next-question chips repeat the subject; an overview over more than 24 notes should say... | docs/roadmap/agent-remaining/OPEN.md:2441 | S | unassigned |
| 411 | Send stays off the undo bar (Ctrl+Z in the composer is text undo); recommended as is. | docs/roadmap/agent-remaining/OPEN.md:2448 | S | unassigned |
| 412 | Needle with the server up but no model leaves Agent greyed: tools_engine is reported only when the server is down (routes_chat.py ~2534). | docs/roadmap/agent-remaining/OPEN.md:2472 | L | unassigned |
| 413 | The document menu's "Translate this passage..." still hands the passage to chat, not the offline engine. | docs/roadmap/agent-remaining/OPEN.md:2491 | L | unassigned |
| 414 | A monthly repeat from the 31st lands on the 28th in February and stays there (recognise.py _add_months). | docs/roadmap/agent-remaining/OPEN.md:2530 | S | unassigned |
| 415 | Statistics row 4 (Brief 37): the page's "not used lately" list (86 on the fixture) is the feed the weekly offer wants; not wired. | docs/roadmap/agent-remaining/OPEN.md:2564 | S | unassigned |
| 416 | "new ways to do and output info" (INBOX 758): the Ask box ignores the chart event (capture-ask.js Ask handlers, ~3065); only the Chat tab draws it... | docs/roadmap/agent-remaining/OPEN.md:2608 | S | unassigned |
| 417 | The Guide's "how do I set a reminder" first line is the topic's first matching sentence ("The Reminders tab groups items..."), not the step that sets... | docs/roadmap/agent-remaining/OPEN.md:2611 | M | unassigned |
| 418 | Guide rows 4 to 6 (CHAT_PLAN "The Guide" table): trust-surface topics, the weekly unused feature, typos through the word list (VC15). | docs/roadmap/agent-remaining/OPEN.md:2613 | S | unassigned |
| 419 | WORLD_CLASS_PLAN 9's dev-only llama.cpp runner is the blocker behind four open items: the evals marker, Skills Phase D's central claim, the retrieval... | docs/roadmap/agent-remaining/OPEN.md:2723 | L | unassigned |
| 420 | A check that cannot tell "nothing matched" from "labels are broken" cries wolf on every small fixture. Two of graph2.js's five failures were exactly... | docs/roadmap/agent-remaining/OPEN.md:2734 | S | unassigned |
| 421 | IME composition inside the editor engine, and the fallback path reached by a genuinely blocked request rather than by setting docCmBroken by hand.... | docs/roadmap/agent-remaining/OPEN.md:3241 | L | unassigned |
| 422 | Real-browser text metrics beyond Chromium. The wrap sweep measured 420 to 2200px at the app's own 95% --zoom; a different engine could shift an exact... | docs/roadmap/agent-remaining/OPEN.md:3264 | L | unassigned |
| 423 | With a model, the composer shows "Filed under Work (100% sure)" for a small model's pick (a dentist appointment); the certainty shown for a small... | docs/roadmap/agent-remaining/OPEN.md:3304 | S | unassigned |
| 424 | Found: one_line for "when is the harbor launch?" quotes the Q4 roadmap rather than the dated sentence; the compose grounding rows lack it. (from... | docs/roadmap/agent-remaining/OPEN.md:3349 | S | unassigned |
| 425 | The eval numbers for the whole voice track (before and after) were not reported: run tests/_composer_eval.py and record them. (from... | docs/roadmap/agent-remaining/OPEN.md:3351 | S | unassigned |
| 426 | Browser check of Ask and Chat with no model at 1440 and 390, light and dark: the "Did you mean" chip and the clarifying question. The sweep... | docs/roadmap/agent-remaining/OPEN.md:3352 | M | unassigned |
| 427 | The noisy-question set's coverage (owner: "any and ALL typos ... all slang"): what is still missed, from the eval. (from composer-voice-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3353 | S | unassigned |
| 428 | Professional variants for the next-question chips and the citation phrases (mention_*, lists, echo), and other languages' wrappers. (from... | docs/roadmap/agent-remaining/OPEN.md:3354 | S | unassigned |
| 429 | The Settings voice row was checked in Chromium on the light theme only at 1440 and 390; dark not run. (from composer-voice-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3355 | S | unassigned |
| 430 | **No change needed 2026-10-19:** the scope is only ever set by the Questions view's own Ask button, in the same init that wires Clear, so Clear is always wired while the scope shows. Ask's "Ask all notes" (#ask-scope-clear) is wired only once the Questions view has been opened, so the scope is only set from there (pre-existing).... | docs/roadmap/agent-remaining/OPEN.md:3357 | S | unassigned |
| 431 | At 390 the Ask head's model picker sits on its own short line (224px of 330), pre-existing. (from composer688-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3358 | S | unassigned |
| 432 | Clicking an Ask chip was not driven: the sweep's button selector missed the chip element. (from composer725-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3360 | S | unassigned |
| 433 | Link reasons from the composer (owner: "can the composer be user to write better link reasons other than just similar in meaning??"): not started.... | docs/roadmap/agent-remaining/OPEN.md:3361 | M | unassigned |
| 434 | ocrflow.js still reads #ocr-engine as a line and clicks #ocr-more; it was not re-run, and its engine checks may need the popover opened first. The... | docs/roadmap/agent-remaining/OPEN.md:3377 | L | unassigned |
| 435 | The fixture is 96 notes (the seed ran twice), not 48. (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3426 | S | unassigned |
| 436 | Ask cannot show a relevant map as a map. Decision taken: retrieval is notes only (a map's entry text is its title, so it grounds nothing). Owner's... | docs/roadmap/agent-remaining/OPEN.md:3430 | M | unassigned |
| 437 | Brief 13 (verifier): agent-remaining/OPEN.md:189 still names Brief 13's evals marker and fixture set as open. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3444 | S | unassigned |
| 438 | The lexicon (decision 7) costs one note in the online simulation (0.521 to 0.510, scratchpad/filing-tools/online.py); the fixture has no category... | docs/roadmap/agent-remaining/OPEN.md:3468 | S | unassigned |
| 439 | Decision 9 (the 30 context rules, 50 acceptance fixtures): not started; taxonomy.context_rules() and... | docs/roadmap/agent-remaining/OPEN.md:3469 | S | unassigned |
| 440 | Blind panel (decision 40): the owner's rating against the 1 to 3B model; not runnable by an agent. | docs/roadmap/agent-remaining/OPEN.md:3486 | S | unassigned |
| 441 | P10 days until a note's date ("how many days until the dentist"): utilities.until_subject (src/memorymap/ai/utilities.py:313) finds the subject... | docs/roadmap/agent-remaining/OPEN.md:3487 | S | unassigned |
| 442 | P12 a list filtered by category or tag ("list my work notes"): composer._filtered (src/memorymap/ai/composer.py:3155) filters by tag and source kind... | docs/roadmap/agent-remaining/OPEN.md:3489 | S | unassigned |
| 443 | P15 a lead-in chosen after the parts: the compare opener is still chosen first. | docs/roadmap/agent-remaining/OPEN.md:3491 | S | unassigned |
| 444 | P16 a note's open checklist items for "what is still open on X". | docs/roadmap/agent-remaining/OPEN.md:3492 | S | unassigned |
| 445 | Captions: the composer reads them as note content; keyword search finds them as the picture's own row (src/memorymap/search/index.py:793), not as its... | docs/roadmap/agent-remaining/OPEN.md:3495 | S | unassigned |
| 446 | Dates like 3/4 read day first (when._date_phrase, src/memorymap/ai/when.py:420); no locale order. | docs/roadmap/agent-remaining/OPEN.md:3496 | S | unassigned |
| 447 | Not seen in a browser: the web sources list with a real search engine; contrast sweeps over .said and the act card. | docs/roadmap/agent-remaining/OPEN.md:3497 | L | unassigned |
| 448 | Polarity in the fact layer: dropped by decision 30's own condition (no feature uses it). | docs/roadmap/agent-remaining/OPEN.md:3498 | S | unassigned |
| 449 | INBOX 694 part 1, "the bottom of these pills gets cut off": not reproduced at DPR 1 (Ask/Agent and Settings .seg: each segment 1 px inside the 32 px... | docs/roadmap/agent-remaining/OPEN.md:3506 | S | unassigned |
| 450 | INBOX 744 (b) and (c), "it didn mention other matching records": composer and grounding work (composer*.py, renderAnswerGrounding), off this agent's... | docs/roadmap/agent-remaining/OPEN.md:3510 | S | unassigned |
| 451 | Start SearXNG "takes a while": not reproduced (status 21 to 101 ms, chat.js:1031 setWebSearxngRunning); a search that failed should retry by itself... | docs/roadmap/agent-remaining/OPEN.md:3511 | L | unassigned |
| 452 | Citation hover, the composer and captions in retrieval (Brief 39) and the density items (Brief 41) are owned elsewhere. | docs/roadmap/agent-remaining/OPEN.md:3513 | S | unassigned |
| 453 | ai/composer.py _DATE_CUE (about line 380) and its second date pattern (about 933) still compile date words; replace with recognise.recognise(...)... | docs/roadmap/agent-remaining/OPEN.md:3568 | M | unassigned |
| 454 | entry/timewords.py keeps its own weekday and number tables (the plan's second allowed reader, for stored precision). Brief 68 decides whether find... | docs/roadmap/agent-remaining/OPEN.md:3569 | S | unassigned |
| 455 | ai/factgraph.py _QUANTITY still reads counts of things ("3 sets", "5 people"); a "count" kind (number plus plural noun) in recognise would let it... | docs/roadmap/agent-remaining/OPEN.md:3570 | S | unassigned |
| 456 | search/query.py before:/after: stay ISO only (test_an_unreadable_date_invents_nothing holds it); before:tuesday is one call to recognise.span if the... | docs/roadmap/agent-remaining/OPEN.md:3571 | S | unassigned |
| 457 | "last week" is the last seven days in search and the previous Monday to Sunday in recognise; both written down, the Reading says the search's window.... | docs/roadmap/agent-remaining/OPEN.md:3572 | S | unassigned |
| 458 | when.resolve("in march"), "march", "q4" give the next one at 09:00 (a reminder is never in the past); the past one comes from when.window and... | docs/roadmap/agent-remaining/OPEN.md:3573 | S | unassigned |
| 459 | "on my birthday" reads only with a stored birthday (context["birthday"], birthday= on /read); no setting holds one yet. [f1-1010] | docs/roadmap/agent-remaining/OPEN.md:3574 | S | unassigned |
| 460 | Quick add is 56 of 60 on tests/fixtures/composer/quickadd_1010.json measured before F1's four fixes landed; re-run scratchpad/ui-sweeps/quickadd.js... | docs/roadmap/agent-remaining/OPEN.md:3576 | S | unassigned |
| 461 | A reminder with no time said is guessed as tomorrow at 9, shown "(no time was said)" (commands.py, when.resolve("tomorrow")); decisions 48 and 50 say... | docs/roadmap/agent-remaining/OPEN.md:3587 | M | unassigned |
| 462 | Ask draws no Confirm and Not right: capture-ask.js keeps onGrounding's insights unread though the route sends them (decision 60 lists chat, Tidy and... | docs/roadmap/agent-remaining/OPEN.md:3588 | S | unassigned |
| 463 | tag: with words still filters after the keyword pass's 200 candidates (engine.search, the wanted_tags block), so a common word plus a rare tag can... | docs/roadmap/agent-remaining/OPEN.md:3597 | L | unassigned |
| 465 | Note editor: offers on the Edit form are wired (note-edit-panels.js after li.append(surface, ...)) but measured only on the Capture composer; the... | docs/roadmap/agent-remaining/OPEN.md:3604 | M | unassigned |
| 466 | Filters: "last week" is the last seven days here (the search's meaning) and the Monday to Sunday week in recognise; F1's owner decision row still... | docs/roadmap/agent-remaining/OPEN.md:3610 | S | unassigned |
| 467 | Import: people and places are named in the summary only; they are not written as tags or entities (the save's own extraction runs as before).... | docs/roadmap/agent-remaining/OPEN.md:3612 | M | unassigned |
| 468 | Library boxes (Library filter, graph filter) are not on the meaning layer: they search notes through /read/filter and the search engine, whose... | agent/mergetrain-1011:docs/roadmap/agent-remaining/meaning94-1011.md:6 | L | unassigned |
| 469 | Autocorrect's table takes Brief 90's owner typos by hand (73 pairs read from agent/typos90*-1011's owner_typos.json, 47 kept: the rest are real... | agent/mergetrain-1011:docs/roadmap/agent-remaining/meaning94-1011.md:8 | S | unassigned |
| 470 | 856: the owner's exact element ("an Ask question link") was not reproduced. scratchpad/ui-sweeps/hoverradius.js measured 0 square hover grounds... | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:14 | M | unassigned |
| 471 | Re-ranking with a small cross-encoder over the top-20, behind a setting. Next: nothing in src/ re-ranks (checked 2026-10-05); the... | docs/roadmap/BACKLOG.md:866 | L | unassigned |
| 472 | An eval/benchmark harness tied to changes here. Pointer: WORLD_CLASS_PLAN B5 "Evals as fixtures" and I8; tests/eval/, pytest -m... | docs/roadmap/BACKLOG.md:878 | L | unassigned |
| 473 | Re-rank the top N with the utility model. Next: same item as section 11's "Re-ranking" (nothing re-ranks in src/); the seam is... | docs/roadmap/BACKLOG.md:2404 | L | unassigned |
| 474 | Selected, not always-on. Attached explicitly in the composer or the document editor, and *offered* by the same deterministic... | docs/roadmap/BACKLOG.md:2525 | M | unassigned |
| 475 | Every Mermaid kind renders where Markdown renders: documents, chat, Ask answers, note previews and the print view: flowchart... | docs/roadmap/BACKLOG.md:2597 | M | unassigned |
| 476 | The AI: steps 5 and 6 above use the full renderer for the preview; the agent gets a render_mermaid check tool so it can see its... | docs/roadmap/BACKLOG.md:2611 | L | unassigned |
| 477 | §88.4 items 1, 2 (ROADMAP.md) are the reason "jump between notes" is already partly real: graph_expansion() walks linked... | docs/roadmap/BACKLOG.md:2847 | M | unassigned |
| 478 | Chasing Notion's block editor. Documents has four views and a real toolbar. Deciding *whether the note composer converges with... | docs/roadmap/BACKLOG.md:3892 | S | unassigned |
| 479 | The owner, 2026-09-21, verbatim: "in the ask subtab in notes, make sure there are appropriate gaps between uploaded files and attachments and the... | docs/roadmap/CHAT_PLAN.md:675 | S | unassigned |
| 480 | The owner, 2026-09-21, verbatim: "there's no generating animation while the model is thinking and streaming in the ask tab either." | docs/roadmap/CHAT_PLAN.md:679 | S | unassigned |
| 481 | The owner, 2026-09-21, verbatim: "can the notes in the matching records that appear in the ask tab be numbered accordingly to match the inline... | docs/roadmap/CHAT_PLAN.md:682 | S | unassigned |
| 482 | The owner, 2026-09-21, verbatim: "fix the ui of this sources button in the ask tab." | docs/roadmap/CHAT_PLAN.md:686 | S | unassigned |
| 483 | The composer assists the model, never replaces it: when a model is running it is the chat bot; the composer supplies the grounded material (the... | docs/roadmap/CHAT_PLAN.md:757 | M | unassigned |
| 484 | The composer writes for the model and the agent, not only for the person (the owner, 2026-10-06, after reading one of this harness's own templated... | docs/roadmap/CHAT_PLAN.md:775 | L | unassigned |
| 485 | A notebook that reads as written for you (the owner, 2026-10-06, verbatim: "the composer could even be used to customise notifications, make the... | docs/roadmap/CHAT_PLAN.md:794 | M | unassigned |
| 486 | No answer is said plainly. "Nothing here says that. The closest is X", plus a suggested question the person could answer with a note. | docs/roadmap/CHAT_PLAN.md:821 | S | unassigned |
| 487 | The bar is all four, each measured: a blind test of composer answers against a 1 to 3B local model on the person's own notes; zero wrong facts, every... | docs/roadmap/CHAT_PLAN.md:823 | M | unassigned |
| 488 | Notes are a mix: the eval weights short jottings (rewrites, joining) and long writing (summaries, choosing the sentence) equally. | docs/roadmap/CHAT_PLAN.md:832 | L | unassigned |
| 489 | "the "start searxng" button doesnt appear for a while" Recommendation: show the SearXNG start control as soon as the web engine is found down, not... | docs/roadmap/CHAT_PLAN.md:851 | L | unassigned |
| 490 | "I pressed the "ask about this" button and it put it in the chat but I was on "ask" mode, shouldnt it have been auto put on "agent"??"... | docs/roadmap/CHAT_PLAN.md:855 | M | unassigned |
| 491 | "I tried to ask for more info from the retrieved website in the previous prompt and it just straight up ignored me and started talking about my... | docs/roadmap/CHAT_PLAN.md:859 | M | unassigned |
| 492 | "not every chat response needs to be related to notes if it is othe rthings about the application." Recommendation: questions about the app are... | docs/roadmap/CHAT_PLAN.md:863 | L | unassigned |
| 493 | "a whitebaord showed as a note in the notes ask subtab matching records column" Recommendation: each match carries its kind (board, map, note... | docs/roadmap/CHAT_PLAN.md:867 | S | unassigned |
| 494 | "I pressed show them, but it just navigated me to the Ask subtab on the notes tab as that was what I was just on in the notes tab and not to the "you... | docs/roadmap/CHAT_PLAN.md:875 | M | unassigned |
| 495 | "Note captions arent counted as note content??" Recommendation: captions join the retrieval text and the fact layer, with a fixture that a... | docs/roadmap/CHAT_PLAN.md:879 | S | unassigned |
| 496 | "I think a lot of composer responses start with "ah,"??" Recommendation: the opener set loses the repeated "ah," and is checked by openers_distinct... | docs/roadmap/CHAT_PLAN.md:885 | M | unassigned |
| 497 | "The composer is shit and I don’t like it, it needs soooo much improvement" / "Still ass composer" Recommendation: this is the composer quality bar... | docs/roadmap/CHAT_PLAN.md:887 | M | unassigned |
| 498 | "There's no way to clear your ask history" Recommendation: add clear-all to the Ask history, with the same control as the destination history. Also... | docs/roadmap/CHAT_PLAN.md:891 | S | unassigned |
| 499 | "Do plan and web search work with the composer?? if not we should disable the plan button and if the user asks the composer to search the web, it can... | docs/roadmap/CHAT_PLAN.md:893 | M | unassigned |
| 500 | "Composer chat messages in the chat and other interfaces should say if the composer or a specific ai model generated it" Recommendation: every... | docs/roadmap/CHAT_PLAN.md:898 | S | unassigned |
| 501 | "Composer responses just appear, I think there should be an animation or smooth transition." Recommendation: a short fade-in with a reduced-motion... | docs/roadmap/CHAT_PLAN.md:900 | M | unassigned |
| 502 | "Ask subtab responses need to have better hierarchy with their sentence connectors." Recommendation: headings, paragraph breaks and connectors are... | docs/roadmap/CHAT_PLAN.md:902 | M | unassigned |
| 503 | "It just uses arrows to go between key sentences and doesn’t join or smoothly write it out at all" Recommendation: the realiser joins key sentences... | docs/roadmap/CHAT_PLAN.md:904 | M | unassigned |
| 504 | "Also the composer should probably use better md rendering and structuring, quotation marks, as well as alter personal words used in notes like "my"... | docs/roadmap/CHAT_PLAN.md:906 | M | unassigned |
| 505 | "Also the composer should note timewords so it can be like, last Friday you did this… etc" Recommendation: time words in the question and the notes... | docs/roadmap/CHAT_PLAN.md:908 | M | unassigned |
| 506 | "I want the composer to be more like a chatbot and not just somenthing that reads out my notes,as I can clearly see them in the right column"... | docs/roadmap/CHAT_PLAN.md:910 | M | unassigned |
| 507 | "also when I use the composer and press "ask this question again" to get a new ai response, the composer doesnt change it up. I want the composer to... | docs/roadmap/CHAT_PLAN.md:912 | M | unassigned |
| 508 | "the composer should have more insights, some social and conversational aspects, more response variation. more stuff than just lkisting my notes back... | docs/roadmap/CHAT_PLAN.md:914 | L | unassigned |
| 509 | "t needs more social and world and word understanding, needs to understand mroe typos, needs better and mroe verything" Recommendation: extend the... | docs/roadmap/CHAT_PLAN.md:916 | S | unassigned |
| 510 | "this is confusing?? I want a better chatbot. is there any more magic we can do?" Recommendation: the bubble explains which engine answered and what... | docs/roadmap/CHAT_PLAN.md:918 | L | unassigned |
| 511 | "Composer doesn’t know it is atlas?? Should the composer be distinct from atlas??" Recommendation: one voice, named Atlas, with the composer as its... | docs/roadmap/CHAT_PLAN.md:920 | L | unassigned |
| 512 | "sounds good. but only if the suer has web search and the tools enabled." (the owner's feedback in the Gemini thread, on the web-aware composer)... | docs/roadmap/CHAT_PLAN.md:922 | M | unassigned |
| 513 | "I just want it to do its job, and I dont want to change the ai, just improve and fix the deterministic composer." (the owner's feedback in the... | docs/roadmap/CHAT_PLAN.md:924 | M | unassigned |
| 514 | "I don’t like the genz version, remove It and expand the composer more. It needs a lot of fixing, expanding, and refining." Recommendation: remove... | docs/roadmap/CHAT_PLAN.md:926 | M | unassigned |
| 515 | "there should be a retry button for failed web searches and/or a button to auto retry when searxng or another engine is available." Recommendation: a... | docs/roadmap/CHAT_PLAN.md:931 | L | unassigned |
| 516 | "I want the composer to be more integrated, have more abilities, utilities, functions, and more." Recommendation: the composer's tool list is the... | docs/roadmap/CHAT_PLAN.md:942 | L | unassigned |
| 517 | "could it have insights?? like with my note about hitting some golf balls after work could imply I may enjoy playing golf or have it as a hobby??... | docs/roadmap/CHAT_PLAN.md:944 | L | unassigned |
| 518 | "can you improve on and expand it further?? cover any flaws, optimise, enhance. impress me." Recommendation: this is the composer's brief at large... | docs/roadmap/CHAT_PLAN.md:946 | M | unassigned |
| 519 | 744 (b) and (c), the unquoted sources and the alarm notice. "it didn mention other matching records i dont think". (b) the composer names the sources... | docs/roadmap/CHAT_PLAN.md:1758 | M | unassigned |
| 520 | INBOX 725 composer: make answers feel like a chatbot (CHAT_PLAN Phase 5 and 6, Briefs 39, 65 to 68) | docs/roadmap/INBOX.md:48 | L | unassigned |
| 521 | INBOX 730 composer files new notes by meaning, keyword and embeddings: held-out accuracy and a one-line explanation per filing (Brief 39b) | docs/roadmap/INBOX.md:57 | M | unassigned |
| 522 | INBOX 741 composer writing quality: speak the content directly with the citation as a marker (CHAT_PLAN Phase 6, Brief 39 realiser) | docs/roadmap/INBOX.md:90 | M | unassigned |
| 523 | INBOX 810 personas row actions styled like the shortcuts Change button; What it learned checks context (joke notes); composer as the app's Siri (maths, timezones, web panel, ghost text, audit the learned store) | docs/roadmap/INBOX.md:199 | L | unassigned |
| 524 | INBOX 812 Ask: answer reads like notes not prose; three citation marks per line; sources shown three times; empty badges while loading; Atlas over the answer | docs/roadmap/INBOX.md:234 | L | unassigned |
| 525 | INBOX placed log: INBOX 899 (composer and agents pull from time words) sent to atlas; 900 folded into 896; 901 (show more and less awkward on wide panes) placed | docs/roadmap/INBOX.md:274 | S | unassigned |
| 526 | INBOX placed log: INBOX 867 to 870 placed as Briefs 102, 103, 104 and a composer opening/joining row | docs/roadmap/INBOX.md:281 | S | unassigned |
| 527 | Briefs 35 to 38 (Gemini triage, whiteboard and mind map, Chat/Ask/first run bugs, graph topics and note properties): unmarked; triage built (triage-1010) | docs/roadmap/SESSION_BRIEFS.md:1247 | L | unassigned |
| 528 | One new section, searchindex ("Search and index"): the search engine, the search index and the search relevance floor, which were in Models (two) and... | docs/roadmap/UI_MODERNISATION_PLAN.md:1144 | L | unassigned |
| 529 | INBOX 761, mind maps listed as notes. The Ask results show a mind map as an Uncategorised note card; check every reader of notes (Ask, Notes, search... | docs/roadmap/UI_MODERNISATION_PLAN.md:1239 | M | unassigned |
| 530 | "very messy" Recommendation: the owner has not named the surface; ask for the screen when the next session starts, and meanwhile run the Brief 41... | docs/roadmap/UI_MODERNISATION_PLAN.md:1266 | S | unassigned |
| 531 | "Also can things still work with all the similarity stuff for the composer and filing and other stuff if sentence-transformers isnt installed??"... | docs/roadmap/WORLD_CLASS_PLAN.md:3096 | M | unassigned |
| 532 | Section 0 finding 1 is unfixed: Gemini-branch utilities are discarded by if not out.rows in ai/composer.py (~2706 to 2795). Owner: "I want the... | docs/roadmap/agent-remaining/assistant-1010.md:6 | M | unassigned |
| 533 | Finding 2 unfixed: the translate rule at ai/composer.py:292 ends in to\s+([a-zA-Z]+)\b and swallows "what do I need to buy", "how to cook rice"... | docs/roadmap/agent-remaining/assistant-1010.md:7 | S | unassigned |
| 534 | Finding 3 unfixed: "summarise my gym notes" raises UnboundLocalError on sides (ai/composer.py ~2795). | docs/roadmap/agent-remaining/assistant-1010.md:8 | S | unassigned |
| 535 | when.resolve("last friday") returns the next Friday (ai/when.py resolve); recall must use entry/timewords.find, which is right; "since March", "the... | docs/roadmap/agent-remaining/assistant-1010.md:9 | S | unassigned |
| 536 | None of the 16 eval fixtures in section 4 exist; the five in decision 40 and the eight proposed ones need their rows written (645 rows), and the... | docs/roadmap/agent-remaining/assistant-1010.md:11 | S | unassigned |
| 537 | Sources whose pages did not state a mechanism, to read from their repositories if the detail matters: Mycroft Adapt's confidence and one_of and... | docs/roadmap/agent-remaining/assistant-1010.md:14 | S | unassigned |
| 538 | Found, not fixed: ai/tool_summary.py is named by commands.py on origin/wip/composer-acts and does not exist on this branch; entry.query entity: finds... | docs/roadmap/agent-remaining/assistant-1010.md:16 | M | unassigned |
| 539 | engine-probe-1010: P1 to P16 probe bugs (word-boundary match, empty social answers, route order, count over retrieval); re-run the probe to see which... | docs/roadmap/agent-remaining/engine-probe-1010.md:7 | M | unassigned |
| 540 | Search latency of the engine alone (without HTTP and background work) is not isolated; GET /search p50 1.8 to 5.0 s is the loaded figure. A trivial... | docs/roadmap/agent-remaining/measure-1010.md:4 | L | unassigned |
| 541 | Decision 34: lead_in_repeats and openers_distinct over a 20-turn session need the eval fixtures (decision 40). | docs/roadmap/agent-remaining/spec39-1010.md:7 | S | unassigned |
| 542 | _stem turns "news" into "new", which its own comment says it must not (src/memorymap/ai/composer.py:453); found writing the stemmer test, not changed. | docs/roadmap/agent-remaining/triage-1010.md:25 | S | unassigned |
| 543 | intent.py's _NOTE_WORDS gained "think", "plan", "idea" and more on the Gemini branch (src/memorymap/ai/intent.py:65), so "I think so" routes to the... | docs/roadmap/agent-remaining/triage-1010.md:30 | S | unassigned |
| 544 | Section: Phase D: recovery (Brief 31) | docs/roadmap/AGENT_SKILLS_REFORM.md:104 | M | unassigned |
| 545 | Section: Does the MCP server work: resources, prompts, ask_user and make_plan to a bare client | docs/roadmap/AGENT_SKILLS_REFORM.md:345 | M | unassigned |
| 546 | Section: Phase 4: skills that finish (Brief 13) | docs/roadmap/CHAT_PLAN.md:365 | M | unassigned |
| 547 | Section: Section 15: inventions I1 to I9 (night shift, margin reader, open questions, resurfacing, time travel, evidence cards, corrections loop, model bench, what it learned) | docs/roadmap/WORLD_CLASS_PLAN.md:1085 | L | unassigned |
| 548 | SKILLS Phase D: no model ran any of it. The fake transport answers every step, so "a rewritten step fixes a run a 3B model stalled on" is the claim... | docs/roadmap/agent-remaining/OPEN.md:2055 | M | unassigned |
| 549 | The follow-up chips were stubbed at the route in the sweep, because /chat/followups answers [] with no model. What is measured is the request a chip... | docs/roadmap/agent-remaining/OPEN.md:2071 | M | unassigned |
| 550 | #chat-results's second half is the only .panel-head with no actions. The next head that wants a control beside its title should take family 8 rather... | docs/roadmap/agent-remaining/OPEN.md:2200 | S | unassigned |
| 551 | The Guide's no-model system answer still prints no "I took that to mean". | docs/roadmap/agent-remaining/OPEN.md:2213 | S | unassigned |
| 552 | The Library's documents, boards, images, bookmarks, recordings and skills boxes suggest recents only, not their own titles. | docs/roadmap/agent-remaining/OPEN.md:2225 | S | unassigned |
| 553 | The Guide, drafting and document review get a ledger run but no narrated lines; chat and agent turns are never announced. | docs/roadmap/agent-remaining/OPEN.md:2243 | S | unassigned |
| 554 | Row actions (rowActions) not yet in meetings, the suggestions inbox, the tag manager; "Kinds: all" triggers and the chat strip's pill toggles a... | docs/roadmap/agent-remaining/OPEN.md:2251 | S | unassigned |
| 555 | Open: a country with several time zones names one ("the time in Australia" says Sydney's). | docs/roadmap/agent-remaining/OPEN.md:2286 | S | unassigned |
| 556 | Open: the user's own bubble shows a trailing backslash as typed. | docs/roadmap/agent-remaining/OPEN.md:2288 | S | unassigned |
| 557 | A held-back skill is still runnable through the agent's run_skill tool; the label is only in the picker and Settings. | docs/roadmap/agent-remaining/OPEN.md:2315 | S | unassigned |
| 558 | Import replaces skills, personas and templates whole (no merge); the desktop save path for Export settings not driven. | docs/roadmap/agent-remaining/OPEN.md:2323 | S | unassigned |
| 559 | The Guide topics board-library and whiteboard-controls sit at 1,918 of 1,920 characters: the next board help line needs a split topic. | docs/roadmap/agent-remaining/OPEN.md:2381 | S | unassigned |
| 560 | Tab-level Guide topics ring the tab's main control, not each topic's own control. | docs/roadmap/agent-remaining/OPEN.md:2449 | S | unassigned |
| 561 | The "remind me" chat answer's text appears twice in the bubble's innerText (not checked whether drawn twice). | docs/roadmap/agent-remaining/OPEN.md:2450 | S | unassigned |
| 562 | The other tabs' starters (Notes, Chat, Graph, Library, Documents) are not in ai/starter_acts.py; with no model they get the composed answer... | docs/roadmap/agent-remaining/OPEN.md:2518 | S | unassigned |
| 563 | A file of tests (describe/it, unittest) debugs as a plain script, without the harness: the tests do not run under Debug. | docs/roadmap/agent-remaining/OPEN.md:2580 | S | unassigned |
| 564 | "the other one" (decision 57) in Chat: routes_chat._spoken_act sends objects only when the client puts them on history turns; chat-attach.js does not... | docs/roadmap/agent-remaining/OPEN.md:2609 | S | unassigned |
| 565 | INBOX 731 (the Guide failing with a model): not touched; the model-path fallback in help_chat.answer_stream still needs the log line read. | docs/roadmap/agent-remaining/OPEN.md:2612 | S | unassigned |
| 566 | Row 9 (rule 12): "a board AI act as one chat tool (summarise this board; a board from a note)". Not built: a tool under src/memorymap/ai/tools/ with... | docs/roadmap/agent-remaining/OPEN.md:2651 | M | unassigned |
| 567 | Eight dialogs open as centred cards at 390 and should be bottom sheets (extract, history, connections, binned, run a skill, board keys, meeting... | docs/roadmap/agent-remaining/OPEN.md:2674 | S | unassigned |
| 568 | Six of 14 content docks show more than seven items at 1440 (Notes 10, Graph 9, Library 9, Chat 8, Timeline 8, Boards 8); fold by count, 13.1 row 2... | docs/roadmap/agent-remaining/OPEN.md:2675 | S | unassigned |
| 569 | The README tour still has two gaps. The chat screenshot shows an empty conversation (no model in the sandbox), so a machine with Ollama should retake... | docs/roadmap/agent-remaining/OPEN.md:2739 | M | unassigned |
| 570 | guideia.md: the Guide is a modal sheet whose scrim dims the app, so "Open the Reminders tab" cannot be read against the tab. [guideia] *Needs: a... | docs/roadmap/agent-remaining/OPEN.md:2796 | S | unassigned |
| 571 | uipolish-0924.md: the surface-by-surface pass (its item D) is already a row above. Triaged: deadbtn.js's findings for Chat's #chat-export and... | docs/roadmap/agent-remaining/OPEN.md:2841 | M | unassigned |
| 572 | Help audit's remainder: menus drawn on press (the chat "/" menu, a message's menu, the board menus, the notes list's menus) are checked by source... | docs/roadmap/agent-remaining/OPEN.md:2986 | M | unassigned |
| 573 | Chat panels not measured: #chat-model-panel with a model connected (popupsart.js (removed 2026-10-12, recoverable from git history) cannot open it without one; use scratchpad/llama-dev.sh) and the... | docs/roadmap/agent-remaining/OPEN.md:2993 | S | unassigned |
| 574 | The popup agent's results pane with a conversation in it. Everything was measured on the empty state, since this sandbox has no model... | docs/roadmap/agent-remaining/OPEN.md:3252 | L | unassigned |
| 575 | The .skill-fact-reads chip reads dy +4px in one of four identical instances on the Skills sub-tab at 1440 (badgealign.js); the instance is not... | docs/roadmap/agent-remaining/OPEN.md:3309 | S | unassigned |
| 576 | Owner (2026-10-07): the janitor warmed a default chat model it never checked ("Chat with 'llama3.2' failed"). warm_filing_model (janitor.py:741)... | docs/roadmap/agent-remaining/OPEN.md:3336 | M | unassigned |
| 577 | Owner (2026-10-07): on first launch, choose the chat, background and image models from the installed ones instead of llama3.2 (Atlas said "was... | docs/roadmap/agent-remaining/OPEN.md:3337 | M | unassigned |
| 578 | Chat's next-question chips were not seen in the browser: the sweep found no .chat-followups button. Check refreshFollowupVisibility and the chip... | docs/roadmap/agent-remaining/OPEN.md:3359 | M | unassigned |
| 579 | Chat dock at narrow widths: the streaming state (Stop shown, Send hidden) was not measured. (from dock694-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3363 | S | unassigned |
| 580 | Chat's 82 (1440) and 136 (390) overlaps after answers: a sticky head over scrolled cards or a real paint clash. (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3420 | S | unassigned |
| 581 | Whether each Guide topic answers its question (only the topic's head was read). (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3421 | S | unassigned |
| 582 | Chat with no model: "what is 15% of 240" quotes a note; "convert 5 km to miles", "what day is it today" and "summarise my week" answer "Nothing in... | docs/roadmap/agent-remaining/OPEN.md:3427 | M | unassigned |
| 583 | Item 32, "metadata ... very messy": the chat answer's foot is still three rows (Sources, Grounded in, meta), 148 px measured on a five-source answer... | docs/roadmap/agent-remaining/OPEN.md:3505 | S | unassigned |
| 584 | INBOX 731, "the help guide failed??": with a model only; no model answers (help-chat.js:329 is the catch). Needs the server log line from a model run. | docs/roadmap/agent-remaining/OPEN.md:3507 | S | unassigned |
| 585 | Web link cards in chat and the web reader share no recipe with markdown.js:1258 linkCard; one recipe for both. | docs/roadmap/agent-remaining/OPEN.md:3512 | S | unassigned |
| 586 | Rule 5: a stopped answer ends its stream without a done line; how Chat, the Guide and the documents panel render that end is not verified in the page. | docs/roadmap/agent-remaining/OPEN.md:3522 | S | unassigned |
| 587 | Chat "Save this chat as a document": creates a document, no undo (chat.js; 28 write functions, 7 with an undo path). | docs/roadmap/agent-remaining/OPEN.md:3550 | S | unassigned |
| 588 | The 390 px layout of the Tidy Patterns rows and the Chat pattern line is not measured (1440: Tidy row buttons 32 px, no overflow; Chat line 55 px).... | docs/roadmap/agent-remaining/OPEN.md:3589 | S | unassigned |
| 589 | A chat is one search row (the whole thread), so a hit opens the chat, not the turn that matched (index._conversation_row). [search-1010] | docs/roadmap/agent-remaining/OPEN.md:3596 | S | unassigned |
| 590 | Decision 7: only note cards changed (category pill to a dot and a word); chat bubble metadata not measured (no conversation without a model) and... | docs/roadmap/agent-remaining/OPEN.md:3668 | S | unassigned |
| 591 | One focus ring at 1:1 in Chat (button.active, its outline takes the ground colour, both themes; scratchpad/ui-sweeps/focusring.js). Bug.... | docs/roadmap/agent-remaining/OPEN.md:3672 | S | unassigned |
| 592 | Messages saved before stamps existed show no time (the owner: "a time stamp on each chat message"): showing the chat's own time on every old line... | agent/mergetrain-1011:docs/roadmap/agent-remaining/chattime-1010.md:3 | M | unassigned |
| 593 | The chat list row still reads "3h ago" (relativeTime of the last message), not a clock time: sheets-selects.js loadConversationList; the exact time... | agent/mergetrain-1011:docs/roadmap/agent-remaining/chattime-1010.md:4 | S | unassigned |
| 594 | Guide topics: board-library (1,496) with board-library-saving (672) and whiteboard-controls (659) with whiteboard-selection (1,504) were already... | agent/mergetrain-1011:docs/roadmap/agent-remaining/room101-1011.md:5 | S | unassigned |
| 595 | Library's chat rows and the Shelved list still show their own updated_at, not last_at. | agent/mergetrain-1011:docs/roadmap/agent-remaining/chattime-1010.md:6 | S | unassigned |
| 596 | The Guide answers an off-topic question with the open tab's help, unlabelled. "what is the weather today" asked from the Library returned "From the... | agent/mergetrain-1011:docs/roadmap/agent-remaining/scan-1011.md:10 | M | unassigned |
| 597 | 852: the Contents, Skills, Boards and Documents renderers were not changed; their shifts measured under 0.02 in the flick loop, with a small seeded... | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:18 | S | unassigned |
| 598 | H4. Evals breadth. The same ten cases at 3B and 4B, and the required first call measured over twenty imperatives and ten questions, with a tighter... | docs/roadmap/AGENT_SKILLS_REFORM.md:274 | M | unassigned |
| 599 | Tools that mean something only inside the chat UI are offered anyway: ask_user, make_plan, compress_chat, search_chat_history, get_app_navigation... | docs/roadmap/AGENT_SKILLS_REFORM.md:368 | M | unassigned |
| 600 | Results carry the app's own label with an icon name in front ("ph:folders Listed your categories"); an external client reads "ph:folders" as text.... | docs/roadmap/AGENT_SKILLS_REFORM.md:373 | S | unassigned |
| 601 | No tool annotations (readOnlyHint, destructiveHint), so a client cannot auto-approve the read tools; the registry already knows which are which. | docs/roadmap/AGENT_SKILLS_REFORM.md:376 | S | unassigned |
| 602 | protocolVersion is a constant, 2024-11-05, with no negotiation of the client's version; no resources (notes as resources would suit a notebook) and... | docs/roadmap/AGENT_SKILLS_REFORM.md:378 | S | unassigned |
| 603 | Startup loads the embedder (stderr shows "Loading weights"), 1.6 s warm and longer cold; a client that times out at 5 s on first call would fail. | docs/roadmap/AGENT_SKILLS_REFORM.md:381 | S | unassigned |
| 604 | Only stdio, so only a process on this computer with a Python that can import the app. The packaged app has no Python (/capabilities already says so... | docs/roadmap/AGENT_SKILLS_REFORM.md:383 | M | unassigned |
| 605 | Settings has no panel for it: nothing shows the client config snippet ({"command": ".../python", "args": ["-m", "memorymap.mcp_server"], "env"... | docs/roadmap/AGENT_SKILLS_REFORM.md:390 | S | unassigned |
| 606 | The run object carries its budget: steps, tool calls, tokens and wall time against the skill's declared caps; a run that exceeds one stops with a... | docs/roadmap/AGENT_SKILLS_REFORM.md:412 | S | unassigned |
| 607 | Every tool result is checked by the harness before the model sees it (the 2026-09-21 decision, made a lint): a tool that can write has a verifier in... | docs/roadmap/AGENT_SKILLS_REFORM.md:415 | S | unassigned |
| 608 | Empty chats could not be deleted. A Delete button in the chat toolbar now covers both cases, an empty or unsaved pane resets... | docs/roadmap/BACKLOG.md:105 | M | unassigned |
| 609 | Chat: plain grounded Q&A | docs/roadmap/BACKLOG.md:184 | S | unassigned |
| 610 | There is no token bill. Ollama runs on the user's own machine, so a token costs latency and context window, not money. Headroom's... | docs/roadmap/BACKLOG.md:719 | S | unassigned |
| 611 | A model comparison / test-run feature, Pointer: WORLD_CLASS_PLAN I8 "The model bench" (H3, row 21; model_bench switch in... | docs/roadmap/BACKLOG.md:827 | L | unassigned |
| 612 | Prompt reuse. Every agent round resends the whole message list; keep_alive is set now (OllamaClient, 30 minutes, checked... | docs/roadmap/BACKLOG.md:857 | S | unassigned |
| 613 | The system prompt is long and grew again this session; it is re-sent every round of every turn, which is where Ollama's... | docs/roadmap/BACKLOG.md:911 | S | unassigned |
| 614 | That skills exist at all (the tools are there; the prompt never mentions them) | docs/roadmap/BACKLOG.md:967 | S | unassigned |
| 615 | Deciding *when* to search, not just how well it searches once asked. Asked for as "better agentic web search through chat", read... | docs/roadmap/BACKLOG.md:1040 | L | unassigned |
| 616 | Undo is a single tool call posted back to /chat/tools/execute (chat-agent.js, changeRow). Its arguments may carry extra keys... | docs/roadmap/BACKLOG.md:1087 | S | unassigned |
| 617 | No fallback when the configured chat/agent endpoint errors. Checked directly: ai/ollama_client.py, ai/openai_client.py, and... | docs/roadmap/BACKLOG.md:1238 | L | unassigned |
| 618 | Benchmark installed models on first run, to suggest a default rather Pointer: WORLD_CLASS_PLAN I8 "The model bench" (H3); this... | docs/roadmap/BACKLOG.md:1827 | M | unassigned |
| 619 | A VS Code extension. Next: nothing is buildable until the owner states a purpose; the HTTP tool API (GET /chat/tools, POST... | docs/roadmap/BACKLOG.md:1860 | M | unassigned |
| 620 | Chat history has retention; nothing else does. §86 added conversation_retention_days (off by default, pinned chats exempt). The... | docs/roadmap/BACKLOG.md:2265 | L | unassigned |
| 621 | A "this model is struggling" signal. Next: the probe is _tools_path_is_broken in ai/ollama_client.py:571 (§94); count its... | docs/roadmap/BACKLOG.md:2383 | M | unassigned |
| 622 | Conversation summaries as retrieval targets. Next: register a chat source in search/index.py (source_for raises on an... | docs/roadmap/BACKLOG.md:2408 | M | unassigned |
| 623 | A plugin system. Skills already cover the "make the app do a new thing" case without a new extension surface to secure. | docs/roadmap/BACKLOG.md:2495 | S | unassigned |
| 624 | A skill is a *procedure* the agent runs, start to finish. | docs/roadmap/BACKLOG.md:2516 | S | unassigned |
| 625 | A Guide is a *format contract* for one piece of output, it does not run, it constrains. Several can apply at once (an assignment... | docs/roadmap/BACKLOG.md:2517 | S | unassigned |
| 626 | Stored like skills (a table, editable in Settings), with a name, a trigger hint, and the instruction body. | docs/roadmap/BACKLOG.md:2523 | S | unassigned |
| 627 | Applies to all three surfaces the user named: chat replies, note drafting, and POST /documents/{id}/ai-edit. | docs/roadmap/BACKLOG.md:2533 | S | unassigned |
| 628 | Wider Mermaid: sequence and timeline diagrams render in documents and chat, and import to boards as frames; anything else stays... | docs/roadmap/BACKLOG.md:2583 | S | unassigned |
| 629 | *"No way to scope a chat query to chosen notes"*, false. note_ids plus attached_notes_only (routes_chat.py) already do exactly... | docs/roadmap/BACKLOG.md:2895 | M | unassigned |
| 630 | The AI Skills tab's step/tool lists: reported directly, with a screenshot: expanded, they read as plain paragraphs sat right on... | docs/roadmap/BACKLOG.md:3380 | M | unassigned |
| 631 | A "Clear" button for the AI Skills sidebar's own log list, DELETE /audit?entity_type=... (entity_type required, so this can never... | docs/roadmap/BACKLOG.md:3407 | M | unassigned |
| 632 | Per-note pinned AI context, Next: note_ids and attached_notes_only (routes_chat.py) already scope a turn; a Entry.pinned_context... | docs/roadmap/BACKLOG.md:3616 | M | unassigned |
| 633 | A plugin marketplace. The skills library covers reusable prompts; arbitrary third-party code in a privacy-first app is a... | docs/roadmap/BACKLOG.md:3890 | S | unassigned |
| 634 | The owner, 2026-09-21, verbatim, with the session's reading beneath it: "it'd be cool if the user can upload songs or connect an... | docs/roadmap/BACKLOG.md:3959 | L | unassigned |
| 635 | "Read all my requests and chat messages sent during and since october 7, analyse them and log them for a new session as I want to... | docs/roadmap/BACKLOG.md:4167 | L | unassigned |
| 636 | The owner, 2026-09-24, verbatim, with a chat screenshot. "I was in a document in the editor, I opened the suggestions panel and pressed check with... | docs/roadmap/CHAT_PLAN.md:694 | L | unassigned |
| 637 | "on the guide the thinking shows below the thinking indicator and stuff" / "with no gap either" Recommendation: measure the gap between the thinking... | docs/roadmap/CHAT_PLAN.md:847 | M | unassigned |
| 638 | "should that no chats text be at the top not the bottom??" Recommendation: place the empty-chat text at the top of the list and measure its position... | docs/roadmap/CHAT_PLAN.md:849 | S | unassigned |
| 639 | "also I just asked another question, didnt like the response so I deleted it, and now somehow the token usage I was at for that chat has lowered??"... | docs/roadmap/CHAT_PLAN.md:861 | M | unassigned |
| 640 | "I can still activate skills and the suggested skill popup still appears when I have no model running." / "The ai model isnt running, skills are... | docs/roadmap/CHAT_PLAN.md:871 | M | unassigned |
| 641 | "Its still allowing me on agent mode even when the ai model isnt connected" Recommendation: agent mode is disabled with its reason when no model is... | docs/roadmap/CHAT_PLAN.md:873 | S | unassigned |
| 642 | "I tried to press "a note" on the slash menu in the chat tab and the panel flickered then nothing happened" / "Same with the other options like "a... | docs/roadmap/CHAT_PLAN.md:889 | M | unassigned |
| 643 | 731, the Guide failing with a model. "the help guide failed??" (Atlas answering "whiteboard templates" with "Something went wrong asking that"). Not... | docs/roadmap/CHAT_PLAN.md:1757 | M | unassigned |
| 644 | INBOX 808 Agent mode: ask_user with one option, search_notes with no query, backslash kept in query, grammar worker did not start | docs/roadmap/INBOX.md:190 | S | unassigned |
| 645 | Briefs 13, 14 and 16 (harness verifier B5, docs condensed, docs refined): unmarked; verify then close | docs/roadmap/SESSION_BRIEFS.md:430 | S | unassigned |
| 646 | Brief 18: the complete open scope sections A to G (bugs, documents, graph, chat, boards, library, plan remainders): unmarked | docs/roadmap/SESSION_BRIEFS.md:660 | L | unassigned |
| 647 | Six nav groups, by what the person is doing: AI (Models, Search and index, Personas, Skills, Tools it can use, What it remembers, What it learned... | docs/roadmap/UI_MODERNISATION_PLAN.md:1137 | M | unassigned |
| 648 | Answer style moves from General to Personas: it is Atlas's voice, and the Personas pane already says so. General is left with the recycle bin, chat... | docs/roadmap/UI_MODERNISATION_PLAN.md:1148 | S | unassigned |
| 649 | Suggested downloads are model cards, grouped by purpose (chat and filing, bigger machines, search, images, reading text), settings-models.js. One... | docs/roadmap/UI_MODERNISATION_PLAN.md:1174 | L | unassigned |
| 650 | "Note metadata and chat bubble metadata still feels incredibly messy, not modern, and unrefined. The whole app needs another ui/ux modernisation... | docs/roadmap/UI_MODERNISATION_PLAN.md:1272 | L | unassigned |
| 651 | "Things that feel off that I cannot place." After the consistency and docks lists close, one review pass per tab with the vendored design skills... | docs/roadmap/WORLD_CLASS_PLAN.md:1563 | M | unassigned |
| 652 | The Guide's row is the answer to INBOX 288 but not to its cause. Smart model routing off silently moves the Guide, an interactive panel, onto the... | docs/roadmap/WORLD_CLASS_PLAN.md:2274 | M | unassigned |
| 653 | A per-feature model is shown on the Chat tab and nowhere else. The chat pill (#chat-active-model) reads the pinned model now, but the writing desk... | docs/roadmap/WORLD_CLASS_PLAN.md:2281 | M | unassigned |
| 654 | 0.4.0, "laptop perfect": 22.1 items 1 to 6, and the devibecode programme through the shell, Notes, Dashboard, Chat and Settings. | docs/roadmap/WORLD_CLASS_PLAN.md:2433 | L | unassigned |
| 655 | The Guide's corpus and the Help accordion are kept in step by hand (guide; the synonym column it asked for exists, help_chat.py's keyword table).... | docs/roadmap/WORLD_CLASS_PLAN.md:3050 | S | unassigned |
| 656 | Reduced motion was checked in source and the harness, not in a browser run. | docs/roadmap/agent-remaining/graphfeel-1010.md:13 | S | unassigned |
| 657 | Decision 38: the other 13 verbs, confirm card, undo, no-model Agent mode, web search tool. | docs/roadmap/agent-remaining/spec39-1010.md:10 | S | unassigned |
| 658 | "Gemini might have removed the spell checker??" (the owner): it did not touch the editor's speller (its frontend diff is skills.js, index.html... | docs/roadmap/agent-remaining/triage-1010.md:24 | M | unassigned |
| 659 | Rail nodes (frontend/css/02-chat-graph.css:732): 0.75rem kept, measured on a synthetic run: thinking and plan rows 0.12px from the first line's... | docs/roadmap/agent-remaining/triage-1010.md:31 | S | unassigned |
| 660 | search_help found nothing for "what is agent mode" and "how does search work" (2 of 10; help_block_for, src/memorymap/ai/help_chat.py:2467). | docs/roadmap/agent-remaining/triage-1010.md:32 | S | unassigned |
| 661 | Atlas round 5, the owner's asks (INBOX 427 (1); 2026-09-27): hands and feet drawn as part of each limb's outline (a mitten with a thumb on the inner... | docs/roadmap/agent-remaining/OPEN.md:1903 | L | unassigned |
| 662 | The companion rides with ScrollTimeline (Chromium 115+, so WebView2); WebKitGTK falls back to the script follow. Not driven in either desktop window.... | docs/roadmap/agent-remaining/OPEN.md:1935 | S | unassigned |
| 663 | Atlas's hide act shows shut eyes and nothing of its hands. The companion's new act (a private note opened) raises both arms over the face; Atlas... | docs/roadmap/agent-remaining/OPEN.md:2150 | L | unassigned |
| 664 | The Atlas look row landed under the Settings sheet's head at 390 in one of four runs. | docs/roadmap/agent-remaining/OPEN.md:2451 | S | unassigned |
| 665 | The rest of Atlas's idle cost is the companion's own behaviour, not the tail: with the tail and breath switched off, 670 recalcs and 130 layouts a... | docs/roadmap/agent-remaining/OPEN.md:2619 | M | unassigned |
| 666 | The chest's breath still writes the torso's scale 2.5 times a second at rest (atlas-life.js atlasBreathFrame): a recalc and a layout each. Zero needs... | docs/roadmap/agent-remaining/OPEN.md:2623 | M | unassigned |
| 667 | 104px faces (the welcome, the large view): 2 to 3 of 15 distinct in light by the same metric; the cue is drawn only at the head and tiny levels. The... | docs/roadmap/agent-remaining/OPEN.md:2626 | M | unassigned |
| 668 | Arm angle over a walk cycle not measured (atlasarms.js measures still poses; the walk swing is the rig's, atlas-motion.js atlasRigFrame). | docs/roadmap/agent-remaining/OPEN.md:2636 | S | unassigned |
| 669 | #nm-buddy:has(.atl-figure) .nm-buddy-char and the lower layer still slow to 6s under the hint (08-consistency.css, the block after the chin hand... | docs/roadmap/agent-remaining/OPEN.md:2638 | M | unassigned |
| 670 | Companion movement Full keeps the script loops (tail, rings) under Reduce by design (atlasMotionOK); the CSS loops stop under the hint regardless. | docs/roadmap/agent-remaining/OPEN.md:2641 | L | unassigned |
| 671 | Atlas motion, measured left (the owner's rows 554 to 575 are above): atlas619-blend.js stepped by hand shows laughing's end moving the figure about... | docs/roadmap/agent-remaining/OPEN.md:2969 | L | unassigned |
| 672 | The owner, 2026-10-05, verbatim. "one of the feminine atlas blinking animations has MASSSSIVE eyebrows." Not reproduced (2026-10-05): the live... | docs/roadmap/agent-remaining/OPEN.md:3100 | M | unassigned |
| 673 | The owner, 2026-10-05, verbatim. "the feminine atlas whisps should wrap the body a bit more instead of all of it sitting in front. also the lower... | docs/roadmap/agent-remaining/OPEN.md:3108 | M | unassigned |
| 674 | The owner, 2026-10-05, verbatim. "and a bit more texture can be added to the lower body as well. make it celestial and majestic and magical and... | docs/roadmap/agent-remaining/OPEN.md:3115 | M | unassigned |
| 675 | The owner, 2026-10-05, verbatim. "can you fix or redesign the male main body on the atlas avatar instead of just being an oval?? also fix how the... | docs/roadmap/agent-remaining/OPEN.md:3120 | L | unassigned |
| 676 | The owner, 2026-10-05, verbatim. "can you have the lower body of both atlas avatars change around in position and and how it is sitting ect with... | docs/roadmap/agent-remaining/OPEN.md:3130 | M | unassigned |
| 677 | "I cant right click to view the menu to change the companion in the expanded popup view" Recommendation: the enlarged view gets the same context menu... | docs/roadmap/agent-remaining/OPEN.md:3279 | M | unassigned |
| 678 | "I barely get to see atlas change expression. atlas and the companion movement and behaviour need to be more and more lifelike, natural, smooth... | docs/roadmap/agent-remaining/OPEN.md:3284 | M | unassigned |
| 679 | "The companion and atlas needs a lot more improvement, and lifelike behaviour, more cool and diverse ways to move around, enter the screen, change... | docs/roadmap/agent-remaining/OPEN.md:3286 | M | unassigned |
| 680 | A click in Atlas's own large view costs 22 to 44ms in setAtlasMood (every layer's animations, then atlasApply on 12 layers), 50 to 100ms on a loaded... | docs/roadmap/agent-remaining/OPEN.md:3332 | M | unassigned |
| 681 | The generic (non-Atlas) faces' arms have no rig and so no speed cap; the fastest segment of their wave and hide keyframes was not measured. (from... | docs/roadmap/agent-remaining/OPEN.md:3333 | S | unassigned |
| 682 | INBOX 742 and 743, "atlas doesnt seem to change emotions alot", "more mouse interaction ... rubbing its head. flipping it upside down": gestures... | docs/roadmap/agent-remaining/OPEN.md:3508 | M | unassigned |
| 683 | Palette rows missing (heuristic word match, the destination and its click path): 1 Notifications: # unread (muted except reminders); 1 Atlas files it... | docs/roadmap/agent-remaining/OPEN.md:3562 | L | unassigned |
| 684 | Decision 7's "under 1 ms a minute" is not met by Atlas: its tail is a script-drawn path (atlas-life.js atlasTailFrame), 15 draws a second at rest... | docs/roadmap/agent-remaining/OPEN.md:3624 | M | unassigned |
| 685 | Atlas's faces do not read as different moods (sheet: atlas-sheet-*.png, 15 moods at 104, 28 and 20 px, both looks, light and dark): at 104 the face... | docs/roadmap/agent-remaining/OPEN.md:3625 | M | unassigned |
| 686 | Under the system's reduce-motion hint Atlas keeps its calm CSS loops (an earlier decision, 08-consistency.css:5056): 1,579 style recalcs a minute.... | docs/roadmap/agent-remaining/OPEN.md:3626 | S | unassigned |
| 687 | The owner's "arm movements ... permanently in a downward arc": the arm hold now changes on idle ticks (45%), but the arm angle range over a walk... | docs/roadmap/agent-remaining/OPEN.md:3628 | S | unassigned |
| 688 | Tail, rings, nebula and lower-body "subtle animations that are all cheap" (owner's list): not changed; they exist (atlas-life.js) and are the cost... | docs/roadmap/agent-remaining/OPEN.md:3629 | S | unassigned |
| 689 | Face sheet (facesheet.js (removed 2026-10-12, recoverable from git history), 12 names, light): one silhouette, one outline, readable at 104; crowns spill 6 px past the card's top edge; the gaming... | docs/roadmap/agent-remaining/OPEN.md:3630 | S | unassigned |
| 690 | Companion bubbles: what the companion says about the notebook (a resurfaced note, a pattern this week, a reminder due, an empty day) is composed from... | docs/roadmap/CHAT_PLAN.md:727 | M | unassigned |
| 691 | Voice: Atlas's by default, changeable. Warm and brief in openings and companion bubbles, plain in answers; a setting offers plain and playful too... | docs/roadmap/CHAT_PLAN.md:829 | S | unassigned |
| 692 | Two functions here are among the ten most complex in src (WORLD_CLASS 26.5): api/routes_chat.py::_stream_lines cx 105 over 321 lines and... | docs/roadmap/CHAT_PLAN.md:1763 | M | unassigned |
| 693 | INBOX 742 Atlas changes emotions more: mood-change count per session (Brief 34 second part) | docs/roadmap/INBOX.md:111 | M | unassigned |
| 694 | INBOX 743 more mouse interaction with Atlas: gestures, enlarged view mirroring the corner, oval clip, Show companion notice (Brief 34, OPEN Atlas rows 752) | docs/roadmap/INBOX.md:118 | M | unassigned |
| 695 | INBOX 772 reduced motion keeps poses without loops: decision taken, companion2 continues | docs/roadmap/INBOX.md:151 | S | unassigned |
| 696 | Brief 34 continues: Atlas and the companion (companion2 landed; OPEN Atlas rows remain) | docs/roadmap/SESSION_BRIEFS.md:1390 | L | unassigned |
| 697 | Settings that guard something stay beside it. "Keep Atlas on this machine" stays with the backend address it guards; the Privacy pane reports, it... | docs/roadmap/UI_MODERNISATION_PLAN.md:1151 | S | unassigned |
| 698 | The owner, 2026-09-24 (after the usage reset), with screenshots. Avatars: (a) "the avatar shows even when the app is on the lock screen. it should... | docs/roadmap/WORLD_CLASS_PLAN.md:2886 | L | unassigned |
| 699 | Decision 36: bubble label "Atlas, from your notes" is a frontend check. | docs/roadmap/agent-remaining/spec39-1010.md:8 | S | unassigned |
| 700 | Section: Phases 1 to 5 as first written (built per sections 9 to 11) | docs/roadmap/MINDMAP_PLAN.md:158 | S | unassigned |
| 701 | Section: 12.3 Phase 6c, what only a notebook can do | docs/roadmap/MINDMAP_PLAN.md:505 | M | unassigned |
| 702 | Section: Section 13: the six complaints, phases open | docs/roadmap/MINDMAP_PLAN.md:604 | L | unassigned |
| 703 | Section: 14.4 What is open (core nodes, linked symbols, layer effects, reactions) | docs/roadmap/MINDMAP_PLAN.md:1755 | M | unassigned |
| 704 | The mind map's own leftover list was re-checked item by item, 2026-09-20 (archive/agent-remaining/mindmap.md, "Left to do", rewritten with what a run... | docs/roadmap/agent-remaining/OPEN.md:2087 | L | unassigned |
| 705 | Pre-existing sweep failures on the base scripts: mapcore.js (removed 2026-10-12, recoverable from git history) 14/16 (a core node's spine and size), mindmap.js three FAILs (the Mind map segment's... | docs/roadmap/agent-remaining/OPEN.md:2119 | M | unassigned |
| 706 | Mind map gaps open: a structure per branch, callouts, labels under a topic, .xmind export, stickers and votes. | docs/roadmap/agent-remaining/OPEN.md:2380 | S | unassigned |
| 707 | Mind map library schematics (wbMapThumbSpec) are monochrome, not tinted with branch colours; a hollow diamond draws the shaft through it. | docs/roadmap/agent-remaining/OPEN.md:2414 | S | unassigned |
| 708 | createConceptMap (whiteboard.js ~20240) has no caller but app.js's lazy stub list now that every "concept map" entry makes the mind map: delete it... | docs/roadmap/agent-remaining/OPEN.md:2551 | S | unassigned |
| 709 | mindmap2.md: mindmapimage.js (removed 2026-10-12, recoverable from git history) passes 12 of 12 at 390x844 (measured 2026-10-04); a picture node does not resize to its picture; mindmap3.js times out... | docs/roadmap/agent-remaining/OPEN.md:2821 | L | unassigned |
| 710 | Frames and the map plan's rest: MINDMAP_PLAN 12.2's rest (a boundary round a lassoed set that is not one branch, priority, progress, flags and due... | docs/roadmap/agent-remaining/OPEN.md:2952 | M | unassigned |
| 711 | The size stepper reads "17px" on a main branch and "22px" on the centre, and Classic's level sizes have no S, M, L or XL word, so the well showed... | docs/roadmap/agent-remaining/OPEN.md:3399 | M | unassigned |
| 712 | Mind map "Add a top-level topic": the board stack grows by one, Ctrl+Z leaves the lists differing (/whiteboard/ state not equal to before)... | docs/roadmap/agent-remaining/OPEN.md:3549 | S | unassigned |
| 713 | Whiteboard 43 write functions, 14 with an undo path; mind map 25 and 7; graph 21 and 9; library 30 and 9; dashboard 9 and 1; timeline 5 and 1... | docs/roadmap/agent-remaining/OPEN.md:3551 | S | unassigned |
| 714 | Documents were not probed in the dark run (the list had not loaded when the sweep opened it), and the mind map "Add a top-level topic" undid in one... | docs/roadmap/agent-remaining/OPEN.md:3553 | S | unassigned |
| 715 | #wb-tool-group span.wb-tool-section-label: text 49 to 56px past its box at 820, 1024 and 1440 on the whiteboard and the mind map (36 nodes counted as... | docs/roadmap/agent-remaining/OPEN.md:3554 | S | unassigned |
| 716 | Board: board acts are off on a mind map (wbPaletteActRow returns null when wbIsMap()): a map's layout is its tidy, not a grid. Pasting a list as... | docs/roadmap/agent-remaining/OPEN.md:3608 | M | unassigned |
| 717 | Library: a "boards" or "mind maps" filter resolves to Entry.is_board ids, but the Library's filter keeps note cards only (library.js libraryPhrase)... | docs/roadmap/agent-remaining/OPEN.md:3609 | M | unassigned |
| 718 | Decision 5 for a date field built after boot: the map topic's due date (whiteboard-map.js) stays native; the date picker's typed field sets the date... | docs/roadmap/agent-remaining/OPEN.md:3670 | S | unassigned |
| 719 | Boards and mind maps both ways: a mind map exports to and imports from Mermaid mindmap; sequence and timeline import as frames... | docs/roadmap/BACKLOG.md:2605 | S | unassigned |
| 720 | Nodes are notes: any node can become a note (and stays linked); a note dragged from the Library becomes a node with its card; the map node and the... | docs/roadmap/MINDMAP_PLAN.md:507 | S | unassigned |
| 721 | Grow with the AI: on any node, "Suggest branches" proposes five children from the notebook (grounded, with the source note on each), "Expand from my... | docs/roadmap/MINDMAP_PLAN.md:510 | M | unassigned |
| 722 | From a question: "Make a map of..." in chat proposes a map (exists, Phase 4) and now opens it in the map editor with the proposal as floating topics... | docs/roadmap/MINDMAP_PLAN.md:517 | L | unassigned |
| 723 | The layout maths is not slow either. 76.8ms to lay out 500 topics is a command a person pressed, and wbMapIndex, which every map action calls first... | docs/roadmap/MINDMAP_PLAN.md:730 | S | unassigned |
| 724 | renderWhiteboard is the whole of the *opening*, and it grows faster than the node count: 8.1× the nodes buys 21× the render. 1,282ms is a full second... | docs/roadmap/MINDMAP_PLAN.md:733 | L | unassigned |
| 725 | It lands on the user at the worst possible moment. A second run of the probe recorded where in the gesture the worst frame falls: dragWorstAt 0.03... | docs/roadmap/MINDMAP_PLAN.md:741 | L | unassigned |
| 726 | Absorb the free link into the map's own grammar (the direction this plan should take). The free link keeps being a sketch row; what changes is that... | docs/roadmap/MINDMAP_PLAN.md:794 | M | unassigned |
| 727 | Absorb the tree edge into rows. Cost: a migration of every map, the loss of the one property that makes the tree cheap to read, and every one of the... | docs/roadmap/MINDMAP_PLAN.md:801 | M | unassigned |
| 728 | The rail's most connection-looking control makes the other kind. The Connect section's two buttons, "Straight link (C)" and "Curved link (Shift+C)"... | docs/roadmap/MINDMAP_PLAN.md:831 | M | unassigned |
| 729 | Still one door only: everything on the link ring (reverse, label, cut) needs a right-click on a line, which nothing on screen advertises; "Add a... | docs/roadmap/MINDMAP_PLAN.md:837 | S | unassigned |
| 730 | The data keeps two kinds of connection; the controls stop having two. parent_id stays. What changes is that a map's free link is spoken about in the... | docs/roadmap/MINDMAP_PLAN.md:916 | M | unassigned |
| 731 | The strip is sized like its subject. A control surface for one topic does not take two thirds of the window, and it adapts below 1440 rather than... | docs/roadmap/MINDMAP_PLAN.md:920 | S | unassigned |
| 732 | Customisation grows at the map level, not at the topic level. The eleven per-topic fields are enough; the missing layouts and the absence of any... | docs/roadmap/MINDMAP_PLAN.md:923 | S | unassigned |
| 733 | Nothing is added to the canvas. Per standing order 11, any new affordance comes from DESIGN.md's recipe index or arrives with its own recipe and lint... | docs/roadmap/MINDMAP_PLAN.md:926 | S | unassigned |
| 734 | A cross-link has no colour of its own (taken 2026-09-21, building 13c). It is drawn in --muted, dashed, whatever the rail's ink well held when it was... | docs/roadmap/MINDMAP_PLAN.md:933 | L | unassigned |
| 735 | The ring's middle slot promotes a cross-link to a branch (taken 2026-09-21, building 13c). The gesture that makes one or the other decides from... | docs/roadmap/MINDMAP_PLAN.md:948 | M | unassigned |
| 736 | A map's theme holds the ten fields that describe how a map draws topics, and none of the ones that say which topic this is (taken 2026-09-21... | docs/roadmap/MINDMAP_PLAN.md:953 | L | unassigned |
| 737 | The theme is resolved when a topic is painted, never written onto the topics (taken 2026-09-21, building 13e). A topic's own value always wins, and... | docs/roadmap/MINDMAP_PLAN.md:969 | L | unassigned |
| 738 | The theme lives in one row of the View menu's Map section, and nothing is added to the canvas (taken 2026-09-21, building 13e). Decision 5 above, and... | docs/roadmap/MINDMAP_PLAN.md:991 | L | unassigned |
| 739 | "Reset to branch" and the map-wide reset are one idea at two scopes, not two ideas (taken 2026-09-21, building 13e). The ring's reset drops one... | docs/roadmap/MINDMAP_PLAN.md:1005 | M | unassigned |
| 740 | Delete removes the whole branch (taken 2026-10-03, order 3). The code and the server already did, and now that it is one undo step (the topics and... | docs/roadmap/MINDMAP_PLAN.md:1029 | M | unassigned |
| 741 | Tab adds a topic only when the map was engaged (taken 2026-10-03). Tab on a selected topic added a child from anywhere, so a keyboard user could not... | docs/roadmap/MINDMAP_PLAN.md:1033 | M | unassigned |
| 742 | The board's Insert and Arrange menus stay in the markup (taken 2026-10-04, §13f's remainder). Read as dead markup on a map; measured, it is the... | docs/roadmap/MINDMAP_PLAN.md:1058 | M | unassigned |
| 743 | Numbering is the map's, by outline place, and off until asked (taken 2026-10-04, §12.2 item 7). One switch in the View menu's Map group (the menu's... | docs/roadmap/MINDMAP_PLAN.md:1068 | L | unassigned |
| 744 | A note behind a topic is plain text, a topic's own, and opens in the help popover's shell (taken 2026-10-04, §12.2 item 5's first half). data.note... | docs/roadmap/MINDMAP_PLAN.md:1083 | L | unassigned |
| 745 | A boundary is a branch's, drawn round the topics it holds (taken 2026-10-04, §12.2 item 1, under standing order 3; XMind's shape). data.boundary on... | docs/roadmap/MINDMAP_PLAN.md:1103 | L | unassigned |
| 746 | A summary is words beside a run of siblings, not a topic (taken 2026-10-04, §12.2 item 2). data.summary (up to 80 characters) and data.summary_span... | docs/roadmap/MINDMAP_PLAN.md:1119 | L | unassigned |
| 747 | A map presents by branch (taken 2026-10-05, §12.2 item 9, under standing order 3; MindMeister's shape on the board's machinery, WHITEBOARD_PLAN... | docs/roadmap/MINDMAP_PLAN.md:1134 | L | unassigned |
| 748 | A FreeMind file's single root node is the central topic (taken 2026-10-05, audit FEAT-01, features.md 9.5: the owner's newer words win). This... | docs/roadmap/MINDMAP_PLAN.md:1144 | L | unassigned |
| 749 | A map made from text starts in tree-right and is tidied once as it opens (taken 2026-10-05, audit FEAT-05). The import and the accepted AI proposal... | docs/roadmap/MINDMAP_PLAN.md:1155 | M | unassigned |
| 750 | A new topic is drawn and open for typing before the server answers (taken 2026-10-05, audit FEAT-02). Tab and Enter make a provisional row (negative... | docs/roadmap/MINDMAP_PLAN.md:1160 | L | unassigned |
| 751 | The open map's commands are palette rows (taken 2026-10-05, audit FEAT-11): add, rename, fold, focus, delete, tidy, open every branch, look... | docs/roadmap/MINDMAP_PLAN.md:1183 | S | unassigned |
| 752 | A new topic and its first name are one Undo step (taken 2026-10-05, audit FEAT-15), as in XMind: the rename is folded while the add is still the last... | docs/roadmap/MINDMAP_PLAN.md:1190 | S | unassigned |
| 753 | A committed name hands the keys back to the canvas and is said aloud (taken 2026-10-05, audit FEAT-16), unless the press that ended it went to... | docs/roadmap/MINDMAP_PLAN.md:1193 | S | unassigned |
| 754 | No front-and-back Order on a laid-out map (taken 2026-10-05, audit FEAT-17): a tidied tree never overlaps; a Free map keeps the group. | docs/roadmap/MINDMAP_PLAN.md:1196 | S | unassigned |
| 755 | Text pasted onto a map is a branch (taken 2026-10-05, audit FEAT-09): one topic per line, nested by indentation, a numbered or heading line read as a... | docs/roadmap/MINDMAP_PLAN.md:1198 | M | unassigned |
| 756 | The dashboard draws a map at its own shape (taken 2026-10-05, INBOX 553(d), the owner's decision): the Boards & maps widget's busiest board at the... | docs/roadmap/MINDMAP_PLAN.md:1204 | M | unassigned |
| 757 | A map writes itself as a document, one way first (taken 2026-10-05, the audit's brief M5, first half): the board menu's Write as a document and the... | docs/roadmap/MINDMAP_PLAN.md:1209 | M | unassigned |
| 758 | A concept map's topics are notes that stay on their map (taken 2026-10-05, audit UX-06). A note made by a map gesture (a new concept map's root, a... | docs/roadmap/MINDMAP_PLAN.md:1216 | L | unassigned |
| 759 | A map's outline is a panel of fields in the tree's order (taken 2026-10-05, §12.2 item 8, the audit's M3). View, Outline (and the palette's row)... | docs/roadmap/MINDMAP_PLAN.md:1227 | L | unassigned |
| 760 | A document maps its own headings, one way (taken 2026-10-05, the audit's M5 second half). The document's menu, Map the headings (and the palette's... | docs/roadmap/MINDMAP_PLAN.md:1257 | L | unassigned |
| 761 | Studying a map is presenting with each branch hidden until recalled (taken 2026-10-05, §12.3 item 5, under standing order 3; op5). The board menu's... | docs/roadmap/MINDMAP_PLAN.md:1269 | L | unassigned |
| 762 | A topic's due date is a day, a marker, and a reminder only when asked (taken 2026-10-05, §12.2 item 4, under standing order 3; op5). data.due is a... | docs/roadmap/MINDMAP_PLAN.md:1282 | L | unassigned |
| 763 | (Audit 2026-10-05: 13a-open's figures hold for a move; the add path was never gated and cost two whole renders, see decision 24.) | docs/roadmap/MINDMAP_PLAN.md:1313 | S | unassigned |
| 764 | 13g. The middle-button pan on the owner's own machine. He reports, with 13.1's own gesture: "the whiteboard and mindmap goes haywire and moves to the... | docs/roadmap/MINDMAP_PLAN.md:1333 | L | unassigned |
| 765 | Every figure above is light mode. Dark is unmeasured in this read. | docs/roadmap/MINDMAP_PLAN.md:1433 | S | unassigned |
| 766 | The timings are one machine, one Chromium, one run each except the 500-node row, which was run twice (1,583.3ms and 1,616.5ms worst drag frame). They... | docs/roadmap/MINDMAP_PLAN.md:1434 | S | unassigned |
| 767 | The strip is measured at 1440, 1024 and 390 only. boot() defaults to 1440 but takes opts.viewport, so other widths were reached by passing it; 820... | docs/roadmap/MINDMAP_PLAN.md:1437 | S | unassigned |
| 768 | The free link was created through /whiteboard/sketches with the fields the connect drag writes, not by driving the drag itself. The row is the same... | docs/roadmap/MINDMAP_PLAN.md:1440 | S | unassigned |
| 769 | Nothing here reproduces the owner's phrase "awkward to use". The counts say where the controls are, not what it feels like to reach for one. 13b and... | docs/roadmap/MINDMAP_PLAN.md:1443 | M | unassigned |
| 770 | The owner, 2026-09-21, verbatim: "the mindmap needs A LOT of improving. Tools and utilities are really awkward to use and dont show themselves how id... | docs/roadmap/MINDMAP_PLAN.md:1467 | L | unassigned |
| 771 | The owner, 2026-09-27 after the reset, verbatim. "I think notes appear in the command palate search / Also is there a way to customise the colour the... | docs/roadmap/MINDMAP_PLAN.md:1489 | L | unassigned |
| 772 | Ghost topics on the canvas: the suggestions drawn faded under the topic, Tab to take one, Escape to drop them all. Waits on boot CSS room (the cap is... | docs/roadmap/MINDMAP_PLAN.md:1637 | S | unassigned |
| 773 | Expand from my notes: a topic grown a level from the note it is grounded in (its headings and links), not from search. | docs/roadmap/MINDMAP_PLAN.md:1640 | S | unassigned |
| 774 | The affinity sort (a board, WHITEBOARD_PLAN's territory): thirty stickies grouped into named frames by theme, each placement shown with the notes... | docs/roadmap/MINDMAP_PLAN.md:1642 | S | unassigned |
| 775 | The claim check (DOCUMENTS_PLAN's territory): a document's sentences checked against the notebook, each marked supported, contradicted or not found... | docs/roadmap/MINDMAP_PLAN.md:1645 | S | unassigned |
| 776 | Linked stickers (Illustrator's symbols): edit one placed icon or emoji and every copy follows. Needs a library_ref that is followed, which decision... | docs/roadmap/MINDMAP_PLAN.md:1760 | S | unassigned |
| 777 | The whiteboard half of 641's research, beyond stickers. | docs/roadmap/MINDMAP_PLAN.md:1765 | S | unassigned |
| 778 | The exported picture draws each topic's shape since 2026-10-10 (boardmap-1010); a topic's effect and a Phosphor icon still do not reach PNG or SVG... | docs/roadmap/MINDMAP_PLAN.md:1766 | S | unassigned |
| 779 | The document editor's :shortcode: completion keeps its own 248-entry table (DOC_EMOJI_SOURCE); fold it into ICON_EMOJI_SOURCE when the completion can... | docs/roadmap/MINDMAP_PLAN.md:1768 | S | unassigned |
| 780 | Measured nearly clean (WORLD_CLASS 26.5): the showcase map at rest 0 long tasks, 0 gaps over 20 ms; a drag of one node 4 gaps over 20 ms of 605... | docs/roadmap/MINDMAP_PLAN.md:1824 | S | unassigned |
| 781 | The owner, 2026-10-11, verbatim. "also when I change stuff in the tools for a mindmap node, I cant actually see what the difference is until I click... | docs/roadmap/MINDMAP_PLAN.md:1847 | M | unassigned |
| 782 | INBOX 816, the owner 2026-10-11, verbatim: "should thes ebuttons be that big??" (screenshot: a zoomed-out dark map; the selected topic "test" is... | docs/roadmap/MINDMAP_PLAN.md:1855 | M | unassigned |
| 783 | INBOX 817, the owner 2026-10-11, verbatim: "also that popup edit bar for when I try editing text doesn follow the selected text with scroll or zoom... | docs/roadmap/MINDMAP_PLAN.md:1856 | L | unassigned |
| 784 | INBOX 818, the owner 2026-10-11, verbatim: "labels on mind map links dont move with the links". Target: a link's label is placed on the link's path... | docs/roadmap/MINDMAP_PLAN.md:1857 | S | unassigned |
| 785 | INBOX 819, the owner 2026-10-11, verbatim: "also i dont think there is a way to label links on a whiteboard. also can link labels be customisable??"... | docs/roadmap/MINDMAP_PLAN.md:1858 | L | unassigned |
| 786 | INBOX 762, "just now" on an untouched mind map. The Library card's modified time moved without the owner; find what writes updated_at on a board when... | docs/roadmap/UI_MODERNISATION_PLAN.md:1240 | M | unassigned |
| 787 | INBOX 791, UI, mind map, the owner 2026-10-10 22:42Z, three screenshots. "these buttons on the mindmap nodes are a little hard to see and interact... | docs/roadmap/UI_MODERNISATION_PLAN.md:1540 | S | unassigned |
| 788 | INBOX 792, UI, mind map, whiteboard and fit, the owner 2026-10-10 22:45Z, three screenshots. "also i dont think i should be typing in these outline... | docs/roadmap/UI_MODERNISATION_PLAN.md:1541 | M | unassigned |
| 789 | Tidy layout never measured past five nodes; a newly opened map leaves its root under the top bar. Owner: mindmap.md item H. | docs/roadmap/WORLD_CLASS_PLAN.md:990 | S | unassigned |
| 790 | The owner, 2026-09-24, verbatim, with screenshots of the writing dictionary, New from a template, the map's radial menus and two linked map nodes.... | docs/roadmap/WORLD_CLASS_PLAN.md:2580 | L | unassigned |
| 791 | The owner, 2026-09-24, verbatim, with screenshots (placed in agent briefs, two at a time). (a) "in the radials on the mind map, the items like "add... | docs/roadmap/WORLD_CLASS_PLAN.md:2623 | L | unassigned |
| 792 | Section: The draw.io programme: 18 areas, 288 rows, Build first (converted libraries not loaded yet) | docs/roadmap/WHITEBOARD_PLAN.md:921 | L | unassigned |
| 793 | Section: canvasdepth ranked gaps (round 3 and the export panel, frame fit, ends and guides, previews) | docs/roadmap/WHITEBOARD_PLAN.md:1556 | L | unassigned |
| 794 | graphjitter.js-style rAF sampling is useless on a loaded machine (frames 50 to 170 ms apart, load average 10 to 33); the worker-tick measure... | docs/roadmap/agent-remaining/OPEN.md:1872 | M | unassigned |
| 795 | The floating topic rename field is 42px tall over a 17px plate (gcRenameTopicInline, graph-canvas.js); not seen by eye, size it to the plate. | docs/roadmap/agent-remaining/OPEN.md:2027 | S | unassigned |
| 796 | chatSourcesPanel is shared, the renderer is not. Judged not worth it in 2026-09-13: the three surfaces have genuinely different frames around the... | docs/roadmap/agent-remaining/OPEN.md:2049 | S | unassigned |
| 797 | The whiteboard's own View menu (.wb-board-menu) was never reproduced as broken. It has its own max-height-on-open logic (whiteboard.js, the... | docs/roadmap/agent-remaining/OPEN.md:2103 | M | unassigned |
| 798 | INBOX 739's documents half: boards and maps name themselves (wbUntitledNames, whiteboard-templates.js); "Untitled document N" is not built... | docs/roadmap/agent-remaining/OPEN.md:2113 | S | unassigned |
| 799 | Document comments do not yet share the board's thread (Reply, Edit, Resolve, Attach); whiteboard.js wbCommentRow is the shape to reuse (Brief 42). | docs/roadmap/agent-remaining/OPEN.md:2114 | S | unassigned |
| 800 | A topic's effect (shadow, glow) and a Phosphor icon do not reach the PNG or SVG picture (wbBuildExportSvg, the map-node branch); shapes do. | docs/roadmap/agent-remaining/OPEN.md:2115 | S | unassigned |
| 801 | The frame-preview clip was reproduced only as the selection canvas lagging a container that grew mid-drag (fixed); the owner's exact trigger is not... | docs/roadmap/agent-remaining/OPEN.md:2116 | S | unassigned |
| 802 | WHITEBOARD_PLAN "Placed from INBOX, 2026-10-07 (next PR)": 740's frame hint has no edit path and its connector arrow-head set (none, open, triangle... | docs/roadmap/agent-remaining/OPEN.md:2118 | M | unassigned |
| 803 | .dock-chip-row has no user in the page since cb8060a (only a comment in index.html names it). Its rules are in frontend/css/07-whiteboard-misc.css... | docs/roadmap/agent-remaining/OPEN.md:2181 | M | unassigned |
| 804 | Logs More menu .dock-menu-check rows 34.9px/8px against 32px/12.8px items; the board's Start and End menus not measured for end gaps. | docs/roadmap/agent-remaining/OPEN.md:2252 | S | unassigned |
| 805 | .wb-resize-handle title still says "double-click fits the text" on non-frame objects; a dead .wb-map-actions coarse-pointer rule pinned by... | docs/roadmap/agent-remaining/OPEN.md:2261 | S | unassigned |
| 806 | Open: "what is there about X" with no model is the quoted answer, not the overview shape (decision 64). | docs/roadmap/agent-remaining/OPEN.md:2285 | S | unassigned |
| 807 | Tables lack column widths and merged cells; Edit data lacks %name% placeholders; .drawio export is not built; a hidden named layer's item eye and... | docs/roadmap/agent-remaining/OPEN.md:2295 | S | unassigned |
| 808 | Whiteboard gaps open: the hand-drawn look, tables, edit data, a current layer new items land in, .drawio pages after the first; an item's eye on a... | docs/roadmap/agent-remaining/OPEN.md:2379 | S | unassigned |
| 809 | The laser sweep's 390 threshold was lowered from 10 dots to 3 and not re-run; a real draw.io file and dark theme not verified. | docs/roadmap/agent-remaining/OPEN.md:2382 | S | unassigned |
| 810 | The AI board tools and import/export do not carry a note's fold. | docs/roadmap/agent-remaining/OPEN.md:2415 | S | unassigned |
| 811 | At 390 the whiteboard sidebar is a full-width sheet, so the fit ignores it there. | docs/roadmap/agent-remaining/OPEN.md:2417 | S | unassigned |
| 812 | Ids inside board object data and comments are copied, not remapped; private notes, several spaces and a browser upload of 5,000 files not verified. | docs/roadmap/agent-remaining/OPEN.md:2425 | S | unassigned |
| 813 | Row 4 at 390: press to editable 140 to 159 ms against the 50 ms bar (1440 is 24 to 27). Each forced style pass in the add restyles about 830 elements... | docs/roadmap/agent-remaining/OPEN.md:2549 | M | unassigned |
| 814 | mapstrip.js: 5 fails left, all failing on the base as well (shapes stored and drawn, the ring's six slots, the grip drag, Shift scaling, the first... | docs/roadmap/agent-remaining/OPEN.md:2556 | S | unassigned |
| 815 | Watches and conditions in JavaScript are evaluated natively over the frame's values (evaluate, api/run_sandbox.py:250), not stepped: a watch that... | docs/roadmap/agent-remaining/OPEN.md:2578 | S | unassigned |
| 816 | Python's runtime still reloads per document opened (ide1's Left row; the frame lives in the panel); the first Debug on a cold runtime waits for it... | docs/roadmap/agent-remaining/OPEN.md:2582 | S | unassigned |
| 817 | The console on an .html, .css, .svg or .sql file is JavaScript in a fresh worker, not the page's global: the page runs in a frame whose window the... | docs/roadmap/agent-remaining/OPEN.md:2591 | S | unassigned |
| 818 | "more access" (INBOX 758): write tools that are not acts (create_category, rename_tag, delete_tag, merge_categories, board and map tools) are named... | docs/roadmap/agent-remaining/OPEN.md:2610 | S | unassigned |
| 819 | Row 2's New is still a menu (details#wb-boards-new-menu): a split button (DESIGN.md's recipe) would make it one press; tour.js and reveal-targets.js... | docs/roadmap/agent-remaining/OPEN.md:2652 | S | unassigned |
| 820 | D6 .md preview in the sandbox frame: not done; a Markdown document already has its own Live and Split views. | docs/roadmap/agent-remaining/OPEN.md:2662 | S | unassigned |
| 821 | Python's runtime reloads on every document opened (5.9 to 7.0 s cold at 1440): the sandbox frame lives in the panel, which is rebuilt per document... | docs/roadmap/agent-remaining/OPEN.md:2663 | M | unassigned |
| 822 | p5 in the sandbox logs "Permissions policy violation: accelerometer" to the console (p5's devicemotion listener in a frame without allow); harmless... | docs/roadmap/agent-remaining/OPEN.md:2665 | S | unassigned |
| 823 | I1's later passes: duplicates, entities and dates as kinds in the same table (tensions are built: pass 4 of the night run, ai/facts.py _pair_passes).... | docs/roadmap/agent-remaining/OPEN.md:2708 | M | unassigned |
| 824 | mapcull.md: freehand and link sketches are not culled (a stroke's box is parsed from its path; worth it only when a board with many strokes measures... | docs/roadmap/agent-remaining/OPEN.md:2807 | M | unassigned |
| 825 | whiteboard-tail.md: the AI half of the map needs a model. INBOX 276 (the sketch pad's toolbar at 820) is closed, HISTORY.md, "OPEN.md rows closed... | docs/roadmap/agent-remaining/OPEN.md:2854 | M | unassigned |
| 826 | Skeletons for a board's Library and Notes tabs (INBOX 596): the tabs (whiteboard-library.js, wbLoadLibrary) draw nothing while they load.... | docs/roadmap/agent-remaining/OPEN.md:2897 | M | unassigned |
| 827 | Board and map history: an agent's or another tab's change is not on a board's stack (decision 17 says the event log is the long memory; a board's... | docs/roadmap/agent-remaining/OPEN.md:2933 | M | unassigned |
| 828 | Draw.io phase 2's tail (WHITEBOARD_PLAN 30 to 36 hold the decisions): Phase G's affinity sort (Group by theme proposes named frames, one Undo) and... | docs/roadmap/agent-remaining/OPEN.md:2941 | L | unassigned |
| 829 | The Boards and maps dashboard widget's tall maps: a 25-topic tree-right map draws a 20x40 paper in the 72x40 row box. Cropping a tall map or a square... | docs/roadmap/agent-remaining/OPEN.md:2965 | M | unassigned |
| 830 | Tablet layouts: the Documents dock is two rows at 1024 (its identity asks for 22rem beside the actions); the arc layout of a 430-note notebook framed... | docs/roadmap/agent-remaining/OPEN.md:3004 | M | unassigned |
| 831 | Every frame-cost number is headless Chromium with no GPU, so the ranking and the order of magnitude hold and the absolute milliseconds do not. The... | docs/roadmap/agent-remaining/OPEN.md:3220 | M | unassigned |
| 832 | The whiteboard's PDF export goes through the browser's print dialog, which Playwright cannot complete, so it is the one pair of the scope-by-format... | docs/roadmap/agent-remaining/OPEN.md:3245 | M | unassigned |
| 833 | Drag to delete takes no drag from the board sidebar (Library, Layers) onto the trash target; a drop from the Library panel is not a delete. (from... | docs/roadmap/agent-remaining/OPEN.md:3302 | S | unassigned |
| 834 | Sweeps that only click the Library tab time out, because the Library opens on its last sub-tab. bm1005-sidebar.js and bm1005-mapmulti.js click Boards... | docs/roadmap/agent-remaining/OPEN.md:3310 | S | unassigned |
| 835 | Sweeps that wait a fixed 1.2 s for the whiteboard's lazy bundle flake under load (initWhiteboard is not defined). op5-1005.js and mapviewmenu.js wait... | docs/roadmap/agent-remaining/OPEN.md:3316 | M | unassigned |
| 836 | The board preview labels (mapPreview in note-cards.js) run over the next shape ("Cut the sign-up fro…" across a diamond); the label placement is... | docs/roadmap/agent-remaining/OPEN.md:3317 | S | unassigned |
| 837 | INBOX 641's rest, which INBOX.md no longer holds: Illustrator linked symbols (library_ref in whiteboard-library.js), Photoshop topic effects (a level... | docs/roadmap/agent-remaining/OPEN.md:3326 | M | unassigned |
| 838 | PNG and SVG export draws every topic as one box: wbBuildExportSvg (whiteboard.js) leaves out levels, shapes and Phosphor icons. (from mc1.md) | docs/roadmap/agent-remaining/OPEN.md:3327 | S | unassigned |
| 839 | Large view: whole-body moves (nmb-hop, a hop, a cheer, a startle) move the head 14 to 17px a frame, 2.2 times the rest. Decision needed on slowing... | docs/roadmap/agent-remaining/OPEN.md:3331 | M | unassigned |
| 840 | Chromium quirk: a blend's implicit end keyframe held rotate at its start value under a CSS animation that starts at the same value. The blend avoids... | docs/roadmap/agent-remaining/OPEN.md:3334 | M | unassigned |
| 841 | Sweep coverage not yet done: an open board or map, the graph's node popup and controls sheet at 390, the print dialog, the lightbox, the confirm... | docs/roadmap/agent-remaining/OPEN.md:3345 | M | unassigned |
| 842 | wbMapDropTargetAt (whiteboard-map.js:2661) still converts by hand. Fold it into wbClientToBoard and update the pinned line in... | docs/roadmap/agent-remaining/OPEN.md:3365 | S | unassigned |
| 843 | scratchpad/ui-sweeps/pickers.js throws pickNotesDialog is not defined at its note-picker section, since that dialog moved into the whiteboard bundle.... | docs/roadmap/agent-remaining/OPEN.md:3372 | M | unassigned |
| 844 | The breath's cost in the large view is not settled: a CSS loop cost the view about half its frames, so the swell is written ten times a second. The... | docs/roadmap/agent-remaining/OPEN.md:3374 | M | unassigned |
| 845 | README docs/screenshots/palette.png (and docs/index.html's copy) still shows notes, a document and a board in the palette. Retake it with... | docs/roadmap/agent-remaining/OPEN.md:3378 | S | unassigned |
| 846 | Other [^\]\n]-style scanners may share the ReDoS shape; the markdown link stripping in the frontend is JS and is not covered by the Python oracle... | docs/roadmap/agent-remaining/OPEN.md:3386 | S | unassigned |
| 847 | .wb-shape-caret has pointer-events: none (per the file), so the Shapes split button's caret never gets a click and the closest(".wb-shape-caret")... | docs/roadmap/agent-remaining/OPEN.md:3397 | M | unassigned |
| 848 | suggestions-inbox.js (a partial link run) and whiteboard.js (a clear that left items) are red by a computed flag; they are partial failures. (from... | docs/roadmap/agent-remaining/OPEN.md:3410 | S | unassigned |
| 849 | GET /entries/count (src/memorymap/api/routes_entries.py:2293) counts every entry row including boards and the bin; its only reader is onboarding's... | docs/roadmap/agent-remaining/OPEN.md:3431 | M | unassigned |
| 850 | The Timeline labels a map under the "Boards" kind chip (frontend/js/timeline.js:266); it draws it with a map chip and an "Open this map" action, so... | docs/roadmap/agent-remaining/OPEN.md:3432 | S | unassigned |
| 851 | Brief 10 (Library card recipe, widget frame): HISTORY has only the plan table rows. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3443 | S | unassigned |
| 852 | P11 mention counts ("how many times did I mention Porto"): no count shape; notebook_stats counts notes, not mentions. | docs/roadmap/agent-remaining/OPEN.md:3488 | S | unassigned |
| 853 | P13 every date and what is due this week: the fact layer has the dates (factgraph.of_kind), no answer shape lists them. | docs/roadmap/agent-remaining/OPEN.md:3490 | S | unassigned |
| 854 | INBOX 735 first half: the p5.js sketch document kind (code beside a sandboxed live canvas, vendored p5.min.js only); api/run_sandbox.py would need a... | docs/roadmap/agent-remaining/OPEN.md:3532 | M | unassigned |
| 855 | Document comments with the board's thread shape (Reply, Edit, Resolve, Attach): a decision first. Comments are ==words== %%remark%% in the text ("no... | docs/roadmap/agent-remaining/OPEN.md:3533 | L | unassigned |
| 856 | Voice: 67 failure toasts in library.js, whiteboard.js and whiteboard-map.js moved; the other 112 JS files still hold their own strings, and only the... | docs/roadmap/agent-remaining/OPEN.md:3614 | M | unassigned |
| 857 | frames.js has no documents or notes-list surface; add one when DOCUMENTS Phase work lands. [measure60-1010] | docs/roadmap/agent-remaining/OPEN.md:3649 | S | unassigned |
| 858 | A hover frame at 2,000 notes is still 22 to 24 ms here (drawImage and clearRect dominate); the 16 ms target is not met at 2,000; 300 notes was not... | agent/graph100-1011:docs/roadmap/agent-remaining/graph100-1011.md:21 | S | unassigned |
| 859 | The first-ever open (no cache) still plays the warm-up spread (INBOX 775's movement, by design); under load its frames step 80 to 100px. | agent/graph100-1011:docs/roadmap/agent-remaining/graph100-1011.md:22 | S | unassigned |
| 860 | Frame times on the owner's hardware; the desktop webview (pywebview) for the cache, @starting-style and :has. | agent/graph100-1011:docs/roadmap/agent-remaining/graph100-1011.md:26 | S | unassigned |
| 861 | There is no calendar events table: core/events.py is the change log, and the timeline's kinds are note, board, document and... | docs/roadmap/BACKLOG.md:1089 | M | unassigned |
| 862 | Ink-to-text (handwriting OCR) on sketches. Decided out: scratchpad/audit1005/features.md section 4 row C5 (no on-device ML, the... | docs/roadmap/BACKLOG.md:1883 | S | unassigned |
| 863 | "Deleting a note leaves whiteboard cards behind, no cascade", already swept: autonomous.clean_orphaned_board_cards()... | docs/roadmap/BACKLOG.md:1958 | S | unassigned |
| 864 | A dry-run mode for the agent. Pointer: WORLD_CLASS_PLAN B5 (planner, verifier, per-run undo); ai/autonomous.py:132 holds the... | docs/roadmap/BACKLOG.md:2445 | M | unassigned |
| 865 | A preview + edit step, the mermaid on one side, the rendered diagram on the other. The document editor's Split view is the same... | docs/roadmap/BACKLOG.md:2558 | S | unassigned |
| 866 | Preview, then act: the step 2 split view, with three actions: Open in whiteboard (a new board via wbMermaidLayout, the source... | docs/roadmap/BACKLOG.md:2580 | S | unassigned |
| 867 | Export: any diagram to SVG and PNG, the .mmd source, and Mermaid kept inside the exported SVG (as boards already do); a diagram... | docs/roadmap/BACKLOG.md:2608 | S | unassigned |
| 868 | One shape for one thing. Two ⋯ builders drew different glyphs; two Stop buttons used different icons; the same setting had two... | docs/roadmap/BACKLOG.md:3869 | S | unassigned |
| 869 | Parity programme, the next brief per surface (full tables in ANALYSIS.md). Whiteboard: the draw.io reader and shape-library... | docs/roadmap/BACKLOG.md:4246 | L | unassigned |
| 870 | Briefs 8 to 10 ( autocomplete and rail, job runtime B2, Library card recipe and widget frame): unmarked; verify then close or build | docs/roadmap/SESSION_BRIEFS.md:312 | M | unassigned |
| 871 | Brief 44: the draw.io programme, editor phases (catalogue and converter landed) | docs/roadmap/SESSION_BRIEFS.md:1447 | L | unassigned |
| 872 | Brief 45 part 2: act on the census (split whiteboard.js initWhiteboard 3730 lines, documents.js, 133 duplicated blocks, 40 dead defs, 424 downward references) | docs/roadmap/SESSION_BRIEFS.md:1496 | L | unassigned |
| 873 | Briefs 61 to 63: services for whiteboard and files (26b), data out of code (26c), runners and embedder (26d) | docs/roadmap/SESSION_BRIEFS.md:1618 | L | unassigned |
| 874 | The grid wants equal heights, and the photograph pays for them. The tile is a column, the frame is the one child that grows, with a 9rem floor and a... | docs/roadmap/UI_MODERNISATION_PLAN.md:346 | M | unassigned |
| 875 | The count and the fold share one line of facts, which is the Files rows' own .library-file-meta shape rather than a new one. They are still two... | docs/roadmap/UI_MODERNISATION_PLAN.md:372 | L | unassigned |
| 876 | INBOX 793, UI, whiteboard, the owner 2026-10-10 22:48Z, two screenshots: "also I think the view and board dropdown menus in the whiteboard need a bit... | docs/roadmap/UI_MODERNISATION_PLAN.md:1542 | S | unassigned |
| 877 | INBOX 794, UI, whiteboard library, the owner 2026-10-10 22:52Z, screenshot: "also the previews in the library arent vissually accurate to what is... | docs/roadmap/UI_MODERNISATION_PLAN.md:1543 | M | unassigned |
| 878 | Whiteboard: export-selection popover opens a full-height list in the wrong place; arrow drawn shows both caps as Arrow in properties; missing... | docs/roadmap/WHITEBOARD_PLAN.md:609 | L | unassigned |
| 879 | Mid-work drop, 2026-09-20, verbatim (the owner), two screenshots. "the rotate line and circle dont sit at the top center of a group selection in the... | docs/roadmap/WHITEBOARD_PLAN.md:648 | L | unassigned |
| 880 | Recommendation, not a change, 2026-09-19 (the session). The reverted outside commit added right-drag to pan the board, filtered so a right-click... | docs/roadmap/WHITEBOARD_PLAN.md:696 | L | unassigned |
| 881 | The small conventions every canvas user takes for granted. The owner, verbatim: "I cant do things on the whiteboard and mindmap like double clcike... | docs/roadmap/WHITEBOARD_PLAN.md:770 | L | unassigned |
| 882 | The owner, 2026-09-24, verbatim. "in the whiteboard, the arrange dropdown menu appears above the top bar, cutting off the contents" (only the Order... | docs/roadmap/WHITEBOARD_PLAN.md:798 | L | unassigned |
| 883 | The owner, 2026-09-24, verbatim, with the board export dialog and two lightbox screenshots. "is there a way to better design all instances of these... | docs/roadmap/WHITEBOARD_PLAN.md:830 | L | unassigned |
| 884 | contrast.js never visits a board or a map (documents was added 2026-10-04). Brief: add whiteboard and mindmap to its TABS with a seeded board (cards... | docs/roadmap/WHITEBOARD_PLAN.md:852 | M | unassigned |
| 885 | The owner, 2026-10-06, verbatim, with an OKR board from the new templates (frame titles "Objective one", hints "A goal worth the quarter") and a... | docs/roadmap/WHITEBOARD_PLAN.md:872 | L | unassigned |
| 886 | The owner, 2026-10-07, verbatim, with a board made from the flowchart template (Start, Do the first step, Did it work?, Try again, End) after... | docs/roadmap/WHITEBOARD_PLAN.md:885 | L | unassigned |
| 887 | The owner, 2026-10-07, verbatim: "also in the whiteboard and mindmap, there's no way to reset a object back to default style". No such action exists... | docs/roadmap/WHITEBOARD_PLAN.md:897 | M | unassigned |
| 888 | The edge arrows also ignore resize and drag (the owner, 2026-10-07, verbatim: "can you fix the edge arrows and line arrows not moving or rotating... | docs/roadmap/WHITEBOARD_PLAN.md:908 | M | unassigned |
| 889 | Measured clean (WORLD_CLASS 26.5): the showcase board at rest has 0 long tasks and 0 gaps over 20 ms in 3 s; a drag of one object has 1 gap over 20... | docs/roadmap/WHITEBOARD_PLAN.md:1550 | M | unassigned |
| 890 | INBOX 797, the owner 2026-10-10 23:02Z: "Also I feel like the mindmap and whiteboard are still missing a lot of features and options and stuff that... | docs/roadmap/WHITEBOARD_PLAN.md:1554 | L | unassigned |
| 891 | One export panel, one recipe. Every Export opens the same panel: a live preview on the left, options on the right, and one primary "Export" with the... | docs/roadmap/WHITEBOARD_PLAN.md:1585 | M | unassigned |
| 892 | The preview is the file. It renders from the same function that writes the file: the PDF's pages, the PNG at its scale, the HTML in a sandboxed... | docs/roadmap/WHITEBOARD_PLAN.md:1591 | M | unassigned |
| 893 | The options per format. - All formats: the format and file name. - PDF: page size, orientation, margins, light or print theme, a header or footer... | docs/roadmap/WHITEBOARD_PLAN.md:1596 | M | unassigned |
| 894 | Nothing is lost silently. The panel lists what the format cannot carry (an ink stroke in Markdown, a video in a PDF) before export. | docs/roadmap/WHITEBOARD_PLAN.md:1605 | S | unassigned |
| 895 | "Show more" shows only when the card's content overflows its size, measured by scrollHeight > clientHeight after layout and re-measured on resize.... | docs/roadmap/WHITEBOARD_PLAN.md:1625 | M | unassigned |
| 896 | Cards resize freely, to any width and height: no snap to preset sizes. Guided snaps instead, while dragging: to a neighbour's width or height, to the... | docs/roadmap/WHITEBOARD_PLAN.md:1626 | M | unassigned |
| 897 | Images and files in a card scale with the card's width: images keep their ratio up to the card's width, and a file chip is one line that truncates... | docs/roadmap/WHITEBOARD_PLAN.md:1627 | S | unassigned |
| 898 | A double-click on a card's resize handle fits the card to its content (the same gesture as a frame's fit, INBOX 821). | docs/roadmap/WHITEBOARD_PLAN.md:1628 | S | unassigned |
| 899 | INBOX 826, the owner 2026-10-11, verbatim (screenshots: a selected note card with no edge arrows; the Start and End menus): "I still feel like the... | docs/roadmap/WHITEBOARD_PLAN.md:1633 | M | unassigned |
| 900 | E1. A note card gets the edge arrows. Its arrow makes a new empty note card joined by a link (copying a note's text would duplicate a note); a shape... | docs/roadmap/WHITEBOARD_PLAN.md:1638 | S | unassigned |
| 901 | E2. Ends added: outlined triangle, concave (stealth) arrow, dot, cross, half arrow, double arrow; and an end size (small, medium, large) beside each... | docs/roadmap/WHITEBOARD_PLAN.md:1639 | S | unassigned |
| 902 | E3. One signature end, "MemoryMap": an open chevron with the brand mark's node dot at its tip, drawn from the mark's own geometry; it sits first... | docs/roadmap/WHITEBOARD_PLAN.md:1640 | S | unassigned |
| 903 | E4. Dragging out a new shape, text box or frame shows the move guides, snaps the moving corner to them, and shows the size ("120 x 80") beside the... | docs/roadmap/WHITEBOARD_PLAN.md:1641 | M | unassigned |
| 904 | C1. Decision E1, with help: the arrow's title, the Guide topic and the manual path. | docs/roadmap/WHITEBOARD_PLAN.md:1645 | S | unassigned |
| 905 | C2. Decision E2: the six ends and the end size, in the Start and End menus, the map's link menu and the export. | docs/roadmap/WHITEBOARD_PLAN.md:1646 | S | unassigned |
| 906 | C3. Decision E3: the signature end, three candidates measured at 1x and 2x, one taken. | docs/roadmap/WHITEBOARD_PLAN.md:1647 | S | unassigned |
| 907 | C4. Decision E4: guides, corner snap and the size readout while drawing. | docs/roadmap/WHITEBOARD_PLAN.md:1648 | S | unassigned |
| 908 | C5. Decision E5: the audit table here, then its top five per surface; it lists the small taken-for-granted things too (Brief 87's list). | docs/roadmap/WHITEBOARD_PLAN.md:1649 | S | unassigned |
| 909 | INBOX 829, the owner 2026-10-11, verbatim (a board card's preview: grey blocks and squiggles): "board map previews need a lot of work, redesigning... | docs/roadmap/WHITEBOARD_PLAN.md:1653 | L | unassigned |
| 910 | P1. A preview is the board itself, drawn small: the real colours, shapes, connectors and the first words of each card, rendered off-screen to an... | docs/roadmap/WHITEBOARD_PLAN.md:1656 | M | unassigned |
| 911 | P2. A map's preview is its real tree: the central topic's title legible, branches in their colours, two levels deep. | docs/roadmap/WHITEBOARD_PLAN.md:1657 | S | unassigned |
| 912 | P3. The card shows the preview cropped to the content's bounds, the title, items and last edited; an empty board shows an empty-state line, not a... | docs/roadmap/WHITEBOARD_PLAN.md:1658 | S | unassigned |
| 913 | Whiteboard board-preview minimap NaN rects: not reproduced 2026-10-05 (six boards, 0 errors at 1440 and 390, errors.js); see worldclass-1005c.md. | docs/roadmap/WORLD_CLASS_PLAN.md:972 | S | unassigned |
| 914 | Quick wins (Fable, 05:20): five features the plans did not list, each a day or less, each with the site. (a) Undo on every delete toast: notes... | docs/roadmap/WORLD_CLASS_PLAN.md:1571 | L | unassigned |
| 915 | Brief 45 part 2 (Opus): act on WORLD_CLASS_PLAN section 24; split whiteboard.js (initWhiteboard is 3730 lines, cx 653) and documents.js along seams... | docs/roadmap/agent-remaining/census-1010.md:3 | M | unassigned |
| 916 | 7983f71a7: scratchpad/stencils/convert_stencils.py, render_compare.js, five converted libraries and the Apache-2.0 NOTICE and LICENSE in... | docs/roadmap/agent-remaining/drawio-1010.md:10 | M | unassigned |
| 917 | c18ce1fa3: WHITEBOARD_PLAN "The draw.io programme, 2026-10-10" (18 areas, 288 table rows, Build first, Decisions). | docs/roadmap/agent-remaining/drawio-1010.md:14 | L | unassigned |
| 918 | Nothing loads the converted sets yet. They sit in frontend/board-library/drawio/, outside the non-recursive glob in routes_board_library.py and... | docs/roadmap/agent-remaining/drawio-1010.md:28 | S | unassigned |
| 919 | wbPortFractions does not read data.ports yet (whiteboard.js 2457); the converter writes it (rebased to the first row's box). Phase 1.... | docs/roadmap/agent-remaining/drawio-1010.md:34 | L | unassigned |
| 920 | Stroke width fidelity: the converter writes 2 board pixels per stencil unit; draw.io's strokewidth="inherit" follows the cell's width. Not compared... | docs/roadmap/agent-remaining/drawio-1010.md:41 | S | unassigned |
| 921 | Bare <rect/> ops (2,378 across all libraries, zero area): faithful to stencils.min.js, counted, drawn as nothing; if a shape looks short a stroke is... | docs/roadmap/agent-remaining/drawio-1010.md:44 | S | unassigned |
| 922 | Not converted: the other 199 libraries (24.1 MB of JSON; run convert_stencils.py --min-js <fork>/src/main/webapp/js/stencils.min.js --out DIR, about... | docs/roadmap/agent-remaining/drawio-1010.md:47 | L | unassigned |
| 923 | 775 "the cluster fills about a fifth of the canvas; after Fit, about half" and "the bubbles overlap": not reproduced here. Seeded 34 notes, 34 links... | docs/roadmap/agent-remaining/graphfeel-1010.md:6 | M | unassigned |
| 924 | Open: notes leaving the picture vanish rather than fade out (gcBornAlpha fades new ones in only; graph-canvas.js). | docs/roadmap/agent-remaining/graphfeel-1010.md:21 | S | unassigned |
| 925 | Board open timed from a direct openWhiteboardBoard(id) call, not from a click on the Library tile; document open from openDocument(id), not a click.... | docs/roadmap/agent-remaining/measure-1010.md:6 | M | unassigned |
| 926 | Test shapes (kwargs turn, salt, dialogue, result keys readings, grounding kind, part kinds computed and help) are proposals; the building session may... | docs/roadmap/agent-remaining/spec39-1010.md:16 | S | unassigned |
| 927 | Unit conversion (Gemini's pint) and the "what time is it" / "reading time" shapes were dropped, not rebuilt: "convert 5 km to miles" is read as a... | docs/roadmap/agent-remaining/triage-1010.md:28 | S | unassigned |
| 928 | Section: Phase 6: the node panel redesign (popup agent) remainder | docs/roadmap/GRAPH_PLAN.md:121 | M | unassigned |
| 929 | Section: Still open after KG1 to KG9 (knowledge graph) | docs/roadmap/GRAPH_PLAN.md:536 | L | unassigned |
| 930 | INBOX 839, graph: only the drag's heat is changed (graph-worker.js dragHeat). A single-tick 7.1px step still shows in one of two 8px runs (a... | docs/roadmap/agent-remaining/OPEN.md:1869 | M | unassigned |
| 931 | A topic drag writes its core note's pin with its own PUT /graph/pin beside the group's one PUT /graph/pins (gcDragEnd); one write. | docs/roadmap/agent-remaining/OPEN.md:2028 | S | unassigned |
| 932 | scratchpad/ui-sweeps/graphfslightbox.js reads .lightbox in the tick it calls the lazy openLightbox; the sweep needs an await. | docs/roadmap/agent-remaining/OPEN.md:2029 | S | unassigned |
| 933 | Topics becoming categories is Brief 39b's (GRAPH_PLAN "Decision made, 2026-10-10"). | docs/roadmap/agent-remaining/OPEN.md:2030 | S | unassigned |
| 934 | Constellation yellow stars are about 2.1:1 in light; the Notes rows/cards toggle is 28x24. | docs/roadmap/agent-remaining/OPEN.md:2269 | S | unassigned |
| 935 | Notes leaving the picture vanish instead of fading out. | docs/roadmap/agent-remaining/OPEN.md:2396 | S | unassigned |
| 936 | The close-other-menus fix covers the graph's three head buttons only; app-wide it needs about 98 bytes of app-scripts room. | docs/roadmap/agent-remaining/OPEN.md:2397 | S | unassigned |
| 937 | contentsRenameTopic (library.js) and the note-panel rename (graph.js) still save on blur. | docs/roadmap/agent-remaining/OPEN.md:2433 | S | unassigned |
| 938 | The 13.0 gate's "every offence per decision" for decisions 9 to 17 are stylesheet counts from the plan's method paragraph, not from the sweep; still... | docs/roadmap/agent-remaining/OPEN.md:2678 | S | unassigned |
| 939 | The graph signal needs an open note, and the Notes list rarely has one. file: frontend/js/app.js, id: search-open-note. The list passes entry_id only... | docs/roadmap/agent-remaining/OPEN.md:2695 | L | unassigned |
| 940 | The Writing Room's stretch: measured at 1440x900 light on the two NOTE_SURFACES boxes only, the graph's two note boxes not opened. (The table full... | docs/roadmap/agent-remaining/OPEN.md:2924 | L | unassigned |
| 941 | Chromium only, mostly 1440x900, no second browser and no real touch device. The graph's world constant in gcWorldFor (1.6 to 1.25) is reasoned above... | docs/roadmap/agent-remaining/OPEN.md:3210 | M | unassigned |
| 942 | Owner's test (2026-10-07): "How do I change the widgets?" got the whole Dashboard paragraph. A how-to should lead with its step sentence and keep the... | docs/roadmap/agent-remaining/OPEN.md:3356 | M | unassigned |
| 943 | The card tooltip and the graph still show a deduced reason as "(73% confidence, deduced)", not a strength word. (from tidy691-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3403 | S | unassigned |
| 944 | Brief 4 (Settings two-pane, 54 paragraphs): WORLD_CLASS_PLAN.md:1019 says the 54 paragraphs "not re-checked here, so still open". (from... | docs/roadmap/agent-remaining/OPEN.md:3438 | S | unassigned |
| 945 | Graph topics as categories ("How are they different from categories??", the graph agent's hand-off in archive/agent-remaining/graph-1010.md): not in... | docs/roadmap/agent-remaining/OPEN.md:3473 | S | unassigned |
| 946 | Adjacency matrix: no crossing edges at all, so it stays readable when a force graph has turned into wool. Worth it only once... | docs/roadmap/BACKLOG.md:614 | M | unassigned |
| 947 | Timeline-graph: the graph laid out left-to-right by date, links as arcs. §10's Timeline tab does the axis; this would do the axis... | docs/roadmap/BACKLOG.md:618 | M | unassigned |
| 948 | Galaxy / starfield: notes as stars sized by access count, links as faint filaments. The dashboard's "notebook constellation"... | docs/roadmap/BACKLOG.md:630 | M | unassigned |
| 949 | Plain force-directed stays the default; everything else is a picker. | docs/roadmap/BACKLOG.md:637 | S | unassigned |
| 950 | The Graph options row's toggles (Similarity/Entities/Documents/Hide unlinked/Labels) were bare switches with muted text, hard to... | docs/roadmap/BACKLOG.md:3385 | S | unassigned |
| 951 | Decide what the graph is *for*. It is currently a picture plus a thing the AI can walk. The two uses pull in different... | docs/roadmap/BACKLOG.md:3737 | M | unassigned |
| 952 | Graph node popup panel redesign (screenshot, 00:50; the owner: "include redesigning the graph node popup panels in the graph redesign plan"): title... | docs/roadmap/GRAPH_PLAN.md:231 | L | unassigned |
| 953 | Hovering a node grows it into its own halo (INBOX 149, the owner: "can you make graph nodes temporarily expand to fill their glow bubble when I hover... | docs/roadmap/GRAPH_PLAN.md:324 | M | unassigned |
| 954 | A real local model's name/kind entity extraction and a topic's sentence were never run here (no model in the sandbox); both fall back cleanly. | docs/roadmap/GRAPH_PLAN.md:538 | S | unassigned |
| 955 | VC11, D3 hierarchy layouts as a category overview (M, rank 11). D3's hierarchy module is 15 exports with 2 called; treemap, pack and partition would... | docs/roadmap/GRAPH_PLAN.md:599 | M | unassigned |
| 956 | The graph is not idle at rest: scratchpad/ui-sweeps/frames.js counted 1, 9 and 10 long tasks (58 to 70 ms) in 3 s, 150 to 170 ms of script a second... | docs/roadmap/GRAPH_PLAN.md:603 | M | unassigned |
| 957 | /graph is 22 ms for 45 KB of 71 notes; 10 of that is _payload_key (routes_graph.py:667). Not measured at 5,000 notes. | docs/roadmap/GRAPH_PLAN.md:604 | S | unassigned |
| 958 | INBOX 798, the owner 2026-10-10 23:27Z, screenshot: "the graph is still completely broken 😞 I miss how it used to move 😞 look at how the movement is... | docs/roadmap/GRAPH_PLAN.md:608 | S | unassigned |
| 959 | INBOX 799, the owner 2026-10-10 23:45Z: "Alright work autonomously to fix, finish,redesign, improve and extend everything. I will be at work. Impress... | docs/roadmap/GRAPH_PLAN.md:609 | L | unassigned |
| 960 | INBOX 802, graph, the owner 2026-10-11 03:35Z, verbatim: "The graph movement is a lot closer to how it is on main and better than you had it, but I... | docs/roadmap/GRAPH_PLAN.md:615 | L | unassigned |
| 961 | The card is a picture and one paragraph about it. Its name is on the photograph, its description under it, clamped to two lines, and nothing else is... | docs/roadmap/UI_MODERNISATION_PLAN.md:333 | S | unassigned |
| 962 | INBOX 796, bug, graph, the owner 2026-10-10 23:00Z, two screenshots: "dropdown menus in the graph dont close when another is opened causing a visual... | docs/roadmap/UI_MODERNISATION_PLAN.md:1545 | M | unassigned |
| 963 | INBOX 803, UI and bugs, the owner 2026-10-11 03:35Z to 03:45Z, screenshots (Loose ends, While you were away, Kinds of link, the OCR workspace, the... | docs/roadmap/UI_MODERNISATION_PLAN.md:1558 | L | unassigned |
| 964 | Notes (8) and Graph (9) docks are over the seven-control ceiling. Owner: docks.md; the fix is a second "more" group, not hiding. | docs/roadmap/WORLD_CLASS_PLAN.md:978 | S | unassigned |
| 965 | The SVG graph path stays behind a flag until the drag gate is met on a quieter machine. Owner: GRAPH_PLAN Phase 2. | docs/roadmap/WORLD_CLASS_PLAN.md:984 | L | unassigned |
| 966 | 54 paragraphs still outside popovers. Owner: Brief 4. | docs/roadmap/WORLD_CLASS_PLAN.md:987 | S | unassigned |
| 967 | Three notes at 1440x900 fill 0.80 of the free height (0.798 measured): the fit's zoom clamp (GRAPH_FIT_MAX_ZOOM 2.5, graph.js) stops it; a larger... | docs/roadmap/agent-remaining/graphfeel-1010.md:7 | S | unassigned |
| 968 | Open: Arc stays a line by design; a person who picks it by mistake sees "a broken graph". Recommendation for INBOX: say the layout's name on the map... | docs/roadmap/agent-remaining/graphfeel-1010.md:22 | S | unassigned |
| 969 | Section: Phase 5: the calendar as the third view (Brief 55 landed; deepened rows in sections 10 to 12) | docs/roadmap/TIMELINE_PLAN.md:207 | M | unassigned |
| 970 | Touch drag on a tablet, a day page dropped on another day, and a 1,000-note month are built but not driven. | docs/roadmap/agent-remaining/OPEN.md:2300 | S | unassigned |
| 971 | The contrast and errors sweeps were not run on the calendar view. | docs/roadmap/agent-remaining/OPEN.md:2301 | S | unassigned |
| 972 | The feed's Last-year range filters by when a note was written, so a note about a day this month written over a year ago shows in the calendar and not... | docs/roadmap/agent-remaining/OPEN.md:2302 | S | unassigned |
| 973 | cifix5: a quit with the reminder notifier running can wait up to the job pool's 5 s deadline (stop_notifier runs after the pool's shutdown path). | docs/roadmap/agent-remaining/OPEN.md:2342 | S | unassigned |
| 974 | The service worker acts with the session token stored in the notification's data: a scoped reminder token is with the followups agent. | docs/roadmap/agent-remaining/OPEN.md:2365 | S | unassigned |
| 975 | Timeline row 8's bar, click to rows under 300 ms at 96 notes: 329 at load 6 to 8 (app side 73 to 164); a 57 to 70 ms task right after the rows paint... | docs/roadmap/agent-remaining/OPEN.md:2525 | M | unassigned |
| 976 | Reminders at 390: the floating New (#reminders-new) can lie over the row under it (2 overlaps in one run, 0 in the final; 10-responsive.css:1762). | docs/roadmap/agent-remaining/OPEN.md:2526 | S | unassigned |
| 977 | The reminder edit form cannot change an alert (shell-reminders.js reminderEditForm); an alert is set by words only. | docs/roadmap/agent-remaining/OPEN.md:2529 | S | unassigned |
| 978 | A timeline-days preference arriving after the click renders the timeline twice (once in nine runs at 5,000 notes). | docs/roadmap/agent-remaining/OPEN.md:2531 | S | unassigned |
| 979 | A load-more in flight when the range changes leaves the new range at 100 rows until a scroll (timeline.js timelineLoadMore). | docs/roadmap/agent-remaining/OPEN.md:2533 | S | unassigned |
| 980 | The tree table, timeline and fishbone are column layouts that tidy the whole map on every add (wbMapTidyBranchScope); not timed at 200 topics. | docs/roadmap/agent-remaining/OPEN.md:2553 | S | unassigned |
| 981 | A reminder ticked before done_at existed counts as done but in no week. | docs/roadmap/agent-remaining/OPEN.md:2567 | S | unassigned |
| 982 | libtl-0926.md: the Timeline feed lays out about 39 times a second while scrolling (the rows' content-visibility: auto, INBOX 400's trade); the... | docs/roadmap/agent-remaining/OPEN.md:2799 | L | unassigned |
| 983 | The tour: the Timeline's Options and the reminders' More were measured at 390 only. (The fresh data dir walk and widths 600 to 1100 are done... | docs/roadmap/agent-remaining/OPEN.md:3000 | M | unassigned |
| 984 | Dismissed reminder notifications: a dismissed reminder notification never returns (status.js notificationsDismissed, keyed reminder:<id>), so a... | docs/roadmap/agent-remaining/OPEN.md:3013 | M | unassigned |
| 985 | Dashboard and Timeline: D6's streak (the calendar strip and the day before and after are built, daystrip.js; a streak count has no surface: the dock... | docs/roadmap/agent-remaining/OPEN.md:3017 | M | unassigned |
| 986 | 24 single-line toast("...", true) calls with a literal message remain in frontend/js; some are expected conditions (validation, "nothing to ... yet")... | docs/roadmap/agent-remaining/OPEN.md:3303 | M | unassigned |
| 987 | 401s in the server log (/preferences, /insights/*, /reminders) when pages boot while sweeps unlock; not reproduced in one clean boot. (from... | docs/roadmap/agent-remaining/OPEN.md:3319 | S | unassigned |
| 988 | settings-packages.js (lines 421, 562 and 591 on this head): the toast call on result.message is red when the package action did not start (the flag... | docs/roadmap/agent-remaining/OPEN.md:3409 | M | unassigned |
| 989 | ai-tools.js says "Open Settings, Models" in words, and none is a link. A button on the toast is the next step and is a new control. (from... | docs/roadmap/agent-remaining/OPEN.md:3411 | S | unassigned |
| 990 | The reminders presets menu lays out while closed: 7 overlaps over the filter chips at 1440 (TIMELINE_PLAN 11 row 2). (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3428 | S | unassigned |
| 991 | Brief 5 (Timeline): TIMELINE_PLAN.md:7 names it as the plan's hand-off and the plan is open. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3439 | S | unassigned |
| 992 | Brief 6 (pagination, scheduler): tests/test_lists_paginate.py the brief names does not exist; TIMELINE_PLAN.md:93 depends on its helper. (from... | docs/roadmap/agent-remaining/OPEN.md:3440 | S | unassigned |
| 993 | Rule 4 "says what happened, why": 24 literal error toasts still fall back to Open the logs rather than an action of their own... | docs/roadmap/agent-remaining/OPEN.md:3519 | M | unassigned |
| 994 | Rule 4: the 338 toast(e.message, true) calls get the why from plainHttpError and the default Open the logs; a per-site retry is not built. | docs/roadmap/agent-remaining/OPEN.md:3520 | S | unassigned |
| 995 | Reminders: "Add" and "Mark done" push nothing (shell-reminders.js; 7 write functions, 3 with an undo path); Ctrl+Z restores neither. | docs/roadmap/agent-remaining/OPEN.md:3547 | S | unassigned |
| 996 | Documents: "Delete" shows a toast Undo, but Ctrl+Z goes to the open editor's history (surfaceHistory in status.js, the Documents branch) so the... | docs/roadmap/agent-remaining/OPEN.md:3548 | M | unassigned |
| 997 | "every weekday", "every other friday" and yearly repeats save once: routes_reminders.Recurring holds only daily, weekly and monthly; the Reading... | docs/roadmap/agent-remaining/OPEN.md:3575 | S | unassigned |
| 998 | Quick note: a reminder chip on a note saved while the server is away (the outbox, saveQuickNote's result.queued branch) is dropped; the note is kept.... | docs/roadmap/agent-remaining/OPEN.md:3578 | S | unassigned |
| 999 | Palette: only the reminder act has a row (quickAddPaletteRow); a note or meeting act and the search window chip (CHAT_PLAN section 1 row 7) wait for... | docs/roadmap/agent-remaining/OPEN.md:3579 | S | unassigned |
| 1000 | Timeline at 390: a long window chip wraps to two lines (39 px), no overflow. [f2-1010] | docs/roadmap/agent-remaining/OPEN.md:3580 | S | unassigned |
| 1001 | Agent: propose_act is offered in the reminder and tag tool groups only; whether a 1 to 3B model calls Calculate rather than computing is not verified... | docs/roadmap/agent-remaining/OPEN.md:3613 | S | unassigned |
| 1002 | pushDocAiUndo (documents.js:11084) already calls pushUndo; nothing to fold. It has no toast by design (the AI edit log is its second way back).... | docs/roadmap/agent-remaining/OPEN.md:3657 | S | unassigned |
| 1003 | Step 5b, decision 6 (a primary calendar paired with the reminders): TIMELINE_PLAN section 9 (Phase 5, Brief 55); renderReminderCalendar... | docs/roadmap/agent-remaining/OPEN.md:3666 | L | unassigned |
| 1004 | App scripts (TOTAL_CAP, the 27 counted) 320,352 to 317,151 (cap 320,600, unchanged): room 248 to 3,449. Moved to lazy files: the bell's panel... | agent/mergetrain-1011:docs/roadmap/agent-remaining/room101-1011.md:4 | M | unassigned |
| 1005 | 847 Notification actions on their own row: 0 actions share the close button's row at 1440 and 390. | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:8 | S | unassigned |
| 1006 | A server restart under an open page shows the toast "Locked" with "Open the logs" and "Report this" when a setting is changed (the PUT is silent, so... | agent/mergetrain-1011:docs/roadmap/agent-remaining/scan-1011.md:9 | M | unassigned |
| 1007 | A reminder needs text and a due time. (shell-reminders.js:1528) is shown when only one of the two is missing; naming the missing one needs... | agent/mergetrain-1011:docs/roadmap/agent-remaining/scan-1011.md:11 | S | unassigned |
| 1008 | The notification bell and Activity count: not a defect, but a fresh launch with no model lists "Warming up the filing model" every launch (one row... | agent/mergetrain-1011:docs/roadmap/agent-remaining/scan-1011.md:12 | M | unassigned |
| 1009 | 847: toasts built outside status.js (none found by grep) and the notification bell's rows (not changed). | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:21 | S | unassigned |
| 1010 | Timeline table rows: the hover ground is tr:hover td on a border-collapse: collapse table, so the row ends are square (06-timeline-dialogs.css:459)... | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:26 | S | unassigned |
| 1011 | Found, not mine: a sticky toast sits under an open modal (the first-run "Check for updates automatically?" confirm, z-index 2100), so Allow cannot be... | agent/mergetrain-1011:docs/roadmap/agent-remaining/lansafe-1011.md:46 | M | unassigned |
| 1012 | A reload loses the page's watch on a running transcription; the card still reads its state from the server, but no notification fires for a run that... | agent/voiceup-1011:docs/roadmap/agent-remaining/voiceup-1011.md:16 | S | unassigned |
| 1013 | Events as bands. Next: no events calendar table exists (the events in core/events.py is the change log, a different thing); it... | docs/roadmap/BACKLOG.md:697 | M | unassigned |
| 1014 | What the user can already see (the step timeline), so it stops re-narrating | docs/roadmap/BACKLOG.md:971 | S | unassigned |
| 1015 | Toasts and confirmations that name the thing ("Moved Passport renewal to the bin; it was linked to 3 notes"). | docs/roadmap/CHAT_PLAN.md:733 | S | unassigned |
| 1016 | Reminders and meetings: the action items and decisions read back as sentences; a reminder's notification says why it matters, from its note. | docs/roadmap/CHAT_PLAN.md:739 | S | unassigned |
| 1017 | Cheap suggestions: follow-up questions, suggested searches, autofill (titles, tags, reminder wording, link reasons) composed first; a model is asked... | docs/roadmap/CHAT_PLAN.md:754 | S | unassigned |
| 1018 | Proactive, rarely and on real signals: a few times a day at most, only for something specific (a due reminder, a resurfaced note, a pattern), never... | docs/roadmap/CHAT_PLAN.md:834 | S | unassigned |
| 1019 | "the notification said it takes a while to pull the first image for searxng but ive already used multiple times" Recommendation: show the first-pull... | docs/roadmap/CHAT_PLAN.md:853 | M | unassigned |
| 1020 | "Issues with these sentences: The picture in Girl with bell shows The image shows a snowy scene with a girl holding a bell, and there is a signature... | docs/roadmap/CHAT_PLAN.md:881 | M | unassigned |
| 1021 | INBOX 561 timeline day strip redesign: built in 543, waits on the owner's look | docs/roadmap/INBOX.md:37 | S | unassigned |
| 1022 | Briefs 2 to 6 (lints, prefs/api.stream, Settings two-pane, Timeline phases 1 and 2, pagination and one scheduler): unmarked; verify against the code, close or build | docs/roadmap/SESSION_BRIEFS.md:72 | M | unassigned |
| 1023 | "The circle on the vertical line on the left isnt in line with the text line" Recommendation: align the rail circle to the first line's centre in... | docs/roadmap/TIMELINE_PLAN.md:204 | S | unassigned |
| 1024 | Month and week grids, agenda on the phone. Month at 1024 and up, week at 768 and up, the feed (already an agenda) below that. The grid is CSS grid... | docs/roadmap/TIMELINE_PLAN.md:216 | M | unassigned |
| 1025 | What sits on the grid: reminders (at their time), day notes (as the cell's head), notes by their written date (dots, not rows, so the grid stays... | docs/roadmap/TIMELINE_PLAN.md:220 | M | unassigned |
| 1026 | Drag reschedules a reminder; dropping a note on a day sets its daily-note date only when it is a day note; anything else is refused with the hint.... | docs/roadmap/TIMELINE_PLAN.md:224 | S | unassigned |
| 1027 | ICS both ways for reminders only: export the reminders as one .ics (routes_reminders), import an .ics as reminders with a report; no account sync... | docs/roadmap/TIMELINE_PLAN.md:227 | S | unassigned |
| 1028 | Keys: T today, arrows move the day, PageUp/PageDown the month, Enter opens the day's feed, N a new reminder on the day. | docs/roadmap/TIMELINE_PLAN.md:230 | S | unassigned |
| 1029 | One calendar (INBOX 768, 2026-10-10): section 9's view is the one grid; the reminders tab's toggle opens it filtered to reminders, and... | docs/roadmap/TIMELINE_PLAN.md:232 | S | unassigned |
| 1030 | VC2, D3's time scale and axis for the timeline and the calendar (M, rank 2). timeline.js builds its date ticks by hand (51 lines with Date( in... | docs/roadmap/TIMELINE_PLAN.md:252 | M | unassigned |
| 1031 | "The whole begin the app for the first time workflow is a mess, popups and notifications clash with each other, the tour gets cancelled, to much goes... | docs/roadmap/UI_MODERNISATION_PLAN.md:1290 | M | unassigned |
| 1032 | 811, the owner, verbatim: "something about the design or smth of those buttons in the notifications and buttons in notifications in the noficiations... | docs/roadmap/UI_MODERNISATION_PLAN.md:1563 | L | unassigned |
| 1033 | 813, the owner, verbatim: "also idk but I feel like it looks awkward when some things have borders and other things dont in a header but idk im not... | docs/roadmap/UI_MODERNISATION_PLAN.md:1564 | M | unassigned |
| 1034 | Every destructive action has an Undo toast, not only deletes of notes. | docs/roadmap/WORLD_CLASS_PLAN.md:2368 | S | unassigned |
| 1035 | Every date and time follows one setting (12 or 24 hour, the locale's order); the status bar clock, the timeline and the reminders do not agree today... | docs/roadmap/WORLD_CLASS_PLAN.md:2369 | S | unassigned |
| 1036 | Toasts overlap content (the reminder toast covers the dashboard head at 1093x614); they belong in a reserved corner above the status bar. | docs/roadmap/WORLD_CLASS_PLAN.md:2391 | S | unassigned |
| 1037 | Dashboard widgets were counted for interactive elements in a notebook of plain notes (no reminders, bookmarks, tensions, activity); clicks were not... | docs/roadmap/agent-remaining/measure-1010.md:7 | S | unassigned |
| 1038 | Decision 32: only the recurrence insight; streak, drift, contrast, load and time-of-day rules, the Tidy and dashboard "Patterns" line, and the slot... | docs/roadmap/agent-remaining/spec39-1010.md:5 | S | unassigned |
| 1039 | Next PR first: INBOX 641 remainder (Illustrator linked symbols, Photoshop layer effects, Miro reactions), 643 OneNote, 644 meeting notes redesign, 646 code editor to VS Code standard | docs/ROADMAP.md:212 | L | unassigned |
| 1040 | Section: Phase 6: responsive by device (partly built) | docs/roadmap/DOCUMENTS_PLAN.md:314 | M | unassigned |
| 1041 | Section: Phase 8: one editor everywhere | docs/roadmap/DOCUMENTS_PLAN.md:396 | M | unassigned |
| 1042 | Section: Section 21: the code editor against VS Code, and writing checks everywhere (INBOX 646) | docs/roadmap/DOCUMENTS_PLAN.md:544 | L | unassigned |
| 1043 | Section: Section 17: the live view for professional use, phases open | docs/roadmap/DOCUMENTS_PLAN.md:1088 | L | unassigned |
| 1044 | Section: Section 23: the code editor as an IDE, phases after I1 to I3 (Briefs 69 to 71 landed) | docs/roadmap/DOCUMENTS_PLAN.md:1267 | L | unassigned |
| 1045 | BUILT earlier (notes-list.js topicRepeatsTag, tests/test_code_documents.py:345; found stale 2026-10-18, open-1018.md): A tag-named topic's chip repeats the tag chip beside it on the card (noteTopicChip, notes-list.js); dedupe against the card's own tags. | docs/roadmap/agent-remaining/OPEN.md:2026 | S | unassigned |
| 1046 | An uploaded document cannot be given a reading from outside the app. POST /media/{id}/ocr and /media/{id}/vision-ocr both answer 415 for a PDF... | docs/roadmap/agent-remaining/OPEN.md:2131 | L | unassigned |
| 1047 | .sidebar-head is off the dock grammar, deliberately. It carries min-height: var(--sidebar-toggle-size), a negative margin-top that meets the... | docs/roadmap/agent-remaining/OPEN.md:2165 | M | unassigned |
| 1048 | Band 3 (600 to 820): the header is two rows, 128px at 819. The band's recorded design (the strip cannot fit beside the wordmark at any width in the... | docs/roadmap/agent-remaining/OPEN.md:2176 | M | unassigned |
| 1049 | The capture box still moves 2.4px down and 1.6px left on the first click (strip 40 to 42.4px; CodeMirror line padding). | docs/roadmap/agent-remaining/OPEN.md:2268 | S | unassigned |
| 1050 | Open: a misspelled place ("westen australia") is not read. | docs/roadmap/agent-remaining/OPEN.md:2287 | S | unassigned |
| 1051 | The code document's dock at 390 is 238px tall (four rows). | docs/roadmap/agent-remaining/OPEN.md:2349 | S | unassigned |
| 1052 | A code file's editor is capped at 78ch and centred (09-editor.css:59), so its panel is 724px at 1440. | docs/roadmap/agent-remaining/OPEN.md:2432 | S | unassigned |
| 1053 | DOCUMENTS 24 row 7 (the list row's ⋮) not built: it would remake INBOX 722; keep the overlay. | docs/roadmap/agent-remaining/OPEN.md:2498 | S | unassigned |
| 1054 | BUILT 2026-10-18 (HISTORY, open-1018; the popover at 1440 for dock and find not opened by the sweep): DOCUMENTS 24 row 11: 78 controls, none with its own data-help-for; one '?' per section plus a command per control. | docs/roadmap/agent-remaining/OPEN.md:2499 | S | unassigned |
| 1055 | Replace in every document reads each document by one request; and it has no dock-menu row. | docs/roadmap/agent-remaining/OPEN.md:2501 | S | unassigned |
| 1056 | Statistics row 3 (VC3, Brief 75): the page's two charts use the hand-built askChartTicks; tick labels did not collide at 1440 or 390 with this data... | docs/roadmap/agent-remaining/OPEN.md:2563 | S | unassigned |
| 1057 | D1's folder again: the brief says frontend/js/run/debug-*.js; the pass is frontend/js/run-debug.js for ide1's reason (65 lints glob... | docs/roadmap/agent-remaining/OPEN.md:2576 | S | unassigned |
| 1058 | Variables show one level (a repr, 200 characters): no expanding a list or an object into its children (VS Code's tree). _mm_names in PY_RUNNER, show... | docs/roadmap/agent-remaining/OPEN.md:2577 | S | unassigned |
| 1059 | Python breakpoints persist per document for the tab's life (DOC_DEBUG.breaks), not across a reload; VS Code keeps them in the workspace. | docs/roadmap/agent-remaining/OPEN.md:2581 | S | unassigned |
| 1060 | F11 is shared: Step into while a session is on, Focus mode otherwise (documents.js); the palette row says "F11 while debugging". Brief 71's... | docs/roadmap/agent-remaining/OPEN.md:2583 | S | unassigned |
| 1061 | The breakpoint lane is 0.875rem wide (1.5rem under a coarse pointer); touch.js does not measure gutters, so a tap's size on it is not checked. | docs/roadmap/agent-remaining/OPEN.md:2584 | S | unassigned |
| 1062 | Debug (Brief 70) is a row of DOC_PANEL_TABS since the merge, its pane docDebugView(); Ctrl+Shift+D (the registry's newDocument... | docs/roadmap/agent-remaining/OPEN.md:2588 | M | unassigned |
| 1063 | "the problems panel fed by every linter": harper is a prose linter and prose documents have no panel (the panel is mounted for code files... | docs/roadmap/agent-remaining/OPEN.md:2589 | S | unassigned |
| 1064 | "the JS parse errors sucrase reports": Problems shows the editor's own JS and TS parse errors (the Lezer tree check, the same lines); sucrase's own... | docs/roadmap/agent-remaining/OPEN.md:2590 | M | unassigned |
| 1065 | A console line that never ends (while (true)) is stopped after 10 s (60 s for Python's first line) by terminating the worker, which loses the run's... | docs/roadmap/agent-remaining/OPEN.md:2592 | S | unassigned |
| 1066 | The split's second half carries the language, theme, gutter and wrap of the first, not its completions, lint, snippets or the run panel... | docs/roadmap/agent-remaining/OPEN.md:2593 | S | unassigned |
| 1067 | Ctrl+K Ctrl+S opens the palette for a moment before the sheet (the app's Ctrl+K is kept in code files); VS Code waits for the second chord instead. | docs/roadmap/agent-remaining/OPEN.md:2594 | S | unassigned |
| 1068 | Live Text on the continuous (scroll) layout of a PDF: only the single-page stage carries the layer. library.js ocrBuildScrollPages. | docs/roadmap/agent-remaining/OPEN.md:2598 | S | unassigned |
| 1069 | D5 "load this CSV document as a table": the sandbox's SQL worker takes tables: [{name, columns, rows}] (_SQL_WORKER), but no panel action picks a CSV... | docs/roadmap/agent-remaining/OPEN.md:2659 | S | unassigned |
| 1070 | D9 stdlib completion and signature help from a generated table (scripts/gen_python_completions.py over the installed Pyodide's inspect): not started. | docs/roadmap/agent-remaining/OPEN.md:2660 | S | unassigned |
| 1071 | D9 ruff-wasm lint and format: DOCUMENTS 25 row 4's (Brief 42's linters), not started here. | docs/roadmap/agent-remaining/OPEN.md:2661 | S | unassigned |
| 1072 | A JSX .js document (the jsx alias) runs without the JSX pass; only .tsx paths get it (runStripTypes). | docs/roadmap/agent-remaining/OPEN.md:2666 | S | unassigned |
| 1073 | evidence_checks is the one switch with no runner: stored and shown in Settings, gating nothing. margin_reader (api/routes_editor.py), model_bench... | docs/roadmap/agent-remaining/OPEN.md:2716 | M | unassigned |
| 1074 | codecomplete.md: Python Run via a Pyodide download extra (INBOX 404's recommendation, needs the owner's yes to a download kind of extra) and... | docs/roadmap/agent-remaining/OPEN.md:2783 | M | unassigned |
| 1075 | pass2.md: typing in a note in a 230-note list costs about 12ms of CodeMirror input handling per key; the Library's lists have no user-owned order to... | docs/roadmap/agent-remaining/OPEN.md:2833 | M | unassigned |
| 1076 | perfpolish.md: the document gutter writes a height and reads a layout per gutter. The menu exit is closed, HISTORY.md, "OPEN.md rows closed... | docs/roadmap/agent-remaining/OPEN.md:2838 | M | unassigned |
| 1077 | ARCH-02, the save at 5,000 notes: POST /entries p50 210 ms (one line) and 345 ms (400 words), not under 150; 390 to 615 ms with 384-wide vectors... | docs/roadmap/agent-remaining/OPEN.md:3031 | M | unassigned |
| 1078 | Sweeps: touch.js needs timeout 300; revealcell.js at 390 needs the editor opened first; errors.js took "Target crashed" at a tab switch (2026-10-05)... | docs/roadmap/agent-remaining/OPEN.md:3083 | M | unassigned |
| 1079 | A PDF's page picture was never seen drawn: this sandbox has no PDF render extra (pdfpages.available() is false, /media/pdf-page/... answers 404), so... | docs/roadmap/agent-remaining/OPEN.md:3232 | M | unassigned |
| 1080 | No screen reader was run against aria-current="location" in the documents outline. [doc-sidebar.md] | docs/roadmap/agent-remaining/OPEN.md:3239 | S | unassigned |
| 1081 | A real log stream under load. The live pill reads green and the filters hide the right count (275 records on the seeded server), but nothing here... | docs/roadmap/agent-remaining/OPEN.md:3260 | M | unassigned |
| 1082 | Undo counts for documents (2/11), OCR (0/5) and meetings (1/6) are a static read of each handler for pushUndo, not driven; Brief 74's undo.js... | docs/roadmap/agent-remaining/OPEN.md:3293 | S | unassigned |
| 1083 | At 1440 with the Connections rail open, the Notes dock wraps nine controls onto a second row; DESIGN.md says seven at most. A judgement for the dock... | docs/roadmap/agent-remaining/OPEN.md:3318 | S | unassigned |
| 1084 | DOC_EMOJI_SOURCE (documents-prose.js) is a second emoji table beside ICON_EMOJI_SOURCE (icon-picker.js). (from mc1.md) | docs/roadmap/agent-remaining/OPEN.md:3328 | S | unassigned |
| 1085 | Playwright reported the topic strip's Text toggle "not visible" after an icon pick, though its rect is 58px wide; mc1-iconpicker.js works around it... | docs/roadmap/agent-remaining/OPEN.md:3329 | S | unassigned |
| 1086 | An interrupted glide restarts at the ease's peak speed: a star's fastest step after a second Regenerate is 13 to 16px against 7px before it. A... | docs/roadmap/agent-remaining/OPEN.md:3375 | M | unassigned |
| 1087 | Settings, Packages has its own Embedding models list beside Search and index's, which does the same and more. Recommendation: Packages keeps a single... | docs/roadmap/agent-remaining/OPEN.md:3382 | S | unassigned |
| 1088 | A word touching a suggestion's marker is never a spelling finding: docSpellable (documents.js) rejects a + on either side, and {++ and ++} are +.... | docs/roadmap/agent-remaining/OPEN.md:3394 | M | unassigned |
| 1089 | The prose-tool grammar rules at a CodeMirror lint tooltip (.cm-tooltip-lint) in code documents are not suppressed while a pointer menu is open. Only... | docs/roadmap/agent-remaining/OPEN.md:3395 | S | unassigned |
| 1090 | The note strip, owner's report (d): every control is 6.4px inside the strip's edge at the default look (measured 320 to 1920). The owner's exact... | docs/roadmap/agent-remaining/OPEN.md:3400 | S | unassigned |
| 1091 | Each VC row is unbuilt; the script and test are the only code (Brief 75 says no code beyond them). (from vendor-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3434 | S | unassigned |
| 1092 | Brief 16 (documentation refined): no HISTORY record of the pass. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3446 | S | unassigned |
| 1093 | Cost: decide is 34 ms a call at 5,000 synthetic notes against 8 to 17 ms for the old tally (scratchpad/filing-tools/perf.py); Tidy's uncategorised... | docs/roadmap/agent-remaining/OPEN.md:3470 | S | unassigned |
| 1094 | Decision 43: the currency table is dated (utilities.RATES_DATE, src/memorymap/ai/utilities.py:113) but has no Settings editor. | docs/roadmap/agent-remaining/OPEN.md:3494 | S | unassigned |
| 1095 | Rule 5 "a long-running task that does not register fails": the lint is a table of thread sites (tests/test_activity.py THREAD_SITES); request-bound... | docs/roadmap/agent-remaining/OPEN.md:3521 | S | unassigned |
| 1096 | Word import of tracked changes: the .docx carries w:ins/w:del, but Mammoth reads an insertion as accepted text and drops a deletion... | docs/roadmap/agent-remaining/OPEN.md:3534 | M | unassigned |
| 1097 | A fenced code block's language (js) is not written to Word, so it comes back as a bare fence (docWordBlocks, the pre branch); header cells come back... | docs/roadmap/agent-remaining/OPEN.md:3535 | S | unassigned |
| 1098 | Docks: 0 sibling intersections in 12 surfaces at 5 widths (at 390: 81 bars and 266 sibling pairs examined), so the dock grammar holds; the counts... | docs/roadmap/agent-remaining/OPEN.md:3559 | S | unassigned |
| 1099 | Deeper than 3 (light): 4 Library > Contents > Probe documentDocument·# sections·#h ago > Outline. | docs/roadmap/agent-remaining/OPEN.md:3563 | S | unassigned |
| 1100 | Note editor: a sum only when written with = ("12 + 7 = 21"); a column of amounts with a "Total:" line is not checked (ai/offers.py _SUM). [f4-1010] | docs/roadmap/agent-remaining/OPEN.md:3605 | S | unassigned |
| 1101 | clip.html and capture.html keep unhashed ?v=<version> stamps (static, not rewritten as index.html and offline.html are), so an edit inside one... | docs/roadmap/agent-remaining/OPEN.md:3636 | S | unassigned |
| 1102 | Warm-load speed gain is inside the noise on a shared machine (466 to 570 ms against 613 to 672 ms) because stamped files were already immutable in... | docs/roadmap/agent-remaining/OPEN.md:3637 | M | unassigned |
| 1103 | 5 foreign keys without a leading index (entity_mentions x2, document_bookmarks x2, entry_bookmarks.bookmark_id) and 64 filtered columns without one... | docs/roadmap/agent-remaining/OPEN.md:3646 | M | unassigned |
| 1104 | editor.js:inlineAiUndo (owner's list of six): the inline AI bar's Undo reverts a CodeMirror transaction on unsaved field text, which rule 1.8 gives... | docs/roadmap/agent-remaining/OPEN.md:3655 | S | unassigned |
| 1105 | Decision 8, indent guides: the active line is built (library-lazy.css .cm-activeLineGutter); indent markers are not in the vendored CodeMirror bundle... | docs/roadmap/agent-remaining/OPEN.md:3667 | S | unassigned |
| 1106 | Brief 86's suggest code (status.js) should call meaningAlts for its candidates once it lands beside this. | agent/mergetrain-1011:docs/roadmap/agent-remaining/meaning94-1011.md:7 | S | unassigned |
| 1107 | scratchpad/ui-sweeps/notif1005-sweep.js still reads a .notif-side element that no longer exists (stale before this work); its checks of controls on... | agent/mergetrain-1011:docs/roadmap/agent-remaining/phonegraph-1011.md:8 | S | unassigned |
| 1108 | Sweep trap: context.route does not see requests the page's service worker serves (after the first load), so a CSS or JS override in a sweep silently... | agent/mergetrain-1011:docs/roadmap/agent-remaining/room101-1011.md:9 | M | unassigned |
| 1109 | Help's topics keep their document order when searching, so the best match by name can sit below others in the same filter (help top-3 38/60 against... | agent/mergetrain-1011:docs/roadmap/agent-remaining/meaning94-1011.md:15 | S | unassigned |
| 1110 | 853: a multi-region reading and a PDF with many pages (the seeded reading is one region); Tesseract is not installed here, the text was posted to... | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:20 | S | unassigned |
| 1111 | Document outline / table of contents, word-count goal, reading time, all three, not just the outline. renderDocOutline builds the... | docs/roadmap/BACKLOG.md:109 | M | unassigned |
| 1112 | Sizing (UI zoom #zoom-slider and Text size exist; Next: line-height and measure are two new tokens read by .entry-content and the... | docs/roadmap/BACKLOG.md:1124 | M | unassigned |
| 1113 | Study / revision: Next: nothing exists (no flashcard or review code in src/ or frontend/js, checked 2026-10-05); the seam is... | docs/roadmap/BACKLOG.md:1201 | M | unassigned |
| 1114 | Before adding more: audit which existing widgets render markdown and which don't (§8's ideas-parking-lot bug) so a new widget... | docs/roadmap/BACKLOG.md:1656 | S | unassigned |
| 1115 | Repair actions from that screen, not just a diagnosis: Next: SearXNG Reinstall and Settings, Models' pull exist; the buttons to... | docs/roadmap/BACKLOG.md:1708 | M | unassigned |
| 1116 | Sources outside the app. Next: Entry.source_url/source_title exist (note-cards.js:1859 draws the badge); the paste-a-highlight... | docs/roadmap/BACKLOG.md:2100 | L | unassigned |
| 1117 | Compression/archival for rarely-used notes, documents, files and chats. (needs owner) Pointer: the same decision as section 26... | docs/roadmap/BACKLOG.md:2302 | L | unassigned |
| 1118 | Web clipper. Pointer: WORLD_CLASS_PLAN D9 "Links and the web clipper"; the clipper agent owns it. read_url exists server-side... | docs/roadmap/BACKLOG.md:2414 | S | unassigned |
| 1119 | A Mermaid editor: a Live and Split view for a fence (source beside the drawing, errors inline with the line), snippets per kind... | docs/roadmap/BACKLOG.md:2602 | S | unassigned |
| 1120 | ATTACHMENT_SUFFIXES (routes_files.py) is broad: pdf/docx/xlsx/csv/md/ txt/code/zip. Attachments are downloaded, never served... | docs/roadmap/BACKLOG.md:2790 | S | unassigned |
| 1121 | MEDIA_SUFFIXES is images + PDF only, and its comment explains why: that folder is served, and *"the AI can write into this folder... | docs/roadmap/BACKLOG.md:2793 | M | unassigned |
| 1122 | *"No import from other note apps"*, overstated. POST /import/markdown and /import/directory (routes_settings.py) already... | docs/roadmap/BACKLOG.md:2901 | M | unassigned |
| 1123 | #search-help and #capture-help were bespoke hand-rolled click toggles from before initHelpToggle existed, never migrated: missing... | docs/roadmap/BACKLOG.md:3370 | M | unassigned |
| 1124 | The lightbox's document preview panel was translucent (var(--card), deliberately glass) sitting over the lightbox's own darkened... | docs/roadmap/BACKLOG.md:3392 | M | unassigned |
| 1125 | "Compose a document from these notes" (gap 10): Next: see section 102 item 10 and section 26. The agent can already do it from a... | docs/roadmap/BACKLOG.md:3581 | M | unassigned |
| 1126 | Live organise-suggestions while typing (gap 9): Next: see section 102 item 9. Offer it *alongside* the audited background... | docs/roadmap/BACKLOG.md:3584 | M | unassigned |
| 1127 | Bookmark URL editing, reported five times, working every time it was tested. The handler was correct and the flow was reproduced... | docs/roadmap/BACKLOG.md:3650 | L | unassigned |
| 1128 | Whether the selection popup should appear in the note editor at all is now moot: it does. What is *not* settled is its dismissal... | docs/roadmap/BACKLOG.md:3664 | M | unassigned |
| 1129 | Highlights as a queryable collection, backlinks panel, conflict-safe editor, per-note pinned AI context, bulk tag editing, all... | docs/roadmap/BACKLOG.md:3670 | M | unassigned |
| 1130 | Three places independently decide what markdown means: Next: one grammar module under frontend/js/ (a table of token, open... | docs/roadmap/BACKLOG.md:3701 | M | unassigned |
| 1131 | Decide whether the note editor is a text box or an editor. It now has a toolbar, a preview and a selection menu, while Documents... | docs/roadmap/BACKLOG.md:3746 | L | unassigned |
| 1132 | Three grammars for markdown (§111.1): Next: section 111.1 carries the brief. MD_ACTIONS, INLINE_MD, and editor.js's "/" menu each... | docs/roadmap/BACKLOG.md:3845 | M | unassigned |
| 1133 | Nothing that is broken. This session alone found a null dereference that silently aborted openConversation, a panel that opened... | docs/roadmap/BACKLOG.md:3861 | M | unassigned |
| 1134 | Note and document helpers: a summary line on a long note, "what links these two notes" on a link, a title suggestion from a note's own words. | docs/roadmap/CHAT_PLAN.md:737 | S | unassigned |
| 1135 | The same features in every surface: Live decorations, note autocomplete, the / menu, the selection toolbar (bold, italic, code, link, list, ask the... | docs/roadmap/DOCUMENTS_PLAN.md:420 | L | unassigned |
| 1136 | One recipe in 09-editor.css: .note-surface with the three size variants, the tokens' radius, --control-h for the strip, the same focus ring; a lint... | docs/roadmap/DOCUMENTS_PLAN.md:425 | S | unassigned |
| 1137 | The engine loads on the first focus of any surface, once per page. | docs/roadmap/DOCUMENTS_PLAN.md:431 | L | unassigned |
| 1138 | The chat composer is not a note editor: it gets and / only, and keeps its own recipe (send on Enter). | docs/roadmap/DOCUMENTS_PLAN.md:432 | S | unassigned |
| 1139 | Languages missing: Visual Basic (vb, vbScript legacy modes), p5.js (JS plus p5 completions from the vendored p5.min.js), PHP stays out (section... | docs/roadmap/DOCUMENTS_PLAN.md:554 | S | unassigned |
| 1140 | Per-language completions and snippets: CSS property values for the property under the cursor, Python, JS, Java, C#, C, C++ keywords and common forms... | docs/roadmap/DOCUMENTS_PLAN.md:557 | M | unassigned |
| 1141 | Where each is used: every code surface (documents, code blocks in notes, chat code, board code blocks) shares one engine and one set of options... | docs/roadmap/DOCUMENTS_PLAN.md:561 | L | unassigned |
| 1142 | Help moves with it (standing order 13). Measure with a Playwright sweep per language; no new required dependency (CLAUDE.md, the owner's offline... | docs/roadmap/DOCUMENTS_PLAN.md:564 | S | unassigned |
| 1143 | "I want to be able to use the documents tab as a plain text editor like before as a view option (not the default though)", "and also if I select a... | docs/roadmap/DOCUMENTS_PLAN.md:655 | L | unassigned |
| 1144 | "i still cant click on a grammar or misspeled underlined word and see a popup like in a realworld editor like obsidian, word, notion, vs code." It... | docs/roadmap/DOCUMENTS_PLAN.md:686 | M | unassigned |
| 1145 | "the whole documents sidebar and ui needs fixing and the document editor still needs a lot of refinement and cleaning but its still in development so... | docs/roadmap/DOCUMENTS_PLAN.md:713 | S | unassigned |
| 1146 | The page is a page. The text sits in a measure with real margins rather than filling its pane to the edge, and the margin is the same on both sides... | docs/roadmap/DOCUMENTS_PLAN.md:1126 | S | unassigned |
| 1147 | The measure is capped. A line of prose has a comfortable length and a wide monitor is not a reason to abandon it. | docs/roadmap/DOCUMENTS_PLAN.md:1129 | S | unassigned |
| 1148 | Nothing is added to the chrome. Every phase below either changes what is already drawn or reveals something on approach. | docs/roadmap/DOCUMENTS_PLAN.md:1131 | S | unassigned |
| 1149 | No new recipe without its lint, per standing order 11. | docs/roadmap/DOCUMENTS_PLAN.md:1133 | S | unassigned |
| 1150 | D1. One run protocol for every language: {kind, source, path, stdin, tests} in and {row, level, line, col} rows out, over postMessage to the sandbox... | docs/roadmap/DOCUMENTS_PLAN.md:1292 | M | unassigned |
| 1151 | D2. The Python debugger is bdb in the Pyodide worker, not a re-implementation: a Bdb subclass posts each stop (frame, line, locals, globals, the... | docs/roadmap/DOCUMENTS_PLAN.md:1297 | L | unassigned |
| 1152 | D3. The JavaScript debugger is JS-Interpreter (Neil Fraser, Apache-2.0, ES5, about 150 KB minified, pure JS, no network), vendored under... | docs/roadmap/DOCUMENTS_PLAN.md:1307 | M | unassigned |
| 1153 | D4. TypeScript runs: sucrase strips the types (no checking) and the row that said "does not compile" becomes "runs without type checking". The same... | docs/roadmap/DOCUMENTS_PLAN.md:1315 | S | unassigned |
| 1154 | D5. SQL runs against SQLite in the browser: sql.js (MIT, SQLite compiled to WASM, about 1.3 MB, lazy, measured first) under frontend/vendor/sqljs; a... | docs/roadmap/DOCUMENTS_PLAN.md:1318 | M | unassigned |
| 1155 | D6. Previews are a kind of run: .css previews against a sample document, .svg and .md render in the sandbox frame, .html as today, the p5 kind (INBOX... | docs/roadmap/DOCUMENTS_PLAN.md:1324 | M | unassigned |
| 1156 | D7. Tests are a kind of run: Python runs unittest discovery over the document (and pytest where the extra carries Pyodide's own pytest wheel... | docs/roadmap/DOCUMENTS_PLAN.md:1328 | M | unassigned |
| 1157 | D8. Two consoles: a Python REPL (Pyodide, the document's namespace after a run) and a JavaScript REPL (the worker's global after a run), as one panel... | docs/roadmap/DOCUMENTS_PLAN.md:1334 | M | unassigned |
| 1158 | D9. The Python improvements are deterministic and local: ruff-wasm for lint and format (Brief 42 decides vendoring on its size), stdlib completion... | docs/roadmap/DOCUMENTS_PLAN.md:1339 | M | unassigned |
| 1159 | The owner, 2026-09-21, verbatim: "can you improve the ui and ux of the live view and make it better for professional use and impressive as both a... | docs/roadmap/DOCUMENTS_PLAN.md:1454 | L | unassigned |
| 1160 | The owner, 2026-09-24, verbatim, with screenshots of Settings, Templates, the persona list, a .json document with the formatting bar over it, and the... | docs/roadmap/DOCUMENTS_PLAN.md:1489 | L | unassigned |
| 1161 | Live code blocks in a prose document (the owner, verbatim: "also I want to be able to make special code blocks where the code editor works and code... | docs/roadmap/DOCUMENTS_PLAN.md:1520 | M | unassigned |
| 1162 | "I cant two finger trackpad zoom in or out on documents or images on the ocr workspace?" Recommendation: pinch zoom (ctrl+wheel from a trackpad) on... | docs/roadmap/DOCUMENTS_PLAN.md:1536 | M | unassigned |
| 1163 | "The note capture subtab formatting toolbar wont open :(" Recommendation: reproduce from the Notes Capture subtab, then fix the toolbar's open state... | docs/roadmap/DOCUMENTS_PLAN.md:1538 | S | unassigned |
| 1164 | "Gemini might have removed the spell checker??" (the owner's words in the Gemini thread: "you removed spellchecker.py") Recommendation: keep... | docs/roadmap/DOCUMENTS_PLAN.md:1540 | M | unassigned |
| 1165 | "I saved a website as a bookmark but the icon didnt change" Recommendation: a saved bookmark takes the site's icon at save time and refreshes it on... | docs/roadmap/DOCUMENTS_PLAN.md:1542 | M | unassigned |
| 1166 | "on vs code selected lines have their line number bolded, the line subtly bordered and there are also indentation lines on vs code as well"... | docs/roadmap/DOCUMENTS_PLAN.md:1547 | M | unassigned |
| 1167 | "also I want a better and more cardlike rendering of links or special liks like bookmarks and maybe even the ability to choose special icons or... | docs/roadmap/DOCUMENTS_PLAN.md:1549 | M | unassigned |
| 1168 | "The document editor and whiteboard and mindmap still have many design issues, functionality bugs, poor usability, lack features, and need... | docs/roadmap/DOCUMENTS_PLAN.md:1551 | M | unassigned |
| 1169 | "And we should massively improve, expand, refine and better integrate long form note taking." Recommendation: the long-form path (document editor)... | docs/roadmap/DOCUMENTS_PLAN.md:1553 | M | unassigned |
| 1170 | "Idea: on long form notes and documents, you can define topics, or use special characters, commands etc to label and link sections of documents on... | docs/roadmap/DOCUMENTS_PLAN.md:1558 | M | unassigned |
| 1171 | BUILT 2026-10-18 (HISTORY.md, "OPEN.md rows closed, 2026-10-18 (open-1018)"; tag offers dropped, a document has no tags): VC5, FlashText link offers and tag offers (M, rank 5). FlashText is used by ai/taxonomy.py alone (2 of 19 members: add_keyword, extract_keywords)... | docs/roadmap/DOCUMENTS_PLAN.md:1566 | M | unassigned |
| 1172 | VC6, Harper's own dictionary and the other three dialects (S, rank 6). The worker uses 3 of 29 Linter members; import_words and export_words take a... | docs/roadmap/DOCUMENTS_PLAN.md:1567 | S | unassigned |
| 1173 | VC7, the diff and dockerFile modes already in the bundle (S, rank 7). legacy modes 15 of 18 called; diff, dockerFile and the sql factory are bundled... | docs/roadmap/DOCUMENTS_PLAN.md:1568 | S | unassigned |
| 1174 | VC13, the lint panel and fold-all in the palette (S, rank 13). lint is 5 of 12 (gutter and next/previous only; openLintPanel and lintKeymap unused)... | docs/roadmap/DOCUMENTS_PLAN.md:1569 | S | unassigned |
| 1175 | VC17, Emmet's stylesheet syntaxes (L, rank 17, lowest). Emmet is fully used (6 of 6 functions) but 4 of its 10 syntaxes are passed (html, css, xml... | docs/roadmap/DOCUMENTS_PLAN.md:1570 | L | unassigned |
| 1176 | documents.js holds 14 requestAnimationFrame sites, 7 scroll listeners, 3 ResizeObserver and 4 MutationObserver (WORLD_CLASS 26.5, scripts/handlers.py... | docs/roadmap/DOCUMENTS_PLAN.md:1574 | M | unassigned |
| 1177 | INBOX 788, the owner: "can you add code templates as document templates as well??", "maybe even add a code modules library like with the whiteboard... | docs/roadmap/DOCUMENTS_PLAN.md:1578 | M | unassigned |
| 1178 | INBOX 827, the owner 2026-10-11, verbatim (screenshots: a file's "Text extracted from this file" box; the empty Recordings tab; a link's details)... | docs/roadmap/DOCUMENTS_PLAN.md:1582 | M | unassigned |
| 1179 | L1. Extracted text: the disclosure is a quiet row (DESIGN "Row actions"), not a bordered button; open, the text sits in a reading column (body size... | docs/roadmap/DOCUMENTS_PLAN.md:1585 | S | unassigned |
| 1180 | L2. Recordings empty state from DESIGN's empty-state recipe: an icon, one line, Record and Import audio, and a second line saying a meeting's... | docs/roadmap/DOCUMENTS_PLAN.md:1586 | S | unassigned |
| 1181 | L3. A link's details: the card shows icon, title, site and a two-line excerpt; the full extract is behind "Show page text" in the L1 reader, never a... | docs/roadmap/DOCUMENTS_PLAN.md:1587 | S | unassigned |
| 1182 | L4. Folders: drag a link onto another to make a folder (named "Folder", renamed in place), drag into and out of folders, and New folder in the bar... | docs/roadmap/DOCUMENTS_PLAN.md:1588 | S | unassigned |
| 1183 | L5. Each link and folder takes an icon (the site's own, an app icon or an emoji) and a highlight colour from the palette tokens, from its kebab menu... | docs/roadmap/DOCUMENTS_PLAN.md:1589 | S | unassigned |
| 1184 | INBOX 735 p5.js as a document kind and code completion (DOCUMENTS_PLAN 23, Brief 42, Briefs 69 to 71) | docs/roadmap/INBOX.md:67 | M | unassigned |
| 1185 | INBOX 737 debugging for other languages (DOCUMENTS_PLAN 23 decisions D1 to D9, Brief 75 vendoring) | docs/roadmap/INBOX.md:77 | L | unassigned |
| 1186 | INBOX 804 console line border clash and the document assistant's buttons, field and send height (backups part fixed) | docs/roadmap/INBOX.md:159 | S | unassigned |
| 1187 | The lightbox is an image viewer showing a document. Reported: "the lightbox needs improving for file and pdf previews, no sections or info are below... | docs/roadmap/UI_MODERNISATION_PLAN.md:234 | M | unassigned |
| 1188 | Region select → read just that. Asked as a question, and it is a good one: "can there be a way for the user to manually outline and single out... | docs/roadmap/UI_MODERNISATION_PLAN.md:248 | M | unassigned |
| 1189 | The Files sub-tab has to show more than a row can hold. OCR text for a long document does not fit where a photo's caption fits; the row needs a... | docs/roadmap/UI_MODERNISATION_PLAN.md:256 | S | unassigned |
| 1190 | The command palette and Tools & features, and nothing new. Ctrl/Cmd-K reaches "Read a document or image with AI" from any tab, and the features... | docs/roadmap/UI_MODERNISATION_PLAN.md:285 | M | unassigned |
| 1191 | Everything you can do to a picture is a row of the card's kebab, not a control on it: open full size, copy the markdown reference, write a... | docs/roadmap/UI_MODERNISATION_PLAN.md:341 | S | unassigned |
| 1192 | Provenance is inside the fold, with the reading it describes. "Described by X, read by Y" has been called noise twice (INBOX 56 and the second design... | docs/roadmap/UI_MODERNISATION_PLAN.md:354 | S | unassigned |
| 1193 | The description holds its second line open (min-height: 2lh while clamped, picture cards only). A one-line caption left the card 21.8px shorter... | docs/roadmap/UI_MODERNISATION_PLAN.md:380 | M | unassigned |
| 1194 | "I pressed install on the documents package and the progress bars appeared for the vision package and the documents package didn’t progress at all"... | docs/roadmap/UI_MODERNISATION_PLAN.md:1255 | M | unassigned |
| 1195 | "Also it failed to let me view the pdf doc I had as the package wasn’t installex, it should have given me a link to nav to where I can install it or... | docs/roadmap/UI_MODERNISATION_PLAN.md:1257 | M | unassigned |
| 1196 | "idk if it is just me but the ui still needs a more modern and professional polish. I think an issue might be that some of the ui elements, controls... | docs/roadmap/UI_MODERNISATION_PLAN.md:1278 | M | unassigned |
| 1197 | "There needs to be more utility on all features app wide and more ui/ux cleansing" Recommendation: this is the Brief 41 refinement pass plus the... | docs/roadmap/UI_MODERNISATION_PLAN.md:1294 | L | unassigned |
| 1198 | INBOX 788, UI and features, documents and code, the owner 2026-10-10 22:35Z, six screenshots. "the topic edit popup needs a redesign and fix. are... | docs/roadmap/UI_MODERNISATION_PLAN.md:1537 | L | unassigned |
| 1199 | T1. Tidy is one list of reviews with counts; a review opens in place with a back link (not a bordered button beside a small title), its one-line... | docs/roadmap/UI_MODERNISATION_PLAN.md:1590 | S | unassigned |
| 1200 | T4. A menu's first and last items sit one menu padding from its edge, never a group label's or a separator's gap (owner: grammar57, with 813's one... | docs/roadmap/UI_MODERNISATION_PLAN.md:1593 | S | unassigned |
| 1201 | Deleting a space leaves its notes in "All spaces". Read and not reproduced in code: routes_spaces.delete_space hard-deletes every workspace-scoped... | docs/roadmap/WORLD_CLASS_PLAN.md:1544 | L | unassigned |
| 1202 | Suggested links panel UI refine (screenshot: rows of quoted pairs, a wide "Why?" input, a percent chip, Link and X). Owner: Opus, next slot: two note... | docs/roadmap/WORLD_CLASS_PLAN.md:1592 | M | unassigned |
| 1203 | The feature list is inside #models-config, which Settings hides whole when no backend is answering. So with the model server down there is no way to... | docs/roadmap/WORLD_CLASS_PLAN.md:2269 | M | unassigned |
| 1204 | Ctrl+S, Ctrl+Z and Escape behave the same in every editor and dialog (the key contract, 1.6, has no lint for Escape yet). | docs/roadmap/WORLD_CLASS_PLAN.md:2364 | S | unassigned |
| 1205 | Search highlights the match inside the note it opens, and remembers the last few queries. | docs/roadmap/WORLD_CLASS_PLAN.md:2366 | S | unassigned |
| 1206 | Icon consistency. Mixed stroke weights between Phosphor regular and the bold ones on the status bar; one weight app-wide. | docs/roadmap/WORLD_CLASS_PLAN.md:2387 | S | unassigned |
| 1207 | Frontend ids are every id="..." text in index.html, including any inside HTML comments; not checked for false hits. | docs/roadmap/agent-remaining/codemap-1010.md:6 | S | unassigned |
| 1208 | tests/test_frontend_wake_sources.py: documents.js raf 14 to 15. | docs/roadmap/agent-remaining/graphfeel-1010.md:16 | S | unassigned |
| 1209 | Root cause of the line, as reproduced: the Layout preference holds Tree or Arc (mirrored server-side, MIRRORED_UI_EXTRAS in ai-tools.js), both... | docs/roadmap/agent-remaining/graphfeel-1010.md:20 | M | unassigned |
| 1210 | Decision 37: map, document and web-page sources; scrollable web source list. | docs/roadmap/agent-remaining/spec39-1010.md:9 | S | unassigned |
| 1211 | The Gemini misspelling table looks drawn from Wikipedia's lists (CC BY-SA); its origin is unrecorded (docs/THIRD_PARTY.md, Data). | docs/roadmap/agent-remaining/triage-1010.md:33 | S | unassigned |
| 1212 | Section: Audio in the notebook: architecture decided, build deferred (partly built by Brief 80, 82, 83, voiceup) | docs/roadmap/WORLD_CLASS_PLAN.md:2135 | L | unassigned |
| 1213 | Section: 28.4 and 28.5 deepened: OCR workspace and audio set rows (Briefs 79, 80 landed; rest open) | docs/roadmap/WORLD_CLASS_PLAN.md:4106 | L | unassigned |
| 1214 | The README's OCR shot is the 0.3.2 capture, in dark: seed-ocr.js (removed 2026-10-12, recoverable from git history) needs a Tesseract binary this sandbox does not have, so it was not retaken with the... | docs/roadmap/agent-remaining/OPEN.md:1962 | S | unassigned |
| 1215 | INBOX 803 item 4 (the OCR workspace's empty squashed box): not reproduced in five states; needs the owner's screenshot or state. | docs/roadmap/agent-remaining/OPEN.md:2267 | S | unassigned |
| 1216 | The recorder saves plain transcript text into the meeting note; the timed lines live only on the recording. /voice/transcribe-meeting still returns... | docs/roadmap/agent-remaining/OPEN.md:2356 | S | unassigned |
| 1217 | The attached-image thumbnail path in the preview (attachmentObjectUrl) was not driven, only inline images. | docs/roadmap/agent-remaining/OPEN.md:2466 | S | unassigned |
| 1218 | Notes cannot link to or embed a recording yet (only entry_id); search does not find recordings. | docs/roadmap/agent-remaining/OPEN.md:2479 | S | unassigned |
| 1219 | Trim decodes the whole file in the page (about 700 MB of samples for an hour). | docs/roadmap/agent-remaining/OPEN.md:2480 | S | unassigned |
| 1220 | Live captions is a palette act, so it cannot be a Quick access tile. | docs/roadmap/agent-remaining/OPEN.md:2481 | S | unassigned |
| 1221 | Brief 81: the stop path is now meetingRecordingStopped; transcription goes through POST /recordings/{id}/transcribe. | docs/roadmap/agent-remaining/OPEN.md:2482 | S | unassigned |
| 1222 | Live translated captions (28.5 row 10, "for ... captions") not built: Brief 82 landed mid-build. | docs/roadmap/agent-remaining/OPEN.md:2489 | S | unassigned |
| 1223 | Only English to Spanish: more pairs are a download block plus a PAIRS row, and the sheet then needs a pair picker. | docs/roadmap/agent-remaining/OPEN.md:2490 | S | unassigned |
| 1224 | Real latency: scratchpad/captions_audio.py through a real whisper-server on the reference laptop (pytest -m captions tests/test_captions_live.py)... | docs/roadmap/agent-remaining/OPEN.md:2506 | M | unassigned |
| 1225 | Accuracy under a cut audio_ctx was read on one sentence only. | docs/roadmap/agent-remaining/OPEN.md:2507 | S | unassigned |
| 1226 | Stop saves a note until Brief 80's recording object lands; then routes_captions._save attaches the audio and makes the transcript its text; the Audio... | docs/roadmap/agent-remaining/OPEN.md:2508 | S | unassigned |
| 1227 | ScriptProcessorNode is deprecated; an AudioWorklet needs a blob: worker the CSP does not allow (captions.js startLiveCaptions). | docs/roadmap/agent-remaining/OPEN.md:2509 | S | unassigned |
| 1228 | A regions cache stored before 2026-10-10 has no words; Live Text appears after the page is read again. routes_files.py PageRead.regions. | docs/roadmap/agent-remaining/OPEN.md:2599 | S | unassigned |
| 1229 | An image's whole reading deleted from the lightbox or the gallery's row menu still clears without the bin (only the workspace's deletes were moved).... | docs/roadmap/agent-remaining/OPEN.md:2600 | M | unassigned |
| 1230 | Undoing a fresh read writes the old text back through the text route, so it keeps the new read's model name ("Read by X") rather than the old one's.... | docs/roadmap/agent-remaining/OPEN.md:2601 | S | unassigned |
| 1231 | undo.js (the trust sweep) does not walk the OCR workspace; ocr79.js measures it instead. | docs/roadmap/agent-remaining/OPEN.md:2602 | S | unassigned |
| 1232 | ocr-reading.md: a page joins the reading panel only once looked at or read (nothing reads ahead, deliberately); nothing was verified with a real... | docs/roadmap/agent-remaining/OPEN.md:2829 | M | unassigned |
| 1233 | Owner's call: RapidOCR ships as an optional extra (Settings, Packages); confirm it against the 2026-10-05 "fully local, vendored" rule... | docs/roadmap/agent-remaining/OPEN.md:3314 | S | unassigned |
| 1234 | Pills still in popups: the Attach picker's five sources (#note-picker-sources, index.html:2842) and pickLibraryItemDialog's sources (selection.js)... | docs/roadmap/agent-remaining/OPEN.md:3343 | M | unassigned |
| 1235 | If the owner means every pill in a popup, these values are next (kept as .seg by DESIGN.md's two-or-three rule): doc-history-filter, ocr-zoom... | docs/roadmap/agent-remaining/OPEN.md:3344 | M | unassigned |
| 1236 | Touch drag from the Library is not tested: HTML5 drag-and-drop does not run on touch. The drag image (its thumbnail and offset) is asserted in source... | docs/roadmap/agent-remaining/OPEN.md:3366 | S | unassigned |
| 1237 | RapidOCR and Tesseract never ran for real here: "ready" and the RapidOCR path are faked through /ocr-readers and monkeypatched tests. A real install... | docs/roadmap/agent-remaining/OPEN.md:3376 | S | unassigned |
| 1238 | Meeting cards show their section headings as raw ## Agenda text, as every note card does. A meeting-aware card preview (when, who, open action items)... | docs/roadmap/agent-remaining/OPEN.md:3406 | S | unassigned |
| 1239 | 852 Library sub-tab flicker: layout shift 0.37 to 0.52 became 0.017 (1440) and 0.016 (390). | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:6 | S | unassigned |
| 1240 | Left in the counted scripts, each used by two bundles so it needs a shared home or a stand-in: noteFirstImage (library.js only, move with... | agent/mergetrain-1011:docs/roadmap/agent-remaining/room101-1011.md:7 | S | unassigned |
| 1241 | 853 OCR find marks every match, "n of m", Enter and Shift+Enter, prev and next buttons. | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:9 | S | unassigned |
| 1242 | library-activity rows keep their ground in a box-shadow spine, not a background. | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:27 | S | unassigned |
| 1243 | One commit per item was not kept for V1 with V2 and V3 to V7: a staged gate took 12 to 25 minutes under load, so items sharing meetings.js were gated... | agent/voiceup-1011:docs/roadmap/agent-remaining/voiceup-1011.md:10 | S | unassigned |
| 1244 | The plan's Built blocks for V1 to V8, T1, T2 (UI_MODERNISATION_PLAN "Placed from INBOX, 2026-10-11 (voice notes ...)" and "(Tidy ...)") move to... | agent/voiceup-1011:docs/roadmap/agent-remaining/voiceup-1011.md:11 | S | unassigned |
| 1245 | Real transcription: faster-whisper is not installed; every run used a stubbed voice.iter_segments (vu/stubserve.py), and live words used... | agent/voiceup-1011:docs/roadmap/agent-remaining/voiceup-1011.md:14 | S | unassigned |
| 1246 | It would compete for the same CPU. The compression path wants ONNX Runtime and a transformer of its own, running immediately... | docs/roadmap/BACKLOG.md:722 | M | unassigned |
| 1247 | Voice capture beyond dictation. Next: mic-note dictates into the capture box and Save files it (two clicks); a one-tap "record a... | docs/roadmap/BACKLOG.md:2428 | M | unassigned |
| 1248 | A persona changes *voice* and applies to everything. | docs/roadmap/BACKLOG.md:2515 | S | unassigned |
| 1249 | Route by type at upload time: an image goes to media/ (served, narrow allowlist, unchanged), anything else goes to the... | docs/roadmap/BACKLOG.md:2803 | M | unassigned |
| 1250 | Widen MEDIA_SUFFIXES and harden serving (explicit Content-Type, Content-Disposition: attachment, a sandboxed CSP on that route).... | docs/roadmap/BACKLOG.md:2808 | M | unassigned |
| 1251 | A live "rough bullets + transcript → merged note" capture flow Next: frontend/js/media.js's meeting overlay gets a bullets... | docs/roadmap/BACKLOG.md:2911 | L | unassigned |
| 1252 | Basic local speaker separation on a transcript Next: faster-whisper does not diarize and a diarization library pulls torch... | docs/roadmap/BACKLOG.md:2957 | M | unassigned |
| 1253 | .library-subtabs button was more rounded than .notes-subtabs button, traced to cascade order, not a missing class: a global... | docs/roadmap/BACKLOG.md:3397 | M | unassigned |
| 1254 | Speaker labelling on transcripts (gap 12): Next: same decision as section 102 item 8 (the owner). Transcription is already local... | docs/roadmap/BACKLOG.md:3573 | S | unassigned |
| 1255 | Speaker labelling on transcripts. Next: the owner's call, section 102 item 8. Transcription is already local, so "Speaker 1/2/3"... | docs/roadmap/BACKLOG.md:3729 | S | unassigned |
| 1256 | Tidy and filing: every reason ("filed under Work because…") in one voice. | docs/roadmap/CHAT_PLAN.md:741 | S | unassigned |
| 1257 | Brief 87 (vendor candidates, voice and dictation): research table added; Opus build of what to vendor unassigned | docs/roadmap/SESSION_BRIEFS.md:1742 | L | unassigned |
| 1258 | It opens on a file rather than on a picker, in this order: the file you last had open in it, else the most recently added readable file, else the... | docs/roadmap/UI_MODERNISATION_PLAN.md:292 | M | unassigned |
| 1259 | Four verbs, without opening anything: open it in the reader (the row's one filled control), save a copy of the original, rename, delete. The last... | docs/roadmap/UI_MODERNISATION_PLAN.md:316 | S | unassigned |
| 1260 | "there's no option to have the ocr workspace in the quick access section in the dashboard, it also isnt accessible in the cmd palatte or find... | docs/roadmap/UI_MODERNISATION_PLAN.md:1288 | M | unassigned |
| 1261 | INBOX 790, UI and bug, the owner 2026-10-10 22:40Z, three screenshots. "can you resesign or restyle these buttons in the ocr workspace header??" then... | docs/roadmap/UI_MODERNISATION_PLAN.md:1539 | M | unassigned |
| 1262 | Tab bar scrolls between 600 and 819px; short tab captions below 480 are a copy decision for the owner. Owner: responsive.md. | docs/roadmap/WORLD_CLASS_PLAN.md:976 | S | unassigned |
| 1263 | #library-media-refresh is misnamed; Settings has two heading indents. Owner: docks.md. | docs/roadmap/WORLD_CLASS_PLAN.md:988 | S | unassigned |
| 1264 | Files sub-tab rows "could still use a massive redesign upgrade", and clicking the file name does nothing. Owner: Library dossier (WORLD_CLASS 4)... | docs/roadmap/WORLD_CLASS_PLAN.md:1587 | L | unassigned |
| 1265 | OCR alternative to pytesseract, asked directly. Answer: RapidOCR (PaddleOCR models on onnxruntime, pip-installable, no system binary, better on... | docs/roadmap/WORLD_CLASS_PLAN.md:1597 | M | unassigned |
| 1266 | Drag and drop of files onto any page imports them (Library only today). | docs/roadmap/WORLD_CLASS_PLAN.md:2372 | S | unassigned |
| 1267 | "Filing and suggested tags and categories and stuff need a lot of improving. Should we include a library of common possible categories and even ways... | docs/roadmap/WORLD_CLASS_PLAN.md:3119 | L | unassigned |
| 1268 | "I think meeting notes should be different or at least partially separate from dictation and audio transcribing. Can there be an auto captioning and... | docs/roadmap/WORLD_CLASS_PLAN.md:3123 | M | unassigned |
| 1269 | "are there any other libraries that could be used that I and u havent found or mentioned??" Recommendation: the candidate-library table in Brief 40... | docs/roadmap/WORLD_CLASS_PLAN.md:3130 | S | unassigned |
| 1270 | Five proposed decisions (computed values, no archive verb, dated currency table, playful voice waits, model picks among readings) are for the... | docs/roadmap/agent-remaining/assistant-1010.md:12 | M | unassigned |
| 1271 | "Clear dismissed suggestions" does not reach per-note "Not suggested" tags; changes are noted only while Settings is open (the top-bar theme button... | docs/roadmap/agent-remaining/OPEN.md:2226 | M | unassigned |
| 1272 | Free lines and arrows (not links) still draw the shaft through hollow ends: their stored path is re-read as the endpoints, so trimming would drift... | docs/roadmap/agent-remaining/OPEN.md:2339 | S | unassigned |
| 1273 | Suggesting tags from a note's own words for a notebook with no tags yet scored 4 of 12 and was not shipped. | docs/roadmap/agent-remaining/OPEN.md:2373 | S | unassigned |
| 1274 | The Connections unlinked-mention Link button is still a bordered ghost button; the tool-confirm pair is untouched. | docs/roadmap/agent-remaining/OPEN.md:2406 | S | unassigned |
| 1275 | Link-label blur not reproduced headless; the re-raster after zoom is untested on a GPU compositor or the desktop webview. | docs/roadmap/agent-remaining/OPEN.md:2413 | S | unassigned |
| 1276 | The sidebar's Comments, Linked from and Notes rows keep their old styling. | docs/roadmap/agent-remaining/OPEN.md:2434 | S | unassigned |
| 1277 | After Undo the run, the per-write stack entries stay; a later Ctrl+Z re-runs an already applied inverse (harmless for pin, tag and edit).... | docs/roadmap/agent-remaining/OPEN.md:2517 | S | unassigned |
| 1278 | **Fixed 2026-10-19.** Dashboard quick links overflow by 4 px at 1440 and 390 (#dash-quicklinks .launch-group). | docs/roadmap/agent-remaining/OPEN.md:2520 | S | unassigned |
| 1279 | The More sheet on a map is 59 to 62 rows at 390 (the table plus the map palette); grouped by hairlines but long. A search field or the palette's own... | docs/roadmap/agent-remaining/OPEN.md:2552 | S | unassigned |
| 1280 | EntryLink rows are counted whole: a link to a binned or private note is still a link on the page (_notebook_block). | docs/roadmap/agent-remaining/OPEN.md:2568 | S | unassigned |
| 1281 | The other search surfaces still do their own thing Closed. The account is in HISTORY.md, "OPEN.md rows closed, 2026-10-05 (the open-ledger pass)". | docs/roadmap/agent-remaining/OPEN.md:2693 | S | unassigned |
| 1282 | maptheme.md: the theme is resolved into each node on export rather than carried; an <arrowlink> written by FreeMind itself is untested. [maptheme]... | docs/roadmap/agent-remaining/OPEN.md:2817 | M | unassigned |
| 1283 | wbtopbar.md: #wb-search-toggle and #wb-navigator-toggle duplicate View menu switches (UI_MODERNISATION_PLAN Phase 8 names them as the bar's find... | docs/roadmap/agent-remaining/OPEN.md:2848 | L | unassigned |
| 1284 | The capture draft counts as unsaved work, so every tab switch with a draft asks "Leave without saving?" though the draft is kept and the switch loses... | docs/roadmap/agent-remaining/OPEN.md:3025 | S | unassigned |
| 1285 | Retrieval and the learned loop, plan rows whose half-built parts live in the scratchpad: "most opened this month" is parked in... | docs/roadmap/agent-remaining/OPEN.md:3060 | M | unassigned |
| 1286 | Retrieval and the learned loop, plan rows: the "wrong" correction on an evidence card (I7's second half) and I1 pass 2's kinds as derived facts... | docs/roadmap/agent-remaining/OPEN.md:3071 | M | unassigned |
| 1287 | Every cosine number in the retrieval work came from the 4-dimensional fake. A real backend is 384-dimensional, anisotropic, and its embed_text per... | docs/roadmap/agent-remaining/OPEN.md:3205 | L | unassigned |
| 1288 | Owner (2026-10-07), a fresh install's search model: an empty or partial models--BAAI--bge-small-en-v1.5 folder is treated as present, the load runs... | docs/roadmap/agent-remaining/OPEN.md:3335 | M | unassigned |
| 1289 | Owner (2026-10-07): the app repairs a broken or missing search-model cache itself. On EmbeddingCacheBroken, start the reinstall as a visible... | docs/roadmap/agent-remaining/OPEN.md:3338 | M | unassigned |
| 1290 | Owner (2026-10-07): each embedding row shows its real state (Downloaded with its size on disk, Not downloaded, or Files missing with Reinstall). The... | docs/roadmap/agent-remaining/OPEN.md:3339 | M | unassigned |
| 1291 | renderAutonomousSettings fills the Models-pane checkboxes only when Background tasks or Web search opens (settings.js, per the file, about line 158)... | docs/roadmap/agent-remaining/OPEN.md:3340 | M | unassigned |
| 1292 | Autonomous with no model running ends "Finished analysing and linking notes." in 65 ms; it should say it had no model (check agent.run_agent for a... | docs/roadmap/agent-remaining/OPEN.md:3341 | S | unassigned |
| 1293 | Older sweeps that expect note rows in the palette (grep palette-input): ux1005-palette.js (removed 2026-10-12, recoverable from git history) and search1005-lazy.js read command rows only, and... | docs/roadmap/agent-remaining/OPEN.md:3380 | S | unassigned |
| 1294 | Stop part way: the night shift, the backup, resurfacing and the embeddings backfill are each one call with no step to stop at. Only housekeeping... | docs/roadmap/agent-remaining/OPEN.md:3381 | M | unassigned |
| 1295 | /entries/{id}/related lists notes that are already linked, so a press on one answers 400 "already linked" (pre-existing). (from tidy691-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3404 | S | unassigned |
| 1296 | Notes keep the old updated_at rule (any write moves it): edited_at answers "when a person changed it", but lexical_filing... | docs/roadmap/agent-remaining/OPEN.md:3433 | M | unassigned |
| 1297 | Row 4 measured on a seeded notebook (13 notes), not the report's: title-only icon controls in the Notes list 54 to 0 at 1440, 21 to 0 at 390. Other... | docs/roadmap/agent-remaining/OPEN.md:3461 | M | unassigned |
| 1298 | Decision 6 says "the pack's flag": the pack has none. The 49 sensitive topics are MemoryMap's own list in... | docs/roadmap/agent-remaining/OPEN.md:3464 | S | unassigned |
| 1299 | The data path: section 23 says src/memorymap/ai/data/taxonomy/, section 26 decision 56 says src/memorymap/data/; section 23's was followed. (from... | docs/roadmap/agent-remaining/OPEN.md:3465 | S | unassigned |
| 1300 | Decision 4, "alternate names come from the pack's labels and the person's own titles": only the pack's labels (entry/tidy.py _rows_category_names).... | docs/roadmap/agent-remaining/OPEN.md:3466 | S | unassigned |
| 1301 | Decision 4's centroid test needs the search model; with it off the merge review uses topics alone at 0.8 and says so in the row... | docs/roadmap/agent-remaining/OPEN.md:3467 | S | unassigned |
| 1302 | The tag picker on an empty field puts the tags the note says first ("training 10 notes, in this note"), but on a note that says none of them it still... | docs/roadmap/agent-remaining/OPEN.md:3471 | M | unassigned |
| 1303 | The model's tag reply is grounded against a faked reply (tests/test_tag_grounding.py); what a real small model answers is not verified. (from... | docs/roadmap/agent-remaining/OPEN.md:3472 | S | unassigned |
| 1304 | Brief 42's other items not started: highlights on pages, comments with bookmarks and links, link cards with a viewer, the long-form preference at... | docs/roadmap/agent-remaining/OPEN.md:3539 | S | unassigned |
| 1305 | Counts scale with the number of seeded notes (the notes list repeats one finding per card): the table in 28.4 was taken on 13 to 23 notes. | docs/roadmap/agent-remaining/OPEN.md:3560 | S | unassigned |
| 1306 | Brief 47's "the sidebar's search field routes here": the Notes sidebar has no search field; the no-match Search everything button and the... | docs/roadmap/agent-remaining/OPEN.md:3599 | S | unassigned |
| 1307 | Import cost 3.3 s against decision 56's 1.5 s: ai.autonomous pulls ai.agent (503 ms), ai.help_chat 271 ms, api.routes_search 226 ms. Brief 62.... | docs/roadmap/agent-remaining/OPEN.md:3647 | S | unassigned |
| 1308 | Sweeps: touch.js reports Settings appearance and privacy "did not open" (section names moved); overlap.js still counts 4 px rows on #notes-tidy... | docs/roadmap/agent-remaining/OPEN.md:3671 | S | unassigned |
| 1309 | Neighbours barely follow a drag (measured: notes with 4 to 5 links move 20 to 50 of the 340 units the note in hand does, then return to their... | agent/graph100-1011:docs/roadmap/agent-remaining/graph100-1011.md:20 | M | unassigned |
| 1310 | tests/test_properties_never_in_previews.py::test_the_dashboards_note_widgets_read_past_the_block (dashboard.js no longer has the stripFrontmatter... | agent/graph100-1011:docs/roadmap/agent-remaining/graph100-1011.md:30 | S | unassigned |
| 1311 | tests/test_ownerfix_1011.py::test_a_link_row_underlines_its_words_not_its_icon (ValueError: substring not found). | agent/graph100-1011:docs/roadmap/agent-remaining/graph100-1011.md:31 | S | unassigned |
| 1312 | Filing against a model that never answers is serial and slow (measured, a stand-in server that holds every request): a burst of 20 notes saved the... | agent/mergetrain-1011:docs/roadmap/agent-remaining/scan-1011.md:6 | L | unassigned |
| 1313 | A note created without defer_filing holds a database connection for the whole model wait. Twenty such POST /entries at once against the stand-in (the... | agent/mergetrain-1011:docs/roadmap/agent-remaining/scan-1011.md:7 | L | unassigned |
| 1314 | 888 pinch: handles (resize, rotate, link ends) still start their own d3-drag on a second finger; they are cancelled by wbCancelGesture but a second... | agent/mergetrain-1011:docs/roadmap/agent-remaining/phone2-1011.md:9 | S | unassigned |
| 1315 | 854 Filing style is a span like Categories and Tags; lint on every .setting-label head. | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:10 | S | unassigned |
| 1316 | Close in meaning against a real embedding model: no torch in the sandbox; the route is tested with a letter-count embedder and the page with... | agent/mergetrain-1011:docs/roadmap/agent-remaining/meaning94-1011.md:11 | S | unassigned |
| 1317 | Found, not fixed (base, not my files): tests/test_undo_contract.py (settings-data.js:settingsHistoryUndo), tests/test_inbox_435.py (tags field... | agent/mergetrain-1011:docs/roadmap/agent-remaining/phone2-1011.md:11 | M | unassigned |
| 1318 | Browse: web search results, reader view, page history | docs/roadmap/BACKLOG.md:188 | S | unassigned |
| 1319 | Treemap / sunburst: area as weight, so a category with 200 notes looks like one. Best for "where does my writing actually go?"... | docs/roadmap/BACKLOG.md:605 | M | unassigned |
| 1320 | Subway map: orthogonal edges, categories as lines. Beautiful and genuinely hard: it needs edge routing, which is real work rather... | docs/roadmap/BACKLOG.md:622 | M | unassigned |
| 1321 | Sea chart: islands per category, notes as landmarks, links as shipping routes, unlinked notes adrift. Parchment palette pairs... | docs/roadmap/BACKLOG.md:634 | M | unassigned |
| 1322 | Retrieved notes are re-sent in full on every turn, including turns that are a follow-up to the previous answer and need no new... | docs/roadmap/BACKLOG.md:906 | L | unassigned |
| 1323 | That a search snippet is rarely enough and read_url exists | docs/roadmap/BACKLOG.md:970 | S | unassigned |
| 1324 | Query expansion: two or three phrasings, results fused. Next: search/websearch.py:329 (search_web) takes one query; add a... | docs/roadmap/BACKLOG.md:1008 | M | unassigned |
| 1325 | A global quick-capture hotkey in desktop mode. Not asked for directly, but the app's own pitch, "just capture, a local AI files... | docs/roadmap/BACKLOG.md:1171 | L | unassigned |
| 1326 | Multi-category is a schema change, entries.category_id becomes a join table (entry_categories), and the janitor's cheap match (§4... | docs/roadmap/BACKLOG.md:1616 | M | unassigned |
| 1327 | Manual grouping, kept genuinely separate from categories/tags, is smaller: a collections table and a join table, with no AI... | docs/roadmap/BACKLOG.md:1622 | M | unassigned |
| 1328 | "#wb-search unwired, P0 bug", already deleted, 993e639 (see ROADMAP.md §0/§1). | docs/roadmap/BACKLOG.md:1956 | S | unassigned |
| 1329 | Email-in. Next: a decision for the owner: an IMAP poll is a second outbound connection, and routes_settings.py:220 and... | docs/roadmap/BACKLOG.md:2416 | M | unassigned |
| 1330 | A live, inline organization suggestion while typing Next: ai/passive_capture.py and frontend/js/tag-suggest.js are the nearest... | docs/roadmap/BACKLOG.md:2962 | L | unassigned |
| 1331 | Suggested-link reasons, the thing "Explain your existing links" was reported as not doing (it never could: see that button's own... | docs/roadmap/BACKLOG.md:3415 | M | unassigned |
| 1332 | Search-result grouping by category/tag, with counts, Next: GET /search (api/routes_search.py) already returns each hit's kind and... | docs/roadmap/BACKLOG.md:3614 | M | unassigned |
| 1333 | /entries/link-suggestions/reasons is sequential. Up to twelve model round-trips one after another in a threadpool endpoint.... | docs/roadmap/BACKLOG.md:3692 | M | unassigned |
| 1334 | Filing costs a model round-trip per capture since the order was reversed. Now a preference (ai_first_filing), so this is a... | docs/roadmap/BACKLOG.md:3697 | M | unassigned |
| 1335 | "Like this is somewhat a hobby but it is also about ai, local llms and other things." Recommendation: context for the scope of... | docs/roadmap/BACKLOG.md:4169 | M | unassigned |
| 1336 | Does a first install need the internet? Yes, once, and the app says so in one place only. README.md (line about "The first launch... | docs/roadmap/BACKLOG.md:4228 | L | unassigned |
| 1337 | Search and Find anything: a one-line answer above the results when the query is a question. | docs/roadmap/CHAT_PLAN.md:735 | S | unassigned |
| 1338 | "Also if I click the "not about [this tag], don’t show this again", is there a way to undo it or see the list of things not to show again for... | docs/roadmap/CHAT_PLAN.md:928 | M | unassigned |
| 1339 | "also should accessed web links in the sources dropdown be lised at the top of the sources??" Recommendation: sort accessed web links to the top of... | docs/roadmap/CHAT_PLAN.md:933 | M | unassigned |
| 1340 | Brief 39b: filing and the taxonomy (WORLD_CLASS_PLAN 23) | docs/roadmap/SESSION_BRIEFS.md:1305 | M | unassigned |
| 1341 | Notes. Capture as a full-height sheet from the floating + button; the list as full-width rows with swipe actions (pin, bin) matched to the row's menu... | docs/roadmap/UI_MODERNISATION_PLAN.md:637 | L | unassigned |
| 1342 | Every existing id and data-section is kept. A deep link that names a control is resolved to the section that holds the control now (openSettingsModal... | docs/roadmap/UI_MODERNISATION_PLAN.md:1154 | S | unassigned |
| 1343 | INBOX 767, the no-model notice. One row at 1440 (icon, one short sentence, the action as a link-styled button, the X at the end), wraps to two only... | docs/roadmap/UI_MODERNISATION_PLAN.md:1241 | S | unassigned |
| 1344 | "is it possible to add and customise the metadata a little more??" Recommendation: custom note properties, shown in the metadata rows with one... | docs/roadmap/UI_MODERNISATION_PLAN.md:1270 | M | unassigned |
| 1345 | "also I think the topbar is a little large but idk maybe not. maybe research design principles or standards?? ensure wcag 2.2 accessibility is... | docs/roadmap/UI_MODERNISATION_PLAN.md:1280 | M | unassigned |
| 1346 | INBOX 830, the owner 2026-10-11, verbatim (Tidy's "Category names" review, empty; Patterns rows with Confirm and Not right; "Recent runs (3)"): "this... | docs/roadmap/UI_MODERNISATION_PLAN.md:1587 | L | unassigned |
| 1347 | 1024px still wraps the Writing Room controls and the capture attachment row. Owner: consistency.md. | docs/roadmap/WORLD_CLASS_PLAN.md:974 | S | unassigned |
| 1348 | "Still lots of issues with filing without the ai model running but it should still work right because the embedding model is running??" / "I filed a... | docs/roadmap/WORLD_CLASS_PLAN.md:3094 | M | unassigned |
| 1349 | "just continue and research categories and tags etc. make it extensive and also dynamic. some categories for example might not just be "gym" or... | docs/roadmap/WORLD_CLASS_PLAN.md:3121 | M | unassigned |
| 1350 | Decision 30 kinds not asserted: duration, link, plan, polarity, topic, list_item; inherited-date flag; fact cache by entry_edited_at. | docs/roadmap/agent-remaining/spec39-1010.md:3 | S | unassigned |
| 1351 | Decision 31: only recall, tag and source kind are specified; the other answer kinds (comparison, why, how, status, recommendation) and length wish... | docs/roadmap/agent-remaining/spec39-1010.md:4 | S | unassigned |
| 1352 | Decision 39: filing and link explanation lines. | docs/roadmap/agent-remaining/spec39-1010.md:11 | S | unassigned |
| 1353 | "Study and university tags are suggested on the top note if it has no tags no matter what the note is about" (the owner, 2026-10-10): not reproduced... | docs/roadmap/agent-remaining/triage-1010.md:23 | M | unassigned |
| 1354 | Section: B2 job runtime (durable, resumable), B6 local-first sync (design now), B7 API contract, B8 extensions | docs/roadmap/WORLD_CLASS_PLAN.md:535 | L | unassigned |
| 1355 | Measured on synthetic rows and one real destination; the status ring under "auto" motion not measured. | docs/roadmap/agent-remaining/OPEN.md:2244 | S | unassigned |
| 1356 | The first load after the upgrade has no ui-synced mark, so a stale second browser pushes its look to the notebook once. | docs/roadmap/agent-remaining/OPEN.md:2308 | S | unassigned |
| 1357 | Not checked in the desktop webview profile or on a second machine. | docs/roadmap/agent-remaining/OPEN.md:2309 | S | unassigned |
| 1358 | The bin row's long label wraps when its reset appears; theme, palette, accent and zoom keep their own resets (no per-row marker). | docs/roadmap/agent-remaining/OPEN.md:2324 | S | unassigned |
| 1359 | The owner's line was a saved Tree or Arc layout (synced, static by design). Recommendation: name the current layout on the map as one dock chip... | docs/roadmap/agent-remaining/OPEN.md:2395 | S | unassigned |
| 1360 | A 5,000-note import takes 45.9 s: each note commits on its own. | docs/roadmap/agent-remaining/OPEN.md:2423 | S | unassigned |
| 1361 | Binned notes import with their old deleted_at, so the startup purge removes expired ones at the next restart. | docs/roadmap/agent-remaining/OPEN.md:2424 | S | unassigned |
| 1362 | Stop is between steps, not mid-call: a step whose model call has already returned still writes when Stop lands during the call (the sync generator's... | docs/roadmap/agent-remaining/OPEN.md:2516 | S | unassigned |
| 1363 | deepen72a.js's shared overlap measure now ignores a clipped scrolling edge, so other surfaces' overlap counts may drop; undo.js was not run on the... | docs/roadmap/agent-remaining/OPEN.md:2521 | S | unassigned |
| 1364 | JavaScript constructs not lowered for the stepper (classes, destructuring, spread and rest, for...of, default parameters, async and generators, ??... | docs/roadmap/agent-remaining/OPEN.md:2579 | M | unassigned |
| 1365 | Sync (B6) as log shipping. id: events-sync. Unstarted and no longer blocked: it needed the retention rule, which now exists. A compacted snapshot... | docs/roadmap/agent-remaining/OPEN.md:2703 | M | unassigned |
| 1366 | world-class-rows-1-2-9.md: two decisions taken differently from Brief 15 (S1 is a cookie, S3 confines to home and the data folder) that the owner may... | docs/roadmap/agent-remaining/OPEN.md:2857 | M | unassigned |
| 1367 | Package bundles: the Word writer's five tests ran once in a scratch venv with python-docx 1.2.0 (2026-10-05, tests/test_docexport_pictures.py 13 of... | docs/roadmap/agent-remaining/OPEN.md:2916 | M | unassigned |
| 1368 | Smaller backend and gate rows: a note type made through POST /note-types before the list was read, then deleted, loses its id on Undo (not... | docs/roadmap/agent-remaining/OPEN.md:3074 | M | unassigned |
| 1369 | No pre-Brief-7 database was upgraded. Both migrations are exercised by the suite and written to be idempotent, but a real year-old file was never... | docs/roadmap/agent-remaining/OPEN.md:3195 | M | unassigned |
| 1370 | wbSyncMapStrip sets a themed field's effective value onto the select, so a topic following the map shows the map's look pressed rather than ringed... | docs/roadmap/agent-remaining/OPEN.md:3401 | M | unassigned |
| 1371 | Settings, every switch and choice: 13 pressed, 0 undone by Ctrl+Z (settings-controls.js has the only pushUndo; 48 write functions in settings*.js and... | docs/roadmap/agent-remaining/OPEN.md:3546 | S | unassigned |
| 1372 | dashboard.js:undoActorFrom / activityUndoControl (and their two helpers) and note-history.js:undoSkillRun: an undo of the AI's changes through POST... | docs/roadmap/agent-remaining/OPEN.md:3656 | M | unassigned |
| 1373 | No backup schedule "shown with the last success" (WORLD_CLASS 4018 row) beyond Settings, About, Health's last backup line. [safety-1010] | docs/roadmap/agent-remaining/OPEN.md:3660 | S | unassigned |
| 1374 | move_notes to a space can reuse routes_spaces.py's move_notes_to_space, once that body is lifted into a shared helper.... | docs/roadmap/BACKLOG.md:1088 | S | unassigned |
| 1375 | Async httpx client: Next: section 78 says the sync routes are correct, so this is optional; measure first with... | docs/roadmap/BACKLOG.md:1295 | M | unassigned |
| 1376 | Archive: already scoped in §4 item 2 (an archived_at column, additive migration). This section doesn't repeat it, just notes it's... | docs/roadmap/BACKLOG.md:1736 | S | unassigned |
| 1377 | A real storage breakdown, not just the database file. Asked for directly: "can the user see a visual depiction of the storage... | docs/roadmap/BACKLOG.md:1747 | L | unassigned |
| 1378 | Note compression: asked for directly, and worth being honest about the payoff before building it. Notes are short text in SQLite... | docs/roadmap/BACKLOG.md:1784 | M | unassigned |
| 1379 | AI-readability additions: Pointer: scratchpad/audit1005/features.md Phase G (FEAT-12 tools; the outline export is row C14 to C18... | docs/roadmap/BACKLOG.md:1996 | M | unassigned |
| 1380 | A Readwise/Kindle importer: Pointer: the imports agent (section 115 row 1 is the importer set; Readwise is not on it, so size it... | docs/roadmap/BACKLOG.md:2106 | M | unassigned |
| 1381 | Sync / multi-device. It is the most-asked-for thing in every notebook app and it is the one that would break this one: the app's... | docs/roadmap/BACKLOG.md:2490 | M | unassigned |
| 1382 | Mobile apps and sync. The offline, single-machine promise is the product. Sync is a distributed-systems project that would... | docs/roadmap/BACKLOG.md:3886 | M | unassigned |
| 1383 | INBOX 805 backups: mark the latest, date in words, what made it, size, checked; one process ledger for every AI and background run (transparency) | docs/roadmap/INBOX.md:170 | M | unassigned |
| 1384 | T2. Recent runs is a quiet disclosure row (DESIGN "Row actions"), not a full-width bordered box. | docs/roadmap/UI_MODERNISATION_PLAN.md:1591 | S | unassigned |
| 1385 | T3. A confirmed or rejected pattern keeps an Undo on its row and in "What it learned" (owner: learnaudit, with decision 68). | docs/roadmap/UI_MODERNISATION_PLAN.md:1592 | S | unassigned |
| 1386 | Data safety is there but hidden. Backups exist (routes_backups.py), revisions exist (EntryRevision), export exists, but none is on the Dashboard or... | docs/roadmap/WORLD_CLASS_PLAN.md:2351 | M | unassigned |
| 1387 | Section: Phase 12: density, refinement and WCAG 2.2 remainder (density agent left rows; see OPEN) | docs/roadmap/UI_MODERNISATION_PLAN.md:1013 | L | unassigned |
| 1388 | Section: Settings information architecture (INBOX 444): decisions made, build status unverified | docs/roadmap/UI_MODERNISATION_PLAN.md:1112 | M | unassigned |
| 1389 | Section: Deepened statistics, utilities, palette and Find anything (Brief 72b rows; built parts moved) | docs/roadmap/UI_MODERNISATION_PLAN.md:1444 | L | unassigned |
| 1390 | tests/test_name_mood.py asserts oklch(from var(--accent) in the CSS: it holds (the accent tints the glow), but a test for the fixed palette would be... | docs/roadmap/agent-remaining/OPEN.md:1899 | M | unassigned |
| 1391 | The dashboard scroll jump (426 u) was not reproduced by wheel, idle or any scroll call; if it recurs, scrolljump.js with the owner's preferences... | docs/roadmap/agent-remaining/OPEN.md:1947 | M | unassigned |
| 1392 | The View menu is 714px of content on a map. Under about a 730px-tall window it still scrolls, which is correct and may still read as the report. If... | docs/roadmap/agent-remaining/OPEN.md:2081 | M | unassigned |
| 1393 | "spacing is really close ... bunched up" on insert: gaps measured 26px before and after on both layouts; only the branch's jump to the end was found... | docs/roadmap/agent-remaining/OPEN.md:2117 | S | unassigned |
| 1394 | The Dashboard hero is deferred by the owner, not by judgement. Do not touch .dash-hero, .dash-wordmark, .dash-greeting, .dash-clock* in... | docs/roadmap/agent-remaining/OPEN.md:2188 | M | unassigned |
| 1395 | At 25% zoom the 20px + overlaps its parent by about 5px; radial and tree-down layouts not driven. | docs/roadmap/agent-remaining/OPEN.md:2260 | S | unassigned |
| 1396 | Design, for Briefs 57 to 59: the Notes dock has 10 items; Tidy's "40" is a pill badge; 177 controls sit off the 28/32/44 height steps (a 36px family... | docs/roadmap/agent-remaining/OPEN.md:2276 | S | unassigned |
| 1397 | settings-reset is in no help group (test_help_coverage.py). | docs/roadmap/agent-remaining/OPEN.md:2278 | S | unassigned |
| 1398 | maplayouts.js "tree-left carries the branch bar" fails on base too (it measures the centre topic). | docs/roadmap/agent-remaining/OPEN.md:2294 | S | unassigned |
| 1399 | The 14 browser-only appearance settings do not follow you to a second browser: decided (WORLD_CLASS 25f, placed 2026-10-11): mirror them all except... | docs/roadmap/agent-remaining/OPEN.md:2322 | S | unassigned |
| 1400 | **Fixed 2026-10-19.** smallButton (app.js) names every worded button by its tooltip (WCAG 2.5.3); only the first-steps buttons are fixed. | docs/roadmap/agent-remaining/OPEN.md:2330 | S | unassigned |
| 1401 | Most used in the sidebar keeps a binned note for up to 30 s (status.js cacheMs). | docs/roadmap/agent-remaining/OPEN.md:2331 | S | unassigned |
| 1402 | The first-run queue (welcome, recovery key, updates) costs 3 acts before the dashboard. | docs/roadmap/agent-remaining/OPEN.md:2332 | S | unassigned |
| 1403 | Still open from uipolish: the rows-view 28px meta button in a 24px line, the tool-confirm pair, lowering BOOT_CSS_CAP. | docs/roadmap/agent-remaining/OPEN.md:2341 | S | unassigned |
| 1404 | .dash-find is the one glyph-only hover left; a rows-view meta icon button is 28px in a 24px line. | docs/roadmap/agent-remaining/OPEN.md:2405 | S | unassigned |
| 1405 | BOOT_CSS_CAP can be lowered now that strip_css drops comment-leftover lines (about 7 KB freed). | docs/roadmap/agent-remaining/OPEN.md:2407 | S | unassigned |
| 1406 | The Background jobs Report button waits for boot room; the Activity panel at 390 is translucent. | docs/roadmap/agent-remaining/OPEN.md:2426 | S | unassigned |
| 1407 | A Settings row whose element is a label or head is focused as that element, not its control ("Accent colour" lands on its DIV at both widths)... | docs/roadmap/agent-remaining/OPEN.md:2540 | S | unassigned |
| 1408 | The learned order is exact words only; Raycast also learns prefixes. Recommendation (take it): add the prefix with half weight once picks have a week... | docs/roadmap/agent-remaining/OPEN.md:2541 | S | unassigned |
| 1409 | Acts with no stem start with the example's first word ("remind ", "note: "); a stem per act in act_registry._ACTS would read better but adds rows to... | docs/roadmap/agent-remaining/OPEN.md:2542 | S | unassigned |
| 1410 | Row 8 (rule 6): "every rail and top-bar control has a data-help-for popover and a palette row; 0 missing". Not built. A first count from the DOM... | docs/roadmap/agent-remaining/OPEN.md:2650 | M | unassigned |
| 1411 | errors.js at 1440 and 390: 0 errors, 0 layout findings each. | docs/roadmap/agent-remaining/OPEN.md:2654 | S | unassigned |
| 1412 | 110 distinct controls show no change on keyboard focus (a11yname.js, 312 stops over 14 surfaces): every .status-item, the .ghost.small buttons, the... | docs/roadmap/agent-remaining/OPEN.md:2673 | M | unassigned |
| 1413 | The markup has 18 overlays plus the built confirm and the tour card, not the plan's 15; $S/design/hierarchy.json lists each with its size (Brief 59... | docs/roadmap/agent-remaining/OPEN.md:2676 | S | unassigned |
| 1414 | mapread.md and maprender.md: 13g, the haywire middle-button pan, needs the owner (it never reproduced headless; do not fix blind); the 50-topic open... | docs/roadmap/agent-remaining/OPEN.md:2811 | M | unassigned |
| 1415 | The frontend audit's leftovers (scratchpad/audit1005/frontend.md (removed 2026-10-12, recoverable from git history)): FE-09 unused CSS (no coverage-driven deletion started); FE-10 Settings panes'... | docs/roadmap/agent-remaining/OPEN.md:3052 | M | unassigned |
| 1416 | Not verified: Quit's 0.72 opacity contrast is computed (about 3.1:1 light, 5:1 dark), not read from pixels; the line numbers' baseline drop is... | docs/roadmap/agent-remaining/OPEN.md:3089 | S | unassigned |
| 1417 | How the dark palette reads on an OLED panel or at another display gamma, and the luminance column glassdepth.js takes, which was not re-run after the... | docs/roadmap/agent-remaining/OPEN.md:3229 | S | unassigned |
| 1418 | Write with AI was measured with the model off, so "Draft it" is disabled and the draft box is empty in every measurement. The column heights are the... | docs/roadmap/agent-remaining/OPEN.md:3256 | M | unassigned |
| 1419 | Help popovers close at once: a popover goes home and is removed on close, which cancels its exit transition. (from motion-1005.md) | docs/roadmap/agent-remaining/OPEN.md:3306 | S | unassigned |
| 1420 | A sub-tab's panel does not cross-fade; only its line slides. CSS cannot tell a section switch from a page arriving; it needs a class set by... | docs/roadmap/agent-remaining/OPEN.md:3307 | S | unassigned |
| 1421 | 444 decision 10, still open: the Tools (4,247px) and Appearance (1,296px) panes are indexed, not split. (from op4-1005.md) | docs/roadmap/agent-remaining/OPEN.md:3312 | S | unassigned |
| 1422 | Doc-focus panels between 720 and 819px cover the page, as below 720 did before; not driven in a sweep. (from op5-1005.md) | docs/roadmap/agent-remaining/OPEN.md:3315 | S | unassigned |
| 1423 | scroll-padding: a control focused by Tab in a scroller is scrolled to the edge with its ring half cut. scroll-padding: var(--ring-room) on .tab-page... | docs/roadmap/agent-remaining/OPEN.md:3346 | S | unassigned |
| 1424 | /jobs/last-runs is polled after a lock and answers 401 once or twice per lock (forgotpw.js's refused list). Next: stop the poll in lockNow and... | docs/roadmap/agent-remaining/OPEN.md:3368 | M | unassigned |
| 1425 | tests-e2e/specs/shell.spec.js has a handoff test that has only had node --check; Playwright's runner has not run it. (from palette666-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3379 | S | unassigned |
| 1426 | The owner's second screenshot showed a stray circle after the hover buttons on an opened row. Not reproduced at 1440, 1920 or 390, light or dark... | docs/roadmap/agent-remaining/OPEN.md:3390 | S | unassigned |
| 1427 | The Notes dock wraps to two rows from about 1280 to 1500 with the connections rail open (90px); Tidy's 40px extends that band to about 1640. Moving... | docs/roadmap/agent-remaining/OPEN.md:3402 | M | unassigned |
| 1428 | Brief 32 (templates and base layouts): deferred by the owner; BACKLOG 4b carries the standing row. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3450 | S | unassigned |
| 1429 | 745 (d): the hover-only tour step reveal is built nowhere (tour.js has no hover handling). (from coverage-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3452 | S | unassigned |
| 1430 | design-1010 row 5, 110 controls with no focus change (a11yname.js focus pass): Brief 57, decision 15. (from a11yfix-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3458 | S | unassigned |
| 1431 | Row height at 1440 is 46.8px, not "one line plus padding" (about 38px): the Connect button's 28.8px target floor sets the row. Left as is; shrinking... | docs/roadmap/agent-remaining/OPEN.md:3479 | S | unassigned |
| 1432 | Rule 14: the Health block stays in Settings, About (where it was built, PLAN B9) rather than its own section; reach is the palette's Health (1) and... | docs/roadmap/agent-remaining/OPEN.md:3525 | S | unassigned |
| 1433 | Not reached by the sweep: right-click menus, keyboard-only acts (Tab for a branch), controls that open a picker and then need a second choice (note... | docs/roadmap/agent-remaining/OPEN.md:3552 | M | unassigned |
| 1434 | #select-btn span.dock-word 40px and #notes-filter-menu span.dock-word 32px clipped at 320 to 1024: the labelled-to-icon collapse hides words by... | docs/roadmap/agent-remaining/OPEN.md:3556 | S | unassigned |
| 1435 | **Fixed 2026-10-19.** button#notes-tidy.ghost.small 4px at every width; #tab-notes div.layout 4px at 320 to 1024. | docs/roadmap/agent-remaining/OPEN.md:3557 | S | unassigned |
| 1436 | Dashboard: 3 overflow and 1 clipped text at 320 and 390, 2 overflow at 820 and wider (selectors in the sweep output, not yet named here). | docs/roadmap/agent-remaining/OPEN.md:3558 | S | unassigned |
| 1437 | Crawl: 55 destinations found from the dashboard (1, 14, 36, 3 and 1 at depths 0 to 4, crawl complete to depth 4), 1 deeper than 3, 16 with no palette... | docs/roadmap/agent-remaining/OPEN.md:3561 | M | unassigned |
| 1438 | The crawl presses navigation-looking controls only and one item of each repeated list; a destination absent from it is "not found by the crawl", not... | docs/roadmap/agent-remaining/OPEN.md:3564 | M | unassigned |
| 1439 | Palette rows from the registry: acts.palette_rows (src/memorymap/ai/acts.py) has no caller and palette.js still lists its own starters; a route and... | docs/roadmap/agent-remaining/OPEN.md:3585 | S | unassigned |
| 1440 | Settings: the synonym groups and the filler list are a hand table (filters.SETTING_WORDS, SETTING_FILLER), measured on 10 phrases in the browser; no... | docs/roadmap/agent-remaining/OPEN.md:3611 | S | unassigned |
| 1441 | The plan row names a "Versions" row; the note menu's existing row is "History" (versions plus every other event). Not renamed: a rename moves help in... | docs/roadmap/agent-remaining/OPEN.md:3658 | S | unassigned |
| 1442 | Decision 1, panel padding 12 and sidebar gutter 8: not measured or moved; the Notes dock wraps to two rows at 1440 (86 px). [density-1010] | docs/roadmap/agent-remaining/OPEN.md:3669 | S | unassigned |
| 1443 | Failing on the base commit, not touched: test_finder_star_790 (expects a clip-path star, the CSS draws a mask), test_has_invalidation (22 unkeyed... | agent/mergetrain-1011:docs/roadmap/agent-remaining/room101-1011.md:8 | M | unassigned |
| 1444 | 856 Hover-ground lint and sweep (see below); the owner's element was not found. | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:11 | S | unassigned |
| 1445 | 856: tests/test_hover_grounds_have_a_radius.py is a class-level scan with a reviewed list; it cannot see an element whose corner comes from a parent... | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:15 | S | unassigned |
| 1446 | Dark mode and 390 px beyond errors.js (0 errors, 0 layout findings at 1440 and 390, light and dark), contrast.js, docks.js, touch.js and chrome.js. | agent/mergetrain-1011:docs/roadmap/agent-remaining/scan-1011.md:17 | S | unassigned |
| 1447 | 851: rows view at 390 (the view toggle is hidden there) and the dark theme for the tick's colours were not measured; cards at 390 dark were. | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:19 | S | unassigned |
| 1448 | Measured (Playwright at 390, X-Forwarded-For: 192.168.0.50 against :8893): data-other-device=1, 12 note lines, #quit-btn display none, a marked... | agent/secscan-1011:docs/roadmap/agent-remaining/secscan-1011.md:39 | M | unassigned |
| 1449 | Getting one error OUT of the log (asked for directly after the console landed: "make sure that if there is an error in the log... | docs/roadmap/BACKLOG.md:50 | L | unassigned |
| 1450 | The JSON it would compress is the JSON that cannot be compressed. This one was worth measuring rather than assuming, and the... | docs/roadmap/BACKLOG.md:727 | M | unassigned |
| 1451 | More themes and palettes (#palette-grid; Next: a "surprise me" is a seeded pick of accent, palette and density from the existing... | docs/roadmap/BACKLOG.md:1128 | M | unassigned |
| 1452 | Live preview while hovering a theme, before committing. Next: applySavedTheme writes through appearancePref; a hover preview... | docs/roadmap/BACKLOG.md:1136 | M | unassigned |
| 1453 | Task management: Next: a decision for the owner, not a build; checklists in notes already feed the Unfinished widget... | docs/roadmap/BACKLOG.md:1199 | M | unassigned |
| 1454 | A screen-reader pass: Pointer: section 115 row 4 of this file (WCAG AA and an axe pass, gate a11yname.js, contrast.js, touch.js)... | docs/roadmap/BACKLOG.md:1285 | M | unassigned |
| 1455 | Opt-in retention rules: "forgetting," not just "archiving." Archive above is a manual action; nothing today acts on a note's age... | docs/roadmap/BACKLOG.md:1774 | L | unassigned |
| 1456 | A swatches/saved-palette panel: Pointer: scratchpad/audit1005/features.md section 4 row C9 and section 8.2 kind 3 (saved styles... | docs/roadmap/BACKLOG.md:1986 | M | unassigned |
| 1457 | §88.4 item 3 ("memory is a surface, not a system") Pointer: PLAN.md row A3 ("Memory with provenance"; Settings, The AI, What it... | docs/roadmap/BACKLOG.md:2853 | M | unassigned |
| 1458 | Gallery kebab stayed open over the rename field. The close-on-pick listener was on the bubble phase, with a comment explaining... | docs/roadmap/BACKLOG.md:3627 | S | unassigned |
| 1459 | The Regenerate-greeting button wrapping onto its own line. The (usually empty) status span had flex: 1 1 auto, giving it a 178px... | docs/roadmap/BACKLOG.md:3646 | M | unassigned |
| 1460 | The suite is 2,700 tests and ~8 minutes. Still fine; worth watching. The lints (test_style_scale, test_frontend_ids... | docs/roadmap/BACKLOG.md:3848 | S | unassigned |
| 1461 | A first run that explains itself. The onboarding overlay exists. What does not exist is the answer to "I have 4,000 notes in... | docs/roadmap/BACKLOG.md:3878 | S | unassigned |
| 1462 | The owner, 2026-09-23 night, verbatim, from the desktop window with a screenshot. "I pressed next on the first panel of the... | docs/roadmap/BACKLOG.md:4133 | L | unassigned |
| 1463 | "why is the token window limit for this model soooo low :(" Recommendation: show the model's real context limit and the reason for it in the token... | docs/roadmap/CHAT_PLAN.md:857 | S | unassigned |
| 1464 | "Hovering over an intext reference opens up the sources dropdown." Recommendation: hover shows a short preview of the source and a click opens the... | docs/roadmap/CHAT_PLAN.md:877 | M | unassigned |
| 1465 | "when I click the token window button pill, i expect to see a dropdown to see my token distribution stats, not it to be a button to compact the... | docs/roadmap/CHAT_PLAN.md:935 | M | unassigned |
| 1466 | Brief 32 (templates and base layouts) and Brief 33 (the rest of WORLD_CLASS_PLAN): unmarked | docs/roadmap/SESSION_BRIEFS.md:850 | L | unassigned |
| 1467 | Brief 92: the whole-app pass the owner asked for (first run, tour, element libraries, themes; INBOX 843) | docs/roadmap/SESSION_BRIEFS.md:1767 | L | unassigned |
| 1468 | "There's overlap on these settings tabs in the sidebar" Recommendation: measure the overlap of the settings tabs at the sidebar width, then fix the... | docs/roadmap/UI_MODERNISATION_PLAN.md:1259 | S | unassigned |
| 1469 | "Some tooltip buttons are circles and some are rounded squares. Should they have backgrounds or borders that are visible??" Recommendation: one... | docs/roadmap/UI_MODERNISATION_PLAN.md:1274 | S | unassigned |
| 1470 | "No vertical gap" Recommendation: the owner has not named the surface; find the gap by the density census and fix it under the spacing tokens. Also... | docs/roadmap/UI_MODERNISATION_PLAN.md:1276 | S | unassigned |
| 1471 | "Ive been screenhotting parts of the perplexity interface and others but there are soo many more modern examples and ways to structure stuff. I think... | docs/roadmap/UI_MODERNISATION_PLAN.md:1282 | M | unassigned |
| 1472 | "feel like there should be a subtle like meatball icon in the top right on the same line as the quick access title on aligned to the right above the... | docs/roadmap/UI_MODERNISATION_PLAN.md:1284 | M | unassigned |
| 1473 | "do way to view logs of bg processes" Recommendation: a background tasks log in settings, read from the job runtime. Also carried by Brief 37 (logs... | docs/roadmap/UI_MODERNISATION_PLAN.md:1286 | S | unassigned |
| 1474 | INBOX 789, UI, the owner 2026-10-10 22:38Z, two screenshots. "not all buttons have the same hover states?? all the ui styles across the app need to... | docs/roadmap/UI_MODERNISATION_PLAN.md:1538 | M | unassigned |
| 1475 | 809, the owner, verbatim: "is there a way to redesign areas in the app like these??" (Help, "Welcome and tours": fourteen bordered tinted buttons and... | docs/roadmap/UI_MODERNISATION_PLAN.md:1562 | L | unassigned |
| 1476 | Settings > Packages rows misaligned (icon, text and the install button on different baselines). Owner: consistency.md item 4; the alignment sweep... | docs/roadmap/WORLD_CLASS_PLAN.md:1558 | S | unassigned |
| 1477 | Settings > Help gaps (accordion rows touch, sections have no rhythm). Owner: help-popovers.md, with item 22. | docs/roadmap/WORLD_CLASS_PLAN.md:1561 | S | unassigned |
| 1478 | The laptop screen is mostly chrome. At 1093x614 the top bar (72px), sub-tabs (55), the list toolbar (55) and the status bar (37) take about 36% of... | docs/roadmap/WORLD_CLASS_PLAN.md:2320 | M | unassigned |
| 1479 | A "Copy diagnostics" button on the About page (versions, model, recent errors) for bug reports from test users. | docs/roadmap/WORLD_CLASS_PLAN.md:2375 | S | unassigned |
| 1480 | The status bar's "." dot says what it means on hover and click. | docs/roadmap/WORLD_CLASS_PLAN.md:2377 | S | unassigned |
| 1481 | Hierarchy in Settings. Section heads are the same weight as labels (in the Sonnet batch). | docs/roadmap/WORLD_CLASS_PLAN.md:2385 | S | unassigned |
| 1482 | **Already met 2026-10-19** (5.91:1 light, 7.96:1 dark, 13.6px `.empty-line`); only the icon-and-action recipe is design work. Empty states. The Chats sidebar's empty text is body size and grey on grey; empty states should use one recipe (icon, one line, one action). | docs/roadmap/WORLD_CLASS_PLAN.md:2389 | S | unassigned |
| 1483 | "I pressed a restart button and it failed: {"[1007/230819.346:ERROR:ui\gfx\win\window_impl.cc:172] Failed to unregister class Chrome_WidgetWin_0.... | docs/roadmap/WORLD_CLASS_PLAN.md:3086 | M | unassigned |
| 1484 | "Also I feel like we should reference all the vendored repos and libraries somewhere to give them credit." Recommendation: a credits list in Help... | docs/roadmap/WORLD_CLASS_PLAN.md:3115 | M | unassigned |
| 1485 | 25f: the 14 appearance settings kept only in this browser do not follow the person to a second browser. Decision, taken: mirror them all to the... | docs/roadmap/WORLD_CLASS_PLAN.md:4192 | M | unassigned |
| 1486 | errors.js ran light theme only; THEME=dark and FAULTS=1 not run. | docs/roadmap/agent-remaining/census-1010.md:4 | S | unassigned |
| 1487 | 24.5 undercounts untested routes (path-param wildcard) and over-reports unused CSS names (string-built classes). | docs/roadmap/agent-remaining/census-1010.md:5 | S | unassigned |
| 1488 | Not indexed: class methods, nested functions, let/var helpers, and JS functions declared in a form other than function name( or const name = (. | docs/roadmap/agent-remaining/codemap-1010.md:5 | S | unassigned |
| 1489 | Settings help mapping is a heuristic (measure-settings-help.py header says the rule); 31 of 72 keys have no Settings control it could find, and some... | docs/roadmap/agent-remaining/measure-1010.md:8 | S | unassigned |
| 1490 | Decision 43: editable rate table in Settings, never fetched without the web toggle. | docs/roadmap/agent-remaining/spec39-1010.md:13 | S | unassigned |
| 1491 | After the bugs: the parity programme, the 'build first' rows of every ANALYSIS parity table (docs/ROADMAP.md) | docs/ROADMAP.md:132 | L | unassigned |
| 1492 | Section: Assistant catalogue section 5: build first, fifteen capabilities by value over cost | docs/roadmap/CHAT_PLAN.md:1516 | L | unassigned |
| 1493 | Section: Phase 7: reports from the v0.2.2 round still open (items 2 and 6 and the rest after Built 1, 3, 4, 5) | docs/roadmap/UI_MODERNISATION_PLAN.md:229 | M | unassigned |
| 1494 | Section: Phase 10: the Liquid Glass adoptions (half a session; confirm what is built) | docs/roadmap/UI_MODERNISATION_PLAN.md:590 | S | unassigned |
| 1495 | Section: 12z Learnability measured on a fresh profile (INBOX 749) | docs/roadmap/UI_MODERNISATION_PLAN.md:1297 | M | unassigned |
| 1496 | Section: Phase 13: design review; 13a built (Brief 57), 13b and 13c (Briefs 58, 59) open | docs/roadmap/UI_MODERNISATION_PLAN.md:1314 | L | unassigned |
| 1497 | Section: Section 2: competitor gaps (what they have that this app does not) | docs/roadmap/WORLD_CLASS_PLAN.md:225 | L | unassigned |
| 1498 | Section: Section 3: frontend dossiers D1 to D16 (each a hand-off brief; build status per dossier unverified) | docs/roadmap/WORLD_CLASS_PLAN.md:289 | L | unassigned |
| 1499 | Section: Section 7: the small things checklist that sessions keep reopening | docs/roadmap/WORLD_CLASS_PLAN.md:740 | M | unassigned |
| 1500 | Section: Section 10: flaws found by static probes (each with its command) | docs/roadmap/WORLD_CLASS_PLAN.md:861 | M | unassigned |
| 1501 | Section: Section 18: the next horizon H1 to H9 | docs/roadmap/WORLD_CLASS_PLAN.md:1726 | L | unassigned |
| 1502 | Section: Section 19: architecture review (776 MB resident idle; 19.5 not covered yet) | docs/roadmap/WORLD_CLASS_PLAN.md:1911 | M | unassigned |
| 1503 | Section: Section 20: a model per feature, Still open | docs/roadmap/WORLD_CLASS_PLAN.md:2220 | M | unassigned |
| 1504 | Section: Section 21: every failure names its way out | docs/roadmap/WORLD_CLASS_PLAN.md:2290 | M | unassigned |
| 1505 | Section: Section 22: the professional baseline gaps and the devibecode programme | docs/roadmap/WORLD_CLASS_PLAN.md:2317 | L | unassigned |
| 1506 | Section: Section 24: codebase census acts (Brief 45 part 2) | docs/roadmap/WORLD_CLASS_PLAN.md:3217 | L | unassigned |
| 1507 | Section: 25.2 Surface by surface bars and gaps (Briefs 46 to 55 landed mostly; gaps per surface remain) | docs/roadmap/WORLD_CLASS_PLAN.md:3755 | L | unassigned |
| 1508 | Section: 26.3 Backend phases with gates (Briefs 61 to 63 open) | docs/roadmap/WORLD_CLASS_PLAN.md:3924 | L | unassigned |
| 1509 | Section: 27.1 Feature by feature gaps and 27.2 the popups one by one | docs/roadmap/WORLD_CLASS_PLAN.md:3984 | L | unassigned |
| 1510 | Section: 28.3 Trust contract phases and the rules still open | docs/roadmap/WORLD_CLASS_PLAN.md:4097 | M | unassigned |
| 1511 | uipolish-0924 leftovers: the surface-by-surface pass (its item D); the icon-only floor is done and measured by iconfloor.js. The footer overlap... | docs/roadmap/agent-remaining/OPEN.md:1951 | L | unassigned |
| 1512 | No lint makes a new outbound call site name its purpose (egress.purpose, nine sites do). | docs/roadmap/agent-remaining/OPEN.md:2242 | S | unassigned |
| 1513 | INBOX 819 (2): a label's look controls (size, bold, colour, chip, position); owner the cards agent. | docs/roadmap/agent-remaining/OPEN.md:2259 | S | unassigned |
| 1514 | Speaker names cannot be edited; the decision and action rules read English cue words only. | docs/roadmap/agent-remaining/OPEN.md:2357 | S | unassigned |
| 1515 | A tab hidden over five minutes can fire up to 60 s late (Chromium's timer throttling). | docs/roadmap/agent-remaining/OPEN.md:2366 | S | unassigned |
| 1516 | Caps measured on a loaded machine sit close to the noise; re-measure idle and tighten (table, README and test move together). | docs/roadmap/agent-remaining/OPEN.md:2388 | S | unassigned |
| 1517 | The skeleton shimmer still runs under the OS reduced-motion setting (data-progress-motion defaults to "always"). | docs/roadmap/agent-remaining/OPEN.md:2404 | S | unassigned |
| 1518 | A slow or failed fetch of app-features.js and a late Quick access first paint were not exercised. | docs/roadmap/agent-remaining/OPEN.md:2459 | S | unassigned |
| 1519 | Questions split at quote marks: INBOX 745 (b) decided a quoted prompt is not the person's own question, so the extractor rejects them; the fragments... | docs/roadmap/agent-remaining/OPEN.md:2465 | M | unassigned |
| 1520 | A failed or slow status poll nulls modelStatus, so Agent greys until the next good poll and may flicker. | docs/roadmap/agent-remaining/OPEN.md:2473 | S | unassigned |
| 1521 | Other AI controls still gate on aiIsOff(); model_ready is the field to move them to. | docs/roadmap/agent-remaining/OPEN.md:2474 | S | unassigned |
| 1522 | The reading does not take a note by its number ("pin note 12"): commands._one_target. | docs/roadmap/agent-remaining/OPEN.md:2519 | S | unassigned |
| 1523 | The fishbone's rib runs behind its causes' boxes (lines are under nodes); the look is not compared against XMind's. | docs/roadmap/agent-remaining/OPEN.md:2554 | S | unassigned |
| 1524 | The week is Monday-first on user_now; a Sunday-first locale reads it a day out (notebook_stats.week_start). | docs/roadmap/agent-remaining/OPEN.md:2565 | S | unassigned |
| 1525 | Words written this week are the words in the notes made that week; edits to older notes are not counted (no per-edit word delta is stored). | docs/roadmap/agent-remaining/OPEN.md:2566 | S | unassigned |
| 1526 | D1's folder: the brief and D1 say frontend/js/run/; the files are frontend/js/run-*.js because 65 lints (test_frontend_symbols, the em-dash and... | docs/roadmap/agent-remaining/OPEN.md:2658 | S | unassigned |
| 1527 | input() is answered before the run (the Input box), not interactively mid-run: that needs SharedArrayBuffer and the COOP/COEP headers, which are D2's... | docs/roadmap/agent-remaining/OPEN.md:2664 | S | unassigned |
| 1528 | netbind.host_allowed("localhost.") and a trailing-dot own name are refused (fail closed, as intended; noted so nobody reads a 421 on localhost. as a... | docs/roadmap/agent-remaining/OPEN.md:2688 | S | unassigned |
| 1529 | arch.md (removed 2026-10-12, recoverable from git history): INBOX 266's usability and lightweight items belong to nobody. [arch] (The emblem's idle cost is built: HISTORY.md, "OPEN.md rows closed... | docs/roadmap/agent-remaining/OPEN.md:2772 | S | unassigned |
| 1530 | writing-desk.md: Stop mid-pass is unverified (the stand-in answers in about 150ms; a slow backend behind an env var in fake_openai_server.py would... | docs/roadmap/agent-remaining/OPEN.md:2863 | M | unassigned |
| 1531 | Prose tools: Harper's lint config per kind in the dictionary dialog (harper-worker.js, setLintConfig; about 200 rules, all or nothing today)... | docs/roadmap/agent-remaining/OPEN.md:2910 | L | unassigned |
| 1532 | Map render and persistence: (the wbMapNodeSize 94px row is closed, HISTORY.md, "OPEN.md rows closed, 2026-10-05 (the pre-0.4.0 buildable rows, sweeps... | docs/roadmap/agent-remaining/OPEN.md:2957 | M | unassigned |
| 1533 | The rest of the architecture audit (scratchpad/audit1005/arch.md (removed 2026-10-12, recoverable from git history)): ARCH-04's client half (the cursor exists, after and X-Next-Cursor, but... | docs/roadmap/agent-remaining/OPEN.md:3040 | L | unassigned |
| 1534 | Nothing in the learning loop was measured past a test-sized notebook. The pass is O(notes) with one query per note for the already-known... | docs/roadmap/agent-remaining/OPEN.md:3200 | M | unassigned |
| 1535 | The desktop window was never run (start-desktop.sh); every visual claim on this branch is a browser tab. [prose-intelligence.md, visual-c.md] | docs/roadmap/agent-remaining/OPEN.md:3218 | S | unassigned |
| 1536 | Timings vary two to four times between runs (the machine was shared with other agents; map add-a-child 102 to 424 ms); the blocks give ranges. Rerun... | docs/roadmap/agent-remaining/OPEN.md:3295 | S | unassigned |
| 1537 | Bergamot's licence (MPL-2.0 into AGPL-3.0) and sizes are stated as the evaluation's job (Brief 83), not checked here. | docs/roadmap/agent-remaining/OPEN.md:3296 | S | unassigned |
| 1538 | A row added or removed after a list's first render does not fade; the lists redraw whole, so this needs keyed rendering first. (from motion-1005.md) | docs/roadmap/agent-remaining/OPEN.md:3305 | S | unassigned |
| 1539 | UI_MOD Phase 11 item 11: the screenshot set for the owner, which needs a place the owner reads. (from op4-1005.md) | docs/roadmap/agent-remaining/OPEN.md:3311 | L | unassigned |
| 1540 | Two-finger scroll jump (460): not reproduced twice; needs a real touchpad trace. (from op4-1005.md) | docs/roadmap/agent-remaining/OPEN.md:3313 | S | unassigned |
| 1541 | scratchpad/ui-sweeps/lib.js LOOK= writes the look into the server's preferences, so later sweeps on that data dir inherit it; run a LOOK=utilitarian... | docs/roadmap/agent-remaining/OPEN.md:3320 | S | unassigned |
| 1542 | The night shift's pairing phase is slow (120 s for 2,400 facts and 4,786 pairings with the local matcher), and the bar resets between the reading and... | docs/roadmap/agent-remaining/OPEN.md:3342 | S | unassigned |
| 1543 | The ring sweep skips a control at the end of a scroller with more content past it, so a real cut at a scrolled edge is not seen; text cut by a fixed... | docs/roadmap/agent-remaining/OPEN.md:3347 | S | unassigned |
| 1544 | Found: a titled note's every sentence scores on its title (_score, TITLE_WEIGHT), so the brief keeps up to four dated sentences of a note named for... | docs/roadmap/agent-remaining/OPEN.md:3350 | S | unassigned |
| 1545 | CI margin: Tests (Python 3.13) took 16 m 14 s of its 25 m timeout on the head that was scanned (3.11 took 15 m 01 s, 3.12 14 m 37 s). A slow runner... | docs/roadmap/agent-remaining/OPEN.md:3367 | M | unassigned |
| 1546 | Markers' Flag is still two previews (seg665-1006.md item 5). (from inbox670-1006.md) | docs/roadmap/agent-remaining/OPEN.md:3373 | S | unassigned |
| 1547 | Other jobruns detail strings that carry {exc} (grep note_finished and run.fail( in src/) were not audited; only the two named in item 5 were changed.... | docs/roadmap/agent-remaining/OPEN.md:3385 | S | unassigned |
| 1548 | An opened row with no title starts with its text, whose first line's centre is 19.4px from the top against the chevron's and cluster's 22px (2.6px... | docs/roadmap/agent-remaining/OPEN.md:3389 | M | unassigned |
| 1549 | The topic bar wraps to two rows at 390 (348x102), measured identical on the base: the Branch line and the reset go to a second row under the open... | docs/roadmap/agent-remaining/OPEN.md:3398 | S | unassigned |
| 1550 | "last week" in Find anything: a window or the words. (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3422 | S | unassigned |
| 1551 | Any real-model behaviour of the agent (CLAUDE.md section 4). (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3424 | S | unassigned |
| 1552 | The rail-dot alignment at 390 (0 px at 1440). (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3425 | S | unassigned |
| 1553 | The agent panel with no model: 16 of 20 controls disabled (AGENT_SKILLS_REFORM, Deepened row 1). (from deepen-b-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3429 | S | unassigned |
| 1554 | The p5 API list in scratchpad/vendor_use.py is a Chromium dump pinned to 1.9.4; regenerate it with a p5 upgrade. (from vendor-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3435 | S | unassigned |
| 1555 | Brief 2 (consistency lints): HISTORY mentions it only as an owner reference; no record of the lint set being built as the brief. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3436 | S | unassigned |
| 1556 | Brief 3 (prefs, api.stream/upload, innerHTML): HISTORY line 43146 area still lists api.stream/api.upload and the no-bare-fetch lint as not built.... | docs/roadmap/agent-remaining/OPEN.md:3437 | S | unassigned |
| 1557 | Brief 8 ( autocomplete, connections rail): HISTORY has only the plan table rows, no Built record. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3441 | S | unassigned |
| 1558 | Brief 9 (job runtime): tests/test_jobs.py the brief names does not exist; HISTORY has no Built record. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3442 | S | unassigned |
| 1559 | Brief 14 (docs condensed): HANDOVER.md is 486 lines against a 300-line done-when; NEXT_FABLE_WINDOW.md does not exist. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3445 | S | unassigned |
| 1560 | Brief 18 (the complete open scope): an umbrella brief, only section A recorded in HISTORY. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3448 | S | unassigned |
| 1561 | Briefs 25 to 31 (group): each plan phase list is still open; "nothing is built" for 25. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3449 | S | unassigned |
| 1562 | Brief 33 (rest of WORLD_CLASS_PLAN): HANDOVER.md:450 names it as the next brief. (from briefs-1010.md) | docs/roadmap/agent-remaining/OPEN.md:3451 | S | unassigned |
| 1563 | Rule 5: "the managed runner killed" has nothing to act on: the app starts no model runner (extras.py says llama-server is run by hand), so an... | docs/roadmap/agent-remaining/OPEN.md:3523 | S | unassigned |
| 1564 | The output grip is 24 px (the grip recipe), under touch.js's 44 px floor at 390; touch.js does not list the run panel as a surface. [docs42b] | docs/roadmap/agent-remaining/OPEN.md:3537 | S | unassigned |
| 1565 | js-beautify on a selection is not used (a selection keeps the conservative re-indent); vendor_use.py reports "selection" as its one unused... | docs/roadmap/agent-remaining/OPEN.md:3538 | S | unassigned |
| 1566 | #entry-list div.entry-meta.note-meta: 64 to 72px wider than its card at 320 and 390 (one per note, 33 to 42 nodes); #entry-list li 24 to 48px at 320. | docs/roadmap/agent-remaining/OPEN.md:3555 | S | unassigned |
| 1567 | A model's proposed act through the registry: acts.propose is tested but nothing calls it; the agent's write tools keep their own confirm path... | docs/roadmap/agent-remaining/OPEN.md:3586 | S | unassigned |
| 1568 | "Grounded in" says 4 notes while the support chip says "3 of 3 from your notes" on "tell me about golf" (seen in a sweep screenshot, not... | docs/roadmap/agent-remaining/OPEN.md:3590 | S | unassigned |
| 1569 | The decision 54 sum rule: "12 * 7 is 84." is read as its own "Read as" because it restates the question's sum; every other utility answer has a "Read... | docs/roadmap/agent-remaining/OPEN.md:3591 | S | unassigned |
| 1570 | Scorecard: the follow-up column needs decision 58's 200 spoken lines, which are not written; variety's minimum is 3 of 20 against the plan's target... | docs/roadmap/agent-remaining/OPEN.md:3615 | S | unassigned |
| 1571 | Brief 34 second part (INBOX 752): snapping transitions per minute (60 Hz joint sampling), 12 distinct idle motions per ten minutes and reaction... | docs/roadmap/agent-remaining/OPEN.md:3627 | S | unassigned |
| 1572 | Decision 58's core/background.py registry (name, started, stop) is not built; the lint only counts sites. Brief 63 neighbour.... | docs/roadmap/agent-remaining/OPEN.md:3643 | S | unassigned |
| 1573 | 49 routes need a test or removal (tests/test_routes_named.py SEED); several are reached by a loop over verbs, check before writing duplicates.... | docs/roadmap/agent-remaining/OPEN.md:3645 | S | unassigned |
| 1574 | The drag's feel by hand; the open-card ring with a keyboard user. | agent/graph100-1011:docs/roadmap/agent-remaining/graph100-1011.md:27 | S | unassigned |
| 1575 | /tmp filled to 100% once during this session (ENOSPC); outputs moved to /dev/shm. | agent/graph100-1011:docs/roadmap/agent-remaining/graph100-1011.md:33 | S | unassigned |
| 1576 | INBOX 883, 884, 885 and 874 are not numbered items in this branch's docs/roadmap/INBOX.md (874 appears only in the "Placed" log), so inbox_resolve.py... | agent/mergetrain-1011:docs/roadmap/agent-remaining/phonegraph-1011.md:6 | M | unassigned |
| 1577 | 851 Select-mode tick in the gutter: card and row heights unchanged, centre within 1px of the first line. | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:7 | S | unassigned |
| 1578 | 887/888/889 are not in this branch's docs/roadmap/INBOX.md (they live on the orchestrator's); resolve them there with python... | agent/mergetrain-1011:docs/roadmap/agent-remaining/phone2-1011.md:7 | S | unassigned |
| 1579 | 19d3155c5: merge of the working branch (next-free-port kept with the gate). | agent/mergetrain-1011:docs/roadmap/agent-remaining/lansafe-1011.md:21 | S | unassigned |
| 1580 | The staged gate ran per commit for 852, 851 and 847; 853, 854 and 856 were gated once together on the final staged tree. | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:22 | S | unassigned |
| 1581 | Contents sub-tab's outline shifts 0.013 to 0.016 on first paint (contents-outline 266px to 634px). | agent/mergetrain-1011:docs/roadmap/agent-remaining/ownerfix3-1011.md:25 | S | unassigned |
| 1582 | Pending device requests live in memory (lantrust._pending, 10 minutes); a restart forgets them, and a device that asked and went away still shows a... | agent/mergetrain-1011:docs/roadmap/agent-remaining/lansafe-1011.md:41 | S | unassigned |
| 1583 | Stray files from this run at the filesystem root: /lansafe-gz.py, /lansafe-tf.txt (removal was refused by the sandbox). | agent/mergetrain-1011:docs/roadmap/agent-remaining/lansafe-1011.md:51 | S | unassigned |
| 1584 | SESSION_BRIEFS Brief 102: the Built block move to HISTORY is the orchestrator's at merge. | agent/mergetrain-1011:docs/roadmap/agent-remaining/lansafe-1011.md:53 | S | unassigned |
| 1585 | The chime is not heard by a sweep; only that no error is thrown. | agent/voiceup-1011:docs/roadmap/agent-remaining/voiceup-1011.md:17 | S | unassigned |
| 1586 | The Tidy review title was 12px because .card h3 (the eyebrow) outranked .tidy-title; fixed here, but other sheets' h3 titles may carry the same rank... | agent/voiceup-1011:docs/roadmap/agent-remaining/voiceup-1011.md:20 | S | unassigned |
| 1587 | Agent: tool-calling with its own controls: which tools are allowed this turn, max rounds, visible plan/progress, and a stop that... | docs/roadmap/BACKLOG.md:185 | S | unassigned |
| 1588 | A dependency-vulnerability sweep (pip-audit / npm audit equivalent for the vendored JS, since nothing currently checks either)... | docs/roadmap/BACKLOG.md:564 | M | unassigned |
| 1589 | Dynamically switch models by task complexity. Next: the manual per-mode assignment this item says to build first exists... | docs/roadmap/BACKLOG.md:820 | L | unassigned |
| 1590 | MAX_CLIENT_HISTORY turns of prior Q&A go up each time, whole. | docs/roadmap/BACKLOG.md:908 | S | unassigned |
| 1591 | That taking several rounds deliberately is expected, plan, act, check, answer | docs/roadmap/BACKLOG.md:966 | S | unassigned |
| 1592 | What to do when a tool fails, the error is returned with no guidance, so small models give up or repeat the same call | docs/roadmap/BACKLOG.md:968 | S | unassigned |
| 1593 | The six named tools are still missing. Check the registry's real count first: the README says 65, while this section said 58. | docs/roadmap/BACKLOG.md:1085 | S | unassigned |
| 1594 | execute_tool already files writes as ai:<tool> through events.acting_as (ai/tools/__init__.py), so a new tool only needs a test... | docs/roadmap/BACKLOG.md:1086 | S | unassigned |
| 1595 | Fonts (#font-seg offers System, Serif, Mono, Arial; Next: a dyslexia-friendly face must be vendored under frontend/vendor/fonts/... | docs/roadmap/BACKLOG.md:1122 | M | unassigned |
| 1596 | The agent controlling the screen itself, "allow the agent to control your screen within the application to navigate and make... | docs/roadmap/BACKLOG.md:1250 | L | unassigned |
| 1597 | Crash-safe recovery for a re-index or a model download interrupted mid-way. Half-checked directly. The re-index half is safe by... | docs/roadmap/BACKLOG.md:1405 | L | unassigned |
| 1598 | A "forgotten connections" widget: proactive rather than on-demand. Pointer: WORLD_CLASS_PLAN I1 "The night shift" (its findings... | docs/roadmap/BACKLOG.md:1644 | L | unassigned |
| 1599 | Numeric X/Y/W/H/rotation entry: Pointer: scratchpad/audit1005/features.md section 4 row C3 (P2, the Format panel, Phase B).... | docs/roadmap/BACKLOG.md:1984 | S | unassigned |
| 1600 | Smaller polish items: Pointer: scratchpad/audit1005/features.md section 4 rows C3 (resize from centre, flip), C9 (whole-object... | docs/roadmap/BACKLOG.md:2006 | M | unassigned |
| 1601 | Tests and guards: a lazy-load test (not in app_js_files), a vendored-file licence notice test, a CSP test that no inline style or... | docs/roadmap/BACKLOG.md:2653 | M | unassigned |
| 1602 | Nav-history popup, genuinely broken this time, reproduced: a history of short single-word entries (a plain tab visit, no... | docs/roadmap/BACKLOG.md:3361 | M | unassigned |
| 1603 | The AI's honesty surface is the app's real differentiator. Answers already carry the notes behind them and the librarian is... | docs/roadmap/BACKLOG.md:3741 | M | unassigned |
| 1604 | It can read everything, not a retrieved sample. A cloud tool meters tokens, so it retrieves five notes and hopes. A local model... | docs/roadmap/BACKLOG.md:3780 | M | unassigned |
| 1605 | It can be wrong safely. Nothing leaves the machine, so a speculative suggestion costs nothing but a dismissal. That is why... | docs/roadmap/BACKLOG.md:3786 | M | unassigned |
| 1606 | Real-time collaboration. Same reason, more so. | docs/roadmap/BACKLOG.md:3889 | S | unassigned |
| 1607 | Mid-work drop, 2026-09-14 morning, verbatim (the owner), the last scan. "finish all the agents, scan for bugs and high complexity... | docs/roadmap/BACKLOG.md:3979 | L | unassigned |
| 1608 | Mid-work drop, 2026-09-20, verbatim (the owner). "What usability and information architecture things are missing and can be... | docs/roadmap/BACKLOG.md:4023 | L | unassigned |
| 1609 | "Is it possible to create custom libraries like the ones vendored that are really good and extensive in their purpose, which can... | docs/roadmap/BACKLOG.md:4171 | L | unassigned |
| 1610 | "no way to clear the destination history or delete individual records??" Recommendation: add clear-all and per-record delete to the destination... | docs/roadmap/CHAT_PLAN.md:865 | S | unassigned |
| 1611 | "it got jokes from another note but not the separate one from the top of the matching records" Recommendation: an answer names the note each claim... | docs/roadmap/CHAT_PLAN.md:869 | M | unassigned |
| 1612 | "These notes do not mention “summarise”." Recommendation: a claim with no source note is dropped before the answer is written, with the summarise... | docs/roadmap/CHAT_PLAN.md:883 | S | unassigned |
| 1613 | "Intext reference should be square brackets or styled differently." Recommendation: in-text references use square brackets or a styled marker... | docs/roadmap/CHAT_PLAN.md:937 | M | unassigned |
| 1614 | "should we store recently retrieved website content for easy reretieval??" Recommendation: keep fetched page text with its fetch time and a re-fetch... | docs/roadmap/CHAT_PLAN.md:948 | M | unassigned |
| 1615 | INBOX 771 the owner asleep: continue autonomously through every open brief (standing) | docs/roadmap/INBOX.md:143 | L | unassigned |
| 1616 | INBOX 807 Where your data went: say what each destination fetched or sent and why | docs/roadmap/INBOX.md:183 | S | unassigned |
| 1617 | Brief 46: measure the table (WORLD_CLASS 25 bars) | docs/roadmap/SESSION_BRIEFS.md:1526 | M | unassigned |
| 1618 | Briefs 58 and 59: the stylesheet's structure (13b) and the surfaces (13c) | docs/roadmap/SESSION_BRIEFS.md:1592 | L | unassigned |
| 1619 | Brief 64: measure the foundation (F0): done as found-1010; confirm | docs/roadmap/SESSION_BRIEFS.md:1634 | S | unassigned |
| 1620 | Briefs 72 to 74: trust contract (WORLD_CLASS 28): 72a/72b/73/74 landed with leftovers; confirm remaining rules | docs/roadmap/SESSION_BRIEFS.md:1700 | M | unassigned |
| 1621 | Brief 85 (second use of the number): the launch splash reimagined (INBOX 834) | docs/roadmap/SESSION_BRIEFS.md:1733 | M | unassigned |
| 1622 | Brief 98: goals and lists (INBOX 861) | docs/roadmap/SESSION_BRIEFS.md:1807 | L | unassigned |
| 1623 | Brief 99: the full functionality scan (scan-1011 built the scan; its Open list is in the ledger rows) | docs/roadmap/SESSION_BRIEFS.md:1813 | S | unassigned |
| 1624 | The agent activity panel, see AGENT_SKILLS_REFORM.md Phase C, which owns it. | docs/roadmap/UI_MODERNISATION_PLAN.md:259 | S | unassigned |
| 1625 | No new markup. Both entries are rows in existing catalogues, so there is no new id, no new surface and nothing for the recipe index to cover. | docs/roadmap/UI_MODERNISATION_PLAN.md:299 | S | unassigned |
| 1626 | Two ranks, not five. The name is the row. Under it, one wrapping line of facts at one rank: what the file is (kind, size, pages, added), whether it... | docs/roadmap/UI_MODERNISATION_PLAN.md:311 | M | unassigned |
| 1627 | A fact is not a control and a control is not a chip. The reading badge states; the "Used in" chips open the note they name; the kebab acts. A row... | docs/roadmap/UI_MODERNISATION_PLAN.md:321 | M | unassigned |
| 1628 | A fact is a line of text, a disclosure is a control, and neither is the other. Where the picture is used is a count you read (Used in 2 places, the... | docs/roadmap/UI_MODERNISATION_PLAN.md:336 | M | unassigned |
| 1629 | The owner, 2026-10-03 night, verbatim. "I keep experiencing scroll jump when scrolling with two fingers on my trackpad?? idk". Placed: the... | docs/roadmap/UI_MODERNISATION_PLAN.md:1208 | L | unassigned |
| 1630 | INBOX 760, card dates. The time floats mid-card on a card the grid stretched taller than its content (about 110px under it on the tallest card, 40px... | docs/roadmap/UI_MODERNISATION_PLAN.md:1238 | M | unassigned |
| 1631 | "popup panels appearing at the start on a new install are messy and clash/overlap a lot" Recommendation: one first-run queue with no overlapping... | docs/roadmap/UI_MODERNISATION_PLAN.md:1247 | M | unassigned |
| 1632 | "that's the box in the corner I was telling you temporarily appeared" Recommendation: reproduce on a fresh profile and name the box in the owner's... | docs/roadmap/UI_MODERNISATION_PLAN.md:1253 | M | unassigned |
| 1633 | "These elements in the lightbox aren’t the same height" Recommendation: give lightbox controls one height token and measure their heights in the... | docs/roadmap/UI_MODERNISATION_PLAN.md:1261 | S | unassigned |
| 1634 | "this panel looks like a demo and not professional" Recommendation: name the panel, then give it the designed empty, error and first-run states that... | docs/roadmap/UI_MODERNISATION_PLAN.md:1268 | M | unassigned |
| 1635 | INBOX 795, UI, the owner 2026-10-10 22:55Z, two screenshots: "just make sure that the app actually recieves a propper ui polish and refinement. there... | docs/roadmap/UI_MODERNISATION_PLAN.md:1544 | L | unassigned |
| 1636 | INBOX 800, UI, the owner 2026-10-11 02:40Z, verbatim: "Can you do another devibecoding, ui/ux modernisation and professionalisation sweep across all... | docs/roadmap/UI_MODERNISATION_PLAN.md:1552 | L | unassigned |
| 1637 | #wb-topbar is 104px at 390. Owner: responsive.md. | docs/roadmap/WORLD_CLASS_PLAN.md:980 | S | unassigned |
| 1638 | The same decision as 62; moved with it. | docs/roadmap/WORLD_CLASS_PLAN.md:1604 | S | unassigned |
| 1639 | Found by scan, 2026-09-19 (the session, not the owner). Ten routes the app serves that frontend/js/*.js never names, from... | docs/roadmap/WORLD_CLASS_PLAN.md:2069 | L | unassigned |
| 1640 | Tabs lose their names on a laptop. Under about 1100px the tab strip is icons only with the active tab labelled, so six of seven tabs are guesses.... | docs/roadmap/WORLD_CLASS_PLAN.md:2329 | S | unassigned |
| 1641 | **Already built (Local chip, DESIGN.md row 677; 2026-10-19).** Offline promise, visible. The Privacy receipt now exists; the top bar should say "Local" with the same verdict, one click to the receipt. S, Sonnet. | docs/roadmap/WORLD_CLASS_PLAN.md:2357 | S | unassigned |
| 1642 | The window title names the view and the open item (22.1.1). | docs/roadmap/WORLD_CLASS_PLAN.md:2363 | S | unassigned |
| 1643 | Every list with more than 20 rows can be filtered by typing. | docs/roadmap/WORLD_CLASS_PLAN.md:2373 | S | unassigned |
| 1644 | Right-click works on every card and row, with a hold as its twin on touch. | docs/roadmap/WORLD_CLASS_PLAN.md:2374 | S | unassigned |
| 1645 | The "Default Space" chip is hidden when only one space exists (it is on every card today and says nothing). | docs/roadmap/WORLD_CLASS_PLAN.md:2378 | S | unassigned |
| 1646 | Glass is still on some surfaces the performance plan listed for removal; the glass-off list lint should cover every blurred surface. | docs/roadmap/WORLD_CLASS_PLAN.md:2393 | S | unassigned |
| 1647 | 0.3.x (now): finish INBOX 430, green CI, the full suite, then publish. | docs/roadmap/WORLD_CLASS_PLAN.md:2432 | L | unassigned |
| 1648 | The owner, 2026-09-23 night, verbatim. "for me, trust in the application isn't just the information it shows but that is very much a key point, it is... | docs/roadmap/WORLD_CLASS_PLAN.md:2482 | L | unassigned |
| 1649 | The owner, 2026-10-03, verbatim. "Can you make sure everything in the frontend, backend, function, utility and process for how the user can write... | docs/roadmap/WORLD_CLASS_PLAN.md:3056 | L | unassigned |
| 1650 | "Is it possible to make use of python libraries that the user already may have installed globally on their computer so the user doesn’t have to... | docs/roadmap/WORLD_CLASS_PLAN.md:3107 | M | unassigned |
| 1651 | "Does the user have to be connected to the interned for the initial install for installing all the dependencies?? Should the user be informed of that... | docs/roadmap/WORLD_CLASS_PLAN.md:3111 | M | unassigned |
| 1652 | "I also want to integrate and use the new vendored repositories and libraries better and also see if there are more complimentary libraries and repos... | docs/roadmap/WORLD_CLASS_PLAN.md:3117 | L | unassigned |
| 1653 | "did you vendor the other libraries and binaries?? do we need to?? what else is there to do??" Recommendation: answer in ANALYSIS.md: which libraries... | docs/roadmap/WORLD_CLASS_PLAN.md:3132 | M | unassigned |
| 1654 | "doesnt harper use a binary though?? are there any other repos or libraries that we can vendor??" Recommendation: Harper is a WebAssembly build in... | docs/roadmap/WORLD_CLASS_PLAN.md:3134 | M | unassigned |
| 1655 | A model that fails mid-answer leaves an error line, not the composed answer (api/routes_chat.py ~1963 to 1976); write tests/test_chat_degrades.py... | docs/roadmap/agent-remaining/assistant-1010.md:10 | S | unassigned |
| 1656 | Re-run the 37-question probe (section 0 method) on Brief 35's head, since the triage may already change findings 1 to 3. | docs/roadmap/agent-remaining/assistant-1010.md:13 | S | unassigned |
| 1657 | Routes match only @router.<method> and @app.<method> decorators; another router name is missed. | docs/roadmap/agent-remaining/codemap-1010.md:7 | S | unassigned |
| 1658 | Not wired into scripts/gate.sh or CI; it runs only as part of the test suite. | docs/roadmap/agent-remaining/codemap-1010.md:10 | S | unassigned |
| 1659 | Known failures this worktree inherits, none from this work: test_scratchpad_size.py (1,018 tracked files over a cap of 1,003 before this branch; this... | docs/roadmap/agent-remaining/drawio-1010.md:51 | M | unassigned |
| 1660 | INBOX 775, 792 and 796 stay in INBOX for the orchestrator to resolve at merge. | docs/roadmap/agent-remaining/graphfeel-1010.md:9 | S | unassigned |
| 1661 | The first server grew to 8.5 GB resident over 35 minutes of seeding and sweeps; after a restart it sat at 0.74 to 2.1 GB. Not reproduced, cause not... | docs/roadmap/agent-remaining/measure-1010.md:5 | M | unassigned |
| 1662 | Key checks written as key.toLowerCase() === "x" or switch (e.key) are not counted. | docs/roadmap/agent-remaining/measure-1010.md:9 | S | unassigned |
| 1663 | The --staged gate took 6 minutes with other gates running; its slowest step is worth measuring. | docs/roadmap/agent-remaining/proofing-1010.md:7 | S | unassigned |
| 1664 | Decision 33: tense shift for a past-due plan, number agreement, comma capitalisation, word-boundary title cuts, list "and" and Oxford comma, quote... | docs/roadmap/agent-remaining/spec39-1010.md:6 | S | unassigned |
| 1665 | Decision 41: date arithmetic, word count and reading time, text transforms. | docs/roadmap/agent-remaining/spec39-1010.md:12 | S | unassigned |
| 1666 | Decision 45: model choosing among readings (needs the evals marker). | docs/roadmap/agent-remaining/spec39-1010.md:14 | S | unassigned |
| 1667 | Gemini's light rewrites ("I" to "you", CHAT_PLAN decision 23) were dropped because they changed quoted text and broke grounding; a marked rewrite... | docs/roadmap/agent-remaining/triage-1010.md:29 | L | unassigned |

### Unassigned, proposed batches

Each batch is one agent, 5 to 15 rows, one surface, by id range (the ids above are contiguous per batch). Model and effort follow CLAUDE.md standing order 4: Opus for design judgement (layout, visual, plan phases, engine), Sonnet for named labour (verification, fixtures, lints, sweeps, bugs whose fix is named). Verification batches run a real browser or model where the row says so; a row that needs hardware the sandbox lacks (a real iPhone, Windows, a real model) cannot close in a batch and stays as a stated non-verification.

| batch | surface | ids | rows | S / M / L | model, effort |
| --- | --- | --- | --- | --- | --- |
| B01 | Verification of unverified claims | 184 to 197 | 14 | 14 / 0 / 0 | Sonnet, medium |
| B02 | Verification of unverified claims | 198 to 211 | 14 | 13 / 1 / 0 | Sonnet, medium |
| B03 | Verification of unverified claims | 212 to 225 | 14 | 14 / 0 / 0 | Sonnet, medium |
| B04 | Verification of unverified claims | 226 to 238 | 13 | 12 / 1 / 0 | Sonnet, medium |
| B05 | Red tests, CI and ratchets | 239 to 253 | 15 | 11 / 3 / 1 | Sonnet, medium |
| B06 | Red tests, CI and ratchets | 254 to 268 | 15 | 10 / 5 / 0 | Sonnet, medium |
| B07 | Red tests, CI and ratchets | 269 to 283 | 15 | 11 / 3 / 1 | Sonnet, medium |
| B08 | Packaging, release and installers | 284 to 296 | 13 | 7 / 5 / 1 | Sonnet, high |
| B09 | Packaging, release and installers | 297 to 309 | 13 | 3 / 5 / 5 | Opus, high |
| B10 | Packaging, release and installers | 310 to 321 | 12 | 5 / 6 / 1 | Sonnet, high |
| B11 | Phone, LAN and security | 322 to 336 | 15 | 9 / 5 / 1 | Opus, medium |
| B12 | Phone, LAN and security | 337 to 351 | 15 | 9 / 5 / 1 | Opus, medium |
| B13 | Phone, LAN and security | 352 to 366 | 15 | 5 / 5 / 5 | Opus, high |
| B14 | Phone, LAN and security | 367 to 381 | 15 | 4 / 9 / 2 | Opus, high |
| B15 | Phone, LAN and security | 382 to 394 | 13 | 7 / 6 / 0 | Opus, high |
| B16 | Composer, engine and Ask | 395 to 409 | 15 | 7 / 3 / 5 | Opus, high |
| B17 | Composer, engine and Ask | 410 to 424 | 15 | 9 / 1 / 5 | Opus, high |
| B18 | Composer, engine and Ask | 425 to 439 | 15 | 11 / 3 / 1 | Opus, medium |
| B19 | Composer, engine and Ask | 440 to 454 | 15 | 12 / 1 / 2 | Opus, high |
| B20 | Composer, engine and Ask | 455 to 469 | 15 | 10 / 3 / 2 | Opus, high |
| B21 | Composer, engine and Ask | 470 to 484 | 15 | 5 / 5 / 5 | Opus, high |
| B22 | Composer, engine and Ask | 485 to 499 | 15 | 4 / 8 / 3 | Opus, high |
| B23 | Composer, engine and Ask | 500 to 514 | 15 | 2 / 10 / 3 | Opus, high |
| B24 | Composer, engine and Ask | 515 to 529 | 15 | 2 / 5 / 8 | Opus, high |
| B25 | Composer, engine and Ask | 530 to 543 | 14 | 9 / 4 / 1 | Opus, medium |
| B26 | Chat, Guide, agent and skills | 544 to 558 | 15 | 9 / 5 / 1 | Opus, medium |
| B27 | Chat, Guide, agent and skills | 559 to 573 | 15 | 11 / 4 / 0 | Opus, medium |
| B28 | Chat, Guide, agent and skills | 574 to 588 | 15 | 10 / 4 / 1 | Opus, medium |
| B29 | Chat, Guide, agent and skills | 589 to 603 | 15 | 11 / 4 / 0 | Opus, medium |
| B30 | Chat, Guide, agent and skills | 604 to 618 | 15 | 9 / 3 / 3 | Opus, high |
| B31 | Chat, Guide, agent and skills | 619 to 633 | 15 | 7 / 7 / 1 | Opus, high |
| B32 | Chat, Guide, agent and skills | 634 to 648 | 15 | 5 / 6 / 4 | Opus, high |
| B33 | Chat, Guide, agent and skills | 649 to 660 | 12 | 5 / 4 / 3 | Opus, high |
| B34 | Atlas and the companion | 661 to 673 | 13 | 3 / 6 / 4 | Opus, high |
| B35 | Atlas and the companion | 674 to 686 | 13 | 2 / 9 / 2 | Opus, high |
| B36 | Atlas and the companion | 687 to 699 | 13 | 7 / 4 / 2 | Opus, high |
| B37 | Mind map | 700 to 713 | 14 | 6 / 5 / 3 | Opus, high |
| B38 | Mind map | 714 to 727 | 14 | 6 / 5 / 3 | Opus, high |
| B39 | Mind map | 728 to 741 | 14 | 4 / 6 / 4 | Opus, high |
| B40 | Mind map | 742 to 755 | 14 | 4 / 3 / 7 | Opus, high |
| B41 | Mind map | 756 to 769 | 14 | 5 / 3 / 6 | Opus, high |
| B42 | Mind map | 770 to 783 | 14 | 9 / 2 / 3 | Opus, high |
| B43 | Mind map | 784 to 791 | 8 | 3 / 2 / 3 | Opus, high |
| B44 | Whiteboard and boards | 792 to 805 | 14 | 8 / 4 / 2 | Opus, high |
| B45 | Whiteboard and boards | 806 to 819 | 14 | 13 / 1 / 0 | Opus, medium |
| B46 | Whiteboard and boards | 820 to 833 | 14 | 3 / 10 / 1 | Opus, high |
| B47 | Whiteboard and boards | 834 to 847 | 14 | 6 / 8 / 0 | Opus, high |
| B48 | Whiteboard and boards | 848 to 861 | 14 | 9 / 4 / 1 | Opus, medium |
| B49 | Whiteboard and boards | 862 to 875 | 14 | 6 / 3 / 5 | Opus, high |
| B50 | Whiteboard and boards | 876 to 889 | 14 | 1 / 5 / 8 | Opus, high |
| B51 | Whiteboard and boards | 890 to 903 | 14 | 6 / 7 / 1 | Opus, high |
| B52 | Whiteboard and boards | 904 to 917 | 14 | 8 / 3 / 3 | Opus, high |
| B53 | Whiteboard and boards | 918 to 927 | 10 | 6 / 2 / 2 | Opus, high |
| B54 | Graph | 928 to 941 | 14 | 8 / 3 / 3 | Opus, high |
| B55 | Graph | 942 to 955 | 14 | 6 / 7 / 1 | Opus, high |
| B56 | Graph | 956 to 968 | 13 | 7 / 2 / 4 | Opus, high |
| B57 | Timeline, reminders and notifications | 969 to 982 | 14 | 11 / 2 / 1 | Opus, medium |
| B58 | Timeline, reminders and notifications | 983 to 996 | 14 | 7 / 7 / 0 | Opus, high |
| B59 | Timeline, reminders and notifications | 997 to 1010 | 14 | 10 / 3 / 1 | Opus, medium |
| B60 | Timeline, reminders and notifications | 1011 to 1024 | 14 | 8 / 6 / 0 | Opus, high |
| B61 | Timeline, reminders and notifications | 1025 to 1038 | 14 | 9 / 4 / 1 | Opus, medium |
| B62 | Documents and the code editor | 1039 to 1053 | 15 | 6 / 4 / 5 | Opus, high |
| B63 | Documents and the code editor | 1054 to 1068 | 15 | 13 / 2 / 0 | Opus, medium |
| B64 | Documents and the code editor | 1069 to 1083 | 15 | 7 / 8 / 0 | Opus, high |
| B65 | Documents and the code editor | 1084 to 1098 | 15 | 12 / 3 / 0 | Opus, medium |
| B66 | Documents and the code editor | 1099 to 1113 | 15 | 9 / 6 / 0 | Opus, medium |
| B67 | Documents and the code editor | 1114 to 1128 | 15 | 4 / 8 / 3 | Opus, high |
| B68 | Documents and the code editor | 1129 to 1143 | 15 | 5 / 5 / 5 | Opus, high |
| B69 | Documents and the code editor | 1144 to 1158 | 15 | 6 / 8 / 1 | Opus, high |
| B70 | Documents and the code editor | 1159 to 1173 | 15 | 3 / 10 / 2 | Opus, high |
| B71 | Documents and the code editor | 1174 to 1188 | 15 | 7 / 6 / 2 | Opus, high |
| B72 | Documents and the code editor | 1189 to 1203 | 15 | 5 / 7 / 3 | Opus, high |
| B73 | Documents and the code editor | 1204 to 1211 | 8 | 7 / 1 / 0 | Opus, medium |
| B74 | Library, OCR, audio and media | 1212 to 1226 | 15 | 12 / 1 / 2 | Opus, high |
| B75 | Library, OCR, audio and media | 1227 to 1241 | 15 | 11 / 4 / 0 | Opus, medium |
| B76 | Library, OCR, audio and media | 1242 to 1256 | 15 | 8 / 6 / 1 | Opus, high |
| B77 | Library, OCR, audio and media | 1257 to 1270 | 14 | 5 / 6 / 3 | Opus, high |
| B78 | Search, filing, tags and notes | 1271 to 1284 | 14 | 11 / 2 / 1 | Sonnet, high |
| B79 | Search, filing, tags and notes | 1285 to 1298 | 14 | 4 / 9 / 1 | Sonnet, high |
| B80 | Search, filing, tags and notes | 1299 to 1312 | 14 | 11 / 2 / 1 | Sonnet, high |
| B81 | Search, filing, tags and notes | 1313 to 1326 | 14 | 5 / 6 / 3 | Opus, high |
| B82 | Search, filing, tags and notes | 1327 to 1340 | 14 | 2 / 10 / 2 | Sonnet, high |
| B83 | Search, filing, tags and notes | 1341 to 1353 | 13 | 6 / 5 / 2 | Sonnet, high |
| B84 | Data, backup, export and import | 1354 to 1364 | 11 | 9 / 1 / 1 | Sonnet, high |
| B85 | Data, backup, export and import | 1365 to 1375 | 11 | 3 / 8 / 0 | Sonnet, medium |
| B86 | Data, backup, export and import | 1376 to 1386 | 11 | 3 / 7 / 1 | Sonnet, high |
| B87 | Settings, themes and UI system | 1387 to 1401 | 15 | 8 / 5 / 2 | Opus, high |
| B88 | Settings, themes and UI system | 1402 to 1416 | 15 | 11 / 4 / 0 | Opus, medium |
| B89 | Settings, themes and UI system | 1417 to 1431 | 15 | 12 / 3 / 0 | Opus, medium |
| B90 | Settings, themes and UI system | 1432 to 1446 | 15 | 11 / 4 / 0 | Opus, medium |
| B91 | Settings, themes and UI system | 1447 to 1461 | 15 | 4 / 9 / 2 | Opus, high |
| B92 | Settings, themes and UI system | 1462 to 1476 | 15 | 6 / 5 / 4 | Opus, high |
| B93 | Settings, themes and UI system | 1477 to 1490 | 14 | 10 / 4 / 0 | Opus, medium |
| B94 | Tooling, docs and housekeeping | 1491 to 1505 | 15 | 1 / 7 / 7 | Sonnet, medium |
| B95 | Tooling, docs and housekeeping | 1506 to 1520 | 15 | 8 / 2 / 5 | Sonnet, medium |
| B96 | Tooling, docs and housekeeping | 1521 to 1535 | 15 | 10 / 3 / 2 | Sonnet, medium |
| B97 | Tooling, docs and housekeeping | 1536 to 1550 | 15 | 12 / 2 / 1 | Sonnet, medium |
| B98 | Tooling, docs and housekeeping | 1551 to 1565 | 15 | 15 / 0 / 0 | Sonnet, medium |
| B99 | Tooling, docs and housekeeping | 1566 to 1580 | 15 | 14 / 1 / 0 | Sonnet, medium |
| B100 | Tooling, docs and housekeeping | 1581 to 1595 | 15 | 12 / 2 / 1 | Sonnet, medium |
| B101 | Tooling, docs and housekeeping | 1596 to 1610 | 15 | 3 / 6 / 6 | Sonnet, medium |
| B102 | Tooling, docs and housekeeping | 1611 to 1625 | 15 | 6 / 6 / 3 | Sonnet, medium |
| B103 | Tooling, docs and housekeeping | 1626 to 1640 | 15 | 4 / 7 / 4 | Sonnet, medium |
| B104 | Tooling, docs and housekeeping | 1641 to 1655 | 15 | 7 / 4 / 4 | Sonnet, medium |
| B105 | Tooling, docs and housekeeping | 1656 to 1667 | 12 | 9 / 2 / 1 | Sonnet, medium |

Order to run them: Verification and Red tests batches first (cheap, they shrink the list), then Phone, LAN and security after lanbar lands, Composer and Chat after atlas and composer, then the surface batches by the owner's priority (documents, graph, whiteboard, mind map, timeline) and Settings and UI last, since the Brief 92 whole-app pass touches it.

### Branches with commits not on the working branch

`git log gemini/composer-improvements..BRANCH` counts below. This clone is shallow and old merges used merge commits, so the count alone overstates: a branch is listed as not merged only when no merge subject or remaining file on the working branch names it (35 of 111). The other 76 show commits by ancestry but are on the branch by content.

| branch | commits | last subject | state |
| --- | --- | --- | --- |
| agent/mergetrain-1011 | 52 | Merge agent/meaning94-1011; meaning.js listed as a lazy piece; one-off | mergetrain (running) |
| agent/atlas-1011 | 25 | A3: "what did I search yesterday", "what ran overnight", "when did I l | atlas (running) |
| agent/cifix-1010 | 13 | CI M: changelog line | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/data101b-1011 | 9 | Codemap and remaining list for data101b | data101b (running) |
| agent/cifix2-1011 | 8 | Search suggest places its list on a short timer instead of a frame loo | mergetrain (merging) |
| agent/graph100-1011 | 6 | Brief 100: CHANGELOG lines and the remaining list (graph100-1011) | mergetrain (merging) |
| agent/lansafe-1011 | 6 | lansafe-1011: remaining list (Brief 102) | mergetrain (merging) |
| agent/ownerfix3-1011 | 6 | Hover grounds: a lint and a sweep for square corners; the remaining fi | mergetrain (merging) |
| agent/throw-1011 | 6 | Atlas: its props read against its body and say what they are | throw (running) |
| agent/voiceup-1011 | 6 | voiceup-1011: the remaining file with the commits | mergetrain (merging) |
| agent/wbcolour-1011 | 6 | Whiteboard: one colour menu, and a selection's shared properties | mergetrain (merging) |
| agent/scan-1011 | 4 | Scan 1011: what the full scan found and left (remaining file), changel | mergetrain (merging) |
| agent/secscan-1011 | 4 | secscan-1011: remaining list | mergetrain (merging) |
| agent/chattime-1011 | 3 | chattime agent: what is left (Brief 103, INBOX 871) | mergetrain (merging) |
| agent/meaning94-1011 | 3 | Autocorrect leaves the editor: notes, chat, Ask and titles, with undo | mergetrain (merging) |
| agent/phone2-1011 | 3 | Files tab and OCR workspace on a phone: no sideways scroll from an ope | mergetrain (merging) |
| agent/phonegraph-1011 | 3 | Notifications: the read circle and remove cross are the row's centred  | mergetrain (merging) |
| agent/room101-1011 | 3 | Room under the caps: remaining ledger, two stale OPEN rows replaced | mergetrain (merging) |
| agent/themes95-1011 | 3 | Themes: Parchment and Ember dark retoned; every look 0 low-contrast (B | mergetrain (merging) |
| agent/devsize-1011 | 2 | INBOX 897 resolved: sizes per device measured and moved to HISTORY | mergetrain (merging) |
| agent/undoall-1011 | 2 | undoall-1011: the remaining ledger (INBOX 898) | undoall2 (running) |
| agent/wbfix-1011 | 2 | An undone shape on no layer comes back identical | mergetrain (merging) |
| agent/cifix3-1010 | 1 | CI red on 142aa25f5: ten failures from the Brief 80, pickers and Brief | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/cifix4-1010 | 1 | CI fixes: /recordings takes a cursor, insight questions skip the overv | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/cifix5-1011 | 1 | CI red: reminder notifier on the pool, no console flash, stale toast e | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/codeql-1010 | 1 | CodeQL-proof census.py and codemap.py: bounded route regex, case-insen | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/gzip-1010 | 1 | Boot gzip budget: MCP snippet and LAN state render move into the lazy  | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/placement-1010 | 1 | Placed from the owner's list, 2026-10-10: 133 items into the plans | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/rebrand-1011 | 1 | Rename the product to Tessellate, formerly MemoryMap AI (INBOX 903) | rebrand (running) |
| agent/restart-1011 | 1 | Restart works in every launch, and the new copy waits for the old one | mergetrain (merging) |
| agent/review56-1010 | 1 | Brief 56 re-run: already built (021fd6c9c, 41655fc24); remaining list  | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/tags89-1011 | 1 | Notes: a "+ Tag" chip on notes with fewer than three tags, with sugges | mergetrain (merging) |
| agent/first101c-1011 | 0 | INBOX 895 to 897: the composer's reach, the LAN status bar, sizes per  | queued: first101c |
| agent/graphfeel100-1011 | 0 | Merge typos90b: 80 of the owner's typos understood (a stray semicolon, | unmerged, unassigned: check, may be on the branch by cherry-pick |
| agent/logo-1011 | 0 | INBOX 895 to 902 placed: composer, sizes, undo, time words, LAN toggle | logo (running) |

Branches 76 of 111 (the -1010 round and most of -1011) are merged by content; their remaining files are the head's agent-remaining files and OPEN.md rows above.



## Left by the ownerfix2 agent (Brief 91, the owner's small UI reports, merged 2026-10-11)

The file is `docs/roadmap/archive/agent-remaining/ownerfix2-1011.md`.

- INBOX 839, graph: only the drag's heat is changed (graph-worker.js `dragHeat`). A single-tick 7.1px step still shows in one of two 8px runs (a non-dragged node, 3 ticks after release); not traced. The main-thread glide (graph-canvas.js `gcGlideStep`) was not touched.
- Attach: at 390 `#attach-image` reads a 999px radius while `#attach-note` reads 4.8px in the chat composer row (the owner's 841 asked for one corner; only the gear was in scope). 04-chat-dock-appearance.css, `#attach-image.has-attachments` near line 2854 is the nearest rule.
- The guide topic `ask-chat` is at 1916 of 1919 characters (`tests/test_help_controls.py`), so Agent-with-no-model could not be named in the Guide without trimming another sentence. The segment's title and the hint line carry it.
- `graphjitter.js`-style rAF sampling is useless on a loaded machine (frames 50 to 170 ms apart, load average 10 to 33); the worker-tick measure (graphticks.js: per-tick steps from the 'tick' messages, the page's onmessage wrapped) is the one that holds.
- Nav history on a phone: the popup was measured by calling `openNavHistoryMenu` directly (the status-bar button is not drawn at 390), so its placement on a phone was not verified, only its widths and 44px targets.

## Left by the 0.3.3 agents (INBOX 426), 2026-09-26

The four agent files of that round (`companion-426.md`, `atlas-fable.md`,
`ui-426.md`, `auth-optional.md`) are in `archive/agent-remaining/`; what
they left that is still true on the 0.3.3 head is here, one line each. The
two decisions only the owner can take are INBOX 427.

- **Boot gzip budget, what the 2026-10-05 split did not take** (792,754 to
  758,418 bytes, notes-list.js 63,548 to 57,929; `test_static_compression.py`
  has the numbers). Candidates measured and left, each with its catch:
  the chord guide in settings-wiring.js (`showTabJumpHint`, `chordGuideEl`,
  `chordGuideGroup`, about 3 KB gzipped; a stand-in makes the guide appear a
  moment after the first `m`, so the real function would need a "still armed"
  check or the second key can leave it stuck on screen); the SearXNG host
  block in settings-wiring.js (about 3 KB; its caller
  is `renderWebSearch`, a Settings render, so it wants `await ensureModule` there); the Ask
  rendering in capture-ask.js (`askQuestion`, `renderChatMeta`,
  `renderAnswerGrounding`, `placeAnswerFigures`; about 10 KB but read by the
  Ask tab's own submit path, so it is a design judgement, not a move); the
  edit form in notes-list.js (`renderEditForm`, 4.5 KB: `renderEntries` calls
  it synchronously and reads the card it fills, so it needs `openNoteEditor`
  to load the file first and every other way into `editingId` checked).
  [split1005]
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": Stray Atlas heads under the status bar (INBOX 429).
- **`tests/test_name_mood.py` asserts `oklch(from var(--accent)` in the
  CSS**: it holds (the accent tints the glow), but a test for the fixed
  palette would be the honest one. [atlas-fable]
  *Needs: a test for the fixed palette needs the palette's values decided first.*
- **Atlas round 5, the owner's asks (INBOX 427 (1); 2026-09-27)**: hands
  and feet drawn as part of each limb's outline (a mitten with a thumb on
  the inner side, a turned-out foot with a heel; `atlasStem`'s `tip`), the
  legs a third of the height on a shorter torso (hips at 58, soles at 90,
  from a fifth showing before), the hair drawn full on both looks (the
  feminine: seven wavy locks fanning from the crown over a soft mass, one
  falling forward to the shoulder; the crest a quarter fuller), the
  feminine lower body two ribbons (a wide sash from the left hip, a
  narrower one from the right) in the swaying layer, the Auto look reading
  Your look when Face looks is Neutral (`atlasLookReason`), and the lab's
  Morning review card (both looks, every expression, every pose, every
  size, with what Auto would draw and why). Proofs
  `scratchpad/shots/atlas-r5/`. Left: the hands' fingers are two soft
  swells, not drawn fingers (the sprite's are mittens, so by choice); the
  feminine hair now reaches x 78 and y -9, past the companion's 64px box
  by the tail's margin; the ring drift and per-glint twinkles stay off at
  companion size; the simulator's stand-in menu says nothing about where
  app.js's menu lands; three CSP "inline style" console warnings on the
  lab come from a style attribute in avatars.js's generated faces; the
  organic body, ribbon tail, strand and heart star await the owner's read
  of the review card. A mood's body move (hop, giggle, doze, sway, ponder)
  runs on the figure box and the Zs and hearts on two roots of their own,
  so at rest in any mood the figure is 0 layouts and 0 paints
  (companionperf.js, atlaswalk.js, 2026-09-27); what still animates inside
  a layer's svg is a mood's small effects (the sparkles of delighted and
  proud, the thinking dots and node pulses, the sad drops, the confused
  wobble), which the companion's pacer steps at 20 Hz for as long as that
  mood lasts, 20 layouts a second. The hook that would end it is the
  pacer's own (avatars.js `nameMarkBuddyTempo`): skip animations whose
  target is inside an `.atl-layer` svg and let them run free (a repaint of
  one 64 by 92 layer, no layout), or pace them at 10 Hz. [atlas-fable]
  *Needs: what is left is drawing changes that await the owner's read of the review card.*
- **The companion rides with `ScrollTimeline`** (Chromium 115+, so WebView2);
  WebKitGTK falls back to the script follow. Not driven in either desktop
  window. [companion-426]
  *Needs: a WebView2 or WebKitGTK window.*
- **Sign-in off, not driven**: the desktop window's persistent profile, a
  real second device on the LAN, the prompt card in dark, and whether a
  restored backup's `preferences.json` brings the setting back (a sweep
  can now boot such a data dir: `lib.js` `boot()` returns `signIn: 'app'`).
  [auth-optional]
  *Needs: the desktop window and a second device.*
- ~~**The vault key is process-wide**~~ built 2026-09-26: the key is granted
  per session (HISTORY.md, "Moved from the plans, 2026-09-26").
- **The dashboard scroll jump (426 u)** was not reproduced by wheel, idle or
  any scroll call; if it recurs, `scrolljump.js` with the owner's
  preferences (`LS=`) and the companion on. [ui-426]
  *Needs: the owner's preferences (`LS=`) to reproduce.*
- **uipolish-0924 leftovers**: the surface-by-surface pass (its item D);
  the icon-only floor is done and measured by `iconfloor.js`. The footer
  overlap `deadbtn.js` reported was the sweep's, settled 2026-09-26: no tab's
  scroller runs under the status bar (each ends at or above its top, at 1440
  and 390), and the three were controls half scrolled out of their own box,
  whose centre the point test found the bar under; the sweep now checks the
  centre against each scrolling ancestor first, 0 findings at 1440 and at 390
  (the graph's `#graph-fullscreen` case is closed, HISTORY.md, "OPEN.md rows
  closed, 2026-10-05 (the pre-0.4.0 buildable rows, sweeps on port 8815)").
  [ui-426]
  *Needs: a surface-by-surface design pass.*
- **The README's OCR shot is the 0.3.2 capture, in dark**: `seed-ocr.js` (removed 2026-10-12, recoverable from git history)
  needs a Tesseract binary this sandbox does not have, so it was not retaken
  with the rest (`SKIP=ocr`). [docs-0.3.3]
  *Needs: a Tesseract binary.*

## The owner's requests on fix/gemini-fixes-5 (PR 157), 2026-09-23

The ledger moved whole to HISTORY.md, "OPEN.md rows closed, 2026-10-05": its 34 Done rows are done. Its ten partial rows each have a home: 113's CodeMirror cost is pass2's row below; 114's traces and listeners are the frontend performance agent's; 124 is WORLD_CLASS_PLAN 1.3; 127 is WHITEBOARD_PLAN's Placed from INBOX 2026-09-23; 133 is the UX agent's surface pass; 137 is codecomplete's row below; 141 is holepoke's; 142's avatars beyond personas and translate-a-selection are queued in INBOX 405's HISTORY entry; 143 is guide's (WORLD_CLASS_PLAN); 146 is the boot split's row above.

## What is left after PR 144, in the order to build it (written 2026-09-14)

The owner's brief for the next session is one line: "here's what's left,
read the handover and OPEN.md, please finish and build all of these". This
section is the "these". Each row points at where the detail lives; the
bullets further down this file and the plan sections hold the file, id,
measurements and next step. Work top to bottom: bugs the owner reported,
then the plan tails by surface, then the horizon.

**A. The owner's open reports (INBOX numbers; the entries are in INBOX.md)**

| # | What is left | Where |
| --- | --- | --- |
| 226 | A flicker above the bottom bar on the dashboard, never reproduced here; needs the owner's theme, art setting and zoom. (needs owner: their preferences; HISTORY holds the entry as "not reproduced") | HISTORY, INBOX 226 |

Rows 238, 246, 232, 253 and 225 are done; their accounts moved whole to HISTORY.md, "Moved from the plans, 2026-10-05 (small-1005: the small open items)".

**B. Plan tails, by surface.** Moved to HISTORY.md, "OPEN.md rows closed, 2026-10-05", 2026-10-05: every row was built or held by its plan. Two stay open: MINDMAP_PLAN's mapux leftover list (this file's Mind map section, the mind map agent's) and UI_MODERNISATION_PLAN Phase 11 item 11's screenshot set for the owner. Section C, the horizon, is WORLD_CLASS_PLAN section 8's own ranked list.

**C. The horizon (WORLD_CLASS_PLAN, one item per PR, in its own stated order)**

H7 the speed budget, H9's perf gate and usage ledger, H1 the night shift,
H2 evidence cards and open questions, H3 the model bench, H6 professional
use (imports, print and PDF, keyboard-complete, WCAG audit, multi-window,
first-run tour; 253 is its first row), H4 the API contract and extensions,
H8 time travel and the margin reader, H5 sync. Behind them the backend
moves B2's second half, B4's pages and citations (its tensions table is built), B6 to B8 and the inventions I1 to I3 and I5 to
I8, each with its spec test named in the plan.

**Done-when for the next session:** sections A and B empty, each Built
block moved to HISTORY, the CHANGELOG carrying the numbers, CI green, and a
PR opened per the standing orders. Section C is one item per PR after that.


One bullet per open item, consolidated 2026-09-14 from the 38 finished agent
files now in [`../archive/agent-remaining/`](../archive/agent-remaining/)
(INBOX 220). Each bullet names the file, the id or selector, and the next
step; the source file is in brackets so the full account, with its
measurements, is one `grep` away. Items an archived file recorded as open and
a later file, the branch head or a live `grep` shows as done were dropped
rather than carried, and the drop is noted where it matters. The files still
being written by running agents stay beside this one.

## Documents

- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": DOCUMENTS_PLAN Phase 4 item 5's daily notes, and only that; Found, not fixed: scratchpad/ui-sweeps/docexports.js (removed 2026-10-12, recoverable from git history) fails on a click timeout; The document surface's aliases have no lint; The table cell menu is a kebabMenu with ten items and no grouping; Atomic ranges, the Mod+click affordance and the toolbar's own state; Outline rows are 24 to 25.2px, under the app's own 28px floor; clampToolbarMenu's comment says the trigger cannot be reproduced here, and that is now out of date; The writing-suggestion underline is the only surface with no hover affordance; docFindingAtPoint walks every mark on every pointer event; The three finding kinds are named in two places.
- Closed here, accounts in HISTORY.md, "Moved from the plans, 2026-10-04 (design-1004)": The rest of the app's viewport popups have not been measured with the background art on.
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05": A finding below the editor's visible box gets a menu drawn over its own word.

## Graph

- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": The graph export's style attributes under the CSP; The options panel scrolls again at 1440x900; /graph/local has no Show switches; GRAPH_PLAN Phase 5; The node popup redesign the owner names; graph.js's step 5 still fails: "clear trace (a route was drawn: false): NO CHANGE"; `graph.js` interrupted by a confirm dialog; scratchpad/ui-sweeps/selectfocus.js fails twice on a notebook with content; INBOX 66: the lightbox the node panel opens is unreachable while the graph is fullscreen.

Left by the graph agent (Brief 38, merged 2026-10-10):

- Built (`topicRepeatsTag`, notes-list.js): a tag-named topic's chip repeats the tag chip beside it on the card (`noteTopicChip`, notes-list.js); dedupe against the card's own tags.
- The floating topic rename field is 42px tall over a 17px plate (`gcRenameTopicInline`, graph-canvas.js); not seen by eye, size it to the plate.
- A topic drag writes its core note's pin with its own `PUT /graph/pin` beside the group's one `PUT /graph/pins` (`gcDragEnd`); one write.
- `scratchpad/ui-sweeps/graphfslightbox.js` reads `.lightbox` in the tick it calls the lazy `openLightbox`; the sweep needs an await.
- Topics becoming categories is Brief 39b's (GRAPH_PLAN "Decision made, 2026-10-10").

## Chat and popup agent

- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": Review of the chat pass and the Library and Timeline pass (2026-09-27).
- **The citation mark's touch box overlaps the lines above and below** (a
  decision to note, not a bug): the `::after` box is 44px tall around a
  13px glyph, so on a phone a tap within 14px above or below a mark opens
  the peek rather than acting on that line's text. By design (6df7310);
  worth a look on an answer dense with marks.
  *Left: by design (6df7310); look only if an answer dense with marks is reported.*
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": A pinned citation peek outlived a Tab past Open note; The chat welcome's blurb wrapping at 1280; CHAT_PLAN Phase 1, which note grounds a sentence.
- **Ask's answer object was measured on the offline branch only.** The sweep
  runs against a server with no model, so `sentences` was empty in every
  measurement and the grounding chips and inline marks under an Ask answer
  were not re-measured. Next step: anyone with a local model runs
  `chatphase3.js` again and adds a line for the sentence count and the mark
  count. [chat-timeline-skills.md]
  *Needs: a local model.*
- **`chatSourcesPanel` is shared, the renderer is not.** Judged not worth it
  in 2026-09-13: the three surfaces have genuinely different frames around the
  same three shared components. Next step if a fourth surface appears: move
  the Chat bubble's foot onto `renderAskAnswerFoot` (renamed) and delete the
  palette's own `cmdPaletteResultRow`. [chat-timeline-skills.md]
  *Left: a decision, revisit if a fourth surface appears.*
- **SKILLS Phase D: no model ran any of it.** The fake transport answers every
  step, so "a rewritten step fixes a run a 3B model stalled on" is the claim
  the mechanism is for and not one the tests make. The chat control (Edit step
  N, beside Resume) is asserted statically against `app.js` because reaching
  it needs a run that stops, which needs a model. [chat-timeline-skills.md]
  *Needs: a model (`scratchpad/llama-dev.sh`; `tests/test_skills_evals.py` holds four evals).*
- **The `evals` marker and its fixture set (Brief 13's done-when).** At least
  80% of the built-in skills complete with zero invalid tool calls under
  small-model mode, and a loose-ends fixture of 70 notes with eight planted
  loose ends, all eight found. Deliberately not built against the fake
  transport: a fake calls whatever its script says. File: a new
  `tests/test_skill_evals.py`, marker `evals` registered in `pyproject.toml`
  and the module skipped unless the dev model is reachable. Next step:
  WORLD_CLASS_PLAN 9's runner first. [brief-13-harness.md]
  *Partly built since: the marker and four evals exist (`tests/test_skills_evals.py`); the 80% built-in-skills run and the 70-note loose-ends fixture still need a model.*
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": A skill's `verify` block; The page cap and a large notebook.
- **The follow-up chips were stubbed at the route in the sweep**, because
  `/chat/followups` answers `[]` with no model. What is measured is the
  request a chip causes, not the model's choice of question. Worth knowing
  before reading the sweep as proof of the whole feature.
  [chat-timeline-skills.md]
  *Left: a caveat about the sweep, not a bug; the chips' model choice needs a model.*

## Whiteboard and mind map

- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": Decision 7's other half: the quick-sketch pad still has its own copy of the tool code; Multiply is worth 3 luminance units on a dark board and 20 on a light one; A sketch's handles scale with the zoom; a card's do not; The context bar at phone width, and the plan's half-answered question; #wb-topbar is 13 controls at 1440 against the dock grammar's ceiling of seven; The old export popover's CSS still names it in grouped selectors.
- **The View menu is 714px of content on a map.** Under about a 730px-tall
  window it still scrolls, which is correct and may still read as the report.
  If it comes back the fix is the menu's own length (four groups, sixteen
  rows), not its placement, which is measured and right from 500 to 1000px
  tall. [visual-c.md]
  *Opus: the menu's own length is a design call.*
- **The mind map's own leftover list was re-checked item by item, 2026-09-20**
  (`archive/agent-remaining/mindmap.md`, "Left to do", rewritten with what a run
  against this head finds). Four of its six items were already done, two of
  them by decisions taken after the list was written: the dock's Layout
  section exists and MINDMAP_PLAN §12.5 decided a map shows no Insert or
  Arrange menu at all, both sweeps take `VIEWPORT`, `mapstrip.js` runs 39/39
  on `#wb-context`, `mapperspective.js` (removed 2026-10-12, recoverable from git history) measures every Colour by on a map of
  twenty notes 12/12 (category 5 colours, 4.59:1 to 9.13:1 against the card),
  and `wbrail.js` reads the rail against the bar recipe 6/6. Of what that
  re-check found actually left, ~~**curve control points on a tree edge**~~ and
  ~~**an image in a node**~~ were built 2026-09-21 (MINDMAP_PLAN §12.1 items 2
  and 5, moved whole to HISTORY.md, "Moved from the plans, 2026-09-21";
  `scratchpad/ui-sweeps/mindmapcurve.js` 14/14 and `mindmapimage.js` (removed 2026-10-12, recoverable from git history) 12/12, light and dark,
  both now in `scripts/gate.sh`'s sweep list). What is left of that list is the
  AI half, which no sandbox here can exercise.
  *Blocked here: the AI half needs a model.*
- **The whiteboard's own View menu (`.wb-board-menu`) was never reproduced as
  broken.** It has its own max-height-on-open logic (`whiteboard.js`, the
  `wb-board-menu-wrap` toggle listener), unrelated to the `details.dock-menu`
  family INBOX 31's fix targeted. Worth a Chromium check in its own right if
  it is still reported. [batch-a.md]
  *Left: measure in Chromium only if it is reported again.*
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": INBOX 12's remainder, owner WHITEBOARD_PLAN; A colour swatch is 1rem and never grows for a finger.

### Left by the boardmap agent (the owner's 2026-10-10 list, merged 2026-10-10)

- INBOX 739's documents half: boards and maps name themselves (`wbUntitledNames`, `whiteboard-templates.js`); "Untitled document N" is not built (`documents.js`, Brief 42). 739 stays in INBOX until then.
- Document comments do not yet share the board's thread (Reply, Edit, Resolve, Attach); `whiteboard.js` `wbCommentRow` is the shape to reuse (Brief 42).
- A topic's effect (shadow, glow) and a Phosphor icon do not reach the PNG or SVG picture (`wbBuildExportSvg`, the map-node branch); shapes do.
- The frame-preview clip was reproduced only as the selection canvas lagging a container that grew mid-drag (fixed); the owner's exact trigger is not known.
- "spacing is really close ... bunched up" on insert: gaps measured 26px before and after on both layouts; only the branch's jump to the end was found and fixed. A screenshot if it recurs.
- WHITEBOARD_PLAN "Placed from INBOX, 2026-10-07 (next PR)": 740's frame hint has no edit path and its connector arrow-head set (none, open, triangle, circle, diamond, bar) is not built; 747's "Reset style" for a board object is not built.
- Pre-existing sweep failures on the base scripts: `mapcore.js` (removed 2026-10-12, recoverable from git history) 14/16 (a core node's spine and size), `mindmap.js` three FAILs (the Mind map segment's active mark, "an ordinary board shows no map chrome", the P5 template tile click timing out), `mapstyle.js` (removed 2026-10-12, recoverable from git history) "Aa grip overlaps the actions".
- `errors.js` at 390 stops on its own second login check (`#lock-password` reads visible after the unlock); 1440, 1024 and 820 report 0 errors.

## Timeline

- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05": WORLD_CLASS D6, the daily journal: the backend is built, the frontend is not.
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": The timeline strip's threshold; The timeline table at 820; The band label sits over the cards scrolled under it; Timeline Phases 1 to 4.
- Closed here, accounts in HISTORY.md, "Moved from the plans, 2026-10-04 (the auto scale)": The "auto" scale thresholds.

## Library

- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05": The Files sub-tab rows were never on screen.
- **An uploaded document cannot be given a reading from outside the app.**
  `POST /media/{id}/ocr` and `/media/{id}/vision-ocr` both answer 415 for a
  PDF, because `ocr.OCR_SUFFIXES` and `vision_ocr.VISION_OCR_SUFFIXES` are the
  six image types, so every seeded PDF's fold says "nothing has read this yet"
  and no sweep can measure the Files fold with a reading behind it. A document's
  reading lives in `PageRead` rows instead (`/media/{id}/ocr-page-read`, which
  needs a model). Not a bug on its own; it is the reason the Files fold's filled
  state is still unmeasured. [readings.md]
  *Needs: a local model (`/media/{id}/ocr-page-read`) to fill a PDF's reading; not a bug, and the only route to the Files fold's filled state.*
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05": A tile's Rename and Delete buttons are never in the DOM; A caption for an image that has none; The other four picker sources have no thumbnail; The Notes (10) and Library (9) docks are still over the seven-control ceiling.

## Notes and capture

- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": The Notes categories sidebar overflows at 390px, on every sub-tab; `textarea.autogrow`'s shared `min-height`; The note edit form's strip is a clone; Boards and maps on a note (INBOX 246).
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05": INBOX 38's bulk-move action is still to build.

## App wide: shell, phone and the shared recipes

- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": Review of the companion's round 5 (3ecadd4 to 69ac76b), 2026-09-26.
- **Atlas's `hide` act shows shut eyes and nothing of its hands.** The
  companion's new act (a private note opened) raises both arms over the
  face; Atlas draws its arms under its head in the body layer, so at the
  act's middle both arms sit inside the head's box (armL 1227..1244 x
  77..98 against the head's 1209..1266 x 46..95, `hidecheck.js`) and are
  not seen. Its eyes shut with the lids layer over the act's middle (the
  generic `.nm-eyes` squash flattened them to a 1.3px line 21px above their
  place, transform-box view-box; fixed 2026-09-26, `atl-lids-hide`). Paws
  over the face would need the arms drawn in the front layer for this act,
  a drawing change for the owner's call (atlas-r6-hide-mid.png).
  *Needs: a drawing change for the owner's call.*
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": A filled button is 2px shorter than every tonal button beside it, app wide.
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05 (op4-1005: four design rows)": the field and the segmented track; an empty line in a small panel; the dark shadow sliders; the Ask results grid's breakpoint.
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05 (op4-1005: the concentric rollout)": `--radius-inner` has four users.
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05 (op4-1005: the meeting head and holepoke's seven)": The meeting dialog's head row holds two heights; holepoke.md.
- **`.sidebar-head` is off the dock grammar, deliberately.** It carries
  `min-height: var(--sidebar-toggle-size)`, a negative `margin-top` that meets
  the absolutely positioned collapse toggle, and `padding-right` reserving
  that toggle's lane; two of the three exist because of reports. If a future
  session wants them on the grammar the only safe route is all three at once
  (`frontend/index.html`: `#chat-sidebar` ~1134, `#sidebar` ~523, the
  documents sidebar ~2172; `frontend/css/05-sidebars-themes.css` line 17),
  with `.dock` gaining the three properties behind a `.dock.is-sidebar`
  modifier and `heads.js` run before and after. [docks.md]
  *Left: deliberate; all three properties or none.*
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05": Phase 11 item 1's last bullet: the top bar's own reduction at 320.
- **Band 3 (600 to 820): the header is two rows, 128px at 819.** The band's
  recorded design (the strip cannot fit beside the wordmark at any width in
  the band, and the wordmark is what was reported twice when it was hidden),
  so it is known rather than open. [ui-phase-11.md]
  *Left: known and recorded design.*
- **`.dock-chip-row` has no user in the page** since `cb8060a` (only a comment
  in `index.html` names it). Its rules are in
  `frontend/css/07-whiteboard-misc.css` with a band-4 partner in
  `10-responsive.css`, written as a general recipe rather than as the
  Timeline's, so left whole; `tests/test_ui_recipes.py` holds the page at zero
  uses either way. [ui-phase-11.md]
  *Left: kept whole as a general recipe; the lint holds it at zero uses.*
- **The Dashboard hero is deferred by the owner, not by judgement.** Do not
  touch `.dash-hero`, `.dash-wordmark`, `.dash-greeting`, `.dash-clock*` in
  `frontend/css/03-dashboard-widgets.css`, the hero markup in
  `frontend/index.html` (`#dash-hero`, around line 489), or `dashboard.js`'s
  `renderEmblem($("dash-hero-emblem"), ...)` call. [docks.md]
  *Left: the owner's call, do not touch.*
- **Two icon-gap outliers, both judged deliberate**: 10 meta chips at 3.6px
  (`.chip.when`, `.map-chip`) against the app's 242 controls at 6.4px, and
  `#conv-browse-all` at 17.7px at 1024 only (it is `width: 100%` with
  `justify-content: center`). Revisit only if the owner reads them as
  inconsistent. [consistency.md]
  *Left: judged deliberate.*
- **`#chat-results`'s second half is the only `.panel-head` with no actions.**
  The next head that wants a control beside its title should take family 8
  rather than inventing a fourth arrangement, which is what the lint is there
  to insist on. [ask-head-ocr.md]
  *Left: a rule for the next head that wants a control.*

- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": Settings → Extras scrolls sideways by 4px at 820.

## Left by the typos90b agent (Brief 90 follow-up, 80 owner typos understood, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/typos90b-1011.md`.

- Not engine-readable, left out of the fixture: "corder" (corner; a one-letter swap in a six-letter word is refused on purpose, it reads "coder"), "nire" (more), "meen", "enout", "thingt", "ohf", "unig".
- The Guide's no-model system answer still prints no "I took that to mean".

## Left by the e2efix2 agent (CI E2E: draft recovery after a killed server, the documents count race, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/e2efix2-1011.md`.

- The budgets spec flaps in CI (a different budget each run: list, search, board, first_interaction) while it shares the runner with the other specs; HEAD measured no slower than the last green E2E (list 150 vs 198 ms best of five). Recommendation: run `budgets.spec.js` alone in a second Playwright invocation in the CI job; no cap raised.

## Left by the search86 agent (Brief 86, search suggestions, Clear and forget, Recent changes, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/search86-1011.md`.

- The Library's documents, boards, images, bookmarks, recordings and skills boxes suggest recents only, not their own titles.
- "Clear dismissed suggestions" does not reach per-note "Not suggested" tags; changes are noted only while Settings is open (the top-bar theme button is not in Recent changes); a look change's Undo toast lands about 1.5 s late.
- App scripts at 320,589 of 320,600 gzipped (11 bytes); seven `typeof` guards removed on eager functions, each path not driven by hand.

## Left by the typos90 agent (Brief 90, the owner's typos as composer fixtures, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/typos90-1011.md`.

- The Guide's no-model system answer (`help_chat.system_answer`) does not say "I took that to mean"; only `composer.compose` answers do.
- A real word missing from both word lists can be mis-repaired; add it to `common_words.py` and `LEFT_ALONE`.
- The asking-word nearest rule turns an all-caps token ("NASA") into "has" unless the whole text is capitals.
- Readings guessed: "liks" (like), "mut" (must), "odf" (of), "ro" (or). Brief 90 is standing: each new prompt's typos join `owner_typos.json`.

## Left by the transparency agent (one ledger, the running panel, backups, where your data went, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/transparency-1011.md`.

- No lint makes a new outbound call site name its purpose (`egress.purpose`, nine sites do).
- The Guide, drafting and document review get a ledger run but no narrated lines; chat and agent turns are never announced.
- Measured on synthetic rows and one real destination; the status ring under "auto" motion not measured.

## Left by the grammar57 agent (Brief 57, the stylesheet's grammar, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/grammar57-1011.md`.

- Decisions 12 (layers, 115 literals), 13 (19 drop shadows), 16 (128 `!important`) are ratchets only; 13.R not started.
- Row actions (`rowActions`) not yet in meetings, the suggestions inbox, the tag manager; "Kinds: all" triggers and the chat strip's pill toggles a different family.
- Logs More menu `.dock-menu-check` rows 34.9px/8px against 32px/12.8px items; the board's Start and End menus not measured for end gaps.
- The Windows grammar worker failure not reproduced (now names its reason).

## Left by the mapfix agent (the topic's tools and the board's frames, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/mapfix-1011.md`.

- INBOX 819 (2): a label's look controls (size, bold, colour, chip, position); owner the cards agent.
- At 25% zoom the 20px + overlaps its parent by about 5px; radial and tree-down layouts not driven.
- `.wb-resize-handle` title still says "double-click fits the text" on non-frame objects; a dead `.wb-map-actions` coarse-pointer rule pinned by `test_map_actions_clear_of_label.py`.

## Left by the ownerfix agent (the owner's UI items, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/ownerfix-1011.md`.

- INBOX 803 item 4 (the OCR workspace's empty squashed box): not reproduced in five states; needs the owner's screenshot or state.
- The capture box still moves 2.4px down and 1.6px left on the first click (strip 40 to 42.4px; CodeMirror line padding).
- Constellation yellow stars are about 2.1:1 in light; the Notes rows/cards toggle is 28x24.

## Left by the uisweep agent (the 2026-10-11 sweep and learnability, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/uisweep-1011.md`.

- Mechanical: the header's six buttons lose 0.5px of their ring at the window top; the Library active sub-tab's border is cut 2.3px at 390; the chat composer's ring is cut 3px each side at 390.
- Design, for Briefs 57 to 59: the Notes dock has 10 items; Tidy's "40" is a pill badge; 177 controls sit off the 28/32/44 height steps (a 36px family among them); the timeline scrubber reads as a glitch; the Dashboard boards-and-maps miniature overlaps its text; the board view menu's labels sit 26px off the rows' text column; Settings Help has 196 buttons.
- Not driven: the code IDE, the OCR workspace, the phone More sheet, the lock screen, the board's tools and Present.
- `settings-reset` is in no help group (`test_help_coverage.py`).

## Left by the noagent agent (Agent mode with no model, merged 2026-10-11)

File: `docs/roadmap/archive/agent-remaining/noagent-1011.md`.

- Not verified: a real Needle engine on leftover turns; a real chat model on a one-option ask_user.
- Open: "what is there about X" with no model is the quoted answer, not the overview shape (decision 64).
- Open: a country with several time zones names one ("the time in Australia" says Sydney's).
- Open: a misspelled place ("westen australia") is not read.
- Open: the user's own bubble shows a trailing backslash as typed.

## Left by the canvasdepth2 agent (canvas depth round 2, merged 2026-10-11)

Full list: [archive/agent-remaining/canvasdepth2-1011.md](../archive/agent-remaining/canvasdepth2-1011.md).
- Not driven: dark theme for the hand-drawn look, tables, the Data tab and the current layer; a real touch double-tap into a table cell; an .xmind opened in XMind; a real multi-page draw.io file; callouts, labels and stamps in the map's PNG and SVG.
- maplayouts.js "tree-left carries the branch bar" fails on base too (it measures the centre topic).
- Tables lack column widths and merged cells; Edit data lacks `%name%` placeholders; .drawio export is not built; a hidden named layer's item eye and layer order are still open.

## Left by the calendar55 agent (Brief 55, merged 2026-10-11)

Full list: [archive/agent-remaining/calendar55-1011.md](../archive/agent-remaining/calendar55-1011.md).
- Touch drag on a tablet, a day page dropped on another day, and a 1,000-note month are built but not driven.
- The feed's Last-year range filters by when a note was written, so a note about a day this month written over a year ago shows in the calendar and not the feed.

## Left by the appsync agent (WORLD_CLASS 25f, merged 2026-10-11)

Full list: [archive/agent-remaining/appsync-1011.md](../archive/agent-remaining/appsync-1011.md).
- No live sync between two open windows; a change shows in the other after a reload.
- The first load after the upgrade has no `ui-synced` mark, so a stale second browser pushes its look to the notebook once.
- Not checked in the desktop webview profile or on a second machine.

## Left by the skills54 agent (Brief 54, merged 2026-10-11)

Full list: [archive/agent-remaining/skills54-1011.md](../archive/agent-remaining/skills54-1011.md).
- No real model here: `skill_rates.json` ships empty, the small-class gate, time to first step and `DEFAULT_CALLS_PER_STEP` are unmeasured.
- A held-back skill is still runnable through the agent's `run_skill` tool; the label is only in the picker and Settings.
- The run's budget usage is on the result event but not drawn in chat-agent.js's result box.

## Left by the settings52 agent (Brief 52, merged 2026-10-11)

Detail: [settings52-1011.md](../archive/agent-remaining/settings52-1011.md).

- The 14 browser-only appearance settings do not follow you to a second browser: decided (WORLD_CLASS 25f, placed 2026-10-11): mirror them all except `perf`.
- Import replaces skills, personas and templates whole (no merge); the desktop save path for Export settings not driven.
- The bin row's long label wraps when its reset appears; theme, palette, accent and zoom keep their own resets (no per-row marker).

## Left by the firstrun49 agent (Brief 49, merged 2026-10-11)

Detail: [firstrun49-1011.md](../archive/agent-remaining/firstrun49-1011.md).

- smallButton (app.js) names every worded button by its tooltip (WCAG 2.5.3); only the first-steps buttons are fixed.
- Most used in the sidebar keeps a binned note for up to 30 s (status.js cacheMs).
- The first-run queue (welcome, recovery key, updates) costs 3 acts before the dashboard.
- Not verified: printed manual output, real-model answers, iOS zoom on the 13.6px name field.

## Left by the followups agent (merged 2026-10-11)

Detail: [followups-1011.md](../archive/agent-remaining/followups-1011.md).

- Free lines and arrows (not links) still draw the shaft through hollow ends: their stored path is re-read as the endpoints, so trimming would drift the line.
- The reminder action token's key is per process (the app has no persisted signing secret): a restart ends open notifications' buttons.
- Still open from uipolish: the rows-view 28px meta button in a 24px line, the tool-confirm pair, lowering BOOT_CSS_CAP.

## Left by the codedocs agent (INBOX 788, merged 2026-10-11)

Detail: [codedocs-1010.md](../archive/agent-remaining/codedocs-1010.md).

- Right-click and long-press on a snippet row do not open its menu (needs navigation.js ROW_MENU_HOSTS, a boot file, and TOTAL_CAP had 35 bytes).
- The code document's dock at 390 is 238px tall (four rows).
- Not verified: a real model or Needle answering the assistant's prompts; the tablet layout beyond one measure at 1024.

## Left by the meet81 agent (Brief 81, merged 2026-10-11)

Detail: [meet81-1010.md](../archive/agent-remaining/meet81-1010.md).

- The recorder saves plain transcript text into the meeting note; the timed lines live only on the recording. `/voice/transcribe-meeting` still returns text only.
- Speaker names cannot be edited; the decision and action rules read English cue words only.
- Not verified: real Whisper segments, a real model's rewording and speaker naming, "Name the speakers" driven in the page.

## Left by the notify86 agent (Brief 86, merged 2026-10-11)

Detail: [notify86-1010.md](../archive/agent-remaining/notify86-1010.md).

- Windows and macOS not run: both need a check by hand. On Windows a toast pressed in the Action Center after 600 s does nothing (needs a COM activator); on macOS osascript notifications have no buttons and a click opens Script Editor.
- A tab hidden over five minutes can fire up to 60 s late (Chromium's timer throttling).

## Left by the filing agent (INBOX 781, merged 2026-10-11)

Detail: [filing-1010.md](../archive/agent-remaining/filing-1010.md).

- Not verified: the path with a real model running (its grounded tags first, then the engine's); dark theme.
- Suggesting tags from a note's own words for a notebook with no tags yet scored 4 of 12 and was not shipped.

## Left by the canvasdepth agent (INBOX 797, merged 2026-10-11)

Detail: [canvasdepth-1010.md](../archive/agent-remaining/canvasdepth-1010.md).

- Whiteboard gaps open: the hand-drawn look, tables, edit data, a current layer new items land in, .drawio pages after the first; an item's eye on a hidden named layer changes nothing visible.
- Mind map gaps open: a structure per branch, callouts, labels under a topic, .xmind export, stickers and votes.
- The Guide topics at the 1,920-character reply budget now are ask-chat 1,918, chat-controls and answers-from-notes 1,913, code-files 1,905, tidy 1,899 and graph-controls 1,896; the board topics were split in two earlier (whiteboard-controls 659 and whiteboard-selection 1,504, board-library 1,496 and board-library-saving 672). [room101-1011]
- The laser sweep's 390 threshold was lowered from 10 dots to 3 and not re-run; a real draw.io file and dark theme not verified.

## Left by the budgets53 agent (Brief 53, merged 2026-10-11)

Detail: [budgets53-1010.md](../archive/agent-remaining/budgets53-1010.md).

- Caps measured on a loaded machine sit close to the noise; re-measure idle and tighten (table, README and test move together).
- First interaction (about 4.4 s) is the slowest number; decision 54's 5,000-note list and search not re-measured; no Settings UI shows the budgets.

## Left by the graphfeel agent (INBOX 775, 792, 796, 798, merged 2026-10-11)

Detail: [graphfeel-1010.md](../archive/agent-remaining/graphfeel-1010.md).

- The owner's line was a saved Tree or Arc layout (synced, static by design). Recommendation: name the current layout on the map as one dock chip whenever it is not Force.
- Notes leaving the picture vanish instead of fading out.
- The close-other-menus fix covers the graph's three head buttons only; app-wide it needs about 98 bytes of app-scripts room.
- Not verified: the owner's screen, Saved views, local and global switching, reduced motion in a browser.

## Left by the uipolish agent (INBOX 776 to 786, merged 2026-10-11)

Detail: [uipolish-1010.md](../archive/agent-remaining/uipolish-1010.md).

- The skeleton shimmer still runs under the OS reduced-motion setting (data-progress-motion defaults to "always").
- `.dash-find` is the one glyph-only hover left; a rows-view meta icon button is 28px in a 24px line.
- The Connections unlinked-mention Link button is still a bordered ghost button; the tool-confirm pair is untouched.
- BOOT_CSS_CAP can be lowered now that strip_css drops comment-leftover lines (about 7 KB freed).

## Left by the canvasui agent (INBOX 790 to 794, merged 2026-10-11)

Detail: [canvasui-1010.md](../archive/agent-remaining/canvasui-1010.md).

- Link-label blur not reproduced headless; the re-raster after zoom is untested on a GPU compositor or the desktop webview.
- Mind map library schematics (wbMapThumbSpec) are monochrome, not tinted with branch colours; a hollow diamond draws the shaft through it.
- The AI board tools and import/export do not carry a note's fold.
- At 390 the whiteboard sidebar is a full-width sheet, so the fit ignores it there.

## Left by the export48 agent (Brief 48, merged 2026-10-10)

Detail: [export48-1010.md](../archive/agent-remaining/export48-1010.md).

- A 5,000-note import takes 45.9 s: each note commits on its own.
- Binned notes import with their old deleted_at, so the startup purge removes expired ones at the next restart.
- Ids inside board object data and comments are copied, not remapped; private notes, several spaces and a browser upload of 5,000 files not verified.
- The Background jobs Report button waits for boot room; the Activity panel at 390 is translucent.

## Left by the docsui agent (INBOX 788 design, merged 2026-10-10)

Detail: [docsui-1010.md](../archive/agent-remaining/docsui-1010.md).

- A code file's editor is capped at 78ch and centred (09-editor.css:59), so its panel is 724px at 1440.
- contentsRenameTopic (library.js) and the note-panel rename (graph.js) still save on blur.
- The sidebar's Comments, Linked from and Notes rows keep their old styling.

## Left by the composer agent (INBOX 787, merged 2026-10-10)

Detail: [composer-1010.md](../archive/agent-remaining/composer-1010.md).

- "What do I know about X" still quotes one sentence unless its notes are tagged with the subject (the 725 and 741 evals pin it).
- Single-note answers still end with "[your note, date]"; some next-question chips repeat the subject; an overview over more than 24 notes should say "at least".
- Not verified: a real embedder, the professional voice in a browser, 390px, the picture notice in a browser.

## Left by the chat88 agent (Brief 88, merged 2026-10-10)

Detail: [chat88-1010.md](../archive/agent-remaining/chat88-1010.md).

- Send stays off the undo bar (Ctrl+Z in the composer is text undo); recommended as is.
- Tab-level Guide topics ring the tab's main control, not each topic's own control.
- The "remind me" chat answer's text appears twice in the bubble's innerText (not checked whether drawn twice).
- The Atlas look row landed under the Settings sheet's head at 390 in one of four runs.
- Not verified: a Chat tap 700 ms after boot at 390 on an idle machine; the Highlight API in the macOS webview.

## Left by the bootdiet agent (merged 2026-10-10)

Detail: [bootdiet-1010.md](../archive/agent-remaining/bootdiet-1010.md).

- `TOTAL_CAP` (all app scripts) has 3,449 bytes of headroom since the bell's panel and the meeting recorder's buttons moved out of the 27 counted scripts (room101-1011); `BOOT_CSS_CAP` has 6,930.
- A slow or failed fetch of app-features.js and a late Quick access first paint were not exercised.

## Left by the pickers agent (INBOX 784, 785, merged 2026-10-10)

Detail: [pickers-1010.md](../archive/agent-remaining/pickers-1010.md).

- Questions split at quote marks: INBOX 745 (b) decided a quoted prompt is not the person's own question, so the extractor rejects them; the fragments were old rows, now retired on read. Keeping quoted prompts as questions would reverse 745 (b): the owner's call.
- The attached-image thumbnail path in the [[ preview (attachmentObjectUrl) was not driven, only inline images.

## Left by the agentgate agent (INBOX 778, merged 2026-10-10)

Detail: [agentgate-1010.md](../archive/agent-remaining/agentgate-1010.md).

- Needle with the server up but no model leaves Agent greyed: `tools_engine` is reported only when the server is down (routes_chat.py ~2534).
- A failed or slow status poll nulls `modelStatus`, so Agent greys until the next good poll and may flicker.
- Other AI controls still gate on `aiIsOff()`; `model_ready` is the field to move them to.
## Left by the audio80 agent (Brief 80, merged 2026-10-10)

Detail: [audio80-1010.md](../archive/agent-remaining/audio80-1010.md).

- Notes cannot link to or embed a recording yet (only `entry_id`). Search finds recordings now (libr-1011).
- Trim decodes the whole file in the page (about 700 MB of samples for an hour); the sheet now says so from 20 minutes (libr-1011). A server-side cut needs a container writer.
- Brief 81: the stop path is now `meetingRecordingStopped`; transcription goes through `POST /recordings/{id}/transcribe`.
- Not verified: real Whisper on a kept recording; a real microphone, Safari (mp4) and Firefox (ogg).

## Left by the translate83 agent (Brief 83, merged 2026-10-10)

Detail: [translate83-1010.md](../archive/agent-remaining/translate83-1010.md).

- Live translated captions: the dock's Translate button is built (libr-1011) against a fake translator; the real model through the dock is not driven (needs device).
- Only English to Spanish: more pairs are a download block plus a PAIRS row, and the sheet then needs a pair picker.
- The document menu's "Translate this passage..." still hands the passage to chat, not the offline engine.
- Not verified: under 1 s through the sheet on an unloaded machine; a real network install inside the app; WebView2 and Safari.

## Left by the docs76 agent (Brief 76, merged 2026-10-10)

Detail: [docs76-1010.md](../archive/agent-remaining/docs76-1010.md).

- DOCUMENTS 24 row 7 (the list row's ⋮) not built: it would remake INBOX 722; keep the overlay.
- Built (open-1018, HISTORY): DOCUMENTS 24 row 11: 78 controls, none with its own `data-help-for`; one '?' per section plus a command per control.
- `confirmDialog` and `promptDialog` mount on `<body>`, so one asked from inside a modal opens beneath it; app.js is at its gzip ratchet.
- Replace in every document reads each document by one request; and it has no dock-menu row.

## Left by the caption82 agent (Brief 82, merged 2026-10-10)

- The packaged helper: a Download pin per platform (URL, sha256, size) for whisper-server and a model in `core/extras.py` (`id="captions"`; the release asset list was unreadable from the sandbox), then a supervisor that starts it on 127.0.0.1 and sets the URL (`ai/captions.helper_url` reads only the environment today). Linux and macOS have no official binary confirmed. Until then Settings, Packages marks Live captions unavailable and only `MEMORYMAP_CAPTIONS_URL` works.
- Real latency: `scratchpad/captions_audio.py` through a real whisper-server on the reference laptop (`pytest -m captions tests/test_captions_live.py`), then tune `STEP_MS`, `LENGTH_MS` and the `audio_ctx` margin (`ai/captions.py`). Measured here against the fake: median 1.03 to 1.12 s from word start at a 0.5 s stand-in, worst word 1.2 s quiet and 2.2 s under load; whisper.cpp tiny.en 0.51 s and base.en 1.85 s per 5 s window with the cut context on one thread (4 threads ran 25 times slower in this container).
- Accuracy under a cut `audio_ctx` was read on one sentence only.
- Stop saves a note until Brief 80's recording object lands; then `routes_captions._save` attaches the audio and makes the transcript its text; the Audio section (28.5 row 3) takes a status-bar tool for captions.
- `ScriptProcessorNode` is deprecated; an AudioWorklet needs a blob: worker the CSP does not allow (`captions.js` `startLiveCaptions`).
- Not verified: any real whisper-server or microphone, Firefox and Safari capture, Chromium's fake-mic start offset.

## Left by the agent87 agent (Brief 87, merged 2026-10-10)

- Not verified against a real model: whether it plans act-shaped steps `plan_writes` can preview and uses the narrowed tools a planned step is offered (`skill_runner._plan_step_offer`); rows 3 and 4 ran against the scripted fake only.
- Not verified in the browser: Chat's own path for the plan card and per-write undo (`chat-attach.js` onTool); an edit's diff under a step (pytest only).
- The other tabs' starters (Notes, Chat, Graph, Library, Documents) are not in `ai/starter_acts.py`; with no model they get the composed answer (palette.js AGENT_TAB_STARTERS).
- The reading does not take a note by its number ("pin note 12"): `commands._one_target`.
- Dashboard quick links overflow by 4 px at 1440 and 390 (`#dash-quicklinks .launch-group`).
- deepen72a.js's shared overlap measure now ignores a clipped scrolling edge, so other surfaces' overlap counts may drop; undo.js was not run on the agent surface.

## Left by the time85 agent (Brief 85, merged 2026-10-10)

- Timeline row 8's bar, click to rows under 300 ms at 96 notes: 329 at load 6 to 8 (app side 73 to 164); a 57 to 70 ms task right after the rows paint; `content-visibility` on the day sections would cut it but the scrubber reads real heights (timeline.js `drawTimelineWindow`). The boot CSS budget is at its cap (183,300 gzipped, 0 bytes left after this merge: the recall row's rule moved into `.library-filters`): the next timeline or reminders CSS goes in a lazy file, or the timeline's stylesheet becomes one.
- Timeline at 390: the On this day row moves the list down 44 px; a phone may want it folded (`#timeline-recall`).
- deepen72b.js's timeline row at 390 waits for `.timeline-rows` but the phone keeps the table view, so it times out (deepen72b.js:61).
- A `timeline-days` preference arriving after the click renders the timeline twice (once in nine runs at 5,000 notes).
- A monthly repeat from the 31st lands on the 28th in February and stays there (recognise.py `_add_months`).
- timelinepaging.js: the strip-click check fails on the base too; its 100 ms frame check passed once and failed twice under load.
- Not verified: Firefox and Safari permission help, the webview's denied state, firing in a hidden tab (falls to the minute poll), a real non-UTC browser for the completion day maths, Move to an existing category, space or Publish drafts from the timeline bar.

## Left by the palette90 agent (Brief 90, merged 2026-10-10)

- Not verified: the dictionary spelling offer in a live empty result; the server's own correction answered every typo tried, so `finderSpellingOffer` was driven directly (search.js).
- Not verified: an act row against a running model; with no model it opens Chat with the act's opening words at 1440 and 390 and sends nothing (app-palette.js `paletteStartAct`).
- A Settings row whose element is a label or head is focused as that element, not its control ("Accent colour" lands on its DIV at both widths): settings-find.js `openSettingRow`.
- The learned order is exact words only; Raycast also learns prefixes. Recommendation (take it): add the prefix with half weight once picks have a week of use (app-palette.js `paletteRanked`).
- Acts with no stem start with the example's first word ("remind ", "note: "); a stem per act in `act_registry._ACTS` would read better but adds rows to the agent palette's Do group.
- errors.js at 390 stops at its login: a second fill and click (errors.js:86) race an unlock slower than its fixed 2.5 s wait; reproduced on the base commit. Recommendation (take it): wait for `#lock-password` to be hidden.

## Left by the map78 agent (Brief 78, merged 2026-10-10)

The remaining file is in `archive/agent-remaining/`; the rows below are what it left, one line each.

- Row 4 at 390: press to editable 140 to 159 ms against the 50 ms bar (1440 is 24 to 27). Each forced style pass in the add restyles about 830 elements at 390; dropping the root/body/tab-page `:has()` rules one group at a time did not change the count, so the cause is not isolated (`renderWbObjects` measure read, whiteboard.js ~19179, and `wbBeginTextEdit`'s contenteditable read, ~7859, are the two left). Measure on a quiet machine first: load was 4 to 8 on four cores.
- VC12 (Harper on node labels) not started: the budget went to rows 1 to 9. MINDMAP_PLAN "Vendored capabilities to use" still holds it.
- `createConceptMap` (whiteboard.js ~20240) has no caller but app.js's lazy stub list now that every "concept map" entry makes the mind map: delete it and its stub, or say why it stays.
- The More sheet on a map is 59 to 62 rows at 390 (the table plus the map palette); grouped by hairlines but long. A search field or the palette's own filter in the sheet would shorten the walk.
- The tree table, timeline and fishbone are column layouts that tidy the whole map on every add (`wbMapTidyBranchScope`); not timed at 200 topics.
- The fishbone's rib runs behind its causes' boxes (lines are under nodes); the look is not compared against XMind's.
- `maplayouts.js` "tree-left carries the branch bar on the edge the parent is on" fails on the base too (1px against 1px).
- `mapstrip.js`: 5 fails left, all failing on the base as well (shapes stored and drawn, the ring's six slots, the grip drag, Shift scaling, the first pan within 4px).

## Left by the stats89 agent (Brief 89, merged 2026-10-10)

The remaining file is in `archive/agent-remaining/`; the rows below are what it left, one line each.

- Utilities row 5, "every utility has ... a `data-help-for` popover": the timer, stopwatch and Count words are palette rows with no surface of their own, so their in-place help is the row's `about` line and the Guide topic; a '?' needs a surface to sit on (a palette head '?' is a design call for Brief 90). `settings-panes.js` `paletteCommands`, the three rows.
- Statistics row 3 (VC3, Brief 75): the page's two charts use the hand-built `askChartTicks`; tick labels did not collide at 1440 or 390 with this data (0 and 0), not checked at a 0 to 1,240 range.
- Statistics row 4 (Brief 37): the page's "not used lately" list (86 on the fixture) is the feed the weekly offer wants; not wired.
- The week is Monday-first on `user_now`; a Sunday-first locale reads it a day out (`notebook_stats.week_start`).
- Words written this week are the words in the notes made that week; edits to older notes are not counted (no per-edit word delta is stored).
- `EntryLink` rows are counted whole: a link to a binned or private note is still a link on the page (`_notebook_block`).

## Left by the debug70, shell71 and ocr79 agents (Briefs 70, 71 and 79, merged 2026-10-10)

The three remaining files are in `archive/agent-remaining/`; the rows below are what they left, one line each.

### debug70 (Brief 70, the debugger)

- D1's folder again: the brief says `frontend/js/run/debug-*.js`; the pass is `frontend/js/run-debug.js` for ide1's reason (65 lints glob `frontend/js/*.js`). Recommendation (take it): keep the prefix.
- Variables show one level (a repr, 200 characters): no expanding a list or an object into its children (VS Code's tree). `_mm_names` in `PY_RUNNER`, `show` in `_JS_DEBUG_WORKER` (api/run_sandbox.py:186).
- Watches and conditions in JavaScript are evaluated natively over the frame's values (`evaluate`, api/run_sandbox.py:250), not stepped: a watch that calls a function of the script runs a native copy of its value, not the interpreter's function; a watch never changes the script's state.
- JavaScript constructs not lowered for the stepper (classes, destructuring, spread and rest, for...of, default parameters, async and generators, `??`, `?.`, `**`): named with their line and refused (`RUN_DEBUG_REFUSED`, run-debug.js:18). A class lowering is the next most useful one.
- A file of tests (describe/it, unittest) debugs as a plain script, without the harness: the tests do not run under Debug.
- Python breakpoints persist per document for the tab's life (`DOC_DEBUG.breaks`), not across a reload; VS Code keeps them in the workspace.
- Python's runtime still reloads per document opened (ide1's Left row; the frame lives in the panel); the first Debug on a cold runtime waits for it (about 5 s at 1440).
- F11 is shared: Step into while a session is on, Focus mode otherwise (documents.js); the palette row says "F11 while debugging". Brief 71's keybindings sheet should show the context.
- The breakpoint lane is 0.875rem wide (1.5rem under a coarse pointer); touch.js does not measure gutters, so a tap's size on it is not checked.

### shell71 (Brief 71, the IDE shell)

- Debug (Brief 70) is a row of `DOC_PANEL_TABS` since the merge, its pane `docDebugView()`; Ctrl+Shift+D (the registry's newDocument, settings-wiring.js:919) is answered by the editor and stopped there, and has no row in `DOC_COMMANDS`, so the sheet does not list it.
- "the problems panel fed by every linter": harper is a prose linter and prose documents have no panel (the panel is mounted for code files, `docCompletionExtras`); its findings stay in the editor's underlines and F8, not in a Problems tab.
- "the JS parse errors sucrase reports": Problems shows the editor's own JS and TS parse errors (the Lezer tree check, the same lines); sucrase's own message appears only in Output when a run is prepared, not in Problems before a run.
- The console on an .html, .css, .svg or .sql file is JavaScript in a fresh worker, not the page's global: the page runs in a frame whose window the sandbox does not expose (run_sandbox.py `runHtml`).
- A console line that never ends (`while (true)`) is stopped after 10 s (60 s for Python's first line) by terminating the worker, which loses the run's namespace: the next line starts fresh.
- The split's second half carries the language, theme, gutter and wrap of the first, not its completions, lint, snippets or the run panel (documents-ide.js `docIdeToggleSplit`).
- Ctrl+K Ctrl+S opens the palette for a moment before the sheet (the app's Ctrl+K is kept in code files); VS Code waits for the second chord instead.

### ocr79 (Brief 79, OCR)

- Live Text on the continuous (scroll) layout of a PDF: only the single-page stage carries the layer. library.js `ocrBuildScrollPages`.
- An image's whole reading deleted from the lightbox or the gallery's row menu still clears without the bin (only the workspace's deletes were moved). library.js callers of `analyseMediaRow(..., { text: "" })` outside the workspace.
- Undoing a fresh read writes the old text back through the text route, so it keeps the new read's model name ("Read by X") rather than the old one's. library.js `ocrTextWriter`.
- `undo.js` (the trust sweep) does not walk the OCR workspace; `ocr79.js` measures it instead.

## Left by the atlas84 and companion2 agents (Briefs 84 and 34, merged 2026-10-10)

Atlas everywhere (Brief 84, CHAT_PLAN F5, the four steps built):

- "new ways to do and output info" (INBOX 758): the Ask box ignores the `chart` event (capture-ask.js Ask handlers, ~3065); only the Chat tab draws it (chat-attach.js `onChart`).
- "the other one" (decision 57) in Chat: `routes_chat._spoken_act` sends `objects` only when the client puts them on history turns; chat-attach.js does not yet send each answer's note titles.
- "more access" (INBOX 758): write tools that are not acts (create_category, rename_tag, delete_tag, merge_categories, board and map tools) are named by the reading but not run with no model; each needs an act row in `act_registry._ACTS` with an inverse.
- The Guide's "how do I set a reminder" first line is the topic's first matching sentence ("The Reminders tab groups items..."), not the step that sets one: `composer.help_line` picks by shared words (composer.py `help_line`).
- INBOX 731 (the Guide failing with a model): not touched; the model-path fallback in `help_chat.answer_stream` still needs the log line read.
- Guide rows 4 to 6 (CHAT_PLAN "The Guide" table): trust-surface topics, the weekly unused feature, typos through the word list (VC15).

- Brief 84, not verified: the Guide's new first line and act topics in a browser (API and unit tests only); no real model.

The companion (Brief 34, second round: faces at 28 and 20 px, the tail on the compositor, reduce motion, calm's arms; smoothness measured only):

- The rest of Atlas's idle cost is the companion's own behaviour, not the
  tail: with the tail and breath switched off, 670 recalcs and 130 layouts a
  minute remain (recalc probe), all from avatars.js timers. Decision 7's 1 ms
  needs the behaviour picker and perch checks profiled next.
- The chest's breath still writes the torso's `scale` 2.5 times a second at
  rest (atlas-life.js `atlasBreathFrame`): a recalc and a layout each. Zero
  needs the torso on its own layer root (a drawing change, `atlasDrawFigure`).
- 104px faces (the welcome, the large view): 2 to 3 of 15 distinct in light by
  the same metric; the cue is drawn only at the head and tiny levels. The
  owner's "I barely get to see atlas change expression" may also mean the
  companion figure (12px face); a cue on the figure is the next step.
- Step 5 not built: one curve table for every joint (120 to 400 ms), the
  idle pool's never-within-five rule and a reaction budget a minute beyond
  the existing 6s gap (avatars.js `NMB_REACT_GAP`). The one snap (both hands
  jumping over 4px out of stillness while hanging, atlasdepth2.js atlassmooth) is likely
  the held arms' crossfade (`atlasRigRead`, -158 degrees); one latency trial
  of five was over 100 ms, the frame wait under load.
- Arm angle over a walk cycle not measured (atlasarms.js measures still
  poses; the walk swing is the rig's, atlas-motion.js `atlasRigFrame`).
- `#nm-buddy:has(.atl-figure) .nm-buddy-char` and the lower layer still slow
  to 6s under the hint (08-consistency.css, the block after the chin hand
  rule) rather than stopping: they may carry acts, so left for a driven check.
- Companion movement Full keeps the script loops (tail, rings) under Reduce
  by design (`atlasMotionOK`); the CSS loops stop under the hint regardless.

- Brief 34, not verified: the arm angle over a walk cycle; 104 px faces (2 to 3 of 15 distinct in light); no real WebView2 or WebKitGTK; all timings from a loaded machine.

## Left by the wb77 and ide1 agents (Briefs 77 and 69, merged 2026-10-10)

Whiteboard (Brief 77, rows 1 to 4 built; 8 and 9 not started):

- Row 8 (rule 6): "every rail and top-bar control has a `data-help-for` popover and a palette row; 0 missing". Not built. A first count from the DOM (`#wb-topbar`, `#wb-tools-panel`, `.wb-board-menu` controls against `WB_COMMANDS` by `data-wb-cmd`, `run.tool`, `run.clickId`) found 240 controls and 166 with no table row, but the board picker's rows and the View menu's switches inflate it; the measure needs the picker excluded and the switches counted once (whiteboard-commands.js `WB_COMMANDS`, index.html 6267 to 6560).
- Row 9 (rule 12): "a board AI act as one chat tool (summarise this board; a board from a note)". Not built: a tool under `src/memorymap/ai/tools/` with its test, README's tool count (`tests/test_readme_freshness.py`), deepen72a.js's "No model" row before and after.
- Row 2's New is still a menu (`details#wb-boards-new-menu`): a split button (DESIGN.md's recipe) would make it one press; tour.js and reveal-targets.js name the menu's id.
- `tests/test_icon_conventions.py::test_the_vertical_kebab_is_only_at_the_end_of_a_vertical_list_row_or_in_a_narrow_column` fails on this branch's head before this work: search.js has a vertical kebab the ratchet does not list.
- `errors.js` at 1440 and 390: 0 errors, 0 layout findings each.

Code editor (Brief 69, I1 built):

- D1's folder: the brief and D1 say `frontend/js/run/`; the files are `frontend/js/run-*.js` because 65 lints (`test_frontend_symbols`, the em-dash and innerHTML lints, the global scope ratchet) glob `frontend/js/*.js` only. Recommendation (take it): keep the prefix; a folder needs every lint made recursive first.
- D5 "load this CSV document as a table": the sandbox's SQL worker takes `tables: [{name, columns, rows}]` (`_SQL_WORKER`), but no panel action picks a CSV document and sends it yet (`run-core.js`, the sql row).
- D9 stdlib completion and signature help from a generated table (`scripts/gen_python_completions.py` over the installed Pyodide's `inspect`): not started.
- D9 `ruff-wasm` lint and format: DOCUMENTS 25 row 4's (Brief 42's linters), not started here.
- D6 `.md` preview in the sandbox frame: not done; a Markdown document already has its own Live and Split views.
- Python's runtime reloads on every document opened (5.9 to 7.0 s cold at 1440): the sandbox frame lives in the panel, which is rebuilt per document (`docRunPanel`, documents-code.js). One frame kept across documents would make a second .py run warm.
- `input()` is answered before the run (the Input box), not interactively mid-run: that needs `SharedArrayBuffer` and the COOP/COEP headers, which are D2's (Brief 70).
- p5 in the sandbox logs "Permissions policy violation: accelerometer" to the console (p5's devicemotion listener in a frame without `allow`); harmless, not silenced.
- A JSX `.js` document (the `jsx` alias) runs without the JSX pass; only `.tsx` paths get it (`runStripTypes`).

- Brief 69, not verified: the desktop webview; dark theme for the new panel rows; a large SQL result; touch.js on the other surfaces.
- Brief 77, found: the shape flyout opens only from its 10 px caret or a long-press, too small for a finger on a phone; boot CSS is within 12 bytes gzipped of its budget.

## Left by the design agent (Brief 56, merged 2026-10-10)

- 110 distinct controls show no change on keyboard focus (`a11yname.js`, 312 stops over 14 surfaces): every `.status-item`, the `.ghost.small` buttons, the status bar; a focus ring rule in the stylesheet's grammar (Brief 57).
- Eight dialogs open as centred cards at 390 and should be bottom sheets (extract, history, connections, binned, run a skill, board keys, meeting notes, features): Brief 59.
- Six of 14 content docks show more than seven items at 1440 (Notes 10, Graph 9, Library 9, Chat 8, Timeline 8, Boards 8); fold by count, 13.1 row 2 (Brief 57).
- The markup has 18 overlays plus the built confirm and the tour card, not the plan's 15; `$S/design/hierarchy.json` lists each with its size (Brief 59 reads it first).
- Not measured by Brief 56: 1024 and 820 widths, dark-theme counts, a Chat with a conversation, the document AI panel, a board with a selection.
- The 13.0 gate's "every offence per decision" for decisions 9 to 17 are stylesheet counts from the plan's method paragraph, not from the sweep; still to be read from code (Brief 57).

## Settings and help

- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": INBOX 235, the Settings Help page and the Models order; INBOX 237, the built-in Librarian persona is Atlas; "Advanced response settings" sits 20.8px right of its siblings; `#settings-tools`'s intro; scratchpad/ui-sweeps/help-popovers.js is not built; "Not one of the seven tabs carries a `data-help-for` popover"; The learning loop's Settings section (I9's frontend) is not built.
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05 (the pre-0.4.0 buildable rows, sweeps on port 8815)": The OCR workspace head could not be measured.

## Backend

- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": Security review of the backend batch (2026-09-26).
- **`netbind.host_allowed("localhost.")` and a trailing-dot own name are
  refused** (fail closed, as intended; noted so nobody reads a 421 on
  `localhost.` as a bug). `_own_names()` calls `gethostname` per request
  off loopback, one syscall.
  *Left: intended behaviour, noted so a 421 on `localhost.` is not read as a bug.*
- ~~The other search surfaces still do their own thing~~ Closed. The account is in HISTORY.md, "OPEN.md rows closed, 2026-10-05 (the open-ledger pass)".
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": No FTS index rebuild job; A bulk write can leave the index stale; The vector matrix forgets by zeroing a row; has: only knows file.
- **The graph signal needs an open note, and the Notes list rarely has one.**
  `file: frontend/js/app.js`, `id: search-open-note`. The list passes `entry_id`
  only in rows view or while editing; in card view the third signal is zero.
  Next step: decide what "open" means on that surface, per the app's own focus
  model. [brief11-retrieval-engine.md]
  *Needs: what "open" means on the card view is a decision.*
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05": Global undo of an AI action: a skill run's Undo.
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": The Timeline and Dashboard activity strips.
- **Sync (B6) as log shipping.** `id: events-sync`. Unstarted and no longer
  blocked: it needed the retention rule, which now exists. A compacted
  snapshot ships as a snapshot. [brief7-event-log.md]
  *Needs: a large unstarted feature.*
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": filing_state = "auto" is set on the two create paths only; The Reminders tab still reads one page; Other first-page-only callers, one call each; POST /learned/bulk.
- **I1's later passes**: duplicates, entities and dates as kinds in the same
  table (tensions are built: pass 4 of the night run, `ai/facts.py`
  `_pair_passes`). `ai/entities.py` already produces entities in its own
  shape; folding it in means giving it a span and a `DerivedFact` row, not a
  second pipeline. [learning-loop.md]
  *Needs: design, folding entities into the fact table.*
- ~~**The morning card**~~ built 2026-09-26: the "While you were away"
  Dashboard widget (HISTORY.md, "Moved from the plans, 2026-09-26").
- **`evidence_checks` is the one switch with no runner**: stored and shown in
  Settings, gating nothing. `margin_reader` (`api/routes_editor.py`),
  `model_bench` (`api/routes_bench.py`) and `open_questions` (`ai/facts.py`,
  the night pass) read theirs. Evidence cards are built per answer sentence
  (`grounding`, `search/chunks.py`) with no background pass to switch off.
  [learning-loop.md]
  *Needs: a decision on what the switch gates (the per-answer evidence view, or a future background check).*
- **WORLD_CLASS_PLAN 9's dev-only llama.cpp runner is the blocker behind four
  open items**: the `evals` marker, Skills Phase D's central claim, the
  retrieval engine's real-embedding numbers, and the paging nudge a real small
  model would have to act on. The suite must never depend on it.
  [brief-13-harness.md, chat-timeline-skills.md, brief11-retrieval-engine.md]
  *Left: the runner exists now (`scratchpad/llama-dev.sh`); the four items still need a model.*

## Sweeps and tooling

- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05": `scratchpad/ui-sweeps/editor.js` still describes the retired editor; `contrast.js` never visits the Documents tab.
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": `menus.js` timing out at its last step; `notessubtabs.js` (removed 2026-10-12, recoverable from git history) counting the hidden native selects.
- **A check that cannot tell "nothing matched" from "labels are broken" cries
  wolf on every small fixture.** Two of `graph2.js`'s five failures were
  exactly that, measured on a scratch profile holding a single note. The
  lesson is the sweep's, not the graph's. [graph.md]
  *Left: a lesson for the next sweep author.*
- **The README tour still has two gaps.** The chat screenshot shows an empty
  conversation (no model in the sandbox), so a machine with Ollama should
  retake `docs/screenshots/chat.png` with a real exchange; and the page reader
  has no shot at all, because it wants a multi-page PDF and an OCR binary and
  this sandbox has neither. Files: `scratchpad/ui-sweeps/readmeshots.js`, the
  `chat` entry. [picker-catalog-readme.md]
  *Needs: Ollama and a Tesseract binary.*
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": "`app.js` is 1.93 MB of source".
- **The launchers want one run on a real Windows machine**: `start.bat`,
  `start.bat --doctor`, `start.bat --shortcut` and `uninstall.bat --dry-run`,
  watching the splash through a first-run install. Everything else in Brief 17
  has been exercised. Two things deliberately left: Copy diagnostics copies
  the step history rather than running `--doctor` live (which would probe the
  port the app is about to bind and talk to the git remote mid-install; the
  safe shape is a `--doctor --offline`), and the dry run's "frees about"
  figure counts `.venv` only on Windows, which is 300 MB of a 305 MB answer.
  [launcher.md]
  *Needs: Windows.*
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": A changelog edit breaking `test_docs_site.py`.

## Carried from the agent files archived 2026-10-04

Thirty-three finished agent files moved to [`../archive/agent-remaining/`](../archive/agent-remaining/)
(their finished work is in HISTORY.md; the files had stopped being written to). What each still held that is open is one row here, tagged; the
archived file has the measurements. Rows that were already in this ledger, or
that the head had since built, are not repeated; the ones the check found built
are named in HISTORY.md, "OPEN.md rows closed, 2026-10-04".

`asktab`, `boot`, `briefs-2026-09-13-night`, `chrome-help`, `documents-tail` and
`readings` hold nothing that is not already a row in this ledger or built on
the head, so they carry no row of their own.

- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05": anim.md.
- **arch.md (removed 2026-10-12, recoverable from git history)**: INBOX 266's usability and lightweight items belong to nobody.
  [arch] (The emblem's idle cost is built: HISTORY.md, "OPEN.md rows closed,
  2026-10-05 (docs hygiene before 0.4.0)".)
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05": askcite.md.
- **backend-0926.md**: F7's thread modules
  onto `core/jobs.py` (13 left, `tests/test_flaw_class_lints.py`'s ratchet).
  Not verified: the receipt against a real outbound call, the five UIs in the
  desktop window, LAN from a second device, the `.ics` in a real calendar app.
  [backend-0926]
  *Needs: a second device, the desktop window and a calendar app, for the unverified list. The Undo row, the night card's scroll and the ledger's flush are closed, HISTORY.md, "OPEN.md rows closed, 2026-10-04".*
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05": chat-0926.md; chrome2.md.
- **codecomplete.md**: Python Run via a Pyodide download extra (INBOX 404's
  recommendation, needs the owner's yes to a download kind of extra) and
  TypeScript Run via a vendored type-stripper; SCSS, Less and SVG are not file
  types, so Emmet has nowhere to run for them. Not verified: WebView2's
  handling of the run sandbox's CSP, the native colour picker's window.
  [codecomplete]
  *Needs: a decision and a vendored dependency each.*
  *Needs owner, 2026-10-05: a Pyodide "download extra" fetches at runtime, which the owner's fully-local rule of 2026-10-05 forbids unless it is vendored (about 10 MB, MPL-2.0); the TypeScript stripper is a vendoring call of the same kind.*
- **companion-r5.md**: the toss on a phone (a quick swipe on the companion
  tosses it) was not tried on a device; `test_unlock_throttle_per_client.py`
  failed once under load and passes alone. [companion-r5]
  *Needs: a phone; the flake is load, not the test.*
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05": featuremodels.md; guide.md.
- **guideia.md**: the Guide is a modal sheet whose scrim dims the app, so
  "Open the Reminders tab" cannot be read against the tab. [guideia]
  *Needs: a non-modal Guide changes `openSheet`'s focus and backdrop contract.*
- **libtl-0926.md**: the Timeline feed lays out about 39 times a second while
  scrolling (the rows' `content-visibility: auto`, INBOX 400's trade); the
  Library search keystroke was 17 to 191ms under load, not re-measured idle;
  the "Mind maps" chip at zero offers "New concept map" (a naming decision);
  Atlas's feminine right arm sits behind the hair at full size; a mood or act
  change swaps loops rather than cross-fading; the graph tab keeps the
  companion on the bottom bar. [libtl-0926]
  *Needs: drawing-order and animation-blend changes; the rest are measurements to retake idle.*
- **mapcull.md**: freehand and link sketches are not culled (a stroke's box is
  parsed from its path; worth it only when a board with many strokes measures
  slow). [mapcull]
  *Left: measure a many-stroke board before building.*
- **mapread.md and maprender.md**: 13g, the haywire middle-button pan, needs
  the owner (it never reproduced headless; do not fix blind); the 50-topic
  open is 393ms and not the render; `mapperf.js` takes minutes (whether the
  gate should pass `SIZES=50`); the keyed render is invalidated by one list,
  `wbObjectPaintKey`, which a new paint input must join. [mapread, maprender]
  *Needs owner: 13g. Left: the rest are notes for whoever touches the paint.*
- **maptheme.md**: the theme is resolved into each node on export rather than
  carried; an `<arrowlink>` written by FreeMind itself is untested. [maptheme]
  *Needs: schema and export design.* (The palette, the font and the pin back to
  the app's default are built, MINDMAP_PLAN 13e.)
- **mindmap2.md**: `mindmapimage.js` (removed 2026-10-12, recoverable from git history) passes 12 of 12 at 390x844 (measured
  2026-10-04); a picture node does not resize to its picture; `mindmap3.js`
  times out at `#wb-boards-generate` (the AI half); `mindmapcurve.js` at
  390x844 passes 11 of 14 (its map is laid out wider than a phone, so the
  hover reveal and the straight-line kink aim at off-screen handles: the
  probe's layout, not the app; the add-button overlap that timed it out was
  the app's and is closed, HISTORY.md). [mindmap2]
  *Needs: lay the curve probe's map out inside 390 wide. Tried 2026-10-05 (topics 110 wide at x 8, 220 and 250, `mindmapcurve.js`): the reveal check passes (the handle's top element is the svg layer, not a button) but every drag moves 0 (9 of 14), so the layout is not the only thing at 390; not kept.*
- **ocr-reading.md**: a page joins the reading panel only once looked at or
  read (nothing reads ahead, deliberately); nothing was verified with a real
  Tesseract or a vision model. [ocr-reading]
  *Needs: Tesseract and a model.*
- **pass2.md**: typing in a note in a 230-note list costs about 12ms of
  CodeMirror input handling per key; the Library's lists have no user-owned
  order to drag; grey-scale text in composited scrollers on a 1x ClearType
  display was not seen. [pass2]
  *Needs: a Windows display; the rest is CodeMirror's own cost.*
- **perfpolish.md**: the document gutter writes a height and reads a layout
  per gutter. The menu exit is closed, HISTORY.md, "OPEN.md rows closed,
  2026-10-05 (the pre-0.4.0 buildable rows, sweeps on port 8815)". [perfpolish]
- **uipolish-0924.md**: the surface-by-surface pass (its item D) is already a
  row above. Triaged: `deadbtn.js`'s findings for Chat's `#chat-export` and
  `#chat-delete` are visually-hidden, `aria-hidden` proxies the ⋯ rows click
  (index.html ~2335), the sweep's finding and not a dead control; the
  Packages rows' title-to-description gap measures 12.8px at 1440, 1024, 820
  and 390 (`packagesgap.js` (removed 2026-10-12, recoverable from git history)), not the 16px reported. [uipolish-0924]
  *Needs: item D, a design pass per surface.*
- **wbtopbar.md**: `#wb-search-toggle` and `#wb-navigator-toggle` duplicate View
  menu switches (UI_MODERNISATION_PLAN Phase 8 names them as the bar's find
  zone); `#wb-context-menu` is not swept (`wbcontextphone.js` is where it
  belongs). INBOX 47's counting question no longer decides anything: the
  Notes and Library docks measure 6 controls each (`docks.js`). [wbtopbar]
  *Needs: the whiteboard agent (a sweep for `#wb-context-menu`).*
- **whiteboard-tail.md**: the AI half of the map needs a model. INBOX 276 (the
  sketch pad's toolbar at 820) is closed, HISTORY.md, "OPEN.md rows closed,
  2026-10-05 (the pre-0.4.0 buildable rows, sweeps on port 8815)". [whiteboard-tail]
- **world-class-rows-1-2-9.md**: two decisions taken differently from Brief 15
  (S1 is a cookie, S3 confines to home and the data folder) that the owner may
  want to confirm; the export-folder preference accepts any writable absolute
  path; a clean full-suite run on that worktree was owed.
  [world-class-rows-1-2-9]
  *Needs: the owner's yes or no on the two decisions and on the export-folder path rule.*
- **writing-desk.md**: Stop mid-pass is unverified (the stand-in answers in
  about 150ms; a slow backend behind an env var in `fake_openai_server.py`
  would do); the thinking panel has never held real thinking; the five draft
  prompts are tested, not judged; sources are notes only. The readOnly hole
  it named is fixed (CHANGELOG, `draftreadonly.js`). [writing-desk]
  *Needs: a slow backend and a real model.*

No per-agent file stays in this folder: the 2026-10-05 pass carried the last
ones' rows below and archived them (`agent_common.md` and `agent_rules_1005.md`,
the rules every agent carries, stay). A running agent writes its own
`<name>.md` here; the next ledger pass carries what it left.

## Carried from the agent files archived 2026-10-05

Thirty-eight finished agent files moved to
[`../archive/agent-remaining/`](../archive/agent-remaining/) (no agent was
running; the finished work is in HISTORY.md). Each row below is what a file
still held that the code, INBOX, BACKLOG and the plans do not already hold,
checked by grep on the head the day they moved; the file named in brackets has
the measurements. Items the plans already carry (the Atlas rows 540 to 575,
WORLD_CLASS_PLAN's B2 and I7 rows, the web clipper's page intake,
UI_MODERNISATION_PLAN's off-band widths, WHITEBOARD_PLAN decisions 30 to 36's
ghosts, line jumps and carried waypoints, AGENT_SKILLS_REFORM's skill-run Undo)
are not repeated. Found built since and dropped: the entity merge Undo, the
note-type, space and conversation delete Undos, `autonomous.reset_state()`,
the `settingsnav.js` skip below 640, `stripground.js` and
`settings-skeletons.js` on the branch, the board card's expanded state (INBOX
238), the lazy graph popup resize stand-in, the reminder chime primed on the
first press, the OCR reading's collapse, Atlas hiding behind a modal, the
Atlas persona text in Settings, the spelling "Boards & maps" and the About
pane's name, the errors sweep's aside clipping at 390.

### Notes, Documents and Library

- **Skeletons for a board's Library and Notes tabs** (INBOX 596): the tabs
  (`whiteboard-library.js`, `wbLoadLibrary`) draw nothing while they load.
  [boardmap-1005, small-1005]
  *Left: the whiteboard's own rail, owned by the WHITEBOARD plan's agent.*

- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-05 (the pre-0.4.0 buildable rows, sweeps on port 8815)": Skeletons for a board's Library and Notes tabs (INBOX 596).
- **Phone selection menus and the selection bar** (documents): iOS and Android
  draw Cut, Copy and Paste above a selection, where the bar also goes; if a
  report arrives the bar goes below the selection on `(pointer: coarse)` (one
  line in `selectionBarShow`). Section 18's chat commands on a phone press
  controls in the chat dock and were never measured against it.
  [documents-1004]
  *Needs: a phone.*
- **Prose tools**: Harper's lint config per kind in the dictionary dialog
  (`harper-worker.js`, `setLintConfig`; about 200 rules, all or nothing today);
  suggestion mode's author and date (CriticMarkup `{>>comment<<}`; export
  writes `MemoryMap` for every revision); a voice and speed picker for read
  aloud (system voices only today). [proseeditor]
  *Checked 2026-10-05: neither is built (`harper-worker.js` turns off the one rule `UseTitleCase` in `HARPER_RULES_OFF` and nothing else; `docReadAloudVoice` in `documents-prose.js` picks the first local voice for the language). Needs a design call: where the two controls live (the dictionary dialog, Settings), what is stored, and the help that moves with them.*
- **Package bundles**: the Word writer's five tests ran once in a scratch venv
  with python-docx 1.2.0 (2026-10-05, `tests/test_docexport_pictures.py` 13 of
  13, none skipped; `test_docexport_bundle.py`, `test_document_import.py`,
  `test_docview_import.py`, `test_extras_bundles.py` 57 passed), but no export
  was opened in Word or LibreOffice; no real pip ran (every bulk test fakes `subprocess.Popen`);
  the bundle groupings are a recommendation (`BUNDLES`, one tuple); the phone
  rows measured clean, not designed further. [extras-bundles]
  *Needs: Word or LibreOffice.*
- **The Writing Room's stretch**: measured at 1440x900 light on the two
  `NOTE_SURFACES` boxes only, the graph's two note boxes not opened. (The table
  full view's X is built: 28x28 at 1440 and 44x44 at 390, each equal to
  `--target-min`; `tablefullclose.js` (removed 2026-10-12, recoverable from git history) asserts it. Its phone width and the Writing
  Room's are closed, HISTORY.md, "OPEN.md rows closed, 2026-10-05 (the pre-0.4.0
  buildable rows, sweeps on port 8815)".) [notes]

### Whiteboard, mind map and Atlas

- **Board and map history**: an agent's or another tab's change is not on a
  board's stack (decision 17 says the event log is the long memory; a board's
  undo survives a reload since 2026-10-05, `undo-store.js`); redo of the board-level steps (theme,
  numbering, layout) is not swept; `wbMapCrossLinkToBranch`,
  `wbMapReverseCrossLink`, `wbMapCutCrossLink`, `wbMapAddReference`,
  `wbApplyMapTemplate`, `wbArrangeMindMap`, `wbMindMapAddCard`, bucket fill and
  fit to text are recorded through `wbRecordGesture` but not swept one by one.
  [undo-1005]
- **Draw.io phase 2's tail** (WHITEBOARD_PLAN 30 to 36 hold the decisions):
  Phase G's affinity sort (Group by theme proposes named frames, one Undo) and
  the claim check, both with faked-transport tests and
  `agent.PROSE_BUDGET_CHARS`; the time machine's plain-words "what changed";
  expand from my notes (MINDMAP_PLAN 12.3 item 2);
  ports are mouse and pen only (touch has no hover). Found: SQLite reuses a
  deleted row's id (no AUTOINCREMENT on the board item tables), so one id's log
  can hold two items; the board history starts a fresh state on each `created`
  but any other reader of an item's log (`events.replay`) would merge them;
  placements made before the history, a duplicated board's copies and a
  generated map's topics have no `created` event. [wb-phase2]
- **Frames and the map plan's rest**: MINDMAP_PLAN 12.2's rest (a boundary round
  a lassoed set that is not one branch, priority, progress, flags and due
  dates, floating topics and palettes, an outline pane). The nested frames'
  shared title area is measured, HISTORY.md, "OPEN.md rows closed, 2026-10-05
  (the pre-0.4.0 buildable rows, sweeps on port 8815)". [harness-wb-1004]
- **Map render and persistence**: (the `wbMapNodeSize` 94px row is closed,
  HISTORY.md, "OPEN.md rows closed, 2026-10-05 (the pre-0.4.0 buildable rows,
  sweeps on port 8815)"); a map does not re-frame
  after a tidy (a decision: frame after a tidy that pushed content off the
  canvas, or rely on Fit); tidy, copy branch and
  "open every folded branch" persist one node per request (a bulk endpoint if
  any ever matters); `mapstyle.js` (removed 2026-10-12, recoverable from git history)'s "radial slot" check reads `w: 0` on the
  base too. [mindmap, mapux2]
- **The Boards and maps dashboard widget's tall maps**: a 25-topic tree-right
  map draws a 20x40 paper in the 72x40 row box. Cropping a tall map or a
  square box is the owner's judgement. [mindmap-13e]
  *Needs: the owner's call.*
- **Atlas motion, measured left** (the owner's rows 554 to 575 are above):
  `atlas619-blend.js` stepped by hand shows laughing's end moving the figure
  about 3px over three frames, base and fix alike (390 dark: the masculine
  tilt's start 7px, the feminine wiggle's end 3.3px; not isolated, trace the
  figure box's computed transform per stepped frame at 390); `atlas601-tail.js`
  still reads the tail's tip still for 1.8 to 2.2s under load 15 to 21
  (re-measure on a quiet machine); at 390 the props and viewer sweeps ran 2 to 7
  frames a second, so the coil, the moon and the feminine sit's calm read under
  threshold there; the masculine cloak's flare leaves the torso's taper at the
  join by 0.1 to 0.2 drawing units. Deferred since 2026-09-27: an arm rig for
  poses that cross in front of the body (hands on hips, clasped, to chest; the
  arms are separate svg roots behind the body in every look), and a fuller
  front hair mass for the feminine look (the owner at release). The Atlas guide
  panel's '?' did not reproduce (needs the owner's case). [atlas-1005, wrapup-0927]

### Settings, help and the shell

- **Help audit's remainder**: menus drawn on press (the chat "/" menu, a
  message's menu, the board menus, the notes list's menus) are checked by
  source grep only, and a sweep that presses each and lists its items would
  close it; the JS-built popovers (`manage-cat-help`, `manage-tags-help`,
  `inbox-help`) and the whiteboard and map help bodies were not read; the sweep
  runs at 1440 only, so a control a narrow window moves into a menu is named for
  the wide layout. [helpaudit-1005]
- **Chat panels not measured**: `#chat-model-panel` with a model connected
  (`popupsart.js` (removed 2026-10-12, recoverable from git history) cannot open it without one; use `scratchpad/llama-dev.sh`)
  and the chat dock's select menus opened from inside the How it answers sheet
  at 390. Status chips: WORLD_CLASS_PLAN 1.2's wording and DESIGN.md's label
  recipe disagree (taken: the label recipe, `META_EDGED`; if the owner wants
  statuses edgeless it is one rule, `.chip.item-label`'s border). [design-1004]
  *Needs: the owner's call on the chips.*
- **The tour**: the Timeline's Options and the reminders' More were measured at
  390 only. (The fresh data dir walk and widths 600 to 1100 are done, HISTORY.md,
  "OPEN.md rows closed, 2026-10-05 (the pre-0.4.0 buildable rows, sweeps on port
  8815)".) [tourdepth]
- **Tablet layouts**: the Documents dock is two rows at 1024 (its identity
  asks for 22rem beside the actions); the arc layout of a 430-note notebook
  framed whole is a line of dots until zoomed; the Notes sub-tabs do not fit the
  list dock's row at 1093 (on a window 700px tall or less the strip could take
  the identity slot as a compact seg, which changes the dock grammar: the
  owner's or the plan's decision). The status bar's fold into the top bar under
  680px is not built, and measured it overlaps nothing, HISTORY.md, "OPEN.md rows
  closed, 2026-10-05 (the pre-0.4.0 buildable rows, sweeps on port 8815)".
  [graph-wb-0926]
- **Dashboard and Timeline**: D6's streak (the calendar strip and the day
  before and after are built, `daystrip.js`; a streak count has no surface:
  the dock is at its grammar and `.dock-chip-row` is held at zero uses); "Undo all" for a
  background pass or a skill run (each change has its own Undo; an honest "all"
  needs `tools.execute_tool` to run the undos in one transaction, or it is N
  requests that can half fail); the graph signal needs an open note, and the
  Notes filter uses `/search` for operators it does not know. [openitems]
  *Needs: design steps, each its own brief.*
- **The capture draft counts as unsaved work**, so every tab switch with a
  draft asks "Leave without saving?" though the draft is kept and the switch
  loses nothing: a decision, not a bug. [wrapup-0927]

### Backend, architecture and tooling

- **ARCH-02, the save at 5,000 notes**: `POST /entries` p50 210 ms (one line)
  and 345 ms (400 words), not under 150; 390 to 615 ms with 384-wide vectors
  against 61 to 96 ms at 500. The profile (`scratchpad/perf2-1005-prof.py` (removed 2026-10-12, recoverable from git history)):
  the lexical pass walks all 4,000 kept docs per save, `nearest` reads up to
  4,000 postings, `janitor._knn_match` takes 52 ms over the matrix. Tried and
  reverted: a test instead of a list and per-category counts in the corpus
  (exact, removed the walks, not the time). Next: a smaller postings budget
  measured with `scratchpad/filing_eval.py`, or the k nearest read from the
  engine's matrix once per save. [arch1005, perf2-1005]
- **The rest of the architecture audit** (`scratchpad/audit1005/arch.md` (removed 2026-10-12, recoverable from git history)):
  ARCH-04's client half (the cursor exists, `after` and `X-Next-Cursor`, but
  `notes-list.js` still reads every page by offset into `allEntries`); ARCH-13
  (response models for the busiest routes and one paging helper; the shape lint
  is built); ARCH-16 (follow-ups are skipped while a turn streams but there is
  no preference and no hardware probe saying "CPU only"); ARCH-22
  (`skill_runner._run_one_step`, 425 lines, and `agent.run_agent`, 416, need a
  state object before they split; `scratchpad/perf2-1005-longfns.py` (removed 2026-10-12, recoverable from git history)); ARCH-10
  (the import-cycle ratchet holds 15 and 3); ARCH-25 (the pool size, a chat
  stream holding its connection, `restore_backup` with sessions open: read, not
  reproduced). ARCH-09 stays as built: `file-entry` shares the one-wide model
  lane with captions on purpose. [arch1005, perf2-1005]
- **The frontend audit's leftovers** (`scratchpad/audit1005/frontend.md` (removed 2026-10-12, recoverable from git history)):
  FE-09 unused CSS (no coverage-driven deletion started); FE-10 Settings panes'
  markup is not fetched on first open (a `<template>` is still parsed and boot
  code reads Settings ids; a real gain moves every boot reader behind it);
  FE-11 the 720 and 640 groups (26 + 6 and 11 queries, each needing its own
  sweep); FE-13 the tab JS at 5,000 notes was not profiled again; FE-14 on a
  phone the chips' overhang is 44px and a card clips it below its last row
  (34px reached). [perf2-1005]
- **Retrieval and the learned loop, plan rows whose half-built parts live in
  the scratchpad**: "most opened this month" is parked in
  `scratchpad/wc1005b-most-opened.md` (removed 2026-10-12, recoverable from git history) (`core/opens.py`, `GET
  /entries/most-accessed?period=month`, hooks on `flashEntry` and
  `openNotePage`, the Most used widget's seg, then the HISTORY block and a
  CHANGELOG line); the "wrong" correction on an evidence card (I7's second

- **A flaky timing test**: `tests/test_relations_kg2.py`'s 10k timing is flaky
  under load (the typo, message-wording, thread-ratchet and list-paging tests
  perf2-1005 and worldclass-1004 recorded as red pass on the head, 2026-10-05).
  [perf2-1005]
- **Retrieval and the learned loop, plan rows**: the "wrong" correction on an evidence card (I7's second
  half) and I1 pass 2's kinds as derived facts (dates, duplicates, entities)
  are WORLD_CLASS_PLAN rows. [worldclass-1005b, worldclass-1004]
- **Smaller backend and gate rows**: a note type made through `POST
  /note-types` before the list was read, then deleted, loses its id on Undo
  (not reproduced, pinned by a test); `gate.sh --changed` selects most of the
  suite on this branch; `tests/test_name_mood.py`'s palette test needs
  the palette decided; the container's shared `/tmp/pytest-of-root` grew to 11G
  once and filled the filesystem (`rm -rf` it); the Guide's longest topics sit
  at 1,916 of 1,920 characters and boot CSS at 183,210 of 183,300 gzipped
  bytes, so any new rule needs dead CSS cut first.
  [integ-1005, open-rows-1005, wb-phase2, sweeps, backend-probe, boardmap-1005]
- **Sweeps**: `touch.js` needs `timeout 300`;
  `revealcell.js` at 390 needs the editor opened first; `errors.js` took
  "Target crashed" at a tab switch (2026-10-05): it did not reproduce on a fresh
  data dir, so the sweep is hardened (a browser per width,
  `--disable-dev-shm-usage`, a crash reported as a finding) and the cause is
  named by its signature, not measured. [sweeps, small-1005, backlog-1005b]
- **Not verified**: Quit's 0.72 opacity contrast is computed (about 3.1:1
  light, 5:1 dark), not read from pixels; the line numbers' baseline drop is
  measured in the sandbox's system-ui only (Segoe UI has other metrics); the
  Windows rasteriser at 125% and 150%; every tablet and phone number is
  Chromium emulation; a real model for the Atlas, retrieval and skill rows.
  [design-rows-1005, quick-gutter, iconalign-skel-1005]

## Atlas, placed from INBOX 2026-10-05

Held by the Atlas motion agent; each closes when its sweep measures it.

540. **The owner, 2026-10-05, verbatim.** "one of the feminine atlas blinking
     animations has MASSSSIVE eyebrows."
     Not reproduced (2026-10-05): the live companion drawn at 6x, feminine
     and masculine, six poses by nine moods/acts, the blink lids sit within
     2px of the eyes and the closed-eye stroke and lashes are their usual
     size; mid-blink frames looked at. Needs the owner: a screenshot of the
     moment, or which pose/mood it was in (sitting, lying, drowsy, startled).

554. **The owner, 2026-10-05, verbatim.** "the feminine atlas whisps should
     wrap the body a bit more instead of all of it sitting in front. also the
     lower body still looks too sharp like a tooth. the whole avatar needs to
     ahve dynamic and organic movement. think of it like an azur lane
     character" Placed: with 550, the Atlas agent.
     Partly done (2026-10-05): the wisps wrap behind the body and the hem is soft; the layered lifelike motion is the follow-up agent's, with 564.

556. **The owner, 2026-10-05, verbatim.** "and a bit more texture can be
     added to the lower body as well. make it celestial and majestic and
     magical and attractive and flowy" Placed: with 550, the Atlas agent.
     Partly done (2026-10-05): the gown's nebula, sheen and glowing hem; the flowing motion is with 564.

564. **The owner, 2026-10-05, verbatim.** "can you fix or redesign the male
     main body on the atlas avatar instead of just being an oval?? also fix
     how the arms connect to the atlas bodies and how they are used in
     transitions between places and positions, same with the lower body,
     animate everything to be smooth and boilogically lifelike." Placed:
     with 550, the Atlas agent (masculine torso, jointed arms from the
     shoulder line, joint-angle blends with follow-through, lifelike idle).
     Then (verbatim): "the arms for both the male and female atlas".
     Partly done (2026-10-05): his V-taper torso and both looks' hanging arms (upper arm 13.4 degrees off vertical, elbow 166 and 165, wrist 0.54 and 0.52 of shoulder width). Open: joint-angle blends and IK in avatars.js, counter-phase swing, head lag, his cloak, the travelling hair and tail motion. The follow-up Atlas agent.

575. **The owner, 2026-10-05, verbatim.** "can you have the lower body of
     both atlas avatars change around in position and and how it is sitting
     ect with different variations and changes based off the current action
     or behaviour??" Placed: the Atlas motion agent, with 564 (a lower-body
     pose per state, small random variants, blended with follow-through).
     Then (verbatim): "dont forget that both atlas avatars have a tail as
     well, same with the hair, and the nebular stream. they all need to be
     dynamically animated and changed": both looks' tails, hair and nebula
     streams, per state, with secondary motion.

## Closed 2026-10-06 (the last round's three found-not-fixed items)

- **The shell at 360 wide, Large text, Spacious density was 368px** (hash
  c069120). Cause: the header's six squares take `--target-min` and
  `--header-control-h`, rems, so Large text made them 49.5px; the dock only
  followed the stretched layout viewport. Both are capped at 44px inside
  `header#top-bar`, and below 360 the bar's padding and gaps step down (inside
  07-whiteboard-misc.css's one 359.98 query; `test_breakpoints.py` allows one).
  `shellwidth.js`: scrollWidth <= viewport at 320, 360, 390 x small, normal,
  large x compact, comfortable, spacious x all seven tabs, 20 failures to 0;
  `phonehead.js` 0 findings. Note `innerWidth` grows with the content on a
  mobile context (it read 368), so the sweep bounds against the viewport it
  asked for.
- **Phone action sheets vanished with no exit** (34a965c). `openSheet`'s close
  adds `.sheet-leaving` (opacity and a short drop, `--motion-fast`) and removes
  the overlay after the computed transition, at once under the OS hint or
  Interface animations "reduced"; the ⋯ sheet sends its menu home in the new
  `onGone`. `sheetexit.js` (removed 2026-10-12, recoverable from git history): gone at 178 and 180ms on Escape and an outside
  press, first frame still drawn and pointer-events none, 0ms under both
  reduced-motion routes, menu home and hidden after.
- **Four sweeps repaired** (447d6fb, e4c1b76, and the commit that records this).
  `kebab-viewport.js` ran 80s, the Bash limit's edge: `ONLY=menus|dock|wb`
  splits it (12, 8 and 60 checks) and a not-found or did-not-open line now
  fails it. `selmenu.js` selected a notes row, where a drag selects nothing; it
  takes a paragraph and ends in PASS or FAIL. `libtab.js` listed no board on a
  fresh data dir; it creates a board and a map and asserts the Library tab
  leaves each. `mapstrip.js` asserts the corner `.wb-map-resize-grip` (absent
  until selected, nwse-resize, grows the box, Shift scales text, 72x40 and 10
  to 44 clamps), 43/43. It found a real fault: the grip, link and reference
  doors closed over the object the node was built with (`wbMapLiveDatum` now
  looks it up by id), so after a refresh a plain grip drag restored a cleared
  25px text size.
- *Found, not fixed:* `phonetabs.js` reports 3 findings on a near-empty
  notebook (the bar does not recede on scroll there: nothing scrolls); not
  compared against the base, since the change here does not touch the dock.

## Not verified

- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": The feminine sash sways on an inner <g>; The companion's walk lays out and recalculates style 59 times a second.
- **Every provider test runs against a fake transport** (CLAUDE.md section 4),
  and that covers more open work than any other single line here: no real
  model has run a skill, the night pass, the Guide's tab context, the paging
  nudge with an offset written into it, or a grounding answer that
  paraphrases. The grounding event that was measured came from seeding a note
  containing the stand-in's one fixed sentence. [chat-b.md,
  brief-13-harness.md, learning-loop.md, chat-popup-agent.md]
- **Nothing Windows was executed**: `splash.ps1` has never been drawn (layout,
  the marquee, the Details toggle, `Clipboard::SetText` from a hidden host,
  the error card's button swap), `start.bat --doctor` has never printed its
  table, `--shortcut`'s `.lnk` and `uninstall.bat --shortcuts` have never run,
  nor `netstat` port detection or the `%DATE%`-derived log filename on a
  non-English Windows. **Not run on macOS** either: `./start.sh --shortcut`'s
  Finder-alias branch, its symlink fallback and the `notify`-mode splash. The
  doctor's Ollama and Updates rows were exercised only in their negative
  state. [launcher.md]
- **No pre-Brief-7 database was upgraded.** Both migrations are exercised by
  the suite and written to be idempotent, but a real year-old file was never
  opened; compaction's numbers come from a database this sandbox built (150
  notes, 40 edits each) and one running app's notebook.
  [brief7-event-log.md]
- **Nothing in the learning loop was measured past a test-sized notebook.**
  The pass is O(notes) with one query per note for the already-known
  fingerprints, which is the first thing to profile on a real notebook. The
  resurfacing numbers are this sandbox's: read 6.7 ms at 800 notes, compute 50
  to 230 ms. [learning-loop.md]
- **Every cosine number in the retrieval work came from the 4-dimensional
  fake.** A real backend is 384-dimensional, anisotropic, and its `embed_text`
  per query is the cost the engine does not measure. Next step:
  WORLD_CLASS_PLAN 9's runner, then re-run
  `scratchpad/search/measure_engine.py` (removed 2026-10-12, recoverable from git history). [brief11-retrieval-engine.md]
- **Chromium only, mostly 1440x900, no second browser and no real touch
  device.** The graph's world constant in `gcWorldFor` (1.6 to 1.25) is
  reasoned above about a thousand notes; touch and pinch on the map are
  untested; the whiteboard was seen at 1440x900 and 390x844 at DPR 1 only;
  the documents contrast ratios use one sampled ground (`--page` is a
  gradient, so the dark figure `rgb(27, 31, 44)` comes from
  `scratchpad/pngpixel.py` on three points of a screenshot). [graph.md,
  whiteboard-phases.md, documents-batch.md, visual-c.md]
- **The desktop window was never run** (`start-desktop.sh`); every visual
  claim on this branch is a browser tab. [prose-intelligence.md, visual-c.md]
- **Every frame-cost number is headless Chromium with no GPU**, so the ranking
  and the order of magnitude hold and the absolute milliseconds do not. The
  background slider's visible effect per step is still unmeasured: ink on the
  canvas varies by about 0.15 points between two boots of the same settings
  (every style places its marks with `p.random`), and frame cost at the two
  ends moves by less than this environment's noise. The honest next step is a
  person looking at five screenshots, or a design change so the slider drives
  something with a large signature (the wash's own alpha). Mesh is the
  expensive style (+27.6ms a frame, worst frame 166.7ms). [responsive.md]
- **How the dark palette reads on an OLED panel or at another display gamma**,
  and the luminance column `glassdepth.js` takes, which was not re-run after
  the shadow tokens changed. [responsive.md, visual-c.md]
- **A PDF's page picture was never seen drawn**: this sandbox has no PDF
  render extra (`pdfpages.available()` is false, `/media/pdf-page/...` answers
  404), so the OCR workspace's stage stayed empty for a PDF. Choosing a reader
  was not exercised end to end either: all three options are `disabled` here,
  so the option row's click handler correctly returns without changing the
  value. Nothing measures a real reading: no vision model and no Tesseract ran.
  [library-blockers.md, ask-head-ocr.md]
- **No screen reader was run** against `aria-current="location"` in the
  documents outline. [doc-sidebar.md]
- **IME composition inside the editor engine**, and the fallback path reached
  by a genuinely blocked request rather than by setting `docCmBroken` by hand.
  (The fallback surface itself was verified in 2026-09-13's `docfallback.js` (removed 2026-10-12, recoverable from git history)
  run, 8 of 8.) [documents-engine.md, documents-phases.md]
- **The whiteboard's PDF export** goes through the browser's print dialog,
  which Playwright cannot complete, so it is the one pair of the
  scope-by-format matrix no sweep asserts; pen pressure and the rail's
  long-press flyout have never been driven by a touch device; the
  highlighter's Shift-straight branch is exercised by hand, not by the gate.
  [whiteboard-phases.md]
- Closed here, accounts in HISTORY.md, "OPEN.md rows closed, 2026-10-04": The whiteboard's align and distribute actions were not driven.
- **The popup agent's results pane with a conversation in it.** Everything was
  measured on the empty state, since this sandbox has no model;
  `.command-palette-results` keeps its own `--card-pad-x` inset, and that is
  reasoned, not observed. [popup-redesigns.md]
- **Write with AI was measured with the model off**, so "Draft it" is disabled
  and the draft box is empty in every measurement. The column heights are the
  same either way (the boxes stretch), but an in-flight draft with its Stop
  button and a long status line has not been seen. [notes-subtabs.md]
- **A real log stream under load.** The live pill reads green and the filters
  hide the right count (275 records on the seeded server), but nothing here
  produced a burst, so Follow's scroll-pinning was not exercised beyond
  toggling it. [logs-cards-links.md]
- **Real-browser text metrics beyond Chromium.** The wrap sweep measured
  420 to 2200px at the app's own 95% `--zoom`; a different engine could shift
  an exact wrap breakpoint by a few pixels, and none of the fixes depends on
  one holding. [wrap-sweep.md]

## Atlas and the companion, placed from INBOX 752 (2026-10-10)

- The behaviour model (Brief 34, second part): a state machine with blended transitions, idle variation from a weighted pool, reactions to every app event with a budget, gaze and lean, the enlarged view on the same state. Measures: snapping transitions per minute 0; 12 distinct idle motions per ten minutes; reaction latency under 100 ms.

## Atlas, placed from the owner's list 2026-10-10

Entries are the owner's words, then the recommendation. Bugs come first, then design requests. Brief 34 carries the whole group.

### Bugs

- "I cant right click to view the menu to change the companion in the expanded popup view"
  Recommendation: the enlarged view gets the same context menu as the small companion, with the change-companion item in it. Also carried by Brief 34 (the enlarged view).

### Design requests

- "I barely get to see atlas change expression. atlas and the companion movement and behaviour need to be more and more lifelike, natural, smooth, varied, and more."
  Recommendation: mood changes are visible within a short session, measured as mood changes per session before and after. Also carried by Brief 34 (moods that change, lifelike motion).
- "The companion and atlas needs a lot more improvement, and lifelike behaviour, more cool and diverse ways to move around, enter the screen, change between behaviours and more."
  Recommendation: add entrance and behaviour-change animations to the companion and Atlas, and count the distinct movements per session. Also carried by Brief 34 (gestures, entries and the walk cycle).

## Left by the deepen agent (Brief 72a, merged 2026-10-10)

- Not verified: whether the closed `.doc-dock-menu-list` at 390 paints (it lays out, 13 items, x = -32 on a code document); open it and measure before Brief 76 row 2.
- Not verified: the map grip that overlaps "Add a child to" (its accessible name was not read; it shows only with a topic selected after adding children).
- Undo counts for documents (2/11), OCR (0/5) and meetings (1/6) are a static read of each handler for `pushUndo`, not driven; Brief 74's `undo.js` replaces them.
- Not driven: Summarise's 503 with no model (read from `routes_meetings.py`), pinch zoom in the OCR workspace, the phone path of any board or map command, Find anything for "ocr".
- Timings vary two to four times between runs (the machine was shared with other agents; map add-a-child 102 to 424 ms); the blocks give ranges. Rerun `deepen72a.js` on an idle machine before a brief quotes a "before".
- Bergamot's licence (MPL-2.0 into AGPL-3.0) and sizes are stated as the evaluation's job (Brief 83), not checked here.

## Carried from the agent files archived 2026-10-10

Thirty-nine finished agent files moved to [`../archive/agent-remaining/`](../archive/agent-remaining/) on 2026-10-10, in four batches: every file dated 1005 or 1006, and landing-645, meetings-644 and mc1. Each row is what a file still held that is open on the head the day it moved and that neither HISTORY.md, CHANGELOG.md, the plans nor INBOX holds. The file in brackets has the measurements.

- Drag to delete takes no drag from the board sidebar (Library, Layers) onto the trash target; a drop from the Library panel is not a delete. (from av1-1005.md)
- 24 single-line `toast("...", true)` calls with a literal message remain in `frontend/js`; some are expected conditions (validation, "nothing to ... yet") that carry Report this. A `report: false` option costs boot bytes. (from e2e-1005.md)
- With a model, the composer shows "Filed under Work (100% sure)" for a small model's pick (a dentist appointment); the certainty shown for a small model's pick is too high. (from e2e-1005.md)
- A row added or removed after a list's first render does not fade; the lists redraw whole, so this needs keyed rendering first. (from motion-1005.md)
- Help popovers close at once: a popover goes home and is removed on close, which cancels its exit transition. (from motion-1005.md)
- A sub-tab's panel does not cross-fade; only its line slides. CSS cannot tell a section switch from a page arriving; it needs a class set by `showNotesSection`. (from motion-1005.md)
- CHAT: the evals gate runs on a 3B model (hours on these cores) and waits on a real-model run. (from op3-1005.md)
- The `.skill-fact-reads` chip reads dy +4px in one of four identical instances on the Skills sub-tab at 1440 (badgealign.js); the instance is not isolated. (from op3-1005.md)
- Sweeps that only click the Library tab time out, because the Library opens on its last sub-tab. `bm1005-sidebar.js` and `bm1005-mapmulti.js` click Boards and maps first; the rest do not. (from op3-1005.md)
- UI_MOD Phase 11 item 11: the screenshot set for the owner, which needs a place the owner reads. (from op4-1005.md)
- 444 decision 10, still open: the Tools (4,247px) and Appearance (1,296px) panes are indexed, not split. (from op4-1005.md)
- Two-finger scroll jump (460): not reproduced twice; needs a real touchpad trace. (from op4-1005.md)
- Owner's call: RapidOCR ships as an optional extra (Settings, Packages); confirm it against the 2026-10-05 "fully local, vendored" rule (WORLD_CLASS_PLAN row 31). (from op4-1005.md)
- Doc-focus panels between 720 and 819px cover the page, as below 720 did before; not driven in a sweep. (from op5-1005.md)
- Sweeps that wait a fixed 1.2 s for the whiteboard's lazy bundle flake under load (`initWhiteboard is not defined`). `op5-1005.js` and `mapviewmenu.js` wait for the function; the other sweeps with a fixed wait do not. (from op5-1005.md)
- The board preview labels (`mapPreview` in note-cards.js) run over the next shape ("Cut the sign-up fro…" across a diamond); the label placement is INBOX 263's design and the whiteboard agent's surface. (from qa-1005.md)
- At 1440 with the Connections rail open, the Notes dock wraps nine controls onto a second row; DESIGN.md says seven at most. A judgement for the dock grammar's owner. (from qa-1005.md)
- `scratchpad/ui-sweeps/lib.js` LOOK= writes the look into the server's preferences, so later sweeps on that data dir inherit it; run a LOOK=utilitarian sweep last. (from qa-1005.md)
- installer.iss's ISPP version reader (`#sub`, `#for`, `RPos`) compiles only on Windows; it is not verified until a Windows CI run passes. (from windows-packaging-1005.md)
- The upgrade step downloads the latest release with `gh` and `github.token`; a fork or a repo without releases fails it loudly. (from windows-packaging-1005.md)
- The traceback check in the smoke step reads the app's whole output; a benign logged traceback on Windows would fail it. (from windows-packaging-1005.md)
- The installer's optional packages (owner, 2026-10-07: "there's no indicator for the optional packages install and I cant minimise or close the window"): Setup waits on pip and cannot repaint, minimise or cancel. Recommendation: Setup records the picks and finishes; the app installs them on first launch as a background task with progress, a log and Stop (a stopped install rolls back, `extras._roll_back`). (from windows-packaging-1005.md)
- `docs/CHANGELOG.md`, `docs/CONTRIBUTING.md` and `docs/SECURITY.md` are mirrors that nothing reads now (the old site fetched them). Keeping or retiring them is the orchestrator's call. (from landing-645.md)
- INBOX 641's rest, which INBOX.md no longer holds: Illustrator linked symbols (`library_ref` in whiteboard-library.js), Photoshop topic effects (a level field each, `WB_MAP_LEVEL_FIELDS` and `MAP_LEVEL_FIELDS`), Miro reactions, and the whiteboard half of the research. (from mc1.md)
- PNG and SVG export draws every topic as one box: `wbBuildExportSvg` (whiteboard.js) leaves out levels, shapes and Phosphor icons. (from mc1.md)
- `DOC_EMOJI_SOURCE` (documents-prose.js) is a second emoji table beside `ICON_EMOJI_SOURCE` (icon-picker.js). (from mc1.md)
- Playwright reported the topic strip's Text toggle "not visible" after an icon pick, though its rect is 58px wide; `mc1-iconpicker.js` works around it with evaluate clicks. Not investigated. (from mc1.md)

- Large view: whole-body moves (`nmb-hop`, a hop, a cheer, a startle) move the head 14 to 17px a frame, 2.2 times the rest. Decision needed on slowing them in the large view; recommendation: a gentler `nmb-hop` only under `.nm-viewer-figure`. (from atlas669-1006.md)
- A click in Atlas's own large view costs 22 to 44ms in `setAtlasMood` (every layer's animations, then `atlasApply` on 12 layers), 50 to 100ms on a loaded machine: a stall, not a jump. `atlas669-clickcost.js` measures it. (from atlas669-1006.md)
- The generic (non-Atlas) faces' arms have no rig and so no speed cap; the fastest segment of their wave and hide keyframes was not measured. (from atlas669-1006.md)
- Chromium quirk: a blend's implicit end keyframe held `rotate` at its start value under a CSS animation that starts at the same value. The blend avoids it by easing only the values that moved; not reduced to a minimal case. (from atlas669-1006.md)
- Owner (2026-10-07), a fresh install's search model: an empty or partial `models--BAAI--bge-small-en-v1.5` folder is treated as present, the load runs offline and fails with `EmbeddingCacheBroken`. Treat the model as present only when its weights and config are in the snapshot; otherwise download it as a background task with progress; test an empty and a half-filled cache. (from autoinstall-1006.md)
- Owner (2026-10-07): the janitor warmed a default chat model it never checked ("Chat with 'llama3.2' failed"). `warm_filing_model` (janitor.py:741) should skip quietly, and Settings, Models should say no chat model is chosen. (from autoinstall-1006.md)
- Owner (2026-10-07): on first launch, choose the chat, background and image models from the installed ones instead of llama3.2 (Atlas said "was running llama3.2, which is not installed any more" on a fresh install with five models present). Say once what was chosen and why, with Change. (from autoinstall-1006.md)
- Owner (2026-10-07): the app repairs a broken or missing search-model cache itself. On `EmbeddingCacheBroken`, start the reinstall as a visible background task ("Fixing search by meaning..."), keep keyword search working, and ask the person only after two failed fixes or with no network. No exception class names in what the person reads. (from autoinstall-1006.md)
- Owner (2026-10-07): each embedding row shows its real state (Downloaded with its size on disk, Not downloaded, or Files missing with Reinstall). The "Runs in the app" badge is built; "Files missing" is not (`embed-choices.js`). (from autoinstall-1006.md)
- `renderAutonomousSettings` fills the Models-pane checkboxes only when Background tasks or Web search opens (settings.js, per the file, about line 158); the new switch is filled in `renderPrefs` instead. (from autoinstall-1006.md)
- Autonomous with no model running ends "Finished analysing and linking notes." in 65 ms; it should say it had no model (check `agent.run_agent` for a no-provider error event). (from bgprogress-1006.md)
- The night shift's pairing phase is slow (120 s for 2,400 facts and 4,786 pairings with the local matcher), and the bar resets between the reading and comparing phases. (from bgprogress-1006.md)
- If the owner means every pill in a popup, these values are next (kept as `.seg` by DESIGN.md's two-or-three rule): doc-history-filter, ocr-zoom, ocr-view, theme-seg, fontsize-seg, border-style-seg, privacy-range, log-view-toggle, confirm-seg, the print setup, chat-skill-pace, wb-export-seg. (from board715-1006.md)
- Sweep coverage not yet done: an open board or map, the graph's node popup and controls sheet at 390, the print dialog, the lightbox, the confirm dialog, the onboarding tour, the Attach dialog, the date and time pickers, every card's kebab menu; other looks (`LOOK=`), `CONTRAST=on`, forced colours, Large text with Spacious density. (from clip685-1006.md)
- `scroll-padding`: a control focused by Tab in a scroller is scrolled to the edge with its ring half cut. `scroll-padding: var(--ring-room)` on `.tab-page`, `.tab-main`, `.modal-content` and `.library-view-section` would close it; not applied on this head (grep), not measured (the sweep does not tab). (from clip685-1006.md)
- The ring sweep skips a control at the end of a scroller with more content past it, so a real cut at a scrolled edge is not seen; text cut by a fixed height without `overflow` is not seen either. (from clip685-1006.md)
- A ring on a control in a body-level fixed sheet that touches the viewport edge (the phone Writing room's draft textarea) is treated as scroll position; no measured fix. (from clip685-1006.md)
- Found: `one_line` for "when is the harbor launch?" quotes the Q4 roadmap rather than the dated sentence; the compose grounding rows lack it. (from composer-everywhere-1006.md)
- Found: a titled note's every sentence scores on its title (`_score`, `TITLE_WEIGHT`), so the brief keeps up to four dated sentences of a note named for its subject. (from composer-model-1006.md)
- The eval numbers for the whole voice track (before and after) were not reported: run `tests/_composer_eval.py` and record them. (from composer-voice-1006.md)
- Browser check of Ask and Chat with no model at 1440 and 390, light and dark: the "Did you mean" chip and the clarifying question. The sweep `scratchpad/ui-sweeps/voice741.js` is on branch `wip/composer-voice` only. (from composer-voice-1006.md)
- The noisy-question set's coverage (owner: "any and ALL typos ... all slang"): what is still missed, from the eval. (from composer-voice-1006.md)
- Professional variants for the next-question chips and the citation phrases (`mention_*`, `lists`, `echo`), and other languages' wrappers. (from composer-voice-1006.md)
- The Settings voice row was checked in Chromium on the light theme only at 1440 and 390; dark not run. (from composer-voice-1006.md)
- Owner's test (2026-10-07): "How do I change the widgets?" got the whole Dashboard paragraph. A how-to should lead with its step sentence and keep the rest behind "More about the Dashboard". The help voice (`voice="help"`) is in CHAT_PLAN. (from composer-voice-1006.md)
- Ask's "Ask all notes" (`#ask-scope-clear`) is wired only once the Questions view has been opened, so the scope is only set from there (pre-existing). (from composer688-1006.md)
- At 390 the Ask head's model picker sits on its own short line (224px of 330), pre-existing. (from composer688-1006.md)
- Chat's next-question chips were not seen in the browser: the sweep found no `.chat-followups button`. Check `refreshFollowupVisibility` and the chip element (it may not be a button), then fix the element or the sweep. (from composer725-1006.md)
- Clicking an Ask chip was not driven: the sweep's `button` selector missed the chip element. (from composer725-1006.md)
- Link reasons from the composer (owner: "can the composer be user to write better link reasons other than just similar in meaning??"): not started. INBOX 691 is not in INBOX.md, so its concrete overlaps (one note names the other, a shared tag, a shared rare word or name, the same category in the same week) and the sentence-pair reason are open. (from composer725-1006.md)

- Chat dock at narrow widths: the streaming state (Stop shown, Send hidden) was not measured. (from dock694-1006.md)
- The icon-only chat-dock toggles are checked by text content and title only; no keyboard or screen-reader pass was run. The phone (under 600) sheet paths (`openChatDockMore`) were measured as a one-line strip and composer at 390, not opened. (from dock694-1006.md)
- `wbMapDropTargetAt` (whiteboard-map.js:2661) still converts by hand. Fold it into `wbClientToBoard` and update the pinned line in `tests/test_map_drag_cost.py`. (from dropplace-1006.md)
- Touch drag from the Library is not tested: HTML5 drag-and-drop does not run on touch. The drag image (its thumbnail and offset) is asserted in source only, since a headless drag shows no ghost. (from dropplace-1006.md)
- CI margin: Tests (Python 3.13) took 16 m 14 s of its 25 m timeout on the head that was scanned (3.11 took 15 m 01 s, 3.12 14 m 37 s). A slow runner is a red build; raising the timeout is the owner's call. (from final-scan-1006.md)
- `/jobs/last-runs` is polled after a lock and answers 401 once or twice per lock (forgotpw.js's refused list). Next: stop the poll in `lockNow` and `purgeLockedContent` (`settings.js` reads it at about line 4425). (from forgotpw-1006.md)
- Not verified in a browser: the another-device notice on the recovery card (the sweep server binds loopback only); a real phone and a screen reader on the card. (from forgotpw-1006.md)
- The Focused hero is taller than before: 157px at 900 to 1920 (was 71), 278px at 390 (was 71 to 87). If the owner finds it too tall on a phone, the next step is the glance as one scrolling row there. (from hero675-1006.md)
- Not verified: a real model's greeting in the new layout (a long AI line widens the left column up to its 45% cap; measured with handwritten phrases only), the desktop window and RTL. (from hero675-1006.md)
- `scratchpad/ui-sweeps/pickers.js` throws `pickNotesDialog is not defined` at its note-picker section, since that dialog moved into the whiteboard bundle. `segbars.js` and `left1005-openrows.js` still read `#graph-layout` as a segmented control. (from inbox670-1006.md)
- Markers' Flag is still two previews (seg665-1006.md item 5). (from inbox670-1006.md)
- The breath's cost in the large view is not settled: a CSS loop cost the view about half its frames, so the swell is written ten times a second. The A/B (base 415, 320, 192, 162 frames; breath 346, 348, 106, 202) is inside the noise. Re-measure on a quiet machine with `breath687-ab.sh viewer-m 5`; 6 Hz (`ATLAS_BREATH_STEP_MS` 166) is the fallback. (from motion686-1006.md)
- An interrupted glide restarts at the ease's peak speed: a star's fastest step after a second Regenerate is 13 to 16px against 7px before it. A velocity-matched retarget (a spring) would remove the kick; it was not asked for. (from motion686-1006.md)
- RapidOCR and Tesseract never ran for real here: "ready" and the RapidOCR path are faked through `/ocr-readers` and monkeypatched tests. A real install and a real read are open. (from ocr717-1006.md)
- `ocrflow.js` still reads `#ocr-engine` as a line and clicks `#ocr-more`; it was not re-run, and its engine checks may need the popover opened first. The region drag (outlining a rectangle) was not re-measured after the Regions toggle became a button. (from ocr717-1006.md)
- README `docs/screenshots/palette.png` (and `docs/index.html`'s copy) still shows notes, a document and a board in the palette. Retake it with `scratchpad/ui-sweeps/readmeshots.js` so the picture matches the alt text. (from palette666-1006.md)
- `tests-e2e/specs/shell.spec.js` has a handoff test that has only had `node --check`; Playwright's runner has not run it. (from palette666-1006.md)
- Older sweeps that expect note rows in the palette (grep `palette-input`): `ux1005-palette.js` (removed 2026-10-12, recoverable from git history) and `search1005-lazy.js` read command rows only, and `readmeshots.js` types "launch". (from palette666-1006.md)
- Stop part way: the night shift, the backup, resurfacing and the embeddings backfill are each one call with no step to stop at. Only housekeeping reads `passes.stop_requested` (passes.py:184); the backfill's loop could check it. (from progress696-1006.md)
- Settings, Packages has its own Embedding models list beside Search and index's, which does the same and more. Recommendation: Packages keeps a single line pointing to Search and index. (from progress696-1006.md)
- Not verified: a real model load for the new built-in embedding models (no sentence-transformers here); Pull a model by name is tested against a mocked Hub; Ollama pulls and the found scan against a real Ollama; the dark theme for the new rows. (from progress696-1006.md)

- Other jobruns detail strings that carry `{exc}` (grep `note_finished` and `run.fail(` in `src/`) were not audited; only the two named in item 5 were changed. (from quickwins-1006.md)
- Other `[^\]\n]`-style scanners may share the ReDoS shape; the markdown link stripping in the frontend is JS and is not covered by the Python oracle tests. (from quickwins-1006.md)
- Not measured at 390: the Documents sidebar and the board zoom pill are not on screen there (the sidebar is a sheet), so both were measured at 1440 only. (from radius682-1006.md)
- Not measured: the chat dock's controls, the board's context bar, the stepper and the map strip, named in `PILL_CONTROLS` with full-round rules. (from radius682-1006.md)
- An opened row with no title starts with its text, whose first line's centre is 19.4px from the top against the chevron's and cluster's 22px (2.6px off). A title row is exact; the fix wants the text's own line box (`1lh`), not a number per font size. (from rows676-1006.md)
- The owner's second screenshot showed a stray circle after the hover buttons on an opened row. Not reproduced at 1440, 1920 or 390, light or dark, open or closed. If it recurs, the seed lacks its state (a draft's Publish, a busy chip, a filing chip). (from rows676-1006.md)
- Phone (390, touch): the first frames of a toggle take 50 to 80ms in headless emulation, so the first frame of the height animation can jump about 40% of the change. Not measured on a real phone. (from rows676-1006.md)
- Phone: a collapsed row's always-shown buttons sit in the details line's scrolled lane, off the row's right edge (right -87.8px, measured; unchanged by the work). (from rows676-1006.md)
- Not verified: suggestion mode switched on while a candidate is chosen (the replacement goes through `docProseFix`), a touch long-press on a suggested change, and the phone width. (from suggest689-1006.md)
- A word touching a suggestion's marker is never a spelling finding: `docSpellable` (documents.js) rejects a `+` on either side, and `{++` and `++}` are `+`. `{++faque++}` has no finding; `{++the faque ++}` does. Fix: treat `{++` before and `++}` after as a boundary, with a test in `tests/test_prose_tools.py`. (from suggest689-1006.md)
- The prose-tool grammar rules at a CodeMirror lint tooltip (`.cm-tooltip-lint`) in code documents are not suppressed while a pointer menu is open. Only code files are affected, where no suggestion marks exist. (from suggest689-1006.md)
- Not verified: the phone's action sheet (`openKebabSheet`) and touch below 600 (its dismissal was not pressed twice), a real screen reader, and the Settings sidebar at 390 as a jump list. (from toggles681-1006.md)
- `.wb-shape-caret` has `pointer-events: none` (per the file), so the Shapes split button's caret never gets a click and the `closest(".wb-shape-caret")` branch in `wbWireToggleGestures` is dead code. A product choice (a 10px caret target), left. (from toggles681-1006.md)
- The topic bar wraps to two rows at 390 (348x102), measured identical on the base: the Branch line and the reset go to a second row under the open door. (from seg665-1006.md)
- The size stepper reads "17px" on a main branch and "22px" on the centre, and Classic's level sizes have no S, M, L or XL word, so the well showed "Map" pressed there. A level-size vocabulary is not in MINDMAP_PLAN. (from seg665-1006.md)
- The note strip, owner's report (d): every control is 6.4px inside the strip's edge at the default look (measured 320 to 1920). The owner's exact state (look, zoom, text size) was not reproduced. (from seg665-1006.md)
- `wbSyncMapStrip` sets a themed field's effective value onto the select, so a topic following the map shows the map's look pressed rather than ringed, except where the value has no option (the 17px size; the level's fill). (from seg665-1006.md)
- The Notes dock wraps to two rows from about 1280 to 1500 with the connections rail open (90px); Tidy's 40px extends that band to about 1640. Moving the words-hidden threshold from 1400 to 1680 fixed both, but `tests/test_breakpoints.py` allows no new width query, so the dock needs a rethink (fewer worded controls above 1400, or a narrower rail). (from tidy691-1006.md)
- The card tooltip and the graph still show a deduced reason as "(73% confidence, deduced)", not a strength word. (from tidy691-1006.md)
- `/entries/{id}/related` lists notes that are already linked, so a press on one answers 400 "already linked" (pre-existing). (from tidy691-1006.md)
- Not verified: the contrast of the accent count on the broom (`contrast.js`), a browser run of the automatic pass after filing (pytest only), and a real model for the "Tags Atlas added" review (the tool door only). (from tidy691-1006.md)
- Meeting cards show their section headings as raw `## Agenda` text, as every note card does. A meeting-aware card preview (when, who, open action items) needs its own pass. (from meetings-644.md)
- The Timeline's table view (a phone's default) has no mark column, so a meeting reads as a Note there; the feed view shows the meeting mark. (from meetings-644.md)
- Not verified: Summarise against a real small model (the fake model only; its pipe format and quoting are unknown), and transcription (no faster-whisper in the sandbox; the save is driven with a typed transcript). (from meetings-644.md)
- `suggestions-inbox.js` (a partial link run) and `whiteboard.js` (a clear that left items) are red by a computed flag; they are partial failures. (from toasts-1006.md)
- `ai-tools.js` says "Open Settings, Models" in words, and none is a link. A button on the toast is the next step and is a new control. (from toasts-1006.md)
- Not verified: the other 100 `toast(..., true)` call sites were not each triggered. A lint covers them; their situations (a formatter refusing a file, Atlas off in Suggestions) were not driven. (from toasts-1006.md)

## Left by the agents merged 2026-10-10 (deepen-b 72b, mapnotes, vendor 75, briefs, coverage)

The five files are in [`../archive/agent-remaining/`](../archive/agent-remaining/); decisions 768 and 769 taken, 728 fixed, 761 and 762 fixed.

- The phone paths through the More sheet: the agent (`toggleAgentPalette()` leaves the overlay hidden at 390), the Guide, the timeline and reminders were reached with `switchTab` or not at all. (from deepen-b-1010.md)
- The reminders quick-add row at 390 (not visible; the phone compose not driven). (from deepen-b-1010.md)
- Chat's 82 (1440) and 136 (390) overlaps after answers: a sticky head over scrolled cards or a real paint clash. (from deepen-b-1010.md)
- Whether each Guide topic answers its question (only the topic's head was read). (from deepen-b-1010.md)
- "last week" in Find anything: a window or the words. (from deepen-b-1010.md)
- Timings: two runs at 1440, one at 390, the second 1440 run under a concurrent sweep; ranges, not budgets. (from deepen-b-1010.md)
- Any real-model behaviour of the agent (CLAUDE.md section 4). (from deepen-b-1010.md)
- The rail-dot alignment at 390 (0 px at 1440). (from deepen-b-1010.md)
- The fixture is 96 notes (the seed ran twice), not 48. (from deepen-b-1010.md)
- Chat with no model: "what is 15% of 240" quotes a note; "convert 5 km to miles", "what day is it today" and "summarise my week" answer "Nothing in the notes"; "remind me to call Sam tomorrow at 9" makes no reminder (CHAT_PLAN foundation 7). (from deepen-b-1010.md)
- The agent panel with no model: 16 of 20 controls disabled (AGENT_SKILLS_REFORM, Deepened row 1). (from deepen-b-1010.md)
- Ask cannot show a relevant map as a map. Decision taken: retrieval is notes only (a map's entry text is its title, so it grounds nothing). Owner's words: "mindmaps still appear as notes in the ask subtab search". To surface maps, add a `maps` list to `ChatResponse` (`src/memorymap/api/routes_chat.py:673`) and draw it with `mapChip` in `frontend/js/capture-ask.js` (the `raw_results` loop near line 2296), fed by `search.engine` hits of kind `map`. (from mapnotes-1010.md)
- `GET /entries/count` (`src/memorymap/api/routes_entries.py:2293`) counts every entry row including boards and the bin; its only reader is onboarding's "is the notebook empty" check (`frontend/js/onboarding.js:73`), so left alone. (from mapnotes-1010.md)
- The Timeline labels a map under the "Boards" kind chip (`frontend/js/timeline.js:266`); it draws it with a map chip and an "Open this map" action, so it is not a note leak. (from mapnotes-1010.md)
- Notes keep the old `updated_at` rule (any write moves it): `edited_at` answers "when a person changed it", but `lexical_filing` (`src/memorymap/ai/lexical_filing.py:554`) keys stamps on `updated_at`, so the board-only guard in `core/database.py` was not widened. (from mapnotes-1010.md)
- Each VC row is unbuilt; the script and test are the only code (Brief 75 says no code beyond them). (from vendor-1010.md)
- The p5 API list in `scratchpad/vendor_use.py` is a Chromium dump pinned to 1.9.4 (the vendored p5 is 1.11.13 since 2026-10-11, not yet regenerated); regenerate it with a p5 upgrade. (from vendor-1010.md)
- Brief 2 (consistency lints): HISTORY mentions it only as an owner reference; no record of the lint set being built as the brief. (from briefs-1010.md)
- Brief 3 (prefs, api.stream/upload, innerHTML): HISTORY line 43146 area still lists `api.stream`/`api.upload` and the no-bare-fetch lint as not built. (from briefs-1010.md)
- Brief 4 (Settings two-pane, 54 paragraphs): WORLD_CLASS_PLAN.md:1019 says the 54 paragraphs "not re-checked here, so still open". (from briefs-1010.md)
- Brief 8 (`[[` autocomplete, connections rail): HISTORY has only the plan table rows, no Built record. (from briefs-1010.md)
- Brief 9 (job runtime): `tests/test_jobs.py` the brief names does not exist; HISTORY has no Built record. (from briefs-1010.md)
- Brief 10 (Library card recipe, widget frame): HISTORY has only the plan table rows. (from briefs-1010.md)
- Brief 13 (verifier): agent-remaining/OPEN.md:189 still names Brief 13's `evals` marker and fixture set as open. (from briefs-1010.md)
- Brief 14 (docs condensed): HANDOVER.md is 486 lines against a 300-line done-when; `NEXT_FABLE_WINDOW.md` does not exist. (from briefs-1010.md)
- Brief 16 (documentation refined): no HISTORY record of the pass. (from briefs-1010.md)
- Brief 17 (launchers, splash): agent-remaining/OPEN.md:405 names the rest of Brief 17 as open. (from briefs-1010.md)
- Brief 18 (the complete open scope): an umbrella brief, only section A recorded in HISTORY. (from briefs-1010.md)
- Briefs 25 to 31 (group): each plan phase list is still open; "nothing is built" for 25. (from briefs-1010.md)
- Brief 32 (templates and base layouts): deferred by the owner; BACKLOG 4b carries the standing row. (from briefs-1010.md)
- Brief 33 (rest of WORLD_CLASS_PLAN): HANDOVER.md:450 names it as the next brief. (from briefs-1010.md)
- 745 (d): the hover-only tour step reveal is built nowhere (tour.js has no hover handling). (from coverage-1010.md)

## Left by the a11yfix and filing agents (merged 2026-10-10)

Both files are in [`../archive/agent-remaining/`](../archive/agent-remaining/). The filing numbers (top-1 0.417 without a model against decision 8's 0.8, 0.808 with the embedder) are in the archived file; decision 6's scope ruling is INBOX 770 (taken); torch and sentence-transformers were removed from the shared venv.

- design-1010 row 5, 110 controls with no focus change (`a11yname.js` focus pass): Brief 57, decision 15. (from a11yfix-1010.md)
- The boot CSS cap (`tests/test_boot_budget.py`, 183,300) had 3 bytes of room; this work spent it with blank-line collapses in `00-tokens-shell.css` and `01-forms-settings.css`. The next CSS addition needs a lazy file or a cap-lowering trim first. (from a11yfix-1010.md)
- `app.js` is within 14 bytes of its ratchet (`tests/test_static_compression.py`, 14,300): `makeUnlinkAccessible` moved out to `note-cards.js` to stay under it. (from a11yfix-1010.md)
- Row 4 measured on a seeded notebook (13 notes), not the report's: title-only icon controls in the Notes list 54 to 0 at 1440, 21 to 0 at 390. Other title-only icon buttons built outside the Notes list (other tabs, Settings) were not counted. (from a11yfix-1010.md)
- Not measured: dark theme for axe `target-size` and `scrollable-region-focusable`; the 1024 width. (from a11yfix-1010.md)
- Decision 8's bar, "below 0.8 top-1 without a model the step is not done": 0.417 (`tests/test_filing_accuracy.py`, strict xfail). Forced to choose, the evidence is right 0.61; 39 of 120 notes name no pack phrase ("dal", "boiler", "episode", "MOT", "nursery"). Recommendation: an everyday vocabulary supplement beside the pack, reviewed by the owner (a pack migration, so the owner's call), measured on a second fixture written after it. (from filing-1010.md)
- Decision 6 says "the pack's flag": the pack has none. The 49 sensitive topics are MemoryMap's own list in `src/memorymap/ai/data/taxonomy/memorymap_filing.json`. (from filing-1010.md)
- The data path: section 23 says `src/memorymap/ai/data/taxonomy/`, section 26 decision 56 says `src/memorymap/data/`; section 23's was followed. (from filing-1010.md)
- Decision 4, "alternate names come from the pack's labels and the person's own titles": only the pack's labels (`entry/tidy.py` `_rows_category_names`). (from filing-1010.md)
- Decision 4's centroid test needs the search model; with it off the merge review uses topics alone at 0.8 and says so in the row (`tidy.MERGE_TOPIC_OVERLAP_ALONE`). (from filing-1010.md)
- The lexicon (decision 7) costs one note in the online simulation (0.521 to 0.510, `scratchpad/filing-tools/online.py`); the fixture has no category named for a topic another holds, so the case it is for ("Work, not Software") is only in `tests/test_tidy_categories.py`. (from filing-1010.md)
- Decision 9 (the 30 context rules, 50 acceptance fixtures): not started; `taxonomy.context_rules()` and `tests/fixtures/taxonomy/context_acceptance_fixtures.json` are in place. (from filing-1010.md)
- Cost: `decide` is 34 ms a call at 5,000 synthetic notes against 8 to 17 ms for the old tally (`scratchpad/filing-tools/perf.py`); Tidy's uncategorised review calls it once a note. (from filing-1010.md)
- The tag picker on an empty field puts the tags the note says first ("training 10 notes, in this note"), but on a note that says none of them it still lists every tag by use (`frontend/js/tag-suggest.js` `fillTagSuggest`): a completion list, not a suggestion, so left. (from filing-1010.md)
- The model's tag reply is grounded against a faked reply (`tests/test_tag_grounding.py`); what a real small model answers is not verified. (from filing-1010.md)
- Graph topics as categories ("How are they different from categories??", the graph agent's hand-off in `archive/agent-remaining/graph-1010.md`): not in section 23's steps, so not done. (from filing-1010.md)

## Left by the notice agent (INBOX 767, merged 2026-10-10)

The no-model notice is one row on the `.notice` recipe on all five surfaces (46.8px at 1440, two rows only under 600px); its 58 gzipped bytes were paid for by the blank lines of 08-consistency.css, so the boot CSS cap stands at 183,300 and the next CSS goes in a lazy file.

- Row height at 1440 is 46.8px, not "one line plus padding" (about 38px): the Connect button's 28.8px target floor sets the row. Left as is; shrinking it would break the touch-target lint. (from notice-1010.md)
- The palette is never shown on a phone (`toggleAgentPalette` goes to Chat), so its 390px notice is unmeasured by design. (from notice-1010.md)

## Left by the engine agent (Brief 39, CHAT_PLAN Phase 6, merged 2026-10-10)

The file is in [`../archive/agent-remaining/engine-1010.md`](../archive/agent-remaining/engine-1010.md); its numbers are in the merge commit.

- Blind panel (decision 40): the owner's rating against the 1 to 3B model; not runnable by an agent.
- P10 days until a note's date ("how many days until the dentist"): `utilities.until_subject` (src/memorymap/ai/utilities.py:313) finds the subject; compose does not yet look the date up in the notes.
- P11 mention counts ("how many times did I mention Porto"): no count shape; `notebook_stats` counts notes, not mentions.
- P12 a list filtered by category or tag ("list my work notes"): `composer._filtered` (src/memorymap/ai/composer.py:3155) filters by tag and source kind, not by category.
- P13 every date and what is due this week: the fact layer has the dates (`factgraph.of_kind`), no answer shape lists them.
- P15 a lead-in chosen after the parts: the compare opener is still chosen first.
- P16 a note's open checklist items for "what is still open on X".
- Decision 45: the readings are listed (`composer._readings`, src/memorymap/ai/composer.py:2693); a running model does not yet pick among them (needs a real model; `pytest -m evals`).
- Decision 43: the currency table is dated (`utilities.RATES_DATE`, src/memorymap/ai/utilities.py:113) but has no Settings editor.
- Captions: the composer reads them as note content; keyword search finds them as the picture's own row (src/memorymap/search/index.py:793), not as its note's.
- Dates like 3/4 read day first (`when._date_phrase`, src/memorymap/ai/when.py:420); no locale order.
- Not seen in a browser: the web sources list with a real search engine; contrast sweeps over `.said` and the act card.
- Polarity in the fact layer: dropped by decision 30's own condition (no feature uses it).
- Found, not mine: tests/test_ask_answer_object.py::test_ask_is_never_disabled_when_the_model_is_off fails on the base too (the chat skills trigger's `dataset.needsModel`).

## Left by the chatui agent (the owner's 2026-10-10 chat and first-run list, merged 2026-10-10)

The file is in [`../archive/agent-remaining/chatui-1010.md`](../archive/agent-remaining/chatui-1010.md).

- Item 32, "metadata ... very messy": the chat answer's foot is still three rows (Sources, Grounded in, meta), 148 px measured on a five-source answer; fold Grounded in and meta into one muted line (chat-agent.js:2275, the sources block). The head label and the result-card reason are done.
- INBOX 694 part 1, "the bottom of these pills gets cut off": not reproduced at DPR 1 (Ask|Agent and Settings `.seg`: each segment 1 px inside the 32 px track top and bottom); the Pace pill is drawn in skills.js:462 (outside this agent's files) and was not measured; try DPR 1.25 and dark.
- INBOX 731, "the help guide failed??": with a model only; no model answers (help-chat.js:329 is the catch). Needs the server log line from a model run.
- INBOX 742 and 743, "atlas doesnt seem to change emotions alot", "more mouse interaction ... rubbing its head. flipping it upside down": gestures, moods from app events, the enlarged view mirroring live state. Not started.
- INBOX 743, "atlas goes out of the border": not reproduced (figure within 4 px of its svg, no oval frame drawn at this head); recheck the welcome card on Windows.
- INBOX 744 (b) and (c), "it didn mention other matching records": composer and grounding work (composer*.py, renderAnswerGrounding), off this agent's list.
- Start SearXNG "takes a while": not reproduced (status 21 to 101 ms, chat.js:1031 `setWebSearxngRunning`); a search that failed should retry by itself once the engine answers.
- Web link cards in chat and the web reader share no recipe with markdown.js:1258 `linkCard`; one recipe for both.
- Citation hover, the composer and captions in retrieval (Brief 39) and the density items (Brief 41) are owned elsewhere.

## Left by the trust73 agent (Brief 73, rules 4, 5 and 14, merged 2026-10-10)

The file is in [`../archive/agent-remaining/trust73-1010.md`](../archive/agent-remaining/trust73-1010.md).

- Rule 4 "says what happened, why": 24 literal error toasts still fall back to Open the logs rather than an action of their own (`tests/test_error_toasts.py` LOGS_ACTION_CAP 24): chat-attach.js 2548/2768/2956, library.js bulk failures (1846, 1892, 3360, 9967, 10106) and 4671, settings.js 3463/3508/3527, whiteboard.js 8335/8351/10359/14697, shell-reminders.js 1135/1143, settings-controls.js 320/393, update-dialogs.js 216, lightbox-view.js 753, note-properties.js 44, documents-code.js 1499. Each wants a Try again bound to its own function, and a why where "Couldn't X." has none.
- Rule 4: the 338 `toast(e.message, true)` calls get the why from `plainHttpError` and the default Open the logs; a per-site retry is not built.
- Rule 5 "a long-running task that does not register fails": the lint is a table of thread sites (`tests/test_activity.py` THREAD_SITES); request-bound long work outside the four streams, transcription and picture reading (a document import, a meeting summary, the jobs pool's model lane rows) registers only through `collect()` or not at all; `core/activity.track` is the one line to add.
- Rule 5: a stopped answer ends its stream without a `done` line; how Chat, the Guide and the documents panel render that end is not verified in the page.
- Rule 5: "the managed runner killed" has nothing to act on: the app starts no model runner (extras.py says llama-server is run by hand), so an OpenAI-compatible backend answers that it keeps its own model.
- Rule 14: `/health` stays the launcher's open probe (instance_lock.py, __main__.py read it unauthenticated, and it answers on the LAN); the fields are on the signed-in `GET /debug/health` under `trust`. Moving them onto `/health` needs the owner's yes.
- Rule 14: the Health block stays in Settings, About (where it was built, PLAN B9) rather than its own section; reach is the palette's Health (1) and Settings, About (2).
- Not verified: Ollama's real `keep_alive: 0` and `/api/ps` (a slow fake in the agent's scratch dir stood in), the desktop window, WebKit.

## Left by the docs42 and docs42b agents (Brief 42, INBOX 736, merged 2026-10-10)

The files, with the measured before table and the vendoring keep-or-drop table, are in [`../archive/agent-remaining/docs42-1010.md`](../archive/agent-remaining/docs42-1010.md) and [`docs42b-1010.md`](../archive/agent-remaining/docs42b-1010.md); what docs42b built is in HISTORY "Moved from the plans, 2026-10-10 (DOCUMENTS Brief 42 remainder)".

- INBOX 735 first half: the p5.js sketch document kind (code beside a sandboxed live canvas, vendored `p5.min.js` only); `api/run_sandbox.py` would need a p5 runner that loads the vendored file into the frame. Brief 69 (D6 previews). [docs42]
- Document comments with the board's thread shape (Reply, Edit, Resolve, Attach): a decision first. Comments are `==words== %%remark%%` in the text ("no comment store and there must not be one", documents.js `renderDocComments`) while `wbCommentRow` needs ids, `reply_to`, `edited`, `resolved`. Recommendation (take it): keep the text model; a reply is the next `%%…%%` on the same line, Edit rewrites in place, Attach appends a `[[link]]`, Resolve takes it out; lift `wbCommentRow`'s DOM into a shared row taking `{list, save, refresh}` and add the recipe ratchet in `tests/test_ui_recipes.py`. [docs42b]
- Word import of tracked changes: the .docx carries `w:ins`/`w:del`, but Mammoth reads an insertion as accepted text and drops a deletion (documents-word.js `docWordImport`); the server reader `docview.docx_to_markdown` keeps them, so a .docx with revisions could go there. [docs42b]
- A fenced code block's language (```js) is not written to Word, so it comes back as a bare fence (`docWordBlocks`, the `pre` branch); header cells come back bold (as before). [docs42b]
- .diff, .patch, .vb and .vbs are not in `docview.CODE_SUFFIXES`, so a Library import of one is refused (415); a Dockerfile has no suffix at all (core/docview.py, with the chat picker's `accept` list `tests/test_docview.py` pins). Bug. [docs42b]
- The output grip is 24 px (the grip recipe), under touch.js's 44 px floor at 390; touch.js does not list the run panel as a surface. [docs42b]
- js-beautify on a selection is not used (a selection keeps the conservative re-indent); `vendor_use.py` reports "selection" as its one unused capability. [docs42b]
- Brief 42's other items not started: highlights on pages, comments with bookmarks and links, link cards with a viewer, the long-form preference at first run, labelled sections with a local graph (a Phase row first), doctype.js under 30 ms. [docs42]
- Not verified: the .docx opened in Word itself (its XML and Mammoth's reading only); Format on a large real file; the list chords on a non-US layout; the docx extra's removal on an install that has python-docx (it stops being listed). [docs42b]

## Left by the trust agent (Brief 74, T0 sweeps for 72a, 72b and 73, merged 2026-10-10)

The file, with the T0 table, is in [`../archive/agent-remaining/trust-1010.md`](../archive/agent-remaining/trust-1010.md); the plan's pointer is WORLD_CLASS_PLAN 28.6.

- Settings, every switch and choice: 13 pressed, 0 undone by Ctrl+Z (`settings-controls.js` has the only `pushUndo`; 48 write functions in `settings*.js` and `prefs.js`, 3 with an undo path).
- Documents: "Delete" shows a toast Undo, but Ctrl+Z goes to the open editor's history (`surfaceHistory` in `status.js`, the Documents branch) so the deleted document stays deleted; "Archive" and "Start a new document" push nothing (21 write functions, 5 with an undo path).
- Mind map "Add a top-level topic": the board stack grows by one, Ctrl+Z leaves the lists differing (`/whiteboard/` state not equal to before); unverified which list.
- Chat "Save this chat as a document": creates a document, no undo (`chat.js`; 28 write functions, 7 with an undo path).
- Whiteboard 43 write functions, 14 with an undo path; mind map 25 and 7; graph 21 and 9; library 30 and 9; dashboard 9 and 1; timeline 5 and 1 (`measure-writes.py --list SURFACE` names the gaps).
- Not reached by the sweep: right-click menus, keyboard-only acts (Tab for a branch), controls that open a picker and then need a second choice (note "Move to another category", "Add tags"), and library delete (all 14 pressed in the library were views or pickers). The 25 pressed actions are a floor on what is exposed, not the whole surface; `measure-writes.py` is the full-coverage count.
- Documents were not probed in the dark run (the list had not loaded when the sweep opened it), and the mind map "Add a top-level topic" undid in one light run and not another: re-run both before quoting them.
- `#wb-tool-group span.wb-tool-section-label`: text 49 to 56px past its box at 820, 1024 and 1440 on the whiteboard and the mind map (36 nodes counted as overflow and as clipped text).
- `#entry-list div.entry-meta.note-meta`: 64 to 72px wider than its card at 320 and 390 (one per note, 33 to 42 nodes); `#entry-list li` 24 to 48px at 320.
- `#select-btn span.dock-word` 40px and `#notes-filter-menu span.dock-word` 32px clipped at 320 to 1024: the labelled-to-icon collapse hides words by clipping instead of removing them (may be intended; if so the rule needs the exception written down).
- `button#notes-tidy.ghost.small` 4px at every width; `#tab-notes div.layout` 4px at 320 to 1024.
- Dashboard: 3 overflow and 1 clipped text at 320 and 390, 2 overflow at 820 and wider (selectors in the sweep output, not yet named here).
- Docks: 0 sibling intersections in 12 surfaces at 5 widths (at 390: 81 bars and 266 sibling pairs examined), so the dock grammar holds; the counts that fail are text and content boxes.
- Counts scale with the number of seeded notes (the notes list repeats one finding per card): the table in 28.4 was taken on 13 to 23 notes.
- Crawl: 55 destinations found from the dashboard (1, 14, 36, 3 and 1 at depths 0 to 4, crawl complete to depth 4), 1 deeper than 3, 16 with no palette command (of 80 commands); dark: 55 destinations, 1 deeper than 3, 14 without a command.
- Palette rows missing (heuristic word match, the destination and its click path): 1  Notifications: # unread (muted except reminders); 1  Atlas files it for you; 1  Draw, then keep it as a note; 2  Chat > About this chat; 2  Chat > Search everything and jump anywhere (Ctrl+K); 2  Library > Boards & maps; 2  Library > Bookmarks; 2  Library > Contents; 2  Settings > Search and index; 2  Settings > What it learned; 2  Settings > Web search; 2  Atlas files it for you > Manage categories; 2  Answered from your notes > About the Use AI switch; 3  Notes > Writing room > Write from notes you already have, up to six of; 3  Library > Contents > Probe documentDocument·# sections·#h ago; 3  Atlas files it for you > Manage categories > About managing categories.
- Deeper than 3 (light): 4  Library > Contents > Probe documentDocument·# sections·#h ago > Outline.
- The crawl presses navigation-looking controls only and one item of each repeated list; a destination absent from it is "not found by the crawl", not proof it is missing. Sub-tabs on one page share candidates, so a button seen on the first sub-tab is not pressed again on the others.

## Left by the F1 and F2 agents (Briefs 65 and 66, the one reader and quick add, merged 2026-10-10)

- `ai/composer.py` `_DATE_CUE` (about line 380) and its second date pattern (about 933) still compile date words; replace with `recognise.recognise(...)` spans when Brief 67 makes chat a client of the reading, then empty `STILL_READING` in `tests/test_one_reader.py`. [f1-1010]
- `entry/timewords.py` keeps its own weekday and number tables (the plan's second allowed reader, for stored precision). Brief 68 decides whether `find` becomes `recognise` spans plus a precision map. [f1-1010]
- `ai/factgraph.py` `_QUANTITY` still reads counts of things ("3 sets", "5 people"); a "count" kind (number plus plural noun) in `recognise` would let it delegate. [f1-1010]
- `search/query.py` `before:`/`after:` stay ISO only (`test_an_unreadable_date_invents_nothing` holds it); `before:tuesday` is one call to `recognise.span` if the owner wants it. [f1-1010]
- "last week" is the last seven days in search and the previous Monday to Sunday in `recognise`; both written down, the Reading says the search's window. An owner decision if one meaning is wanted. [f1-1010]
- `when.resolve("in march")`, "march", "q4" give the next one at 09:00 (a reminder is never in the past); the past one comes from `when.window` and `recognise`. By design. [f1-1010]
- "on my birthday" reads only with a stored birthday (`context["birthday"]`, `birthday=` on `/read`); no setting holds one yet. [f1-1010]
- Quick add is 56 of 60 on `tests/fixtures/composer/quickadd_1010.json` measured before F1's four fixes landed; re-run `scratchpad/ui-sweeps/quickadd.js` on this head and move CHAT_PLAN F2's Built block to HISTORY only at 60 of 60 (decision 50's gate). [f2-1010]
- `ai/reading.py` reads "review budget friday" (reminder surface) as sure at 09:00 while quickadd.js asks "What time on ...?" (decision 50); the reading should ask the same question. [f2-1010]
- Quick note: a reminder chip on a note saved while the server is away (the outbox, `saveQuickNote`'s `result.queued` branch) is dropped; the note is kept. [f2-1010]
- Palette: only the reminder act has a row (`quickAddPaletteRow`); a note or meeting act and the search window chip (CHAT_PLAN section 1 row 7) wait for Brief 67's act registry. [f2-1010]
- Not verified by either: a real model's path; a screen reader toggling a chip; a browser locale other than en-US; the full suite. [f1-1010, f2-1010]

## Left by the F3 agent (Brief 67, the validators and the acts, merged 2026-10-10)

- Palette rows from the registry: `acts.palette_rows` (src/memorymap/ai/acts.py) has no caller and `palette.js` still lists its own starters; a route and the palette drawing them (decision 53; Brief 68 row 7). [f3-1010]
- A model's proposed act through the registry: `acts.propose` is tested but nothing calls it; the agent's write tools keep their own confirm path (`agent.py`). Brief 68 row 8. [f3-1010]
- A reminder with no time said is guessed as tomorrow at 9, shown "(no time was said)" (`commands.py`, `when.resolve("tomorrow")`); decisions 48 and 50 say ask once. `acts.missing` and `validate.slots_missing` are in place; the reader fills the slot first. [f3-1010]
- Ask draws no Confirm and Not right: `capture-ask.js` keeps `onGrounding`'s insights unread though the route sends them (decision 60 lists chat, Tidy and the dashboard; Ask is optional). [f3-1010]
- The 390 px layout of the Tidy Patterns rows and the Chat pattern line is not measured (1440: Tidy row buttons 32 px, no overflow; Chat line 55 px). [f3-1010]
- "Grounded in" says 4 notes while the support chip says "3 of 3 from your notes" on "tell me about golf" (seen in a sweep screenshot, not investigated). [f3-1010]
- The decision 54 sum rule: "12 * 7 is 84." is read as its own "Read as" because it restates the question's sum; every other utility answer has a "Read as" line. [f3-1010]
- Not verified: real-model answers through the validators (fake transport and the route test only); dark mode. [f3-1010]

## Left by the search agent (Brief 47, WORLD_CLASS 25a, merged 2026-10-10)

- A chat is one search row (the whole thread), so a hit opens the chat, not the turn that matched (`index._conversation_row`). [search-1010]
- `tag:` with words still filters after the keyword pass's 200 candidates (`engine.search`, the `wanted_tags` block), so a common word plus a rare tag can miss notes. [search-1010]
- Brief 47's "the sidebar's search field routes here": the Notes sidebar has no search field; the no-match Search everything button and the saved-search rows are the routes built. [search-1010]
- Not verified: hybrid ranking cost at 5,000 notes with a real embedding model (keyword plus the fake backend only); the saved-search ⋯ menu opened in a browser; the phone's saved-search rows at 390 beyond the DOM count. [search-1010]

## Left by the f4 agent (Brief 68, CHAT_PLAN F4, merged 2026-10-10)

- Note editor: offers on the Edit form are wired (`note-edit-panels.js` after `li.append(surface, ...)`) but measured only on the Capture composer; the Edit form's filing offer sets the hidden select and redraws the chip through its `change`, not seen in a sweep. [f4-1010]
- Note editor: a sum only when written with `=` ("12 + 7 = 21"); a column of amounts with a "Total:" line is not checked (`ai/offers.py` `_SUM`). [f4-1010]
- Dashboard: the digest is in dashboard.js (a boot file, about 700 bytes gzipped); a lazy home would delay the first paint of the widget it opens. The model "refining" the digest (the plan's "with the model refining it when present") is not built: Atlas's week below it is the old stream, unchanged. [f4-1010]
- Documents: the status bar shows characters, words and reading time; lines (`wc -l`) are counted by `textCounts` but shown nowhere. "find with the same windows" is the Library's Search documents box (`GET /documents?q=`); the editor's own Find bar is a substring find, unchanged. [f4-1010]
- Board: board acts are off on a mind map (`wbPaletteActRow` returns null when `wbIsMap()`): a map's layout is its tidy, not a grid. Pasting a list as stickies or map topics was already built (`wbPasteText`, `wbMapPasteText`). [f4-1010]
- Library: a "boards" or "mind maps" filter resolves to `Entry.is_board` ids, but the Library's filter keeps note cards only (`library.js` `libraryPhrase`), so it shows nothing there; the Graph is notes only too. [f4-1010]
- Filters: "last week" is the last seven days here (the search's meaning) and the Monday to Sunday week in `recognise`; F1's owner decision row still stands. [f4-1010]
- Settings: the synonym groups and the filler list are a hand table (`filters.SETTING_WORDS`, `SETTING_FILLER`), measured on 10 phrases in the browser; no settings phrase fixture in tests. [f4-1010]
- Import: people and places are named in the summary only; they are not written as tags or entities (the save's own extraction runs as before). `recognise` reads a person only in some shapes ("with Ken", "Sam Carter"), not "serviced by Ken" or "Ken Adams serviced" (`ai/recognise.py` `_contact_cands`). [f4-1010]
- Agent: `propose_act` is offered in the reminder and tag tool groups only; whether a 1 to 3B model calls Calculate rather than computing is not verified (no model here). [f4-1010]
- Voice: 67 failure toasts in library.js, whiteboard.js and whiteboard-map.js moved; the other 112 JS files still hold their own strings, and only the failure shape is in the table (decision 55: surface by surface). One template toast left as written (`library.js` "Couldn't import “${file.name}”"). [f4-1010]
- Scorecard: the follow-up column needs decision 58's 200 spoken lines, which are not written; variety's minimum is 3 of 20 against the plan's target of 8. [f4-1010]
- Boot JS 582,371 to 583,240 bytes gzipped (+869: the digest, the Library and Graph filters, the palette rows, the voice table, `textCounts`; cap 588,400); boot CSS 183,286 to 183,286 (cap 183,300, 14 bytes left). New UI otherwise lives in the lazy quick add, library and graph bundles. [f4-1010]

Swept on this head: errors.js 0 errors and 0 layout findings at 1440, 1024, 820 and 390 (1024 timed out once on a click under load, 0 on the rerun); touch.js 0 findings. Not verified: a real model's path (no `MEMORYMAP_EVALS_URL`); the agent palette at 390 (it did not open from `toggleAgentPalette` in the phone shell); a screen reader on the new chips; the full suite.

## Left by the companion agent (Brief 34, first round, merged 2026-10-10)

Taken up by the companion2 agent (Brief 34 continues, INBOX 772 and 773).

- Decision 7's "under 1 ms a minute" is not met by Atlas: its tail is a script-drawn path (atlas-life.js `atlasTailFrame`), 15 draws a second at rest, about 770 layouts a minute. Meeting it needs the tail on the compositor (a cached sprite strip, or CSS on layer roots), a drawing change. [companion-1010]
- Atlas's faces do not read as different moods (sheet: atlas-sheet-*.png, 15 moods at 104, 28 and 20 px, both looks, light and dark): at 104 the face is about 12 px inside rings and tail, at 28 and 20 the moods are one face. Real mascot work changes eyes, brows and mouth boldly, with a mood cue (sweat drop, zZ, hearts, "!") that survives at 20 px. Likely the root of "I barely get to see atlas change expression" (atlas.js `atlasApply`). [companion-1010]
- Under the system's reduce-motion hint Atlas keeps its calm CSS loops (an earlier decision, 08-consistency.css:5056): 1,579 style recalcs a minute. Decision 7 says reduced motion keeps poses without loops; the owner should say which wins. The app's own Reduce setting was not measured. [companion-1010]
- Brief 34 second part (INBOX 752): snapping transitions per minute (60 Hz joint sampling), 12 distinct idle motions per ten minutes and reaction latency under 100 ms were not measured; the latency bar conflicts with the 1.5s reaction debounce the owner asked for ("atlas startles a lot"). [companion-1010]
- The owner's "arm movements ... permanently in a downward arc": the arm hold now changes on idle ticks (45%), but the arm angle range over a walk cycle and at rest was not measured (atlasarms.js has the probe). [companion-1010]
- Tail, rings, nebula and lower-body "subtle animations that are all cheap" (owner's list): not changed; they exist (atlas-life.js) and are the cost above. [companion-1010]
- Face sheet (facesheet.js (removed 2026-10-12, recoverable from git history), 12 names, light): one silhouette, one outline, readable at 104; crowns spill 6 px past the card's top edge; the gaming controller reads as a black block at 104. [companion-1010]

Not verified: Every "Done when" face site was read in code (`nameMark` goes through `characterRendererFor` first), not driven one by one this round. Context reactions (drowsy, sleep, headphones, glasses, nightcap, bell, offline, wave on focus) are present in avatars.js and were measured by earlier sweeps; not re-driven. Timings: other agents held the load at 6 to 10 on four cores; counts (layouts, recalcs) are load-free, milliseconds are not. A WebView2 or WebKitGTK window; a touch rub (mouse and pen only by design).

## Left by the pwa agent (Brief 50, WORLD_CLASS 25d, merged 2026-10-10)

- clip.html and capture.html keep unhashed `?v=<version>` stamps (static, not rewritten as index.html and offline.html are), so an edit inside one version can be served stale from the immutable HTTP cache there. [pwa-1010]
- Warm-load speed gain is inside the noise on a shared machine (466 to 570 ms against 613 to 672 ms) because stamped files were already `immutable` in the HTTP cache; the gain is offline-ability and a cache the browser cannot evict as easily. A quiet-machine A/B would settle it. [pwa-1010]

Not verified: a real install prompt (`beforeinstallprompt` was dispatched by hand in Chromium; no real Chrome install, no Edge, no Safari, no iPhone). The iPhone row (no event, "Share, then Add to Home Screen") is source-tested only. frontend/js/settings-wiring.js, `renderInstallRow`. the share target from a real phone share sheet. The query landing in Capture was driven in Chromium with the worker controlling the page (`/?share_title=...` fills `#entry-content` under the Notes tab); the installed-app path is untested. frontend/manifest.webmanifest `share_target` is GET. the desktop (pywebview) window's own cache with the worker; only Chromium was driven.

## Left by the measure60 agent (Brief 60, WORLD_CLASS 26.0 and 26a, merged 2026-10-10)

- Decision 58's `core/background.py` registry (name, started, stop) is not built; the lint only counts sites. Brief 63 neighbour. `tests/test_background_registry.py`. [measure60-1010]
- The 68 broad excepts that log nothing and return a fallback (89 minus the 21 seeded) are not ratcheted; decide whether decision 57 means them. `tests/test_no_silent_except.py`. [measure60-1010]
- 49 routes need a test or removal (`tests/test_routes_named.py` SEED); several are reached by a loop over verbs, check before writing duplicates. [measure60-1010]
- 5 foreign keys without a leading index (`entity_mentions` x2, `document_bookmarks` x2, `entry_bookmarks.bookmark_id`) and 64 filtered columns without one: needs a migration and an `EXPLAIN QUERY PLAN` at 5,000 notes first (26.4). [measure60-1010]
- Import cost 3.3 s against decision 56's 1.5 s: `ai.autonomous` pulls `ai.agent` (503 ms), `ai.help_chat` 271 ms, `api.routes_search` 226 ms. Brief 62. [measure60-1010]
- Graph at rest (1 to 10 long tasks) and the companion (4 to 6 at rest) are the two surfaces over the zero target (`frames.js` REST_BUDGET). [measure60-1010]
- `frames.js` has no documents or notes-list surface; add one when DOCUMENTS Phase work lands. [measure60-1010]

Not verified: Frame figures are one machine at load 5 to 9 on four cores; re-run `frames.js` idle before fixing a budget. Resident memory was measured on an empty notebook; a populated one loads the model at warm-up. The 647 MB is torch 2.14 CPU with bge-small, first embed 6.6 s. Hot-route times are in-process with the thread pool bypassed; `_to_out` at 5,000 notes is an extrapolation. Untested-route match is by path literal in `tests/`; a path built by concatenation of more than a trailing slash is counted untested. The `recalcs` CDP counter equals frames on every surface including the control; not read as a finding.

## Left by the safety agent (Brief 51, WORLD_CLASS 25e, merged 2026-10-10)

- `editor.js:inlineAiUndo` (owner's list of six): the inline AI bar's Undo reverts a CodeMirror transaction on unsaved field text, which rule 1.8 gives to the editor's own history. Recommendation: move it to the lint's editor histories rather than the stack (a stack entry outlives the field it would write to). Needs the decision taken. [safety-1010]
- `dashboard.js:undoActorFrom` / `activityUndoControl` (and their two helpers) and `note-history.js:undoSkillRun`: an undo of the AI's changes through `POST /events/undo`, which refuses the person's own changes ("Undo works on the AI's changes, not yours", routes_settings.py:1648), so there is no redo to give `pushUndo`. Needs a server redo (re-apply the reversed events) before they can fold. [safety-1010]
- The plan row names a "Versions" row; the note menu's existing row is "History" (versions plus every other event). Not renamed: a rename moves help in five places for no new reach. Recommendation: keep "History", record the decision. [safety-1010]
- A notice's `go: { settings, focus }` scrolls Settings to the control at 1440 (Back up now at y 499 of 900) but not at 390 (y 1527 of 900): the phone sheet does not scroll to `scrollToId` (settings.js:245). Shared by every notice that opens Settings. [safety-1010]
- No backup schedule "shown with the last success" (WORLD_CLASS 4018 row) beyond Settings, About, Health's last backup line. [safety-1010]

Not verified: A real disk failure or power cut; damage was made by overwriting pages of a copy (three embeddings leaves: opens, notice shows; pages read by the start-up backfill: `DamagedNotebookError`). The desktop launcher's loading window showing the damaged-file words was not driven (only `startup_status.get_phase()` asserted). The e2e spec ran locally once (2.0 min); not in CI yet. Folds measured with direct calls to the real functions (`deleteCategoryFromPanel`, `chatDeleteUndo`, `undoImport`, `pushDraftUndo`) after an API setup, not by clicking through each surface's own menu.

## Left by the density agent (Brief 41, UI_MODERNISATION Phase 12, merged 2026-10-10)

- Step 5b, decision 6 (a primary calendar paired with the reminders): TIMELINE_PLAN section 9 (Phase 5, Brief 55); `renderReminderCalendar` (shell-reminders.js) stands until it goes (decision 19). [density-1010]
- Decision 8, indent guides: the active line is built (library-lazy.css `.cm-activeLineGutter`); indent markers are not in the vendored CodeMirror bundle (DOCUMENTS_PLAN 25 row 3, Brief 71's shell). [density-1010]
- Decision 7: only note cards changed (category pill to a dot and a word); chat bubble metadata not measured (no conversation without a model) and library cards untouched. [density-1010]
- Decision 1, panel padding 12 and sidebar gutter 8: not measured or moved; the Notes dock wraps to two rows at 1440 (86 px). [density-1010]
- Decision 5 for a date field built after boot: the map topic's due date (whiteboard-map.js) stays native; the date picker's typed field sets the date only ("tomorrow at 3pm" does not move the time field). [density-1010]
- Sweeps: touch.js reports Settings appearance and privacy "did not open" (section names moved); overlap.js still counts 4 px rows on `#notes-tidy`, `#dash-quicklinks`, `.library-controls`. [density-1010]
- One focus ring at 1:1 in Chat (`button.active`, its outline takes the ground colour, both themes; `scratchpad/ui-sweeps/focusring.js`). Bug. [density-1010]
- Not verified: tests elsewhere that relied on blank lines removed from CSS files 00, 01, 02, 05, 06, 07 and 10 to pay for the CSS budget; the picker on the Timeline range and Ask's as-of day beyond a smoke check; 390 beyond Reminders. [density-1010]

## Left by the open-rows agent (time reader, 2026-10-17)

Closed (see HISTORY, "OPEN.md rows closed, 2026-10-17"): row 464 and the time-reader gaps found while probing. Still open, none built:

- `when.resolve("in 2 weeks at 3pm")` still reads 15:55 on the day: the clock after a day-sized offset is applied only in `reminder_parser.parse_relative` (`_with_clock`), not in `resolve`. A bare "at one" ("lunch at one") is deliberately unread, since "at one point" is as common; say so to the owner if it matters.
- A `before:tuesday` search operator is an owner decision (which side of the day it excludes).
- chat-agent.js result box budget line (row 243) is blocked by the eager-script gzip caps.


## Left by the 0.6.01 bug-document pass (2026-10-22)

Source: the owner's "Tessellate bugs" document (34 screenshots). Fixed in the patch: tray start/log hardening, whiteboard drag-select highlighting, Fill/Border popup placement, skills menu tag. Not verified on a real Windows desktop: the tray icon (could be in the taskbar overflow ^ if it did start). Open, none built:

- Composer: aware of recent activity (what you were writing or viewing) with varied, kinder replies and a suggested next step; answers that stay on the question and differ per note in Ask; a length setting; personas off when no model is connected.
- Composer: web search with SearXNG down gives only a failure line; a clarify-first flow for open asks ("open a note"); alternative actions by lexical and cosine similarity when nothing matches.
- Reminders magic add: "remind me to do my tax return when I get home tonight, probably around 7pm" must parse (task, tonight, about 7pm). Edit reminder buttons: equal heights and a gap.
- Composer analysing pages in the web panel (key points, highlights, a linked section list).
- Whiteboard: frame contents stay rotated when the frame's rotate handle is double-clicked to reset; emojis do not scale with their box; the dimensions label is missing while resizing; anchors and selection borders lag a resize until release.
- Documents: hide Harper suggestions temporarily and a list of dismissed ones; checkboxes clickable in read mode, wider comfortable width in full screen; selection toolbar and meatball missing in full screen; highlight colour switching on already-highlighted text, and the highlight menu not closing on an outside click; slash menu closing on an outside click and removing its slash; line-number gutter too wide and wrapped lines not indented in the live view; table meatball overflow and far-off plus button; history popup redesign; layout at half width (top of full screen, Ask tab, notes more-actions button half off the edge, blank bar at the bottom, blank bar at the top of Settings, Models page).
- Chat suggestions fade out on the right instead of wrapping; button styles look out of place (redesign pass); companion hard to throw and scrolls the page; an on-desktop companion avatar (quick open, new note, reminders) as in ChatGPT desktop pets.
- Custom domain: see the answer in the thread; documented in INSTALL for Docker only.
