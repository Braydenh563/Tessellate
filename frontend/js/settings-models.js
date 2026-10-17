// settings-models.js: the Models screen's suggested downloads, as model cards
// (INBOX 444).
//
// Loaded with the first open of Settings (`LAZY_MODULES.settingsUi`, app.js),
// so none of it is in the boot gzip budget; it replaced `renderSuggested` in
// ai-tools.js, which was 31 rows of `name ~size purpose` with 29 identical
// filled Download buttons and not a word about memory. status.js calls
// `renderSuggested(status)` on every poll while Settings is open, behind a
// `typeof` guard.
//
// A card says, in this order: the name; the one-line purpose; the facts
// (size on disk, the memory it asks for, what it is good at); whether it fits
// this computer; whether it is installed or in use; and one primary action.
// The numbers come from the server (`model_cards.py`, `/models/suggested`);
// nothing here estimates anything.
//
// **Cards are kept, not rebuilt, on every poll.** The status poll runs every
// second while a download is going, and a card rebuilt each time would drop an
// open menu and the focus inside it. Each card remembers a signature of what
// it shows; only a changed signature rebuilds its contents, and progress is
// updated in place.

//: What each catalogue group is for, in the order the page shows them. The key
//: is the group's own key in `SUGGESTED_MODELS` (model_manager.py).
const MODEL_GROUPS = {
  text: { title: "Chat and filing", about: "Answers your questions and files your notes. Start small." },
  moe: { title: "Bigger machines", about: "Large downloads that answer at a smaller model's speed. They need the big one's memory." },
  embedding: { title: "Search", about: "Turns notes into numbers for semantic search. Optional: the built-in engine needs no download." },
  vision: { title: "Images", about: "Can look at a picture you attach in chat." },
  ocr: { title: "Reading text", about: "Reads scanned pages and the text in images." },
};

//: The words for what a model is good at (`good_for` from the server).
const MODEL_GOOD_FOR = {
  chat: "chat",
  filing: "filing",
  agent: "agent mode",
  writing: "writing",
  "long documents": "long documents",
  embeddings: "search",
  vision: "images",
  ocr: "reading text",
};

//: What "Use" means for each purpose, and the route that does it.
const MODEL_USE = {
  chat: { label: "Use for chat", role: "chat", path: "/models/chat-model" },
  vision: { label: "Use for images", role: "images", path: "/models/vision-model" },
  ocr: { label: "Use for reading text", role: "reading text", path: "/models/ocr-model" },
  embeddings: { label: "Use for search", role: "search", path: "/models/embedding-backend" },
};

const modelCards = new Map(); // name -> { el, sig, host }
let modelHardwareGb; // undefined: not asked yet; null: unknown
const modelHw = { data: null, at: 0 }; // the whole /models/hardware reply and when it came (B67)
//: Free memory moves, so the verdicts are asked for again this often while the
//: page is open (two small requests).
const MODEL_HARDWARE_REFRESH_MS = 30000;
let modelLastStatus = null;
let modelGroupsSig = "";
let modelCatalogNames = "";
let modelCustom = null; // { name, info } for the name just checked

function modelHidesBig() {
  try {
    return prefs.get("hideBigModels", null) === "1";
  } catch (error) {
    return false;
  }
}

function modelBase(name) {
  return String(name || "").replace(/:latest$/, "");
}

function modelSame(a, b) {
  return !!a && !!b && modelBase(a) === modelBase(b);
}

//: The installed model a catalogue name stands for: the catalogue says
//: `llama3.2`, Ollama reports `llama3.2:latest`.
function modelInstalledName(name, status) {
  const hit = (status.installed_models || []).find((m) => modelSame(m.name, name));
  return hit ? hit.name : null;
}

//: The roles an installed model plays right now, from the status.
function modelRoles(installed, status) {
  const roles = [];
  if (!installed) return roles;
  if (modelSame(status.chat_model, installed)) roles.push("chat");
  if (status.utility_model && modelSame(status.utility_model, installed)) roles.push("background jobs");
  if (modelSame(status.vision_model_resolved || status.vision_model, installed)) roles.push("images");
  if (modelSame(status.ocr_model_resolved || status.ocr_model, installed)) roles.push("reading text");
  if (status.embedding_backend === "ollama" && modelSame(status.embedding_model, installed)) roles.push("search");
  return roles;
}

