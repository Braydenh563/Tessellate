> **Fix the class, not the case, the owner 2026-10-26 (standing, INBOX 1357):** "each time I show an issue for the composer, I think you are only fixing for that specific case scenario, I need you to take all my highlighted issues and then see if there are any ither similar or related issues stemming from that for all future prompts." Every reported bug, composer first: name its failure class, list the sibling cases (other phrasings, other surfaces, other kinds), test them, fix the class. Budget for this run: stop at 40% weekly.
>
> **Performance, the owner 2026-10-26 (standing):** "also make sure to keep optimising, make everything lighweight, insanely fast, not laggy, low complexity and mroe". Every brief carries it: measure frame time, long tasks and wakeups on the paths it touches, lazy-load new code, and report the numbers.
> **Haiku for grunt work, the owner 2026-10-19 (INBOX 1312, standing):** "maybe assign haiku agents to go the grunt work and catalog everything, haiku must be used a lot for grunt work and repo exploring so that I can maximise usage and progress. make the agents use haiku for those tasks as well." Every brief tells the agent to hand searches, cataloguing, log and test-output reading and repo exploring to Haiku subagents (Agent tool, model haiku), keeping its own turns for implementation and judgement.
>
> **Tier and routing, the owner 2026-10-17 (supersedes every older agent-cap, model and Fable line below):** tier `max`. "use haiku for all the labour, sonnet for implemenbtation." Rungs, caps and the Fable opt-in rule are in CLAUDE.md sections 2.4 and 8; the lines below are history. Set `pro` here when the plan changes.
>
> **Agent cap, the owner 2026-10-11 09:20Z (superseded 2026-10-17):** "I wanna hard push for the rest of the open items, can you run 2-3 more agents??" Cap now seven at once (five Opus, two Sonnet); Sonnet where quality holds.
>
> **The composer and the model, the owner 2026-10-11 (standing, CHAT_PLAN decision 75):** "just make sure that if the ai is active, the ai still does everythign properly and the composer doesnt completely replace it. it SHOULD completely replace it if the ai isnt available, otheriwse the composer is an assistant to the ai ... make sure that the ai doesnt skip corners or assume everything has been done just becaus ehte compoiser gave it something to try and assist yk?? I need ot to not negatively affect the ai. but if the ai isnt active, i need ot to be the best thing people have ever used ... the user should eb able to ask anything and go to, find, create, do anything with the composer. the composer is the ultimate siri for the app." So: with a model up, the model answers every surface and the composer only hands it gathered facts as context, never a finished answer the model may skip work on; with no model, the composer answers everything (ask, find, go to, create, do). Every composer brief carries this.

# HANDOVER

## Morning summary

Away run 2026-10-28, branch claude/sharp-thompson-45hngp, PR 211; stopped at about 56% weekly (line 62%) because each turn now carries a long context, so a fresh session is cheaper.

- Audit: five clean-eye audits (board, docs, backend, shell, agent) plus UX, ranked in `agent-remaining/audit-1028-ranked.md` (313 rows, 258 new). Agents' leftovers: board-1028, board2-1028, docux-1028, composer-1028.
- Built and pushed: D1 to D8, D14 to D16; K2, K3, K7 to K10, K12, K17; E1 to E12, E30, E31; S1, S4 to S10; B5 (part), B8, B9, B16, B21; U1 to U8, U10, U11; find panel; help and Guide text for all of it (standing order 13).
- E10 tasks as acts: add (reminder with `task`), complete by name (reminders and `- [ ]` lines), ask on ambiguity, Undo. Not built: cancel, snooze and bin a task by name; Guide help topic text for tasks.
- Fixed in passing: `test_no_import_cycles` was red on the base (commands.py lazy imports); CodeQL `_ASK` unused.
- CI: green on every head through c64b1af. gitleaks fails on the workflow's shallow checkout (needs fetch-depth 0; CI files are not edited by agents; commented on PR 211).
- Not reviewed independently (budget): the E10 merge and the docux merge. Run `reviewer` on them, and `blind-tester` on documents, before PR 211 merges.
- Owner question: INBOX 1424 (K1, password reset needs proof of this computer; recommended a six-digit code printed to the terminal).
- Next by rank: B3/B4 incremental board render, S2 graph layout off the main thread, S3 index.html boot weight, E42/E66/E70 agent safety, K4 to K6, K19, D11, E32, E33, B5 pen/lasso/marquee, U43.

## 0.6.01 bug-document pass (2026-10-22, branch claude/project-thread-ol5yuv)

- Done: tray start hardening (icon decoded up front, startup failure logged), whiteboard drag-select no longer highlights page text, Fill/Border colour popup keeps its place, skills menu "(edits)" tag. Not verified on a real Windows desktop.
- Open: the whole bug list is in `agent-remaining/OPEN.md`, "Left by the 0.6.01 bug-document pass". The tray icon may be in the taskbar overflow (^) on Windows 11.
- Custom domain: not built in; reverse proxy with TLS plus `TESSELLATE_ALLOWED_HOSTS` (Docker docs only).
- Version number and CI fixes are owned by the threads on claude/project-thread-iv24e6; expect conflicts on the version files.
- Usage stopped at 93% weekly (self-stop 85%).

## Earlier morning summary (away run 2026-10-18b, branch claude/magical-feynman-7bgj7j, PR 192, 0.6.0)

- Done: INBOX 1300 C01 to C44 (resolved to HISTORY) and 1301 D1 to D8; C30 lightbox redesign; UX audit 1 to 12; undo/redo race; palette lexical rows; phone hero height; splat reach; composer prose openers (composer6); backup rows show what made them and verified (805 part); framed Atlas kept inside (743 tail); 13 complexity splits, 241 to 228 over 15 (1298 part); CodeQL ReDoS fixed; dark contrast on whiteboard and map measured clean (uxfix4). Released as 0.6.0; PR title and description updated.
- CI: green on every pushed head through da548db; 29351d9 (complexity merge) pushed after the full suite (one stale string test fixed).
- Blocked on the owner: the merge of PR 192; pale palette branch ribbons under 3:1 (lifting palette colours per theme moves a pinned test, uxfix4-1018.md); PR 191 items below (B61, B58, B39, B20, B70).
- Usage: weekly 46% to about 51% (self-stop 55%); agents fixes1 to 9, design1 to 7, uxfix1 to 5, composer5 to 6, cx1298.
- Next: INBOX 1298 rest (agent.run_agent 78, search_manager._retrieve 60, skill_runner._run_one_step 53, routes_chat._prepare 52); 805 process ledger; 743 gestures and enlarged view; INBOX 904 open bugs.


> **Where the owner reads screenshots (UI_MODERNISATION_PLAN Phase 11 item 11; ledger 1539):** `docs/screenshots/*.png`, shown in the README and `docs/index.html`; `scratchpad/ui-sweeps/readmeshots.js` retakes them against a running app. A change to a surface retakes that surface's shot in the same commit. The phone picture is `docs/screenshots/phone.png` (390 wide, the same script; `SKIP=phone` leaves it); nothing else is a place the owner reads.

> **The owner's typos are fixtures, 2026-10-11 (standing, Brief 90):** "all my spelling mistakes and grammar issues in all these and future prompts in these sessions are checked against the composer to see if it can properly understand them, if not, add the capability and understanding with response variations." Every session appends the owner's new misspellings to `tests/fixtures/owner_typos.json` and fixes any the engine misreads.

> **Model per task, the owner 2026-10-11:** "make sure you are making use of sonnet and haiku agents as well but make sure quality doesnt degrade, change models and effort levels based on the task to save on tokens. be token efficient". Haiku for mechanical sweeps and doc moves (low effort), Sonnet for named fixes, research and specified features (medium), Opus for design judgement (high only for plan phases); never Fable.

