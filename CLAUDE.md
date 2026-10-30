# Tessellate: read this first

Tessellate (formerly MemoryMap AI; the package, env vars and data folder keep
the old name) is an offline, local-first notebook where a local AI files your
notes and answers questions about them. Python/FastAPI, vanilla JS, SQLite, no
build step. This is the short manual, loaded every turn; the full text of every
section, with the reasons, is [`docs/WORKING.md`](docs/WORKING.md). Section and
standing-order numbers are cited from code comments, so they stay fixed.

## 1. Before you build anything

- **Check the running app first; `grep` first.** Rebuilding what exists is the
  most expensive recurring mistake here.
- **"Already exists" is not "good enough":** judge it against what renders.
- **Reasoned UI is not observed UI:** drive the app (section 5), measure, and
  say plainly what you could not verify.

## 2. Standing orders

Work lands on `main` by pull request from the session's branch. The owner's
latest dated additions are at the top of
[`docs/roadmap/HANDOVER.md`](docs/roadmap/HANDOVER.md); the newest dated entry wins.

1. **"Continue"**: read this file, HANDOVER's top block and "Now" line, and
   `docs/ROADMAP.md`'s table; merge agent worktrees; then work INBOX,
   `agent-remaining/*.md`, SESSION_BRIEFS, plan phases, ROADMAP, BACKLOG, in
   that order, without asking.
2. **Mid-work drops** go into `INBOX.md` verbatim, triaged at the next step
   boundary; never lose the "Now" line. A usage figure means commit, push, be
   terser. INBOX stays under twenty items (lint); a triaged item is fixed and
   moved to HISTORY, or placed in its plan's "Placed from INBOX" section.
3. **Decisions are not remade.** A missing one becomes an INBOX entry with a
   recommendation, which is then taken.
4. **Agents** by the rungs in section 8 (Haiku labour, Sonnet implementation,
   Opus design). Fable is opt-in only: nothing (routing, escalation, hook,
   skill, agent, retry, scheduled task) may start it; only when the owner
   names it for a task, and only for that task. The agent cap is the tier
   line at the top of HANDOVER; if unsure, take the lower number. Own
   worktree, port and data dir each; first step
   `git merge --no-edit -q <working branch>`; commit per step and every 20
   minutes; write a remaining list. The orchestrator merges, gates and
   pushes. Briefs begin with
   `docs/roadmap/agent-remaining/agent_common.md` and the `orient` skill.
5. **Quality does not drop with the model:** tests first, measure before
   claiming, one commit per step, push per batch, five-line reports.
5a. **Speed without losing quality:** targeted tests plus `scripts/gate.sh`
   per step; the full suite only at session end or for changes targeted tests
   cannot see (migrations, event bus, conftest), never by agents (four cores);
   run merged agents' tests serially (the repo-`data/` guard and some ratchets
   fail only serially); agents landing close together are merged, gated and
   swept in one pass; briefs name files, selectors, line areas, measured
   numbers and the sweep to run.
6. **Copy:** sentence case, no em-dashes (lint), no "Oops", no exclamation
   marks, one line per section, longer help behind `data-help-for`.
7. **CI red is fixed the same hour.** CodeQL comments are bug reports: fix,
   push, resolve the thread. The hourly `send_later` check-in re-arms only
   while an agent runs or a PR waits, carries these orders, and stops after 3
   empty check-ins.
8. **No new plan documents:** a brief row in its plan, or an INBOX entry.
9. **Commit trailers** as the session supplies; no model ids in commits, PRs or code.
10. **Doc hygiene (lints):** plans hold open work only; built blocks move to
   `HISTORY.md` ("Moved from the plans") at that step boundary, leaving a
   pointer (`tests/test_plan_hygiene.py`; HANDOVER over 600 lines moves its
   session record to HISTORY); `tests/test_readme_freshness.py` checks the
   README's numbers. Every merge: CHANGELOG line, README if a number or name
   moved, INBOX entry resolved (`python scratchpad/inbox_resolve.py <n>`),
   the plan's Built block moved.
11. **New UI comes from `docs/DESIGN.md`'s recipe index**, never from scratch:
   a menu is `kebabMenu`, a bar is `.dock`, help is `data-help-for`, a blurred
   surface is on the glass-off list, spacing and radius are tokens. A new need
   gets its recipe and lint in the same commit (`tests/test_ui_recipes.py`).
12. **Concise style:** no preamble or narration; bullets; five-line reports.
13. **Help moves with the UI:** popovers, Settings, Help, the Guide topics
   (`ai/help_chat.py`, `ai/help_topics_more.py`) and
   `tests/test_manual_parity.py`, in the same commit.

