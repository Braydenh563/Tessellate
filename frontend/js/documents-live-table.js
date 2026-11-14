// documents-live-table.js: the Live view's decorations switch and extension set (with the block drag handle), and the table's
// select, remove and filter row. Moved out of documents.js and wrapped (L-documents-116): only what other files call goes on `window`.
// Loaded after documents.js: at load it only declares and writes `docViewState.tableFilter`, so it needs that object first.
(() => {
  //: The whole table, for the one command that is not an edit inside it. The
  //: newline after it goes too, or deleting a table leaves the blank line it was
  //: separated from the next paragraph by.
  function docTableRemoveEdits(context) {
    const { table, text } = context;
    let to = table.to;
    if (text[to] === "\n") to += 1;
    return [{ from: table.from, to, insert: "" }];
  }

  //: Select a row, a column (one range per cell, so Delete clears them and
  //: copy reads them) or the table. A textarea has one range only: the first
  //: to the last.
  function docTableSelect(context, kind) {
    const index = kind === "row" ? context.cell.row : kind === "column" ? context.cell.col : 0;
    const ranges = docTableSelectRanges(context.table, kind, index);
    if (!ranges.length) return false;
    const view = context.surface.view;
    const CM = window.CM6;
    if (view && CM) {
      const { EditorSelection } = CM.state;
      view.dispatch({
        selection: EditorSelection.create(ranges.map((range) => EditorSelection.range(range.from, range.to))),
        scrollIntoView: true,
      });
    } else {
      context.surface.setSelectionRange(ranges[0].from, ranges[ranges.length - 1].to);
    }
    return true;
  }

  //: **The filter row and the formula letters** (DOCUMENTS_PLAN gap row 12). A
  //: filter is a view of the table, never an edit: it lives in `docViewState`
  //: under the header's text (a table has no id in markdown, and the header is
  //: what a person calls it), hides body rows in Live only, and is gone with the
  //: page. `docViewState.tableFilter.set` repaints by re-sending the selection, which the
  //: table decoration always rebuilds on.
  docViewState.tableFilter = {
    key: (table) => table.rows[0].cells.map((cell) => cell.trim()).join("|"),
    of(table) {
      const filter = docViewState.tableFilters && docViewState.tableFilters[this.key(table)];
      return filter && filter.needle ? filter : null;
    },
    set(view, table, filter) {
      docViewState.tableFilters = docViewState.tableFilters || {};
      const key = this.key(table);
      if (filter && filter.needle) docViewState.tableFilters[key] = filter;
      else delete docViewState.tableFilters[key];
      if (view) view.dispatch({ selection: view.state.selection });
    },
    letters(col) {
      let letters = "";
      for (let n = col + 1; n > 0; n = Math.floor((n - 1) / 26)) letters = String.fromCharCode(65 + ((n - 1) % 26)) + letters;
      return letters;
    },
    async ask(context) {
      const column = (context.table.rows[0].cells[context.cell.col] || "").trim() || `column ${this.letters(context.cell.col)}`;
      const was = this.of(context.table);
      const needle = await promptDialog(`Show rows where ${column} contains`, was ? was.needle : "", { confirmLabel: "Filter" });
      if (needle !== null && needle !== undefined) {
        this.set(context.surface.view, context.table, { col: context.cell.col, needle: needle.trim() });
      }
      context.surface.focus();
    },
  };

  //: The commands, as data, because three things read them: the cell menu, the
  //: "/" menu's table entry and the tests. `run` takes the live context rather
  //: than closing over one, so a menu built for the cell you opened it on still
  //: acts on the cell you are in when you choose an item.

  //: Named so the "/" menu, a shortcut or a test can run one without going
  //: through the menu's DOM.

  //: The cell menu, built from the app's own ⋯ recipe (`kebabMenu`) rather than
  //: from scratch: DESIGN.md's index says a menu is `kebabMenu`, and a
  //: hand-built one here would be the eleventh thing in this app that opens a
  //: list of actions and the first that does it differently.


  //: **Grips on a Live table's edges** (INBOX 904 B23: "lines on the edges and
  //: rows and columns on the outside etc to select whole rows or columns, or to
  //: add new rows or columns or even dragging icons to drag and rearrange
  //: columns and rows"). While the caret is in a table: a bar above each column
  //: and one beside each row (a click selects it, a drag moves it, a right-click
  //: or a hold opens the table's menu there), and a plus at the end of the
  //: header (a column) and under the last row (a row). Every drag has the menu's
  //: Move row and Move column as its keyboard and touch alternative (WCAG 2.5.7).
  //:
  //: A layer inside the editor's scroller, so it scrolls with the text; the
  //: geometry is read from the rendered cells (`requestMeasure`), never guessed
  //: from the grid's template. Rebuilt only when that geometry changes, and never
  //: mid-press, because a press that loses its element loses its release.


  //: One command, by id, against a context the caller already holds. The named
  //: `docTableCommand` reads the caret itself; a grip has just moved it.
  //: The compartment decision 3 names: Live is this editor with the markdown
  //: decorations on, Source is the same editor with them off. Nothing else
  //: differs between the two views, which is the whole point.
  //: **A reconfigure that changes nothing is skipped** (DOCUMENTS 25 row 7).
  //: Each one is a view update that reads the DOM selection and lays the page
  //: out: measured on a 241-line file, the open spent 103ms here and 75ms in the
  //: gutter's twin below re-saying what `docCmExtensions` had just built. The
  //: live set is cached instances (`docLivePlugin`, the two fields), so on or
  //: off is the whole of its state, as the line numbers' preference is the
  //: gutter's.
  function docCmPartIs(part, on) {
    const current = part.get(docCmView.state);
    return Boolean(current && current.length) === Boolean(on);
  }

  function docSetLiveDecorations(on) {
    const CM = window.CM6;
    if (!docCmView || !CM || !docCmParts.live) return;
    if (docCmPartIs(docCmParts.live, on)) return;
    docCmView.dispatch({
      effects: docCmParts.live.reconfigure(on ? docLiveExtensions(CM) : []),
    });
  }

  //: **A span's marks show while a selection is in it or touching it**
  //: (INBOX 1473 b, the owner: "like obsidian where it does it per phrase,
  //: word, or whatever text string is formatted when clicked inside or next
  //: to"). Every range counts, not only the main one, so each cursor of a
  //: multi-cursor edit and every span a selection crosses reveal. Ends are
  //: inclusive: a caret just after the closing `**` is "next to" the span.
  function docLiveSpanTouched(ranges, from, to) {
    for (const range of ranges) {
      if (range.from <= to && range.to >= from) return true;
    }
    return false;
  }

  //: Whether a new selection reveals exactly what the last build revealed.
  //: `probes` is the flat `[from, to, revealed, ...]` list a build records for
  //: every reveal it decided; when none flips, a caret move changes no
  //: decoration and the plugin keeps the set it has.
  function docLiveRevealSame(probes, ranges) {
    for (let i = 0; i < probes.length; i += 3) {
      const v = probes[i + 2];
      if ((v & 2 ? docLiveSpanTouched.anchorIn : docLiveSpanTouched)(ranges, probes[i], probes[i + 1]) !== Boolean(v & 1)) return false;
    }
    return true;
  }
  //: A rendered widget turns to source only while a selection starts in it (INBOX 1547): a caret
  //: there, or a drag begun there; a selection that crosses it leaves it drawn, height and all.
  //: A property, not a name: the shared scope is at its cap (test_global_scope_ratchet).
  //: **A caret shows it only from strictly inside** (audit 1102 DX5): Up or Down lands a caret on a
  //: widget's edge (it has no inside to land in), and the edge revealing it moved the page 235px at
  //: `[TOC]`; Left or Right from the edge steps in. A drag begun at the edge still shows it.
  docLiveSpanTouched.anchorIn = (ranges, from, to) => ranges.some((range) => range.anchor >= from && range.anchor <= to && (!range.empty || (range.anchor > from && range.anchor < to)));


  //: Live is three extensions rather than one now, and all three go in the same
  //: compartment, so a view switch turns them on and off together: the block
  //: widget and the arrow keys that step into it belong to Live exactly as the
  //: markdown decorations do.
  function docLiveExtensions(CM) {
    return [docLivePlugin(CM), docTableGripsPlugin(CM), docColumnsField(CM), docColumnsArrowKeymap(CM), docMermaidField(CM), docMathRender.graphField(CM), docMathRender.baseField(CM), docMathRender.queryField(CM), docMathRender.sectionsField(CM), docLiveExtensions.dragHandle(CM)];
  }

  //: **A drag handle for a Live block** (audit 1102 DX29; Notion's grip). Beside
  //: the block under the pointer a grip appears in the page margin; dragging it
  //: and letting go moves the whole block (a paragraph, a list item with what is
  //: nested under it, a fence, a heading's section) to the drop point.
  //:
  //: It is the keyboard move repeated, not a second model: `docBlockMoveEdit`
  //: (Alt+Up and Alt+Down) is applied to a copy of the text once per neighbour the
  //: drop is past, and the difference between the copy and the document is
  //: dispatched as ONE transaction, so one Undo puts the block back. The keyboard
  //: path already meets WCAG 2.5.7, so the grip is `aria-hidden` and its title
  //: names the keys. Pointer only: a phone has no hover (the stylesheet hides it
  //: too) and a code file keeps the editor's own line move.
  docLiveExtensions.dragHandle = (CM) => {
    if (docViewState.blockHandle) return docViewState.blockHandle;
    const { ViewPlugin } = CM.view;
    docViewState.blockHandle = ViewPlugin.fromClass(
      class {
        constructor(view) {
          this.view = view;
          this.press = null;
          this.plan = null;
          this.unit = null;
          this.seen = -1;
          this.el = document.createElement("div");
          this.el.className = "doc-block-handle hidden";
          this.el.title = "Drag to move this block. Alt+Up and Alt+Down move it from the keyboard";
          this.el.setAttribute("aria-hidden", "true");
          const icon = document.createElement("i");
          icon.className = "ph ph-dots-six-vertical";
          this.el.appendChild(icon);
          this.mark = document.createElement("div");
          this.mark.className = "doc-block-drop hidden";
          view.scrollDOM.append(this.el, this.mark);
          this.on = {
            hover: (event) => this.hover(event),
            leave: () => this.press || this.hide(),
            down: (event) => this.down(event),
            move: (event) => this.drag(event),
            up: (event) => this.drop(event),
            cancel: () => this.end(),
          };
          view.contentDOM.addEventListener("pointermove", this.on.hover);
          view.scrollDOM.addEventListener("pointerleave", this.on.leave);
          this.el.addEventListener("pointerdown", this.on.down);
          this.el.addEventListener("pointermove", this.on.move);
          this.el.addEventListener("pointerup", this.on.up);
          this.el.addEventListener("pointercancel", this.on.cancel);
        }
        update(update) {
          if (!update.docChanged) return;
          this.end();
          this.hide();
        }
        destroy() {
          this.view.contentDOM.removeEventListener("pointermove", this.on.hover);
          this.view.scrollDOM.removeEventListener("pointerleave", this.on.leave);
          this.el.remove();
          this.mark.remove();
        }

        hide() {
          this.unit = null;
          this.seen = -1;
          this.el.classList.add("hidden");
        }

        //: The block under the pointer. Recomputed only when the pointer changes
        //: line (the block model reads the whole text), and a blank line between
        //: two blocks leaves the grip where it was so the pointer can reach it.
        hover(event) {
          if (this.press || event.pointerType !== "mouse" || window.matchMedia("(hover: none)").matches) return;
          if (!docFileType().previewable) return this.hide();
          const view = this.view;
          const pos = view.posAtCoords({ x: event.clientX, y: event.clientY }, false);
          if (pos == null) return;
          const doc = view.state.doc;
          const line = doc.lineAt(pos);
          if (line.from === this.seen) return;
          if (!line.text.trim()) return;
          this.seen = line.from;
          const text = docStr(doc);
          let edit = docBlockMoveEdit(text, line.from, 1);
          if (!edit || edit.noop) edit = docBlockMoveEdit(text, line.from, -1);
          if (!edit || edit.noop || !edit.unit) return this.hide();
          const box = view.coordsAtPos(edit.unit.from);
          if (!box) return this.hide();
          const scroller = view.scrollDOM;
          const sr = scroller.getBoundingClientRect();
          this.unit = edit.unit;
          this.el.classList.remove("hidden");
          this.el.style.top = `${Math.round(box.top - sr.top - scroller.clientTop + scroller.scrollTop)}px`;
          this.el.style.height = `${Math.round(box.bottom - box.top)}px`;
          this.el.style.left = `${Math.max(0, Math.round(box.left - sr.left - scroller.clientLeft + scroller.scrollLeft))}px`;
        }

        down(event) {
          if (event.button !== 0 || !this.unit) return;
          //: Not a text press: the editor keeps its focus and its caret.
          event.preventDefault();
          this.press = { id: event.pointerId, x: event.clientX, y: event.clientY, drag: false, unit: this.unit, text: docStr(this.view.state.doc) };
          this.plan = null;
          try {
            this.el.setPointerCapture(event.pointerId);
          } catch {
            /* a pointer that is already gone: the release will not come, and the press is dropped */
          }
        }

        //: Where a drop at this height lands: the nearest line edge, then as many
        //: neighbours as that edge is past, each one the keyboard move.
        planFor(drop) {
          const press = this.press;
          let text = press.text;
          let at = press.unit.from;
          let edge = null;
          let steps = 0;
          const delta = drop > at ? 1 : -1;
          while (steps < 500) {
            const edit = docBlockMoveEdit(text, at, delta);
            if (!edit || edit.noop) break;
            if (delta > 0 ? drop < edit.hopTo : drop > edit.hopFrom) break;
            text = text.slice(0, edit.from) + edit.insert + text.slice(edit.to);
            if (delta > 0 && drop >= edit.to) drop += edit.insert.length - (edit.to - edit.from);
            at = edit.caret;
            edge = delta > 0 ? edit.hopTo : edit.hopFrom;
            steps += 1;
          }
          return { text, at, edge, steps };
        }

        drag(event) {
          const press = this.press;
          if (!press || event.pointerId !== press.id) return;
          if (!press.drag && Math.hypot(event.clientX - press.x, event.clientY - press.y) >= DOC_GRIP_DRAG_PX) {
            press.drag = true;
            this.el.classList.add("is-dragging");
          }
          if (!press.drag) return;
          const view = this.view;
          const scroller = view.scrollDOM;
          const sr = scroller.getBoundingClientRect();
          if (event.clientY < sr.top + 24) scroller.scrollTop -= 12;
          else if (event.clientY > sr.bottom - 24) scroller.scrollTop += 12;
          const doc = view.state.doc;
          const block = view.lineBlockAtHeight(event.clientY - view.documentTop);
          const line = doc.lineAt(block.from);
          const upper = event.clientY - view.documentTop < (block.top + block.bottom) / 2;
          const drop = upper ? line.from : Math.min(line.to + 1, doc.length);
          if (!this.plan || this.plan.drop !== drop) this.plan = { ...this.planFor(drop), drop };
          const edge = this.plan.steps ? view.lineBlockAt(this.plan.edge) : null;
          this.mark.classList.toggle("hidden", !edge);
          if (!edge) return;
          const cr = view.contentDOM.getBoundingClientRect();
          const y = this.plan.edge >= doc.length ? edge.bottom : edge.top;
          this.mark.style.top = `${Math.round(view.documentTop + y - sr.top - scroller.clientTop + scroller.scrollTop)}px`;
          this.mark.style.left = `${Math.round(cr.left - sr.left - scroller.clientLeft + scroller.scrollLeft)}px`;
          this.mark.style.width = `${Math.round(cr.width)}px`;
        }

        drop(event) {
          const press = this.press;
          const plan = this.plan;
          if (!press || event.pointerId !== press.id) return;
          const view = this.view;
          this.end();
          if (!press.drag || !plan || !plan.steps || view.state.doc.length !== press.text.length) return;
          //: The move is a swap of text the document already has, so the change is
          //: the stretch that differs: one edit, one transaction, one Undo.
          const old = press.text;
          const next = plan.text;
          const room = Math.min(old.length, next.length);
          let from = 0;
          while (from < room && old.charCodeAt(from) === next.charCodeAt(from)) from += 1;
          let tail = 0;
          while (tail < room - from && old.charCodeAt(old.length - 1 - tail) === next.charCodeAt(next.length - 1 - tail)) tail += 1;
          view.dispatch({
            changes: { from, to: old.length - tail, insert: next.slice(from, next.length - tail) },
            selection: { anchor: plan.at },
            userEvent: "move.line",
          });
        }

        end() {
          this.press = null;
          this.plan = null;
          this.el.classList.remove("is-dragging");
          this.mark.classList.add("hidden");
        }
      },
    );
    return docViewState.blockHandle;
  };

  //: The file's surface: what other files call.
  Object.assign(window, { docTableRemoveEdits, docTableSelect, docCmPartIs, docSetLiveDecorations, docLiveSpanTouched, docLiveRevealSame, docLiveExtensions });
})();
