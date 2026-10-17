// chat-tasks.js: Settings, Tasks (the running and recent jobs, with the live
// output lines), moved out of ai-tools.js on 2026-10-12 for the boot gzip
// budget. It draws only when the Tasks pane is open, and every caller ignores
// the return value, so `LAZY_ENTRY_POINTS.chatTasks` (app.js) stands in for
// `renderTasks` and `renderTaskHistory` until this loads. `taskLineStream`,
// `taskElapsed`, `taskSteps` and `taskRunFold` stay in ai-tools.js: the
// status poll and the activity panel read them.

// The list is built by the server (GET /tasks), not assembled here from
// whatever happened to be in the model status. It used to know about exactly
// two jobs, a re-index and a model download, so the embedding model loading
// at startup and the SearXNG install, which is minutes long, ran with nothing
// on this screen to say so. Rendering whatever the server sends means the
// next background job appears here without touching this file.
// `payload` is the /tasks body when the caller has already fetched it, the
// status poll has, once, for the bar. Opening the panel passes nothing and
// fetches, so the list is filled the moment you get there rather than at the
// next tick.
async function renderTasks(payload) {
  const list = $("task-list");
  const body = payload || (await apiJson("/tasks", { silent: true }).catch(() => null));
  const jobs = (body && body.tasks) || [];
  list.replaceChildren();
  $("tasks-empty").classList.toggle("hidden", jobs.length > 0);
  for (const job of jobs) {
    const li = document.createElement("li");
    // The heading row is the job and its Quit button; everything else stacks
    // underneath at full width. The bar used to sit inline after the label,
    // where it ran off the right edge of the card on a long job name.
    const row = document.createElement("div");
    row.className = "entry-meta";
    const name = document.createElement("strong");
    name.textContent = job.label;
    row.appendChild(name);
    //: How long it has run, on the server's clock (INBOX 696); a waiting row
    //: says how long it has waited.
    if (job.started && body.now) {
      const took = document.createElement("span");
      took.className = "muted task-elapsed";
      took.textContent = `${job.queued ? "waiting " : ""}${taskElapsed(body.now - job.started)}${taskOriginWords(job.origin)}`;
      row.appendChild(took);
    }
    if (job.run_id) li.dataset.runId = job.run_id;

    if (job.cancellable) {
      const actions = document.createElement("span");
      actions.className = "entry-actions";
      actions.appendChild(
        //: "Stop" (INBOX 713, the owner: "manually stop or cancel them").
        smallButton("ph:stop-circle Stop", "Stop this job at its next step", async () => {
          // `/tasks/cancel`, not `/models/jobs/cancel`: the old endpoint knew
          // about a re-index and a model pull and nothing else, so this
          // button only ever appeared on two of the eight kinds this panel
          // lists. The server now answers for all of them and says what it
          // actually did: a pip install is terminated, an autonomous pass
          // stops at its next safe point and stays off for a while, an
          // embedding download stops after the file it is on. Reporting the
          // server's own sentence rather than a fixed "asked it to stop"
          // is the difference between the three.
          try {
            const result = await apiJson("/tasks/cancel", {
              method: "POST",
              body: JSON.stringify({ kind: job.kind, name: job.name || "" }),
            });
            toast(result.detail || (result.stopped ? "Stopping." : "It had already finished."));
          } catch (e) {
            toast(e.message, true);
          }
          renderTasks();
          refreshModelStatus();
        })
      );
      row.appendChild(actions);
    }
    li.appendChild(row);

    if (job.detail) {
      const detail = document.createElement("p");
      detail.className = "muted task-detail";
      detail.textContent = job.detail;
      li.appendChild(detail);
    }

    //: Every running row has a bar (INBOX 696, the owner: "they are just flat
    //: rows"): the real fraction where the job reports one, else an
    //: indeterminate bar, which guesses nothing; the elapsed time beside the
    //: name is what keeps moving under reduced motion. A waiting row has none.
    if (!job.queued) {
      const bar = document.createElement("progress");
      bar.className = "task-progress";
      if (typeof job.progress === "number") {
        bar.max = 1;
        bar.value = job.progress;
      }
      bar.setAttribute("aria-label", job.label);
      li.appendChild(bar);
    }
    //: A bulk install's packages, each with where it is.
    if ((job.steps || []).length) li.appendChild(taskSteps(job.steps));

    // What the job itself is printing. A bar answers "is it working?" only
    // while it moves, and pip can sit on one number for minutes, the output
    // is the thing that keeps changing, so it is the real answer to "has it
    // frozen?". Open by default while a job is running; there is nothing to
    // be spared from here.
    const lines = job.lines || (job.log || []).map((text) => ({ text }));
    if (lines.length) li.appendChild(taskRunFold(job.run_id || job.kind, lines, job.started, "running"));
    list.appendChild(li);
  }
  renderTaskHistory((body && body.history) || []);
  followTaskLines();
}

