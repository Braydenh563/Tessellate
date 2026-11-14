// run-core.js: one run protocol for every language (DOCUMENTS_PLAN 23, D1).
//
// Lazy (`LAZY_MODULES.run` in app.js): documents-code.js loads it the first
// time Run, Run tests or a preview is asked for, so none of it is boot code.
//
// **The protocol.** The panel under the editor (documents-code.js, "Run, and
// its output") builds one request, `{kind, source, path, stdin, tests,
// lineOffset}`, and hands it here. The language's row in `RUN_LANGS` turns it
// into the message the sandbox page takes (`api/run_sandbox.py`, `RUNNERS`):
// a `kind` the page knows, the source after any pass (TypeScript's types
// stripped), and a vendored library's text where the runner needs one. Rows
// come back the same way for every language, `{t: "log", level, text, line,
// col}`, so the panel, Stop and the limits are shared and never per language.
//
// **A language is a row, not a branch.** Each row says which sandbox page it
// runs in (`page`), whether what it makes is a page to show (`shows`), and
// implements `run`, and optionally `test`. Adding a language is adding a row;
// the panel does not change.
//
// **Libraries never reach the sandbox by URL.** The sandbox page may fetch
// nothing (`connect-src 'none'`), so a library it needs (sql.js, p5) is
// fetched here, from this app's own origin, and posted over as text and
// bytes. The code that runs still has no network and none of the notebook.

const RUN_CORE = {
  //: The two sandbox pages. Python has its own because its policy names the
  //: runtime's folder; everything else shares the first.
  pages: { main: "/documents/run-sandbox", python: "/documents/run-sandbox/python" },
  //: One fetch per library for the life of the tab.
  loads: new Map(),
};

//: A vendored file as text (or bytes), fetched once. A failed fetch is not
//: kept, so the next Run tries again.
function runVendorFetch(url, as = "text") {
  const key = `${as}:${url}`;
  if (!RUN_CORE.loads.has(key)) {
    //: `api()` throws on a refusal and carries the session's token, so the
    //: vendored file is read the way every other same-origin file is.
    const load = api(url, { silent: true })
      .then((response) => (as === "bytes" ? response.arrayBuffer() : response.text()))
      .catch((error) => {
        RUN_CORE.loads.delete(key);
        throw error;
      });
    RUN_CORE.loads.set(key, load);
  }
  return RUN_CORE.loads.get(key);
}

//: A vendored script that runs in this page (the TypeScript pass), loaded
//: once as a `<script>` from the app's own origin under the app's policy.
function runVendorScript(url, global) {
  if (window[global]) return Promise.resolve(window[global]);
  const key = `script:${url}`;
  if (!RUN_CORE.loads.has(key)) {
    RUN_CORE.loads.set(key, new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = url;
      script.async = true;
      script.addEventListener("load", () => (window[global] ? resolve(window[global]) : reject(new Error(`${url} did not load`))));
      script.addEventListener("error", () => {
        RUN_CORE.loads.delete(key);
        reject(new Error(`${url} did not load`));
      });
      document.head.appendChild(script);
    }));
  }
  return RUN_CORE.loads.get(key);
}

//: The fields every message carries, whatever the language.
function runBase(request, kind) {
  return {
    kind,
    source: String(request.source || ""),
    path: String(request.path || ""),
    lineOffset: Math.max(0, Number(request.lineOffset) || 0),
  };
}