function modelState(model, status) {
  const installed = modelInstalledName(model.name, status);
  const pull = (status.pulls || {})[model.name];
  const running = pull && pull.status === "running";
  return {
    installed,
    pull,
    roles: modelRoles(installed, status),
    kind: running ? "downloading" : installed ? "installed" : pull && pull.status === "error" ? "failed" : "available",
  };
}

//: The name as a person would say it: a Hugging Face path loses its host and
//: owner (the owner moves to the facts line), nothing else changes.
function modelDisplayName(name) {
  const hf = /^hf\.co\/([^/]+)\/(.+)$/.exec(name);
  return hf ? hf[2] : name;
}

function modelGb(value) {
  return `${Number.isInteger(value) ? value : value.toFixed(1)} GB`;
}

const FIT_WORDS = {
  fits: { chip: "ph:check-circle Fits", tone: "item-label is-ok" },
  tight: { chip: "ph:warning Tight fit", tone: "item-label is-warn" },
  too_big: { chip: "ph:warning Too big here", tone: "item-label is-warn" },
};

function modelFitTitle(model) {
  if (!model.ram_gb || !modelHardwareGb) return "";
  const need = modelGb(model.ram_gb);
  const have = modelGb(modelHardwareGb);
  const reason = modelFitReasonText(model);
  if (model.fit === "fits") return `Needs about ${need} of memory; this computer has ${have}.${reason}`;
  if (model.fit === "tight") return `Needs about ${need} of memory and this computer has ${have}: it will run, with little to spare.${reason}`;
  return `Needs about ${need} of memory and this computer has ${have}: it would be very slow or fail.`;
}

//: Why the badge is not the plain share of memory (`fit_reason`, model_cards.py).
function modelFitReasonText(model) {
  const hw = modelHw.data || {};
  if (model.fit_reason === "gpu") return ` It runs on the graphics card, which has ${modelGb(hw.vram_gb || 0)} of its own.`;
  if (model.fit_reason === "low_free") return ` Only ${modelGb(hw.free_ram_gb || 0)} of memory is free right now.`;
  return "";
}

function modelFacts(model) {
  const facts = [];
  if (model.size) {
    const approximate = model.size_source !== "measured";
    const span = document.createElement("span");
    span.textContent = `${approximate ? `~${String(model.size).replace(/^~/, "")}` : model.size} on disk`;
    span.title = approximate ? "The download size we shipped. It turns exact once the model is installed." : "Measured on this computer.";
    facts.push(span);
  }
  if (model.ram_gb) {
    const span = document.createElement("span");
    span.textContent = `about ${modelGb(model.ram_gb)} of memory`;
    span.title = "An estimate for a normal conversation length.";
    facts.push(span);
  }
  const line = document.createElement("p");
  line.className = "library-file-meta model-card-facts";
  facts.forEach((fact, i) => {
    if (i) {
      const sep = document.createElement("span");
      sep.className = "library-file-meta-sep";
      sep.setAttribute("aria-hidden", "true");
      sep.textContent = "·";
      line.appendChild(sep);
    }
    line.appendChild(fact);
  });
  return line;
}

// --- actions ------------------------------------------------------------------------

async function modelDownload(model, button) {
  const memory = model.ram_gb ? ` It asks for about ${modelGb(model.ram_gb)} of memory and this computer has ${modelGb(modelHardwareGb)}.` : "";
  if (model.fit === "too_big") {
    const go = await confirmDialog(
      `${model.name} is bigger than this computer is likely to run.${memory}\n\nDownload it anyway?`,
      { confirmLabel: "Download anyway", danger: false }
    );
    if (!go) return;
  }
  if (button) button.disabled = true;
  try {
    await api("/models/pull", { method: "POST", body: JSON.stringify({ name: model.name }) });
    refreshModelStatus();
  } catch (error) {
    toast(error.message, true);
    if (button) button.disabled = false;
  }
}

