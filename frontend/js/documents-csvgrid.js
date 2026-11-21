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
  // DOC-CSVGRID-END

  const MAX_ROWS = 1000;
  const MAX_CHARS = 2_000_000;
  const state = { open: false, model: null, docId: null, active: { r: 0, c: 0 }, writing: false, root: null, table: null, chip: null, wired: false, title: "" };

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
    const rows = Math.min(state.model.rows.length, MAX_ROWS);
    const cols = columns(state.model);
    const cell = cellAt(Math.max(0, Math.min(r, rows - 1)), Math.max(0, Math.min(c, cols - 1)));
    if (!cell) return false;
    cell.focus();
    if (select) selectAll(cell);
    return true;
  }

  function describe() {
    const { r, c } = state.active;
    const total = state.model.rows.length;
    state.chip.textContent = total ? `Row ${r + 1} of ${total}, column ${c + 1}` : "No rows yet";
  }

  function render() {
    const { model } = state;
    const cols = Math.max(columns(model), 1);
    const shown = Math.min(model.rows.length, MAX_ROWS);
    const table = state.table;
    table.textContent = "";
    if (!model.rows.length) {
      const empty = el("p", "csv-grid-empty", "This file has no rows yet. Add a row to start.");
      table.append(empty);
      describe();
      return;
    }
    const head = el("thead");
    const body = el("tbody");
    for (let r = 0; r < shown; r++) {
      const tr = el("tr");
      const gutter = el("th", "csv-grid-num", String(r + 1));
      gutter.scope = "row";
      tr.append(gutter);
      for (let c = 0; c < cols; c++) {
        const cell = el(r === 0 ? "th" : "td", "csv-grid-cell");
        cell.contentEditable = "plaintext-only";
        if (cell.contentEditable !== "plaintext-only") cell.contentEditable = "true";
        cell.spellcheck = false;
        cell.dataset.r = String(r);
        cell.dataset.c = String(c);
        cell.setAttribute("role", r === 0 ? "columnheader" : "gridcell");
        cell.tabIndex = r === state.active.r && c === state.active.c ? 0 : -1;
        cell.textContent = model.rows[r].cells[c]?.text ?? "";
        tr.append(cell);
      }
      (r === 0 ? head : body).append(tr);
    }
    table.append(head, body);
    if (model.rows.length > shown) table.append(el("p", "csv-grid-more", `Only the first ${MAX_ROWS} rows are shown. Edit the text for the rest.`));
    describe();
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
    if (message) toast(message, "info", { action: ["Undo", () => { undoRedo(false); }] });
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
    const rows = Math.min(state.model.rows.length, MAX_ROWS);
    const cols = columns(state.model);
    let to = null;
    if (event.key === "Tab") {
      const step = event.shiftKey ? -1 : 1;
      const at = r * cols + c + step;
      //: At either end Tab leaves the grid, as it leaves any other control.
      if (at >= 0 && at < rows * cols) to = { r: Math.floor(at / cols), c: at % cols };
    } else if (event.key === "Enter") {
      if (event.altKey) {
        event.preventDefault();
        document.execCommand("insertText", false, "\n");
        return;
      }
      to = { r: r + (event.shiftKey ? -1 : 1), c };
    } else if (event.key === "ArrowDown" && !mod) to = { r: r + 1, c };
    else if (event.key === "ArrowUp" && !mod) to = { r: r - 1, c };
    else if (event.key === "ArrowRight" && !mod && atEdge(cell, true)) to = { r, c: c + 1 };
    else if (event.key === "ArrowLeft" && !mod && atEdge(cell, false)) to = { r, c: c - 1 };
    else if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (!to) return;
    event.preventDefault();
    if (to.r >= 0 && to.r < rows && to.c >= 0 && to.c < cols) focusCell(to.r, to.c);
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
    table.addEventListener("focusin", (event) => {
      const cell = event.target.closest?.(".csv-grid-cell");
      if (!cell) return;
      const prev = cellAt(state.active.r, state.active.c);
      if (prev) prev.tabIndex = -1;
      state.active = { r: Number(cell.dataset.r), c: Number(cell.dataset.c) };
      cell.tabIndex = 0;
      describe();
    });
    //: A paste is plain text, whatever the clipboard holds.
    table.addEventListener("paste", (event) => {
      if (!event.target.closest?.(".csv-grid-cell")) return;
      event.preventDefault();
      document.execCommand("insertText", false, event.clipboardData.getData("text/plain"));
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
