// ai-tools.js: the tasks manager, a model per feature, improve writing,
// tensions, link suggestions, keeping the look. Moved out of app.js on
// 2026-09-26 as one contiguous range (INBOX 426 cc,
// docs/roadmap/agent-remaining/appjs-split.md). A classic script sharing
// app.js's globals, loaded in app.js's old order; nothing in an earlier file
// calls into it while the page loads (scratchpad/appjs-map.js --check).

// --- Wave N: tasks manager (see and quit background jobs) ---------------------------


//: Who started a run, after its time: ", you started it" (INBOX 805).
const TASK_ORIGIN_WORDS = {
  you: "you started it",
  schedule: "on its schedule",
  "start-up": "at start-up",
  app: "the app",
};

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
  fold.querySelector("summary").textContent = `${verb} (${lines.length} line${lines.length === 1 ? "" : "s"})`;
  pre.textContent = taskRunLinesText(lines, Number(pre.dataset.started) || 0);
  //: Follow the tail, the way a terminal does, unless the reader scrolled up.
  if (fold.open && taskLogScrollStates.get(key) !== false) {
    requestAnimationFrame(() => {
      pre.scrollTop = pre.scrollHeight;
    });
  }
}

//: **The panel reads the jobs stream** (`GET /jobs/stream`), not a poll of
//: its own: while Settings, Running jobs is open, its `tasks` event repaints
//: the rows (one recipe, `renderTasks`) when they change, and its `runs`
//: event moves each running row's lines as the run says them (Brief 9).
//: Fetch, not EventSource, for the auth header (settings.js
//: `startLogStream` says why).
const taskLineStream = { controller: null };




// "45 s", "3 min 05 s", "1 h 12 min".
function taskElapsed(seconds) {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`;
  return `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
}

//: One line per package of a bulk action: waiting, in hand, done or not.
//: Shared with the bundle rows in Settings, Packages (settings-packages.js).
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

// What has stopped, newest first. Separate from the running list on purpose:
// mixing them means a finished job and a running one look alike at a glance,
// and the question this screen answers most often is "is it still going?".
const TASK_OUTCOMES = {
  completed: { icon: "ph:check-circle", className: "" },
  failed: { icon: "ph:warning", className: "task-failed" },
  // Not an error. Reporting a user's own decision in red is how people learn
  // to ignore red.
  cancelled: { icon: "ph:x", className: "muted" },
};


//: Run kinds a person starts and watches where they started them (an answer
//: streaming in the chat): `routes_tasks.WATCHED_KINDS`.
const WATCHED_RUN_KINDS = new Set(["generation", "transcription", "ocr", "run"]);

// Which task logs the user has opened, kept across the 3-second re-render so
// a fold doesn't slam shut under them.
const taskLogsOpen = new Set(["searxng"]);
const taskLogScrollStates = new Map();

// Model pickers (rewritten, Wave O). The old version let the status poll
// (every ~3s while Settings is open) reset the dropdown to the SAVED
// model, so a selection would "switch back after a few seconds".
//
// New rule, dead simple: the option list is (re)built ONLY when the SET
// of installed model names actually changes (order-independent: Ollama
// doesn't return a stable order). The selected value is set once, when
// the list is first built; after that a poll never touches `.value`, so
// your choice stays put until you Apply (which re-syncs to the new saved
// value). No timing-sensitive "userChosen" flag to get wrong.
function _namesSignature(names) {
  return [...names].sort().join("|");
}

function fillModelSelect(select, names, extraFirst, savedValue) {
  //: `extraFirst` started as one leading option ("Inherited: X"); the model-
  //: per-feature select needs three (Inherited, Same as chat model, Same as
  //: utility model, INBOX 430), so it takes an array too now. Every existing
  //: caller still passes a single object or null, unchanged.
  const extras = Array.isArray(extraFirst) ? extraFirst.filter(Boolean) : extraFirst ? [extraFirst] : [];
  const wanted = [...extras.map((e) => e.value), ...names];
  const signature = _namesSignature(wanted);
  if (select.dataset.sig === signature) return; // same options → leave it alone
  select.dataset.sig = signature;
  const previous = select.value; // preserve a live selection across a rebuild
  select.replaceChildren();
  for (const extra of extras) {
    const option = document.createElement("option");
    option.value = extra.value;
    option.textContent = extra.label;
    select.appendChild(option);
  }
  for (const name of names) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  }
  // Prefer the value already showing; else the saved preference.
  const values = [...select.options].map((o) => o.value);
  const match =
    (previous && values.includes(previous) && previous) ||
    values.find((v) => v === savedValue) ||
    values.find((v) => v.split(":")[0] === savedValue);
  if (match !== undefined) select.value = match;
}

function renderChatModelPicker(status) {
  const names = status.installed_models.map((m) => m.name);
  fillModelSelect($("chat-model-select"), names, null, status.chat_model);
  //: The name beside the model, which is INBOX 225's decision for this
  //: screen: the app speaks as Atlas everywhere else, and "Active: qwen2.5:7b"
  //: was the one place it went back to naming the machinery. Both halves are
  //: here on purpose, "which model" is the question this line exists to
  //: answer and the name alone would not answer it.
  //: Never chosen (a fresh install's default) is not "was running" (the
  //: owner, 2026-10-07); a start-up choice says why, once more, here.
  $("chat-model-note").textContent =
    status.chat_model_installed === false
      ? status.chat_model_chosen === false
        ? "No chat model is chosen yet. Pick one you have, or download one below."
        : `${aiNameNow()} was running “${status.chat_model}”, which is not installed any more. Pick another or download it below.`
      : `${aiNameNow()}, running ${status.chat_model}${status.chat_model_chosen_why ? ` (chosen at start: ${status.chat_model_chosen_why})` : ""}`;
  //: B65: "Use this model" needs a model to pick; "Stop the model" needs
  //: something to stop. Both were enabled with no model at all.
  $("chat-model-apply").disabled = !names.length;
  const stop = $("chat-model-stop");
  const noModel = status.chat_model_installed === false;
  stop.disabled = noModel; // the rest waits for /activity, so a poll does not flicker it
  stop.title = noModel ? "No model is running" : "Stop any answer and unload the model from memory";
  //: Whether it is in memory now, beside its Stop (rule 5). Stop is live only
  //: while the model is in memory or an answer can still be stopped.
  apiJson("/activity", { silent: true })
    .then((body) => {
      const loaded = body && body.model ? body.model.loaded : null;
      const answering = ((body && body.jobs) || []).some((job) => job.stoppable);
      stop.disabled = noModel || !(loaded === true || answering);
      if (stop.disabled && !noModel) stop.title = "The model is not in memory, and no answer is running";
      if (loaded === null || noModel) return;
      $("chat-model-note").textContent += loaded ? ", in memory now" : ", not in memory";
    })
    .catch(() => {
      stop.disabled = noModel;
    });
}

