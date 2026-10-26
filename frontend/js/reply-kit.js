// reply-kit.js: what the app draws into a reply beside its words (INBOX 1300
// C06, the owner: "I want the composer and ai's responses to be more visually
// impressive and interactive helped by the app").
//
// Lazy (`LAZY_MODULES.replyKit` in lazy-entries.js, with reply-kit-lazy.css). One renderer for
// every answer surface (Chat, Ask, the popup agent), whoever wrote the words:
// the stream's `panel` event names what to draw (routes_chat `reply_panel`),
// and a model's answer gets the same panel a composed one does (CHAT_PLAN
// decision 75: the panel assists the model, it never replaces it).

//: "statistics": the notebook in cards with small charts (`GET /statistics`,
//: the Statistics page's own call), and the way into that page.
//: "calculator": a sum's or a conversion's way into the calculator, with the
//: question already in it.
const REPLY_PANELS = {
  statistics: () => replyStatsPanel(),
  calculator: (event) => replyCalcPanel(event),
};

function renderReplyPanel(holder, event) {
  const build = REPLY_PANELS[event?.panel];
  if (!holder || !build) return null;
  const panel = build(event);
  holder.appendChild(panel);
  return panel;
}

//: Every panel an answer carries, drawn in order: a `web` list (the pages a
//: search found, or the one page read: ask-compose.js's cards and reader) or
//: a `panel` event. `before` keeps a page read above the popup's answer.
function replyDrawAll(holder, panels, before = null) {
  return ensureModule("askCompose").then(() => {
    for (const event of panels) {
      if (event.web && !event.web.length) continue;
      const drawn = event.web ? renderWebSources(holder, event.web, { read: Boolean(event.read) }) : renderReplyPanel(holder, event);
      if (drawn && before) holder.insertBefore(drawn, before);
    }
  });
}

function replyPanelShell(cls, label, icon) {
  const panel = document.createElement("section");
  panel.className = `reply-panel ${cls}`;
  panel.setAttribute("aria-label", label);
  const head = document.createElement("div");
  head.className = "reply-panel-head";
  const title = document.createElement("span");
  title.className = "reply-panel-title";
  setLabel(title, `${icon} ${label}`);
  head.appendChild(title);
  panel.appendChild(head);
  return { panel, head };
}

// --- elsewhere in your notebook ----------------------------------------------

// The "nothing in your notes, but…" row (moved here from capture-ask.js for
// the boot budget: it is drawn only on an answer that found no note). Sent only on the empty path (see
// `_related_elsewhere`, routes_chat.py): a question whose answer lives in a
// document, a saved chat or a reminder used to end at "I couldn't find any
// saved notes matching that question", which is true and a dead end.
//
// Chips, matching every other "here is something to open" row in this app,
// each landing on the thing itself rather than on a search for it.
function renderRelatedElsewhere(target, items) {
  if (!target || !items || !items.length) return;
  const row = document.createElement("div");
  row.className = "answer-related";
  const label = document.createElement("span");
  label.className = "muted answer-grounding-label";
  label.textContent = "Elsewhere in your notebook:";
  row.appendChild(label);
  const icons = { document: "ph:file-text", chat: "ph:chat-circle", reminder: "ph:bell" };
  for (const item of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip chip-interactive answer-related-chip";
    setNoteLabel(button, icons[item.kind] || "ph:link", item.label || item.kind, 120);
    button.title = `Open this ${item.kind}`;
    button.addEventListener("click", () => {
      if (item.kind === "document") {
        switchTab("documents");
        openDocument(item.id);
      } else if (item.kind === "chat") {
        switchTab("chat");
        openConversation?.(item.id);
      } else if (item.kind === "reminder") {
        switchTab("reminders");
      }
    });
    row.appendChild(button);
  }
  target.appendChild(row);
}

// --- the notebook in cards ---------------------------------------------------

//: One count a card: its icon, the figure, what it counts, one muted line and
//: a small chart. A card is a fact, never a control (DESIGN.md, "A chip"):
//: the one way on is the head's Open Statistics.
function replyStatCard({ icon, value, label, line, chart }) {
  const card = document.createElement("div");
  card.className = "reply-stat";
  card.setAttribute("role", "group");
  const figure = document.createElement("div");
  figure.className = "reply-stat-top";
  const glyph = document.createElement("i");
  glyph.className = `ph ph-${icon} reply-stat-icon`;
  glyph.setAttribute("aria-hidden", "true");
  const number = document.createElement("strong");
  number.className = "reply-stat-value";
  number.textContent = Number(value || 0).toLocaleString();
  figure.append(glyph, number);
  const name = document.createElement("span");
  name.className = "reply-stat-label";
  name.textContent = label;
  card.append(figure, name);
  if (line) {
    const said = document.createElement("span");
    said.className = "muted reply-stat-line";
    said.textContent = line;
    card.appendChild(said);
  }
  if (chart) card.appendChild(chart);
  card.setAttribute("aria-label", `${Number(value || 0).toLocaleString()} ${label}${line ? `, ${line}` : ""}`);
  return card;
}

const REPLY_SVG_NS = "http://www.w3.org/2000/svg";

