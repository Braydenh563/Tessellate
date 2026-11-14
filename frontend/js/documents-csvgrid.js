// documents-csvgrid.js: an editable grid for a csv or tsv document (L328, decision D42: an editable view,
// not the read-only table Run shows).
//
// The Grid button (`#doc-csv-grid`, documents.js) swaps the editor for a table of the file's cells. A cell edits in
// place; Tab, Enter and the arrow keys move between cells; Add row, Add column, Delete row and Delete column act on
// the cell you are in. **Nothing is a second copy of the file**: every edit is a `{from, to, insert}` change to the
// editor's own text, made in one CodeMirror transaction, so Ctrl+Z, autosave and version history see the same file
// they would see after typing it. The model below reads the text with each cell's span, so an edit rewrites that
// cell's own characters (quoted when it holds the delimiter, a quote or a line break) and every other byte stays as
// it was typed: a file with its own quoting or CRLF comes back the same.
//
// Lazy: `LAZY_MODULES.docCsvGrid` (lazy-entries.js), fetched on the first press. It adds no global name: the API is
// `docViewState.csvGrid` (documents.js). The region between DOC-CSVGRID-BEGIN and -END is pure, and
// `tests/test_doc_csv_grid.py` runs it in node.
(() => {
  // DOC-CSVGRID-BEGIN
  //: The file as rows of cells, each with the span of its raw text. RFC 4180: a quoted field may hold the delimiter,
  //: a doubled quote and a line break. `row.to` is where its content ends, `row.next` where the next row starts (the
  //: line break is between them, none on a last line without one).
  function parse(text, delim) {
    const rows = [];
    const n = text.length;
    let i = text.charCodeAt(0) === 0xfeff ? 1 : 0;
    let eol = "";
    while (i < n) {
      const row = { cells: [], from: i, to: i, next: i };
      for (;;) {
        const cell = { from: i, to: i, text: "" };
        let k = i;
        let value = "";
        if (text[i] === '"') {
          k = i + 1;
          for (; k < n; k++) {
            if (text[k] !== '"') value += text[k];
            else if (text[k + 1] === '"') { value += '"'; k += 1; } else { k += 1; break; }
          }
        }
        //: Anything after a closing quote, up to the delimiter, is kept as it is.
        while (k < n && text[k] !== delim && text[k] !== "\n" && text[k] !== "\r") value += text[k++];
        cell.text = value;
        cell.to = k;
        i = k;
        row.cells.push(cell);
        if (text[i] === delim) { i += 1; continue; }
        break;
      }
      row.to = i;
      if (text[i] === "\r" && text[i + 1] === "\n") { i += 2; eol = eol || "\r\n"; } else if (i < n) { eol = eol || text[i]; i += 1; }
      row.next = i;
      rows.push(row);
    }
    return { rows, delim, eol: eol || "\n", length: n };
  }

  //: A tab-separated file: its title says so, or its first line has a tab and no comma.
  function delimiterOf(text, title) {
    const first = String(text).split("\n", 1)[0];
    return /\.tsv$/i.test(String(title || "")) || (!/,/.test(first) && /\t/.test(first)) ? "\t" : ",";
  }

  //: A value as one field. A lone empty field is `""`, or its line would read as no row at all.
  function quote(value, delim, alone) {
    if (value === "" && alone) return '""';
    return value.includes(delim) || /["\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
  }

  function columns(model) {
    return model.rows.reduce((most, row) => Math.max(most, row.cells.length), 0);
  }

  //: Each operation returns changes in the text's own coordinates, ascending and apart, for one transaction.
  const ops = {
    //: A cell's new value. A cell the row does not have yet (a short row) is made with the delimiters before it.
    setCell(model, r, c, value) {
      const row = model.rows[r];
      if (!row) return [];
      const alone = row.cells.length === 1 && c === 0;
      if (c < row.cells.length) return [{ from: row.cells[c].from, to: row.cells[c].to, insert: quote(value, model.delim, alone) }];
      return [{ from: row.to, to: row.to, insert: model.delim.repeat(c - row.cells.length + 1) + quote(value, model.delim, false) }];
    },
    //: A blank row below row `r` (or above it, with `after` false).
    addRow(model, r, after = true) {
      const row = model.rows[r];
      const blank = columns(model) > 1 ? model.delim.repeat(columns(model) - 1) : '""';
      if (!row) return [{ from: model.length, to: model.length, insert: blank + model.eol }];
      if (!after) return [{ from: row.from, to: row.from, insert: blank + model.eol }];
      if (row.next === row.to) return [{ from: row.to, to: row.to, insert: model.eol + blank }];
      return [{ from: row.next, to: row.next, insert: blank + model.eol }];
    },
    //: An empty column at index `k`: a delimiter before that cell in every row long enough to have it.
    addColumn(model, k) {
      const changes = [];
      for (const row of model.rows) {
        if (k < row.cells.length) changes.push({ from: row.cells[k].from, to: row.cells[k].from, insert: model.delim });
        else if (k === row.cells.length) changes.push({ from: row.to, to: row.to, insert: model.delim });
      }
      return changes;
    },
    deleteRow(model, r) {
      const row = model.rows[r];
      if (!row) return [];
      //: The last row has no line break after it: the one before it gives up its own.
      if (row.next === row.to && r > 0) return [{ from: model.rows[r - 1].to, to: row.to, insert: "" }];
      return [{ from: row.from, to: row.next, insert: "" }];
    },
    deleteColumn(model, c) {
      const changes = [];
      for (const row of model.rows) {
        const cells = row.cells;
        if (c >= cells.length) continue;
        if (cells.length === 1) changes.push({ from: cells[0].from, to: cells[0].to, insert: "" });
        else if (c < cells.length - 1) changes.push({ from: cells[c].from, to: cells[c + 1].from, insert: "" });
        else changes.push({ from: cells[c - 1].to, to: cells[c].to, insert: "" });
      }
      return changes;
    },
  };

  //: The text after changes (ascending, apart), for the tests and for a check of the in-place shift.
  function applyChanges(text, changes) {
    let out = "";
    let at = 0;
    for (const change of changes) {
      out += text.slice(at, change.from) + change.insert;
      at = change.to;
    }
    return out + text.slice(at);
  }

  //: The rows the view shows, as file row indices. `header` keeps row 0 on top whatever the sort and filters; the rest
  //: are filtered (every column's text is contained, case ignored) then sorted by `sort` ({c, dir: 1 or -1}), stably.
  //: Nothing here moves a byte of the file: a hidden row is still in it.
  function viewOrder(model, header, sort, filters) {
    const start = header ? 1 : 0;
    const needles = Object.entries(filters || {}).map(([c, v]) => [Number(c), String(v).toLowerCase()]).filter(([, v]) => v);
    let order = [];
    for (let r = start; r < model.rows.length; r++) {
      const cells = model.rows[r].cells;
      if (needles.every(([c, v]) => (cells[c]?.text ?? "").toLowerCase().includes(v))) order.push(r);
    }
    if (sort) order = sortRows(model, order, sort);
    return header && model.rows.length ? [0, ...order] : order;
  }

  //: Numbers by value when both sides are numbers, else text by the locale with digits in order; blanks last either way.
  function compareCells(a, b) {
    const x = a.trim();
    const y = b.trim();
    if (!x || !y) return x === y ? 0 : x ? -1 : 1;
    const nx = Number(x);
    const ny = Number(y);
    if (!Number.isNaN(nx) && !Number.isNaN(ny)) return nx - ny;
    return x.localeCompare(y, undefined, { numeric: true, sensitivity: "base" });
  }

  function sortRows(model, order, sort) {
    const key = (r) => model.rows[r].cells[sort.c]?.text ?? "";
    const keyed = order.map((r, i) => ({ r, i, k: key(r) }));
    keyed.sort((p, q) => {
      const blank = !p.k.trim() || !q.k.trim();
      const by = compareCells(p.k, q.k);
      return (blank ? by : by * sort.dir) || p.i - q.i;
    });
    return keyed.map((e) => e.r);
  }

  //: "Sort the file": the data rows' own text put in the sorted order, the line breaks between them left where they were.
  //: One change over the span of the data rows, so it is one undo step.
  function sortFile(model, text, header, sort) {
    const start = header ? 1 : 0;
    const rows = model.rows.slice(start);
    if (rows.length < 2) return [];
    const order = sortRows(model, rows.map((_, i) => i + start), sort);
    const raw = (r) => text.slice(model.rows[r].from, model.rows[r].to);
    let insert = "";
    order.forEach((r, i) => {
      insert += raw(r) + (i < rows.length - 1 ? text.slice(rows[i].to, rows[i].next) : "");
    });
    const from = rows[0].from;
    const to = rows[rows.length - 1].to;
    return insert === text.slice(from, to) ? [] : [{ from, to, insert }];
  }

  //: Clipboard text as rows of cells: tab between cells, a line break between rows, and a quoted cell may hold either (a
  //: spreadsheet quotes such a cell when it copies). One trailing line break is the end of the last row, not a blank row.
  function clipRows(text) {
    return parse(String(text), "\t").rows.map((row) => row.cells.map((cell) => cell.text));
  }

  //: A block of cells pasted with its top-left corner at column `c` of the file rows `targets` (file row indices; a row
  //: past the end of the list, or of the file, is a new row at the end). A row too short grows to reach the block; the
  //: cells around it keep their bytes.
  function pasteBlock(model, targets, c, block) {
    const changes = [];
    const width = Math.max(...block.map((row) => row.length), 1);
    const fresh = [];
    block.forEach((values, i) => {
      const row = model.rows[targets[i]];
      if (!row) {
        fresh.push(model.delim.repeat(c) + values.map((v) => quote(v, model.delim, c === 0 && width === 1)).join(model.delim));
        return;
      }
      let tail = "";
      for (let k = 0; k < values.length; k++) {
        const at = c + k;
        if (at < row.cells.length) changes.push({ from: row.cells[at].from, to: row.cells[at].to, insert: quote(values[k], model.delim, row.cells.length === 1 && at === 0) });
      }
      for (let at = row.cells.length; at < c + values.length; at++) {
        tail += model.delim + (at >= c ? quote(values[at - c], model.delim, false) : "");
      }
      if (tail) changes.push({ from: row.to, to: row.to, insert: tail });
    });
    if (fresh.length) {
      const last = model.rows[model.rows.length - 1];
      const lead = last && last.next === last.to ? model.eol : "";
      changes.push({ from: model.length, to: model.length, insert: lead + fresh.join(model.eol) + (last && last.next === last.to ? "" : model.eol) });
    }
    return changes.sort((a, b) => a.from - b.from);
  }
  // DOC-CSVGRID-END

  const MAX_ROWS = 1000;
  const MAX_CHARS = 2_000_000;
  //: `view` is what the grid shows and never what the file holds: a sort, the filters, the column widths and the header
  //: row's meaning. Only the header toggle is kept, per document (`prefs`, like the outline's folds).
  const HEADER_KEY = "doc-csv-header";
  const MIN_WIDTH = 48;
  const MAX_WIDTH = 800;
  const WIDTH_STEP = 16;
  const state = { open: false, model: null, docId: null, active: { r: 0, c: 0 }, writing: false, root: null, table: null, chip: null, wired: false, title: "", order: [], view: { header: true, sort: null, filters: {}, widths: {}, filterOpen: false }, bar: {} };

  const text = () => docSurface().text;

  function el(tag, className, label) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (label !== undefined) node.textContent = label;
    return node;
  }

  function barButton(icon, label, hint, run) {
    const button = el("button", "ghost small csv-grid-act");
    button.type = "button";
    button.title = hint;
    const glyph = el("i", `ph ${icon} ph-lead`);
    glyph.setAttribute("aria-hidden", "true");
    button.append(glyph, el("span", "toolbar-word", ` ${label}`));
    button.addEventListener("click", run);
    return button;
  }

  //: One transaction for a set of changes: the editor's undo takes it back whole.
  function write(changes) {
    if (!changes.length || !docCmView) return;
    state.writing = true;
    try {
      docCmView.dispatch({ changes, userEvent: "input.grid", scrollIntoView: false });
    } finally {
      state.writing = false;
    }
  }

  function cellAt(r, c) {
    return state.table?.querySelector(`[data-r="${r}"][data-c="${c}"]`) || null;
  }

  function selectAll(cell) {
    const range = document.createRange();
    range.selectNodeContents(cell);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }

  function focusCell(r, c, { select = true } = {}) {
    const cols = columns(state.model);
    const cell = cellAt(r, Math.max(0, Math.min(c, cols - 1)));
    if (!cell) return false;
    cell.focus();
    if (select) selectAll(cell);
    return true;
  }

  function describe() {
    const { r, c } = state.active;
    const total = state.model.rows.length;
    const { header, sort, filters } = state.view;
    let note = "";
    if (Object.values(filters).some(Boolean)) note = `, ${state.order.length - (header && total ? 1 : 0)} rows match`;
    else if (sort) note = ", sorted in view";
    state.chip.textContent = total ? `Row ${r + 1} of ${total}, column ${c + 1}${note}` : "No rows yet";
  }

  //: Column letters (A, B, ... Z, AA) name a column that has no header text.
  function colName(c) {
    let name = "";
    for (let k = c + 1; k > 0; k = Math.floor((k - 1) / 26)) name = String.fromCharCode(65 + ((k - 1) % 26)) + name;
    return name;
  }

  function colLabel(c) {
    const head = state.view.header ? state.model.rows[0]?.cells[c]?.text.trim() : "";
    return head || `column ${colName(c)}`;
  }

  //: A resized column pins its cells' width (floor and ceiling together); no width gives the stylesheet's back.
  function sizeCell(node, w) {
    node.style.minInlineSize = w ? `${w}px` : "";
    node.style.maxInlineSize = w ? `${w}px` : "";
  }

  function applyWidth(c) {
    const w = state.view.widths[c];
    for (const node of state.table.querySelectorAll(`[data-c="${c}"]`)) {
      sizeCell(node, w);
    }
    const grip = state.table.querySelector(`.csv-grid-grip[data-c="${c}"]`);
    if (grip) grip.setAttribute("aria-valuenow", String(Math.round(w || grip.parentElement.getBoundingClientRect().width)));
  }

  function setWidth(c, px) {
    if (px === null) delete state.view.widths[c];
    else state.view.widths[c] = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, Math.round(px)));
    applyWidth(c);
  }

  function widthOf(c) {
    return state.view.widths[c] || state.table.querySelector(`.csv-grid-ctl[data-c="${c}"]`)?.getBoundingClientRect().width || 112;
  }

  function sortView(c, dir) {
    const now = state.view.sort;
    state.view.sort = dir === null || (now && now.c === c && now.dir === dir) ? null : { c, dir };
    render();
  }

  //: The header button: ascending, then descending, then the file's own order.
  function cycleSort(c) {
    const now = state.view.sort;
    if (!now || now.c !== c) return sortView(c, 1);
    if (now.dir === 1) return sortView(c, -1);
    state.view.sort = null;
    render();
  }

  function sortTheFile(c, dir) {
    const changes = sortFile(state.model, text(), state.view.header, { c, dir });
    state.view.sort = null;
    if (!changes.length) {
      render();
      return toast("The rows are already in that order.", "info");
    }
    structural(changes, null, `File sorted by ${colLabel(c)}.`);
  }

  function columnMenu(c) {
    const sorted = state.view.sort?.c === c ? state.view.sort.dir : 0;
    return kebabMenu(
      [
        { label: "Sort A to Z in view", title: "Show the rows in this order; the file is not changed", current: sorted === 1, run: () => sortView(c, 1), group: "view" },
        { label: "Sort Z to A in view", title: "Show the rows in the opposite order; the file is not changed", current: sorted === -1, run: () => sortView(c, -1), group: "view" },
        { label: "Clear the sort", run: () => sortView(c, null), group: "view" },
        { label: "Sort the file A to Z", title: "Rewrite the file's rows in this order (Undo brings the old order back)", run: () => sortTheFile(c, 1), group: "file" },
        { label: "Sort the file Z to A", title: "Rewrite the file's rows in the opposite order (Undo brings the old order back)", run: () => sortTheFile(c, -1), group: "file" },
        { label: "Widen the column", run: () => setWidth(c, widthOf(c) + WIDTH_STEP * 2), group: "width" },
        { label: "Narrow the column", run: () => setWidth(c, widthOf(c) - WIDTH_STEP * 2), group: "width" },
        { label: "Reset the width", run: () => setWidth(c, null), group: "width" },
      ],
      `Column options for ${colLabel(c)}`,
    );
  }

  function ctlCell(c) {
    const th = el("th", "csv-grid-ctl");
    th.dataset.c = String(c);
    th.scope = "col";
    const sort = state.view.sort;
    th.setAttribute("aria-sort", sort?.c === c ? (sort.dir === 1 ? "ascending" : "descending") : "none");
    const top = el("div", "csv-grid-ctl-top");
    const name = el("button", "ghost small csv-grid-sort");
    name.type = "button";
    name.title = "Sort the view by this column: A to Z, Z to A, then the file's own order";
    name.append(el("span", "csv-grid-sort-name", colLabel(c)));
    if (sort?.c === c) {
      const arrow = el("i", `ph ${sort.dir === 1 ? "ph-arrow-up" : "ph-arrow-down"} ph-lead`);
      arrow.setAttribute("aria-hidden", "true");
      name.append(arrow);
    }
    name.addEventListener("click", () => cycleSort(c));
    top.append(name, columnMenu(c));
    th.append(top);
    if (state.view.filterOpen) {
      const input = el("input", "csv-grid-filter");
      input.type = "text";
      input.dataset.f = String(c);
      input.value = state.view.filters[c] || "";
      input.placeholder = "Contains";
      input.setAttribute("aria-label", `Show rows where ${colLabel(c)} contains`);
      th.append(input);
    }
    //: A separator you can drag (the pointer) or focus and nudge with the arrow keys, Home to reset (the keyboard).
    const grip = el("span", "csv-grid-grip");
    grip.dataset.c = String(c);
    grip.tabIndex = 0;
    grip.setAttribute("role", "separator");
    grip.setAttribute("aria-orientation", "vertical");
    grip.setAttribute("aria-label", `Resize ${colLabel(c)}. Left and Right change the width, Home resets it.`);
    grip.setAttribute("aria-valuemin", String(MIN_WIDTH));
    grip.setAttribute("aria-valuemax", String(MAX_WIDTH));
    th.append(grip);
    return th;
  }

  function rowEl(r, cols, tag) {
    const tr = el("tr");
    const gutter = el("th", "csv-grid-num", String(r + 1));
    gutter.scope = "row";
    tr.append(gutter);
    for (let c = 0; c < cols; c++) {
      const cell = el(tag, "csv-grid-cell");
      cell.contentEditable = "plaintext-only";
      if (cell.contentEditable !== "plaintext-only") cell.contentEditable = "true";
      cell.spellcheck = false;
      cell.dataset.r = String(r);
      cell.dataset.c = String(c);
      cell.setAttribute("role", tag === "th" ? "columnheader" : "gridcell");
      cell.tabIndex = r === state.active.r && c === state.active.c ? 0 : -1;
      cell.textContent = state.model.rows[r].cells[c]?.text ?? "";
      sizeCell(cell, state.view.widths[c]);
      tr.append(cell);
    }
    return tr;
  }

  //: The rows under the header: only this is redrawn while a filter box is typed in.
  function fillBody() {
    const { model, view } = state;
    const cols = Math.max(columns(model), 1);
    state.order = viewOrder(model, view.header, view.sort, view.filters);
    const first = view.header ? 1 : 0;
    const shown = state.order.slice(first, first + MAX_ROWS);
    const body = state.table.tBodies[0];
    body.textContent = "";
    for (const r of shown) body.append(rowEl(r, cols, "td"));
    for (const note of state.root.querySelectorAll(".csv-grid-more")) note.remove();
    if (state.order.length - first > shown.length) state.table.after(el("p", "csv-grid-more", `Only the first ${MAX_ROWS} rows are shown. Narrow the filters or edit the text for the rest.`));
    else if (!shown.length && model.rows.length > first) state.table.after(el("p", "csv-grid-more", "No rows match the filters."));
    describe();
  }

  function render() {
    const { model, view } = state;
    const cols = Math.max(columns(model), 1);
    const table = state.table;
    table.textContent = "";
    for (const note of state.root.querySelectorAll(".csv-grid-more, .csv-grid-empty")) note.remove();
    for (const [key, on] of [["header", view.header], ["filter", view.filterOpen]]) {
      state.bar[key]?.setAttribute("aria-pressed", String(on));
      state.bar[key]?.classList.toggle("active", on);
    }
    if (!model.rows.length) {
      table.after(el("p", "csv-grid-empty", "This file has no rows yet. Add a row to start."));
      state.order = [];
      describe();
      return;
    }
    const head = el("thead");
    const ctl = el("tr", "csv-grid-ctl-row");
    ctl.append(el("th", "csv-grid-num csv-grid-corner"));
    for (let c = 0; c < cols; c++) ctl.append(ctlCell(c));
    head.append(ctl);
    if (view.header) {
      const top = rowEl(0, cols, "th");
      top.classList.add("csv-grid-head-row");
      head.append(top);
    }
    table.append(head, el("tbody"));
    fillBody();
    for (const c of Object.keys(view.widths)) applyWidth(Number(c));
    //: The header row sticks under the controls row, so it needs that row's own height.
    const under = `${ctl.getBoundingClientRect().height}px`;
    for (const cell of head.querySelectorAll(".csv-grid-head-row .csv-grid-cell")) cell.style.insetBlockStart = under;
  }

  //: Read the text again and redraw, keeping the cell you were in.
  function reload() {
    state.model = parse(text(), delimiterOf(text(), state.title));
    render();
  }

  //: A structural change: written, read back, redrawn, and the cursor put where it makes sense.
  function structural(changes, then, message) {
    write(changes);
    reload();
    if (then) {
      state.active = { r: Math.max(0, then.r), c: Math.max(0, then.c) };
      focusCell(state.active.r, state.active.c);
    }
    //: toastAction, not toast: a plain toast drops its action, so the old Undo on Row deleted never showed.
    if (message) toastAction(message, "Undo", () => undoRedo(false));
  }

  function undoRedo(redo) {
    const CM = window.CM6;
    if (!CM?.commands || !docCmView) return;
    (redo ? CM.commands.redo : CM.commands.undo)(docCmView);
    if (state.open) reload();
  }

  //: A cell was typed in: its span in the text is rewritten, and every span after it moves by the difference.
  function edited(cell) {
    const r = Number(cell.dataset.r);
    const c = Number(cell.dataset.c);
    const value = cell.textContent;
    const { model } = state;
    const row = model.rows[r];
    if (!row) return;
    const changes = ops.setCell(model, r, c, value);
    write(changes);
    const change = changes[0];
    if (c >= row.cells.length) {
      state.model = parse(text(), model.delim);
      return;
    }
    const delta = change.insert.length - (change.to - change.from);
    row.cells[c].to = change.from + change.insert.length;
    row.cells[c].text = value;
    let seen = false;
    for (const each of model.rows) {
      for (const one of each.cells) {
        if (one === row.cells[c]) { seen = true; continue; }
        if (!seen) continue;
        one.from += delta;
        one.to += delta;
      }
      if (each !== row && seen) { each.from += delta; each.to += delta; each.next += delta; }
      if (each === row) { each.to += delta; each.next += delta; }
    }
    model.length += delta;
  }

  function atEdge(cell, end) {
    const selection = window.getSelection();
    if (!selection.rangeCount) return true;
    const range = selection.getRangeAt(0);
    if (!cell.contains(range.startContainer)) return true;
    const length = cell.textContent.length;
    //: Everything selected (a cell just entered): either arrow leaves it.
    if (length > 0 && range.toString().length >= length) return true;
    if (!selection.isCollapsed) return false;
    const probe = document.createRange();
    probe.selectNodeContents(cell);
    probe.setEnd(range.endContainer, range.endOffset);
    const before = probe.toString().length;
    return end ? before >= length : before === 0;
  }

  function onKey(event) {
    const cell = event.target.closest?.(".csv-grid-cell");
    if (!cell) return;
    const r = Number(cell.dataset.r);
    const c = Number(cell.dataset.c);
    const mod = event.ctrlKey || event.metaKey;
    if (mod && !event.altKey && /^[zy]$/i.test(event.key)) {
      event.preventDefault();
      undoRedo(event.key.toLowerCase() === "y" || event.shiftKey);
      return;
    }
    const cols = columns(state.model);
    //: Rows are walked in the order the view shows them (sorted, filtered), not the file's.
    const { order } = state;
    const at = order.indexOf(r);
    const near = (step) => order[at + step] ?? -1;
    let to = null;
    if (event.key === "Tab") {
      const spot = at * cols + c + (event.shiftKey ? -1 : 1);
      //: At either end Tab leaves the grid, as it leaves any other control.
      if (spot >= 0 && spot < order.length * cols) to = { r: order[Math.floor(spot / cols)], c: spot % cols };
    } else if (event.key === "Enter") {
      if (event.altKey) {
        event.preventDefault();
        document.execCommand("insertText", false, "\n");
        return;
      }
      to = { r: near(event.shiftKey ? -1 : 1), c };
    } else if (event.key === "ArrowDown" && !mod) to = { r: near(1), c };
    else if (event.key === "ArrowUp" && !mod) to = { r: near(-1), c };
    else if (event.key === "ArrowRight" && !mod && atEdge(cell, true)) to = { r, c: c + 1 };
    else if (event.key === "ArrowLeft" && !mod && atEdge(cell, false)) to = { r, c: c - 1 };
    else if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (!to) return;
    event.preventDefault();
    if (to.r >= 0 && to.c >= 0 && to.c < cols) focusCell(to.r, to.c);
  }

  //: Rows go down the view's order from the cell you are in, so a sorted or filtered view pastes the way it reads; past its
  //: last row, and past the file's, the block makes new rows at the end.
  function pasteBlockAt(r, c, block) {
    const at = state.order.indexOf(r);
    const targets = block.map((_, i) => state.order[at + i]);
    const wide = Math.max(...block.map((row) => row.length));
    const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
    structural(pasteBlock(state.model, targets, c, block), { r, c }, `Pasted ${plural(block.length, "row")} by ${plural(wide, "column")}.`);
  }

  function build() {
    const root = el("div", "csv-grid hidden");
    root.setAttribute("aria-label", "Table editor");
    const bar = el("div", "dock csv-grid-bar");
    const identity = el("div", "dock-identity");
    identity.append(el("h2", "", "Grid"));
    state.chip = el("span", "dock-chip");
    state.chip.setAttribute("aria-live", "polite");
    identity.append(state.chip);
    const actions = el("div", "dock-actions");
    const here = () => state.active;
    actions.append(
      barButton("ph-rows-plus-bottom", "Add row", "Add a blank row below this one", () => structural(ops.addRow(state.model, here().r, true), { r: here().r + 1, c: here().c })),
      barButton("ph-columns-plus-right", "Add column", "Add an empty column to the right of this one", () => structural(ops.addColumn(state.model, here().c + 1), { r: here().r, c: here().c + 1 })),
      barButton("ph-trash", "Delete row", "Delete this row (Undo brings it back)", () => structural(ops.deleteRow(state.model, here().r), { r: Math.min(here().r, state.model.rows.length - 2), c: here().c }, "Row deleted.")),
      barButton("ph-trash", "Delete column", "Delete this column (Undo brings it back)", () => structural(ops.deleteColumn(state.model, here().c), { r: here().r, c: Math.min(here().c, columns(state.model) - 2) }, "Column deleted.")),
    );
    //: Two toggles of the view: whether row 1 is the header (kept for this document) and the row of filter boxes.
    state.bar.header = barButton("ph-text-h", "Header row", "Treat row 1 as the header: it stays on top when the view is sorted or filtered", () => {
      state.view.header = !state.view.header;
      const key = `${HEADER_KEY}:${state.docId}`;
      if (state.view.header) prefs.remove(key);
      else prefs.set(key, "0");
      state.view.sort = null;
      state.view.filters = {};
      render();
    });
    state.bar.filter = barButton("ph-funnel", "Filters", "Show a box under each column heading to hide the rows that do not contain its text (the file keeps them)", () => {
      state.view.filterOpen = !state.view.filterOpen;
      if (!state.view.filterOpen) state.view.filters = {};
      render();
    });
    for (const button of [state.bar.header, state.bar.filter]) button.setAttribute("aria-pressed", "false");
    actions.prepend(state.bar.header, state.bar.filter);
    //: The keys are in the dock's own About these controls (index.html), not a second popover here.
    bar.append(identity, actions);
    const scroll = el("div", "csv-grid-scroll");
    scroll.tabIndex = -1;
    const table = el("table", "csv-grid-table");
    table.setAttribute("role", "grid");
    table.setAttribute("aria-label", "Cells of this file");
    scroll.append(table);
    root.append(bar, scroll);
    state.table = table;
    state.root = root;
    table.addEventListener("input", (event) => {
      const cell = event.target.closest?.(".csv-grid-cell");
      if (cell) edited(cell);
    });
    table.addEventListener("keydown", onKey);
    table.addEventListener("input", (event) => {
      const box = event.target.closest?.(".csv-grid-filter");
      if (!box) return;
      state.view.filters[box.dataset.f] = box.value;
      fillBody();
    });
    table.addEventListener("keydown", (event) => {
      const grip = event.target.closest?.(".csv-grid-grip");
      if (!grip) return;
      const c = Number(grip.dataset.c);
      const step = (event.shiftKey ? 4 : 1) * WIDTH_STEP;
      if (event.key === "ArrowRight" || event.key === "ArrowLeft") setWidth(c, widthOf(c) + (event.key === "ArrowRight" ? step : -step));
      else if (event.key === "Home") setWidth(c, null);
      else return;
      event.preventDefault();
    });
    //: Dragging a column's edge: the pointer is captured by the grip, so it can leave the header while it moves.
    table.addEventListener("pointerdown", (event) => {
      const grip = event.target.closest?.(".csv-grid-grip");
      if (!grip || event.button !== 0) return;
      event.preventDefault();
      const c = Number(grip.dataset.c);
      const x0 = event.clientX;
      const w0 = widthOf(c);
      const sign = getComputedStyle(table).direction === "rtl" ? -1 : 1;
      grip.setPointerCapture(event.pointerId);
      grip.classList.add("dragging");
      const move = (e) => setWidth(c, w0 + sign * (e.clientX - x0));
      const up = () => {
        grip.classList.remove("dragging");
        grip.removeEventListener("pointermove", move);
        grip.removeEventListener("pointerup", up);
        grip.removeEventListener("pointercancel", up);
      };
      grip.addEventListener("pointermove", move);
      grip.addEventListener("pointerup", up);
      grip.addEventListener("pointercancel", up);
    });
    table.addEventListener("dblclick", (event) => {
      const grip = event.target.closest?.(".csv-grid-grip");
      if (grip) setWidth(Number(grip.dataset.c), null);
    });
    table.addEventListener("focusin", (event) => {
      const cell = event.target.closest?.(".csv-grid-cell");
      if (!cell) return;
      const prev = cellAt(state.active.r, state.active.c);
      if (prev) prev.tabIndex = -1;
      state.active = { r: Number(cell.dataset.r), c: Number(cell.dataset.c) };
      cell.tabIndex = 0;
      describe();
    });
    //: A paste is plain text, whatever the clipboard holds. Text with tabs or line breaks is a block of cells that lands
    //: with its top-left corner in the cell you are in, as one undo step; anything else is typed into the cell.
    table.addEventListener("paste", (event) => {
      const cell = event.target.closest?.(".csv-grid-cell");
      if (!cell) return;
      event.preventDefault();
      const clip = event.clipboardData.getData("text/plain");
      const single = clip.replace(/\r?\n$/, "");
      if (!/[\t\r\n]/.test(single)) return void document.execCommand("insertText", false, single);
      pasteBlockAt(Number(cell.dataset.r), Number(cell.dataset.c), clipRows(clip));
    });
    //: Dropped markup would make a cell hold elements, not text.
    table.addEventListener("drop", (event) => event.preventDefault());
    //: The text changed under the grid (Ctrl+Z in the editor, a version restored, another file opened).
    docSurface().onChange(() => {
      if (!state.open || state.writing) return;
      if (currentDoc?.id !== state.docId || docFileType().ext !== "csv") return close();
      reload();
    });
    document.getElementById("doc-panes").append(root);
  }

  function setButton(on) {
    for (const button of document.querySelectorAll("#doc-csv-grid, [data-click-proxy=doc-csv-grid]")) {
      button.setAttribute("aria-pressed", String(on));
      button.classList.toggle("active", on);
    }
  }

  function open() {
    if (!docCmView || !window.CM6) return toast("The grid needs the editor, which is not loaded.", "info");
    if (docFileType().ext !== "csv") return;
    if (text().length > MAX_CHARS) return toast("This file is too large for the grid. Edit it as text.", "info");
    if (!state.root) build();
    state.open = true;
    state.docId = currentDoc?.id ?? null;
    state.title = currentDoc?.title || "";
    state.active = { r: 0, c: 0 };
    //: A view belongs to one document: another file starts unsorted and unfiltered, its header choice read from prefs.
    state.view = { header: prefs.get(`${HEADER_KEY}:${state.docId}`, "1") !== "0", sort: null, filters: {}, widths: {}, filterOpen: false };
    reload();
    state.root.classList.remove("hidden");
    document.getElementById("doc-panes").classList.add("csv-grid-on");
    setButton(true);
    if (state.model.rows.length) focusCell(0, 0);
  }

  function close() {
    if (!state.root || !state.open) return;
    state.open = false;
    state.root.classList.add("hidden");
    document.getElementById("doc-panes").classList.remove("csv-grid-on");
    setButton(false);
    docCmView?.focus();
  }

  docViewState.csvGrid = { open, close, toggle: () => (state.open ? close() : open()), isOpen: () => state.open, forDoc: () => state.docId };
})();