function taskOriginWords(origin) {
  return TASK_ORIGIN_WORDS[origin] ? `, ${TASK_ORIGIN_WORDS[origin]}` : "";
}

function taskLinesWanted() {
  return settingsModalOpen() && currentSettingsSection === "tasks" && !document.hidden;
}

async function followTaskLines() {
  if (taskLineStream.controller || !taskLinesWanted()) return;
  const controller = new AbortController();
  taskLineStream.controller = controller;
  try {
    while (taskLinesWanted() && !controller.signal.aborted) {
      const response = await api.stream("/jobs/stream?seconds=60", { silent: true, signal: controller.signal });
      if (!response.body) break;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffered = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done || !taskLinesWanted()) break;
        buffered += decoder.decode(value, { stream: true });
        const blocks = buffered.split("\n\n");
        buffered = blocks.pop();
        for (const block of blocks) {
          const isRuns = block.startsWith("event: runs\n");
          if (!isRuns && !block.startsWith("event: tasks\n")) continue;
          try {
            const body = JSON.parse(block.slice(block.indexOf("data: ") + 6));
            if (isRuns) paintLiveRunLines(body);
            else renderTasks(body);
          } catch {
            /* a torn block is not worth dropping the stream over */
          }
        }
      }
      reader.cancel().catch(() => {});
    }
  } catch {
    /* closed on purpose, or the server went: the poll still paints the rows */
  } finally {
    controller.abort();
    if (taskLineStream.controller === controller) taskLineStream.controller = null;
  }
}

function paintLiveRunLines(body) {
  for (const run of body.running || []) {
    const pre = document.querySelector(`#task-list pre[data-run-lines="${CSS.escape(run.id)}"]`);
    if (pre && (run.lines || []).length) paintTaskRunLines(pre.closest("details"), run.lines);
  }
}

function renderTaskHistory(history) {
  const box = $("task-history-box");
  const list = $("task-history");
  // A finished background job goes into the notifications centre whether or
  // not this screen is open, which is the point of the centre (§36E). These
  // jobs are long: an install or a re-index finishes minutes after you stopped
  // watching it, and until now the only record was a screen inside Settings
  // that you had to know to open. Recorded first, so it happens even when the
  // Tasks panel is not on screen and the two elements below are missing.
  for (const item of history) {
    //: A turn the person watched in its own surface (a chat answer) is in
    //: the list below, not announced: one notification per question asked
    //: would bury the ones that matter.
    if (item.origin === "you" && WATCHED_RUN_KINDS.has(item.kind)) continue;
    const key = `task:${item.kind || item.label}:${item.at}`;
    //: Its "Started:" row becomes the ending (INBOX 811 item 4): one row
    //: per run, never a stale "Started" left behind.
    if (settleStartedNotification(item, key)) continue;
    recordNotification({
      kind: item.outcome === "failed" ? "error" : "task",
      title: item.label,
      detail: item.detail || "",
      // Keyed on the job and when it stopped, so the three-second re-render
      // does not add the same finished job over and over.
      key,
    });
  }
  if (!box || !list) return;
  box.classList.toggle("hidden", history.length === 0);
  list.replaceChildren();
  for (const item of history) {
    const style = TASK_OUTCOMES[item.outcome] || TASK_OUTCOMES.completed;
    const li = document.createElement("li");
    if (style.className) li.className = style.className;

    const row = document.createElement("div");
    row.className = "entry-meta";
    const name = document.createElement("strong");
    setLabel(name, `${style.icon} ${item.label}`);
    const when = document.createElement("span");
    when.className = "muted";
    // Which model actually did the work (captioning, OCR, the weekly
    // digest): recorded by the backend all along (`taskhistory.record`'s
    // `name` param) but never shown here, so "which model answered this"
    // was answerable only by opening the log console. Asked about
    // directly (BACKLOG.md §95 item A.3).
    //: When, how long, how many times and who started it (INBOX 805).
    const took = jobDurationWords(item.duration_ms);
    when.textContent = [
      relativeTime(item.at),
      took ? `took ${took}` : "",
      item.count > 1 ? `${item.count} times` : "",
      TASK_ORIGIN_WORDS[item.origin] || "",
      item.name || "",
    ]
      .filter(Boolean)
      .join(" · ");
    //: Its log (the owner, 2026-10-10: "no way to view logs of bg
    //: processes"): Settings, Logs, filtered to this task (settings.js).
    row.append(name, taskLogButton(item));
    li.append(row, when);

    // The reason, which is the whole point for a failure, until now it
    // existed only in the log console, a screen you have to know to open.
    if (item.detail) {
      const detail = document.createElement("p");
      detail.className = "muted task-detail";
      setLabel(detail, item.detail);
      li.appendChild(detail);
    }
    if ((item.lines || []).length) li.appendChild(taskRunFold(item.run_id || item.at, item.lines, item.started, "finished"));
    list.appendChild(li);
  }
}
