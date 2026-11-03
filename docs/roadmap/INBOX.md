# Inbox: things the owner dropped in while work was in flight

**How this file is used (the interrupt rule).** Anything the owner sends
while a step is in progress (a bug, a screenshot, a request, an opinion,
a usage figure) is appended here verbatim with the time, and NOT acted on
until the step in hand has passed its gate and is committed. Then, at that
boundary only, the inbox is triaged in one pass:

1. A bug in something built this session goes next (it is cheaper now).
2. A bug elsewhere goes into the relevant `agent-remaining/*.md` or
   BACKLOG row with the owner's words, and is scheduled by impact.
3. A feature or design request becomes a brief row (SESSION_BRIEFS or the
   plan it belongs to); it is not built ad hoc.
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
(GRAPH_PLAN Phase 6), the mind map ring (MINDMAP_PLAN "Decisions made,
2026-09-13 night", the mapux agent), and the second batch's five
not-reproduced visuals (BACKLOG, "Reported, not reproduced"). Everything
below is open work from the night of 2026-09-13 and the morning after,
with its owner named in the entry.

## Open items

1582. **Owner, 2026-11-03, verbatim:** "also what autocorrect and spellchecker does MS word use, can we use it to help improve the current libraries and harper?? cna we make it so the user just has to install the packages for their language??" Answer: Word uses Microsoft's own proofing tools (closed, not licensable, not shippable). Recommendation taken: keep Harper plus the open Hunspell dictionaries (the LibreOffice and Mozilla word lists, per language, MPL/LGPL/GPL-compatible) and LanguageTool's open rule sets where licences allow (AGPL may take LGPL); per-language packs the person installs from Setup, one download each (dictionary, affix rules, autocorrect list), joined with D30 language packs in BACKLOG. **Then, verbatim (screenshots: a note with "I havent been" not underlined, and "ive" offered only "Ive"):** "it didnt pick up my misspell of \"havent\"??"; "or ive". A bug, first: apostrophe-less contractions (havent, ive, dont, cant, wont, isnt, im, youre, theyre, shouldnt and the rest) are flagged and corrected to the contraction ("haven't", "I've"), with "I" capitalised; a test over the whole contraction family, not these two words.

1581. **Owner, 2026-11-03, verbatim:** "is there more behaviour and npc improvements we can add to and make with the atlas avatars and general companions??" Recommendation: yes; a judge-rung design pass lists behaviours by cost (reacting to what the person does: a note saved, a streak, a long silence, a search with no result; idle routines with variety and rarity; attention that follows the pointer and the open surface; moods that drift through the day; small interactions with the page such as sitting on a card edge or peeking from the dock; a reaction to being dragged or poked), each with a rule that it never blocks a click, never runs while the person types, and costs nothing at rest (transform and opacity, one timer grid).

1579. **Owner, 2026-11-03, verbatim (screenshots: the Calculator and the equations panel):** "can the calculator actually use proper rendered icons/symbols and spacing for the written equation?? do they get rendered as such if the user types them?? can the calculator have other versions like as a scientific calculator?? also this message keeps appearing while Im entering in an equation" ("55*9+" shows "That is not a sum, a percentage, a conversion or a date question the app can work out."); "this equation button's contents get cut off on each side" (the 3x3 matrix tile's brackets clipped); "is there anything missing from this equations list?? surely there are more symbols and equation things and such right??" Recommendation: the sum line renders as typeset maths as typed (× ÷ − and superscripts, spaced operators) with the raw text kept for editing; no error while the input ends in an operator or an open bracket (the error waits for a pause or Enter); a Scientific mode (trig, logs, powers, roots, factorial, constants, degrees and radians, memory); tiles size to their content (no clipped brackets); the equations palette gains the missing groups (Greek letters, relations and arrows, sets and logic, accents and decorations, limits and sums with limits, matrices and cases, common formulas).

1578. **Owner, 2026-11-03, verbatim (screenshots: Find anything's kind row cut at "Remi" under Sort; the Activity heatmap scrolled to the far left of an empty year):** "in the find anything section row below the search bar, that scrollable row has no horizontal scrollbar"; "also the activity heatmap is auto scrolled to the left and not right where the actual data is". Recommendation: a scrolling chip row uses the one scroll-row recipe (thin visible scrollbar on pointer devices, edge fade, arrows where it overflows) and never runs under its neighbour (Sort); the heatmap opens scrolled to today (right end) and keeps that on resize.

1575. **Owner, 2026-11-03 (pasted server log, Windows):** `Lag: frame 1340ms on dashboard: 1329ms of script with no source file, then 11ms rendering` and `frame 260ms ... 255ms of script with no source file` about 3 s after start (after Housekeeping and the spelling lists, before the embeddings loaded); earlier `frame 314ms on dashboard: 275ms of script with no source file`. Recommendation: reproduce at boot on the dashboard at 4x CPU with a Performance trace; "no source file" is script the lag reporter cannot name (an eval, a `new Function`, a blob or inline worker, a wasm compile, or a vendor bundle loaded as text): name it in the reporter first, then split or defer it so no boot frame passes 50 ms. **Second log, 2:26 to 2:28 pm, dashboard:** "no source file" frames 256, 458 and 269 ms recur after boot (not only at start); `atlas-life.js atlasTailFrame` 32 ms (forced layout 31); `atlas-motion.js atlasRigFrame` 36 calls/s at 3.8 ms each (136 ms of every second) and 25 ms forced layout; `companion-menu.js` setTimeout 52 ms (forced layout 50); input 384 ms `pointerout on div.modal-overlay.nm-viewer`, 352 ms `pointerout on span.chip.nm-viewer-act`, 328 ms `pointerup on button.menu-item`. **Third log, 2:34 to 2:43 pm:** `avatars.js go 540ms (forced layout 417ms)` and `TimerHandler:setTimeout 749ms (forced 500)` on library; tab clicks `input 944ms ... #tab-btn-dashboard` with `phone-shell.js ...onclick 192ms (forced 137)` plus avatars 590 ms, `#tab-btn-notes.onclick 104ms (forced 89)` plus `navigation.js revealTab 39ms (forced 38)`; library OCR: `apiJson /media/11/ocr-regions ... 260ms (forced layout 238ms)` and `library.js ocrScheduleFitDock 66ms (forced 65)`; reminders `apiJson /health ... 78ms (forced 39)`.

1574. **Owner, 2026-11-03, verbatim (screenshots: the Windows launcher splash with the PowerShell icon on the taskbar; the splash's logo tile next to the app's):** "at least on my version, when the splash is showing before the app window starts up, the windows taskbar icon is the powershell logo and not tessellate. also the colour gradient on the splash isnt the same as all the others and has much more pink" Recommendation: the splash window sets the app's AppUserModelID and its window icon (the same .ico as the app window) so the taskbar shows Tessellate; the splash logo uses the one brand gradient (the icon file itself, or the tokens the app's mark uses), with a test that the splash's gradient stops equal the mark's.

1568. **Owner, 2026-11-03, verbatim (screenshots: the OCR workspace on a board export, a region drawn round the "Goal" box, "No text was found in that region."; the full read gives "New to}" at 78%):** "the text couldnt be read in the region on an image?? im using tesserract rn..." The labels are about 8px tall, dark on light boxes over a dark canvas. Recommendation: before Tesseract, a region's crop (and a whole page with small text) is upscaled so the text height reaches about 30px, converted to grey, inverted when the ground is dark, and binarised (Otsu); the region read tries the single-block mode and falls back to sparse text; test with a rendered 8px label on a dark ground (a fixture PNG) read through the real pipeline where Tesseract is installed, skipped where not.

1566. **Owner, 2026-11-03, verbatim (screenshots: the Calculator and equations panel, Equation tab):** "I want you to redesign this quick jump scroll menu, also it doesnt have a horizontal scrollbar" (the row of boxed group buttons, Fraction to Bracket) and "can you also redesign that pill selector?? it looks awkward, the whole equations panel needs a slight better modern and professional redesign" (the Inline / Display segmented well under the Sum, Units, Equation tabs). Step 1 (this commit): the jump row is a `.tabs-line.edge-fade` strip with a thin scrollbar and wheel-to-sideways scroll, not measured in a browser yet. Rest, for an agent with the recipes: the Inline / Display choice as the `.seg` recipe at the dock height (or one row with the lede, Pin and LaTeX), the lede and its two boxed buttons as one quiet toolbar row, the tile grid's tiles quieter (inset fill, no ink edge, glyphs centred and larger), group heads on the type scale, the foot ("Insert writes into the note once there is an equation." plus Copy and Insert) as the dialog foot recipe with the one filled button last, spacing on tokens; measured at the panel's default and narrowest sizes, light and dark. Then, verbatim: "also I dont like excessive use of these glowy grey styled buttons, they feel vibe coded, its alright ot still use them but just not excessively yk?? use them intentionally and in a modern and professional way. also with that toggle pill for inline/display, small toggles like that where they ar eon their own line and the only thing on their line and they are just there on the right, it just feels liek the pill has been chuckedc there with no thought, like at least make it extend the full width or redesign it some other way" (screenshots: the calculator keypad, twenty bordered grey keys; the equation tiles; Pin and LaTeX boxed). Class: a bordered grey ghost button used for every control in a grid or row; and a lone `.seg` on its own line. Recommendation: a DESIGN rule and lint: a grid of keys or tiles takes the quiet inset fill with no edge (operators tinted, `=` the one filled key), a toolbar's secondary actions are icon or text buttons without an edge, the bordered ghost stays for a lone secondary action beside a filled one; a `.seg` alone on its line spans the row (equal segments) or joins the row of the control it governs. Sweep every surface for both, after the equations panel. **Panel built 6c08378** (the sweep of the other surfaces remains, `agent-remaining/a30n-1103.md`): seg 492 of a 492px row (320px: 284 of 284), keys and tiles border 0, keypad glyphs 18.4px, group heads 12px/600 on the eyebrow, jump row scrollWidth 1311 over 492 with a thin bar, foot right edge at the row's, no horizontal overflow at 1440 and 320, light and dark; the Radical tiles' x cleared the sign by 0 and 0.5px before, 1.5px after (an ink-component count on a 4x capture), no tile has ink at its edge. **Sweep a30q (6894c02, 56c97cb, c7d9119, c911fec, 246ee43):** bordered ghosts 80 to 15 across the tabs and Settings, 23 to 9 across the deeper states (1440, light); every lone seg spans its row (prompt 438 of 438, Forgot password 418 of 418, 300 of 300 and 336.8 of 336.8 narrow); radicand gap 0 to 0.5px before, at least 2.5px after in Live, Read and the tiles. Left in `agent-remaining/a30q-1103.md` (Reminders filter chips, icon pickers and add-widget tiles, dark, 390 and high contrast unmeasured), so the item stays open.

1564. **Owner decisions, 2026-11-03 (asked and answered):** U15 arrange menu: "I think it is a good idea to make it subsectioned yeah" (build the submenus). E33 Guide lead: sentence first, the click path as its own second line (the current order; tests stay). E50: keep Fork and Compress in the phone chat menu. U41: shorten the map-created toast to one line with an action, the longer help behind the help button (tests/test_wb_dog1_fixb.py changes with this dated reason). D30 spellcheck: "japanese, chinese, uk/us english spelling, shouldn the user be able to download language packs like with MS Word?" plus Spanish, French and German, Portuguese. Recommendation: language packs downloaded on demand from Settings (like the model downloads: one download, then offline), a per-document language, UK and US English as two variants of the bundled list; Japanese and Chinese have no word-list spellcheck (no spaces between words), so their pack gives the document language and input hints only, said plainly in the pack's card. Also "tell me about this" joins composer_digest `_THIS` (a30e's found-not-fixed).

1560. **Owner, 2026-11-03 (pasted logs, Windows, 0.6.2-2f2e9850e8):** `Lag: frame 362ms on notes: avatars.js nameMarkBuddyBeat 156ms (forced layout 98ms); avatars.js nameMarkBuddyDodge 12ms`; `input 368ms on notes: pointerup on button.active in #notes-subtabs`; `input 1016ms on dashboard: pointerout on div#dash-grid.spans-ready` with `frame 534ms: 525ms of script with no source file`; `input 464ms on dashboard: pointerout on span.dash-list-title in #dash-grid`; `frame 860ms on dashboard: animation loops (top: atlas-motion.js atlasRigFrame) 8ms`; `request 3339ms on dashboard: /models/status`; `frame 410ms on dashboard: theme-boot.js 8ms` (boot, while the jobs ran). Later on Graph, at rest: `raf 397ms: graph-canvas.js gcRequestDraw 55 calls/s, 7.2ms each` (a redraw every frame with nothing moving). On Documents: `library.js openDoc 94ms (forced layout 53ms)`, `icon-picker.js BUTTON.onclick 256ms (forced layout 247ms)`, `mermaid-frame.js DOMWindow.onmessage 234ms`, `input 880ms pointerup on div.cm-content`; Notes: `media.js Promise.resolve 194ms`, `math-editor.js onload 202ms (forced layout 167ms)`; `request 18447ms /voice/transcribe` (the model load plus a needless huggingface.co check, fixed with local_files_only). Then on Chat: `frame 216ms: avatars.js Promise.resolve 177ms (forced layout 104ms); avatars.js nameMarkBuddyDodge 9ms`; `input 472ms on chat: keydown on textarea#chat-input`; `frame 245ms on chat: app.js Response.json.then 218ms (forced layout 125ms) [apiJson /conversations/100/truncate from whiteboard-history.js apiJson]; chat-agent.js DIV#chat-messages.onscroll 12ms`. Recommendation: a perf agent reproduces each at 4x CPU, removes the forced layout in nameMarkBuddyBeat (read geometry once per beat, write after), finds the pointerout handler on #dash-grid, and makes /models/status answer from cache while the backend probe runs.

730. **The owner, 2026-10-06, verbatim**: "also would the composer be able to
     somewhat accurately put new notes into a category using meaning similarity,
     mathematical shenanigans, keyword, and more and like the embedding model as
     well?? the embedding model should still be accessible and usable without the
     ai right??" Answer: yes, filing without a model already runs (lexical
     filing, category centroids and nearest neighbours over the embedder, which
     needs no AI model); next is measuring its accuracy on a held-out set and
     letting the composer explain each filing in one line.
     Owner: Brief 39b (filing and the taxonomy), WORLD_CLASS_PLAN 23; the held-out accuracy measure and the one-line explanation of each filing are its rows.

