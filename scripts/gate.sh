#!/usr/bin/env bash
# The merge gate, in one command, so no merge skips a step it is tired of:
#
#   scripts/gate.sh            # lint set + node --check + ruff (about 40 s)
#   scripts/gate.sh --changed  # plus the tests that name files changed since
#                              # the last push (the routine local gate;
#                              # GATE_BASE=<ref> compares with another)
#   scripts/gate.sh --full     # plus the whole suite (10 to 15 minutes: CI runs
#                              # it on push; locally once before the PR closes)
#   scripts/gate.sh --staged   # the lint set against what is STAGED, not the
#                              # working tree: the one that catches a commit
#                              # that splits a pair (see below)
#   BASE=http://127.0.0.1:8784 scripts/gate.sh --sweeps   # plus errors, docks,
#                                                          # contrast, touch on a running app
#
# Exit code is the first failure's. Prints the five-line shape the reports
# use: what ran, what passed, what failed, what was skipped, where the logs
# are. CLAUDE.md standing orders 5 and 5a; HANDOVER's merge recipe.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# An agent worktree has no `.venv` of its own, so resolve the interpreter and
# ruff from the main checkout when this copy lacks them. Reported by an agent
# whose ruff step failed for that reason alone, on a tree with nothing wrong
# with it. `git rev-parse --git-common-dir` names the main repo's .git even
# from inside a linked worktree, which is what makes the fallback findable
# without hard-coding a path.
MAIN="$(cd "$(git -C "$ROOT" rev-parse --git-common-dir 2>/dev/null || echo "$ROOT/.git")/.." && pwd)"
PY="${PY:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY="$MAIN/.venv/bin/python"
RUFF="$ROOT/.venv/bin/ruff"
[ -x "$RUFF" ] || RUFF="$MAIN/.venv/bin/ruff"
LOG="${GATE_LOG:-$ROOT/.gate}"
mkdir -p "$LOG"; : > "$LOG/timings.txt"
FULL=0; SWEEPS=0; CHANGED=0; STAGED=0
for arg in "$@"; do
  case "$arg" in
    --full) FULL=1 ;;
    --changed) CHANGED=1 ;;
    --sweeps) SWEEPS=1 ;;
    --staged) STAGED=1 ;;
  esac
