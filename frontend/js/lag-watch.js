// lag-watch.js: the lag log's browser half (the owner, 2026-10-26: "can you
// make the app detect lag spikes or complexity issues ... and then it logs it
// and the cause or when it happened ... so if it happens then I can give you
// the logs?"). Loaded by drag-edge.js (`LAZY_MODULES.dragEdge`) with the other late
// bundles, three seconds after boot; the observers ask for `buffered` entries,
// so a stall during boot is still seen.
//
// What counts as lag, and what is written about it:
// - a frame that kept the page from answering for 200ms or more
//   (`long-animation-frame`, Chromium 123 and the desktop window's WebView2):
//   the scripts that ran in it, by file and function, and how much of it was
//   forced style and layout, which is the usual cause of a stall in a big DOM;
//   `longtask` where that entry type is missing, which names no cause;
// - a click, tap or key that took 300ms or more to paint its answer (`event`
//   timing): which control, and whether the time went in waiting, in the
//   handler or in drawing;
// - a request to this app's server that took 3 seconds or more.
// Each report also carries the view on screen, the last thing pressed (the
// element, never the text typed), the page's element count and the JS heap,
// because "slow" is usually one of those growing.
//
// INBOX 1430 (the owner, 2026-10-28: "so I can just give you the logs"): each
// report also carries the control pressed and how long before, the viewport,
// pixel ratio, cores and device memory (the server adds the notebook's size,
// the version and the build); a stall no script owns is merged into the last
// one instead of logged again; a sampler of `requestAnimationFrame` loops by
// owner reports a loop that costs too much a second; errors are counted by
// message; and `lagSnapshot` is the "why is it heavy" page of the report
// (diag-report.js builds the text).
//
// Written twice: a WARN line in Settings, Logs at once, and a batch every 10
// seconds to POST /logs/lag, which keeps them in `<data dir>/logs/lag.log`
// (core/lagwatch.py) across restarts. Nothing is sent anywhere but this app's
// own server. A hidden page reports nothing: a background tab's timers are
// throttled, and its "lag" is the browser's choice, not the app's.

//: The report's two files, as one lazy module (lazy-entries.js is a boot script and at its budget).
LAZY_MODULES.diagnostics = ["/js/lag-watch.js", "/js/diag-report.js"];

const LAG = { queue: [], timer: 0, lastInput: "", lastInputAt: 0, lastAt: {}, bare: {}, recent: [], errors: new Map() };
//: The frame sampler: a loop that spends more than `LAG_RAF_BUDGET_MS` of
//: every second for `LAG_RAF_SECONDS` seconds running is reported once.
const LAG_RAF_BUDGET_MS = 120;
const LAG_RAF_SECONDS = 3;
const LAG_RECENT_MS = 5 * 60 * 1000;
const LAG_RAF = { on: true, fns: new WeakMap(), bucket: new Map(), hot: new Map(), owners: new Map(), second: 0 };
const LAG_FRAME_MS = 200;
const LAG_INPUT_MS = 300;
const LAG_REQUEST_MS = 3000;

function lagView() {
  return prefs.get("activeTab", null) || "notes";
}

//: `button#ask-btn.primary`: enough to find the control, no text content.
function lagTarget(el) {
  if (!el || !el.tagName) return "";
  const cls = typeof el.className === "string" ? el.className.trim().split(/\s+/).slice(0, 2).join(".") : "";
  return `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}${cls ? "." + cls : ""}`.slice(0, 80);
}

function lagFile(url) {
  return String(url || "").split("?")[0].split("/").pop() || "inline";
}

//: The scripts that ran in a long frame, longest first: "documents.js
//: docRender 412ms (layout 120ms)".
function lagScriptCause(scripts, frame) {
  return [...(scripts || [])]
    .sort((a, b) => b.duration - a.duration)
    .slice(0, 3)
    .map((s) => {
      const name = s.sourceFunctionName || s.invoker || s.invokerType || "?";
      const layout = s.forcedStyleAndLayoutDuration >= 20 ? ` (forced layout ${Math.round(s.forcedStyleAndLayoutDuration)}ms)` : "";
      //: The sampler's own wrapper runs every animation callback, so LoAF names this file for
      //: them: say what they are and which loop cost most this second.
      const file = lagFile(s.sourceURL) === "lag-watch.js" ? `animation loops (top: ${lagRafTop()})` : `${lagFile(s.sourceURL)} ${name}`;
      return `${file} ${Math.round(s.duration)}ms${layout}${lagApiWho(name, frame)}`;
    })
    .join("; ");
}