//: A line of counts over time, no axes: the trend is the point and the
//: numbers are in its label (and on the Statistics page).
function replySpark(values, label) {
  const svg = document.createElementNS(REPLY_SVG_NS, "svg");
  svg.setAttribute("class", "reply-spark");
  svg.setAttribute("viewBox", "0 0 100 28");
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", label);
  const top = Math.max(1, ...values);
  const step = values.length > 1 ? 100 / (values.length - 1) : 100;
  const points = values.map((v, i) => [i * step, 26 - (v / top) * 23]);
  const line = points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = document.createElementNS(REPLY_SVG_NS, "polygon");
  area.setAttribute("class", "reply-spark-area");
  area.setAttribute("points", `0,28 ${line} 100,28`);
  const stroke = document.createElementNS(REPLY_SVG_NS, "polyline");
  stroke.setAttribute("class", "reply-spark-line");
  stroke.setAttribute("points", line);
  stroke.setAttribute("vector-effect", "non-scaling-stroke");
  svg.append(area, stroke);
  return svg;
}

//: A share as a filled track: a full-width bar scaled from the left, never a
//: width that grows (DESIGN.md, "An animation of anything").
function replyMeter(share, label) {
  const track = document.createElement("div");
  track.className = "reply-meter";
  track.setAttribute("role", "img");
  track.setAttribute("aria-label", label);
  const fill = document.createElement("span");
  fill.className = "reply-meter-fill";
  fill.dataset.share = String(Math.max(0, Math.min(1, share || 0)));
  track.appendChild(fill);
  return track;
}

//: This week against last, as two short bars on one scale.
function replyCompare(now, before, label) {
  const box = document.createElement("div");
  box.className = "reply-compare";
  box.setAttribute("role", "img");
  box.setAttribute("aria-label", label);
  const top = Math.max(1, now, before);
  for (const [value, cls] of [[now, "is-now"], [before, "is-before"]]) {
    const track = document.createElement("span");
    track.className = `reply-compare-bar ${cls}`;
    const fill = document.createElement("span");
    fill.className = "reply-meter-fill";
    fill.dataset.share = String(value / top);
    track.appendChild(fill);
    box.appendChild(track);
  }
  return box;
}

//: The meters fill once they are on the page: a transform through the CSSOM
//: (the CSP refuses a style attribute), so nothing lays out.
function replyFillMeters(panel) {
  requestAnimationFrame(() =>
    requestAnimationFrame(() => {
      for (const fill of panel.querySelectorAll(".reply-meter-fill")) fill.style.transform = `scaleX(${fill.dataset.share || 0})`;
    })
  );
}

function replyMonthName(key) {
  const [year, month] = String(key).split("-").map(Number);
  return new Date(year, (month || 1) - 1, 1).toLocaleDateString(undefined, { month: "short" });
}

function replyStatCards(page) {
  const book = page.notebook || {};
  const rem = page.reminders || {};
  const week = page.week || { this: {}, last: {} };
  const growth = (book.growth || []).map((row) => Number(row.value) || 0);
  const busiest = (book.growth || []).reduce((best, row) => (row.value > (best?.value || 0) ? row : best), null);
  const thisWeek = week.this || {};
  const lastWeek = week.last || {};
  const linked = Math.max(0, (book.notes || 0) - (book.orphans || 0));
  const plural = (n, one, many = `${one}s`) => (n === 1 ? one : many);
  return [
    {
      icon: "notebook",
      value: book.notes,
      label: plural(book.notes, "note"),
      line: busiest ? `Most in ${replyMonthName(busiest.label)}` : "None in the last year",
      chart: replySpark(growth, `Notes made per month, the last ${growth.length} months: ${growth.join(", ")}`),
    },
    {
      icon: "text-aa",
      value: book.words,
      label: plural(book.words, "word"),
      line: `${(thisWeek.words || 0).toLocaleString()} this week, ${(lastWeek.words || 0).toLocaleString()} last`,
      chart: replyCompare(thisWeek.words || 0, lastWeek.words || 0, `Words this week ${thisWeek.words || 0}, last week ${lastWeek.words || 0}`),
    },
    {
      icon: "hash",
      value: book.tags,
      label: plural(book.tags, "tag"),
      line: `In ${(book.categories || 0).toLocaleString()} ${plural(book.categories || 0, "category", "categories")}`,
    },
    {
      icon: "graph",
      value: book.links,
      label: plural(book.links, "link"),
      line: `${linked.toLocaleString()} of ${(book.notes || 0).toLocaleString()} notes joined`,
      chart: replyMeter(book.notes ? linked / book.notes : 0, `${linked} of ${book.notes || 0} notes have a link`),
    },
    {
      icon: "bell",
      value: rem.open,
      label: `${plural(rem.open || 0, "reminder")} open`,
      line: `${(rem.done || 0).toLocaleString()} done${rem.late ? `, ${rem.late} late` : ""}`,
      chart: replyMeter(rem.made ? rem.done / rem.made : 0, `${rem.done || 0} of ${rem.made || 0} reminders done`),
    },
    {
      icon: "calendar-check",
      value: thisWeek.notes,
      label: `${plural(thisWeek.notes || 0, "note")} this week`,
      line: `${(lastWeek.notes || 0).toLocaleString()} last week`,
      chart: replyCompare(thisWeek.notes || 0, lastWeek.notes || 0, `Notes this week ${thisWeek.notes || 0}, last week ${lastWeek.notes || 0}`),
    },
  ];
}