done
ran=(); passed=(); failed=(); skipped=()
# **pytest's exit 5 is "no tests were collected", and it is a failure here.**
#
# The reading that would make it a pass is that a change touching no tested
# file legitimately runs nothing. That case never reaches pytest: `--changed`
# checks `${#TARGETED[@]}` first and records `changed-tests (none matched)` as
# *skipped*, with the base it compared against printed above it, so an empty
# selection is already said out loud rather than shown as a green test run.
#
# What is left, by elimination, is pytest being handed test files that yield
# no tests: a new test file with nothing in it yet, a file whose tests were all
# renamed out from under the selection, a collection error swallowed into an
# empty run. Every one of those is the selection and reality disagreeing, which
# is the same silence an empty `--changed` used to print green, and the gate
# that let two agents measure nothing was fixed tonight for exactly it.
#
# So it fails, and it says which failure it is: "no tests failed" and "no tests
# ran" want different answers from whoever is reading the five lines, and a
# bare red step name gives neither. Only pytest returns 5; `node --check`
# returns 0 or 1 and ruff 0, 1 or 2, so nothing else can land here by accident.
#
# The five lines are the whole diagnosis, and that is not a stylistic
# preference: `pytest -q` on an empty collection writes one byte to its log
# (measured), so "logs: .gate/changed-tests.log" leads to a blank file and the
# step name is all the reader gets.
step() {  # name, command...
  local name="$1" rc; shift
  ran+=("$name")
  local t0=$SECONDS
  "$@" > "$LOG/$name.log" 2>&1
  rc=$?
  # Seconds per step, beside the logs and not in the five lines: the slowest
  # step is what to measure before trimming a gate (OPEN ledger row 1663).
  echo "$name $((SECONDS - t0))s" >> "$LOG/timings.txt"
  if [ "$rc" = 0 ]; then passed+=("$name")
  elif [ "$rc" = 5 ]; then failed+=("$name (exit 5: no tests collected)")
  else failed+=("$name"); fi
}
LINTS=(tests/test_style_scale.py tests/test_ui_signatures.py tests/test_css_braces.py
  tests/test_css_invalidation.py
  tests/test_frontend_ids.py tests/test_frontend_handlers.py tests/test_dock_grammar.py
  tests/test_status_bar_grammar.py
  tests/test_docs_layout.py tests/test_asset_cache_busting.py tests/test_no_em_dashes.py
  tests/test_no_innerhtml_interpolation.py tests/test_markdown_link_schemes.py
  tests/test_frontend_load_order.py tests/test_ui_recipes.py tests/test_perf_mode.py
  # The gzip boot budget: a few hundred bytes from the cap, and a merge that
  # passed every other lint here went over it on CI (2026-10-03).
  tests/test_static_compression.py
  # The whole boot (every script and stylesheet index.html loads, gzipped as
  # served), the breakpoint set, and "fully local" (no other host in what is
  # served): each reads every frontend file at once, so no one file's name
  # selects it (audit 2026-10-05, FE-06, FE-11).
  tests/test_boot_budget.py tests/test_breakpoints.py tests/test_fully_local.py
  # Which boot-loaded file may call into a lazy bundle, and on what terms.
  # Here rather than left to the changed-test heuristic because it reads
  # index.html, app.js's two loader tables and every frontend file at once,
  # so a change to any one of them can break it without naming it.
  tests/test_lazy_bundle_calls.py
  # The command tables' row shape: it reads editor.js and documents.js
  # together, so neither file's name selects it on its own.
  tests/test_command_row_shape.py
  # The documentation hygiene lint (standing order 10: plan sizes, the
  # HANDOVER line cap, a "Fixed" item left in INBOX). Here because the
  # changed-test heuristic cannot reach it: it opens `HANDOVER.md` and the
  # plans through `ROADMAP / "..."`, a constructed path rather than a
  # literal a diff can be matched against, so editing HANDOVER selects no
  # test at all. 2026-09-21: two HANDOVER additions took it to 606 lines
  # and `--changed` printed "changed-tests (none matched)" on the commit
  # that did it; CI found it thirteen minutes later.
  tests/test_plan_hygiene.py
  # The privacy promise against the code that keeps it. Here rather than
  # left to the changed-test heuristic because it reads five copy files
  # and two config files at once, so a sentence edited in one of them
  # selects nothing.
  tests/test_offline_promise.py
  tests/test_cheap_animations.py tests/test_motion_tokens.py tests/test_icon_label_gap.py tests/test_like_escaping.py
  # The copy lint, here for the same reason `test_docs_site.py` is below: it
  # reads every string in `frontend/js/*.js` and every piece of markup outside a
  # comment, so the changed-test heuristic (a test naming a changed source
  # file) never selects it, and the first new string written after it landed
  # broke it. Caught by a full local run rather than by any gate that day.
  tests/test_ai_name.py tests/test_frontend_symbols.py tests/test_codemap_fresh.py
  # The Guide's controls entries against the markup and the shortcut tables:
  # it reads `ai/help_chat.py` and the frontend together, so a help or a
  # control edit never names it. A help edit once put the Guide's whiteboard
  # keys entry at 1,926 characters against 1,920 and passed this gate.
  tests/test_help_controls.py
  # Same reason again: it reads every string in `frontend/js/*.js`, so no changed
  # source file selects it.
  tests/test_no_glyph_icons.py
  # The scratchpad file cap: a merge adds sweeps from several branches at once,
  # and no changed source file selects it (2026-10-05: an Atlas merge took the
  # count 14 over and the gate passed).
  tests/test_scratchpad_size.py
  # A request inside an assert: CodeQL flags each new one on push.
  tests/test_codeql_shapes.py
  tests/test_plan_hygiene.py tests/test_readme_freshness.py tests/test_vendor_licences.py
  # Mirror drift (docs/CHANGELOG.md and friends) belongs here rather than in
  # --changed: the file that goes stale is a `.md` at the repo root, and the
  # changed-test heuristic matches on a test naming a changed *source* file, so
  # it never selects this one. A full local run caught six edits' worth of
  # drift on 2026-09-12 that every `--changed` gate that day had passed. One
  # second.
  tests/test_docs_site.py)