async function modelCancel(model, button) {
  if (button) button.disabled = true;
  try {
    await api(`/models/jobs/cancel?kind=pull&name=${encodeURIComponent(model.name)}`, { method: "POST" });
  } catch (error) {
    toast(error.message, true);
  }
  refreshModelStatus();
}

async function modelUse(model, purpose, installedName, button) {
  const use = MODEL_USE[purpose];
  if (!use) return;
  if (purpose === "embeddings") {
    const go = await confirmDialog(
      `Search will re-read every note with ${installedName}. It runs in the background, and search uses keywords until it finishes.`,
      { confirmLabel: "Switch and re-index", danger: false }
    );
    if (!go) return;
  }
  if (button) button.disabled = true;
  try {
    const body = purpose === "embeddings" ? { backend: "ollama", model: installedName } : { name: installedName };
    await api(use.path, { method: "POST", body: JSON.stringify(body) });
    toast(`${installedName} is now used for ${use.role}.`);
    refreshModelStatus();
  } catch (error) {
    toast(error.message, true);
    if (button) button.disabled = false;
  }
}

async function modelRemove(installedName) {
  if (!(await confirmDialog(`Remove “${installedName}” from Ollama? This frees its disk space, you can re-download it any time.`))) return;
  try {
    await api("/models/delete", { method: "POST", body: JSON.stringify({ name: installedName }) });
    toast(`Removed ${installedName}.`);
    refreshModelStatus();
  } catch (error) {
    toast(error.message, true);
  }
}

function modelMenuItems(model, state) {
  const items = [];
  if (state.installed) {
    //: An installed model is offered the uses its kind has (`uses`, from the
    //: poll: `model_cards.installed_uses`), so an embedding model says "Use
    //: for search" and never "Use for chat"; a catalogue model offers its own
    //: purpose first as the primary button and the other sensible one here.
    const offered = model.custom ? model.uses || ["chat"] : model.purpose_key === "chat" ? ["utility"] : [];
    for (const purpose of offered) {
      if (purpose === "utility") {
        items.push({
          label: "ph:lightning Use for background jobs",
          title: "Filing, the digest and writing fixes run on this model",
          group: "use",
          run: async () => {
            try {
              await api("/models/utility-model", { method: "POST", body: JSON.stringify({ name: state.installed }) });
              toast(`Background jobs now use ${state.installed}.`);
              refreshModelStatus();
            } catch (error) {
              toast(error.message, true);
            }
          },
        });
      } else if (!(state.roles || []).includes(MODEL_USE[purpose].role)) {
        items.push({
          label: `ph:check-circle ${MODEL_USE[purpose].label}`,
          title: `Use ${state.installed} for ${MODEL_USE[purpose].role}`,
          group: "use",
          run: () => modelUse(model, purpose, state.installed),
        });
      }
    }
  }
  items.push({
    label: "ph:copy Copy name",
    title: "Copy the name Ollama knows this model by",
    group: "name",
    run: async () => {
      //: The shared helper: it falls back where the clipboard API is absent
      //: (the desktop window over plain http), as every copy path does.
      if (await copyToClipboard(model.name)) toast("Copied the name.");
      else toast("Couldn't copy it from here.", "info");
    },
  });
  if (state.installed) {
    const busy = state.roles.length > 0;
    items.push({
      label: "ph:trash Remove",
      title: busy ? `In use for ${state.roles.join(" and ")}, so it can't be removed` : "Free its disk space",
      disabled: busy,
      danger: true,
      group: "remove",
      run: () => (onOtherDevice() ? toast(THIS_COMPUTER_ONLY, "info") : busy ? toast(`${state.installed} is in use for ${state.roles.join(" and ")}. Choose another model there first.`, "info") : modelRemove(state.installed)),
    });
  }
  return items;
}

// --- one card -------------------------------------------------------------------------

//: Decimal, like the sizes the server prints (`_human_bytes`) and the download
//: sizes in the catalogue: a card that said "2.0 GB" above "1.9 GB of 1.9 GB"
//: would be the app disagreeing with itself.
function modelBytes(count) {
  if (count >= 1e9) return `${(count / 1e9).toFixed(1)} GB`;
  return `${Math.round(count / 1e6)} MB`;
}