function replyStatsPanel() {
  const { panel, head } = replyPanelShell("reply-stats", "Your notebook", "ph:chart-bar");
  const open = document.createElement("button");
  open.type = "button";
  open.className = "ghost small reply-panel-open";
  setLabel(open, "ph:arrow-square-out Open Statistics");
  open.title = "The Statistics page: notebook, reminders and usage, counted";
  open.addEventListener("click", () => openStatistics());
  head.appendChild(open);
  const grid = document.createElement("div");
  grid.className = "reply-stat-grid";
  grid.setAttribute("aria-busy", "true");
  panel.appendChild(grid);
  apiJson("/statistics")
    .then((page) => {
      grid.replaceChildren(...replyStatCards(page).map(replyStatCard));
      grid.removeAttribute("aria-busy");
      replyFillMeters(panel);
    })
    .catch(() => {
      const line = document.createElement("p");
      line.className = "muted reply-panel-empty";
      line.textContent = "The figures could not be read. Open Statistics to try again.";
      grid.replaceChildren(line);
      grid.removeAttribute("aria-busy");
    });
  return panel;
}

// --- the calculator ------------------------------------------------------------

//: **The calculator** (INBOX 1300 C06: "an interactive calculator popup that
//: is accessible and also link it to the /calc command as well as other unit
//: conversions"). A sheet (`openSheet`, the app's one), with two modes in a
//: `.seg`: Work out (a sum, a percentage or a conversion typed or keyed, the
//: same reader as /calc and the chat's `calculate` tool: `GET
//: /utilities/work`) and Convert (a number and two units of one kind, from
//: `GET /utilities/units`). The keypad is one Tab stop and the arrows walk
//: it; the result is a live region; the last results come back with a press.
//: Reached from a sum or a conversion's answer (its panel), /calc with
//: nothing after it, and the palette's Calculator row.
const replyCalc = { history: [], units: null };

const REPLY_CALC_KEYS = [
  ["C", "clear"], ["(", "("], [")", ")"], ["ph:divide", "/"],
  ["7", "7"], ["8", "8"], ["9", "9"], ["ph:x", "*"],
  ["4", "4"], ["5", "5"], ["6", "6"], ["ph:minus", "-"],
  ["1", "1"], ["2", "2"], ["3", "3"], ["ph:plus", "+"],
  ["0", "0"], [".", "."], ["ph:percent", "%"], ["ph:equals", "equals"],
];

//: The pair a kind opens on: the conversion people most often want, not the
//: first two names of an alphabetical list (nanometres to micrometres).
const REPLY_CALC_PAIRS = {
  length: ["kilometres", "miles"], mass: ["kilograms", "pounds"], volume: ["litres", "US gallons"],
  temperature: ["°C", "°F"], speed: ["kilometres an hour", "miles an hour"], area: ["square metres", "square feet"],
  time: ["hours", "minutes"], data: ["gigabytes", "megabytes"], currency: ["USD", "EUR"],
};

const REPLY_CALC_NAMES = { clear: "Clear", "/": "Divide", "*": "Times", "-": "Minus", "+": "Plus", "%": "Percent", equals: "Work it out", ".": "Point" };

function replyCalcPanel(event) {
  const { panel, head } = replyPanelShell("reply-calc", "Calculator", "ph:calculator");
  const open = document.createElement("button");
  open.type = "button";
  open.className = "ghost small reply-panel-open";
  setLabel(open, "ph:arrow-square-out Open the calculator");
  open.title = "Work it out again, change it, or convert units";
  open.addEventListener("click", () => openCalculator(event.input || ""));
  head.appendChild(open);
  // "/calc" with nothing after it asks for the calculator itself.
  if (!event.input) requestAnimationFrame(() => openCalculator());
  return panel;
}

async function replyCalcWork(text) {
  const asked = String(text || "").trim();
  if (!asked) return null;
  return apiJson(`/utilities/work?q=${encodeURIComponent(asked)}`);
}

function openCalculator(input = "", mode = "work") {
  const existing = document.querySelector('[data-sheet="calculator"]');
  if (existing) {
    const box = existing.querySelector(".calc-input");
    if (box && input) {
      box.value = input;
      box.dispatchEvent(new Event("input"));
    }
    box?.focus();
    if (mode === "convert") existing.querySelector('.calc-modes [role="tab"]:last-child')?.click();
    return;
  }
  openSheet({
    label: "Calculator",
    sub: "Sums, percentages and conversions, worked out by the app with no model.",
    name: "calculator",
    build: (card) => replyCalcBuild(card, input, mode),
  });
}

function replyCalcBuild(card, input, mode = "work") {
  //: A tab strip, not a pill (DESIGN.md, "A popup that chooses a kind").
  const modes = document.createElement("div");
  modes.className = "tabs-line popup-kinds calc-modes";
  modes.setAttribute("role", "tablist");
  modes.setAttribute("aria-label", "Calculator mode");
  const work = replyCalcWorkPane(input);
  const convert = replyCalcConvertPane();
  convert.classList.add("hidden");
  const panes = { work, convert };
  for (const pane of [work, convert]) pane.setAttribute("role", "tabpanel");
  for (const [key, words] of [["work", "Work out"], ["convert", "Convert units"]]) {
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("role", "tab");
    button.textContent = words;
    button.setAttribute("aria-selected", String(key === "work"));
    button.classList.toggle("active", key === "work");
    button.tabIndex = key === "work" ? 0 : -1;
    button.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const other = [...modes.children].find((tab) => tab !== button);
      other.click();
      other.focus();
    });
    button.addEventListener("click", () => {
      for (const other of modes.children) {
        other.setAttribute("aria-selected", String(other === button));
        other.classList.toggle("active", other === button);
        other.tabIndex = other === button ? 0 : -1;
      }
      for (const [name, pane] of Object.entries(panes)) pane.classList.toggle("hidden", name !== key);
      (key === "work" ? work.querySelector(".calc-input") : convert.querySelector(".calc-amount"))?.focus();
    });
    modes.appendChild(button);
  }
  card.append(modes, work, convert);
  if (mode === "convert") modes.lastElementChild.click();
  else requestAnimationFrame(() => work.querySelector(".calc-input")?.focus());
}