// Nielsen #6, recognition over recall: which model answers was previously
// knowable only by opening Settings → Models, and only then if the backend
// is Ollama (the picker above is gated on ollama_running). status.chat_model
// itself isn't backend-specific, so this reads it straight off the poll
// loop instead of piggybacking on that gated render.
function renderChatActiveModelBadge() {
  const badge = $("chat-active-model");
  if (!badge) return;
  //: **The Chat tab's own model, which is not always the app's.** Since the
  //: chat tab is a row in `model_manager.FEATURES` it can be pinned to a
  //: model of its own, and a pill reading the global `chat_model` would then
  //: name a model this tab is not using: the one thing this badge exists to
  //: report, wrong, on the surface it reports for. The row is already
  //: resolved by the server, so this is a lookup rather than a second rule.
  const pinned = (modelStatus && modelStatus.feature_models || []).find(
    (row) => row.key === "chat" && row.overridden
  );
  //: `chat_model_effective`, not `chat_model`: on a llama.cpp or LM Studio
  //: server the configured name is not what answers when that server has a
  //: different model loaded (owner: the header said llama3.2, which was not
  //: installed, while another model answered). On Ollama a missing model
  //: is said to be missing rather than named as if it ran.
  const name = (pinned && pinned.model)
    || (modelStatus && (modelStatus.chat_model_effective || modelStatus.chat_model));
  const missing = !pinned && modelStatus?.chat_model_installed === false
    && name === modelStatus.chat_model;
  //: **No model connected, no model named** (the owner: "if an ai model
  //: isnt connected, it shouldnt show a model being used right??"). The
  //: header named the configured model in accent, as if it were answering,
  //: directly above the composer's own "No model is connected". Same signal
  //: the composer and Ask use (`syncModelGatedControls`), so the three can
  //: never disagree; pressing it goes straight to connecting one.
  //:
  //: **And then said once, not twice** (the owner, 2026-09-24: "No model
  //: connected" in this badge and again in the composer's notice under it).
  //: The composer's notice (`#chat-offline`, `renderAiOfflineNotice`) is the
  //: statement that says what still works and carries the button that
  //: connects one, so it is the one kept; the badge steps aside while no
  //: model is running, and names the model again the moment one is.
  if (modelStatus && modelStatus.ollama_running === false) {
    badge.hidden = true;
    badge.classList.add("is-missing");
    badge.textContent = "";
    badge.title = "";
    badge.dataset.offline = "1";
    return;
  }
  delete badge.dataset.offline;
  badge.hidden = !name;
  badge.classList.toggle("is-missing", Boolean(missing));
  //: The short form in the badge, the full id in the tooltip below, the
  //: badge is 22ch wide and a HuggingFace id is routinely longer than that.
  badge.textContent = missing ? `${shortModelName(name)} (not installed)` : shortModelName(name);
  // The badge itself ellipsis-truncates a long id (a full HuggingFace path
  // easily runs past the header), the full name is still one hover away.
  badge.title = !name
    ? ""
    : missing
      ? `${name} is set for chat but is not installed: click to pick a model you have`
      : `${aiNameNow()} is answering with ${name}: click for what it is and what it can do`;
}

//: **What this model actually is.** Asked for: "in chat I want more details in
//: features, including model attributes, token expense distribution, more
//: features."
//:
//: `GET /models/spec` has existed since §11, size, quantisation, family, the
//: declared window against the one the app will really run it at, and the
//: tri-state capability flags: and **nothing in the frontend had ever called
//: it.** A whole endpoint that never ran once, which is this repo's second
//: recurring failure shape. It answers the first question anyone has when a
//: model behaves oddly ("can this one even use tools?") and the answer was
//: only discoverable by trying it and reading the failure.
//:
//: Pressing the badge opens this rather than jumping straight to Settings: the
//: panel is what you wanted nine times in ten, and "change it" is a button
//: inside it for the tenth.
//: Places the panel under the badge, in viewport coordinates. It is
//: `position: fixed` (see the stylesheet's own note on why `absolute` put it
//: off the bottom of the screen), so nothing positions it but this.
function placeChatModelPanel() {
  const panel = $("chat-model-panel");
  const badge = $("chat-active-model");
  if (!panel || !badge || panel.classList.contains("hidden")) return;
  const margin = 8;
  panel.style.left = "0px";
  panel.style.top = "0px";
  const anchor = badge.getBoundingClientRect();
  const box = panel.getBoundingClientRect();
  let left = anchor.left;
  if (left + box.width > window.innerWidth - margin) {
    left = window.innerWidth - margin - box.width;
  }
  if (left < margin) left = margin;
  let top = anchor.bottom + margin;
  if (top + box.height > window.innerHeight - margin) {
    // Above the badge when there is no room below it, and pinned inside the
    // window when there is room neither way, never off the edge, which is
    // the whole bug this is here to end.
    const above = anchor.top - margin - box.height;
    top = above >= margin ? above : Math.max(margin, window.innerHeight - margin - box.height);
  }
  panel.style.left = `${Math.round(left)}px`;
  panel.style.top = `${Math.round(top)}px`;
}

//: The panel fills in asynchronously (`GET /models/spec`), and it grows when
//: it does: so it is placed again once the content lands, and on any resize
//: or scroll that moves the badge out from under it.
window.addEventListener("resize", placeChatModelPanel);
window.addEventListener("scroll", placeChatModelPanel, true);

async function openChatModelPanel() {
  const name = modelStatus && modelStatus.chat_model;
  const panel = $("chat-model-panel");
  if (!panel || !name) return;
  panel.replaceChildren();
  const head = document.createElement("div");
  head.className = "row space-between chat-model-panel-head";
  const title = document.createElement("strong");
  title.textContent = name;
  title.className = "chat-model-panel-name";
  head.appendChild(title);
  const close = smallButton("ph:x", "Close", () => panel.classList.add("hidden"));
  close.classList.add("icon-only");
  head.appendChild(close);
  panel.appendChild(head);

  const list = document.createElement("dl");
  list.className = "chat-model-facts";
  const loading = document.createElement("p");
  loading.className = "muted";
  setLabel(loading, "ph:spin Reading the model's own specification…");
  panel.append(list, loading);
  panel.classList.remove("hidden");
  placeChatModelPanel();

  const spec = await apiJson(`/models/spec?name=${encodeURIComponent(name)}`).catch(() => null);
  //: The panel was measured empty a moment ago; it is a different height now.
  placeChatModelPanel();
  loading.remove();
  if (!spec) {
    const failed = document.createElement("p");
    failed.className = "muted";
    //: Named as a *backend* silence rather than a model fault: the usual cause
    //: is that Ollama is not running, and "unknown" with no reason sends
    //: people looking at the wrong thing.
    failed.textContent =
      "The backend didn't answer. This needs the model runner to be up, everything else in this panel comes from it.";
    panel.appendChild(failed);
    return;
  }
  const fact = (label, value, why) => {
    if (value === null || value === undefined || value === "") return;
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = String(value);
    if (why) dd.title = why;
    list.append(dt, dd);
  };
  fact("Family", spec.family, "The architecture this model is built on");
  fact("Size", spec.parameters, "How many parameters it has");
  fact("Quantisation", spec.quantisation, "How much its weights were compressed to fit in memory");
  if (spec.context_length) {
    fact(
      "Declared window",
      `${compactTokens(spec.context_length)} tokens`,
      "What the model says it can hold"
    );
  }
  if (spec.usable_context) {
    fact(
      "Used here",
      `${compactTokens(spec.usable_context)} tokens`,
      "What this app actually runs it at, often lower on purpose, to leave room for the key/value cache"
    );
  }
  //: Tri-state, and rendered as three states. `null` means this backend does
  //: not say, and drawing that as "No" would be a confident lie about a model
  //: that works fine: the endpoint's own docstring makes the same point.
  const flag = (value) => (value === null || value === undefined ? "Not reported" : value ? "Yes" : "No");
  fact("Can call tools", flag(spec.supports_tools), "Whether agent mode can work with this model");
  fact("Can show its reasoning", flag(spec.supports_thinking));
  fact("Can see images", flag(spec.supports_vision), "Whether it can read a picture or a scanned page");

  const change = smallButton("ph:gear Change the model", "Open Settings → Models", () => {
    panel.classList.add("hidden");
    openSettingsModal("models", "chat-model-select");
  });
  panel.appendChild(change);
}

