# Session briefs: the week's work, written so a smaller model cannot lose the thread

**Status: written by direct instruction as the execution companion to
[WORLD_CLASS_PLAN.md](WORLD_CLASS_PLAN.md) §11.** Each brief below is
complete on its own: the goal, what "done" means, the decisions already
made (do not re-decide them), the exact files and functions, the tests to
write first, the steps in order with the commands, the traps, and what to
report. A session takes ONE brief, reads §0, reads the brief, and starts.
Nothing here needs a design judgement; where one was needed it is written
down, with the reason, so it does not get remade worse under time
pressure.

Back to [../ROADMAP.md](../ROADMAP.md).

---

## 0. The operating protocol (read every session, it is short)

1. **Start.** `git fetch origin claude/epic-ramanujan-8xocc0 && git checkout
   claude/epic-ramanujan-8xocc0 && git pull` (or the branch you were given).
   Read `CLAUDE.md`, then `HANDOVER.md`'s first 100 lines, then this file's
   §0 and your brief. Nothing else before the first commit.
2. **Check the running app before building.** Start it
   (`bash scratchpad/ui-sweeps/serve.sh 8781 /tmp/mm-<brief>`), drive it with
   Playwright (`scratchpad/ui-sweeps/lib.js`, `boot({viewport})`, password
   `testpassword123`, `THEME=dark` for dark; `waitUntil: "domcontentloaded"`
   plus `waitForTimeout`, never `networkidle`). Grep for the feature. If it
   exists, your job is "make it meet the brief", not "rebuild it".
3. **Tests first.** Every brief names its tests. Write them, watch them fail
   for the right reason, then build. A test that passes before you build
   is a test of nothing.
4. **One step, one commit.** Commit after every numbered step with the
   trailer lines the repo requires (see any recent commit). The container
   can restart; uncommitted work is gone.
5. **Measure, do not look.** A claim about the UI needs a number from
   `page.evaluate` (`getComputedStyle`, `getBoundingClientRect`,
   `scrollHeight` vs `clientHeight`) or from `scratchpad/pngpixel.py`. A
   screenshot is for you, not for the report.
6. **Gates before push.** `.venv/bin/ruff check .`, `node --check` on every
   JS file touched, the brief's named tests, then the lints:
   `python -m pytest -q tests/test_style_scale.py tests/test_ui_signatures.py
   tests/test_css_braces.py tests/test_frontend_ids.py
   tests/test_frontend_handlers.py tests/test_dock_grammar.py
   tests/test_docs_layout.py tests/test_asset_cache_busting.py`, then
   `scratchpad/ui-sweeps/errors.js` (0 console errors at 1440, 1024, 390).
   Restart the server after any Python change.
7. **Scope.** The brief is the scope. Something adjacent that is broken
   goes in your report's "found, not fixed" list with the file and line,
   unless it blocks the gate.
8. **Copy.** Sentence case. No em-dashes anywhere (a lint will fail you).
   No "Oops", no exclamation marks. One line of description per section;
   longer help goes behind a `data-help-for` '?' button.
9. **When blocked** (a tool you cannot install, a test that cannot pass on
   the sandbox), do every step that does not depend on it, say exactly
   what blocked you and how you verified that it did, and stop. Never
   skip, disable or weaken a test to get green.
10. **Report** in five lines: status, commits, numbers measured
    (before/after), what could not be verified and why, found-not-fixed.
    Then add the same to `HANDOVER.md` under a dated heading, at the top.

The four failure shapes reviewers look for first (from `CLAUDE.md`), so
you can check your own diff for them: a working thing rewritten into a
riskier thing; a feature that never ran once (grep the call site of
anything new); a guard removed while the shape around it was kept; a
policy silently refusing the work (inline `style=` is rejected by the CSP;
use `el.style.x =` or a class).

---

### Brief 1: built; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (SESSION_BRIEFS Briefs 1 to 33)")

### Brief 2: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 3: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 4: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 5: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 6: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 7: built; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (SESSION_BRIEFS Briefs 1 to 33)")

### Brief 8: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 9: built; moved to HISTORY.md ("Brief 9, the rest of B2", with the 2026-10-17 folder import)

### Brief 10: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 11: built; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (SESSION_BRIEFS Briefs 1 to 33)")