function replyCalcResult() {
  const out = document.createElement("output");
  out.className = "calc-result";
  out.setAttribute("aria-live", "polite");
  const figure = document.createElement("strong");
  figure.className = "calc-figure";
  const read = document.createElement("span");
  read.className = "muted calc-read";
  out.append(figure, read);
  return out;
}

//: "12*(3+4) is about 84." to "84". String steps, not a regex: CodeQL
//: read `^.*? is ` on an answer as polynomial backtracking.
function calcFigure(answer, dropRates) {
  let a = String(answer || "");
  const i = a.indexOf(" is ");
  if (i >= 0) a = a.slice(i + 4);
  if (a.startsWith("about ")) a = a.slice(6);
  if (!a.endsWith(".")) return a;
  const j = dropRates ? a.indexOf(" at the rates from ") : -1;
  return j >= 0 ? a.slice(0, j) : a.slice(0, -1);
}

function replyCalcShow(out, got, { final = false } = {}) {
  const figure = out.querySelector(".calc-figure");
  const read = out.querySelector(".calc-read");
  out.classList.toggle("is-error", Boolean(got?.error));
  out.classList.toggle("is-preview", !final);
  if (!got) {
    figure.textContent = "";
    read.textContent = "";
    return;
  }
  //: The figure on its own ("84", not "12*(3+4) is 84."): the sum is in the
  //: box, and how the app read it is the line under.
  figure.textContent = got.error ? "" : calcFigure(got.answer, true);
  read.textContent = got.error ? got.error : got.read_as ? `Read as ${got.read_as}` : "";
}

function replyCalcWorkPane(input) {
  const pane = document.createElement("div");
  pane.className = "calc-pane";
  const box = document.createElement("input");
  box.type = "text";
  box.className = "calc-input";
  box.setAttribute("aria-label", "A sum, a percentage or a conversion");
  box.placeholder = "12 * (3 + 4), 15% of 80, 5 km to miles";
  box.autocomplete = "off";
  box.spellcheck = false;
  box.value = input;
  const out = replyCalcResult();
  const history = document.createElement("ul");
  history.className = "calc-history";
  history.setAttribute("aria-label", "Earlier results");
  let timer = 0;
  let asked = 0;
  const run = async (final) => {
    const mine = ++asked;
    try {
      const got = await replyCalcWork(box.value);
      if (mine !== asked) return;
      replyCalcShow(out, got, { final });
      if (final && got?.answer) {
        replyCalc.history = [{ input: box.value.trim(), answer: got.answer }, ...replyCalc.history.filter((h) => h.input !== box.value.trim())].slice(0, 5);
        replyCalcHistory(history, box);
      }
    } catch (error) {
      if (mine === asked) replyCalcShow(out, { error: error.message }, { final });
    }
  };
  box.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => run(false), 250);
  });
  box.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    clearTimeout(timer);
    run(true);
  });
  const keys = replyCalcKeypad(box, () => {
    clearTimeout(timer);
    run(true);
  });
  //: Copy sits beside the figure it copies, outside the live region.
  const foot = document.createElement("div");
  foot.className = "calc-result-row";
  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "ghost small icon-only";
  setLabel(copy, "ph:copy");
  copy.setAttribute("aria-label", "Copy result");
  copy.title = "Copy result";
  copy.addEventListener("click", () => {
    const text = out.querySelector(".calc-figure").textContent;
    if (!text) return;
    navigator.clipboard?.writeText(text).then(() => toast("Result copied."), () => toast("Couldn't copy the result.", "info"));
  });
  foot.append(out, copy);
  pane.append(box, foot, keys, history);
  replyCalcHistory(history, box);
  if (input) run(true);
  return pane;
}

//: The keypad: one Tab stop (a roving `tabindex`), the arrows walk its four
//: columns, Home and End its row; each key says what it does to a screen
//: reader ("Times", not the icon's name).
function replyCalcKeypad(box, equals) {
  const pad = document.createElement("div");
  pad.className = "calc-keys";
  pad.setAttribute("role", "group");
  pad.setAttribute("aria-label", "Keypad");
  const keys = REPLY_CALC_KEYS.map(([face, act], i) => {
    const key = document.createElement("button");
    key.type = "button";
    // = is the pad's one primary action (the app's filled button); the rest are ghosts.
    key.className = act === "equals" ? "calc-key" : `ghost calc-key${/^[0-9.]$/.test(act) ? "" : " is-op"}`;
    setLabel(key, face);
    key.tabIndex = i === 0 ? 0 : -1;
    if (REPLY_CALC_NAMES[act]) key.setAttribute("aria-label", REPLY_CALC_NAMES[act]);
    key.addEventListener("click", () => {
      if (act === "equals") return equals();
      if (act === "clear") box.value = "";
      else {
        const start = box.selectionStart ?? box.value.length;
        const end = box.selectionEnd ?? box.value.length;
        box.setRangeText(act, start, end, "end");
      }
      box.dispatchEvent(new Event("input"));
    });
    pad.appendChild(key);
    return key;
  });
  pad.addEventListener("keydown", (event) => {
    const at = keys.indexOf(document.activeElement);
    if (at < 0) return;
    const step = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: 4, ArrowUp: -4 }[event.key];
    let next = step === undefined ? -1 : at + step;
    if (event.key === "Home") next = at - (at % 4);
    if (event.key === "End") next = at - (at % 4) + 3;
    if (next < 0 || next >= keys.length) return;
    event.preventDefault();
    keys[at].tabIndex = -1;
    keys[next].tabIndex = 0;
    keys[next].focus();
  });
  return pad;
}