function modelProgressText(pull) {
  if (!pull || !pull.total) return "Starting…";
  const pct = Math.min(100, Math.round((pull.done / pull.total) * 100));
  return `${pct}% · ${modelBytes(pull.done)} of ${modelBytes(pull.total)}`;
}

function modelSignature(model, state) {
  return JSON.stringify([
    model.name, model.fit, model.fit_reason, model.size,model.size_source, model.ram_gb, model.recommended,
    state.kind, state.installed, state.roles,
    state.pull ? [state.pull.status, state.pull.error] : null, modelHardwareGb,
  ]);
}

function buildModelCard(model, state) {
  const card = document.createElement("article");
  card.className = "model-card";
  card.dataset.model = model.name;
  card.dataset.state = state.kind;
  card.dataset.fit = model.fit || "unknown";

  const head = document.createElement("div");
  head.className = "model-card-head";
  const name = document.createElement("h5");
  name.className = "model-card-name";
  name.textContent = model.label || modelDisplayName(model.name);
  name.title = model.name;
  head.appendChild(name);
  if (model.recommended) {
    const pick = chip("ph:star Our starting pick", "item-label");
    pick.title = "Chosen for being small and dependable for this job. Not a benchmark.";
    head.appendChild(pick);
  }
  card.appendChild(head);

  if (model.purpose) {
    const purpose = document.createElement("p");
    purpose.className = "model-card-purpose muted";
    purpose.textContent = model.purpose;
    card.appendChild(purpose);
  } else if (model.detail) {
    const detail = document.createElement("p");
    detail.className = "model-card-purpose muted";
    detail.textContent = model.detail;
    card.appendChild(detail);
  }
  if (model.size || model.ram_gb) card.appendChild(modelFacts(model));
  const good = (model.good_for || []).map((tag) => MODEL_GOOD_FOR[tag] || tag);
  const hf = /^hf\.co\/([^/]+)\//.exec(model.name);
  const about = [];
  if (good.length) about.push(`Good for ${good.join(", ")}.`);
  if (hf) about.push(`From ${hf[1]} on Hugging Face.`);
  if (about.length) {
    const line = document.createElement("p");
    line.className = "model-card-good";
    line.textContent = about.join(" ");
    card.appendChild(line);
  }

  //: Badges, on a row of their own above the actions (INBOX 468: in the foot
  //: they wrapped into a ragged stack beside the button): the fit, then what
  //: it is doing for you now. One recipe, `chip item-label`.
  const badges = document.createElement("div");
  badges.className = "model-card-badges";
  const fit = FIT_WORDS[model.fit];
  if (fit) {
    const mark = chip(fit.chip, fit.tone);
    mark.title = modelFitTitle(model);
    badges.appendChild(mark);
  }
  //: Not in the Installed models list, where every card is installed.
  if (state.installed && !model.listed) badges.appendChild(chip("ph:check Installed", "item-label"));
  if (state.roles.length) {
    const using = chip(`ph:lightning In use for ${state.roles.join(" and ")}`, "item-label is-yours");
    using.title = using.textContent;
    badges.appendChild(using);
  }
  if (state.pull && state.pull.status === "cancelled" && state.kind === "available") badges.appendChild(chip("Download cancelled", "item-label"));
  if (badges.children.length) card.appendChild(badges);

  if (state.kind === "downloading") {
    const box = document.createElement("div");
    box.className = "model-card-progress";
    const bar = document.createElement("progress");
    bar.className = "model-progress";
    bar.setAttribute("aria-label", `Downloading ${model.name}`);
    const text = document.createElement("span");
    text.className = "model-progress-text muted";
    box.append(bar, text);
    card.appendChild(box);
    updateModelProgress(card, state.pull);
  }
  if (state.kind === "failed") {
    const failed = document.createElement("p");
    failed.className = "status error model-card-error";
    failed.textContent = (state.pull && state.pull.error) || `Couldn't download ${model.name}.`;
    card.appendChild(failed);
  }

  //: One primary action, and a menu for the rest.
  const actions = document.createElement("div");
  actions.className = "model-card-actions";
  const filled = !!model.recommended || !!model.custom;
  let primary = null;
  if (state.kind === "downloading") {
    primary = smallButton("Cancel download", `Stop downloading ${model.name}`, (event) => modelCancel(model, event.currentTarget), true);
  } else if (state.kind === "installed") {
    const purpose = model.custom ? null : model.purpose_key;
    const use = purpose && MODEL_USE[purpose];
    if (use && !state.roles.includes(use.role)) {
      primary = smallButton(use.label, `Use ${state.installed} for ${use.role}`, (event) => modelUse(model, purpose, state.installed, event.currentTarget), !filled);
    }
  } else {
    const label = state.kind === "failed" ? "Retry" : "Download";
    primary = smallButton(label, `Download ${model.name} with Ollama`, (event) => modelDownload(model, event.currentTarget), !filled || model.fit === "too_big");
    primary.dataset.thisComputer = "";
  }
  if (primary) {
    primary.classList.add("model-card-primary");
    actions.appendChild(primary);
  }
  const menu = state.kind !== "downloading" && kebabMenu(modelMenuItems(model, state), `More for ${model.name}`);
  //: **No main button: the menu sits in the head, top right** (the owner,
  //: 2026-10-06, "wierd gaps on model cards"). An installed card's foot held
  //: only the ⋯, pinned to the bottom under an empty band.
  if (!primary && menu) {
    head.appendChild(menu);
    return card;
  }
  if (menu) actions.appendChild(menu);
  card.appendChild(actions);
  return card;
}

