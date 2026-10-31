// model-menu.js (lazy, LAZY_MODULES.modelMenu): the model picker's shape.
// INBOX 1477, the owner's reference: a search field at the top, a "Recent"
// section, one collapsible row per source with its count ("On this computer,
// 4 models"), and per model a glyph, the name cut by an ellipsis and a pin
// that lifts it to the top.
//
// It dresses the menu `enhanceSelect` (sheets-selects.js) already draws for a
// `.feature-model-select`, the Chat, Ask and Writing pickers, and builds no
// second picker: the option rows `enhanceSelect` made are the ones a press
// runs (each shown row calls its row's own click), `syncValue` still marks the
// chosen one, and the menu opens, places, closes and returns focus through
// `openActionMenu` and `closeActionMenus` as every select does.
//
// The backend reports one provider at a time, so a model's source is read
// from its name (`modelSource`): Ollama's cloud models, Hugging Face files and
// the rest, "On this computer" (or "On the model server" when the status says
// the server is not local). Pins and recent picks are the person's, kept in
// `model-pins` and `model-recent`, which `MIRRORED_UI_EXTRAS` carries to the
// notebook so a restart or a second browser keeps them.

const MODEL_PINS_KEY = "model-pins";
const MODEL_RECENT_KEY = "model-recent";
const MODEL_RECENT_SHOWN = 3;
//: Source keys the person folded or opened this visit; a source holding the chosen model starts open.
const modelMenuOpenState = new Map();

function modelMenuList(key) {
  try {
    const list = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(list) ? list.filter((name) => typeof name === "string") : [];
  } catch {
    return [];
  }
}

function modelMenuSave(key, list) {
  try {
    localStorage.setItem(key, JSON.stringify(list));
  } catch {
    // Storage blocked: the menu still works, it just forgets.
  }
}

