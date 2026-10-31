// task-steps.js: one line per package of a bulk action, loaded with the two
// panels that show them (Settings, Tasks in chat-tasks.js and Settings,
// Packages in settings-packages.js). Moved out of ai-tools.js, a boot script,
// to win back the boot gzip budget (2026-10-27, INBOX 1412's Done verdict).

//: One line per package of a bulk action: waiting, in hand, done or not.
const TASK_STEP_ICONS = {
  queued: "ph:hourglass-medium",
  running: "ph:spin",
  completed: "ph:check-circle",
  failed: "ph:warning",
  skipped: "ph:minus-circle",
  cancelled: "ph:stop-circle",
};
const TASK_STEP_WORDS = { queued: "waiting", running: "installing", completed: "done" };
function taskSteps(steps) {
  const list = document.createElement("ul");
  list.className = "task-steps";
  for (const step of steps) {
    const li = document.createElement("li");
    li.className = `task-step is-${step.outcome}`;
    setLabel(li, `${TASK_STEP_ICONS[step.outcome] || "ph:info"} ${step.label}: ${step.word || TASK_STEP_WORDS[step.outcome] || step.outcome}`);
    if (step.message) li.title = step.message;
    //: pip reports no fraction, so the package in hand has an indeterminate bar.
    if (step.outcome === "running") {
      const bar = document.createElement("progress");
      bar.className = "task-progress task-step-bar";
      bar.setAttribute("aria-label", step.label);
      li.appendChild(bar);
    }
    list.appendChild(li);
  }
  return list;
}

// Which task logs the user has opened, kept across the 3-second re-render so
// a fold doesn't slam shut under them.
const taskLogsOpen = new Set(["searxng"]);
const taskLogScrollStates = new Map();

//: One run's lines as text, each with when it was said from the run's start
//: ("+3 s  Called search_notes: ..."), the way a terminal log reads.
function taskRunLinesText(lines, started) {
  return lines
    .map((line) => (line.at && started ? `+${taskElapsed(line.at - started)}  ${line.text}` : line.text))
    .join("\n");
}

//: The disclosure under a run (DESIGN.md list row with a `.task-log` fold):
//: open while it runs if it was open before, closed once finished. Keyed on
//: the run, so a fold someone opened stays open across the re-render, and
//: `data-run-lines` lets the jobs stream refresh just its text.
function taskRunFold(key, lines, started, state) {
  const fold = document.createElement("details");
  fold.className = "task-log";
  fold.open = taskLogsOpen.has(key);
  fold.addEventListener("toggle", () => {
    if (fold.open) taskLogsOpen.add(key);
    else taskLogsOpen.delete(key);
  });
  const summary = document.createElement("summary");
  const pre = document.createElement("pre");
  pre.className = "task-log-lines";
  pre.dataset.runLines = key;
  pre.dataset.started = started || "";
  fold.dataset.state = state;
  fold.append(summary, pre);
  paintTaskRunLines(fold, lines);
  pre.addEventListener("scroll", () => {
    const isAtBottom = Math.abs(pre.scrollHeight - pre.scrollTop - pre.clientHeight) < 5;
    taskLogScrollStates.set(key, isAtBottom);
  });
  return fold;
}

function paintTaskRunLines(fold, lines) {
  const pre = fold.querySelector("pre");
  const key = pre.dataset.runLines;
  const verb = fold.dataset.state === "running" ? "What it's doing" : "What it did";
  fold.querySelector("summary").textContent = `${verb} (${nounCount(lines.length, "line")})`;
  pre.textContent = taskRunLinesText(lines, Number(pre.dataset.started) || 0);
  //: Follow the tail, the way a terminal does, unless the reader scrolled up.
  if (fold.open && taskLogScrollStates.get(key) !== false) {
    requestAnimationFrame(() => {
      pre.scrollTop = pre.scrollHeight;
    });
  }
}
