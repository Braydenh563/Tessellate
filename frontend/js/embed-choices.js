// embed-choices.js: Settings, Search and index's embedding models (INBOX 700).
// Lazy (`embedChoices` in app.js's LAZY_MODULES), fetched the first time the
// Search and index section is drawn, so the boot scripts carry none of it.
//
// The owner: "can you also add more embedding model options as alternatives
// in the models??". The list is the server's (`core/embedmodels.catalogue`):
// each row says what the model costs and buys, Use switches in one press where
// the licence allows it, and anything else links to its terms. A switch runs
// in the background (`core/embedswitch.py`); search keeps using the current
// model until the new set is complete, so the row shows its progress here and
// Background tasks shows the same job with Quit.

const embedChoicesUi = { poll: null };

//: What an Install, Uninstall, Use or Pull answer says, as a toast. The server
//: answering "no" (already downloading, Ollama is not running, switch first) is
//: an expected situation, a plain toast; only a request that threw (`failed`)
//: is a fault, the red one with Report this (tests/test_error_toasts.py).
function embedToast(result) {
  if (result.failed) toast(result.error.message, true);
  else toast(result.message, "info");
}

async function renderEmbedChoices() {
  const list = $("embed-choices");
  if (!list) return;
  if (!list.children.length) showSkeletons(list, 3, "li");
  const body = await apiJson("/embedding-models/choices", { silent: true }).catch(() => null);
  clearSkeletons(list);
  if (!body) return;
  const now = Date.now() / 1000;
  list.replaceChildren(...body.choices.map((choice) => embedChoiceRow(choice, body, now)));
  const found = body.found || [];
  $("embed-found").replaceChildren(...found.map((row) => embedFoundRow(row, body)));
  $("embed-found-empty").classList.toggle("hidden", found.length > 0);
  renderEmbedLegacy(body.legacy || {});
  const done = body.switch || {};
  $("embed-choices-status").textContent = done.running ? "" : done.message || "";
  //: Where they are, in as many words ("somewhere in your home directory" is
  //: the answer the old Packages list existed to replace).
  const where = $("embed-choices-cache");
  if (where) where.textContent = body.cache ? `Kept in ${body.cache}` : "";
  clearTimeout(embedChoicesUi.poll);
  if (done.running && settingsModalOpen() && currentSettingsSection === "searchindex") {
    embedChoicesUi.poll = setTimeout(renderEmbedChoices, 2000);
  }
}