> **A question is a bug report, the owner 2026-10-11:** "if I ask about something and it is meant to be that way like with the blue highlights in the sidebar, it means that it probably isnt learnable or made evident enough or labeled properly." Standing rule: when the owner asks why something looks or behaves a certain way and it is by design, the design is still wrong. Answer the question, then file a learnability fix (a label, a count, a visible control or a `data-help-for` line) in the same placement, never "working as intended". Every brief carries it. The owner again, same day: "across all my future conversations and sessions, analyse the questions I am asking to identify more issues, like if I am asking these questions and the features exist, then it obviously isnt learnable, accessible, or usable enough if even the owner of the repository doesnt knoe how to use or access something ro how something works. the application needs to be instinctive to use." So every session reads the owner's questions for "does X exist / how do I / where is", greps whether X exists, and when it does, files where a person would look for it (INBOX 828: live captions existed, reachable only from the palette).
> **Agent mix, the owner 2026-10-10 21:40Z (INBOX 774):** the orchestrator moved off Fable for cost (half the weekly usage went in one day); "do just as good of a job as it". At most three Opus agents, the latest word on the cap; Sonnet and Haiku wherever they reach the same standard.
> **Overnight, the owner 2026-10-10 16:02Z (INBOX 771):** "I am sleeping so continue autonomously. Impress me a lot." The queue, in order, as Opus slots free (cap four, Sonnet extra): 70, 71 (after 69), 84 (after 68), 76 to 83, 85 to 90, 48, 49, 52, 54, 55, 57 to 59, 61 to 63; Sonnet now: 50, 53. Each merge: gate, CHANGELOG, Built block to HISTORY, push.

> **Decisions asked, the owner 2026-10-10 (INBOX 765):** audience "Public release now" (installers for Windows, macOS and Linux, a GitHub release and a landing page are release work, not a later phase; the friends-on-a-phone path stays inside it); model "A small ollama model (2B-9B), or no model at all because ollama makes my computer slow and drains battery so I can only run it when on charge and not trying to play video games etc." (so no model is the first mode of the app, a 2B to 9B model the second, and the app must never start or keep a model running without saying so and offering Stop: CHAT_PLAN decision 61); priority "The deterministic chatbot first and foremost, then the trust and polish, then the code editor and IDE, then the companion and avatars. all of the above but in that order" (the Now order below follows it); Word files: Mammoth and docx vendored (DOCUMENTS_PLAN). Then (INBOX 766): "the app needs to work with all models though, dont base things off only what I use, it is a public app so it needs to suit everything and everyone": CHAT_PLAN decision 62, the provider matrix is the contract and the owner's setup is one row of it.

> **Skills, the owner 2026-10-10:** "make use of all relevant skills if you feel the need but dont let them limit you. they are a guide and tool. you ai models are improving all the time and sometimes outdated skills cna be a hindrance." Read: a skill is consulted, not obeyed; when its advice and a measurement disagree, the measurement wins and the brief says which skill was overruled and why. `docs/DESIGN.md` still overrides the vendored design skill for anything in `frontend/`.

> **Polish, the owner 2026-10-10:** "keep improving, redesigning, modernising and proffesionalising and imrpoving ui and especially ux across the app. add more small taken for granted features, more utility, more abilities and function. clean everything, polish everything." Read: UX before UI; every brief that touches a surface adds the small expected things (keyboard, undo, empty states, hover and focus, counts, remembered state, a help popover) and lists them in its report.

> **Mandate, the owner 2026-10-10:** "keep improving, on expanding, bug fixing and bettering the deterministic features and chat bot composer a well. cover absolutely all of my requests but dont stop there, you know sooo much more than me and I believe you can do so much more to iomprove and things that I havent even thought of. I trust you to better the app while remaining token effcient and throrough." Then (INBOX 757): "and more". Read: every placed request is the floor; each brief adds what a professional would expect that the owner did not name, measured, and reports it under found-not-fixed or builds it when small.

> **Token spend, measured 2026-10-10 (Fable):** over 33 agents this session, cache reads were about 95% of every agent's tokens, so an agent's cost is its turn count times the context it carries, not its model alone. Two Opus agents of 600 to 700 turns (chatui, boardmap) cost more, at list-price ratios, than the nineteen Sonnet agents together; Sonnet for the same turn count was a fifth to a tenth. Standing practice from here: every brief carries a tool-call budget (research and measurement 120, building 160), briefs are split rather than run long, agents batch reads and read ranges, the orchestrator gates agents that land together in one pass, and the owner's asks are batched into one message where possible (each mid-turn message re-reads the orchestrator's whole context).

> **Coverage and authority, the owner 2026-10-10:** "make sure nothing from all my requests and bugs and issues has been missed and is missed. and then go further. fix any issues or architectural decisions you dont agree with as I trust you more than it." So: every owner item is placed verbatim in a plan (Brief 40 (a)) and checked off at merge; Brief 43 goes past the list; and the orchestrator may overturn a recorded decision when the evidence says so, writing the reversal and its measurement next to the old decision rather than deleting it.
>
> **Agents, the owner 2026-10-10:** "make use of sonnet 5.5 as well as it is cheaper, maybe even haiku 5.5 ... just maximise the amount of use I can get token wise from my usage. be thorough. miss no bugs or flaws." and "maybe change effort for agents based on the task?? just make sure quality doesnt suffer". So: effort set per task (high for design and engine work, medium for named fixes, low only for mechanical passes); Opus for design judgement, Sonnet for well-defined fixes and research, Haiku for placement, sweeps and copy moves; up to four Opus at once plus Sonnet or Haiku extras (the 2026-10-05 allowance). Never Fable agents. Quality bar unchanged: measure, test, commit per step, five-line report.
>
> **Models and count, the owner 2026-10-05:** mainly Opus; Sonnet for well defined, labour tasks ("actually mainly use opus but just remember that sonnet is there for well defined and labour tasks"). Once the current four finish, at most three agents at once.
>
> **More Sonnet, the owner 2026-10-05:** "focus on finishing everything open. work faster, be thorough, be more token efficient. Ill allow more agents if they are sonnet 5.5". At most four Opus; extra agents beyond that are Sonnet. Shared rules: archive/agent-remaining/agent_rules_1005.md.
>
> **Agent count, the owner 2026-10-05:** "after these agents are done drop down one or two agents so the usage isnt as close". Running agents are not replaced as they finish; at most four at once from here.

## 2026-09-08, the third night: read this block first, whoever you are

**If you are the Opus continuation of the Fable session** (same session,
same branch, the owner's Fable window closed): the standard is the one
in `SESSION_BRIEFS.md` §0 and it does not drop. Measure before claiming,
tests first, one commit per step, push after every merged batch, no
em-dashes, report in five lines. When unsure, the decision is already
written in `WORLD_CLASS_PLAN.md` or a plan file; find it, do not remake
it.

### If Opus is the orchestrator (no Fable available)

This is the expected case for most of the week. Everything Opus needs is
already written; the rule is to work it, not to redesign it.

1. **Open with:** read `CLAUDE.md`, this block, `ROADMAP.md`'s opening
   table, the "Now" line below, `INBOX.md`, then the file the Now line
   names. Nothing else before the first commit.
2. **Order of work** is the standing orders' order: INBOX bugs (Sonnet
   for the named-fix ones, Opus for the design ones), `agent-remaining/*.md`
   (Opus), `SESSION_BRIEFS.md` Briefs 2 to 15 (by the specialty split),
   then the plan phases in ROADMAP order (TIMELINE, WHITEBOARD, CHAT,
   DOCUMENTS, GRAPH, MINDMAP), each against its plan's gates and, for the
   backend, its spec tests (remove a strict-xfail marker only when the
   test passes on its own).
3. **Decisions are not remade.** Every plan carries a "Decisions made"
   section; a session that finds itself choosing between two designs
   looks there first, and if the answer is missing, records the question
   in `INBOX.md` under "Design and feature requests" with a one-line
   recommendation and takes the recommendation. Fable's next window
   reviews those entries.
