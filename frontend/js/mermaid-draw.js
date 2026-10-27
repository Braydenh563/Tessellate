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

let mermaidProbe = null;

//: Any CSS colour as [r, g, b, a]: a canvas pixel, so `color-mix()` and every
//: other spelling the stylesheet uses come out as numbers.
function mermaidRgba(css) {
  if (!mermaidProbe) {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 1;
    mermaidProbe = canvas.getContext("2d", { willReadFrequently: true });
  }
  mermaidProbe.clearRect(0, 0, 1, 1);
  mermaidProbe.fillStyle = "#000";
  mermaidProbe.fillStyle = css || "#000";
  mermaidProbe.fillRect(0, 0, 1, 1);
  const [r, g, b, a] = mermaidProbe.getImageData(0, 0, 1, 1).data;
  return [r, g, b, a / 255];
}

function mermaidHex(rgb) {
  return `#${rgb.slice(0, 3).map((v) => Math.round(v).toString(16).padStart(2, "0")).join("")}`;
}

function mermaidMix(base, over, amount) {
  return base.slice(0, 3).map((v, i) => v + (over[i] - v) * amount);
}

function mermaidLuma([r, g, b]) {
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
}

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
function mermaidTheme() {
  const ground = mermaidTokenColour("--modal-bg-opaque", "#ffffff");
  const ink = mermaidTokenColour("--ink", "#1f2430");
  const accent = mermaidTokenColour("--accent", "#4664f0");
  const muted = mermaidTokenColour("--muted", "#5b6472");
  const dark = mermaidLuma(ground) < 0.45;
  const strong = document.documentElement.dataset.contrast === "on";
  const hex = mermaidHex;
  const soft = mermaidMix(ground, accent, strong ? 0.28 : 0.16);
  const softer = mermaidMix(ground, accent, 0.08);
  const line = mermaidMix(ground, ink, strong ? 1 : 0.7);
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
    primaryTextColor: hex(ink),
    primaryBorderColor: hex(strong ? ink : accent),
    secondaryColor: hex(softer),
    secondaryTextColor: hex(ink),
    secondaryBorderColor: hex(muted),
    tertiaryColor: hex(ground),
    tertiaryTextColor: hex(ink),
    tertiaryBorderColor: hex(muted),
    lineColor: hex(line),
    textColor: hex(ink),
    mainBkg: hex(soft),
    nodeBorder: hex(strong ? ink : accent),
    nodeTextColor: hex(ink),
    clusterBkg: hex(softer),
    clusterBorder: hex(muted),
    titleColor: hex(ink),
    edgeLabelBackground: hex(ground),
    noteBkgColor: hex(softer),
    noteTextColor: hex(ink),
    noteBorderColor: hex(muted),
    actorBkg: hex(soft),
    actorBorder: hex(strong ? ink : accent),
    actorTextColor: hex(ink),
    actorLineColor: hex(muted),
    signalColor: hex(ink),
    signalTextColor: hex(ink),
    labelBoxBkgColor: hex(soft),
    labelBoxBorderColor: hex(muted),
    labelTextColor: hex(ink),
    loopTextColor: hex(ink),
    activationBkgColor: hex(softer),
    activationBorderColor: hex(muted),
    sequenceNumberColor: hex(ground),
    taskBkgColor: hex(soft),
    taskTextColor: hex(ink),
    taskTextLightColor: hex(ink),
    taskTextOutsideColor: hex(ink),
    taskBorderColor: hex(accent),
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

//: The theme read once per burst: a page of figures asks for it per figure.
let mermaidThemeMemo = null;

function mermaidThemeNow() {
  if (!mermaidThemeMemo) {
    mermaidThemeMemo = mermaidTheme();
    setTimeout(() => {
      mermaidThemeMemo = null;
    }, 50);
  }
  return mermaidThemeMemo;
}

function mermaidCacheKey(themeKey, source) {
  return `${themeKey}\u0000${source}`;
}

//: The answer already known for this source in the theme in force, or null.
//: A figure built from a known answer is complete at once, which is what lets
//: a print or a redraw on a caret move be synchronous.
function mermaidKnown(source) {
  return mermaidState.cache.get(mermaidCacheKey(mermaidThemeNow().key, source)) || null;
}

//: The one-line reason a source was refused by the parser, remembered so the
//: Live view can leave that fence as code without asking again.
function mermaidFailure(source) {
  return mermaidState.bad.get(source) || "";
}

function mermaidRequest(source) {
  const theme = mermaidThemeNow();
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
        { type: "render", id, source, themeVariables: theme.variables },
        location.origin
      );
    });
  }).then((result) => {
    if (result.svg) {
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
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  const img = document.createElement("img");
  img.className = "md-mermaid-img";
  img.alt = mermaidAltFor(source);
  img.decoding = "async";
  img.src = url;
  img.mermaidSvg = svg;
  if (figure.mermaidUrl) URL.revokeObjectURL(figure.mermaidUrl);
  figure.mermaidUrl = url;
  figure.mermaidKey = result.key;
  figure.replaceChildren(img);
  figure.classList.remove("md-mermaid-pending");
  figure.removeAttribute("aria-busy");
}

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
      return;
    }
    figure.remove();
    block.dataset.mermaidState = "failed";
    const reason = document.createElement("p");
    reason.className = "md-mermaid-reason";
    reason.setAttribute("role", "status");
    reason.textContent = `Could not draw this diagram: ${result.error}`;
    block.after(reason);
  });
}

function mermaidDrawIn(container) {
  const blocks = [...container.querySelectorAll('.code-block code[data-lang="mermaid"]')].map((c) => c.closest(".code-block"));
  return Promise.all(blocks.map(mermaidDrawBlock));
}

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
}

// --- the theme moved ----------------------------------------------------------

let mermaidRedrawTimer = 0;

function mermaidRedrawAll() {
  mermaidThemeMemo = mermaidTheme();
  const now = mermaidThemeMemo.key;
  for (const figure of document.querySelectorAll("figure.md-mermaid")) {
    if (figure.mermaidSource && figure.mermaidKey !== now) mermaidFill(figure, figure.mermaidSource);
  }
}

if (typeof MutationObserver === "function") {
  //: `style` too, because an accent colour is written there; the key compare
  //: above means a change that moves no colour redraws nothing.
  new MutationObserver(() => {
    clearTimeout(mermaidRedrawTimer);
    mermaidRedrawTimer = setTimeout(mermaidRedrawAll, 120);
  }).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme", "data-mode", "data-contrast", "class", "style"],
  });
}
