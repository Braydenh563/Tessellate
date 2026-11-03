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
//: "timeline": the strip under /today, /recent and a day with nothing in it
//: (INBOX 1333): notes over the span, the Statistics card's spark line.
const REPLY_PANELS = {
  statistics: () => replyStatsPanel(),
  timeline: (event) => replyTimelinePanel(event),
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
  const icons = { document: "ph:file-text", chat: "ph:chat-circle", reminder: "ph:bell", note: "ph:note" };
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
      } else if (item.kind === "note") flashEntry(item.id);
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

//: The strip's points arrive counted (`slash_more.timeline_panel`); the spark
//: line is the Statistics card's, its two ends named under it.
function replyTimelinePanel(event) {
  const { panel } = replyPanelShell("reply-timeline", event.title || "Notes over time", "ph:chart-line");
  const points = (event.points || []).map((n) => Number(n) || 0);
  panel.appendChild(replySpark(points, `${event.title}, ${event.from} to ${event.to}: ${points.join(", ")}`));
  const ends = document.createElement("div");
  ends.className = "muted reply-timeline-ends";
  for (const text of [event.from, event.to]) {
    const end = document.createElement("span");
    end.textContent = text || "";
    ends.appendChild(end);
  }
  panel.appendChild(ends);
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
//: `tabs`: the dialog's, in order: sums, conversions, and the equation editor, all named for what they hold (INBOX 1530 g L4: a verb, a verb and a noun read as three tools). `opened` numbers the dialogs, for ids that never collide with one still leaving.
const replyCalc = { units: null, opened: 0, tabs: [["work", "Sum"], ["convert", "Units"], ["equation", "Equation"]],
  //: **The history, one list per tab** (INBOX 1541), kept in this browser's prefs store as `{work, convert, equation}`; `calcTex.log` holds its rules.
  load: (tab) => calcTex.log.clean(prefs.json("calc-history", {})[tab]),
  save: (tab, list) => prefs.setJSON("calc-history", { ...prefs.json("calc-history", {}), [tab]: list }),
};

//: The head '?' (INBOX 1530 g M6): the dialog is worked out by the app with no model; one line per tab, then where Insert writes.
const REPLY_CALC_HELP = [
  "Worked out by the app, with no model.",
  "Sum: type or key a sum, a percentage or a conversion (12 * (3 + 4), 15% of 80, 5 km to miles). A preview shows as you type; Enter or = keeps it.",
  "Units: pick a kind, an amount and two units. Currency rates are set by hand and dated, not today's rate.",
  "Equation: click a dotted box to fill it. / makes a fraction, ^ and _ a power or a subscript, and LaTeX such as \\frac or \\alpha turns into the symbol as you type it. Pick a structure or a symbol from the palette; a selection goes into the first box. The row of groups jumps to one; Pin makes a tile a favourite, and Recent shows the last ones used. Inline sits in a sentence, Display on its own line. Click a drawn equation in a note, or open this with the cursor inside one, to edit it.",
  "History: each tab keeps its last twenty answers on this device. Open History under the keypad, press a row to put it back in the fields, or use Copy, Edit (the next keep replaces that row) and Remove; Clear empties it, and Undo brings it back. Every answer has a Copy button beside it.",
  "Insert writes into the text box you opened this from (Alt+= in a box, or Ctrl+K over one). With none open, Copy is the way out. Ctrl+Enter inserts an equation.",
];

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

//: **One maths tool** (INBOX 1527): `mode` is the tab it opens on, and `target`
//: the box it was opened from (Alt+= and the palette over a text box), which a
//: result and an equation are written into; with none, the Insert buttons are
//: not drawn and the editor's Insert is Copy.
function openCalculator(input = "", mode = "work", { target = null } = {}) {
  const existing = document.querySelector('[data-sheet="calculator"]');
  //: A new box to write into needs a new dialog: the open one makes way.
  if (existing && target) existing.querySelector(".sheet-close")?.click();
  else if (existing) {
    const box = existing.querySelector(".calc-input");
    if (box && input) {
      box.value = input;
      box.dispatchEvent(new Event("input"));
    }
    const tab = existing.querySelectorAll('.calc-modes [role="tab"]')[replyCalc.tabs.findIndex(([key]) => key === mode)];
    if (tab && mode !== "work") tab.click();
    else box?.focus();
    return;
  }
  openSheet({
    label: "Calculator and equations",
    name: "calculator",
    //: A half-written equation survives a stray press outside (the popover it replaced ignored one, maths1527).
    hasWork: () => [...document.querySelectorAll('[data-sheet="calculator"] math-field')].some((f) => f.value?.trim()),
    build: (card, close) => replyCalcBuild(card, input, mode, { target, close }),
  });
}

//: A dashboard widget's body (INBOX 1558): the Sum and Units tabs drawn into it through the dialog's own build, with no Insert and no focus taken.
openCalculator.inline = (host, mode = "work") => replyCalcBuild(host, "", mode, { inline: true });

function replyCalcBuild(card, input, mode = "work", { target = null, close = () => {}, inline = false } = {}) {
  //: One height for all three tabs, the strip and the action row pinned and the panes between them scrolling (INBOX 1530 g M2: on a bottom-anchored sheet the strip moved 188 px between tabs and 4 to 40 px on a result).
  card.classList.add("calc-card");
  if (inline) card.classList.add("calc-inline");
  //: An inline calculator has no Equation tab (the field needs its own bundle and a box to write into).
  const kinds = inline ? replyCalc.tabs.filter(([key]) => key !== "equation") : replyCalc.tabs;
  if (!kinds.some(([key]) => key === mode)) mode = "work";
  //: A tab strip, not a pill (DESIGN.md, "A popup that chooses a kind").
  const modes = document.createElement("div");
  modes.className = "tabs-line popup-kinds calc-modes";
  modes.setAttribute("role", "tablist");
  modes.setAttribute("aria-label", "Calculator mode");
  const actions = replyCalcActions(target, close, inline);
  const equation = inline ? null : replyCalcEquation(target, close, actions);
  const panes = { work: replyCalcWorkPane(input, actions), convert: replyCalcConvertPane(actions), ...(equation ? { equation: equation.pane } : {}) };
  //: Where focus goes when a tab is chosen with a press; an arrow keeps it on the strip (INBOX 1530 g M4: the first arrow onto Equation put the caret in the math field, so the next arrow moved inside the equation instead of on to the tab after it).
  const focusIn = {
    work: () => panes.work.querySelector(".calc-input")?.focus(),
    convert: () => panes.convert.querySelector(".calc-amount")?.focus(),
    equation: () => equation?.mount(),
  };
  const wrap = document.createElement("div");
  wrap.className = "calc-panes";
  //: Each tab names its panel and each panel its tab (INBOX 1530 g M3), by ids that carry the dialog's number.
  const n = replyCalc.opened;
  for (const [key, pane] of Object.entries(panes)) {
    pane.setAttribute("role", "tabpanel");
    pane.id = `calc-panel-${n}-${key}`;
    pane.setAttribute("aria-labelledby", `calc-tab-${n}-${key}`);
    pane.classList.toggle("hidden", key !== mode);
  }
  const select = (key, { focus = true } = {}) => {
    for (const other of tabs) {
      const on = other.dataset.tab === key;
      other.setAttribute("aria-selected", String(on));
      other.classList.toggle("active", on);
      other.tabIndex = on ? 0 : -1;
    }
    for (const [name, pane] of Object.entries(panes)) pane.classList.toggle("hidden", name !== key);
    wrap.scrollTop = 0;
    actions.show(key);
    if (focus) focusIn[key]();
    else if (key === "equation") equation?.mount({ focus: false });
  };
  const tabs = kinds.map(([key, words]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("role", "tab");
    button.id = `calc-tab-${n}-${key}`;
    button.setAttribute("aria-controls", `calc-panel-${n}-${key}`);
    button.textContent = words;
    button.dataset.tab = key;
    button.addEventListener("click", () => select(key));
    return button;
  });
  //: Arrows, Home and End walk the strip, which is one Tab stop; the panel opens under the focus without taking it.
  modes.addEventListener("keydown", (event) => {
    const at = tabs.indexOf(document.activeElement);
    const to = { ArrowRight: (at + 1) % tabs.length, ArrowLeft: (at + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1 }[event.key];
    if (at < 0 || to === undefined) return;
    event.preventDefault();
    select(tabs[to].dataset.tab, { focus: false });
    tabs[to].focus();
  });
  modes.append(...tabs);
  wrap.append(...Object.values(panes));
  card.append(modes, wrap, actions.el);
  //: **The head's '?'** (DESIGN.md, a dialog's head; INBOX 1530 g M6): what each tab does and where Insert writes, behind the title as every dialog's is. It replaces the sub line (a sentence the dialog carried at all times, 32 px of the card) and the Equation tab's own '?'.
  const head = card.querySelector(".sheet-head");
  if (head) {
    const helpId = `calc-help-${n}`;
    const help = document.createElement("button");
    help.type = "button";
    help.className = "icon-only ghost small dialog-head-btn";
    help.setAttribute("data-help-for", helpId);
    help.setAttribute("aria-controls", helpId);
    help.setAttribute("aria-expanded", "false");
    help.title = "About Calculator and equations";
    help.setAttribute("aria-label", "About Calculator and equations");
    const icon = document.createElement("i");
    icon.className = "ph ph-question";
    icon.setAttribute("aria-hidden", "true");
    help.appendChild(icon);
    const group = document.createElement("span");
    group.className = "dialog-head-actions";
    const closeButton = head.querySelector(".sheet-close");
    if (closeButton) group.appendChild(closeButton);
    head.querySelector(".sheet-title")?.after(help);
    head.appendChild(group);
    const body = document.createElement("div");
    body.className = "help-body hidden";
    body.id = helpId;
    body.setAttribute("role", "dialog");
    body.setAttribute("aria-label", "About Calculator and equations");
    for (const line of REPLY_CALC_HELP) {
      const p = document.createElement("p");
      p.textContent = line;
      body.appendChild(p);
    }
    head.after(body);
  }
  const first = Math.max(0, kinds.findIndex(([key]) => key === mode));
  for (const [i, tab] of tabs.entries()) {
    tab.setAttribute("aria-selected", String(i === first));
    tab.classList.toggle("active", i === first);
    tab.tabIndex = i === first ? 0 : -1;
  }
  actions.show(kinds[first][0]);
  if (inline) return;
  if (first) focusIn[kinds[first][0]]();
  else requestAnimationFrame(() => focusIn.work());
}

//: **One action row for all three tabs** (INBOX 1530 g, H2, M1, L2, L6). The
//: tabs read as three tools because Work out had a left ghost Insert row,
//: Equation a right filled Insert beside a Cancel and Convert nothing; nothing
//: said where Insert writes, and a dialog opened with no box had no Insert and
//: no reason. Now every tab ends in the same row: a line saying where Insert
//: writes (or that no box is open), then Copy, Insert as equation (Sum and
//: Units) and the one filled Insert. A button with nothing to act on stays in
//: the Tab order as `aria-disabled`, is described by that line, and says why
//: when pressed (Copy on an empty result used to do nothing at all). A pane
//: hands in what it can do with `provide(key, {ready, text, equation, ...})`.
function replyCalcActions(target, close, inline = false) {
  const id = `calc-where-${++replyCalc.opened}`;
  const el = document.createElement("div");
  el.className = "calc-actions";
  const where = document.createElement("p");
  where.className = "muted calc-where";
  where.id = id;
  const row = document.createElement("div");
  row.className = "row right calc-actions-buttons";
  const providers = {};
  let shown = "work";
  const current = () => providers[shown];
  //: Where Insert writes, in the words a person would use for the box they were in (by id, as the opener does: `editorSurfaceKind` answers null until the Library bundle has loaded).
  const kind = target ? EDITOR_SURFACES[target.id] || editorSurfaceKind(target) : null;
  const name = target?.id === "question" ? "the Ask box" : { note: "the note", document: "the document", chat: "the Chat box", agent: "the Agent box", skill: "the skill steps" }[kind] || "the text box you came from";
  const blocked = (kind) => {
    const p = current();
    if (kind !== "copy" && !target) return "No text box is open, so there is nowhere to insert. Use Copy.";
    return p?.ready() ? "" : p?.first || "There is nothing here yet.";
  };
  const write = async (equation) => {
    const p = current();
    const text = equation ? p.equation() : p.text();
    await ensureModule("mathEditor");
    if (mathEditorWrite(target, text, { plain: !equation })) close();
    else toast("Couldn't write into that box.", "info");
  };
  const act = (kind) => {
    const why = blocked(kind);
    if (why) return toast(why, "info");
    const p = current();
    if (kind === "copy") {
      if (p.copy) return p.copy();
      return navigator.clipboard?.writeText(p.text()).then(() => toast("Result copied."), () => toast("Couldn't copy the result.", "info"));
    }
    if (p.insert) return p.insert();
    return write(kind === "equation");
  };
  const copy = smallButton("Copy", "Copy the result", () => act("copy"));
  const asEquation = smallButton("Insert as equation", "Write the sum and its result as an equation", () => act("equation"));
  const insert = smallButton("Insert", "Write the result into the text", () => act("insert"), false);
  insert.classList.add("primary");
  for (const button of [copy, asEquation, insert]) button.setAttribute("aria-describedby", id);
  //: The dialog foot: the one filled Insert last, Copy the lone bordered secondary beside it, and the third (a different kind of write) a quiet one at the start of the row.
  asEquation.classList.add("quiet", "calc-as-equation");
  row.append(asEquation, copy, insert);
  //: A widget has no box to write into: Copy is its one action, and the line about Insert is not drawn.
  if (inline) where.classList.add("hidden");
  el.append(where, row);
  const sync = () => {
    const p = current();
    if (!p) return;
    const ready = Boolean(p.ready());
    const label = p.label?.() || "Insert";
    setLabel(insert, label);
    copy.title = p.copyTitle;
    insert.title = p.insertTitle;
    asEquation.classList.toggle("hidden", inline || !p.equation);
    insert.classList.toggle("hidden", inline);
    copy.setAttribute("aria-disabled", String(!ready));
    insert.setAttribute("aria-disabled", String(!ready || !target));
    asEquation.setAttribute("aria-disabled", String(!ready || !target));
    where.textContent = !target
      ? `No text box is open. Copy ${p.what}, then paste it where you want it.`
      : ready
        ? `${label} writes into ${name}.`
        : `${label} writes into ${name} once there is ${p.needs}.`;
  };
  return {
    el,
    sync,
    provide: (key, provider) => { providers[key] = provider; },
    show: (key) => { shown = key; sync(); },
    //: What the row does with a worked-out result (Sum and Units): the figure to copy or insert, and the sum with its figure as an equation.
    result: (read, words) => ({
      ...words,
      copyTitle: "Copy the result",
      insertTitle: "Write the result into the text",
      ready: () => Boolean(read()),
      text: () => calcFigure(read().answer, true),
      equation: () => calcTex.toTex(read().input, calcFigure(read().answer, true)),
    }),
  };
}

// CALC-TEX-BEGIN
const calcTex = {
  //: An equation's TeX as the sum Work out reads ("\frac{1}{2}+3" to
  //: "((1)/(2))+3"), or null when it is not made of numbers and the signs the
  //: evaluator reads (a letter, a root, a symbol), so a number-free equation
  //: shows no value.
  toSum(tex) {
    let sum = String(tex || "").replace(/\\left|\\right/g, "").replace(/\\[,;: ]/g, " ");
    sum = sum.replace(/\\cdot|\\times/g, "*").replace(/\\div/g, "/").replace(/\\%/g, "%");
    //: The innermost fraction first, so a nested one unwinds from the inside.
    for (let i = 0; i < 8 && sum.includes("\\frac"); i++) sum = sum.replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g, "(($1)/($2))");
    sum = sum.replace(/\^\{([^{}]*)\}/g, "^($1)").replace(/\{/g, "(").replace(/\}/g, ")");
    const plain = /^[0-9+\-*/^().,%\s]+$/.test(sum) && /\d/.test(sum);
    return plain && /[+\-*/^%]/.test(sum.replace(/^\s*-/, "")) ? sum.trim() : null;
  },

  //: A worked-out sum as an equation to write: "12 * (3 + 4)" and "84" to
  //: "12 \times (3 + 4) = 84"; words ("15% of 80", "5 km to miles") stay words
  //: in `\text`.
  toTex(input, figure) {
    const escapes = { "%": "\\%", $: "\\$", "&": "\\&", "#": "\\#", _: "\\_", "{": "\\{", "}": "\\}", "\\": "\\textbackslash{}", "^": "\\^{}", "~": "\\~{}" };
    const words = (text) => `\\text{${text.replace(/[%$&#_{}\\^~]/g, (c) => escapes[c])}}`;
    const side = (text) => {
      if (!/^[0-9+\-*/^().,%\s×÷]+$/.test(text) || !/\d/.test(text)) return words(text);
      const group = String.raw`(\d[\d.,]*|\([^()]*\))`;
      const bare = (part) => (part.startsWith("(") ? part.slice(1, -1) : part);
      return text
        .replace(/\s*[*×]\s*/g, " \\times ")
        .replace(new RegExp(`${group}\\s*[/÷]\\s*${group}`, "g"), (_all, top, bottom) => `\\frac{${bare(top)}}{${bare(bottom)}}`)
        .replace(/\s*[/÷]\s*/g, " \\div ")
        .replace(new RegExp(String.raw`\^\s*(-?\d[\d.,]*|\([^()]*\))`, "g"), (_all, power) => `^{${bare(power)}}`)
        .replace(/%/g, "\\%")
        .trim();
    };
    return `${side(String(input || "").trim())} = ${side(String(figure || "").trim())}`;
  },
};

//: **What a history keeps** (INBOX 1541): newest first, twenty rows, a row told from another by its `key` (the words of a sum, the TeX of an equation). `replacing` is the key of a row being edited: the new row takes its place in the list rather than joining the top, and a row that is gone just adds.
calcTex.log = {
  max: 20,
  add(list, entry, replacing = "") {
    const at = replacing ? list.findIndex((row) => row.key === replacing) : -1;
    const rest = list.filter((row) => row.key !== entry.key && row.key !== replacing);
    if (at < 0) return [entry, ...rest].slice(0, calcTex.log.max);
    rest.splice(list.slice(0, at).filter((row) => row.key !== entry.key && row.key !== replacing).length, 0, entry);
    return rest.slice(0, calcTex.log.max);
  },
  remove: (list, key) => list.filter((row) => row.key !== key),
  //: What was stored, as a list of rows: anything else (a hand-edited value, an older shape) is no history.
  clean: (raw) => (Array.isArray(raw) ? raw.filter((row) => row && typeof row.key === "string" && row.key).slice(0, calcTex.log.max) : []),
};
// CALC-TEX-END

//: **The result** (INBOX 1530 g L1). The figure is worded as a preview while it
//: is one ("Preview. Enter keeps it."), not only greyed, and it is not itself
//: the live region (an `<output>` is one by role, and it spoke on every key):
//: a visually hidden status is set once the figure settles, at once for Enter
//: and =, after a pause for typing (`replyCalcShow`).
function replyCalcResult() {
  const out = document.createElement("div");
  out.className = "calc-result";
  const line = document.createElement("div");
  line.className = "calc-figure-row";
  const figure = document.createElement("strong");
  figure.className = "calc-figure";
  const tag = document.createElement("span");
  tag.className = "muted calc-tag";
  tag.textContent = "Preview. Enter keeps it.";
  tag.hidden = true;
  //: An answer is copied from where it is (INBOX 1541); an equation's value line reads "= 3.5" and copies "3.5".
  const copy = smallButton("ph:copy", "Copy the result", () => {
    const text = figure.textContent.replace(/^=\s*/, "");
    if (text) navigator.clipboard?.writeText(text).then(() => toast("Result copied."), () => toast("Couldn't copy the result.", "info"));
  });
  copy.classList.add("calc-copy");
  copy.hidden = true;
  line.append(figure, tag, copy);
  const read = document.createElement("span");
  read.className = "muted calc-read";
  const say = document.createElement("span");
  say.className = "visually-hidden";
  say.setAttribute("role", "status");
  say.setAttribute("aria-live", "polite");
  out.append(line, read, say);
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

function replyCalcShow(out, got, { final = false, now = false } = {}) {
  const figure = out.querySelector(".calc-figure");
  const read = out.querySelector(".calc-read");
  const say = out.querySelector(".visually-hidden");
  out.classList.toggle("is-error", Boolean(got?.error));
  out.classList.toggle("is-preview", !final);
  //: Said after a pause, so a key held or a sum typed is one announcement, not one per character.
  clearTimeout(out._said);
  const announce = (words) => (now ? (say.textContent = words) : (out._said = setTimeout(() => (say.textContent = words), 800)));
  if (!got) {
    figure.textContent = "";
    read.textContent = "";
    out.querySelector(".calc-tag").hidden = true;
    out.querySelector(".calc-copy").hidden = true;
    return announce("");
  }
  //: The figure on its own ("84", not "12*(3+4) is 84."): the sum is in the
  //: box, and how the app read it is the line under.
  figure.textContent = got.error ? "" : calcFigure(got.answer, true);
  read.textContent = got.error ? got.error : got.read_as ? `Read as ${got.read_as}` : "";
  out.querySelector(".calc-tag").hidden = final || Boolean(got.error);
  out.querySelector(".calc-copy").hidden = !figure.textContent;
  announce([figure.textContent, read.textContent].filter(Boolean).join(". ") + (final || got.error ? "" : ". Preview"));
}

function replyCalcWorkPane(input, actions) {
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
  //: Restoring puts the sum back in the box (a preview, not a keep); Copy writes the figure.
  const history = replyCalcHistory("work", {
    label: (row) => `${row.input} = ${calcFigure(row.answer, false)}`,
    copy: (row) => calcFigure(row.answer, true),
    restore: (row) => {
      box.value = row.input;
      box.dispatchEvent(new Event("input"));
      box.focus();
    },
  });
  let timer = 0;
  let asked = 0;
  //: The result on show, for the action row.
  let last = null;
  actions.provide("work", actions.result(() => last, { what: "the result", needs: "a result", first: "Work out a sum first." }));
  const run = async (final) => {
    const mine = ++asked;
    try {
      const got = await replyCalcWork(box.value);
      if (mine !== asked) return;
      replyCalcShow(out, got, { final, now: final });
      last = got?.answer && !got.error ? { input: box.value.trim(), answer: got.answer } : null;
      actions.sync();
      if (final && last) history.record({ key: last.input, input: last.input, answer: last.answer });
    } catch (error) {
      if (mine !== asked) return;
      replyCalcShow(out, { error: error.message }, { final, now: final });
      last = null;
      actions.sync();
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
  pane.append(box, out, keys, history.el);
  if (input) run(true);
  return pane;
}

//: **The Equation tab** (INBOX 1527): the pane the editor is built into the
//: first time the tab opens (its library is the heavy part), with the value
//: of an equation made of numbers under the field, worked out by the same
//: reader as Work out. `mount()` builds it, or puts focus back in it.
function replyCalcEquation(target, close, actions) {
  const pane = document.createElement("div");
  pane.className = "calc-pane calc-equation";
  const note = replyCalcResult();
  note.classList.add("hidden");
  let editor = null;
  let loading = null;
  let timer = 0;
  let asked = 0;
  //: The history (INBOX 1541): an equation is kept when it is copied or inserted, and a moment after the last change (not for the one the editor opened with).
  let history = null;
  let settle = 0;
  let changed = false;
  const keep = (auto = false) => {
    const row = editor?.entry();
    if (row) history?.record(row, auto);
  };
  //: The action row's Copy and Insert are the editor's own (it knows the display mode, the equation being edited and the box).
  actions.provide("equation", {
    what: "the equation",
    needs: "an equation",
    first: "Type an equation first.",
    copyTitle: "Copy the equation, between dollar signs",
    insertTitle: "Write the equation into the text (Ctrl+Enter)",
    ready: () => Boolean(editor?.ready()),
    label: () => editor?.label || "Insert",
    copy: () => (keep(), editor.copy()),
    insert: () => (keep(), editor.insert()),
  });
  const onTex = (tex) => {
    actions.sync();
    clearTimeout(settle);
    if (changed) settle = setTimeout(() => keep(true), 2500);
    changed = true;
    clearTimeout(timer);
    const sum = calcTex.toSum(tex);
    const mine = ++asked;
    if (!sum) return note.classList.add("hidden");
    timer = setTimeout(async () => {
      let got = null;
      try {
        got = await replyCalcWork(sum);
      } catch {
        got = null;
      }
      if (mine !== asked) return;
      if (!got?.answer || got.error) return note.classList.add("hidden");
      replyCalcShow(note, { answer: got.answer }, { final: true });
      note.querySelector(".calc-figure").textContent = `= ${calcFigure(got.answer, true)}`;
      note.classList.remove("hidden");
    }, 250);
  };
  const say = (words) => {
    const line = document.createElement("p");
    line.className = "muted calc-note";
    line.textContent = words;
    pane.replaceChildren(line);
  };
  const mount = ({ focus = true } = {}) => {
    if (editor) return focus ? editor.focus() : undefined;
    if (!loading) {
      say("Loading the equation editor.");
      loading = ensureModule("mathEditor")
        .then((ok) => {
          //: Its rows are drawn by the editor's own tile face, so this waits for the editor to be loaded.
          history = ok
            ? replyCalcHistory("equation", {
                label: (row) => mathEditorTileFace({ sample: row.tex }),
                copy: (row) => mathEditorOutput(row.tex, row.display),
                restore: (row) => editor?.load(row),
              })
            : null;
          editor = ok && typeof mathEditorMount === "function" ? mathEditorMount({ host: pane, target, done: close, note, onTex, focus, log: history?.el }) : null;
          changed = false;
          if (!editor) throw new Error("not loaded");
        })
        .catch(() => {
          loading = null;
          say("The equation editor could not load. Open this tab again to retry.");
        });
    }
    return loading;
  };
  return { pane, mount };
}

//: The keypad: one Tab stop (a roving `tabindex`), the arrows walk its four
//: columns, Home and End its row; each key says what it does to a screen
//: reader ("Times", not the icon's name).
function replyCalcKeypad(box, equals) {
  const pad = document.createElement("div");
  pad.className = "key-grid calc-keys";
  pad.setAttribute("role", "group");
  pad.setAttribute("aria-label", "Keypad");
  const keys = REPLY_CALC_KEYS.map(([face, act], i) => {
    const key = document.createElement("button");
    key.type = "button";
    // A key of a `.key-grid`: the quiet inset fill, operators tinted, and `=` the grid's one filled key (the dialog's own is Insert, in the foot).
    key.className = `calc-key${/^[-+*/%]$/.test(act) ? " is-op" : ""}${act === "equals" ? " is-equals" : ""}`;
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

//: **A tab's history** (INBOX 1541, the owner: "calculation, conversion and equation history ... an easy way to copy the answers ... if the user clicks on a history thing, they will be reentered in the fields ... clear or edit the history"). A bar under the pane, "History" with its count and Clear, closed until opened (kept per browser) so the keypad keeps its room; the rows newest first, each a button that puts it back in the fields (`restore`), then Copy (`copy` says what), Edit (the same, and the next keep replaces that row instead of adding one) and Remove. Clear and Remove can be undone from the toast. `record(row, auto)` adds a row; `auto` is a row kept after a pause (Units, the Equation), which replaces the last one made within eight seconds so typing does not fill the list.
function replyCalcHistory(tab, { label, copy, restore }) {
  let list = replyCalc.load(tab);
  let replacing = "";
  let editing = false;
  let lastKey = "";
  let lastAt = 0;
  let open = prefs.bool("calc-history-open", false);
  const el = document.createElement("div");
  el.className = "calc-log";
  const bar = document.createElement("div");
  bar.className = "calc-log-bar";
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "ghost small calc-log-toggle";
  const count = document.createElement("span");
  count.className = "calc-log-count";
  const note = document.createElement("span");
  note.className = "muted calc-log-note";
  const clear = smallButton("Clear", "Clear the history", () => {
    const before = list;
    set([]);
    toastAction("History cleared.", "Undo", () => set(before), { ms: 10000, record: false });
  });
  const rows = document.createElement("ul");
  rows.className = "calc-history";
  rows.id = `calc-history-${tab}-${replyCalc.opened}`;
  rows.setAttribute("aria-label", "Earlier answers");
  toggle.setAttribute("aria-controls", rows.id);
  const caret = document.createElement("i");
  caret.className = "ph ph-caret-down";
  caret.setAttribute("aria-hidden", "true");
  toggle.append("History", count, caret);
  bar.append(toggle, note, clear);
  el.append(bar, rows);
  const set = (next) => {
    list = next;
    if (!list.some((row) => row.key === replacing)) {
      replacing = "";
      editing = false;
    }
    replyCalc.save(tab, list);
    draw();
  };
  const row = (item) => {
    const li = document.createElement("li");
    li.classList.toggle("is-editing", editing && item.key === replacing);
    const again = document.createElement("button");
    again.type = "button";
    again.className = "ghost small calc-again";
    again.replaceChildren(label(item));
    again.title = "Put this back in the fields";
    again.addEventListener("click", () => restore(item));
    const text = () => copy(item);
    const out = smallButton("ph:copy", "Copy this answer", () => navigator.clipboard?.writeText(text()).then(() => toast("Copied."), () => toast("Couldn't copy it.", "info")));
    const edit = smallButton("ph:pencil-simple", "Edit this one", () => {
      replacing = item.key;
      editing = true;
      restore(item);
      draw();
    });
    const drop = smallButton("ph:x", "Remove from the history", () => {
      const before = list;
      set(calcTex.log.remove(list, item.key));
      toastAction("Removed from the history.", "Undo", () => set(before), { ms: 10000, record: false });
    });
    li.append(again, out, edit, drop);
    return li;
  };
  function draw() {
    el.classList.toggle("hidden", !list.length);
    count.textContent = ` ${list.length}`;
    toggle.setAttribute("aria-expanded", String(open));
    rows.hidden = !open;
    clear.hidden = !open;
    note.textContent = editing && open ? "Editing a saved row: keeping a result replaces it." : "";
    rows.replaceChildren(...(open ? list.map(row) : []));
  }
  toggle.addEventListener("click", () => {
    open = !open;
    prefs.set("calc-history-open", open ? "1" : "0");
    draw();
    //: One setting for the dialog: the other tabs' bars follow (each one's click lands here once, and stops when it matches).
    for (const other of el.closest(".calc-card")?.querySelectorAll(".calc-log-toggle") || []) {
      if (other !== toggle && other.getAttribute("aria-expanded") !== String(open)) other.click();
    }
  });
  draw();
  return {
    el,
    record(item, auto = false) {
      const now = Date.now();
      //: A row kept after a pause replaces the last one made so, within eight seconds, and a row being edited is replaced where it stands.
      const prior = auto && lastKey && now - lastAt < 8000 ? lastKey : "";
      list = calcTex.log.add(list, item, replacing || prior);
      if (editing && auto) replacing = item.key;
      else {
        replacing = "";
        editing = false;
      }
      lastKey = auto ? item.key : "";
      lastAt = now;
      replyCalc.save(tab, list);
      draw();
    },
  };
}

function replyCalcConvertPane(actions) {
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
  //: The conversion on show, for the action row (the same shape as Sum's).
  let last = null;
  actions.provide("convert", actions.result(() => last, { what: "the result", needs: "a result", first: "Pick an amount and two units first." }));
  //: Kept a moment after the last change (the conversion runs on every key); a row puts the kind, the amount and both units back.
  let seen = 0;
  let settle = 0;
  //: Nothing is kept for the conversion the pane opens with: only after a press or a change in it.
  let touched = false;
  for (const type of ["input", "change", "click"]) pane.addEventListener(type, () => (touched = true), true);
  const history = replyCalcHistory("convert", {
    label: (row) => `${row.input} = ${calcFigure(row.answer, false)}`,
    copy: (row) => calcFigure(row.answer, true),
    restore: (row) => {
      if (!replyCalc.units?.[row.kind]) return;
      kind.value = row.kind;
      fillKind();
      [from.value, to.value, amount.value] = [row.from, row.to, row.amount];
      run();
    },
  });
  const run = async () => {
    const mine = ++seen;
    clearTimeout(settle);
    last = null;
    if (!from.value || !to.value || amount.value === "") {
      replyCalcShow(out, null);
      return actions.sync();
    }
    const asked = `${amount.value} ${from.value} to ${to.value}`;
    try {
      const got = await replyCalcWork(asked);
      if (mine !== seen) return;
      replyCalcShow(out, got, { final: true });
      last = got?.answer && !got.error ? { input: asked, answer: got.answer } : null;
      if (last && touched) {
        const row = { key: asked, input: asked, answer: got.answer, kind: kind.value, amount: amount.value, from: from.value, to: to.value };
        settle = setTimeout(() => history.record(row, true), 1500);
      }
    } catch (error) {
      if (mine !== seen) return;
      replyCalcShow(out, { error: error.message }, { final: true });
    }
    actions.sync();
  };
  const fillKind = () => {
    const names = replyCalc.units?.[kind.value] || [];
    const [one, two] = REPLY_CALC_PAIRS[kind.value] || [];
    fill(from, names, one);
    fill(to, names, two || names[1]);
    const dated = new Date(`${replyCalc.units?.rates_date}T12:00`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
    note.textContent = kind.value === "currency" ? `Rates from ${dated}, set by hand: not today's rate.` : "";
  };
  const pickKind = () => {
    fillKind();
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
  pane.append(kind, row, out, note, history.el);
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
  //: **One line under a reply the window cut short** (audit 1028 E57): when a
  //: long chat no longer fits the model's context, the oldest exchanges are left
  //: out of the prompt, and a model that "forgot" the start of a chat looked like
  //: a model that was wrong. The turn's first stats event carries the count
  //: (`composition.history_dropped`); Compress in the header is the fix, named in
  //: the line rather than pressed for the person.
  function renderHistoryTrimmedNotice(container, dropped) {
    if (!container || !(dropped > 0)) return;
    const line = document.createElement("p");
    line.className = "notice notice-warn history-trimmed-notice";
    line.setAttribute("role", "note");
    const many = dropped !== 1;
    setLabel(line, `ph:warning The oldest ${many ? `${dropped} exchanges` : "exchange"} no longer fit the model's window, so this answer was written without ${many ? "them" : "it"}. Compress in the header keeps the gist.`);
    container.insertBefore(line, container.querySelector(":scope > .msg-meta"));
  }
  //: Nested, not a global: the shared scope is capped (test_global_scope_ratchet).

  const list = (answers instanceof Element ? [answers] : [...(answers || [])]).filter((el) => el?.isConnected);
  if (!list.length) return;
  for (const answer of list) replyFoldLong(answer);
  replyNotePreviews(list);
  if (opts.head && list.some((answer) => answer.textContent.trim())) replyByline(opts.head, opts);
  if (opts.composed) replyReveal(list);
  if (opts.unsupported) renderToolsUnsupportedNotice(opts.bubble, opts.unsupported);
  if (opts.trimmed) renderHistoryTrimmedNotice(opts.bubble, opts.trimmed);
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
//: (DESIGN.md, "An animation of anything"). Reduced motion makes it a quick
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
    const words = wordCount(text);
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
  //: The server's count is over the whole note; a clipped list row holds its first 300 characters.
  const words = entry?.word_count ?? (content ? wordCount(plainText(content)) : 0);
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