$("chat-active-model")?.addEventListener("click", () => {
  if ($("chat-active-model").dataset.offline) {
    openSettingsModal("models");
    return;
  }
  const panel = $("chat-model-panel");
  if (panel && !panel.classList.contains("hidden")) {
    panel.classList.add("hidden");
    return;
  }
  openChatModelPanel();
});

function renderUtilityModelPicker(status) {
  const names = status.installed_models.map((m) => m.name);
  fillModelSelect(
    $("utility-model-select"),
    names,
    { value: "", label: "Same as chat model" },
    status.utility_model || ""
  );
  //: INBOX 277. The select shows what is stored; this line says what runs.
  //: The two differ exactly when smart model routing is off, and the server
  //: decides which (`ModelManager.utility_resolution`), so this only words
  //: the reason it was given rather than repeating the rule.
  const note = $("utility-model-note");
  if (!note) return;
  const resolved = status.utility_model_resolved || status.chat_model || "";
  const reasons = {
    routing_off: `Background jobs run on ${resolved}, the chat model, because smart model routing is off.`,
    unset: `Background jobs run on ${resolved}, the chat model, until you choose another.`,
    chosen: `Background jobs run on ${resolved}.`,
  };
  note.textContent = resolved ? reasons[status.utility_model_reason] || `Background jobs run on ${resolved}.` : "";
}

function renderVisionModelPicker(status) {
  const names = status.installed_models.map((m) => m.name);
  fillModelSelect(
    $("vision-model-select"),
    names,
    // The one model preference in this app that does NOT default to "same
    // as chat model" (model_manager.py's vision_model() explains why: a
    // chat model silently can't see images more often than it can).
    { value: "", label: "Auto-detect" },
    status.vision_model || ""
  );
  // Auto-detect is a choice with no fixed answer, say what it resolved to
  // right now, the same reason chat-model-note exists, rather than leaving
  // "Auto-detect" to mean nothing concrete in the UI.
  const note = $("vision-model-note");
  if (status.vision_model) {
    note.textContent = `Active: ${status.vision_model}`;
  } else if (status.vision_model_resolved) {
    note.textContent = `Auto-detect, currently ${status.vision_model_resolved}`;
  } else {
    note.textContent =
      "Auto-detect: no installed model reports it can see images yet.";
  }
}

// --- a model per feature -----------------------------------------------------
//
// Asked for directly: *"allow the user to alter the model they use for that
// specific feature if they wish ... individually altered and reset and for
// there to be a mass reset."*
//
// The rows are drawn from `/models/status`'s `feature_models`, which the
// server has already resolved: each row carries the model in use, what it
// inherits, and whether the first of those is this feature's own choice. So
// this file never has to know which role a feature falls back to, and the next
// feature appears here by being added to `model_manager.FEATURES`, with no
// change to any of the code below.
//
// The same data drives the inline picker in each surface's own ⋯, so the two
// places a model can be changed are one list read twice and cannot disagree.

//: The last rows the poll delivered. Read by the inline pickers, which open
//: from a menu and cannot wait for a round trip before drawing themselves.
let featureModelRows = [];
let featureModelNames = [];
//: The two sentinel values `/models/feature-model` accepts for "Same as
//: chat model" / "Same as utility model" (INBOX 430), read from the status
//: poll rather than hardcoded, so this file never has to carry a string
//: that only means something because it matches model_manager.py's own
//: constant.
let featureModelFollow = { chat: "", utility: "" };

function featureModelRow(key) {
  return featureModelRows.find((row) => row.key === key) || null;
}

//: What a row says about itself under its name. This is the fact the control
//: beside it cannot carry: a select showing "llama3.2" looks the same whether
//: that name was chosen for this feature, arrived from the chat model, or is
//: this feature explicitly following the *other* role on purpose.
function featureModelState(row) {
  if (row.override_kind === "chat") return `Same as chat model (currently ${row.model})`;
  if (row.override_kind === "utility") return `Same as utility model (currently ${row.model})`;
  return row.overridden
    ? `Its own model: ${row.model}`
    : `Inherited: ${row.inherits}`;
}

//: The toast names what was actually chosen, never the raw sentinel: "now
//: uses __follow_chat_model__" would mean nothing to anyone reading it.
function featureModelChoiceLabel(name) {
  if (name === featureModelFollow.chat) return "the chat model";
  if (name === featureModelFollow.utility) return "the utility model";
  return name;
}

async function applyFeatureModel(key, name) {
  const row = featureModelRow(key);
  try {
    await api("/models/feature-model", {
      method: "POST",
      body: JSON.stringify({ feature: key, name }),
    });
    const label = row ? row.label : "This feature";
    toast(
      name
        ? `${label} now uses ${featureModelChoiceLabel(name)}.`
        : `${label} is back on its default model.`
    );
    refreshModelStatus();
  } catch (error) {
    toast(error.message || "Couldn't set that model.", true);
    refreshModelStatus();
  }
}

function renderFeatureModels(status) {
  featureModelRows = status.feature_models || [];
  featureModelNames = (status.installed_models || []).map((m) => m.name);
  featureModelFollow = status.feature_model_follow || featureModelFollow;
  syncFeatureModelSelects();
  const list = $("feature-models-list");
  if (!list) return;
  list.replaceChildren();
  list.removeAttribute("aria-busy");
  for (const row of featureModelRows) {
    const line = document.createElement("div");
    line.className = "feature-model-row";
    line.dataset.feature = row.key;
    //: Read by the stylesheet, which tints the state line of a row that is on
    //: a model of its own: the list's only job is to make those findable.
    line.dataset.overridden = row.overridden ? "1" : "0";

    const name = document.createElement("div");
    name.className = "feature-model-name";
    const label = document.createElement("span");
    label.className = "feature-model-label";
    label.textContent = row.label;
    const state = document.createElement("span");
    state.className = "feature-model-state";
    state.textContent = featureModelState(row);
    state.title = row.note || "";
    name.append(label, state);

    const select = document.createElement("select");
    select.setAttribute("aria-label", `Model for ${row.label}`);
    select.title = `Model for ${row.label}`;
    //: The "inherited" option names what it inherits, so the list can be read
    //: without opening anything: every row says which model it is on. The two
    //: "Same as ..." options (INBOX 430) are the sentinels themselves, so
    //: picking one round-trips to `applyFeatureModel` unchanged and the
    //: backend stores the sentinel, not a name that would go stale the next
    //: time that role's model changes.
    let savedValue = "";
    if (row.override_kind === "model") savedValue = row.override_value;
    else if (row.override_kind === "chat") savedValue = featureModelFollow.chat;
    else if (row.override_kind === "utility") savedValue = featureModelFollow.utility;
    fillModelSelect(
      select,
      featureModelNames,
      [
        { value: "", label: `Inherited: ${row.inherits}` },
        { value: featureModelFollow.chat, label: "Same as chat model" },
        { value: featureModelFollow.utility, label: "Same as utility model" },
      ],
      savedValue
    );
    select.addEventListener("change", () => applyFeatureModel(row.key, select.value));

    //: Disabled until the row is overridden, because a reset on a row that is
    //: already on its default is a control that does nothing when pressed.
    const reset = smallButton(
      "ph:arrow-counter-clockwise",
      row.overridden
        ? `Reset ${row.label} to the model it inherits`
        : `${row.label} is already on the model it inherits`,
      () => applyFeatureModel(row.key, "")
    );
    //: Named, because `enhanceSelect` wraps the select beside it in a shell
    //: with a button of its own: "the first button in the row" stopped being
    //: this one the moment the select was enhanced.
    reset.classList.add("icon-only", "feature-model-reset");
    reset.disabled = !row.overridden;

    line.append(name, select, reset);
    list.appendChild(line);
  }

  const count = Number(status.feature_models_overridden || 0);
  const reset = $("feature-models-reset");
  const note = $("feature-models-reset-note");
  if (reset) {
    //: The mass reset says how many it would clear and does nothing when the
    //: answer is none, rather than reporting success over a no-op.
    reset.disabled = count === 0;
    reset.title = count
      ? `Hand ${count === 1 ? "one feature" : `${count} features`} back to the model they inherit`
      : "No feature has a model of its own yet";
  }
  if (note) {
    note.textContent = count === 0
      ? "No feature has a model of its own yet."
      : count === 1
        ? "One feature is on a model of its own."
        : `${count} features are on models of their own.`;
  }
}


