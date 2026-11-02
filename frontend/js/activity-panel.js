// activity-panel.js: the Running tab of the Activity panel (WORLD_CLASS_PLAN
// 28.1 rule 5, decision 70). Lazy (LAZY_MODULES.activity): agent-activity.js
// opens the panel and loads this the first time the tab is shown.
//
// The list is the server's (`GET /activity`): every row `routes_tasks.collect`
// draws, the booked runs it does not, and what registered with
// `core/activity.py` (an answer streaming, a transcription, a reading). This
// file renders whatever it is given, so a new kind of job needs no edit here.

//: Polled while the tab is in view, every two seconds: the bar is the answer
//: to "is it still working?", and a slower bar reads as frozen.
const ACTIVITY_POLL_MS = 2000;
const activityPoll = { timer: null };

function activityRunningShown() {
  return !$("agent-monitor").classList.contains("hidden") && !$("activity-running").classList.contains("hidden");
}

async function renderActivity() {
  clearTimeout(activityPoll.timer);
  if (!activityRunningShown()) return;
  const body = await apiJson("/activity", { silent: true }).catch(() => null);
  if (body) paintActivity(body);
  activityPoll.timer = setTimeout(renderActivity, ACTIVITY_POLL_MS);
}
window.renderActivity = renderActivity;

function activityModelLine(model) {
  const line = $("activity-model");
  if (!model || !model.model) {
    line.textContent = "No chat model is set.";
    return;
  }
  const where = model.loaded === true ? "in memory" : model.loaded === false ? "not in memory" : "state unknown";
  line.textContent = `Model: ${model.model}, ${where}.`;
}

function activityRow(job, now) {
  const li = document.createElement("li");
  li.dataset.jobId = job.id;
  const row = document.createElement("div");
  row.className = "entry-meta";
  const name = document.createElement("strong");
  //: The run's own words ("Answering 'what is a mouse'") over its kind's.
  name.textContent = job.title || job.label;
  row.appendChild(name);
  if (job.finished) {
    const done = document.createElement("span");
    done.className = "muted task-elapsed";
    done.textContent = activityEnding(job);
    if (job.origin) done.title = `${job.origin[0].toUpperCase()}${job.origin.slice(1)}.`;
    row.appendChild(done);
  } else if (job.started && now) {
    const took = document.createElement("span");
    took.className = "muted task-elapsed";
    took.textContent = `${job.queued ? "waiting " : ""}${taskElapsed(now - job.started)}`;
    row.appendChild(took);
  }
  if (job.stoppable || job.report) {
    const actions = document.createElement("span");
    actions.className = "entry-actions";
    if (job.stoppable) actions.appendChild(smallButton("ph:stop-circle Stop", `Stop ${job.label.toLowerCase()} at its next step`, () => stopActivityJob(job.id)));
    //: A finished job with a page (an import's report, WORLD_CLASS 25b).
    if (job.report) actions.appendChild(smallButton("ph:file-text Report", `Open the report of ${job.label.toLowerCase()}`, () => openActivityReport(job.report)));
    row.appendChild(actions);
  }
  li.appendChild(row);
  if (job.detail) {
    const detail = document.createElement("p");
    detail.className = "muted task-detail";
    detail.textContent = job.detail;
    li.appendChild(detail);
  }
  //: Its lines (INBOX 805): what it has done so far, in a fold that stays
  //: open across the two-second repaint (`taskRunFold`, ai-tools.js).
  if ((job.lines || []).length) li.appendChild(taskRunFold(job.run_id || job.id, job.lines, job.started, job.finished ? "finished" : "running"));
  if (!job.queued && !job.finished) {
    const bar = document.createElement("progress");
    bar.className = "task-progress";
    if (typeof job.progress === "number") {
      bar.max = 1;
      bar.value = job.progress;
    }
    bar.setAttribute("aria-label", job.label);
    li.appendChild(bar);
  }
  return li;
}

//: How a finished run ended, how long it took and when (INBOX 805, B77: "how
//: long it took to file"): "Finished in 2.4 s at 10:04 pm".
const ACTIVITY_ENDINGS = { failed: "Failed after", cancelled: "Stopped after" };

function activityDuration(ms) {
  if (typeof ms !== "number") return "";
  if (ms < 1000) return `${Math.max(1, Math.round(ms))} ms`;
  return ms < 10000 ? `${(ms / 1000).toFixed(1)} s` : taskElapsed(ms / 1000);
}