# **The code map regenerates itself here**, never by hand: `docs/CODEMAP.md`
# is what every agent greps instead of reading files (the orient skill), and
# `tests/test_codemap_fresh.py` fails when a function has moved since the last
# build. A gate that left the map stale would turn that lint into a chore, so
# the gate rebuilds it (about 2.5 s) and, under --staged, stages it so the
# commit carries the map its code matches.
if [ -f "$ROOT/scripts/codemap.py" ]; then
  "$PY" "$ROOT/scripts/codemap.py" > /dev/null 2>&1 || true
  if [ "$STAGED" = 1 ] && ! git -C "$ROOT" diff --quiet -- docs/CODEMAP.md; then
    git -C "$ROOT" add docs/CODEMAP.md
  fi
fi

# **The lint set runs once.** Under `--staged` it runs against the index (the
# scratch tree below) and not also against the working tree: the two used to
# run back to back, so a staged commit paid for the lint set twice (over
# twenty-five minutes under load, OPEN.md "Smaller backend and gate rows").
# The staged run checks everything the working-tree run did, because it is the
# same LINTS array over the same tracked files, and it checks what the commit
# will contain rather than what the folder holds. With nothing staged there is
# no index to check, so the working tree is linted instead: `--staged` never
# runs zero lints. `tests/test_gate_staged_once.py` pins all three cases.
if [ "$STAGED" = 1 ] && ! git -C "$ROOT" diff --cached --quiet; then
  skipped+=("lints (--staged lints the index once, as staged-lints)")
else
  step lints "$PY" -m pytest -q -p no:warnings "${LINTS[@]}"
fi

# --staged: the same lint set, against the *index* rather than the working
# tree.
#
# Why this exists, and it cost a broken build to learn. In the shared
# worktree two agents and the orchestrator edit at once, so `git add <file>`
# stages the whole of a file including whatever someone else has half-written
# in it. One commit on 2026-09-12 staged `frontend/index.html` while an agent
# was mid-way through removing the "Add to document" select: the id went, its
# `$("entry-document").addEventListener` in `app.js` stayed (unstaged), and a
# top-level listener on `null` aborted the whole of `app.js`. `initAuth` never
# ran, the lock overlay never left `.hidden`, and the app did not boot at all
# on that head.
#
# `test_frontend_ids.py` would have caught it: it is in LINTS above and it
# checks exactly that every `$("id")` exists in the markup. It passed, because
# it ran against the *working tree*, where the pair was still whole. The gate
# was checking something nobody was about to commit.
#
# `git checkout-index` writes the staged content of every tracked file into a
# scratch tree, and the lints run there, which is what CI will see.
# The scratch tree is a global with an EXIT trap: a gate killed mid-run
# (a TERM from an impatient agent) skipped the inline `rm -rf`, and about
# ninety 99 MB trees filled the disk on 2026-10-11. A trap cannot run on
# SIGKILL, so each gate also sweeps its own kind left over two hours ago.
GATE_TMP=""
gate_cleanup() { [ -n "${GATE_TMP:-}" ] && rm -rf "$GATE_TMP"; GATE_TMP=""; }
trap gate_cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
find "${TMPDIR:-/tmp}" -maxdepth 1 -name 'mmgate.*' -type d -mmin +120 -exec rm -rf {} + 2>/dev/null
staged_lints() {
  local rc
  GATE_TMP="$(mktemp -d -t mmgate.XXXXXX)"
  local tmp="$GATE_TMP"
  if git -C "$ROOT" checkout-index -a --prefix="$tmp/"; then
    (cd "$tmp" && "$PY" -m pytest -q -p no:warnings "${LINTS[@]}")
    rc=$?
  else
    rc=1
  fi
  gate_cleanup
  return "$rc"
}
if [ "$STAGED" = 1 ]; then
  if git -C "$ROOT" diff --cached --quiet; then
    skipped+=("staged-lints (nothing staged; the working tree was linted above)")
  else
    step staged-lints staged_lints
  fi
