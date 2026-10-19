// statistics.js: the Statistics page and the weekly review card
// (UI_MODERNISATION_PLAN "Deepened 2026-10-10: statistics", rows 1 and 2;
// Brief 89).
//
// Lazy (`LAZY_MODULES.statistics`, with ask-chart.js and utilities-lazy.css):
// the palette's "Statistics" row, the heatmap's Statistics button and the
// dashboard's This week card reach it through `openStatistics`'s stand-in or
// `ensureModule`. Every figure comes from one `GET /statistics`, counted from
// rows with no model (ai/notebook_stats.py `page`); the charts are the Ask
// chart recipe (`drawAskChart`), never a second chart. The one figure made
// here is "not used", because the features the app offers are this page's
// own (its tabs and palette rows, `usageLabels` in usage-ledger.js); the
// counts it compares against are the ledger's, from the same call.

const STATS_USAGE_TOP = 8;

function statsTile(value, label, go) {
  //: A tile that can open what it counts is a button; one that cannot stays a block.
  const tile = document.createElement(go ? "button" : "div");
  tile.className = "stats-tile";
  if (go) {
    tile.type = "button";
    tile.classList.add("is-link");
    tile.title = `Open ${label}`;
    tile.addEventListener("click", () => statsGo(go));
  }
  const number = document.createElement("strong");
  number.className = "stats-tile-value";
  number.textContent = Number(value || 0).toLocaleString();
  const name = document.createElement("span");
  name.className = "muted stats-tile-label";
  name.textContent = label;
  tile.append(number, name);
  return tile;
}

function statsSection(title, about) {
  const section = document.createElement("section");
  section.className = "stats-section";
  const head = document.createElement("h3");
  head.textContent = title;
  section.appendChild(head);
  if (about) {
    const line = document.createElement("p");
    line.className = "muted stats-about";
    line.textContent = about;
    section.appendChild(line);
  }
  return section;
}

function statsTiles(pairs) {
  const grid = document.createElement("div");
  grid.className = "stats-tiles";
  //: [value, "note", "notes", go]: the one form a count of 1 takes, and
  //: where a click on the tile goes (none: the tile only counts).
  for (const [value, one, many = one, go] of pairs) grid.appendChild(statsTile(value, value === 1 ? one : many, go));
  return grid;
}

function statsChart(chart) {
  const host = document.createElement("div");
  host.className = "ask-chart stats-chart";
  //: Every chart here answers the pointer and the keyboard (INBOX 1319).
  drawAskChart(host, { ...chart, interactive: true });
  return host;
}

//: Closes the open Statistics card, if one is open (set by `openStatistics`),
//: so what a click opens is not behind it.
const statsCard = { close: null };

//: A click on the page acts: it closes the card and goes where the thing is.
//: Month points open the Timeline at that month; a feature bar opens that
//: feature, a tab or the palette command the ledger counted it under.
async function statsGo(go) {
  statsCard.close?.({ stay: true });
  try {
    await go();
  } catch {
    toast("Couldn't open that.", true, { action: ["Try again", () => statsGo(go)] });
  }
}

const statsOpenTab = (tab) => () => switchTab(tab);

async function statsOpenReminders(filter) {
  await switchTab("reminders");
  document.querySelector(`#reminder-filter [data-filter="${filter}"]`)?.click();
}

async function statsOpenLooseEnds() {
  await switchTab("dashboard");
  await new Promise((resolve) => setTimeout(resolve, 400));
  const card = document.querySelector('.dash-widget[data-widget="orphans"]:not(.dash-hidden)');
  if (card) card.scrollIntoView({ block: "center" });
  else toast("Loose ends isn't on your Dashboard. Add it from Widgets.");
}

function statsOpenMonth(row) {
  return statsGo(async () => {
    await switchTab("timeline");
    timelineJumpToDay(`${row.label}-01`);
  });
}

function statsOpenFeature(name) {
  return statsGo(async () => {
    if (name.startsWith("tab:")) return switchTab(name.slice(4));
    const command = paletteCommands().find((c) => usageFeatureName(c.label) === name);
    if (command) command.run();
  });
}

function statsDay(iso) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

//: "3 more than last week", "the same as last week": said in words beside the
//: two counts, so the line reads without comparing two numbers by eye.
function statsChange(now, before) {
  if (now === before) return "the same as last week";
  const diff = Math.abs(now - before).toLocaleString();
  return now > before ? `${diff} more than last week` : `${diff} fewer than last week`;
}

