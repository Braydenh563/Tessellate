// documents-base.js: the ```base block (DOCUMENTS_PLAN gap row 6, the Obsidian "Bases" ask): a fence of lines is drawn as
// a table of the notes whose properties match. Read-only by decision: the table shows the `---` blocks the notes already
// have (`GET /property-table`, repo/properties.py `table`), and a note's block is changed in the note, so there is one
// place a value is written. The first column opens the note. Three views (L-documents-52): a table, a board that groups the
// rows by a property (a card moves by drag or by its menu, which writes the one property through `PUT /entries/{id}/properties`,
// the route the note's own sheet uses) and a month calendar placed by a date property.
//
//   type: Book                one `type:` property
//   where: status = read      any number of these, all must hold (a list property matches any of its values)
//   columns: author, rating   the properties to show, in order
//   sort: rating desc         one property, asc or desc (numbers and dates sort as such)
//   limit: 50                 rows, at most 300
//   view: board               table (default), board or calendar; the switch on the block rewrites this line
//   group: status             the board's column property (a select or a list such as tags)
//   date: due                 the calendar's date property
//
// Lazy: `LAZY_MODULES.docBase`, registered in lazy-entries.js; documents-math.js draws Read and Live and calls
// `docMathRender.base.fill`. Everything is a property of `docMathRender.base`, so the file adds no global name.
(() => {
  // DOC-BASE-BEGIN (tests/test_doc_base.py runs this region in node)
  const KEYS = new Set(["type", "where", "columns", "sort", "limit", "view", "group", "date"]);
  const VIEWS = ["table", "board", "calendar"];
  const MAX_ROWS = 300;

  //: **`parse(source)`**: `{ type, where: [[key, value]], columns, sort, desc, limit, errors }`, the reasons a line was
  //: not understood being sentences for under the table.
  function parse(source) {
    const model = { type: "", where: [], columns: [], sort: "", desc: false, limit: 100, view: "table", group: "", date: "", errors: [] };
    for (const raw of String(source || "").split("\n")) {
      const line = raw.trim();
      if (!line) continue;
      const at = line.indexOf(":");
      const key = at > 0 ? line.slice(0, at).trim().toLowerCase() : "";
      const value = at > 0 ? line.slice(at + 1).trim() : "";
      if (!KEYS.has(key)) {
        model.errors.push(`"${line.slice(0, 40)}" is not a line a base reads. Use type, where, columns, sort, limit, view, group or date.`);
      } else if (key === "type") {
        model.type = value;
      } else if (key === "where") {
        const eq = value.indexOf("=");
        if (eq > 0 && value.slice(0, eq).trim()) model.where.push([value.slice(0, eq).trim(), value.slice(eq + 1).trim()]);
        else model.errors.push(`"where: ${value.slice(0, 30)}" should read property = value.`);
      } else if (key === "columns") {
        model.columns = value.split(",").map((c) => c.trim()).filter(Boolean).slice(0, 12);
      } else if (key === "sort") {
        const m = /^(.*?)(?:\s+(asc|desc))?$/i.exec(value);
        model.sort = (m && m[1] ? m[1] : value).trim();
        model.desc = Boolean(m && m[2] && m[2].toLowerCase() === "desc");
      } else if (key === "view") {
        if (VIEWS.includes(value.toLowerCase())) model.view = value.toLowerCase();
        else model.errors.push(`"view: ${value.slice(0, 20)}" should be table, board or calendar.`);
      } else if (key === "group" || key === "date") {
        model[key] = value;
      } else {
        const n = Number.parseInt(value, 10);
        if (n >= 1) model.limit = Math.min(n, MAX_ROWS);
        else model.errors.push(`"limit: ${value.slice(0, 20)}" should be a number of rows.`);
      }
    }
    return model;
  }

  //: The address the table is read from.
  function query(model) {
    const params = new URLSearchParams();
    if (model.type) params.set("type", model.type);
    for (const [k, v] of model.where) params.append("where", `${k}=${v}`);
    //: The board's and the calendar's property is fetched even when `columns` leaves it out.
    const names = [...new Set([...model.columns, model.group, model.date].filter(Boolean))].slice(0, 12);
    if (names.length) params.set("columns", names.join(","));
    if (model.sort) params.set("sort", model.sort);
    if (model.desc) params.set("desc", "true");
    params.set("limit", String(model.limit));
    return `/property-table?${params}`;
  }

  //: **`setLine(source, key, value)`**: the fence's text with that one line set (an empty value removes it), so the view
  //: switch is stored in the block itself.
  function setLine(source, key, value) {
    const lines = String(source || "").split("\n");
    const at = lines.findIndex((l) => l.slice(0, Math.max(l.indexOf(":"), 0)).trim().toLowerCase() === key);
    if (!value) return at < 0 ? lines.join("\n") : lines.filter((_, i) => i !== at).join("\n");
    const line = `${key}: ${value}`;
    if (at >= 0) lines[at] = line;
    else lines.push(line);
    return lines.join("\n");
  }

  //: **`groupRows(rows, key)`**: `[{ name, rows }]`, a card under each value it holds (a list property such as tags is in
  //: several), the rows with none last under an empty name.
  function groupRows(rows, key) {
    const by = new Map();
    for (const row of rows) {
      const values = (row.values[key] || []).filter((v) => String(v).trim());
      for (const v of values.length ? values : [""]) {
        if (!by.has(v)) by.set(v, []);
        by.get(v).push(row);
      }
    }
    const names = [...by.keys()].sort((a, b) => (a === "") - (b === "") || String(a).localeCompare(String(b)));
    return names.map((name) => ({ name, rows: by.get(name) }));
  }

  //: **`moveValue(value, from, to)`**: a property's new value when a card leaves column `from` for `to`: a list swaps the
  //: one entry, anything else becomes `to`; `null` means the property is cleared.
  function moveValue(value, from, to) {
    if (Array.isArray(value)) {
      const kept = value.filter((v) => String(v) !== String(from));
      if (to && !kept.some((v) => String(v) === String(to))) kept.push(to);
      return kept.length ? kept : null;
    }
    return to ? String(to) : null;
  }

  const pad = (n) => String(n).padStart(2, "0");

  //: **`dateOf(row, key)`**: the row's `YYYY-MM-DD`, or "" when it holds none.
  function dateOf(row, key) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String((row.values[key] || [])[0] || ""));
    return m ? `${m[1]}-${m[2]}-${m[3]}` : "";
  }

  //: **`monthGrid(year, month)`**: six Monday-first weeks of `{ iso, day, inMonth }` (`month` is 0 to 11).
  function monthGrid(year, month) {
    const first = new Date(Date.UTC(year, month, 1));
    const start = Date.UTC(year, month, 1 - ((first.getUTCDay() + 6) % 7));
    return Array.from({ length: 42 }, (_, i) => {
      const d = new Date(start + i * 86400000);
      return { iso: `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`, day: d.getUTCDate(), inMonth: d.getUTCMonth() === month };
    });
  }

  //: **`queryParse(source)`**: the ```query block (L-documents-43): `{ name, text, limit, errors }`. A line `saved: Reading list`
  //: names a saved search (the finder's, then the Notes filter's), `search: tag:work` is a query typed in place, a bare line is
  //: read as a saved name and, when none is called that, as the query itself, and `limit: 20` caps the list (50 at most).
  function queryParse(source) {
    const model = { name: "", text: "", limit: 10, errors: [] };
    for (const raw of String(source || "").split("\n")) {
      const line = raw.trim();
      const m = /^(saved|search|limit)\s*:\s*(.*)$/i.exec(line);
      if (!line) continue;
      const key = m ? m[1].toLowerCase() : "";
      if (key === "limit") {
        const n = Number.parseInt(m[2], 10);
        if (n >= 1) model.limit = Math.min(n, 50);
        else model.errors.push(`"${line.slice(0, 30)}" should be a number of results.`);
      } else if (key === "search") model.text = m[2].trim();
      else if (key === "saved") model.name = m[2].trim();
      else if (!model.name && !model.text) model.name = line;
    }
    return model;
  }

  //: **`queryAddress(model, saved)`**: `{ q, path, label }` where `saved` is `[{ name, query }]`; `q` is "" when the block names
  //: nothing to look for.
  function queryAddress(model, saved) {
    const hit = model.name && saved.find((s) => s.name.toLowerCase() === model.name.toLowerCase());
    const q = hit ? hit.query : model.text || model.name;
    const params = new URLSearchParams({ q, kind: "note,document", limit: String(model.limit) });
    return { q, path: `/search?${params}`, label: hit ? hit.name : q };
  }
  // DOC-BASE-END

  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  const open = (row) => {
    const button = el("button", "db-open link-button", row.title);
    button.type = "button";
    button.addEventListener("click", () => flashEntry(row.id));
    return button;
  };

  function drawTable(body, model, data) {
    const columns = model.columns.length ? model.columns : data.columns;
    const wrap = el("div", "db-scroll");
    const table = el("table", "db-table");
    const head = el("tr");
    for (const name of ["Note", ...columns]) head.append(el("th", "", name));
    const thead = el("thead");
    thead.append(head);
    table.append(thead);
    const rows = el("tbody");
    for (const row of data.rows) {
      const tr = el("tr");
      const first = el("td", "db-title");
      first.append(open(row));
      tr.append(first);
      for (const column of columns) tr.append(el("td", "", (row.values[column] || []).join(", ")));
      rows.append(tr);
    }
    table.append(rows);
    wrap.append(table);
    body.append(wrap);
  }

  async function moveCard(row, key, from, to) {
    const before = await fullEntry(row.id);
    const found = await apiJson(`/entries/${row.id}/properties`);
    const props = { ...found.properties };
    const name = Object.keys(props).find((k) => k.toLowerCase() === key.toLowerCase()) || key;
    const next = moveValue(props[name], from, to);
    if (next === null) delete props[name];
    else props[name] = next;
    const done = await apiJson(`/entries/${row.id}/properties`, { method: "PUT", body: JSON.stringify({ properties: props, base_hash: before.content_hash || null }) });
    if (!before.content_truncated && typeof before.content === "string" && done.content !== before.content) {
      pushEntryPutUndo(row.id, "Moved a card", { content: before.content }, { content: done.content });
    }
    row.values[key] = next === null ? [] : [].concat(next).map(String);
  }

  function drawBoard(body, model, data, redraw) {
    const key = model.group;
    if (!key) {
      body.append(el("p", "db-empty", "Name the property to group by, from the menu above or with a line such as group: status."));
      return;
    }
    const groups = groupRows(data.rows, key);
    const move = (row, from, to) =>
      moveCard(row, key, from, to)
        .then(() => redraw())
        .catch((error) => {
          toast(error.message || "The note could not be moved.", true);
          redraw();
        });
    const lane = el("div", "db-board");
    for (const group of groups) {
      const column = el("section", "db-col");
      column.setAttribute("aria-label", `${group.name || "No value"}, ${nounCount(group.rows.length, "note")}`);
      column.append(el("h4", "db-col-head", `${group.name || "No value"} (${group.rows.length})`));
      const list = el("div", "db-cards");
      column.addEventListener("dragover", (event) => {
        if (event.dataTransfer?.types.includes("text/x-db-card")) {
          event.preventDefault();
          column.classList.add("db-over");
        }
      });
      column.addEventListener("dragleave", () => column.classList.remove("db-over"));
      column.addEventListener("drop", (event) => {
        column.classList.remove("db-over");
        const [id, from] = (event.dataTransfer?.getData("text/x-db-card") || "").split("\n");
        const row = data.rows.find((r) => String(r.id) === id);
        event.preventDefault();
        if (row && from !== group.name) move(row, from, group.name);
      });
      for (const row of group.rows) {
        const card = el("div", "db-card");
        card.draggable = true;
        card.addEventListener("dragstart", (event) => event.dataTransfer?.setData("text/x-db-card", `${row.id}\n${group.name}`));
        const targets = groups.filter((g) => g.name !== group.name).map((g) => g.name);
        const items = targets.map((name) => ({ label: `Move to ${name || "no value"}`, run: () => move(row, group.name, name) }));
        card.append(open(row));
        if (items.length) card.append(kebabMenu(items, `Move ${row.title}`));
        list.append(card);
      }
      column.append(list);
      lane.append(column);
    }
    body.append(lane);
  }

  function drawCalendar(body, model, data, state, redraw) {
    const key = model.date;
    if (!key) {
      body.append(el("p", "db-empty", "Name the date property, from the menu above or with a line such as date: due."));
      return;
    }
    if (state.year === undefined) {
      const first = data.rows.map((r) => dateOf(r, key)).find(Boolean) || new Date().toISOString();
      state.year = Number(first.slice(0, 4));
      state.month = Number(first.slice(5, 7)) - 1;
    }
    const step = (by) => {
      const d = new Date(Date.UTC(state.year, state.month + by, 1));
      state.year = d.getUTCFullYear();
      state.month = d.getUTCMonth();
      redraw();
    };
    const nav = el("div", "db-month");
    const prev = smallButton("ph:caret-left", "Previous month", () => step(-1));
    const next = smallButton("ph:caret-right", "Next month", () => step(1));
    prev.classList.add("icon-only");
    next.classList.add("icon-only");
    const title = new Date(Date.UTC(state.year, state.month, 1)).toLocaleString(undefined, { month: "long", year: "numeric", timeZone: "UTC" });
    nav.append(prev, el("strong", "db-month-name", title), next);
    const byDay = new Map();
    let dated = 0;
    for (const row of data.rows) {
      const iso = dateOf(row, key);
      if (!iso) continue;
      dated += 1;
      if (!byDay.has(iso)) byDay.set(iso, []);
      byDay.get(iso).push(row);
    }
    const grid = el("div", "db-cal");
    for (const name of ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]) grid.append(el("div", "db-dow", name));
    for (const cell of monthGrid(state.year, state.month)) {
      const day = el("div", cell.inMonth ? "db-day" : "db-day db-day-out");
      day.append(el("span", "db-daynum", String(cell.day)));
      for (const row of byDay.get(cell.iso) || []) day.append(open(row));
      grid.append(day);
    }
    body.append(nav, grid);
    if (dated < data.rows.length) body.append(el("p", "db-count", `${nounCount(data.rows.length - dated, "note")} without a date in ${key}.`));
  }

  function draw(body, model, data, state, redraw) {
    body.replaceChildren();
    if (!data.rows.length) {
      body.append(el("p", "db-empty", "No notes match."));
      return;
    }
    if (model.view === "board") drawBoard(body, model, data, redraw);
    else if (model.view === "calendar") drawCalendar(body, model, data, state, redraw);
    else drawTable(body, model, data);
    if (data.total > data.rows.length) body.append(el("p", "db-count", `${data.rows.length} of ${nounCount(data.total, "note")}.`));
  }

  //: **`fill(figure, source, write)`**: reads the notes and draws them into `figure`; false (the reasons left in the figure)
  //: when the fence names nothing to look for, so Read keeps it as code. `write(text)` puts a changed fence back into the
  //: document (the view switch, the chosen property); without it the choice lasts only while the figure does.
  function fill(figure, source, write) {
    const model = parse(source);
    figure.replaceChildren();
    const issues = el("ul", "db-issues");
    for (const line of model.errors) issues.append(el("li", "", line));
    if (!model.type && !model.where.length && !model.columns.length) {
      figure.append(el("p", "db-empty", "Nothing to look for yet. Write a line such as type: Book."));
      if (model.errors.length) figure.append(issues);
      return false;
    }
    const bar = el("div", "db-bar");
    const label = el("span", "db-label", model.type ? `Notes of type ${model.type}` : "Notes");
    const refresh = smallButton("ph:arrow-clockwise", "Refresh the table", () => load());
    refresh.classList.add("icon-only");
    const seg = el("div", "seg seg-compact db-views");
    seg.setAttribute("role", "group");
    seg.setAttribute("aria-label", "View");
    const choose = el("span", "db-choose");
    bar.append(refresh, label, seg, choose);
    const body = el("div", "db-body");
    body.setAttribute("aria-live", "polite");
    figure.append(bar, body);
    if (model.errors.length) figure.append(issues);
    const state = {};
    let current = null;
      const setKey = (key, value, reload) => {
      source = setLine(source, key, value);
      model[key] = value || (key === "view" ? "table" : "");
      if (write) write(source);
      if (reload) load();
      else paint();
    };
    function paint() {
      seg.replaceChildren();
      for (const [id, name] of [["table", "Table"], ["board", "Board"], ["calendar", "Calendar"]]) {
        const button = el("button", model.view === id ? "active" : "", name);
        button.type = "button";
        button.setAttribute("aria-pressed", model.view === id ? "true" : "false");
        button.addEventListener("click", () => setKey("view", id === "table" ? "" : id, false));
        seg.append(button);
      }
      choose.replaceChildren();
      const pickKey = model.view === "board" ? "group" : model.view === "calendar" ? "date" : "";
      const names = current ? current.columns : [];
      if (pickKey && names.length) {
        const items = names.map((name) => ({ label: name, current: name === model[pickKey], run: () => setKey(pickKey, name, false) }));
        choose.append(el("span", "db-label", pickKey === "group" ? "Group by" : "Date in"), kebabMenu(items, pickKey === "group" ? "Group by property" : "Date property"));
      }
      if (current) draw(body, model, current, state, paint);
    }
    let token = 0;
    function load() {
      const mine = ++token;
      body.replaceChildren(el("p", "db-empty", "Reading the notes"));
      apiJson(query(model), { silent: true })
        .then((data) => {
          if (mine !== token || !figure.isConnected) return;
          current = data;
          if (!model.group && data.columns[0]) model.group = data.columns[0];
          if (!model.date && data.columns[0]) model.date = data.columns.find((c) => data.rows.some((r) => dateOf(r, c))) || "";
          paint();
        })
        .catch(() => {
          if (mine === token) body.replaceChildren(el("p", "db-empty", "The notes could not be read just now."));
        });
    }
    paint();
    load();
    return true;
  }

  //: **`queryFill(figure, source)`**: the saved search's results as a list, read again after each save of the document; a title
  //: opens the note or document. False when the block names nothing, so Read keeps it as code.
  function queryFill(figure, source) {
    const model = queryParse(source);
    figure.replaceChildren();
    const saved = [...(prefsCache?.saved_finds || []), ...(prefsCache?.saved_searches || [])];
    const at = queryAddress(model, saved);
    if (!at.q) {
      figure.append(el("p", "db-empty", "Nothing to look for yet. Write the name of a saved search, or search: and some words."));
      return false;
    }
    const bar = el("div", "db-bar");
    const refresh = smallButton("ph:arrow-clockwise", "Refresh the results", () => load());
    refresh.classList.add("icon-only");
    bar.append(refresh, el("span", "db-label", `Search: ${at.label}`));
    const body = el("div", "db-body");
    body.setAttribute("aria-live", "polite");
    figure.append(bar, body);
    for (const line of model.errors) figure.append(el("p", "db-count", line));
    let token = 0;
    function load() {
      const mine = ++token;
      body.replaceChildren(el("p", "db-empty", "Reading the notes"));
      apiJson(at.path, { silent: true })
        .then((data) => {
          if (mine !== token || !figure.isConnected) return;
          body.replaceChildren();
          const hits = (data.hits || []).filter((h) => h.kind === "note" || h.kind === "document");
          if (!hits.length) return body.append(el("p", "db-empty", "Nothing matches."));
          const list = el("ul", "db-hits");
          for (const hit of hits) {
            const item = el("li", "db-hit");
            const open = el("button", "db-open link-button", hit.title || "Untitled");
            open.type = "button";
            open.addEventListener("click", () => {
              if (hit.kind === "document") {
                switchTab("documents");
                openDocument(hit.id);
              } else flashEntry(hit.id);
            });
            item.append(open, el("span", "db-kind", hit.kind === "document" ? "Document" : "Note"));
            list.append(item);
          }
          body.append(list);
        })
        .catch(() => {
          if (mine === token) body.replaceChildren(el("p", "db-empty", "The results could not be read just now."));
        });
    }
    const again = () => (figure.isConnected ? load() : document.removeEventListener("doc-saved", again));
    document.addEventListener("doc-saved", again);
    load();
    return true;
  }

  Object.assign(docMathRender, { base: { parse, query, fill, setLine, groupRows, moveValue, monthGrid, dateOf, queryParse, queryAddress, queryFill } });
})();