function embedChoiceRow(choice, body, now) {
  const switching = body.switch || {};
  const current = body.current || {};
  const inUse = current.backend === choice.backend && current.model === choice.model;
  const moving = switching.running && switching.backend === choice.backend && switching.model === choice.model;

  const li = document.createElement("li");
  li.className = "extras-row embed-choice";
  li.dataset.choice = choice.id;
  const head = document.createElement("div");
  head.className = "entry-meta";
  const title = document.createElement("span");
  title.className = "entry-title";
  const name = document.createElement("strong");
  name.textContent = choice.label;
  title.append(name, chip(choice.backend === "ollama" ? "Through Ollama" : "Runs in the app", "item-label"));
  if (inUse) title.appendChild(chip("ph:check-circle In use", "item-label is-ok"));
  else if (choice.default) title.appendChild(chip("Default", "item-label"));
  //: **The row's real state** (the owner, 2026-10-07): Downloaded with its size
  //: on disk, Not downloaded, or Files missing with a Reinstall one press away.
  //: Only for a model the app runs itself; an Ollama row's state is Ollama's.
  const partial = choice.backend !== "ollama" && choice.files_missing;
  if (choice.backend !== "ollama" && choice.one_press) {
    if (partial) title.appendChild(chip("ph:warning Files missing", "item-label is-warn"));
    else if (choice.downloaded) title.appendChild(chip(`ph:hard-drives Downloaded, ${choice.on_disk || "on disk"}`, "item-label"));
    else title.appendChild(chip("Not downloaded", "item-label"));
  }
  head.appendChild(title);

  const actions = document.createElement("span");
  actions.className = "entry-actions";
  if (choice.one_press) {
    //: Use, Install or Reinstall, Uninstall (the owner's second addendum:
    //: "options to modify, install, uninstall, reinstall embedded models").
    //: Uninstall is refused on the model search uses, with the reason.
    const busy = switching.running ? "Wait for the switch in hand to finish." : "";
    const usedHere = inUse ? "In use for search: switch to another model first." : "";
    actions.appendChild(
      kebabMenu(
        [
          {
            label: "ph:swap Use",
            disabled: inUse || moving || Boolean(busy),
            title: inUse ? "Search uses it now." : busy,
            //: A muted item still runs (`kebabMenu`): it says why instead.
            run: () => (inUse || moving || busy ? toast(inUse ? "Search uses it now." : busy || "It is switching now.", "info") : embedChoiceUse(choice)),
          },
          {
            label: choice.downloaded || choice.files_missing ? "ph:arrow-clockwise Reinstall" : "ph:download-simple Install",
            disabled: moving,
            run: () => (moving ? toast("It is switching now.", "info") : embedChoiceInstall(choice)),
          },
          {
            label: "ph:trash Uninstall",
            danger: true,
            //: A part-filled folder can be cleared too ("Files missing").
            disabled: !(choice.downloaded || choice.files_missing) || Boolean(usedHere),
            title: usedHere || (choice.downloaded || choice.files_missing ? "" : "It is not on this computer."),
            run: () =>
              usedHere || !(choice.downloaded || choice.files_missing)
                ? toast(usedHere || "It is not on this computer.", "info")
                : embedChoiceUninstall(choice),
          },
        ],
        `More for ${choice.label}`
      )
    );
  } else if (choice.terms_url) {
    actions.appendChild(
      smallButton("ph:arrow-square-out Terms", `Read the terms for ${choice.label}`, () =>
        window.open(safeHref(choice.terms_url), "_blank", "noopener,noreferrer")
      )
    );
  }
  if (partial && !moving) {
    const fix = smallButton("ph:arrow-clockwise Reinstall", `Fetch ${choice.label} again; its files on this computer are incomplete`, () => embedChoiceInstall(choice));
    fix.classList.add("quiet");
    actions.prepend(fix);
  }
  head.appendChild(actions);
  li.appendChild(head);

  const best = document.createElement("p");
  best.className = "muted extras-enables";
  best.textContent = choice.best_for;
  const meta = document.createElement("p");
  meta.className = "muted extras-meta";
  meta.textContent = [choice.params ? `${choice.params} parameters` : "", choice.size, choice.languages, choice.context, choice.licence]
    .filter(Boolean)
    .join(" · ");
  li.append(best, meta);

  if (!choice.one_press && choice.why_not) {
    const why = document.createElement("p");
    why.className = "muted extras-caveat";
    setLabel(why, `ph:scales ${choice.why_not}`);
    li.appendChild(why);
  }

  //: The switch to this model, in its row: a bar over the notes done (none
  //: while the model is fetched or loaded) and how long it has run.
  if (moving) {
    const bar = document.createElement("progress");
    bar.className = "task-progress";
    if (switching.phase === "stage" && switching.total) {
      bar.max = switching.total;
      bar.value = switching.done;
    }
    bar.setAttribute("aria-label", `Switching to ${choice.label}`);
    const line = document.createElement("p");
    line.className = "muted task-detail";
    const stage = {
      prepare: "Getting the model ready; the first time it is downloaded.",
      stage: `${switching.done} of ${switching.total} notes read. Search uses the current model until then.`,
      swap: "Swapping the new vectors in.",
      paragraphs: "Reading long notes paragraph by paragraph.",
    }[switching.phase] || "Starting.";
    line.textContent = switching.started ? `${stage} ${taskElapsed(now - switching.started)}.` : stage;
    li.append(bar, line);
  }
  return li;
}

//: Install or Reinstall: a built-in model through the download the Packages
//: list uses (verified once it lands), an Ollama one through Ollama's pull.
//: Both are Background tasks with their progress.
async function embedChoiceInstall(choice) {
  const again = choice.downloaded || choice.files_missing;
  if (!(await confirmDialog(
    `${again ? "Download" : "Install"} ${choice.label}${again ? " again" : ""}?\n\n${choice.size}, from ` +
      (choice.backend === "ollama" ? "the Ollama library" : "Hugging Face") + ". It needs the internet.",
    { confirmLabel: again ? "Reinstall" : "Install" }
  ))) return;
  const result =
    choice.backend === "ollama"
      ? await apiJson("/models/pull", { method: "POST", body: JSON.stringify({ name: choice.model }) })
          .then(() => ({ started: true, message: `Pulling ${choice.model}. Background tasks shows its progress.` }))
          .catch((e) => ({ started: false, failed: true, error: e, message: e.message }))
      : await apiJson(`/embedding-models/${encodeURIComponent(choice.id)}/download${again ? "?reinstall=true" : ""}`, { method: "POST" })
          .catch((e) => ({ started: false, failed: true, error: e, message: e.message }));
  embedToast(result);
  renderEmbedChoices();
}

async function embedChoiceUninstall(choice) {
  if (!(await confirmDialog(`Uninstall ${choice.label}?\n\nIts files leave this computer; Install brings it back.`, { confirmLabel: "Uninstall" }))) return;
  const result =
    choice.backend === "ollama"
      ? await apiJson("/models/delete", { method: "POST", body: JSON.stringify({ name: choice.model }) })
          .then(() => ({ removed: true, message: `${choice.label} removed.` }))
          .catch((e) => ({ removed: false, failed: true, error: e, message: e.message }))
      : await apiJson(`/embedding-models/${encodeURIComponent(choice.id)}`, { method: "DELETE" })
          .catch((e) => ({ removed: false, failed: true, error: e, message: e.message }));
  embedToast(result);
  renderEmbedChoices();
}