function updateModelProgress(card, pull) {
  const bar = card.querySelector(".model-progress");
  const text = card.querySelector(".model-progress-text");
  if (!bar || !text) return;
  if (pull && pull.total) {
    bar.max = Math.max(pull.total, 1);
    bar.value = pull.done;
  } else {
    bar.removeAttribute("value");
  }
  text.textContent = modelProgressText(pull);
}

//: Make sure a model has its card, current. Returns the element.
function modelCardFor(model, status) {
  const state = modelState(model, status);
  const sig = modelSignature(model, state);
  let entry = modelCards.get(model.name);
  if (!entry) {
    entry = { el: null, sig: "" };
    modelCards.set(model.name, entry);
  }
  if (entry.sig !== sig || !entry.el) {
    //: Focus inside the old card survives a rebuild: onto the new primary
    //: button, or the menu, whichever the card has.
    const had = entry.el && entry.el.contains(document.activeElement);
    const next = buildModelCard(model, state);
    if (entry.el && entry.el.parentNode) entry.el.replaceWith(next);
    entry.el = next;
    entry.sig = sig;
    if (had) (next.querySelector(".model-card-primary") || next.querySelector(".menu-wrap button"))?.focus({ preventScroll: true });
  } else if (state.kind === "downloading") {
    updateModelProgress(entry.el, state.pull);
  }
  return entry.el;
}

// --- the groups --------------------------------------------------------------------------

//: Open when the person left it open, else the first group, else when
//: something in it is being downloaded or is in use right now.
function modelGroupOpen(kind, shown, status) {
  try {
    const kept = prefs.get(`modelGroup:${kind}`, null);
    if (kept !== null) return kept === "1";
  } catch (error) {
    /* fall through to the default */
  }
  if (kind === "text") return true;
  return shown.some((m) => {
    const state = modelState(m, status);
    return state.kind === "downloading" || state.roles.length > 0;
  });
}

