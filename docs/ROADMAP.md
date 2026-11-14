# Tessellate: the work plan

This file is the entry point to the plans. It is short on purpose: the
detail lives in `docs/roadmap/`, and what is finished lives in
[roadmap/HISTORY.md](roadmap/HISTORY.md) (every section number in a code
comment resolves through HISTORY's index). The standing backlog is
[roadmap/BACKLOG.md](roadmap/BACKLOG.md); every open item outside the plans is a row in
[roadmap/LEDGER.md](roadmap/LEDGER.md), and the standing decisions are in
[ARCHITECTURE.md](ARCHITECTURE.md). The licence constraint: this project is AGPL-3.0, so odysseus's AGPL code may
come in with its notices and nothing may go out to an MIT project.

**The standing caveat:** every provider test runs against a fake transport.
Plain SSE streaming and one streamed tool call are verified against a real
socket (`scratchpad/fake_openai_server.py`); real inference, concurrent
tool calls, Ollama's native tool-call dialect and every claim about how a
real small model responds are not. UI claims are checkable (Chromium is in
the sandbox); model behaviour claims mostly are not. Reproduce, or say
plainly that you could not.

The sections this file carried from earlier sessions (the three "start
here" blocks, the older live list, §87 to §90, the four tiers) are in
HISTORY under "ROADMAP archive, 2026-09-14", verbatim. Everything still
open from them is in the plans, `roadmap/LEDGER.md`, or
BACKLOG; nothing was dropped in the move.

## Direction, 2026-10-10 (Fable orchestrating): the thesis, the policies, the tracks

The owner's ask, condensed: judge the Gemini branch, fix every bug of every

**Release, the owner 2026-10-10 (INBOX 765): "Public release now".** The release track runs beside the feature tracks from here: installers for Windows (built in CI already), macOS and Linux, a GitHub release per version with the changelog, a landing page from the README, and the phone path (an installed web app over the owner's Wi-Fi) inside it. Nothing ships with a known data-loss path or a red trust rule (WORLD_CLASS 28.1).
size (the 2026-10-10 list, INBOX 727 to 745, HANDOVER's next-PR list), use
the vendored and forked repositories well, make the deterministic engine
(composer, filing, understanding) something no notebook has, modernise and
professionalise the UI again, keep the app light on old hardware, and lay
out the direction for everything after. This section is that direction;
the surface plans carry the phases it names; LEDGER.md's plan session
briefs are the agent briefs. Decisions here are taken (standing order 3).

### The thesis

Tessellate is a local-first second brain whose intelligence is **two
engines, one answer**: a deterministic engine that always runs (reads,
files, links, answers, acts, explains; every sentence traced to a note or a
measurement) and an optional local model that adds fluency and judgement
when it is there. The deterministic engine is the product; the model is an
accelerator. Everything else (boards, maps, documents, graph, timeline,
companion) is a surface onto the same notebook and the same engine.

### Policies (taken 2026-10-10)

1. **Vendoring.** Pure Python or plain JS/WASM, offline, small, licence
   file beside it, listed in `docs/THIRD_PARTY.md` (a lint checks the
   list). No compiled extensions, no binaries, no package copied whole
   when two functions are used, no dependency added for what the stdlib or
   the app already does (difflib before thefuzz; the app's trigram repair
   before pyspellchecker). The Gemini branch's networkx, whoosh, pint,
   langdetect, dateutil and friends go; flashtext, porter stemmer and
   simpleeval (or an ast evaluator of our own) stay only where a test shows
   the gain. Import time of `tessellate.ai.composer` is a measured budget
   (under 0.5 s); boot gzip is a measured budget (`test_static_compression`).
2. **The forks.** The ArtCraft suite (storytold/wordcraft, designcraft,
   deckcraft, gridcraft, photocraft, lightcraft, pdfcraft, soundcraft,
   filmcraft; Rust and egui compiled to WASM, MIT or Apache-2.0) does not
   fit a no-build vanilla JS app: multi-megabyte WASM, GPU canvas, no DOM
   for accessibility or theming. It is a source of feature lists, command
   catalogues and file-format handling (docx, pdf, xlsx read and write) to
   learn from, not code to vendor. draw.io (Apache-2.0, JS) stays what it
   has been since HISTORY §53 and BACKLOG 29e: the reference for anchors,
   orthogonal routing, the shape library format (its stencil XML can be
   converted offline to our shape JSON) and the format panel. haifengl/smile
   is Java: its algorithms (clustering, keyword extraction, association
   rules) are read for ideas and re-implemented small in Python only where
   a measured need exists. NLTK and WordNet are too heavy as shipped; a
   trimmed synonym table from the Perplexity pack and the app's own groups
   is the substitute, measured on the eval. Brief 40 does the research pass
   once and records it in ARCHITECTURE.md.
2b. **Taken, not transplanted** (the owner, 2026-10-10: "anything coming
   from repos like draw.io not directly the same but truly part of this
   app and uniquely fitted and redesigned and altered to be part of this
   app"). What a reference gives is the behaviour and the data (a mechanic's
   thresholds, a shape library, an algorithm); what Tessellate gives is the
   form: DESIGN.md's recipes, tokens and copy, the notebook's object model
   (a shape can hold a note, a connector can be a link with a reason, a
   board can be filed and cited), and the keyboard and help conventions of
   the rest of the app. A ported feature is done when a person who knows
   draw.io recognises how it behaves and a person who knows Tessellate
   recognises how it looks and where it lives. No reference's panel, icon
   set, menu structure or copy is reproduced; a converted asset (a stencil
   set) is restyled to the board's tokens (stroke, radius, palette) at
   load. Each parity row therefore has a "fitted as" column before it is
   built.
3. **The taxonomy pack** (Perplexity, "MemoryMap final consolidated <!-- brand: keep, a document title -->
   taxonomy pack", 5.0.0: 527 categories, 6,478 keyword assignments, 1,109
   role concepts, facets, 30 context rules as a spec, 64 passing lexical
   tests) is adopted as **seed data**, not as the classifier: its JSON
   files load lazily, FlashText generates candidates, and the app's own
   scoring (the person's categories, centroids over the embedder when it
   runs, TF-IDF votes, recency) decides. Its facet model (topics,
   purposes, entities, actions, events, assertion mode, temporal scope) is
   the data model for the engine's fact layer. WORLD_CLASS_PLAN section 23.
4. **The composer is Atlas.** One voice, one identity, one memory of the
   conversation, whether or not a model runs; the bubble says which engine
   wrote it. CHAT_PLAN Phase 6.
5. **Modernisation is density and intent**, not decoration: smaller,
   intentional controls on a 4px grid, hover on the icon rather than a box
   behind it, one radius per control class, WCAG 2.2 AA throughout
   (24px targets, visible focus, no drag-only actions), custom pickers
   where the browser's are out of place. UI_MODERNISATION_PLAN Phase 12.
6. **Agents.** At most four at once, mainly Opus; Sonnet for named fixes,
   lints, docs and sweeps; never Fable. Every brief names files, numbers
   and the sweep; every merge is gated and measured.

### The tracks, in order (each a brief; the agent model in brackets)

| # | Track | Brief | Plan |
| --- | --- | --- | --- |
| 1 | Gemini branch triaged: boot fixed, unused vendoring stripped, grounding back to 1.0, credits file | 35 (Opus) | this section |
| 2 | Whiteboard and mind map bugs and the owner's list | 36 (Opus) | WHITEBOARD_PLAN, MINDMAP_PLAN |
| 3 | Chat, Ask, first run, model gating, the owner's UI bugs | 37 (Opus) | CHAT_PLAN, UI_MODERNISATION_PLAN |
| 4 | Graph views, topics as first-class, note properties | 38 (Opus) | GRAPH_PLAN |
| 5 | The deterministic engine: fact layer, planner, realiser, dialogue state, acts, insights | 39 (Opus) | CHAT_PLAN Phase 6 |
| 6 | Filing and the taxonomy: candidates, decision, explanation, merge suggestions | 39b (Opus) | WORLD_CLASS_PLAN 23 |
| 7 | Research and placement: repositories, forks, Docker, system site-packages, MCP, phone access, the owner's list placed | 40 (Sonnet) | ARCHITECTURE.md, the plans |
| 8 | UI density and refinement, WCAG 2.2, pickers, calendar | 41 (Opus) | UI_MODERNISATION_PLAN 12, TIMELINE_PLAN |
| 9 | Documents: code editor to VS Code standard, highlights and annotations, comments with links, p5 kind | 42 (Opus) | DOCUMENTS_PLAN 21 and 22 |
| 10 | Atlas and the companion: moods that change, gestures, lifelike motion, the enlarged view | 34 (Opus) | LEDGER world-class Atlas rows |
| 11 | Audio: meeting notes apart from dictation, voice memos, live captions; long-form preference at first run | WORLD_CLASS_PLAN "Audio in the notebook" | WORLD_CLASS_PLAN |
| 12 | Packaging: Docker image, reuse of system Python packages, installer's optional packages | 40 then 17 | BACKLOG |
| 13 | The code editor as an IDE: run, preview and test for TypeScript, SQL, CSS, SVG and p5; the Python and JavaScript debuggers; the panels, consoles and palette | 69 to 71 (Opus), after 42 | DOCUMENTS_PLAN 23 |
| 14 | Learnability measured on a fresh profile (time to a saved note, tour targets, help coverage, Guide answers, shortcut discovery) | 41 (Opus) | UI_MODERNISATION_PLAN 12z |

### After the bugs: the parity programme (the owner, 2026-10-10)

The owner's words: "after all bugs are fixed, expand and improve all the main
features and integrate all features better together, restructure and redesign
ui where it suffers, expand tools and utilities, maximise modernisation and
professionalisation. make the app reliable to use and not like a demo or beta.
use my forked repositories as my whiteboard and mindmap and documents editor
definitely still arent up to par with them, like the open source alternatives
to adobe and microsoft applications, draw.io, vs code and more."

Taken as a programme, in this shape:

1. **A gap matrix per surface against a named reference**, written before
   any building (Brief 40 produces it in ARCHITECTURE.md from each fork's feature
   list and command catalogue, then each surface's Opus brief carries its
   rows): whiteboard against draw.io and designcraft; mind map against the
   best of Coggle, XMind and Whimsical (MINDMAP_PLAN's research) plus
   designcraft's canvas; documents against wordcraft and VS Code (prose and
   code); tables and the data in notes against gridcraft; the PDF viewer and
   OCR workspace against pdfcraft; image notes and the Library against
   photocraft and lightcraft; audio notes and meetings against soundcraft;
   presentations from boards and maps against deckcraft. Each row: the
   feature, whether Tessellate has it (checked in the app), the gap, the
   cost, a keep or drop.
2. **Integration before breadth**: a board, a map, a document, a note, a
   reminder and a web clip are one object model with one properties panel,
   one comments system, one link card, one slash menu, one export menu and
   one search; a feature built on one surface lands on all of them through
   the shared recipe or not at all.
3. **Reliability as a gate**: the full suite, the sweeps and a 30-minute
   scripted session (deepflows.js) green on every merge (CI's UI sweeps job,
   `scripts/ci_sweeps.sh`: 61 steady sweeps and 10 deepflows flows; the rest
   are L-ui-modernisation-75); no console error on
   any surface; a cold boot under the measured budget; "not a demo" means
   every empty state, error state and first-run state is designed and
   measured (WORLD_CLASS_PLAN 21 and 22).
4. **Order**: bugs (Briefs 35 to 38), the engine (39, 39b), density and
   WCAG (41), then the matrix rows by surface in the order the owner named:
   whiteboard, mind map, documents, then the Library, audio and
   presentations.

### The road to 1.0: milestones with exit criteria (the owner, 2026-10-10: "still very much a demo and beta")

What "publishable" means here, as gates a build either passes or does not.
Each milestone is a release; nothing below it ships with a visible
half-feature (an unfinished feature sits behind a flag, off by default,
not on a menu).

| Release | Theme | Exit criteria, every one measured |
| --- | --- | --- |
| 0.5 Reliable | the app never loses, lies or stalls | Brief 43's nine probes green: backup and restore round-trip equal on 500 notes; every export re-imports; migrations from 0.3.0; zero silent failures when the server dies; zero console errors on any surface; keyboard-only completion of every surface; axe clean; boot under 2.5 s at 4x throttle; idle CPU under 1 percent; offline run makes no outbound request; auth on every write route; CI green with no xfail newly added |
| 0.6 Engine | the deterministic engine is the product | CHAT_PLAN Phase 6 steps 1 to 10 built; grounded 1.0 on every eval set; measured sentences 1.0; a 20-turn session with no repeated template; acts for the twelve verbs with confirm and undo; filing top-1 at or above 0.8 without a model on the 120-note fixture, every filing explained; the Guide and Chat one engine; a blind panel rating at or above the 1 to 3B model's on the owner's notebook |
| 0.7 Surfaces | boards, maps, documents, graph at parity on what matters | the "build first" rows of every parity table in the plans built; one object model (properties, comments, links, slash menu, export, search) across note, board, map, document, reminder and clip, with a test that walks all six; the whiteboard regression suite and map sweeps green; documents' code editor at DOCUMENTS 21's bar |
| 0.8 Design | one system, dense, accessible | UI Phase 12 complete: the density tokens with no literal heights outside them, the hover grammar lint, one radius per class, the axe sweep clean on every surface at 1440, 1024 and 390 in both themes, custom pickers, the calendar mode, metadata rows unified; the README screenshots recaptured last |
| 0.9 Public beta | strangers can install it and come back | Windows, macOS and Linux launchers and the Docker image each installed on a clean machine by someone who is not the owner, timed, with the first-run queue measured (no overlaps, the tour on request); the phone over HTTPS trusted by the QR and guide flow on iOS and Android; the update path from 0.8 with data in place; a crash and feedback channel that is local and opt-in (a bundle the person sends by hand); ten testers for two weeks, their reports placed and the bugs closed |
| 1.0 | publishable | 0.9's testers report no data loss and no blocker for a month; the full suite, the sweeps and the scripted session green on the tag; THIRD_PARTY.md complete; the manual (Guide topics) covers every control (test_manual_parity); AGPL notices in place; the release notes written for a reader who has never seen the app |

Rules that hold from here to 1.0:

1. **A feature lands everywhere or nowhere.** Built on one surface only, it
   stays behind a flag until the shared recipe carries it to the rest.
2. **Nothing visible is unfinished.** An empty state, an error state and a
   first-run state are part of the feature, not follow-ups.
3. **Every claim has a number.** A plan row without a measurement is not
   done; a report without numbers is not merged.
4. **The model is optional on every path.** Any path that fails without a
   model is a bug, not a limitation.
5. **Weight is a budget.** Boot gzip, import time, idle CPU, memory at 5,000
   notes and the vendor directory each have a measured cap and a lint.
6. **One recipe per need.** A second way to do the same thing (a menu, a
   bar, a picker, a card) is removed in the same PR that notices it.

Order: 0.5 and 0.6 run together now (Briefs 35 to 39b and 43, then
WORLD_CLASS_PLAN 25's Briefs 46, 51 and 53 for 0.5); 0.7 follows the
parity tables plus Briefs 47, 48, 54 and 55; 0.8 is Brief 41 plus Briefs 49
and 52 and the surface briefs' design rows; 0.9 needs Brief 50 and the
owner's testers. The whole-app table (every surface, its bar, its gap and
its owner) is WORLD_CLASS_PLAN section 25.

The owner's 2026-10-10 list is placed by Brief 40 under "Placed from the
owner's list, 2026-10-10" in each plan; INBOX stays under its cap.

## Next up: retired queues, now the ledger and HANDOVER

"Next PR, first" (2026-10-05), "How to proceed after PR 149" (2026-09-14) and "Next up, ranked" were open-looking queues. Their text, with the owner's words, is in `roadmap/HISTORY.md`, "Moved from the roadmap, 2026-11-12". What was still open is in `roadmap/LEDGER.md` and the plans; the live order is CLAUDE.md standing order 1 and HANDOVER's "Now" line.

## The plan documents, in one list (read this before opening any of them)

Eleven plans and a handful of reference files live under `docs/roadmap/`.
Work from the plans, in this order; look things up in the rest.

| Work from these (in this order) | Where it stands, 2026-10-05 |
| --- | --- |
| [roadmap/HANDOVER.md](roadmap/HANDOVER.md) | The standing orders, the "Now" line (what is in flight and what its gate is) and the plan-progress table. Read first, every session. |
| [roadmap/INBOX.md](roadmap/INBOX.md) | The owner's open reports, each with an owner. Bugs first. Under twenty items by lint. |
| [roadmap/LEDGER.md](roadmap/LEDGER.md) | Every open item outside the plans and BACKLOG, one row each, tagged by plan, with a paste-in brief per plan session at its end. Rows are added and closed with `scripts/ledger.py`. |
| [roadmap/WORLD_CLASS_PLAN.md](roadmap/WORLD_CLASS_PLAN.md) | The consistency contract (all lints), the competitor gap table, the backend moves and inventions, the security review, section 18's horizon. Every row was read against the code on 2026-09-24 (INBOX 399): the built ones are in HISTORY, each open row carries a "State 2026-09-24" line, and the ranked list of 38 is at the top of section 8. Built since: F3 (`semantic_search` on a matrix), `similar_pairs` cached, S1 to S3, S5 and S6's redirect half; the dev-only llama.cpp runner (section 9, `scratchpad/llama-dev.sh`). Open at the top: Brief 15's LAN hardening tail, B2 durable jobs, D2's connections rail, I1's night runs, chunk vectors then I6's evidence cards. |
| [roadmap/UI_MODERNISATION_PLAN.md](roadmap/UI_MODERNISATION_PLAN.md) | Phases 0 to 11 built (Phase 8's docks re-measured under the ceiling, the phone done properly on 2026-09-20, Phase 10's clear glass variant built on 2026-10-04 as the `--glass-filter-clear` token), plus the Settings information architecture (INBOX 444) and the 2026-10-03 consistency passes. The README screenshot set was retaken on 2026-10-04. |
| [roadmap/DOCUMENTS_PLAN.md](roadmap/DOCUMENTS_PLAN.md) | Phases 0 to 8 built (CodeMirror 6 as the surface, blocks, the connected document, review and history, export, one editor everywhere), plus the slash menus as one system (section 18) and boards and maps as objects in a note (section 19). Open: the Phase 2, 6 and 8 tails, the engine's three deliberate omissions, the bottom formatting bar on a phone. |
| [roadmap/GRAPH_PLAN.md](roadmap/GRAPH_PLAN.md) | Phases 1 to 6 built, the minimap (6b) and the local pane included, and the 2026-10-03 shape work (categories gather, the unlinked on a ring). Open: the `?since=` cursor (nothing polls `/graph` yet) and the local pane's Show switches, left by decision. |
| [roadmap/MINDMAP_PLAN.md](roadmap/MINDMAP_PLAN.md) | Phases 1 to 5 built, and section 12's controls and structure; section 13's render pass met its gate at 500 topics. Open: an outline view beside the map (L), a map-level branch palette and font (13e), a notebook-note node that shows and edits its text (12.2 item 5's second half), and the owner's calls on middle-button and right-drag pan; tasks, notes behind a topic and branch numbering were built on 2026-10-04. |
| [roadmap/CHAT_PLAN.md](roadmap/CHAT_PLAN.md) | Phases 1 to 4 built (Phase 1's grounding closed 2026-09-20 to 2026-09-23, Phase 4's harness items 2026-09-20). Open: the `evals` breadth (WORLD_CLASS_PLAN 9) and the 2026-10-03 chat stutter (INBOX 413) notes. |
| [roadmap/TIMELINE_PLAN.md](roadmap/TIMELINE_PLAN.md) | Phases 1 to 4 built, section 7's two measurements taken (2026-09-20, each found and fixed a bug). The "auto" scale thresholds are tuned (2026-10-04). |
| [roadmap/WHITEBOARD_PLAN.md](roadmap/WHITEBOARD_PLAN.md) | Phases 1 to 4 built. Map boundaries, summaries and presenting by branch built 2026-10-05 (MINDMAP_PLAN decisions 19 to 21); board frames, lock, presenting the frames and comment threads built 2026-10-04 (decisions 14 to 17), Export this frame and nesting 2026-10-05 (decision 18); decision 7, the phone context bar, sketch handles at zoom and the arrange panel were confirmed built and swept on 2026-10-04, with shape text and connector labels added (`scratchpad/wbmap-tails.md`). |

| Reference (look things up, do not start from) | |
| --- | --- |
| [roadmap/HISTORY.md](roadmap/HISTORY.md), [roadmap/BACKLOG.md](roadmap/BACKLOG.md), [roadmap/LEDGER.md](roadmap/LEDGER.md) | What is built (with every retraction), the standing backlog (section 115 is the professional-use block), the judgements, the measured audit. |
| [DESIGN.md](DESIGN.md), [ARCHITECTURE.md](ARCHITECTURE.md) | The design system (lint-enforced) and how the pieces fit. |

## How to work on this repo

- `pytest tests/`: 6,700+ tests, fully offline, no Ollama needed
  (`pytest.ini` sets `pythonpath = src`); ten to fifteen minutes, so the
  routine local gate is `bash scripts/gate.sh --changed` and CI runs the rest.
- `ruff check .`: matches CI.
- `node --check frontend/js/<file>.js`: the frontend is plain JS with no bundler (61 files in `frontend/js/`), so run it on each file you touch.
- **Install non-ML deps by hand** (see root `CLAUDE.md`); do not install
  `torch` or `sentence-transformers`, since both have failed to install cleanly in
  past sessions and the suite passes without them (semantic search falls
  back to keywords; tests that care use a fake embedding backend).
- **Drive the app in a browser before claiming a UI change works.** Chromium
  + Playwright are in the sandbox. Launch with `service_workers="block"` or
  `sw.js` serves a cached `app.js` and you'll be testing yesterday's code.
  Assert on measured geometry (`scrollWidth - clientWidth`), not screenshots.
- **Collect the console while driving.** The app sends a strict CSP; a
  refused style/script/fetch shows up *only* in the console (no failed
  request, no thrown error, the thing just silently doesn't happen).

### Traps that have each cost real time

1. **Don't guess element ids.** Check `index.html` or query generically.
2. **`git checkout <file>` discards uncommitted work in that file.** Commit
   before experimenting.
3. **A POST response can lie about stored state.** SQLAlchemy returns the
   in-memory object; assert on the next GET, not the create response.
4. **`utcnow() + offset` is a lie with a timezone attached.** It tags UTC on
   a value that actually holds local wall-clock. Build the user's clock as
   `utcnow().astimezone(timezone(offset))`.
5. **The Notes tab is sub-tabbed.** Anything that scrolls to a note must call
   `showNotesSection("browse")` first, or it targets an element inside
   `display: none`.
6. **The app sends a strict CSP; a violation is reported only in the console.**
   No failed request, no thrown error. An injected `<style>` tag won't apply
   (use `adoptedStyleSheets`), `style=""` in `index.html` won't apply (use a
   class in one of `frontend/css/*.css`), and a script from off-origin is
   refused outright.
7. **CSS automatic minimum sizing is the usual cause of a wide page.** A
   `1fr` grid track or a flex item with default `min-width: auto` refuses to
   shrink below its content; `overflow-x: auto` on the child does nothing
   until every ancestor has an explicit floor.
8. **A POSIX idiom can mean something else on Windows, silently.**
   `os.kill(pid, 0)` terminates on Windows rather than probing; the sandbox
   is Linux, so this class of bug never reproduces here.
9. **A control that "does nothing" is usually working.** Check the
   *computed* result. Most reported cases wrote correctly and were then
   overridden by CSS source order, a status poll repainting, or living in a
   hidden section.
10. **This suite cannot see any of the above.** Every UI bug this project has
    found passed a fully green test run first.

Full historical detail for every trap above (the original report, the
diagnosis, the fix, and what verification could and couldn't cover) is in
[roadmap/HISTORY.md](roadmap/HISTORY.md).
