// documents-columns.js: the columns block (split out of documents.js, audit
// 1031 DC13 remainder).
//
// What is here: the `:::columns` parser (`docColumnsBlocks`, `docColumnsAt`,
// bracketed by `DOC-BLOCKS-BEGIN`/`END` for `tests/test_doc_columns.py`, which
// runs it in node) and the Live editor's half: the StateField that draws a
// block as columns while the caret is outside it (`docColumnsField`) and the
// arrow keys that step into it (`docColumnsArrowKeymap`). What stayed in
// documents.js: `docLiveExtensions`, which names both from inside a function,
// and the Read view's columns, which call `docColumnsBlocks` the same way.
//
// **Loaded in the Library bundle, before documents.js**, the way
// documents-props.js is: this file's own top level declares regular
// expressions and functions and reads nothing from documents.js. One closure;
// what other files call is the `Object.assign` at the foot.
(() => {
  // =============================================================================
  // Columns and image options (DOCUMENTS_PLAN Phase 3 item 5)
  // =============================================================================
  //
  // Two small parsers, both pure string work, both bracketed for
  // `tests/test_doc_columns.py` to run in node.
  //
  // **The syntax, decided here and written into the plan's decisions.**
  //
  // `:::columns` opens a block, `:::column` starts the next column inside it,
  // and `:::` closes it. Three reasons for that shape rather than another:
  // `:::` fenced divs are what Pandoc, Obsidian's community plugins and every
  // markdown-it-container setup already use, so the text stays readable
  // somewhere else; the opening word says what the block is rather than naming
  // an id the way the multi-column plugins do; and a break that is `:::column`
  // (singular) can never be confused with the `:::` that closes, which is the
  // ambiguity every other candidate had.
  //
  // An image's options are `|`-separated and recognised by *shape*, not by
  // position: `![[photo.png|300]]` is Obsidian's own width syntax and reads the
  // same here, `![[photo.png|300|center]]` adds the alignment, and any option
  // that is neither a number nor an alignment is the caption. Shape rather than
  // order, because `![[photo.png|A river at dusk|400]]` is what people actually
  // type once they know both exist, and an editor that then made the caption
  // four hundred pixels wide would be obeying its grammar instead of its author.
  // The same options work on a plain markdown image through its alt text,
  // `![A river|400|center](/media/river.jpg)`, which is the form that travels.

  // DOC-BLOCKS-BEGIN

  //: `:::columns`, `::: columns`, `:::columns 3`: the count is accepted and
  //: ignored, because the number of columns is how many there *are*, and a
  //: header that disagrees with the body is a lie the renderer would have to
  //: pick a side in.
  const DOC_COLS_OPEN = /^[ \t]*:::[ \t]*columns\b[ \t]*\d*[ \t]*$/i;
  const DOC_COLS_BREAK = /^[ \t]*:::[ \t]*column[ \t]*$/i;
  const DOC_COLS_CLOSE = /^[ \t]*:::[ \t]*$/;
  const DOC_CODE_FENCE = /^[ \t]*(?:```|~~~)/;

  //: Every columns block in a text, with each column's own span. Offsets are the
  //: document's, like every other model in this file, so a widget built from one
  //: can dispatch a selection into it without a second coordinate system.
  //:
  //: An unclosed block is not a block: it is somebody halfway through typing
  //: one, and rendering the rest of the document as a column while they do it is
  //: the behaviour that makes live preview feel unsafe.
  function docColumnsBlocks(text) {
    const source = String(text == null ? "" : text);
    const lines = source.split("\n");
    const starts = [];
    let at = 0;
    for (const line of lines) {
      starts.push(at);
      at += line.length + 1;
    }
    const blocks = [];
    let fenced = false;
    let open = -1;
    let breaks = [];
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i];
      //: A code fence wins: `:::columns` inside one is an example of the syntax,
      //: not a use of it, and this file has already been bitten once by a
      //: scanner that could not tell the two apart.
      if (DOC_CODE_FENCE.test(line)) {
        fenced = !fenced;
        continue;
      }
      if (fenced) continue;
      if (open === -1) {
        if (DOC_COLS_OPEN.test(line)) {
          open = i;
          breaks = [];
        }
        continue;
      }
      if (DOC_COLS_BREAK.test(line)) {
        breaks.push(i);
        continue;
      }
      if (DOC_COLS_OPEN.test(line)) {
        //: A second opener before the close: the first one was never a block.
        open = i;
        breaks = [];
        continue;
      }
      if (!DOC_COLS_CLOSE.test(line)) continue;
      const edges = [open, ...breaks, i];
      const columns = [];
      for (let c = 0; c < edges.length - 1; c += 1) {
        const from = starts[edges[c]] + lines[edges[c]].length + 1;
        const to = Math.max(from, starts[edges[c + 1]] - 1);
        columns.push({ from, to, text: source.slice(from, to) });
      }
      blocks.push({
        from: starts[open],
        to: starts[i] + lines[i].length,
        openLine: open,
        closeLine: i,
        columns,
      });
      open = -1;
      breaks = [];
    }
    return blocks;
  }

  //: The block an offset is inside, or null. The whole block including its
  //: fences, because the caret being on the `:::` line is being in the block.
  function docColumnsAt(text, offset) {
    return docColumnsBlocks(text).find((block) => offset >= block.from && offset <= block.to) || null;
  }

  // DOC-BLOCKS-END

  // -----------------------------------------------------------------------------
  // Columns in Live: a block widget from a StateField
  // -----------------------------------------------------------------------------
  //
  // **Why a StateField and not the view plugin every other construct here uses.**
  // A columns block spans lines by definition, and a `Decoration.replace` that
  // contains a line break may not come from a plugin: CodeMirror throws
  // "Decorations that replace line breaks may not be specified via plugin" and
  // the whole view stops updating. A state field may provide one, which is
  // exactly the escape hatch the library documents for block widgets, and this
  // is the one construct in this editor that needs it.
  //
  // **The block is replaced only while the caret is outside it.** Inside, the
  // fences and the two columns are the plain text you typed and every other
  // decoration in Live applies to them as usual; that is the same "reveal what
  // you are in" rule the rest of this view follows, one block wide instead of
  // one line wide. Clicking a rendered column puts the caret at the top of that
  // column, and ArrowDown/ArrowUp into the block step inside it rather than over
  // it (`docColumnsArrowKeymap`), because a block you can only reach with a
  // mouse is a block a keyboard user cannot edit.
  let docColumnsFieldCache = null;

  function docColumnsField(CM) {
    if (docColumnsFieldCache) return docColumnsFieldCache;
    const { StateField } = CM.state;
    const { Decoration, EditorView, WidgetType } = CM.view;

    class DocColumnsWidget extends WidgetType {
      constructor(source, from) {
        super();
        this.source = source;
        this.from = from;
      }
      eq(other) {
        return other.source === this.source && other.from === this.from;
      }
      //: The widget's own DOM handles its clicks; everything else (a drag that
      //: started outside it, a wheel) belongs to the editor.
      ignoreEvent(event) {
        return event.type !== "mousedown";
      }
      toDOM(view) {
        const box = document.createElement("div");
        box.className = "doc-cols";
        const blocks = docColumnsBlocks(this.source);
        const columns = blocks.length ? blocks[0].columns : [];
        box.style.setProperty("--doc-cols", String(Math.max(1, columns.length)));
        for (const column of columns) {
          const col = document.createElement("div");
          col.className = "doc-col";
          //: Through the app's one markdown renderer, so a column holds what a
          //: document holds: headings, lists, links, an image.
          renderMarkdown(col, column.text);
          //: Where the caret goes when this column is clicked. The offsets in
          //: `blocks` are relative to the block's own text, so the block's start
          //: is added back here rather than at every use of it.
          col.dataset.docColFrom = String(this.from + column.from);
          box.appendChild(col);
        }
        box.addEventListener("mousedown", (event) => {
          const target = event.target instanceof Element ? event.target.closest("[data-doc-col-from]") : null;
          //: A link inside a column is a link: let it be clicked.
          if (event.target instanceof Element && event.target.closest("a, button")) return;
          event.preventDefault();
          const at = target ? Number(target.dataset.docColFrom) : this.from;
          view.dispatch({ selection: { anchor: Math.min(at, view.state.doc.length) } });
          view.focus();
        });
        return box;
      }
    }

    const build = (state) => {
      const text = docStr(state.doc);
      //: The cheap test first: a document with no `:::` in it at all is most of
      //: them, and this runs on every keystroke.
      if (!text.includes(":::")) return Decoration.none;
      const sel = state.selection.main;
      const ranges = [];
      for (const block of docColumnsBlocks(text)) {
        if (sel.from <= block.to && sel.to >= block.from) continue;
        ranges.push(
          Decoration.replace({
            widget: new DocColumnsWidget(text.slice(block.from, block.to), block.from),
            block: true,
          }).range(block.from, block.to)
        );
      }
      return Decoration.set(ranges, true);
    };

    docColumnsFieldCache = StateField.define({
      create: (state) => build(state),
      //: **`(value, tr)`, in that order**, which is the whole signature and cost
      //: an hour: written `(tr, value)` the field returned the *transaction* as
      //: its value on every update that was not an edit, the decorations facet
      //: was handed a Transaction where a RangeSet belonged, and the view died
      //: with "Cannot read properties of undefined (reading 'isEmpty')" on the
      //: next paint, nowhere near this line.
      update: (value, tr) => (tr.docChanged || tr.selection ? build(tr.state) : value),
      provide: (field) => EditorView.decorations.from(field),
    });
    return docColumnsFieldCache;
  }

  //: Arrow into a rendered block rather than over it. CodeMirror moves the caret
  //: *across* a replaced block range, which is right for a widget with nothing
  //: to edit in it and wrong for this one: the block is the text you wrote.
  function docColumnsArrowKeymap(CM) {
    const step = (view, back) => {
      const state = view.state;
      const sel = state.selection.main;
      if (!sel.empty) return false;
      const text = docStr(state.doc);
      if (!text.includes(":::")) return false;
      const line = state.doc.lineAt(sel.head);
      const next = back ? line.from - 1 : line.to + 1;
      if (next < 0 || next > state.doc.length) return false;
      const block = docColumnsAt(text, next);
      //: Only when the caret is not already in one: inside the block the arrows
      //: are the editor's own again.
      if (!block || docColumnsAt(text, sel.head)) return false;
      const columns = block.columns;
      const at = back && columns.length ? columns[columns.length - 1].to : (columns[0] ? columns[0].from : block.from);
      view.dispatch({ selection: { anchor: Math.max(0, Math.min(at, state.doc.length)) }, scrollIntoView: true });
      return true;
    };
    return CM.view.keymap.of([
      { key: "ArrowDown", run: (view) => step(view, false) },
      { key: "ArrowUp", run: (view) => step(view, true) },
    ]);
  }

  //: The file's whole surface: what documents.js and documents-cm.js call.
  Object.assign(window, { docColumnsBlocks, docColumnsField, docColumnsArrowKeymap });
})();