//: The menu row every surface uses to reach the picker above. One label, one
//: place, so the three surfaces cannot drift apart in wording.
function featureModelMenuItem(key) {
  const row = featureModelRow(key);
  return {
    label: "ph:cube Model for this feature",
    //: A static title on purpose. These menus are built once and the model
    //: can change under them, so the state is named by the sheet, which is
    //: built at the moment it opens, rather than by a row that would go stale.
    title: "Pick the model this feature runs on",
    run: () => openFeatureModelSheet(key),
  };
}

//: **The model picker inside a surface.** The owner, 2026-09-23: "I want to be
//: able to change the model I use within the features themselves using a model
//: dropdown which pairs with the feature-specific model selections in
//: settings". The sheet above, behind the Chat tab's ⋯, was the only way in
//: there, and the Ask box had none. A plain `<select>` in the surface's own
//: composer (DESIGN.md: a dropdown of values is a `<select>`, and
//: `enhanceSelect` styles it), written through `applyFeatureModel`, the one
//: call Settings' own list makes, and redrawn from the same rows on every
//: status poll: changing either moves the other on the next tick, and
//: neither keeps a copy of its own.
//:
//: **It names the model that will run** (INBOX 277: "a role can say one model
//: and silently run another"). The first option is "Inherited: <name>", the
//: name the server resolves through the role, smart routing included, rather
//: than a bare "Default"; and an override that is not in the installed list
//: (the model server is down, or the model was removed) is still offered, so
//: the control never shows one model while the turn runs on another.
const FEATURE_MODEL_SELECTS = [
  ["chat-feature-model", "chat"],
  ["ask-feature-model", "ask"],
  ["draft-feature-model", "writing"],
];

function syncFeatureModelSelects() {
  for (const [id, key] of FEATURE_MODEL_SELECTS) {
    const select = $(id);
    if (!select) continue;
    const row = featureModelRow(key);
    //: No rows yet (the first poll has not answered, or the app is locked):
    //: a control that would write a guess is worse than a disabled one.
    select.disabled = !row;
    if (!row) continue;
    const names = [...featureModelNames];
    if (row.overridden && !names.includes(row.model)) names.unshift(row.model);
    //: **Never name a model that will not run as if it will** (INBOX 277).
    //: With no backend connected the inherited name is only the configured
    //: default: measured, the picker said "Inherited: llama3.2" under a banner
    //: saying no model is connected.
    //: Installed by the server's own rule (`_name_matches`: "llama3.2" is an
    //: installed "llama3.2:latest"), and the server's own verdict on the chat
    //: model wins over this list: measured, an installed
    //: `hf.co/...:UD-Q4_K_XL` read "(not installed)" from a literal compare.
    //: The short name in the label, the full id in the tooltip: the long
    //: form made the Ask header's picker 1,200px wide.
    const installedNames = new Set(featureModelNames.flatMap((n) => [n, String(n).split(":")[0]]));
    const serverSaysInstalled = row.inherits === modelStatus?.chat_model
      && modelStatus?.chat_model_installed === true;
    const isInstalled = serverSaysInstalled || installedNames.has(row.inherits)
      || modelStatus?.chat_model_installed == null;
    //: No model server answering is its own case, and it comes first: the
    //: install check reads "unknown" as installed, so a disconnected app still
    //: said "Inherited: llama3.2" under the no-model banner (the owner: "if an
    //: ai model isnt connected, it shouldnt show a model being used right??").
    const disconnected = modelStatus?.ollama_running === false;
    const inherited = disconnected
      ? `Inherited: ${shortModelName(row.inherits)} (not connected)`
      : isInstalled
        ? `Inherited: ${shortModelName(row.inherits)}`
        : `Inherited: ${shortModelName(row.inherits)} (not installed)`;
    fillModelSelect(
      select,
      names,
      { value: "", label: inherited },
      row.overridden ? row.model : ""
    );
    //: The inherited name moves when the chat model is changed in Settings,
    //: and `fillModelSelect` only rebuilds when the *values* change, which
    //: the first option's never does. Its words are kept current here.
    const first = select.options[0];
    if (first && first.value === "" && first.textContent !== inherited) {
      first.textContent = inherited;
    }
    //: Always the stored choice, not whatever the control last showed:
    //: `fillModelSelect` prefers the live selection so a poll cannot undo a
    //: pick in flight, which is right for Settings and would leave this one
    //: stale after the other side changed it.
    const wanted = row.overridden ? row.model : "";
    if (select.value !== wanted) select.value = wanted;
    select.title = row.overridden
      ? `${row.label} runs on ${row.model}, its own choice. The same setting as Settings, Models.`
      : `${row.label} runs on ${row.inherits}, inherited. The same setting as Settings, Models.`;
  }
}

function wireFeatureModelSelects() {
  for (const [id, key] of FEATURE_MODEL_SELECTS) {
    const select = $(id);
    if (!select || select.dataset.wired) continue;
    select.dataset.wired = "1";
    select.addEventListener("change", () => {
      const row = featureModelRow(key);
      const wanted = row && row.overridden ? row.model : "";
      if (select.value !== wanted) applyFeatureModel(key, select.value);
    });
  }
}

// Separate from the vision picker above because the jobs are separate, see
// ModelManager.ocr_model. "Automatic" here means something more specific than
// the vision picker's "Auto-detect": it prefers an installed document reader
// over a general vision model, because both report the same `vision`
// capability and only one of them is built to transcribe a page.
function renderOcrModelPicker(status) {
  const names = status.installed_models.map((m) => m.name);
  fillModelSelect(
    $("ocr-model-select"),
    names,
    { value: "", label: "Automatic" },
    status.ocr_model || ""
  );
  const note = $("ocr-model-note");
  if (status.ocr_model) {
    note.textContent = `Active: ${status.ocr_model}`;
  } else if (status.ocr_model_resolved) {
    note.textContent = `Automatic, currently ${status.ocr_model_resolved}`;
  } else {
    note.textContent =
      "Automatic: nothing installed can read text off a page yet.";
  }
}

