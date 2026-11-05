// desk-frames.js: the desktop companion's frames for a companion that has none shipped
// (INBOX 1684: "why cant the companion be the regular ones like the ones based off my name,
// saved or persona?"). Lazy: the desk overlay loads it with `lazyScript` when the desk
// overlay needs a look it has no pictures of, and nothing else loads it.
//
// The shipped Atlas frames come from `scripts/render_desk_frames.js`, which needs a browser
// driven from outside. This is the same capture done inside the page: the app's own figure
// (`characterFor(seed).figure()`, the `#nm-buddy` clone below) is posed by the app's own
// classes, frozen at a chosen moment, copied with its computed styles into an SVG
// `foreignObject`, drawn to a canvas and read back as a PNG. A wide, transparent picture per
// frame; `core/overlay/capture.py` crops them to one box and caches them per companion.
//
// **Not on the live figure.** The live `#nm-buddy` keeps running on its own timers, and its
// rules are keyed on that id. The page's stylesheets are copied once with `#nm-buddy` made
// `#nmb-cap` (a constructed sheet, which the CSP allows), and a deep clone with that id is
// posed off screen, so the person's companion is never touched or repainted.
//
// The pull is by polling (`deskFramesStart`, then `deskFramesNext` until it answers "done"),
// because the host's `evaluate_js` returns one value and does not wait for a promise.

