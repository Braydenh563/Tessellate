// mermaid-frame.js: the page inside the hidden diagram frame (`/mermaid-frame`).
//
// Why a frame at all: Mermaid writes a <style> element and style= attributes
// into whatever it draws, and measures text by laying it out. The app's own
// policy (`style-src 'self'`) refuses both, which showed as console errors and
// wrong text widths. Relaxing the app's policy would trade the notebook's
// protection for a viewer feature, so the drawing happens here instead, in a
// same-origin document whose response carries a policy of its own
// (`MERMAID_FRAME_CSP`, core/security.py). The parent never sees Mermaid's
// markup: it gets a finished SVG as text and shows it as an <img>, which keeps
// its styles and sits outside the page policy.
//
// Loaded after /vendor/mermaid/mermaid.min.js, which defines `mermaid`.

// MERMAID-FRAME-PROTOCOL-BEGIN
const MERMAID_FRAME_MAX_SOURCE = 20000;

//: A request is taken only from the window that framed us, from our own
//: origin, in the one shape the parent sends. Anything else is ignored
//: silently: a stray message is not an error worth answering.
function mermaidFrameAccepts(event, parentWindow, origin) {
  if (!event || event.origin !== origin || event.source !== parentWindow) return false;
  const data = event.data;
  return !!data && data.type === "render" && typeof data.id === "string" && typeof data.source === "string";
}

