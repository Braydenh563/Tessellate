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
// Written twice: a WARN line in Settings > Logs at once, and a batch every 10
// seconds to POST /logs/lag, which keeps them in `<data dir>/logs/lag.log`
// (core/lagwatch.py) across restarts. Nothing is sent anywhere but this app's
// own server. A hidden page reports nothing: a background tab's timers are
// throttled, and its "lag" is the browser's choice, not the app's.

const LAG = { queue: [], timer: 0, lastInput: "", lastAt: {} };
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
function lagScriptCause(scripts) {
  return [...(scripts || [])]
    .sort((a, b) => b.duration - a.duration)
    .slice(0, 3)
    .map((s) => {
      const name = s.sourceFunctionName || s.invoker || s.invokerType || "?";
      const layout = s.forcedStyleAndLayoutDuration >= 20 ? ` (forced layout ${Math.round(s.forcedStyleAndLayoutDuration)}ms)` : "";
      return `${lagFile(s.sourceURL)} ${name} ${Math.round(s.duration)}ms${layout}`;
    })
    .join("; ");
}

function lagNote(kind, ms, cause, extra = {}) {
  if (document.hidden) return;
  const now = Date.now();
  //: One report a kind per half second: a stall that spans several frames is
  //: one event to a person, and a flood would push the rest out of the log.
  if (now - (LAG.lastAt[kind] || 0) < 500) return;
  LAG.lastAt[kind] = now;
  const event = {
    at: new Date().toISOString(),
    kind,
    ms: Math.round(ms),
    view: lagView(),
    cause: cause || "no detail from the browser",
    input: LAG.lastInput,
    nodes: document.getElementsByTagName("*").length,
    heap_mb: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null,
    ...extra,
  };
  recordBrowserLog("WARN", [`Lag: ${kind} ${event.ms}ms on ${event.view}: ${event.cause}`]);
  LAG.queue.push(event);
  if (LAG.queue.length > 20) LAG.queue.shift();
  if (!LAG.timer) LAG.timer = setTimeout(lagFlush, 10000);
}

function lagFlush() {
  LAG.timer = 0;
  const events = LAG.queue.splice(0, 20);
  if (!events.length) return;
  api("/logs/lag", { method: "POST", body: JSON.stringify({ events }) }).catch(() => {});
}

function lagFrame(e) {
  if (e.duration < LAG_FRAME_MS) return;
  const layout = e.styleAndLayoutStart ? e.startTime + e.duration - e.styleAndLayoutStart : 0;
  const cause = lagScriptCause(e.scripts) || (layout >= 50 ? "style and layout" : "");
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
  //: The long-lived streams (chat, logs, events) are slow by design.
  if (!fetched || e.duration < LAG_REQUEST_MS || /\/stream\b|\/events\b/.test(e.name)) return;
  lagNote("request", e.duration, new URL(e.name, location.href).pathname);
}

function lagObserve(type, handle, options = {}) {
  if (!PerformanceObserver.supportedEntryTypes?.includes(type)) return false;
  new PerformanceObserver((list) => list.getEntries().forEach(handle)).observe({ type, buffered: true, ...options });
  return true;
}

function lagStart() {
  if (typeof PerformanceObserver === "undefined") return;
  if (!lagObserve("long-animation-frame", lagFrame)) {
    lagObserve("longtask", (e) => e.duration >= LAG_FRAME_MS && lagNote("frame", e.duration, ""));
  }
  lagObserve("event", lagInput, { durationThreshold: LAG_INPUT_MS });
  lagObserve("resource", lagRequest);
  for (const type of ["pointerdown", "keydown"]) {
    document.addEventListener(type, (e) => { LAG.lastInput = `${type} ${lagTarget(e.target)}`; }, { capture: true, passive: true });
  }
  //: A report waiting for its batch is sent when the page is hidden or closed.
  document.addEventListener("visibilitychange", () => document.hidden && lagFlush());
}

lagStart();
