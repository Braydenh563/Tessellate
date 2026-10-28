// Agent Activity: a list of runs, not a log. Moved out of app.js on
// 2026-09-26 (INBOX 426 cc, and the gzipped-size ratchet in
// tests/test_static_compression.py). A classic script loaded right after
// app.js: it shares app.js's globals, and everything app.js calls in here
// (addAgentRun, endAgentRun, agentRunStep...) is called from inside a
// function, never while app.js itself is loading.

// --- Agent Activity: a list of runs, not a log -------------------------------
//
// Reported, verbatim: *"make a better way to view and access agent model
// activity and logs that appear in the agent activity toast panels then how
// they appear now, they just spawn in and its a bunch of text dump in your
// face and just gets annoying. it should still be accessible though."*
//
// What it was: a live tail of every log record from `memorymap.*`, opened by
// the arrival of a line. One agent turn writes its context budget, its prompt
// composition and its tool budget, three paragraphs of arithmetic, so the
// panel's whole content was machinery nobody asked to read, and it opened
// itself to show it.
//
// What it is (AGENT_SKILLS_REFORM.md, Phase C): **one row per run**, collapsed.
// Opening a row shows its steps; opening a step shows the tool calls it made
// and what they returned. Three levels, each collapsed until asked for, and
// deliberately the *same* `<details>` shape and CSS the chat transcript uses
// for Thinking (`agent-step step-thinking`) and for a skill's plan
// (`agent-step step-plan`), so this is that component in another place rather
// than a fourth thing to maintain.
//
// The log is not gone and is not summarised: it is behind "Show log", with the
// same lines it always had. That is the "it should still be accessible though"
// half, and it is why `appendAgentLog` below is unchanged apart from no longer
// forcing the panel open.
const agentMonitor = $("agent-monitor");
const agentMonitorLogs = $("agent-monitor-logs");
const agentMonitorRuns = $("agent-monitor-runs");
const agentMonitorEmpty = $("agent-monitor-empty");
const agentMonitorLogToggle = $("agent-monitor-log-toggle");
const agentMonitorClose = $("agent-monitor-close");
const agentMonitorClear = $("agent-monitor-clear");

//: Runs kept in the panel for this session, oldest first. Twelve because the
//: panel is 350px wide and a row is one line collapsed: past that it is a list
//: to scroll rather than a thing to glance at, and the audit log
//: (Library → AI Skills) is the real history.
const AGENT_RUN_LIMIT = 12;
const agentRuns = [];
let agentRunSeq = 0;

//: Whether the reader opened the panel themselves. A manual open must not be
//: taken away by the idle timer twelve seconds later, that timer exists for
//: a panel that opened *itself*.
let agentMonitorPinned = false;

//: **One wording for a step's state, used in both places it is shown.** The
//: chat's plan card and this panel are two renderings of the same run, and
//: two different sentences for `retrying` would read as two different things
//: happening. Phase A's runner emits `attempt`/`of`/`reason` with the event;
//: this is where they become words.
function stepStateWords(state, event = {}) {
  const reason = event.reason ? `, ${event.reason}` : "";
  if (state === "retrying") {
    const attempt = event.attempt || 1;
    const of = event.of || attempt;
    return `retrying, attempt ${attempt} of ${of}${reason}`;
  }
  //: A step the run *rewrote* after it failed (PLAN.md §4 A2: 
  //: `skill_runner.MAX_REPLANS`). Worded as recovery rather than as an error,
  //: because that is what it is: the step is about to be tried again with a
  //: smaller instruction, and the line under it is the new one.
  if (state === "replanned") {
    const attempt = event.attempt || 1;
    const of = event.of || attempt;
    return `re-planned, attempt ${attempt} of ${of}${reason}`;
  }
  //: **Paging** (CHAT_PLAN decision 10). A step that must see every note
  //: calls its read once per page, and without this the reader watches one
  //: step sit on "running" through four tool calls with no sign that it is
  //: getting anywhere. The count of notes read is the progress, so it is the
  //: half that gets said.
  if (state === "paging") {
    const page = event.page || 1;
    const of = event.of || page;
    const seen = event.seen ? `, ${event.seen} read` : "";
    return `reading page ${page} of at most ${of}${seen}`;
  }
  if (state === "running") return "running";
  if (state === "done") return "done";
  if (state === "earlier") return "done in the run this resumed";
  if (state === "failed") return `failed${reason}`;
  if (state === "stalled") return `stalled${reason}`;
  return `${state}${reason}`;
}

