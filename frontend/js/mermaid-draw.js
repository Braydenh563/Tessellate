// mermaid-draw.js: the page's half of drawing a ```mermaid fence.
//
// Lazy (app.js `LAZY_MODULES.mermaid`): nothing here runs until a fence is on
// screen, and the library itself (5 MB) is not loaded by this file at all. It
// lives in a hidden same-origin frame (`/mermaid-frame`, mermaid-frame.js)
// because the app's policy refuses the <style> and style= attributes Mermaid
// writes; see the header of that file. This side posts `{id, source,
// themeVariables}`, gets back `{id, svg}` or `{id, error}`, and shows the
// svg as an <img> from a blob: URL, which keeps its own styles and sits
// outside the page policy. Every Mermaid kind draws the same way, so there is
// no drawing code of ours left for any of them.
//
// Who calls it: `renderMarkdown` (navigation.js) for chat, Ask and every other
// rendered Markdown, after a short settle so a streaming reply is not drawn
// per token; documents.js for Read (so for the print and the HTML export) and
// for the Live widget. A fence that cannot be read stays the code block it is
// with the reason under it.

// MERMAID-DRAW-PROTOCOL-BEGIN
//: The frame's answer is taken only from the window this page framed, from
//: this origin, as an object. Both sides check both, so a message from any
//: other window or origin is ignored rather than trusted.
(() => {
  function mermaidResultAccepts(event, frameWindow, origin) {
    if (!event || !frameWindow || event.origin !== origin || event.source !== frameWindow) return false;
    return !!event.data && typeof event.data === "object";
  }

  const MERMAID_KINDS = [
    [/^(flowchart|graph)\b/i, "Flowchart"],
    [/^sequenceDiagram\b/i, "Sequence diagram"],
    [/^classDiagram\b/i, "Class diagram"],
    [/^stateDiagram/i, "State diagram"],
    [/^erDiagram\b/i, "Entity relationship diagram"],
    [/^gantt\b/i, "Gantt chart"],
    [/^pie\b/i, "Pie chart"],
    [/^mindmap\b/i, "Mind map"],
    [/^timeline\b/i, "Timeline"],
    [/^journey\b/i, "User journey"],
    [/^quadrantChart\b/i, "Quadrant chart"],
    [/^gitGraph\b/i, "Git graph"],
    [/^requirementDiagram\b/i, "Requirement diagram"],
    [/^xychart/i, "XY chart"],
    [/^sankey/i, "Sankey diagram"],
    [/^block/i, "Block diagram"],
    [/^architecture/i, "Architecture diagram"],
    [/^packet/i, "Packet diagram"],
    [/^kanban\b/i, "Kanban board"],
    [/^C4/i, "C4 diagram"],
  ];

  //: The words a screen reader hears for a figure: the kind, then the diagram's
  //: own title when it has one (`accTitle:`, a `title` line, or front matter).
  function mermaidAltFor(source) {
    let lines = String(source || "").split("\n").map((l) => l.trim());
    let title = "";
    if (lines[0] === "---") {
      const end = lines.indexOf("---", 1);
      if (end > 0) {
        const found = lines.slice(1, end).map((l) => /^title:\s*(.+)$/.exec(l)).find(Boolean);
        if (found) title = found[1].replace(/^["']|["']$/g, "");
        lines = lines.slice(end + 1);
      }
    }
    lines = lines.filter((l) => l && !l.startsWith("%%"));
    const head = lines[0] || "";
    const kind = (MERMAID_KINDS.find(([re]) => re.test(head)) || [null, ""])[1];
    const acc = lines.map((l) => /^accTitle:\s*(.+)$/.exec(l)).find(Boolean);
    const named = lines.map((l) => /^title\s+(.+)$/.exec(l)).find(Boolean) || /^\w+\s+title\s+(.+)$/.exec(head);
    const words = (acc && acc[1]) || title || (named && named[1]) || "";
    const label = kind || "Diagram";
    return words ? `${label}: ${words.trim()}` : label;
  }
  // MERMAID-DRAW-PROTOCOL-END

  const mermaidState = {
    frame: null,
    ready: null,
    waiting: new Map(),
    seq: 0,
    cache: new Map(),
    bad: new Map(),
    draws: new Set(),
    listening: false,
    //: The colour probe, the theme read once per burst, the theme-move debounce.
    probe: null,
    themeMemo: null,  // a Map of look to theme, for one burst
    redrawTimer: 0,
  };
  const MERMAID_CACHE_MAX = 80;
  const MERMAID_WAIT_MS = 25000;

  function mermaidOnMessage(event) {
    if (!mermaidResultAccepts(event, mermaidState.frame && mermaidState.frame.contentWindow, location.origin)) return;
    const data = event.data;
    if (data.type === "ready" && mermaidState.readyDone) {
      mermaidState.readyDone(true);
    } else if (data.type === "result" && mermaidState.waiting.has(data.id)) {
      const done = mermaidState.waiting.get(data.id);
      mermaidState.waiting.delete(data.id);
      done(typeof data.svg === "string" ? { svg: data.svg } : { error: String(data.error || "This diagram could not be drawn.") });
    }
  }

  //: The frame is made once, on the first fence, and kept. It has to be laid
  //: out (Mermaid measures text), so it is off to the side and invisible, not
  //: `display: none`.
  function mermaidEnsureFrame() {
    if (mermaidState.ready) return mermaidState.ready;
    if (!mermaidState.listening) {
      mermaidState.listening = true;
      window.addEventListener("message", mermaidOnMessage);
    }
    mermaidState.ready = new Promise((resolve) => {
      const timer = setTimeout(() => resolve(false), MERMAID_WAIT_MS);
      mermaidState.readyDone = (ok) => {
        clearTimeout(timer);
        resolve(ok);
      };
      const frame = document.createElement("iframe");
      frame.className = "mermaid-frame";
      frame.title = "Diagram renderer";
      frame.setAttribute("aria-hidden", "true");
      frame.tabIndex = -1;
      frame.src = "/mermaid-frame";
      mermaidState.frame = frame;
      document.body.appendChild(frame);
    }).then((ok) => {
      //: A frame that never answered is dropped so the next fence tries again.
      if (!ok) {
        mermaidState.frame?.remove();
        mermaidState.frame = null;
        mermaidState.ready = null;
      }
      return ok;
    });
    return mermaidState.ready;
  }

  // --- the app's colours, as Mermaid's variables --------------------------------


  //: Any CSS colour as [r, g, b, a]: a canvas pixel, so `color-mix()` and every
  //: other spelling the stylesheet uses come out as numbers.
  function mermaidRgba(css) {
    if (!mermaidState.probe) {
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 1;
      mermaidState.probe = canvas.getContext("2d", { willReadFrequently: true });
    }
    mermaidState.probe.clearRect(0, 0, 1, 1);
    mermaidState.probe.fillStyle = "#000";
    mermaidState.probe.fillStyle = css || "#000";
    mermaidState.probe.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = mermaidState.probe.getImageData(0, 0, 1, 1).data;
    return [r, g, b, a / 255];
  }

  function mermaidHex(rgb) {
    return `#${rgb.slice(0, 3).map((v) => Math.round(v).toString(16).padStart(2, "0")).join("")}`;
  }

  // MERMAID-LOOK-BEGIN
  function mermaidMix(base, over, amount) {
    return base.slice(0, 3).map((v, i) => v + (over[i] - v) * amount);
  }

  //: How much of the accent a box's fill is when nothing was chosen.
  function mermaidFillShare(strong) {
    return strong ? 0.28 : 0.16;
  }

  //: **The fills of a diagram** (INBOX 1486). `look` is what the board object
  //: stored, `{fill: [r, g, b], fillAlpha, lineAlpha}` with any part missing, or
  //: null for the look every diagram had. The picture carries its own opaque
  //: ground, so a fill's opacity is its mix over that ground: 1 is the colour
  //: itself, 0 is the ground. Boxes (nodes, actors, notes, activation bars) take
  //: the strength chosen; the grouping fills (clusters, sections) one step
  //: lighter, as the defaults always were.
  function mermaidFills(ground, accent, strong, look) {
    const softer = mermaidMix(ground, accent, 0.08);
    if (!look || (!look.fill && look.fillAlpha == null)) return { soft: mermaidMix(ground, accent, mermaidFillShare(strong)), softer, note: softer };
    const base = look.fill || accent;
    const share = look.fillAlpha ?? mermaidFillShare(strong);
    const soft = mermaidMix(ground, base, share);
    return { soft, softer: mermaidMix(ground, base, share / 2), note: soft };
  }

  //: A line's colour at its opacity over the ground; no opacity leaves it be.
  function mermaidFaded(ground, colour, alpha) {
    return alpha == null || alpha >= 1 ? colour.slice(0, 3) : mermaidMix(ground, colour, Math.max(0, alpha));
  }
  function mermaidLuma([r, g, b]) {
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  }

  //: The words on a box the person gave a fill: the theme's ink, or the ground
  //: when that reads better on the fill (white words on a solid blue box). A
  //: diagram with no stored look keeps the ink, as it always did.
  function mermaidInkOn(fill, ink, ground, look) {
    if (!look) return ink;
    return Math.abs(mermaidLuma(fill) - mermaidLuma(ink)) >= Math.abs(mermaidLuma(fill) - mermaidLuma(ground)) ? ink : ground;
  }
  // MERMAID-LOOK-END

  function mermaidHue([r, g, b]) {
    const [x, y, z] = [r / 255, g / 255, b / 255];
    const max = Math.max(x, y, z);
    const min = Math.min(x, y, z);
    if (max === min) return 215;
    const d = max - min;
    const h = max === x ? ((y - z) / d) % 6 : max === y ? (z - x) / d + 2 : (x - y) / d + 4;
    return (h * 60 + 360) % 360;
  }

  function mermaidTokenColour(name, fallback) {
    const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return mermaidRgba(raw || fallback);
  }

  //: Light, dark and high contrast all come from the tokens in force, so a
  //: theme switch needs no table here; the key says when they moved.
  function mermaidTheme(look = null) {
    const ground = mermaidTokenColour("--modal-bg-opaque", "#ffffff");
    const ink = mermaidTokenColour("--ink", "#1f2430");
    const accent = mermaidTokenColour("--accent", "#4664f0");
    const muted = mermaidTokenColour("--muted", "#5b6472");
    const dark = mermaidLuma(ground) < 0.45;
    const strong = document.documentElement.dataset.contrast === "on";
    const hex = mermaidHex;
    const { soft, softer, note } = mermaidFills(ground, accent, strong, look);
    const onSoft = mermaidInkOn(soft, ink, ground, look);
    const onSofter = mermaidInkOn(softer, ink, ground, look);
    const onNote = mermaidInkOn(note, ink, ground, look);
    //: A line's opacity fades its borders and strokes toward the ground; text keeps its ink.
    const fade = (rgb) => mermaidFaded(ground, rgb, look?.lineAlpha);
    const edge = fade(strong ? ink : accent);
    const quiet = fade(muted);
    const line = fade(mermaidMix(ground, ink, strong ? 1 : 0.7));
    const hue = mermaidHue(accent);
    //: Twelve slices or branches round the accent's hue, light enough in the
    //: dark theme and dark enough in the light one that the label colour below
    //: holds contrast against every one.
    const swatch = [];
    for (let i = 0; i < 12; i++) swatch.push(`hsl(${Math.round((hue + i * 30) % 360)}, 55%, ${dark ? 62 : 38}%)`);
    const onSwatch = dark ? "#111111" : "#ffffff";
    const vars = {
      darkMode: dark,
      background: hex(ground),
      fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
      primaryColor: hex(soft),
      primaryTextColor: hex(onSoft),
      primaryBorderColor: hex(edge),
      secondaryColor: hex(softer),
      secondaryTextColor: hex(onSofter),
      secondaryBorderColor: hex(quiet),
      tertiaryColor: hex(ground),
      tertiaryTextColor: hex(ink),
      tertiaryBorderColor: hex(quiet),
      lineColor: hex(line),
      textColor: hex(ink),
      mainBkg: hex(soft),
      nodeBorder: hex(edge),
      nodeTextColor: hex(onSoft),
      clusterBkg: hex(softer),
      clusterBorder: hex(quiet),
      titleColor: hex(ink),
      edgeLabelBackground: hex(ground),
      noteBkgColor: hex(note),
      noteTextColor: hex(onNote),
      noteBorderColor: hex(quiet),
      actorBkg: hex(soft),
      actorBorder: hex(edge),
      actorTextColor: hex(onSoft),
      actorLineColor: hex(quiet),
      signalColor: hex(fade(ink)),
      signalTextColor: hex(ink),
      labelBoxBkgColor: hex(soft),
      labelBoxBorderColor: hex(quiet),
      labelTextColor: hex(onSoft),
      loopTextColor: hex(ink),
      activationBkgColor: hex(note),
      activationBorderColor: hex(quiet),
      sequenceNumberColor: hex(ground),
      taskBkgColor: hex(soft),
      taskTextColor: hex(onSoft),
      taskTextLightColor: hex(onSoft),
      taskTextOutsideColor: hex(ink),
      taskBorderColor: hex(fade(accent)),
      sectionBkgColor: hex(softer),
      altSectionBkgColor: hex(ground),
      gridColor: hex(mermaidMix(ground, ink, 0.2)),
      pieTitleTextColor: hex(ink),
      pieLegendTextColor: hex(ink),
      pieSectionTextColor: onSwatch,
      pieStrokeColor: hex(ground),
      pieOuterStrokeColor: hex(muted),
      archEdgeColor: hex(line),
    };
    swatch.forEach((css, i) => {
      const rgb = mermaidRgba(css);
      vars[`pie${i + 1}`] = hex(rgb);
      vars[`cScale${i}`] = hex(rgb);
      vars[`cScaleLabel${i}`] = onSwatch;
    });
    return { key: Object.entries(vars).map(([k, v]) => `${k}=${v}`).join("|"), variables: vars };
  }

  // --- asking the frame ---------------------------------------------------------

  //: A board object's stored look (`{fill: "#hex", fillAlpha, lineAlpha}`, any
  //: part missing) as the numbers `mermaidFills` takes; null when it stored none.
  function mermaidLook(raw) {
    if (!raw) return null;
    const fill = raw.fill && raw.fill !== "transparent" ? mermaidRgba(raw.fill).slice(0, 3) : null;
    const num = (v) => (Number.isFinite(Number(v)) && v !== null && v !== "" && v !== undefined ? Math.max(0, Math.min(1, Number(v))) : null);
    const look = { fill, fillAlpha: num(raw.fillAlpha), lineAlpha: num(raw.lineAlpha) };
    return look.fill || look.fillAlpha !== null || look.lineAlpha !== null ? look : null;
  }

  //: The theme read once per burst: a page of figures asks for it per figure.
  //: Each look is read once per burst too.

  function mermaidThemeNow(look = null) {
    if (!mermaidState.themeMemo) {
      mermaidState.themeMemo = new Map();
      setTimeout(() => {
        mermaidState.themeMemo = null;
      }, 50);
    }
    const tag = look ? JSON.stringify(look) : "";
    if (!mermaidState.themeMemo.has(tag)) mermaidState.themeMemo.set(tag, mermaidTheme(mermaidLook(look)));
    return mermaidState.themeMemo.get(tag);
  }

  function mermaidCacheKey(themeKey, source) {
    return `${themeKey}\u0000${source}`;
  }

  //: The answer already known for this source in the theme in force, or null.
  //: A figure built from a known answer is complete at once, which is what lets
  //: a print or a redraw on a caret move be synchronous.
  function mermaidKnown(source, look = null) {
    return mermaidState.cache.get(mermaidCacheKey(mermaidThemeNow(look).key, source)) || null;
  }

  //: The one-line reason a source was refused by the parser, remembered so the
  //: Live view can leave that fence as code without asking again.
  // MERMAID-PLAIN-BEGIN
  function mermaidFailure(source) {
    return mermaidState.bad.get(source) || "";
  }

  //: **The reason in plain words** (audit 1102 DX17). The parser's own line is a
  //: token list ("Expecting 'AMP', 'COLON', 'PIPE' ...") that tells a writer
  //: nothing; what they need is which line and what is wrong with it. The line
  //: is found in the source, because Mermaid reports the line where it gave up
  //: (often the empty one after a dangling arrow). A reason that is already a
  //: sentence (empty, too long, renderer missing) comes back as it was. A
  //: property of `mermaidFailure`, not a global of its own.
  mermaidFailure.plain = (error, source) => {
    const raw = String(error || "");
    if (/No diagram type detected|UnknownDiagramError/i.test(raw)) {
      return "The first line should name a diagram, such as flowchart TD or sequenceDiagram.";
    }
    const found = /^Parse error on line (\d+)/.exec(raw);
    if (!found) return raw;
    const lines = String(source || "").split("\n");
    let at = Math.min(Number(found[1]), lines.length) - 1;
    while (at > 0 && !lines[at].trim()) at -= 1;
    const text = (lines[at] || "").replace(/;\s*$/, "").trim();
    const where = `Line ${at + 1}: `;
    const count = (open, close) => text.split(open).length - text.split(close).length;
    // Plain string ends, not one regex: this checks a diagram line, it filters no HTML.
    if (["-->", "---", "==>", "===", "-.->", "<-->"].some((arrow) => text.endsWith(arrow)) || /--[ox>]$/.test(text)) return `${where}an arrow needs a box after it.`;
    if (text.split('"').length % 2 === 0) return `${where}a quote is not closed.`;
    if (count("[", "]") || count("(", ")") || count("{", "}")) return `${where}a bracket is not closed.`;
    return `${where}this line is not valid here. Check its arrows and brackets.`;
  };

  // MERMAID-PLAIN-END

  //: The note under a diagram that would not draw, for Read and for the Live
  //: widget alike: the plain sentence, and the parser's own words behind a
  //: disclosure when they differ.
  mermaidFailure.note = (error, source) => {
    const note = document.createElement("div");
    note.className = "md-mermaid-reason";
    note.setAttribute("role", "status");
    const plain = mermaidFailure.plain(error, source);
    note.append(`Couldn't draw this diagram. ${plain}`);
    if (plain !== error) {
      const more = document.createElement("details");
      more.className = "md-mermaid-raw";
      const label = document.createElement("summary");
      label.textContent = "Details";
      const raw = document.createElement("code");
      raw.textContent = error;
      more.append(label, raw);
      note.append(more);
    }
    return note;
  };

  //: Mermaid writes a `#quot;` or `#35;` code in a label as `&amp;quot;` and may wrap the line inside it, so the picture showed the
  //: entity's text, not the mark (1679 blind pass). These three codes go to it as private-use letters and come back as the marks.
  function mermaidRequest(source, look = null) {
    const marks = [["#quot;", "\ue001", "&quot;"], ["#35;", "\ue002", "#"], ["#124;", "\ue003", "|"]];
    const theme = mermaidThemeNow(look);
    const key = mermaidCacheKey(theme.key, source);
    const hit = mermaidState.cache.get(key);
    if (hit) return Promise.resolve(hit);
    return mermaidEnsureFrame().then((ok) => {
      if (!ok) return { error: "The diagram renderer did not load.", transient: true };
      return new Promise((resolve) => {
        const id = `m${++mermaidState.seq}`;
        const timer = setTimeout(() => {
          mermaidState.waiting.delete(id);
          resolve({ error: "Drawing this diagram took too long.", transient: true });
        }, MERMAID_WAIT_MS);
        mermaidState.waiting.set(id, (result) => {
          clearTimeout(timer);
          resolve(result);
        });
        mermaidState.frame.contentWindow.postMessage(
          { type: "render", id, source: marks.reduce((text, [code, stand]) => text.split(code).join(stand), source), themeVariables: theme.variables },
          location.origin
        );
      });
    }).then((result) => {
      if (result.svg) {
        result.svg = marks.reduce((text, [, stand, mark]) => text.split(stand).join(mark), result.svg);
        //: A timeline's axis and event lines take the label colour of its slices by Mermaid's own sheet (`.lineWrapper line`: #111111 on the dark ground, white on the light), so the axis was lost in both themes; the theme's line colour stands in, for its arrowhead (a bare path, black) too.
        result.svg = result.svg.replace(/(\.lineWrapper line\{stroke:)#[0-9a-f]{6}(;\})/g, `$1${theme.variables.lineColor}$2`).split('V 4 L6,2 Z"/>').join(`V 4 L6,2 Z" fill="${theme.variables.lineColor}"/>`);
        result.key = theme.key;
        mermaidState.cache.set(key, result);
        if (mermaidState.cache.size > MERMAID_CACHE_MAX) mermaidState.cache.delete(mermaidState.cache.keys().next().value);
        mermaidState.bad.delete(source);
      } else if (!result.transient) {
        mermaidState.bad.set(source, result.error);
      }
      return result;
    });
  }

  // --- the figure ---------------------------------------------------------------

  //: The picture in a figure: an <img> from a blob: URL (SVG as an image keeps
  //: its own styles and is outside the page policy). The old URL is revoked.
  function mermaidShow(figure, result, source) {
    const svg = result.svg;
    //: A moving arrow (`e1@{ animate: true }`) holds still under reduced motion, the app's switch or the system's (L-documents-58).
    const still = document.documentElement.dataset.motion === "reduced" || matchMedia("(prefers-reduced-motion: reduce)").matches;
    const shown = still && /edge-animation/.test(svg) ? svg.replace(/(<svg\b[^>]*>)/, "$1<style>[class*='edge-animation']{animation:none !important}</style>") : svg;
    const url = URL.createObjectURL(new Blob([shown], { type: "image/svg+xml" }));
    const img = document.createElement("img");
    img.className = "md-mermaid-img";
    img.alt = mermaidAltFor(source);
    img.decoding = "async";
    img.src = url;
    img.mermaidSvg = svg;
    if (figure.mermaidUrl) URL.revokeObjectURL(figure.mermaidUrl);
    figure.mermaidUrl = url;
    figure.mermaidKey = result.key;
    //: The builder's overlay (diagram-overlay.js) lives in the figure and outlasts a new picture.
    figure.replaceChildren(img, ...figure.querySelectorAll(":scope > .dgm-overlay"));
    figure.classList.remove("md-mermaid-pending");
    figure.removeAttribute("aria-busy");
    //: The builder's own picture selects blocks; only a document's picture follows a block's link.
    if (!figure.closest(".dgm-picture, .dgm-template-figure")) mermaidShow.links(figure, svg, source);
  }

  //: L-documents-78: the picture is an <img> under the strict level, so a `click` link cannot live in it. A layer of buttons over
  //: it, one per linked block (`n.href`, https or `[[note]]` only), is placed from the node boxes of the drawn SVG (a node's
  //: translate, on the node or on the link around it, and its rect, circle or polygon) as shares of the viewBox, so it follows the picture's size. A property of
  //: `mermaidShow`, not a global.
  mermaidShow.links = (figure, svg, source) => {
    const model = window.diagramModel?.parse(source);
    const linked = (model?.nodes || []).filter((n) => /^(?:https?:\/\/[^\s"]+|\[\[[^\]"\n]+\]\])$/i.test(n.href || ""));
    if (!linked.length) return;
    const svgDoc = new DOMParser().parseFromString(svg, "image/svg+xml");
    const view = (svgDoc.documentElement.getAttribute("viewBox") || "").trim().split(/[\s,]+/).map(Number);
    if (view.length !== 4 || !(view[2] > 0 && view[3] > 0)) return;
    const layer = document.createElement("div");
    layer.className = "md-mermaid-hit";
    for (const n of linked) {
      const g = [...svgDoc.querySelectorAll("g.node")].find((el) => new RegExp(`(?:^|-)flowchart-${n.id.replace(/[^\w-]/g, "\\$&")}-\\d+$`).test(el.id));
      const at = /translate\(\s*(-?[\d.]+)[ ,]+(-?[\d.]+)\s*\)/.exec(g?.getAttribute("transform") || g?.parentNode.getAttribute?.("transform") || "");
      if (!g || !at) continue;
      const xs = [];
      const ys = [];
      for (const el of g.querySelectorAll("rect, circle, ellipse, polygon")) {
        if (el.localName === "rect") {
          const [x, y, w, h] = ["x", "y", "width", "height"].map((k) => Number(el.getAttribute(k)) || 0);
          xs.push(x, x + w);
          ys.push(y, y + h);
        } else if (el.localName === "polygon") {
          for (const pair of (el.getAttribute("points") || "").trim().split(/\s+/)) {
            const [x, y] = pair.split(",").map(Number);
            if (Number.isFinite(x) && Number.isFinite(y)) xs.push(x), ys.push(y);
          }
        } else {
          const rx = Number(el.getAttribute("r") || el.getAttribute("rx")) || 0;
          const ry = Number(el.getAttribute("r") || el.getAttribute("ry")) || 0;
          xs.push(-rx, rx);
          ys.push(-ry, ry);
        }
      }
      if (!xs.length) continue;
      const left = Number(at[1]) + Math.min(...xs);
      const top = Number(at[2]) + Math.min(...ys);
      const hit = document.createElement("button");
      hit.type = "button";
      hit.className = "md-mermaid-hit-node";
      hit.title = n.tip || `Open ${n.href}`;
      hit.setAttribute("aria-label", `Open the link of ${n.text}`);
      hit.style.left = `${((left - view[0]) / view[2]) * 100}%`;
      hit.style.top = `${((top - view[1]) / view[3]) * 100}%`;
      hit.style.width = `${((Math.max(...xs) - Math.min(...xs)) / view[2]) * 100}%`;
      hit.style.height = `${((Math.max(...ys) - Math.min(...ys)) / view[3]) * 100}%`;
      //: A press on the figure puts the caret on its fence in Live, which swaps the figure for its text before the click lands.
      for (const kind of ["mousedown", "pointerdown", "touchstart"]) hit.addEventListener(kind, (event) => event.stopPropagation(), { passive: true });
      hit.addEventListener("click", async (event) => {
        event.stopPropagation();
        //: The link path is the document bundle's; a figure in a chat answer asks for it first.
        if (!(await ensureModule("library"))) return;
        if (n.href.startsWith("[[")) docOpenWikiTarget(n.href.slice(2, -2));
        else docOpenLink(n.href);
      });
      layer.append(hit);
    }
    if (!layer.childElementCount) return;
    //: The layer is the picture's own box without a watcher: the image is as wide as its viewBox, or the figure when that is
    //: narrower, centred, and the layer takes the same width and ratio (the CSS centres it).
    layer.style.width = `min(100%, ${Math.ceil(view[2])}px)`;
    layer.style.aspectRatio = `${Math.ceil(view[2])} / ${Math.ceil(view[3])}`;
    figure.append(layer);
  };

  //: Fill a figure for `source`; resolves to the result. `onDone(result)` runs
  //: once the picture (or the refusal) is known, whether that was at once or
  //: after the frame answered.
  function mermaidFill(figure, source, onDone) {
    figure.mermaidSource = source;
    figure.classList.add("md-mermaid");
    //: Drawn again (a theme switch) keeps its old picture until the new one is in.
    if (!figure.querySelector("img")) {
      figure.classList.add("md-mermaid-pending");
      figure.setAttribute("aria-busy", "true");
    }
    const hit = mermaidKnown(source);
    if (hit) {
      mermaidShow(figure, hit, source);
      if (onDone) onDone(hit);
      return Promise.resolve(hit);
    }
    const draw = mermaidRequest(source).then((result) => {
      //: A figure that left the page while the frame worked has nothing to show.
      if (result.svg && figure.mermaidSource === source) mermaidShow(figure, result, source);
      if (onDone) onDone(result);
      return result;
    });
    mermaidState.draws.add(draw);
    draw.finally(() => mermaidState.draws.delete(draw));
    return draw;
  }

  //: Resolves when every draw in flight has finished: the print and the HTML
  //: export wait on it so a figure is never saved as its placeholder.
  function mermaidSettled() {
    return Promise.allSettled([...mermaidState.draws]);
  }

  //: A rendered fence (`.code-block` with `code[data-lang="mermaid"]`) becomes
  //: its figure; one the parser refuses stays the code block with the reason
  //: under it.
  function mermaidDrawBlock(block) {
    if (!block || block.dataset.mermaidState) return null;
    const code = block.querySelector('code[data-lang="mermaid"]');
    if (!code) return null;
    block.dataset.mermaidState = "pending";
    const figure = document.createElement("figure");
    if (block.dataset.srcLine) figure.dataset.srcLine = block.dataset.srcLine;
    block.before(figure);
    return mermaidFill(figure, code.textContent, (result) => {
      if (result.svg) {
        block.remove();
        if (figure.closest(".step-answer, .answer")) mermaidFill.asDiagram(figure, code.textContent);
        return;
      }
      figure.remove();
      block.dataset.mermaidState = "failed";
      block.after(mermaidFailure.note(result.error, code.textContent));
    });
  }

  function mermaidDrawIn(container) {
    const blocks = [...container.querySelectorAll('.code-block code[data-lang="mermaid"]')].map((c) => c.closest(".code-block"));
    return Promise.all(blocks.map(mermaidDrawBlock));
  }

  //: A reply's diagram (Chat, Ask) can become one of its own (1546 D6): "Open as a diagram" makes a Mermaid
  //: diagram document of the fence and opens it in Blocks. Properties of `mermaidFill`, not globals.
  mermaidFill.asDiagram = (figure, source) => {
    const open = document.createElement("button");
    open.type = "button";
    open.className = "linklike md-mermaid-as";
    open.textContent = "Open as a diagram";
    open.title = "Make a diagram document of this and edit it as blocks";
    open.addEventListener("click", async () => {
      open.disabled = true;
      try {
        const doc = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: mermaidAltFor(source).replace(/:.*/, ""), content: source, file_type: "mmd" }) });
        switchTab("documents");
        await openDocument(doc.id);
        offerCreateUndo(doc);
      } catch (error) {
        toast(error.message || "Couldn't make the diagram.", true);
      } finally {
        open.disabled = false;
      }
    });
    figure.after(open);
  };

  //: `![[a diagram]]` in a note or a document (1546 D6): the diagram document's source is fetched and
  //: drawn as a fence is (`mermaidDrawIn`); a line under it opens the document. A diagram that will not
  //: draw, or has nothing in it, is the document card it was.
  mermaidFill.embed = async (box, doc, name) => {
    try {
      const source = String((await apiJson(`/documents/${doc.id}`, { silent: true })).content || "").trim();
      if (!source) throw new Error("empty");
      const block = document.createElement("div");
      block.className = "code-block";
      const code = block.appendChild(document.createElement("pre")).appendChild(document.createElement("code"));
      code.dataset.lang = "mermaid";
      code.textContent = source;
      box.append(block);
      await mermaidDrawIn(box);
      if (!box.querySelector("img")) throw new Error("not drawn");
      const open = document.createElement("button");
      open.type = "button";
      open.className = "linklike diagram-embed-open";
      open.textContent = `${doc.title || "Diagram"}: open the diagram`;
      open.addEventListener("click", (event) => {
        event.stopPropagation();
        openDocument.back = true;
        openDocument(doc.id);
      });
      //: A double click is two presses: the first opens the diagram, and the second lands on the page that replaced this one
      //: (measured: a 297-character selection across the builder). For half a second a press that is a second or later of its
      //: run is stopped, its default (selecting) and its click (it could press a button of the builder).
      const calm = () => {
        const stop = (event) => {
          if (event.detail > 1) (event.preventDefault(), event.stopPropagation());
        };
        for (const name of ["mousedown", "click"]) document.addEventListener(name, stop, true);
        setTimeout(() => {
          for (const name of ["mousedown", "click"]) document.removeEventListener(name, stop, true);
        }, 500);
      };
      //: The picture opens the diagram too (blind test 1108: pressing the embed did nothing). A `click` only: no mousedown, no
      //: preventDefault, so a pointer press still reaches the editor first. In the Live editor the embed is a widget whose
      //: `ignoreEvent` is true (documents-cm.js), so CodeMirror never placed a caret from a press on it, and its own click handler
      //: already opened the target; stopPropagation here only keeps that from opening it a second time (review 1108).
      box.classList.add("diagram-embed-box");
      box.title = "Open the diagram";
      box.addEventListener("click", (event) => {
        if (event.target.closest("button, a")) return;
        event.stopPropagation();
        openDocument.back = true;
        calm();
        openDocument(doc.id);
      });
      box.append(open);
    } catch {
      box.replaceChildren(mdDocumentCard(doc, name, true));
    }
  };

  //: A saved HTML file outlives this page's blob: URLs, so the export carries
  //: each picture as a data: URL of its own SVG. `live` and `clone` are the same
  //: tree, so the Nth picture of one is the Nth of the other.
  function mermaidInlineForExport(live, clone) {
    const from = [...live.querySelectorAll(".md-mermaid img")];
    const into = [...clone.querySelectorAll(".md-mermaid img")];
    from.forEach((img, i) => {
      if (!img.mermaidSvg || !into[i]) return;
      into[i].setAttribute("src", `data:image/svg+xml;charset=utf-8,${encodeURIComponent(img.mermaidSvg)}`);
    });
    //: The layer of link buttons is for this page only; a saved file keeps the picture.
    clone.querySelectorAll(".md-mermaid-hit").forEach((layer) => layer.remove());
  }

  // --- the theme moved ----------------------------------------------------------


  function mermaidRedrawAll() {
    mermaidState.themeMemo = null;
    const now = mermaidThemeNow().key;
    for (const figure of document.querySelectorAll("figure.md-mermaid")) {
      if (figure.mermaidSource && figure.mermaidKey !== now) mermaidFill(figure, figure.mermaidSource);
    }
  }

  {
    //: `style` too, because an accent colour is written there; the key compare
    //: above means a change that moves no colour redraws nothing.
    new MutationObserver(() => {
      clearTimeout(mermaidState.redrawTimer);
      mermaidState.redrawTimer = setTimeout(mermaidRedrawAll, 120);
    }).observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme", "data-mode", "data-contrast", "class", "style"],
    });
  }

  Object.assign(window, { mermaidAltFor, mermaidDrawBlock, mermaidDrawIn, mermaidFailure, mermaidFill, mermaidInlineForExport, mermaidKnown, mermaidRequest, mermaidSettled, mermaidShow, mermaidThemeNow });
})();
