# Tessellate: read this first

Tessellate (formerly MemoryMap AI; the package, env vars and data folder
keep the old name where existing installs depend on it) is a 100% offline,
local-first notebook where a local AI files your notes and answers
questions about them. Python and FastAPI backend, vanilla JS
frontend, SQLite. No build step: `frontend/js/*.js` and `frontend/css/*.css`
are served as-is.

This file is the operating manual for any session, human or model. It is
short on purpose; the detail lives in the files it points at. Section and
standing-order numbers are cited from code comments, so they stay fixed.

## 1. Before you build anything

**Check the running app first.** Rebuilding something that already exists is
this project's most expensive recurring mistake: three sessions did it, and
one roadmap audit found four of six "quick wins" already done. `grep` first.

**"Already exists" is not "is good enough."** A flagged thing may be present
and still wrong: the wrong shape, a missing case, clumsy, visually
inconsistent. Read the report against what actually renders or runs and say
whether it meets what was asked.

**Reasoned UI is not observed UI.** The owner: "A session that forgets this
will report UI work as done when it's untested." Drive the app with Chromium
and Playwright (section 5), measure, and say plainly what you could not
verify.

## 2. Standing orders

Work lands on `main` by pull request, from the branch the session was
given. (The old integration branch `claude/notes-flow-rebuild` no longer
exists on the remote.) These are the owner's rules; the reasons and the
latest dated additions are in the block at the top of
[`docs/roadmap/HANDOVER.md`](docs/roadmap/HANDOVER.md). When the two
disagree, the most recent dated entry wins.

1. **"Continue"** (or the owner's usual prompt: review the docs, do the
   top-priority, most impactful work autonomously and token-efficiently,
   scan for bugs, keep docs current) means: read this file, the HANDOVER
   block and its "Now" line, and `docs/ROADMAP.md`'s opening table; merge
   any agent worktree with commits not on the branch; then work, in order,
   `docs/roadmap/INBOX.md`, `docs/roadmap/agent-remaining/*.md`,
   `docs/roadmap/SESSION_BRIEFS.md` Briefs in order, the plan phases in
   ROADMAP order, then ROADMAP's live list and BACKLOG by impact. Do not
   wait for a prompt or ask permission for work inside the plans.
2. **Mid-work drops** (a screenshot, a bug, a request, a usage figure) go
   into `INBOX.md` verbatim and are triaged at the next step boundary in one
   pass. Finish the step in hand to standard first, and never lose the
   HANDOVER "Now" line to the pile. A usage figure means commit and push
   now, then continue more tersely. INBOX is a tray, not a backlog: under
   twenty items (a lint checks). A triaged item is fixed now and moved to
   HISTORY, or placed in its plan's "Placed from INBOX" section.
3. **Decisions are not remade.** Every plan has a "Decisions made" section.
   A missing decision becomes an INBOX entry with a one-line
   recommendation, which is then taken.
4. **Agents.** Route by the rungs in section 8: Haiku for lookup and
   mechanical labour (searches, triage, lints, copy moves, fixture edits,
   doc placement), Sonnet for implementation (named bugs, bounded features,
   sweeps), Opus for design judgement (frontend layout and visual work,
   plan phases, backend moves against their spec tests, plans and specs,
   risky reviews). Fable is opt-in only: no routing, escalation, hook,
   skill, agent, retry or scheduled task may start it; use it only when
   the owner names it for a task, and only for that task. The agent cap is
   the tier line at the top of HANDOVER; if unsure, take the lower
   number. Each agent gets its own worktree, port and data dir. Its first
   step is `git merge --no-edit -q <working branch>`, because a worktree can
   be cut from an old base and a reset is refused. It commits per step and
   at least every 20 minutes, so a usage limit never loses work, and writes
   its remaining list before stopping. The orchestrator merges, gates and
   pushes. Every brief begins with `docs/roadmap/agent-remaining/agent_common.md`
   and the `orient` skill.
5. **Quality does not drop with the model.** Tests first, measure before
   claiming, one commit per step, push per batch, five-line reports
   (status, commits, numbers, not verified, found-not-fixed).