function renderAutonomousModelPicker(status) {
  const names = status.installed_models.map((m) => m.name);
  //: The default names the model it falls back to, in the per-feature
  //: pickers' own words (INBOX 430, line 550; 444 decision 10, op4-1005): this
  //: is the pass's own override, not a second copy of Models' utility model,
  //: and naming the one in use shows the difference.
  const fallback = status.utility_model || status.chat_model;
  fillModelSelect(
    $("pref-autonomous-model"),
    names,
    { value: "", label: fallback ? `Same as utility model (currently ${fallback})` : "Same as utility model" },
    (window.prefsCache && window.prefsCache.autonomous_tasks_model) || ""
  );
}

function renderEmbeddingPicker(status) {
  // Name the built-in model rather than describing it. "Works out of the box,
  // no download" was wrong on both counts: it fetches ~130 MB from Hugging
  // Face the first time, which is a long quiet wait to have described as
  // needing nothing.
  //: Its own name, and whether it is the one in use: the label used to
  //: carry the *active* model's name, so with Ollama in use the built-in
  //: option named the Ollama model and nothing said which one was working
  //: (owner, 0.3.31: "idk if it is using the built in one or not").
  const builtinName = status.builtin_embedding_model || "the built-in model";
  $("builtin-model-name").textContent =
    status.embedding_backend === "ollama"
      ? `${builtinName}, downloaded once on first use`
      : `${builtinName}, in use`;
  //: The built-in model needs the sentence-transformers package, which the
  //: app installs by itself, once, the first time it is needed: a download
  //: of several hundred MB that needs the internet. Said here, with the
  //: alternative that needs neither Python packages nor that download.
  const note = $("builtin-embed-note");
  if (note) {
    let text = "";
    if (status.builtin_embedding_installing) {
      text =
        "Installing sentence-transformers for the built-in model. This happens once and " +
        "can take several minutes. Prefer not to wait? Pick nomic-embed-text from Ollama below.";
    } else if (status.builtin_embedding_installed === false) {
      text =
        "The built-in model needs sentence-transformers, which the app installs by itself " +
        "the first time it is needed if the switch below is on (a one-time download that needs the internet). " +
        "Or pick nomic-embed-text from Ollama below instead.";
    }
    note.textContent = text;
    note.classList.toggle("hidden", !text);
  }
  // The backend radios only reflect the saved value while the user has no
  // pending choice of their own.
  //
  // A focus check alone was not enough, and it is why switching search
  // engines was reported as impossible. Picking a radio does not save
  // anything, "Apply & re-index" does, so between the click and the apply
  // there is a pending choice the server doesn't know about yet. The moment
  // focus moved (clicking Apply, or just tabbing away) the status poll ran,
  // found `touching` false, and reset the radio to the *saved* backend. The
  // selection visibly snapped back, so the setting looked stuck.
  //
  // Same `userChosen` latch the model selects already use, cleared once the
  // choice is actually applied.
  const group = document.querySelectorAll('input[name="emb-backend"]');
  const touching =
    document.activeElement?.name === "emb-backend" ||
    [...group].some((radio) => radio.dataset.userChosen === "1");
  if (!touching) {
    for (const radio of document.querySelectorAll('input[name="emb-backend"]')) {
      radio.checked = radio.value === status.embedding_backend;
    }
  }
  const names = (status.installed_models || []).map((m) => m.name);
  fillModelSelect(
    $("embedding-model-select"),
    names,
    null,
    status.embedding_model
  );
  // With Ollama down there are no embedding models to pick from, so that half
  // of the choice is disabled and says why, rather than the whole section
  // disappearing, which is what used to happen.
  const offline = !status.ollama_running;
  //: **And it says whether it is the one in use.** Asked after reading the
  //: code: "does the ai embedding model actually get used??" It does, in
  //: seven places, but only when the backend above is set to Ollama, and the
  //: built-in backend is the default. So somebody who picked a model here
  //: expecting it to be doing the work had a fully enabled, fully ignored
  //: control, which is the same class of thing as a disabled control that
  //: does not say why: a setting whose state is invisible.
  //:
  //: Disabled rather than hidden, because hiding it would make the choice
  //: unfindable from the radio that mentions it, and the tooltip carries the
  //: reason so the state is legible without a second paragraph on screen.
  syncEmbeddingPickerState(offline);
  document.querySelector('input[name="emb-backend"][value="ollama"]').disabled = offline;
  $("embedding-ollama-note").classList.toggle("hidden", offline);
  $("embedding-offline-note").classList.toggle("hidden", !offline);
}

//: **A control says whether it is the one in use.** Asked after reading the
//: code: *"does the ai embedding model actually get used??"* It does, in
//: seven places, but only when the backend radio above is set to Ollama, and
//: the built-in backend is the default. So somebody who picked a model here
//: expecting it to be doing the work had a fully enabled, fully ignored
//: control, which is the same class of thing as a disabled control that does
//: not say why: a setting whose state is invisible.
//:
//: Disabled rather than hidden, because hiding it would make the choice
//: unfindable from the radio that names it, and the reason rides on the
//: tooltip so the state is legible without another paragraph on screen.
//:
//: `offline` is passed by the status poll, which knows; the radio's own
//: handler omits it and it is read back off the control the poll last set,
//: so a change of radio cannot claim Ollama is reachable when it is not.
function syncEmbeddingPickerState(offline) {
  const ollamaRadio = document.querySelector('input[name="emb-backend"][value="ollama"]');
  const down = offline === undefined ? Boolean(ollamaRadio?.disabled) : offline;
  const usingOllama =
    document.querySelector('input[name="emb-backend"]:checked')?.value === "ollama";
  const picker = $("embedding-model-select");
  if (!picker) return;
  picker.disabled = down || !usingOllama;
  //: An empty select says nothing: with Ollama off it drew as a blank 46px
  //: box beside a pale Apply button. It names why it is empty instead.
  if (!picker.options.length || picker.options[0].dataset.placeholder) {
    const note = down ? "Needs Ollama running" : "No embedding models installed";
    let option = picker.options[0];
    if (!option) {
      option = document.createElement("option");
      option.value = "";
      option.dataset.placeholder = "1";
      picker.appendChild(option);
    }
    option.textContent = note;
  }
  picker.title = down
    ? "Ollama is not running, so there are no embedding models to choose from"
    : usingOllama
      ? "The model used for semantic search"
      : "Only used when the backend above is set to Ollama. The built-in one is in use";
  const apply = $("embedding-apply");
  if (!apply) return;
  //: **Enabled for the built-in choice too.** It was disabled whenever
  //: Built-in was picked, so switching back from an Ollama model could never
  //: be applied: the backend stayed on Ollama and that model stayed "in use"
  //: and could not be removed (owner, 0.3.31).
  apply.disabled = usingOllama && down;
  apply.title = usingOllama
    ? "Re-read every note with this model"
    : "Switch to the built-in model and re-read every note with it";
}

// The button lives in index.html (see `#reindex-box`) rather than being built
// here: `test_frontend_ids.py` refuses an id this file looks up that the
// markup never declares, and it is right to, a control that exists only in
// JS is one nobody can find by reading the page.
function wireReindexButton() {
  const button = $("reindex-start");
  if (!button || button.dataset.wired === "1") return;
  button.dataset.wired = "1";
  setLabel(button, "ph:arrows-clockwise Rebuild search index");
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      await apiJson("/models/reindex", { method: "POST" });
      toast("Rebuilding the search index…");
      refreshModelStatus?.();
    } catch (error) {
      // A 409 is not a failure to report as one: it means the thing the user
      // asked for is already happening.
      toast(error.message, !/already running/i.test(error.message || ""));
    } finally {
      button.disabled = false;
    }
  });
}

