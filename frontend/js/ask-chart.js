// ask-chart.js: a chart drawn from a counting or trend question asked in the
// Ask box (WORLD_CLASS_PLAN section 17 row 4, "charts from questions").
//
// Lazy, in the Ask history's bundle (app.js `LAZY_MODULES.askHistory`): the
// Ask box asks for it only when a question reads as a count ("how many notes
// per category this month", "notes per week in 2026"), so nothing here runs on
// an ordinary question. The numbers come from `POST /charts/question`
// (routes_vision.py), which reads the words with no model and counts the
// records, so the chart is the same with the model off; the answer under it is
// whatever the model says, and the chart does not wait for it.
//
// The recipe (DESIGN.md, "A chart answering a question"): one `.ask-chart`
// card above the answer, its title and a total, an SVG of bars (a category or
// a tag) or a line (time), drawn from the theme's tokens through classes so
// both themes hold, the same numbers as a table under it, and Save as PNG. The
// SVG is the one picture; the table is what a screen reader reads.

const ASK_CHART_W = 640;
const ASK_CHART_H = 220;
const ASK_CHART_PAD = { top: 12, right: 12, bottom: 44, left: 36 };
const SVG_NS = "http://www.w3.org/2000/svg";

function askChartSvgEl(name, attrs = {}) {
  const el = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
  return el;
}

//: Round numbers for the axis: a step of 1, 2, 2.5 or 5 times a power of ten
//: (2.5 only from 25 up, so a count never ticks at a fraction), at most four
//: steps, the last at or above the top. A step of max / 4 put 310, 620 and
//: 930 on a 0 to 1,240 axis.
function askChartTicks(max) {
  if (max <= 4) return Array.from({ length: max + 1 }, (_, i) => i);
  const raw = max / 4;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw && Number.isInteger(s));
  const out = [];
  for (let tick = 0; tick < max + step; tick += step) out.push(tick);
  return out;
}

//: The axis is 36 of the chart's 640 units: four digits fit beside it, five
//: do not, so ten thousand and up is said in thousands.
function askChartTickLabel(tick) {
  return tick >= 10000 ? `${Math.round(tick / 1000)}k` : String(tick);
}