### Brief 12: built; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (SESSION_BRIEFS Briefs 1 to 33)")

### Brief 13: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 14: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 15: built; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (SESSION_BRIEFS Briefs 1 to 33)")

### The quarter's briefs: each item is a row in its plan; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

## What "quality" means for a smaller model here, in one paragraph

Quality is not cleverness; it is not skipping steps. Every brief above is
ordered so that the test exists before the code, the measurement exists
before the claim, and the commit exists before the next step. A session
that follows the order, keeps to the scope, and reports the numbers will
produce work indistinguishable from a larger model's. A session that
reads the goal, guesses the shape, and writes the code in one go will
produce the four failure shapes, every time, whatever the model.

### Brief 16: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 17: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 18: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 19: built; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (SESSION_BRIEFS Briefs 1 to 33)")

### Brief 20: built; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (SESSION_BRIEFS Briefs 1 to 33)")

### Brief 21: built; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (SESSION_BRIEFS Briefs 1 to 33)")

### Brief 22: built; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (SESSION_BRIEFS Briefs 1 to 33)")

### Brief 23: built; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (SESSION_BRIEFS Briefs 1 to 33)")

### Brief 24: built; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (SESSION_BRIEFS Briefs 1 to 33)")

## Briefs 25 to 31: 25, 26 and 28 to 31 built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 27 (Opus): UI Phase 11, the phone

`docs/roadmap/UI_MODERNISATION_PLAN.md` Phase 11. The decisions are made
there. What this session did is the floor, not the phase: 320 to 1024 has no
sideways scroll, every touch target on 16 surfaces is 44px, the chat dock is
20% of the window rather than 38%, and `errors.js` reports 0 findings at 390.
What Phase 11 asks for and nobody has built: the five-item bottom tab bar that
recedes to icons on scroll down and returns on scroll up, More as a sheet, and
every panel becoming a sheet rather than a column. That is the brief.

### Brief 33: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 32: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

## Brief 34 (built 2026-10-12): characters, the faces, the companion and Atlas

Built; the brief moved whole to HISTORY "Moved from the plans, 2026-10-12 (Brief 34)". What the companion still lacks (the idle cost, step 5) is in agent-remaining/OPEN.md.

## Briefs 35 to 42: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 34 continues (Opus, high): Atlas and the companion
INBOX 742 and 743 and the owner's list ("atlas's arm movements on both
versions need a lot better animating as they are basically permanently in a
downward arc except for when hanging"; "experiment with more tail behaviour
and movement as well, and give the rings, as well as nebular flow and lower
body subtle animations that are all cheap"; "the companion doesn't really have
any variation in how it moves around at various distances"; "more mouse
interaction with the companion like rubbing its head, flipping it upside
down"; "the behaviour of the companion is not often reflected in the enlarged
view"). Numbers: mood changes per session before and after; layouts and
paints per second at rest (companionperf.js); the arm's angle range over a
walk cycle.

Second part (INBOX 752, the owner: "better npc behaviour at the level of real life ... so incredibly smoothe between everything and every event"): one behaviour model for the companion and every avatar, a state machine whose every transition blends (no pose snaps: each joint eases over 120 to 400 ms through the same curve table), idle variation drawn from a weighted pool that never repeats within five picks, reactions to every app event (save, error, reminder, the model thinking, a long task, the lock screen) with a reaction budget per minute, a gaze and lean toward what the person is doing, and the enlarged view driven by the same state. Numbers: transitions per minute that snap (bar 0, measured by sampling joint angles at 60 Hz in `companionperf.js`), distinct idle motions per ten minutes (bar 12), reaction latency from event to first frame (bar under 100 ms), long tasks per second at rest (unchanged from the first part).

### Brief 43: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")
### Brief 43 (Opus, high; Sonnet medium for the fixes it names): the expert audit
The owner, 2026-10-10: "I have only given you everything I have noticed but I
am not an expert ... fix, improve and extend and add everything I have missed
or havent thought of." The things a notebook of this kind must get right that
no report has asked for, each a measured probe with its command, fixed when
small, else a BACKLOG row with the number:
1. **Data safety**: a backup made, the data dir deleted, the backup restored,
   every note, board, map, document, reminder, tag and setting compared
   (`backupbundle.js`; a Python round-trip test over a 500-note fixture);
   every export (markdown, HTML, docx, PDF, JSON) re-imported and diffed;
   the alembic chain from 0.3.0's schema to head on a copied database.