//: Where a model lives, from its name and the status (see the header).
function modelSource(name) {
  const lower = String(name).toLowerCase();
  if (/[:-]cloud$/.test(lower)) return { key: "cloud", label: "Ollama cloud", icon: "ph-cloud" };
  if (/^(hf\.co|huggingface\.co)\//.test(lower)) return { key: "hf", label: "From Hugging Face", icon: "ph-package" };
  if (typeof modelStatus !== "undefined" && modelStatus && modelStatus.is_local === false) {
    return { key: "server", label: "On the model server", icon: "ph-hard-drives" };
  }
  return { key: "local", label: "On this computer", icon: "ph-desktop" };
}

function modelCountLabel(count) {
  return `${count} model${count === 1 ? "" : "s"}`;
}

//: One shown row: the option's own row does the choosing, a pin sits beside it.
function modelMenuItem(model, state) {
  const item = document.createElement("div");
  item.className = "mm-item";
  item.dataset.find = `${model.value} ${model.label}`.toLowerCase();
  const row = document.createElement("button");
  row.type = "button";
  row.className = "menu-item select-option mm-option";
  row.setAttribute("role", "option");
  row.dataset.value = model.value;
  row.title = model.value || model.label;
  const glyph = document.createElement("i");
  glyph.className = `ph ${model.icon} mm-glyph`;
  glyph.setAttribute("aria-hidden", "true");
  const name = document.createElement("span");
  name.className = "mm-name";
  name.textContent = model.value ? shortModelName(model.value) : model.label;
  row.append(glyph, name);
  row.addEventListener("click", (event) => {
    event.stopPropagation();
    model.row.click();
  });
  item.append(row);
  if (model.value) item.append(modelMenuPin(model, state));
  return item;
}

function modelMenuPin(model, state) {
  const pinned = state.pins.includes(model.value);
  const pin = document.createElement("button");
  pin.type = "button";
  pin.className = "mm-pin";
  pin.dataset.model = model.value;
  pin.setAttribute("aria-pressed", String(pinned));
  pin.title = pinned ? `Unpin ${model.value}` : `Pin ${model.value} to the top`;
  pin.setAttribute("aria-label", pin.title);
  const icon = document.createElement("i");
  icon.className = `ph ${pinned ? "ph-fill " : ""}ph-push-pin`;
  icon.setAttribute("aria-hidden", "true");
  pin.append(icon);
  pin.addEventListener("click", (event) => {
    event.stopPropagation();
    state.pins = pinned ? state.pins.filter((name) => name !== model.value) : [model.value, ...state.pins];
    modelMenuSave(MODEL_PINS_KEY, state.pins);
    state.render();
    state.body.querySelector(`.mm-pin[data-model="${CSS.escape(model.value)}"]`)?.focus();
  });
  return pin;
}

function modelMenuLabel(text) {
  const label = document.createElement("div");
  label.className = "select-group-label mm-label";
  label.textContent = text;
  return label;
}

//: A source's header and its models; folding is the header's own button.
function modelMenuGroup(source, models, state) {
  const open = modelMenuOpenState.has(source.key)
    ? modelMenuOpenState.get(source.key)
    : state.groups === 1 || models.some((model) => model.value === state.chosen);
  const group = document.createElement("div");
  group.className = "mm-group";
  const head = document.createElement("button");
  head.type = "button";
  head.className = "menu-item mm-group-head";
  head.setAttribute("aria-expanded", String(open));
  const caret = document.createElement("i");
  caret.className = "ph ph-caret-right mm-caret";
  caret.setAttribute("aria-hidden", "true");
  const glyph = document.createElement("i");
  glyph.className = `ph ${source.icon} mm-glyph`;
  glyph.setAttribute("aria-hidden", "true");
  const words = document.createElement("span");
  words.className = "mm-group-words";
  const count = document.createElement("span");
  count.className = "mm-group-count";
  count.textContent = `, ${modelCountLabel(models.length)}`;
  words.append(source.label, count);
  head.append(caret, glyph, words);
  const list = document.createElement("div");
  list.className = "mm-group-list";
  list.hidden = !open;
  for (const model of models) list.append(modelMenuItem({ ...model, icon: source.icon }, state));
  head.addEventListener("click", () => {
    const next = head.getAttribute("aria-expanded") !== "true";
    modelMenuOpenState.set(source.key, next);
    head.setAttribute("aria-expanded", String(next));
    list.hidden = !next;
  });
  group.append(head, list);
  group.dataset.count = String(models.length);
  return group;
}

//: The typed words narrow every row at once: sections go, groups open on what matches.
function applyModelQuery(state) {
  const words = state.input.value.trim().toLowerCase();
  state.body.classList.toggle("is-searching", Boolean(words));
  let hits = 0;
  for (const group of state.body.querySelectorAll(".mm-group")) {
    const items = [...group.querySelectorAll(".mm-item")];
    let inGroup = 0;
    for (const item of items) {
      const show = !words || item.dataset.find.includes(words);
      item.classList.toggle("hidden", !show);
      if (show) inGroup += 1;
    }
    group.classList.toggle("hidden", Boolean(words) && inGroup === 0);
    group.querySelector(".mm-group-list").hidden = words
      ? false
      : group.querySelector(".mm-group-head").getAttribute("aria-expanded") !== "true";
    group.querySelector(".mm-group-count").textContent = words
      ? `, ${inGroup} of ${modelCountLabel(items.length)}`
      : `, ${modelCountLabel(items.length)}`;
    hits += inGroup;
  }
  state.empty.classList.toggle("hidden", !words || hits > 0);
}

function modelMenuRender(state) {
  const parts = [];
  const byValue = new Map(state.models.map((model) => [model.value, model]));
  if (state.fallback) parts.push(modelMenuItem({ ...state.fallback, icon: "ph-circle-dashed" }, state));
  const pinned = state.pins.map((name) => byValue.get(name)).filter(Boolean);
  const recent = state.recent
    .filter((name) => !state.pins.includes(name))
    .map((name) => byValue.get(name))
    .filter(Boolean)
    .slice(0, MODEL_RECENT_SHOWN);
  for (const [title, list] of [["Pinned", pinned], ["Recent", recent]]) {
    if (!list.length) continue;
    const section = document.createElement("div");
    section.className = "mm-section";
    section.append(modelMenuLabel(title));
    for (const model of list) section.append(modelMenuItem({ ...model, icon: modelSource(model.value).icon }, state));
    parts.push(section);
  }
  const groups = new Map();
  for (const model of state.models) {
    const source = modelSource(model.value);
    if (!groups.has(source.key)) groups.set(source.key, { source, models: [] });
    groups.get(source.key).models.push(model);
  }
  state.groups = groups.size;
  for (const { source, models } of groups.values()) parts.push(modelMenuGroup(source, models, state));
  state.body.replaceChildren(...parts, state.empty);
  applyModelQuery(state);
}

//: The rows an arrow can land on, in the order the eye reads them.
function modelMenuStops(menu) {
  return [...menu.querySelectorAll(".mm-search-input, .mm-group-head, .mm-option")].filter((el) => el.getClientRects().length);
}

//: Arrows, Home and End walk the stops; the search keeps its own Home and End.
function modelMenuWalk(event, menu) {
  const stops = modelMenuStops(menu);
  const inSearch = document.activeElement.classList.contains("mm-search-input");
  const step = { ArrowDown: stops.indexOf(document.activeElement) + 1, ArrowUp: stops.indexOf(document.activeElement) - 1, Home: 0, End: stops.length - 1 }[event.key];
  if (step === undefined || (inSearch && (event.key === "Home" || event.key === "End"))) return false;
  event.preventDefault();
  event.stopPropagation();
  focusMenuItem(stops[(step + stops.length) % stops.length], menu);
  return true;
}

//: Enter in the search chooses the first match; right and left cross between a row and its pin.
function modelMenuAct(event, menu) {
  const here = document.activeElement;
  if (event.key === "Enter" && here.classList.contains("mm-search-input")) {
    event.preventDefault();
    modelMenuStops(menu).find((el) => el.classList.contains("mm-option"))?.click();
    return;
  }
  const item = here.closest(".mm-item");
  const side = { ArrowRight: ".mm-pin", ArrowLeft: ".mm-option" }[event.key];
  const target = side && item ? item.querySelector(side) : null;
  if (target) {
    event.preventDefault();
    target.focus();
  }
}

function modelMenuKeys(menu, opener) {
  menu.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      closeActionMenus();
      (opener._returnFocusTo?.isConnected ? opener._returnFocusTo : opener).focus();
    } else if (!modelMenuWalk(event, menu)) modelMenuAct(event, menu);
  });
}