function askChartLabel(chart, label) {
  if (chart.by === "month") {
    const [y, m] = label.split("-").map(Number);
    return new Date(y, m - 1, 1).toLocaleDateString(undefined, { month: "short", year: "2-digit" });
  }
  if (chart.by === "day" || chart.by === "week") {
    return new Date(`${label}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  }
  return label.length > 12 ? `${label.slice(0, 11)}…` : label;
}

//: The words for one mark, spoken and shown: the period in full and the exact
//: value ("March 2026: 12 notes"). `chart.unit` is [one, many] for a count of
//: something other than notes (the Statistics page's feature uses).
function askChartTipText(chart, row) {
  let when = row.label;
  if (chart.by === "month") {
    const [y, m] = row.label.split("-").map(Number);
    when = new Date(y, m - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });
  } else if (chart.by === "day" || chart.by === "week") {
    when = new Date(`${row.label}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
  }
  const [one, many] = chart.unit || ["note", "notes"];
  return `${when}: ${row.value.toLocaleString()} ${row.value === 1 ? one : many}`;
}

//: Which mark an arrow key lands on; the ends stop rather than wrap.
function askChartStep(index, key, count) {
  if (key === "ArrowRight" || key === "ArrowDown") return Math.min(count - 1, index + 1);
  if (key === "ArrowLeft" || key === "ArrowUp") return Math.max(0, index - 1);
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return index;
}

//: A chart that follows its card draws at the card's width, so the text keeps
//: its size instead of scaling with the picture.
function askChartWidth(measured) {
  if (!measured) return ASK_CHART_W;
  return Math.max(320, Math.min(1400, Math.round(measured)));
}

function askChartSvg(chart, width = ASK_CHART_W) {
  const rows = chart.rows;
  const max = Math.max(1, ...rows.map((r) => r.value));
  const ticks = askChartTicks(max);
  const top = ticks[ticks.length - 1] || 1;
  const { top: pt, right: pr, bottom: pb, left: pl } = ASK_CHART_PAD;
  const plotW = width - pl - pr;
  const plotH = ASK_CHART_H - pt - pb;
  const y = (value) => pt + plotH - (value / top) * plotH;
  const svg = askChartSvgEl("svg", { viewBox: `0 0 ${width} ${ASK_CHART_H}`, class: "ask-chart-svg", role: chart.interactive ? "group" : "img" });
  svg.setAttribute("aria-label", `${chart.title}, as a ${chart.kind === "bar" ? "bar" : "line"} chart; the table below has the numbers`);
  for (const tick of ticks) {
    svg.appendChild(askChartSvgEl("line", { x1: pl, x2: width - pr, y1: y(tick), y2: y(tick), class: "ask-chart-grid" }));
    const text = askChartSvgEl("text", { x: pl - 6, y: y(tick) + 4, "text-anchor": "end", class: "ask-chart-axis" });
    text.textContent = askChartTickLabel(tick);
    svg.appendChild(text);
  }
  const slot = plotW / Math.max(1, rows.length);
  //: Every label when they fit, else every nth: a label per day of a month
  //: is thirty words on top of each other.
  const every = Math.max(1, Math.ceil(rows.length / Math.floor(plotW / 54)));
  const isBar = chart.kind === "bar";
  const barW = Math.max(2, Math.min(48, slot * 0.7));
  if (!isBar) {
    const points = rows.map((row, i) => `${(pl + slot * i + slot / 2).toFixed(1)},${y(row.value).toFixed(1)}`).join(" ");
    svg.appendChild(askChartSvgEl("polyline", { points, class: "ask-chart-line" }));
  }
  rows.forEach((row, i) => {
    const cx = pl + slot * i + slot / 2;
    if (i % every === 0) {
      const text = askChartSvgEl("text", { x: cx, y: ASK_CHART_H - pb + 16, "text-anchor": "middle", class: "ask-chart-axis" });
      text.textContent = askChartLabel(chart, row.label);
      svg.appendChild(text);
    }
    const mark = isBar
      ? askChartSvgEl("rect", { x: cx - barW / 2, y: y(row.value), width: barW, height: Math.max(0, pt + plotH - y(row.value)), rx: 3, class: "ask-chart-bar" })
      : askChartSvgEl("circle", { cx, cy: y(row.value), r: rows.length > 40 ? 1.5 : 3, class: "ask-chart-dot" });
    if (!chart.interactive) {
      const tip = askChartSvgEl("title");
      tip.textContent = `${row.label}: ${row.value}`;
      mark.appendChild(tip);
      svg.appendChild(mark);
      return;
    }
    //: One group per mark: a transparent hit area the whole height of its slot
    //: (a 3-unit dot is not a target), the mark, and the roving tab stop.
    const group = askChartSvgEl("g", {
      class: "ask-chart-pt",
      tabindex: i === 0 ? 0 : -1,
      role: chart.onPick ? "button" : "img",
      "aria-label": askChartTipText(chart, row),
      "data-i": i,
    });
    group.append(askChartSvgEl("rect", { x: cx - slot / 2, y: pt, width: slot, height: plotH, class: "ask-chart-hit" }), mark);
    svg.appendChild(group);
  });
  return svg;
}

function askChartTable(chart) {
  const wrap = document.createElement("details");
  wrap.className = "ask-chart-numbers";
  const summary = document.createElement("summary");
  summary.textContent = "The numbers";
  const table = document.createElement("table");
  table.className = "ask-chart-table";
  const head = table.createTHead().insertRow();
  //: `columns` names a chart that is not notes counted (the Statistics
  //: page's Most used: a feature and its uses).
  for (const name of chart.columns || [{ category: "Category", tag: "Tag" }[chart.by] || "When", "Notes"]) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = name;
    head.appendChild(th);
  }
  const body = table.createTBody();
  for (const row of chart.rows) {
    const tr = body.insertRow();
    tr.insertCell().textContent = row.label;
    tr.insertCell().textContent = String(row.value);
  }
  wrap.append(summary, table);
  return wrap;
}

//: The chart as a PNG: the SVG with its resolved colours written onto each
//: mark (a file has no stylesheet), on the card's own flat background.
async function askChartPng(svg, title) {
  const clone = svg.cloneNode(true);
  const live = [svg, ...svg.querySelectorAll("*")];
  const copies = [clone, ...clone.querySelectorAll("*")];
  live.forEach((el, i) => {
    const style = getComputedStyle(el);
    for (const prop of ["fill", "stroke", "stroke-width", "font-size", "font-family", "opacity"]) {
      copies[i].setAttribute(prop, style.getPropertyValue(prop));
    }
  });
  const wide = svg.viewBox.baseVal.width || ASK_CHART_W;
  clone.setAttribute("xmlns", SVG_NS);
  clone.setAttribute("width", wide * 2);
  clone.setAttribute("height", ASK_CHART_H * 2);
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const img = new Image();
    await new Promise((resolve, reject) => {
      img.onload = resolve;
      img.onerror = () => reject(new Error("Couldn't draw the chart."));
      img.src = url;
    });
    const canvas = document.createElement("canvas");
    canvas.width = wide * 2;
    canvas.height = ASK_CHART_H * 2;
    const ctx = canvas.getContext("2d");
    //: A flat card colour per theme, as the graph's PNG does: the page's own
    //: background is a gradient and a translucent card, neither a fill.
    ctx.fillStyle = document.documentElement.dataset.theme === "dark" ? "rgb(27, 30, 38)" : "rgb(255, 255, 255)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((resolve, reject) =>
      canvas.toBlob((made) => (made ? resolve(made) : reject(new Error("Couldn't save the chart."))), "image/png")
    );
    const name = `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "chart"}.png`;
    await saveFile(name, blob);
  } finally {
    URL.revokeObjectURL(url);
  }
}