2. **Old hardware**: boot to interactive under 2.5 s with the CPU throttled
   4x in Chromium, idle CPU under 1 percent (`idlecpu.js`), memory under 300
   MB with 5,000 notes seeded (`seed-timeline-bulk.py`), every list paged,
   the graph worker's frame under 16 ms at 2,000 nodes, no layout thrash on
   typing (`autogrowfast.js`), the service worker's cache honouring the
   version stamps.
3. **Offline and privacy**: a run with the network blocked (Playwright
   `route` abort) makes zero requests to anything but localhost and shows no
   broken surface; every outbound call (model pulls, web search, updates)
   behind an explicit setting with its own line in Settings, Network.
4. **Keyboard and screen reader**: every surface completed by keyboard alone
   (`keyboard.js`, `dockeyboard.js`, `keyreach`), axe clean (`axe.js`), names
   on every control (`a11yname.js`), focus never lost after a dialog closes.
5. **Error and empty states**: every API error path renders a designed
   notice with a way out (WORLD_CLASS_PLAN 21): kill the server mid-session
   and count the surfaces that fail silently; the empty state of every tab
   and widget measured against the recipe.
6. **Search quality**: a 60-query relevance set over the showcase notebook
   (lexical, semantic, hybrid) with precision at 5 recorded; typos and
   synonyms from the noisy set included.
7. **Security**: CodeQL clean, the CSP without unsafe-inline, auth on every
   write route (a test that walks the router), rate limits on the lock
   screen, the LAN mode's cert (Brief 40's findings), uploads type-checked.
8. **Upgrade path**: the app updated from the previous tag with data in
   place; the release notes rendered; the launcher's rollback.
9. **Tests**: the suite's slowest 20 tests and any flaky one (three runs of
   the frontend lints), the xfail markers still honest.
Report the numbers per item; fixes under one hour land in the brief; the
rest become BACKLOG rows "Expert audit, 2026-10-10" ranked by user impact.

### Brief 44: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)"); part 2 is WHITEBOARD_PLAN's expansion row 5 and `archive/agent-remaining/drawio-1010.md`

### Brief 45 part 2 (Opus, high): structure and complexity, acted on

Part 1 (the census, WORLD_CLASS_PLAN 24) is built; the dead defs are done (HISTORY, Brief 45 dead defs). Left (`archive/agent-remaining/census-1010.md`): split `whiteboard.js` (21,567 lines; `initWhiteboard` 3,730 lines) and `documents.js` along their seams with no behaviour change (the lints and `wbregress.sh` prove it); fold the 133 duplicated blocks into recipes; judge the structural decisions as decision rows with their numbers.
Run it when no agent holds the two files: on 2026-10-11 the wbs, docs and chatmind worktrees had uncommitted edits in them, and a split under live edits turns each of their merges into a hand rebase. 96 test files read `whiteboard.js` by name and 86 `documents.js`; the split moves their assertions to the new file in the same commit.

## Briefs 46 to 55: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

## Briefs 56 to 59 (2026-10-10, Fable): the design review

From UI_MODERNISATION_PLAN Phase 13 (the principles table, the surface
table, decisions 9 to 22, the phases). Brief 56 first and alone.

### Brief 56: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 57: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 58 (Opus, high): the stylesheet's structure (13b)
`08-consistency.css` and `10-responsive.css` dissolved into the component
files; the 236 unused selectors removed; decisions 18 and 19 with ratchets.

### Brief 59 (Opus, high): the surfaces (13c)
`index.html`, `status.js`, `capture-ask.js`, `notes-list.js`, `chat.js`,
`phone-shell.js`, the CSS they own; decisions 20 to 22; help moves with the
UI in the same commits.

## Briefs 60 to 63 (2026-10-10, Fable): the backend review

From WORLD_CLASS_PLAN 26 (the layer table, decisions 55 to 62, the phases)
and 27 (features and popups; its rows name Briefs 42, 47 to 55 and 59).