//: **The installed models, as model cards** (UI_MODERNISATION_PLAN, Settings
//: information architecture, decision 10: "the Installed models list is the
//: old row list"; op4-1005). The row list said "in use" without saying for
//: what, and offered Remove or nothing. Each installed model is now the
//: suggested downloads' own card (`buildModelCard`) as a custom model: its
//: size measured on this computer, "In use for chat and images" where it is
//: one, and its menu (`modelMenuItems`): the uses its kind has (`uses`),
//: copy its name, Remove (disabled, with the reason, while in use).
//: Built fresh rather than through `modelCardFor`, whose cache is keyed by name
//: and owns the suggested list's element for the same model; redrawn only when
//: what it shows changes, so a poll never takes the focus out of an open menu.
function renderInstalledModels(status) {
  const box = $("installed-box");
  const list = $("installed-list");
  if (!box || !list) return;
  const models = status.installed_models || [];
  box.classList.toggle("hidden", models.length === 0);
  const cards = models.map((m) => {
    const model = { name: m.name, size: m.size ? modelBytes(m.size) : "", size_source: "measured", custom: true, listed: "installed", uses: m.uses };
    return [model, modelState(model, status)];
  });
  const sig = JSON.stringify(cards.map(([model, state]) => modelSignature(model, state)));
  if (list.dataset.sig === sig) return;
  list.dataset.sig = sig;
  list.replaceChildren(...cards.map(([model, state]) => buildModelCard(model, state)));
}

function renderSuggested(status) {
  modelLastStatus = status;
  const host = $("suggested-list");
  if (!host || !suggestedCatalog) return;
  if (modelHardwareGb === undefined) {
    modelHardwareGb = null;
    refreshModelHardware(false);
  } else if (Date.now() - modelHw.at > MODEL_HARDWARE_REFRESH_MS) {
    refreshModelHardware(true);
  }
  paintModelHardware();

  //: Measured sizes arrive with the catalogue, so a model installed since it
  //: was read is read again, once.
  const installedNames = (status.installed_models || []).map((m) => m.name).sort().join("|");
  if (modelCatalogNames && installedNames !== modelCatalogNames) {
    modelCatalogNames = installedNames;
    apiJson("/models/suggested", { silent: true })
      .then((fresh) => {
        suggestedCatalog = fresh;
        if (modelLastStatus) renderSuggested(modelLastStatus);
      })
      .catch(() => {});
  } else if (!modelCatalogNames) {
    modelCatalogNames = installedNames;
  }

  const hide = modelHidesBig();
  const toggle = $("suggested-hide-big");
  if (toggle) toggle.checked = hide;
  $("suggested-hide-wrap")?.classList.toggle("hidden", !modelHardwareGb);

  let hidden = 0;
  const groups = [];
  for (const [kind, models] of Object.entries(suggestedCatalog)) {
    if (!models.length) continue;
    const meta = MODEL_GROUPS[kind] || { title: kind, about: "" };
    const shown = [];
    for (const model of [...models].sort((a, b) => Number(b.recommended) - Number(a.recommended))) {
      if (hide && model.fit === "too_big" && !modelInstalledName(model.name, status)) {
        hidden += 1;
        continue;
      }
      shown.push(model);
    }
    if (shown.length) groups.push({ kind, meta, shown });
  }

  const sig = JSON.stringify([hide, groups.map((g) => [g.kind, g.shown.map((m) => m.name)])]);
  if (sig !== modelGroupsSig || !host.firstChild) {
    modelGroupsSig = sig;
    host.replaceChildren();
    for (const group of groups) {
      //: **A group is a fold** (the `details.settings-fold` recipe): thirty-one
      //: cards in one run was 4,081px at 1440 (8,626 at 390), and nobody reads
      //: the images list while choosing a chat model. The first group is open;
      //: the rest open on a press and keep what you chose, per browser. A
      //: group with a download running or a model in use opens itself.
      const section = document.createElement("details");
      section.className = "settings-fold model-group";
      section.dataset.group = group.kind;
      section.open = modelGroupOpen(group.kind, group.shown, status);
      section.addEventListener("toggle", () => {
        try {
          prefs.set(`modelGroup:${group.kind}`, section.open ? "1" : "0");
        } catch (error) {
          /* the choice just does not persist */
        }
      });
      const summary = document.createElement("summary");
      const head = document.createElement("div");
      head.className = "row help-head";
      const title = document.createElement("h4");
      title.className = "inline-h3";
      title.textContent = group.meta.title;
      const count = document.createElement("span");
      count.className = "muted model-group-count";
      count.textContent = `${group.shown.length} ${group.shown.length === 1 ? "model" : "models"}`;
      head.append(title, count);
      summary.appendChild(head);
      const about = document.createElement("p");
      about.className = "muted";
      about.textContent = group.meta.about;
      const grid = document.createElement("div");
      grid.className = "model-grid";
      grid.dataset.group = group.kind;
      section.append(summary, about, grid);
      host.appendChild(section);
    }
  }
  for (const group of groups) {
    const grid = host.querySelector(`.model-grid[data-group="${group.kind}"]`);
    if (!grid) continue;
    group.shown.forEach((model, i) => {
      const el = modelCardFor(model, status);
      if (grid.children[i] !== el) grid.insertBefore(el, grid.children[i] || null);
    });
  }
  const note = $("suggested-hide-wrap")?.querySelector("span");
  if (note) note.textContent = hide && hidden ? `Hide models too big for this computer (${hidden} hidden)` : "Hide models too big for this computer";
  renderCustomCards(status);
}

