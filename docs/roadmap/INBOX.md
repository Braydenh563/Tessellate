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
   belongs to; it is never built ad hoc. INBOX is intake only: a triaged item
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

1779. **Graph spoke, 2026-11-11 ~17:50Z (decision asked for, not the owner's words):** the composer panel with a model on (Qwen2.5-1.5B, one blind tester, 25 questions) rated the model's answer 12.2 of 20 against the composer's 16.1, worse on 17 and tied or better on 8; the existing validator flags only 4 of the 17. Asked: at 3B and below, should plain Ask answer from notes (the composer) by default? Recommendation (taken, standing order 3): keep decision 75 (the model leads when one is on) for PR 216, since changing it remakes a decision; the figures are in CHAT_PLAN "Open from Phase 6" for the owner to overrule. **Placed: CHAT_PLAN, Open from Phase 6.**
904. **The owner, 2026-10-17, verbatim** (a OneNote bug list pasted into a Word document, 86 items, screenshots described in `bugs-1017.md` (git history); the pasted model-thinking transcript under B42 is elided). Triage and per-bug status: `bugs-1017.md` (git history). **Placed: LEDGER** (the open B rows from the E18 triage were swept into LEDGER; B04, B36, B83 and B86 are L-world-class-1, L-documents-1, L-world-class-2 and L-chat-1).

     B01. A first install setup popup showed as I was looking through the app but I accidentally clicked off it and idk what it was, there should be some way to access it, like a get started dropdown checklist to complete and maybe they can go in the notifications as well?? **E18 fixed.** 0b082cb; frontend/js/first-run.js (Get started).
     B02. The composer needs more understanding, it still has a lot of flaws **E18 true.** Coverage answer fixed (src/tessellate/ai/notebook_stats.py:948); the composer's general understanding is open (W7, O3).
     B03. Use composer to refine magic add on reminders like with bad sentence grammar and spelling mistakes and intent etc **E18 true.** Composer refining magic add was placed (row O8, bugs-1017.md).
     B04. Autocorrect on reminders and other app surfaces with harper, maybe other libraries and the composer, but also subtly highlight or colour the change for the user to notice in case it is wrong, then the user can hover over it and confirm it, edit it, or rewind the change. **E18 true.** Harper runs in the note boxes (frontend/js/autocorrect.js); no harper hook on reminders or magic add.
     B05. I think the connect a model buttons in the no ai available popups should have a mini dropdown arrow on the side of the button so the user can click it as the connect a model button, or they can click the dropdown menu and press a shortcut button for hiding the popups instead of having to go into settings to manually find and toggle it. **E18 fixed.** 86cb8e0; frontend/js/offline-split.js:31 and :39 (Hide these popups).
     B06. When adding tags in the edit notes form, the tag textbox just keeps getting shorter and shortyer until it eventually goes to a new line, I feel like it should just permanently be on the line below with the tags being placed above **E18 fixed.** e70f11e (tag input sits on its own line below the chips).
     B07. Should this have an '?'?? I want the composer to have more variation, could it be more dynamic and actually come up with responses like an ai and not just preprepared responses?? idk **E18 true.** Variation placed: replies come from fixed tables (src/tessellate/ai/composer_smalltalk.py); the '?' is an owner question.
     B08. This is alright but I feel like it should have acknowledged that it could be a test note?? Don't just account for this exact example, the composer needs to respond well to anything like this or similar scenarios. Like what if the user just button mashes or does a random string of keyboard charracters?? The composer needs to be like apple's siri with the same utility and usefullness and decent responses but better **E18 fixed.** src/tessellate/ai/intent.py:341 is_mash and :366 is_test, used at :278 and composer_smalltalk.py:250.
     B09. It autocorrected my spelling, and it underlined it blue which is good, but when I clicked the word that was underlinedd, it instantly reverted, it should probablu show a little undo icon popup button near the word for confirming or reverting if the word is clicked on instead. **E18 fixed.** fc388f3; frontend/js/autocorrect.js:238-239 (Put back, Edit the word).
     B10. Also the composer is "Atlas's Assistant" and the ai models are Atlas themselves, it shouldn stay composer. Also it should probably tell the user that it is the assistant and if they want to talk to atlas, they should connect a model. And it should also give a composed general rundown of capabilities. This should be composed and not a set response, with variations, longer or shorter based on response style and user request etc. if the user asks about specific features or more yk?? **E18 fixed.** 008594fa5 and a9d427ce9 (Atlas's assistant; composed rundown).
     B11. The guide should alo consider that some queries may not be related to the current page the user is on and needs to bnetter detect intent **E18 true.** Guide intent off the current page is W22 (open).
     B12. Why does the quick access look so small on the full view?? **E18 fixed.** cec4e74 (a short window keeps Full).
     B13. Unchecking a quick access option in the edit quick access panel navigates me to the unchecked option and then if I want to uncheck multiple I have to keep scrolling up. **E18 fixed.** ba7df45 (unticking keeps the manager's scroll).
     B14. Each settings page should have an expand and collapse all sections button at the top **E18 fixed.** a29dfab; frontend/js/settings-controls.js:3260-3264 (Expand all / Collapse all in a pane's dock).
     B15. I think we should market the application as "Tessellate Notes" but it is Tessellate for short… **E18 true.** No 'Tessellate Notes' string in frontend/ or src/ (0 hits); the About text bugs-1017 cites is not on base.
     B16. The properties panel popups like with the date select arent the custom style like sued in the reminders tab **E18 fixed.** 513f237 (custom picker on book type documents).
     B17. When making ned documents, I shouldn’t have to enter a title, it should fill it with "Untitled Document #[number}" and then have it preselected and highlighted for the user to replace it. That way if the user cant be bothered or cant think of a name they don’t have to. Also there should be an option in the editor to have the composer and ai if it is available suggest and rename the document. This should be the same for boards and maps as well. **E18 true.** Names and selection fixed (787f8a9); the AI rename option in the editor is still placed in DOCUMENTS_PLAN.
     B18. On the document editor, I want a library of prefileld templates and curated text sections and stuff like the code snippets but for general documents as well **E18 true.** Curated template library placed in DOCUMENTS_PLAN).
     B19. Also there needs to be more debugging and running tools for the other offered document types and languages, and also there needs to be code snippets and prewritten code examples and skeletons for all document types and code languages. And I want to be able to have it like it is now  where I select somehwere in the document and click the snippet and it pastes there, but also I can drag the snippet from the library and paste it whwere I drag it to and there'll be a ghose cursor under my dragging cursor where it will place and if I drag my mouse to the bottom or top of the document then it wills begin to scroll up or down if the document is long and scrollable. **E18 true.** Snippet drag with ghost cursor placed in DOCUMENTS_PLAN).
     B20. On lined documents I want there to be a togglable temporary manage or edit mode or smth where it allows me to rearrange content by line and or elements **E18 true.** Manage mode on lined documents placed in DOCUMENTS_PLAN).
     B21. I switched from a md document to a code document and then back to md but it still thought it was and treated it like a code document. **E18 fixed.** 9b9580c (a forced Source is no longer stored).
     B22. Also live view on the document editor for md files should be default not source. **E18 fixed.** 9b9580c (live view is the default).
     B23. Also the tables in the live view for document editor should have more management capability, like lines on the edges and rows and columns on the outside etc to select whole rows or columns, or to add new rows or columns or even dragging icons to drag and rearrange coumns and rows if they are selected yk?? I cant even highlight select the live view table or multiple rows, columns or cells, and Im not given a popup menu for tables when I righ click them. This needs expansion and probably the same for other elements and the whole luve view for md as well. **E18 true.** Live-view table row and column management placed in DOCUMENTS_PLAN).
     B24. Awkward popup in board **E18 fixed.** a6bc16d (one row of actions).
     B25. I want to be able to make wireframes and diagrams like erd, orm, uml, class and other diagrams on the boards so I want the proper elements available for them and templates **E18 fixed.** frontend/board-library/templates.json:2349 (Class diagram), :2803 (erd), :3193 (wireframe).
     B26. These dropdowns don’t show anything **E18 fixed.** 25f4a69 (the library list keeps its scroll on redraw).
     B27. I shouldn’t be able to uninstall the desktop view in the packaged windows app **E18 fixed.** 04a1a7e; src/tessellate/core/extras.py:1118 removal_locked.
     B28. Is it possible for tessellate to run on its own hosted and managed local server instead of on local host?? **E18 true.** Own managed local server placed in ROADMAP and research).
     B29. The whiteboard needs a lot of work, like the ungroup button on the popup tools doesn’t change, I cant widen objects on one axis when grouped, resizing or moving objects doesn’t update their xywh values in the format panel in real time, the popup controls are all over the place, it just needs soo much fixing, refining, redesigning and more. **E18 fixed.** 183ec07 (Group/Ungroup follow the selection; W/H scale; x/y/w/h live).
     B30. Composer still needs a lot of refining and fixing. It is still very buggy, lacks a lot of understanding, and just straight up gives me the note back to me without any actual composing in the ask tab. **E18 true.** Composer answers and the note-back reply are O1 (open); recency alone does not close the row.
     B31. Add tessellate as a taxonomy option **E18 fixed.** src/tessellate/ai/data/taxonomy/memorymap_taxonomy.json:1087 (Tessellate topic).
     B32. It filed my newest note about uni assignments in the about tessellate category?? That's wrong and now I need to go and manually change it and probably make a uni or studies or smth category idk **E18 true.** Not reproducible from code; needs the model that filed the note (bugs-1017 question).
     B33. Can the comoposer do these ai actions well and just as good?? And they arent ai actions If the comoser does them when the ai isnt available **E18 true.** Composer running AI actions without a model is O7 (open).
     B34. More workflows and actions?? **E18 true.** Placed in AGENT_SKILLS_REFORM.
     B35. Companion doesn’t scroll with what it is perched on if the thing it is perched on is scrollable sometimes on the dashboard. **E18 fixed.** 89cfc4e (scroll area adopted after the perch).
     B36. On draw.io I can pan by holding down my right mouse button and dragging, scrolling on the mouse is zoom. **E18 true.** No right-button pan in the diagram code (grep of frontend/js for button 2 finds companion and whiteboard lines only).
     B37. Pressing down the scroll wheel and dragging sometimes glitches a little initially when starting to drag. **E18 fixed.** f013e84 (wheel press pans; default prevented).
     B38. Attaching a file or thing to a mind map node makes a node that I cant edit or even go to the thing attached. **E18 fixed.** de37669ac (mind map file and bookmark nodes open; captions).
     B39. Rebuild or vendor jupyter notebook in tessellate document editor?? **E18 true.** Jupyter in the document editor placed in DOCUMENTS_PLAN).
     B40. The ai should be aware of the user's current time in its responses through ai harness context. **E18 fixed.** src/tessellate/ai/librarian.py:647 clock_hint, used at :454.
     B41. No numbers on matching records while the ai is thinking **E18 true.** Not reproduced; the owner's question on numbers while thinking is open.
     B42. I used plan mode and the model didn’t have access to the make_plan tool **E18 fixed.** src/tessellate/ai/tools/tool_sets.py:142 (make_plan in the plan tool set).
     B43. Thinking **E18 stale.** A bare word from the paste with no behaviour; 5c0b10a60 already re-driven it as stale.
     B44. The user wants me to plan a development of an app that acts as a "backpack on screen" - like Microsoft Sticky Notes, but where the user can store things (copy and paste regularly), then press one click "copy" on stored content to easily copy it. **E18 stale.** A pasted prompt for a different app, not a Tessellate behaviour.
     B45. They say "Plan this before you do any of it. Call make_plan with the goal and the steps, then carry the plan out." **E18 stale.** A pasted prompt; its behaviour is B42 (fixed).
     B46. […elided: the pasted model-thinking transcript, 82 paragraphs; its point: plan mode was on, the task said "Call make_plan", and the model's tool list had no make_plan, so it spent its turns reasoning about the missing tool and created no plan…] **E18 stale.** Elided transcript placeholder; its point is B42 (fixed).
     B47. Poor agent harness design and needs a lot of improvement. **E18 true.** Harness design open (O10).
     B48. Use composer to custom name tool calls?? The way tools are offered and other parts of the agentic harness need to be refined and improved. **E18 true.** Tool naming and offer refinement open (O10).
     B49. The agent failed **E18 fixed.** The label 'Failed due to error' is gone from src/ and frontend/js; why it failed needs the model (bugs-1017 question).
     B50. I think the splash needs a bit of refining in how it l;oosk and works visually, and I can't minimise it (if that is possible) **E18 true.** Minimise exists (scripts/splash.ps1:440-457); the visual refinement is open; Windows only, not run here.
     B51. I think the user's should have a button or way to access the project's github from the settings pages. **E18 fixed.** frontend/index.html:14839 (about-github link).
     B52. Easier way to set up docker and mcp server and get a link or smth I can use to connect claude or another ai to it if I wish. Can we give the mcp server the ability to restrict access to certain notes or things?? Like a custom settings or token that the user can use to give other ai's access through the mcp server but one that the user can control that the ai's have access to in their notebook through that token or url etc. **E18 true.** MCP is stdio only; a restricted token and remote access were placed (ROADMAP).
     B53. Cant set up mcp server in settings?? **E18 fixed.** frontend/js/settings-controls.js:2214 (mcp-config-snippet in Settings, Tools).
     B54. Is that side selection line on the right wrong?? **E18 true.** Not reproduced; the owner's question on which line is open.
     B55. Idk how to use the web clipper, it is unintuitive to use and hidden in settings, can you redesign the ui and ux of how it can be used and accessed?? Also the button in the dropdown for starting searxng in the web sidebar in the chat tab is gone. **E18 true.** Web menu fix 1784757; the clipper redesign is placed (too large).
     B56. When settings are on auto, I cant tell what it autoed to… **E18 fixed.** dd53c5f; tests/test_settings_bugs_1017.py:64 and :227 (Auto names its answer).
     B57. If I change the app's appearance colour and then try to change back to default, it changes to indigo instead… **E18 fixed.** 5567c10be (Default no longer paints indigo).
     B58. I want the hover time to preview themes to be slightly longer or add like a small eye icon button in the corner to preview. Also across the app, there are quite a few instances where clicking an icon button to toggle smth doesn’t change the icon's look so it is hard to tell if it worked or not. **E18 fixed.** 4f7f073e0 and 35b100d15 (theme eye; icon toggles swap their glyph).
     B59. The app seemingly redownloaded the embedding model (I already had It but idk), except it still says it is connected to the internet which it isnt really right?? Idk **E18 true.** embeddings.py:1079 still fetches again when a stored copy fails to load; the owner's question is open.
     B60. This dropdown combobox and the text next to it arent aligned properly **E18 fixed.** b0c7e36 (OCR caption centres on its select).
     B61. For the dictation model size there is no idication for which ones are installed, does the app check which modesl are stored even if they arent offered?? Also gemma 2 embeddings doesn’t need the lisence if you use the unsloth version, unsloth versions I find are a lot better than the main versions. Also if I click a different dictation model size, does it download immediately?? What if I change my mind?? Can I delete or uninstall models like for dictation and embedding etc that I don’t want?? **E18 true.** Installed markers and Remove exist (settings-packages.js:110, :122); the unsloth licence variant is not offered.
     B62. The profile avatar in the enlarged popup from double clicking the profile picture doesn’t have any life to it. **E18 fixed.** 7d9c563; tests/test_companion_viewer_face.py.
     B63. When I change the theme or colour in settings, the animated app logo in the dashboard hero doesn’t update to the new colour until I reload or switch tabs and go back **E18 fixed.** ae7fc72; tests/test_settings_bugs_1017.py (crimson accent case).
     B64. The quick access sometimes loses it's full form and then goes really small and short. **E18 fixed.** cec4e74 (see B12).
     B65. Stop th emodel options should probs be disabled when no ai model is running **E18 fixed.** 6cb4ef988 (Use this model and Stop the model follow what exists).
     B66. I didn’t even have the app running the whole day until less than 26 minutes ago **E18 fixed.** 94db83d73 (an interrupted run keeps its own start time).
     B67. The top of the suggested models section should show the detected hardware of the user and allow the user to adjust or edit it if it is incorrect. Also I feel like the "fits" or "tight" suggestions etc should take into account the user's current memory and stuff if possible and what and how many ai models they already have installed. **E18 true.** 4f7f073e0 names the cores and free memory; editing the detected hardware was placed (LEDGER, the E18 sweep).
     B68. Gemma4 26b is a4b **E18 fixed.** cc91af39d; src/tessellate/ai/model_manager.py:131 label 'gemma4:26b (a4b)'.
     B69. Can the composer run skills and do them well?? The composer needs a lot of work and upgrading and making better. **E18 true.** Composer skills are O7 (open).
     B70. Why does this node wanna be all  the way down there?? The graph force structuring is still a bit messy and uncool looking **E18 true.** tetherForce is a partial leash (frontend/js/graph-worker.js); the owner's data is not reproduced.
     B71. This image is me separating them out as it was soo messy and stuck together before I couldn’t read it. **E18 stale.** An image of the owner's separated nodes; no behaviour to check.
     B72. Have the timeline calendar on the timelone act and be more usable as a calendar, I wanna be able to double click on a date and be able to add an event and set a reminder and stuff. Also on the timeline I wanna be able to scroll above today's date to see future dates and also I want the app to be able to recognise future date and time mentions and suggest to use magic add to add it to the timeline, calendar and as a reminder **E18 fixed.** 1c7182d, f06de1e, 69064a7 (calendar add, week ahead, future-date offer).
     B73. Cant select on separate attachment nodes in the graph?? **E18 fixed.** 0cf90ce13 (a graph click opens file and document nodes).
     B74. Could there be a way to print out or render a document or attachment in the whiteboard?? Like a pdf or document viewer object that the user can resize and move around, or even print the documents as separate pages like images that the user can move around, like dragging a document on onenote and having the option to print it out or place as an attachment **E18 true.** No document or PDF object on the whiteboard (frontend/js/whiteboard-commands.js); placed in WHITEBOARD_PLAN.
     B75. The text size in tooltip dropdowns across the app are always different and arent consistent (I think) **E18 fixed.** 24cf030e3 (one text size for help popovers).
     B76. Should the drafting rotating animation and text be at the top of the ai side not the bottom of the user input side in the writing room?? **E18 fixed.** af021363d (drafting spinner at the top of the Atlas side).
     B77. **Fixed 4261fca** (the late answer's row is "Waiting for a late filing answer" and ends on every way out; finished runs show "Finished in 2 ms at 12:03 AM"). The agent run still says the note is filing but it is finished. Though there needs to be some more metrics like how long it took to file and similar across the app. **E18 fixed.** 4261fca; frontend/js/activity-panel.js:103 ('Finished in'); src/tessellate/ai/janitor.py:713 (late filing end).
     B78. 9:57:12 pm INFO:    tessellate.embeddings: retrieval matrix warm with 46 vector(s) **E18 fixed.** da49e08; src/tessellate/core/database.py:549-550 graph_pin_x and graph_pin_y.
          10:02:29 pm ERROR:   browser: [HTTP 422] PUT /graph/pin/document:2: Check the entry id and try again.
          10:04:57 pm INFO:    tessellate.jobruns: [run-7] Drafting started
          10:05:27 pm INFO:    tessellate.jobruns: [run-7] Thinking.
          10:07:01 pm INFO:    tessellate.jobruns: [run-7] Writing the answer.
          10:07:03 pm INFO:    tessellate.jobruns: [run-7] Done: 1 word.
          10:07:03 pm INFO:    tessellate.jobruns: [run-7] Drafting finished
          10:08:18 pm INFO:    tessellate.jobruns: [run-8] Filing a note started
          10:08:30 pm INFO:    tessellate.janitor: janitor: the model said 95% for 'Thoughts & Ideas'; shown as 78%
     B79. The writing room translated note I filed got filed as a draft, is that intentional?? **E18 fixed.** e7bb5ff8c (Save files a note; the caret keeps a draft).
     B80. Tag with atlas didn’t work right, it didn’t suggest tags, it doesn’t have a field for me to add more tags, it didn’t suggest alternate categories to make or move to if they  were viable, and all it gave me were suggested links… **E18 fixed.** e7bb5ff8c; frontend/js/tag-suggest.js:539 (categories and a tag field).
     B81. Can you add the japanese emoticons library to the available emojis library?? **E18 fixed.** 5350dcd (Japanese emoticons group).
     B82. Some emojis don’t appear in the search when the user tries to look for them and uses the wrong name like🙏 this is called folded hands but It should be both high five and pray orsmth yk?? **E18 fixed.** frontend/js/icon-picker.js:212-213 (aliases for folded hands).
     B83. The composer written weekly digest sentences count as a clickable button in the weekly digest **E18 true.** Digest sentences as buttons is O9 (open); not re-driven.
     B84. Do the patterns ever change?? What's the meaning or use of them?? Can I view them or smth?? {" **E18 fixed.** frontend/js/settings-controls.js:2659-2680 (confirmed patterns list); src/tessellate/ai/help_topics_more.py:3624 (meaning).
          Patterns: university, 4 times since 16 July"}
     B85. Composer's wording and grammar, especially around dates is a bit off and hard to read. And other things could be improved as well **E18 true.** Composer wording and dates are O4 (open).
     B86. The compsoer guide didn’t answer my question :( **E18 true.** Guide answer gap is W22 (open).

## Placed (last 20, newest first)
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