//: The icon and word for a whole run, in the same "ph:icon Text" shape every
//: other label in this app uses (`setLabel` resolves it).
function runStateLabel(state) {
  if (state === "running") return "ph:spin Running";
  if (state === "done") return "ph:check-circle Done";
  if (state === "failed") return "ph:x-circle Failed";
  if (state === "stalled") return "ph:pause-circle Stalled";
  if (state === "paused") return "ph:pause-circle Waiting for you";
  return state;
}

function renderAgentRunSummary(run) {
  if (!run) return;
  //: The icon is its own grid column rather than part of the name, so the
  //: name, the detail line and the bar under it all start on one edge
  //: (measured before: the name's text at 76px, the detail at 43.6px). The
  //: name ellipsises in one line and carries the whole of itself on `title`.
  const iconName = /^ph:([\w-]+)$/.exec(run.icon || "")?.[1] || "circle";
  run.iconEl.className = `ph ph-${iconName} agent-run-icon`;
  run.nameEl.textContent = run.name;
  run.nameEl.title = run.name;
  // "Step 2 of 5" only when the run declared steps. A background job knows how
  // far along it is as a fraction and not as a step number; an agent turn with
  // no plan has no steps at all, and inventing one for either would be the
  // progress bar that guesses.
  const done = run.steps.filter((step) => step.state === "done" || step.state === "earlier").length;
  if (run.stepCount) {
    const at = Math.min(run.stepCount, (run.currentIndex ?? done) + 1);
    run.metaEl.textContent =
      run.state === "running" ? `Step ${at} of ${run.stepCount}` : `${done} of ${nounCount(run.stepCount, "step")}`;
  } else {
    run.metaEl.textContent = run.detail || "";
  }
  run.metaEl.title = run.metaEl.textContent;
  //: **A counter is a label on the bar beside it; a detail is a sentence.**
  //: Both go in the same slot, and the slot is allowed to wrap because of the
  //: sentence: so "Step 2 of 3" broke across two lines next to the bar, which
  //: is how a 60px row became 78 and three runs came to need a scroller in a
  //: panel that could hold them. The class says which of the two this is, and
  //: the stylesheet stops the counter wrapping without touching the sentence.
  run.metaEl.classList.toggle("agent-run-count", Boolean(run.stepCount));
  setLabel(run.stateEl, runStateLabel(run.state));
  run.stateEl.className = `agent-run-state plan-step-${run.state}`;
  // A fraction, or nothing at all, the same rule the Tasks panel follows for
  // exactly the same reason (`renderTasks`): a bar that guesses is worse than
  // one that admits it cannot say.
  const fraction =
    typeof run.progress === "number"
      ? run.progress
      : run.stepCount
        ? done / run.stepCount
        : null;
  //: Only while it runs (the owner, 2026-10-10: "says done but the bar is
  //: still there??"): a finished row's state chip is its answer, and a bar
  //: left beside "Done" reads as still going.
  const bar = run.state === "running" && fraction !== null;
  run.bar.classList.toggle("hidden", !bar);
  if (bar) run.bar.value = Math.max(0, Math.min(1, fraction));
  // An agent turn has neither a step count nor a fraction, and an empty second
  // line under its name is a gap that looks like something failed to load.
  run.progressWrap.classList.toggle("hidden", !bar && !run.metaEl.textContent);
  run.el.classList.toggle("is-running", run.state === "running");
}

//: What to call a run that has no name of its own. An agent turn is titled by
//: the question that started it, trimmed to something that fits one line of a
//: 350px panel: the alternative is a row called "Agent turn" fourteen times.
function agentRunTitle(question) {
  const text = String(question || "").replace(/\s+/g, " ").trim();
  if (!text) return "Agent turn";
  return text.length > 48 ? `${text.slice(0, 47)}…` : text;
}