function renderReindex(status) {
  const box = $("reindex-box");
  const job = status.reindex;
  const running = job && job.status === "running";
  wireReindexButton();
  // The box is no longer only a progress readout, so it stays visible, the
  // heading and the progress bar are what come and go with the job.
  box.classList.remove("hidden");
  const heading = box.querySelector("h3");
  if (heading) heading.textContent = running ? "Re-indexing your notes…" : "Search index";
  $("reindex-progress").classList.toggle("hidden", !running);
  $("reindex-label").classList.toggle("hidden", !running);
  $("reindex-start").classList.toggle("hidden", running);
  if (running) {
    $("reindex-progress").value = job.done;
    $("reindex-progress").max = Math.max(job.total, 1);
    $("reindex-label").textContent = `${job.done} of ${job.total} notes re-indexed`;
  }
  //: **Say when it is actually worth doing.** Asked for: "suggest rebuilding
  //: the search index upon large changes". The backend counts notes that
  //: arrived or vanished in bulk (`mark_index_stale`); this is the only place
  //: that counter is ever shown, and it says nothing at all until the count
  //: crosses the threshold the same module sets, a permanent nudge is
  //: furniture, and a nudge after every third note is noise.
  const stale = Number(status.index_stale_notes || 0);
  const threshold = Number(status.index_stale_suggest_at || 20);
  const staleLine = $("reindex-stale");
  if (staleLine) {
    const worth = !running && stale >= threshold;
    staleLine.classList.toggle("hidden", !worth);
    if (worth) {
      //: Through `setLabel`, because `.notice` carries its icon as a child
      //: element (the recipe, 08-consistency.css) and `textContent` would wipe
      //: it and print the token.
      setLabel(
        staleLine,
        `ph:warning ${stale} notes have been added or removed in bulk since the ` +
          "last rebuild, semantic search may be missing them."
      );
    }
  }
}

//: The installed models are model cards too, drawn by `renderInstalledModels`
//: in settings-models.js (lazy, INBOX 444 decision 10, op4-1005).

//: The Models screen's suggested downloads are model cards now: `renderSuggested`
//: lives in settings-models.js (INBOX 444), loaded with the first open of
//: Settings, and status.js calls it behind a `typeof` guard.

// --- Wave N: AI improve-writing (before/after, user approves) -----------------------

let improveMode = "proofread";
let improveTarget = null; // the textarea to write the accepted result into
let improveCustomInstruction = "";






// Heuristic: does this Ollama model look like it can produce embeddings?
// Chat/generation models can't, Ollama answers /api/embed with 501, and
// picking one by mistake is the #1 way people break the search engine.
function looksLikeEmbeddingModel(name) {
  return /embed|minilm|bge|gte|e5|arctic/i.test(name || "");
}

async function applyEmbeddingBackend() {
  const backend = document.querySelector('input[name="emb-backend"]:checked')?.value;
  const model = $("embedding-model-select").value || null;
  if (!backend) return;
  // Guard the #1 misconfiguration: a chat model chosen as the search engine.
  if (backend === "ollama") {
    if (!model) {
      toast("Pick an embedding model first, e.g. nomic-embed-text.", "info");
      return;
    }
    if (!looksLikeEmbeddingModel(model)) {
      const proceed = (await confirmDialog(
        `"${model}" doesn't look like an embedding model. Chat models can't create ` +
          "embeddings, so semantic search will fail (Ollama returns 501). Download and " +
          "pick a dedicated embedding model like nomic-embed-text instead.\n\nApply anyway?"
      ));
      if (!proceed) return;
    }
  }
  const ok = (await confirmDialog(
    `Switching the search engine re-indexes all ${allEntries.length} of your ` +
      "notes so search keeps making sense. Notes and keyword search stay " +
      "available while it runs. Continue?"
  ));
  if (!ok) {
    // Backing out puts the saved backend back on screen, rather than leaving
    // a radio selected for a switch that never happened.
    clearEmbeddingBackendLatch();
    refreshModelStatus();
    return;
  }
  try {
    await api("/models/embedding-backend", {
      method: "POST",
      body: JSON.stringify({ backend, model: backend === "ollama" ? model : null }),
    });
    clearEmbeddingBackendLatch(); // applied: polling may reflect it again
    refreshModelStatus();
  } catch (error) {
    toast(error.message, true);
  }
}

// Let the status poll own the radios again. Called once a choice is applied,
// and when the user backs out of applying it, otherwise a cancelled switch
// would leave the radio showing a backend that was never saved, which is the
// same lie in the opposite direction.
function clearEmbeddingBackendLatch() {
  delete $("embedding-model-select").dataset.userChosen;
  for (const radio of document.querySelectorAll('input[name="emb-backend"]')) {
    delete radio.dataset.userChosen;
  }
}

// --- keeping the look across restarts (§35E) --------------------------------
//
// Reported as two bugs: *"the theme resets to default on every start"* and
// *"onboarding shows every time"*. They are one bug. Both were stored in
// `localStorage` and nowhere else, and the desktop shell does not reliably
// persist it: pywebview is a different browser with its own profile, and if
// that profile is not stable across launches then everything kept there is
// something the app forgets. Two symptoms, one storage, exactly as §35E
// predicted.
//
// The fix is a mirror, not a move. localStorage stays the thing every
// `appearancePref` read goes through: it is synchronous, it works with the
// server unreachable, and moving the reads would mean rewriting the whole
// appearance system to be async. The server keeps a copy, seeded back into
// localStorage on load when the local one is empty, so a shell that loses it
// gets it back, and a browser that keeps it never notices.

//: Sizes and places on the screen belong to the device they were chosen on
//: (INBOX 897: "if I change the size of say the companion and the zoom on my
//: computer, it shouldnt affect my phone"). Never written to `ui_state`, and a
//: notebook that still holds them from an older version is not applied:
//: `mirroredUiKeys()` leaves them out, so the save, the seed and the settings
//: file all skip them. Colours, themes, fonts and motion still follow the
//: person. A saved look leaves them out too: a look is colours (`LOOK_KEYS`).
const DEVICE_ONLY_KEYS = [
  "zoom",
  "fontsize",
  "density",
  "avatar-buddy-size",
  "nm-buddy-spots",
  "chat-composer-height",
  "wb-panel-pos-board",
  "wb-panel-pos-library",
  "wb-panel-pos-tools",
  "wb-panel-pos-zoom",
];

