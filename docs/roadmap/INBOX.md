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

725. **The owner, 2026-10-06, verbatim**: "can you like maximise the application
     responses and sentence concatenation and responses?? I want it soooo good it is
     almost like a chat bot. make them something the world hasnt seen before like
     stringing sentences together based off meaning, similarity etc. idk im just
     throing stuff out there. I want the app to be really impressive". The
     no-model composer (`ai/composer.py`, INBOX 688). Placed: Opus agent, as a
     CHAT_PLAN phase row.
     Owner: CHAT_PLAN Phase 5 and Phase 6, Brief 39 and Briefs 65 to 68 (the engine agent runs on 39); built so far in composer725-1006.md and composer-voice-1006.md (first line answers 25 of 25, joining phrases 27 to 44).

730. **The owner, 2026-10-06, verbatim**: "also would the composer be able to
     somewhat accurately put new notes into a category using meaning similarity,
     mathematical shenanigans, keyword, and more and like the embedding model as
     well?? the embedding model should still be accessible and usable without the
     ai right??" Answer: yes, filing without a model already runs (lexical
     filing, category centroids and nearest neighbours over the embedder, which
     needs no AI model); next is measuring its accuracy on a held-out set and
     letting the composer explain each filing in one line.
     Owner: Brief 39b (filing and the taxonomy), WORLD_CLASS_PLAN 23; the held-out accuracy measure and the one-line explanation of each filing are its rows.