//: A run row. Built once and updated in place, re-rendering the list on every
//: event would slam shut any `<details>` the reader had just opened, which is
//: the one thing this panel exists to let them do.
function addAgentRun({ kind, name, icon = "", steps = [], detail = "" }) {
  //: A desktop shell running a cached `index.html` against a fresh `app.js`
  //: is a thing that has actually happened here (CLAUDE.md, the static-cache
  //: header bug), and the failure mode must be "no run list", not a TypeError
  //: that takes the chat turn down with it.
  if (!agentMonitorRuns) return null;
  const run = {
    id: `run-${++agentRunSeq}`,
    kind,
    name: name || "Run",
    icon,
    detail,
    state: "running",
    steps: [],
    stepCount: steps.length,
    currentIndex: null,
    progress: null,
  };

  const el = document.createElement("details");
  // The chat's own plan card, reused wholesale: same fold, same marker, same
  // type scale.
  el.className = "agent-step step-plan agent-run-row";
  const summary = document.createElement("summary");
  summary.className = "agent-run-summary";
  run.iconEl = document.createElement("i");
  run.iconEl.setAttribute("aria-hidden", "true");
  run.nameEl = document.createElement("span");
  run.nameEl.className = "agent-run-name";
  run.metaEl = document.createElement("span");
  run.metaEl.className = "agent-run-meta";
  run.stateEl = document.createElement("span");
  run.stateEl.className = "agent-run-state";
  run.bar = document.createElement("progress");
  run.bar.className = "task-progress";
  run.bar.max = 1;
  run.bar.value = 0;
  //: **The bar goes inside the `<summary>`, and it has to.** A row is
  //: collapsed by default, that is the whole point of the rebuild, so
  //: anything in the `<details>` body is invisible exactly when the run is
  //: worth watching. `<progress>` and `<span>` are phrasing content, which is
  //: what a `<summary>` may contain.
  //:
  //: The second line is a wrapper rather than two more items in the summary's
  //: own flex row: measured on the 350px panel, "Step 1 of 3" and "Running"
  //: beside the name left it 125px, a run called "Summarise my week" showed
  //: as "Summarise …". The step count belongs with the bar it describes, and
  //: moving it there gives the name back most of the row.
  run.progressWrap = document.createElement("span");
  run.progressWrap.className = "agent-run-progress";
  run.progressWrap.append(run.metaEl, run.bar);
  summary.append(run.iconEl, run.nameEl, run.stateEl, run.progressWrap);
  run.body = document.createElement("div");
  run.body.className = "agent-run-body";
  el.append(summary, run.body);
  run.el = el;
  //: **A run with no steps must not offer a fold.** Reported twice (INBOX 69,
  //: "a 'Starting SearXNG' row with a caret that does nothing"; and again on
  //: 2026-09-09 against "Loading the embedding model"). Both are background
  //: jobs, which is exactly the case that declares no steps: the `<details>`
  //: still drew the marker and still toggled, onto an empty body. The step
  //: rows have had this rule since Phase C (`:not(.has-tools)`), the run row
  //: never got it. `has-steps` is set by `agentRunAddStep`; the guard below
  //: is the half the CSS cannot do, since a hidden marker is still a summary
  //: and a click on it still toggles.
  summary.addEventListener("click", (event) => {
    if (!el.classList.contains("has-steps")) event.preventDefault();
  });

  for (const [index, text] of steps.entries()) agentRunAddStep(run, index, text);

  agentMonitorRuns.appendChild(el);
  agentRuns.push(run);
  // Oldest first out, and never one that is still going: a run scrolled off
  // the list while it was running is a run whose end is never shown.
  while (agentRuns.length > AGENT_RUN_LIMIT) {
    const oldest = agentRuns.findIndex((item) => item.state !== "running");
    if (oldest === -1) break;
    agentRuns.splice(oldest, 1)[0].el.remove();
  }
  renderAgentRunSummary(run);
  renderActivityStatusItem();
  agentMonitorEmpty?.classList.add("hidden");
  //: The list is chronological and it scrolls, so without this a run that
  //: starts while eight are already listed is appended out of sight, the
  //: same tail-following the log it replaced has always done.
  agentMonitorRuns.scrollTop = agentMonitorRuns.scrollHeight;
  return run;
}

