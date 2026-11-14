# Inbox: things the owner dropped in while work was in flight

**How this file is used (the interrupt rule).** Anything the owner sends
while a step is in progress (a bug, a screenshot, a request, an opinion,
a usage figure) is appended here verbatim with the time, and NOT acted on
until the step in hand has passed its gate and is committed. Then, at that
boundary only, the inbox is triaged in one pass:

1. A bug in something built this session goes next (it is cheaper now).
2. A bug elsewhere becomes a LEDGER row (`python scripts/ledger.py add`)
   with the owner's words, scheduled by impact.
3. A feature or design request becomes a LEDGER row, or a row in the plan it
   belongs to; it is not built ad hoc. INBOX is intake only: a triaged item
   becomes a LEDGER row or HISTORY.
4. An opinion or a decision is recorded in the plan it affects and
   followed from then on.
5. "X% usage" means commit and push now, then continue more tersely.

Each item is moved out of this file when it has a home, with one line in
the report saying where it went. The point: the owner's pile after a usage
reset is processed as a batch at a boundary, the step that was in flight is
finished to standard first, and the goals in HANDOVER's "Now" line are
never lost to the smaller stuff.

## What is actually open, 2026-09-14

The 2026-09-09 to 2026-09-13 batches (110, 111, 114, 174, 176, 177, 180)
are in HISTORY's "INBOX resolved" with every sub-report marked; the three
residues they left are owned elsewhere: the graph agent popup redesign
(GRAPH_PLAN Phase 6, built: its "Built, Phase 6" block), the mind map ring (MINDMAP_PLAN "Decisions made,
2026-09-13 night", the mapux agent), and the second batch's five
not-reproduced visuals (BACKLOG, "Reported, not reproduced"). Everything
below is open work from the night of 2026-09-13 and the morning after,
with its owner named in the entry.

## Open items

1811. **UI modernisation session, 2026-11-14 (owner decided 2026-11-14 ~13:55Z, relayed by the hub: reject, reword; the rename waits on the owner confirming in this session, as the session's permission check refused it):** two `open_scan.py` changes, built and then reverted at the hub's word because the owner approved only 66c596bf. (a) a quoted CSS string is copy, as in JS and Python: the one ui-modernisation hit is the `todo` callout's selector `[class*="-todo"]` (05-sidebars-themes.css:1435); (b) TODO, FIXME, XXX and HACK count only in capitals, so a lowercase `todo` (callout kind, `data-mode="todo"`, a queue variable) is a name: 23 of 84 frontend and scratchpad hits. Measured: whole-repo hits 1376 to 1305 with both. Recommendation: allow both (tests were written: a CSS comment and an uppercase TODO stay hits). Until then the selector is a hit that cannot be reworded without changing the callout's class. The 24 hits left under this call (all a `todo` name, none open work): 05-sidebars-themes.css:1435 selector; index.html:2687 `capture-bar-todo` and `data-mode="todo"`; editor.js:308, 391 callout keys and 545 a comment quoting `/todo`; documents-word.js:442 key; entry-card.js:31 and tag-manager.js:321 word lists; documents-prose.js:1483, 1496 and navigation.js:694 comments naming the command word; desk-frames.js:200, 222, 226 `job.todo` queue; first-run.js:370 local; scratchpad/appjs-map.js:125 to 128 and graph-fixture.js:63, 65 locals; ui-sweeps/proseautofill.js:9, 145 comments; ui-sweeps/undo.js:27 a verb-list regex. The other 61 frontend and scratchpad hits were comments reworded where clearer (follow-on, unclosed, still showing, postponed).

## Placed (last 20, newest first)
- 2026-11-12: L-ui-modernisation-64 (group notes by hand): recommendation taken under standing order 3, not built: a hand-made group is a tag (or a space, or Favourites), the sidebar's tags and `tag:` filter are the grouped view, and section headings in the windowed, threaded list would be a second ordering beside the sort.
- 2026-11-12: L-ui-modernisation-65 (more than one category): recommendation taken, not built: a category stays single (filing picks one, the graph and the dashboard pie colour by one); tags are the many-labels mechanism.
- 2026-11-12: L-ui-modernisation-66 (compress on disk): recommendation taken, not built: the live SQLite file needs random access and its FTS index; backups are already VACUUMed and stripped, exports are deflated zips; whole-disk compression is the operating system's job.
- 2026-11-12: L-ui-modernisation-69 (in-app browser with MCP tools): recommendation taken, parked in BACKLOG: a browser inside a local-first notebook is a large security surface; web clip and web search cover the need now.
- 2026-11-12: L-ui-modernisation-70 (VS Code extension): recommendation taken: no extension, VS Code runs MCP servers itself; docs/MCP.md gives the `.vscode/mcp.json` entry.
- 2026-11-12: L-ui-modernisation-74 (sweep orphaned attachments on the background pass): recommendation taken under standing order 3, the pass never deletes uploads (a gallery-only picture is wanted); Settings, About counts them and deletes on a confirmed click. Found and fixed with it: the orphan check skipped the bin, revisions and locked private documents.
- 2026-11-12: L-general-25 (question_noise misspelling table's source): recommendation taken under standing order 3, keep and credit as a CC BY-SA 4.0 adaptation (GPLv3-compatible one way, combinable under AGPLv3 section 13); docs/THIRD_PARTY.md and the block's comment say so.
- 2026-11-05: 1685 (the shape bar, Filled keeps its colour, the app's own colour popover with hex and opacity) to WHITEBOARD_PLAN "Placed from INBOX, 2026-11-04"; 1686 (Atlas perches on every mind map node) to MINDMAP_PLAN "Placed from INBOX, 2026-11-04".

- 2026-11-04: 1684 (every companion on the desk) to BACKLOG "Placed from INBOX, 2026-11-04", after 1683.
- 2026-11-04: 1682 (the held-answers tag specs flake under load) to BACKLOG "Placed from INBOX, 2026-11-04".
- 2026-11-04: 1681 (more poses and variants) to BACKLOG "Placed from INBOX, 2026-11-04", after 1680.
- 2026-11-04: 1678 (a deeper companion mind) to BACKLOG "Placed from INBOX, 2026-11-04"; 1679 (the Fable diagram deep dive) to DOCUMENTS_PLAN "Placed from INBOX, 2026-11-04".
- 2026-11-03: 730 (filing without a model) to WORLD_CLASS_PLAN 23 and Brief 39b; 810 (Atlas as the app's assistant) to CHAT_PLAN decisions 65 to 69; 1298 (complexity exceptions) to BACKLOG "Placed from INBOX, 2026-11-03b".
- 1571 (friendly local name) and 1513 (graph motion; left: the untangle freeze, GR1) to BACKLOG "Placed from INBOX, 2026-11-03b".
- 2026-11-03: 1561 (a question about Atlas read as a topic), 1569 (background jobs counted as edits), 1570 (an answer to a clarifying question not bound to its act): BACKLOG "Placed from INBOX, 2026-11-03 (chat; CHAT_PLAN is at its cap)".
- 2026-11-03: 1562 (code editor indent guides) DOCUMENTS_PLAN, 1563 (frame margins in the alignment guides) WHITEBOARD_PLAN, 1565 (app-wide quiet motion) UI_MODERNISATION_PLAN, each under "Placed from INBOX, 2026-11-03".
- 1430, 1431 (2026-10-28, deep audit agents and the diagnostics report): PLAN "Placed from INBOX, 2026-10-28".
- 1416 (companion biological motion), 1417 (spaces as AI context), 1338 (Use AI switch disabled without a model), 1339 (relative times in Ask theme summaries): BACKLOG "Placed from INBOX, 2026-10-27 (next PR)".
- 1415 (2026-10-27, speed and smoothness, with a lag log): UI_MODERNISATION_PLAN "Placed from INBOX, 2026-10-27". Next PR.
- 2026-10-27: 1411 (the Ask box's AI pill is tight) fixed in the sketch round, recorded in HISTORY. 1412 (a confirmed plan line that never closes), 1414 (the guide's answers) placed in BACKLOG's "Placed from INBOX, 2026-10-27" (CHAT_PLAN is at its cap); 1413 (drag a graph popup, or have it follow its node) in GRAPH_PLAN's.

- 2026-10-27: 1410 (the AI and composer make and edit Mermaid diagrams, in every main feature, easy to build) placed in BACKLOG's mermaid section as 12d; step 8 is with one agent now.
- 2026-10-27: 1409 (glass controls as an Appearance option; glass only when on) placed in UI_MODERNISATION_PLAN, half built.
- 2026-10-27: 1406 (the Guide dumps a whole help sentence) placed in CHAT_PLAN, half fixed; 1407 (Harper false positives, app-side filter) and 1408 (doc sidebars not resizable in full screen) placed in DOCUMENTS_PLAN.
- 2026-10-27: 1403 (rich text runs on the whiteboard: size, font, colour on selected text; the ⋯ menu top) and 1404 (drag a connector label by its words) placed in WHITEBOARD_PLAN; next free slot.
- 2026-10-27: 1402 (Atlas looks grumpy at rest; a thrown companion flies back across the screen) placed in UI_MODERNISATION_PLAN; one agent now.
- 2026-10-26: 1400 (force graph composition, node popups, controls; code editor and recordings; composer) placed in GRAPH_PLAN; graph redesign next free Opus slot.
- 2026-10-26: 1357 (world-class composer, fix the class, open inventory, grammar) placed in WORLD_CLASS_PLAN; 1358 (whiteboard, mind map, document editor dogfood passes) placed in WHITEBOARD_PLAN; both running now.
- 2026-10-19: 1344 (the Composer badge explains it is not an AI) placed in UI_MODERNISATION_PLAN, starting as soon as an agent slot frees.
- 2026-10-19: 1342 (map edges never use the sides) placed in MINDMAP_PLAN, next PR.
- 2026-10-19: 1340 (board and map views) and 1341 (Format on a map) placed in WHITEBOARD_PLAN; 1336 (peek sidebar header) and 1337 (split button halves) placed in UI_MODERNISATION_PLAN; all for the next PR.
- 2026-10-12: 1299 (Ask digest grammar; Harper over composer output) placed in BACKLOG "Placed from INBOX, 2026-10-12" (CHAT_PLAN is at its cap); "every a week" and "Your the ... note" fixed now.
- 2026-10-11: 899 ("dont notes also already work out timewords and time references?? can the composer and agents ... pull from those") sent to atlas; 900 ("click on the lan icon in the bototm bar and easily be able to toggle it on or off ... without having to restert") folded into 896; 901 (show more and less awkward on wide paragraphs, two screenshots) sent to tags89; 902 (companion physics, entries, organic movement, no jolts, Atlas behaviours, the expanded panel's hanging arms, the arm that rises on a click) sent to throw.
- 2026-10-11: 898 ("make sure that the undo and redo are properly and completely universal") sent to undoall: every mutating request offers undo and redo through `pushUndo`, or sits on a shrinking exempt list. **Fixed d68f621c6, 466d4721a, 353d975b5.** The exempt list has no GAP left (89 to 0, the rest classed with a reason); a ratchet fails any step without a Redo; 21 live acts in Chromium (`scratchpad/ui-sweeps/undoall.js`) each undo and redo twice, which found and fixed Ctrl+Z walking a covered board's history and a several-shape step undoing twice.
- 2026-10-11: 897 ("the size of things should be proportional and individual to the device") sent to devsize: zoom, font size, density and the companion's size and spots stay on the device.
- 2026-10-11: 895 ("The composer needs to be a legitimately smart chatbot ... do anything and everythinf and do it very accurately and well") placed with atlas (the owner's semester example as a gold answer: relative time resolved against the note's date, facts woven into prose) and the composer agent after it (Briefs 104 and 97).
- 2026-10-11: 892 ("Could we do connection to phone via Bluetooth and or hotspot??") and 894 ("make sure a phone connecting is logged as an outgoing connection") placed with 896 (the lanbar agent).
- 2026-10-11: 893 ("Shouldn’t the notice be "you can only download files on your computer" or "action denied on this device"??") fixed: the refusal reads "Not available on this device. Do it on the computer Tessellate runs on." (downloads are not refused; an export saves on the device that asked).
- 2026-10-11: 871 ("the help search bar should be below the welcome tour section at the top of the help dropdowns") sent to chattime; 872 ("I restarted the app with the button and it didnt restart??", "or it took like 3 minutes?") fixed by the orchestrator (wt-restart, `--restart-after`); 873 ("there is still no smooth transition loading up the app nd viewing the graph") sent to graph100; 874 ("should the x and tick buttons on notifications be at the bototom of the notification?? I thought they were in the middle or top right??") queued for the next Sonnet; 875 ("can this be better styled and easier to read??", the receipt's address list) sent to lansafe; 876 ("can you add more deterministic welcome messages?? mroe variety and ones for each time of the day?? maybe the composer can spin something up based on usage patterns, note content, and more??") fixed by the orchestrator (`ai/greeting_compose.py`: seven slots, weekday lines, notebook facts); 877 ("if I load it up on my phone, it doesnt install all the libraries again does it??") answered and written into the phone help; 878 ("it came up with a security not trusted screen on my phone using safari ... its taking a very long time", "it still hasnt loaded") fixed: silent preconnects held the eight peek threads; 879 ("the companion still covers some parts of the ui and doesnt move out of the way", over Notes' more menu) fixed: open `<details>` menus joined its popup list; 880 ("what if multiple people are running memory map and want to connect over the same lan connection??") answered, and a second notebook on one computer now takes the next LAN port; 881 ("what if I make a change on my phone?? does it live update?? what if there are update  clashes??") answered (clashes are refused with Keep mine or theirs), live refresh of an open screen placed in BACKLOG; 882 ("I try throwing the companion across the screen and it just goes back to the same side, the companion physics just isnt there and needs to be upgraded and fixed.") queued for the next Opus slot; 883 to 885 (graph node popup buttons wrap onto three rows on a phone; "i have no clue what the buttons do as I cant hover over them"; "clicking the graph settings button on my phone auto opens the graph layout dropdown menu") with 874 sent to the phonegraph agent (Sonnet); 886 ("the bottom of the settings page gets cut off??", "on my phone", "I cant scroll or close the settings page, I think the top is cut off as well") fixed by the orchestrator (dialogs capped by dvh, the overlay scrolls, safe centring; not seen on a real iPhone); 887 to 889 (the chat input under the keyboard and the no-model notice; a pinch on the whiteboard moved a note; the OCR workspace and the Files extracted text scrolling sideways) sent to the phone2 agent (Sonnet); 890 (the owner's support bundle: "[browser/csp] blocked style-src-elem: inline (user-script)", "[browser/error] Script error.") fixed: Safari's injected scripts and extensions are not logged as the app's; 891 ("I pressed open file location for the support bundle on my phone and it opened up file explorer on my computer ... I need maximum trust, proper safe connection, proper security for the lan and open connection") fixed: `api/this_computer.py` refuses 17 computer-acting routes to any other device; the phone UI hiding them and the full audit go to lansafe and the security scan.
- 2026-10-11: 867 (iPhone; LAN on a public network, automatic with overrides) placed as the retired session briefs Brief 102 (lansafe running); 868 (a time on every chat message and session) as Brief 103 (chattime running); 869 (typos read in context, not as slang) as Brief 104; 870 (composer answers with real openings, joining clauses and a close that adds something) into the atlas agent's running brief (CHAT_PLAN decision 70). Verbatims in the retired session briefs.
- 2026-10-11: the reqaudit pass (153 asks, 41 unplaced found-not-fixed rows) placed as the retired session briefs Brief 101; 845 ("can you redesign or change the design of this \"clear this list\" button??") and 846 ("there's an excessive gap on the right for the x close buttons on the nav history, can you integrate them together??") with ownerfix2; 848 ("on these screenshots from the search suggestions agent, these button text clashes") and 849 ("should search suggestion dropdown panels be the width of the search bar with the minimum being what the panel default is??", yes) with search86.

- 2026-10-11: 862 (a full functionality and experience scan) placed as the retired session briefs Brief 99; 864 and 865 (the graph appearing and updating smoothly, eased hover, a better node, the glow kept) with 802 as Brief 100; 863 (Peek slightly too see-through) fixed in the typos90 merge commit (the body 22% to 32%, the ground 8% to 14%).

- 2026-10-11: 847 (notification actions beside the X), 851 (Select checkboxes above the text), 852 (Library subtab flicker), 853 (OCR search highlight), 854 (Filing style head), 856 (hover ground radius) placed as the retired session briefs Brief 93; 850 and 857 (autocorrect everywhere, find by meaning) as Brief 94; 858 (themes) as Brief 95; 859 (the recording row) as Brief 96; 860 (the composer and the chart maker) as Brief 97; 848 and 849 (Recent changes buttons, suggestion width) sent to the search86 agent; 855 (Welcome and tours wall) was built by grammar57 (Help tour rows); 861 (goals and lists, recognised anywhere) as Brief 98.

- 2026-10-11: 838 to 842 (constellation on a theme change, the quick sketch panel and graph jitter, Agent with no model, the chat dock's round settings button, the timeline's year row) placed as the retired session briefs Brief 91; 843 (the whole-app pass, first run and the tour, element libraries, themes) as Brief 92.

- 2026-10-11: 836 (Add tags with suggestions on lightly tagged notes; Don't suggest tags) and 837 (the owner's typos as composer fixtures, standing) placed as the retired session briefs Briefs 89 and 90.

- 2026-10-11: 835 (props hard to see on Atlas, varied throws, natural motion, more variants) placed as the retired session briefs Brief 88.

- 2026-10-11: 832 (search suggestions, clearing history, undo in Settings), 833 (voice, dictation, vendoring, small features) and 834 (the splash) placed as the retired session briefs Briefs 86, 87 and 85.

- 2026-10-11: 830 (Tidy's layout, undoing a confirmed pattern, gaps at a menu's ends) placed in UI_MODERNISATION_PLAN "Placed from INBOX, 2026-10-11 (Tidy, undoing a pattern, menu gaps)". 831 (the image picker's check sat on the picture's corner) fixed 2026-10-11 in 04-chat-dock-appearance.css.

- 2026-10-11: 828 (voice notes in the background, input devices, noise, live transcription and captions) and 829's focus timer placed in UI_MODERNISATION_PLAN "Placed from INBOX, 2026-10-11 (voice notes, live captions, the focus timer; voiceup)"; 829's board and map previews in WHITEBOARD_PLAN "Placed from INBOX, 2026-10-11 (board and map previews)"; 829's toast buttons sent to grammar57 with 811.

- 2026-10-11: 827 (the extracted text on a file row, the Recordings empty state, a link's details, folders, icons and highlights for links) placed in DOCUMENTS_PLAN "Placed from INBOX, 2026-10-11 (Files, Recordings and Links; libraryup)", owner libraryup.

- 2026-10-11: 826 (the edge arrows missing on a note card, more ends and a Tessellate end, guides while drawing, the board, map and editor feature gap) placed in WHITEBOARD_PLAN "Placed from INBOX, 2026-10-11 (ends, edge arrows, guides while drawing; canvasdepth3)", owner canvasdepth3.

- 2026-10-11: 809, 811 and 813 (the tours wall, the notifications panel's buttons, one bar control grammar) placed in UI_MODERNISATION_PLAN "Placed from INBOX, 2026-10-11 (bars, notifications and tours; grammar57)", owner grammar57.

- 2026-10-11: 814 and 816 (a mind map topic's look shows only after deselecting; the topic's + and link buttons too big) placed in MINDMAP_PLAN "Placed from INBOX, 2026-10-11 (the topic's tools)", owner the mapfix agent; 815 (preview and adjust every export in a panel) placed in WHITEBOARD_PLAN "Placed from INBOX, 2026-10-11 (one export panel for the whole app)", owner the exports agent.

- 2026-10-11: 801 (Agent mode and the composer with no model) placed in CHAT_PLAN; 802 (drag the force graph like main) in GRAPH_PLAN; 803 (buttons, OCR, the constellation, the capture gutter) in UI_MODERNISATION_PLAN, each "Placed from INBOX, 2026-10-11".

- 2026-10-11: 800 (the owner: "another devibecoding, ui/ux modernisation and professionalisation sweep across all ui faces") placed in UI_MODERNISATION_PLAN "Placed from INBOX, 2026-10-11 (the owner's sweep request)": the uisweep agent, then Briefs 57 to 59.

- 2026-10-10: 798 and 799 placed in GRAPH_PLAN "Placed from INBOX, 2026-10-10 (the owner on the graph, again)".

- 2026-10-10: 797 (whiteboard and mind map feature depth) placed in WHITEBOARD_PLAN and MINDMAP_PLAN "Placed from INBOX, 2026-10-10 (the owner on feature depth)", the next Opus brief.

- 2026-10-10: 788 to 796 (the owner's afternoon reports) placed in UI_MODERNISATION_PLAN "Placed from INBOX, 2026-10-10 (the owner's afternoon reports)" and DOCUMENTS_PLAN "Placed from INBOX, 2026-10-10 (code as documents)".

- 2026-10-10: 776, 777, 779, 780, 782, 783 placed in UI_MODERNISATION_PLAN "Placed from INBOX, 2026-10-10 (the owner's morning UI reports)", owner the uipolish agent.

- 2026-10-10: 781 placed in WORLD_CLASS_PLAN "Placed from INBOX, 2026-10-10 (filing suggestions)", an Opus brief after the running ones.

- 2026-10-10: 767 placed in UI_MODERNISATION "Placed from the owner's list, 2026-10-10" and with the notice agent.

- 2026-10-10: 766 placed as CHAT_PLAN decision 62, amending 61.

- 2026-10-10: 729, 731, 734, 744 placed in CHAT_PLAN "Placed from INBOX, 2026-10-10 (the coverage pass over 729 to 744)" and Briefs 37, 39, 67, 84; 561, 725, 728, 730, 735 to 737, 741 to 743, 745 hold their Owner lines here; 694, 727, 739 fixed.

- 2026-10-10: 765 placed in HANDOVER, ROADMAP Direction, CHAT_PLAN decision 61 and DOCUMENTS_PLAN (docx).

- 2026-10-10: 764 placed as CHAT_PLAN decision 60 and the amendment to 32 and 58.

- 2026-10-10: 762 placed in UI_MODERNISATION "Placed from the owner's list, 2026-10-10" and with the mapnotes agent.

- 2026-10-10: 760 and 761 placed in UI_MODERNISATION "Placed from the owner's list, 2026-10-10" and with the carddate and mapnotes agents.

- 2026-10-10: 759 taken (the audio go) in WORLD_CLASS_PLAN "Audio in the notebook" and 28.5.

- 2026-10-10: 753 to 758 placed (HANDOVER Skills note; CHAT_PLAN decisions 58 and 59, F5, Brief 84; UI_MODERNISATION decision 23 and 13.R; WORLD_CLASS decision 63 and Brief 60).

- 2026-10-10: 752 placed in the retired session briefs Brief 34 (second part) and LEDGER.md Atlas rows.

- 2026-10-10: 751 placed as the retired session briefs Brief 75.

- 2026-10-10: 750 placed in WORLD_CLASS_PLAN 28 and the retired session briefs Briefs 72 to 74.

- 2026-10-10: 748 placed in DOCUMENTS_PLAN 23, the retired session briefs Briefs 69 to
  71 and CHAT_PLAN decision 57; 749 placed in UI_MODERNISATION_PLAN "12z
  Learnability" and the existing programme sections.

- 2026-10-07: 740, 746, 747 (connector arrows on rotated shapes, template
  connectors that do not follow, Reset style) placed in WHITEBOARD_PLAN.md,
  "Placed from INBOX, 2026-10-07".

- 2026-10-05: 596, 608 (board rail and dock, edge auto-pan) placed in
  WHITEBOARD_PLAN.md and 607, 609, 610 (map from the graph, smooth
  branches, node toolbar) in MINDMAP_PLAN.md, "Placed from INBOX,
  2026-10-05 (boardmap-1005)"; the boardmap-1005 agent holds them.
- 2026-10-05: 540, 554, 556, 564, 575 (Atlas motion and form) placed in
  LEDGER.md, "Atlas, placed from INBOX 2026-10-05"; the Atlas
  agent holds them.
- 2026-10-04: 528 (the knowledge graph, better than Obsidian and Notion)
  placed in GRAPH_PLAN.md, "The knowledge graph, 2026-10-04".
- 2026-09-13: 128 placed in DOCUMENTS_PLAN.md.
- 2026-09-13: 162, 159 placed in WORLD_CLASS_PLAN.md.
- 2026-09-13: 165, 164 placed in UI_MODERNISATION_PLAN.md.
- 2026-09-08: dashboard hero preference, New note tile colours, sub-tab
  arrow keys, Files reading, sidebar toggle, mindmap bugs, line numbers,
  docks as one bar, timeline redesign, responsive design, em-dashes,
  paragraphs to popovers, security review: all placed (HANDOVER "flagged
  list") and most built.