//: The hardware line above the cards (INBOX 904 B67): memory, memory free now,
//: the graphics card, and how many models are here, with Edit to correct it.
function modelHardwareSentence(hw) {
  const parts = [`${modelGb(hw.ram_gb)} of memory`];
  if (hw.free_ram_gb) parts[0] += ` (${modelGb(hw.free_ram_gb)} free now)`;
  const card = (hw.gpus || [])[0];
  if (hw.vram_gb) parts.push(`${card && !hw.override ? `${card.name} with ` : ""}${modelGb(hw.vram_gb)} of video memory`);
  else if (card && card.shared) parts.push(`${card.name}, which shares the memory`);
  else parts.push("no graphics card with memory of its own");
  const here = hw.models_installed
    ? ` ${hw.models_installed} model${hw.models_installed === 1 ? "" : "s"} installed${hw.models_loaded ? `, ${hw.models_loaded} loaded now` : ""}.`
    : "";
  const fixed = hw.override ? " You corrected these numbers." : "";
  return `This computer: ${parts.join(", ")}.${here}${fixed} Each card says whether a model fits.`;
}

function paintModelHardware() {
  const line = $("suggested-hardware");
  if (!line) return;
  const hw = modelHw.data;
  line.textContent = modelHardwareGb && hw
    ? modelHardwareSentence(hw)
    : "Models Ollama can download for you. This computer's memory could not be read, so fit is not shown. Edit tells us what it has.";
  $("suggested-hardware-edit")?.classList.toggle("hidden", !hw);
}

async function refreshModelHardware(withCatalog) {
  modelHw.at = Date.now();
  try {
    const reply = await apiJson("/models/hardware", { silent: true });
    modelHw.data = reply;
    modelHardwareGb = reply && reply.ram_gb ? reply.ram_gb : null;
    if (withCatalog) suggestedCatalog = (await apiJson("/models/suggested", { silent: true })) || suggestedCatalog;
  } catch (error) {
    return;
  }
  paintModelHardware();
  if (modelLastStatus) renderSuggested(modelLastStatus);
}

function openModelHardwareForm(open) {
  const form = $("suggested-hardware-form");
  const edit = $("suggested-hardware-edit");
  if (!form || !edit) return;
  form.classList.toggle("hidden", !open);
  edit.setAttribute("aria-expanded", String(open));
  if (!open || !modelHw.data) return;
  $("hardware-ram").value = modelHw.data.ram_gb || "";
  $("hardware-vram").value = modelHw.data.vram_gb || 0;
  $("hardware-ram").focus();
}

//: Blank memory means "as detected"; Undo and Redo use the same PUT.
async function putModelHardware(body) {
  modelHw.data = await apiJson("/models/hardware", { method: "PUT", body: JSON.stringify(body) });
  modelHardwareGb = modelHw.data.ram_gb || null;
  refreshModelHardware(true);
}

async function saveModelHardware(body) {
  const before = modelHw.data?.override || {};
  try {
    await putModelHardware(body);
  } catch (error) {
    toast(error.message || "Could not save that.", true);
    return;
  }
  openModelHardwareForm(false);
  offerUndo("Memory correction", "Memory saved.", () => putModelHardware(before), () => putModelHardware(body));
}