function agentRunAddStep(run, index, text) {
  const step = { index, state: "pending", text, toolCount: 0 };
  const el = document.createElement("details");
  // The Thinking disclosure, reused: quieter than the run row above it, folds
  // the same way, and the marker is drawn inside the summary rather than in
  // the rail's gutter (see its rule in 02-chat-graph.css).
  el.className = "agent-step step-thinking agent-run-step";
  const summary = document.createElement("summary");
  summary.className = "plan-step";
  step.summary = summary;
  step.tools = document.createElement("div");
  step.tools.className = "agent-run-tools";
  el.append(summary, step.tools);
  step.el = el;
  run.body.appendChild(el);
  run.el.classList.add("has-steps");
  run.steps.push(step);
  agentRunPaintStep(run, step);
  return step;
}

function agentRunPaintStep(run, step, event = {}) {
  const words = step.state === "pending" ? "not started yet" : stepStateWords(step.state, event);
  const number = `${step.index + 1}. `;
  step.summary.textContent = `${number}${step.text}: ${words}`;
  step.summary.className = `plan-step plan-step-${step.state}`;
  step.summary.dataset.state = step.state;
}

//: **What the app checked after the run, in the app's own words.** A skill
//: may declare a `verify` block (a tool call plus a predicate); the runner
//: runs it against the notebook once the last step is done and the answer
//: lands here. Worded as a fact with the number in it, never as a badge on
//: its own: "verified" with nothing behind it is the same reassurance the
//: green tick on an unfinished step used to give.
function verificationRow(check) {
  const row = document.createElement("div");
  row.className = `skill-verify skill-verify-${check.ok ? "ok" : "not-ok"}`;
  row.textContent = check.ok ? `Verified: ${check.reason}` : `Not verified: ${check.reason}`;
  return row;
}

//: One step event from the runner. `retrying` is Phase A's own state and is
//: the reason this panel had to change: a step that is being re-prompted looks
//: exactly like one that is running unless it says so.
function agentRunStep(run, event) {
  if (!run) return;
  let step = run.steps[event.index];
  if (!step) step = agentRunAddStep(run, event.index, event.text || `Step ${event.index + 1}`);
  if (event.text) step.text = event.text;
  step.state = event.state;
  agentRunPaintStep(run, step, event);
  run.currentIndex = event.index;
  //: `replanned` is included because the step is about to be run again at the
  //: same index: the calls it makes next belong under it, not under whatever
  //: step happened to be current before it.
  if (
    event.state === "running" ||
    event.state === "retrying" ||
    event.state === "replanned" ||
    //: `paging` is the step still working: the next page's tool call belongs
    //: under it, and leaving it out would file the rest of a paged read under
    //: whatever step was current before this one.
    event.state === "paging"
  ) {
    run.currentStep = step;
  }
  //: A step that stopped the run opens itself. Everything else stays folded, 
  //: which is the point of the panel, but a failure nobody can see without a
  //: click is a failure reported as silence.
  if (event.state === "failed" || event.state === "stalled") step.el.open = true;
  renderAgentRunSummary(run);
}

//: A tool call, filed under the step that made it. A run with no steps (a
//: plain agent turn) keeps its calls at the top level: inventing a "step 1 of
//: 1" for it would be a level that says nothing.
function agentRunTool(run, node) {
  if (!run || !node) return;
  const holder = run.currentStep ? run.currentStep.tools : run.body;
  holder.appendChild(node);
  if (run.currentStep) {
    run.currentStep.toolCount += 1;
    run.currentStep.el.classList.add("has-tools");
  }
  renderAgentRunSummary(run);
}