(() => {
const DESK_FRAME_CAP_ID = "nmb-cap";
//: The capture box in CSS pixels, and where the figure's top-left sits in it: roomy, cropped later.
const DESK_FRAME_BOX = { width: 280, height: 300, left: 110, top: 70 };
const DESK_FRAME_SCALE = 2;
const DESK_IDLE_N = 24;
const DESK_WALK_N = 12;

//: name -> pose, classes and the moment: `at` seconds into each running animation, `phase` of its cycle.
const DESK_FRAME_SPECS = [
  { name: "stand", pose: "stand", classes: [] },
  { name: "blink", pose: "stand", classes: ["nmb-act-blink"], at: 0.12 },
  { name: "look", pose: "stand", classes: ["nmb-act-look"], at: 1.1 },
  ...Array.from({ length: DESK_WALK_N }, (_, i) => ({ name: `walk${i}`, pose: "stand", classes: ["nmb-walking"], phase: i / DESK_WALK_N })),
  { name: "sit", pose: "sit", classes: [] },
  { name: "sleep", pose: "sit", classes: ["nmb-sleep"], at: 1.0 },
  { name: "wave", pose: "stand", classes: ["nmb-desk-wave"], at: 0.45, arm: "rotate(-140deg)" },
  { name: "held", pose: "stand", classes: ["nm-buddy-dragging"] },
  { name: "fall", pose: "stand", classes: ["nmb-act-startle"], at: 0.25 },
  { name: "land", pose: "stand", classes: ["nmb-act-land"], at: 0.1 },
  { name: "hop", pose: "stand", classes: ["nmb-act-hop"], at: 0.3 },
  { name: "hang", pose: "hang", classes: [] },
  { name: "tumble", pose: "stand", classes: ["nmb-act-startle"], at: 0.25, spin: 115 },
  //: One breath, a raised cosine on the figure's height about its feet, so the loop closes on itself.
  ...Array.from({ length: DESK_IDLE_N }, (_, i) => ({ name: `idle${i}`, pose: "stand", classes: [], breath: i / DESK_IDLE_N })),
];

const deskFrames = { sheet: null, job: null };

//: The page's rules that name `#nm-buddy`, as a sheet that names `#nmb-cap`. Nested rules come
//: with their parent's text, so one replace covers them.
function deskFramesSheet() {
  if (deskFrames.sheet) return deskFrames.sheet;
  const texts = [];
  const walk = (rules) => {
    for (const rule of rules) {
      let text = "";
      try { text = rule.cssText; } catch (e) { continue; }
      if (text.includes("#nm-buddy")) texts.push(text.split("#nm-buddy").join("#" + DESK_FRAME_CAP_ID));
    }
  };
  for (const sheet of document.styleSheets) {
    try { walk(sheet.cssRules); } catch (e) { /* a sheet from another origin has no readable rules */ }
  }
  const sheet = new CSSStyleSheet();
  for (const text of texts) {
    try { sheet.insertRule(text, sheet.cssRules.length); } catch (e) { /* a rule the engine would not take whole is left out */ }
  }
  document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
  deskFrames.sheet = sheet;
  return sheet;
}

//: A frame's text of a pseudo-element, when it draws one.
function deskFramesPseudo(el, which) {
  const cs = getComputedStyle(el, which);
  const content = cs.content;
  if (!content || content === "none" || content === "normal") return null;
  const box = document.createElement("span");
  for (const prop of cs) box.style.setProperty(prop, cs.getPropertyValue(prop));
  box.style.setProperty("display", cs.display === "inline" ? "inline-block" : cs.display);
  const quoted = /^"(.*)"$/.exec(content);
  if (quoted) box.textContent = quoted[1];
  return box;
}

//: The element's subtree as a detached copy that carries what it looks like now, as inline
//: declarations (set through the CSSOM, which the CSP allows), pseudo-elements made real.
function deskFramesBake(el, withPseudo = true) {
  const copy = el.cloneNode(false);
  if (el.nodeType !== 1) return copy;
  const cs = getComputedStyle(el);
  copy.removeAttribute("style");
  copy.removeAttribute("id");
  for (const prop of cs) copy.style.setProperty(prop, cs.getPropertyValue(prop));
  if (withPseudo && el.namespaceURI === "http://www.w3.org/1999/xhtml") {
    const before = deskFramesPseudo(el, "::before");
    if (before) copy.appendChild(before);
  }
  for (const child of el.childNodes) {
    if (child.nodeType === 1) copy.appendChild(deskFramesBake(child, withPseudo));
    else if (child.nodeType === 3) copy.appendChild(child.cloneNode());
  }
  if (withPseudo && el.namespaceURI === "http://www.w3.org/1999/xhtml") {
    const after = deskFramesPseudo(el, "::after");
    if (after) copy.appendChild(after);
  }
  return copy;
}

//: A clone of the live companion under the capture id, off screen, with the person's own figure in it.
function deskFramesBuild() {
  const real = document.getElementById("nm-buddy");
  if (!real) throw new Error("no #nm-buddy");
  deskFramesSheet();
  const clone = real.cloneNode(true);
  clone.id = DESK_FRAME_CAP_ID;
  for (const gone of clone.querySelectorAll(".nm-say, .nmb-size-grip, .nm-buddy-x")) gone.remove();
  const host = document.createElement("div");
  host.setAttribute("aria-hidden", "true");
  for (const [k, v] of Object.entries({ position: "fixed", left: "-10000px", top: "0", width: DESK_FRAME_BOX.width + "px", height: DESK_FRAME_BOX.height + "px", "pointer-events": "none", overflow: "hidden" })) host.style.setProperty(k, v, "important");
  host.appendChild(clone);
  document.body.appendChild(host);
  for (const k of ["left", "top", "right", "bottom", "transform", "opacity", "visibility", "display"]) clone.style.removeProperty(k);
  for (const name of clone.getAttributeNames()) if (name.startsWith("data-") && !["data-gait", "data-seed", "data-atlas-variant", "data-feel"].includes(name)) clone.removeAttribute(name);
  for (const [k, v] of Object.entries({ position: "absolute", left: DESK_FRAME_BOX.left + "px", top: DESK_FRAME_BOX.top + "px", opacity: "1", visibility: "visible", display: "block", transform: "none" })) clone.style.setProperty(k, v, "important");
  clone.classList.remove("nmb-away");
  return { host, clone };
}

//: Set the clone to a frame's pose and classes, move its animations to the frame's moment.
function deskFramesPose(clone, frame) {
  clone.className = frame.classes.join(" ");
  clone.dataset.pose = frame.pose;
  clone.dataset.feel = "calm";
  const char = clone.querySelector(".nm-buddy-char");
  for (const el of clone.querySelectorAll(".nm-buddy-char, .nmb-arm-r")) { el.style.removeProperty("transform"); el.style.removeProperty("transform-origin"); }
  for (const a of clone.getAnimations({ subtree: true })) {
    if (a.transitionProperty) { a.finish(); continue; }
    a.pause();
    if (!a.animationName || (frame.phase === undefined && frame.at === undefined)) continue;
    const t = a.effect.getComputedTiming();
    const cycle = (t.duration || 0) * (String(t.direction).startsWith("alternate") ? 2 : 1);
    const start = Math.max(0, t.delay || 0);
    a.currentTime = frame.phase !== undefined ? cycle * frame.phase + start : frame.at * 1000 + start;
  }
  if (char && frame.spin) {
    char.style.setProperty("transform", `rotate(${frame.spin}deg)`, "important");
    char.style.setProperty("transform-origin", "50% 45%", "important");
  }
  if (char && frame.breath !== undefined) {
    const k = (1 - Math.cos(frame.breath * 2 * Math.PI)) / 2;
    char.style.setProperty("transform", `scale(1, ${(1 + 0.02 * k).toFixed(4)})`, "important");
    char.style.setProperty("transform-origin", "50% 100%", "important");
  }
  const arm = frame.arm && clone.querySelector(".nmb-arm-r");
  if (arm) {
    //: A running animation outranks an inline value, so the arm's own are dropped first.
    for (const a of arm.getAnimations()) a.cancel();
    arm.style.setProperty("transform-origin", "50% 8%", "important");
    arm.style.setProperty("transform", frame.arm, "important");
  }
  //: A value set just now starts a CSS transition from the old one: finished, so the frame shows where it went.
  for (const a of clone.getAnimations({ subtree: true })) if (a.transitionProperty) a.finish();
}

//: The posed clone as one transparent PNG (base64) of the capture box.
async function deskFramesShot(clone) {
  const { width, height } = DESK_FRAME_BOX;
  const baked = deskFramesBake(clone);
  baked.style.setProperty("position", "absolute", "important");
  const wrap = document.createElementNS("http://www.w3.org/1999/xhtml", "div");
  wrap.style.setProperty("position", "relative");
  wrap.style.setProperty("width", width + "px");
  wrap.style.setProperty("height", height + "px");
  wrap.appendChild(baked);
  const xhtml = new XMLSerializer().serializeToString(wrap).replace("<div ", '<div xmlns="http://www.w3.org/1999/xhtml" ');
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><foreignObject x="0" y="0" width="${width}" height="${height}">${xhtml}</foreignObject></svg>`;
  const image = new Image();
  image.decoding = "sync";
  const loaded = new Promise((ok, no) => { image.onload = ok; image.onerror = () => no(new Error("the figure would not draw")); });
  image.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  await loaded;
  const canvas = document.createElement("canvas");
  canvas.width = width * DESK_FRAME_SCALE;
  canvas.height = height * DESK_FRAME_SCALE;
  const ctx = canvas.getContext("2d");
  ctx.scale(DESK_FRAME_SCALE, DESK_FRAME_SCALE);
  ctx.drawImage(image, 0, 0);
  return canvas.toDataURL("image/png").split(",")[1];
}

//: Start a capture of `names` (all of them when omitted). The answer is a count, or "busy".
function deskFramesStart(names) {
  if (deskFrames.job && !deskFrames.job.done) return "busy";
  const want = Array.isArray(names) && names.length ? DESK_FRAME_SPECS.filter((f) => names.includes(f.name)) : DESK_FRAME_SPECS.slice();
  const { host, clone } = deskFramesBuild();
  deskFrames.job = { host, clone, todo: want, done: false, result: "", busy: false };
  return String(want.length);
}

function deskFramesEnd(job) {
  job.done = true;
  job.host.remove();
}

//: The next frame, by polling: `wait` while one is being drawn (started by the call before it), then
//: JSON `{name, png, width, height}` once, `{done: true}` at the end, or `{error}`. Each call is
//: synchronous because the host's `evaluate_js` returns one value and does not wait for a promise.
function deskFramesNext() {
  const job = deskFrames.job;
  if (!job) return JSON.stringify({ error: "not started" });
  if (job.result) {
    const out = job.result;
    job.result = "";
    return out;
  }
  if (job.busy) return "wait";
  if (job.done) return JSON.stringify({ done: true });
  if (!job.todo.length) {
    deskFramesEnd(job);
    return JSON.stringify({ done: true });
  }
  const frame = job.todo.shift();
  job.busy = true;
  const fail = (e) => {
    deskFramesEnd(job);
    job.busy = false;
    job.result = JSON.stringify({ error: `${frame.name}: ${e && e.message ? e.message : e}` });
  };
  try {
    deskFramesPose(job.clone, frame);
    deskFramesShot(job.clone).then((png) => {
      job.busy = false;
      job.result = JSON.stringify({ name: frame.name, png, width: DESK_FRAME_BOX.width * DESK_FRAME_SCALE, height: DESK_FRAME_BOX.height * DESK_FRAME_SCALE });
    }, fail);
  } catch (e) {
    fail(e);
  }
  return "wait";
}

//: Stop and clean up (the overlay was closed mid-capture).
function deskFramesStop() {
  if (deskFrames.job && !deskFrames.job.done) deskFramesEnd(deskFrames.job);
}

window.deskFramesStart = deskFramesStart;
window.deskFramesNext = deskFramesNext;
window.deskFramesStop = deskFramesStop;
})();