function activityEnding(job) {
  const took = activityDuration(job.duration_ms);
  const verb = ACTIVITY_ENDINGS[job.outcome] || (took ? "Finished in" : "Finished");
  const at = new Date(job.finished * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const times = job.count > 1 ? `, ${job.count} times` : "";
  return `${verb}${took ? ` ${took}` : ""} at ${at}${times}`;
}

function paintActivity(body) {
  activityModelLine(body.model);
  const jobs = body.jobs || [];
  $("activity-list").replaceChildren(...jobs.map((job) => activityRow(job, body.now)));
  $("activity-empty").classList.toggle("hidden", jobs.length > 0);
  //: Finished lines (an import with its report), under what is running. The
  //: result line is the job record's, written lower case for "Last run ...".
  const finished = (body.finished || []).map((job) => {
    const detail = job.detail ? job.detail[0].toUpperCase() + job.detail.slice(1) : "";
    const li = activityRow({ ...job, detail }, 0);
    li.classList.add("is-finished");
    return li;
  });
  $("activity-finished").replaceChildren(...finished);
  $("activity-finished-card").classList.toggle("hidden", !finished.length);
  $("activity-count-running").textContent = String(jobs.length);
}

//: The report sheet lives with the importers (app-import.js, lazy).
async function openActivityReport(id) {
  if (await ensureModule("appImport")) openImportReport(id);
}

async function stopActivityJob(id) {
  try {
    const result = await apiJson(`/activity/${encodeURIComponent(id)}/stop`, { method: "POST" });
    toast(result.detail || (result.stopped ? "Stopping." : "It had already finished."), "info");
  } catch (e) {
    toastAction(`Could not stop that job: ${e.message}`, "Try again", () => stopActivityJob(id));
  }
  renderActivity();
}

async function stopActivityModel() {
  try {
    const result = await apiJson("/activity/model/stop", { method: "POST" });
    toast(result.detail, "info");
  } catch (e) {
    toastAction(`Could not stop the model: ${e.message}`, "Try again", stopActivityModel);
  }
  renderActivity();
}
window.stopActivityModel = stopActivityModel;

async function stopAllActivity() {
  const body = await apiJson("/activity", { silent: true }).catch(() => null);
  const jobs = ((body && body.jobs) || []).filter((job) => job.stoppable);
  if (!jobs.length) {
    toast("Nothing running can stop part way.", "info");
    return;
  }
  let error = null;
  const asked = await Promise.all(
    jobs.map((job) =>
      apiJson(`/activity/${encodeURIComponent(job.id)}/stop`, { method: "POST" }).then(
        () => 1,
        (caught) => {
          error = error || caught;
          return 0;
        },
      ),
    ),
  );
  const stopped = asked.reduce((sum, one) => sum + one, 0);
  if (stopped) toast(`Asked ${nounCount(stopped, "job")} to stop.`, "info");
  if (error) toast(error.message, true);
  renderActivity();
}
window.stopAllActivity = stopAllActivity;

// --- The panel's tabs and its ⋯, wired once when this file loads ----------

function setActivityTab(name) {
  for (const tab of document.querySelectorAll("#activity-tabs [role=tab]")) {
    const on = tab.dataset.value === name;
    tab.setAttribute("aria-selected", String(on));
    tab.tabIndex = on ? 0 : -1;
  }
  $("activity-running").classList.toggle("hidden", name !== "running");
  $("activity-runs").classList.toggle("hidden", name !== "runs");
  //: The broom and the log are the runs' own controls.
  $("agent-monitor-clear")?.classList.toggle("hidden", name !== "runs");
  $("agent-monitor-log-toggle")?.classList.toggle("hidden", name !== "runs");
  if (name === "running") renderActivity();
}
window.setActivityTab = setActivityTab;

for (const tab of document.querySelectorAll("#activity-tabs [role=tab]")) {
  tab.addEventListener("click", () => setActivityTab(tab.dataset.value));
  tab.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const next = tab.dataset.value === "running" ? "runs" : "running";
    setActivityTab(next);
    document.querySelector(`#activity-tabs [data-value="${next}"]`)?.focus();
  });
}

//: The panel's ⋯ (the `kebabMenu` recipe): what acts on the whole panel.
{
  const slot = $("activity-more");
  const menu = kebabMenu([
    { label: "ph:stop-circle Stop the model", title: "Stop any answer and unload the model from memory", run: stopActivityModel },
    { label: "ph:stop Stop everything", title: "Stop every job that can stop part way", run: stopAllActivity },
    { label: "ph:terminal-window Show the log", title: "The agent's log lines, on the Agent runs tab", group: "runs", run: () => {
      setActivityTab("runs");
      setAgentMonitorLogVisible(true);
    } },
    { label: "ph:broom Clear finished runs", title: "Clear finished runs", group: "runs", run: () => $("agent-monitor-clear")?.click() },
    { label: "ph:gear Background tasks settings", title: "History, last runs and schedules", group: "settings", run: () => openSettingsModal("tasks") },
  ], "More activity actions");
  menu.id = "activity-more";
  menu.querySelector("button")?.classList.add("dialog-head-btn");
  slot?.replaceWith(menu);
}