//: `Response.json.then` is how LoAF names the continuation of `apiJson`'s caller.
//: Each answer is stamped with its path and the first script that asked.
const LAG_API = [];

function lagApi(path) {
  Error.stackTraceLimit = 8;
  const who = lagStackOwner(new Error().stack, /lag-watch\.js|at (?:async )?apiJson /);
  Error.stackTraceLimit = 10;
  return (data) => {
    LAG_API.push({ t: performance.now(), label: `${String(path).split("?")[0]} from ${who}` });
    if (LAG_API.length > 24) LAG_API.shift();
    return data;
  };
}

function lagApiWho(name, frame) {
  if (!/Response\.json\.then/.test(name)) return "";
  const seen = new Set(LAG_API.filter((a) => a.t >= frame.startTime && a.t <= frame.startTime + frame.duration).map((a) => a.label));
  return seen.size ? ` [apiJson ${[...seen].slice(0, 3).join(", ")}]` : "";
}

function lagNote(kind, ms, cause, extra = {}) {
  if (document.hidden) return;
  const now = Date.now();
  //: One report a kind per half second: a stall that spans several frames is
  //: one event to a person, and a flood would push the rest out of the log.
  if (now - (LAG.lastAt[kind] || 0) < 500) return;
  LAG.lastAt[kind] = now;
  LAG.recent.push({ at: now, kind, ms: Math.round(ms), cause: cause || "" });
  while (LAG.recent.length > 100 || (LAG.recent[0] && now - LAG.recent[0].at > LAG_RECENT_MS)) LAG.recent.shift();
  //: A stall no script owns names nothing, so a run of them is one report
  //: with a count and the worst time, not a line each.
  const bare = !cause && LAG.bare[kind];
  if (bare && LAG.queue.includes(bare) && now - bare.t < 10000) {
    bare.n += 1;
    bare.ms = Math.max(bare.ms, Math.round(ms));
    return;
  }
  const event = {
    at: new Date().toISOString(),
    kind,
    ms: Math.round(ms),
    view: lagView(),
    cause: cause || "no script attributed",
    input: LAG.lastInput,
    input_ago_ms: LAG.lastInput ? now - LAG.lastInputAt : null,
    nodes: document.getElementsByTagName("*").length,
    heap_mb: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null,
    vp: `${innerWidth}x${innerHeight}`,
    dpr: window.devicePixelRatio || 1,
    cores: navigator.hardwareConcurrency || null,
    mem_gb: navigator.deviceMemory || null,
    n: 1,
    ...extra,
  };
  if (cause) {
    recordBrowserLog("WARN", [`Lag: ${kind} ${event.ms}ms on ${event.view}: ${event.cause}`]);
  } else {
    event.t = now;
    LAG.bare[kind] = event;
  }
  LAG.queue.push(event);
  if (LAG.queue.length > 20) LAG.queue.shift();
  if (!LAG.timer) LAG.timer = setTimeout(lagFlush, 10000);
}

function lagFlush() {
  LAG.timer = 0;
  const events = LAG.queue.splice(0, 20).map(({ t, ...rest }) => rest);
  if (!events.length) return Promise.resolve();
  return api("/logs/lag", { method: "POST", body: JSON.stringify({ events }) }).catch(() => {});
}

function lagFrame(e) {
  if (e.duration < LAG_FRAME_MS) return;
  const layout = e.styleAndLayoutStart ? e.startTime + e.duration - e.styleAndLayoutStart : 0;
  const cause = lagScriptCause(e.scripts, e) || (layout >= 50 ? "style and layout" : "");
  lagNote("frame", e.duration, cause, { blocking_ms: Math.round(e.blockingDuration || 0), layout_ms: Math.round(layout) });
}

function lagInput(e) {
  if (e.duration < LAG_INPUT_MS) return;
  lagNote("input", e.duration, `${e.name} on ${lagTarget(e.target)}`, {
    wait_ms: Math.round(e.processingStart - e.startTime),
    run_ms: Math.round(e.processingEnd - e.processingStart),
    paint_ms: Math.round(e.startTime + e.duration - e.processingEnd),
  });
}