function replyCalcHistory(list, box) {
  list.replaceChildren();
  list.classList.toggle("hidden", !replyCalc.history.length);
  for (const row of replyCalc.history) {
    const item = document.createElement("li");
    const again = document.createElement("button");
    again.type = "button";
    again.className = "ghost small calc-again";
    again.textContent = `${row.input} = ${calcFigure(row.answer, false)}`;
    again.title = "Put this back in the box";
    again.addEventListener("click", () => {
      box.value = row.input;
      box.dispatchEvent(new Event("input"));
      box.focus();
    });
    item.appendChild(again);
    list.appendChild(item);
  }
}

function replyCalcConvertPane() {
  const pane = document.createElement("div");
  pane.className = "calc-pane calc-convert";
  const amount = document.createElement("input");
  amount.type = "number";
  amount.step = "any";
  amount.value = "1";
  amount.className = "calc-amount";
  amount.setAttribute("aria-label", "Amount");
  const kind = document.createElement("select");
  kind.className = "small-select calc-kind";
  kind.setAttribute("aria-label", "What to convert");
  const from = document.createElement("select");
  from.className = "small-select calc-from";
  from.setAttribute("aria-label", "From");
  const to = document.createElement("select");
  to.className = "small-select calc-to";
  to.setAttribute("aria-label", "To");
  const swap = document.createElement("button");
  swap.type = "button";
  swap.className = "ghost small icon-only calc-swap";
  setLabel(swap, "ph:arrows-left-right");
  swap.setAttribute("aria-label", "Swap the two units");
  swap.title = "Swap";
  const out = replyCalcResult();
  const note = document.createElement("p");
  note.className = "muted calc-note";
  const fill = (select, names, pick) => {
    select.replaceChildren(...names.map((name) => new Option(name, name)));
    select.value = names.includes(pick) ? pick : names[0];
  };
  const run = async () => {
    if (!from.value || !to.value || amount.value === "") return replyCalcShow(out, null);
    try {
      replyCalcShow(out, await replyCalcWork(`${amount.value} ${from.value} to ${to.value}`), { final: true });
    } catch (error) {
      replyCalcShow(out, { error: error.message }, { final: true });
    }
  };
  const pickKind = () => {
    const names = replyCalc.units?.[kind.value] || [];
    const [one, two] = REPLY_CALC_PAIRS[kind.value] || [];
    fill(from, names, one);
    fill(to, names, two || names[1]);
    const dated = new Date(`${replyCalc.units?.rates_date}T12:00`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
    note.textContent = kind.value === "currency" ? `Rates from ${dated}, set by hand: not today's rate.` : "";
    run();
  };
  kind.addEventListener("change", pickKind);
  for (const box of [amount, from, to]) box.addEventListener("input", run);
  swap.addEventListener("click", () => {
    [from.value, to.value] = [to.value, from.value];
    run();
  });
  const row = document.createElement("div");
  row.className = "calc-convert-row";
  row.append(amount, from, swap, to);
  pane.append(kind, row, out, note);
  (replyCalc.units ? Promise.resolve(replyCalc.units) : apiJson("/utilities/units"))
    .then((units) => {
      replyCalc.units = units;
      const kinds = Object.keys(units).filter((key) => Array.isArray(units[key]));
      kind.replaceChildren(...kinds.map((key) => new Option(key[0].toUpperCase() + key.slice(1), key)));
      kind.value = kinds.includes("length") ? "length" : kinds[0];
      pickKind();
    })
    .catch((error) => replyCalcShow(out, { error: error.message }, { final: true }));
  return pane;
}

// --- finishing a reply -------------------------------------------------------------

//: What every answer surface (Chat, Ask, the popup agent, the Guide) does to
//: a reply once its words are final, whoever wrote them: `finishReply`
//: (capture-ask.js) hands it the answer's element, or a turn's several.
function replyFinish(answers, opts = {}) {
  const list = (answers instanceof Element ? [answers] : [...(answers || [])]).filter((el) => el?.isConnected);
  if (!list.length) return;
  for (const answer of list) replyFoldLong(answer);
  replyNotePreviews(list);
  if (opts.head && list.some((answer) => answer.textContent.trim())) replyByline(opts.head, opts);
  if (opts.composed) replyReveal(list);
  if (opts.unsupported) renderToolsUnsupportedNotice(opts.bubble, opts.unsupported);
  if (opts.match_info) replyRecordReasons(opts.match_info);
}

//: **Why each Matching records card is there, in words** (INBOX 1310, the
//: owner: "it has no frame of reference for how related each shown matching
//: record is or why it was shown"): the server's `match_info[id].why`
//: ("Matches hobbies by meaning, and shares #gaming with ..."), on the Notes
//: search's "why this result" line, wrapping inside the card. Drawn here when
//: the answer is final, not in capture-ask.js, for the boot budget.
function replyRecordReasons(info) {
  for (const row of document.querySelectorAll("#raw-results > li[data-id]")) {
    const why = info[row.dataset.id]?.why;
    if (!why || row.querySelector(":scope > .entry-why")) continue;
    const line = document.createElement("div");
    line.className = "entry-why";
    line.appendChild(chip(`ph:sparkle ${why}`, "result-reason-chip result-reason-why"));
    row.appendChild(line);
  }
}

//: INBOX 272 part 1, "every failure names its way out": the same
//: `.notice.notice-warn` recipe as `renderAnswerSupport` above, plus the one
//: control that fixes it, right under the turn that hit it rather than a
//: sentence pointing at a different screen. Only the Chat tab's Agent mode
//: can produce this event (the Ask box always sends `useTools: false`), so
//: this has one caller (Chat, through `replyFinish`; moved here from
//: capture-ask.js for the boot budget).
function renderToolsUnsupportedNotice(container, event) {
  if (!container || !event) return;
  const line = document.createElement("p");
  line.className = "notice notice-warn tools-unsupported-notice";
  line.setAttribute("role", "note");
  setLabel(line, `ph:warning ${event.message || "This model can't call tools."}`);
  const row = document.createElement("div");
  row.className = "row tools-unsupported-fix-row";
  row.appendChild(
    smallButton("ph:gear Change the model", "Open Settings, Models", () => {
      openSettingsModal("models", "chat-model-select");
    })
  );
  //: Above the turn's facts line, where it was drawn before it moved here.
  container.insertBefore(row, container.querySelector(":scope > .msg-meta"));
  row.before(line);
}

// --- who wrote it ----------------------------------------------------------------------

//: **Who wrote a reply, as a badge** (INBOX 1300 C14, the owner: "Should
//: 'composer' and the model should be a badge or smnth similar"). The head
//: keeps the assistant's name; beside it one `chip item-label` (DESIGN.md,
//: "A word saying where an item came from") says what wrote the words: From
//: your notes (composed, no model), the model's name, or Composer (the app
//: answered itself: a greeting, a count, a time). Its title says it in full.
//: The same chip on Chat, the popup agent and the Guide; Ask's
//: `#answered-by` is the same chip in its own head (`.answer-model`, the
//: shrinking one: a long model id ends in an ellipsis).
function replyBylineFacts({ composed, model, engine, help }) {
  if (composed) {
    return help
      ? ["From the help", "No model answered: this is the app's own help for what you asked", "help"]
      : ["From your notes", "Answered from your notes with no model: every sentence comes from a note", "notes"];
  }
  if (model) return [model, `Answered by ${model}`];
  if (engine) return ["Composer", "The app answered this itself, with no model", "engine"];
  return null;
}

//: **The badge explains itself** (INBOX 1344, the owner: "a hover/click
//: tooltip popup with a disclaimer and description for the composer message
//: badge to inform the user how it isnt an ai"). A badge no model wrote is a
//: button on the `data-help-for` recipe; its `.help-body` is built per badge
//: because `wireHelpPopover` takes one trigger per panel.
const REPLY_BY_WHAT = {
  notes: "This answer was written without an AI model. The app picked sentences from your own notes and joined them.",
  help: "This answer was written without an AI model. It is the app's own help text for what you asked.",
  engine: "This answer was worked out by the app itself, without an AI model: a greeting, a count, a time, a sum.",
};

function replyByHelpPanel(kind) {
  const panel = document.createElement("div");
  panel.className = "help-body hidden";
  panel.id = `reply-by-help-${(replyByHelpPanel.seq = (replyByHelpPanel.seq || 0) + 1)}`;
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "About this badge");
  for (const line of [
    REPLY_BY_WHAT[kind] || REPLY_BY_WHAT.notes,
    "Every sentence in a notes answer is quoted from a note and cited. The only words the app adds are the joining ones and the counts and dates it measured. It does not guess, so it can miss what a model would work out.",
    "A model's answer shows the model's name here instead, and its sentences are new wording.",
    "To use a model, turn on the switch labelled AI in Ask when a model is running, or connect one in Settings, Models.",
  ]) {
    const p = document.createElement("p");
    p.textContent = line;
    panel.appendChild(p);
  }
  return panel;
}