4. **Review is Opus's job too.** Before merging any agent branch: read
   the diff for the four failure shapes in `CLAUDE.md` (a working thing
   rewritten riskier; a feature that never ran; a guard removed; a policy
   silently refusing), run the lint set and the sweep the brief names,
   and refuse a merge whose report has no numbers.
5. **No new plan documents.** There are eleven; a new need becomes a brief
   row in the plan it belongs to, or an INBOX entry. `HANDOVER.md`'s Now
   line and this table are the only status surfaces; keep them true.
6. **Agents:** at most two, by the specialty split below, each with its
   own worktree, port and data dir, committing per step and writing its
   remaining list before it stops.
7. **The hourly check-in** (`send_later`) is re-armed at the end of every
   turn; it carries the standing orders in its prompt, so a session that
   went idle resumes itself.

The opening prompt that does all of this: "Read CLAUDE.md, then the top
of docs/roadmap/HANDOVER.md, and continue."

### PR 144 is done when (the owner's checklist, 2026-09-09 05:30 UTC)

Tick these in order; the PR merges on the last tick. Everything added to
the plans this session (DOCUMENTS Phase 8, MINDMAP §12, GRAPH 6b, INBOX
100 to 104, CHAT and TIMELINE in full) is the next session's, not this
PR's.

- [x] 1. Documents Phase 2 steps 2 to 4 merged (2026-09-09;
      `tests/test_doc_surface.py` carries no xfail marker): the CodeMirror surface is
      the editor, Live as decorations, findings, undo, search, folding;
      `tests/test_doc_surface.py` has no xfail markers left; doctype.js
      under 30 ms; the vendor bundle absent at boot.
- [x] 2. Graph Phase 6 merged: the node panel on the new recipe, measured
      at 1440, 1024 and 390; graph4b.js passes. (Panel 416x439 to 448x348 at
      1440 and 1024, three groups of three to nine buttons in one row,
      shortest control 28 to 36px, no page scroll, and a 362x442 sheet at
      390. Its header and its action footer were fixed later the same day:
      close button back at 0,0 with an ellipsised title, and the actions as
      a centred band 446px wide in a 448px panel.)
- [x] 3. Library image cards and the whiteboard bottom bar and properties
      panel merged (INBOX 52, 56, 64, 65), with their numbers. (Card 651.6
      to 371.8px, font sizes 4 to 3, usage lines 2 to 1, scrim 3.6:1 to
      6.8:1; whiteboard own backgrounds 16 to 1 and 15 to 3, overlapping
      pairs 4 to 0, bar and pill both 46px, surface 0.549 to 0.96 opaque.
      The Arrange group was restructured later the same day into three
      named rows, 192px wide in a 200px panel.)
- [x] 4. The owner's section-A bugs closed or ruled out at head: INBOX 66,
      69, 70, 73, 77, 81, 83, 84, 86, 88, 89, 96 (each fixed and moved to
      HISTORY, or marked "not reproduced" with the measurement). Eleven of
      the twelve are in HISTORY with their numbers. 77 is the exception and
      is half done on purpose: the badge is fixed and measured, the
      per-model context size is the half the entry itself assigns to the
      next session, and INBOX says so. It is the only item left in there.
- [x] 5. The three "not verified in a browser" fixes measured: INBOX 75
      (kebab first click), 82 (settings rows), 91 (chat header), plus
      Ctrl+S and the profile group; errors.js, contrast.js, docks.js,
      touch.js and weight.js green on the head.
      **Where this stands, 2026-09-09.** Ctrl+S is measured and fixed (the
      visible section had no reachable Save button, all six in the document
      laid out at zero height). errors, contrast, docks and touch all passed
      on the merged head. 82 is clean as far as it was checked: two settings
      rows carrying both a field and a button, zero height mismatches, which
      is thin coverage rather than a result. 91 is measured by the wrap
      sweep, which took the answer header from three fragmented lines at
      1280px to two clean rows. 75 is measured now
      (`scratchpad/ui-sweeps/kebabfirst.js`): 58 kebab wraps on the Notes
      tab, the first click opens exactly one menu at 375px tall, the second
      closes it. The earlier probe reported "no kebab found" because it
      looked for `[aria-haspopup]`; the recipe is `kebabMenu()`, which builds
      a `.menu-wrap` around a `.action-menu` and a `smallButton`, so the wrap
      is what to look for. Worth writing down: the same wrong selector would
      fail the same way next time.
      A note on the metric, so the next attempt does not repeat it: counting
      distinct `top` values among a row's children does **not** detect
      wrapping. A `nowrap` row whose children are baseline- or
      centre-aligned reports several distinct tops and has not wrapped. Test
      whether a child's `top` is at or below the first child's `bottom`.
- [x] 5b. The README's screenshots recaptured, last of all. The owner:
      "I think the screen shots on the readme need an update from all the ui
      changes." Eight of them in `docs/images/` (chat, dashboard, documents,
      graph, library, notes, reminders, timeline). Capture them only once
      every UI batch has merged: taken mid-session they are stale within the
      hour, which is how they got stale in the first place.
- [x] 6. Mind map previews (INBOX 68) acceptable in the dashboard widget
      and the Library gallery (the board's real shapes at its aspect, no
      inner scrollbar). (Whiteboard card 5 blocks at one size to 5 at four
      sizes with 5 of 5 labels inside their shapes; map card 0 of 6 labels
      inside to 6 of 6, worst contrast 3.82:1 to 4.77:1; dashboard
      thumbnail 293.2 square to 40.5 square with the widget's body no
      longer scrolling, where it was 602 against 320.)
- [x] 7. The full suite green on the final head (the one local run this
      PR gets; CI covers every push in between); ruff and CodeQL green;
      **Run, 2026-09-09:** `PYTHONPATH=src .venv/bin/python -m pytest
      tests/` on the head, exit code 0, no F or E in the progress line, the
      xfails still xfail. Worth knowing before the next reader thinks the
      run was cut short: with `addopts = -q` from `pytest.ini`, the totals
      line does not survive being read out of a redirect on a run this
      long, while a single-file run prints it normally. The exit code is
      the result. All sixteen CodeQL review threads on the PR are resolved,
      the sweeps (errors, docks, contrast, touch) pass on the head, and
      the branch is mergeable.
      **Note, 2026-09-09:** `.github/workflows/ci.yml` runs `python -m
      pytest` with no selection, so CI *is* the full suite, on every push,
      and it has reported no failing suite on every head today. CodeQL has
      come back green on each one it has finished. The local run this item
      asks for is therefore a second opinion rather than the only evidence,
      which is exactly why the owner's "not as routine" rule costs nothing.
      no open CodeQL threads; the branch mergeable.
- [x] 8. Documentation: every Built block of the merged phases in
      HISTORY (the lint holds it), INBOX holding open items only, the
      README's numbers passing `test_readme_freshness.py`, CHANGELOG's
      "Since 0.2.2" carrying one line per merged item, this Now line
      rewritten as "PR 144 merged; next: Brief 18 section A onward".
- [ ] 9. The owner has run the updated build once: `start-desktop.bat`
      launches, the splash reads right, the glass frosts the art.

Then: tag the release (`__version__` is already 0.3.0, a minor bump by
RELEASING.md's rule: new features, not fixes; rename "## [Unreleased]" to
"## [0.3.0] - <date>" in both CHANGELOG copies, `git tag v0.3.0`, push the
tag, watch the release workflow), merge PR 144, restart the branch from main for the next session
(the branch rule at the top of the session prompt), and open with "Read
CLAUDE.md, then the top of docs/roadmap/HANDOVER.md, and continue".

### Fable's working notes for Opus (2026-09-09 05:10 UTC)

What made this session's fixes land first time, written down so the method
survives the model change. Use it verbatim.

