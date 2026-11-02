
let py = null;
let interruptSet = false;
//: D2's buffer, from the page when it is cross-origin isolated: [0] is the
//: flag this worker waits on, [1] the reply's length, the reply's bytes
//: after. `exchange` posts a stop (or an input() prompt) and blocks on
//: `Atomics.wait` until the page writes the panel's answer and notifies.
let shared = null;
let current = null;
function exchange(text) {
  if (!shared || !current) return null;
  const ctl = new Int32Array(shared, 0, 2);
  Atomics.store(ctl, 0, 0);
  current(JSON.parse(String(text)));
  Atomics.wait(ctl, 0, 0);
  const n = Atomics.load(ctl, 1);
  return new TextDecoder().decode(new Uint8Array(shared, 8, n).slice());
}
function ask(prompt) {
  const reply = exchange(JSON.stringify({ t: "input", prompt: String(prompt) }));
  try {
    const value = JSON.parse(reply);
    return value && typeof value.line === "string" ? value.line : null;
  } catch (err) {
    return null;
  }
}
//: One load, however many callers: a Run that arrives while the page's
//: warm-up is still loading waits on the same promise instead of starting a
//: second runtime (Brief 101c). A failed load is forgotten so the next try
//: reports its own error.
let loading = null;
function load(post) {
  if (py) return Promise.resolve(py);
  if (!loading) {
    loading = (async () => {
      post({ t: "status", text: "Starting Python" });
      const mod = await import(BASE + "pyodide.mjs");
      const loaded = await mod.loadPyodide({ indexURL: BASE, stdin: () => null });
      loaded.runPython(RUNNER);
      py = loaded;
      return loaded;
    })();
    loading.catch(() => { loading = null; });
  }
  return loading;
}
self.onmessage = async (e) => {
  const run = e.data.run;
  const post = (msg) => postMessage({ run, msg });
  //: Warm-up (Brief 101c): load the runtime and say nothing; a failure is the
  //: first real run's to report. Never marks the worker busy.
  if (e.data.warm) {
    try { await load(() => {}); } catch (err) { /* reported by the first run */ }
    return;
  }
  //: A new document's panel: the console must not read the last document's
  //: variables, and the runtime itself stays loaded.
  if (e.data.forget) {
    if (py) { try { py.runPython("_MM_NS.clear()"); } catch (err) { /* nothing to forget */ } }
    return;
  }
  shared = e.data.sab instanceof SharedArrayBuffer ? e.data.sab : null;
  current = post;
  try {
    const p = await load(post);
    if (e.data.interrupt instanceof SharedArrayBuffer && !interruptSet) {
      p.setInterruptBuffer(new Uint8Array(e.data.interrupt));
      interruptSet = true;
    }
    post({ t: "started" });
    //: The app stops a run at 500 lines, but only once it has read 500:
    //: measured in Chromium, a `while True: print(i)` posted lines far
    //: faster than the app's tab could take them, and the backlog kept the
    //: tab busy for minutes after Stop. So the cap is kept here too, at the
    //: source: past it, nothing more is posted and the app's Stop arrives
    //: behind at most 500 messages.
    let sent = 0;
    const emit = (level, text, line, uncaught) => {
      sent += 1;
      if (sent > MAX_LINES && !uncaught) return;
      post({
        t: "log", level: String(level), text: String(text),
        line: line == null ? null : Number(line), uncaught: Boolean(uncaught),
      });
    };
    if (e.data.eval) {
      //: The console (D8): one line in the last run's namespace.
      const evaluate = p.globals.get("_mm_eval");
      try { evaluate(String(e.data.source || ""), emit); } finally { evaluate.destroy(); }
      post({ t: "eval-done", ok: true });
      postMessage({ run, idle: true });
      return;
    }
    const t0 = performance.now();
    const emitTest = (name, state, ms, text, line) => post({
      t: "test", name: String(name), state: String(state), ms: Number(ms) || 0,
      text: String(text || ""), line: line == null ? null : Number(line),
    });
    if (e.data.tests && !e.data.debug) {
      //: Tests (D7): one `test` row per test, then the totals.
      const tester = p.globals.get("_mm_tests");
      let counts = null;
      try {
        counts = tester(String(e.data.source || ""), emit, emitTest, Number(e.data.lineOffset) || 0);
        const totals = counts.toJs({ dict_converter: Object.fromEntries });
        post({ t: "tests-done", passed: totals.passed, failed: totals.failed, skipped: totals.skipped, ms: Math.round(performance.now() - t0) });
      } finally {
        if (counts && counts.destroy) counts.destroy();
        tester.destroy();
      }
    } else if (e.data.debug) {
      //: Debug (D2): the run goes through `bdb`; each stop blocks here.
      const debug = p.globals.get("_mm_debug");
      let ended = "done";
      try {
        ended = String(debug(String(e.data.source || ""), emit, exchange, Number(e.data.lineOffset) || 0,
          String(e.data.stdin || ""), JSON.stringify(e.data.breaks || []), JSON.stringify(e.data.watches || []),
          e.data.tests ? emitTest : null));
        //: A file of tests debugged (row 563) ends with its totals, as Run's does.
        const held = p.globals.get("_MM_DEBUG_TESTS");
        const totals = e.data.tests ? held.get(0) : null;
        held.destroy();
        if (totals) {
          const t = totals.toJs({ dict_converter: Object.fromEntries });
          post({ t: "tests-done", passed: t.passed, failed: t.failed, skipped: t.skipped, ms: Math.round(performance.now() - t0) });
          totals.destroy();
        }
      } finally { debug.destroy(); }
      post({ t: "done", ended });
      postMessage({ run, idle: true });
      return;
    } else {
      const runner = p.globals.get("_mm_run");
      try {
        runner(String(e.data.source || ""), emit, Number(e.data.lineOffset) || 0, String(e.data.stdin || ""), shared ? ask : null);
      } finally { runner.destroy(); }
    }
    post({ t: "done" });
  } catch (err) {
    post({ t: "log", level: "error", text: "Python could not run: " + String((err && err.message) || err), line: null, uncaught: true });
    if (e.data.eval) post({ t: "eval-done", ok: false });
  }
  postMessage({ run, idle: true });
};