//: Hover opens it where the device has hover and the pointer rests (a
//: crossing mouse is not a request); a click right after is not a close.
function replyByHover(badge, panel) {
  if (!window.matchMedia("(hover: hover)").matches) return;
  let timer = 0;
  let openedAt = 0;
  const open = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (badge.getAttribute("aria-expanded") === "true") return;
      openedAt = Date.now();
      badge.click();
    }, 350);
  };
  const leave = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (badge.getAttribute("aria-expanded") === "true" && openedAt) badge.click();
      openedAt = 0;
    }, 250);
  };
  badge.addEventListener("click", (event) => {
    if (openedAt && event.isTrusted && Date.now() - openedAt < 600) {
      event.stopImmediatePropagation();
      event.preventDefault();
    }
    if (event.isTrusted) openedAt = 0;
  }, true);
  badge.addEventListener("mouseenter", open);
  badge.addEventListener("mouseleave", leave);
  panel.addEventListener("mouseenter", () => clearTimeout(timer));
  panel.addEventListener("mouseleave", leave);
}

function replyByline(head, facts) {
  const said = head && replyBylineFacts(facts);
  if (!said) return;
  head.querySelector(":scope > .reply-by")?.remove();
  const kind = said[2];
  const chip = document.createElement(kind ? "button" : "span");
  chip.className = "chip item-label answer-model reply-by";
  chipWords(chip, said[0]);
  chip.title = said[1];
  if (kind) {
    const panel = replyByHelpPanel(kind);
    chip.type = "button";
    chip.classList.add("chip-interactive");
    chip.setAttribute("data-help-for", panel.id);
    chip.setAttribute("aria-controls", panel.id);
    chip.setAttribute("aria-expanded", "false");
    chip.setAttribute("aria-label", `${said[0]}, written without an AI model. About this badge`);
    head.appendChild(chip);
    //: Inside the head, not after it: a hidden panel between the head and the
    //: steps broke `.msg-role:has(+ .agent-steps)`, so the bubble grew 2.4px
    //: each time the open panel moved out to <body> (the owner, 2026-10-27).
    head.appendChild(panel);
    wireHelpPopover(chip, panel);
    replyByHover(chip, panel);
    return;
  }
  head.appendChild(chip);
}