//: This week against last, day by day: last week's seven days as a quiet
//: line, this week's so far on top in the accent, both from the week's first
//: day so the two are read against each other. Said in words beside it, so
//: it is a picture only.
function statsSpark(values, days) {
  const w = 84;
  const h = 22;
  const top = Math.max(1, ...values);
  const line = (part, cls) => {
    const points = part.map((v, i) => `${(2 + (i * (w - 4)) / 6).toFixed(1)},${(h - 2 - (v / top) * (h - 4)).toFixed(1)}`).join(" ");
    return askChartSvgEl("polyline", { points, class: cls });
  };
  const svg = askChartSvgEl("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h, class: "stats-spark", "aria-hidden": "true" });
  svg.append(line(values.slice(0, 7), "stats-spark-last"), line(values.slice(7, 7 + days), "stats-spark-this"));
  //: A dot on today, so a week that has only just begun still shows where it is.
  const now = values[6 + days];
  svg.appendChild(askChartSvgEl("circle", { cx: 2 + ((days - 1) * (w - 4)) / 6, cy: h - 2 - ((now || 0) / top) * (h - 4), r: 2.25, class: "stats-spark-dot" }));
  return svg;
}

//: Screen Time's weekly report: each line one count, this week so far
//: against the whole of last week, both weeks named.
function statsWeekCard(week) {
  const card = document.createElement("div");
  card.className = "stats-week";
  const span = document.createElement("p");
  span.className = "muted stats-week-span";
  span.textContent = `This week, ${statsDay(week.this.start)} to ${statsDay(week.this.end)}, against ${statsDay(week.last.start)} to ${statsDay(week.last.end)}`;
  const list = document.createElement("ul");
  list.className = "stats-week-list";
  for (const [key, label] of [["notes", "Notes made"], ["words", "Words written"], ["edited_words", "Words added to older notes"], ["reminders_done", "Reminders done"]]) {
    const now = week.this[key] || 0;
    const before = week.last[key] || 0;
    const li = document.createElement("li");
    li.className = "stats-week-row";
    li.dataset.stat = key;
    const name = document.createElement("span");
    name.className = "stats-week-label";
    name.textContent = label;
    const value = document.createElement("strong");
    value.className = "stats-week-value";
    value.textContent = now.toLocaleString();
    const change = document.createElement("span");
    change.className = "muted stats-week-change";
    change.textContent = `${statsChange(now, before)} (${before.toLocaleString()})`;
    const daily = week.daily && week.daily[key];
    if (daily) {
      //: Days of this week so far: Monday on the clock to the week's last counted day.
      const days = Math.max(1, Math.round((new Date(`${week.this.end}T00:00:00`) - new Date(`${week.this.start}T00:00:00`)) / 864e5) + 1);
      li.append(name, statsSpark(daily, Math.min(7, days)), value, change);
    } else {
      li.append(name, value, change);
    }
    list.appendChild(li);
  }
  card.append(span, list);
  return card;
}

//: Which of the app's own features have no use in the ledger's window: the
//: page knows what it offers, the ledger knows what was used.
async function statsUnused(usage, asOf) {
  await ensureModule("usageLedger");
  const labels = usageLabels();
  const cutoff = new Date(asOf);
  cutoff.setDate(cutoff.getDate() - (usage.unused_days || 90));
  const since = cutoff.toISOString().slice(0, 10);
  const used = new Map(usage.features.map((f) => [f.name, f]));
  const unused = Object.keys(labels).filter((name) => !used.has(name) || String(used.get(name).last || "") < since);
  return { labels, unused };
}

const STATS_RANGES = [
  ["12", "The last year", "the last year"],
  ["3", "The last 3 months", "the last 3 months"],
  ["all", "Since the first note", "since the first note"],
];

function statsGrowthChart(book) {
  const total = book.growth.reduce((sum, row) => sum + row.value, 0);
  const words = (STATS_RANGES.find(([value]) => value === book.growth_range) || STATS_RANGES[0])[2];
  return statsChart({ title: `Notes made per month, ${words}`, kind: "line", by: "month", rows: book.growth, total, onPick: statsOpenMonth });
}

function statsRangeControl(holder, book) {
  const label = document.createElement("label");
  label.className = "stats-range";
  const text = document.createElement("span");
  text.className = "muted text-sm";
  text.textContent = "Range";
  const select = document.createElement("select");
  select.id = "stats-range";
  for (const [value, name] of STATS_RANGES) select.add(new Option(name, value));
  select.value = book.growth_range || "12";
  select.addEventListener("change", async () => {
    try {
      const data = await apiJson(`/statistics?growth=${encodeURIComponent(select.value)}`, { silent: true });
      holder.replaceChildren(statsGrowthChart(data.notebook));
    } catch {
      toast("Couldn't change the range.", true, { action: ["Try again", () => select.dispatchEvent(new Event("change"))] });
    }
  });
  label.append(text, select);
  return label;
}

function statsNotebookSection(book) {
  const section = statsSection("Notebook", "What is in it, and how it grew. Click a count to open what it counts.");
  section.appendChild(
    statsTiles([
      [book.notes, "note", "notes", statsOpenTab("notes")],
      [book.words, "word", "words"],
      [book.tags, "tag", "tags", statsOpenTab("notes")],
      [book.categories, "category", "categories", statsOpenTab("notes")],
      [book.documents, "document", "documents", statsOpenTab("library")],
      [book.links, "link", "links", statsOpenTab("graph")],
      [book.orphans, "note with no link", "notes with no link", statsOpenLooseEnds],
    ])
  );
  const holder = document.createElement("div");
  holder.className = "stats-growth";
  holder.appendChild(statsGrowthChart(book));
  section.append(statsRangeControl(holder, book), holder);
  return section;
}

function statsRemindersSection(rem) {
  const section = statsSection("Reminders", "Made, ticked off, and past their time. Click a count to open them.");
  const open = (filter) => () => statsOpenReminders(filter);
  section.appendChild(statsTiles([[rem.made, "made", "made", open("all")], [rem.done, "done", "done", open("done")], [rem.open, "open", "open", open("open")], [rem.late, "late", "late", open("open")]]));
  return section;
}

async function statsUsageSection(usage, asOf) {
  const section = statsSection("Usage", `Counted on this computer only, over the last ${usage.unused_days || 90} days.`);
  const { labels, unused } = await statsUnused(usage, asOf).catch(() => ({ labels: {}, unused: null }));
  const usedNames = usage.features.filter((f) => labels[f.name] || f.name.startsWith("tab:"));
  section.appendChild(
    statsTiles([
      [usage.features.length, "feature used", "features used"],
      [usage.uses, "use counted", "uses counted"],
      ...(unused ? [[unused.length, "not used lately"]] : []),
    ])
  );
  const top = usedNames.slice(0, STATS_USAGE_TOP).map((f) => ({ label: labels[f.name] || f.name, value: f.count, name: f.name }));
  if (top.length) {
    section.appendChild(
      statsChart({
        title: "Most used", kind: "bar", by: "feature", rows: top, total: usage.uses, columns: ["Feature", "Uses"],
        source: "uses on this computer", unit: ["use", "uses"], onPick: (row) => statsOpenFeature(row.name),
      })
    );
  }
  if (unused && unused.length) {
    const line = document.createElement("p");
    line.className = "muted stats-unused";
    const names = unused.map((name) => labels[name] || name);
    line.textContent = `Not used lately: ${names.slice(0, 12).join(", ")}${names.length > 12 ? `, and ${names.length - 12} more` : ""}.`;
    section.appendChild(line);
  }
  return section;
}

//: "Ask about your statistics": the Guide's pattern (a box, three starters,
//: the answer under it) over `POST /statistics/ask`, which counts the answer
//: from the rows with no model (ai/stats_ask.py). Nothing is kept: a new
//: question replaces the last answer.
const STATS_ASK_STARTERS = ["Summarise my month", "What do I use most?", "Am I writing more than last month?"];

function statsAskBox() {
  const form = document.createElement("form");
  form.className = "stats-ask";
  const label = document.createElement("label");
  label.className = "stats-ask-label";
  label.htmlFor = "stats-ask-input";
  label.textContent = "Ask about your statistics";
  const row = document.createElement("div");
  row.className = "stats-ask-row";
  const input = document.createElement("input");
  input.id = "stats-ask-input";
  input.type = "text";
  input.maxLength = 300;
  input.autocomplete = "off";
  input.placeholder = "How many notes did I write in July?";
  const send = document.createElement("button");
  send.type = "submit";
  send.className = "primary small";
  send.textContent = "Ask";
  row.append(input, send);
  const chips = document.createElement("div");
  chips.className = "stats-ask-chips";
  const answer = document.createElement("div");
  answer.className = "stats-ask-answer hidden";
  answer.setAttribute("aria-live", "polite");
  const ask = async (question) => {
    const text = question.trim();
    if (!text) return;
    input.value = text;
    send.disabled = true;
    try {
      const done = await apiJson("/statistics/ask", { method: "POST", body: JSON.stringify({ question: text }), readOnly: true, silent: true });
      const line = document.createElement("p");
      line.className = "stats-ask-text";
      line.textContent = done.text;
      answer.replaceChildren(line);
      if ((done.facts || []).length > 1 && done.kind !== "none") {
        const list = document.createElement("ul");
        list.className = "muted stats-ask-facts";
        for (const fact of done.facts.slice(0, 8)) {
          const li = document.createElement("li");
          li.textContent = `${fact.label}: ${Number(fact.count).toLocaleString()}`;
          list.appendChild(li);
        }
        answer.appendChild(list);
      }
      answer.classList.remove("hidden");
    } catch {
      toast("Couldn't answer that.", true, { action: ["Try again", () => ask(text)] });
    } finally {
      send.disabled = false;
    }
  };
  for (const starter of STATS_ASK_STARTERS) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "ghost small stats-ask-chip";
    chip.textContent = starter;
    chip.addEventListener("click", () => ask(starter));
    chips.appendChild(chip);
  }
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    ask(input.value);
  });
  form.append(label, row, chips, answer);
  return form;
}

