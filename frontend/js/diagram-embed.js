// diagram-embed.js: the diagram builder where a document is not open (1546 P5; DOCUMENTS_PLAN
// "1546 design" D6 and D7). Lazy: `LAZY_MODULES.diagramEmbed`, registered in documents-mermaid.js,
// whose `openDiagramBuilder` is the stand-in the Live figure and the board call.
//
// Three things live here and nothing else: `open` mounts the builder (diagram-builder.js, loaded on
// demand) in a dialog with the dialog head, so `panelMovable` moves and sizes it, and hands the final
// source to `onDone`; `out` is the builder's export menu (SVG, PNG, Copy as Mermaid, Copy as SVG).
// A diagram embedded with `![[name]]` and a reply's "Open as a diagram" are in mermaid-draw.js.
(() => {
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  };

  // --- export (D7) ---------------------------------------------------------------------
  //: The frame's SVG text for a source, or "" with a toast saying why.
  async function svgOf(source) {
    if (!(await ensureModule("mermaid"))) return "";
    const result = await mermaidRequest(source);
    if (!result.svg) toast(`This diagram could not be drawn. ${mermaidFailure.plain(result.error, source)}`, "info");
    return result.svg || "";
  }

  //: The SVG drawn on a canvas at twice its size. The frame's SVG holds no outside pictures and carries
  //: its own ground (mermaid-frame.js), so the canvas stays clean and the PNG reads on any page.
  async function pngOf(svg) {
    const box = /\bviewBox="([^"]+)"/.exec(svg)?.[1].trim().split(/[ ,]+/).map(Number) || [];
    const width = Math.ceil(box[2]) * 2;
    const height = Math.ceil(box[3]) * 2;
    if (!(width > 0 && height > 0 && width * height < 64e6)) return null;
    const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
    try {
      const img = new Image();
      img.src = url;
      await img.decode();
      const canvas = Object.assign(document.createElement("canvas"), { width, height });
      canvas.getContext("2d").drawImage(img, 0, 0, width, height);
      return await new Promise((done) => canvas.toBlob(done, "image/png"));
    } finally {
      URL.revokeObjectURL(url);
    }
  }

  //: The PNG on the clipboard, handed over as a promise so the click's permission is not spent while it draws. Where the
  //: browser will not copy a picture it is saved as a file, and the toast says so.
  async function copyPicture(svg, file) {
    const png = pngOf(svg);
    try {
      if (!navigator.clipboard?.write || typeof ClipboardItem === "undefined") throw 0;
      await navigator.clipboard.write([new ClipboardItem({ "image/png": png.then((blob) => blob || Promise.reject(0)) })]);
      toast("Copied the picture. Paste it into a note, a document or a chat.");
    } catch {
      const blob = await png.catch(() => null);
      if (!blob) return toast("This diagram could not be copied as a picture. Save it as SVG.", "info");
      await saveFile(`${file}.png`, blob);
      toast("This browser would not copy a picture, so it was saved as a PNG instead.");
    }
  }

  //: `how`: "svg" and "png" save a file, "picture", "mermaid" and "svgtext" copy.
  async function out(how, source, name = "diagram") {
    const text = String(source || "").trim();
    if (!text) return toast("Add a block first. There is nothing to export yet.");
    const file = (String(name).trim() || "diagram").replace(/[\\/:*?"<>|]+/g, "-").slice(0, 80);
    if (how === "mermaid") return void (await copyToClipboard(source));
    const svg = await svgOf(source);
    if (!svg) return;
    if (how === "picture") return void (await copyPicture(svg, file));
    if (how === "svgtext") return void (await copyToClipboard(svg));
    if (how === "svg") return void (await saveFile(`${file}.svg`, new Blob([svg], { type: "image/svg+xml" })));
    const png = await pngOf(svg).catch(() => null);
    if (!png) return toast("This diagram could not be saved as a picture. Save it as SVG.", "info");
    await saveFile(`${file}.png`, png);
  }

  //: A saved diagram by its document id (the shelf's menu), exported as `out` does.
  async function outDoc(id, how) {
    const doc = await apiJson(`/documents/${id}`).catch(() => null);
    if (!doc) return toast("This diagram could not be opened.", "info");
    return out(how, doc.content, doc.title);
  }

  // --- Save to Library (R9c, 1621 D4) ---------------------------------------------------
  //: The whole fence round the lines `diagramModel.fence` found: from its opening mark to the end of its closing line.
  function swapRange(text, at) {
    const end = text.indexOf("\n", at.to + 1);
    return { from: text.lastIndexOf("\n", at.from - 2) + 1, to: end < 0 ? text.length : end };
  }

  //: Makes the `.mmd` row; the toast button runs `offer` to link its source. The random tail keeps `![[Title]]` unique.
  async function save(source, offer = null) {
    if (offer?.fence) {
      const [view, fenceSource, near] = offer.fence;
      offer = { label: "Link the fence", run: (row) => {
        const text = docStr(view.state.doc);
        const at = diagramModel.fence(text, fenceSource, Math.min(near, text.length));
        if (!at) return toast("That diagram is no longer in the document.", "info");
        view.dispatch({ changes: { ...swapRange(text, at), insert: `![[${row.title}]]` }, userEvent: "input.diagram" });
      } };
    }
    const text = String(source || "").trim();
    if (!text) return toast("Add a block first.");
    const title = `Diagram ${new Date().toISOString().slice(0, 16).replace("T", " ")} ${Math.random().toString(36).slice(2, 6)}`;
    const made = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title, content: `${text}\n`, file_type: "mmd" }) }).catch(() => (toast("Not saved. Try again.", "info"), null));
    if (!made) return;
    offerCreateUndo(made);
    const said = `Saved “${made.title || title}” to the Library.`;
    if (offer) toastAction(said, offer.label, () => offer.run(made), { ms: 12000 });
    else toast(said);
    return made;
  }

  //: A board object gains the row's id: one Undo step.
  async function link(d, row, source) {
    wbPushUndo({ action: "move", kind: "object", id: d.id, before: WB_KIND_INFO.object.payload(d) });
    d.data = { ...d.data, mermaid: String(source).trim(), diagram_id: row.id };
    delete d._wbGone;
    await wbSaveObject(d);
    wbScheduleRender();
    wbAnnounce("Diagram linked.");
  }

  //: The look (DD-13, 1107) is two front matter lines Mermaid reads (`config: look: handDrawn`), so the model keeps them, the document
  //: carries them and every export draws them. Another key in the front matter stays; clean takes the lines out and an empty fence with them.
  const withLook = (source, hand) => {
    const { front, rest } = diagramModel.front(String(source).replace(/\r/g, ""));
    const kept = (front[0] === "---" ? front.slice(1, front.lastIndexOf("---")) : []).filter((line) => !/^\s+look:/.test(line));
    const at = kept.findIndex((line) => /^config:\s*$/.test(line));
    const lines = hand
      ? at < 0 ? [...kept, "config:", "  look: handDrawn"] : [...kept.slice(0, at + 1), "  look: handDrawn", ...kept.slice(at + 1)]
      : kept.filter((line, i) => !(/^config:\s*$/.test(line) && !/^\s/.test(kept[i + 1] || "")));
    return (lines.length ? `---\n${lines.join("\n")}\n---\n` : "") + rest;
  };
  //: end withLook

  // --- the dialog (D6) ----------------------------------------------------------------
  const STARTS = { flowchart: "flowchart TD", mindmap: "mindmap\n  root((Topic))", timeline: "timeline\n  title Timeline", sequence: "sequenceDiagram" };

  //: `{source, kind, title, shapes, named, onDone(source, changed, name)}`. `named` adds a title field: the new document's name and the exports' file name. `kind` names the blank diagram to start
  //: when there is no source. `shapes` is a function that receives the source and makes board shapes
  //: of it (Turn into shapes). `existing` is `{pick, open}` for the door. `offer` is what Save may link. Done calls `onDone` once; Cancel, Escape and the X call nothing, after
  //: asking when there are changes.
  async function open({ source = "", kind = "flowchart", title = "Edit diagram", shapes = null, offer = null, onDone = null, existing = null, named = false } = {}) {
    if (!(await ensureModule("diagramBuilder"))) return toast("The block editor did not load. Try again.", "info");
    const first = String(source || "").trim() ? String(source) : STARTS[kind] || STARTS.flowchart;
    const history = [first];
    let at = 0;
    let closing = false;
    //: The overlay recipe, not a native <dialog>: the sheets, menus and pickers the builder opens are
    //: ordinary overlays, and a modal <dialog> sits above them all (measured: a phone's ... sheet hidden under it).
    //: Its head is `dialogHead`'s `.dialog-head`, so `panelMovable` moves and sizes the card by it.
    const overlay = el("div", "modal-overlay confirm-overlay");
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", title);
    const dialog = el("div", "card modal-card space-dialog dgm-dialog");
    const returnFocus = document.activeElement;
    const host = el("div", "dgm-host");
    //: The title (DD-12, 1107): what a new diagram document is called and what its exports are named; blank keeps the dialog's title.
    const titleField = named ? el("input", "dgm-title") : null;
    const field = el("textarea", "dgm-source");
    field.spellcheck = false;
    field.setAttribute("aria-label", "Mermaid source");
    field.value = first;
    //: Line numbers beside the text, the error line marked (DD-5, 1107). The field does not wrap, so a number sits on its own line.
    field.setAttribute("wrap", "off");
    const srcwrap = el("div", "dgm-srcwrap");
    const gutter = el("div", "dgm-gutter");
    gutter.setAttribute("aria-hidden", "true");
    srcwrap.append(gutter, field);
    const number = () => {
      const bad = Number(field.dataset.errorLine) || 0;
      const all = Array.from({ length: field.value.split("\n").length }, (_, i) => i + 1);
      gutter.replaceChildren(...(bad && bad <= all.length ? [all.slice(0, bad - 1).map((n) => `${n}\n`).join(""), el("span", "dgm-gutter-bad", String(bad)), all.slice(bad).map((n) => `\n${n}`).join("")] : [all.join("\n")]));
      gutter.scrollTop = field.scrollTop;
    };
    field.addEventListener("scroll", () => (gutter.scrollTop = field.scrollTop));
    field.addEventListener("dgmerror", number);
    number();
    const io = {
      get name() { return titleField?.value.trim() || title; },
      set: (next) => {
        const kind = diagramModel.builder.kindOf(history[at]);
        history.length = at + 1;
        history.push(next);
        at = history.length - 1;
        if (field.value !== next) (field.value = next), number();
        //: A press on another kind (diagram-kindbar.js) only sets the source; the pane has to be drawn for it. The page gets
        //: this through the document; a block gesture draws its own pane, so only a change of kind shows again (DD-1).
        if (diagramModel.builder.kindOf(next) !== kind) show();
      },
      undo: () => at > 0 && (at -= 1, apply()),
      redo: () => at < history.length - 1 && (at += 1, apply()),
      menu: [
        ...(shapes ? [makeMenuItem("ph:shapes Turn into shapes", "Replace it with shapes and connectors you can move one by one", () => (leave(), shapes(history[at])))] : []),
        //: The door opens on a drawn starter (DD-3b, 1107), so a blank page is one press away, and Undo brings the starter back.
        makeMenuItem("ph:eraser Clear", "Start again from an empty diagram of this kind. Undo brings this one back", () => (io.set(`${STARTS[diagramModel.builder.kindOf(history[at])] || STARTS.flowchart}\n`), apply())),
        makeMenuItem("ph:pencil-line Hand-drawn look", "Draw the picture as if sketched by hand. Kept in the diagram's own text; Undo takes it back", () => (io.set(withLook(history[at], true)), apply())),
        makeMenuItem("ph:rectangle Clean look", "Draw the picture with straight, even lines again", () => (io.set(withLook(history[at], false)), apply())),
        makeMenuItem("ph:books Save to Library", "Keep it in the Library to show it with ![[name]]", () => save(history[at], offer?.link ? { label: "Link this diagram", run: (row) => link(offer.link, row, history[at]) } : offer)),
      ],
    };
    const apply = () => {
      field.value = history[at];
      number();
      show();
    };
    //: The pane on show, for the keys sheet (`?`, the Keys chip).
    let pane = null;
    const show = () =>
      diagramModel.builder.show(host, io, history[at]).then((S) => {
        pane = S;
        for (const name of ["canvas", "blocks"]) seg.querySelector(`[data-view="${name}"]`).disabled = Boolean(S?.plain);
        if (S?.plain && dialog.dataset.view !== "source") view("source");
        return S;
      });
    const view = (name) => {
      dialog.dataset.view = name;
      if (name !== "source") host.dataset.dgmLayout = name;
      for (const b of seg.children) {
        b.classList.toggle("active", b.dataset.view === name);
        b.setAttribute("aria-pressed", String(b.dataset.view === name));
      }
      if (name === "source") field.focus();
    };
    const seg = el("div", "seg dgm-views");
    seg.setAttribute("role", "group");
    seg.setAttribute("aria-label", "Diagram view");
    for (const [name, label] of [["canvas", "Canvas"], ["blocks", "Blocks"], ["source", "Source"]]) {
      const b = smallButton(label, { canvas: "The picture, with the blocks beside it", blocks: "The diagram as blocks", source: "The diagram as text, with its picture" }[name], () => view(name));
      b.dataset.view = name;
      seg.append(b);
    }
    let timer = 0;
    //: What was typed a moment ago becomes its own history step now, so Ctrl+Z in the text undoes it and a block edit alike (DD-5).
    const flush = () => {
      clearTimeout(timer);
      if (field.value !== history[at]) io.set(field.value);
    };
    field.addEventListener("input", () => {
      number();
      clearTimeout(timer);
      timer = setTimeout(() => {
        flush();
        show();
      }, 250);
    });
    //: Tab is two spaces, on every selected line when the selection spans lines; Shift+Tab takes them back. Escape is the way out (below).
    field.addEventListener("keydown", (event) => {
      if (!(event.key === "Tab" && !event.ctrlKey && !event.metaKey && !event.altKey)) return;
      event.preventDefault();
      const { value, selectionStart: from, selectionEnd: to } = field;
      const start = value.lastIndexOf("\n", from - 1) + 1;
      if (!event.shiftKey && from === to) field.setRangeText("  ", from, to, "end");
      else {
        const block = value.slice(start, to).split("\n");
        const next = block.map((line) => (event.shiftKey ? line.replace(/^ {1,2}/, "") : `  ${line}`));
        field.setRangeText(next.join("\n"), start, to, "select");
        field.setSelectionRange(from === start ? start : Math.max(start, from + next[0].length - block[0].length), start + next.join("\n").length);
      }
      field.dispatchEvent(new Event("input"));
    });
    const onKey = (event) => {
      if (event.key !== "Escape" || activeOverlay() !== overlay) return;
      //: Tab indents in the text, so Escape leaves it for the views; the next Escape closes the window (DD-5).
      if (event.target === field) {
        event.preventDefault();
        event.stopPropagation();
        return seg.querySelector('[data-view="source"]').focus();
      }
      //: A menu or an inline field takes its own Escape first; the dialog closes on the next one.
      if (document.querySelector(".action-menu:not(.hidden), .help-popover:not(.hidden)") || event.target.closest?.("input, [contenteditable]")) return;
      event.preventDefault();
      event.stopPropagation();
      finish(false);
    };
    const leave = () => {
      closing = true;
      clearTimeout(timer);
      document.removeEventListener("keydown", onKey, true);
      overlay.remove();
      if (returnFocus?.isConnected) returnFocus.focus?.();
    };
    //: True when leaving may go ahead: nothing changed, or the person confirmed they do not want the changes.
    const mayDiscard = async () => history[at] === first || (await confirmDialog("Close without keeping your changes to this diagram?", { confirmLabel: "Discard changes", cancelLabel: "Keep editing" }));
    const finish = async (done) => {
      if (closing) return;
      if (!done && !(await mayDiscard())) return;
      leave();
      if (done && onDone) onDone(history[at], history[at] !== first, titleField ? titleField.value.trim() : "");
    };
    const foot = el("div", "row right space-dialog-actions");
    const cancel = smallButton("Cancel", "Close without keeping changes", () => finish(false));
    const go = smallButton("Done", "Keep the diagram", () => finish(true), false);
    go.classList.add("accent");
    //: The door's dialog also opens a diagram that exists (1679 slice 9): `existing.pick()` answers a row or nothing, `existing.open(row)` shows it.
    const known = existing ? smallButton("ph:folder-open Open an existing diagram", "Leave this one and open a diagram you already made", async () => {
      const row = await existing.pick();
      //: Opening another diagram leaves this one, so it asks as Cancel does (a reviewer found it dropped edits silently).
      if (!row || closing || !(await mayDiscard())) return;
      leave();
      existing.open(row);
    }) : null;
    //: Help in reach (DD-7, 1107): every key in one sheet, from a chip that is always there, from `?` anywhere in the dialog
    //: outside a field, and from the ... menu; the '?' by the title says what the window is and offers the Guide's topic.
    const keys = () => pane && diagramModel.builder.styleDo(pane, "shortcuts");
    const chip = smallButton("ph:keyboard Keys", "Every key in this editor (?). F6 leaves the blocks", keys);
    chip.classList.add("dgm-keychip");
    if (known) {
      known.classList.add("dgm-known");
      known.setAttribute("aria-label", "Open an existing diagram");
    }
    foot.append(seg, ...(known ? [known] : []), chip, cancel, go);
    //: On a phone the views are the sheet's top row, not the foot's first (DD-6, 1107): the foot is one row of Keys, Cancel and Done.
    const viewbar = el("div", "dgm-viewbar");
    const phone = matchMedia("(max-width: 599.98px)");
    const place = () => (phone.matches ? viewbar : foot).prepend(seg);
    phone.addEventListener("change", place);
    place();
    const head = dialogHead(title, () => finish(false));
    const help = el("button", "icon-only ghost small graph-help-toggle");
    help.type = "button";
    help.title = "About this editor";
    help.setAttribute("aria-label", "About this editor");
    help.setAttribute("data-help-for", "dgm-dialog-help");
    help.setAttribute("aria-controls", "dgm-dialog-help");
    help.setAttribute("aria-expanded", "false");
    setLabel(help, "ph:question");
    const helpBody = el("div", "help-body hidden");
    helpBody.id = "dgm-dialog-help";
    helpBody.setAttribute("role", "dialog");
    helpBody.setAttribute("aria-label", "About this editor");
    helpBody.append(el("p", "", "Draw with blocks and the picture follows. Press N to add a box, Tab on the last box to add one joined to it, Enter to name it, F6 leaves the blocks, Ctrl+Enter keeps the diagram and ? lists every key."), atlasSuggestion("How do I make a diagram?", "Ask about making a diagram"));
    head.querySelector(".dialog-head-title").after(help);
    dialog.append(helpBody);
    const body = el("div", "dgm-dialog-body");
    body.append(srcwrap, host);
    let titlebar = null;
    if (titleField) {
      titleField.type = "text";
      titleField.maxLength = 80;
      titleField.placeholder = "Name it, or leave blank to date it";
      titleField.setAttribute("aria-label", "Diagram title");
      titleField.addEventListener("keydown", (event) => event.key === "Escape" && (event.preventDefault(), seg.querySelector(".active")?.focus()));
      titlebar = el("label", "dgm-titlebar");
      titlebar.append(el("span", "muted", "Title"), titleField);
    }
    dialog.append(head, ...(titlebar ? [titlebar] : []), viewbar, body, foot);
    document.addEventListener("keydown", onKey, true);
    wireBackdropClose(overlay, () => finish(false));
    //: Ctrl+Z in the blocks or the text steps the source history, as it does in a diagram document.
    dialog.addEventListener("keydown", (event) => {
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "z") return;
      event.preventDefault();
      if (event.target === field) flush();
      (event.shiftKey ? io.redo : io.undo)();
    });
    //: Ctrl+Enter keeps the diagram from anywhere in the window (the other route to Done is 15 Tabs).
    dialog.addEventListener("keydown", (event) => {
      if (!((event.ctrlKey || event.metaKey) && event.key === "Enter") || event.altKey) return;
      event.preventDefault();
      finish(true);
    });
    //: `?` from anywhere in the dialog but a text field; a block's own handler has taken it already (and said so by `defaultPrevented`).
    dialog.addEventListener("keydown", (event) => {
      if (event.key !== "?" || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || event.target.closest?.("input, textarea, select, [contenteditable]")) return;
      event.preventDefault();
      keys();
    });
    overlay.append(dialog);
    document.body.append(overlay);
    initHelpToggles(dialog);
    view("canvas");
    const S = await show();
    //: Focus goes into the dialog, to the first step or block (R6.5): it stayed on the button behind, and the first Tab reached Close.
    //: A starter's first box is selected and focused, so Enter names it, Tab adds the next (DD-3).
    const firstBox = host.querySelector(".dgm-block");
    if (firstBox && S && !S.k) diagramModel.builder.select(S, firstBox.dataset.key, true);
    else (host.querySelector(".dgm-steps button, .dgm-block[tabindex='0']") || dialog.querySelector(".dgm-pane") || dialog).focus?.({ preventScroll: true });
    return dialog;
  }

  diagramModel.embed = { open, out, outDoc, save, swapRange, link };
})();