function endAgentRun(run, { state = "done", detail = "" } = {}) {
  if (!run || run.state !== "running") return;
  run.state = state;
  if (detail) run.detail = detail;
  run.currentStep = null;
  // Anything still marked running when the run ended did not finish. Saying so
  // is the difference between a record and a wish.
  for (const step of run.steps) {
    if (step.state !== "running" && step.state !== "retrying" && step.state !== "paging") continue;
    step.state = state === "done" ? "done" : state;
    agentRunPaintStep(run, step);
  }
  renderAgentRunSummary(run);
  renderActivityStatusItem();
  //: **The only toast a chat run raises, and only when nobody could have seen
  //: it end.** Phase C's rule is start / finished / failed and nothing else;
  //: the *start* of a run the reader is not watching is already announced by
  //: this panel opening itself, so the end is the half with nothing saying it.
  //: A run that ended in the transcript the reader is looking at needs no
  //: notice at all: the transcript is the notice.
  //:
  //: Through `agentActivityNotice`, never `toast`, so the mute and "Panel
  //: only" switches keep working: it records into the notifications centre
  //: either way and only flies a toast past the corner of the screen when the
  //: reader has asked for those. Background jobs are not included, they have
  //: announced their own ends since before this panel existed
  //: (`noticeTaskTransitions`), and doing it here as well would say it twice.
  if (run.kind !== "job" && agentRunWantsPanel(run)) {
    const failed = state === "failed" || state === "stalled";
    agentActivityNotice(failed ? `Stopped: ${run.name}` : `Finished: ${run.name}`, {
      isError: state === "failed",
      detail: failed ? "Open Agent Activity to see which step stopped it." : "",
    });
  }
}

//: Whether a starting run should also *open* the panel.
//:
//: The old rule was "any log line opens it", which is the reported complaint.
//: The new one: a run the reader is already watching does not need a panel
//: over the top of it, a skill run in the Chat tab is drawn step by step in
//: the transcript: but a background pass, or a run left behind on another
//: tab, has nowhere else to show itself.
function agentRunWantsPanel(run) {
  if (run.kind === "job") return true;
  //: The tab the app is actually showing, read the way every other caller
  //: reads it: `switchTab` writes it, and there is no in-memory copy to go
  //: stale against a reload.
  return (prefs.get("activeTab", null) || "") !== "chat";
}

function openPanelForRun(run) {
  if (!run || !agentRunWantsPanel(run)) return;
  if (!agentMonitor.classList.contains("hidden")) return;
  if (Date.now() - agentMonitorDismissedAt < AGENT_MONITOR_REOPEN_AFTER_MS) return;
  setAgentMonitorVisible(true);
  showActivityTab("runs");
  nudgeAgentMonitorIdle();
}

//: The way back in. See index.html for why it exists: log lines no longer open
//: this panel, so without a control naming it, a finished run would be
//: unreachable the moment the panel timed out.
function renderActivityStatusItem() {
  //: Every start and end of a run passes here: the app's mark lifts its
  //: cells while one is running (phone-shell.js).
  syncEmblemBusy();
  const button = $("status-activity");
  if (!button) return;
  button.classList.toggle("hidden", agentRuns.length === 0);
  syncPhoneMoreRuns();
  if (!agentRuns.length) return;
  const running = agentRuns.filter((run) => run.state === "running").length;
  paintStatusItem("status-activity", {
    icon: "ph:strategy",
    value: running || agentRuns.length,
    label: running ? "running" : agentRuns.length === 1 ? "run" : "runs",
    title: "Agent activity: every run this session, and the log.\n\nClick to show or hide the panel.",
  });
}

function setAgentMonitorLogVisible(show) {
  if (!agentMonitorLogToggle || !agentMonitorRuns) return;
  agentMonitorLogs.classList.toggle("hidden", !show);
  agentMonitorRuns.classList.toggle("hidden", show);
  agentMonitorEmpty?.classList.toggle("hidden", show || agentRuns.length > 0);
  //: An icon button now (the head is the panel-head recipe), so what it
  //: will do is said in its name and its tooltip, and the glyph is the view
  //: it switches to.
  const words = show ? "Show the runs" : "Show the log";
  agentMonitorLogToggle.setAttribute("aria-label", words);
  agentMonitorLogToggle.title = words;
  setLabel(agentMonitorLogToggle, show ? "ph:list-checks" : "ph:terminal-window");
  agentMonitorLogToggle.setAttribute("aria-expanded", String(show));
}

if (agentMonitorLogToggle) {
  agentMonitorLogToggle.addEventListener("click", () => {
    setAgentMonitorLogVisible(agentMonitorLogs.classList.contains("hidden"));
  });
}

$("status-activity")?.addEventListener("click", () => {
  const showing = !agentMonitor.classList.contains("hidden");
  agentMonitorPinned = !showing;
  setAgentMonitorVisible(!showing);
  // Opened by hand, so the dismissal window that keeps a run from reopening it
  // is spent: otherwise pressing this within 90s of an X does nothing.
  if (!showing) {
    agentMonitorDismissedAt = 0;
    showActivityTab("runs");
  }
});

