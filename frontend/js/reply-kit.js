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
(() => {
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
    open.className = "ghost quiet small reply-panel-open";
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
  //: The strip as the chart recipe's line (`drawAskChart`, ask-chart.js): a
  //: value under the pointer and the keyboard, and the numbers in a fold (the
  //: owner, 2026-11-12: "I cant interact with or see the values").
  function replyTimelinePanel(event) {
    const host = document.createElement("div");
    host.className = "ask-chart reply-timeline";
    const labels = event.labels || [];
    const rows = (event.points || []).map((n, i) => ({ label: labels[i] ?? String(i), value: Number(n) || 0 }));
    ensureModule("askHistory").then(() => drawAskChart(host, { kind: "line", by: event.by, title: event.title || "Notes over time", rows, total: rows.reduce((sum, row) => sum + row.value, 0) }));
    return host;
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
    //: **The scientific keys** (INBOX 1579): four columns like the keypad, each inserting what it shows ("sin(" waits for its number), the last row the memory.
    sciKeys: [
      ["sin", "sin("], ["cos", "cos("], ["tan", "tan("], ["π", "pi"],
      ["sin⁻¹", "asin("], ["cos⁻¹", "acos("], ["tan⁻¹", "atan("], ["e", "e"],
      ["ln", "ln("], ["log", "log("], ["√", "sqrt("], ["x²", "^2"],
      ["xʸ", "^"], ["n!", "!"], ["|x|", "abs("], ["eˣ", "exp("],
      ["MC", "mc"], ["MR", "mr"], ["M+", "m+"], ["M−", "m-"],
    ],
    sciNames: {
      "sin(": "Sine", "cos(": "Cosine", "tan(": "Tangent", pi: "Pi", "asin(": "Inverse sine", "acos(": "Inverse cosine", "atan(": "Inverse tangent", e: "e",
      "ln(": "Natural logarithm", "log(": "Logarithm, base 10", "sqrt(": "Square root", "^2": "Squared", "^": "To the power of", "!": "Factorial",
      "abs(": "Absolute value", "exp(": "e to the power of", mc: "Memory clear", mr: "Memory recall", "m+": "Memory add", "m-": "Memory subtract",
    },
    //: **A `.tabs-line` of exclusive choices** (DESIGN.md, "A popup that chooses a kind": no pills in popups, INBOX 715 and 1622): words with a 2px line under the chosen one, `role="tab"` and `aria-selected`, one Tab stop with the arrows and Home and End walking it. The ring is `:focus-visible` only (the strip's own rule), so a press with the pointer draws none. `sync(value)` moves the choice.
    seg(label, choices, value, onChange) {
      const seg = document.createElement("div");
      seg.className = "tabs-line popup-kinds calc-seg";
      seg.setAttribute("role", "tablist");
      seg.setAttribute("aria-label", label);
      //: A choice's third element is the short form it shows (Deg, Rad: the head fits one row at 390 with no width query); the full words stay its name and its title.
      const buttons = choices.map(([key, words, short]) => {
        const b = document.createElement("button");
        b.type = "button";
        b.setAttribute("role", "tab");
        b.dataset.value = key;
        b.textContent = short || words;
        if (short) {
          b.setAttribute("aria-label", words);
          b.title = words;
        }
        b.addEventListener("click", () => onChange(key));
        return b;
      });
      seg.addEventListener("keydown", (event) => {
        const at = buttons.indexOf(document.activeElement);
        const to = { ArrowRight: (at + 1) % buttons.length, ArrowLeft: (at + buttons.length - 1) % buttons.length, Home: 0, End: buttons.length - 1 }[event.key];
        if (at < 0 || to === undefined) return;
        event.preventDefault();
        onChange(buttons[to].dataset.value);
        buttons[to].focus();
      });
      const sync = (now) => {
        for (const b of buttons) {
          const chosen = b.dataset.value === now;
          b.setAttribute("aria-selected", String(chosen));
          b.classList.toggle("active", chosen);
          b.tabIndex = chosen ? 0 : -1;
        }
      };
      seg.append(...buttons);
      sync(value);
      return { seg, sync };
    },
  };

  //: The head '?' (INBOX 1530 g M6): the dialog is worked out by the app with no model; one line per tab, then where Insert writes.
  const REPLY_CALC_HELP = [
    "Worked out by the app, with no model.",
    "Sum: type or key a sum, a percentage or a conversion (12 * (3 + 4), 15% of 80, 5 km to miles). It is drawn as maths under the box as you type, and a preview shows once it is a whole sum; Enter or = keeps it. Scientific adds sine, cosine, tangent and their inverses, logs, powers, roots, a factorial, pi and e, with Degrees or Radians and a memory (MC, MR, M+, M-).",
    "Units: pick a kind, an amount and two units. Currency rates are set by hand and dated, not today's rate. Time zone takes a time of day and two places (09:00, London, Tokyo) and reads each place's clock from this computer, so it works offline.",
    "Equation: click a dotted box to fill it; a box you empty again comes back. / makes a fraction, ^ and _ a power or a subscript, and LaTeX such as \\frac or \\alpha turns into the symbol as you type it. Pick a structure or a symbol from the palette; a selection goes into the first box. The row of groups jumps to one; Pin makes a tile a favourite, and Recent shows the last ones used. Inline sits in a sentence, Display on its own line. Click a drawn equation in a note, or open this with the cursor inside one, to edit it.",
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
    time: ["hours", "minutes"], data: ["gigabytes", "megabytes"], currency: ["USD", "EUR"], timezone: ["London", "Tokyo"],
  };

  const REPLY_CALC_NAMES = { clear: "Clear", "/": "Divide", "*": "Times", "-": "Minus", "+": "Plus", "%": "Percent", equals: "Work it out", ".": "Point" };

  function replyCalcPanel(event) {
    const { panel, head } = replyPanelShell("reply-calc", "Calculator", "ph:calculator");
    const open = document.createElement("button");
    open.type = "button";
    open.className = "ghost quiet small reply-panel-open";
    setLabel(open, "ph:arrow-square-out Open the calculator");
    open.title = "Work it out again, change it, or convert units";
    open.addEventListener("click", () => openCalculator(event.input || ""));
    head.appendChild(open);
    // "/calc" with nothing after it asks for the calculator itself.
    if (!event.input) requestAnimationFrame(() => openCalculator());
    return panel;
  }

  async function replyCalcWork(text) {
    //: A typeset minus (U+2212), pasted from a note, is the sign the reader knows.
    const asked = String(text || "").replace(/\u2212/g, "-").trim();
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
  //: `only` draws that one tab with no strip (the Convert widget, INBOX 1617).
  openCalculator.inline = (host, mode = "work", { only = false } = {}) => replyCalcBuild(host, "", mode, { inline: true, only });

  function replyCalcBuild(card, input, mode = "work", { target = null, close = () => {}, inline = false, only = false } = {}) {
    //: One height for all three tabs, the strip and the action row pinned and the panes between them scrolling (INBOX 1530 g M2: on a bottom-anchored sheet the strip moved 188 px between tabs and 4 to 40 px on a result).
    card.classList.add("calc-card");
    if (inline) card.classList.add("calc-inline");
    //: An inline calculator has no Equation tab (the field needs its own bundle and a box to write into).
    let kinds = inline ? replyCalc.tabs.filter(([key]) => key !== "equation") : replyCalc.tabs;
    if (!kinds.some(([key]) => key === mode)) mode = "work";
    if (only) kinds = kinds.filter(([key]) => key === mode);
    //: A tab strip, not a pill (DESIGN.md, "A popup that chooses a kind").
    const modes = document.createElement("div");
    modes.className = "tabs-line popup-kinds calc-modes";
    modes.setAttribute("role", "tablist");
    modes.setAttribute("aria-label", "Calculator mode");
    const actions = replyCalcActions(target, close, inline);
    const equation = inline ? null : replyCalcEquation(target, close, actions);
    const made = { work: () => replyCalcWorkPane(input, actions), convert: () => replyCalcConvertPane(actions), equation: () => equation.pane };
    const panes = Object.fromEntries(kinds.map(([key]) => [key, made[key]()]));
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
      pane.classList.toggle("is-off", key !== mode);
    }
    const select = (key, { focus = true } = {}) => {
      for (const other of tabs) {
        const on = other.dataset.tab === key;
        other.setAttribute("aria-selected", String(on));
        other.classList.toggle("active", on);
        other.tabIndex = on ? 0 : -1;
      }
      for (const [name, pane] of Object.entries(panes)) pane.classList.toggle("is-off", name !== key);
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
    card.append(...(only ? [] : [modes]), wrap, actions.el);
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
    const asEquation = smallButton("ph:function Insert as equation", "Write the sum and its result as an equation", () => act("equation"));
    const insert = smallButton("Insert", "Write the result into the text", () => act("insert"), false);
    insert.classList.add("primary");
    for (const button of [copy, asEquation, insert]) button.setAttribute("aria-describedby", id);
    //: The dialog foot: the one filled Insert last, Copy the lone bordered secondary beside it, and the third (a different kind of write) a quiet one at the start of the row.
    asEquation.classList.add("quiet", "calc-as-equation");
    row.append(asEquation, copy, insert);
    //: A widget has no Insert, so Copy is alone in its row and takes no edge.
    if (inline) copy.classList.add("quiet");
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

    //: Whether a typed sum is still being written: it ends in a sign, a joining word ("5 km to") or has a bracket left open. Such a sum is not an error yet (INBOX 1579).
    pending(text) {
      const sum = String(text || "").trim();
      if (!sum) return false;
      const open = (sum.match(/\(/g) || []).length > (sum.match(/\)/g) || []).length;
      return open || /[-+*/×÷^(√∛]$/.test(sum) || /\b(?:of|to|in|into|as|from|plus|minus|times|over|by|and|per|sin|cos|tan|asin|acos|atan|sinh|cosh|tanh|ln|log|sqrt|cbrt|exp|abs)$/i.test(sum);
    },

    //: **The sum as typeset maths, as it is typed** (INBOX 1579): `12*(3+4)` as 12 × (3 + 4), `2^10` with a raised 10, `sqrt(16)` under a root, `pi` as π, `sin(30)` upright, words in text. It reads whatever is typed, unfinished or not, and never throws: a sign with nothing after it leaves an empty box, not a failure. The raw text stays in the field; this is only what is drawn under it. Returns TeX, "" for nothing.
    live(text) {
      const names = {
        sin: "\\sin", cos: "\\cos", tan: "\\tan", sinh: "\\sinh", cosh: "\\cosh", tanh: "\\tanh", ln: "\\ln", log: "\\log", lg: "\\lg", exp: "\\exp",
        asin: "\\arcsin", arcsin: "\\arcsin", acos: "\\arccos", arccos: "\\arccos", atan: "\\arctan", arctan: "\\arctan", log2: "\\log_{2}", log10: "\\log_{10}",
      };
      const consts = { pi: "\\pi", π: "\\pi", tau: "\\tau", τ: "\\tau", e: "e" };
      //: The empty box the math renderer draws where a sign has nothing after it yet.
      const slot = "\u25a1";
      //: The bracket that opens at `from`: its inside and where it ends (a bracket still open runs to the end).
      const inside = (s, from) => {
        let depth = 0;
        for (let j = from; j < s.length; j++) {
          if (s[j] === "(") depth++;
          else if (s[j] === ")" && !--depth) return [s.slice(from + 1, j), j + 1];
        }
        return [s.slice(from + 1), s.length];
      };
      //: What a root or a power takes: a bracket, or the number or name right after it.
      const operand = (s, at) => {
        if (s[at] === "(") {
          const [body, end] = inside(s, at);
          return [walk(body) || slot, end];
        }
        const m = /^(?:-?\d[\d.]*|[A-Za-z]+|[πτ])/.exec(s.slice(at));
        if (!m) return [slot, at];
        const w = m[0].toLowerCase();
        return [w in consts ? consts[w] : m[0], at + m[0].length];
      };
      const known = (w) => w in names || w in consts || w === "sqrt" || w === "cbrt";
      const walk = (s) => {
        let out = "";
        let word = "";
        const flush = () => {
          if (word) out += `${out ? "\\;" : ""}\\text{${word}}\\;`;
          word = "";
        };
        for (let i = 0; i < s.length; ) {
          const c = s[i];
          const rest = s.slice(i);
          let m;
          if (/\s/.test(c)) i++;
          else if ((m = /^[A-Za-z]+[0-9]{0,2}|^[πτ]/.exec(rest))) {
            //: A whole word, or a name with figures run on ("log10", "e2"); never the front of a longer word ("tangent").
            let w = m[0].toLowerCase();
            if (!known(w)) w = w.replace(/[0-9]+$/, "");
            if (!known(w)) {
              word += `${word ? " " : ""}${m[0]}`;
              i += m[0].length;
              continue;
            }
            flush();
            i += w.length;
            if (w === "sqrt" || w === "cbrt") {
              const [body, end] = operand(s, i);
              out += w === "cbrt" ? `\\sqrt[3]{${body}}` : `\\sqrt{${body}}`;
              i = end;
            } else out += w in names ? `${names[w]} ` : consts[w];
          } else {
            flush();
            i++;
            if (/\d|\./.test(c)) {
              const n = /^(?:\d[\d,]*\.?\d*|\.\d+)/.exec(rest)?.[0] || c;
              out += n.replace(/,/g, "");
              i += n.length - 1;
            } else if ("*×·⋅".includes(c)) out += " \\times ";
            else if ("/÷".includes(c)) out += " \\div ";
            else if (c === "−" || c === "-") out += "−";
            else if ("+=()!".includes(c)) out += c;
            else if (c === "%") out += "\\%";
            else if (c === "²" || c === "³") out += c === "²" ? "^{2}" : "^{3}";
            else if (c === "°") out += "^{\\circ}";
            else if (c === "^") {
              const [body, end] = operand(s, i);
              out += `^{${body}}`;
              i = end;
            } else if (c === "√" || c === "∛") {
              const [body, end] = operand(s, i);
              out += c === "∛" ? `\\sqrt[3]{${body}}` : `\\sqrt{${body}}`;
              i = end;
            } else if (/[^\x00-\x7f]/.test(c)) out += `\\text{${c}}`;
          }
        }
        flush();
        return out.replace(/(?:\\;)+$/, "").trim();
      };
      return walk(String(text || ""));
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
          .replace(/\s*[*×]\s*/g, () => " \\times ")
          .replace(new RegExp(`${group}\\s*[/÷]\\s*${group}`, "g"), (_all, top, bottom) => `\\frac{${bare(top)}}{${bare(bottom)}}`)
          .replace(/\s*[/÷]\s*/g, " \\div ")
          .replace(new RegExp(String.raw`\^\s*(-?\d[\d.,]*|\([^()]*\))`, "g"), (_all, power) => `^{${bare(power)}}`)
          .replace(/%/g, "\\%")
          .trim();
      };
      return `${side(String(input || "").trim())} = ${side(String(figure || "").trim())}`;
    },
  };

  //: **The scientific reader** (INBOX 1579): a sum with functions, constants and a factorial, read by a small
  //: tokenizer and a recursive descent, never `eval` or `Function`. `evaluate(text, {angle})` answers
  //: `{value, angled}` or throws an `Error` whose `.sci` is true: `.notMath` when the text is not a sum at all
  //: (words, units: the server's reader gets it) and a message otherwise ("divide by zero").
  calcTex.sci = {
    functions: {
      sin: "trig", cos: "trig", tan: "trig", asin: "arc", acos: "arc", atan: "arc",
      sinh: Math.sinh, cosh: Math.cosh, tanh: Math.tanh,
      ln: Math.log, log: Math.log10, log2: Math.log2, lg: Math.log10, sqrt: Math.sqrt, cbrt: Math.cbrt,
      abs: Math.abs, exp: Math.exp, floor: Math.floor, ceil: Math.ceil, round: Math.round,
    },
    aliases: { arcsin: "asin", arccos: "acos", arctan: "atan", log10: "log", "√": "sqrt", "∛": "cbrt" },
    constants: { pi: Math.PI, π: Math.PI, e: Math.E, tau: 2 * Math.PI, τ: 2 * Math.PI },

    tokens(text) {
      const out = [];
      const src = String(text).replace(/(\d),(?=\d{3}\b)/g, "$1").replace(/²/g, "^2").replace(/³/g, "^3").replace(/[−–]/g, "-").replace(/[×·⋅]/g, "*").replace(/÷/g, "/");
      const bad = (words, notMath) => Object.assign(new Error(words), { sci: true, notMath });
      for (let i = 0; i < src.length; ) {
        const c = src[i];
        if (/\s/.test(c)) i++;
        else if (/[0-9.]/.test(c)) {
          const m = /^(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+(?![\w]))?/.exec(src.slice(i));
          if (!m) throw bad("A number is not finished.", false);
          out.push({ n: Number(m[0]) });
          i += m[0].length;
        } else if (/[a-zA-Zπτ√∛]/.test(c)) {
          const word = /^(?:[a-zA-Z]+[0-9]{0,2}|[πτ√∛])/.exec(src.slice(i))[0];
          const sci = calcTex.sci;
          const known = (w) => w in sci.functions || w in sci.aliases || w in sci.constants;
          //: A word may run into what follows ("sin30", "sinpi"): the longest known name first.
          let cut = word.length;
          while (cut > 0 && !known(word.slice(0, cut).toLowerCase())) cut--;
          if (!cut) throw bad("Not a sum.", true);
          const low = word.slice(0, cut).toLowerCase();
          out.push(low in sci.constants ? { n: sci.constants[low], c: true } : { f: sci.aliases[low] || low });
          i += cut;
        } else if ("+-*/^()!%".includes(c)) {
          out.push({ op: c });
          i++;
        } else throw bad("Not a sum.", true);
      }
      return out;
    },

    evaluate(text, { angle = "deg" } = {}) {
      const sci = calcTex.sci;
      const tokens = sci.tokens(text);
      const bad = (words) => Object.assign(new Error(words), { sci: true });
      let at = 0;
      let angled = false;
      const peek = () => tokens[at];
      const isOp = (...ops) => peek()?.op !== undefined && ops.includes(peek().op);
      const starts = (t) => t && (t.n !== undefined || t.f !== undefined || t.op === "(");
      //: What may follow a value with no sign between ("2pi", "3(4)", "2sin(30)"); two plain numbers side by side are not a product.
      const joins = (t) => t && (t.c || t.f !== undefined || t.op === "(");
      const toRad = (x) => (angle === "deg" ? (x * Math.PI) / 180 : x);
      const fromRad = (x) => (angle === "deg" ? (x * 180) / Math.PI : x);
      const fact = (x) => {
        if (!Number.isInteger(x) || x < 0 || x > 170) throw bad("A factorial needs a whole number from 0 to 170.");
        let r = 1;
        for (let k = 2; k <= x; k++) r *= k;
        return r;
      };
      const apply = (name, x) => {
        const f = sci.functions[name];
        if (!f) throw bad(`${name} is not a function here.`);
        if (f === "trig") {
          angled = true;
          const r = toRad(x);
          if (name === "tan" && Math.abs(Math.cos(r)) < 1e-12) throw bad("tan is undefined there.");
          const v = Math[name](r);
          return Math.abs(v) < 1e-12 ? 0 : v;
        }
        if (f === "arc") {
          angled = true;
          if (Math.abs(x) > 1 && name !== "atan") throw bad(`${name} needs a number from -1 to 1.`);
          return fromRad(Math[name](x));
        }
        if ((name === "ln" || name === "log" || name === "log2" || name === "lg") && x <= 0) throw bad("A logarithm needs a number above 0.");
        if (name === "sqrt" && x < 0) throw bad("There is no real square root of a negative number.");
        return f(x);
      };
      const primary = () => {
        const t = tokens[at++];
        if (!t) throw bad("The sum is not finished.");
        if (t.n !== undefined) return t.n;
        if (t.f) {
          //: A function takes its bracket, or the one number, constant or function after it ("sin 30", "sqrt16").
          if (isOp("(")) return apply(t.f, primary());
          if (starts(peek()) && !isOp("(")) return apply(t.f, postfix(true));
          throw bad(`${t.f} needs a number after it.`);
        }
        if (t.op === "(") {
          const v = expr();
          if (!isOp(")")) throw bad("A bracket is not closed.");
          at++;
          return v;
        }
        throw bad(t.op === ")" ? "A bracket closes with none open." : "The sum is not finished.");
      };
      const postfix = (bare = false) => {
        let v = primary();
        while (true) {
          if (isOp("!")) {
            at++;
            v = fact(v);
          } else if (!bare && isOp("%") && !starts(tokens[at + 1])) {
            at++;
            v /= 100;
          } else return v;
        }
      };
      const power = () => {
        const base = postfix();
        if (!isOp("^")) return base;
        at++;
        return base ** unary();
      };
      const unary = () => {
        if (isOp("-")) return (at++, -unary());
        if (isOp("+")) return (at++, unary());
        return power();
      };
      const term = () => {
        let v = unary();
        while (true) {
          if (isOp("*")) (at++, (v *= unary()));
          else if (isOp("/")) {
            at++;
            const d = unary();
            if (d === 0) throw bad("Cannot divide by zero.");
            v /= d;
          } else if (isOp("%") && starts(tokens[at + 1])) {
            at++;
            const d = unary();
            if (d === 0) throw bad("Cannot divide by zero.");
            v %= d;
          } else if (joins(peek())) v *= unary();
          else return v;
        }
      };
      const expr = () => {
        let v = term();
        while (isOp("+", "-")) v = tokens[at++].op === "+" ? v + term() : v - term();
        return v;
      };
      if (!tokens.length) throw Object.assign(new Error("Nothing to work out."), { sci: true, notMath: true });
      const value = expr();
      if (at < tokens.length) throw bad(tokens[at].op === ")" ? "A bracket closes with none open." : "Put a sign between the numbers.");
      if (!Number.isFinite(value)) throw bad("That is too large to show.");
      return { value, angled };
    },

    //: A value in the words the server's reader uses: twelve significant figures, no float dust ("0.1 + 0.2" is 0.3), commas by thousands.
    format(value) {
      const v = Number(value.toPrecision(12));
      if (Math.abs(v) >= 1e15 || (v !== 0 && Math.abs(v) < 1e-6)) return String(v).replace("e+", "e");
      return v.toLocaleString("en-GB", { maximumFractionDigits: 12 });
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
    //: **Standard or Scientific** (INBOX 1579): two choices in view, remembered with the angle unit and the memory in this browser's prefs. Scientific adds the function keys and reads sums with trig, logs, powers, roots, a factorial, pi and e (`calcTex.sci`, no `eval`); anything it does not read as a sum (a percentage of, a conversion, a date) still goes to the app's own reader.
    const saved = prefs.json("calc-sci", {});
    const mode = { on: saved.on === true, angle: saved.angle === "rad" ? "rad" : "deg", memory: Number.isFinite(saved.memory) ? saved.memory : 0 };
    const keep = () => prefs.setJSON("calc-sci", mode);
    //: **One head row** (INBOX 1584): the kind at the start, the angle unit beside it in Scientific only, the memory's value at the end. The angle unit's words shorten to Deg and Rad below 26rem (a third element of a choice) so the row stays one row at 390.
    const head = document.createElement("div");
    head.className = "calc-head";
    const kind = replyCalc.seg("Calculator kind", [["standard", "Standard"], ["scientific", "Scientific"]], mode.on ? "scientific" : "standard", (value) => setMode(value === "scientific"));
    const angle = replyCalc.seg("Angle unit", [["deg", "Degrees", "Deg"], ["rad", "Radians", "Rad"]], mode.angle, (value) => {
      mode.angle = value;
      keep();
      angle.sync(value);
      rerun();
    });
    const memory = document.createElement("span");
    memory.className = "muted calc-memory";
    memory.setAttribute("role", "status");
    head.append(kind.seg, angle.seg, memory);
    //: **The sum as typeset maths, as it is typed** (INBOX 1579): × ÷ − and raised powers drawn by the document renderer, under the field. The field keeps the raw text, which is what is edited and read aloud, so this is hidden from a screen reader.
    const typeset = document.createElement("div");
    typeset.className = "calc-typeset";
    typeset.setAttribute("aria-hidden", "true");
    const paint = () => {
      const tex = calcTex.live(box.value);
      let drawn = null;
      //: `docMathRender` is in this bundle (documents-math.js, listed before this file), never a guard.
      if (tex) {
        try {
          drawn = docMathRender(tex, false);
        } catch {
          drawn = null;
        }
      }
      typeset.replaceChildren(...(drawn ? [drawn] : []));
    };
    box.addEventListener("input", paint);
    paint();
    const out = replyCalcResult();
    //: Restoring puts the sum back in the box (a preview, not a keep), in the kind it was worked out in; Copy writes the figure.
    const history = replyCalcHistory("work", {
      label: (row) => `${row.input} = ${calcFigure(row.answer, false)}`,
      copy: (row) => calcFigure(row.answer, true),
      restore: (row) => {
        if (row.sci && !mode.on) setMode(true);
        box.value = row.input;
        box.dispatchEvent(new Event("input"));
        box.focus();
      },
    });
    let timer = 0;
    let asked = 0;
    //: The result on show, for the action row.
    let last = null;
    //: A sum read by the scientific reader, in the server's shape (`answer` "sin(30) is 0.5."); null when the text is not a sum at all, which the app's reader then takes.
    const sciRead = (text) => {
      try {
        const got = calcTex.sci.evaluate(text, { angle: mode.angle });
        return { answer: `${text.trim()} is ${calcTex.sci.format(got.value)}.`, read_as: got.angled ? `angles in ${mode.angle === "deg" ? "degrees" : "radians"}` : "" };
      } catch (error) {
        if (error.sci) return error.notMath ? null : { error: error.message };
        throw error;
      }
    };
    const rerun = () => {
      if (!box.value.trim()) return;
      clearTimeout(timer);
      run(false);
    };
    const showMemory = () => {
      memory.textContent = mode.on && mode.memory ? `Memory ${calcTex.sci.format(mode.memory)}` : "";
    };
    //: MC clears, MR types the stored number, M+ and M− add or take away the value of what is in the box.
    const onKey = (act) => {
      if (act === "mc") mode.memory = 0;
      else if (act === "mr") return String(mode.memory);
      else if (act === "m+" || act === "m-") {
        const got = sciRead(box.value);
        const value = got && !got.error ? calcTex.sci.evaluate(box.value, { angle: mode.angle }).value : null;
        if (value === null) {
          toast("Work out a sum first, then store it.", "info");
          return false;
        }
        mode.memory = Number((mode.memory + (act === "m+" ? value : -value)).toPrecision(12));
      } else return undefined;
      keep();
      showMemory();
      return false;
    };
    actions.provide("work", actions.result(() => last, { what: "the result", needs: "a result", first: "Work out a sum first." }));
    const run = async (final) => {
      const mine = ++asked;
      clearTimeout(out._late);
      //: **No error while a sum is being typed** (INBOX 1579, "55*9+" showed "That is not a sum"): a sum that ends in a sign or an open bracket is unfinished, not wrong, so the preview waits for the next key; any other error waits for a pause (about 800 ms with the key delay), or Enter, which says the sum is unfinished.
      if (!final && calcTex.pending(box.value)) {
        replyCalcShow(out, null);
        last = null;
        return actions.sync();
      }
      try {
        const got = (mode.on && sciRead(box.value)) || (await replyCalcWork(box.value));
        if (mine !== asked) return;
        if (final && got?.error && calcTex.pending(box.value)) got.error = "That sum is not finished. Add what comes after the last sign.";
        if (!final && got?.error) {
          replyCalcShow(out, null);
          last = null;
          actions.sync();
          out._late = setTimeout(() => mine === asked && replyCalcShow(out, got, { final }), 550);
          return;
        }
        replyCalcShow(out, got, { final, now: final });
        last = got?.answer && !got.error ? { input: box.value.trim(), answer: got.answer } : null;
        actions.sync();
        if (final && last) history.record({ key: last.input, input: last.input, answer: last.answer, ...(mode.on ? { sci: true } : {}) });
      } catch (error) {
        if (mine !== asked) return;
        replyCalcShow(out, { error: error.message }, { final, now: final });
        last = null;
        actions.sync();
      }
    };
    box.addEventListener("input", () => {
      clearTimeout(timer);
      clearTimeout(out._late);
      timer = setTimeout(() => run(false), 250);
    });
    box.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      clearTimeout(timer);
      run(true);
    });
    const equals = () => {
      clearTimeout(timer);
      run(true);
    };
    const keys = replyCalcKeypad(box, equals);
    const sciKeys = replyCalcKeypad(box, equals, { keys: replyCalc.sciKeys, names: replyCalc.sciNames, label: "Scientific keys", extra: "calc-keys-sci", onKey });
    const setMode = (on) => {
      mode.on = on;
      keep();
      sciKeys.classList.toggle("hidden", !on);
      //: Scientific lays the function keys beside the digits when the card is wide enough (reply-kit-lazy.css, `.is-sci`), so its card is no taller than Standard's.
      pane.classList.toggle("is-sci", on);
      angle.seg.classList.toggle("hidden", !on);
      kind.sync(on ? "scientific" : "standard");
      showMemory();
      box.placeholder = on ? "sin(30), 2 * pi, sqrt(16), 5!" : "12 * (3 + 4), 15% of 80, 5 km to miles";
      rerun();
    };
    setMode(mode.on);
    pane.append(box, typeset, head, out, sciKeys, keys, history.el);
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
  function replyCalcKeypad(box, equals, { keys: layout = REPLY_CALC_KEYS, names = REPLY_CALC_NAMES, label = "Keypad", extra = "", onKey = null } = {}) {
    const pad = document.createElement("div");
    pad.className = `key-grid calc-keys ${extra}`.trim();
    pad.setAttribute("role", "group");
    pad.setAttribute("aria-label", label);
    const keys = layout.map(([face, act], i) => {
      const key = document.createElement("button");
      key.type = "button";
      // A key of a `.key-grid`: the quiet inset fill, operators tinted, and `=` the grid's one filled key (the dialog's own is Insert, in the foot).
      key.className = `calc-key${/^[-+*/%]$/.test(act) ? " is-op" : ""}${act === "equals" ? " is-equals" : ""}`;
      setLabel(key, face);
      key.tabIndex = i === 0 ? 0 : -1;
      if (names[act]) key.setAttribute("aria-label", names[act]);
      key.addEventListener("click", () => {
        if (act === "equals") return equals();
        //: A key with its own work (the memory) answers `false` when it typed nothing, or the text to type instead.
        const handled = onKey ? onKey(act) : undefined;
        if (handled === false) return;
        const text = typeof handled === "string" ? handled : act;
        if (text === "clear") box.value = "";
        else {
          const start = box.selectionStart ?? box.value.length;
          const end = box.selectionEnd ?? box.value.length;
          box.setRangeText(text, start, end, "end");
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
    toggle.className = "ghost small disclosure-row calc-log-toggle";
    const count = document.createElement("span");
    count.className = "calc-log-count";
    const note = document.createElement("span");
    note.className = "muted calc-log-note";
    const clear = smallButton("Clear", "Clear the history", () => {
      const before = list;
      set([]);
      toastAction("History cleared.", "Undo", () => set(before), { ms: 10000, record: false });
    });
    clear.classList.add("quiet");
    const rows = document.createElement("ul");
    rows.className = "calc-history";
    rows.id = `calc-history-${tab}-${replyCalc.opened}`;
    rows.setAttribute("aria-label", "Earlier answers");
    toggle.setAttribute("aria-controls", rows.id);
    //: The one disclosure row (DESIGN.md): the caret first, History, its count as a muted badge, and Clear at the end of the same line as the quiet text action.
    const caret = document.createElement("i");
    caret.className = "ph ph-caret-down contents-caret";
    caret.setAttribute("aria-hidden", "true");
    toggle.append(caret, "History", count);
    bar.append(toggle, clear);
    el.append(bar, note, rows);
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
      again.className = "ghost quiet small calc-again";
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
      count.textContent = String(list.length);
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
      //: A time zone takes a time of day, not a number; the type follows the kind and the figure starts at a morning.
      const zone = kind.value === "timezone";
      if (zone !== (amount.type === "time")) {
        amount.type = zone ? "time" : "number";
        amount.value = zone ? "09:00" : "1";
        amount.setAttribute("aria-label", zone ? "Time of day" : "Amount");
      }
      const names = replyCalc.units?.[kind.value] || [];
      const [one, two] = REPLY_CALC_PAIRS[kind.value] || [];
      fill(from, names, one);
      fill(to, names, two || names[1]);
      const dated = new Date(`${replyCalc.units?.rates_date}T12:00`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
      note.textContent = kind.value === "currency" ? `Rates from ${dated}, set by hand: not today's rate.` : zone ? "Today's date, read from this computer's clock." : "";
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
        kind.replaceChildren(...kinds.map((key) => new Option(key === "timezone" ? "Time zone" : key[0].toUpperCase() + key.slice(1), key)));
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

    //: A reopened chat passes only its bubble (INBOX 1693): the answers and the head are found in it.
    if (!answers && opts.bubble) answers = opts.bubble.querySelectorAll(".bubble-answer");
    if (!opts.head && opts.bubble) opts = { engine: true, ...opts, head: opts.bubble.querySelector(".msg-role") };
    const list = (answers instanceof Element ? [answers] : [...(answers || [])]).filter((el) => el?.isConnected);
    if (!list.length) return;
    //: A composed reply only (B1): a model's own answer is never folded.
    if (opts.composed) for (const answer of list) replyFoldLong(answer);
    replyNotePreviews(list);
    if (opts.head && list.some((answer) => answer.textContent.trim())) replyByline(opts.head, opts);
    if (opts.why) ensureModule("askCompose").then(() => drawWhyTrail(opts.records, opts.why)).catch(() => {});
    if (opts.composed) replyReveal(list);
    if (opts.unsupported) renderToolsUnsupportedNotice(opts.bubble, opts.unsupported);
    if (opts.trimmed) renderHistoryTrimmedNotice(opts.bubble, opts.trimmed);
    if (opts.match_info) replyRecordCards($("raw-results"), null, opts.match_info);
  }

  //: **A Matching records card is a title, two lines, one quiet facts line and a
  //: reason** (INBOX 1735, the owner: "messy and unprofessional"). The note card
  //: it is built from carries a chip lane for the Notes list (a fixed grid with
  //: empty slots, bare icons, two scores, one link chip a row); here it is
  //: replaced by one line of words, `category · date · score`, each present only
  //: when it has something to say. The links fold into one "N links" row that
  //: opens the chips, and the excerpt is two lines with a Show more. Styled in
  //: reply-kit-lazy.css (`.record-card`), so boot pays nothing.
  //:
  //: **And why each card is there, in words** (INBOX 1310, the owner: "it has no
  //: frame of reference for how related each shown matching record is or why it
  //: was shown"): the server's `match_info[id].why`, one plain secondary line
  //: under the facts. It arrives when the answer is final (`replyFinish`, with
  //: no `entries`), the cards when the records do. One function, its helpers
  //: nested: the shared scope is capped (test_global_scope_ratchet).
  function replyRecordCards(list, entries, info, scored) {
    const byId = new Map((entries || []).map((entry) => [String(entry.id), entry]));
    //: Two lines, then Show more (the note card's own toggle when it drew one).
    const excerpt = (li) => {
      const body = li.querySelector(":scope > .entry-content");
      if (!body || li.querySelector(":scope > .entry-more")) return;
      body.classList.add("entry-clamped");
      const more = document.createElement("button");
      more.type = "button";
      more.className = "entry-more";
      more.textContent = "Show more";
      more.addEventListener("click", (event) => {
        event.stopPropagation();
        const clamped = body.classList.toggle("entry-clamped");
        more.textContent = clamped ? "Show more" : "Show less";
      });
      body.after(more);
      //: Measured, not guessed, by the note card's own observer: a card drawn in
      //: a hidden tab reads 0 and waits, and a text that fits loses its button.
      body.unclip = () => {
        noteClampFit.unobserve(body);
        body.classList.remove("entry-clamped");
        more.remove();
      };
      noteClampFit.observe(body);
    };
    //: Every link behind one "N links" row that opens the chips.
    const folded = (li) => {
      const links = li.querySelector(":scope > .entry-links");
      if (!links) return;
      links.querySelector(".entry-links-more")?.remove();
      links.classList.add("show-all", "hidden");
      const count = links.querySelectorAll(".link-connection").length;
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "ghost small disclosure-row record-links-toggle";
      toggle.textContent = `${count} link${count === 1 ? "" : "s"}`;
      toggle.setAttribute("aria-expanded", "false");
      toggle.title = "Show the notes this one is linked to";
      toggle.addEventListener("click", (event) => {
        event.stopPropagation();
        toggle.setAttribute("aria-expanded", String(!links.classList.toggle("hidden")));
      });
      links.before(toggle);
    };
    for (const li of list.querySelectorAll(":scope > li[data-id]")) {
      const old = li.querySelector(":scope > .entry-meta");
      if (!li.classList.contains("record-card") && old && byId.has(li.dataset.id)) {
        li.classList.add("record-card");
        const line = document.createElement("div");
        line.className = "record-meta";
        const fact = (className, text, title) => {
          const span = document.createElement("span");
          span.className = className;
          span.textContent = text;
          span.title = title;
          line.appendChild(span);
        };
        const category = old.querySelector(".chip.category")?.textContent.trim();
        if (category) fact("record-cat", category, `Filed under ${category}`);
        const date = old.querySelector(".entry-date");
        if (date) fact("record-date", date.textContent.trim(), date.title);
        //: Dates the note mentions ("Mentions 15 Nov"), a fact the old row had.
        const mention = old.querySelector(".chip.when");
        if (mention) fact("record-mention", mention.textContent.trim(), mention.title);
        //: The one stat slot: a percentage, or in words how a link-only note got here.
        const got = info?.[li.dataset.id];
        const score = got?.score;
        const pct = Math.round(score * 100);
        const said =
          scored && typeof score === "number"
            ? [`${pct}% match`, `Matched by meaning: ${pct}% similar to your question.`]
            : got?.type === "connected"
              ? ["Linked", "Here because it is linked to a note that matched."]
              : got?.type === "connected_2hop"
                ? ["Two steps away", "Here because it is linked to a note that is linked to a match."]
                : null;
        if (said) fact("record-score", said[0], said[1]);
        old.replaceWith(line);
        li.querySelector(":scope > .entry-why")?.remove();
        excerpt(li);
        folded(li);
      }
      const why = info?.[li.dataset.id]?.why;
      if (why && !li.querySelector(":scope > .record-why")) {
        const reason = document.createElement("p");
        reason.className = "record-why";
        reason.textContent = why;
        const meta = li.querySelector(":scope > .record-meta");
        if (meta) meta.after(reason);
        else li.appendChild(reason);
      }
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
    const change = smallButton("ph:gear Change the model", "Open Settings, Models", () => {
      openSettingsModal("models", "chat-model-select");
    });
    change.classList.add("quiet");
    row.appendChild(change);
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
        : ["Atlas's assistant, from your notes", "Atlas's assistant answered from your notes with no model: every sentence comes from a note", "notes"];
    }
    if (model) return [`Atlas, ${model}`, `Atlas answered with ${model}`];
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
  //: find; nothing is rewritten. **Text the composer wrote, never a model's
  //: answer** (CHAT_PLAN B1, the owner: "the whole response from my ai model
  //: just got placed in a dropdown collapsed box": one 145-word paragraph).
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

  //: **One queue for every composer** (`composerQueue`, palette.js; INBOX 1321 for
  //: Chat; CHAT_PLAN B3, the owner: "I cant type in the text box while the popup
  //: agent is respondning (check the guide as well) and I cant draft, queue or
  //: edit/delete queued messages like in chat"). Chat, the popup agent and the
  //: Guide keep the box open while a reply runs; a send then waits, oldest
  //: first, listed by the box with Edit (back into the box, out of the queue) and
  //: Remove, and goes as each reply ends. Stop holds it until the next send; a
  //: queued send leaves the box to what is being typed. A surface gives
  //: `{ input(), busy(), send(text), before() }`, the list going just before `before()`; `composerQueue(name)` reads
  //: its queue back. A list moved out of the page with its sheet is drawn again
  //: in the same place.
  composerQueue.paint = (q) => {
    const input = q.input();
    if (!q.items.length) {
      q.list?.remove();
      q.list = null;
      return;
    }
    if (!q.list?.isConnected) {
      q.list = document.createElement("ul");
      q.list.className = "chat-queue";
      q.list.setAttribute("aria-label", "Queued messages");
      q.before().before(q.list);
    }
    const join = input.tagName === "TEXTAREA" ? "\n" : " ";
    q.list.replaceChildren(
      ...q.items.map((text, i) => {
        const li = document.createElement("li");
        li.className = "chat-queue-item";
        const words = document.createElement("span");
        words.className = "chat-queue-text";
        words.textContent = text;
        words.title = text;
        const edit = smallButton("ph:pencil-simple", "Edit: back into the box", () => {
          q.items.splice(i, 1);
          input.value = input.value.trim() ? `${text}${join}${input.value}` : text;
          input.dispatchEvent(new Event("input"));
          input.focus();
          composerQueue.paint(q);
        });
        const remove = smallButton("ph:x", "Remove from the queue", () => {
          q.items.splice(i, 1);
          composerQueue.paint(q);
          input.focus();
        });
        for (const b of [edit, remove]) b.classList.add("icon-only");
        li.append(words, edit, remove);
        return li;
      })
    );
  };

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { openCalculator, renderRelatedElsewhere, replyDrawAll, replyFinish, replyRecordCards });
})();