735. **The owner, 2026-10-06, verbatim**: "also since p5.js is vendored, can it be a
     document option in the text editor?? also when on a code document, I get auto
     fill for redular sentences, not code specific autofill" "I was on js document".
     Two items for DOCUMENTS_PLAN: a p5.js sketch document kind (code beside a
     sandboxed live canvas, the vendored p5 only, no network); and on a code
     document (.js here) the prose autocomplete must switch off and code-aware
     completion (words from the file, the language's keywords, bracket pairs) take
     its place.
     Owner: DOCUMENTS_PLAN 23 and Brief 42 (the p5 kind, code completion on code documents); Briefs 69 to 71 for the IDE.

737. **The owner, 2026-10-06, verbatim**: "can the debugging run for other languages
     as well?? also error messages, syntax errors, code suggestions and more". Then:
     "are there any more repos we can vendor??" Today: JS runs (sandboxed), syntax
     checks cover js, ts and css (`DOC_CHECK_TREE`), completion covers js, ts, py,
     css and html. Vendored: codemirror, d3, emmet, harper, p5, phosphor, wordlist.
     Candidates, all to be checked for licence (AGPL-compatible inbound) and size,
     lazy-loaded, offline: Pyodide (Python in the browser, large), mermaid.js
     (already decided, BACKLOG steps 8 to 13), KaTeX (maths), a Lua or Ruby WASM
     runner, a linter per language (eslint-linter-browserify, ruff-wasm). For
     DOCUMENTS_PLAN: errors pinned to their line, syntax errors for py and html,
     a run for Python first.
     Owner: DOCUMENTS_PLAN 23 decisions D1 to D9, Briefs 69 to 71; the vendoring candidates are Brief 75.

741. **The owner, 2026-10-06, verbatim**: "will the composer get better at writing,
     sentence structure, more variations and natural language, betetr to understand,
     more biological. more social, more engaging, better at responding and answering
     questions correctly". Not covered by the three composer agents running
     (model context, composer acts, composer everywhere). Recommendation, taken: a
     fourth Opus track, "composer voice", once one finishes: question understanding
     (indirect and casual phrasings, synonyms, a clarifying question when
     ambiguous), more question kinds answered (why, how, how many, comparisons,
     yes or no as "your notes say"), a first-line-answers check, a larger tested
     phrasebook of joins and openers, turn-aware follow-ons, length fit to the
     question, the app voice; facts stay quoted. Measured on the 725 eval grown
     to about 100 questions with variety and readability scores.
     Then, verbatim: "rn the ask chat messages just say, ur note starting with this
     says this. also ur not starting with this says this, furthermore, ur note
     starting with this says this." Cause: `ai/composer.py` PHRASES (`says`,
     `also_says`, `says_a_end`): every sentence is introduced by its note's
     opening words plus "says:". First fix in the voice track: name a note by
     its title or topic once, then speak the content directly ("You planned
     Lisbon for May; the hotel is booked") with the citation as a marker.
     Owner: composer-voice-1006.md (merged: no "your note starting with ... says", casual phrasings, typos, 847 slang entries, voices) and CHAT_PLAN Phase 6, Brief 39 (the realiser). Open: speak the content directly with the citation as a marker (measured today: Ask now answers "Also, the hobbies I want to try: ..." with no "says"); the remaining eval numbers are in that file.

742. **The owner, 2026-10-07, verbatim**: "atlas doesnt seem to change emotions alot
     if at all?? maybe log that for next pr". Next PR: measure how often Atlas's
     mood changes in a session (the mood triggers in atlas-life.js and
     companion code) and widen what drives it (answers found, nothing found,
     reminders done, idle, time of day), each visible within a few seconds.
     Owner: Brief 34 (companion), the second part; the mood-change count per session is its first number.

743. **The owner, 2026-10-07, verbatim**: "and I want more mouse interaction with the
     companion like rubbing its head. flipping it upside down?? doing things or
     event triggers that get it to change emotion ro behavior. \"ro\" is an or
     misspell. also the behaviour of the companion is not often reflected in the
     enlarged view. better popup messages and more varied. more life and natural
     biological behaviour and transitions and actions and movement etc."
     With 742 (moods rarely change), one next-PR track: pointer gestures (rub
     the head by moving back and forth over it, drag and flip upside down, hold,
     poke, toss), app events as mood triggers, the enlarged view mirroring the
     corner companion's live state, the composer's companion remarks
     (`composer_voice.py`, built, not yet on screen) as its bubbles, and
     springy, interruptible transitions between poses. "ro" for "or" is in the
     typo table (question_noise.py).
     Then, verbatim, with Atlas in the onboarding welcome card and an oval
     frame: "atlas goes out of the border". The figure's tail, swirl and orbit
     spill past the oval's ring: either clip the figure to the frame
     (`overflow: clip` with the frame's radius, as the mini avatar now is) or
     scale it to fit inside with a margin; same for every framed Atlas.
     Then, verbatim: "the show companion notification button was poorly shown
     but I didnt screenshot it in time". Not seen yet: reproduce the notice
     that offers to show the companion (first run, after hiding it, or a
     notification with a Show companion action), measure its button against
     the toast-with-action recipe in DESIGN.md, and fix what is off.
     Owner: Brief 34 (companion), second part, and OPEN.md Atlas rows (INBOX 752): gestures, the enlarged view mirroring the corner, the framed Atlas clipped to its oval, the Show companion notice measured against the toast recipe.

771. **The owner, 2026-10-10, 16:02Z, verbatim.** "I am sleeping so continue
     autonomously. Impress me a lot. I want to fall off my chair lol with how
     good the changes, fixes, improvements, additions, and nire are when I
     wake up in the morning lol." Read: no cap on the night's work beyond the
     agent cap (four Opus, Sonnet extra); every open brief in SESSION_BRIEFS
     order; the PR stays green and the docs current at each merge. Owner:
     HANDOVER "Now" (the night's queue).

772. **Decision needed, found by the companion agent (Brief 34), 2026-10-10.**
     Under the system's reduce-motion hint Atlas keeps its calm CSS loops (an
     earlier decision, `08-consistency.css:5056`): 1,579 style recalcs a
     minute. Decision 7 says reduced motion keeps poses without loops.
     Recommendation, taken: decision 7 wins; the system hint and the app's
     own Reduce setting both stop every loop and keep the pose. Owner: Brief
     34 continues (companion2).

804. **The owner, 2026-10-11, verbatim.** "there are more backups than my max
     set number of 3, this console line's border clashes with the line above,
     also these buttons and ui in the documents editor need to be fixed in
     their design and height and stlying etc." (screenshots: four backups
     under "Keep this many backups 3"; the Python console's `>>>` input with a
     focus border meeting the rule above; the document assistant's
     suggestion buttons over an "Ask about this code..." field and a send
     button of another height). Backups fixed in b928a7d9c (every start
     prunes to the number). Owner: grammar57 (the console line and the
     assistant's field, send and suggestions, in the button grammar).

805. **The owner, 2026-10-11, verbatim.** "it is unclear which backup is the
     latest, and also the backups need more file info and details I feel. all
     information and processes across the app need to be 100% transparent. so
     all things that use the ai or composer and all background processes need
     to be logged and shown in bg processes wtc, along with their individual
     logs and process lines to show thier process live and when they are
     finished as well. whena ny process is running it needs to be clear to the
     suer." Owner: the transparency agent (next Opus slot): one process
     ledger every AI, composer and background run writes to, live lines per
     run in the background processes panel, a running indicator in the
     shell, and the backup rows (latest marked, date in words, what made it,
     size, checked).

807. **The owner, 2026-10-11, verbatim.** "it isnt really clear exactly what
     these were for" (screenshot: Where your data went, rows such as
     "huggingface.co (2600:...:443) The internet, Optional downloads,
     connected 4 times"). Owner: the transparency agent: each destination
     says what it fetched or sent (the model or file name, the search
     words) and why, the address behind a disclosure.

808. **The owner, 2026-10-11, verbatim** (a log): Agent mode calls
     `ask_user` with one option three times ("ask_user needs at least 2
     different options"), calls `search_notes` with no query on "NOTEBOOK
     STATS", searches `'what is there about a gaming mouse?\\'` with the
     backslash kept, "can you search the web?" finds 0 notes via none, and
     "Grammar check off for this session: the grammar worker did not start".
     Owner: noagent (the agent's calls and the query clean-up); the grammar
     worker to grammar57.

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

812. **The owner, 2026-10-11, verbatim.** "also the composer in the ask tab
     and structuring of sentences and outputs needs to be cleaned up a lot. it
     still looks messy. and the response feels, plain, boring, lifeless, and
     doesnt give me anything more. I may as well just read the notes I made on
     the right. the composer needs to be better but I dont know how and you
     keep saying youve improved it but i still cant see much. I feel like Im
     going in a loop 😞 also the first time I use the ask subtab search after
     loading up the app, the badges next to the sub headers on each column are
     visibly empty" (screenshots: Ask, "What have I saved about courses &
     study?": quoted fragments with a bar, a superscript and "[your note, 27
     July]" each, then "Grounded in" chips and "4 of 4 from your notes" that
     repeat the right column; the corner Atlas drawn over "You asked"; empty
     badges beside "Atlas" and "Matching records" while loading). Read: the
     answer quotes, it does not answer; three citation marks per line; the
     sources shown three times. Placed: CHAT_PLAN decision 70 (the answer is
     judged against written gold answers, not rule counts), first in the
     assistant brief; the empty badges and Atlas over the answer to ownerfix.

903. **The owner, 2026-10-11, verbatim.** "alright lets rename and
     retrademark to Tessellate update absolutely everything including all
     the documentation and the pages site. make sure to still note the
     former name though." Placed: the rebrand agent (agent/rebrand-1011):
     step 1 the brand (`scripts/rebrand.py`, re-run after every merge;
     `tests/test_brand_name.py`), step 2 the internal identifiers with
     fallbacks for existing installs, as its own last commit.

1297. **Owner review, from the ledger (tagsearch-1011).** Read
     `src/tessellate/ai/data/taxonomy/memorymap_everyday.json` (about 630 general
     words added to 23 pack topics; the pack file is untouched) and say keep,
     trim or drop. Recommendation: keep; no model it files 0.417 to 0.617 on the
     120 notes and 0.458 to 0.667 on 48 held-out ones (`tests/test_everyday_vocabulary.py`).
     Placed: WORLD_CLASS_PLAN 23 step 6.

1298. **The owner, 2026-10-12, verbatim.** "Make the exceptions for the
     complexity but mark them to be fixed start of next pr". First work of the
     next PR: split the 16 `composer_digest.py` rows seeded into
     `tests/complexity_seed.json` (`_single` 79, `_facts` 75, `_lines` 62,
     `answer` 57 and 12 more) to 15 or below, deleting each row, with the
     composer tests as the net. Also 18 seeded functions that grew this PR
     (`_stream_lines` 93 to 106, `_generate_diagram` 27 to 47, `mcp_server.handle_request`
     17 to 30 and 15 more; `python scripts/complexity.py` lists them): bring each
     back to its seed.

904. **The owner, 2026-10-17, verbatim** (a OneNote bug list pasted into a Word document, 86 items, screenshots described in `agent-remaining/bugs-1017.md`; the pasted model-thinking transcript under B42 is elided). Triage and per-bug status: `docs/roadmap/agent-remaining/bugs-1017.md`.

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
     B77. The agent run still says the note is filing but it is finished. Though there needs to be some more metrics like how long it took to file and similar across the app.
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
