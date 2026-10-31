# Deep audit checklist (every deep-audit-* agent reads this first)

The owner's standing ask (INBOX 1357, 1426, 1430): find everything that is
wrong or missing, every little and humongous thing, and fix the class, not
the case. Read-only: no repo edits except your one findings file.

## Coverage first, then findings

1. Inventory before judging. From `docs/CODEMAP.md`, list every function,
   element id, route, CSS section and Guide topic in your scope (grep the map
   by file). That list is your coverage table; every row ends `checked`,
   `driven`, or `not reached (why)`. A finding count without a coverage table
   is not a deep audit.
2. Then walk every interaction a person can do in your scope: each button,
   menu item, shortcut, drag, gesture, empty, loading, error and offline
   state, at 1440x900 and 390x844, light and dark, mouse, keyboard only and
   touch emulation.
3. Skip what `docs/roadmap/agent-remaining/audit-*-ranked.md`,
   `docs/roadmap/INBOX.md` and the plans already hold, unless it is still
   broken on this head (then say "still open, re-verified").

## Lenses (every one, every surface)

- **Broken:** does it do what its label says; races, double submits,
  stale state, lost input, undo and redo, data loss, sync, reload restores.
- **Missing:** what a world-class app of this kind has that this does not
  (compare to the best two in its class by name); half-built features (a
  control with no handler, a handler with no control: grep the call site).
- **UX:** discoverability ("where is" and "how do I" answerable from the
  UI), feedback after every act, confirm on destructive acts, focus after
  every act, error copy that says what to do next, consistency between
  surfaces.
- **UI and design:** `docs/DESIGN.md` recipes (standing order 11), tokens
  for spacing and radius, alignment, contrast, dark mode parity, glass, icon
  meaning, responsive at every width, no horizontal scroll, no clipped text.
- **Accessibility, WCAG 2.2 AA:** names, roles, states, focus order and
  visibility, 2.5.7 drag alternatives, 2.5.8 target size (24px, 44px on
  phone), 1.4.3 and 1.4.11 contrast, live regions, reduced motion.
- **Copy:** sentence case, no em-dashes, no exclamation marks, no "Oops",
  plurals right, no doubled words, help behind `data-help-for`, Guide topic
  parity (standing order 13).
- **Performance and complexity (the owner's standing order):** forced
  layout (a read after a write), per-frame work in rAF loops, listeners
  never removed, full re-renders where a dirty set would do, O(n^2) over
  notes, main-thread work over 50 ms, payload and boot size, timers that run
  while hidden, server routes slow under a slow model, functions over the
  complexity ratchet (`tests/complexity_seed.json`). Measure at 4x CPU
  throttle on a seeded notebook (200 notes, 20 boards, 10 documents).
- **Security and privacy:** auth on every route, Origin and CSRF, LAN mode,
  private notes never leaking (search, index, logs, export, AI context),
  path traversal, injection (prompt injection from notes and the web too),
  secrets in logs or localStorage, body size caps, downloads unpinned.
- **AI and composer:** answers right with the model off and on (CHAT_PLAN
  decision 75), English quality, citations, every act phrasing class,
  refusals, Stop, regenerate.
- **Logs:** run the app's lag and error reporters during the walk; every
  lag line, console error and slow request you see is a finding with its
  cause.

## Method rules

- CLAUDE.md section 5: serve with `bash scratchpad/ui-sweeps/serve.sh <port> <dir>`,
  drive with Playwright (`scratchpad/ui-sweeps/lib.js`, password
  `testpassword123`), `domcontentloaded` plus a wait, never networkidle.
- A screenshot is not a measurement: `getComputedStyle`,
  `getBoundingClientRect`, `PerformanceObserver` long tasks, timings.
- Mark every row `run` (driven and measured) or `code` (read only).
- Every provider runs against a fake transport (CLAUDE.md 4); say so.
- Kill your server by port (`kill $(lsof -ti tcp:PORT)`), never
  `pkill -f uvicorn`. Scratch files in your own scratch dir, not the repo.

## Output

One file: `docs/roadmap/agent-remaining/audit-<date>-<surface>.md`.

1. Coverage table counts (rows checked, driven, not reached).
2. Findings table: `| id | sev | kind | finding | evidence (file:line or selector, the number) | verified | fix (the class) | effort |`.
   Severity: high (data loss, security, broken core flow), med, low.
   Kind: bug, missing, ux, ui, a11y, copy, perf, complexity, security, ai.
3. What is already good (one line each) and what you could not verify.

Report to the orchestrator in five lines: counts by severity and kind, the
top five, the file path.
