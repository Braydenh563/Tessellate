// documents-edit-keys.js: indent, comment toggle and table keys in the plain editor.
// Moved out of documents.js whole (L335) and wrapped: only what other files call goes on `window`; nothing here runs at load.
(() => {
  function docSelectedLines(box) {
    const value = box.value;
    const start = value.lastIndexOf("\n", box.selectionStart - 1) + 1;
    let end = value.indexOf("\n", box.selectionEnd);
    if (end === -1) end = value.length;
    // A selection ending exactly at a line start has not touched that line, 
    // without this, selecting one whole line by dragging comments out two.
    if (box.selectionEnd > box.selectionStart && box.selectionEnd === start) {
      end = box.selectionEnd;
    }
    return { start, end, text: value.slice(start, end) };
  }
  function docReplaceRange(box, start, end, text) {
    //: CodeMirror has its own history and its own transaction pipeline, so the
    //: `execCommand` dance below is not only unnecessary there, it is wrong:
    //: `insertText` on a contenteditable goes through the browser rather than
    //: through the state, and the two would disagree about the document.
    if (box.kind === "codemirror") {
      box.replaceRange(start, end, text);
      return;
    }
    box.focus();
    box.setSelectionRange(start, end);
    if (!document.execCommand || !document.execCommand("insertText", false, text)) {
      // execCommand is deprecated and may be gone. Falling back to a direct
      // write loses native undo for that one edit, which beats the edit not
      // happening: and `markDocDirty` still runs, so nothing is lost.
      const value = box.value;
      box.value = value.slice(0, start) + text + value.slice(end);
    }
  }
  function docTakeTabEscape() {
    const armed = docTabEscapes;
    docTabEscapes = false;
    return armed;
  }
  const DOC_LIST_LINE = /^([ \t]*)([-*+]|\d+[.)])(\s)/;
  function docOrderedNumberAt(value, start, indent) {
    const above = value.slice(0, Math.max(0, start - 1)).split("\n");
    for (let i = above.length - 1; i >= 0; i--) {
      const line = above[i];
      if (!line.trim()) continue;
      const m = /^([ \t]*)(?:(\d+)[.)]|[-*+])\s/.exec(line);
      if (!m) {
        if (/^\s/.test(line)) continue;
        return 1;
      }
      if (m[1].length > indent) continue;
      return m[1].length === indent && m[2] ? Number(m[2]) + 1 : 1;
    }
    return 1;
  }
  function docCanOutdent(box) {
    if (!box) return false;
    if (box.selectionEnd > box.selectionStart) return true;
    return /^[ \t]/.test(docSelectedLines(box).text);
  }
  function indentDocSelection(box, outdent) {
    //: One undo step per Tab, not one per burst, see `docUndoBreak`.
    docUndoBreak();
    const type = docFileType();
    const unit = type.indent || "  ";
    const { start, end, text } = docSelectedLines(box);
    const multiline = text.includes("\n") || box.selectionEnd > box.selectionStart;
    //: Read before anything is replaced: an edit moves the surface's own
    //: selection, so a caret read afterwards is the engine's guess rather than
    //: where the writer was.
    const caretWas = box.selectionStart;

    // A list item is indented as a whole, from wherever the caret sits in it,
    // and Shift+Tab pulls it back the same way. `DOC_LIST_LINE` carries the
    // reason. The caret is kept where it was in the text rather than being
    // dropped at the line start or spread over the line: an indent that moves
    // the caret is an indent you have to recover from.
    if (!multiline && DOC_LIST_LINE.test(text)) {
      const caret = caretWas;
      const leading = text.match(/^[ \t]*/)[0];
      let next = leading;
      if (!outdent) {
        next = leading + unit;
      } else if (leading.startsWith(unit)) {
        next = leading.slice(unit.length);
      } else {
        next = leading.slice(Math.min(leading.length, unit.length));
      }
      if (next === leading) return; // nothing to remove: the caller lets Tab go
      //: A numbered item that changes level takes its place in the new list:
      //: indented under "1. a" it is the first of a nested list ("1."), and
      //: brought back out it is the parent's next number. Left alone it kept
      //: "2." in a list of one, which renders as "2." and counts from there.
      const digits = /^\d+/.exec(text.slice(leading.length))?.[0] || "";
      const number = digits ? String(docOrderedNumberAt(box.value, start, next.length)) : "";
      docReplaceRange(box, start, start + leading.length + digits.length, next + number);
      const moved = next.length - leading.length + number.length - digits.length;
      const at = Math.max(start + next.length, caret + moved);
      box.setSelectionRange(at, at);
      markDocDirty();
      renderDocGutter();
      return;
    }

    // A plain Tab with no selection inserts one indent at the caret, which is
    // what Tab does in every editor. Only a selection (or Shift+Tab) means
    // "re-indent these lines".
    if (!multiline && !outdent) {
      const at = box.selectionStart;
      docReplaceRange(box, at, box.selectionEnd, unit);
      //: **After the indent, said rather than assumed.** The textarea's
      //: `insertText` leaves the caret after what it inserted; the engine's
      //: `replaceRange` maps a caret sitting exactly at the insertion point to
      //: *before* it. Measured 2026-09-23 in both a code and a markdown
      //: document: Tab then "a" at the start of `int x;` gave `a    int x;`,
      //: so every Tab in the editor since the engine landed put the next
      //: keystroke on the wrong side of the indent it had just made.
      box.setSelectionRange(at + unit.length, at + unit.length);
      markDocDirty();
      renderDocGutter();
      return;
    }

    const lines = text.split("\n");
    const changed = lines.map((line) => {
      if (!outdent) return line ? unit + line : line;
      // Dedent removes one indent unit, or, for a line indented with the
      // wrong-width whitespace, which happens constantly in a pasted file, 
      // up to that many leading spaces. Removing nothing when the line is
      // flush left is correct, not a failure.
      if (line.startsWith(unit)) return line.slice(unit.length);
      const leading = line.match(/^[ \t]+/);
      if (!leading) return line;
      return line.slice(Math.min(leading[0].length, unit.length));
    });
    const joined = changed.join("\n");
    docReplaceRange(box, start, end, joined);
    if (box.selectionEnd > box.selectionStart || multiline) {
      box.setSelectionRange(start, start + joined.length);
    } else {
      //: A Shift+Tab with no selection is a caret gesture, so it leaves a
      //: caret. Selecting the whole line here (what this did until 2026-09-12)
      //: meant the next character typed replaced the line the writer had just
      //: dedented.
      const moved = joined.length - text.length;
      const at = Math.min(Math.max(start, caretWas + moved), start + joined.length);
      box.setSelectionRange(at, at);
    }
    markDocDirty();
    renderDocGutter();
  }
  function toggleDocComment(box) {
    if (docCodeCommentAtCaret(box)) return;
    docUndoBreak();
    const type = docFileType();
    const { start, end, text } = docSelectedLines(box);
    const lines = text.split("\n");

    if (type.line_comment) {
      const marker = type.line_comment;
      const real = lines.filter((line) => line.trim());
      // Uncomment only when *every* non-blank line is already commented. The
      // other way round (any line commented -> uncomment all) silently strips
      // a real comment that happened to be inside the selection.
      const allCommented =
        real.length > 0 && real.every((line) => line.trimStart().startsWith(marker));
      const changed = lines.map((line) => {
        if (!line.trim()) return line;
        if (allCommented) {
          const at = line.indexOf(marker);
          // Drop one following space if this put one there, so a round trip
          // of comment-then-uncomment gives back exactly the original line.
          const after = line.slice(at + marker.length);
          return line.slice(0, at) + (after.startsWith(" ") ? after.slice(1) : after);
        }
        // Inserted after the existing indentation, not at column zero: a
        // comment marker flush left inside an indented block is legal and ugly,
        // and is not what any editor does.
        const indent = line.match(/^[ \t]*/)[0];
        return `${indent}${marker} ${line.slice(indent.length)}`;
      });
      docReplaceRange(box, start, end, changed.join("\n"));
      box.setSelectionRange(start, start + changed.join("\n").length);
    } else if (type.block_comment) {
      // No line-comment form at all (HTML, XML, CSS). Toggling a line means
      // wrapping it: a prefix would produce a file that no longer parses.
      const [open, close] = type.block_comment;
      const trimmed = text.trim();
      const wrapped = trimmed.startsWith(open.trim()) && trimmed.endsWith(close.trim());
      const changed = wrapped
        ? trimmed.slice(open.trim().length, trimmed.length - close.trim().length).trim()
        : `${open}${text}${close}`;
      docReplaceRange(box, start, end, changed);
      box.setSelectionRange(start, start + changed.length);
    } else {
      // Plain text genuinely has no comment syntax. Doing nothing quietly is
      // right: there is no sensible thing to insert.
      return;
    }
    markDocDirty();
    renderDocGutter();
  }
  function docCodeCommentRun(CM, target, block) {
    return block ? CM.commands.toggleBlockComment(target) : CM.commands.toggleComment(target);
  }
  function docCodeCommentAtCaret(box, block = false) {
    const CM = window.CM6;
    const type = docFileType();
    if (!CM || !docCmView || box?.view !== docCmView || type.previewable || docView === "plain") return false;
    const view = docCmView;
    const target = { state: view.state, dispatch: (tr) => view.dispatch(tr) };
    if (!docCodeCommentRun(CM, target, block)) return false;
    markDocDirty();
    return true;
  }
  function docTableContext(box = null) {
    const surface = box || docSurface();
    if (!surface) return null;
    const text = surface.text;
    const at = surface.selectionStart;
    const table = docTableParse(text, at);
    if (!table) return null;
    return { surface, text, table, cell: docTableCellAt(table, at) || { row: 0, col: 0 } };
  }
  function docTableDispatch(context, edits) {
    if (!edits || !edits.length) return false;
    const surface = context.surface;
    docUndoBreak();
    if (docCmView && surface.kind === "codemirror") {
      docCmView.dispatch({
        changes: edits.map((edit) => ({ from: edit.from, to: edit.to, insert: edit.insert })),
        scrollIntoView: true,
        annotations: docCmIsolate(),
      });
      return true;
    }
    surface.value = docTableApplyEdits(surface.text, edits);
    finishMarkdownEdit(surface, "doc-content");
    return true;
  }
  function docTableGo(context, edits, row, col) {
    docTableDispatch(context, edits);
    const surface = context.surface;
    let table = docTableParse(surface.text, context.table.from);
    if (!table || !table.rows[row]) return true;
    if (col >= table.rows[row].cells.length) {
      //: The cell GFM pads into existence but the text does not have yet. It has
      //: to be real before the caret can sit in it, or the next keystroke lands
      //: at the end of the previous cell.
      docTableDispatch({ surface, text: surface.text }, docTableFillRowEdits(table, row, col));
      table = docTableParse(surface.text, context.table.from);
    }
    const span = table && docTableCellSpan(table, row, col);
    if (!span) return true;
    const raw = table.rows[row].cells[col];
    //: **An empty cell takes the caret after its first space, not its last.**
    //: A new row is written `|  |  |`, two spaces a cell, and the caret was put
    //: after both: measured, Tab out of the last cell and "Three" typed gave
    //: `|  Three|`, a cell that no longer matched a single other one in the
    //: table. One space in is where a person would have typed it by hand.
    if (!raw.trim()) {
      const at = span.from + Math.min(1, raw.length);
      surface.setSelectionRange(at, at);
      return true;
    }
    const lead = (/^[ \t]*/.exec(raw) || [""])[0].length;
    const tail = (/[ \t]*$/.exec(raw) || [""])[0].length;
    surface.setSelectionRange(span.from + lead, Math.max(span.from + lead, span.to - tail));
    return true;
  }
  function docTableTabStep(backwards, from = null) {
    const context = from || docTableContext();
    if (!context) return false;
    const step = docTableStepCell(context.table, context.cell.row, context.cell.col, backwards ? -1 : 1);
    if (step) return docTableGo(context, [], step.row, step.col);
    if (backwards) return false;
    const rows = context.table.rows.length;
    return docTableGo(context, docTableAddRowEdits(context.table, rows - 1), rows, 0);
  }
  function docTableCaretTo(context, row, col) {
    const surface = context.surface;
    let table = context.table;
    if (!table.rows[row]) return false;
    if (col >= table.rows[row].cells.length) {
      docTableDispatch({ surface, text: surface.text }, docTableFillRowEdits(table, row, col));
      table = docTableParse(surface.text, table.from);
      if (!table) return true;
    }
    const span = docTableCellSpan(table, row, Math.min(col, table.rows[row].cells.length - 1));
    if (!span) return true;
    const raw = surface.text.slice(span.from, span.to);
    const tail = (/[ \t]*$/.exec(raw) || [""])[0].length;
    const at = raw.trim() ? span.to - tail : span.from + Math.min(1, raw.length);
    surface.setSelectionRange(at, at);
    return true;
  }
  function docTableExit(view, table, dropLast) {
    const out = docTableExitEdit(table, docStr(view.state.doc), dropLast);
    view.dispatch({ changes: out.changes, selection: { anchor: out.anchor }, scrollIntoView: true, userEvent: "input" });
    return true;
  }
  function docTableCtrlEnter(view) {
    const context = docTableContext();
    if (!context || context.surface.kind !== "codemirror" || context.surface.view !== view) return false;
    return docTableExit(view, context.table, false);
  }
  function docTableKeyMove(view, key) {
    if (docView !== "live") return false;
    const sel = view.state.selection.main;
    if (!sel.empty || view.state.selection.ranges.length > 1) return false;
    const context = docTableContext();
    if (!context || context.surface.kind !== "codemirror" || context.surface.view !== view) return false;
    const { table, cell } = context;
    if (key === "Enter") {
      const last = table.rows[table.rows.length - 1];
      if (cell.row === table.rows.length - 1 && table.rows.length > 2 && !last.cells.some((c) => c.trim())) return docTableExit(view, table, true);
      //: A row typed by hand ends with its closing pipe: Enter there is the
      //: plain newline, so the next line is typed rather than found inside a
      //: cell (typed line by line, `| --- |` then Enter used to add an empty
      //: row and park the next line inside it).
      const line = view.state.doc.lineAt(sel.head);
      if (sel.head === line.to && line.text.trimEnd().endsWith("|")) return false;
      const next = docTableStepRow(table, cell.row, 1);
      if (next !== null) return docTableCaretTo(context, next, cell.col);
      const rows = table.rows.length;
      return docTableGo(context, docTableAddRowEdits(table, rows - 1), rows, cell.col);
    }
    const down = key === "ArrowDown";
    const moved = view.moveVertically(sel, down);
    const landed = docTableCellAt(table, moved.head);
    if (moved.head !== sel.head && landed && landed.row === cell.row && landed.col === cell.col) return false;
    const next = docTableStepRow(table, cell.row, down ? 1 : -1);
    if (next !== null) return docTableCaretTo(context, next, cell.col);
    if (down) return docTableExit(view, table, false);
    const doc = view.state.doc;
    if (table.from > 0) {
      view.dispatch({ selection: { anchor: table.from - 1 }, scrollIntoView: true });
    } else {
      view.dispatch({
        changes: { from: 0, insert: "\n\n" },
        selection: { anchor: 0 },
        scrollIntoView: true,
        userEvent: "input",
      });
    }
    return true;
  }
  function docTablePasteEvent(event, view) {
    if (view.dom.classList.contains("doc-content-code")) return false;
    const data = event.clipboardData;
    if (!data) return false;
    const grid = docTableGridFromText(data.getData("text/plain"));
    if (!grid) return false;
    const context = docTableContext();
    if (context && context.surface.kind === "codemirror" && context.surface.view === view) {
      const result = docTablePasteEdits(context.text, context.table, context.cell.row, context.cell.col, grid);
      if (!result) return false;
      event.preventDefault();
      docUndoBreak();
      view.dispatch({ changes: result.edit, userEvent: "input.paste", scrollIntoView: true });
      const table = docTableParse(docStr(view.state.doc), context.table.from);
      if (table) docTableCaretTo({ surface: context.surface, table }, result.row, result.col);
      return true;
    }
    const html = data.getData("text/html") || "";
    const square = grid.length >= 2 && grid[0].length >= 2 && grid.every((row) => row.length === grid[0].length);
    if (!/<table[\s>]/i.test(html) || !square) return false;
    event.preventDefault();
    const { state } = view;
    const sel = state.selection.main;
    const startLine = state.doc.lineAt(sel.from);
    const endLine = state.doc.lineAt(sel.to);
    //: A table is a block: it needs a blank line between it and the text on
    //: either side, or the line after it would be read as one more row.
    const textBefore = state.doc.sliceString(startLine.from, sel.from).trim();
    const lineAbove = startLine.number > 1 ? state.doc.line(startLine.number - 1).text.trim() : "";
    const textAfter = state.doc.sliceString(sel.to, endLine.to).trim();
    const lineBelow = endLine.number < state.doc.lines ? state.doc.line(endLine.number + 1).text.trim() : "";
    const before = textBefore ? "\n\n" : lineAbove ? "\n" : "";
    const after = textAfter ? "\n\n" : lineBelow ? "\n" : "";
    const table = docTableFromGrid(grid);
    docUndoBreak();
    view.dispatch({
      changes: { from: sel.from, to: sel.to, insert: before + table + after },
      selection: { anchor: sel.from + before.length + table.length },
      userEvent: "input.paste",
      scrollIntoView: true,
    });
    docPasteOfferTable(view, sel.from, before + table + after, data.getData("text/plain"));
    return true;
  }

  //: The file's surface: what other files call (L335).
  Object.assign(window, { docReplaceRange, docTakeTabEscape, docCanOutdent, indentDocSelection, toggleDocComment, docCodeCommentAtCaret, docTableContext, docTableDispatch, docTableGo, docTableTabStep, docTableCtrlEnter, docTableKeyMove, docTablePasteEvent });
})();