// --- Activity: one panel, two tabs (WORLD_CLASS_PLAN 28.1 rule 5, decision 70)
//
// This panel was the agent's run list. Every running job (indexing, a model
// answering, imports, reading text, transcribing, backups, the agent's
// passes) is now its first tab, Running, from `GET /activity`, with Stop on
// each; the runs are the second. The tabs, the ⋯ and the list are lazy
// (activity-panel.js): boot only knows how to open the panel on a tab.
function showActivityTab(tab) {
  ensureModule("activity").then(() => window.setActivityTab?.(tab));
}

//: Opened by hand on one tab: pinned, so the idle timer leaves it up.
function openActivity(tab = "running") {
  agentMonitorPinned = true;
  agentMonitorDismissedAt = 0;
  setAgentMonitorVisible(true);
  showActivityTab(tab);
}
window.openActivity = openActivity;

// The monitor is `position: fixed` in the bottom-right corner, which is also
// where the whiteboard keeps its zoom controls, so while it was open those
// controls were behind it and simply could not be clicked. A floating panel
// that covers a fixed control is a broken control, so the app is told when the
// monitor is showing and the whiteboard lifts its panel clear.
function setAgentMonitorVisible(visible) {
  agentMonitor.classList.toggle("hidden", !visible);
  document.body.classList.toggle("has-agent-monitor", visible);
  if (!visible) clearTimeout(agentMonitorIdleTimer);
}

//: How long after the last line the monitor puts itself away. Reported
//: directly: "autonomous background task notifications never auto close and
//: stay open until the user closes them", and they did not, because nothing
//: here ever called `setAgentMonitorVisible(false)` except the X button. A
//: background pass would open this panel over the corner of the app and leave
//: it there for the rest of the session.
//:
//: Twelve seconds is picked against what the panel is *for*: it is a live
//: tail, so it is interesting while lines are arriving and is a leftover the
//: moment they stop. Every new line restarts the clock, so a pass that runs
//: for four minutes keeps it open for four minutes.
const AGENT_MONITOR_IDLE_MS = 12000;

//: Long enough that a *new* pass reopens the panel, short enough that a
//: dismissal during one pass is not overridden two seconds later by the next
//: line of the same pass. Closing it used to mean nothing at all: the very
//: next log line re-opened it, so the X button read as broken.
const AGENT_MONITOR_REOPEN_AFTER_MS = 90000;

let agentMonitorIdleTimer = null;
let agentMonitorDismissedAt = 0;

function nudgeAgentMonitorIdle() {
  clearTimeout(agentMonitorIdleTimer);
  //: **A panel somebody opened on purpose is never taken away.** The timer
  //: below exists for a panel that opened *itself*; applying it to a manual
  //: open would close the run list twelve seconds into reading it.
  if (agentMonitorPinned) return;
  agentMonitorIdleTimer = setTimeout(() => {
    // Never yank it away from under a pointer or a keyboard focus: someone
    // reading a line or reaching for the X is the one case where the panel
    // is doing its job.
    if (agentMonitor.matches(":hover") || agentMonitor.contains(document.activeElement)) {
      nudgeAgentMonitorIdle();
      return;
    }
    //: Nor while something is still going: a run row that is still ticking is
    //: the live thing this panel is for, and it used to be a log line every
    //: few seconds that kept the panel awake. There are no log lines keeping
    //: it awake any more, so the run itself has to.
    if (agentRuns.some((run) => run.state === "running")) {
      nudgeAgentMonitorIdle();
      return;
    }
    setAgentMonitorVisible(false);
  }, AGENT_MONITOR_IDLE_MS);
}

//: **Clear**, reported on 2026-09-09: "the agent activity logs cant be
//: cleared". The panel is a session tail with a fifty-line cap and an
//: eight-row run cap, so it never emptied on its own except by ageing out,
//: and a reader who has read it had no way to say so. Both halves go, since
//: the button is in the header above both and clearing one while the other
//: kept its backlog would be the sort of half-action that reads as broken.
//: A run still going is kept: it is the live thing the panel is for, and
//: removing its row would strand its end with nothing to draw it on.
if (agentMonitorClear) {
  agentMonitorClear.addEventListener("click", () => {
    const kept = [];
    for (const run of agentRuns) {
      if (run.state === "running") kept.push(run);
      else run.el.remove();
    }
    agentRuns.length = 0;
    agentRuns.push(...kept);
    agentMonitorLogs.textContent = "";
    agentMonitorEmpty?.classList.toggle(
      "hidden",
      agentRuns.length > 0 || !agentMonitorLogs.classList.contains("hidden"),
    );
    renderActivityStatusItem();
  });
}