## 3. Where things are written down

Start with `docs/ROADMAP.md`'s table. HANDOVER (orders, "Now"), INBOX
(owner findings), SESSION_BRIEFS, one plan per surface (`docs/roadmap/*_PLAN.md`),
`agent-remaining/OPEN.md` (ledger), HISTORY (built, with retractions), BACKLOG,
ANALYSIS, `docs/DESIGN.md` (design system), `docs/ARCHITECTURE.md`,
`docs/CODEMAP.md` (every function, id, route as `name | file:line`).
**Licence:** AGPL-3.0; AGPL or MIT code may come in, nothing goes out to MIT.

## 4. The standing caveat

Every provider test runs against a fake transport; real inference is
unverified unless said. Reproduce before theorising. Real-model checks:
`scratchpad/llama-dev.sh serve`, then `pytest -m evals`.

## 5. Running and verifying the app

`bash scratchpad/ui-sweeps/serve.sh 8781 <scratch dir>` (one server per data
dir; `setsid`, never `pkill -f uvicorn`). Drive with Playwright
(`scratchpad/ui-sweeps/lib.js`, password `testpassword123`, `THEME=dark`).
Traps (detail in WORKING.md):

- `waitUntil: "networkidle"` never settles; use `domcontentloaded` plus a wait.
- Login is one field: fill `#lock-password`, click `#lock-submit`.
- A screenshot is not a measurement: `getComputedStyle`, `getBoundingClientRect`,
  `scratchpad/pngpixel.py`. Never close a visual report without a number.
- A value invalid where used, not where set, does damage far away (`NaN` in CSS).
- Two merged CSS sections can drop a `}`; only `tests/test_css_braces.py` sees it.
- Bash times out at 120s: run `errors.js` in the background.
- Restart uvicorn after any Python change.
- Assets are hash-stamped, so a report that keeps coming back on a current head
  is a real bug, not a cache: reproduce it.
- Scripts that delete things run in a scratch copy, never `cwd=ROOT`.
- CodeQL reads `scratchpad/` too.

## 6. Reviewing work from elsewhere

Check first: a working thing rewritten riskier; a feature that never ran
(grep the call site); a guard removed; a policy silently refusing (CSP).
Run targeted tests against the base branch first.

## 7. Working here

- No torch or `sentence-transformers`; the venv recipe is in WORKING.md.
  `PYTHONPATH=src` to run the app. The suite is about 9,000 tests, under 9
  minutes with `-n auto`.
- `scripts/gate.sh` (`--changed`, `--staged`, `--full`, `--sweeps`) is the
  merge gate; `node --check` after JS edits.
- The app's code is 27 classic scripts sharing one global scope (index.html
  order); a file calls only upwards at load. Tests read `app_js_text()` from
  `tests/_app_js.py`, never `frontend/js/app.js`. Only `frontend/sw.js` stays
  at the root. `python scripts/codemap.py` regenerates CODEMAP
  (`tests/test_codemap_fresh.py`).
- DOM lints (`test_style_scale`, `test_css_braces`, `test_frontend_ids`, ...)
  have found something real when they fail: fix the cause, never widen a rule.
- Strict-xfail spec tests: remove a marker only when its test passes alone.
- Comments explain why; prompt text is budgeted.

## 8. Token budget

Quality first; never downgrade for quality-sensitive work. Cost is turns times
context: batch tool calls, grep then read line ranges, no screenshots where a
number will do, a fresh session per milestone, compact past 150k per turn (the dash budget);
an idle gap over an hour rewrites the cache (avoid idle check-ins).
`python scripts/usage_report.py` prints a session's split.

| Rung | Model | Work |
| --- | --- | --- |
| scout | Haiku | lookup, triage, logs, mechanical edits with a check |
| implement | Sonnet high | named fixes, bounded changes, tests, sweeps |
| judge | Opus medium (high on evidence) | design, ambiguous bugs, risky review |

`max`: three agents, one Opus. `pro`: one agent, no Opus, targeted tests
only, no check-in loop. Tests use a fixed clock, never the real one. Never
weaken a test (change it only when its stated intent moved, and say why).
Replace, do not layer: remove the old path unless persisted data or a public
interface needs it. One retry per new hypothesis; the same call three times
in a row is a stop: report the blocker. Independent review (`reviewer`, `ux-auditor`, `blind-tester`) on
risky or UI changes; the builder does not grade its own work. The
`lean-workflow` plugin packages this workflow (README in its repo). Run the
`retro` skill at session end.

**Compact instructions:** keep the "Now" line, the current task and its
check, failing tests with commands, files being edited, branch and PR, and
decisions made this session.
