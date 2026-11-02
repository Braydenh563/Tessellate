// documents-cm.js: the editor's two largest CodeMirror pieces (split out of
// documents.js, audit 1031 DC13).
//
// What is here, whole and verbatim: `docLivePlugin` and its cache (the one
// place a source offset becomes a rendered thing in Live: headings, emphasis,
// links, task boxes, wiki links, highlights, built from the markdown tree over
// the visible ranges) and `docCmTheme` (every CodeMirror rule that dresses the
// editor from the app's own tokens: the gutter, the finding underlines, the
// linter and completion lists, the search panel). Their helpers stayed in
// documents.js, which names both from `docCmExtensions`.
//
// **Loaded in the Library bundle, before documents.js**: the top level here is
// a cache and two function declarations and reads nothing from documents.js;
// every use is inside a function that runs after the bundle.

//: Built once and reused: a `ViewPlugin` is a class, and reconfiguring a
//: compartment with a *new* class every time would tear the plugin's state
//: down and rebuild it on every view switch.
let docLivePluginCache = null;

//: The one place a source offset becomes a rendered thing. Everything here is
//: computed from the lezer markdown tree (`syntaxTree`) over the visible
//: ranges only, except the two constructs the tree does not know about:
//: `==highlight==`, which is not markdown, and `[[wiki links]]`, which are
//: this app's own. Those two are found by a regex over the visible text and
//: are skipped inside code, which is the same rule `layerDocWikiLinks` has
//: always followed in the preview.
function docLivePlugin(CM) {
  if (docLivePluginCache) return docLivePluginCache;
  const { Decoration, ViewPlugin, EditorView, WidgetType } = CM.view;
  const { syntaxTree } = CM.language;
  const hidden = Decoration.replace({});

  //: A real checkbox, because a task list you cannot tick is a list of
  //: sentences with brackets in front of them. Toggling writes the source, so
  //: the document and the tick can never disagree.
  class DocTaskWidget extends WidgetType {
    constructor(checked, from, to) {
      super();
      this.checked = checked;
      this.from = from;
      this.to = to;
    }
    //: The tick and the marker's length, not its place (DX1): with the start
    //: in it, every box below a typed key was built again, per key. The click
    //: asks the view where the box is now.
    eq(other) {
      return other.checked === this.checked && other.to - other.from === this.to - this.from;
    }
    //: **The view is handed in, and the listener goes on the element.** The
    //: first version toggled from the plugin's own `mousedown` handler, which
    //: works for a pointer and for nothing else: a scripted `click()`, and
    //: more importantly the keyboard (a checkbox is focusable and Space
    //: activates it), raise `click` and no `mousedown` at all. Caught by
    //: measuring, `scratchpad/ui-sweeps/cm-live.js` toggled nothing.
    //:
    //: **The box is drawn at the text's size and pressed at the target's.**
    //: The app's checkbox floor (`--target-min`) sized the box itself, so a
    //: task in a 24px line drew a 28px square on a desktop and a 44px one on
    //: a phone, where its line grew to 36px and two tasks' boxes overlapped
    //: (measured, docphonebar.js). The input is now 1.1em and the span around
    //: it carries the target: an invisible strip `--target-min` wide and one
    //: line tall (09-editor.css), so the press area is the floor's width
    //: without pushing the text, and two task lines' strips meet rather than
    //: overlap. The listener is on the span: a press on the strip lands
    //: there, a press on the box bubbles there, and Space on the focused box
    //: raises the same `click`.
    toDOM(view) {
      const hit = document.createElement("span");
      hit.className = "cm-md-task-hit";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.className = "cm-md-task";
      box.checked = this.checked;
      box.setAttribute("aria-label", this.checked ? "Done" : "Not done");
      hit.appendChild(box);
      const size = this.to - this.from;
      hit.addEventListener("click", (event) => {
        event.preventDefault();
        const from = view.posAtDOM(hit);
        const to = from + size;
        const marker = view.state.doc.sliceString(from, to);
        //: The source is what changes, and the tick follows it on the next
        //: repaint. Writing the two separately is how they come to disagree.
        view.dispatch({ changes: { from, to, insert: /[xX]/.test(marker) ? "[ ]" : "[x]" } });
      });
      return hit;
    }
  }

  //: **Same-origin sources only.** A document is text a person can paste into,
  //: and an `<img src="http://tracker/…">` in one would turn opening a note
  //: into a network request to somebody else's server, in an app whose whole
  //: claim is that it works with the plug pulled. A remote address is left as
  //: the markdown that it is.
  class DocImageWidget extends WidgetType {
    constructor(src, alt, underSource = false) {
      super();
      this.src = src;
      this.alt = alt;
      this.underSource = underSource;
      //: `![A river|400|center](/media/river.jpg)`: the options ride in the alt
      //: text, which is the form that survives being opened somewhere else.
      this.options = imageOptionsFromAlt(alt);
    }
    eq(other) {
      return other.src === this.src && other.alt === this.alt && other.underSource === this.underSource;
    }
    toDOM(view) {
      const img = document.createElement("img");
      img.className = this.underSource ? "cm-md-image cm-md-image-under" : "cm-md-image";
      //: **Through `mediaSrc`, like every other image in this app.** An
      //: `<img>` cannot send a header, so `/media/…` and `/files/…` carry the
      //: unlock token as a query parameter; this widget set the raw path and
      //: every image in Live view answered 401, which the app's own missing
      //: media handler then drew as "no longer in this notebook" over a file
      //: that was still there. Measured against this branch before the fix:
      //: two console 401s per image, `naturalWidth` 0 in Live and 1 in the
      //: rendered pane beside it, which is the same file through the two
      //: paths. The embed path below already did this; this one never did.
      img.src = mediaSrc(this.src);
      img.alt = this.options.caption || this.options.name || "";
      if (this.underSource) return imageApplyOptions(img, this.options);
      //: **Resized and aligned where it is shown** (decision 8, the audit's
      //: D5): a frame round the picture holding a grip on its lower right
      //: corner and an align button, both writing the options back into the
      //: alt text (`imageAltWith`), so Read, a print and an export agree.
      const frame = document.createElement("span");
      frame.className = "cm-md-image-frame";
      frame.appendChild(img);
      if (this.options.width) frame.dataset.sized = "1";
      docImageLive(view, frame, this.options);
      return imageApplyOptions(frame, this.options);
    }
  }

  const sameOrigin = (url) => {
    const clean = String(url || "").trim();
    if (!clean || clean.startsWith("//")) return null;
    if (clean.startsWith("/")) return clean;
    try {
      const parsed = new URL(clean, window.location.href);
      return parsed.origin === window.location.origin ? parsed.href : null;
    } catch {
      return null;
    }
  };

  //: The callout kinds the rest of the app already renders (`CALLOUT_KINDS` in
  //: editor.js) and the syntax GitHub, Obsidian and Typora all understand.
  //: The capture is the whole `[!kind]`, so the marker can be hidden the way
  //: every other marker here is; the group inside it names the kind.
  const CALLOUT = /^>\s*(\[!([A-Za-z][\w-]*)\][-+]?)/;
  //: How deep a list item is indented before the indent stops growing. Past
  //: four levels the number is more useful as "this is deep" than as a count,
  //: and an indent that kept growing would push a badly nested line off the
  //: measure the whole document is set in.
  const LIST_DEPTH_MAX = 4;

  //: **A bullet's dash, drawn as a bullet while the caret is elsewhere.** The
  //: last piece of raw markdown left in a rendered list: `-`, `*` and `+` all
  //: mean the same thing and a reader has no use for knowing which was typed.
  //:
  //: Safe to replace here where hiding a `**` is not, and the difference is
  //: length: this is one character standing in for one character, at the
  //: start of a line, so nothing after it moves by more than the difference
  //: between two glyph widths, and the caret cannot be inside it (the line is
  //: not replaced while it is touched). `ignoreEvent` returns false for the
  //: reason the callout label's does: a click on the bullet is a click into
  //: the line behind it.
  class DocBulletWidget extends WidgetType {
    eq() {
      return true;
    }
    ignoreEvent() {
      return false;
    }
    toDOM() {
      const dot = document.createElement("span");
      dot.className = "cm-md-li-mark cm-md-li-bullet";
      dot.textContent = "\u2022";
      return dot;
    }
  }

  //: **A callout says which kind it is, in words, where its marker was.**
  //: Measured before this: with the caret away from the line, `> [!note] a
  //: callout` rendered as `[!note] a callout` on a tinted, accent-barred line.
  //: The `>` went, as it should, and the `[!note]` stayed, which is the one
  //: thing on the line that is pure markdown syntax. The owner's sentence is
  //: about exactly that: "md formatting should go invisible unless i click
  //: back on that word or section". Hiding it outright would leave a note and
  //: a warning looking identical apart from a border colour, so the marker is
  //: replaced by the label the rest of the app already uses for that kind
  //: (`CALLOUT_KINDS` in editor.js, the same table the "/" menu writes
  //: from), which is what Obsidian shows in the same place.
  //: **The kind once, as its icon, and the title after it is the line's own
  //: text** (INBOX 486, the owner: "I have no clue how to use these things":
  //: the chip read "Note" and the title "Note" beside it). The word is drawn
  //: only when there is no title, muted, standing in for one. The icon is a
  //: button with a caret, the kind picker (`docCalloutKindMenu`).
  class DocCalloutWidget extends WidgetType {
    constructor(kind, fold, at, titled) {
      super();
      this.kind = kind;
      this.titled = titled;
      //: `null` when the callout is not a toggle at all, otherwise the line it
      //: starts on and whether it is currently folded.
      this.fold = fold;
      //: The callout's first line, which the kind button rewrites.
      this.at = at;
    }
    eq(other) {
      //: Not the place (DX1): the buttons ask the view for their line when pressed.
      return (
        other.kind === this.kind &&
        other.titled === this.titled &&
        !!other.fold === !!this.fold &&
        (!this.fold || other.fold.closed === this.fold.closed)
      );
    }
    ignoreEvent() {
      //: A click on the label is a click into the line behind it: the widget
      //: is a rendering of text that is really there, and swallowing the
      //: event would make the one spot on the line you cannot put a caret in.
      return false;
    }
    toDOM() {
      const meta =
        (typeof CALLOUT_KINDS === "object" && CALLOUT_KINDS[this.kind]) || null;
      const chip = document.createElement("span");
      chip.className = `cm-md-callout-label cm-md-callout-label-${this.kind}`;
      //: **The icon is the kind switcher** (INBOX 421 b: "change kind from the
      //: rendered block"). A tile of the kind's own tint, like the rendered
      //: head's, that opens the kinds menu (`docCalloutKindMenu`); the word
      //: beside it still puts the caret in the line, as it always did. The
      //: icon was once written as its `ph:` token in text here, which printed
      //: "ph:warning Warning" (fixed 6e072b2); it is an element now.
      const icon = document.createElement("span");
      icon.className = "cm-md-callout-kindbtn";
      icon.dataset.docCalloutKind = String(this.at);
      icon.title = `${meta ? meta.label : "Callout"}: change its kind or folding`;
      const glyph = document.createElement("i");
      glyph.className = `ph ph-${String(meta ? meta.icon : "ph:note").replace(/^ph:/, "")}`;
      glyph.setAttribute("aria-hidden", "true");
      const caret = document.createElement("i");
      caret.className = "ph ph-caret-down cm-md-callout-caret";
      caret.setAttribute("aria-hidden", "true");
      icon.append(glyph, caret);
      const word = document.createElement("span");
      word.className = "cm-md-callout-word";
      word.textContent = meta ? meta.label : this.kind;
      chip.append(icon);
      if (!this.titled) chip.append(word);
      //: **A callout written `[!note]-` or `[!note]+` is a toggle**, which is
      //: the syntax Obsidian uses and the "toggles" half of Phase 3 item 2.
      //: The marker is the *initial* state and clicking does not rewrite it,
      //: which is also Obsidian's behaviour and the right one: folding a
      //: section to read past it is not an edit to the document, and a
      //: notebook whose files change every time somebody collapses something
      //: has no clean diffs left.
      if (this.fold) {
        const chevron = document.createElement("span");
        chevron.className = "cm-md-callout-fold";
        const caret = document.createElement("i");
        caret.className = `ph ph-caret-${this.fold.closed ? "right" : "down"}`;
        caret.setAttribute("aria-hidden", "true");
        chevron.appendChild(caret);
        word.dataset.docCalloutFold = String(this.fold.at);
        chevron.dataset.docCalloutFold = String(this.fold.at);
        word.title = chevron.title = this.fold.closed ? "Show what is inside" : "Fold this away";
        chip.append(" ", chevron);
      }
      return chip;
    }
  }

  //: An empty callout body's hint ("Write the note"): drawn after the line's
  //: end, not text, so nothing is saved and typing replaces it.
  class DocCalloutHintWidget extends WidgetType {
    constructor(text) {
      super();
      this.text = text;
    }
    eq(other) {
      return other.text === this.text;
    }
    toDOM() {
      const hint = document.createElement("span");
      hint.className = "cm-md-callout-hint";
      hint.setAttribute("aria-hidden", "true");
      hint.textContent = this.text;
      return hint;
    }
  }

  //: **A table cell that is empty still has to hold its column open.** The
  //: rendered table is a CSS grid over the line, and its columns are its
  //: children: a cell with no characters in it contributes no child, so the
  //: row silently loses a column and every cell after it slides left. One
  //: empty span, carrying the cell's own classes, is the whole fix.
  class DocTableCellWidget extends WidgetType {
    constructor(cls) {
      super();
      this.cls = cls;
    }
    eq(other) {
      return other.cls === this.cls;
    }
    ignoreEvent() {
      return false;
    }
    toDOM() {
      const cell = document.createElement("span");
      cell.className = this.cls;
      cell.contentEditable = "false";
      return cell;
    }
  }

  //: The cell menu, on the table the caret is in. Rebuilt when the caret
  //: changes cell (`eq` on the key) because two of its rows are unavailable
  //: in the header and in a one-column table, and a menu that says a row can
  //: be deleted when it cannot is worse than no menu.
  class DocTableMenuWidget extends WidgetType {
    constructor(key, context) {
      super();
      this.key = key;
      this.context = context;
    }
    eq(other) {
      return other.key === this.key;
    }
    //: The menu is a control, not text: CodeMirror must not try to put a
    //: caret inside it or read a selection out of it.
    ignoreEvent() {
      return true;
    }
    //: **And it must not read the menu's own DOM work as the document
    //: changing under it** (INBOX 290). `openActionMenu` shows the popup,
    //: measures it and, when it would be clipped, reparents it to `<body>`;
    //: every one of those is a mutation inside this widget, and a widget that
    //: does not claim its mutations makes CodeMirror re-read the content DOM,
    //: which rebuilt the view and blurred the editor. Measured before the fix:
    //: after one press, `.cm-editor.cm-focused` was gone, the widget was
    //: unmounted, and the menu was left standing under the header row with no
    //: opener, which is both halves of the report ("another row appears below
    //: it", "I cant click the meatball button").
    ignoreMutation() {
      return true;
    }
    //: A menu whose opener is being removed has to close with it, or it is
    //: left floating over the document.
    destroy(dom) {
      if (dom && dom.querySelector(".action-menu:not(.hidden)")) {
        closeActionMenus();
      }
    }
    toDOM() {
      const wrap = docTableMenu(this.context);
      wrap.classList.add("cm-md-table-menu");
      return wrap;
    }
  }

  //: **A remark is a pin, not a span of purple text** (Phase 5 item 1). The
  //: `%%…%%` hides like every other marker and a small control takes its place,
  //: because a comment has to be *visible* in the document without being *read*
  //: in it: that is the whole difference between a margin note and the prose.
  //: Pressing it opens the Comments panel at that remark rather than a popover
  //: over the sentence, which is DESIGN.md's one-surface-at-a-time rule and the
  //: decision DOCUMENTS_PLAN 12 D3 made for the writing panel.
  class DocCommentWidget extends WidgetType {
    constructor(body, at) {
      super();
      this.body = body;
      this.at = at;
    }
    //: The words, not the place (DX1): a key above the pin no longer draws it again, and
    //: the click asks the view where the pin is now.
    eq(other) {
      return other.body === this.body;
    }
    //: A control, not text: CodeMirror must not put a caret inside it.
    ignoreEvent() {
      return true;
    }
    toDOM(view) {
      const pin = document.createElement("button");
      pin.type = "button";
      pin.className = "doc-comment-pin";
      pin.title = this.body;
      pin.setAttribute("aria-label", `Comment: ${this.body}`);
      const icon = document.createElement("i");
      icon.className = "ph ph-chat-teardrop-text";
      icon.setAttribute("aria-hidden", "true");
      pin.appendChild(icon);
      pin.addEventListener("click", (event) => {
        event.preventDefault();
        docShowComment(view ? view.posAtDOM(pin) : this.at);
      });
      return pin;
    }
  }

  //: **Math, rendered where it was written.** The renderer is the MathML one
  //: at the top of this file, so what Live draws and what an export would draw
  //: come from one place. The widget replaces the `$…$` only while the caret
  //: is off its line, which is the rule every other marker here follows: the
  //: way to edit a formula is to put the caret in it and see the TeX again.
  class DocMathWidget extends WidgetType {
    constructor(tex, display) {
      super();
      this.tex = tex;
      this.display = display;
    }
    eq(other) {
      return other.tex === this.tex && other.display === this.display;
    }
    ignoreEvent() {
      return false;
    }
    toDOM(view) {
      const host = document.createElement("span");
      host.className = this.display ? "cm-md-math cm-md-math-block" : "cm-md-math";
      try {
        //: An empty `{}` is a box left to fill (the field's dotted box), so
        //: it is drawn as one here: a fraction with nothing under it is a
        //: target to click, not a 12px sliver.
        host.appendChild(docMathRender(this.tex.replace(/\{\s*\}/g, "{\u25a1}"), this.display));
      } catch {
        host.textContent = this.tex;
      }
      host.title = "Click to edit the equation";
      //: **A click edits the equation where it is** (INBOX 1473 a): a field
      //: over the widget (math-field.js, lazy) in place of the caret landing on
      //: raw TeX. The press is taken here so the editor never sees it and the
      //: selection stays where it was; the range is the widget's own, read
      //: when the press lands, and the field checks it is still that text
      //: before it writes.
      host.addEventListener("mousedown", (event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        event.stopPropagation();
        const delim = this.display ? "$$" : "$";
        const from = view.posAtDOM(host);
        const to = from + delim.length * 2 + this.tex.length;
        ensureModule("mathField").then(() => {
          if (typeof openMathInPlace === "function") openMathInPlace({ view, host, from, to, delim, tex: this.tex });
        });
      });
      return host;
    }
  }

  //: An icon in a line, drawn by the renderer every other reader uses.
  class DocIconWidget extends WidgetType {
    constructor(name) {
      super();
      this.name = name;
    }
    eq(other) {
      return other.name === this.name;
    }
    toDOM() {
      return appendPlainText.icon(this.name) || document.createElement("span");
    }
  }

  //: **`[TOC]` as the contents it stands for** (INBOX 421 b). The headings
  //: come from the document's own text (`mdTocEntries`, app.js), the same
  //: list the Read view draws, and an entry moves the caret to its heading
  //: and scrolls it to the top, which is what "contents" means in an editor.
  //: `eq` compares the serialised list, so typing in a paragraph does not
  //: redraw it and renaming a heading does.
  class DocTocWidget extends WidgetType {
    constructor(entries) {
      super();
      this.entries = entries;
      this.key = JSON.stringify(entries);
    }
    eq(other) {
      return other.key === this.key;
    }
    ignoreEvent() {
      return true;
    }
    toDOM(view) {
      const nav = mdTocElement();
      nav.classList.add("cm-md-toc");
      const list = nav.querySelector(".md-toc-list") || nav;
      const top = this.entries.length ? Math.min(...this.entries.map((e) => e.level)) : 1;
      for (const entry of this.entries) {
        const item = document.createElement("li");
        item.className = `md-toc-item md-toc-depth-${Math.min(3, entry.level - top)}`;
        const link = document.createElement("a");
        link.href = "#";
        link.textContent = entry.text.replace(/[*_`~]/g, "");
        link.addEventListener("mousedown", (event) => {
          event.preventDefault();
          docTocJump(view, entry);
        });
        item.appendChild(link);
        list.appendChild(item);
      }
      if (!this.entries.length) {
        const empty = document.createElement("li");
        empty.className = "md-toc-empty";
        empty.textContent = "Headings you add appear here.";
        list.appendChild(empty);
      }
      return nav;
    }
  }

  //: **`![[name]]` draws the thing itself.** The card comes from whichever
  //: renderer already owns that kind (`docEmbedNode`); this only decides where
  //: it goes and when. `ignoreEvent` is true because the cards carry their own
  //: controls: a file tile has Open and Save on it, and CodeMirror treating
  //: those clicks as clicks into the text would put a caret in the middle of
  //: a button.
  class DocEmbedWidget extends WidgetType {
    //: The whole `name|300|center|caption` spec, not just the name: the name
    //: is what resolves to a thing and the options are how it is drawn, and
    //: keeping them together is what lets `eq` say "this is the same embed"
    //: about two widgets that differ only in their width.
    constructor(spec) {
      super();
      this.spec = spec;
      this.options = imageOptions(spec);
      this.name = this.options.name;
    }
    eq(other) {
      return other.spec === this.spec;
    }
    ignoreEvent() {
      return true;
    }
    toDOM() {
      const host = document.createElement("span");
      host.className = "cm-md-embed";
      host.dataset.docEmbed = this.name;
      docEmbedFill(host, this.name, this.options);
      //: The card opens its target, except where the card already has a
      //: control of its own under the pointer.
      host.addEventListener("click", (event) => {
        if (event.target instanceof Element && event.target.closest("button, a, input")) return;
        docOpenWikiTarget(this.name);
      });
      return host;
    }
  }

  //: `record` collects every reveal this build decided (`probes`, flat
  //: `[from, to, revealed]`) and whether anything read the caret's exact
  //: position rather than "touched or not" (`selFree`: a table's active cell
  //: and its menu row do), which is what lets a caret move skip the rebuild.
  function build(view, record = { probes: [], selFree: true }) {
    const state = view.state;
    const doc = state.doc;
    const sel = state.selection.main;
    const selRanges = state.selection.ranges;
    const ranges = [];
    //: **Nothing is revealed while the editor is not focused.** A selection
    //: exists whether or not anyone is in the editor, and a document just
    //: opened has one at offset 0, which is almost always the title heading:
    //: so every document opened with the rendered view on showed its first
    //: line's "#" before the reader had touched anything. The owner's
    //: sentence is "md formatting should go invisible unless i click back on
    //: that word or section", and an untouched document is the one case where
    //: nobody has clicked on anything at all.
    const focused = view.hasFocus;
    //: `held`: a rendered widget's rule (INBOX 1547), source only while a
    //: selection starts in it, so a drag that crosses a diagram leaves it drawn.
    const probe = (from, to, held = false) => {
      const on = focused && (held ? docLiveSpanTouched.anchorIn(selRanges, from, to) : docLiveSpanTouched(selRanges, from, to));
      record.probes.push(from, to, (on ? 1 : 0) | (held ? 2 : 0));
      return on;
    };
    const widgetRevealed = (from, to) => probe(from, to, true);
    const touched = probe;
    const lineTouched = (pos) => {
      const line = doc.lineAt(pos);
      return touched(line.from, line.to);
    };
    //: **Inline marks reveal per span, block marks per line** (INBOX 1473 b,
    //: which remakes the line rule this file followed since the 28.4px note
    //: below; DESIGN.md, "A markdown mark in Live view").
    //:
    //: A span (`**bold**`, `*em*`, `` `code` ``, `~~struck~~`, `==mark==`, a
    //: link, a `[[wiki link]]`, an escape, a `$math$` range taken whole) shows
    //: its marks while a selection is inside it or touching either end, and
    //: every other span on the line stays rendered: Obsidian's rule, asked for
    //: by name. Nested spans follow from containment: the caret inside `*b*`
    //: in `**a *b* c**` is inside both, and in neither of their neighbours.
    //:
    //: The cost the line rule was chosen to avoid comes back at a span's
    //: right edge, and only there: ArrowLeft from just past `**bold** ` lands
    //: touching the span, its marks appear to the caret's left, and the caret
    //: is drawn one mark's width to the right of where it was (measured 28.4px
    //: for `**` at the time). That is what Obsidian does, and what the owner
    //: asked for; `cm-reveal.js` holds the rest of that walk to "never right".
    //: A click is measured there too: the clicked character keeps its offset
    //: and moves only by the opening mark's width, where the line rule moved
    //: it by every mark before it on the line.
    //:
    //: Block marks (`#`, a list's bullet or number, `>`, a task box, `---`, a
    //: table's rule) keep the line rule, which is also Obsidian's: they sit at
    //: the line's start, and revealing them as the caret crossed a word would
    //: shift the whole line under it. Code fences and Mermaid keep their own
    //: block rule (`blockRevealed`): the fence reveals while the caret is
    //: anywhere in the block.
    const rangeRevealed = (from, to) =>
      probe(from, to);
    const blockRevealed = (from, to) =>
      touched(doc.lineAt(from).from, doc.lineAt(to).to);
    //: Whether the line numbers are showing, read once per build rather than
    //: per fenced block: the fence rows collapse only when they are off, see
    //: the note beside `cm-md-fence-quiet` below.
    const gutterOn = docFenceGutterOn();
    const tree = syntaxTree(state);
    //: The document as one string, at most once per build, for a table's menu
    //: and the frontmatter; a table itself is parsed from its own lines
    //: (`docTableParse.at`).
    let sourceText = null;
    const source = () => {
      if (sourceText === null) sourceText = docStr(doc);
      return sourceText;
    };
    //: A table is drawn once, from whichever of its lines the viewport reaches
    //: first.
    const tableSeen = new Set();
    //: The callouts met so far, for `QuoteMark` (a parent is entered first).
    const calloutSpans = [];

    //: **A replace decoration may not contain a line break, and this is not a
    //: style rule: CodeMirror throws "Decorations that replace line breaks may
    //: not be specified via plugin" and the whole view stops updating.** Every
    //: hidden marker below is one or two characters, which looks safe and is
    //: not: a markdown link's text can wrap across a soft line break, so
    //: `[some\nlabel](url)` puts a newline inside the `](url)` this hides, and
    //: an image's alt text can do the same. The failure lands on one unusual
    //: document, in a plugin nowhere near the link that caused it, which is
    //: the shape this codebase keeps recording. One guard, at the one place
    //: that pushes a replacement.
    const hide = (from, to) => {
      if (to <= from) return;
      if (doc.sliceString(from, to).includes("\n")) return;
      ranges.push(hidden.range(from, to));
    };

    for (const visible of view.visibleRanges) {
      tree.iterate({
        from: visible.from,
        to: visible.to,
        enter: (node) => {
          const name = node.name;
          //: `Setext` as well as `ATX`, and this was a real hole. A setext
          //: heading is the `Title` / `=====` form, and its underline is a
          //: `HeaderMark` like any other, so the branch below was already
          //: hiding it while this branch matched `ATXHeading` only: the
          //: underline vanished, the line got no heading class, and a setext
          //: heading rendered as ordinary body text. Found by taking an
          //: inventory of every markdown line against what it renders as,
          //: which is what `scratchpad/ui-sweeps/cm-reveal.js` now does.
          //: A setext heading spans two lines and the class belongs on the
          //: first, which `doc.lineAt(node.from)` already gives.
          const heading = /^(?:ATX|Setext)Heading([1-6])$/.exec(name);
          if (heading) {
            const line = doc.lineAt(node.from);
            ranges.push(Decoration.line({ class: `cm-md-h${heading[1]}` }).range(line.from));
            return undefined;
          }
          if (name === "HeaderMark") {
            if (lineTouched(node.from)) return false;
            let end = node.to;
            while (end < doc.length && doc.sliceString(end, end + 1) === " ") end += 1;
            hide(node.from, end);
            return false;
          }
          if (name === "StrongEmphasis" || name === "Emphasis" || name === "Strikethrough") {
            const cls =
              name === "StrongEmphasis" ? "cm-md-strong" : name === "Emphasis" ? "cm-md-em" : "cm-md-strike";
            ranges.push(Decoration.mark({ class: cls }).range(node.from, node.to));
            return undefined;
          }
          if (name === "InlineCode") {
            ranges.push(Decoration.mark({ class: "cm-md-code" }).range(node.from, node.to));
            return undefined;
          }
          if (name === "EmphasisMark" || name === "StrikethroughMark" || name === "CodeMark" || name === "CodeInfo") {
            const parent = node.node.parent;
            if (!parent) return false;
            //: A fence's own ``` (and the language word after it) is hidden
            //: like every other mark while the caret is elsewhere: the block
            //: keeps its boundary through the `cm-md-fence` line ground, so
            //: the three backticks were the one piece of syntax the live view
            //: still showed after you clicked off a code block (INBOX 198).
            //: Back the moment the caret is inside the block, like the rest.
            const revealedBy = parent.name === "FencedCode" ? blockRevealed : rangeRevealed;
            if (!revealedBy(parent.from, parent.to)) hide(node.from, node.to);
            return false;
          }
          if (name === "Link") {
            const text = doc.sliceString(node.from, node.to);
            const close = text.lastIndexOf("](");
            if (close <= 0) return false;
            const url = text.slice(close + 2, text.length - 1);
            ranges.push(
              Decoration.mark({
                class: "cm-md-link",
                attributes: { "data-doc-href": url, title: `Ctrl+click to open ${url}` },
              }).range(node.from + 1, node.from + close)
            );
            if (!rangeRevealed(node.from, node.to)) {
              hide(node.from, node.from + 1);
              hide(node.from + close, node.to);
            }
            return false;
          }
          if (name === "Image") {
            const text = doc.sliceString(node.from, node.to);
            const close = text.lastIndexOf("](");
            if (close <= 1) return false;
            const src = sameOrigin(text.slice(close + 2, text.length - 1));
            if (!src) return false;
            //: **The caret on an image's line shows its markdown and keeps the
            //: picture, under it** (INBOX 442, the owner: "the image/sketch in
            //: the graph popup didnt render"). The popup's Edit put the caret
            //: at the end of a note whose last line was the picture, so the
            //: line revealed as source and the picture went, which read as an
            //: image that never rendered. A widget after the source keeps it.
            if (widgetRevealed(node.from, node.to)) {
              ranges.push(
                Decoration.widget({ widget: new DocImageWidget(src, text.slice(2, close), true), side: 1 }).range(node.to)
              );
              return false;
            }
            //: Same rule as `hide`: an image whose alt text wraps would put a
            //: line break inside the range this widget replaces.
            if (text.includes("\n")) return false;
            ranges.push(
              Decoration.replace({
                widget: new DocImageWidget(src, text.slice(2, close)),
              }).range(node.from, node.to)
            );
            return false;
          }
          //: **A bare address and an `<address>` are links too** (INBOX 392's
          //: inventory, `scratchpad/ui-sweeps/doclivemd.js`). The GitHub
          //: dialect parses both, as a `URL` on its own and as an `Autolink`
          //: holding one, and the view drew neither: a pasted address was
          //: plain text you could not open, and `<https://…>` kept its
          //: brackets. Both now wear the link chip and open on Ctrl+click
          //: through the same `data-doc-href` a `[text](url)` link uses. A
          //: `URL` inside a `Link` or an `Image` never reaches here: those
          //: two branches return false and the walk skips their children.
          if (name === "Autolink") {
            const url = node.node.getChild("URL");
            if (!url) return false;
            const href = doc.sliceString(url.from, url.to);
            ranges.push(
              Decoration.mark({
                class: "cm-md-link",
                attributes: { "data-doc-href": href, title: `Ctrl+click to open ${href}` },
              }).range(url.from, url.to)
            );
            if (!rangeRevealed(node.from, node.to)) {
              hide(node.from, url.from);
              hide(url.to, node.to);
            }
            return false;
          }
          if (name === "URL") {
            const href = doc.sliceString(node.from, node.to);
            ranges.push(
              Decoration.mark({
                class: "cm-md-link",
                attributes: { "data-doc-href": href, title: `Ctrl+click to open ${href}` },
              }).range(node.from, node.to)
            );
            return false;
          }
          //: `\*` is how a writer says "a star, not emphasis", and the
          //: backslash is syntax like every other marker here: hidden while
          //: the caret is elsewhere, back when it is in or beside the escape.
          if (name === "Escape") {
            if (!rangeRevealed(node.from, node.to)) hide(node.from, node.from + 1);
            return false;
          }
          if (name === "TaskMarker") {
            const marker = doc.sliceString(node.from, node.to);
            //: **A finished task reads as finished**, struck through in the
            //: muted ink, which is what every task list the plan compares
            //: against does and what the rendered view now does too
            //: (09-editor.css). Drawn whether or not the caret is on the
            //: line: the `[x]` coming back is a reveal, the item being done
            //: is a fact about it.
            if (/[xX]/.test(marker)) {
              const task = node.node.parent;
              const end = Math.min(task ? task.to : node.to, doc.lineAt(node.from).to);
              if (end > node.to) {
                ranges.push(Decoration.mark({ class: "cm-md-task-done" }).range(node.to, end));
              }
            }
            if (lineTouched(node.from)) return false;
            ranges.push(
              Decoration.replace({
                widget: new DocTaskWidget(/[xX]/.test(marker), node.from, node.to),
              }).range(node.from, node.to)
            );
            //: The space after `]` goes with the dash's: a space's width is the
            //: font's, so it left the first line's words 0.35em past the
            //: list's hanging indent and a wrapped line fell back under the
            //: box. With it hidden the box (a fixed 1.6em, `.cm-md-task-hit`) is the
            //: whole 1.6em lead, and the wrap lines up under the words.
            if (doc.sliceString(node.to, node.to + 1) === " ") ranges.push(hidden.range(node.to, node.to + 1));
            return false;
          }
          //: **Lists, which the live view drew as plain text.** Measured
          //: against the same document's own paragraph: a `- First bullet`
          //: line had the same left edge, the same 0 indent and the same 0
          //: padding as a paragraph, and a nested `  - Nested bullet` was
          //: drawn at that same left edge too, so nesting was invisible and a
          //: wrapped item ran back under its own marker. The single most
          //: common construct in markdown was the one this view did nothing
          //: for (INBOX 262: "the rendering on the live view of the documents
          //: needs a lot of improvement").
          //:
          //: **A hanging indent rather than a hidden marker**, and that is
          //: the decision this file's long note beside `rangeRevealed`
          //: argues: taking characters out from under the caret moves the
          //: text the caret is in, which is the reflow bug measured at 28.4px
          //: backwards on a leftward keystroke. The marker stays where it is
          //: and the line is indented around it, so nothing under the caret
          //: moves at any time, and a wrapped line aligns under its own text
          //: the way a list reads on paper.
          //:
          //: The depth is the item's own indentation in the document, in
          //: units of two spaces (the width a tab is drawn at here), capped:
          //: past four levels the indent is more useful as a signal that it
          //: is deep than as an accurate count, and an uncapped one would
          //: push a badly nested line off the measure.
          if (name === "ListItem") {
            const line = doc.lineAt(node.from);
            const lead = /^[ \t]*/.exec(line.text)[0];
            const depth = Math.min(
              LIST_DEPTH_MAX,
              Math.floor(lead.replace(/\t/g, "  ").length / 2)
            );
            //: Every line the item occupies, so a two-line bullet keeps its
            //: indent on the continuation as well as on the marker row. The
            //: same walk the blockquote below does, for the same reason.
            for (let at = node.from; at <= node.to; ) {
              const row = doc.lineAt(at);
              ranges.push(
                Decoration.line({ class: `cm-md-li cm-md-li-${depth}` }).range(row.from)
              );
              if (row.to >= node.to) break;
              at = row.to + 1;
            }
            //: The marker itself, dimmed to the muted ink so the eye reads
            //: the words and not the punctuation, and left in place so it can
            //: still be selected, deleted and typed over. Ordered and
            //: unordered take the same class: an editor that draws "1." in
            //: one colour and "-" in another is saying they are different
            //: kinds of thing, and they are not.
            const mark = /^[ \t]*([-*+]|\d+[.)])(?=\s)/.exec(line.text);
            if (mark) {
              const from = line.from + mark[0].length - mark[1].length;
              const to = from + mark[1].length;
              //: A number carries information ("this is item 3") and stays as
              //: it was typed; a dash does not, and becomes a bullet while
              //: the caret is elsewhere. Both keep the muted ink.
              //: **A task has its box, not a bullet as well** (INBOX 710: "a
              //: bullet beside a task box"). The dash and the space after it
              //: go while the caret is elsewhere; the box (the task marker's
              //: widget, 1.1em and its 0.4em margin) takes the hanging
              //: indent's 1.6em, so a wrapped line still aligns under its
              //: words.
              const taskLead = /^[ \t]*[-*+]\s+(?=\[[ xX]\]\s)/.exec(line.text);
              if (taskLead && !touched(line.from, line.to)) {
                ranges.push(hidden.range(from, line.from + taskLead[0].length));
              } else if (/^[-*+]$/.test(mark[1]) && !touched(line.from, line.to)) {
                ranges.push(
                  Decoration.replace({ widget: new DocBulletWidget() }).range(from, to)
                );
                //: The space after it goes: the bullet is a fixed 1.6em box, so
                //: the first line's words start exactly where a wrapped line's
                //: do (a space is the font's width, which left them 11px apart).
                if (doc.sliceString(to, to + 1) === " ") ranges.push(hidden.range(to, to + 1));
              } else if (/^\d+[.)]$/.test(mark[1]) && !touched(line.from, line.to)) {
                //: A number and its space share a box at least 1.6em wide, so a
                //: short number's wrap lines up as the bullet's does.
                const space = doc.sliceString(to, to + 1) === " " ? 1 : 0;
                ranges.push(Decoration.mark({ class: "cm-md-li-mark cm-md-li-num" }).range(from, to + space));
              } else {
                ranges.push(Decoration.mark({ class: "cm-md-li-mark" }).range(from, to));
              }
            }
            return undefined;
          }
          if (name === "Blockquote") {
            const first = doc.lineAt(node.from);
            const callout = CALLOUT.exec(first.text);
            //: The kind as the reader means it: Obsidian's aliases resolve
            //: (`caution` is a warning), and an unknown word is a note, the
            //: same answer `mdCalloutHead` gives the rendered view.
            const kind = callout
              ? (typeof calloutKindOf === "function" && calloutKindOf(callout[2])) || "note"
              : null;
            const cls = kind ? `cm-md-callout cm-md-callout-${kind}` : "cm-md-quote";
            //: A plain quote's last line, `> -- Name`, is its attribution
            //: (`mdQuoteAttribution`), set apart here as it is when rendered.
            const lastLine = doc.lineAt(Math.max(node.from, node.to - 1));
            const cites =
              !kind && lastLine.from > first.from && /^\s*>\s*(?:--|\u2014|\u2013)\s*\S/.test(lastLine.text);
            for (let at = node.from; at <= node.to; ) {
              const line = doc.lineAt(at);
              let lineCls = cites && line.from === lastLine.from ? `${cls} cm-md-quote-cite` : cls;
              //: A callout's first line is its title, set as one.
              if (kind && line.from === first.from) lineCls += " cm-md-callout-head";
              ranges.push(Decoration.line({ class: lineCls }).range(line.from));
              if (line.to >= node.to) break;
              at = line.to + 1;
            }
            //: The `[!kind]` marker, on the callout's first line only, swapped
            //: for the kind's own label while the caret is elsewhere. Offsets
            //: come from the match rather than from a second search, so a body
            //: line that happens to contain `[!note]` cannot be hit.
            //: **Always, not only while the caret is elsewhere** (INBOX 486):
            //: the kind is changed from its icon, so `[!note]` and the `>`
            //: never show in the Live view; Source shows the raw text.
            if (kind) {
              calloutSpans.push([node.from, node.to]);
              const from = first.from + first.text.indexOf(callout[1]);
              const to = from + callout[1].length;
              const titled = first.text.slice(first.text.indexOf(callout[1]) + callout[1].length).trim() !== "";
              let end = to;
              //: The space after the marker goes with it, exactly as the
              //: heading and quote marks take theirs: leaving it would indent
              //: the label's line by one space against every other line.
              while (end < doc.length && doc.sliceString(end, end + 1) === " ") end += 1;
                if (!doc.sliceString(from, end).includes("\n")) {
                //: A toggle only where the marker says so, and its chevron
                //: pointing the way the view actually is rather than the way
                //: the marker asked for on open.
                const toggle = /[-+]$/.test(callout[1])
                  ? { at: first.from, closed: docCalloutFolded(state, first) }
                  : null;
                ranges.push(
                  Decoration.replace({ widget: new DocCalloutWidget(kind, toggle, first.from, titled) }).range(from, end)
                );
              }
              //: A body with nothing in it says what goes there.
              if (first.to < node.to) {
                const second = doc.lineAt(first.to + 1);
                const rest = doc.sliceString(second.from, node.to);
                if (!rest.replace(/^[ \t]*>[ \t]?/gm, "").trim() && typeof calloutHint === "function") {
                  ranges.push(
                    Decoration.widget({ widget: new DocCalloutHintWidget(calloutHint(kind)), side: 1 }).range(second.to)
                  );
                }
              }
            }
            return undefined;
          }
          if (name === "QuoteMark") {
            const line = doc.lineAt(node.from);
            const inCallout = calloutSpans.some(([from, to]) => node.from >= from && node.to <= to);
            if (!inCallout && touched(line.from, line.to)) return false;
            let end = node.to;
            while (end < doc.length && doc.sliceString(end, end + 1) === " ") end += 1;
            hide(node.from, end);
            return false;
          }
          if (name === "FencedCode") {
            //: **The two fence lines are the block's padding, not two rows of
            //: it.** Reported with a screenshot: "the md rendering on the live
            //: view ... especially for codeblocks", a fenced block drawn as a
            //: dark slab with an empty numbered row above and below the code.
            //:
            //: Measured on a four-line Python block: five rows of 26px each,
            //: two of them empty, so 52 of 130 pixels of the block said
            //: nothing. That is INBOX 198's doing and INBOX 198 was right: the
            //: backticks and the language word are syntax, and syntax is what
            //: this view hides. What it did not do was give the now-empty
            //: lines a height to match what was left on them, which is
            //: nothing.
            //:
            //: So they keep the tint, since they are part of the block, and
            //: shrink to the padding a code block would have had anyway. The
            //: language goes on the opening line as an attribute the theme
            //: draws in the corner: outside the text flow, so it takes no row,
            //: and it is the one thing the hidden `” ```python ”` was still
            //: telling you.
            const first = doc.lineAt(node.from);
            const last = doc.lineAt(node.to);
            const info = node.node.getChild("CodeInfo");
            const language = info ? doc.sliceString(info.from, info.to).trim() : "";
            //: With the caret inside the block the real `” ```python ”` is back
            //: on screen (the `CodeMark`/`CodeInfo` branch above stops hiding
            //: it), so both of the things below have to stand down with it: a
            //: half-height row would clip the text that just came back, and
            //: the corner label would be saying the language a second time
            //: right next to where it is now written out.
            const revealed = blockRevealed(node.from, node.to);
            for (let at = node.from; at <= node.to; ) {
              const line = doc.lineAt(at);
              const edge =
                line.from === first.from
                  ? "cm-md-fence-open"
                  : line.from === last.from
                  ? "cm-md-fence-close"
                  : "";
              //: The rounded corners are the block's shape and stay whatever
              //: the caret is doing; only the height and the label are tied to
              //: whether the row has text on it.
              //:
              //: **And to whether the line numbers are on** (INBOX 262). A
              //: gutter draws one element per line at that line's own height
              //: while the number inside keeps the editor's line-height, so a
              //: row collapsed to half a line leaves its digit standing 26px
              //: tall in an 8px box. Measured with the gutter on: "6 paints
              //: 18px into 7" and "8 paints 18px into 9", the pair in the
              //: report's screenshot. One row, one number, in line with the
              //: text it counts is the contract the gutter makes, so where
              //: the two disagree the gutter wins and the fence keeps its
              //: row.
              const quiet = edge && !revealed && !gutterOn ? " cm-md-fence-quiet" : "";
              ranges.push(
                Decoration.line({
                  class: `cm-md-fence${edge ? ` ${edge}` : ""}${quiet}`,
                  attributes:
                    edge === "cm-md-fence-open" && language && !revealed
                      ? { "data-lang": language }
                      : undefined,
                }).range(line.from)
              );
              if (line.to >= node.to) break;
              at = line.to + 1;
            }
            return undefined;
          }
          if (name === "HorizontalRule") {
            const line = doc.lineAt(node.from);
            //: The variant the rendered view draws (`mdDividerKind`): a
            //: hairline, the three-dot break, or the strong rule.
            const variant = mdDividerKind(line.text);
            ranges.push(
              Decoration.line({ class: `cm-md-rule${variant ? ` cm-md-rule-${variant}` : ""}` }).range(line.from)
            );
            //: **The rule's own dashes go with the rest of the markers.**
            //: Measured before this: `---` rendered as the three characters
            //: `---` on a line that also drew the border, so the divider was a
            //: line with the word for a line written on top of it. The line
            //: class is the rule; the text is the syntax that asks for one, and
            //: syntax is what this whole view hides. Hidden rather than
            //: replaced by a widget: there is nothing to say that the border
            //: does not already say.
            if (!touched(line.from, line.to)) hide(line.from, line.to);
            return false;
          }
          return undefined;
        },
      });

      //: The two constructs the markdown tree has no node for. Scanned over
      //: the visible text only, and skipped inside code for the same reason
      //: the preview's own wiki-link pass skips `<code>`: a literal `[[x]]` in
      //: a fenced snippet is a snippet, not a link.
      const text = doc.sliceString(visible.from, visible.to);
      const inCode = (pos) => {
        const at = tree.resolveInner(pos, 1);
        for (let node = at; node; node = node.parent) {
          if (node.name === "InlineCode" || node.name === "FencedCode" || node.name === "CodeText") {
            return true;
          }
        }
        return false;
      };
      const scan = (pattern, handle) => {
        pattern.lastIndex = 0;
        let match;
        while ((match = pattern.exec(text)) !== null) {
          const from = visible.from + match.index;
          if (inCode(from)) continue;
          handle(match, from, from + match[0].length);
        }
      };
      //: **The same allowlist the saved view carries** (`app.js`, the inline
      //: pattern): `==text==` is the plain yellow highlight and
      //: `==green|text==` picks one of a named set. Without the colour half
      //: here, the live view drew every highlight in one colour and left the
      //: `green|` sitting in the middle of the words as text, so the two views
      //: of the same line disagreed about both the colour and the content.
      //: The colour lands in a class name rather than an inline style, because
      //: this app's CSP rejects inline styles outright.
      scan(/==(?:(yellow|green|blue|pink|purple|orange|red|grey)\|)?([^=\n]{1,200})==/g, (match, from, to) => {
        const colour = match[1];
        ranges.push(
          Decoration.mark({
            class: colour ? `cm-md-highlight cm-md-highlight-${colour}` : "cm-md-highlight",
          }).range(from, to),
        );
        //: A highlight with a remark after it is a comment's subject, and it is
        //: drawn differently from a highlight somebody made to find their place
        //: again: the underline is what says "there is something to read about
        //: these words". The lookahead is the model's own rule (at most one
        //: space, one line) rather than a second opinion about it.
        if (/^ ?%%[^\n]*?[^%\n]%%/.test(text.slice(match.index + match[0].length))) {
          ranges.push(Decoration.mark({ class: "cm-md-commented" }).range(from, to));
        }
        if (rangeRevealed(from, to)) return;
        //: The colour prefix is syntax, so it is hidden with the marks rather
        //: than read as part of the highlighted words.
        hide(from, from + 2 + (colour ? colour.length + 1 : 0));
        hide(to - 2, to);
      });
      //: The remark itself. Revealed as its own text when the caret is on its
      //: line, which is how every marker in this view is edited.
      //: `[TOC]` on its own line, drawn as the contents while the caret is
      //: elsewhere. The entries are read from the whole document once per
      //: build, and only when the visible text has a `[TOC]` in it.
      if (/\[toc\]/i.test(text)) {
        let tocEntries = null;
        scan(/^[ \t]*\[toc\][ \t]*$/gim, (match, from, to) => {
          if (widgetRevealed(from, to)) return;
          if (!tocEntries) tocEntries = mdTocEntries(docStr(doc));
          ranges.push(Decoration.replace({ widget: new DocTocWidget(tocEntries) }).range(from, to));
        });
      }
      scan(/%%([^\n]*?)%%/g, (match, from, to) => {
        const note = match[1].trim();
        if (!note) return;
        if (widgetRevealed(from, to)) return;
        ranges.push(
          Decoration.replace({ widget: new DocCommentWidget(note, from) }).range(from, to)
        );
      });
      //: **Math.** `$$…$$` first and `$…$` second, with the ranges the first
      //: took recorded: `$$x$$` contains `$x$`, so an inline pass run on its
      //: own would draw a second widget inside the first one's range, and two
      //: replacements over one span is a decoration set that throws rather
      //: than one that looks wrong.
      //:
      //: Both are limited to a single line, and that is a property of the
      //: architecture rather than an omission: a replace decoration from a
      //: view plugin may not contain a line break (CodeMirror throws and the
      //: whole view stops updating), so a `$$` block spread over three lines
      //: stays as the text it is. Single-line `$$…$$` is what people write
      //: inside a paragraph, which is where this matters.
      const mathTaken = [];
      scan(/\$\$([^$\n]{1,400})\$\$/g, (match, from, to) => {
        if (!docMathLooksLikeMath(match[1])) return;
        mathTaken.push([from, to]);
        if (widgetRevealed(from, to)) return;
        ranges.push(
          Decoration.replace({ widget: new DocMathWidget(match[1], true) }).range(from, to)
        );
      });
      scan(/\$([^$\n]{1,300})\$/g, (match, from, to) => {
        if (mathTaken.some(([start, end]) => from >= start && to <= end)) return;
        if (!docMathLooksLikeMath(match[1])) return;
        if (widgetRevealed(from, to)) return;
        ranges.push(
          Decoration.replace({ widget: new DocMathWidget(match[1], false) }).range(from, to)
        );
      });

      //: **`:ph-name:` is the icon** (INBOX 1545), the token the icon picker
      //: inserts and the reading view and an export draw; a name the font does
      //: not have stays the text it is. Revealed as text under the caret.
      scan(/:ph-([a-z0-9-]{1,40}):/g, (match, from, to) => {
        const icon = appendPlainText.icon(match[1]);
        if (!icon || widgetRevealed(from, to)) return;
        ranges.push(Decoration.replace({ widget: new DocIconWidget(match[1]) }).range(from, to));
      });

      //: **Footnotes**, Phase 3 item 2. Two shapes of the same thing: a
      //: reference `[^1]` in the prose and its definition `[^1]: the text` at
      //: the foot of the document. Both render as the identifier alone, raised,
      //: because the brackets and the caret are syntax like every other marker
      //: in this view; the reference is a link to its definition and the
      //: definition is not a link to anything.
      //:
      //: Scanned rather than taken from the tree because the lezer markdown
      //: grammar here has no footnote extension: `[^1]` parses as ordinary
      //: text, which is also why nothing was drawing it before this.
      scan(/\[\^([^\][\s]{1,40})\](:?)/g, (match, from, to) => {
        const line = doc.lineAt(from);
        const definition = match[2] === ":" && line.from === from;
        const idFrom = from + 2;
        const idTo = to - (definition ? 2 : 1);
        if (idTo <= idFrom) return;
        ranges.push(
          Decoration.mark({
            class: definition ? "cm-md-footnote" : "cm-md-footnote cm-md-footnote-ref",
            attributes: definition
              ? {}
              : { "data-doc-footnote": match[1], title: `Go to footnote ${match[1]}` },
          }).range(idFrom, idTo)
        );
        if (rangeRevealed(from, to)) return;
        hide(from, idFrom);
        hide(idTo, to);
      });
      //: **A block id, hidden like every other marker.** `^abc123` at the end
      //: of a line is scaffolding: it is what makes the paragraph linkable and
      //: it is not what the paragraph says. It comes back when the caret is on
      //: its line, which is the rule the whole of this view follows, so a
      //: person can see, select and delete one.
      //:
      //: The pattern is the model's `DOC_BLOCK_ID_AT_END` with `gm` on it,
      //: which is why the narrow id shape matters here and not only there:
      //: a `$` after any run of characters would have hidden the end of every
      //: line ending in a caret ("2^31", "x ^ y").
      scan(/(?:^|[ \t])\^([A-Za-z0-9][A-Za-z0-9-]{0,31})[ \t]*$/gm, (match, from, to) => {
        if (rangeRevealed(from, to)) {
          ranges.push(Decoration.mark({ class: "cm-md-blockid" }).range(from, to));
          return;
        }
        hide(from, to);
      });
      scan(/\[\[([^[\]\n]{1,120})\]\]/g, (match, from, to) => {
        const spec = match[1].trim();
        //: A link is its whole text; an embed's is `name|300|center|caption`,
        //: and only the part before the first pipe names the thing.
        const name = spec;
        //: `![[name]]` is the embed form, and the `!` is one character to the
        //: left of what this pattern matched.
        const embed = from > 0 && doc.sliceString(from - 1, from) === "!";
        if (embed && !widgetRevealed(from - 1, to)) {
          ranges.push(
            Decoration.replace({ widget: new DocEmbedWidget(spec) }).range(from - 1, to)
          );
          return;
        }
        //: **The target's own heading marker is markup here too.** Reported
        //: twice: "note links have inline md not rendered or suppressed", then
        //: "document reference links still show inline md" with a screenshot of
        //: this editor drawing `# Girl with bell` inside the link chip. The
        //: button renderers were fixed by cleaning their label
        //: (`wikiLinkLabel`, app.js); here the text is the document's own
        //: content, so nothing can be rewritten, only hidden.
        //:
        //: Which is exactly what the two lines below already do to `[[` and
        //: `]]`: they are syntax rather than words, they are concealed while
        //: the caret is elsewhere, and `rangeRevealed` gives every character
        //: back the moment you edit the link. The `# ` the `[[` picker copied
        //: out of the target note's first line is the same kind of thing, and
        //: it is the only part of a link's text that is never the note's name.
        //:
        //: The mark starts after it so the chip is drawn around the words
        //: alone; `data-doc-wiki` keeps the whole spec, because that is what
        //: the resolver matches against and every link ever written is in that
        //: form.
        const marker = /^#{1,6}[ \t]*/.exec(name);
        const markerLength = marker ? marker[0].length : 0;
        //: **`[[Target|Shown]]`: only the shown words are drawn** (the bar is
        //: syntax, like the brackets; `wikiLinkTarget` says where the target
        //: ends). A board reference (`board:12|Title`) keeps its bar: it is
        //: read by `boardEmbedRef`, and its title is the chip's words already.
        //: Offsets are taken from `match[1]`, which `name` is the trimmed copy
        //: of, so leading space is counted.
        const lead = name ? match[1].length - match[1].trimStart().length : 0;
        const bar = wikiLinkTarget(name) === name ? -1 : name.indexOf("|");
        const hasAlias = bar !== -1 && name.slice(bar + 1).trim() !== "";
        const skip = hasAlias ? bar + 1 : markerLength;
        ranges.push(
          Decoration.mark({
            class: "cm-md-wiki",
            attributes: { "data-doc-wiki": name, title: `Open “${wikiLinkTarget(name) || name}”` },
          }).range(from + 2 + lead + skip, to - 2)
        );
        if (rangeRevealed(from, to)) return;
        hide(from, from + 2 + lead + skip);
        hide(to - 2, to);
      });
    }
    //: **Tables, from the model at the top of this file rather than from the
    //: syntax tree.** The tree's `Table` nodes would be enough to *find* one,
    //: and nothing like enough to edit one: the commands need each cell's own
    //: span with its padding intact, which is exactly what the model keeps and
    //: what makes the round trip through Source byte-exact. Drawing from the
    //: same parse the commands use also means what you see and what Tab moves
    //: through can never be two different opinions about where the cells are.
    //:
    //: The rendering is a CSS grid over the line: the pipes are replaced (they
    //: are syntax, like every other marker in this view), each cell is a mark,
    //: and the line's `display: grid` makes those marks the columns. The
    //: delimiter row is the header's underline and is drawn as one until the
    //: caret arrives on it, which is the rule `---` already follows.
    for (const visible of view.visibleRanges) {
      for (let pos = visible.from; pos <= visible.to && pos <= doc.length; ) {
        const line = doc.lineAt(pos);
        pos = line.to + 1;
        if (tableSeen.has(line.number)) continue;
        tableSeen.add(line.number);
        if (!docTableRowLike(line.text)) continue;
        const table = docTableParse.at(doc, line.from);
        if (!table) continue;
        for (const row of table.rows) tableSeen.add(doc.lineAt(row.from).number);
        record.selFree = false;
        const inTable = focused && sel.from <= table.to && sel.to >= table.from;
        //: **An open menu holds its own opener on screen** (INBOX 290). The
        //: menu is drawn from `focused`, and pressing the kebab can take
        //: focus out of the editor, so without this the act of opening the
        //: menu removed the button that opened it. `aria-expanded` is set by
        //: `openActionMenu` before anything it does can move focus, so it is
        //: true by the time this recomputes. The selection is still inside
        //: the table (nothing moved it), so the menu's commands still act on
        //: the row the person left the caret in.
        const menuHeld =
          !focused &&
          sel.from <= table.to &&
          sel.to >= table.from &&
          !!view.dom.querySelector('.cm-md-table-menu [aria-expanded="true"]');
        //: **The cell being edited is marked** (INBOX 392: "it is hard to
        //: edit things like tables"). With the pipes hidden, the caret was the
        //: only thing saying which cell a keystroke would land in, and a
        //: one-pixel caret in a grid of ruled cells is easy to lose: a ring
        //: round the cell says it at a glance, and follows Tab and Shift+Tab.
        //: Only while the editor has focus, like every other reveal here.
        const activeCell = inTable ? docTableCellAt(table, sel.head) : null;
        //: **The menu rides the row being edited** (INBOX 425 i). It sat at
        //: the end of the header, so in the fourth body row of a four-row
        //: table it was 158px from the caret, and past a screen of rows it was
        //: off screen altogether: the actions for "this row" were drawn on a
        //: different one. The delimiter is the header's underline, so a caret
        //: on it puts the menu on the header.
        const menuCell = docTableCellAt(table, sel.from) || { row: 0, col: 0 };
        const menuRow = menuCell.row === table.delim ? 0 : menuCell.row;
        for (let r = 0; r < table.rows.length; r += 1) {
          const row = table.rows[r];
          const rule = r === table.delim && !touched(row.from, row.to);
          if (rule) {
            ranges.push(Decoration.line({ class: "cm-md-table-rule" }).range(row.from));
            hide(row.from, row.to);
            continue;
          }
          //: The count goes on the *line* and the index on each cell: the
          //: line's own template is what makes two rows of the same table
          //: agree about where column three starts, even when one of them
          //: holds fewer cells than the header.
          const grid =
            table.columns <= DOC_TABLE_GRID_MAX
              ? ` cm-md-cols-${table.columns}`
              : " cm-md-table-wide";
          ranges.push(
            Decoration.line({
              class: (r === 0 ? "cm-md-table cm-md-table-head" : "cm-md-table") + grid,
            }).range(row.from)
          );
          const body = row.from + row.indent.length;
          hide(row.from, body);
          if (row.lead) hide(body, body + 1);
          for (let c = 0; c < row.cells.length; c += 1) {
            const span = docTableCellSpan(table, r, c);
            const align = table.aligns[c];
            const place = c < DOC_TABLE_GRID_MAX ? ` cm-md-c${c + 1}` : "";
            //: Every row's last cell keeps room for the kebab, since the kebab
            //: now follows the caret from row to row: the room is reserved on
            //: all of them so moving the caret never re-wraps a cell.
            const last = c === row.cells.length - 1 ? " cm-md-td-last" : "";
            const active =
              activeCell && activeCell.row === r && activeCell.col === c ? " cm-md-td-active" : "";
            const cls = (align ? `cm-md-td cm-md-td-${align}` : "cm-md-td") + place + last + active;
            if (span.to > span.from) {
              ranges.push(Decoration.mark({ class: cls }).range(span.from, span.to));
            } else {
              ranges.push(Decoration.widget({ widget: new DocTableCellWidget(cls) }).range(span.from));
            }
            if (c < row.cells.length - 1) hide(span.to, span.to + 1);
          }
          if (row.trail) {
            const last = docTableCellSpan(table, r, row.cells.length - 1);
            hide(last.to, row.to);
          }
          //: The menu goes at the end of the header row, where a table's own
          //: controls sit in every editor the plan names, and is drawn out of
          //: the grid's flow by its class so it cannot become a column of its
          //: own.
          if (r === menuRow && (inTable || menuHeld)) {
            const cell = menuCell;
            //: The *view's* own surface, not the document's: this plugin is
            //: mounted in every note editor too (Phase 8), and a menu that
            //: edited `doc-content` from inside a note would write into
            //: whatever document happened to be open.
            const context = { surface: asSurface(view.contentDOM) || docSurface(), text: source(), table, cell };
            ranges.push(
              Decoration.widget({
                widget: new DocTableMenuWidget(`${table.from}:${cell.row}:${cell.col}:${table.columns}`, context),
                side: 1,
              }).range(row.to)
            );
          }
        }
      }
    }

    //: **The vertical rhythm** (DOCUMENTS_PLAN 17b). Measured before this
    //: (`scratchpad/ui-sweeps/docpage17.js`): every gap between two blocks was
    //: the blank line the writer typed, so a paragraph, a heading, a table and
    //: a fence were all separated by exactly one 25.6px line of nothing, the
    //: space above a section was the same as the space under it, and two
    //: blank lines drew twice the gap the rendered view draws. The source's
    //: blank line is what separates blocks, so it is the blank line that is
    //: given the gap, from one small scale of tokens:
    //:
    //: - `cm-md-gap`: between two blocks, `--space-6`;
    //: - `cm-md-gap-major` / `-minor`: above an h1 or h2 / an h3 to h6,
    //:   `--space-9` / `--space-8`, so a section starts visibly apart from
    //:   the one before it;
    //: - `cm-md-gap-tight`: under a heading, `--space-3`, so the heading
    //:   belongs to the text it introduces rather than floating between two;
    //: - `cm-md-gap-extra`: the second and later blank lines of a run, which
    //:   the rendered view collapses to one gap and so does this.
    //:
    //: **By `line-height`, never by `height`**, and this is the reason the
    //: caret does not jump. A blank line's only content is the `<br>`, so its
    //: line height *is* its height, and the caret CodeMirror draws on it is
    //: that tall: arrowing through a gap moves nothing, and the line grows to
    //: a text line only when a character is typed into it, which is a
    //: change the writer made. The one exception is an extra blank line,
    //: which is zero tall until the caret arrives on it and then takes the
    //: plain gap, because a caret with no height is a caret nobody can find.
    //:
    //: Never inside a fenced block (a blank line in code is code) or the
    //: frontmatter (hidden above), and only in the documents editor: the note
    //: editors mount this plugin too, and a note card is not a page.
    //:
    //: **And not while the line numbers are on**, the rule the quiet fence
    //: rows already follow (INBOX 262): a gutter number keeps the editor's
    //: line height whatever its line's height is, so a 16px gap left its
    //: number standing 10px into the line below (measured by `docgutter.js`,
    //: "9 paints 10px into 10"). One row, one number, in line with the text
    //: it counts is the gutter's contract, and where the two disagree the
    //: gutter wins and the blank line keeps its full row.
    if (view.dom.closest(".doc-editor") && !gutterOn) {
      const fence = (pos) => {
        for (let node = tree.resolveInner(pos, 1); node; node = node.parent) {
          if (node.name === "FencedCode") return true;
        }
        return false;
      };
      const headingLevel = (text) => {
        const atx = /^ {0,3}(#{1,6})(?:[ \t]|$)/.exec(text);
        return atx ? atx[1].length : 0;
      };
      const blank = (n) => n >= 1 && n <= doc.lines && !doc.line(n).text.trim();
      const fmEnd =
        doc.length > 3 && doc.sliceString(0, 4) === "---\n"
          ? (docFrontmatterParse(source()) || { to: -1 }).to
          : -1;
      //: The whole rendered viewport rather than the visible ranges the
      //: other passes walk: this changes line heights, and a line drawn
      //: just below the fold at a full line's height would shrink to its gap
      //: as it scrolled into view, moving the text under the reader's eye.
      {
        const first = doc.lineAt(view.viewport.from).number;
        //: One past the viewport's last line: measured, a document ending in
        //: a newline reported a viewport ending one character short of its
        //: length, so its final empty line was drawn and never given a gap.
        const last = Math.min(doc.lines, doc.lineAt(view.viewport.to).number + 1);
        for (let n = first; n <= last; n += 1) {
          if (!blank(n)) continue;
          const line = doc.line(n);
          if (line.from <= fmEnd || fence(line.from)) continue;
          let cls = "cm-md-gap";
          if (blank(n - 1)) {
            if (!touched(line.from, line.to)) cls = "cm-md-gap cm-md-gap-extra";
          } else {
            let next = n + 1;
            while (blank(next)) next += 1;
            const below = next <= doc.lines ? headingLevel(doc.line(next).text) : 0;
            const above = n > 1 ? doc.line(n - 1).text : "";
            //: A setext heading's underline is the line above a gap under
            //: a heading just as surely as a `#` line is.
            const underHeading =
              headingLevel(above) ||
              (/^ {0,3}=+[ \t]*$/.test(above) && n > 2 && !blank(n - 2));
            if (below === 1 || below === 2) cls = "cm-md-gap cm-md-gap-major";
            else if (below) cls = "cm-md-gap cm-md-gap-minor";
            else if (underHeading) cls = "cm-md-gap cm-md-gap-tight";
          }
          ranges.push(Decoration.line({ class: cls }).range(line.from));
        }
      }
    }

    //: **Properties.** The block is hidden in Live and drawn as the panel
    //: above the editor (`renderDocProperties`), which is the only shape
    //: available: a `Decoration.replace` from a plugin may not contain a line
    //: break, and frontmatter is three lines at the very least. So each line
    //: hides on its own, the way a table's delimiter row does, and a line the
    //: caret is on comes back to full height like every other marker in this
    //: view.
    //:
    //: **Only the lines that are actually in the viewport.** A plugin may not
    //: change the height of a line outside it, which is the same rule the
    //: table loop above follows; the block is at the top of the document, so
    //: in practice this is "unless you have scrolled past it".
    if (doc.length > 3 && doc.sliceString(0, 4) === "---\n") {
      const fm = docFrontmatterParse(source());
      if (fm) {
        const lastLine = fm.closeLine + 1;
        //: Its own set, not the table loop's: that one marks every line it has
        //: looked at, which by this point is every visible line in the
        //: document, and sharing it hid nothing at all (measured: five
        //: frontmatter lines, none marked).
        const seen = new Set();
        for (const visible of view.visibleRanges) {
          if (visible.from > fm.to) continue;
          const first = doc.lineAt(Math.max(0, visible.from)).number;
          const last = doc.lineAt(Math.min(fm.to, Math.max(0, visible.to))).number;
          for (let n = Math.max(1, first); n <= Math.min(lastLine, last); n += 1) {
            if (seen.has(n)) continue;
            seen.add(n);
            const line = doc.line(n);
            if (touched(line.from, line.to)) continue;
            ranges.push(Decoration.line({ class: "cm-md-frontmatter" }).range(line.from));
            hide(line.from, line.to);
          }
        }
      }
    }

    //: Sorted by CodeMirror rather than by hand: the tree walk and the two
    //: regex passes produce ranges in three different orders, and a set built
    //: out of order throws rather than drawing something wrong, which is the
    //: right way round but is still a crash if it is left to chance.
    return Decoration.set(ranges, true);
  }

  //: **A key inside one paragraph rebuilds that paragraph** (audit 1102 DX1), with the line
  //: above and below it for the blank-line gaps, instead of every visible line: 6 ms of a
  //: key at 4x CPU in the 3,120-line document went on the visible rebuild. The rest of the
  //: set is mapped through the edit. Only where nothing outside can depend on the
  //: paragraph's words: the change has no line break, the caret starts and ends inside it,
  //: the block is a paragraph or a task under nothing but lists both before and after (a
  //: quote is out: a callout's kind is its first line), the block after it is unmoved, and
  //: the lines hold no table row, no `$$` and no frontmatter. Anything else is null, and
  //: the plugin rebuilds as before. `tests/test_doc_typing_dx1.py` compares the two.
  const PATCH_LEAF = new Set(["Paragraph", "Task"]);
  const PATCH_UNDER = new Set(["Document", "BulletList", "OrderedList", "ListItem"]);
  const patchLeaf = (tree, from, to) => {
    if (tree.length < to) return null;
    for (const side of [1, -1]) {
      for (let node = tree.resolveInner(from, side); node; node = node.parent) {
        if (PATCH_LEAF.has(node.name)) {
          if (node.from > from || node.to < to) break;
          const chain = [];
          for (let up = node.parent; up; up = up.parent) {
            if (!PATCH_UNDER.has(up.name)) return null;
            chain.push(up);
          }
          return { node, chain };
        }
      }
    }
    return null;
  };
  function patchRegion(update, visible) {
    const { startState, state, changes, view } = update;
    let fromA = Infinity, toA = -1, fromB = Infinity, toB = -1, broken = false;
    changes.iterChanges((fa, ta, fb, tb, inserted) => {
      if (inserted.lines > 1 || startState.doc.sliceString(fa, ta).includes("\n")) broken = true;
      fromA = Math.min(fromA, fa);
      toA = Math.max(toA, ta);
      fromB = Math.min(fromB, fb);
      toB = Math.max(toB, tb);
    });
    if (broken || toA < 0) return null;
    const was = patchLeaf(syntaxTree(startState), fromA, toA);
    const now = was && patchLeaf(syntaxTree(state), fromB, toB);
    if (!now || was.node.name !== now.node.name || was.chain.length !== now.chain.length) return null;
    const same = (a, b) => a.name === b.name && changes.mapPos(a.from, -1) === b.from && changes.mapPos(a.to, 1) === b.to;
    if (!same(was.node, now.node) || was.chain.some((a, i) => !same(a, now.chain[i]))) return null;
    const top = (hit) => (hit.chain.length > 1 ? hit.chain[hit.chain.length - 2] : hit.node);
    const nextA = top(was).nextSibling;
    const nextB = top(now).nextSibling;
    if (!nextA !== !nextB || (nextA && !same(nextA, nextB))) return null;
    const doc = state.doc;
    const first = Math.max(1, doc.lineAt(now.node.from).number - 1);
    const last = Math.min(doc.lines, doc.lineAt(now.node.to).number + 1);
    const region = { from: doc.line(first).from, to: doc.line(last).to };
    const old = { from: startState.doc.line(first).from, to: startState.doc.line(last).to };
    const inside = (sel, r) => sel.ranges.every((range) => range.from >= r.from && range.to <= r.to);
    if (!inside(startState.selection, old) || !inside(state.selection, region)) return null;
    for (let n = first; n <= last; n += 1) if (docTableRowLike(doc.line(n).text)) return null;
    if (doc.sliceString(region.from, region.to).includes("$$")) return null;
    if (doc.length > 3 && doc.sliceString(0, 4) === "---\n") {
      const fm = docFrontmatterParse(doc.sliceString(0, region.from));
      if (!fm || fm.to >= region.from) return null;
    }
    //: The view's lines have to be the old ones moved by the edit, or lines the patch never
    //: looks at would have come into view.
    const ranges = [...view.visibleRanges, view.viewport];
    if (ranges.length !== visible.length / 2) return null;
    for (let i = 0; i < ranges.length; i += 1) {
      if (changes.mapPos(visible[2 * i], -1) !== ranges[i].from || changes.mapPos(visible[2 * i + 1], 1) !== ranges[i].to) return null;
    }
    return { region, old };
  }
  const visibleOf = (view) => [...view.visibleRanges, view.viewport].flatMap((r) => [r.from, r.to]);

  docLivePluginCache = ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.rebuild(view);
        this.gutterOn = docFenceGutterOn();
      }
      rebuild(view) {
        this.record = { probes: [], selFree: true };
        this.decorations = build(view, this.record);
        this.visible = visibleOf(view);
      }
      //: The paragraph's decorations built again from a view that sees only its lines, laid
      //: into the old set mapped through the edit (`patchRegion` says when that is exact).
      patch(update) {
        const hit = patchRegion(update, this.visible);
        if (!hit) return false;
        const { region, old } = hit;
        const view = update.view;
        const probes = [];
        const was = this.record.probes;
        for (let i = 0; i < was.length; i += 3) {
          if (was[i] >= old.from && was[i + 1] <= old.to) continue;
          probes.push(update.changes.mapPos(was[i], -1), update.changes.mapPos(was[i + 1], 1), was[i + 2]);
        }
        if (!docLiveRevealSame(probes, update.state.selection.ranges)) return false;
        const record = { probes: [], selFree: true };
        const part = build(
          { state: update.state, hasFocus: view.hasFocus, dom: view.dom, contentDOM: view.contentDOM, visibleRanges: [region], viewport: region },
          record
        );
        const add = [];
        part.between(region.from, region.to, (from, to, value) => {
          if (from >= region.from) add.push(value.range(from, to));
        });
        this.decorations = this.decorations.map(update.changes).update({
          filter: (from) => from < region.from || from > region.to,
          filterFrom: region.from,
          filterTo: region.to,
          add,
          sort: true,
        });
        this.record = { probes: probes.concat(record.probes), selFree: this.record.selFree && record.selFree };
        this.visible = visibleOf(view);
        return true;
      }
      update(update) {
        //: Selection as well as document and viewport: the whole idea of this
        //: view is that markers appear when the caret enters what they mark,
        //: so a caret move is a repaint. Focus too, since the markers are
        //: down entirely while the editor is not focused (`focused` in
        //: `build`): without this the reveal would wait for the first caret
        //: move after a click rather than happening on the click.
        //:
        //: And the line numbers, because one decoration reads them
        //: (`cm-md-fence-quiet`, whose note in the theme says why). Toggling
        //: them reaches the engine as a compartment reconfigure, which is an
        //: update with none of the four flags above set, so without this the
        //: fence rows kept whichever shape they were built with and the
        //: collision came back the moment the numbers went on. Compared as a
        //: value rather than sniffed out of `update.transactions`: the
        //: preference is what the decoration actually depends on, and a
        //: reconfigure that does not change it should not cost a rebuild.
        //:
        //: And the parse. The markdown parser works in slices, so a viewport
        //: that moves into a long document (a jump, a dragged scrollbar, a
        //: search hit) can arrive somewhere the tree has not reached yet; the
        //: build then reads the partial tree, finds no headings, and draws
        //: plain text. The parser catching up sets none of the flags above,
        //: so the lines stayed raw until the next keystroke or scroll. Measured
        //: (`doclonglive.js`): in a 21k-word document a jump to 30% drew its
        //: heading as `### Section`, still so 2.5s later. Compared as the
        //: tree object, a pointer check, so a keystroke inside a stable tree
        //: costs nothing extra.
        const gutterOn = docFenceGutterOn();
        if (update.docChanged && !update.focusChanged && gutterOn === this.gutterOn && this.patch(update)) return;
        const other = update.docChanged || update.viewportChanged || update.focusChanged
          || gutterOn !== this.gutterOn
          || syntaxTree(update.startState) !== syntaxTree(update.state);
        if (!other && !update.selectionSet) return;
        //: **A caret move rebuilds only when it flips a reveal** (INBOX 1473
        //: b). With marks per span, most moves stay inside one span or
        //: between two, and the decorations they would rebuild are the ones
        //: already drawn; a table reads the exact caret, so it always does.
        if (!other && this.record.selFree && (!update.view.hasFocus
            || docLiveRevealSame(this.record.probes, update.state.selection.ranges))) return;
        this.gutterOn = gutterOn;
        this.rebuild(update.view);
      }
    },
    {
      decorations: (plugin) => plugin.decorations,
      eventHandlers: {
        mousedown(event, view) {
          const target = event.target;
          //: A callout's line from where its button is drawn now, not where it was built.
          const lineOf = (el, at) => (view ? view.state.doc.lineAt(view.posAtDOM(el)).from : Number(at));
          if (!(target instanceof Element)) return false;
          const wiki = target.closest("[data-doc-wiki]");
          if (wiki) {
            event.preventDefault();
            event.stopPropagation();
            //: Through the same resolution the preview's own chips use, so a
            //: name that resolves in one view resolves in the other.
            docOpenWikiTarget(wiki.dataset.docWiki);
            return true;
          }
          const kindButton = target.closest("[data-doc-callout-kind]");
          if (kindButton) {
            event.preventDefault();
            event.stopPropagation();
            const box = kindButton.getBoundingClientRect();
            docCalloutKindMenu(lineOf(kindButton, kindButton.dataset.docCalloutKind), box.left, box.bottom + 4);
            return true;
          }
          const fold = target.closest("[data-doc-callout-fold]");
          if (fold) {
            event.preventDefault();
            event.stopPropagation();
            docToggleCalloutFold(lineOf(fold, fold.dataset.docCalloutFold));
            return true;
          }
          const note = target.closest("[data-doc-footnote]");
          if (note) {
            event.preventDefault();
            event.stopPropagation();
            docGoToFootnote(note.dataset.docFootnote);
            return true;
          }
          const link = target.closest("[data-doc-href]");
          if (link && (event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            docOpenLink(link.dataset.docHref);
            return true;
          }
          return false;
        },
      },
    }
  );
  return docLivePluginCache;
}

function docCmTheme(CM) {
  const dark = document.documentElement.dataset.mode === "dark";
  return CM.view.EditorView.theme(
    {
      "&": {
        color: "var(--text)",
        backgroundColor: "transparent",
        height: "100%",
      },
      "&.cm-focused": { outline: "none" },
      ".cm-scroller": {
        fontFamily: "var(--ui-font, system-ui, -apple-system, 'Segoe UI', sans-serif)",
        lineHeight: "1.6",
        overflow: "auto",
      },
      //: The tail padding is not decoration: without it the last line of a
      //: document sits against the bottom of the pane and you write the end
      //: of a chapter at the very edge of the screen. Every editor this app
      //: is compared to scrolls past the end, for that reason.
      ".cm-content": {
        caretColor: "var(--text)",
        padding: "var(--space-4) var(--space-4) 40vh",
      },
      ".cm-line": { padding: "0" },
      ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--text)" },
      "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection": {
        backgroundColor: "var(--accent-soft)",
      },
      ".cm-gutters": {
        backgroundColor: "transparent",
        color: "var(--muted)",
        border: "none",
      },
      //: The fold lane is a line tall and centred in itself, so an arrow lines
      //: up with the number beside it and with the text it folds. Without the
      //: explicit `lineHeight` the marker inherits the gutter's own, which is
      //: not the editor's line height, and every arrow sits a little high.
      ".cm-foldGutter": { width: "1.1em" },
      ".cm-foldGutter .cm-gutterElement": {
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "0",
        lineHeight: "inherit",
        cursor: "pointer",
      },
      ".cm-fold-caret": {
        fontSize: "0.85em",
        lineHeight: "1",
        color: "var(--muted)",
      },
      ".cm-gutterElement:hover .cm-fold-caret": { color: "var(--text)" },
      //: **The numbers** (INBOX 590, the owner: "cleaner and more modern and
      //: professional"): a size under the text's, figures of one width so 9
      //: and 10 end on the same edge, right-aligned with room either side,
      //: and the line box the text's own (`1.6em` of the text is `1.6 /
      //: 0.8 = 2em` of the smaller figure). Centred in that box a figure's
      //: baseline sits about 2.4px above the text's (the size difference plus
      //: the 0.6px the gutter's rounded offset adds, `gutter.js`), so it is
      //: drawn 0.17em lower, onto the line it counts; `top` moves the glyph
      //: and not the element, so the rows below keep their places. The line
      //: the caret is on is in the body ink while the editor has the focus,
      //: and muted like the rest when it does not.
      ".cm-lineNumbers .cm-gutterElement": {
        fontSize: "0.8em",
        lineHeight: "2em",
        position: "relative",
        top: "0.17em",
        fontVariantNumeric: "tabular-nums",
        padding: "0 var(--space-4) 0 var(--space-3)",
        minWidth: "3ch",
      },
      ".cm-activeLineGutter": { backgroundColor: "transparent", color: "var(--muted)" },
      "&.cm-focused .cm-activeLineGutter": { color: "var(--text)" },
      //: **The caret's line is washed, only while the numbers show** (INBOX
      //: 651, the owner: "subtle line highlighting in the document editor
      //: when the line numbers are showing"). `highlightActiveLine()` is
      //: added with the gutter (`docCmGutter`, `noteSurfaceGutter`), so with
      //: numbers off no line carries the class at all. The wash is DESIGN.md's
      //: `--hover-veil`, a translucent ink laid over whatever ground the line
      //: has, so it reads in light and dark and never covers the selection
      //: layer's tint; it shows only while the editor has the focus, the same
      //: rule the number beside it follows. Half the veil since INBOX 684
      //: (the owner: "the active line highlighting is a little too strong"):
      //: 0.045 white in dark, 0.035 ink in light, a place marker rather than
      //: a band.
      ".cm-activeLine": { backgroundColor: "transparent" },
      "&.cm-focused .cm-activeLine": { backgroundColor: "color-mix(in srgb, var(--hover-veil) 50%, transparent)" },
      ".cm-selectionMatch": { backgroundColor: "var(--accent-soft)" },
      ".cm-searchMatch": { backgroundColor: "var(--accent-soft)" },
      ".cm-searchMatch.cm-searchMatch-selected": { outline: "1px solid var(--accent)" },
      ".cm-placeholder": { color: "var(--muted)" },
      ".cm-tooltip": {
        backgroundColor: "var(--card)",
        border: "1px solid var(--border)",
        color: "var(--text)",
      },

      //: --- a code file's diagnostics and completions (INBOX 392) ----------
      //: CodeMirror's own lint styles are fixed colours (#d11 for an error,
      //: a red SVG squiggle, a white-on-#17c selected completion), which is
      //: the same trap the highlighter fell into (`docCmHighlight`): right on
      //: a white page, wrong on this app's dark one, and deaf to a custom
      //: accent. Every one is restated here in the app's tokens.
      //:
      //: The underline is the prose findings' own shape, a wavy line in the
      //: kind's ink (`.cm-finding-spelling`), so an error in code and a
      //: misspelling in prose are one idea drawn once. The SVG CodeMirror
      //: paints as a background is switched off rather than recoloured: its
      //: colour is baked into a data URL.
      ".cm-lintRange": {
        backgroundImage: "none",
        paddingBottom: "0",
        textDecorationSkipInk: "none",
        textUnderlineOffset: "0.18em",
      },
      ".cm-lintRange-error": {
        textDecoration: "underline wavy",
        textDecorationColor: "var(--error)",
      },
      ".cm-lintRange-warning": {
        textDecoration: "underline wavy",
        textDecorationColor: "var(--warn)",
      },
      ".cm-lintRange-info, .cm-lintRange-hint": {
        textDecoration: "underline dotted",
        textDecorationThickness: "2px",
        textDecorationColor: "var(--muted)",
      },
      ".cm-lintRange-active": { backgroundColor: "var(--accent-soft)" },
      //: The gutter mark: a dot in the kind's ink, centred on its line. The
      //: library's marker is an SVG in its own colours set as `content`, so
      //: `content: normal` takes it away and the box draws the dot.
      ".cm-gutter-lint": { width: "1em" },
      ".cm-gutter-lint .cm-gutterElement": {
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "0",
      },
      ".cm-lint-marker": {
        content: "normal",
        width: "0.55em",
        height: "0.55em",
        borderRadius: "var(--radius-pill)",
        backgroundColor: "var(--muted)",
      },
      ".cm-lint-marker-error": { backgroundColor: "var(--error)" },
      ".cm-lint-marker-warning": { backgroundColor: "var(--warn)" },
      //: **The diagnostic card** (the owner, 2026-10-10: "this popup is poorly
      //: designed and spaced"). Measured before: the message and its fix on one
      //: line, 6.4px of padding above and 9.6 beside, a 3px coloured edge as the
      //: only sign of severity and the card with no ground of its own. Now a
      //: severity glyph (a Phosphor character, in the kind's ink: an error is
      //: never the colour alone), the message as the card's one line of ink, and
      //: the fix on its own row under the message, indented to the message's
      //: edge, as a button of the app's size. A second fix sits beside the
      //: first. The card is the opaque tooltip ground below, with an inset
      //: from the line it is about so it never touches it.
      ".cm-diagnostic": {
        display: "flex",
        flexWrap: "wrap",
        alignItems: "flex-start",
        columnGap: "var(--space-2)",
        rowGap: "var(--space-2)",
        maxWidth: "min(26rem, 80vw)",
        padding: "var(--space-3) var(--space-4)",
        marginLeft: "0",
        fontSize: "var(--text-sm)",
        lineHeight: "1.45",
        borderLeft: "none",
        "--diagnostic-ink": "var(--muted)",
      },
      ".cm-diagnostic::before": {
        content: '"\\e4f8"',
        fontFamily: "Phosphor",
        fontSize: "1rem",
        lineHeight: "1.3",
        width: "1rem",
        flex: "none",
        color: "var(--diagnostic-ink)",
      },
      ".cm-diagnostic-error": { "--diagnostic-ink": "var(--error)" },
      ".cm-diagnostic-warning": { "--diagnostic-ink": "var(--warn)" },
      ".cm-diagnostic-info, .cm-diagnostic-hint": { "--diagnostic-ink": "var(--accent-text)" },
      ".cm-diagnostic-error::before": { content: '"\\e4f8"' },
      ".cm-diagnostic-warning::before": { content: '"\\e4e0"' },
      ".cm-diagnostic-info::before, .cm-diagnostic-hint::before": { content: '"\\e2ce"' },
      ".cm-diagnosticText": { flex: "1 1 calc(100% - 1rem - var(--space-2))", minWidth: "0", color: "var(--text)", fontWeight: "500", overflowWrap: "anywhere" },
      ".cm-diagnosticText + .cm-diagnosticAction": { marginLeft: "calc(1rem + var(--space-2))" },
      ".cm-tooltip-lint": { padding: "0", borderRadius: "var(--radius-md)" },
      //: A quick fix on the hover card, the quiet tinted button on its own
      //: row under the message it answers (the library's own is white on a
      //: fixed dark grey), at the dense control height, with the accent edge
      //: on hover and on keyboard focus.
      ".cm-diagnosticAction": {
        font: "inherit",
        fontSize: "var(--text-sm)",
        color: "var(--text)",
        backgroundColor: "var(--accent-soft)",
        border: "1px solid transparent",
        borderRadius: "var(--radius-md)",
        padding: "0 var(--space-3)",
        margin: "0",
        minHeight: "var(--control-h-dense)",
        cursor: "pointer",
      },
      ".cm-diagnosticAction:hover, .cm-diagnosticAction:focus-visible": {
        borderColor: "var(--accent)",
        outline: "none",
      },
      //: **Opaque, where the tooltip above is glass.** `--card` is 55%
      //: opaque (measured through `doccode.js`), which is right for a panel
      //: over the page's own ground and wrong for a box of words laid over
      //: other words: the code under a diagnostic read through its message.
      //: The ground the selection bar uses for the same reason
      //: (DESIGN.md's recipe index, "a bar of actions").
      ".cm-tooltip.cm-tooltip-hover, .cm-tooltip.cm-tooltip-autocomplete": {
        backgroundColor: "var(--modal-bg-opaque)",
      },
      ".cm-tooltip.cm-tooltip-hover": {
        borderRadius: "var(--radius-md)",
        boxShadow: "var(--shadow-md)",
        overflow: "hidden",
      },
      //: A gap between the card and the line it is about (measured 1px before):
      //: the library sets only the card's top and left, so the gap is a shift
      //: away from the line, whichever side it chose.
      ".cm-tooltip.cm-tooltip-hover.cm-tooltip-above": { transform: "translateY(calc(-1 * var(--space-1)))" },
      ".cm-tooltip.cm-tooltip-hover.cm-tooltip-below": { transform: "translateY(var(--space-1))" },
      ".cm-tooltip.cm-tooltip-autocomplete": {
        borderRadius: "var(--radius-sm, 6px)",
        boxShadow: "var(--shadow-md)",
        overflow: "hidden",
      },
      ".cm-tooltip.cm-tooltip-autocomplete > ul": {
        fontFamily: "var(--mono, ui-monospace, monospace)",
        fontSize: "var(--text-sm)",
        maxHeight: "16em",
      },
      ".cm-tooltip.cm-tooltip-autocomplete > ul > li": {
        padding: "var(--space-1) var(--space-4)",
        lineHeight: "1.5",
      },
      ".cm-tooltip-autocomplete ul li[aria-selected]": {
        backgroundColor: "var(--accent-soft)",
        color: "var(--text)",
      },
      ".cm-completionMatchedText": {
        textDecoration: "none",
        fontWeight: "700",
        color: "var(--accent-text)",
      },
      ".cm-completionDetail": { color: "var(--muted)", fontStyle: "normal" },
      ".cm-completionIcon": { color: "var(--muted)", opacity: "1" },
      //: The detail pane beside the list (an Emmet row's expansion): the
      //: list's own opaque ground and code type, because it is code laid
      //: over code.
      ".cm-tooltip.cm-completionInfo": {
        backgroundColor: "var(--modal-bg-opaque)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-sm, 6px)",
        boxShadow: "var(--shadow-md)",
        padding: "var(--space-2) var(--space-3)",
        maxWidth: "min(480px, 60vw)",
      },
      ".cm-emmet-preview": {
        margin: "0",
        fontFamily: "var(--mono, ui-monospace, monospace)",
        fontSize: "var(--text-sm)",
        lineHeight: "1.5",
        color: "var(--text)",
        whiteSpace: "pre",
        tabSize: "2",
      },
      //: The ghost text: the rest of the chosen row after the caret, in the
      //: muted ink the placeholder uses, so it reads as offered, not typed.
      ".cm-ghostText": { color: "var(--muted)", opacity: "0.85", pointerEvents: "none" },
      //: Run's output, under the editor: a head row of the dock's own
      //: small ghost buttons, then the page (an HTML file) above the log.
      //: The log is code type, a hairline between rows, errors and
      //: warnings in their own inks on their soft grounds.
      ".cm-run-panel": {
        display: "flex",
        flexDirection: "column",
        height: "min(40vh, 320px)",
        borderTop: "1px solid var(--border)",
        backgroundColor: "var(--modal-bg-opaque)",
      },
      ".cm-run-head": {
        display: "flex",
        alignItems: "center",
        gap: "var(--space-2)",
        padding: "var(--space-1) var(--space-2)",
        borderBottom: "1px solid var(--border)",
      },
      ".cm-run-title": { fontWeight: "600", color: "var(--text)" },
      //: The status gives way first when the head is tight (Brief 70: a
      //: Python run's head with Input shown ran 60px past at 1440).
      ".cm-run-status": { color: "var(--muted)", fontSize: "var(--text-sm)", minWidth: "0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
      ".cm-run-spacer": { flex: "1" },
      ".cm-run-body": { flex: "1", minHeight: "0", display: "flex", flexDirection: "column" },
      ".cm-run-frame": { display: "none", border: "0", width: "100%", flex: "3", minHeight: "0" },
      ".cm-run-panel.is-page .cm-run-frame": { display: "block", borderBottom: "1px solid var(--border)" },
      //: A page with nothing printed gives the frame the whole body, not 60
      //: percent of it and a line saying nothing ran (1031 CE7: 166 px).
      ".cm-run-panel.is-page .cm-run-log:empty": { display: "none" },
      ".cm-run-log": {
        flex: "2",
        minHeight: "0",
        overflow: "auto",
        margin: "0",
        padding: "0",
        listStyle: "none",
        fontFamily: "var(--mono, ui-monospace, monospace)",
        fontSize: "var(--text-sm)",
      },
      ".cm-run-row": {
        display: "flex",
        alignItems: "baseline",
        gap: "var(--space-2)",
        padding: "var(--space-1) var(--space-3)",
        borderBottom: "1px solid var(--border)",
        color: "var(--text)",
      },
      ".cm-run-row.is-error": { color: "var(--error)", backgroundColor: "var(--error-soft)" },
      ".cm-run-row.is-warn": { color: "var(--warn)", backgroundColor: "var(--warn-soft)" },
      ".cm-run-row.is-info, .cm-run-row.is-debug": { color: "var(--muted)" },
      ".cm-run-text": { flex: "1", whiteSpace: "pre-wrap", overflowWrap: "anywhere" },
      ".cm-run-line": { color: "var(--muted)", fontSize: "var(--text-xs)", whiteSpace: "nowrap" },
      //: A SQL statement's result (Brief 69, D5): the count on the row's
      //: first line, the table under it at the row's full width, scrolling
      //: sideways inside the row rather than widening the panel.
      ".cm-run-row.is-table": { flexWrap: "wrap" },
      ".cm-run-table-wrap": { flexBasis: "100%", minWidth: "0", overflowX: "auto" },
      ".cm-run-table": { borderCollapse: "collapse", fontSize: "var(--text-xs)" },
      ".cm-run-table th, .cm-run-table td": {
        border: "1px solid var(--border)",
        padding: "var(--space-1) var(--space-2)",
        textAlign: "left",
        whiteSpace: "nowrap",
      },
      ".cm-run-table th": { fontWeight: "600", backgroundColor: "var(--surface-2)" },
      ".cm-run-table td.is-null": { color: "var(--muted)", fontStyle: "italic" },
      ".cm-run-more": { margin: "var(--space-1) 0 0", color: "var(--muted)" },
      //: A test (D7): its state's icon, its name, its time, its line; a
      //: failure's message under it in the row's own ink.
      ".cm-run-test": { flexWrap: "wrap" },
      ".cm-run-test.is-pass > .ph": { color: "var(--ok)" },
      ".cm-run-test .cm-run-text": { flex: "1" },
      ".cm-run-ms": { color: "var(--muted)", fontSize: "var(--text-xs)", whiteSpace: "nowrap" },
      ".cm-run-why": { flexBasis: "100%", margin: "var(--space-1) 0 0", whiteSpace: "pre-wrap", font: "inherit", overflowWrap: "anywhere" },
      ".cm-run-summary": { fontWeight: "600" },
      //: Input (D9): the lines Python's input() reads, a field under the head.
      ".cm-run-stdin-wrap": {
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-1)",
        padding: "var(--space-1) var(--space-2)",
        borderBottom: "1px solid var(--border)",
      },
      ".cm-run-stdin-label": { color: "var(--muted)", fontSize: "var(--text-sm)" },
      ".cm-run-stdin": { fontFamily: "var(--mono, ui-monospace, monospace)", fontSize: "var(--text-sm)", resize: "vertical", minHeight: "0" },
      //: input() asked mid-run (Brief 70): the prompt, then the field the
      //: answer is typed in, on the row the answer will take.
      ".cm-run-ask": { flex: "1", display: "flex", alignItems: "baseline", gap: "var(--space-2)", minWidth: "0" },
      ".cm-run-ask .cm-run-text": { flex: "none" },
      ".cm-run-ask-field": { flex: "1", minWidth: "0", fontFamily: "inherit", fontSize: "inherit" },
      //: Run on a .py file before the Pyodide extra is installed: the row's
      //: one action, kept whole beside the sentence it answers.
      ".cm-run-install": { flex: "none", whiteSpace: "nowrap" },
      //: The Debug tab: the five actions and where it stopped, the exception
      //: if that is why, then Variables, Watch, Call stack and Breakpoints as
      //: columns that fold to a stack on a narrow panel.
      //: The Debug tab is one of the panel's panes (Brief 71): shown and hidden
      //: by `.hidden`, like the others.
      ".cm-debug": { display: "flex", flex: "1", minHeight: "0", overflow: "auto", flexDirection: "column" },
      ".cm-debug-bar": {
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        gap: "var(--space-1)",
        padding: "var(--space-1) var(--space-2)",
        borderBottom: "1px solid var(--border)",
      },
      ".cm-debug-where": { color: "var(--muted)", fontSize: "var(--text-sm)", marginInlineStart: "var(--space-2)" },
      ".cm-debug-thrown": {
        margin: "0",
        padding: "var(--space-1) var(--space-3)",
        maxHeight: "8rem",
        overflow: "auto",
        whiteSpace: "pre-wrap",
        overflowWrap: "anywhere",
        fontFamily: "var(--mono, ui-monospace, monospace)",
        fontSize: "var(--text-xs)",
        color: "var(--error)",
        backgroundColor: "var(--error-soft)",
        borderBottom: "1px solid var(--border)",
      },
      ".cm-debug-grid": { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(13rem, 1fr))" },
      ".cm-debug-section": {
        minWidth: "0",
        padding: "var(--space-1) var(--space-2)",
        borderInlineEnd: "1px solid var(--border)",
        borderBottom: "1px solid var(--border)",
      },
      ".cm-debug-title": { margin: "0 0 var(--space-1)", fontSize: "var(--text-sm)", fontWeight: "600", color: "var(--text)" },
      ".cm-debug-list": { listStyle: "none", margin: "0", padding: "0", fontSize: "var(--text-sm)" },
      ".cm-debug-row": { display: "flex", alignItems: "baseline", gap: "var(--space-2)", minWidth: "0" },
      ".cm-debug-name, .cm-debug-value": { fontFamily: "var(--mono, ui-monospace, monospace)" },
      ".cm-debug-name": { flex: "none", maxWidth: "45%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--accent-text)" },
      ".cm-debug-value": { flex: "1", minWidth: "0", whiteSpace: "pre-wrap", overflowWrap: "anywhere", color: "var(--text)" },
      ".cm-debug-row.is-error .cm-debug-value": { color: "var(--error)" },
      ".cm-debug-row.has-children": { display: "block" },
      ".cm-debug-tree > summary": { display: "flex", alignItems: "baseline", gap: "var(--space-2)", minWidth: "0", cursor: "pointer", listStyle: "none" },
      ".cm-debug-tree > summary::-webkit-details-marker": { display: "none" },
      ".cm-debug-tree > summary::before": { content: '"\\25B8"', flex: "none", color: "var(--muted)" },
      ".cm-debug-tree[open] > summary::before": { content: '"\\25BE"' },
      ".cm-debug-children": { paddingInlineStart: "var(--space-3)", borderInlineStart: "1px solid var(--border)", marginInlineStart: "var(--space-1)" },
      ".cm-debug-sub": { marginTop: "var(--space-1)", color: "var(--muted)", fontSize: "var(--text-xs)" },
      ".cm-debug-empty": { color: "var(--muted)" },
      ".cm-debug-go": { minWidth: "0", textAlign: "start", fontFamily: "var(--mono, ui-monospace, monospace)" },
      ".cm-debug-remove": { marginInlineStart: "auto", flex: "none" },
      ".cm-debug-watch-add": { width: "100%", minHeight: "var(--target-min)", marginTop: "var(--space-1)", fontFamily: "var(--mono, ui-monospace, monospace)", fontSize: "var(--text-sm)" },
      //: The breakpoint lane, left of the numbers, as VS Code's: a dot, red,
      //: amber with a condition; a faint one under the pointer says a click
      //: puts one there. The stopped line is lit across the text.
      ".cm-debug-gutter .cm-gutterElement": { display: "flex", alignItems: "center", justifyContent: "center", width: "0.875rem", cursor: "pointer" },
      ".cm-debug-bp": { display: "inline-block", width: "0.625rem", height: "0.625rem", borderRadius: "50%", backgroundColor: "var(--error)" },
      ".cm-debug-bp.is-cond": { backgroundColor: "var(--warn)" },
      ".cm-debug-gutter .cm-gutterElement:hover:not(:has(.cm-debug-bp))::before": {
        content: '""',
        width: "0.625rem",
        height: "0.625rem",
        borderRadius: "50%",
        backgroundColor: "var(--error)",
        opacity: "0.35",
      },
      ".cm-debug-here": { backgroundColor: "var(--warn-soft)" },
      //: Sticky scroll: the enclosing scopes' first lines over the top of the
      //: scroller, on the opaque ground words laid over words take, with the
      //: hairline and small shadow of a bar that sits above content.
      ".cm-sticky": {
        position: "absolute",
        zIndex: "3",
        backgroundColor: "var(--modal-bg-opaque)",
        borderBottom: "1px solid var(--border)",
        boxShadow: "var(--shadow-sm)",
      },
      ".cm-sticky.hidden": { display: "none" },
      ".cm-sticky-line": {
        paddingLeft: "var(--sticky-pad, 0px)",
        whiteSpace: "pre",
        overflow: "hidden",
        textOverflow: "ellipsis",
        cursor: "pointer",
      },
      ".cm-sticky-line:hover": { backgroundColor: "var(--accent-soft)" },
      //: Shown whitespace (Alt+Z's neighbour in the menu): a dot per space and
      //: a line through a tab, in muted ink rather than the library's grey.
      ".cm-highlightSpace": {
        backgroundImage: "radial-gradient(circle at 50% 55%, var(--muted) 14%, transparent 16%)",
      },
      ".cm-highlightTab": {
        backgroundImage: "linear-gradient(var(--muted), var(--muted))",
        backgroundSize: "70% 1px",
        backgroundPosition: "50% 55%",
        backgroundRepeat: "no-repeat",
      },
      //: Indentation guides: a hairline in `--border` at the left edge of
      //: each step of the whitespace, so it stops where the code starts.
      ".cm-indent-guide": {
        backgroundImage: "linear-gradient(to right, var(--border) 0 1px, transparent 1px)",
        backgroundRepeat: "no-repeat",
      },
      //: Every step drawn 2em wide, whatever its number of spaces
      //: (`docIndentGuides`, which measures `--doc-space-w`).
      ".cm-indent-w1": { letterSpacing: "calc(2em / 1 - var(--doc-space-w, 0.25em))" },
      ".cm-indent-w2": { letterSpacing: "calc(2em / 2 - var(--doc-space-w, 0.25em))" },
      ".cm-indent-w3": { letterSpacing: "calc(2em / 3 - var(--doc-space-w, 0.25em))" },
      ".cm-indent-w4": { letterSpacing: "calc(2em / 4 - var(--doc-space-w, 0.25em))" },
      ".cm-indent-w5": { letterSpacing: "calc(2em / 5 - var(--doc-space-w, 0.25em))" },
      ".cm-indent-w6": { letterSpacing: "calc(2em / 6 - var(--doc-space-w, 0.25em))" },
      ".cm-indent-w7": { letterSpacing: "calc(2em / 7 - var(--doc-space-w, 0.25em))" },
      ".cm-indent-w8": { letterSpacing: "calc(2em / 8 - var(--doc-space-w, 0.25em))" },
      //: Bracket pairs by depth: three of the app's own inks, each mixed a
      //: third of the way back to the text, so the pairs are told apart
      //: without the brackets shouting over the code between them.
      ".cm-bracket-0": { color: "color-mix(in srgb, var(--accent-text) 70%, var(--text))" },
      ".cm-bracket-1": { color: "color-mix(in srgb, var(--syntax-keyword, var(--ok)) 70%, var(--text))" },
      ".cm-bracket-2": { color: "color-mix(in srgb, var(--warn) 70%, var(--text))" },
      //: A name's one line on hover: the name in code type, the line in the
      //: body's, the values it takes in muted ink under it.
      ".cm-hover-doc": {
        padding: "var(--space-2) var(--space-3)",
        maxWidth: "min(420px, 70vw)",
        fontSize: "var(--text-sm)",
        lineHeight: "1.5",
      },
      ".cm-hover-doc code": { fontFamily: "var(--mono, ui-monospace, monospace)", fontWeight: "600", color: "var(--text)" },
      ".cm-hover-doc-line": { color: "var(--text)", marginTop: "var(--space-1)" },
      ".cm-hover-doc-values": { color: "var(--muted)", marginTop: "var(--space-1)" },
      //: A colour value's swatch: the colour on a hairline in the border
      //: token, square with the inner radius, one text-height small, so it
      //: reads as a mark beside the value and not as a control of its own.
      ".cm-color-swatch": {
        display: "inline-block",
        width: "0.8em",
        height: "0.8em",
        marginRight: "var(--space-1)",
        verticalAlign: "-0.05em",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-inner)",
        cursor: "pointer",
      },

      //: --- Live preview -------------------------------------------------
      //: The rendered shapes, in the app's own type scale rather than in a
      //: second one. A heading in the editor and the same heading in the
      //: rendered preview beside it are the thing a split view is *for*, so
      //: the two have to agree.
      ".cm-md-h1": { fontSize: "1.8em", fontWeight: "700", lineHeight: "1.25" },
      ".cm-md-h2": { fontSize: "1.5em", fontWeight: "700", lineHeight: "1.3" },
      ".cm-md-h3": { fontSize: "1.25em", fontWeight: "650", lineHeight: "1.35" },
      ".cm-md-h4": { fontSize: "1.1em", fontWeight: "650" },
      ".cm-md-h5": { fontSize: "1em", fontWeight: "650" },
      ".cm-md-h6": { fontSize: "1em", fontWeight: "650", color: "var(--muted)" },
      ".cm-md-strong": { fontWeight: "700" },
      ".cm-md-em": { fontStyle: "italic" },
      ".cm-md-strike": { textDecoration: "line-through", opacity: "0.65" },
      //: **The three tinted inlines wrap as whole chips, not as a chip cut in
      //: half.** Reported (INBOX 232): "link chips wrap oddly". `box-
      //: decoration-break` defaults to `slice`, which lays the background,
      //: the rounded corners and the horizontal padding out once across the
      //: whole run and then cuts it at the line break: the fragment that ends
      //: a line has a flat right edge and no padding after its last letter,
      //: and the fragment that starts the next one is flush against the
      //: column's left margin with no padding and no rounding. Measured at
      //: 390px on a document of wiki links: three of nine chips broke that
      //: way, the second fragment starting at x=10, the column's own edge.
      //:
      //: `clone` gives every fragment the whole decoration, so a wrapped chip
      //: reads as two chips rather than as one broken one. The `-webkit-`
      //: spelling is the one Chromium still implements, so both are set and
      //: the standard name is second, to win where it is supported.
      //:
      //: All three, not just the wiki link: inline code and a highlight are
      //: the same shape (a tint with a radius and side padding) and break the
      //: same way, which is why a fix for one of them is a fix for the class.
      ".cm-md-code, .cm-md-highlight, .cm-md-wiki": {
        WebkitBoxDecorationBreak: "clone",
        boxDecorationBreak: "clone",
      },
      ".cm-md-code": {
        fontFamily: "var(--mono, ui-monospace, monospace)",
        backgroundColor: "var(--field-inset)",
        borderRadius: "3px",
        padding: "0 0.25em",
      },
      //: Yellow is the default, the same as the saved view's
      //: `mark.text-highlight-yellow`. It read `--accent-soft` here, which is
      //: the *blue* of that set, so every plain highlight in the live view came
      //: out blue and only a highlight somebody had explicitly called blue
      //: looked right. One rule per colour in the allowlist above, taking the
      //: same tokens as 05-sidebars-themes.css so the two views match in both
      //: themes.
      ".cm-md-highlight": { backgroundColor: "var(--warn-soft)", borderRadius: "3px" },
      ".cm-md-highlight-yellow": { backgroundColor: "var(--warn-soft)" },
      ".cm-md-highlight-green": { backgroundColor: "var(--ok-soft)" },
      ".cm-md-highlight-blue": { backgroundColor: "var(--accent-soft)" },
      ".cm-md-highlight-pink": { backgroundColor: "rgba(236, 72, 153, 0.22)" },
      ".cm-md-highlight-purple": { backgroundColor: "rgba(168, 85, 247, 0.22)" },
      ".cm-md-highlight-orange": { backgroundColor: "rgba(249, 115, 22, 0.22)" },
      ".cm-md-highlight-red": { backgroundColor: "rgba(239, 68, 68, 0.22)" },
      ".cm-md-highlight-grey": { backgroundColor: "rgba(148, 163, 184, 0.25)" },
      //: **A commented span, told apart from a plain highlight** (Phase 5 item
      //: 1). A hairline under the words rather than a fourth underline *shape*:
      //: the three the findings own (wavy in the error ink, wavy in the accent,
      //: dotted in the muted) are all `text-decoration`, and a fourth one would
      //: be a fourth thing for a reader to decode in the same channel. A border
      //: is a different channel, and it reads correctly against the highlight's
      //: own ground, which is doing half the work already.
      ".cm-md-commented": { borderBottom: "1px solid var(--accent)" },
      //: **The remark itself, as a pin rather than as purple text.** A comment
      //: has to be visible in the document without being read in it, which is
      //: the whole difference between a margin note and the prose, so the
      //: `%%…%%` hides like every other marker and this takes its place. Sized
      //: in `em` and aligned on the text's own middle so a line with a pin in it
      //: is the same height as a line without one: measured, 24px either way.
      //: Every longhand a bare `button` would otherwise bring (the accent fill,
      //: the shadow, the 0.5rem of padding) is turned off here rather than in
      //: the stylesheet, because this element exists only inside the view and a
      //: widget split across two files is a widget that drifts.
      ".doc-comment-pin": {
        display: "inline-flex",
        verticalAlign: "middle",
        margin: "0 0.15em",
        padding: "0 0.25em",
        border: "0",
        borderRadius: "var(--radius-pill)",
        background: "var(--accent-soft)",
        boxShadow: "none",
        color: "var(--accent-text)",
        fontSize: "0.8em",
        lineHeight: "1.6",
        cursor: "pointer",
      },
      ".doc-comment-pin:hover": { background: "var(--accent)", color: "var(--on-accent)" },
      ".cm-md-link": { color: "var(--accent-text)", textDecoration: "underline", cursor: "pointer" },
      ".cm-md-wiki": {
        color: "var(--accent-text)",
        backgroundColor: "var(--accent-soft)",
        borderRadius: "4px",
        padding: "0 0.25em",
        cursor: "pointer",
      },
      //: A block id when the caret is on its line. Muted and monospaced, so it
      //: reads as scaffolding the moment it appears rather than as a word
      //: somebody typed at the end of the sentence.
      ".cm-md-blockid": {
        color: "var(--muted)",
        fontFamily: "var(--mono, ui-monospace, monospace)",
        fontSize: "0.85em",
      },
      //: **A list item's hanging indent.** `padding-left` moves the whole
      //: line in and a matching negative `text-indent` pulls the first line
      //: back out again, so the marker sits in the margin and the words line
      //: up under each other however many times the item wraps. One rule per
      //: depth rather than a CSS variable, because a CodeMirror theme is a
      //: static stylesheet and there is nowhere to set a per-line variable
      //: without an inline style, which the app's CSP refuses.
      //:
      //: `1.6em` is the width of a marker and its space at this type size,
      //: measured rather than chosen: a `-` plus a space is 2 characters of a
      //: 0.8em-per-character face.
      ".cm-md-li": { paddingLeft: "1.6em", textIndent: "-1.6em" },
      ".cm-md-li-1": { paddingLeft: "3.2em", textIndent: "-1.6em", ...docListGuides(1) },
      ".cm-md-li-2": { paddingLeft: "4.8em", textIndent: "-1.6em", ...docListGuides(2) },
      ".cm-md-li-3": { paddingLeft: "6.4em", textIndent: "-1.6em", ...docListGuides(3) },
      ".cm-md-li-4": { paddingLeft: "8em", textIndent: "-1.6em", ...docListGuides(4) },
      ".cm-md-task-done": {
        color: "var(--muted)",
        textDecoration: "line-through",
        textDecorationColor: "color-mix(in srgb, var(--muted) 70%, transparent)",
      },
      //: The marker itself: the muted ink, so the eye reads the words rather
      //: than the punctuation, and left in the document so it can be
      //: selected, deleted and typed over like any other character.
      ".cm-md-li-mark": { color: "var(--muted)" },
      //: `textIndent: 0`: an inline-block is a block container, so it inherits
      //: the line's hanging `-1.6em` and drew its own glyph 24px left of its
      //: box (bullet 44px from the words, half outside the page at 720).
      ".cm-md-li-bullet": { display: "inline-block", width: "1.6em", textIndent: "0" },
      ".cm-md-li-num": { display: "inline-block", minWidth: "1.6em", textIndent: "0" },
      //: **A quotation's bar has to be seen to do its job** (17c). It was
      //: `--border`, a 10% ink that composites to 1.2:1 on the page, so a
      //: quotation read as a paragraph set in grey. Half the muted ink is a
      //: rule you can see without it competing with the callout's accent
      //: bar, and the rendered view's `#doc-preview blockquote` (09-editor.css)
      //: now draws the same bar, inset and ink, where before it drew the
      //: browser's own 40px indent and nothing else.
      ".cm-md-quote": {
        borderLeft: "3px solid color-mix(in srgb, var(--muted) 70%, transparent)",
        paddingLeft: "var(--space-5)",
        color: "var(--muted)",
      },
      //: The kind's own ink (`--callout-accent`, set per kind in
      //: 05-sidebars-themes.css for this class and the rendered `.callout`
      //: alike), so a warning is amber in the Live view as it is in Read.
      ".cm-md-callout": {
        borderLeft: "3px solid var(--callout-accent)",
        paddingLeft: "0.75em",
        backgroundColor: "color-mix(in srgb, var(--callout-accent) 8%, transparent)",
      },
      ".cm-md-callout-toggle": {
        borderLeftColor: "var(--border)",
        backgroundColor: "transparent",
      },
      //: A quote's attribution line, set small and muted like the rendered
      //: figure's caption.
      ".cm-md-quote-cite": { fontSize: "0.88em", fontStyle: "normal" },
      ".cm-md-rule-thick": {
        backgroundImage: "linear-gradient(color-mix(in srgb, var(--muted) 55%, transparent), color-mix(in srgb, var(--muted) 55%, transparent))",
        backgroundSize: "100% 3px",
      },
      ".cm-md-rule-dots": { backgroundImage: "none", textAlign: "center" },
      ".cm-md-rule-dots::after": {
        content: "'\\2022\\2003\\2022\\2003\\2022'",
        color: "var(--muted)",
        fontSize: "0.85em",
      },
      //: The inset is the rendered `pre`'s own (`--space-5`): without it the
      //: code's first glyph sat on the very edge of its tinted slab, 0px in,
      //: which is how a block reads as a highlighted paragraph rather than
      //: as a panel of code (17c).
      ".cm-md-fence": {
        fontFamily: "var(--mono, ui-monospace, monospace)",
        backgroundColor: "var(--field-inset)",
        paddingInline: "var(--space-5)",
      },
      //: The opening and closing fence rows. Their text is hidden (INBOX
      //: 198), so a full line-height row of it is 26px of nothing at each end
      //: of every code block; these give them the height of padding instead,
      //: and round the block's own corners so five tinted rows read as one
      //: slab. `position: relative` is the anchor for the language label
      //: below.
      ".cm-md-fence-open, .cm-md-fence-close": {
        position: "relative",
      },
      //: Only while the row has nothing on it. With the caret inside the
      //: block its `” ``` ”` is back, and half a line of height would clip it.
      //:
      //: **And only while the line numbers are off** (INBOX 262: "the page
      //: numbers and collapse arrows in the documents clash with other page
      //: numnbers"). A gutter draws one element per line at that line's own
      //: height, but the number inside it keeps the editor's line-height, so
      //: a row collapsed to half a line leaves its digit standing 26px tall
      //: in an 8px box. Measured on a fenced block with the gutter on: "6
      //: paints 18px into 7" and "8 paints 18px into 9", which is the pair in
      //: the report's screenshot exactly.
      //:
      //: Numbers win, because they are the contract: one row, one number, in
      //: line with the text it counts. The tidy block is what prose gets, and
      //: prose is where the gutter is off by default (`docGutterWanted`),
      //: which is also where a fenced block wearing two blank rows was worth
      //: fixing in the first place.
      //:
      //: The decision is made where the class is set, not here: a CodeMirror
      //: theme's rules are injected into a stylesheet this page cannot read
      //: back, and a `:has(.cm-gutters)` guard written here could not be
      //: verified in the browser, only hoped for. `docGutterWanted` already
      //: knows the answer at decoration time.
      ".cm-md-fence-quiet": {
        height: "0.5em",
      },
      ".cm-md-fence-open": {
        borderTopLeftRadius: "var(--radius-sm, 6px)",
        borderTopRightRadius: "var(--radius-sm, 6px)",
      },
      ".cm-md-fence-close": {
        borderBottomLeftRadius: "var(--radius-sm, 6px)",
        borderBottomRightRadius: "var(--radius-sm, 6px)",
      },
      //: The block's language, in the corner rather than on a line of its
      //: own: it is a label for the block, the same relationship
      //: `.cm-md-callout-label` has to a callout, and the whole point of this
      //: change is that the block stops spending rows on things that are not
      //: code. `user-select: none` and `pointer-events: none` so a drag
      //: across the block selects the code and not the word "python".
      ".cm-md-fence-open[data-lang]::after": {
        content: "attr(data-lang)",
        position: "absolute",
        right: "0.6em",
        top: "0",
        fontSize: "0.7em",
        lineHeight: "1.6",
        color: "var(--muted)",
        userSelect: "none",
        pointerEvents: "none",
      },
      //: A rule whose own `---` is hidden is an empty line, and an empty line
      //: with a bottom border is a hairline sitting on the baseline of nothing.
      //: The height is what makes it read as a divider between two blocks
      //: rather than as an underline belonging to the paragraph above.
      //: **A full line tall, the rule drawn in its middle** (INBOX 1300 C44).
      //: It was a 0.6em box with a bottom border and 0.4em of margin, so the
      //: line-number gutter, which gives each number the line's own height,
      //: had an 8.8px element holding a 14px figure: numbers 1 and 2 overlapped
      //: (4 overlaps in 8 lines measured, `scratchpad/ui-sweeps/c44.js`). The
      //: gutter follows the line's height, so the line is given a line's height.
      ".cm-md-rule": {
        backgroundImage: "linear-gradient(var(--border), var(--border))",
        backgroundSize: "100% 1px",
        backgroundPosition: "center",
        backgroundRepeat: "no-repeat",
      },
      //: The gaps between blocks (17b), one token each; the note beside the
      //: decoration in `docLivePlugin` says why this is `line-height` and not
      //: `height`.
      ".cm-md-gap": { lineHeight: "var(--space-6)" },
      ".cm-md-gap-major": { lineHeight: "var(--space-9)" },
      ".cm-md-gap-minor": { lineHeight: "var(--space-8)" },
      ".cm-md-gap-tight": { lineHeight: "var(--space-3)" },
      ".cm-md-gap-extra": { lineHeight: "0" },
      //: The callout's kind, in the place its `[!note]` marker was. Set in
      //: `em` so it tracks the editor's own type scale, and in the muted ink
      //: because it labels the block rather than being part of what it says.
      ".cm-md-callout-label": {
        display: "inline-flex",
        alignItems: "center",
        gap: "0.35em",
        fontSize: "0.85em",
        fontWeight: "600",
        color: "var(--ink)",
        marginRight: "0.4em",
        userSelect: "none",
        verticalAlign: "baseline",
      },
      //: The kind's badge, the rendered head's `.callout-icon` at the Live
      //: view's type size, and the one control on the chip that is a button:
      //: it opens the kinds menu.
      ".cm-md-callout-kindbtn": {
        display: "inline-grid",
        placeItems: "center",
        width: "1.5em",
        height: "1.5em",
        borderRadius: "var(--radius-sm)",
        backgroundColor: "color-mix(in srgb, var(--callout-accent) 18%, transparent)",
        color: "var(--callout-accent)",
        cursor: "pointer",
      },
      ".cm-md-callout-kindbtn:hover": {
        backgroundColor: "color-mix(in srgb, var(--callout-accent) 30%, transparent)",
      },
      //: The kind button is a tile with a caret, so it reads as a menu.
      ".cm-md-callout-kindbtn:has(.cm-md-callout-caret)": {
        display: "inline-flex",
        gap: "0.1em",
        width: "auto",
        padding: "0 0.3em",
      },
      ".cm-md-callout-caret": { fontSize: "0.7em", opacity: "0.75" },
      //: No title: the kind's name stands in for one, a step back.
      ".cm-md-callout-label .cm-md-callout-word": { color: "var(--muted)", fontWeight: "500" },
      ".cm-md-callout-head": { fontWeight: "600" },
      ".cm-md-callout-hint": { color: "var(--muted)", pointerEvents: "none", userSelect: "none" },
      //: A footnote's identifier, raised, where its brackets were. The
      //: reference is a link to the definition; the definition is the place
      //: being linked to, so only one of them is clickable.
      //: Math sits on the text's own baseline and takes the editor's ink;
      //: MathML brings its own metrics, so nothing here sets a size.
      //: An embedded card is a block of app inside a line of text, so it is
      //: given the line's width to work in and nothing else: every card in it
      //: is styled by the stylesheet that owns that card.
      ".cm-md-embed": {
        display: "inline-block",
        maxWidth: "100%",
        verticalAlign: "top",
        cursor: "pointer",
      },
      //: The cards keep their own appearance and are given a width to work
      //: in: a note card sized to its content is as wide as its longest line,
      //: and a minimap is `width: 100%` of whatever box it is handed.
      ".cm-md-embed .entry-list": { width: "min(420px, 100%)", margin: "0", padding: "0" },
      ".cm-md-embed .doc-embed-map": { display: "block", width: "min(320px, 100%)" },
      ".cm-md-embed .att-card": { width: "min(360px, 100%)" },
      ".cm-md-math": { cursor: "text" },
      ".cm-md-math-block": { display: "block", textAlign: "center", margin: "0.2em 0" },
      ".cm-md-footnote": {
        verticalAlign: "super",
        fontSize: "0.72em",
        color: "var(--accent-text)",
        fontWeight: "600",
      },
      ".cm-md-footnote-ref": {
        cursor: "pointer",
        //: A target of at least 24px (44 under touch) with no change to the
        //: line: the padding is the hit area, the negative margin takes it
        //: out of the layout (audit 1102 DX21, the same pair as `.md-fn-ref a`).
        padding: "var(--space-3) var(--space-5)",
        margin: "0 calc(var(--space-5) * -1)",
      },
      //: The toggle's chevron sits with the callout's own label, in the same
      //: muted ink, because it is part of the same control.
      ".cm-md-callout-fold": { fontSize: "0.9em", opacity: "0.8" },
      ".cm-md-callout-label [data-doc-callout-fold]": { cursor: "pointer" },
      ".cm-md-task-hit": { cursor: "pointer" },
      ".cm-md-image": { maxWidth: "100%", borderRadius: "var(--radius-sm)" },
      ".cm-md-image-under": { display: "block", marginTop: "var(--space-2)" },

      //: --- tables ---------------------------------------------------------
      //: **A grid over the line, not a `<table>` widget.** Replacing the block
      //: with a rendered table is what every "table editor" in a markdown app
      //: does and it is what forces them to have a serialiser, which is what
      //: loses the author's own whitespace (PLAN D4's gate, and the long
      //: comment on the model at the top of this file). Here the pipes are
      //: hidden like every other marker in this view and each cell is a mark,
      //: so `display: grid` on the line turns those marks into the columns:
      //: the text on screen is still the text in the file, at the same
      //: offsets, and the caret walks it normally.
      //:
      //: `minmax(0, 1fr)` rather than `1fr`, because a grid column's implicit
      //: minimum is its content's min-content width, so one long unbroken word
      //: in a cell would push the table wider than the editor instead of
      //: wrapping.
      ".cm-md-table": {
        display: "grid",
        "--doc-table-col-min": "6em",
        borderLeft: "1px solid var(--border)",
        //: The cell menu is positioned against whichever row it is on.
        position: "relative",
      },
      //: Past `DOC_TABLE_GRID_MAX` columns there is no class to place the
      //: cells with, so the line falls back to what it did before them. It is
      //: the worse rendering (every zero-width child behind a hidden pipe
      //: takes a track of its own), and it is a table no editor this wide can
      //: show usefully in any case.
      ".cm-md-table-wide": {
        gridAutoFlow: "column",
        gridAutoColumns: "minmax(var(--doc-table-col-min), 1fr)",
      },
      ...docTableGridRules(),
      ".cm-md-table-head": {
        fontWeight: "650",
        backgroundColor: "var(--field-inset)",
        borderTop: "1px solid var(--border)",
        //: The cell menu is positioned against this line.
        position: "relative",
      },
      //: The rendered view's own cell inset (`.md-table td`: 0.4rem by
      //: 0.6rem), where this was 0.05em by 0.5em and a row of words sat
      //: against the rules above and below it (17c, measured in
      //: `scratchpad/ui-sweeps/docblocks17c.js`).
      ".cm-md-td": {
        padding: "var(--space-2) var(--space-4)",
        borderRight: "1px solid var(--border)",
        borderBottom: "1px solid var(--border)",
      },
      //: The cell the caret is in: a ring inside the cell, so it moves no
      //: rule and changes no column width, and a faint ground that sits
      //: under a selection rather than hiding it.
      ".cm-md-td-active": {
        boxShadow: "inset 0 0 0 2px var(--accent)",
        backgroundColor: "color-mix(in srgb, var(--accent) 6%, transparent)",
        borderRadius: "var(--radius-sm, 6px)",
      },
      ".cm-md-table .cm-md-td-last": {
        paddingRight: "calc(var(--space-4) + 1.75rem)",
      },
      ".cm-md-td-left": { textAlign: "left" },
      ".cm-md-td-center": { textAlign: "center" },
      ".cm-md-td-right": { textAlign: "right" },
      //: The delimiter row is the header's underline, and the header's cells
      //: already draw that. With its own text hidden it would otherwise leave
      //: a blank line through the middle of the table; it comes back to full
      //: height the moment the caret arrives on it, which is the rule `---`
      //: has followed here since Phase 2.
      ".cm-md-table-rule": { height: "0", overflow: "hidden" },
      //: A frontmatter line, hidden the same way and for the same reason: the
      //: properties panel above the editor is where it is read and written.
      //: `border: 0` as well as the height, and it is measured: the opening
      //: fence is also a `---`, so it carries `.cm-md-rule`'s bottom border,
      //: and a zero-high line with a border is a 1px line across the top of
      //: the document.
      ".cm-md-frontmatter": { height: "0", overflow: "hidden", border: "0" },
      //: Out of the grid's flow, or the menu would be a column of its own and
      //: every cell in the table would narrow to make room for it.
      //: Centred on its row, which is now any row (the menu follows the
      //: caret): pinned to the top it sat 5px high on a one-line row.
      ".cm-md-table-menu": {
        position: "absolute",
        right: "2px",
        top: "calc(50% - 0.875rem)",
        opacity: "0.7",
      },
      ".cm-md-table-menu:hover, .cm-md-table-menu:focus-within": { opacity: "1" },

      //: --- the prose findings ---------------------------------------------
      //: Three shapes, one per kind of claim. Wavy for a spelling
      //: the checker is sure about, wavy in the accent for a style note,
      //: dotted for a repeated word: three, because three is what a reader can
      //: decode at a glance from the shape of a line.
      ".cm-finding": {
        textDecorationSkipInk: "none",
        textUnderlineOffset: "0.18em",
        cursor: "pointer",
      },
      //: **The hover, which was the one surface in this feature with none.**
      //: Four things draw a finding (the underline, the word menu, the panel,
      //: the dictionary) and three of them answered the pointer; the underline
      //: offered `cursor: pointer` and nothing else, so the only way to learn
      //: that a squiggle is pressable was to press it.
      //:
      //: A tint rather than a thicker line: the three kinds are told apart by
      //: the *shape* of their underline (wavy, wavy, dotted), and thickening
      //: one on hover moves it towards another kind's shape. A ground behind
      //: the word says "this is one object" without touching the mark that
      //: says which kind it is, and it is the same thing `.menu-item:hover`
      //: does one surface over.
      //:
      //: 12% of the kind's own colour, mixed against the page rather than
      //: stated as an alpha, so it composes on the editor's ground in either
      //: theme and follows `[data-contrast="on"]`'s redefinitions of
      //: `--error`, `--accent` and `--muted` without a branch of its own.
      //: Measured light and dark in `prosepanel.js`.
      ".cm-finding-spelling:hover": {
        backgroundColor: "color-mix(in srgb, var(--error) 12%, transparent)",
        borderRadius: "3px",
      },
      ".cm-finding-style:hover": {
        backgroundColor: "color-mix(in srgb, var(--accent) 12%, transparent)",
        borderRadius: "3px",
      },
      ".cm-finding-repeat:hover": {
        backgroundColor: "color-mix(in srgb, var(--muted) 12%, transparent)",
        borderRadius: "3px",
      },
      ".cm-finding-grammar:hover": {
        backgroundColor: "color-mix(in srgb, var(--warn) 14%, transparent)",
        borderRadius: "3px",
      },
      ".cm-finding-ai:hover": {
        backgroundColor: "color-mix(in srgb, var(--accent) 12%, transparent)",
        borderRadius: "3px",
      },
      ".cm-finding-access:hover": {
        backgroundColor: "color-mix(in srgb, var(--accent) 12%, transparent)",
        borderRadius: "3px",
      },
      ".cm-finding-link:hover": {
        backgroundColor: "color-mix(in srgb, var(--accent) 12%, transparent)",
        borderRadius: "3px",
      },
      ".cm-finding-spelling": {
        textDecoration: "underline wavy",
        textDecorationColor: "color-mix(in srgb, var(--error) 80%, transparent)",
      },
      ".cm-finding-style": {
        textDecoration: "underline wavy",
        textDecorationColor: "color-mix(in srgb, var(--accent) 80%, transparent)",
      },
      ".cm-finding-repeat": {
        textDecoration: "underline dotted",
        textDecorationThickness: "2px",
        textDecorationColor: "var(--muted)",
      },
      //: Grammar (Harper, INBOX 401): a double line, the shape Word gives
      //: grammar, in the warning ink, so it reads as neither a typo (wavy
      //: red) nor a style note (wavy accent).
      ".cm-finding-grammar": {
        textDecoration: "underline double",
        textDecorationColor: "var(--warn)",
      },
      //: Accessibility (INBOX 404): dashed, the one line shape left, in the
      //: accent, because it is about structure rather than a mistake.
      //: Check with AI (INBOX 410): dotted accent, a lighter mark than the
      //: style note's wavy accent, because a model's reading is a suggestion
      //: to consider rather than a rule broken.
      ".cm-finding-ai": {
        textDecoration: "underline dotted",
        textDecorationThickness: "2px",
        textDecorationColor: "color-mix(in srgb, var(--accent) 80%, transparent)",
      },
      ".cm-finding-access": {
        textDecoration: "underline dashed",
        textDecorationThickness: "2px",
        textDecorationColor: "color-mix(in srgb, var(--accent) 80%, transparent)",
      },
      //: A link offer (VC5): a plain thin underline in the accent, the line a
      //: link wears, because this is where one could be, not a mistake.
      ".cm-finding-link": {
        textDecoration: "underline solid",
        textDecorationThickness: "1px",
        textUnderlineOffset: "3px",
        textDecorationColor: "color-mix(in srgb, var(--accent) 80%, transparent)",
      },
    },
    { dark }
  );
}