**The method, per report.** (1) Find the code by grep before reading any
file whole; the sites below are already found. (2) Write a 20-line
Playwright probe (`scratchpad/ui-sweeps/lib.js` `boot()`, then
`page.evaluate` returning numbers: rects, computed styles, counts) and run
it against `serve.sh 8784 /tmp/mm-8784`; never screenshot-and-look. (3)
Fix the cause, not the symptom (the shape that recurs here: a handler
re-renders over what it just opened; a rule set on the wrong class; a
value measured while hidden). (4) Re-run the probe, then the lint set,
`node --check`, ruff; errors.js in the background. (5) One commit per
report with the measured numbers in the message, the INBOX line marked
"Fixed" with the numbers, push. (6) Say "not verified" when a browser did
not confirm it. Never widen a lint; a failing lint found something.

**Where each open section-A item lives** (INBOX number: file, area,
diagnosis):
- 66 lightbox in graph fullscreen: `frontend/js/app.js` lightbox mount (grep
  `lightbox`), `#graph-card` is the fullscreen element; mount the dialog
  inside `document.fullscreenElement` while it is set.
- 69 agent panel rows: `frontend/js/app.js` ~35850 (`agent-run-summary`,
  `agent-run-name`); the caret's toggle handler is per-row and lost on
  re-render; delegate it on the panel.
- 70 notifications combobox: the panel's outside-click guard closes on a
  click inside `.select-menu` (enhanceSelect at `app.js` ~18359); exclude
  it.
- 73 mute toggle resets: `frontend/js/settings.js`, grep `mute`; write the
  value into `prefsCache` before the save round-trip, not after.
- 74 profile panels and Ctrl+S: `frontend/index.html` "About you
  (optional)" group; a `keydown` on `#settings-modal` for Ctrl/Cmd+S that
  clicks the visible section's Save.
- 77 token badge: `frontend/index.html` ~1238 `.chat-subline`; the pill's
  padding is asymmetric and its text is `x% of window`; centre with
  `inline-flex; align-items:center; line-height:1`.
- 81 web links: the answer renderer's link rule (grep `renderMarkdown` in
  `app.js`), accept `<https://...>` autolinks; number web sources after
  the notes in the Sources list.
- 83 Tools paragraphs: `frontend/index.html` Settings > Tools, "How many
  are offered at once" and "Small model mode"; one line each, the rest
  behind `data-help-for` (pattern at index.html ~5321).
- 84 marquee behind objects: `frontend/js/whiteboard.js`, the selection
  rectangle is drawn on the object canvas; draw it on the overlay canvas
  (the one the guides use).
- 86 zoom popup under dialogs: the zoom indicator's z-index (grep
  `zoom-indicator` in CSS) is below `.modal-overlay`'s; raise it.
- 88 fullscreen graph glass: `:fullscreen .graph-card` paints over
  `--page` with nothing behind it; give it `--modal-bg` on purpose and a
  comment.
- 89 glass sliders: measure `--glass-blur` on `header#top-bar`'s computed
  backdrop-filter, `--glass-opacity` on `.card` background alpha (palette
  override order in `00-tokens-shell.css` 131/628/677), sheen on
  `:root[data-glass-sheen="on"] .card` (3389); the card blur is off unless
  `data-bg-art="on"` (INBOX 49), which is why "blur does nothing" on a
  still page.
- 96 drag without pin: `frontend/js/graph-canvas.js` drag end (grep `fx =`
  and `gcTogglePin`); on drop set `x/y`, clear `fx/fy`, reheat at
  alpha 0.1; pin only on Shift+drag or the menu.
- 67 gravity: `frontend/js/graph-worker.js` `tuning()`; `pull` is 0.25x to
  3.25x; if still spread at 100 on the owner's build, raise to 5x and add
  the component ring.

**The two agent briefs**, verbatim, are SESSION_BRIEFS Briefs 19 and 20 so
an agent that dies can be relaunched by anyone with the same words.

**What Opus should not do:** redesign what a plan decided; touch
`documents.js`/`editor.js` while the documents agent runs; merge a report
without numbers; run pkill on uvicorn; install torch; use inline
`style=`; add a glass surface without the `[data-glass="off"]` list.

### Standing orders for this session (whoever the model is)

The owner will say "continue", or paste a batch of issues, possibly
after a usage reset. Either way, without asking anything:

1. **"Continue"** means, now and after every brief is done: read
   `CLAUDE.md`, this block, `ROADMAP.md`'s opening table and `DESIGN.md`
   (token-efficiently: first screens, then only what the next item
   needs); merge any agent worktree that has commits not on the branch
   (table below, recipe below); then take the next unfinished item in
   this order: the owner's flagged items (this block and
   `agent-remaining/*.md`, deferred not dropped), `SESSION_BRIEFS.md`
   Briefs 1 to 15 in order, WORLD_CLASS_PLAN §11's quarter, then
   `ROADMAP.md`'s live list and `BACKLOG.md` top-down by impact and
   quality. Scan for bugs, flaws and stale docs on the way and fix or
   record them. Keep `HANDOVER.md`, `ROADMAP.md` and `BACKLOG.md` true as
   you go. Commit per step, push per batch, five-line reports. Never
   wait for a prompt; never ask permission for work inside the plans.
1a. **The "Now" line.** The first line under "State of the branch" below
   always says what is in flight and what its gate is. Update it when a
   step starts and when it ends. A session that resumes after a pile-up
   reads it before the pile.
1b. **Things the owner drops in mid-work** (a screenshot, a complaint, a
   feature, "X% usage") are not a change of task: finish the step in
   hand, add the new item to the task list with the owner's words, place
   it by impact (a bug in something just built goes next; a new feature
   goes into the relevant plan or BACKLOG with a brief row), and say in
   one line where it landed. The mechanism is `INBOX.md`: append
   verbatim on arrival, triage only at a step boundary, in one pass. A
   usage figure means: commit and push now, then continue more tersely.
   Never finish a step early, never drop quality, never lose the "Now"
   line to the pile: the owner has said this is the recurring failure.
2. **A batch of issues** means: for each one, reproduce it in the running
   app first (Chromium, `scratchpad/ui-sweeps/lib.js`), fix it to the
   standard (measured, a sweep check added where one exists), commit it
   on its own with the owner's words in the message, and push the batch.
   One that cannot be reproduced gets a line saying exactly what was
   driven and what was seen, never "works for me". One that is bigger
   than a fix gets a row in the relevant `agent-remaining` file or a
   SESSION_BRIEFS brief, and the owner is told which.