else
  skipped+=("staged-lints (--staged)")
fi
node_check() { local bad=0; for f in frontend/js/*.js frontend/sw.js; do node --check "$f" || bad=1; done; return $bad; }
step node-check node_check
step ruff "$RUFF" check .
# --changed: every changed test file, plus tests/test_<stem>*.py for each
# changed source or frontend file (routes_files.py -> test_files*.py and
# test_routes_files*.py; graph.js -> test_graph*.py), for the files changed
# since the last push (the branch's upstream; GATE_BASE overrides) plus the
# working tree. Not since origin/main: on a long branch that is the whole
# suite again. It prints the list it picked so a miss is visible.
# What `--changed` compares against. Printed by `changed_tests`, because a
# gate that will not say what it compared against cannot be trusted by the
# person reading its five lines. In order:
#
# 1. `GATE_BASE`, when set: `GATE_BASE=origin/main` still gives the old,
#    whole-branch comparison, on purpose.
# 2. The merge-base with the upstream, for a branch that tracks one: what
#    this branch has that its remote does not, and never the remote's own
#    newer commits.
# 3. The last pushed commit: the parent of the oldest commit here that no
#    remote branch has. An agent worktree tracks nothing (`git worktree add
#    -b`), and this is where its own work starts.
# 4. `HEAD~1`, when nothing is on any remote.
#
# **Why not origin/main.** It was the fallback for a worktree with no
# upstream, and on a long branch that is the whole branch: 338 test files,
# forty minutes and more, for what standing order 5a calls the per-step gate
# (OPEN.md, 0.3.3). And before that fallback existed, a worktree fell through
# to HEAD~1 on its base commit, diffed nothing and printed green, which is
# why step 3 walks to the first unpushed commit rather than guessing.
# `tests/test_gate_changed_base.py` builds each case in a scratch repo.
changed_base() {
  if [ -n "${GATE_BASE:-}" ]; then echo "$GATE_BASE"; return; fi
  local upstream first
  upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"
  if [ -n "$upstream" ]; then
    git merge-base HEAD "$upstream" 2>/dev/null && return
  fi
  first="$(git rev-list --reverse --topo-order HEAD --not --remotes 2>/dev/null | head -n 1)"
  if [ -z "$first" ]; then echo HEAD; return; fi
  if git rev-parse --verify --quiet "$first^" >/dev/null && [ -n "$(git branch -r --contains "$first^" 2>/dev/null)" ]; then
    echo "$first^"; return
  fi
  echo "HEAD~1"
}
changed_tests() {
  local base
  base="$(changed_base)"
  # To stderr, not stdout: this function *returns* the test list on stdout,
  # so a friendly line printed here becomes a file name pytest then cannot
  # find. Caught by the gate itself one minute after it was written.
  echo "changed-base: $base" >&2
  { git diff --name-only "$base"; git diff --name-only; git ls-files --others --exclude-standard; } | sort -u |
  while read -r f; do
    case "$f" in
      tests/test_*.py) [ -f "$f" ] && echo "$f" ;;
      src/tessellate/*.py|src/tessellate/*/*.py|frontend/js/*.js|frontend/sw.js|frontend/css/*.css)
        stem="$(basename "$f")"; stem="${stem%.*}"
        ls tests/test_"${stem}"*.py 2>/dev/null
        case "$stem" in routes_*) ls tests/test_"${stem#routes_}"*.py 2>/dev/null ;; esac
        # **And any test that names this file, when the name is distinctive.**
        # The rule above maps a changed file to tests *named* after it, which
        # misses a test that exercises it under another name: on 2026-09-09 a
        # preview change turned `tests/test_library_previews.py` red and this
        # gate stayed green, because nothing anyone touched was called
        # "library_previews". An agent found it while doing something else.
        #
        # Distinctive is the whole difficulty. A first attempt grepped every
        # stem and `app`, `library` and `graph` selected most of the suite,
        # which is the full run this flag exists to avoid. So: at least seven
        # characters, and never one of the handful of words that name a whole
        # surface. A stem below the bar keeps the name-based rule above and
        # nothing more, and `--full` and CI are what cover the rest.
        case "$stem" in
          app|main|utils|index|graph|library|settings|documents|whiteboard|chat|notes) ;;
          ???????*) grep -rls --include='test_*.py' -e "$stem" tests/ 2>/dev/null ;;
        esac ;;
    esac
  done | sort -u
}
if [ "$CHANGED" = 1 ]; then
  mapfile -t TARGETED < <(changed_tests)
  # A selection this large is not a targeted run any more, and pretending
  # otherwise would hide how long the gate is about to take. Say so and run
  # it: a slow honest gate beats a fast one that skipped the thing that
  # matters.
  if [ "${#TARGETED[@]}" -gt 40 ]; then
    echo "changed-tests: ${#TARGETED[@]} files selected, which is most of the suite; consider --full"
  fi
  if [ "${#TARGETED[@]}" = 0 ]; then skipped+=("changed-tests (none matched)");
  else
    [ "${#TARGETED[@]}" -le 40 ] && echo "changed-tests: ${TARGETED[*]}"
    step changed-tests "$PY" -m pytest -q -p no:warnings "${TARGETED[@]}"
  fi
else skipped+=("changed-tests (--changed)"); fi
# Across every core when pytest-xdist is there (requirements.txt): the suite
# is 25 minutes serial and under 9 on four cores, and each test already runs
# in its own data dir, so nothing is shared between workers.
XDIST=(); "$PY" -c "import xdist" 2>/dev/null && XDIST=(-n auto)
if [ "$FULL" = 1 ]; then step full-suite "$PY" -m pytest -q -p no:warnings "${XDIST[@]}" tests/; else skipped+=("full-suite (--full)"); fi
if [ "$SWEEPS" = 1 ]; then
  export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}"
  export BASE="${BASE:-http://127.0.0.1:8781}"
  # previewclash: the board and map thumbnails, whose faults (a caption over a
  # block, over another caption, or past the paper) are pure geometry and so
  # are a number, but a number no lint can reach without a browser.
  # Only sweeps that exist: fifteen names here (requests, previewclash, wbfitanchor,
  # helpstream, writingroom, dashdensity, timelinetablewidth, tourtile, findinghover,
  # dochighlight, spinnershape, featuremodels, btnrows, answersupport, listenerrounds)
  # outlived their files in the sweep cleanup and failed this mode for good;
  # `tests/test_gate_lint_set.py` keeps the list and the folder in step.
  for s in errors fontmatrix docks contrast touch leaks keyboard diskspace vibecheck vibefail graphminimap wbgroupguides phonehead phonesidebar phonecapture phoneswipe phonenotepage phoneshare phonedocs phonereminders graphphone wbphone draftreadonly wbexportimage ctrlwheelzoom libreadingfoot libreader hoveronly wbtopbar820 docdaily doccodecopy dockeyboard doctoolbarstate mindmapcurve wbtopbar spinners tagoffer imagecardfoot asktab mapperf maptwokinds mapmidpan tourdim toursteps slashicons uitrio animcost noteobject mapdoors maplayouts maptheme canvasconventions mapviewmenu companionscroll companionbeats companionperf companionsmooth companionmenu companionlife profilelook companionpin perchall iconfloor companionreact companioninteract libtlscroll wbshapetext maplinkcue; do step "sweep-$s" node "scratchpad/ui-sweeps/$s.js"; done
else
  skipped+=("sweeps (--sweeps, needs BASE)")
fi
echo "ran:     ${ran[*]}"
echo "passed:  ${passed[*]:-none}"
echo "failed:  ${failed[*]:-none}"
echo "skipped: ${skipped[*]:-none}"
echo "logs:    $LOG/<step>.log"
[ "${#failed[@]}" = 0 ]