async function paintStatistics(body) {
  let data;
  try {
    data = await apiJson("/statistics");
  } catch {
    surfaceFailed(body, "the statistics", () => paintStatistics(body));
    return;
  }
  surfaceRecovered(body);
  const week = statsSection("This week", "Every line is a count, against last week.");
  week.appendChild(statsWeekCard(data.week));
  body.replaceChildren(
    statsAskBox(),
    week,
    statsNotebookSection(data.notebook),
    statsRemindersSection(data.reminders),
    await statsUsageSection(data.usage, data.as_of)
  );
}

function openStatistics() {
  if (document.querySelector(".stats-overlay")) return;
  const returnFocus = document.activeElement;
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay stats-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "stats-title");
  const card = document.createElement("div");
  card.className = "card modal-card stats-card";
  const head = document.createElement("div");
  head.className = "dialog-head";
  const title = document.createElement("h2");
  title.className = "dialog-head-title";
  title.id = "stats-title";
  title.textContent = "Statistics";
  const actions = document.createElement("span");
  actions.className = "dialog-head-actions";
  const help = smallButton("ph:question", "About statistics", () => {});
  help.classList.add("icon-only", "graph-help-toggle");
  help.dataset.helpFor = "stats-help";
  help.setAttribute("aria-controls", "stats-help");
  help.setAttribute("aria-expanded", "false");
  const close = (opts) => {
    statsCard.close = null;
    document.removeEventListener("keydown", onKey, true);
    overlay.remove();
    if (returnFocus?.isConnected) returnFocus.focus?.();
    if (typeof overlayClosed === "function") overlayClosed("Statistics", { stay: opts?.stay === true });
  };
  const onKey = (event) => {
    if (event.key !== "Escape" || document.querySelector("#stats-help:not(.hidden)")) return;
    event.stopPropagation();
    close();
  };
  const x = smallButton("ph:x", "Close", close);
  x.classList.add("icon-only", "dialog-head-btn");
  actions.append(help, x);
  head.append(title, actions);
  const about = document.createElement("p");
  about.className = "muted stats-lede";
  about.textContent = "Your notebook, your reminders and what you use, counted.";
  const helpBody = document.createElement("div");
  helpBody.className = "help-body hidden";
  helpBody.id = "stats-help";
  helpBody.setAttribute("role", "dialog");
  helpBody.setAttribute("aria-label", "About statistics");
  const helpText = document.createElement("p");
  helpText.textContent =
    "Every number here is counted from your notes, reminders and this computer's usage counts, with no model. Private and binned notes are left out. This week runs from Monday on your clock; words written are the words in the notes made that week; a reminder counts as done in the week it was ticked off. Hover or focus a point or bar for its exact value, use the arrow keys to move between them, and click or press Enter to open it: a month opens the Timeline there, a feature bar opens that feature. The counts open what they count, the range picks how far back the growth chart goes, and the small line beside each week row is this week's days against last week's. The Ask box answers from these same counts, with no model: try the three starters. Usage is counted on this computer and never leaves it.";
  helpBody.appendChild(helpText);
  const body = document.createElement("div");
  body.className = "stats-body";
  body.setAttribute("aria-busy", "true");
  body.textContent = "Counting…";
  card.append(head, about, helpBody, body);
  overlay.appendChild(card);
  document.body.appendChild(overlay);
  statsCard.close = close;
  recordTabVisit("Statistics");
  ensureModule("quickNote");
  wireBackdropClose(overlay, close);
  document.addEventListener("keydown", onKey, true);
  initHelpToggles(card);
  x.focus();
  return paintStatistics(body).finally(() => body.removeAttribute("aria-busy"));
}

//: The dashboard's This week card (DASH_WIDGETS.week): the page's first
//: section, with the way into the rest.
async function renderWeekWidget(body) {
  let data;
  try {
    data = await apiJson("/statistics", { silent: true });
  } catch {
    surfaceFailed(body, "this week's counts", () => renderWeekWidget(body));
    return;
  }
  body.replaceChildren(statsWeekCard(data.week));
  const more = smallButton("ph:chart-bar All statistics", "Open the Statistics page", () => openStatistics());
  const foot = document.createElement("div");
  foot.className = "row stats-more";
  foot.appendChild(more);
  body.appendChild(foot);
}