function lagRequest(e) {
  const fetched = e.initiatorType === "fetch" || e.initiatorType === "xmlhttprequest";
  //: The long-lived streams (chat, logs, events) and the long-poll the
  //: server holds open (`/auth/lan-watch`, 25 s a turn) are slow by design.
  if (!fetched || e.duration < LAG_REQUEST_MS || /\/stream\b|\/events\b|\/lan-watch\b/.test(e.name)) return;
  lagNote("request", e.duration, new URL(e.name, location.href).pathname);
}

function lagObserve(type, handle, options = {}) {
  if (!PerformanceObserver.supportedEntryTypes?.includes(type)) return false;
  new PerformanceObserver((list) => list.getEntries().forEach(handle)).observe({ type, buffered: true, ...options });
  return true;
}

//: The first stack line outside this file: "atlas-motion.js tick".
function lagStackOwner(stack, skip) {
  for (const line of String(stack).split("\n").slice(1)) {
    if (skip ? skip.test(line) : line.includes("lag-watch.js")) continue;
    const m = line.match(/at (?:(\S+) \()?[^\s()]*?([^/\s()]+\.js)[?:\d]/);
    if (m) return m[1] ? `${m[2]} ${m[1].replace(/^.*\./, "")}` : m[2];
  }
  return "unknown";
}

function lagRafOwner(fn) {
  let owner = LAG_RAF.fns.get(fn);
  if (owner) return owner;
  const limit = Error.stackTraceLimit;
  Error.stackTraceLimit = 5;
  owner = lagStackOwner(new Error().stack);
  Error.stackTraceLimit = limit;
  if (fn instanceof Function) LAG_RAF.fns.set(fn, owner);
  return owner;
}

function lagRafTop() {
  let top = "none";
  let most = 0;
  for (const [owner, s] of LAG_RAF.bucket) if (s.ms > most) [top, most] = [owner, s.ms];
  return top;
}

function lagRafClose(now) {
  for (const [owner, s] of LAG_RAF.bucket) {
    if (s.ms < LAG_RAF_BUDGET_MS) {
      LAG_RAF.hot.delete(owner);
      continue;
    }
    const seconds = (LAG_RAF.hot.get(owner) || 0) + 1;
    LAG_RAF.hot.set(owner, seconds);
    if (seconds >= LAG_RAF_SECONDS) {
      LAG_RAF.hot.delete(owner);
      lagNote("raf", s.ms, `${owner} ${s.n} calls/s, ${(s.ms / s.n).toFixed(1)}ms each (${Math.round(s.ms)}ms of every second)`);
    }
  }
  LAG_RAF.bucket.clear();
  LAG_RAF.second = now;
}

//: Wrapped once. Off, the wrapper hands the callback straight on: the cost
//: of the switch is one boolean read a call.
function lagRafInstall() {
  const native = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) => {
    if (!LAG_RAF.on) return native(cb);
    const owner = lagRafOwner(cb);
    return native((t) => {
      const t0 = performance.now();
      try {
        cb(t);
      } finally {
        const ms = performance.now() - t0;
        const s = LAG_RAF.bucket.get(owner) || { n: 0, ms: 0 };
        s.n += 1;
        s.ms += ms;
        LAG_RAF.bucket.set(owner, s);
        const all = LAG_RAF.owners.get(owner) || { n: 0, ms: 0, max: 0 };
        all.n += 1;
        all.ms += ms;
        if (ms > all.max) all.max = ms;
        LAG_RAF.owners.set(owner, all);
        if (t0 - LAG_RAF.second >= 1000) lagRafClose(t0);
      }
    });
  };
}

//: Errors by message and first frame, counted: a loop that throws sixty times
//: a second is one line with a count, and the table stops growing at 60.
function lagNoteError(message, stack) {
  const text = String(message || "").slice(0, 300);
  const key = `${text}|${String(stack || "").split("\n").slice(0, 2).join("|")}`.slice(0, 500);
  const known = LAG.errors.get(key);
  if (known) {
    known.n += 1;
    known.last = Date.now();
    return;
  }
  if (LAG.errors.size >= 60) return;
  LAG.errors.set(key, { n: 1, first: Date.now(), last: Date.now(), view: lagView(), message: text, stack: String(stack || "").slice(0, 1200) });
}