//: The keys worth surviving a restart. Explicit rather than "everything in
//: localStorage": this is written to the notebook's own preferences file, and
//: scroll positions and one-visit UI state have no business in there.
// The appearance half is `LOOK_KEYS`, the same list a saved custom theme
// snapshots: rather than a second hand-written copy of it. The first draft
// *was* a hand-written copy, and it guessed two key names wrong ("bgart",
// "bgart-motion" for what are really `bgArt`, `bg-style`, `bg-motion` and
// `bg-intensity`), so the background art would have been the one setting that
// still did not survive a restart. Deriving it cannot be wrong.
// Everything not covered by the look: the tour flag, and the few view
// settings that are properties of how you use the app rather than of one
// visit.
const MIRRORED_UI_EXTRAS = [
  "themePreset",
  "motion",
  "ui-motion",
  "custom-css",
  "onboardingDone",
  //: Appearance that follows the person to a second browser (WORLD_CLASS 25f).
  //: Not `perf`: performance mode is a property of the machine.
  "contrast",
  "progress-motion",
  "show-thinking-words",
  "border-style",
  "shadow-intensity",
  "avatar-motion",
  "avatar-follow",
  "avatar-buddy",
  "atlas-style",
  "assistant-avatar",
  "atlas-look",
  "face-look",
  "dash-mark",
  // The guided tour's own flag, for the same reason `onboardingDone` is here:
  // both were reported as "onboarding shows every time" when the desktop
  // shell lost its profile, and a tour that reintroduces the app to somebody
  // who has already been through it is the same bug wearing the new feature.
  "tourDone",
  "activeTab",
  "graph-layout",
  "graph-colour",
  "graph-size",
  "graph-options-open",
  "graph-trace-open",
  // The options panel's four folds, keyed `graph-fold-<the section's id>` by
  // `initGraphOptionFolds` far below. Written out rather than spread from a
  // constant beside that function: this array is read at module level and the
  // constant would be declared hundreds of lines later, which is the
  // temporal-dead-zone blank app the comment above already describes.
  "graph-fold-graph-physics",
  "graph-fold-graph-groups-section",
  "graph-fold-graph-minimap-section",
  "graph-fold-graph-display",
  "wb-bg-color",
];

// A function rather than a `const` array, because `LOOK_KEYS` is declared
// several hundred lines below this one and a top-level spread of it would be
// read before its initialiser had run, a temporal-dead-zone error at load,
// which in a file with no bundler means a blank app.
function mirroredUiKeys() {
  return [...LOOK_KEYS, ...MIRRORED_UI_EXTRAS].filter((key) => !DEVICE_ONLY_KEYS.includes(key));
}

let uiStateSaveTimer = null;

//: Whether the boot restore has had its turn. Until it has, this browser does
//: not yet know what the server is holding, and a save would be a guess: the
//: tab restore writes `activeTab` at module level, which schedules a save for
//: 800 ms later, and on this sandbox that lands *before* the unlock and the
//: `/preferences` read that follows it have finished. So a cold start wrote a
//: `ui_state` built from a browser that had not been given its settings back
//: yet, which is both a wasted PUT (A2) and, on a browser that had lost
//: `localStorage`, the one write that could make the loss permanent.
//:
//: Dropped rather than deferred, the same as the `authToken()` guard below and
//: for the same reason: `watchMirroredUiKeys` sees every later write, so the
//: next real change saves, and nothing here is the only copy of anything.
let uiStateSeeded = false;

//: The mirrored state the server is known to be holding, as the same JSON this
//: file would send. Null until something establishes it: either the boot seed
//: below (the server told us) or a save that came back (we told the server).
//:
//: **Why it exists** (WORLD_CLASS_PLAN A2). `seedUiStateFromServer` writes the
//: server's copy into `localStorage`, and `watchMirroredUiKeys` has patched
//: `setItem` to schedule a save on exactly those keys, so every cold start
//: ended with a PUT of the document it had just been given. One of the four
//: `/preferences` requests a boot was making was this round trip, and the same
//: shape fires again whenever a control is set to the value it already had.
let uiStateOnServer = null;

//: The payload, built from `localStorage`, in `mirroredUiKeys()` order so two
//: of these are comparable as strings.
function uiStatePayload() {
  const state = {};
  for (const key of mirroredUiKeys()) {
    const value = prefs.get(key, null);
    if (value != null) state[key] = String(value).slice(0, 400);
  }
  return state;
}

//: The same shape, built from a server document, so the comparison is between
//: like and like: the server's `ui_state` can carry keys this build no longer
//: mirrors (an old key, a key from a newer version), and those must not read as
//: a difference worth a write.
function uiStateFingerprint(state) {
  const out = {};
  for (const key of mirroredUiKeys()) {
    if (state[key] != null) out[key] = String(state[key]).slice(0, 400);
  }
  return JSON.stringify(out);
}

// Write the mirrored keys to the server, coalesced. Debounced because the
// appearance panel fires a change per slider tick, and a preferences write per
// tick would be a write per pixel of a corner-radius drag.
function saveUiState() {
  clearTimeout(uiStateSaveTimer);
  uiStateSaveTimer = setTimeout(() => {
    // Not before the unlock. The tab restore writes `activeTab` at module
    // level, which schedules a save that would land while the lock screen is
    // still up: a guaranteed 401 on every cold load, visible in the browser's
    // network log and in the server's, where it reads as an auth failure worth
    // investigating. §35E-bis found exactly this in the reminder poll; the
    // guard is the same one, for the same reason.
    if (!authToken()) return;
    if (!uiStateSeeded) return;
    const state = uiStatePayload();
    const sending = JSON.stringify(state);
    //: Nothing has changed since the server and this browser last agreed, so
    //: there is nothing to back up. Local still wins when they differ: this
    //: only skips the write, it never skips a difference.
    if (sending === uiStateOnServer) return;
    // Silent and best-effort. This is a backup of something that already
    // worked locally; a toast about it would be noise about a copy.
    apiJson("/preferences", {
      method: "PUT",
      body: JSON.stringify({ ui_state: state }),
      silent: true,
    })
      .then(() => {
        uiStateOnServer = sending;
        uiStateRememberSynced(state);
      })
      .catch(() => {});
  }, 800);
}

// Mirror every write to a watched key, from one place.
//
// There are twenty-odd sites that write these, a theme toggle, eight
// appearance controls, the graph's pickers, onboarding. Adding a `saveUiState()`
// call to each would work today and rot the moment somebody adds the
// twenty-third and forgets: the setting would keep working in a browser and
// quietly stop surviving a desktop restart, which is a bug nobody would
// connect to the commit that caused it.
//
// So the *store* is watched instead of its callers. Adding a key to
// MIRRORED_UI_KEYS is then the whole of making a new setting persistent, which
// is the property worth having. Only the listed keys trigger a save; every
// other `localStorage` write in the app is untouched and unwatched.
function watchMirroredUiKeys() {
  const mirrored = new Set(mirroredUiKeys());
  const store = window.localStorage;
  const setItem = store.setItem.bind(store);
  const removeItem = store.removeItem.bind(store);
  // Own properties shadowing Storage.prototype, the storage itself is
  // untouched, so anything else reading it (including these two) is unaffected.
  store.setItem = (key, value) => {
    setItem(key, value);
    if (mirrored.has(String(key))) saveUiState();
  };
  store.removeItem = (key) => {
    removeItem(key);
    // A removal is a change too: clearing an explicit theme to fall back to
    // the system one has to survive a restart just as setting one does.
    if (mirrored.has(String(key))) saveUiState();
  };
}

