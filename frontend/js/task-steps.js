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