// --- a composed reply arrives ----------------------------------------------------

//: **One reveal for a reply no model wrote** (INBOX 1300 C28; the owner,
//: 2026-10-10: "Composer responses just appear, I think there should be an
//: animation"). A composed reply lands in one piece, so its blocks rise in
//: turn, `REPLY_REVEAL_STEP` apart, as a streamed one grows: the same on
//: Chat, Ask, the popup agent and the Guide. Opacity and a short lift only
//: (DESIGN.md, "An animation of anything"). Reduce motion makes it a quick
//: fade with no lift and no stagger; Interface animations off, or Settings,
//: Appearance, Reveal replies off, and it simply appears.
const REPLY_REVEAL_STEP = 60;

function replyRevealWanted() {
  const root = document.documentElement;
  return root.dataset.uiMotion !== "off" && prefs.get("reply-motion", "on") !== "off";
}

function replyReveal(answers) {
  if (!replyRevealWanted()) return;
  const still = reducedMotionWanted();
  let step = 0;
  for (const answer of answers) {
    for (const block of answer.children) {
      block.animate(still ? [{ opacity: 0 }, {}] : [{ opacity: 0, translate: "0 4px" }, {}], {
        id: "reply-reveal",
        duration: still ? 120 : 200,
        delay: still ? 0 : Math.min(step++, 8) * REPLY_REVEAL_STEP,
        easing: "ease-out",
        fill: "backwards",
      });
    }
  }
}

// --- a long block, folded ------------------------------------------------------------

//: **A wall of text folds** (INBOX 1300 C08, the owner: "if it outputs a mass
//: block of text like from the ocr of one of my note's images, maybe it could
//: be in a collapsible subtle panel or smth or abrieviated/summarised"). A
//: paragraph, quote or code block of a reply longer than `REPLY_FOLD_CHARS`
//: becomes the Thinking fold's disclosure (`details.agent-step.long-fold`),
//: shut, whose summary is its gist: the first sentence cut to a line, and how
//: long the whole is. Open, it reads in an inset panel capped and scrolling,
//: as the web reader does. The words are all still there, for copy and for
//: find; nothing is rewritten.
const REPLY_FOLD_CHARS = 600;

function replyGist(text) {
  const first = text.split(/(?<=[.!?])\s+/)[0] || text;
  return clipText(first.replace(/\s+/g, " "), 90);
}

function replyFoldLong(answer) {
  for (const block of [...answer.children]) {
    if (!block.matches("p, pre, blockquote")) continue;
    const text = block.textContent.trim();
    if (text.length < REPLY_FOLD_CHARS) continue;
    const words = text.split(/\s+/).length;
    const fold = document.createElement("details");
    fold.className = "agent-step long-fold";
    const summary = document.createElement("summary");
    summary.className = "fold-summary";
    const gist = document.createElement("span");
    gist.className = "long-fold-gist";
    gist.textContent = replyGist(text);
    const size = document.createElement("span");
    size.className = "muted long-fold-size";
    size.textContent = `${words.toLocaleString()} words`;
    setLabel(summary, "ph:text-align-left");
    summary.append(gist, size);
    summary.title = "Show the whole text";
    block.replaceWith(fold);
    fold.append(summary, block);
    block.classList.add("long-fold-body");
  }
}

// --- the notes a reply gives -----------------------------------------------------

//: **A note a reply names is previewed where it is named** (INBOX 1300 C07,
//: the owner: "if it is going to give me a note, can it at least preview it
//: for me as well??"). Every link to a note (`#/notes/N`, how tool_say and the
//: slash commands write one) shows the citation peek on hover or focus, the
//: one a source number shows; a reply that gives one to three notes also
//: carries them as cards under its words, the document embed's card
//: (`.embed-card`), so a phone, with no hover, sees them too. More than three
//: is a list (/recent, /tags), and the peek is enough there.
const REPLY_NOTE_CARDS = 3;