if (agentMonitorClose) {
  agentMonitorClose.addEventListener("click", () => {
    agentMonitorDismissedAt = Date.now();
    agentMonitorPinned = false;
    setAgentMonitorVisible(false);
  });
  //: Escape closes it when focus is inside it, as it closes every other
  //: floating surface (OPEN.md, Chat and popup agent). Only from inside: the
  //: panel is non-modal and never takes focus, so an Escape meant for the
  //: editor behind it must not also dismiss it.
  agentMonitor.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || event.defaultPrevented) return;
    event.preventDefault();
    agentMonitorClose.click();
  });
}

function appendAgentLog(record) {
  // **Agent lines only.** This used to read `if (!isAgent && record.level !==
  // "ERROR") return;`, which let *every* ERROR in the app through whatever
  // logger produced it: so a failed embedding backend, a bad request, a
  // stray traceback all popped open a panel labelled "Agent Activity" and
  // left it there. Errors already have somewhere to go (a toast, and
  // Settings → Logs); this panel is a tail of one specific thing.
  const logger = record.logger || "";
  const isAgent =
    logger.startsWith("tessellate.ai") ||
    logger.includes("autonomous") ||
    logger.includes("agent");
  if (!isAgent) return;

  //: **A log line no longer opens this panel** (Phase C). It is the whole of
  //: the reported complaint: one agent turn writes its context budget, its
  //: prompt composition and its tool budget, and each of those three
  //: paragraphs was enough to throw the panel over whatever you were reading.
  //: The lines are still collected, identically, and still capped at fifty , 
  //: and Show log is one click. What opens the panel now is a *run* starting
  //: (`openPanelForRun`), which is a thing that happened rather than a
  //: sentence that was written about it.
  const div = document.createElement("div");
  div.className = "monitor-log-item " + record.level.toLowerCase();
  div.textContent = record.message;

  agentMonitorLogs.appendChild(div);

  if (agentMonitorLogs.children.length > 50) {
    agentMonitorLogs.removeChild(agentMonitorLogs.firstChild);
  }

  agentMonitorLogs.scrollTop = agentMonitorLogs.scrollHeight;
  //: Only while the log is the view being read, otherwise a burst of lines
  //: from a background pass would keep a panel awake that is showing a list
  //: nothing is changing in.
  if (!agentMonitorLogs.classList.contains("hidden")) nudgeAgentMonitorIdle();
}

let agentLogStreamStarted = false;
async function streamAgentLogs() {
  if (agentLogStreamStarted) return;
  agentLogStreamStarted = true;
  let cursor = 0;
  while (true) {
    try {
      // `api.stream` (F5), silent: a 401 or a refusal throws into the wait
      // below without the lock screen, as the hand-rolled fetch did.
      const response = await api.stream(`/logs/stream?after=${cursor}`, { silent: true });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // keep last incomplete line
        
        for (const line of lines) {
          if (!line.trim()) continue;
          const msg = JSON.parse(line);
          if (msg.cursor) cursor = msg.cursor;
          
          if (msg.type === "open") {
            cursor = msg.latest || cursor;
          } else if (msg.type === "record") {
            appendAgentLog(msg.record);
          }
        }
      }
    } catch (e) {
      await new Promise(r => setTimeout(r, 5000));
    }
  }
}

// Hook it into startApp
const originalStartAppAgentHook = window.startApp;
window.startApp = async function() {
  if (originalStartAppAgentHook) {
    await originalStartAppAgentHook.apply(this, arguments);
  }
  streamAgentLogs();
  //: After the app has painted, so the strips that are built at run time
  //: (the Library sub-tabs, the editor toolbars) are in the DOM to be wired.
  //: Idempotent per element (`data-wheel-x`), so calling it again is free.
  wireHorizontalWheelScrolling();
}