5a. **Speed without losing quality.** None of these trims a measurement.
   - After each step, run the targeted tests for the files touched plus
     the lint set: `scripts/gate.sh --changed` for the orchestrator,
     targeted tests run serially plus `gate.sh --staged` for agents.
   - **The full suite is not routine.** CI runs it on every push. Agents
     never run it (four cores; parallel agent suites pushed load past 100).
     The orchestrator runs it at most once, alone: at the end of a session
     before the PR closes, before a large agent task's final report, or
     when a change touches what targeted tests cannot see (migrations, the
     event bus, conftest). Never per step, never per merge.
   - A brief names the files, selectors, line areas, the plan's measured
     numbers and the sweep script to run, so the agent starts at the change
     rather than re-reading the codebase.
   - Agents that land close together are merged and gated in one pass
     (sweeps, push once). Skipping the sweeps is what caused the "fixed
     again" rounds.
6. **Copy:** sentence case; no em-dashes anywhere (a lint fails the build);
   no "Oops", no exclamation marks; one line of description per section,
   longer help behind a `data-help-for` '?' popover.
7. **CI red is fixed the same hour.** CodeQL comments are bug reports: fix,
   push, resolve the thread. The hourly check-in (`send_later`) re-arms
   at the end of a turn only while an agent runs or a PR waits, with these
   orders in its prompt, and stops after 3 empty check-ins: each one
   rewrites the whole context into the cache.
8. **No new plan documents.** A new need is a brief row in the plan it
   belongs to, or an INBOX entry.
9. **Commit trailers** on every commit: the `Co-Authored-By` and
   `Claude-Session` lines the session supplies. No model identifiers in
   commit bodies, PR bodies or code.