function replyNoteId(link) {
  const id = Number(/^#\/notes\/(\d+)$/.exec(link.getAttribute("href") || "")?.[1]);
  return Number.isInteger(id) && id > 0 ? id : 0;
}

function replyNoteEntry(id) {
  return allEntries.find((entry) => entry.id === id) || null;
}

function replyNotePreviews(answers) {
  const ids = [];
  const names = new Map();
  for (const answer of answers) {
    for (const link of answer.querySelectorAll('a[href^="#/notes/"]')) {
      const id = replyNoteId(link);
      if (!id || link.closest(".reply-panel")) continue;
      if (!ids.includes(id)) ids.push(id);
      if (!names.has(id)) names.set(id, link.textContent.trim());
      replyPeekLink(link, id);
    }
  }
  const last = answers[answers.length - 1];
  if (!ids.length || ids.length > REPLY_NOTE_CARDS || last.querySelector(":scope > .reply-notes")) return;
  const { panel } = replyPanelShell("reply-notes", ids.length === 1 ? "The note" : `${ids.length} notes`, "ph:note");
  for (const id of ids) panel.appendChild(replyNoteCard(id, names.get(id)));
  last.appendChild(panel);
}

function replyPeekLink(link, id) {
  if (link.dataset.peek) return;
  link.dataset.peek = "note";
  link.setAttribute("aria-haspopup", "dialog");
  //: The peek of a source with no number: named for its note, its number
  //: slot left empty (and so not drawn, reply-kit-lazy.css).
  const open = () => {
    openCitationPeek(link, { noteId: id, number: "", entry: replyNoteEntry(id), label: link.textContent }, { pinned: false });
    if (citationPeekState.link === link) citationPeekState.panel?.setAttribute("aria-label", `Preview of ${link.textContent.trim() || "the note"}`);
  };
  //: `scheduleCitationPeek`'s wait, through its own timer so its close cancels it.
  link.addEventListener("mouseenter", () => {
    clearTimeout(citationPeekState.closeTimer);
    clearTimeout(citationPeekState.openTimer);
    if (citationPeekState.link !== link) citationPeekState.openTimer = setTimeout(open, citationPeekState.panel ? 0 : 140);
  });
  link.addEventListener("mouseleave", () => scheduleCitationPeekClose());
  link.addEventListener("focus", () => {
    if (!citationPeekState.restoring) open();
  });
  link.addEventListener("blur", (event) => {
    if (!citationPeekState.panel?.contains(event.relatedTarget)) scheduleCitationPeekClose();
  });
}

//: The note as the document embed's card: a tile, its title, one facts line
//: (where it is filed, when, how long) and its first words; the whole card
//: is the one button that opens it.
function replyNoteCard(id, name) {
  const entry = replyNoteEntry(id);
  const content = entry?.content || "";
  const card = document.createElement("button");
  card.type = "button";
  card.className = "embed-card reply-note-card";
  card.title = "Open this note";
  const tile = document.createElement("span");
  tile.className = "embed-card-tile";
  tile.setAttribute("aria-hidden", "true");
  const glyph = document.createElement("i");
  glyph.className = "ph ph-note";
  tile.appendChild(glyph);
  const text = document.createElement("span");
  text.className = "embed-card-text";
  const title = document.createElement("span");
  title.className = "embed-card-title";
  //: The title is the note's first line, the preview what follows it.
  const [head, ...rest] = content.trim().split("\n");
  title.textContent = content ? noteLabel({ content: head }, 60) : name || "A note";
  const facts = document.createElement("span");
  facts.className = "embed-card-meta";
  const words = content ? plainText(content).split(/\s+/).filter(Boolean).length : 0;
  facts.textContent = [
    "Note",
    entry?.category,
    entry?.created_at ? relativeTime(entry.created_at) : "",
    words ? `${words.toLocaleString()} ${words === 1 ? "word" : "words"}` : "",
  ].filter(Boolean).join(" · ");
  text.append(title, facts);
  //: A one-line note cut short in the title is read in full under it.
  const opening = (rest.length ? plainText(rest.join("\n")) : title.textContent.endsWith("…") ? plainText(content) : "").trim();
  if (opening) {
    const preview = document.createElement("span");
    preview.className = "embed-card-preview";
    preview.textContent = clipText(opening, 180);
    text.appendChild(preview);
  }
  const go = document.createElement("i");
  go.className = "ph ph-arrow-square-out embed-card-go";
  go.setAttribute("aria-hidden", "true");
  card.append(tile, text, go);
  card.addEventListener("click", () => openNoteAtPassage(id, ""));
  return card;
}

//: **The chat's queue** (INBOX 1321, `sendChatMessage`): each message sent
//: while an answer streams, above the box, with Edit (back into the box,
//: out of the queue) and Remove. They go in order as each answer ends.
function chatQueuePaint() {
  const input = $("chat-input");
  const row = input.parentElement;
  let list = document.querySelector(".chat-queue");
  if (!chatQueue.length) {
    list?.remove();
    return;
  }
  if (!list) {
    list = document.createElement("ul");
    list.className = "chat-queue";
    list.setAttribute("aria-label", "Queued messages");
    row.parentElement.insertBefore(list, row);
  }
  list.replaceChildren(
    ...chatQueue.map((text, i) => {
      const li = document.createElement("li");
      li.className = "chat-queue-item";
      const words = document.createElement("span");
      words.className = "chat-queue-text";
      words.textContent = text;
      words.title = text;
      const edit = smallButton("ph:pencil-simple", "Edit: back into the box", () => {
        chatQueue.splice(i, 1);
        input.value = input.value.trim() ? `${text}\n${input.value}` : text;
        input.dispatchEvent(new Event("input"));
        input.focus();
        chatQueuePaint();
      });
      const remove = smallButton("ph:x", "Remove from the queue", () => {
        chatQueue.splice(i, 1);
        chatQueuePaint();
        input.focus();
      });
      for (const b of [edit, remove]) b.classList.add("icon-only");
      li.append(words, edit, remove);
      return li;
    })
  );
}
