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

  //: Ctrl+Z and Ctrl+Shift+Z in the dialog. The press is the dialog's whole: stopPropagation keeps the app's undo (a listener on
  //: the document) from running a second step after this one when focus is on Picture, List, Source, Done or Cancel.
  //: A text field other than the source box (the title, a block's name while it is renamed) keeps the browser's own text undo:
  //: this returns before preventDefault there, so Ctrl+Z undoes the typing, not the diagram. The source box is the one field that
  //: steps the diagram's history, because its words are the source.
  function historyKey(event, field, flush, io) {
    if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "z") return;
    if (event.target !== field && (event.target.isContentEditable || event.target.closest?.("input, textarea, select"))) return;
    event.preventDefault();
    event.stopPropagation();
    if (event.target === field) flush();
    (event.shiftKey ? io.redo : io.undo)();
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
    //: The undo store is the Library's; the builder may have opened without it (INBOX 1722), so it comes in now, after the save.
    await ensureModule("library");
    offerCreateUndo(made);
    diagramModel.madeKnown?.(made);
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
    const at = kept.findIndex((line) => /^config:/.test(line));
    //: A `config:` on the key's own line is a flow mapping (`config: {theme: dark}`) the look joins inside the braces; any other value
    //: on that line cannot take a look without turning the file into two `config` keys, so it is left alone (null: the caller says so).
    const flow = at >= 0 && /^config:\s*\{.*\}\s*$/.test(kept[at]);
    if (at >= 0 && !flow && !/^config:\s*$/.test(kept[at])) return null;
    if (flow) {
      const inner = kept[at].replace(/^config:\s*\{|\}\s*$/g, "").replace(/\s*\blook:\s*\w+\s*,?/, "").replace(/^\s*,\s*|\s*,\s*$/g, "").trim();
      kept.splice(at, 1, ...(hand ? [`config: {look: handDrawn${inner ? `, ${inner}` : ""}}`] : inner ? [`config: {${inner}}`] : []));
    }
    const lines = flow ? kept
      : hand
        ? at < 0 ? [...kept, "config:", "  look: handDrawn"] : [...kept.slice(0, at + 1), "  look: handDrawn", ...kept.slice(at + 1)]
        : kept.filter((line, i) => !(/^config:\s*$/.test(line) && !/^\s/.test(kept[i + 1] || "")));
    return (lines.length ? `---\n${lines.join("\n")}\n---\n` : "") + rest;
  };
  //: end withLook

  //: The spacing (DD-13, 1109): Mermaid's default layout here is ELK, which has no spacing setting (`flowchart.nodeSpacing` and
  //: `rankSpacing` are read by dagre only: measured, a 4-box chart drew 552 x 219 whatever they said). So Compact and Roomy are three
  //: front matter lines each: `layout: dagre` and the two spacings; Normal takes them out and the default engine draws again.
  //: The gap is one number for both directions; 50 is dagre's own default, which is why neither level is 50.
  const SPACINGS = { compact: 20, roomy: 100 };
  const spacingOf = (source) => {
    const gap = /^\s+nodeSpacing:\s*(\d+)\s*$/m.exec(diagramModel.front(String(source)).front.join("\n"));
    return Object.keys(SPACINGS).find((level) => SPACINGS[level] === Number(gap?.[1])) || "normal";
  };
  const withSpacing = (source, level) => {
    const { front, rest } = diagramModel.front(String(source).replace(/\r/g, ""));
    let kept = front[0] === "---" ? front.slice(1, front.lastIndexOf("---")) : [];
    //: A `config:` with its value on the same line (a flow mapping) cannot take nested lines: left alone, the caller says so.
    if (kept.some((line) => /^config:\s*\S/.test(line))) return null;
    kept = kept.filter((line) => !/^ {4}(nodeSpacing|rankSpacing):/.test(line) && !/^ {2}layout:\s*dagre\s*$/.test(line));
    //: A `flowchart:` left with no keys under it, and a `config:` left with nothing, go too.
    const bare = (key, depth) => (line, i) => !(new RegExp(`^ {${depth}}${key}:\\s*$`).test(line) && !new RegExp(`^ {${depth + 1},}\\S`).test(kept[i + 1] || ""));
    kept = kept.filter(bare("flowchart", 2));
    kept = kept.filter(bare("config", 0));
    if (level !== "normal") {
      if (!kept.some((line) => /^config:\s*$/.test(line))) kept.push("config:");
      kept = kept.filter((line) => !/^ {2}layout:/.test(line));
      const at = kept.findIndex((line) => /^config:\s*$/.test(line));
      kept.splice(at + 1, 0, "  layout: dagre");
      let flow = kept.findIndex((line) => /^ {2}flowchart:\s*$/.test(line));
      if (flow < 0) kept.splice(at + 2, 0, "  flowchart:"), (flow = at + 2);
      kept.splice(flow + 1, 0, `    nodeSpacing: ${SPACINGS[level]}`, `    rankSpacing: ${SPACINGS[level]}`);
    }
    return (kept.length ? `---\n${kept.join("\n")}\n---\n` : "") + rest;
  };
  //: end withSpacing

  //: The line shape (R13, 1109): `config: flowchart: curve` is read by dagre only, as the spacing is: measured in Mermaid 12.2, the
  //: default ELK layout ignores `flowchart.curve` (the same paths for linear, step and none), while under `layout: dagre` linear draws
  //: straight runs, basis cubic curves and step right angles. So a shape names the engine too; Usual takes the curve out, and the
  //: engine line with it unless the spacing still needs it.
  const CURVES = { straight: "linear", curved: "basis", stepped: "step" };
  const curveOf = (source) => {
    const name = /^ +curve:[ \t]*(\w+)[ \t]*$/m.exec(diagramModel.front(String(source)).front.join("\n"))?.[1];
    return Object.keys(CURVES).find((shape) => CURVES[shape] === name) || "usual";
  };
  const withCurve = (source, shape) => {
    const { front, rest } = diagramModel.front(String(source).replace(/\r/g, ""));
    let kept = front[0] === "---" ? front.slice(1, front.lastIndexOf("---")) : [];
    if (kept.some((line) => /^config:\s*\S/.test(line))) return null;
    kept = kept.filter((line) => !/^ {4}curve:/.test(line));
    if (shape === "usual" && !kept.some((line) => /^ {4}(nodeSpacing|rankSpacing):/.test(line))) kept = kept.filter((line) => !/^ {2}layout:\s*dagre\s*$/.test(line));
    const bare = (key, depth) => (line, i) => !(new RegExp(`^ {${depth}}${key}:\\s*$`).test(line) && !new RegExp(`^ {${depth + 1},}\\S`).test(kept[i + 1] || ""));
    kept = kept.filter(bare("flowchart", 2));
    kept = kept.filter(bare("config", 0));
    if (shape !== "usual") {
      if (!kept.some((line) => /^config:\s*$/.test(line))) kept.push("config:");
      const at = kept.findIndex((line) => /^config:\s*$/.test(line));
      if (!kept.some((line) => /^ {2}layout:\s*dagre\s*$/.test(line))) kept.splice(at + 1, 0, "  layout: dagre");
      let flow = kept.findIndex((line) => /^ {2}flowchart:\s*$/.test(line));
      if (flow < 0) kept.splice(at + 2, 0, "  flowchart:"), (flow = at + 2);
      kept.splice(flow + 1, 0, `    curve: ${CURVES[shape]}`);
    }
    return (kept.length ? `---\n${kept.join("\n")}\n---\n` : "") + rest;
  };
  //: end withCurve

  //: The document's name from the Title field: nothing a `![[ ]]` link or a `Title#^id` block reference reads as syntax, and never a name
  //: another document has (links resolve to the first document of that title, so a repeat would show the earlier diagram). Blank is dated.
  const cleanTitle = (text) => String(text || "").replace(/[\[\]|#]+/g, " ").replace(/\s+/g, " ").trim();
  const freshTitle = (base, taken) => {
    let title = base;
    for (let n = 2; taken.has(title.toLowerCase()); n += 1) title = `${base} ${n}`;
    return title;
  };
  //: end freshTitle
  const documentName = async (typed) => {
    const base = cleanTitle(typed) || `Diagram ${new Date().toISOString().slice(0, 16).replace("T", " ")}`;
    const all = await apiPagedList("/documents", 200).catch(() => (typeof docs !== "undefined" && Array.isArray(docs) ? docs : []));
    return freshTitle(base, new Set(all.map((d) => String(d.title || "").trim().toLowerCase())));
  };

  // --- the kept draft (blind test 1108) ----------------------------------------------
  //: A reload with the dialog open lost everything. The document editor keeps its unsaved text on this device and offers it back
  //: the next time that document opens (documents.js `keepDocEditLocally`, `offerKeptDocEdit`); the dialog does the same, per
  //: target: `draft` is the caller's key ("doc:12", "new", "board:7") and the hash of the source it opened on is added, so two
  //: diagrams in one page keep one draft each. At most five, two weeks, 2 MB; Done and Discard forget it.
  const DRAFTS = "diagram-drafts";
  const draftsRead = () => {
    let all = {};
    try {
      all = prefs.json(DRAFTS, {}) || {};
    } catch {
      all = {};
    }
    const cutoff = Date.now() - 14 * 864e5;
    return Object.fromEntries(Object.entries(all).filter(([, d]) => d?.at > cutoff));
  };
  const draftsWrite = (all) => (Object.keys(all).length ? prefs.setJSON(DRAFTS, all) : prefs.remove(DRAFTS));
  const draftKeep = (key, draft) => {
    if (!key || String(draft.source).length > 2e6) return;
    try {
      const all = { ...draftsRead(), [key]: { ...draft, at: Date.now() } };
      const newest = Object.entries(all).sort((a, b) => b[1].at - a[1].at).slice(0, 5);
      draftsWrite(Object.fromEntries(newest));
    } catch {
      /* storage full or blocked: nothing more can be done */
    }
  };
  const draftForget = (key) => {
    try {
      const all = draftsRead();
      if (key && key in all) (delete all[key], draftsWrite(all));
    } catch {
      /* nothing kept, nothing to forget */
    }
  };
  const hashOf = (text) => {
    let h = 5381;
    for (let i = 0; i < text.length; i += 1) h = ((h * 33) ^ text.charCodeAt(i)) >>> 0;
    return h.toString(36);
  };

  // --- the dialog (D6) ----------------------------------------------------------------
  const STARTS = { flowchart: "flowchart TD", mindmap: "mindmap\n  root((Topic))", timeline: "timeline\n  title Timeline", sequence: "sequenceDiagram" };

  //: `{source, kind, title, shapes, named, onDone(source, changed, name)}`. `named` adds a title field: the new document's name and the exports' file name. `kind` names the blank diagram to start
  //: when there is no source. `shapes` is a function that receives the source and makes board shapes
  //: of it (Turn into shapes). `draft` keys the kept unsaved copy (a reload offers it back). `existing` is `{pick, open}` for the door. `offer` is what Save may link. Done calls `onDone` once; Cancel, Escape and the X call nothing, after
  //: asking when there are changes. `live` is a host's own `io` (a diagram document's): the dialog is then that diagram taken to the full
  //: screen ("Expand", `expand` below), every change goes to the host as it is made so the document saves as it always does, and Collapse,
  //: Escape and the X just close it, with nothing to keep or discard. `onClose` runs once it has closed.
  //: **One builder at a time** (the owner, 2026-11-09: "I clicked it multiple times and it didnt close"). The first press
  //: fetches the code, so a press that seemed to do nothing was pressed again and each press stacked its own dialog; an X
  //: then closed one of identical copies (measured: three presses, three dialogs, three X presses). A press while one is
  //: opening or open answers with that one and brings it forward; `leave` frees the door.
  let current = null;
  function open(options) {
    if (current) {
      current.then((dialog) => dialog?.isConnected && dialog.focus?.({ preventScroll: true }));
      return current;
    }
    const opening = mount(options);
    current = opening;
    //: A builder that did not load answers nothing, and the next press tries again.
    const free = () => current === opening && (current = null);
    opening.then((dialog) => dialog || free(), free);
    return opening;
  }

  async function mount({ source = "", kind = "flowchart", title = "Edit diagram", shapes = null, offer = null, onDone = null, existing = null, named = false, draft = "", live = null, onClose = null } = {}) {
    if (!(await ensureModule("diagramBuilder"))) return toast("The block editor did not load. Try again.", "info");
    //: Without it the Source pane is a plain field (the list is an extra, so a failed load is not an error).
    const hasComplete = await ensureModule("diagramComplete");
    const first = String(source || "").trim() ? String(source) : STARTS[kind] || STARTS.flowchart;
    const draftId = draft ? `${draft}:${hashOf(first)}` : "";
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
    dialog.tabIndex = -1;
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
    //: Long source lines fold onto the next row when asked (L304): the numbers are hidden while they do, because a
    //: number is beside its line only while lines do not wrap. Kept on the device, off by default.
    let wrapBtn = null;
    const setWrap = (on) => {
      field.setAttribute("wrap", on ? "soft" : "off");
      wrapBtn?.setAttribute("aria-pressed", String(on));
      srcwrap.classList.toggle("is-wrapped", on);
      try {
        prefs.set("dgm-source-wrap", on ? "on" : "off");
      } catch {
        // A private window can refuse storage; the fold still applies for now.
      }
    };
    const wrapRow = () => field.getAttribute("wrap") === "off"
      ? makeMenuItem("ph:text-align-left Wrap long lines", "Fold long Source lines onto the next row. Line numbers hide while lines fold", () => setWrap(true))
      : makeMenuItem("ph:arrows-out-line-horizontal Stop wrapping", "Keep each Source line on one row again, with its number", () => setWrap(false));
    if (prefs.get("dgm-source-wrap", "off") === "on") setWrap(true);
    const number = () => {
      const bad = Number(field.dataset.errorLine) || 0;
      const all = Array.from({ length: field.value.split("\n").length }, (_, i) => i + 1);
      gutter.replaceChildren(...(bad && bad <= all.length ? [all.slice(0, bad - 1).map((n) => `${n}\n`).join(""), el("span", "dgm-gutter-bad", String(bad)), all.slice(bad).map((n) => `\n${n}`).join("")] : [all.join("\n")]));
      gutter.scrollTop = field.scrollTop;
    };
    field.addEventListener("scroll", () => (gutter.scrollTop = field.scrollTop));
    field.addEventListener("dgmerror", number);
    number();
    //: Kept a moment after each change and when the page goes (a reload, a closed tab); nothing is kept for a dialog that has not changed.
    let keepTimer = 0;
    const keep = () => {
      if (closing || !draftId) return;
      const typed = titleField ? titleField.value : "";
      if (history[at] === first && !typed.trim()) return draftForget(draftId);
      draftKeep(draftId, { source: history[at], title: typed });
    };
    const keepSoon = () => (clearTimeout(keepTimer), (keepTimer = setTimeout(keep, 500)));
    window.addEventListener("pagehide", keep);
    const io = {
      get name() { return titleField?.value.trim() || title; },
      dialog: true,
      collapse: live ? () => finish(true) : null,
      set: (next) => {
        const kind = diagramModel.builder.kindOf(history[at]);
        history.length = at + 1;
        history.push(next);
        at = history.length - 1;
        if (field.value !== next) (field.value = next), number();
        keepSoon();
        live?.set(next);
        //: A press on another kind (diagram-kindbar.js) only sets the source; the pane has to be drawn for it. The page gets
        //: this through the document; a block gesture draws its own pane, so only a change of kind shows again (DD-1).
        if (diagramModel.builder.kindOf(next) !== kind) show();
      },
      undo: () => at > 0 && (at -= 1, apply(), live?.set(history[at])),
      redo: () => at < history.length - 1 && (at += 1, apply(), live?.set(history[at])),
      get menu() {
        return [
          ...(shapes ? [makeMenuItem("ph:shapes Turn into shapes", "Replace it with shapes and connectors you can move one by one", () => (leave(), shapes(history[at])))] : []),
          //: The door opens on a drawn starter (DD-3b, 1107), so a blank page is one press away, and Undo brings the starter back.
          makeMenuItem("ph:eraser Clear", "Start again from an empty diagram of this kind. Undo brings this one back", () => (io.set(`${STARTS[diagramModel.builder.kindOf(history[at])] || STARTS.flowchart}\n`), apply())),
          //: One look row, the one that is not on: the menu never says "Hand-drawn" while it is already drawn so, and it is rebuilt with every pane.
          lookRow(),
          wrapRow(),
          ...spacingRows(),
          ...curveRows(),
          makeMenuItem("ph:books Save to Library", "Keep it in the Library to show it with ![[name]]", () => save(history[at], offer?.link ? { label: "Link this diagram", run: (row) => link(offer.link, row, history[at]) } : offer)),
        ];
      },
      get canUndo() { return at > 0; },
      get canRedo() { return at < history.length - 1; },
    };
    //: A look that cannot be written (a front matter `config` this menu cannot edit) says so and changes nothing.
    const setLook = (hand) => {
      const next = withLook(history[at], hand);
      if (next === null) return toast("The front matter has a config line the menu cannot edit. Change it in Source.", "info");
      io.set(next);
      apply();
    };
    //: Normal spacing takes the engine line out, which would stop a set line shape drawing: the shape is written again after it.
    const setCurve = (shape) => {
      const next = withCurve(history[at], shape);
      if (next === null) return toast("The front matter has a config line the menu cannot edit. Change it in Source.", "info");
      io.set(next);
      apply();
    };
    function curveRows() {
      const now = curveOf(history[at]);
      const rows = { straight: ["ph:line-segment Straight lines", "Draw arrows as straight runs. Kept in the diagram's own text; Undo takes it back"], curved: ["ph:wave-sine Curved lines", "Draw arrows as smooth curves. Kept in the diagram's own text; Undo takes it back"], stepped: ["ph:path Stepped lines", "Draw arrows with right angles. Kept in the diagram's own text; Undo takes it back"], usual: ["ph:arrows-horizontal Usual lines", "Draw arrows the usual way again"] };
      return Object.keys(rows).filter((shape) => shape !== now).map((shape) => makeMenuItem(rows[shape][0], rows[shape][1], () => setCurve(shape)));
    }
    //: The spacing rows are the two levels that are not on, like the look row: Normal is the way back from either.
    const setSpacing = (level) => {
      const shape = curveOf(history[at]);
      let next = withSpacing(history[at], level);
      if (next !== null && shape !== "usual") next = withCurve(next, shape);
      if (next === null) return toast("The front matter has a config line the menu cannot edit. Change it in Source.", "info");
      io.set(next);
      apply();
    };
    function spacingRows() {
      const now = spacingOf(history[at]);
      const rows = { compact: ["ph:arrows-in-line-horizontal Compact spacing", "Draw the blocks closer together. Kept in the diagram's own text; Undo takes it back"], roomy: ["ph:arrows-out-line-horizontal Roomy spacing", "Draw the blocks further apart. Kept in the diagram's own text; Undo takes it back"], normal: ["ph:arrows-horizontal Normal spacing", "Draw the blocks at the usual distance again"] };
      return Object.keys(rows).filter((level) => level !== now).map((level) => makeMenuItem(rows[level][0], rows[level][1], () => setSpacing(level)));
    }
    function lookRow() {
      const hand = diagramModel.front(history[at]).front.some((line) => /\blook:\s*handDrawn/.test(line));
      return hand
        ? makeMenuItem("ph:rectangle Clean look", "Draw the picture with straight, even lines again", () => setLook(false))
        : makeMenuItem("ph:pencil-line Hand-drawn look", "Draw the picture as if sketched by hand. Kept in the diagram's own text; Undo takes it back", () => setLook(true));
    }
    const apply = () => {
      field.value = history[at];
      number();
      show();
    };
    //: The pane on show, for the keys sheet (`?`, the Keys chip).
    let pane = null;
    const show = () => {
      //: The pane is mounted anew, so a row pressed in the ⋯ (the look) left focus on the page; the new ⋯ takes it back (dgmlive2 1108).
      const fromMore = Boolean(document.activeElement?.closest?.(".dgm-more"));
      return diagramModel.builder.show(host, io, history[at]).then((S) => {
        pane = S;
        if (fromMore && !host.contains(document.activeElement)) host.querySelector(".dgm-more button")?.focus({ preventScroll: true });
        for (const name of ["canvas", "blocks"]) seg.querySelector(`[data-view="${name}"]`).disabled = Boolean(S?.plain);
        if (S?.plain && dialog.dataset.view !== "source") view("source");
        return S;
      });
    };
    const view = (name) => {
      dialog.dataset.view = name;
      if (name !== "source") host.dataset.dgmLayout = name;
      for (const b of seg.children) {
        b.classList.toggle("active", b.dataset.view === name);
        b.setAttribute("aria-pressed", String(b.dataset.view === name));
      }
      //: The line says what this view gives the room to, and the split re-reads that view's own list width (diagram-split.js).
      note.textContent = VIEW_NOTE[name];
      host.dispatchEvent(new CustomEvent("dgmlayout", { detail: name }));
      if (name === "source") field.focus();
    };
    //: One visible line beside the views (1702: "I still dont know what the difference between picture and list do").
    const VIEW_NOTE = { canvas: "Picture: the drawing gets the room", blocks: "List: the blocks get the room", source: "Source: edit the text, the picture follows" };
    const note = el("span", "muted dgm-viewnote");
    note.setAttribute("role", "status");
    const seg = el("div", "seg dgm-views");
    seg.setAttribute("role", "group");
    seg.setAttribute("aria-label", "Diagram view");
    for (const [name, label] of [["canvas", "Picture"], ["blocks", "List"], ["source", "Source"]]) {
      const b = smallButton(label, { canvas: "Picture first: the drawing is wide, with a narrow list of its blocks beside it", blocks: "List first: the blocks list is wide, with the drawing beside it", source: "The diagram as text, with its picture" }[name], () => {
        //: A phone shows the picture alone, and its blocks are a sheet (the dock's list button): the List view opens that sheet, not a view that shows nothing new.
        const sheet = name === "blocks" && phone.matches ? pane?.root?.querySelector(".dgm-listbtn") : null;
        sheet ? sheet.click() : view(name);
      });
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
    //: The completion list under the caret (DD-5, diagram-complete.js). Wired before Tab's indent so a list that is open takes Tab first.
    const complete = hasComplete ? diagramModel.complete.wire(field, srcwrap, (text) => diagramModel.parse(text)) : null;
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
        //: An open completion list takes this Escape (it closes it) before the field gives way to the views.
        if (complete?.open()) return;
        event.preventDefault();
        event.stopPropagation();
        return seg.querySelector('[data-view="source"]').focus();
      }
      //: A menu or an inline field takes its own Escape first; the dialog closes on the next one.
      if (document.querySelector(".action-menu:not(.hidden), .help-popover:not(.hidden)") || event.target.closest?.("input, [contenteditable]")) return;
      //: A picked block goes first (INBOX 1661 h): Escape lets go of it, and the next one closes the window.
      if (pane?.clear?.()) return event.preventDefault(), event.stopPropagation();
      event.preventDefault();
      event.stopPropagation();
      finish(false);
    };
    const leave = () => {
      closing = true;
      current = null;
      clearTimeout(timer);
      clearTimeout(keepTimer);
      window.removeEventListener("pagehide", keep);
      document.removeEventListener("keydown", onKey, true);
      overlay.remove();
      if (returnFocus?.isConnected) returnFocus.focus?.();
      onClose?.();
    };
    //: True when leaving may go ahead: nothing changed, or the person confirmed they do not want the changes.
    //: A typed title is a change too: Escape, Cancel and the backdrop ask before dropping it.
    const mayDiscard = async () => (history[at] === first && !titleField?.value.trim()) || (await confirmDialog("Close without keeping your changes to this diagram?", { confirmLabel: "Discard changes", cancelLabel: "Keep editing" }));
    const finish = async (done) => {
      if (closing) return;
      if (!done && !live && !(await mayDiscard())) return;
      const [next, changed, typed] = [history[at], history[at] !== first, titleField ? titleField.value : ""];
      //: Done keeps the diagram and Discard was confirmed: either way the draft has done its work.
      draftForget(draftId);
      leave();
      if (done && onDone) onDone(next, changed, titleField ? await documentName(typed) : "");
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
      draftForget(draftId);
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
    //: Expanded, the foot is the views, the keys and one way back; the changes are already in the document.
    const back = smallButton("ph:arrows-in Collapse", "Back to the document, where you left it (Escape)", () => finish(true), false);
    back.classList.add("accent");
    foot.append(seg, ...(live ? [chip, back] : [...(known ? [known] : []), chip, cancel, go]));
    if (live) overlay.classList.add("dgm-expanded");
    //: On a phone the views are the sheet's top row, not the foot's first (DD-6, 1107): the foot is one row of Keys, Cancel and Done.
    const viewbar = el("div", "dgm-viewbar");
    const phone = matchMedia("(max-width: 599.98px)");
    //: Wrap, in Source only: the ... menu is in the dock, which Source hides (L304).
    wrapBtn = smallButton("ph:text-align-left Wrap", "Fold long Source lines onto the next row. Line numbers hide while lines fold", () => setWrap(field.getAttribute("wrap") === "off"));
    wrapBtn.classList.add("dgm-wrapbtn");
    wrapBtn.setAttribute("aria-pressed", String(field.getAttribute("wrap") !== "off"));
    const place = () => {
      (phone.matches ? viewbar : foot).prepend(seg);
      seg.after(note);
      note.after(wrapBtn);
    };
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
    //: Short lines, one thought each (the 200-word paragraph read as a wall): the sequence sentence and the shelf sentence stay together.
    const helpLines = [
      "Draw with blocks and the picture follows. Picture gives the drawing the room, List gives the blocks list the room, and Source is the text. A line beside them says which view you are in.",
      "Pick a block in the picture or in the list and it is picked in the other too. The shelf's left arrow folds the shelf to one button. On a mind map or timeline a shelf tile pressed or dropped on the picture adds after the picked block.",
      "Press N to add a box, Tab on the last box to add one joined to it, Enter to name it.",
      "[ and ] fold the list and the picture, F6 leaves the blocks, Ctrl+Enter keeps the diagram and ? lists every key.",
      "On a sequence picture, double press a part to name it, drag a head to reorder and drag from one lifeline to another to add a message. The shelf in the picture's corner adds a block by a press or a drag onto the picture, joined from the box nearest the drop; on a touch screen hold a tile a moment, then drag.",
      "Kind asks before it clears a diagram that has blocks.",
      "If the page closes with this window open, the next open offers your changes back.",
    ];
    helpBody.append(...helpLines.map((line) => el("p", "", line)), atlasSuggestion("How do I make a diagram?", "Ask about making a diagram"));
    head.querySelector(".dialog-head-title").after(help);
    dialog.append(helpBody);
    const body = el("div", "dgm-dialog-body");
    body.append(srcwrap, host);
    let titlebar = null;
    if (titleField) {
      titleField.type = "text";
      titleField.maxLength = 80;
      //: Short on a phone, where the full line was cut at "leave blar" (dgbt-1109 3); the tooltip keeps it whole.
      titleField.placeholder = matchMedia("(max-width: 599.98px)").matches ? "Name it (optional)" : "Name it, or leave blank to date it";
      titleField.title = "Name it, or leave blank to date it";
      titleField.setAttribute("aria-label", "Diagram title");
      //: The characters a link reads as syntax never enter the name, so what is shown is what the document is called.
      titleField.addEventListener("input", () => {
        const clean = titleField.value.replace(/[\[\]|#]+/g, "");
        if (clean !== titleField.value) titleField.value = clean;
      });
      titleField.addEventListener("input", keepSoon);
      titleField.addEventListener("keydown", (event) => event.key === "Escape" && (event.preventDefault(), seg.querySelector(".active")?.focus()));
      titlebar = el("label", "dgm-titlebar");
      titlebar.append(el("span", "muted", "Title"), titleField);
    }
    dialog.append(head, ...(titlebar ? [titlebar] : []), viewbar, body, foot);
    document.addEventListener("keydown", onKey, true);
    wireBackdropClose(overlay, () => finish(false));
    //: Ctrl+Z in the blocks or the source box steps the source history, as it does in a diagram document; in any other text field
    //: (the title, a rename) it is the browser's text undo and this listener leaves it alone (`historyKey`).
    dialog.addEventListener("keydown", (event) => historyKey(event, field, flush, io));
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
    //: Not for an expanded diagram: it is not a starter, and a pick it did not make would take the first Escape.
    if (firstBox && S && !S.k && !live) diagramModel.builder.select(S, firstBox.dataset.key, true);
    else (host.querySelector(".dgm-steps button, .dgm-block[tabindex='0']") || dialog.querySelector(".dgm-pane") || dialog).focus?.({ preventScroll: true });
    //: A phone hides the blocks (they are a sheet), so that focus went nowhere and the first Tab left the window's top: the picture takes it (measured at 390: BODY).
    if (!dialog.contains(document.activeElement)) (host.querySelector(".dgm-picture") || dialog).focus?.({ preventScroll: true });
    //: A draft kept by a reload is offered back, not applied: the person may have meant to start again. Asked in the confirm, not a
    //: toast: a toast over this dialog steps aside from its buttons (status.js `toastYield`, measured 0.12 opacity and not pressable).
    const kept = draftId ? draftsRead()[draftId] : null;
    if (kept && (kept.source !== first || (kept.title || "").trim())) {
      const back = await confirmDialog("Put back your unsaved changes?\n\nThis diagram was open when the page closed, and what you drew was kept on this device.", { confirmLabel: "Put them back", cancelLabel: "Start fresh", danger: false });
      if (closing) return dialog;
      if (back) {
        if (titleField && kept.title) titleField.value = kept.title;
        io.set(kept.source);
        apply();
      } else draftForget(draftId);
    } else if (kept) draftForget(draftId);
    return dialog;
  }

  //: The page head's Export (W18 Q26): a worded menu beside Picture, List and Source, so a diagram's pictures are one press
  //: from the head and not behind the page's ... menu. Made here, not in the page, for the boot budget; the type toggle in
  //: documents.js hides it for any other file. The rows are the toolbar's `out` rows.
  function headExport() {
    const anchor = document.querySelector("#tab-documents .doc-view-cluster");
    if (!anchor || document.getElementById("doc-diagram-export")) return;
    const run = (how) => () => out(how, docText(), currentDoc?.title);
    const rows = [["ph:file-png Download as .png", "png", "file"], ["ph:file-svg Download as .svg", "svg", "file"], ["ph:image Copy as picture", "picture", "copy"], ["ph:copy Copy as Mermaid", "mermaid", "copy"], ["ph:code Copy as SVG", "svgtext", "copy"]];
    const menu = labelledMenu("ph:export Export", rows.map(([label, how, group]) => ({ label, group, run: run(how) })), "Export this diagram");
    menu.id = "doc-diagram-export";
    menu.classList.add("doc-diagram-export");
    anchor.after(menu);
  }

  //: The diagram in a document, taken to the full screen builder (the toolbar's Expand): the same source and the same `io`, so every
  //: change is saved by the document as it is made. Collapse puts the document back where it was: the scroll of every page around
  //: the diagram, its list and its picture, kept now and set again once the document has redrawn what the dialog changed.
  async function expand(S) {
    const kept = [S.scroll, S.fig];
    for (let node = S.root; node; node = node.parentElement) kept.push(node);
    const spots = kept.filter((n) => n && (n.scrollTop || n.scrollLeft)).map((n) => [n, n.scrollLeft, n.scrollTop]);
    const put = () => spots.forEach(([n, x, y]) => Object.assign(n, { scrollLeft: x, scrollTop: y }));
    const button = S.root.querySelector(".dgm-expand");
    const onClose = () => {
      put();
      //: The document redraws once the text has settled; for three seconds after, each redraw of the picture sets the places again.
      const stop = Date.now() + 3000;
      const again = () => Date.now() < stop && put();
      (S.fig.onpaint ||= []).push(again);
      //: A picture's height is known only once its image has decoded; a scroll set before that is clamped to nothing.
      S.fig.addEventListener("load", again, true);
      if (button?.isConnected) button.focus({ preventScroll: true });
    };
    return open({ source: S.source, title: S.io.name || "Diagram", live: S.io, onClose });
  }

  diagramModel.embed = { open, out, outDoc, save, swapRange, link, historyKey, headExport, expand };
})();
