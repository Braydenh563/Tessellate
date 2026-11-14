(() => {
  // whiteboard-textedit.js: the text box and sticky editor, runs, text style bar and box fitting.
  // Moved out of whiteboard.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  //: **A text box is a box first and a text field second.** The other half of
  //: the same report ("I can't drag text boxes... basically unmovable"): the
  //: `.wb-text-content` was `contenteditable` from the moment it rendered and
  //: fills the box edge to edge, so it swallowed every pointerdown before the
  //: object's own drag could see one. The only draggable surface left was the
  //: grip and a ~0.5rem strip of padding, and grabbing anywhere else did
  //: nothing at all, which reads as "broken" rather than "aim for the handle".
  //:
  //: So the box is only editable once you ask it to be, which is what every
  //: canvas app with text does (Figma, Excalidraw, PowerPoint): drag it like
  //: any other object, double-click to get a caret, blur to go back. A box
  //: made by the text tool starts in edit mode, since the whole point of
  //: click-to-place is typing straight away.
  //: **Rendered markdown in a text box or sticky, toggleable.** Asked for
  //: directly. Editing always shows the raw text, markdown you cannot see is
  //: markdown you cannot fix, so this paints the rendered form only when the
  //: box is not being edited, and `wbBeginTextEdit` puts the source back.
  function wbPaintTextContent(contentEl, d) {
    if (!contentEl) return;
    const raw = d.data.content || "";
    if (d.data.md && raw.trim() && typeof renderMarkdown === "function") {
      contentEl.replaceChildren();
      contentEl.classList.add("wb-text-md");
      renderMarkdown(contentEl, raw);
      wbFmtState.textMore?.paintScripts(contentEl); // H~2~O and x^2^, board only (whiteboard-text-more.js)
      return;
    }
    contentEl.classList.remove("wb-text-md");
    contentEl.textContent = raw;
  }

  //: A marker around `text[from, to)`, or taken off again when the run already
  //: wears it (so Bold twice is not `****`). Pure, so a test can run it: the
  //: old code did `raw.replace(pickedText, ...)`, which wrapped the FIRST
  //: occurrence of the picked words, not the ones selected ("the cat and the
  //: cat" with the second "cat" picked bolded the first).
  function wbWrapRange(text, from, to, marker) {
    const n = marker.length;
    const inner = text.slice(from, to);
    if (inner.length > 2 * n && inner.startsWith(marker) && inner.endsWith(marker)) {
      return { text: text.slice(0, from) + inner.slice(n, -n) + text.slice(to), from, to: to - 2 * n };
    }
    if (text.slice(Math.max(0, from - n), from) === marker && text.slice(to, to + n) === marker) {
      return { text: text.slice(0, from - n) + inner + text.slice(to + n), from: from - n, to: to - n };
    }
    return { text: text.slice(0, from) + marker + inner + marker + text.slice(to), from: from + n, to: to + n };
  }

  //: Wrap the selection inside a text box (or the whole text, when nothing is
  //: selected) in a markdown marker, the formatting bar a text box never had.
  //: While the box is being typed in, the work is done on what is on screen
  //: through its editing surface (`insertText`, so Ctrl+Z holds), by offsets:
  //: the saved `content` is stale until blur, and the picked words may occur
  //: twice.
  function wbWrapTextSelection(marker) {
    const item = wbSelectedTextObjectOrNull();
    if (!item) return;
    const el = document.querySelector(`.wb-object[data-id="${item.id}"] .wb-text-content`);
    const surf = el && el.isContentEditable ? el.wbEditorSurface : null;
    if (surf) {
      const value = surf.text;
      const { from, to } = surf.selection();
      const whole = from === to;
      const out = wbWrapRange(value, whole ? 0 : from, whole ? value.length : to, marker);
      if (!value.trim() || out.text === value) return;
      surf.value = out.text;
      surf.setSelectionRange(out.from, out.to);
      return;
    }
    const before = WB_KIND_INFO.object.payload(item);
    wbPushUndo({ action: "move", kind: "object", id: item.id, before });
    const raw = item.data.content || "";
    const next = raw.trim() ? wbWrapRange(raw, 0, raw.length, marker).text : raw;
    item.data = { ...item.data, content: next };
    wbSaveObject(item);
    wbScheduleRender();
  }

  //: **Runs** (INBOX 1403). Every character of `text` with the run it sits in
  //: (`{}` for none) and where it starts in `text`, the run marks themselves
  //: dropped. Shared by the editor below and the export.
  function wbRunChars(text) {
    const chars = [];
    const re = new RegExp(MD_RUN.source, "g");
    let cursor = 0;
    let hit;
    const plain = (end) => {
      for (; cursor < end; cursor += 1) chars.push({ ch: text[cursor], attrs: {}, at: cursor });
    };
    while ((hit = re.exec(text)) !== null) {
      plain(hit.index);
      const attrs = mdRunParse(hit[1]);
      const inner = hit.index + hit[0].indexOf("|") + 1;
      for (let i = 0; i < hit[2].length; i += 1) chars.push({ ch: hit[2][i], attrs, at: inner + i });
      cursor = re.lastIndex;
    }
    plain(text.length);
    return chars;
  }

  //: `patch` (`size`, `font`, `ink`, `hl`; a value sets it, null clears it, a
  //: missing key leaves it) applied to the characters in `text[from, to)` only,
  //: and the whole text written back with its runs rebuilt: neighbours with
  //: equal values share one run, a line break or a `}` ends a run (neither can
  //: sit inside one), and what lay outside the selection reads as it did. Pure,
  //: so a test can run it. `from`/`to` come back around the same words.
  function wbRunApply(text, from, to, patch) {
    const chars = wbRunChars(text);
    const n = chars.length;
    const first = chars.findIndex((c) => c.at >= from);
    const last = chars.findIndex((c) => c.at >= to);
    const cf = first === -1 ? n : first;
    const ct = last === -1 ? n : last;
    if (cf >= ct) return { text, from, to };
    for (let i = cf; i < ct; i += 1) {
      const next = { ...chars[i].attrs };
      for (const key of ["size", "font", "ink", "hl"]) {
        if (patch[key] === null) delete next[key];
        else if (patch[key] !== undefined) next[key] = patch[key];
      }
      chars[i] = { ...chars[i], attrs: next };
    }
    const bare = (c) => c.ch === "\n" || c.ch === "}";
    const pos = [];
    let out = "";
    let i = 0;
    while (i < n) {
      const key = bare(chars[i]) ? "" : mdRunFormat(chars[i].attrs);
      if (!key) {
        pos[i] = out.length;
        out += chars[i].ch;
        i += 1;
        continue;
      }
      let j = i;
      let body = "";
      while (j < n && !bare(chars[j]) && mdRunFormat(chars[j].attrs) === key) {
        body += chars[j].ch;
        j += 1;
      }
      const head = `{{${key}|`;
      for (let k = i; k < j; k += 1) pos[k] = out.length + head.length + (k - i);
      out += `${head}${body}}}`;
      i = j;
    }
    return { text: out, from: pos[cf], to: pos[ct - 1] + 1 };
  }

  //: The colours a run's swatches show (the stylesheet draws the real ones, in
  //: both themes); the export's fills are `WB_RUN_INK` and these at a quarter.
  const WB_RUN_SWATCHES = {
    yellow: "#eab308", green: "#22c55e", blue: "#3b82f6", pink: "#ec4899",
    purple: "#a855f7", orange: "#f97316", red: "#ef4444", grey: "#94a3b8",
  };
  const WB_RUN_INK = {
    yellow: "#b45309", green: "#15803d", blue: "#1d4ed8", pink: "#be185d",
    purple: "#7e22ce", orange: "#c2410c", red: "#b91c1c", grey: "#6b7280",
  };
  const WB_RUN_SIZES = [12, 16, 20, 28, 40];

  //: **The selection bar's Text style** (INBOX 1403): size, font, text colour
  //: and highlight colour for the selected words only, as a run in the text.
  //: The picks go through the editing surface (`wbSpliceEditable`, so the
  //: browser's Undo holds them), and the menu is the colour popover's own
  //: element, built the way `wbOpenPaperMenu` builds the paper row. The whole
  //: box's text settings, which are object-wide, are one press from here.
  async function wbOpenRunMenu(button) {
    const surface = document.activeElement?.wbEditorSurface;
    if (!surface) return;
    const span = surface.selection();
    if (span.from === span.to) return;
    if (typeof swatchPicker !== "function" && !(await ensureModule("categories"))) return;
    const state = { from: span.from, to: span.to };
    const apply = (patch) => {
      closeActionMenus();
      surface.el.focus({ preventScroll: true });
      const before = surface.text;
      const out = wbRunApply(before, state.from, state.to, patch);
      if (out.text === before) return;
      surface.el.dataset.wbFormatted = "1";
      wbSpliceEditable(surface, before, out.text);
      surface.setSelectionRange(out.from, out.to);
    };
    const menu = wbColourMenu();
    wbStopEyedrop();
    wbColourState.input = null;
    menu.setAttribute("aria-label", "Text style");
    const head = document.createElement("p");
    head.className = "wb-colour-head";
    head.textContent = "Text style";
    const row = (words, buttons) => {
      const box = document.createElement("div");
      box.className = "wb-colour-actions";
      box.setAttribute("role", "group");
      box.setAttribute("aria-label", words);
      box.append(...buttons);
      return box;
    };
    //: A press on the menu must not take focus from the box: that ends the
    //: edit (the blur saves and drops the editing surface) before the pick runs.
    //: The selection bar's own buttons are `mousedown` for the same reason.
    const keepFocus = (el) => {
      el.addEventListener("mousedown", (event) => event.preventDefault());
      return el;
    };
    const choice = (words, title, patch, face) => {
      const b = keepFocus(document.createElement("button"));
      b.type = "button";
      b.className = "ghost small";
      b.title = title;
      b.textContent = words;
      if (face) b.style.fontFamily = MD_RUN_FONTS[face];
      b.addEventListener("click", () => (patch instanceof Function ? patch() : apply(patch)));
      return b;
    };
    //: Subscript and superscript (L-whiteboard-27): the pandoc marks round the selected words, or off them again.
    const wrap = (mark) => () => {
      closeActionMenus();
      surface.el.focus({ preventScroll: true });
      const before = surface.text;
      const out = wbFmtState.textMore?.wrapScript(before, state.from, state.to, mark);
      if (!out) return toast("Pick up to 20 characters with no spaces to lower or raise them.");
      surface.el.dataset.wbFormatted = "1";
      wbSpliceEditable(surface, before, out.text);
      surface.setSelectionRange(out.from, out.to);
    };
    const scripts = [choice("Subscript", "Lower the selected words: H~2~O", wrap("~")), choice("Superscript", "Raise the selected words: x^2^", wrap("^"))];
    const sizes = WB_RUN_SIZES.map((px) => choice(String(px), `Size ${px} for the selected words`, { size: px }));
    sizes.push(choice("Default", "The box's own size for the selected words", { size: null }));
    const fonts = Object.entries({ serif: "Serif", mono: "Mono", wide: "Wide", hand: "Hand" }).map(([key, words]) =>
      choice(words, `${words} for the selected words`, { font: key }, key));
    fonts.push(choice("Default", "The box's own font for the selected words", { font: null }));
    const colours = (label, field, none) =>
      keepFocus(swatchPicker({ label, value: undefined, palette: WB_RUN_SWATCHES, none, onChoose: (key) => apply({ [field]: key }) }));
    const whole = keepFocus(document.createElement("button"));
    whole.type = "button";
    whole.className = "ghost small";
    whole.title = "Size, colour and font for all the text in the box";
    whole.textContent = "Text settings for the whole box";
    whole.addEventListener("click", () => {
      closeActionMenus();
      wbFormatOpen("text");
    });
    menu.replaceChildren(
      head,
      wbColourHeading("Size"), row("Size", sizes),
      wbColourHeading("Font"), row("Font", fonts),
      wbColourHeading("Text colour"), colours("Text colour", "ink", "Default"),
      wbColourHeading("Highlight"), colours("Highlight colour", "hl", "None"),
      wbColourHeading("Script"), row("Script", scripts),
      whole
    );
    closeActionMenus();
    window._menuOpenedAt = performance.now();
    menu._escapedOpener = button;
    menu.classList.add("action-menu-escaped");
    menu.classList.remove("hidden");
    button.setAttribute("aria-expanded", "true");
    placeEscapedMenu(menu, button);
  }

  function wbBulletTextLines() {
    const item = wbSelectedTextObjectOrNull();
    if (!item) return;
    const before = WB_KIND_INFO.object.payload(item);
    wbPushUndo({ action: "move", kind: "object", id: item.id, before });
    const lines = (item.data.content || "").split("\n");
    const allBulleted = lines.every((line) => !line.trim() || line.trimStart().startsWith("- "));
    item.data = {
      ...item.data,
      content: lines
        .map((line) => (!line.trim() ? line : allBulleted ? line.replace(/^(\s*)- /, "$1") : `- ${line}`))
        .join("\n"),
    };
    wbSaveObject(item);
    wbScheduleRender();
  }

  function wbBeginTextEdit(contentEl, ownText) {
    if (!contentEl || contentEl.isContentEditable) return;
    //: Back to the source while editing, whatever the rendered view showed.
    //: `ownText`: a frame's title or hint line is not the object's `content` (C17).
    const objectEl = contentEl.closest(".wb-object");
    const item = (wbState.objects || []).find((o) => String(o.id) === objectEl?.dataset.id);
    if (ownText !== undefined) {
      contentEl.textContent = ownText;
    } else if (item) {
      contentEl.classList.remove("wb-text-md");
      contentEl.textContent = item.data.content || "";
    }
    //: **Plain text, so a line break stays a line break.** With
    //: `contenteditable="true"` Enter inserts a `<div>`, and the blur handlers
    //: read `textContent`, which has no line breaks for those: measured,
    //: "start", Enter, "- item" saved as "start- item". `plaintext-only` keeps
    //: the box a run of text with real "\n"s (Chromium, WebView2 and WebKit
    //: all support it); where it is refused the attribute falls back to
    //: "true" and `wbEditedText` still reads the lines back correctly.
    contentEl.setAttribute("contenteditable", "plaintext-only");
    if (contentEl.contentEditable !== "plaintext-only") contentEl.setAttribute("contenteditable", "true");
    contentEl.closest(".wb-object")?.classList.add("wb-text-editing");
    wbAttachEditorMenu(contentEl);
    contentEl.focus({ preventScroll: true });
  }

  //: **The editor's "/" and "[[" menus, in a box on the board** (the owner,
  //: 2026-10-10: "/ command menus don't appear in text boxes in the
  //: whiteboard"; "the / command menu and [[ adding notes etc doesn't work on
  //: mind map nodes"). editor.js drives a textarea or CodeMirror through a
  //: surface (documents.js `textareaSurface`); a board box is a
  //: `plaintext-only` contenteditable, so it gets a surface of its own with
  //: the same members the menu reads: its text, the caret as offsets into
  //: that text, a splice, and the caret's point on screen. The offsets are
  //: the text nodes' (and a `<br>` as one "\n"), the model `wbEditedText`
  //: and `wbIndentEditableLines` already use. The context names what the menu
  //: offers: a text box renders markdown and keeps the blocks; a topic keeps
  //: links, an emoji and the date (`EDITOR_BOARD_ROWS`, editor.js).
  const WB_EDITOR_SURFACES = { "wb-text-edit": "board", "wb-topic-edit": "topic" };

  //: What each of the boards' contexts offers (the owner, 2026-10-10: "/
  //: command menus don't appear in text boxes in the whiteboard", "the /
  //: command menu and [[ adding notes etc doesn't work on mind map nodes", and
  //: links "in comments on documents and boards/maps"): the note's rows, cut
  //: to what each place can draw. A text box renders markdown, so it keeps the
  //: blocks; a map topic is a line or two, so it keeps links, an emoji and the
  //: date; a comment keeps links. Handed to editor.js's `EDITOR_CONTEXT_ROWS`
  //: with the surfaces, so they cost the boot nothing.
  const WB_EDITOR_CONTEXT_ROWS = {
    board: ["bullets", "numbered", "checklist", "quote", "h1", "heading", "h3", "divider", "emoji", "wikilink", "bookmark-link", "link-card", "weblink", "math-inline", "equation", "stamp-date", "stamp-time", "stamp-datetime"],
    topic: ["emoji", "wikilink", "bookmark-link", "weblink", "stamp-date", "stamp-time"],
    comment: ["wikilink", "bookmark-link", "link-card", "weblink", "emoji", "stamp-date", "stamp-time"],
  };

  function wbRegisterEditorContexts() {
    if (typeof EDITOR_CONTEXT_ROWS === "object") Object.assign(EDITOR_CONTEXT_ROWS, WB_EDITOR_CONTEXT_ROWS);
  }

  function wbAttachEditorMenu(el) {
    if (typeof EDITOR_SURFACES !== "object" || el.wbEditorSurface) return;
    //: A frame's title and a connector's label are one-line names: no menu.
    const id = el.classList.contains("wb-map-text")
      ? "wb-topic-edit"
      : el.classList.contains("wb-text-content") || el.classList.contains("wb-shape-label-editor")
        ? "wb-text-edit"
        : null;
    if (!id) return;
    Object.assign(EDITOR_SURFACES, WB_EDITOR_SURFACES);
    wbRegisterEditorContexts();
    el.wbEditorSurface = wbEditableSurface(el, id);
  }

  function wbDetachEditorMenu(el) {
    if (!el?.wbEditorSurface) return;
    if (typeof editorMenuState === "object" && editorMenuState.open && editorMenuState.textarea === el.wbEditorSurface) editorCloseMenu();
    delete el.wbEditorSurface;
  }

  function wbEditableSurface(el, id) {
    //: Every text node and line break in order, with where each starts.
    const pieces = () => {
      const out = [];
      let at = 0;
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (node.nodeType === Node.TEXT_NODE) {
          out.push({ node, at, length: node.length });
          at += node.length;
        } else if (node.nodeName === "BR") {
          out.push({ node, at, length: 1, br: true });
          at += 1;
        }
      }
      return out;
    };
    const text = () => pieces().map((p) => (p.br ? "\n" : p.node.data)).join("");
    //: A DOM point to an offset into `text()`.
    const offsetOf = (container, offset) => {
      if (container.nodeType !== Node.TEXT_NODE) {
        //: An element point counts child nodes: every piece wholly before it.
        const before = document.createRange();
        before.setStart(el, 0);
        before.setEnd(container, offset);
        let n = 0;
        for (const p of pieces()) if (before.intersectsNode(p.node)) n = p.at + p.length;
        return n;
      }
      const hit = pieces().find((p) => p.node === container);
      return hit ? hit.at + Math.min(offset, hit.length) : 0;
    };
    //: An offset to a DOM point: inside the text node that holds it.
    const pointAt = (target) => {
      const list = pieces();
      for (const p of list) {
        if (p.br) {
          if (target <= p.at) return [p.node.parentNode, [...p.node.parentNode.childNodes].indexOf(p.node)];
          continue;
        }
        if (target <= p.at + p.length) return [p.node, Math.max(0, target - p.at)];
      }
      return [el, el.childNodes.length];
    };
    const range = () => {
      const sel = window.getSelection();
      if (!sel || !sel.rangeCount || !el.contains(sel.anchorNode)) {
        const end = text().length;
        return { from: end, to: end };
      }
      const r = sel.getRangeAt(0);
      return { from: offsetOf(r.startContainer, r.startOffset), to: offsetOf(r.endContainer, r.endOffset) };
    };
    const surface = {
      el,
      kind: "textarea",
      id,
      isDocument: false,
      scrollEl: el,
      get value() { return text(); },
      //: Only the changed run is replaced, through `insertText`, so the
      //: browser's own Ctrl+Z inside the box takes back a Bold from the
      //: selection bar (`applyMarkdown` writes `value`, K24).
      set value(next) { wbSpliceEditable(surface, text(), next); },
      get text() { return text(); },
      set text(next) { surface.value = next; },
      get selectionStart() { return range().from; },
      get selectionEnd() { return range().to; },
      //: `wrapDocSelection` sets the two ends one after the other.
      set selectionStart(at) { surface.setSelectionRange(at, Math.max(at, range().to)); },
      set selectionEnd(at) { surface.setSelectionRange(Math.min(range().from, at), at); },
      get classList() { return el.classList; },
      get dataset() { return el.dataset; },
      selection() { return range(); },
      setSelectionRange(from, to = from) {
        const sel = window.getSelection();
        if (!sel) return;
        const r = document.createRange();
        r.setStart(...pointAt(from));
        r.setEnd(...pointAt(to));
        sel.removeAllRanges();
        sel.addRange(r);
      },
      setSelection(from, to = from) { surface.setSelectionRange(from, to); },
      setRangeText(insert, from, to) {
        const value = text();
        wbSpliceEditable(surface, value, value.slice(0, from) + insert + value.slice(to));
        surface.setSelectionRange(from + insert.length);
      },
      //: The caret's point on screen: a collapsed range's rect, or the box's
      //: own first line when the caret sits on an empty line (no rect).
      coordsAt(pos) {
        const r = document.createRange();
        r.setStart(...pointAt(pos));
        r.collapse(true);
        let rect = r.getClientRects()[0] || r.getBoundingClientRect();
        const box = el.getBoundingClientRect();
        const line = parseFloat(getComputedStyle(el).lineHeight) || 20;
        const scale = box.width / (el.offsetWidth || box.width) || 1;
        if (!rect || (!rect.width && !rect.height && !rect.top && !rect.left)) rect = { top: box.top, left: box.left, height: line * scale };
        return { top: rect.top, left: rect.left, lineHeight: rect.height || line * scale, offscreen: rect.top > window.innerHeight || rect.top + (rect.height || 0) < 0 };
      },
      lineAt(pos) {
        const value = text();
        const at = Math.max(0, Math.min(pos, value.length));
        const from = value.lastIndexOf("\n", at - 1) + 1;
        const found = value.indexOf("\n", at);
        const to = found === -1 ? value.length : found;
        return { number: value.slice(0, from).split("\n").length, from, to, text: value.slice(from, to) };
      },
      onChange(fn) { el.addEventListener("input", fn); },
      focus() { el.focus({ preventScroll: true }); },
      blur() { el.blur(); },
      rect() { return el.getBoundingClientRect(); },
      getBoundingClientRect() { return el.getBoundingClientRect(); },
      dispatchEvent(event) { return el.dispatchEvent(event); },
    };
    return surface;
  }

  //: Replace what changed between `before` and `next` in a box being edited:
  //: the run between their common start and end, selected and typed over with
  //: `insertText`, which is what keeps the edit on the box's own undo stack.
  //: Where the command is refused the box is written whole.
  function wbSpliceEditable(surface, before, next) {
    if (before === next) return;
    let head = 0;
    const limit = Math.min(before.length, next.length);
    while (head < limit && before[head] === next[head]) head += 1;
    let tail = 0;
    while (tail < limit - head && before[before.length - 1 - tail] === next[next.length - 1 - tail]) tail += 1;
    surface.setSelectionRange(head, before.length - tail);
    const insert = next.slice(head, next.length - tail);
    const done = document.activeElement === surface.el
      && document.execCommand(insert ? "insertText" : "delete", false, insert);
    if (!done || surface.value !== next) {
      surface.el.textContent = next;
      surface.setSelectionRange(head + insert.length);
    }
  }

  //: The surface `applyMarkdown` writes to when its target is a board box
  //: (documents.js `docSurfaceById`): the box being typed in, if it is that
  //: kind. Marked, so the box shows its markdown rendered once the edit ends.
  function wbEditorSurfaceById(id) {
    const surface = document.activeElement?.wbEditorSurface;
    if (!surface || surface.id !== id) return null;
    surface.el.dataset.wbFormatted = "1";
    return surface;
  }

  //: Ctrl+B, Ctrl+I and Ctrl+K in a text box or sticky being edited: the
  //: documents editor's own actions on the selection (K24).
  const WB_TEXT_FORMAT_KEYS = { b: "bold", i: "italic", k: "link" };

  function wbTextFormatKey(event) {
    if (!(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) return false;
    const kind = WB_TEXT_FORMAT_KEYS[String(event.key).toLowerCase()];
    if (!kind || typeof applyMarkdown !== "function" || !event.currentTarget?.wbEditorSurface) return false;
    event.preventDefault();
    applyMarkdown(kind, "wb-text-edit");
    return true;
  }

  //: **The selection bar on a board** (K24): the documents editor's bar
  //: (editor.js `selectionBarShow`), cut to what a box draws. A text box or
  //: sticky keeps the inline marks and gains a list; a map topic draws only
  //: bold, italic and code (`WB_MAP_INLINE`). Turn into, Ask and Rewrite act on
  //: a document, so they are off here. The list button is added once, beside
  //: Link, and hidden everywhere else.
  const WB_BAR_TEXT = new Set(["bold", "italic", "strike", "highlight", "code", "link", "ul"]);
  const WB_BAR_TOPIC = new Set(["bold", "italic", "code"]);

  function wbSelectionBarFit(bar, surface) {
    let list = bar.querySelector("[data-board-md]");
    if (!list) {
      list = document.createElement("button");
      list.type = "button";
      list.className = "ghost small icon-button";
      list.dataset.boardMd = "ul";
      list.title = "Bulleted list";
      list.setAttribute("aria-label", list.title);
      setLabel(list, "ph:list-bullets");
      list.addEventListener("mousedown", (event) => {
        event.preventDefault();
        const target = selectionBarState.textarea;
        if (target) applyMarkdown("ul", target.id);
      });
      bar.querySelector('[data-md="link"]')?.after(list);
    }
    //: Text style: a run's size, font and colours, on a text box or sticky only.
    let run = bar.querySelector("[data-board-run]");
    if (!run) {
      run = document.createElement("button");
      run.type = "button";
      run.className = "ghost small icon-button";
      run.dataset.boardRun = "1";
      run.title = "Text style: size, font, colour and highlight for the selection";
      run.setAttribute("aria-label", "Text style");
      run.setAttribute("aria-haspopup", "dialog");
      setLabel(run, "ph:text-aa");
      run.addEventListener("mousedown", (event) => {
        event.preventDefault();
        wbOpenRunMenu(run);
      });
      list.after(run);
    }
    run.hidden = surface?.id !== "wb-text-edit";
    const keep = surface?.id === "wb-text-edit" ? WB_BAR_TEXT : surface?.id === "wb-topic-edit" ? WB_BAR_TOPIC : null;
    list.hidden = !keep?.has("ul");
    //: Ask carries no data mark, so editor.js never shows it again by itself.
    const ask = bar.querySelector("button:not([data-md]):not([data-turn]):not([data-inline-ai]):not([data-board-md]):not([data-board-run])");
    if (!keep) {
      if (ask) ask.hidden = false;
      return;
    }
    for (const button of bar.querySelectorAll("button:not([data-board-md]):not([data-board-run])")) button.hidden = !keep.has(button.dataset.md);
    for (const rule of bar.querySelectorAll(".selection-bar-rule")) rule.hidden = true;
  }

  //: What a text box or topic being edited says, with its line breaks. See
  //: `wbBeginTextEdit` for why `textContent` is not it.
  function wbEditedText(contentEl) {
    return contentEl.innerText.replace(/\r\n?/g, "\n");
  }

  //: **Tab and Shift+Tab indent lines on the board too** (INBOX 392:
  //: "indenting and dedenting across the app"). The same rule the note and
  //: document editors apply: whole lines, two spaces, a list item moves as a
  //: block, and Shift+Tab takes off only what is there (returns false when
  //: there is nothing, so the key keeps its ordinary meaning). Done through
  //: `insertText` on a selection of the affected lines, so the browser's own
  //: Ctrl+Z inside the box still undoes it.
  function wbIndentEditableLines(contentEl, outdent) {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount || !contentEl.contains(sel.anchorNode)) return false;
    const text = wbEditedText(contentEl);
    const offsetOf = (node, offset) => {
      const range = document.createRange();
      range.selectNodeContents(contentEl);
      range.setEnd(node, offset);
      return range.toString().length;
    };
    const range = sel.getRangeAt(0);
    const selStart = offsetOf(range.startContainer, range.startOffset);
    const selEnd = offsetOf(range.endContainer, range.endOffset);
    const lineStart = text.lastIndexOf("\n", selStart - 1) + 1;
    const endBreak = text.indexOf("\n", selEnd > selStart ? selEnd - 1 : selEnd);
    const lineEnd = endBreak === -1 ? text.length : endBreak;
    const lines = text.slice(lineStart, lineEnd).split("\n");
    if (outdent && !lines.some((line) => /^( {1,2}|\t)/.test(line))) return false;
    const next = lines.map((line) => (outdent ? line.replace(/^( {1,2}|\t)/, "") : `  ${line}`));
    //: Select exactly the affected lines, by walking text nodes to the two
    //: offsets, then replace them in one edit.
    const locate = (target) => {
      const walker = document.createTreeWalker(contentEl, NodeFilter.SHOW_TEXT);
      let seen = 0;
      let node = walker.nextNode();
      while (node) {
        if (seen + node.length >= target) return [node, target - seen];
        seen += node.length;
        node = walker.nextNode();
      }
      return [contentEl, contentEl.childNodes.length];
    };
    const replace = document.createRange();
    replace.setStart(...locate(lineStart));
    replace.setEnd(...locate(lineEnd));
    sel.removeAllRanges();
    sel.addRange(replace);
    const replacement = next.join("\n");
    if (!document.execCommand("insertText", false, replacement)) {
      replace.deleteContents();
      replace.insertNode(document.createTextNode(replacement));
    }
    const shift = next[0].length - lines[0].length;
    const after = document.createRange();
    after.setStart(...locate(Math.max(lineStart, selStart + shift)));
    after.setEnd(...locate(selEnd + (replacement.length - (lineEnd - lineStart))));
    sel.removeAllRanges();
    sel.addRange(after);
    return true;
  }

  //: **A box is as tall as its words.** What a text box or sticky needs to show
  //: all its text: the words' own scroll height plus the box's chrome (its
  //: padding and border, which the content element does not own). Used by
  //: "Grow to fit the words" and by typing, which grows the box as it goes:
  //: before, a lecture paragraph typed into a sticky sat behind a scroll bar
  //: (177px of words in a 62px box, measured) and the rest could only be read
  //: by scrolling inside the card.
  function wbTextFitHeight(el) {
    const words = el.querySelector(".wb-text-content");
    if (!words) return 0;
    return Math.ceil(words.scrollHeight) + Math.max(0, el.offsetHeight - words.offsetHeight);
  }

  //: Typing in a box taller than the box: the box grows now (never shrinks, so
  //: a box made small on purpose stays small until its words need more). The
  //: state before the first growth is kept for the one undo step the blur makes.
  function wbGrowBoxToWords(contentEl, d) {
    if (d.data.sticker) return false;
    const el = contentEl.closest(".wb-object");
    if (!el) return false;
    const fit = wbTextFitHeight(el);
    if (!(fit > (d.height || el.offsetHeight) + 1)) return false;
    if (!contentEl.wbBeforeGrow) contentEl.wbBeforeGrow = WB_KIND_INFO.object.payload(d);
    d.height = fit;
    el.style.height = `${fit}px`;
    wbUpdateSelectionBar();
    return true;
  }

  function wbEndTextEdit(contentEl) {
    if (!contentEl) return;
    wbDetachEditorMenu(contentEl);
    contentEl.setAttribute("contenteditable", "false");
    contentEl.closest(".wb-object")?.classList.remove("wb-text-editing");
  }

  function wbItemTransform(d) {
    const rot = d.rotation ? ` rotate(${d.rotation}deg)` : "";
    return `translate(${d.x}px, ${d.y}px)${rot}`;
  }

  //: A screen-space point's angle from a screen-space centre, in degrees,
  //: 0-360, with "straight up" (the rotate handle's own resting position) as
  //: 0: so an untouched handle already reads as the item's actual rotation.
  //: `shiftSnap` rounds to the nearest 15°, the same modifier convention as
  //: shift-to-constrain while drawing a shape.
  //: `wbAngleFromCenterDeg`, but for a sketch's rotate handle specifically, 
  //: the center it's given is in *board* space (the same coordinate space
  //: `d` itself uses), while the pointer only ever arrives in *screen*
  //: space (`clientX`/`clientY`). The resize-handle drag just above this
  //: function divides `event.dx` by the zoom scale by hand for the same
  //: reason: an SVG child's d3.drag coordinates are not auto-corrected for
  //: an ancestor `<g transform>` in this app's actual DOM, so the two
  //: spaces have to be reconciled explicitly rather than assumed to match.
  function wbSketchAngleFromCenterDeg(boardCx, boardCy, sourceEvent, shiftSnap) {
    const transform = d3.zoomTransform(document.getElementById("whiteboard-container"));
    const rect = wbCanvasOriginRect();
    const screenCx = boardCx * transform.k + transform.x + rect.left;
    const screenCy = boardCy * transform.k + transform.y + rect.top;
    return wbAngleFromCenterDeg(screenCx, screenCy, sourceEvent.clientX, sourceEvent.clientY, shiftSnap);
  }

  //: A shape's drawn group, path and hit path, for a drag to write to.
  function wbSketchLiveEls(id) {
    const g = document.querySelector(`.sketch-group[data-id="${id}"]`);
    return { g, path: g?.querySelector(".sketch-path"), hit: g?.querySelector(".sketch-hitbox") };
  }

  function wbAngleFromCenterDeg(cx, cy, px, py, shiftSnap) {
    let deg = Math.atan2(py - cy, px - cx) * (180 / Math.PI) + 90;
    deg = ((deg % 360) + 360) % 360;
    if (shiftSnap) deg = Math.round(deg / 15) * 15 % 360;
    //: **Upright and square are magnetic** (INBOX 1354, rotating "is very
    //: finicky"): without Shift, an angle within 3 degrees of 0, 90, 180 or 270
    //: lands on it, so a shape turned by eye to a quarter turn is one.
    else if (Math.abs(deg - Math.round(deg / 90) * 90) < 3) deg = Math.round(deg / 90) * 90 % 360;
    return Math.round(deg);
  }

  //: A board made by this act (INBOX 898): Undo bins it and Redo brings it back,
  //: kept on that board's own history, so call it once the board is open.
  function wbBoardMadeStep(board) {
    if (!board?.id) return;
    wbPushCall(`Made the board “${board.title || "Untitled"}”`, () => wbBinBoard(board.id, true), () => wbBinBoard(board.id, false));
  }

  //: A board's own fields changed by `PUT /whiteboard/boards/{id}` (its name, its
  //: kind; INBOX 898): the step writes `before` or `after` and repaints the
  //: board list, and reopens the board when the change redraws it (a kind).
  function wbBoardPutStep(label, boardId, before, after, reopen = false) {
    const put = (body) => async () => {
      const board = await apiJson(`/whiteboard/boards/${boardId}`, { method: "PUT", body: JSON.stringify(body) });
      await refreshBoardList(board);
      if (reopen && window.currentBoardId === boardId) await openWhiteboardBoard(boardId);
    };
    return wbPushCall(label, put(before), put(after));
  }

  //: A step that is a pair of calls rather than a board edit (the library
  //: panel's acts, INBOX 898): the history swaps the two on every press.
  function wbPushCall(label, undo, redo) {
    const step = { action: "call", label, run: undo, back: redo };
    wbPushUndo(step);
    return step;
  }

  async function wbApplyHistoryEntry(from, to) {
    const entry = from.pop();
    if (!entry) return false;
    if (entry.action === "call") {
      await entry.run();
      to.push({ action: "call", label: entry.label, run: entry.back, back: entry.run });
      return true;
    }
    if (entry.action === "batch") {
      // A single user gesture that touched several items at once, an
      // arrow-key nudge on a multi-selection, or an alignment/distribute pass
      //, needs to undo/redo as the one action it visibly was, not N separate
      // Undo presses. Bundles N sub-entries and replays each through this same
      // function (recursively: none of the sub-actions are themselves
      // batches), re-bundling whatever came back as the one reverse entry.
      //: **Replayed backwards the other way** (INBOX 537): a batch whose steps
      //: depend on each other (put a child back, then delete the topic it hung
      //: from) must redo them in the opposite order. The steps not yet run and
      //: the reverses already made are visible to `wbRemapUndoIds`, so a topic
      //: re-made mid-batch with a new id is followed by the steps that name it.
      const reverse = [];
      const pending = [...entry.entries];
      if (!wbHistoryInFlight.length) wbRemapSeen = new WeakMap();
      wbHistoryInFlight.push(pending, reverse);
      try {
        while (pending.length) {
          const run = wbTakeMoveRun(pending);
          if (run.length) {
            reverse.push(...(await wbApplyMoveRun(run)));
            continue;
          }
          const subTo = [];
          await wbApplyHistoryEntry([pending.shift()], subTo);
          if (subTo.length) reverse.push(subTo[0]);
        }
      } finally {
        wbHistoryInFlight.splice(wbHistoryInFlight.indexOf(pending), 2);
      }
      to.push({ action: "batch", entries: reverse.reverse() });
      return true;
    }
    if (entry.action === "reparent") {
      //: A map topic's parent (INBOX 410). `PUT /objects/{id}` deliberately
      //: never writes `parent_id`, so a "move" entry cannot put a branch back
      //: under its old parent; `/move` can, with the same cycle check a drag
      //: gets. The reverse is the parent it had a moment ago.
      const item = (wbState.objects || []).find((i) => i.id === entry.id);
      if (!item) return true;
      const current = item.parent_id ?? null;
      const moved = await apiJson(
        `/whiteboard/boards/${item.board_id ?? window.currentBoardId}/nodes/${entry.id}/move`,
        { method: "PUT", body: JSON.stringify({ parent_id: entry.parentId }) }
      );
      Object.assign(item, moved);
      to.push({ action: "reparent", kind: entry.kind, id: entry.id, parentId: current });
      return true;
    }
    //: A map branch deleted with Delete (`wbMapDeleteSubtree`): the rows the
    //: server handed back, restored parents first with their parent links
    //: remapped, which a "delete" entry's flat POST cannot do. Its reverse
    //: deletes the restored tops again and keeps what came back for the redo.
    if (entry.action === "subtree") {
      const tops = await wbMapRestoreRows(entry.rows, entry.links || []);
      await wbRefreshMapState();
      to.push({ action: "unsubtree", kind: "object", ids: tops });
      return true;
    }
    if (entry.action === "unsubtree") {
      const rows = [];
      const links = [];
      for (const id of entry.ids) {
        if (!(wbState.objects || []).some((o) => o.id === id)) continue;
        const res = await apiJson(`/whiteboard/objects/${id}`, { method: "DELETE" });
        rows.push(...(Array.isArray(res.deleted) ? res.deleted : []));
        links.push(...(Array.isArray(res.links) ? res.links : []));
      }
      const gone = new Set(rows.map((row) => row.id));
      const goneLinks = new Set(links.map((link) => link.id));
      wbState.objects = (wbState.objects || []).filter((o) => !gone.has(o.id));
      wbState.sketches = (wbState.sketches || []).filter((k) => !goneLinks.has(k.id));
      if (wbSelectedItem && gone.has(wbSelectedItem.id)) clearWbSelection();
      to.push({ action: "subtree", kind: "object", rows, links });
      return true;
    }
    //: The note behind a card: its words as they were, or the note a branch
    //: card made, to the recycle bin and back (never purged from here).
    if (entry.action === "note") {
      const current = await apiJson(`/entries/${entry.entryId}`);
      await apiJson(`/entries/${entry.entryId}`, { method: "PUT", body: JSON.stringify({ content: entry.content }) });
      to.push({ action: "note", entryId: entry.entryId, content: current.content });
      await loadEntries();
      return true;
    }
    if (entry.action === "noteMade" || entry.action === "noteBinned") {
      const made = entry.action === "noteMade";
      await apiJson(made ? `/entries/${entry.entryId}` : `/entries/${entry.entryId}/restore`, { method: made ? "DELETE" : "POST" });
      to.push({ action: made ? "noteBinned" : "noteMade", entryId: entry.entryId });
      await loadEntries();
      return true;
    }
    //: The map's layout, numbering and theme as they were (`wbHistoryFromRows`):
    //: a theme is a patch, so a field the old theme lacked is sent as null.
    //: A board's look (decision 24): put back whole, every field the step
    //: did not have sent as null.
    if (entry.action === "layers") {
      const current = wbState.layers || [];
      await wbSaveNamedLayers(entry.before || [], { undo: false });
      to.push({ action: "layers", before: current });
      return true;
    }
    if (entry.action === "background") {
      const current = { ...wbBoardBackground() };
      const was = entry.before || {};
      await wbSetBackground({ color: was.color ?? null, image: was.image ?? null, sticky_fold: was.sticky_fold ?? null, rough: was.rough ?? null, defaults: was.defaults ?? null, ...Object.fromEntries(["grid_size", "grid_color", "guides", "page_view", "shadow_default", "paper", "orientation", "paper_w", "paper_h"].map((k) => [k, was[k] ?? null])) }, { undo: false });
      to.push({ action: "background", before: current });
      return true;
    }
    if (entry.action === "board") {
      const current = wbBoardSettings();
      if (current && entry.before) {
        const was = JSON.parse(entry.before);
        const now = JSON.parse(current);
        const theme = {};
        for (const key of new Set([...Object.keys(was.theme), ...Object.keys(now.theme)])) theme[key] = was.theme[key] ?? null;
        await apiJson(`/whiteboard/boards/${window.currentBoardId}`, {
          method: "PUT",
          body: JSON.stringify({ layout: was.layout ?? undefined, numbered: was.numbered, theme }),
        });
        await wbRefreshMapState();
        wbApplyMapFont();
        wbSyncMapChrome();
      }
      to.push({ action: "board", before: current });
      return true;
    }
    const { base, list, payload: toPayload } = WB_KIND_INFO[entry.kind];
    if (entry.action === "delete") {
      // This entry means "bring back what was deleted". Applying it recreates
      // the item; reversing *that* is deleting the newly-recreated one again.
      const restored = await apiJson(base, { method: "POST", body: JSON.stringify(wbKeepOwnLayer(entry.kind, entry.payload)) });
      wbState[list].push(restored);
      //: **A map topic comes back under its parent, and as itself** (INBOX
      //: 537): the flat create cannot write `parent_id` (only `/move` can, with
      //: its cycle check), so a redone topic came back loose; and the new id
      //: is handed to every history step that still names the old one.
      if (entry.parentId != null && restored.board_id != null) {
        const placed = await apiJson(`/whiteboard/boards/${restored.board_id}/nodes/${restored.id}/move`, {
          method: "PUT",
          body: JSON.stringify({ parent_id: entry.parentId }),
        });
        Object.assign(restored, placed);
      }
      //: And its links with it, re-ended on the new id (INBOX 537): the server
      //: drops a deleted item's links, so a card, box or shape came back alone.
      const linkIds = await wbRestoreLinks(entry.links, entry.kind, entry.oldId, restored.id);
      if (entry.kind === "sketch") await wbFmtState.linkEdge?.reattach(entry.edgeEnds, restored.id);
      if (entry.oldId != null) {
        const ids = new Map([[entry.oldId, restored.id]]);
        const none = new Map();
        wbRemapUndoIds(entry.kind === "object" ? ids : none, entry.kind === "sketch" ? new Map([...ids, ...linkIds]) : linkIds, entry.kind === "node" ? ids : none);
      }
      //: Already in the new id space: a later item's translation must not touch it.
      const made = { action: "create", kind: entry.kind, id: restored.id };
      wbRemapSeen.set(made, new Set(["id"]));
      to.push(made);
    } else if (entry.action === "move") {
      // A drag, resize, or nudge's own undo: asked for directly ("account
      // for resizes, rotates, positional movement"). `before` is the item's
      // whole payload (x/y, width/height, a sketch's own `d`) as it was right
      // before the change, so this one action type covers move and resize
      // both: restoring is the same PUT either way, just a different set of
      // fields differing from the current row. Mirrors the delete/create pair
      // above: capture the *current* state before overwriting it, so the
      // pushed reverse entry can undo the undo.
      const item = wbState[list].find((i) => i.id === entry.id);
      if (!item) return true; // stale: nothing to restore, but the stack still advances
      const current = toPayload(item);
      const restored = await apiJson(`${base}/${entry.id}`, { method: "PUT", body: JSON.stringify(entry.before) });
      Object.assign(item, restored);
      to.push({ action: "move", kind: entry.kind, id: entry.id, before: current });
    } else {
      // This entry means "remove what was created". The item's current data
      // has to be captured *before* deleting it, once gone, nothing else
      // remembers what it looked like, and the reverse of this reverse (a
      // future redo/undo) needs a real payload to recreate it from, not a
      // blank one.
      const item = wbState[list].find((i) => i.id === entry.id);
      //: Already gone (taken with its parent's branch a step earlier): nothing
      //: to delete, and a DELETE would 404 and stop the rest of the batch.
      if (!item) return true;
      const payload = toPayload(item);
      const links = wbLinksTouching(entry.kind, entry.id);
      //: Marked first: a save of this item still on its way (a topic just added, then undone) is dropped by
      //: `wbSaveObject` instead of racing the DELETE into a stale write (L-whiteboard-18).
      item._undoing = true;
      let res;
      try {
        res = await apiJson(`${base}/${entry.id}`, { method: "DELETE" });
      } catch (err) {
        delete item._undoing;
        throw err;
      }
      //: **A topic that has gained a branch since goes, and comes back, whole**
      //: (INBOX 537). The server takes a map topic's subtree with it; this step
      //: used to keep only the one row, so the branch under it was lost for good.
      const rows = entry.kind === "object" && Array.isArray(res?.deleted) ? res.deleted : [];
      if (rows.length > 1) {
        const gone = new Set(rows.map((row) => row.id));
        wbState.objects = wbState.objects.filter((o) => !gone.has(o.id));
        wbForgetLinks(res.links);
        if (item.parent_id != null) wbUndoParents.push(item.parent_id);
        to.push({ action: "subtree", kind: "object", rows, links: Array.isArray(res.links) ? res.links : [] });
        return true;
      }
      wbState[list] = wbState[list].filter((i) => i.id !== entry.id);
      wbForgetLinks(links);
      //: A topic made by Tab or Enter and taken back leaves its parent as the
      //: selection (below, in `wbUndo`): the person was on that topic a moment
      //: before they made the new one, and nothing selected would drop them off
      //: the keyboard path the map is built on.
      if (entry.kind === "object" && item && item.parent_id != null) wbUndoParents.push(item.parent_id);
      to.push({ action: "delete", kind: entry.kind, payload, oldId: entry.id, parentId: item.parent_id ?? null, links });
    }
    return true;
  }

  // Reverses the single most recent create or delete, a sketch stroke, a
  // shape, a link, or a note card. Asked for implicitly by adding an eraser:
  // a tool whose whole job is deleting things you swipe over needs a safety
  // net more than any other control on this toolbar.
  //: On `window` because app.js owns the Ctrl+Z chord for the whole app and
  //: hands it here while a board is open (see the board's keydown handler).
  window.wbUndo = wbUndo;
  window.wbRedo = wbRedo;
  //: And whether there is anything on either stack, so the status bar's two
  //: buttons can be lit or dimmed by the board's own history rather than by the
  //: app's, which knows nothing about a shape that moved.
  window.wbCanUndo = () => (wbHistoryFor(), wbUndoStack.length > 0);
  window.wbCanRedo = () => (wbHistoryFor(), wbRedoStack.length > 0);



  //: A topic or box being typed in is finished first, as its own step, so an
  //: Undo never runs under an open editor that saves into the board afterwards.
  function wbCommitOpenEdit() {
    const active = document.activeElement;
    if (active?.isContentEditable && active.closest("#wb-html-layer")) active.blur();
  }

  //: **A box still being typed in is saved when the page goes** (boardfix-1108):
  //: the save runs on blur, and a reload or a closed tab does not blur, so words
  //: typed into an open sticky, text box or topic never left (measured: type,
  //: reload, the server kept the old text and no write was sent). `pagehide`
  //: finishes the edit and `wbSaveObject` sends with `keepalive` while
  //: `wbCommitOpenEdit.leaving` is set (a property, not a new shared name: the global-scope ratchet), so the request outlives the page. Not
  //: `visibilitychange`: switching tabs must not end an edit in progress.
  window.addEventListener("pagehide", () => {
    wbCommitOpenEdit.leaving = true;
    try {
      wbCommitOpenEdit();
    } finally {
      setTimeout(() => { wbCommitOpenEdit.leaving = false; }, 0);
    }
  });

  async function wbUndo() {
    await wbDeleting.settled();
    wbHistoryFor();
    wbCommitOpenEdit();
    wbUndoParents = [];
    try {
      if (!(await wbApplyHistoryEntry(wbUndoStack, wbRedoStack))) return;
      wbUpdateUndoRedoButtons();
      //: C32: no labels on a board's history, so the notice names the place; "info" shows even when muted.
      toast("Undone: last change on this board", "info");
      if (wbIsMap()) {
        const parentId = wbUndoParents.find((id) => (wbState.objects || []).some((o) => o.id === id));
        if (parentId != null) selectWbItem("object", parentId);
      }
      wbScheduleRender();
    } catch {
      toast(voiceLine("failed", { what: "undo that" }), true);
    }
  }

  // Reapplies whatever the most recent undo took back, asked for directly
  // (`wbUndoStack` "exists; nothing analogous does"). Pushes the reverse onto
  // `wbUndoStack`, so undo/redo/undo/redo keeps working rather than only
  // ever reversing once.
  async function wbRedo() {
    await wbDeleting.settled();
    wbHistoryFor();
    wbCommitOpenEdit();
    try {
      if (!(await wbApplyHistoryEntry(wbRedoStack, wbUndoStack))) return;
      wbUpdateUndoRedoButtons();
      toast("Redone: last change on this board", "info");
      wbScheduleRender();
    } catch {
      toast(voiceLine("failed", { what: "redo that" }), true);
    }
  }

  // Images and text boxes, the two new object kinds, created here and
  // rendered by `renderWbObjects`. One shared creator (a POST plus the usual
  // create-undo-entry dance every other whiteboard item already does) rather
  // than a copy per kind, since only the `kind`/`data` differ.
  //: Made on top of its own band of the stack (`wbStackNewZ`; a frame under
  //: the frames already there), so what was just made is what is on top.
  async function wbCreateObject(kind, data, x, y, width, height, z = wbStackNewZ("object", { kind }), extra = null) {
    if (kind === "text") data = wbFmtState.board?.withDefaults("text", data) ?? data;
    //: `extra`: row fields beside the data (an import's `rotation`).
    const body = { kind, data, board_id: window.currentBoardId, x, y, z, width, height, ...(extra || {}) };
    try {
      const created = await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify(body) });
      wbState.objects = wbState.objects || [];
      wbState.objects.push(created);
      wbPushUndo({ action: "create", kind: "object", id: created.id });
      wbScheduleRender();
      await refreshBoardList();
      return created;
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "add that to the board" }), true);
      return null;
    }
  }

  //: **A sticky note is a text box that already looks like one** (PLAN.md W3).
  //: Same object kind, same editor, same properties panel, the difference is
  //: three defaults (a yellow fill, a warm border, a larger face) and a size
  //: that fits a thought rather than a paragraph. Kept as `kind: "text"` on
  //: purpose: no schema change, and every text feature (copy style, AI, undo)
  //: works on a sticky the day it exists.
  //: `box`, when given, is the rectangle a press-drag drew with the tool
  //: (`wbPlaceBox`): the note takes that size and corner instead of the default
  //: one centred on the click.
  //: **Paper, lifted, with a folded corner** (the owner, 2026-10-10: "there's
  //: no real way to visually distinguish between a text box and a note. and
  //: note appearances arent changable"). `sticky: true` says it is one; its
  //: colour is `bg`, one of the papers below from its bar's swatches (or any
  //: colour from the "..." menu). The papers are light, so the one ink reads
  //: on all of them (measured on `wbstickylook.js`).
  const WB_STICKY_PAPERS = [
    { value: "#fff4a3", label: "Yellow" },
    { value: "#ffd8a8", label: "Orange" },
    { value: "#ffc9de", label: "Pink" },
    { value: "#e5d4ff", label: "Purple" },
    { value: "#cfe8ff", label: "Blue" },
    { value: "#d3f5c4", label: "Green" },
    { value: "#ececec", label: "Grey" },
  ];

  //: A sticky, and one made before the flag existed: those were the yellow
  //: paper with the warm edge `wbCreateSticky` gave every one of them.
  //: Whether a sticky's corner is drawn folded (INBOX 792): the note's own
  //: `fold`, else the board's default (`background.sticky_fold`, folded unless
  //: it says `false`).
  function wbStickyFolds(item) {
    return item?.data?.fold ?? wbBoardBackground().sticky_fold !== false;
  }

  function wbIsSticky(item) {
    const data = item?.data || {};
    if (data.sticker) return false;
    return Boolean(data.sticky) || (data.border_color === "#e8d56a" && Boolean(data.bg));
  }

  //: **Enter, for someone with no pointer.** A text box, sticky or frame was
  //: only ever placed by a click, so N then Enter did nothing and a selected
  //: sticky could not be written in without a double-click (WCAG 2.1.1; Figma,
  //: tldraw and Excalidraw all take Enter). With a placing tool held, Enter
  //: drops the thing at the middle of the view; with one text box or sticky
  //: selected, Enter puts the caret at the end of its words. Returns whether it
  //: acted, so the key keeps its other meanings otherwise. Only from the
  //: canvas itself: a focused toolbar button's Enter is its own.
  function wbKeyboardEnter() {
    const focus = document.activeElement;
    if (focus && focus !== document.body && focus.id !== "whiteboard-container") return false;
    const place = { text: wbCreateTextBox, sticky: wbCreateSticky, frame: wbCreateFrame }[window.currentTool];
    if (place) {
      const [x, y] = wbViewCentre();
      place(x, y);
      return true;
    }
    const lone = wbSelectedItem?.kind === "object" && wbMultiSelection.size <= 1 ? wbFindItem("object", wbSelectedItem.id) : null;
    if (!lone || lone.kind !== "text" || lone.data?.sticker || wbIsLocked("object", lone)) return false;
    const words = document.querySelector(`.wb-object[data-id="${lone.id}"] .wb-text-content`);
    if (!words) return false;
    wbBeginTextEdit(words);
    const range = document.createRange();
    range.selectNodeContents(words);
    range.collapse(false);
    window.getSelection()?.removeAllRanges();
    window.getSelection()?.addRange(range);
    return true;
  }

  async function wbCreateSticky(x, y, box = null, like = null) {
    const at = box || { x: x - 90, y: y - 70, w: 180, h: 140 };
    const paper = like?.data || {};
    const created = await wbCreateObject(
      "text",
      { content: "", sticky: true, bg: paper.bg || WB_STICKY_PAPERS[0].value, color: paper.color || "#2a2a1f", font_size: paper.font_size || 16 },
      at.x, at.y, at.w, at.h
    );
    if (!created) return;
    wbSelectToolRef?.("select");
    requestAnimationFrame(() => {
      const el = document.querySelector(`.wb-object[data-id="${created.id}"] .wb-text-content`);
      if (el) wbBeginTextEdit(el);
    });
  }

  //: **The paper is one dropdown button, not a row of seven chips** (the owner,
  //: INBOX 1300 C18: "condense the colour options into like a dropdown panel
  //: ... for the whiteboard"). It shows the current paper and opens the same
  //: popover the colour wells use (`wbOpenPaperMenu`, whiteboard-format.js);
  //: the colours are `WB_STICKY_PAPERS`, set through the CSSOM (the CSP refuses
  //: an inline `style=`).
  function wbFillPaperPicker(group, item) {
    let button = group.querySelector(".wb-paper-trigger");
    if (!button) {
      button = document.createElement("button");
      button.type = "button";
      button.className = "ghost small wb-paper-trigger";
      button.setAttribute("aria-haspopup", "dialog");
      button.setAttribute("aria-expanded", "false");
      button.title = "Note colour";
      const dot = document.createElement("span");
      dot.className = "wb-swatch-dot";
      dot.setAttribute("aria-hidden", "true");
      const words = document.createElement("span");
      words.textContent = "Paper";
      const caret = document.createElement("i");
      caret.className = "ph ph-caret-down";
      caret.setAttribute("aria-hidden", "true");
      button.append(dot, words, caret);
      button.addEventListener("click", () => wbOpenPaperMenu(button));
      group.appendChild(button);
    }
    const now = String(item.data.bg || WB_STICKY_PAPERS[0].value).toLowerCase();
    const paper = WB_STICKY_PAPERS.find((p) => p.value === now);
    button.dataset.paper = now;
    button.firstElementChild.style.setProperty("--swatch", now);
    button.setAttribute("aria-label", `Note colour: ${paper ? paper.label : "custom"}`);
  }

  //: Every selected sticky takes the paper, one undo step each, as the
  //: "..." menu's Background does for one.
  async function wbSetStickyPaper(value) {
    //: A key is "kind:id" (`wbMultiKey`).
    const targets = wbMultiSelection.size
      ? [...wbMultiSelection].filter((key) => key.startsWith("object:")).map((key) => wbFindItem("object", Number(key.slice(7))))
      : [wbSelectedTextObjectOrNull()];
    const stickies = targets.filter((obj) => obj && wbIsSticky(obj));
    const undo = [];
    for (const obj of stickies) {
      undo.push({ action: "move", kind: "object", id: obj.id, before: WB_KIND_INFO.object.payload(obj) });
      const data = { ...obj.data, bg: value, sticky: true };
      delete data.border_color;
      obj.data = data;
    }
    await wbCommitMoves(stickies.map((item) => ({ kind: "object", item })), undo);
    wbScheduleRender();
    const group = document.querySelector('#wb-context [data-wb-ctx="paper"]');
    if (group && stickies[0]) wbFillPaperPicker(group, stickies[0]);
  }

  async function wbCreateTextBox(x, y, box = null) {
    const at = box || { x: x - 100, y: y - 40, w: 200, h: 80 };
    const created = await wbCreateObject(
      "text",
      { content: "" },
      at.x, at.y, at.w, at.h
    );
    if (!created) return;
    wbSelectToolRef?.("select");
    // The point of click-to-place is typing immediately, a text box with
    // nothing in it and no visible focus is a box nobody knows they can type
    // into. wbScheduleRender() just rebuilt the DOM, so the element has to be
    // looked up fresh rather than kept from before the render.
    requestAnimationFrame(() => {
      const el = document.querySelector(`.wb-object[data-id="${created.id}"] .wb-text-content`);
      if (el) wbBeginTextEdit(el);
    });
  }

  // whiteboard-locks.js: whiteboard-locks.js: lock and hide: the flags, the lock badges and the locked-pr (moved out, L286).
  function wbSketchData(sketch) {
    try {
      const parsed = JSON.parse(sketch?.data);
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch {
      return null;
    }
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbPaintTextContent, wbWrapTextSelection, wbRunChars, WB_RUN_SWATCHES, WB_RUN_INK, wbBulletTextLines, wbBeginTextEdit, wbRegisterEditorContexts, wbEditorSurfaceById, wbTextFormatKey, wbSelectionBarFit, wbEditedText, wbIndentEditableLines, wbTextFitHeight, wbGrowBoxToWords, wbEndTextEdit, wbItemTransform, wbSketchAngleFromCenterDeg, wbSketchLiveEls, wbAngleFromCenterDeg, wbBoardMadeStep, wbBoardPutStep, wbPushCall, wbCommitOpenEdit, wbUndo, wbRedo, wbCreateObject, WB_STICKY_PAPERS, wbStickyFolds, wbIsSticky, wbKeyboardEnter, wbCreateSticky, wbFillPaperPicker, wbSetStickyPaper, wbCreateTextBox, wbSketchData });
})();