//: The parent's colours, kept to plain values: a key that is a word and a
//: value that is a colour or a font stack, nothing else reaches Mermaid.
function mermaidFrameVariables(raw) {
  const out = {};
  if (!raw || typeof raw !== "object") return out;
  for (const [key, value] of Object.entries(raw)) {
    if (!/^[A-Za-z][A-Za-z0-9]{0,40}$/.test(key)) continue;
    if (typeof value === "boolean") out[key] = value;
    else if (typeof value === "string" && value.length <= 120 && /^[#\w(),.%\s"'-]+$/.test(value)) out[key] = value;
  }
  return out;
}

//: One line for under the code block. Mermaid's parse errors run to several
//: lines with the source and a caret picture between "Parse error on line 3:"
//: and "Expecting ...", so the reason is the first line and the last when the
//: last says what was expected.
function mermaidReasonLine(error) {
  const raw = String((error && error.message) || error || "").trim();
  const lines = raw.split("\n").map((l) => l.trim()).filter(Boolean);
  let line = lines[0] || "This is not a diagram Mermaid can read.";
  const last = lines[lines.length - 1];
  if (lines.length > 1 && /^(Expecting|Got|Unexpected)/.test(last)) line = `${line.replace(/:$/, "")}. ${last}`;
  const clean = line.replace(/\s+/g, " ").trim();
  return clean.length > 160 ? `${clean.slice(0, 159)}…` : clean;
}
// MERMAID-FRAME-PROTOCOL-END

//: An SVG as an <img> with no width or height of its own has no size to show
//: (Mermaid writes width="100%" and a max-width style). The viewBox is the
//: size, so it becomes the attributes, and the style goes.
function mermaidFrameSized(svgText, background) {
  //: A diagram with a `click` link has `<a xlink:href>` and Mermaid does not declare the prefix, so the picture was a parse error and a
  //: broken image (L-documents-78, measured: naturalWidth 0). Declared here, in the text, before it is read.
  if (/\bxlink:/.test(svgText) && !/xmlns:xlink=/.test(svgText)) svgText = svgText.replace("<svg", '<svg xmlns:xlink="http://www.w3.org/1999/xlink"');
  const doc = new DOMParser().parseFromString(svgText, "image/svg+xml");
  const root = doc.documentElement;
  if (!root || root.localName !== "svg" || doc.querySelector("parsererror")) return svgText;
  const box = (root.getAttribute("viewBox") || "").trim().split(/[\s,]+/).map(Number);
  if (box.length === 4 && box[2] > 0 && box[3] > 0) {
    root.setAttribute("width", String(Math.ceil(box[2])));
    root.setAttribute("height", String(Math.ceil(box[3])));
  }
  root.removeAttribute("style");
  const walk = doc.createTreeWalker(root, 4);
  for (let node = walk.nextNode(); node; node = walk.nextNode()) if (node.nodeValue.includes("&")) node.nodeValue = mermaidFrameSized.entities(node.nodeValue);
  //: The picture carries its own ground, so it reads the same on a printed
  //: page or in a saved file as in the theme it was drawn for (light text on
  //: a transparent picture vanished on white paper).
  if (background) {
    const rect = doc.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("width", "100%");
    rect.setAttribute("height", "100%");
    rect.setAttribute("fill", background);
    root.insertBefore(rect, root.firstChild);
  }
  if (!root.getAttribute("xmlns")) root.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  return new XMLSerializer().serializeToString(root);
}
// MERMAID-ENTITY-BEGIN
//: Mermaid turns a written `#quot;` into the text `&quot;` and, with SVG labels, serialises it as `&amp;quot;`, so the
//: picture showed the entity itself (1679 m). A text node that still holds a named or numeric entity gets the character.
//: A property of the one function, not a name of its own (the shared scope only shrinks).
mermaidFrameSized.entities = (text) =>
  String(text).replace(/&(quot|lt|gt|amp|apos|#\d{1,7});/g, (all, k) => ({ quot: '"', lt: "<", gt: ">", amp: "&", apos: "'" })[k] ?? (Number(k.slice(1)) <= 0x10ffff ? String.fromCodePoint(Number(k.slice(1))) : all));
// MERMAID-ENTITY-END

function mermaidFrameConfigure(variables) {
  //: `htmlLabels: false` everywhere: labels as SVG text, not foreignObject
  //: HTML, which an <img> does not draw the same in every browser and which
  //: is the markup the strict level exists to keep out.
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    htmlLabels: false,
    flowchart: { htmlLabels: false },
    suppressErrorRendering: true,
    theme: "base",
    themeVariables: variables,
    fontFamily: variables.fontFamily || "system-ui, sans-serif",
  });
}

const mermaidFrameRun = { seq: 0, chain: Promise.resolve() };



async function mermaidFrameDraw(request) {
  const mermaidFrameYield = () => new Promise((resolve) => setTimeout(resolve, 0));
  const source = request.source.trim();
  if (!source) return { error: "The diagram is empty." };
  if (source.length > MERMAID_FRAME_MAX_SOURCE) return { error: "This diagram is too long to draw here." };
  mermaidFrameConfigure(mermaidFrameVariables(request.themeVariables));
  const domId = `mmd${++mermaidFrameRun.seq}`;
  try {
    //: **Each step is its own task** (INBOX 1662: `DOMWindow.onmessage 245ms`): the draw ran inside the
    //: message's promise chain, so the parse, the layout and the SVG build were all billed to one handler
    //: and the page waited on the whole. A turn of the loop between them lets input and paint run.
    await mermaidFrameYield();
    await mermaid.parse(source);
    await mermaidFrameYield();
    const { svg } = await mermaid.render(domId, source);
    await mermaidFrameYield();
    const ground = mermaidFrameVariables(request.themeVariables).background;
    return { svg: mermaidFrameSized(svg, typeof ground === "string" ? ground : "") };
  } catch (error) {
    return { error: mermaidReasonLine(error) };
  } finally {
    //: A failed render can leave its scratch element in the body.
    document.getElementById(`d${domId}`)?.remove();
    document.getElementById(domId)?.remove();
  }
}

window.addEventListener("message", (event) => {
  if (!mermaidFrameAccepts(event, window.parent, location.origin)) return;
  const id = event.data.id;
  //: Mermaid keeps one global config, so draws run one at a time.
  mermaidFrameRun.chain = mermaidFrameRun.chain
    .then(() => mermaidFrameDraw(event.data))
    .then((result) => window.parent.postMessage({ type: "result", id, ...result }, location.origin));
});

window.parent.postMessage({ type: "ready" }, location.origin);