//: TypeScript to JavaScript (D4): sucrase strips the types and checks
//: nothing, keeping every line where it was, so a row's line is the
//: document's. `import` and `export` become the CommonJS names the runner
//: defines, only when the file has them (the pass adds "use strict"). A
//: parse error throws with its line, which the panel links.
async function runStripTypes(source, { jsx = false, types = true } = {}) {
  const sucrase = await runVendorScript("/vendor/sucrase/sucrase.min.js", "SUCRASE");
  const transforms = types ? ["typescript"] : [];
  if (jsx) transforms.push("jsx");
  if (/^\s*(?:import|export)\b/m.test(source)) transforms.push("imports");
  try {
    return sucrase.transform(source, { transforms, production: true }).code;
  } catch (error) {
    const where = /\((\d+):(\d+)\)/.exec(String(error?.message || ""));
    const failure = new Error(`Couldn't read this as ${types ? "TypeScript" : "JSX"}: ${String(error?.message || error).replace(/\s*\(\d+:\d+\)$/, "")}`);
    if (where) failure.line = Number(where[1]);
    throw failure;
  }
}

//: A p5.js sketch (D6, INBOX 735): a script that defines `setup` or `draw`
//: and makes a canvas. It runs as a page beside the vendored p5.min.js
//: rather than as a worker script, which has no canvas to draw on.
const RUN_P5_SKETCH = /\bfunction\s+(?:setup|draw)\s*\(/;
function runIsP5(source) {
  return RUN_P5_SKETCH.test(source) && /\bcreateCanvas\s*\(/.test(source);
}

//: Debug for JavaScript and TypeScript (D3): the script lowered to what
//: JS-Interpreter steps (run-debug.js), and the interpreter's text, fetched
//: here and handed over, as sql.js is. A p5 sketch draws in a page, which
//: the stepper has none of. Throws the pass's sentence, with its line.
async function runDebugScript(request, source) {
  if (runIsP5(source)) throw new Error("Debug steps scripts: a p5.js sketch draws in a page, so Run it instead.");
  const lowered = runDebugLower(source);
  const interp = await runVendorFetch("/vendor/js-interpreter/js-interpreter.min.js");
  //: A file of tests debugs through the worker's own harness (L314), so a
  //: breakpoint in a test body stops there and each test is listed.
  return { ...runBase(request, "jsdebug"), source: lowered.code, lib: { interp }, dom: lowered.dom, tests: runLooksLikeTests("js", source) };
}

//: JSX in a .js document (the jsx alias, OPEN 1072): a .jsx title, or
//: markup where an expression starts (after =, (, a comma, :, ?, => or
//: return). Only that pass runs: the file is JavaScript, so no types are
//: stripped. A comparison (`a < b`) has a name before its `<`, so it is not
//: taken for markup.
const RUN_JSX_MARKUP = /(?:^|[=(,:?]|=>|\breturn)\s*<(?:[A-Za-z][\w.]*[\s/>]|>)/m;
function runIsJsx(request) {
  return /\.jsx$/i.test(String(request.path || "")) || RUN_JSX_MARKUP.test(String(request.source || ""));
}

async function runJsRequest(request) {
  const base = runBase(request, "js");
  return runIsJsx(request) ? { ...base, source: await runStripTypes(base.source, { jsx: true, types: false }) } : base;
}

//: The languages. `page`: which sandbox page; `shows`: the run makes a page
//: to look at rather than (only) output rows; `debug`: what Debug sends.
const RUN_LANGS = {
  js: {
    label: "JavaScript",
    page: "main",
    test: async (request) => ({ ...(await runJsRequest(request)), tests: true, harness: runTestHarnessSource() }),
    debug: async (request) => runDebugScript(request, (await runJsRequest(request)).source),
    run: async (request) => {
      if (!runIsP5(request.source)) return runJsRequest(request);
      const p5 = await runVendorFetch("/vendor/p5.min.js");
      return { ...runBase(request, "p5"), lib: { p5 }, shows: true, preview: true };
    },
  },
  ts: {
    label: "TypeScript",
    page: "main",
    notice: "TypeScript runs without type checking: the types are removed, not checked.",
    run: async (request) => ({ ...runBase(request, "js"), source: await runStripTypes(request.source, { jsx: /\.tsx$/i.test(request.path || "") }) }),
    test: async (request) => ({ ...(await RUN_LANGS.ts.run(request)), tests: true, harness: runTestHarnessSource() }),
    debug: async (request) => runDebugScript(request, await runStripTypes(request.source, { jsx: /\.tsx$/i.test(request.path || "") })),
  },
  //: SQL (D5): SQLite in the sandbox, an in-memory database per run, each
  //: statement's result a table in the panel. sql.js comes from this app's
  //: own server and is handed over, text and binary.
  sql: {
    label: "SQL",
    page: "main",
    run: async (request) => {
      const [js, wasm] = await Promise.all([
        runVendorFetch("/vendor/sqljs/sql-wasm.js"),
        runVendorFetch("/vendor/sqljs/sql-wasm.wasm", "bytes"),
      ]);
      const tables = (Array.isArray(request.tables) ? request.tables : []).map(({ name, columns, rows }) => ({ name, columns, rows }));
      return { ...runBase(request, "sql"), lib: { js, wasm }, tables };
    },
  },
  html: {
    label: "HTML",
    page: "main",
    shows: true,
    preview: true,
    run: (request) => runBase(request, "html"),
  },
  //: Previews (D6): a stylesheet over a sample page, an SVG as an image.
  css: {
    label: "CSS",
    page: "main",
    shows: true,
    preview: true,
    run: (request) => runBase(request, "css"),
  },
  svg: {
    label: "SVG",
    page: "main",
    shows: true,
    preview: true,
    run: (request) => runBase(request, "svg"),
  },
  //: A CSV file's Run shows it as a table: an HTML page drawn from its rows.
  csv: {
    label: "CSV",
    page: "main",
    shows: true,
    preview: true,
    run: (request) => ({ ...runBase(request, "html"), source: docCsvTableHtml(request.source, request.path) }),
  },
  py: {
    label: "Python",
    page: "python",
    run: (request) => ({ ...runBase(request, "py"), stdin: String(request.stdin || "") }),
    test: (request) => ({ ...RUN_LANGS.py.run(request), tests: true }),
    //: D2: `bdb` in the Pyodide worker, which needs the page isolated.
    //: A file of tests debugs through the harness, so a breakpoint in a
    //: test stops there (OPEN row 563).
    debug: (request) => ({
      ...RUN_LANGS.py.run(request), debug: true,
      tests: runLooksLikeTests("py", String(request.source || "")),
    }),
  },
};

//: The language a document runs as, or null. `ext` is the document's type.
function runLanguage(ext) {
  return Object.prototype.hasOwnProperty.call(RUN_LANGS, ext) ? RUN_LANGS[ext] : null;
}

//: The request turned into what the panel needs: the page to load, whether
//: the run shows a page, and the message to post. `mode` is "run", "test"
//: or "debug". Throws with a sentence the panel shows as the run's one row.
async function runPrepare(request, mode = "run") {
  const lang = runLanguage(request.ext);
  if (!lang) throw new Error("This kind of file does not run here.");
  //: Run on a file of tests runs its tests (D7): `describe` and `it` mean
  //: nothing without the harness, and a TestCase does nothing on its own.
  if (mode === "run" && lang.test && runLooksLikeTests(request.ext, String(request.source || ""))) mode = "test";
  const act = mode === "test" ? lang.test : mode === "debug" ? lang.debug : lang.run;
  if (typeof act !== "function") throw new Error(mode === "debug" ? `Debug steps JavaScript, TypeScript and Python; ${lang.label} runs with Run.` : `${lang.label} has no tests to run here.`);
  const { page, shows, preview, ...message } = await act(request);
  return {
    page: page || lang.page,
    shows: Boolean(shows ?? lang.shows),
    //: A preview refreshes itself while "Live" is on (D6).
    preview: Boolean(preview ?? lang.preview),
    //: Debug on a Python file of tests lists them too (row 563).
    tests: mode === "test" || Boolean(message.tests),
    debug: mode === "debug",
    notice: lang.notice || "",
    message,
  };
}