function modelMenuSearch(state) {
  const wrap = document.createElement("div");
  wrap.className = "mm-search";
  const field = document.createElement("div");
  field.className = "search-field";
  const icon = document.createElement("i");
  icon.className = "ph ph-magnifying-glass search-field-icon";
  icon.setAttribute("aria-hidden", "true");
  const input = document.createElement("input");
  input.type = "search";
  input.className = "search-field-input mm-search-input";
  input.placeholder = "Search models";
  input.setAttribute("aria-label", "Search models");
  input.autocomplete = "off";
  input.addEventListener("input", () => applyModelQuery(state));
  field.append(icon, input);
  wrap.append(field);
  state.input = input;
  return wrap;
}

//: What `enhanceSelect` calls after it has drawn the plain rows: the rows are
//: read, then the menu is drawn again in the picker's shape.
function decorateModelMenu(menu, select, opener) {
  const rows = [...menu.querySelectorAll(":scope > .select-option")];
  if (!rows.length) return;
  const fresh = menu.classList.contains("hidden");
  const kept = fresh ? "" : menu._modelQuery || "";
  const state = {
    models: rows.filter((row) => row.dataset.value !== "").map((row) => ({ value: row.dataset.value, label: row.textContent, row })),
    fallback: rows.filter((row) => row.dataset.value === "").map((row) => ({ value: "", label: row.textContent, row }))[0],
    pins: modelMenuList(MODEL_PINS_KEY),
    recent: modelMenuList(MODEL_RECENT_KEY),
    chosen: select.value,
    groups: 1,
  };
  if (!state.recent.length && state.chosen) state.recent = [state.chosen];
  state.empty = document.createElement("div");
  state.empty.className = "mm-empty hidden";
  state.empty.setAttribute("role", "status");
  state.empty.textContent = "No model matches.";
  state.body = document.createElement("div");
  state.body.className = "mm-body";
  state.render = () => modelMenuRender(state);
  const search = modelMenuSearch(state);
  state.input.value = kept;
  state.input.addEventListener("input", () => (menu._modelQuery = state.input.value));
  menu.classList.add("model-menu");
  menu.replaceChildren(search, state.body);
  state.render();
  if (!menu.dataset.modelKeys) {
    menu.dataset.modelKeys = "1";
    modelMenuKeys(menu, opener);
  }
  if (!select.dataset.modelRecent) {
    select.dataset.modelRecent = "1";
    select.addEventListener("change", () => modelMenuRemember(select.value));
  }
  //: Opening puts the cursor in the search on a pointer that has a keyboard; a phone keeps its chosen row.
  if (fresh) {
    menu._modelQuery = "";
    queueMicrotask(() => {
      if (!window.matchMedia("(pointer: coarse)").matches && menu.getClientRects().length) state.input.focus({ preventScroll: true });
    });
  }
}

function modelMenuRemember(value) {
  if (!value) return;
  modelMenuSave(MODEL_RECENT_KEY, [value, ...modelMenuList(MODEL_RECENT_KEY).filter((name) => name !== value)].slice(0, 8));
}