10. **Documentation hygiene, enforced by lints.** A plan holds open work
   only. When a phase or step is built, its "Built" block moves whole into
   `HISTORY.md` ("Moved from the plans") at that step boundary, leaving a
   one-line pointer; `tests/test_plan_hygiene.py` fails otherwise, and when
   `HANDOVER.md` passes 600 lines (the session record goes to HISTORY).
   `tests/test_readme_freshness.py` checks the README's tool count, skill
   count, version and mode names against the code. Every merge ends with:
   CHANGELOG line, README if a number or name moved, INBOX entry resolved
   (`python scratchpad/inbox_resolve.py <n>` moves it to HISTORY's "INBOX
   resolved"; the lint fails on a "Fixed" item left in INBOX), the plan's
   Built block moved.
11. **New UI comes from DESIGN.md's recipe index**, never from scratch: a
   menu is `kebabMenu`, a bar is `.dock`, help is `data-help-for`, a blurred
   surface is on the glass-off list, spacing and radius are tokens. A need
   the index does not cover gets its recipe and its lint in the same commit
   as the feature. `tests/test_ui_recipes.py` holds the ratchets. The
   owner: "all the ui issues ... happen when new features are added or
   changed because you don't follow design.md".
12. **Concise style, to save tokens**, for the orchestrator and every
   agent: no preamble, recap or narration; terse status lines; bullets over
   prose; five-line reports; briefs that name files and numbers rather than
   explain.
13. **Help moves with the UI.** A commit that adds, moves, renames or
   removes a control updates, in the same commit, every help surface that
   names it: the `data-help-for` popovers, Settings, Help, the Guide's
   topics (`ai/help_chat.py`, `ai/help_topics_more.py`) and the manual paths
   (`tests/test_manual_parity.py`). Briefs say so; merges check it.

## 3. Where things are written down

Start with [`docs/ROADMAP.md`](docs/ROADMAP.md): its opening table says
which roadmap files are plans, which are reference, and which are
superseded. Then:

| File | What it answers |
| --- | --- |
| [`docs/roadmap/HANDOVER.md`](docs/roadmap/HANDOVER.md) | The standing orders' latest additions, the orchestrator block, the "Now" line, plan progress, the agents table and merge recipe, the last session's traps. |
| [`docs/roadmap/INBOX.md`](docs/roadmap/INBOX.md) | The owner's mid-work findings, placed. Bugs first. |
| [`docs/roadmap/SESSION_BRIEFS.md`](docs/roadmap/SESSION_BRIEFS.md) | The operating protocol (section 0) and one complete brief per session. |
| [`docs/roadmap/WORLD_CLASS_PLAN.md`](docs/roadmap/WORLD_CLASS_PLAN.md) | The consistency contract with a lint per rule, competitor gaps, frontend dossiers, backend moves, security review, flaw classes with commands, execution order. |
| [`docs/roadmap/UI_MODERNISATION_PLAN.md`](docs/roadmap/UI_MODERNISATION_PLAN.md) | Phases 0 to 9 of the UI work. |
| [`DOCUMENTS_PLAN.md`](docs/roadmap/DOCUMENTS_PLAN.md), [`GRAPH_PLAN.md`](docs/roadmap/GRAPH_PLAN.md), [`TIMELINE_PLAN.md`](docs/roadmap/TIMELINE_PLAN.md), [`WHITEBOARD_PLAN.md`](docs/roadmap/WHITEBOARD_PLAN.md), [`CHAT_PLAN.md`](docs/roadmap/CHAT_PLAN.md), [`MINDMAP_PLAN.md`](docs/roadmap/MINDMAP_PLAN.md), [`AGENT_SKILLS_REFORM.md`](docs/roadmap/AGENT_SKILLS_REFORM.md) | One plan per surface: what exists, why it disappoints (measured), target, decisions made, gated phases, not verified. |
| [`docs/roadmap/agent-remaining/`](docs/roadmap/agent-remaining/) | OPEN.md, the consolidated ledger, plus one file per running agent; finished ones are in `docs/roadmap/archive/agent-remaining/`. |
| [`docs/roadmap/HISTORY.md`](docs/roadmap/HISTORY.md), [`BACKLOG.md`](docs/roadmap/BACKLOG.md), [`ANALYSIS.md`](docs/roadmap/ANALYSIS.md), [`MODERNISATION_AUDIT.md`](docs/roadmap/MODERNISATION_AUDIT.md) | What is built (with every retraction), the standing backlog, judgements and competitor reads, the measured audit. |
| [`docs/DESIGN.md`](docs/DESIGN.md) | The design system; `tests/test_style_scale.py` fails the build otherwise. |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How the pieces fit. |
| [`.claude/skills/README.md`](.claude/skills/README.md) | The one vendored design skill (`ui-ux-pro-max`); `docs/DESIGN.md` overrides it for anything in `frontend/`. |

**Licence:** this project is AGPL-3.0. AGPL or MIT code may come in with its
notices; nothing may go out to an MIT project (details in ANALYSIS.md).

Section numbers (`§21`) in code comments resolve through HISTORY.md's index;
`tests/test_docs_layout.py` enforces the cross-links.

## 4. The standing caveat

**Every provider test runs against a fake transport.** Plain SSE streaming
and one streamed tool call are verified against a real socket
(`scratchpad/fake_openai_server.py`). Real inference, concurrent tool calls
at index 1+, Ollama's native tool-call dialect, and every claim about how a
real small model responds to a re-prompt are not. When something is
reported broken, reproduce it before theorising, and say plainly when you
could not.

For real-model checks, `scratchpad/llama-dev.sh serve` starts a small local
model and prints `TESSELLATE_EVALS_URL` and `TESSELLATE_EVALS_MODEL`;
`pytest -m evals` then runs the tests that need one. Without those variables
every `evals` test is skipped, and `tests/test_skills_evals.py` asserts the
suite and `scripts/gate.sh` never reach for the script.

## 5. Running and verifying the app

```bash
# setsid, not plain &: pkill -f uvicorn kills your own shell here (exit 144).
# One server per data dir; never put `kill $(pgrep ...)` and a setsid start
# on the same shell line.
bash scratchpad/ui-sweeps/serve.sh 8781 /tmp/mm-me
# or:
setsid env PYTHONPATH=src TESSELLATE_DATA_DIR=<scratch>/appdata \
    .venv/bin/python -m uvicorn tessellate.api.app:create_app \
    --factory --port 8781 > <scratch>/server.log 2>&1 < /dev/null &
# then drive it: node script.js, requiring
# /opt/node22/lib/node_modules/playwright, with PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
```

Sweeps live in `scratchpad/ui-sweeps/` (`lib.js` boot, `errors.js`,
`contrast.js`, `docks.js`, `touch.js`, `chrome.js`, per-surface sweeps).
Password `testpassword123`; `THEME=dark` for dark.

**Traps, each worth an hour:**

- `waitUntil: "networkidle"` never settles (the app polls); use
  `domcontentloaded` plus `waitForTimeout`.
- The login is one field in two modes: fill `#lock-password`, click
  `#lock-submit`.
- A screenshot you look at is not a measurement. Use `getComputedStyle`,
  `getBoundingClientRect`, `scrollHeight` vs `clientHeight`, and
  `scratchpad/pngpixel.py` for colour. Never close a visual report as a
  capture artifact without a number.
- A value that is invalid where it is used, not where it is set, does its
  damage far from its cause (two missing appearance defaults once wrote
  `NaN` into CSS and flattened every card in the app).
- Two appended CSS sections merged can drop a `}`; only
  `tests/test_css_braces.py` sees it.
- The Bash tool times out at 120s; run `errors.js` in the background.
- Restart the server after any Python change: a stale uvicorn is why a
  correct fix "did not work" twice.
- Local `css`/`js` URLs are stamped `?v=<version>-<file hash>` (`_stamp_for`
  in `src/tessellate/api/app.py`; `tests/test_asset_cache_busting.py`), so
  the persistent desktop webview profile always fetches edited files. A
  report that keeps coming back on a current head is a real bug or a bad
  interaction shape, not a cache: reproduce it.
- A test that runs a script able to delete things (the uninstallers, the
  launcher's `--reinstall`) runs it in a scratch copy, never with
  `cwd=ROOT`; one such test once deleted the sandbox's `.venv` mid-suite.
  `tests/test_launcher_scripts.py` has the guard fixture.
- CodeQL reads `scratchpad/` too: lazy `.*?` over argv paths, unclosed
  `open()`, case-sensitive tag filters and wrong keyword arguments have all
  been flagged there.

## 6. Reviewing work that came from somewhere else

Look for these four shapes first, in this order; they are cheap to check
and expensive to miss:

1. A working thing rewritten into a riskier thing, with no stated reason.
2. A feature that never ran once: grep the call site of anything new.
3. A guard removed while the shape around it was kept.
4. A policy silently refusing the work (inline `style=` is rejected by the
   CSP; use `el.style.x =` or a class).

Run the targeted tests against the base branch first, so "everything else
here is new" is a fact rather than a guess.

## 7. Working here

- **Do not install torch or `sentence-transformers`.** Set up by hand:
  `python3 -m venv .venv && .venv/bin/pip install fastapi "uvicorn[standard]" SQLAlchemy alembic python-dotenv requests numpy "fsspec[http]" bcrypt cryptography python-multipart pytest pytest-xdist httpx ruff defusedxml`
- The suite is about 9,000 tests, all green: under 9 minutes with
  `python -m pytest -n auto tests/` on four cores, about 25 serial. When to
  run it is standing order 5a. `PYTHONPATH=src` is needed to run the app.
- `scripts/gate.sh` is the merge gate in one command: the lint set,
  `node --check`, ruff. `--changed` adds the tests that name files changed
  since `origin/main` (the routine local gate). `--staged` runs the lint set
  against the index rather than the working tree; it is the only mode that
  catches a commit splitting a pair (staging an `index.html` id without its
  handler once stopped the app booting while the working tree passed).
  `--full` adds the whole suite. `BASE=... --sweeps` adds errors, docks,
  contrast and touch against a running app. Run it before every push and
  paste its five lines into the report.
- `node --check frontend/js/<file>.js` after any JS edit; there is no
  bundler. Scripts live in `frontend/js/`; only `frontend/sw.js` stays at
  the root, because a service worker controls only pages under its path.
- **The app's code is 27 classic scripts**, `app.js` through
  `agent-activity.js` in index.html's order, sharing one global scope; a
  file calls only upwards at load. A test that means "the app's code" reads
  `app_js_text()` from `tests/_app_js.py`, never `frontend/js/app.js`
  (now only the head: api, auth, the lazy loader).
  `grep -n "^function name" frontend/js/*.js` finds a function's file.
  `docs/CODEMAP.md` lists every function, id, route, CSS section, module,
  test file and plan heading as `name | file:line`; `python scripts/codemap.py`
  regenerates it, and `tests/test_codemap_fresh.py` fails when it is stale.
- These lints exist because the suite cannot see the DOM:
  `test_style_scale.py`, `test_ui_signatures.py`, `test_css_braces.py`,
  `test_frontend_ids.py`, `test_frontend_handlers.py`, `test_dock_grammar.py`,
  `test_docs_layout.py`, `test_asset_cache_busting.py`, `test_no_em_dashes.py`,
  `test_no_innerhtml_interpolation.py`, `test_markdown_link_schemes.py`. If
  one fails it has found something real: fix the cause, never widen the
  rule.
- The executable specs for the backend moves are strict-xfail tests
  (`tests/test_events.py`, `test_search_engine_spec.py`,
  `test_harness_verifier_spec.py`, `test_learned_spec.py`,
  `test_resurface_spec.py`): remove a marker only when its test passes on
  its own.
- Comments explain why; a comment that restates the code is noise. Prompt
  text is budgeted (`agent.PROSE_BUDGET_CHARS`).

## 8. Token budget

Quality first: never downgrade model or effort for quality-sensitive work
because usage is high. Subagents report a status line plus results, never a
transcript. When usage is low, say so in one line and be terser rather than
silently cutting corners.

**What usage costs.** Every turn re-reads the whole context; cached reads
are cheap per token but are most of the tokens, so cost is turns times
context. `python scripts/usage_report.py` prints the split for a session.
The levers, in order:

- Fewer turns: batch independent tool calls into one response; one brief
  that names files and line ranges beats an agent that searches.
- Less context: start a fresh session at each milestone (the HANDOVER "Now"
  line carries the state); grep, then read line ranges; no screenshots
  where a number will do (an image stays in context every turn after).
- No cold rewrites: a gap over the cache lifetime (about an hour) rewrites
  the whole context at the higher write rate; avoid idle check-ins.
- Cheapest capable rung, escalated on evidence, never by task length.

**Rungs and tiers.** HANDOVER's top line names the tier (`max` or `pro`).

| Rung | Model, effort | Work |
| --- | --- | --- |
| scout | Haiku | lookup, triage, log and test-failure reading, mechanical edits with a runnable check |
| implement | Sonnet high | named fixes, bounded multi-file changes, tests, sweeps |
| judge | Opus medium, high if a lower rung failed with evidence | design, ambiguous bugs, architecture, risky review |

- Orchestrator: Sonnet high by default; Opus medium for a design-heavy
  session. Fable only as section 2.4 says.
- `max`: at most three agents at once, at most one of them Opus. `pro`: one
  agent at a time, no Opus agents, targeted tests only, no check-in loop.
- Tests take a fixed "now" (an injected clock or frozen time), never the
  real clock; a date read at test time is a bug waiting for its day.
- Never weaken a test to make it pass: fix the cause, or change the test
  only when its stated intent moved, and say why in the commit.
- Replace, do not layer: change the existing implementation and remove the
  old path (a re-export, a shim, a flag) unless persisted data or a public
  interface needs it.
- Retries: one per new hypothesis. The same call three times in a row is a
  stop: report the blocker.
- Independent checks on risky or UI changes: `reviewer` (the diff),
  `ux-auditor` (WCAG 2.2, CARP, DESIGN.md), `blind-tester` (the goal and
  URL only). The builder does not grade its own work.
- The `lean-workflow` plugin (its own MIT repo,
  `github.com/Braydenh563/lean-workflow`, README there) is
  this workflow packaged for any repo: autopilot rules, the guards (huge
  whole-file reads, a third identical call, an agent with no model, an
  unrequested Fable agent), context and cold-cache warnings, `/spend`,
  `/dash` and `/prune`. Install once per machine:
  `/plugin install lean-workflow --marketplace Braydenh563/lean-workflow`.
- At session end run the `retro` skill: it measures the session, keeps the
  ledger and changes at most one rule, so the workflow improves across
  sessions on evidence.

**Compact instructions.** When compacting, keep: the HANDOVER "Now" line,
the current task and its acceptance check, failing tests with their
commands, the file paths being edited, the branch and PR number, and any
decision made this session. Drop tool output and exploration that led
nowhere. Long unattended runs work best as one task per session or `/goal`,
state in files (HANDOVER, INBOX, git), verbose work in subagents;
compaction (`autoCompactWindow`, 400k here) is the safety net, not the plan.