### Brief 60: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 61: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 62 (Opus, high): data out of code (26c)
`ai/question_noise.py`, `ai/composer_tables.py`, the help topics and the
taxonomy as JSON under `src/tessellate/data/`, lazy and cached;
`tests/test_import_time.py`; the composer eval unchanged.

### Brief 63 (Opus, high): the runners (26d)
`ai/agent.py` `run_agent` (complexity 78, line 2843 to the end) and
`ai/skill_runner.py` `_run_one_step` (line 882 to 1313) as state machines
(decision 61); `ai/tools/__init__.py` (4,986 lines) one file per family. The
embedder half is built (HISTORY "Brief 63 part 1, the embedder").

## Briefs 64 to 68: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

## Briefs 69 to 71: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

## Briefs 72 to 75: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

## Briefs 76 to 84 (from 72a and 72b): built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

## Brief 85 (built 2026-10-12): the launch splash, reimagined (INBOX 834)

Built; the brief moved whole to HISTORY "Moved from the plans, 2026-10-12 (Brief 85, the launch splash)".

### Brief 86: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (Brief 86)")

## Brief 87 step 2 (Opus): build the top two vendor candidates (INBOX 833)

Step 1 is built: ANALYSIS.md "Vendor candidates, 2026-10-11" (26 candidates by licence, size and cost; top five named). Left: build the top two, measured (TTS voice quality by a listening pair, dictation word error on 20 fixture clips), each as an optional package under the packages system so the suite never reaches for it. The editor, board and map polish half belongs to WHITEBOARD_PLAN E5 (canvasdepth3).

## Brief 88 (Opus): Atlas and the companions, alive (INBOX 835)

The owner 2026-10-11, verbatim (screenshots: a faint prop glyph on Atlas; Atlas with the orbit ring): "what is this on the atlas companion?? sometimes when icons appear on atlas it is hard to see them or make them out. and every time I try throwing the companion across the screen, it just bounces off a panel and back to the top, I want it to do that, but vary how much it does that. like I want more life, biological motion, natural motion, movement, transitions, actions and more from the companions and atlas. also more atlas variations for each gesture, movement, position, emotion and more."
Decisions: (a) a prop or icon on Atlas (`atlasPropsFrame`, atlas-life.js; the props in atlas.js) is drawn at 3:1 against Atlas's body with a dark keyline, at least 14 px, and names itself in the companion's tooltip; measured with `contrast.js` on each prop. (b) A throw keeps its bounce but varies: restitution and friction drawn per throw from a range, spin from the release velocity, a squash on impact scaled by speed, a slide or a tumble on a shallow hit, a settle with a small overshoot; never the same path twice for the same fling (`avatars.js` near 5587 and 6008). (c) Biological motion: breathing, weight shift, follow-through on hair and tail (secondary motion lagging the body), ease curves from DESIGN's motion tokens, idle variety on a schedule with no repeat in a row. (d) Three or more variants per gesture, emotion, movement and pose, chosen without repeating the last. Reduced motion keeps the crossfades. Long tasks at rest held to the census numbers (CHAT_PLAN "Placed from Brief 60").

## Brief 89 (Sonnet): Add tags on lightly tagged notes (INBOX 836)

Built: HISTORY.md, "Moved from the plans, 2026-10-11 (Brief 89)".

## Brief 90 (Sonnet, standing): the owner's own typos as composer fixtures (INBOX 837)

The owner 2026-10-11, verbatim: "also make sure that for all future conversations, all my spelling mistakes and grammar issues in all these and future prompts in these sessions are checked against the composer to see if it can properly understand them, if not, add the capability and understanding  with response variations."
Decisions: (a) `tests/fixtures/owner_typos.json` holds the owner's real misspellings and run-ons from their prompts, each with the reading it should get ("hwo do I" how do I, "redeisgn", "knoe", "ro", "wierd", "ahve", "cna", "suer", "doesn follow", "thes ebuttons", "a nd", "proffesionalising", "westen australia"); (b) `question_noise.repair` and the composer's routing are tested against every entry, and a miss is fixed in the engine, never by special-casing the string; (c) each session appends the owner's new typos (standing; HANDOVER note); (d) an answer to a repaired question varies its acknowledgement ("Reading that as ..."), never the same words twice in a row.

