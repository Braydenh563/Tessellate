// status-tasks.js: a background job starting and finishing, said out loud (`noticeTaskTransitions`,
// called by status.js's task poll). Moved out of status.js (LEDGER L698) to come out of the boot gzip
// budget: lazy, the `statusTasks` bundle with a stand-in in lazy-entries.js. `QUIET_TASK_KINDS` stays in
// status.js, because chat-tasks.js reads it without this file.

// --- a background job starting and finishing, said out loud --------------------
//
// Half of this existed and half did not, which is why it read as broken rather
// than as missing: `renderTaskHistory` records every *finish* into the
// notifications centre, but a **start** was recorded nowhere, and neither end
// was ever said out loud. So kicking off a re-index or an extras install and
// then going back to writing gave you no sign anything was happening and no
// sign when it stopped, the only trace was a screen inside Settings and a
// centre you had to open.
//
// What this adds is the transitions: a job appearing in `GET /tasks` and a job
// disappearing from it.
//
// The rule that keeps it from becoming noise: **a toast only for a job whose
// start this session actually saw.** These jobs run for minutes and the app
// may well have been opened halfway through one; announcing the end of
// something you were never told had begun is a notification about nothing.
// The centre still records both ends either way, because that is a record
// rather than an interruption.

//: The jobs seen running on the previous poll, keyed the way `taskKey` keys
//: them. A Map rather than a Set so a finish can name the job that ended
//: without needing the poll it vanished from to still carry it.
const seenRunningTasks = new Map();

//: The activity panel's row for each of those jobs, keyed the same way. Kept
//: beside `seenRunningTasks` rather than inside it because the two answer
//: different questions: that map is "did this session see it start", which is
//: what decides whether its end is announced, and this one is "which row on
//: screen is it".
const backgroundRunRows = new Map();

//: **A watched run that outlived its page** (L514): a transcription (or any
//: run its own surface watches) still running on the first poll after a
//: reload has no page watching it any more, so its ending is announced like
//: any other job's rather than passing in silence. Its start is not news.
//: (`polled` is a property, not a global: tests/test_global_scope_ratchet.py.)
function noticeTaskTransitions(running, history) {
  //: `name` distinguishes two downloads running at once; `kind` alone would
  //: merge them into one job that appears to start twice and finish once.
  //: Local, not a global (test_global_scope_ratchet).
  const taskKey = (task) => `${task.kind || "job"}:${task.name || ""}`;
  const now = new Map(running.map((task) => [taskKey(task), task]));
  const firstPoll = !noticeTaskTransitions.polled;
  noticeTaskTransitions.polled = true;

  //: A running job's row keeps its fraction and its own status line up to
  //: date. It is the same run list the chat's skill runs land in, an
  //: autonomous pass rewriting tags in the background is exactly the "agent
  //: model activity" the report was about, and reading it off `/tasks` is how
  //: it gets a progress bar the chat runs cannot have.
  for (const [key, task] of now) {
    const run = backgroundRunRows.get(key);
    if (!run) continue;
    run.progress = typeof task.progress === "number" ? task.progress : null;
    run.detail = task.detail || "";
    renderAgentRunSummary(run);
  }

  for (const [key, task] of now) {
    if (seenRunningTasks.has(key)) continue;
    seenRunningTasks.set(key, task);
    if (task.watched && firstPoll) task.orphaned = true;
    //: A chat answer, a transcription: the person is watching it where they
    //: started it. The status bar and Running jobs list it; nothing announces it.
    if (task.watched) continue;
    const run = addAgentRun({
      kind: "job",
      name: task.label,
      icon: "ph:gear",
      detail: task.detail || "",
    });
    run.progress = typeof task.progress === "number" ? task.progress : null;
    renderAgentRunSummary(run);
    backgroundRunRows.set(key, run);
    if (!QUIET_TASK_KINDS.has(task.kind)) openPanelForRun(run);
    //: Upkeep the app starts itself is not news for the bell: only its
    //: failure is, which agentActivityNotice records below (audit 1030 Y7).
    if (!QUIET_TASK_KINDS.has(task.kind)) task.noticeId = recordNotification({
      kind: "task",
      title: `Started: ${task.label}`,
      detail: task.detail || "",
      runId: task.run_id || "",
      // Keyed per *start*, not per job. It used to be `task-start:${key}`,
      // which deduped against localStorage, so the second time the
      // autonomous pass (or any recurring job) ran, its start recorded
      // nothing at all, forever, because an entry with that exact id was
      // already stored from the first run days earlier. The poll-repeat this
      // was defending against is already handled by `seenRunningTasks` two
      // lines up, which `continue`s before reaching here.
      key: `task-start:${key}:${Date.now()}`,
    });
  }

  for (const [key, task] of [...seenRunningTasks]) {
    if (now.has(key)) continue;
    seenRunningTasks.delete(key);
    const row = backgroundRunRows.get(key);
    backgroundRunRows.delete(key);
    if (task.watched && !task.orphaned) continue;
    // The outcome comes from the server's own history, on this same payload, 
    // "it stopped appearing in the running list" is true of a job that died as
    // much as one that succeeded, and a cheerful toast over a failure is how
    // people learn to ignore toasts. Newest first, so `find` takes the ending
    // that just happened rather than a previous run of the same job.
    const ended =
      history.find((item) => task.run_id && item.run_id === task.run_id) ||
      history.find((item) => (item.kind || "job") === (task.kind || "job"));
    //: Its "Started:" row now says how it ended (INBOX 811 item 4).
    if (task.noticeId) {
      const endKey = ended ? `task:${ended.kind || ended.label}:${ended.at}` : `${task.noticeId}:end`;
      settleNotification(task.noticeId, { key: endKey, ...taskEndingWords(ended, task.label) });
    }
    if (ended?.outcome === "failed") {
      endAgentRun(row, { state: "failed" });
      agentActivityNotice(`Failed: ${ended.label || task.label}`, { isError: true });
    } else if (ended?.outcome === "cancelled") {
      endAgentRun(row, { state: "stalled", detail: "cancelled" });
      // Not an error and not an achievement, the user stopped it and already
      // knows. Recorded in the centre by renderTaskHistory; no toast.
      continue;
    } else {
      endAgentRun(row, { state: "done" });
      if (!QUIET_TASK_KINDS.has(task.kind)) agentActivityNotice(`Finished: ${ended?.label || task.label}`);
    }
  }
}