$("suggested-hardware-edit")?.addEventListener("click", () => {
  openModelHardwareForm($("suggested-hardware-form").classList.contains("hidden"));
});
$("hardware-cancel")?.addEventListener("click", () => openModelHardwareForm(false));
$("hardware-reset")?.addEventListener("click", () => saveModelHardware({}));
$("suggested-hardware-form")?.addEventListener("submit", (event) => {
  event.preventDefault();
  const ram = parseFloat($("hardware-ram").value);
  const vram = parseFloat($("hardware-vram").value);
  const body = {};
  //: Only a number that differs from the detected one is a correction.
  if (ram > 0 && ram !== modelHw.data.detected_ram_gb) body.ram_gb = ram;
  if (vram >= 0 && vram !== (modelHw.data.detected_vram_gb || 0)) body.vram_gb = vram;
  saveModelHardware(body);
});

// --- "Download another model" ----------------------------------------------------------------

//: A custom card is a card like any other for a name that is not in the
//: catalogue: the one just checked, and any download of one still running (a
//: reload does not lose it).
function renderCustomCards(status) {
  const host = $("custom-model-cards");
  if (!host) return;
  const catalogued = new Set(Object.values(suggestedCatalog || {}).flat().map((m) => m.name));
  const wanted = new Map();
  for (const [name, pull] of Object.entries(status.pulls || {})) {
    if (!catalogued.has(name) && (pull.status === "running" || pull.status === "error")) wanted.set(name, null);
  }
  if (modelCustom && !catalogued.has(modelCustom.name)) wanted.set(modelCustom.name, modelCustom.info);
  const cards = [];
  for (const [name, info] of wanted) {
    const model = {
      name,
      custom: true,
      kind: "custom",
      fit: "unknown",
      detail: info ? `${info.title}. ${info.detail}` : "A download you started.",
      good_for: [],
    };
    cards.push(modelCardFor(model, status));
  }
  const keep = new Set(cards);
  for (const child of [...host.children]) if (!keep.has(child)) child.remove();
  cards.forEach((el, i) => {
    if (host.children[i] !== el) host.insertBefore(el, host.children[i] || null);
  });
}

async function checkCustomModel() {
  const input = $("custom-model-name");
  const note = $("custom-model-note");
  if (!input || !note) return;
  const typed = input.value.trim();
  note.className = "status";
  if (!typed) {
    note.textContent = "Type a model name or paste a link first.";
    modelCustom = null;
    if (modelLastStatus) renderSuggested(modelLastStatus);
    return;
  }
  note.textContent = "Checking…";
  let info;
  try {
    info = await apiJson("/models/inspect", { method: "POST", body: JSON.stringify({ name: typed }) });
  } catch (error) {
    note.className = "status error";
    note.textContent = error.message || "Couldn't check that name.";
    return;
  }
  if (!info.valid) {
    note.className = "status error";
    note.textContent = info.error;
    modelCustom = null;
    if (modelLastStatus) renderSuggested(modelLastStatus);
    return;
  }
  const bits = [`${info.title}.`];
  if (info.installed) bits.push("Already installed.");
  if (info.suggested) bits.push(`In the list above (${info.suggested.size}).`);
  if (info.name !== typed) bits.push(`Will download ${info.name}.`);
  bits.push(...(info.warnings || []));
  note.textContent = bits.join(" ");
  modelCustom = { name: info.name, info };
  if (modelLastStatus) renderSuggested(modelLastStatus);
}

$("custom-model-check")?.addEventListener("click", checkCustomModel);
$("custom-model-name")?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    checkCustomModel();
  }
});
$("custom-model-name")?.addEventListener("input", () => {
  //: A new name is a new question: the old answer's card goes.
  if (modelCustom) {
    modelCustom = null;
    $("custom-model-note").textContent = "";
    if (modelLastStatus) renderSuggested(modelLastStatus);
  }
});
$("suggested-hide-big")?.addEventListener("change", (event) => {
  try {
    prefs.set("hideBigModels", event.target.checked ? "1" : "0");
  } catch (error) {
    /* the choice just does not persist */
  }
  if (modelLastStatus) renderSuggested(modelLastStatus);
});