function lagErrorsStart() {
  //: What went wrong before this file loaded, from app.js's own record.
  for (const r of typeof browserLogs === "undefined" ? [] : browserLogs) {
    if (r.level === "ERROR") lagNoteError(r.message.slice(0, 200), r.message);
  }
  window.addEventListener("error", (e) => e.filename && lagNoteError(e.message, e.error?.stack || `${e.filename}:${e.lineno}`));
  window.addEventListener("unhandledrejection", (e) => lagNoteError(`Unhandled rejection: ${e.reason?.message || e.reason}`, e.reason?.stack));
  const original = console.error;
  console.error = (...parts) => {
    const said = (p) => (typeof p === "string" ? p : p?.message || JSON.stringify(p) || String(p));
    const stack = parts.find((p) => p?.stack)?.stack || new Error().stack;
    lagNoteError(parts.map(said).join(" "), stack.split("\n").filter((l) => !l.includes("lag-watch.js")).join("\n"));
    original(...parts);
  };
}

//: The "why is it heavy" page of the report, on demand: how many elements,
//: which hold the most children, the worst stalls of the last five minutes,
//: the ten most expensive animation loops and the heap.
function lagSnapshot() {
  const all = document.getElementsByTagName("*");
  const wide = [];
  for (const el of all) {
    if (el.childElementCount >= 100 && el.tagName !== "HEAD") wide.push([el.childElementCount, lagTarget(el)]);
  }
  wide.sort((a, b) => b[0] - a[0]);
  const cutoff = Date.now() - LAG_RECENT_MS;
  const owners = [...LAG_RAF.owners].sort((a, b) => b[1].ms - a[1].ms).slice(0, 10);
  return {
    nodes: all.length,
    wide: wide.slice(0, 5).map(([n, who]) => `${who} ${n} children`),
    longest: LAG.recent.filter((r) => r.at >= cutoff).sort((a, b) => b.ms - a.ms).slice(0, 5),
    raf: owners.map(([owner, s]) => ({ owner, calls: s.n, ms: Math.round(s.ms), avg: +(s.ms / s.n).toFixed(2), max: +s.max.toFixed(1) })),
    heap_mb: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null,
    sampler: LAG_RAF.on,
  };
}

//: Settings, Logs, the three dots: Copy diagnostics, Save as file and the sampler switch. Wired
//: here, not in settings.js, so the buttons cost the boot scripts nothing; this file is in by the
//: time anyone has opened Settings. The report itself (diag-report.js) is fetched on the first press.
function lagWireSettings() {
  const press = (id, run) => document.getElementById(id)?.addEventListener("click", () => ensureModule("diagnostics").then((ok) => ok && run()));
  press("logs-diag-copy", () => diagCopy());
  press("logs-diag-save", () => diagSave());
  const box = document.getElementById("logs-sampler");
  if (!box) return;
  box.checked = LAG_RAF.on;
  box.addEventListener("change", () => {
    LAG_RAF.on = box.checked;
    prefs.set("lagSampler", box.checked ? "on" : "off");
  });
}

function lagStart() {
  if (typeof PerformanceObserver === "undefined") return;
  if (!lagObserve("long-animation-frame", lagFrame)) {
    lagObserve("longtask", (e) => e.duration >= LAG_FRAME_MS && lagNote("frame", e.duration, ""));
  }
  lagObserve("event", lagInput, { durationThreshold: LAG_INPUT_MS });
  lagObserve("resource", lagRequest);
  LAG_RAF.on = prefs.get("lagSampler", "on") !== "off";
  lagRafInstall();
  lagErrorsStart();
  lagWireSettings();
  for (const type of ["pointerdown", "keydown"]) {
    document.addEventListener(type, (e) => { LAG.lastInput = `${type} ${lagTarget(e.target)}`; LAG.lastInputAt = Date.now(); }, { capture: true, passive: true });
  }
  //: A report waiting for its batch is sent when the page is hidden or closed.
  document.addEventListener("visibilitychange", () => document.hidden && lagFlush());
}

//: Wrapped here rather than edited in app.js (the boot scripts are at their gzip cap; status.js
//: wraps it the same way). The caller is read before the call, while it is still on the stack.
if (typeof apiJson === "function") {
  const apiJsonInner = apiJson;
  apiJson = function apiJson(path, options) {
    return apiJsonInner(path, options).then(lagApi(path));
  };
}

lagStart();