## Brief 91 (Sonnet, ownerfix2): the owner's small UI reports, 2026-10-11 afternoon (INBOX 838 to 842)

Built: HISTORY.md, "Moved from the plans, 2026-10-11 (Brief 91)".

## Brief 92 (Opus, after the queue): the whole-app pass the owner asked for (INBOX 843)

Verbatim: "I need you to clean up more ui around the app, make it consistent, make it all clean, make it all modern, professional, devibecoded, RESPONSIVE, not squashed, dynamic, a good experience, satisfying to use and look at, understandable adn learnable, accessible, fully wired up (no featrues not working or broken), and also just really clean and polished." and "I need you to keep hacking away at the features and utility and things in key features, UI/UX, small things that make the app feel truly polished, proper information architecture, no ui clashes, a clean experience after first downloading the app, making sure the guided tour fully works and doesnt get cancelled after first install and the welcome tour. the quality of the agentic harness, maximise the composer, ti should have sooo much utility, responses should be clean and human readable. everything should be done for the user, fully managable and togglable, fully transparent and readable, instinctive to use, fully guided and more. can we upgrade some of the themes?? can we vendor any repositories for ui elements and design or smth like with the glass aesthetic and other ui elements?? use free element libraries and compare them to the elements in this app to make sure there are no bugs or issues??"
Decisions: (a) first run is tested end to end: a fresh data dir, the welcome, the guided tour to its last step with no cancel (an E2E spec that fails if the tour closes early), at 1440 and 390; (b) an element-by-element comparison against free reference libraries (Radix UI behaviour, shadcn/ui, Open Props, the WAI-ARIA APG patterns) for menu, select, dialog, tabs, toggle, slider, tooltip, popover, toast: keyboard, focus, ARIA and states, each gap a fix with a test; nothing vendored unless ANALYSIS's licence rule and the boot caps allow it; (c) themes: two existing themes upgraded and the glass look checked against Apple's Liquid Glass guidance already in UI_MODERNISATION Phase 10; (d) the composer and harness work stays in CHAT_PLAN rows B1 to B40 (Atlas agent); (e) the rest runs through Briefs 57 to 59 and the uisweep findings, measured.

State (triage 2026-10-11): (c) went into Brief 95 (themes95, merged); (d) stays in CHAT_PLAN; (e) Brief 57 is built, 58 and 59 are open above. Left here: (a) the first-run tour E2E and (b) the element comparison.

### Brief 93: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 94: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

## Brief 95 (Opus): themes, dug deep (INBOX 858)

Verbatim: "can you really dig deep and create some truly good themes?? upgrade existing themes (keep the classic and quiet utilitarian the same. add more colour options. maybe even a custom picker, add more animated background options, make them varied from simple, to complex, heavy, and light, maybe even visually rate them?? make sure there is no high volumes of calculations, no glitches, everything is fast to run, no high complexity. polish mroe ui. maximise ux"
Decisions: Classic and Quiet utilitarian untouched (a pixel test pins them). Every other theme reviewed against contrast (0 low on the 44 surfaces, both modes) and given a real palette pass; new accents plus a custom accent picker (any colour, the app derives soft, surface, hover and text tones and refuses a pick below 4.5:1 with the nearest passing tone). Animated backgrounds: a set graded light to heavy, each labelled with a cost badge (Light, Medium, Heavy, measured: CPU ms per frame at 1440 and frames held at 60) and a preview; CSS or one canvas at reduced frame rate, paused when hidden or under reduced motion, never above 2 ms per frame on the reference machine; Brief 92 (c) folds in.

### Brief 96: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

## Brief 97 (Opus, after Atlas): the composer as the place to go, the graph maker (INBOX 860)