3. **Agents, by specialty, at most two at once** (the owner's rule):
   **Sonnet** takes the mechanical and the verifiable: lints (Brief 2),
   copy moves and popovers (Brief 4), docs condensation (Brief 14), test
   fixture edits, sweeps, and bugs whose fix is already named in
   `INBOX.md`; **Opus** takes anything with a design judgement in it:
   frontend layout and visual fixes, the one-bar and alignment work, plan
   phases (DOCUMENTS, GRAPH, TIMELINE, WHITEBOARD, CHAT, MINDMAP) and the
   backend moves (Briefs 6 to 13), each against its spec tests
   (`tests/test_events.py`, `test_search_engine_spec.py`,
   `test_harness_verifier_spec.py`: strict-xfail, remove the marker as
   each passes); **never Fable** (the owner, 2026-10-04: it kills usage); Opus writes plans and specs,
   reviews merges line by line and root-causes the invisible bugs. Each
   agent works in its own worktree cut from the branch with its own port
   and data dir, commits per step, and writes its remaining list before
   stopping. The orchestrator merges, gates, pushes.
4. **Never stop on a red**: CI, CodeQL and review comments are fixed the
   same hour; the hourly check-in re-arms itself (`send_later`), and the
   subscription on PR #144 stays.
5. **Quality does not drop with the model.** Tests first, measure before
   claiming, no em-dashes, no scope creep, the four failure shapes checked
   in every diff. If a decision seems needed, it is already written in a
   plan file; find it.
- (Odysseus, fourth read 2026-10-10) 

### How far each plan actually is (honest, as of 2026-10-03)

The owner: "many of the plan and ui redesign and modernisation documents
are only just begun or half done." The 2026-09-08 version of this table said
so and was right; the plans have since been built through, and this is the
state now. The line-by-line ledger of what is left is
`agent-remaining/OPEN.md`, section B.

| Plan | Done | Left |
| --- | --- | --- |
| UI_MODERNISATION_PLAN | Phases 0 to 11 (tooling to the Liquid Glass adoptions to the phone done properly), the Settings information architecture (444), consistency pass 1 and the zoom sweep (2026-10-03) | Consistency pass 2 (Settings shell, Reminders on a phone, Library, Notes and Documents chrome, running), Phase 11 item 11's screenshot set, Phase 10's `.glass-clear` |
| GRAPH_PLAN | Phases 1 to 6, the minimap (6b), the local pane, saved views restoring positions, the lasso as one drag, the 2026-10-03 shape (categories gather, unlinked on a ring) | The `?since=` cursor (nothing polls `/graph`), the local pane's Show switches (left by decision) |
| DOCUMENTS_PLAN | Phases 0 to 8 (CodeMirror 6, blocks, the connected document, review and history, export, one editor everywhere), the slash menus as one system (section 18), boards and maps as objects in a note (section 19) | The Phase 2, 6 and 8 tails, the engine's three deliberate omissions, the phone's bottom formatting bar |
| MINDMAP_PLAN | Phases 1 to 5, section 12's controls and structure, section 13's render pass (500 topics: render 47.8 to 149.1 ms, open 965.6 ms) | The 2026-10-03 audit's found-not-fixed list (445 (2)) and the mapux agent's leftovers |
| AGENT_SKILLS_REFORM | Phases A to D, D verified against a real model (2026-09-20) | The same gate at 3B and 4B, an eval each for CLAUDE.md section 4's unproven list |
| WHITEBOARD_PLAN | Phases 1 to 4 (the rail and keys, the context bar, export dialog and handles, mind map regressions and Tidy) | Decision 7's other half, the phone context bar comparison, sketch handles at zoom, the arrange panel items |
| CHAT_PLAN | Phases 1 to 4 (grounding closed 2026-09-23, one composer, Ask unified and the popup agent, skills that finish) | The `evals` breadth (WORLD_CLASS_PLAN 9), the chat stutter notes (413) |
| TIMELINE_PLAN | Phases 1 to 4, section 7's two measurements | Nothing (the "auto" scale thresholds were tuned 2026-10-04) |
| WORLD_CLASS_PLAN / SESSION_BRIEFS | Briefs 1 to 34 written; the row check of 2026-09-24, F3, `similar_pairs`, S1 to S3 and S5, the llama.cpp runner | The ranked list of 38 (plan section 8): Brief 15's LAN tail, B2 durable jobs, D2, I1, chunk vectors then I6, I3 |

### State of the branch (`claude/notes-flow-rebuild`, PR #162)

**Away run (owner at work about 8 hours, 2026-10-18), branch claude/trusting-cannon-wrf8s5, PR 191, from main 3b9072c (PR 189 merged):** tier max (three Sonnet agents, no Opus, no Fable); stops at weekly usage 85%, 8 hours or 60 minutes with no commit. Order: red CI first, then the owner's known-open list (clock offsets, long-question cost, the `data/` writer, Library and Notes reveal cost, companion release frames, Harper beyond the popup, popup citations, typo fixtures), then INBOX, agent-remaining, briefs, plan phases in ROADMAP order, BACKLOG and OPEN, with bug, security and UI sweeps between. Done so far: 8cc6639 (`when.resolve` keeps the clock beside a day-sized offset; `utilities.kind_of` cached and bounded, route 4.1 to 0.7 s on a 20,000-character question), 6da55eb (Performance workflow frame spec opened the removed Documents tab and hung 180 s; six `test_mcp_server` tests wrote the repo's `data/`, a conftest guard now fails any test that does). Decisions: owner questions, B61 and B58 left as written; the dashboard's 62 rAF/s idle seen on the CI runner did not reproduce locally, so the frame spec now names the looping callback and the finding waits for the next run; no CI definitions touched. Later: the cite, companion, order and reveal agents merged (popup citations with numbered marks, reminder autocorrect underline, release read-before-write, Library `content-visibility`, 18 typo fixtures); boot JS back under its cap by deleting dead code (the budget has 1 byte of headroom, so the next boot change must be net zero or lazy); `kind_of`'s cache now keys on the web search setting (it served a stale route after the toggle); `test_ocr_regions` and the background-thread teardown were the last `data/` writers CI's serial PDF job named. Decisions: Notes' first reveal stays as measured (701 to 917 elements already `content-visibility` rows; a 13-row first paint changes the settled list and Select all), recorded found-not-fixed in `reveal-1018.md`; INBOX 735, 742, 771, 772, 804, 807, 808, 903 moved to HISTORY as placed. Harper in plain boxes (capture, chat, quick note) is not built, by decision: its 15.9 MB binary compiles in a worker on first use (measured in `p2-harper.js`) and a textarea has no overlay for lint underlines, so the table and dictionary corrector stays the thing that rewrites and Harper stays in the document editor and note edit form; the owner can reverse it. Then merged: composer-1018b (post-pass, 17 complexity rows, ghose, happyer), timeline-1018 (audit, tick labels from d3's time scale), order-1018. CI cancels an in-flight run on every push and a full Python run takes 15 to 25 minutes, so push once per batch and read the finished run's failure list before the next push. The run on 295c516 named nine real failures from those merges (not flakes): a data/ writer in test_bgtasks and test_janitor_warm, the speller warm-up job in /tasks, import cycles closed by the two cold-process fixes (the registries stay; conftest loads the Guide and commands, the cold-process tests load the app), timeline-ticks' stylesheet, observer and two lets, a renamed citation callback, a second date reader in composer_digest, silent excepts, and the scratchpad file cap. Fixed in fc37dff and 7e4c3d6 (the extras installer's record is reset around each app_state test). Then: `deps.peek_config()` lets prompt building read the clock without starting the app (the `test_connected_results` 3.11 failures); presets, prompt-budget, bgtasks and janitor tests use `app_state`; `test_ocr_engine` resets its language cache; `_generate_diagram` and `mcp_server.handle_request` split under the complexity line. INBOX 1297 kept as is (decision: it is the owner's wording, not a defect). graph-1018 and documents-1018 merged (owner questions B39 and B20 left as written; Tessellation layout chosen by the plan's decision; B70 did not reproduce); their one-off sweeps were removed to hold the scratchpad cap at 766. Agent dev servers may remain on ports 8791, 8792, 8796 and 8797 (kill by exact PID only). ui13a-1018 merged (drop shadows 19 to 7, `!important` 128 to 117; z-index and colour literals left, they need a pair sweep and a visual judgement). chat-1018 merged (topic read whole, computed answers for days until, order, mention counts, lists, due dates; live gold mean 76 to 87; INBOX 812 fixed; its date words now read through `recognise.ahead_window`). The one serial full run named eight tests that started the app in the repo's `data/`: they take `app_state` now and `tool_enabled` reads `deps.peek_config()`. Pushed ebc5a46 (31 commits) as one batch. whiteboard-1018 (draw.io steps 1 to 7 and 9; step 8 layer order left for an Opus pass, it needs a stacking sweep), mindmap-1018 (Expand from my notes, topic note answer, resize grip fix) and a read-only security review merged; the review's five confirmed findings fixed in 5691a83. The CI run on ebc5a46 named three failures on every Python version (wake-source seed for the snippet drag's two frame loops, the top-level let cap, two table-grip hover rules without a focus twin), fixed in 048584e (pushed). Agents running: worldclass-1018 (nav and undo audit), open-1018 (OPEN.md Library, Notes, shell, Timeline), left-1018 (mindmap strip cover, Ask due-date path); their lines land in `agent-remaining/`.

**Away queue (owner asleep, 2026-10-17 late), state at the last push (5af1c03 on PR 189):** merged and green: both WIP branches, CI fixes, companion physics/perch/boot budget, Atlas stars and the companion mind (lazy companion-menu.js), timeline calendar add (B72), Harper hover (B04), the new-chat skeleton, composer O5 to O11, tab-entry costs (reduced-motion blankets now motion-still.css, timeline `:has()` anchors removed: timeline entry style 654 to 246 ms at 4x), accessibility WCAG 2.2 sweep, security review (graph pins, slash, ReDoS, LIKE wildcards), composer question cap (2,000 chars planned), `/improve` bounded, B80 new-tag suggestions, folder import as a durable pool job, word-boundary snippets, time-reader gaps (spoken clocks, 24-hour figures, `eod`, week offsets, midnight). Open, in order: B50 splash (Windows only, unverifiable here); Harper-driven autocorrect beyond the popup; Library/Notes reveal cost (first style of the revealed page, 1,389 and 1,186 elements; only a smaller first chunk helps); `when.resolve` ignores a clock after a day-sized offset; the route still takes about 5 s on a 20,000-character question (`question_noise.guided` on 2,000 characters, 7 times a turn); owner questions in bugs-1017.md (B32, B41, B49, B54, B77, B70, B53, B59, B07, B61 unsloth licence, B58 icon toggles needs a named example). The two remote WIP branches were merged and deleted by the owner. Two CI flakes seen on this PR were a timing test (`test_duplicates_scan_speed`, 2.20 s against 2.0) and a leaked `TESSELLATE_LAUNCHED` from `test_frozen_packaging` (fixed).

**Now (2026-10-28f, branch claude/sharp-thompson-45hngp, PR 211, head 490e3c3):** audits filed and ranked (`agent-remaining/audit-1028-ranked.md`). Merged and pushed this session: D1 to D8, D14 to D16 (D7 window), K2, K3, K7 to K10, K12, K17, E1 to E9, E11, E12, E30, E31, S1, S4 to S10, B8, B9, B16, B21, B5 partial, U1 to U8, U10, U11, find panel. Running: help text parity (agent/help-1028, standing order 13 for today's UI), E10 tasks as acts (agent/tasks-1028). Next by rank: B3/B4 incremental board render, S2 graph layout off the main thread, S3 index.html boot weight, E42/E66/E70 agent safety, K4 to K6, K19, D11; K1 is INBOX 1424. gitleaks red is the workflow's shallow checkout (commented on PR 211). Stopped (see Morning summary).

**Now (2026-10-27f, branch claude/loving-edison-4d0din, PR 204, head 70126d0):** CI fixes for 915649f's 7 reds pushed (complexity splits, global lets, Alt listeners, warm-up log, helper imports, guide test); CodeQL 1846/1847 fixed and resolved; watch CI on 70126d0. INBOX 1418 to 1423 merged (thumbnail, launch, composer wording, silent model server, popup Save row, Ask head presses, lone Alt); 0.6.2 CHANGELOG folded. Stopped at the owner's 53% weekly line. Next: CI green on the head, then README screenshots retake (scratchpad/ui-sweeps/readmeshots.js), the repo cleanup pass, citation numbers in text order (1420 leftover), Alt on a real Windows webview, the throw's idle spot measure and mood timer, BACKLOG 1416, 1417, 1338, 1339.

**Now (2026-10-27e, branch claude/loving-edison-4d0din, PR 204, head 2f0401f):** PR 204 open items done: whiteboard 1403/1404/auto-select, Atlas bar landing, facts check, guide 1414, graph popups 1413, plan Done 1412 merged. Left: real-model check (needs `scratchpad/llama-dev.sh serve`, `pytest -m evals`), BACKLOG "Placed from the guide round", watch CI on 2f0401f.

**Now (2026-10-27d, branch claude/loving-edison-4d0din, PR 204, head 17c4ff5):** mermaid vendored and merged (documents, chat, Ask; remaining list agent-remaining/mermaid.md). CI on a86cc98 had 11 reds: 6 fixed in 9f66a0b (one-reader, aware now, two exemptions); the other 5 unnamed, read them from CI on 17c4ff5 and fix. Disk: /tmp/pytest-of-root holds 20 GB, deletion needs the owner; no full local suite until freed. INBOX 1410 placed as BACKLOG mermaid 12d.

**Now (2026-10-27c, branch claude/loving-edison-4d0din, PR 204, head bc27f5d):** stopped at the owner's 48% weekly line; all three agents merged; read the Morning summary at the top for open items and next steps.

**Now (2026-10-27b, branch claude/loving-edison-4d0din, PR 204, head 1eb5a0c):** container restarted 10-27 ~01:00 UTC; agents resumed by SendMessage. Running (3, cap): graph opening smooth and flowy (worktree-agent-a8db85ea1cad3c72f, WIP uncommitted then); wrap toggle on table and code cards plus Reminders row kebab under `.entry-date` (worktree-agent-ae3d7e0d08bd0486c); model writes counted answers from the composer's facts (worktree-agent-a70dafd805f3858f8, 645e72b, NOT merged): reviewer found HIGH `_prose_keeps_facts` accepts miscounts (any digit in facts/clock counts as known; one/no/none unchecked), HIGH test_reminders_with_model on the real clock, MEDIUM stats lists lost, MEDIUM `_ASKS_TO_DO` misses and over-matches, LOW refused thinking streamed, LOW 'list my work notes' still composer, PRIVACY `_list_reminders` no private filter; sent back to the same agent to fix, then re-review before merge. Next (owner asked 10-27): fastembed swap for sentence-transformers and torch (same bge-small-en-v1.5 on onnxruntime; one re-embed via the stored model id; extras installer, Windows spec, help, capabilities), launch when a slot frees, Opus. Then: full suite on the head (last run killed by the restart; the one before found 3 reds, fixed in ea535ff); Timeline open 941 to 1200ms frame; whiteboard leftovers (multi-select stroke outline under cards, pre-migration board import). Done 10-27: certifi floor 2026.10.23 (eMudhra) 1eb5a0c; wordmark, model ask-first, seasons by locale, docs counts cac7a0f; whiteboard strokes stack eb969bf; reminders Google/Outlook and chat chip bb85e70; desktop Open in a new tab one-file link 65853ff; popup Send and graph chevron gap 5672429.

**Now (2026-10-26i, branch claude/loving-edison-4d0din, PR 204, away, stop at 43% weekly (35% at 17:40), then morning summary):** head 1c37f42. Merged since 10-26h: composer round 2 (boards, maps, documents as sources; map hierarchy; filtered counts; told by source; ranges and recently, 49/49), code editor and recordings dogfood (f5d0fba), whiteboard layer order (painted vs model 92 to 0), CodeQL regex fixes in ai/no_model_text.py (5 threads resolved). Running: graph round 3 (help on every Options group, panel fit, toasts clear of legend, untangle on warm-up; carries unmerged round 2 worktree-agent-a0f8670b3e82df58e), code editor leftovers (status bar counts, empty assist send, print code, waveform height), composer round 3 (state, tag and season counts, week-of phrases). Next: harness and Needle. Found-not-fixed: whiteboard drawings are one layer under cards (owner decision), mind map root width (owner decision).

**Now (2026-10-12, branch gemini/composer-improvements, PR 169, 0.5.0):** the rename is done (package `tessellate`, the "notes" lockup, new installs in a `Tessellate` data folder, an old `%APPDATA%\MemoryMap AI` folder kept while it exists, `memorymap.db` renamed `tessellate.db` once at start, downloads named `tessellate-*`); the packaged Windows exe starts `scripts/splash.ps1` itself (`_start_frozen_splash`; not run on Windows from here). First work of the next PR: BACKLOG "Start of the next PR" (the owner's 2026-10-12 list: settings header and gaps, Activity Logs button, OCR workspace empty state, whisper.cpp and needle notices, chord key, companion fall physics, Harper grammar) and INBOX 1298, the complexity rows seeded on the owner's order (16 `composer_digest.py` functions, 18 that grew). The block below is the 2026-10-10 record.

**Now (2026-10-10, branch gemini/composer-improvements, Fable orchestrating):** the owner's order (INBOX 765): the deterministic chatbot (CHAT_PLAN Phase 6 and the foundation, Briefs 64 to 68, then 84), then trust and polish (WORLD_CLASS 28, Briefs 72 to 74 and the design rows), then the code editor as an IDE (DOCUMENTS 23, Briefs 69 to 71), then the companion (Brief 34); release work (installers, GitHub release, landing page) runs beside them because the audience is "Public release now". Merged by 19:30Z: 84 (Atlas everywhere), 34 second round (the faces and the tail), 70 (the debugger), the CI batch (21 tests at cause, guards 281 to 277), 71 (the IDE shell, Debug as its fifth tab) and 79 (OCR: five undos, pinch, Live Text); and 89 (Statistics: one page, the week card, timer and stopwatch, Count words, insert template); and 78 (the mind map: Untitled map N, "mind map" everywhere, grips apart, one render per add, every command at 390, four layouts, effects in the export); and 90 (the palette: UI_MODERNISATION palette rows 1, 3, 5, 7; spelling offer, act rows, learned order); and 85 (timeline and reminders: undo 6/6 and 15/15, firing on time, recurrence and early alerts, On this day, 100-row pages); 83's evaluation says keep (MPL-2.0, 5 MB engine, 25 MB a pair, a paragraph in 0.35 to 0.55 s; the build waits for an Opus slot); and 87 (the agent: every starter answered with no model through ai/starter_acts.py, the agent as a sheet at 390, a plan's writes listed and confirmed, each write on the undo bar); and 82 (live captions: the whisper.cpp helper contract, a fake helper, ai/captions.py, the dock, the palette and Packages rows; the packaged helper's download pins are left); 76 (documents: rows 24.1 to 24.4, 24.9, 25.7); 83 (offline translation, English to Spanish, in the browser) and 80 (recordings as objects, the Audio group, recovery of a killed take); running Opus: 88, 48, graphfeel; Sonnet: uipolish, agentgate, pickers (the owner's morning reports, INBOX 775 to 785) (INBOX 775, the owner's live graph report) (three Opus from here, INBOX 774); next 81 after 80, then 49, 52, 54, 55.
the Gemini session's 12 commits are under triage (Brief 35: boot broken by a
`thefuzz` import, 15 MB of unused vendoring, grounded 1.0 to 0.25); four Opus
agents run (triage, boardmap, chatui, graph: Briefs 35 to 38) on the owner's
2026-10-10 list, INBOX 727 to 745 and the plans' placed items; the direction
for everything after is ROADMAP "Direction, 2026-10-10", with CHAT_PLAN Phase
6 (the deterministic engine), WORLD_CLASS_PLAN 23 (filing and the taxonomy
pack), UI_MODERNISATION Phase 12 (density, WCAG 2.2) and SESSION_BRIEFS 35 to
42. The whole app against world class is WORLD_CLASS_PLAN 25 (every
surface, its bar, its gap, its owner; Briefs 46 to 55), the design review
UI_MODERNISATION Phase 13 (Briefs 56 to 59), the backend review
WORLD_CLASS 26 (Briefs 60 to 63) and the features pass WORLD_CLASS 27. The deterministic layer under every surface (INBOX 746) is CHAT_PLAN "The deterministic foundation" (decisions 46 to 56, Briefs 64 to 68). The code editor as an IDE (INBOX 748) is DOCUMENTS_PLAN 23 (decisions D1 to D9, Briefs 69 to 71, after 42); the owner's "full improvement" ask (INBOX 749) is the programme already placed, plus learnability measured in UI_MODERNISATION 12z. The owner's trust conditions (INBOX 750) are WORLD_CLASS 28 (rules 1 to 14, decisions 67 to 71, Briefs 72 to 74).
Merged by 14:30Z: 35, 36 to 38, 39, 39b, 42 steps 1 to 4, 56, 72a, 72b, 73,
74, 75, chatui, the filing decision 6 hold on every path, CodeQL (46 alerts on
the day, all at cause); by 15:10Z also 65 (the one reader, `ai/recognise.py`
and `GET /read`) and 66 (quick add on five surfaces, 56 of 60 before 65's
fixes: re-run `scratchpad/ui-sweeps/quickadd.js`) and 67 (the validators and
the act registry; its sweep found every Chat send throwing on the pushed head
after a ratchet commit took out a `let` another file read: a ratchet fix is
checked in the browser, not only by the lint), and 47 (search everywhere:
"Find anything" moved into lazy `search.js` with a chat kind, kind chips,
paging, operator help and saved searches; WORLD_CLASS 25a built), and 42's
remainder (python-docx retired, Word round trip with pictures and tracked
changes, four file types, js-beautify, every code command keyed, the grip at
24 px), and 41 (density: the top bar 64 to 44, docks at 28, icon hover on
the glyph, the date picker; Phase 12 steps 1 to 4 and 6). Merged 51 (never lose a note, 16:30Z); 60, 50 and 34's first round by
17:05Z; 68, 77 (rows 1 to 4) and 69 by 17:30Z, pushed as 07048214e with the CI
fixes for c9e9a4ccc's ten red tests. 84 (Atlas everywhere) and 34's second round
(the companion's faces, tail, reduce motion, arms) merged 18:40Z. Running:
70 (the debugger, debug70), 71 (the IDE shell, shell71), 78 (the mind map,
map78), 79 (the OCR workspace, ocr79) and a Sonnet cifix agent on the 21
tests CI found red on 1fdf9d50d (brief-cifix.md). Next: 85, 89, 90, then 76
after 71, 87 and 88 after 84's merge settles, 80 to 83; Sonnet 53 when load
allows. Brief 75's script and ratchet already exist; its placed rows run
inside each surface's brief. The PR merges when the gate,
the sweeps and one full suite run are green.

**A trap the batch merge paid for (2026-10-10).** `scripts/gate.sh` runs the
lint set, not the ratchets: six agent squashes gated green and CI then failed
17 suite ratchets (`test_global_scope_ratchet`, `test_list_limits`,
`test_feature_catalog`, `test_error_toasts`, `test_prefs_module`,
`test_vendor_utilisation`, `test_a11y_wcag22`, the Quick access and tag
tests) plus 11 filing tests on a hold that read "Dad Jokes" as Relationships.
Before pushing a batch, run `gate.sh --changed` (the tests that name the
changed files) or the ratchet files above by hand; the lint gate alone is
not a merge gate for a batch.

**Now (2026-10-07, main, 0.4.1 complete):** everything since PR 167 is on main
and folded into CHANGELOG 0.4.1 (composer voice and vocabulary, background
progress, auto-install refusal and rollback, composer brief for a running
model). The owner re-tags `v0.4.1` at main's head. Next PR, in order: the
composer's `voice="help"` and the Guide through it, Chat's missing follow-up
chips, composer follow-ups while a model runs
(`agent-remaining/composer-voice-1006.md`); then `wip/composer-acts`
(`composer-acts-1006.md`), the composer-everywhere screens
(`composer-everywhere-1006.md`), `composer-model-1006.md`,
`bgprogress-1006.md` (autonomous pass with no model, night pairing speed),
`autoinstall-1006.md`; then WHITEBOARD_PLAN "Placed from INBOX, 2026-10-07" (edge arrows on rotate, resize and drag; template connectors following their shapes; Reset style), DOCUMENTS_PLAN's live code blocks with completion, the Windows installer's frozen optional-packages step (`windows-packaging-1005.md`), then INBOX 727 to 745.

**Now (2026-10-06, PR 167, 0.4.1):** 0.4.1 is ready to merge from
`claude/mini-release-0.4.1` (forgot-password flow plus INBOX 663 to 726). Next
session, in order: INBOX 727 to 736 (Ask search indicator, missing similarity
numbers, composer answer polish, filing without a model, Guide failure with a
model, reminders magic add, p5 documents and code completion, output panel
resize); then CHAT_PLAN Phase 5 and the composer decisions 17 to 29, measured on
the 725 eval. The owner tags `v0.4.0` on main and then `v0.4.1` after merge.

**Now (2026-10-06, PR 162):** release 0.4.0 is ready to merge: version
bumped (`__version__`, pyproject, README, every `?v=` stamp), CHANGELOG
`[0.4.0] - 2026-10-06` with a Highlights block (release.yml cuts the notes
under 120,000 bytes with a link), CI green on every job including the 49
E2E browser tests and the Windows install/upgrade/uninstall. Final scan:
`agent-remaining/final-scan-1006.md` (5 open, none blocking). After the
merge: tag `v0.4.0` on main; then the next PR from ROADMAP's top block
(OneNote ideas and meeting notes, the code editor, the rest of 641).

**Before that (2026-10-03 night, PR 162):** merged since evening: Library pages and
whiteboard/mind map audits (445), job last-run status (438), note making
(434: Quick note Alt+N, offline outbox, paste/drop, `#tags`), mind map undo
follow-ups, UI consistency pass 1 (Chat, Graph chrome, Dashboard, Timeline,
Reminders, Settings jobs) and the zoom sweep: every tab 0 at 200% and 400%
(433 resolved). Running: UI consistency pass 2 (Settings shell, Reminders
phone, Library, Notes and Documents chrome, Opus). Next: refresh
`docs/screenshots` with `readmeshots.js` after pass 2 (today's density pass
made them stale), then 437 and 434's open parts. `gate.sh --staged` now
includes the gzip boot budget (CI went red by 141 bytes once). Gate with
`grep -q "^failed:  none"` before every commit. `smoke.js`,
`selmenu-items.js` (removed 2026-10-12, recoverable from git history), `captureaudit.js` are the quick feature checks; run
`zoom.js` one tab at a time (`ONLY=`).

**Before that (2026-10-03 morning, PR 162, branch `claude/notes-flow-rebuild`):** the note
flow (INBOX 432, in HISTORY "INBOX resolved, 2026-10-03") is fixed end to end
and measured; a real model runs in the sandbox (`scratchpad/llama-dev.sh`,
llama.cpp built from source, Qwen2.5-1.5B), so drive the popup agent and
filing against it before claiming either works. Open after it: INBOX 431
(5) companion stacking, (6) graph default forces, the companion motion
work, then 430. Then, as before:

**Before that (2026-09-27, v0.3.3 released from `fix/gemini-fixes-5`, PR 157):** start the
next PR from the "Carry-over to the next PR (0.3.4)" list at the top of
[`archive/agent-remaining/wrapup-0927.md`](archive/agent-remaining/wrapup-0927.md), item 1
first (the `frontend/js/` move).

**A trap this session paid for, keep it.** In the shared worktree,
`git add <file>` stages the *whole* file, including whatever an agent has
half-written in it. Doing that to `frontend/index.html` committed an
agent's mid-step removal of `#entry-document` without the matching handler
removal in `app.js`, so a top-level `addEventListener` on a null element
aborted the whole of `app.js`: `initAuth` never ran, the lock overlay never
came out of `.hidden`, and the E2E suite failed on
`waitForSelector("#lock-password")` with the element present but hidden 35
times over 15 seconds. The app did not boot at all on that head. Stage by
hunk, or commit only files no agent holds, and run `scripts/gate.sh
--staged`, which exists because of this: it runs the lint set against the
index rather than the working tree. `test_frontend_ids.py` was already in
the lint set and already checks that every `$("id")` exists in the markup;
it passed, because the gate was reading the working tree, where the pair
was still whole. Proven on the same shape afterwards, with the break staged
and the working tree clean: `lints` passed and `staged-lints` failed,
naming the missing id.

**And its twin, learned the same hour, in the other direction.** A staged
file is not yours either: `git add` leaves it in the index, and the next
agent to run a plain `git commit` in the shared worktree takes it. The
`--staged` change above landed inside an agent's commit `3ef6b9b` ("The
line numbers go away with the box they number") for exactly that reason,
which is why that commit also carries `scripts/gate.sh`, `CLAUDE.md` and
this file. The content is right and the attribution is not; rewriting a
shared branch's history to fix that would cost more than it is worth.
**Stage and commit in one step, and never leave the index populated.**
In practice that means `git commit -m ... -- <paths>`, which commits
those paths directly and leaves the index alone, rather than `git add`
followed by `git commit`. It happened three times in one evening before
the habit changed, each time putting the orchestrator's work inside an
agent's unrelated commit: `scripts/gate.sh` went in with a preview
gutter fix, and `ai/learning.py` with a picture-card note. Nothing was
lost either time, and the history now says things it does not mean,
which is its own slow cost when the next session reads it. The same three symptoms in the
console are the signature: one real error, then `X is not defined` and
`Cannot access Y before initialization` from everything declared after it.

## How to proceed after PR 149 (the owner asked, 2026-09-14)

The full answer is `docs/ROADMAP.md`, "How to proceed after PR 149",
written for PR 144 and brought forward on 2026-09-20: the plan table with where each plan stands,
the ordered queue (speed budget H7, the professional-use block BACKLOG
115, `agent-remaining/OPEN.md` surface by surface with each plan's open
phase, UI Phase 11, then WORLD_CLASS_PLAN 18's horizon H1 to H8), and the
rules that do not change. In one breath: every open item now lives in
exactly one of INBOX (the owner's reports), `OPEN.md` (what the agents
left, 134 bullets by surface), a plan's open phase, or BACKLOG; nothing
open lives in HANDOVER or HISTORY. A session starts by reading CLAUDE.md,
this file's standing orders and Now line, INBOX, then `OPEN.md` and the
plan for the surface in hand. Brief 33 in SESSION_BRIEFS is the next
session's brief.

**Now (2026-09-26, 0.3.3 released on the branch, Opus orchestrating): INBOX
426 is built and closed, and the docs say so.** The round: Atlas redrawn to
the owner's reference sheets in two looks with moods and poses, the corner
companion (it perches on any panel, rides with it, reacts, and can be a
character of your own), a face for every person, optional sign-in on this
computer, the Documents toolbar and focus-mode fixes, Library Activity, the
tour's per-frame follow, the `--accent-text` token, and the app.js split
into 23 files (warm boot about 28ms slower, cold the same, 3.6% more bytes on
the wire). The README has Atlas at its title and 25 screenshots retaken on
this head (`readmeshots.js`, `atlasreadme.js` (removed 2026-10-12, recoverable from git history), `pngshrink.py` (removed 2026-10-12, recoverable from git history)).

**Next:** INBOX 427, the owner's two calls (Atlas's anatomy after rounds 3
and 4; the companion's pin near an edge). Then `agent-remaining/OPEN.md`,
"Left by the 0.3.3 agents", top down (the two the README pass found, the
agent's Atlas head and the heading-case rule, are both fixed).

**The 2026-09-21 Now blocks** (the app saying true things about itself; the
guided tour's third fix, CI's cancel-in-progress, the unsigned commits) are
in HISTORY.md, "Moved from HANDOVER, 2026-09-26".

**Previously (2026-09-19 night):** moved to HISTORY.md, "Moved from HANDOVER, 2026-09-21 (third pass)".

**Previously (2026-09-14 midday):** moved to HISTORY.md, "Moved from HANDOVER, 2026-09-21 (third pass)".

**Previously (2026-09-14 early and 2026-09-13 night):** moved to HISTORY.md,
"Moved from HANDOVER, 2026-09-21 (second pass)".

**Previously (2026-09-13 evening and midday):** moved to HISTORY.md, "Moved from HANDOVER, 2026-09-21".

**Previously (2026-09-13 morning to midday):** moved to HISTORY.md, "Moved from HANDOVER, 2026-09-13 night".

## Earlier sessions

The session-by-session record that used to follow here (12k lines) is in HISTORY.md under "HANDOVER archive, 2026-09-09". This file is the current state only.