//: A model already on this computer (core/embedfind.py): Use when the engine
//: loads it as it is, otherwise the reason in its own line.
function embedFoundRow(row, body) {
  const current = body.current || {};
  const inUse = current.backend === row.backend && current.model === row.model;
  const li = document.createElement("li");
  li.className = "extras-row embed-choice";
  const head = document.createElement("div");
  head.className = "entry-meta";
  const title = document.createElement("span");
  title.className = "entry-title";
  const name = document.createElement("strong");
  name.textContent = row.label;
  title.append(name, chip(row.where, "item-label"));
  if (inUse) title.appendChild(chip("ph:check-circle In use", "item-label is-ok"));
  head.appendChild(title);
  const actions = document.createElement("span");
  actions.className = "entry-actions";
  if (row.usable && !inUse) {
    const use = smallButton("ph:swap Use", `Switch search to ${row.label}`, () => embedChoiceUse({ ...row, size: "Already here" }));
    use.disabled = Boolean((body.switch || {}).running);
    actions.appendChild(use);
  }
  head.appendChild(actions);
  li.appendChild(head);
  if (row.why_not) {
    const why = document.createElement("p");
    why.className = "muted extras-caveat";
    setLabel(why, `ph:info ${row.why_not}`);
    li.appendChild(why);
  }
  return li;
}

//: The previous engine's files (`legacy` in /embedding-models/choices): each
//: catalogue model's PyTorch copy, and in a packaged app the packages. The
//: server lists them only once the new build of the model in use is here, so
//: Remove never takes away the way back to a working search.
function renderEmbedLegacy(legacy) {
  const items = [
    ...(legacy.files || []).map((file) => ({ ...file, label: `${file.label}, old files`, where: file.folder })),
    ...(legacy.engine ? [{ ...legacy.engine, where: "In the app's extras folder" }] : []),
  ];
  $("embed-legacy-box").classList.toggle("hidden", items.length === 0);
  $("embed-legacy").replaceChildren(...items.map(embedLegacyRow));
}

function embedLegacyRow(item) {
  const li = document.createElement("li");
  li.className = "extras-row embed-choice";
  const head = document.createElement("div");
  head.className = "entry-meta";
  const title = document.createElement("span");
  title.className = "entry-title";
  const name = document.createElement("strong");
  name.textContent = item.label;
  title.append(name, chip(`ph:hard-drives ${item.size}`, "item-label"));
  head.append(
    title,
    rowActions([{ label: "ph:trash Remove", title: `Remove ${item.label}`, danger: true, run: () => embedLegacyRemove(item) }], `Actions for ${item.label}`)
  );
  const where = document.createElement("p");
  where.className = "muted extras-meta";
  where.textContent = item.where;
  li.append(head, where);
  return li;
}

async function embedLegacyRemove(item) {
  const frees = item.id === "engine" ? `${item.size}, once Tessellate restarts,` : item.size;
  if (!(await confirmDialog(
    `Remove ${item.label}?\n\nThe previous search engine made them and Tessellate no longer uses them. ` +
      `${frees} comes back; search and your notes do not change.`,
    { confirmLabel: "Remove" }
  ))) return;
  const result = await apiJson(`/embedding-models/legacy/${encodeURIComponent(item.id)}`, { method: "DELETE" })
    .catch((e) => ({ removed: false, failed: true, error: e, message: e.message }));
  embedToast(result);
  if (item.id === "engine") refreshBackgroundTasks();
  renderEmbedChoices();
}

//: Pull a model by name: a Hugging Face repo or an Ollama name, checked
//: online only on this click, then a Background task with its progress.
async function embedPullTyped() {
  const input = $("embed-pull-name");
  const name = input.value.trim();
  const status = $("embed-pull-status");
  if (!name) {
    status.textContent = "Type a Hugging Face repo (owner/name) or an Ollama name (name:tag).";
    input.focus();
    return;
  }
  status.textContent = "Checking…";
  const result = await apiJson("/embedding-models/pull", { method: "POST", body: JSON.stringify({ name }) })
    .catch((e) => ({ started: false, failed: true, error: e, message: e.message }));
  status.textContent = result.message || "";
  if (result.started) {
    input.value = "";
    toast(result.message, "info");
  }
  renderEmbedChoices();
}

$("embed-pull-go").addEventListener("click", embedPullTyped);
$("embed-pull-name").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    embedPullTyped();
  }
});

async function embedChoiceUse(choice) {
  const ok = await confirmDialog(
    `Switch search to ${choice.label}?\n\n${choice.size}, ` +
      (choice.backend === "ollama" ? "pulled into Ollama" : "downloaded to this machine") +
      " once if it is not here yet, which needs the internet. Every note is read again in the background; search keeps using the current model until that finishes.",
    { confirmLabel: "Switch" }
  );
  if (!ok) return;
  const result = await apiJson("/embedding-models/use", {
    method: "POST",
    body: JSON.stringify({ id: choice.id }),
  }).catch((e) => ({ started: false, failed: true, error: e, message: e.message }));
  embedToast(result);
  renderEmbedChoices();
}
