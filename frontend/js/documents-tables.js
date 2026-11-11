// documents-tables.js: the table model (split out of documents.js, audit 1031
// DC13 remainder).
//
// What is here: the pure string model between `DOC-TABLE-BEGIN` and
// `DOC-TABLE-END` (parse a table byte-exactly, every operation returning
// `{from, to, insert}` edits), which `tests/test_doc_tables.py` runs in node.
// What stayed in documents.js: the table commands that read the caret and
// dispatch these edits, and the Live grid's styles; documents-cm.js,
// documents-props.js and documents-prose.js call in here only from inside
// functions.
//
// **Loaded in the Library bundle, before documents.js**, the way
// documents-props.js is: this file's own top level declares a regular
// expression, a number and functions and reads nothing from documents.js. One
// closure; what other files call is the `Object.assign` at the foot.
(() => {
  // =============================================================================
  // Tables, as a model over the markdown rather than a second document
  // (DOCUMENTS_PLAN Phase 3 item 1)
  // =============================================================================
  //
  // **The gate this is written for, first, because it decides the whole shape.**
  // PLAN D4: a table edited in Live and then read in Source has to be the
  // markdown a person would have typed, byte for byte. The obvious
  // implementation, parse the table into a grid and print it back out, fails
  // that gate on its first keystroke: a hand-aligned table comes back with its
  // padding rebuilt, a ragged one comes back tidied, and a cell holding `\|`
  // comes back holding whatever the printer decided to do about pipes. The
  // document is then no longer the file its author wrote, which is the one
  // promise a markdown editor makes.
  //
  // So nothing here ever *prints a table*. Every operation returns a list of
  // `{from, to, insert}` edits in document coordinates, each one covering the
  // smallest span it can: setting a cell rewrites that cell's own characters
  // between its pipes and nothing else; adding a column inserts one `|` and one
  // cell per line; alignment rewrites one delimiter cell. Every byte the
  // operation did not have to touch is still the byte the author typed, which
  // is a stronger statement than "the output matches the input" and is what
  // `tests/test_doc_tables.py` measures: it applies an operation and its
  // inverse and compares the result to the original string.
  //
  // The parse is byte-exact by construction for the same reason: a row is kept
  // as its indent, whether it had a leading pipe, the raw text of each cell
  // *including its padding*, and whatever followed the last pipe.
  // `docTableJoinRow(docTableSplitRow(line)) === line` for every line, which the
  // test asserts over the awkward shapes (a pipe escaped inside a cell, a table
  // with no outer pipes, mismatched column widths, an indented table).
  //
  // This region is bracketed by `DOC-TABLE-BEGIN` / `DOC-TABLE-END` because the
  // test runs it in node, away from the browser: it is pure string work with no
  // DOM and no app globals in it, and that is a property worth keeping.

  // DOC-TABLE-BEGIN

  //: A delimiter cell is the `---`, `:---`, `---:` or `:---:` under a header.
  //: GFM wants at least one dash; the colons are the alignment.
  const DOC_TABLE_DELIM_CELL = /^[ \t]*:?-+:?[ \t]*$/;

  //: How many columns the Live grid can place by class. Every cell in the
  //: rendered line has to be *placed* rather than left to auto-flow, because a
  //: hidden pipe leaves three zero-width children behind it (two
  //: `cm-widgetBuffer` images and the replacement's own empty span) and
  //: auto-flow gives each of those a column of its own: a three-column table
  //: was drawn as fifteen tracks with the cells at 51.6px and the text wrapping
  //: inside them (INBOX 191). The classes are generated in pairs
  //: (`cm-md-cols-N` on the line, `cm-md-cN` on the cell), so the cap is only
  //: how many rules the theme carries; a table wider than this keeps the old
  //: auto-flow, which no editor of this width can show usefully anyway.
  const DOC_TABLE_GRID_MAX = 20;

  //: Split one line into the pieces that put it back together exactly.
  //: `cells` holds the raw text between the pipes, padding included, so the
  //: join below is the identity and an edit to one cell cannot disturb another.
  //: Only *unescaped* pipes split: `\|` is a pipe inside a cell, which is the
  //: one piece of table syntax people get wrong when they hand-edit.
  function docTableSplitRow(line) {
    const text = String(line);
    const indent = (/^[ \t]*/.exec(text) || [""])[0];
    let body = text.slice(indent.length);
    let lead = false;
    if (body.startsWith("|")) {
      lead = true;
      body = body.slice(1);
    }
    const cells = [];
    let cur = "";
    for (let at = 0; at < body.length; at += 1) {
      const ch = body[at];
      if (ch === "\\" && at + 1 < body.length) {
        cur += ch + body[at + 1];
        at += 1;
        continue;
      }
      if (ch === "|") {
        cells.push(cur);
        cur = "";
        continue;
      }
      cur += ch;
    }
    //: What follows the last pipe is the trailing pipe's own tail when it is
    //: only whitespace, and one more cell when it is not. `| a | b |   ` and
    //: `| a | b ` differ by exactly that, and both have to come back unchanged.
    let trail = false;
    let tail = "";
    if (cells.length && /^[ \t]*$/.test(cur)) {
      trail = true;
      tail = cur;
    } else {
      cells.push(cur);
    }
    return { indent, lead, cells, trail, tail };
  }

  function docTableJoinRow(row) {
    return (
      row.indent +
      (row.lead ? "|" : "") +
      row.cells.join("|") +
      (row.trail ? `|${row.tail}` : "")
    );
  }

  //: A line that could be part of a table: it has a pipe that is not escaped,
  //: and it is not blank. Deliberately loose, because what actually makes a
  //: table in GFM is the delimiter row underneath the header, which
  //: `docTableParse` checks.
  function docTableRowLike(line) {
    const text = String(line == null ? "" : line);
    if (!text.trim()) return false;
    return docTableSplitRow(text).cells.length > 1 || /(?:^|[^\\])\|/.test(text);
  }

  function docTableIsDelimiter(line) {
    if (line == null) return false;
    const row = docTableSplitRow(line);
    if (!row.cells.length) return false;
    return row.cells.every((cell) => DOC_TABLE_DELIM_CELL.test(cell));
  }

  function docTableAlignOf(cell) {
    const text = String(cell).trim();
    const left = text.startsWith(":");
    const right = text.endsWith(":");
    if (left && right) return "center";
    if (right) return "right";
    if (left) return "left";
    return null;
  }

  //: The table around a document offset, or null. Offsets are the document's,
  //: so every edit below can be dispatched without a second coordinate system.
  //:
  //: The run of pipe-bearing lines around the caret is found first and the
  //: delimiter row is then looked for *inside* it, rather than assuming it sits
  //: at the second line: a paragraph line that happens to contain a pipe sits
  //: directly above plenty of real tables, and taking the run's first line as
  //: the header would have made every such table unparseable.
  function docTableParse(text, offset) {
    const lines = String(text == null ? "" : text).split("\n");
    const starts = [];
    let at = 0;
    for (const line of lines) {
      starts.push(at);
      at += line.length + 1;
    }
    let index = 0;
    for (let i = 0; i < lines.length; i += 1) {
      if (offset >= starts[i]) index = i;
      else break;
    }
    if (!docTableRowLike(lines[index])) return null;
    let first = index;
    while (first > 0 && docTableRowLike(lines[first - 1])) first -= 1;
    let last = index;
    while (last + 1 < lines.length && docTableRowLike(lines[last + 1])) last += 1;

    let delim = -1;
    for (let i = first + 1; i <= last; i += 1) {
      if (docTableIsDelimiter(lines[i])) {
        delim = i;
        break;
      }
    }
    if (delim < 0) return null;
    const startLine = delim - 1;
    if (index < startLine) return null;
    let endLine = last;
    //: A second delimiter row means a second table underneath this one, and
    //: its header is the line above it.
    for (let i = delim + 1; i <= last; i += 1) {
      if (docTableIsDelimiter(lines[i])) {
        endLine = i - 2;
        break;
      }
    }
    if (endLine < delim || index > endLine) return null;

    const rows = [];
    for (let i = startLine; i <= endLine; i += 1) {
      const row = docTableSplitRow(lines[i]);
      row.from = starts[i];
      row.to = starts[i] + lines[i].length;
      row.line = i;
      rows.push(row);
    }
    //: GFM: the delimiter row has to have as many cells as the header, or the
    //: block is a paragraph that happens to contain dashes.
    if (rows[1].cells.length !== rows[0].cells.length) return null;
    return {
      from: rows[0].from,
      to: rows[rows.length - 1].to,
      startLine,
      endLine,
      rows,
      delim: 1,
      columns: rows[0].cells.length,
      aligns: rows[1].cells.map(docTableAlignOf),
    };
  }
  //: **The same table, parsed from its own lines** (audit 1102 DX1): `doc` is the editor's
  //: `Text`. The parse only ever reads the run of pipe lines around the offset, so the run is
  //: all it is given, and the offsets and line indexes are moved back to the document's. The
  //: whole-text call split all 3,120 lines once per visible table, per key. A property, not
  //: a name: the shared scope is at its cap (test_global_scope_ratchet).
  docTableParse.at = (doc, offset) => {
    const here = doc.lineAt(offset);
    if (!docTableRowLike(here.text)) return null;
    let first = here.number;
    let last = here.number;
    while (first > 1 && docTableRowLike(doc.line(first - 1).text)) first -= 1;
    while (last < doc.lines && docTableRowLike(doc.line(last + 1).text)) last += 1;
    const base = doc.line(first).from;
    const table = docTableParse(doc.sliceString(base, doc.line(last).to), offset - base);
    if (!table) return null;
    for (const row of table.rows) {
      row.from += base;
      row.to += base;
      row.line += first - 1;
    }
    return { ...table, from: table.from + base, to: table.to + base, startLine: table.startLine + first - 1, endLine: table.endLine + first - 1 };
  };

  //: Where one cell's raw text lives in the document. The sum of the cells
  //: before it plus one character per pipe between them, which is the only
  //: arithmetic in this file and the reason the row keeps its pieces.
  function docTableCellSpan(table, row, col) {
    const line = table.rows[row];
    if (!line || col < 0 || col >= line.cells.length) return null;
    let from = line.from + line.indent.length + (line.lead ? 1 : 0);
    for (let i = 0; i < col; i += 1) from += line.cells[i].length + 1;
    return { from, to: from + line.cells[col].length };
  }

  //: The width a *new* cell in this column is written at. A table whose column
  //: is already one width everywhere is a table somebody has been keeping
  //: aligned by hand, and a new row that breaks the alignment is a new row they
  //: have to go and fix; a ragged column gets a single space, because padding
  //: it to the widest cell would be tidying up text nobody asked to have
  //: tidied. Neither case moves a byte that already exists.
  function docTableColumnPad(table, col, body) {
    const widths = new Set();
    for (let i = 0; i < table.rows.length; i += 1) {
      const cell = table.rows[i].cells[col];
      if (cell == null) continue;
      widths.add(cell.length);
    }
    const text = ` ${body} `;
    if (widths.size !== 1) return text;
    const width = [...widths][0];
    return text.length >= width ? text : text + " ".repeat(width - text.length);
  }

  //: A new row, built from the row above it so the outer pipes and the indent
  //: match the table they are joining rather than one house style.
  function docTableAddRowEdits(table, afterRow) {
    const like = table.rows[Math.max(afterRow, table.delim)] || table.rows[0];
    const cells = [];
    for (let col = 0; col < table.columns; col += 1) cells.push(docTableColumnPad(table, col, ""));
    const line = docTableJoinRow({
      indent: like.indent,
      lead: like.lead,
      cells,
      trail: like.trail,
      tail: "",
    });
    const anchor = table.rows[Math.max(afterRow, table.delim)] || table.rows[table.rows.length - 1];
    return [{ from: anchor.to, to: anchor.to, insert: `\n${line}` }];
  }

  //: Only a body row can go: deleting the header or the delimiter deletes the
  //: table, which is a different command with a different name.
  function docTableRemoveRowEdits(table, row) {
    if (row <= table.delim || row >= table.rows.length) return [];
    const line = table.rows[row];
    return [{ from: line.from - 1, to: line.to, insert: "" }];
  }

  //: One `|` and one cell per line, inserted at the same column in each. The
  //: delimiter row gets a run of dashes as long as the one already under the
  //: column it is following, so a table written with `---` does not acquire a
  //: `----------` in the middle of it.
  function docTableAddColumnEdits(table, anchorCol, before = false) {
    const edits = [];
    const afterCol = anchorCol;
    const sample = Math.min(anchorCol, table.columns - 1);
    const dashSample = table.rows[table.delim].cells[sample] || " --- ";
    const dashes = "-".repeat(Math.max(3, (dashSample.match(/-/g) || []).length));
    for (let row = 0; row < table.rows.length; row += 1) {
      const line = table.rows[row];
      const col = Math.min(afterCol, line.cells.length - 1);
      const span = docTableCellSpan(table, row, col);
      if (!span) continue;
      const last = col >= line.cells.length - 1;
      let body;
      if (row === table.delim) body = ` ${dashes} `;
      //: **The header's new cell is named**, and not only because Notion and
      //: Obsidian name theirs. A blank cell at the end of a row that has no
      //: trailing pipe is dropped by GFM, so a nameless new column in a table
      //: written without outer pipes would leave the header one cell short of
      //: the delimiter row and stop the whole block being a table at all.
      else if (row === 0) body = docTableColumnPad(table, sample, "Column");
      else body = docTableColumnPad(table, sample, "");
      //: A body row that cannot hold a blank final cell is left alone: GFM pads
      //: a short row out to the header's width, so the column is there in the
      //: rendered table, and `docTableFillRowEdits` appends it for real when
      //: Tab sends the caret into it. Inserting whitespace GFM is going to drop would put bytes
      //: in the file that nothing in the editor could ever reach again.
      //: Inserting *before* a cell needs no such care: the new cell has a real
      //: one after it, so nothing can drop it, and the pipe goes on its right.
      //: A row too short to have this column is left for GFM to pad, exactly as
      //: above, rather than having a column inserted in the wrong place in it.
      if (before) {
        if (anchorCol > line.cells.length - 1) continue;
        //: **A first column needs a leading pipe, and that is markdown's rule
        //: rather than this editor's.** GFM strips one optional pipe from each
        //: end of a row and reads leading spaces as indentation, so there is no
        //: way to write a blank *first* cell in a row that has no outer pipes:
        //: `  | a | b` is an indented two-cell row, not a three-cell one with an
        //: empty cell at the front. A table written without outer pipes
        //: therefore gains a leading pipe on the day a column is put in front of
        //: it, and keeps it if that column is taken away again. It is the only
        //: byte in this file an operation adds that its inverse does not remove,
        //: and `tests/test_doc_tables.py` asserts exactly that rather than
        //: letting it pass as a round trip.
        const outer = anchorCol === 0 && !line.lead ? "|" : "";
        edits.push({ from: span.from, to: span.from, insert: `${outer}${body}|` });
        continue;
      }
      if (row !== 0 && row !== table.delim && last && !line.trail) continue;
      edits.push({ from: span.to, to: span.to, insert: `|${body}` });
    }
    return edits;
  }

  function docTableRemoveColumnEdits(table, col) {
    if (table.columns < 2) return [];
    const edits = [];
    for (let row = 0; row < table.rows.length; row += 1) {
      const line = table.rows[row];
      if (col >= line.cells.length) continue;
      //: The pipe that goes with the cell is the one *before* it, except for
      //: the first column, which owns the pipe after it instead. Taking the
      //: wrong one leaves a row with one separator too few and turns the rest
      //: of the table into one wide cell.
      const span = docTableCellSpan(table, row, col);
      if (col > 0) {
        const prev = docTableCellSpan(table, row, col - 1);
        edits.push({ from: prev.to, to: span.to, insert: "" });
      } else if (line.cells.length > 1) {
        const next = docTableCellSpan(table, row, 1);
        edits.push({ from: span.from, to: next.from, insert: "" });
      } else {
        edits.push({ from: span.from, to: span.to, insert: "" });
      }
    }
    return edits;
  }

  //: The cells a row is missing, appended. GFM pads a short row out to the
  //: header's width when it renders it, so those cells are visible in the table
  //: and absent from the text; this is what makes one real, and it is called
  //: when the caret is sent into one (Tab) rather than on sight, so a ragged
  //: table nobody is editing keeps the bytes it has.
  function docTableFillRowEdits(table, row, upto) {
    const line = table.rows[row];
    if (!line || upto < line.cells.length) return [];
    const last = docTableCellSpan(table, row, line.cells.length - 1);
    const at = line.trail ? last.to : line.to;
    let insert = "";
    for (let col = line.cells.length; col <= upto; col += 1) insert += `|${docTableColumnPad(table, col, "")}`;
    //: A blank cell at the end of a row with no trailing pipe is not a cell:
    //: GFM drops a row's optional trailing pipe and everything after the last
    //: one, so the row would come back one cell short of its header. The pipe
    //: is what makes the cell exist in the text rather than only in the render.
    if (!line.trail) insert += "|";
    return [{ from: at, to: at, insert }];
  }

  //: Alignment is a property of the delimiter cell and of nothing else, so it
  //: is one edit to one cell. The dash run is kept at the length the author
  //: wrote; the colons are added or removed around it.
  function docTableAlignEdits(table, col, align) {
    const span = docTableCellSpan(table, table.delim, col);
    if (!span) return [];
    const raw = table.rows[table.delim].cells[col];
    const parts = /^([ \t]*)([\s\S]*?)([ \t]*)$/.exec(raw);
    const dashes = "-".repeat(Math.max(3, (parts[2].match(/-/g) || []).length));
    const body =
      align === "center" ? `:${dashes}:` : align === "right" ? `${dashes}:` : align === "left" ? `:${dashes}` : dashes;
    const insert = parts[1] + body + parts[3];
    if (insert === raw) return [];
    return [{ from: span.from, to: span.to, insert }];
  }

  //: **Managing a table by its rows and columns** (INBOX 904 B23): move a row
  //: or a column one place, sort the body by a column, and the ranges a row, a
  //: column or the whole table is, for selecting. Edits like every operation
  //: here: a row moves by re-writing the lines between its two places with
  //: their own bytes in the new order, a column by moving each row's cell (the
  //: alignment marker goes with its column). `delta` is any distance: the menu
  //: moves one place, the edge grips drag to any place (B23).
  function docTableMoveRowEdits(table, row, delta) {
    const to = row + delta;
    const first = table.delim + 1;
    if (row < first || to < first || row >= table.rows.length || to >= table.rows.length || !delta) return [];
    const body = table.rows.slice(first);
    const moved = body.slice();
    moved.splice(to - first, 0, moved.splice(row - first, 1)[0]);
    const edits = [];
    body.forEach((place, i) => {
      if (moved[i] !== place) edits.push({ from: place.from, to: place.to, insert: docTableJoinRow(moved[i]) });
    });
    return edits;
  }

  function docTableMoveColumnEdits(table, col, delta) {
    const to = col + delta;
    if (!delta || col < 0 || to < 0 || col >= table.columns || to >= table.columns) return [];
    const edits = [];
    for (const row of table.rows) {
      const cells = row.cells.slice();
      //: A short row gains the cell it lacks, with its closing pipe: a blank
      //: cell at the end of a row with no trailing pipe is not a cell.
      const padded = cells.length < table.columns;
      while (cells.length < table.columns) cells.push("  ");
      cells.splice(to, 0, cells.splice(col, 1)[0]);
      const next = { ...row, cells, trail: row.trail || padded, tail: row.trail ? row.tail : "" };
      edits.push({ from: row.from, to: row.to, insert: docTableJoinRow(next) });
    }
    return edits;
  }

  //: Numbers as numbers, words in natural order, blanks last in either
  //: direction, equal rows in the order they had.
  function docTableSortEdits(table, col, descending) {
    const first = table.delim + 1;
    const body = table.rows.slice(first);
    if (body.length < 2 || col < 0 || col >= table.columns) return [];
    const key = (row) => (row.cells[col] || "").trim();
    const number = (text) => {
      const value = Number(text.replace(/[,\s]/g, ""));
      return text !== "" && Number.isFinite(value) ? value : null;
    };
    const order = (a, b) => {
      const ka = key(a);
      const kb = key(b);
      if (ka === "" || kb === "") return ka === kb ? 0 : ka === "" ? 1 : -1;
      const na = number(ka);
      const nb = number(kb);
      const way = na != null && nb != null ? na - nb : ka.localeCompare(kb, undefined, { numeric: true, sensitivity: "base" });
      return descending ? -way : way;
    };
    const sorted = body.map((row, i) => ({ row, i })).sort((x, y) => order(x.row, y.row) || x.i - y.i);
    const edits = [];
    body.forEach((place, i) => {
      if (sorted[i].row !== place) edits.push({ from: place.from, to: place.to, insert: docTableJoinRow(sorted[i].row) });
    });
    return edits;
  }

  //: What selecting a row, a column or the table selects: a row is its cells
  //: end to end, a column is each body cell's words (one range per row, the
  //: delimiter skipped), the table is its whole text.
  function docTableSelectRanges(table, kind, index) {
    if (kind === "table") return [{ from: table.from, to: table.to }];
    if (kind === "row") {
      const row = table.rows[index];
      if (!row || index === table.delim) return [];
      return [{ from: docTableCellSpan(table, index, 0).from, to: docTableCellSpan(table, index, row.cells.length - 1).to }];
    }
    if (kind !== "column" || index < 0 || index >= table.columns) return [];
    const ranges = [];
    for (let r = 0; r < table.rows.length; r += 1) {
      if (r === table.delim) continue;
      const span = docTableCellSpan(table, r, index);
      if (!span) continue;
      const raw = table.rows[r].cells[index];
      const lead = (/^[ \t]*/.exec(raw) || [""])[0].length;
      const tail = (/[ \t]*$/.exec(raw) || [""])[0].length;
      const from = span.from + (raw.trim() ? lead : Math.min(1, raw.length));
      ranges.push({ from, to: raw.trim() ? span.to - tail : from });
    }
    return ranges;
  }

  //: The edits applied to a plain string, which is what the fallback surface
  //: and the test both need. Back to front so an earlier edit cannot move a
  //: later one's offsets.
  function docTableApplyEdits(text, edits) {
    let out = String(text == null ? "" : text);
    const ordered = [...edits].sort((a, b) => b.from - a.from);
    for (const edit of ordered) out = out.slice(0, edit.from) + edit.insert + out.slice(edit.to);
    return out;
  }

  //: Which cell an offset is in, for Tab and for the cell menu.
  function docTableCellAt(table, offset) {
    for (let row = 0; row < table.rows.length; row += 1) {
      const line = table.rows[row];
      if (offset < line.from || offset > line.to) continue;
      for (let col = 0; col < line.cells.length; col += 1) {
        const span = docTableCellSpan(table, row, col);
        if (offset >= span.from && offset <= span.to) return { row, col, ...span };
      }
      return { row, col: Math.max(0, line.cells.length - 1), ...docTableCellSpan(table, row, Math.max(0, line.cells.length - 1)) };
    }
    return null;
  }

  //: The cell Tab goes to, wrapping across rows. `null` at the end of the last
  //: row means "there is no next cell", which is the caller's cue to add a row:
  //: Tab at the end of a table making a new row is the behaviour every editor
  //: in the plan's competitor table has.
  function docTableStepCell(table, row, col, delta) {
    let r = row;
    let c = col + delta;
    {
      if (c < 0) {
        r -= 1;
        if (r === table.delim) r -= 1;
        if (r < 0) return null;
        c = Math.max(table.columns, table.rows[r].cells.length) - 1;
        if (c < 0) return null;
        return { row: r, col: c };
      }
      if (c >= Math.max(table.columns, table.rows[r].cells.length)) {
        r += 1;
        if (r === table.delim) r += 1;
        if (r >= table.rows.length) return null;
        c = 0;
        if (!table.rows[r].cells.length) return null;
        return { row: r, col: c };
      }
      return { row: r, col: c };
    }
  }

  //: The row an arrow or Enter goes to from `row`, stepping over the delimiter
  //: (which is the header's underline, not a row anyone writes in). `null`
  //: past either end: the caller's cue to leave the table or to add a row.
  //: INBOX 425 i: measured before this, ArrowDown from the third column
  //: landed in the fourth, because the editor moves by pixels and the cells
  //: of the next row are laid out by a grid it cannot see.
  function docTableStepRow(table, row, delta) {
    let r = row + delta;
    if (r === table.delim) r += delta;
    if (r < 0 || r >= table.rows.length) return null;
    return r;
  }

  //: The way out of a table below: the edits and the caret. The caret lands
  //: after one blank line, added when missing: text on the very next line
  //: would be read as one more row. `dropLast` first removes the last row,
  //: for Enter on an empty one (Notion and Google Docs do the same);
  //: Ctrl+Enter keeps every row, in Source too.
  function docTableExitEdit(table, text, dropLast) {
    const end = table.to;
    const from = dropLast ? table.rows[table.rows.length - 1].from - 1 : end;
    const lead = Math.min(2, /^\n*/.exec(text.slice(end))[0].length);
    const changes = dropLast ? [{ from, to: end, insert: "" }] : [];
    if (lead < 2) changes.push({ from: end + lead, to: end + lead, insert: "\n".repeat(2 - lead) });
    return { changes, anchor: from + 2 };
  }

  //: A cell's text as markdown can hold it: one line, and a pipe escaped so it
  //: stays inside its cell rather than opening a new one. An already escaped
  //: pipe is kept as it is.
  function docTableEscapeCell(text) {
    return String(text == null ? "" : text)
      .replace(/[\r\n]+/g, " ")
      .trim()
      .replace(/\\\|/g, "\u0000")
      .replace(/\|/g, "\\|")
      .replace(/\u0000/g, "\\|");
  }

  //: What a spreadsheet puts on the clipboard: rows on lines, cells split by
  //: tabs. `null` for anything without a tab, which is ordinary text and is
  //: pasted as it is. A trailing newline (every spreadsheet adds one) is not a
  //: row.
  function docTableGridFromText(text) {
    if (typeof text !== "string" || text.indexOf("\t") === -1) return null;
    const lines = text.replace(/\r\n?/g, "\n").split("\n");
    while (lines.length && lines[lines.length - 1] === "") lines.pop();
    if (!lines.length) return null;
    return lines.map((line) => line.split("\t").map(docTableEscapeCell));
  }

  //: A new table from a grid, its first row as the header. Written the way
  //: this editor writes a new row (`| a | b |`, a space either side), so a
  //: pasted table and a typed one look the same in Source.
  function docTableFromGrid(grid) {
    const width = Math.max(1, ...grid.map((row) => row.length));
    const line = (cells) =>
      "|" + Array.from({ length: width }, (_, i) => ` ${cells[i] == null ? "" : cells[i]} `).join("|") + "|";
    return [line(grid[0] || []), "|" + Array.from({ length: width }, () => " --- ").join("|") + "|",
      ...grid.slice(1).map(line)].join("\n");
  }

  //: The edits that put `text` into cells, each cell keeping the padding it
  //: was written with: the words between the spaces change and nothing else,
  //: the same promise every operation above keeps. A blank cell has no words
  //: to stand between, so it is written ` text `, as a new row's cells are.
  function docTableSetCellEdits(table, cells) {
    const edits = [];
    for (const { row, col, text } of cells) {
      const span = docTableCellSpan(table, row, col);
      if (!span) continue;
      const raw = table.rows[row].cells[col];
      if (!raw.trim()) {
        edits.push({ from: span.from, to: span.to, insert: ` ${text} ` });
        continue;
      }
      const lead = (/^[ \t]*/.exec(raw) || [""])[0].length;
      const tail = (/[ \t]*$/.exec(raw) || [""])[0].length;
      edits.push({ from: span.from + lead, to: span.to - tail, insert: text });
    }
    return edits;
  }

  //: **A spreadsheet's rows pasted into a table fill its cells** (INBOX 425 i,
  //: "paste from a spreadsheet"). Measured before this: the whole clipboard
  //: landed in the one cell the caret was in, tabs and newlines and all, and
  //: the three lines after it stopped being a table. From the caret's cell,
  //: right and down, one cell per value; rows and columns the table does not
  //: have yet are added the way Tab and the cell menu add them, and a paste on
  //: the delimiter starts on the first body row.
  //:
  //: Returns one edit covering the table, so the paste is one step of undo,
  //: and the cell the last value went into for the caret. Every byte of the
  //: table the paste did not have to change is still the author's.
  function docTablePasteEdits(text, table, row, col, grid) {
    if (!grid || !grid.length) return null;
    const from = table.from;
    let work = String(text);
    let t = table;
    const targets = [];
    let r = row === t.delim ? t.delim + 1 : row;
    for (let i = 0; i < grid.length; i += 1) {
      if (r === t.delim) r += 1;
      targets.push(r);
      r += 1;
    }
    while (t && t.rows.length <= targets[targets.length - 1]) {
      work = docTableApplyEdits(work, docTableAddRowEdits(t, t.rows.length - 1));
      t = docTableParse(work, from);
    }
    const width = Math.max(...grid.map((cells) => cells.length));
    while (t && t.columns < col + width) {
      work = docTableApplyEdits(work, docTableAddColumnEdits(t, t.columns - 1));
      t = docTableParse(work, from);
    }
    if (!t) return null;
    //: A row made short by GFM's padding gets its missing cells for real
    //: before anything is written into them, as Tab does.
    for (const target of targets) {
      work = docTableApplyEdits(work, docTableFillRowEdits(t, target, col + width - 1));
      t = docTableParse(work, from);
    }
    const cells = [];
    grid.forEach((values, i) =>
      values.forEach((value, j) => cells.push({ row: targets[i], col: col + j, text: value }))
    );
    work = docTableApplyEdits(work, docTableSetCellEdits(t, cells));
    const grown = work.length - String(text).length;
    return {
      edit: { from, to: table.to, insert: work.slice(from, table.to + grown) },
      row: targets[targets.length - 1],
      col: col + grid[grid.length - 1].length - 1,
    };
  }

  //: The text of a table's cells as rows, trimmed, the delimiter row left
  //: out: the sheet a formula reads (row 1 is the header, as on a ruled page).
  function docTableValues(table) {
    return table.rows.filter((_, i) => i !== table.delim).map((row) => {
      const cells = row.cells.map((cell) => cell.trim());
      while (cells.length < table.columns) cells.push("");
      return cells;
    });
  }

  //: **Simple formulas in a cell** (DOCUMENTS_PLAN gap row 12): `=SUM(B)`,
  //: `=AVG(B2:B5)`, `=COUNT(C)`, `=MIN` and `=MAX`, over a column or a range.
  //: The cell keeps the formula as its markdown; the result is drawn over it
  //: (Live when the caret is elsewhere, Read always), so a table read in Source
  //: is still the file the author wrote. A column alone is every body row.
  //: Only numbers count: blanks and words are skipped, `$` and thousands
  //: commas are read, and a formula cell is a word, so a total in the column
  //: it sums cannot count itself. Null when the text is not a formula.
  const DOC_TABLE_FORMULA = /^=\s*(SUM|AVG|AVERAGE|COUNT|MIN|MAX)\s*\(\s*([A-Z]+)(\d*)\s*(?::\s*([A-Z]+)(\d*))?\s*\)$/i;
  function docTableFormula(text, grid) {
    const m = DOC_TABLE_FORMULA.exec(String(text || "").trim());
    if (!m) return null;
    const colOf = (letters) => [...letters.toUpperCase()].reduce((n, ch) => n * 26 + ch.charCodeAt(0) - 64, 0) - 1;
    const c1 = colOf(m[2]);
    const c2 = m[4] ? colOf(m[4]) : c1;
    const r1 = m[3] ? Number(m[3]) : 2;
    const r2 = m[5] ? Number(m[5]) : m[3] && !m[4] ? r1 : grid.length;
    const width = Math.max(0, ...grid.map((row) => row.length));
    if (Math.min(c1, c2) < 0 || Math.max(c1, c2) >= width || r1 < 1 || r2 < r1) return "#REF";
    const nums = [];
    for (let r = r1; r <= Math.min(r2, grid.length); r += 1) {
      for (let c = Math.min(c1, c2); c <= Math.max(c1, c2); c += 1) {
        const raw = String((grid[r - 1] || [])[c] || "").replace(/[,\s$]/g, "");
        if (raw !== "" && Number.isFinite(Number(raw))) nums.push(Number(raw));
      }
    }
    const fn = m[1].toUpperCase();
    if (fn === "COUNT") return String(nums.length);
    if (!nums.length) return fn === "SUM" ? "0" : "#N/A";
    const sum = nums.reduce((a, b) => a + b, 0);
    const value = fn === "SUM" ? sum : fn === "MIN" ? Math.min(...nums) : fn === "MAX" ? Math.max(...nums) : sum / nums.length;
    return String(Number(value.toFixed(8)));
  }

  //: Read view's call (navigation.js): the result of a formula cell given the
  //: table's lines as written, or "" for any other cell.
  function docTableCell(text, lines) {
    text = String(text || "").trim();
    if (text[0] !== "=") return "";
    const table = docTableParse(lines.join("\n"), 0);
    return (table && docTableFormula(text, docTableValues(table))) || "";
  }

  //: **The filter row** (same gap row): the body rows whose cell in `col` (or
  //: any cell, `-1`) does not hold `needle`, as row indexes. A view, not an
  //: edit: the markdown keeps every row, so Source is untouched and clearing
  //: the filter brings them back.
  function docTableFilterHidden(table, col, needle) {
    const want = String(needle || "").trim().toLowerCase();
    const hidden = [];
    if (!want) return hidden;
    for (let r = table.delim + 1; r < table.rows.length; r += 1) {
      const cells = col < 0 ? table.rows[r].cells : [table.rows[r].cells[col] || ""];
      if (!cells.some((cell) => cell.toLowerCase().includes(want))) hidden.push(r);
    }
    return hidden;
  }

  // DOC-TABLE-END

  //: The file's whole surface: what documents.js and documents-cm.js call.
  Object.assign(window, { DOC_TABLE_GRID_MAX, docTableRowLike, docTableParse, docTableCellSpan, docTableAddRowEdits, docTableRemoveRowEdits, docTableAddColumnEdits, docTableRemoveColumnEdits, docTableFillRowEdits, docTableAlignEdits, docTableMoveRowEdits, docTableMoveColumnEdits, docTableSortEdits, docTableSelectRanges, docTableApplyEdits, docTableCellAt, docTableStepCell, docTableStepRow, docTableExitEdit, docTableEscapeCell, docTableGridFromText, docTableFromGrid, docTablePasteEdits });
  //: The formula and filter half hangs off the parse, as `.at` does: the shared scope has no room for four more names.
  docTableParse.calc = { values: docTableValues, formula: docTableFormula, hidden: docTableFilterHidden };
  docTableParse.cell = docTableCell;
})();