Verbatim: "does that vendored networkx repo/library help improve the knowledge graph and the visual graph itself?? can we generate more statisitcal graphs for statistics?? could we add a graph maker where the user can plug in values or have data and then manually make a graph, table or diagram, or have the ai plug in pasted data and then generate a diagram which is downloadable, customisable, and more?? I want the way the composer shows infoa dn retrieves info to be very stylised and visually readable. very professional. stuff like that. mass composer upgrades, for the chat, the ask tab, the help guide, and then everywhere else it is used for application utility functions. it needs to be insanely good and basically be the go to whenever the user needs help, needs to find something, do a quick search web read, access a specific object (the composer will return a hyperlinked card for it or smth), for asking things like timexones, measurement conversion, any and all maths, restructuring and properly formatting thing, code formatting, and more. like generateing files and templates, visualising data, ocrring file sand images, providing nav links, and mroe. I cant think of everything so expand on this and implement it. the ai should be able to do all fo this and do it even better."
Answer recorded: networkx is not in the app (the Gemini session vendored it; Brief 35 dropped it for 60 lines of metrics in `notebook_stats.py`, ANALYSIS); the visual graph's layout is d3 in `graph-worker.js`, which networkx would not change.
Decisions: (a) a chart maker: paste or type values (CSV, a table, a list), pick bar, line, area, pie, scatter, histogram or table, style it (the theme's palette, titles, axes, labels), export SVG, PNG and CSV, save to a note or a board; the composer builds the same chart from pasted data ("chart this"); drawn in SVG with no new dependency unless the boot caps and licence rule allow one. (b) Notebook statistics as charts (notes per week, by category, tags, links), on Stats. (c) The composer's answer shapes: object cards (a note, board, map, document, setting) as hyperlinked cards, tables, unit and zone answers as a result block, maths with its working, formatted code, nav links; the CHAT_PLAN B rows carry the parity across chat, Ask, the Guide and utility surfaces. (d) New utilities enumerated in the brief's first step (conversions, zones, maths, formatting, templates, file generation, OCR from the composer, a quick web read), each with fixtures and a no-model answer.

- INBOX 870, verbatim: "can you also add some longer sentence joiners and intros, things between sentences, at the start, and at the end of sentences tp composer responces?? one or two words between directly giveing me what I can see from the notes on the right on the ask tab feels like the response is completely useless and gives me nothing. idk it just still feels basic." Given to the atlas agent first (an answering opening, joining clauses, a close that adds a pattern, gap or next step, varied); what it leaves comes here.

## Brief 98 (Opus): goals and lists (INBOX 861)

Verbatim: "should we add a feature where the user can enter goals for both long term and short term?? paired with a todo list and list feature. all of this will be integrated with all the existing feature, the application, the composer, and the ai should also be able to recognise things like this written by the user anywhere and should be able to suggest things like add ing things mentioned in chats and notes etc to goals or lists."
Exists: reminders (dated, `routes_reminders.py`), checklists inside notes (the composer counts ticked items), the suggestions inbox; no goals, no standalone lists.
Decisions (recommendation taken, standing order 3): yes. (a) Goals: a title, short or long term (a horizon: this week, this month, this year, someday), an optional why, progress from linked items; (b) lists: named lists of items (a todo list is a list whose items tick), an item may carry a date (then it is also a reminder, one record, not two), a note link and a goal; (c) one Goals and lists surface in the sidebar, with a quiet count on Today; (d) recognition: a deterministic extractor over notes and chat turns ("I want to", "my goal is", "need to", "todo", "remember to", "- [ ]") proposes items into the suggestions inbox with the source quoted and one click to add or dismiss (and "don't suggest from this note"); the model, when on, only refines wording; (e) the composer reads and acts on them ("what are my goals this month", "add milk to shopping", "tick call mum"), with no-model answers and fixtures; agent tools for list and goal CRUD; (f) Help, the Guide's topics and the manual move with it. Tests first: model and routes, the extractor's table of 40 phrasings including the owner's typos, the composer fixtures.

### Brief 99: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

### Brief 100: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

## Brief 101 (Sonnet, three agents): the found-not-fixed ledger, placed (the owner: "make sure you cover all bugs and issues found and not fixed as well")

The reqaudit pass (2026-10-11) found 41 found-not-fixed rows with no plan row, brief or BACKLOG line. Each is placed here or in the brief that owns its surface.
- **101a, room:** built (room101, merged 2026-10-11; what is left in `archive/agent-remaining/room101-1011.md`).
- **101b, data correctness:** binned notes imported with an old `deleted_at` are purged by the startup sweep; a monthly repeat from the 31st sticks on the 28th; the reminder edit form cannot change an alert; load-more leaves a new range at 100 rows; a reminder's action token dies with the process (a restart ends open notifications' buttons); private notes and multi-space exports untested; Agent Undo-the-run then Ctrl+Z re-runs an applied inverse; Agent Stop only between steps.
- **101c, first run (the owner 2026-10-07):** optional packages in the installer show no progress and cannot be minimised or cancelled (install on first launch as a background task with Stop); an empty or partial `models--BAAI--bge-small-en-v1.5` is treated as present and fails `EmbeddingCacheBroken` (self-repair as a visible task, the rows say "Files missing" with Reinstall); the janitor warms an unchosen default chat model ("llama3.2 failed"; first launch chooses from installed models); the Python runtime reloads on every document opened (5.9 to 7.0 s cold).
- **Into owning briefs:** notes leaving the graph vanish (Brief 100); Atlas whole-body speed and `setAtlasMood` cost (Brief 88); `rowActions` for meetings, suggestions inbox, tag manager, the tool-confirm pair and the Connections Link button, sidebar Comments/Linked from rows, `smallButton` names by tooltip (Brief 92); the composer's quoting answers, "at least" past 24 notes, steps for the top 20 how-tos, other tabs' starters, "pin note 12", a trailing backslash in the user's bubble (atlas, Brief 97); chat and agent turns never announced, the Guide/drafting/review without narrated lines, a lint for `egress.purpose` (Brief 99's scan reports, then a Sonnet follow-up); skill budgets drawn and declared (Brief 97); the reset per Settings group and `settings-reset` in a help group (Brief 92); free lines drawing the shaft through hollow ends, Edit data placeholders, table column widths, hidden-layer eye (canvasdepth3); the map's More sheet at 390 and retidy cost at 200 topics (canvasdepth3); Week Monday-first only and words-written counting only new notes (Brief 92); Translate en to es only (Brief 97); live captions without a Quick access tile (voiceup V6); constellation yellow stars 2.1:1, the capture box's 2.4px first-click shift, the Notes rows/cards toggle 28x24 (Brief 93 follow-up); filing for journal notes with no tag word, turn-downs counting notes not offers (Brief 99); calendar touch drag and 1,000-note month, Last-year range; live sync between two windows; Windows and macOS reminder actions (Brief 92, measured on the owner's machine only); the code palette's shortcuts and snippet residues (Brief 92); meeting speaker names (voiceup).
- **For the owner:** which elements "these elements are ugly and not even the same height" (2026-10-11 03:38Z, one screenshot) means; whether the OCR "squashed text box" (INBOX 803 item 4) still happens; what "liks" and "mut" meant.

## Brief 102 (Opus, lansafe): LAN safe by default on any network (INBOX 867)

The owner uses an iPhone. Recommendation taken (standing order 3): everything automatic, each with a manual override in Settings, Other devices.
- **Allowed networks.** Turning the switch on remembers this network (gateway hardware address plus subnet, read locally, best effort; Windows also reads the network's Public/Private category). At launch on a network not on the list, other devices stay off and Settings and the bell say so, with "Allow on this network". Override: "Allow on any network" (off by default). Windows' Public category never opens without asking.
- **New-device approval.** The first sign-in from a device over the network is held until this computer allows it (a notice with Allow and Deny); allowed devices are remembered and listed with Remove. Override: "Ask before a new device signs in" (on by default).
- **Clients from private addresses only.** The LAN port refuses a client whose address is not private, shared or link-local (a forwarded port, a public-address network). Override: none.
- **The iPhone flow.** The lock screen, reached over the network, offers "Install the certificate" (the profile download) and the steps; Settings shows a QR code of the address if one fits the scripts budget, else the address large and copyable.
- Tests first; the real-socket harness is `tests/test_lan.py`. Not verifiable here: a real iPhone, Windows' category.

### Brief 103: built; moved to HISTORY.md ("Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)")

## Brief 104 (Opus, after atlas): typos read in context, not as slang (INBOX 869)

The composer's spelling repair picks a reading by probability: candidates (the word, edits of it, joins and splits) are scored by an edit likelihood (keyboard distance, transposition, doubled letters) times a context score (the notebook's own word pairs, then the lexicon's), and a slang or shortened reading wins only when the context supports it. The owner's typos (Brief 90 fixtures) are the gold set; the measure is the share read right before and after, with no regression on correctly spelt questions.