810. **The owner, 2026-10-11, verbatim** (screenshots: the personas' quiet
     Edit and Delete text buttons; Keyboard shortcuts with a bordered tinted
     "Change" on every row; What it learned, three "Claim" cards with a large
     checkbox and a tall empty bottom, one of them a joke): "also on the
     personas, see the edit and delete buttons?? I want the same styling for
     other areas on the app and/or settings like with the change buttons on
     the keyboard shortcuts?? maybe?? is that a good design decision?? I want
     your opinion. I want controls and tools and stuff around the app to be
     cleaned up more. also in the what it learned, some of the things like me
     writing when my uni days are are correct, but with other test notes, like
     with the homework joke i had are incorrect. if it learns something it
     also needs to make sure that the context od the thing it thinks it is
     learning is correct, like that note is tagged as a joke yk?? the composer
     needs A LOT more contextual understanding and needs to actually do its job
     right. it needs to be the siri for the application, the user should be
     able to ask it general questions like for maths, timezones, statistics,
     what the app cna do, what the user can do on the app, things like history
     records, maybe if it web searches it can show a panel of the web results
     in a dropdown like with the thinking box?? maybe if it finds a web site it
     can render the extracted website in a dropdown or panel?? things like that
     are only the surface. the composer. like I asked if it could web search
     and then searched the web for the word "web" and then didnt even output
     the results. it needs soo much more work. also using the composer for
     other application functions in the background and suggestions and search
     history, prefilling responses or suggesting sentence or word completions
     with the greyed out text that they can tab to or use arrows to accept etc
     yk?? and also if the app collects insights or questions, then I thing the
     ai should be able to or go through and clean them up and audit them to
     make sure they are correct, maybe as a bg job, skill, runnable audit etc.
     things like that. expand on this to a full feature and improvement, Im
     just spurting out words but I know there is so much more I havent
     covered." Placed: CHAT_PLAN "Placed from INBOX, 2026-10-11 (the owner:
     Atlas as the app's assistant)", decisions 65 to 69; the row actions to
     grammar57 (DESIGN.md "Row actions").

1298. **The owner, 2026-10-12, verbatim.** "Make the exceptions for the
     complexity but mark them to be fixed start of next pr". The 17 `composer_digest.py` rows are split and deleted
     (composer-1018b, the composer tests as the net). cx1298-1018 split 13 more under 15 with no
     behaviour change (`_stream_lines` 105, `_plain_events` 81, `recognise.py` span 60, resolve 44,
     `_date_cands` 45, `_time_cands` 22, `parse_reminder_text` 27, `factgraph._note_facts` 105,
     `routes_tasks.collect` 74, `engine.search` 69, `composer._follow_one` 66 and `_compose` 77,
     `lexical_filing.decide` 59; list in `archive/agent-remaining/cx1298-1018.md`); cx1298b-1018 split the
     five largest (`run_agent` 78, `_retrieve` 60, `_run_one_step` 53, `_prepare` 52,
     `restore_board` 49; `archive/agent-remaining/cx1298b-1018.md`). Left, largest first:
     `routes_files.analyse_attachment` 47, `inbox.merge_candidates` 46 and the rest of
     `python scripts/complexity.py` (223 over 15): split each toward its seed, lower the row in
     `tests/complexity_seed.json`, start of the next PR.

904. **The owner, 2026-10-17, verbatim** (a OneNote bug list pasted into a Word document, 86 items, screenshots described in `archive/agent-remaining/bugs-1017.md`; the pasted model-thinking transcript under B42 is elided). Triage and per-bug status: `docs/roadmap/archive/agent-remaining/bugs-1017.md`.

     B01. A first install setup popup showed as I was looking through the app but I accidentally clicked off it and idk what it was, there should be some way to access it, like a get started dropdown checklist to complete and maybe they can go in the notifications as well??
     B02. The composer needs more understanding, it still has a lot of flaws
     B03. Use composer to refine magic add on reminders like with bad sentence grammar and spelling mistakes and intent etc
     B04. Autocorrect on reminders and other app surfaces with harper, maybe other libraries and the composer, but also subtly highlight or colour the change for the user to notice in case it is wrong, then the user can hover over it and confirm it, edit it, or rewind the change.
     B05. I think the connect a model buttons in the no ai available popups should have a mini dropdown arrow on the side of the button so the user can click it as the connect a model button, or they can click the dropdown menu and press a shortcut button for hiding the popups instead of having to go into settings to manually find and toggle it.
     B06. When adding tags in the edit notes form, the tag textbox just keeps getting shorter and shortyer until it eventually goes to a new line, I feel like it should just permanently be on the line below with the tags being placed above
     B07. Should this have an '?'?? I want the composer to have more variation, could it be more dynamic and actually come up with responses like an ai and not just preprepared responses?? idk
     B08. This is alright but I feel like it should have acknowledged that it could be a test note?? Don't just account for this exact example, the composer needs to respond well to anything like this or similar scenarios. Like what if the user just button mashes or does a random string of keyboard charracters?? The composer needs to be like apple's siri with the same utility and usefullness and decent responses but better
     B09. It autocorrected my spelling, and it underlined it blue which is good, but when I clicked the word that was underlinedd, it instantly reverted, it should probablu show a little undo icon popup button near the word for confirming or reverting if the word is clicked on instead.
     B10. Also the composer is "Atlas's Assistant" and the ai models are Atlas themselves, it shouldn stay composer. Also it should probably tell the user that it is the assistant and if they want to talk to atlas, they should connect a model. And it should also give a composed general rundown of capabilities. This should be composed and not a set response, with variations, longer or shorter based on response style and user request etc. if the user asks about specific features or more yk??
     B11. The guide should alo consider that some queries may not be related to the current page the user is on and needs to bnetter detect intent
     B12. Why does the quick access look so small on the full view??
     B13. Unchecking a quick access option in the edit quick access panel navigates me to the unchecked option and then if I want to uncheck multiple I have to keep scrolling up.
     B14. Each settings page should have an expand and collapse all sections button at the top
     B15. I think we should market the application as "Tessellate Notes" but it is Tessellate for short…
     B16. The properties panel popups like with the date select arent the custom style like sued in the reminders tab
     B17. When making ned documents, I shouldn’t have to enter a title, it should fill it with "Untitled Document #[number}" and then have it preselected and highlighted for the user to replace it. That way if the user cant be bothered or cant think of a name they don’t have to. Also there should be an option in the editor to have the composer and ai if it is available suggest and rename the document. This should be the same for boards and maps as well.
     B18. On the document editor, I want a library of prefileld templates and curated text sections and stuff like the code snippets but for general documents as well
     B19. Also there needs to be more debugging and running tools for the other offered document types and languages, and also there needs to be code snippets and prewritten code examples and skeletons for all document types and code languages. And I want to be able to have it like it is now  where I select somehwere in the document and click the snippet and it pastes there, but also I can drag the snippet from the library and paste it whwere I drag it to and there'll be a ghose cursor under my dragging cursor where it will place and if I drag my mouse to the bottom or top of the document then it wills begin to scroll up or down if the document is long and scrollable.
     B20. On lined documents I want there to be a togglable temporary manage or edit mode or smth where it allows me to rearrange content by line and or elements
     B21. I switched from a md document to a code document and then back to md but it still thought it was and treated it like a code document.
     B22. Also live view on the document editor for md files should be default not source.
     B23. Also the tables in the live view for document editor should have more management capability, like lines on the edges and rows and columns on the outside etc to select whole rows or columns, or to add new rows or columns or even dragging icons to drag and rearrange coumns and rows if they are selected yk?? I cant even highlight select the live view table or multiple rows, columns or cells, and Im not given a popup menu for tables when I righ click them. This needs expansion and probably the same for other elements and the whole luve view for md as well.
     B24. Awkward popup in board
     B25. I want to be able to make wireframes and diagrams like erd, orm, uml, class and other diagrams on the boards so I want the proper elements available for them and templates
     B26. These dropdowns don’t show anything
     B27. I shouldn’t be able to uninstall the desktop view in the packaged windows app
     B28. Is it possible for tessellate to run on its own hosted and managed local server instead of on local host??
     B29. The whiteboard needs a lot of work, like the ungroup button on the popup tools doesn’t change, I cant widen objects on one axis when grouped, resizing or moving objects doesn’t update their xywh values in the format panel in real time, the popup controls are all over the place, it just needs soo much fixing, refining, redesigning and more.
     B30. Composer still needs a lot of refining and fixing. It is still very buggy, lacks a lot of understanding, and just straight up gives me the note back to me without any actual composing in the ask tab.
     B31. Add tessellate as a taxonomy option
     B32. It filed my newest note about uni assignments in the about tessellate category?? That's wrong and now I need to go and manually change it and probably make a uni or studies or smth category idk
     B33. Can the comoposer do these ai actions well and just as good?? And they arent ai actions If the comoser does them when the ai isnt available
     B34. More workflows and actions??
     B35. Companion doesn’t scroll with what it is perched on if the thing it is perched on is scrollable sometimes on the dashboard.
     B36. On draw.io I can pan by holding down my right mouse button and dragging, scrolling on the mouse is zoom.
     B37. Pressing down the scroll wheel and dragging sometimes glitches a little initially when starting to drag.
     B38. Attaching a file or thing to a mind map node makes a node that I cant edit or even go to the thing attached.
     B39. Rebuild or vendor jupyter notebook in tessellate document editor??
     B40. The ai should be aware of the user's current time in its responses through ai harness context.
     B41. No numbers on matching records while the ai is thinking
     B42. I used plan mode and the model didn’t have access to the make_plan tool
     B43. Thinking
     B44. The user wants me to plan a development of an app that acts as a "backpack on screen" - like Microsoft Sticky Notes, but where the user can store things (copy and paste regularly), then press one click "copy" on stored content to easily copy it.
     B45. They say "Plan this before you do any of it. Call make_plan with the goal and the steps, then carry the plan out."
     B46. […elided: the pasted model-thinking transcript, 82 paragraphs; its point: plan mode was on, the task said "Call make_plan", and the model's tool list had no make_plan, so it spent its turns reasoning about the missing tool and created no plan…]
     B47. Poor agent harness design and needs a lot of improvement.
     B48. Use composer to custom name tool calls?? The way tools are offered and other parts of the agentic harness need to be refined and improved.
     B49. The agent failed
     B50. I think the splash needs a bit of refining in how it l;oosk and works visually, and I can't minimise it (if that is possible)
     B51. I think the user's should have a button or way to access the project's github from the settings pages.
     B52. Easier way to set up docker and mcp server and get a link or smth I can use to connect claude or another ai to it if I wish. Can we give the mcp server the ability to restrict access to certain notes or things?? Like a custom settings or token that the user can use to give other ai's access through the mcp server but one that the user can control that the ai's have access to in their notebook through that token or url etc.
     B53. Cant set up mcp server in settings??
     B54. Is that side selection line on the right wrong??
     B55. Idk how to use the web clipper, it is unintuitive to use and hidden in settings, can you redesign the ui and ux of how it can be used and accessed?? Also the button in the dropdown for starting searxng in the web sidebar in the chat tab is gone.
     B56. When settings are on auto, I cant tell what it autoed to…
     B57. If I change the app's appearance colour and then try to change back to default, it changes to indigo instead…
     B58. I want the hover time to preview themes to be slightly longer or add like a small eye icon button in the corner to preview. Also across the app, there are quite a few instances where clicking an icon button to toggle smth doesn’t change the icon's look so it is hard to tell if it worked or not.
     B59. The app seemingly redownloaded the embedding model (I already had It but idk), except it still says it is connected to the internet which it isnt really right?? Idk
     B60. This dropdown combobox and the text next to it arent aligned properly
     B61. For the dictation model size there is no idication for which ones are installed, does the app check which modesl are stored even if they arent offered?? Also gemma 2 embeddings doesn’t need the lisence if you use the unsloth version, unsloth versions I find are a lot better than the main versions. Also if I click a different dictation model size, does it download immediately?? What if I change my mind?? Can I delete or uninstall models like for dictation and embedding etc that I don’t want??
     B62. The profile avatar in the enlarged popup from double clicking the profile picture doesn’t have any life to it.
     B63. When I change the theme or colour in settings, the animated app logo in the dashboard hero doesn’t update to the new colour until I reload or switch tabs and go back
     B64. The quick access sometimes loses it's full form and then goes really small and short.
     B65. Stop th emodel options should probs be disabled when no ai model is running
     B66. I didn’t even have the app running the whole day until less than 26 minutes ago
     B67. The top of the suggested models section should show the detected hardware of the user and allow the user to adjust or edit it if it is incorrect. Also I feel like the "fits" or "tight" suggestions etc should take into account the user's current memory and stuff if possible and what and how many ai models they already have installed.
     B68. Gemma4 26b is a4b
     B69. Can the composer run skills and do them well?? The composer needs a lot of work and upgrading and making better.
     B70. Why does this node wanna be all  the way down there?? The graph force structuring is still a bit messy and uncool looking
     B71. This image is me separating them out as it was soo messy and stuck together before I couldn’t read it.
     B72. Have the timeline calendar on the timelone act and be more usable as a calendar, I wanna be able to double click on a date and be able to add an event and set a reminder and stuff. Also on the timeline I wanna be able to scroll above today's date to see future dates and also I want the app to be able to recognise future date and time mentions and suggest to use magic add to add it to the timeline, calendar and as a reminder
     B73. Cant select on separate attachment nodes in the graph??
     B74. Could there be a way to print out or render a document or attachment in the whiteboard?? Like a pdf or document viewer object that the user can resize and move around, or even print the documents as separate pages like images that the user can move around, like dragging a document on onenote and having the option to print it out or place as an attachment
     B75. The text size in tooltip dropdowns across the app are always different and arent consistent (I think)
     B76. Should the drafting rotating animation and text be at the top of the ai side not the bottom of the user input side in the writing room??
     B77. **Fixed 4261fca** (the late answer's row is "Waiting for a late filing answer" and ends on every way out; finished runs show "Finished in 2 ms at 12:03 AM"). The agent run still says the note is filing but it is finished. Though there needs to be some more metrics like how long it took to file and similar across the app.
     B78. 9:57:12 pm INFO:    tessellate.embeddings: retrieval matrix warm with 46 vector(s)
          10:02:29 pm ERROR:   browser: [HTTP 422] PUT /graph/pin/document:2: Check the entry id and try again.
          10:04:57 pm INFO:    tessellate.jobruns: [run-7] Drafting started
          10:05:27 pm INFO:    tessellate.jobruns: [run-7] Thinking.
          10:07:01 pm INFO:    tessellate.jobruns: [run-7] Writing the answer.
          10:07:03 pm INFO:    tessellate.jobruns: [run-7] Done: 1 word.
          10:07:03 pm INFO:    tessellate.jobruns: [run-7] Drafting finished
          10:08:18 pm INFO:    tessellate.jobruns: [run-8] Filing a note started
          10:08:30 pm INFO:    tessellate.janitor: janitor: the model said 95% for 'Thoughts & Ideas'; shown as 78%
     B79. The writing room translated note I filed got filed as a draft, is that intentional??
     B80. Tag with atlas didn’t work right, it didn’t suggest tags, it doesn’t have a field for me to add more tags, it didn’t suggest alternate categories to make or move to if they  were viable, and all it gave me were suggested links…
     B81. Can you add the japanese emoticons library to the available emojis library??
     B82. Some emojis don’t appear in the search when the user tries to look for them and uses the wrong name like🙏 this is called folded hands but It should be both high five and pray orsmth yk??
     B83. The composer written weekly digest sentences count as a clickable button in the weekly digest
     B84. Do the patterns ever change?? What's the meaning or use of them?? Can I view them or smth?? {"
          Patterns: university, 4 times since 16 July"}
     B85. Composer's wording and grammar, especially around dates is a bit off and hard to read. And other things could be improved as well
     B86. The compsoer guide didn’t answer my question :(

## Placed (last 20, newest first)

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
- 2026-10-11: 867 (iPhone; LAN on a public network, automatic with overrides) placed as SESSION_BRIEFS Brief 102 (lansafe running); 868 (a time on every chat message and session) as Brief 103 (chattime running); 869 (typos read in context, not as slang) as Brief 104; 870 (composer answers with real openings, joining clauses and a close that adds something) into the atlas agent's running brief (CHAT_PLAN decision 70). Verbatims in SESSION_BRIEFS.
- 2026-10-11: the reqaudit pass (153 asks, 41 unplaced found-not-fixed rows) placed as SESSION_BRIEFS Brief 101; 845 ("can you redesign or change the design of this \"clear this list\" button??") and 846 ("there's an excessive gap on the right for the x close buttons on the nav history, can you integrate them together??") with ownerfix2; 848 ("on these screenshots from the search suggestions agent, these button text clashes") and 849 ("should search suggestion dropdown panels be the width of the search bar with the minimum being what the panel default is??", yes) with search86.

- 2026-10-11: 862 (a full functionality and experience scan) placed as SESSION_BRIEFS Brief 99; 864 and 865 (the graph appearing and updating smoothly, eased hover, a better node, the glow kept) with 802 as Brief 100; 863 (Peek slightly too see-through) fixed in the typos90 merge commit (the body 22% to 32%, the ground 8% to 14%).

- 2026-10-11: 847 (notification actions beside the X), 851 (Select checkboxes above the text), 852 (Library subtab flicker), 853 (OCR search highlight), 854 (Filing style head), 856 (hover ground radius) placed as SESSION_BRIEFS Brief 93; 850 and 857 (autocorrect everywhere, find by meaning) as Brief 94; 858 (themes) as Brief 95; 859 (the recording row) as Brief 96; 860 (the composer and the chart maker) as Brief 97; 848 and 849 (Recent changes buttons, suggestion width) sent to the search86 agent; 855 (Welcome and tours wall) was built by grammar57 (Help tour rows); 861 (goals and lists, recognised anywhere) as Brief 98.

- 2026-10-11: 838 to 842 (constellation on a theme change, the quick sketch panel and graph jitter, Agent with no model, the chat dock's round settings button, the timeline's year row) placed as SESSION_BRIEFS Brief 91; 843 (the whole-app pass, first run and the tour, element libraries, themes) as Brief 92.

- 2026-10-11: 836 (Add tags with suggestions on lightly tagged notes; Don't suggest tags) and 837 (the owner's typos as composer fixtures, standing) placed as SESSION_BRIEFS Briefs 89 and 90.

- 2026-10-11: 835 (props hard to see on Atlas, varied throws, natural motion, more variants) placed as SESSION_BRIEFS Brief 88.

- 2026-10-11: 832 (search suggestions, clearing history, undo in Settings), 833 (voice, dictation, vendoring, small features) and 834 (the splash) placed as SESSION_BRIEFS Briefs 86, 87 and 85.

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

- 2026-10-10: 752 placed in SESSION_BRIEFS Brief 34 (second part) and OPEN.md Atlas rows.

- 2026-10-10: 751 placed as SESSION_BRIEFS Brief 75.

- 2026-10-10: 750 placed in WORLD_CLASS_PLAN 28 and SESSION_BRIEFS Briefs 72 to 74.

- 2026-10-10: 748 placed in DOCUMENTS_PLAN 23, SESSION_BRIEFS Briefs 69 to
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
  agent-remaining/OPEN.md, "Atlas, placed from INBOX 2026-10-05"; the Atlas
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
