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
function fillModelSelect(select, names, extraFirst, savedValue) {
  //: `extraFirst` started as one leading option ("Inherited: X"); the model-
  //: per-feature select needs three (Inherited, Same as chat model, Same as
  //: utility model, INBOX 430), so it takes an array too now. Every existing
  //: caller still passes a single object or null, unchanged.
  const extras = Array.isArray(extraFirst) ? extraFirst.filter(Boolean) : extraFirst ? [extraFirst] : [];
  const wanted = [...extras.map((e) => e.value), ...names];
  const signature = [...wanted].sort().join("|");
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
      : `${aiNameNow()} answers with ${status.chat_model}${status.chat_model_chosen_why ? ` (chosen at start: ${status.chat_model_chosen_why})` : ""}.`;
  const note = $("chat-model-note").textContent.slice(0, -1);
  //: B65: "Use this model" needs a model to pick; "Stop the model" needs
  //: something to stop. Both were enabled with no model at all.
  $("chat-model-apply").disabled = !names.length;
  //: With one model and it already the one in use, the button has nothing to do.
  $("chat-model-apply").classList.toggle("hidden", names.length === 1 && names[0] === status.chat_model);
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
      if (stop.disabled && !noModel) stop.title = "The model is not loaded, and no answer is running";
      if (loaded === null || noModel) return;
      $("chat-model-note").textContent = `${note}${loaded ? ", which is ready now." : ", which loads when you ask."}`;
    })
    .catch(() => {
      stop.disabled = noModel;
    });
}

// Nielsen #6, recognition over recall: which model answers was previously
// knowable only by opening Settings, Models, and only then if the backend
// is Ollama (the picker above is gated on ollama_running). status.chat_model
// itself isn't backend-specific, so this reads it straight off the poll
// loop instead of piggybacking on that gated render.
function renderChatActiveModelBadge() {
  const badge = document.getElementById("chat-active-model");
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

onSurface("chat", () => $("chat-active-model")?.addEventListener("click", () => {
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
}));

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
  //: Drawn again whatever the answer: a refused change leaves its select on
  //: the choice, and the rows are only rebuilt when something moved.
  $("feature-models-list").dataset.sig = "";
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
    toast(error.message || voiceLine("failed", { what: "set that model" }), true);
    refreshModelStatus();
  }
}

function renderFeatureModels(status) {
  featureModelRows = status.feature_models || [];
  featureModelNames = (status.installed_models || []).map((m) => m.name);
  featureModelFollow = status.feature_model_follow || featureModelFollow;
  syncFeatureModelSelects();
  //: The rows themselves are Settings' own, drawn by settings-controls.js:
  //: `renderSettings` runs only while the window is open, and the window
  //: awaits that file before it shows.
  renderFeatureModelRows(status);
}


//: The menu row every surface uses to reach the picker above. One label, one
//: place, so the three surfaces cannot drift apart in wording.
function featureModelMenuItem(key) {
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
  syncFeatureModelSelects.pills?.();
  for (const [id, key] of FEATURE_MODEL_SELECTS) {
    const select = document.getElementById(id);
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
    //: "Default (off)": the banner beside it already says no model is
    //: connected, and saying it twice was noise (audit 1030 Y18).
    const inherited = modelStatus?.ollama_running === false
      ? "Default (off)"
      : `Inherited: ${shortModelName(row.inherits)}${isInstalled ? "" : " (not installed)"}`;
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

//: The dock pills (the owner, 2026-11-12: "Yes, a dock pill") are painted and wired by feature-model-sheet.js,
//: fetched when either surface is built (the pills live in those lazy surfaces).
for (const surface of ["notes", "documents"]) onSurface(surface, () => ensureModule("featureModelSheet"));

function wireFeatureModelSelects() {
  for (const [id, key] of FEATURE_MODEL_SELECTS) {
    const select = document.getElementById(id);
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

//: `renderEmbeddingPicker` lives in settings-models.js (lazy `settingsUi`),
//: like the model cards: only an open Settings draws it.

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
    $("reindex-label").textContent = `${job.done} of ${nounCount(job.total, "note")} re-indexed`;
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
  "panel-pos",
  "panel-push",
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
  "reply-motion",
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
  // The options panel's folds, keyed `graph-fold-<the section's id>` by
  // `initGraphOptionFolds` far below. Written out rather than spread from a
  // constant beside that function: this array is read at module level and the
  // constant would be declared hundreds of lines later, which is the
  // temporal-dead-zone blank app the comment above already describes.
  "graph-fold-graph-physics",
  "graph-fold-graph-groups-section",
  "graph-fold-graph-minimap-section",
  "graph-fold-graph-display",
  "graph-fold-graph-filter-section",
  "graph-fold-graph-toggle-group",
  "graph-fold-graph-temporal",
  "wb-bg-color",
  //: The model picker's pins and recent picks (model-menu.js, INBOX 1477).
  "model-pins",
  "model-recent",
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
      noHistory: true,
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
  "density", "radius", "glass", "glass-blur", "glass-opacity", "glass-sheen", "glass-controls", "page-wash",
  "glass-sheen-strength", "bg-style", "bg-motion", "bg-intensity", "zoom",
  "read-leading", "read-measure",
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
  // Not `typeof`-guarded (88bfe5341 removed it). `refreshArtForTheme` lives in
  // dashboard.js, which loads after this file, so a call made before
  // dashboard.js has run would throw ReferenceError. That no longer happens:
  // the one early path, `applyAppearance()` -> `applyPalette()`, now runs from
  // settings.js's tail, after dashboard.js, and every other caller (theme
  // toggle, accent/theme pickers, the OS dark-mode listener) fires from user
  // interaction. A new caller that runs at parse time here must not reach
  // this line. At startup the art widget has not mounted a canvas
  // (`artHolder` is null), so the call returns at once anyway.
  refreshArtForTheme();
}