// Seed localStorage from the server's copy. Called once, before the look is
// applied, so the app paints in the remembered theme rather than flashing the
// default and correcting itself.
//
// **The notebook's copy wins unless this browser has a change it has not yet
// sent.** A key is taken from the server when this browser has none, or when
// its value is still the one the two last agreed on (`ui-synced`): then the
// difference is another browser's newer change, which is how a theme set on
// one computer reaches the next. A value that differs from what was agreed is
// this browser's own unsent change (a reload inside the 800 ms save delay, a
// server that was down) and keeps winning, so two windows never overwrite
// each other's last word with an old copy. A browser with no mark at all has
// agreed on nothing yet, so the notebook wins every key there.
function seedUiStateFromServer(state) {
  if (!state || typeof state !== "object") return false;
  const synced = prefs.json("ui-synced", {});
  //: A browser that has never agreed with the notebook (the first load after
  //: the upgrade that added the mark, or a cleared profile) has no way to tell
  //: its own unsent change from an old copy. Its differing values are almost
  //: always the old copy: an unsent change lives for 800 ms. So the notebook
  //: wins there, rather than a stale second browser pushing its look over a
  //: newer one once.
  const marked = prefs.has("ui-synced");
  let restored = 0;
  for (const key of mirroredUiKeys()) {
    if (state[key] == null) continue;
    const remote = String(state[key]);
    const local = prefs.has(key) ? prefs.get(key, "") : null;
    if (local === remote) continue;
    if (local == null || !marked || local === synced[key]) {
      prefs.set(key, remote);
      restored += 1;
    }
  }
  //: What the server is holding, recorded so the saves those `setItem` calls
  //: just scheduled can tell "this browser had lost its settings and has now
  //: been given them back" from "the person changed something" (A2). Set after
  //: the loop and before the 800 ms debounce fires, so the first save of the
  //: session compares against it. A browser that kept a key the server does not
  //: have still differs here, and still writes.
  uiStateOnServer = uiStateFingerprint(state);
  uiStateRememberSynced(state);
  //: A notebook written by an older version still holds this device's sizes.
  //: They are ignored above; one save replaces the map without them, so the
  //: copy does not carry a stale zoom for a phone to be tempted by.
  if (DEVICE_ONLY_KEYS.some((key) => state[key] != null)) {
    uiStateOnServer = null;
    saveUiState();
  }
  return restored > 0;
}

//: The values this browser and the notebook last agreed on, kept beside the
//: settings (not in the mirrored list, so writing it saves nothing).
function uiStateRememberSynced(state) {
  const agreed = {};
  for (const key of mirroredUiKeys()) if (state[key] != null) agreed[key] = String(state[key]);
  prefs.setJSON("ui-synced", agreed);
}

//: Repaint after the look in localStorage changed underneath the page (the
//: notebook's copy was taken at boot, or another window changed it). The same
//: three calls the theme picker makes, in the same order: the root attributes,
//: then the light/dark choice and the palette, neither of which re-records
//: itself as a manual override.
function applyRestoredLook() {
  applyAppearance();
  applyThemeChoice(appearancePref("theme"), false);
  applyPalette(appearancePref("palette"), false);
  renderBrandLogo();
  if (bgArtOn()) startBgArt();
}

//: **Live sync between two open windows** (OPEN ledger 286). A change in one
//: window used to show in the other only after a reload. Two cases:
//: - the same browser profile: `storage` fires in the other windows, so they
//:   repaint from their own localStorage at once;
//: - another browser or computer: the window asks the notebook for its copy
//:   when it regains focus or becomes visible, at most every 5 seconds, and
//:   repaints only when `seedUiStateFromServer` took a key. An unsent change
//:   of its own still wins, as at boot.
const lookPull = {
  at: 0,
  busy: false,
  echoTimer: 0,
};
async function pullLookFromNotebook() {
  if (!uiStateSeeded || lookPull.busy || document.hidden || !authToken()) return;
  if (Date.now() - lookPull.at < 5000) return;
  lookPull.busy = true;
  lookPull.at = Date.now();
  try {
    const fresh = await apiJson("/preferences", { silent: true });
    if (fresh && seedUiStateFromServer(fresh.ui_state)) applyRestoredLook();
  } catch {
    // A missed pull is retried the next time the window is looked at.
  } finally {
    lookPull.busy = false;
  }
}
function lookFromOtherWindow(event) {
  if (event.storageArea !== localStorage || !event.key || !uiStateSeeded) return;
  if (!mirroredUiKeys().includes(event.key)) return;
  clearTimeout(lookPull.echoTimer);
  lookPull.echoTimer = setTimeout(applyRestoredLook, 120);
}
window.addEventListener("focus", pullLookFromNotebook);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) pullLookFromNotebook();
});
window.addEventListener("storage", lookFromOtherWindow);

// Which manual overrides are currently sitting on top of the theme. Shown in
// the UI so "why isn't the theme's colour showing?" has a visible answer.
const OVERRIDABLE_KEYS = [
  "theme", "palette", "accent", "accent-custom", "page-bg", "font", "fontsize",
  "density", "radius", "glass", "glass-blur", "glass-opacity", "glass-sheen", "page-wash",
  "glass-sheen-strength", "bg-style", "bg-motion", "bg-intensity", "zoom",
];

// LOOK_KEYS stays here, not in settings.js with the rest of "your own saved
// themes" (§88.3 item 4): mirroredUiKeys() above spreads it into its own
// list from a bare top-level call in this file's own wiring
// (`watchMirroredUiKeys();`), which runs before settings.js has loaded, so
// it has to already exist here. OVERRIDABLE_KEYS above is kept for the same
// reason (LOOK_KEYS is built from it). settings.js's saveCurrentLook() and
// friends read both across the file boundary, which is safe: they only ever
// run from a user's own click, long after every script has loaded.
const LOOK_KEYS = [...OVERRIDABLE_KEYS, "bgArt"].filter((key) => !DEVICE_ONLY_KEYS.includes(key));

function applyPalette(id, remember = true) {
  const root = document.documentElement;
  // "default" means "no palette overrides", leave the attribute off rather
  // than shipping a block that restates the base :root values.
  if (id && id !== "default") root.dataset.palette = id;
  else delete root.dataset.palette;
  if (remember) prefs.set("palette", id || "default");
  // The generative background paints from the accent, so it has to be rebuilt, 
  // and so does the dashboard constellation, for the same reason.
  if (bgArtOn()) startBgArt();
  // Guarded since the dashboard.js split (roadmap §88.3 item 3): originally
  // because applyPalette() was reachable from a bare top-level call in THIS
  // file's own wiring (`applyAppearance()` -> `applyPalette()`, painting the
  // saved appearance before first render) while dashboard.js, which owns
  // `refreshArtForTheme`, hadn't loaded yet. An unguarded call threw
  // `ReferenceError: refreshArtForTheme is not defined` from inside that
  // exact chain and aborted the rest of app.js's synchronous top-level code
  // (same shape as the `initDocSidebarTabs()` hazard documents.js's split
  // found). The settings.js split (item 4) moved that bare call itself, 
  // `applyAppearance()` now runs from settings.js's own tail, after
  // dashboard.js has already loaded, so this guard now always passes at
  // that call site too. Left in place rather than removed: applyPalette()
  // stays a plain global function, callable from anywhere, and nothing
  // guarantees a *future* caller runs this late, the guard is what makes
  // that safe by construction instead of by "nothing calls it early right
  // now." Still a genuine no-op either way at today's one early call site:
  // the dashboard's art widget hasn't mounted a canvas yet at startup
  // (`artHolder` is still null), so `refreshArtForTheme()` returns
  // immediately regardless of whether the guard lets it run. Every other
  // call site (the theme toggle, the accent/theme pickers, the OS
  // dark-mode listener) fires only from user interaction, well after every
  // script has loaded.
  if (typeof refreshArtForTheme === "function") refreshArtForTheme();
}
