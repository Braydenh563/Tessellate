// documents-tablemenu.js: the table commands, their menu and the row and column grips.
// Moved out of documents.js whole (L335) and wrapped: only what other files call goes on `window`; nothing here runs at load.
(() => {
  const DOC_TABLE_COMMANDS = [
    {
      id: "row-above",
      group: "rows",
      label: "Insert row above",
      title: "Add an empty row above this one",
      run: (context) =>
        docTableGo(context, docTableAddRowEdits(context.table, context.cell.row - 1),
          Math.max(context.cell.row, context.table.delim + 1), 0),
    },
    {
      id: "row-below",
      group: "rows",
      label: "Insert row below",
      title: "Add an empty row below this one",
      run: (context) =>
        docTableGo(context, docTableAddRowEdits(context.table, context.cell.row),
          Math.max(context.cell.row, context.table.delim) + 1, 0),
    },
    {
      id: "row-delete",
      group: "rows",
      label: "Delete row",
      title: "Remove this row",
      danger: true,
      //: The header and the delimiter are the table's shape rather than its
      //: contents: deleting either is "delete table", which is its own command.
      enabled: (context) => context.cell.row > context.table.delim,
      run: (context) =>
        docTableGo(context, docTableRemoveRowEdits(context.table, context.cell.row),
          Math.min(context.cell.row, context.table.rows.length - 2), context.cell.col),
    },
    {
      id: "col-left",
      group: "columns",
      label: "Insert column left",
      title: "Add a column before this one",
      run: (context) =>
        docTableGo(context, docTableAddColumnEdits(context.table, context.cell.col, true),
          context.cell.row, context.cell.col),
    },
    {
      id: "col-right",
      group: "columns",
      label: "Insert column right",
      title: "Add a column after this one",
      run: (context) =>
        docTableGo(context, docTableAddColumnEdits(context.table, context.cell.col),
          context.cell.row, context.cell.col + 1),
    },
    {
      id: "col-delete",
      group: "columns",
      label: "Delete column",
      title: "Remove this column",
      danger: true,
      enabled: (context) => context.table.columns > 1,
      run: (context) =>
        docTableGo(context, docTableRemoveColumnEdits(context.table, context.cell.col),
          context.cell.row, Math.max(0, context.cell.col - 1)),
    },
    {
      id: "row-up",
      group: "arrange",
      label: "Move row up",
      title: "Swap this row with the one above",
      enabled: (context) => context.cell.row > context.table.delim + 1,
      run: (context) =>
        docTableGo(context, docTableMoveRowEdits(context.table, context.cell.row, -1),
          context.cell.row - 1, context.cell.col),
    },
    {
      id: "row-down",
      group: "arrange",
      label: "Move row down",
      title: "Swap this row with the one below",
      enabled: (context) =>
        context.cell.row > context.table.delim && context.cell.row < context.table.rows.length - 1,
      run: (context) =>
        docTableGo(context, docTableMoveRowEdits(context.table, context.cell.row, 1),
          context.cell.row + 1, context.cell.col),
    },
    {
      id: "col-move-left",
      group: "arrange",
      label: "Move column left",
      title: "Swap this column with the one before it",
      enabled: (context) => context.cell.col > 0,
      run: (context) =>
        docTableGo(context, docTableMoveColumnEdits(context.table, context.cell.col, -1),
          context.cell.row, context.cell.col - 1),
    },
    {
      id: "col-move-right",
      group: "arrange",
      label: "Move column right",
      title: "Swap this column with the one after it",
      enabled: (context) => context.cell.col < context.table.columns - 1,
      run: (context) =>
        docTableGo(context, docTableMoveColumnEdits(context.table, context.cell.col, 1),
          context.cell.row, context.cell.col + 1),
    },
    {
      id: "sort-up",
      group: "arrange",
      label: "Sort A to Z",
      title: "Order the rows by this column, numbers as numbers",
      enabled: (context) => context.table.rows.length > context.table.delim + 2,
      run: (context) =>
        docTableGo(context, docTableSortEdits(context.table, context.cell.col, false),
          context.cell.row, context.cell.col),
    },
    {
      id: "sort-down",
      group: "arrange",
      label: "Sort Z to A",
      title: "Order the rows by this column, the other way",
      enabled: (context) => context.table.rows.length > context.table.delim + 2,
      run: (context) =>
        docTableGo(context, docTableSortEdits(context.table, context.cell.col, true),
          context.cell.row, context.cell.col),
    },
    {
      id: "filter",
      group: "filter",
      label: "Filter rows…",
      title: "Show only the rows whose cell in this column holds some text. The markdown keeps every row",
      enabled: (context) => !!context.surface.view && context.table.rows.length > context.table.delim + 1,
      run: (context) => {
        docViewState.tableFilter.ask(context);
        return true;
      },
    },
    {
      id: "filter-clear",
      group: "filter",
      label: "Show all rows",
      title: "Remove this table's filter",
      enabled: (context) => !!docViewState.tableFilter.of(context.table),
      run: (context) => {
        docViewState.tableFilter.set(context.surface.view, context.table, null);
        return true;
      },
    },
    ...[["sum", "Sum", "SUM"], ["avg", "Average", "AVG"], ["count", "Count", "COUNT"]].map(([id, word, fn]) => ({
      id: `formula-${id}`,
      group: "formula",
      label: `${word} of this column`,
      title: `Write =${fn}(column) in this cell: it shows the ${word.toLowerCase()} of the numbers in the column`,
      enabled: (context) => context.cell.row > context.table.delim,
      run: (context) =>
        docTableGo(context, docTableSetCellEdits(context.table, [{ row: context.cell.row, col: context.cell.col,
          text: `=${fn}(${docViewState.tableFilter.letters(context.cell.col)})` }]), context.cell.row, context.cell.col),
    })),
    {
      id: "select-row",
      group: "select",
      label: "Select row",
      title: "Select every cell of this row",
      enabled: (context) => context.cell.row !== context.table.delim,
      run: (context) => docTableSelect(context, "row"),
    },
    {
      id: "select-column",
      group: "select",
      label: "Select column",
      title: "Select this column's cells, to copy or clear them",
      run: (context) => docTableSelect(context, "column"),
    },
    {
      id: "select-table",
      group: "select",
      label: "Select table",
      title: "Select the whole table",
      run: (context) => docTableSelect(context, "table"),
    },
    {
      id: "align-left",
      group: "alignment",
      label: "Align left",
      title: "Align this column to the left",
      run: (context) => docTableGo(context, docTableAlignEdits(context.table, context.cell.col, "left"),
        context.cell.row, context.cell.col),
    },
    {
      id: "align-centre",
      group: "alignment",
      label: "Align centre",
      title: "Centre this column",
      run: (context) => docTableGo(context, docTableAlignEdits(context.table, context.cell.col, "center"),
        context.cell.row, context.cell.col),
    },
    {
      id: "align-right",
      group: "alignment",
      label: "Align right",
      title: "Align this column to the right",
      run: (context) => docTableGo(context, docTableAlignEdits(context.table, context.cell.col, "right"),
        context.cell.row, context.cell.col),
    },
    {
      id: "table-delete",
      group: "table",
      label: "Delete table",
      title: "Remove the whole table",
      danger: true,
      run: (context) => {
        docTableDispatch(context, docTableRemoveEdits(context));
        return true;
      },
    },
  ];
  function docTableCommand(id) {
    const command = DOC_TABLE_COMMANDS.find((item) => item.id === id);
    const context = docTableContext();
    if (!command || !context) return false;
    if (command.enabled && !command.enabled(context)) return false;
    const done = command.run(context);
    context.surface.focus();
    return done !== false;
  }
  function docTableMenuItems(context) {
    return DOC_TABLE_COMMANDS.map((command) => ({
      label: command.label,
      title: command.title,
      danger: command.danger,
      //: Rows, columns, alignment, the table itself. Ten rows read as one list
      //: of ten before this, and finding "Align centre" in it meant knowing the
      //: order. `kebabMenu` draws a hairline wherever this name changes
      //: (DOCUMENTS_PLAN section 16).
      group: command.group,
      disabled: command.enabled ? !command.enabled(context) : false,
      run: () => docTableCommand(command.id),
    }));
  }
  function docTableMenu(context) {
    if (typeof kebabMenu !== "function") return document.createElement("span");
    const wrap = kebabMenu(docTableMenuItems(context), "Table row and column actions");
    //: **Pressing it must not move the caret out of the table** (the owner: the
    //: kebab "does nothing and just deselects the row when I try to press that
    //: meatball button"). The menu only exists while the selection is inside the
    //: table: the decoration that draws it is rebuilt from the selection, so the
    //: moment a pointer-down moves the caret out of the header row, the widget
    //: is unmounted, taking the menu that was opening with it. Measured: after a
    //: press, the widget was gone.
    //:
    //: `mousedown` is where the caret moves, so that is where it is refused. The
    //: click still lands and the menu still opens, and every command below then
    //: runs against a selection that is still where the person left it, which is
    //: also what makes "Insert row above" mean a row.
    wrap.addEventListener("mousedown", (event) => event.preventDefault());
    return wrap;
  }
  const DOC_GRIP_DRAG_PX = 4;
  function docTableGripsPlugin(CM) {
    if (docViewState.tableGrips) return docViewState.tableGrips;
    const { ViewPlugin } = CM.view;
    docViewState.tableGrips = ViewPlugin.fromClass(
      class {
        constructor(view) {
          this.view = view;
          this.geo = null;
          this.sig = "";
          this.press = null;
          this.layer = document.createElement("div");
          this.layer.className = "doc-table-grips";
          this.line = document.createElement("div");
          this.line.className = "doc-table-grip-line hidden";
          view.scrollDOM.appendChild(this.layer);
          this.measure = {
            key: this,
            read: (v) => this.read(v),
            write: (geo) => this.write(geo),
          };
          for (const type of ["pointerdown", "pointermove", "pointerup", "pointercancel"]) {
            this.layer.addEventListener(type, (event) => this[type](event));
          }
          view.requestMeasure(this.measure);
        }
        update(update) {
          //: The loop's own flags go through one request per frame, outside the loop.
          if (update.docChanged || update.selectionSet || update.focusChanged) update.view.requestMeasure(this.measure);
          else if (update.viewportChanged || update.geometryChanged || update.heightChanged) {
            docMeasureNextFrame(this, update.view, this.measure);
          }
        }
        destroy() {
          this.measureDead = true;
          this.layer.remove();
        }

        read(view) {
          const doc = view.state.doc;
          const head = view.state.selection.main.head;
          //: Cheap exit for the common case: a caret on a line with no pipe is not
          //: in a table, and reading the document to say so on every keystroke of a
          //: long page would be the cost of a feature most lines never use.
          if (!doc.lineAt(head).text.includes("|") && !doc.lineAt(view.state.selection.main.anchor).text.includes("|")) return null;
          const table = docTableParse.at(doc, head);
          if (!table) return null;
          const scroller = view.scrollDOM;
          const sr = scroller.getBoundingClientRect();
          const rect = (el) => {
            const b = el.getBoundingClientRect();
            return {
              x: Math.round(b.left - sr.left - scroller.clientLeft + scroller.scrollLeft),
              y: Math.round(b.top - sr.top - scroller.clientTop + scroller.scrollTop),
              w: Math.round(b.width),
              h: Math.round(b.height),
            };
          };
          const rows = [];
          let cols = [];
          for (const el of view.contentDOM.querySelectorAll(".cm-line.cm-md-table")) {
            const pos = view.posAtDOM(el);
            const index = table.rows.findIndex((row) => pos >= row.from && pos <= row.to);
            if (index < 0) continue;
            rows.push({ row: index, ...rect(el) });
            if (index === 0) cols = [...el.querySelectorAll(".cm-md-td")].map((cell, col) => ({ col, ...rect(cell) }));
          }
          if (!rows.length || !cols.length) return null;
          rows.sort((a, b) => a.row - b.row);
          const left = Math.min(...rows.map((r) => r.x));
          const right = Math.max(...rows.map((r) => r.x + r.w));
          const last = rows[rows.length - 1];
          return {
            from: table.from,
            delim: table.delim,
            columns: table.columns,
            rows,
            cols,
            box: { left, top: rows[0].y, right, bottom: last.y + last.h },
            limit: scroller.clientWidth + scroller.scrollLeft,
          };
        }

        write(geo) {
          const signature = geo ? JSON.stringify([geo.from, geo.rows, geo.cols, geo.limit]) : "";
          if (this.press && this.press.drag) return;
          if (signature === this.sig) return;
          this.sig = signature;
          this.geo = geo;
          this.layer.replaceChildren();
          if (!geo) return;
          const put = (cls, kind, index, box, label) => {
            const el = document.createElement("div");
            el.className = cls;
            el.dataset.kind = kind;
            el.dataset.index = String(index);
            el.title = label;
            el.setAttribute("aria-hidden", "true");
            el.style.left = `${box.x}px`;
            el.style.top = `${box.y}px`;
            el.style.width = `${box.w}px`;
            el.style.height = `${box.h}px`;
            this.layer.appendChild(el);
            return el;
          };
          //: The hit areas are as high and as wide as the band the table's own
          //: spacing leaves (16px above the header, what the content's left
          //: padding allows beside the rows); the visible bar is drawn inside
          //: them by the stylesheet.
          const band = 16;
          const side = Math.max(8, Math.min(band, geo.box.left));
          const lastCol = geo.cols[geo.cols.length - 1];
          geo.cols.forEach((c) => {
            const shorten = c === lastCol ? band + 2 : 0;
            put("doc-table-grip doc-table-grip-col", "col", c.col, { x: c.x, y: geo.box.top - band, w: Math.max(8, c.w - shorten), h: band },
              `Column ${c.col + 1}: click to select, drag to move, right-click for more`);
          });
          geo.rows.forEach((r) => {
            put("doc-table-grip doc-table-grip-row", "row", r.row, { x: geo.box.left - side, y: r.y, w: side, h: r.h },
              `${r.row === 0 ? "Header row" : `Row ${r.row - geo.delim}`}: click to select, drag to move, right-click for more`);
          });
          const addCol = put("doc-table-add doc-table-add-col", "add-col", 0,
            { x: lastCol.x + lastCol.w - band, y: geo.box.top - band, w: band, h: band }, "Add a column at the end");
          const addRow = put("doc-table-add doc-table-add-row", "add-row", 0,
            { x: geo.box.left, y: geo.box.bottom, w: band, h: band }, "Add a row at the end");
          this.layer.appendChild(this.line);
        }

        pointerdown(event) {
          const grip = event.target instanceof Element ? event.target.closest(".doc-table-grip, .doc-table-add") : null;
          if (!grip || event.button !== 0 || !this.geo) return;
          //: Not a text press: the caret stays in the table, and the editor keeps
          //: its focus, which is what the commands read.
          event.preventDefault();
          this.press = { el: grip, kind: grip.dataset.kind, index: Number(grip.dataset.index), x: event.clientX, y: event.clientY, id: event.pointerId, drag: false, target: null };
          try {
            grip.setPointerCapture(event.pointerId);
          } catch {
            /* a pointer that is already gone: the release will not come, and the press is dropped below */
          }
        }

        pointermove(event) {
          const press = this.press;
          if (!press || event.pointerId !== press.id) return;
          //: The header is the table's shape, not a row that moves.
          const movable = press.kind === "col" || (press.kind === "row" && press.index > this.geo.delim);
          if (!press.drag && movable && Math.hypot(event.clientX - press.x, event.clientY - press.y) >= DOC_GRIP_DRAG_PX) {
            press.drag = true;
            this.layer.classList.add("is-dragging");
            press.el.classList.add("is-source");
          }
          if (!press.drag) return;
          const scroller = this.view.scrollDOM;
          const sr = scroller.getBoundingClientRect();
          const px = event.clientX - sr.left - scroller.clientLeft + scroller.scrollLeft;
          const py = event.clientY - sr.top - scroller.clientTop + scroller.scrollTop;
          const geo = this.geo;
          const line = this.line;
          line.classList.remove("hidden");
          if (press.kind === "col") {
            const slot = geo.cols.filter((c) => c.x + c.w / 2 < px).length;
            press.target = slot > press.index ? slot - 1 : slot;
            const edge = slot < geo.cols.length ? geo.cols[slot].x : geo.cols[geo.cols.length - 1].x + geo.cols[geo.cols.length - 1].w;
            line.className = "doc-table-grip-line doc-table-grip-line-col";
            line.style.left = `${edge}px`;
            line.style.top = `${geo.box.top}px`;
            line.style.height = `${geo.box.bottom - geo.box.top}px`;
            line.style.width = "";
          } else {
            const body = geo.rows.filter((r) => r.row > geo.delim);
            const slot = body.filter((r) => r.y + r.h / 2 < py).length;
            const slotRow = geo.delim + 1 + slot;
            press.target = slotRow > press.index ? slotRow - 1 : slotRow;
            const edge = slot < body.length ? body[slot].y : body[body.length - 1].y + body[body.length - 1].h;
            line.className = "doc-table-grip-line doc-table-grip-line-row";
            line.style.top = `${edge}px`;
            line.style.left = `${geo.box.left}px`;
            line.style.width = `${geo.box.right - geo.box.left}px`;
            line.style.height = "";
          }
        }

        pointerup(event) {
          const press = this.press;
          if (!press || event.pointerId !== press.id) return;
          this.finish();
          if (press.drag) {
            if (press.target != null && press.target !== press.index) this.commitMove(press);
            else this.view.requestMeasure(this.measure);
            return;
          }
          const grip = document.elementFromPoint(event.clientX, event.clientY);
          //: A release off the grip it began on is a cancelled press, as it is on
          //: every button.
          if (!(grip instanceof Element) || grip.closest(".doc-table-grip, .doc-table-add") !== press.el) return;
          this.click(press);
        }

        pointercancel() {
          if (this.press) this.finish();
          this.view.requestMeasure(this.measure);
        }

        finish() {
          const press = this.press;
          this.press = null;
          this.layer.classList.remove("is-dragging");
          this.line.classList.add("hidden");
          if (press && press.el) {
            press.el.classList.remove("is-source");
            try {
              press.el.releasePointerCapture(press.id);
            } catch {
              /* released already */
            }
          }
        }

        //: The live table the grips were drawn for, or null if the document moved
        //: under them.
        context() {
          const surface = asSurface(this.view.contentDOM) || docSurface();
          const context = surface && docTableContext(surface);
          return context && this.geo && context.table.from === this.geo.from ? context : null;
        }

        click(press) {
          const context = this.context();
          if (!context) return;
          const table = context.table;
          if (press.kind === "col" || press.kind === "row") {
            context.cell = press.kind === "row" ? { row: press.index, col: context.cell.col } : { row: context.cell.row, col: press.index };
            docTableSelect(context, press.kind === "col" ? "column" : "row");
          } else if (press.kind === "add-col") {
            context.cell = { row: context.cell.row === table.delim ? 0 : context.cell.row, col: table.columns - 1 };
            docTableCommandRun("col-right", context);
          } else if (press.kind === "add-row") {
            context.cell = { row: table.rows.length - 1, col: context.cell.col };
            docTableCommandRun("row-below", context);
          }
          this.view.focus();
        }

        commitMove(press) {
          const context = this.context();
          if (!context) return;
          const delta = press.target - press.index;
          const edits = press.kind === "col"
            ? docTableMoveColumnEdits(context.table, press.index, delta)
            : docTableMoveRowEdits(context.table, press.index, delta);
          docTableDispatch(context, edits);
          //: The moved row or column stays selected, so the person sees where it
          //: went and the next press acts on it.
          const table = docTableParse(context.surface.text, context.table.from);
          if (table) {
            const cell = press.kind === "col" ? { row: 0, col: press.target } : { row: press.target, col: 0 };
            docTableSelect({ surface: context.surface, table, cell }, press.kind === "col" ? "column" : "row");
          }
          this.view.focus();
        }
      }
    );
    return docViewState.tableGrips;
  }
  function docTableCommandRun(id, context) {
    const command = DOC_TABLE_COMMANDS.find((item) => item.id === id);
    if (!command || (command.enabled && !command.enabled(context))) return false;
    return command.run(context) !== false;
  }

  //: The file's surface: what other files call (L335).
  Object.assign(window, { docTableMenuItems, docTableMenu, DOC_GRIP_DRAG_PX, docTableGripsPlugin });
})();