//: Draws the chart for `question` into `host`, or leaves it hidden when the
//: question is not a count. `isCurrent` says whether this question is still
//: the one on screen, so a slow answer never draws over a newer one.
async function renderAskChart(question, host, isCurrent = () => true) {
  const answer = await apiJson("/charts/question", {
    method: "POST",
    body: JSON.stringify({ question }),
    readOnly: true,
    silent: true,
    //: Nobody pressed anything for the chart: a failure is the console's
    //: (`backgroundWriteFailed`), and the answer above it stands alone.
  }).catch(backgroundWriteFailed);
  if (!isCurrent()) return;
  drawAskChart(host, answer && answer.chart);
}

//: The drawing alone, from a chart object: the Ask box's fetched one above,
//: and a Chat answer's bar of counts (CHAT_PLAN decision 59, step 2: a
//: `chart` stream event from `realise.chart`, drawn by chat-attach.js).
function drawAskChart(host, chart) {
  if (!chart || !chart.rows || !chart.rows.length) {
    host.replaceChildren();
    host.classList.add("hidden");
    return;
  }
  const head = document.createElement("div");
  head.className = "ask-chart-head";
  const title = document.createElement("strong");
  title.className = "ask-chart-title";
  title.textContent = chart.title;
  const total = document.createElement("span");
  total.className = "muted text-sm";
  const source = chart.source || "from your notes";
  if (chart.total != null) total.textContent = `${chart.total.toLocaleString()} in all, ${source}`;
  else total.textContent = source[0].toUpperCase() + source.slice(1);
  const svg = askChartSvg(chart);
  const save = smallButton("ph:download-simple Save as PNG", "Save this chart as a picture", () =>
    askChartPng(host.querySelector(".ask-chart-svg"), chart.title).catch((error) => toast(error.message, true))
  );
  head.append(title, total, save);
  host.replaceChildren(head, svg, askChartTable(chart));
  host.classList.remove("hidden");
  if (chart.interactive) askChartWire(host, chart);
}

//: The Statistics page's charts (`chart.interactive`): a tooltip with the
//: period and exact value under the pointer or the keyboard's focus, arrow
//: keys between marks, a click or Enter handing the row to `chart.onPick`,
//: and a redraw at the card's width as it resizes.
function askChartWire(host, chart) {
  const tip = document.createElement("div");
  tip.className = "ask-chart-tip hidden";
  tip.setAttribute("aria-hidden", "true");
  host.appendChild(tip);
  const show = (group) => {
    tip.textContent = group.getAttribute("aria-label");
    tip.classList.remove("hidden");
    const at = group.getBoundingClientRect();
    const box = host.getBoundingClientRect();
    const half = tip.offsetWidth / 2;
    const mid = at.left + at.width / 2 - box.left;
    tip.style.left = `${Math.max(half, Math.min(box.width - half, mid))}px`;
    tip.style.top = `${at.top - box.top + at.height * 0.25}px`;
  };
  const hide = () => tip.classList.add("hidden");
  const groupOf = (event) => event.target.closest?.(".ask-chart-pt");
  const pick = (group) => chart.onPick?.(chart.rows[Number(group.dataset.i)], Number(group.dataset.i));
  host.addEventListener("pointerover", (event) => {
    const group = groupOf(event);
    if (group) show(group);
  });
  host.addEventListener("pointerout", (event) => {
    if (groupOf(event)) hide();
  });
  host.addEventListener("focusin", (event) => {
    const group = groupOf(event);
    if (group) show(group);
  });
  host.addEventListener("focusout", hide);
  host.addEventListener("click", (event) => {
    const group = groupOf(event);
    if (group) pick(group);
  });
  host.addEventListener("keydown", (event) => {
    const group = groupOf(event);
    if (!group) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      pick(group);
      return;
    }
    const from = Number(group.dataset.i);
    const to = askChartStep(from, event.key, chart.rows.length);
    if (to === from && !["Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const marks = [...host.querySelectorAll(".ask-chart-pt")];
    marks.forEach((mark, i) => mark.setAttribute("tabindex", i === to ? "0" : "-1"));
    marks[to].focus();
  });
  let drawn = ASK_CHART_W;
  const observer = new ResizeObserver(() => {
    //: Fires once while the host is still detached (it is built before it is
    //: placed): not a reason to stop watching.
    if (!host.isConnected) return;
    const old = host.querySelector(".ask-chart-svg");
    const measured = old ? old.getBoundingClientRect().width : 0;
    if (!measured) return;
    const width = askChartWidth(measured);
    if (Math.abs(width - drawn) < 8) return;
    drawn = width;
    const keep = old.contains(document.activeElement) ? document.activeElement.dataset.i : null;
    const next = askChartSvg(chart, width);
    old.replaceWith(next);
    hide();
    if (keep != null) next.querySelector(`.ask-chart-pt[data-i="${keep}"]`)?.focus();
  });
  observer.observe(host);
}
