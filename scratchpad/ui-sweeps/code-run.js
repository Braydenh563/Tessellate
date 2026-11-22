// Brief 69 (DOCUMENTS_PLAN 23, I1): every kind of run, preview and test a code
// document has, driven in Chromium through the one run protocol
// (run-core.js, api/run_sandbox.py). Each kind opens a document, presses Run
// (or Run tests), waits for the panel to say it finished, and checks the rows
// it shows. Times are click to the first row and click to the end.
//
// Usage: BASE=http://127.0.0.1:8869 [WIDTH=390] [ONLY=ts,sql] node code-run.js
// WIDTH=390 runs the phone shell (touch, coarse pointer). Python kinds need
// the Pyodide extra installed in the server's data dir; without it they check
// the disabled Run and its one line instead.
const { boot } = require("./lib.js");

const WIDTH = Number(process.env.WIDTH || 1440);
const ONLY = (process.env.ONLY || "").split(",").filter(Boolean);
let bad = 0;
let good = 0;
const ok = (n, c, d) => {
  if (c) good += 1;
  else bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};
const J = JSON.stringify;
const times = {};

(async () => {
  const phone = WIDTH < 600;
  const { browser, page } = await boot(phone
    ? { viewport: { width: WIDTH, height: 844 }, hasTouch: true, isMobile: true }
    : { viewport: { width: WIDTH, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => {
    if (!/about:srcdoc|blob:null/.test(String(e.stack))) errors.push(e.message);
  });
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);

  const open = async (title, fileType, content) => {
    await page.evaluate(
      async ([t, f, c]) => {
        const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: t, content: c, file_type: f }) });
        await loadDocuments(d.id);
      },
      [title, fileType, content]
    );
    await page.waitForTimeout(1200);
  };
  const output = () =>
    page.evaluate(() => {
      const panel = document.querySelector(".cm-run-panel");
      if (!panel) return null;
      return {
        status: panel.querySelector(".cm-run-status").textContent,
        rows: [...panel.querySelectorAll(".cm-run-row")].map((r) => ({
          cls: r.className.replace("cm-run-row ", ""),
          text: r.querySelector(".cm-run-text")?.textContent || "",
          why: r.querySelector(".cm-run-why")?.textContent || "",
          line: r.querySelector(".cm-run-line")?.textContent || null,
        })),
        tables: [...panel.querySelectorAll(".cm-run-table")].map((t) => ({
          head: [...t.querySelectorAll("th")].map((c) => c.textContent),
          rows: [...t.querySelectorAll("tbody tr")].map((r) => [...r.children].map((c) => c.textContent)),
        })),
        tests: [...panel.querySelectorAll(".cm-run-test")].map((r) => ({
          state: r.dataset.state,
          name: r.querySelector(".cm-run-text")?.textContent || "",
          ms: r.querySelector(".cm-run-ms")?.textContent || "",
          line: r.querySelector(".cm-run-line")?.textContent || null,
        })),
        page: panel.classList.contains("is-page"),
        frameH: Math.round(panel.querySelector(".cm-run-frame").getBoundingClientRect().height),
      };
    });
  //: Press Run (or a command) and wait until the status leaves "running":
  //: the time to the first row and to the end, measured in the page.
  const run = async (kind, how = "#doc-code-run", limit = 30000) => {
    const t = await page.evaluate(async ([sel, max]) => {
      const t0 = performance.now();
      let first = null;
      if (sel.startsWith("#")) document.querySelector(sel).click();
      else window[sel]();
      while (performance.now() - t0 < max) {
        await new Promise((r) => setTimeout(r, 25));
        const panel = document.querySelector(".cm-run-panel");
        if (!panel) continue;
        if (first === null && panel.querySelector(".cm-run-row, .cm-run-table, .cm-run-test")) first = performance.now() - t0;
        const status = panel.querySelector(".cm-run-status").textContent;
        const stop = panel.querySelector(".cm-run-head button[title='Stop the run']");
        if (status && !/^(Preparing|Running|Starting|Checking|Loading)/.test(status) && stop && stop.disabled) break;
        if (/^Page loaded|^Preview/.test(status)) break;
      }
      return { first: first === null ? null : Math.round(first), end: Math.round(performance.now() - t0) };
    }, [how, limit]);
    times[kind] = t;
    return output();
  };
  const want = (kind) => !ONLY.length || ONLY.includes(kind);

  if (want("js")) {
    await open("hello.js", "js", 'console.log("hello", 1 + 1);\nthrow new Error("boom");');
    const out = await run("js");
    ok("js: a log row and an error on its line", out && out.rows[0]?.text === "hello 2" && out.rows[1]?.line === "Line 2", J(out && out.rows));
  }

  if (want("tla")) {
    // L-documents-108: top-level await runs, lines stay the document's, a late throw lands on its line.
    await open("waits.js", "js", "const wait = (v) => new Promise((r) => setTimeout(() => r(v), 50));\nconsole.log('start');\nconst v = await wait(10);\nconsole.log('got', v);\nthrow new Error('late');");
    const out = await run("js");
    const rows = (out && out.rows) || [];
    ok("tla: top-level await runs, rows on lines 2, 4 and 5", rows[0]?.text === "start" && rows[0]?.line === "Line 2" && rows[1]?.text === "got 10" && rows[1]?.line === "Line 4" && /late/.test(rows[2]?.text || "") && rows[2]?.line === "Line 5", J(rows));
  }

  if (want("ts")) {
    await open("shapes.ts", "ts", [
      "interface Shape { area(): number }",
      "class Square implements Shape {",
      "  constructor(private side: number) {}",
      "  area(): number { return this.side * this.side; }",
      "}",
      "const s: Shape = new Square(3);",
      "console.log(`area ${s.area()}`);",
      "const n: number = undefinedName as number;",
    ].join("\n"));
    const out = await run("ts");
    ok("ts: says it runs without type checking", out && out.rows[0]?.cls === "is-info" && /without type checking/.test(out.rows[0].text), J(out && out.rows[0]));
    ok("ts: runs and logs on its line", out && out.rows[1]?.text === "area 9" && out.rows[1]?.line === "Line 7", J(out && out.rows[1]));
    ok("ts: an error keeps the document's line", out && out.rows[2]?.cls === "is-error" && out.rows[2]?.line === "Line 8", J(out && out.rows[2]));
    await open("broken.ts", "ts", "const a: number = 1;\nconst b = (;\n");
    const bad2 = await run("ts-parse");
    ok("ts: a parse error is a row on its line", bad2 && bad2.rows.some((r) => r.cls === "is-error" && r.line === "Line 2"), J(bad2 && bad2.rows));
  }

  if (want("sql")) {
    await open("people.sql", "sql", [
      "-- a table, three rows, a query",
      "CREATE TABLE people (name TEXT, age INTEGER);",
      "INSERT INTO people VALUES ('Ada', 36), ('Alan', 41), ('Grace', NULL);",
      "SELECT name, age FROM people ORDER BY name;",
      "",
      "SELECT count(*) AS n FROM people WHERE age > 40;",
      "SELECT * FROM missing;",
    ].join("\n"));
    const out = await run("sql");
    ok("sql: CREATE and INSERT say what they changed", out && out.rows[0]?.cls === "is-info" && out.rows[1]?.text === "3 rows changed." && out.rows[1]?.line === "Line 3", J(out && out.rows.slice(0, 2)));
    ok("sql: a SELECT is a table on its line", out && out.tables[0] && J(out.tables[0].head) === J(["name", "age"]) && out.tables[0].rows.length === 3 && out.rows[2]?.line === "Line 4", J(out && out.tables[0]));
    ok("sql: NULL shows as NULL", out && out.tables[0]?.rows[2]?.[1] === "NULL", J(out && out.tables[0]?.rows[2]));
    ok("sql: the second SELECT on line 6", out && out.tables[1]?.rows[0]?.[0] === "1" && out.rows[3]?.line === "Line 6", J(out && out.rows[3]));
    ok("sql: an error stops the run on its line", out && out.rows[4]?.cls === "is-error" && /no such table/.test(out.rows[4].text) && out.rows[4].line === "Line 7" && out.status === "Stopped by an error.", J(out && out.rows[4]) + " " + (out && out.status));
    const again = await run("sql-again");
    ok("sql: a second run starts from an empty database", again && again.rows[1]?.text === "3 rows changed.", J(again && again.rows[1]));
  }

  //: The page a preview made, inside the sandbox page inside the panel.
  const inPreview = async (fn) => {
    const frame = page.frames().find((f) => f.url() === "about:srcdoc");
    return frame ? frame.evaluate(fn) : null;
  };

  if (want("css")) {
    await open("site.css", "css", "h1 { color: rgb(200, 0, 0); }\n.card { border: 3px solid rgb(0, 0, 200); }\n");
    const out = await run("css");
    const seen = await inPreview(() => ({
      h1: getComputedStyle(document.querySelector("h1")).color,
      card: getComputedStyle(document.querySelector(".card")).borderTopColor,
      scripts: document.scripts.length,
    }));
    ok("css: previews against the sample page", out && out.page && out.frameH > 80 && out.status === "Preview shown.", J(out && { page: out.page, h: out.frameH, status: out.status }));
    ok("css: its rules apply to the sample", seen && seen.h1 === "rgb(200, 0, 0)" && seen.card === "rgb(0, 0, 200)" && seen.scripts === 0, J(seen));
    const liveShown = await page.evaluate(() => !document.querySelector(".cm-run-live").classList.contains("hidden"));
    ok("css: the Live toggle is offered", liveShown);
    //: Live on: a change refreshes the preview 400 ms after the typing stops.
    await page.evaluate(() => { if (!docRunLiveOn()) document.querySelector(".cm-run-live").click(); });
    await page.waitForTimeout(800);
    const t0 = Date.now();
    await page.evaluate(() => docCmView.dispatch({ changes: { from: 0, to: 0, insert: "h1 { color: rgb(0, 128, 0) !important; }\n" } }));
    let live = null;
    for (let i = 0; i < 40 && live !== "rgb(0, 128, 0)"; i += 1) {
      await page.waitForTimeout(100);
      live = await inPreview(() => getComputedStyle(document.querySelector("h1")).color).catch(() => null);
    }
    times["css-live"] = { end: Date.now() - t0 };
    ok("css: Live refreshes after a pause", live === "rgb(0, 128, 0)", `${live} in ${times["css-live"].end} ms`);
    await page.evaluate(() => { if (docRunLiveOn()) document.querySelector(".cm-run-live").click(); });
  }

  if (want("svg")) {
    await open("dot.svg", "svg", '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">\n  <circle cx="60" cy="40" r="30" fill="red"/>\n  <script>parent.postMessage("svg script ran", "*")</script>\n</svg>\n');
    const out = await run("svg");
    const seen = await inPreview(() => {
      const img = document.querySelector("img");
      return img ? { w: img.naturalWidth, h: img.naturalHeight } : null;
    });
    ok("svg: renders as an image", out && out.page && seen && seen.w === 120 && seen.h === 80 && out.status === "Preview shown.", J({ seen, status: out && out.status }));
    ok("svg: its script does not run", out && out.rows.length === 0, J(out && out.rows));
    await open("bad.svg", "svg", '<svg xmlns="http://www.w3.org/2000/svg">\n  <circle r="3">\n</svg>\n');
    const broken = await run("svg-broken");
    ok("svg: a broken file is an error on its line", broken && broken.rows[0]?.cls === "is-error" && broken.rows[0]?.line === "Line 3", J(broken && broken.rows));
  }

  if (want("p5")) {
    await open("sketch.js", "js", [
      "function setup() {",
      "  createCanvas(100, 60);",
      "  noLoop();",
      "}",
      "function draw() {",
      "  background(220, 0, 0);",
      "  console.log('drawn', width, height);",
      "}",
    ].join("\n"));
    const out = await run("p5", "#doc-code-run", 15000);
    await page.waitForTimeout(500);
    const seen = await inPreview(() => {
      const c = document.querySelector("canvas");
      if (!c) return null;
      const px = c.getContext("2d").getImageData(10, 10, 1, 1).data;
      return { w: c.width, h: c.height, px: [px[0], px[1], px[2]] };
    });
    const after = await output();
    ok("p5: a sketch runs as a page with p5", out && out.page, J(out && { page: out.page, status: out.status }));
    ok("p5: its canvas is drawn", seen && seen.px[0] > 200 && seen.px[1] < 30, J(seen));
    ok("p5: its console arrives on its line", after && after.rows.some((r) => r.text === "drawn 100 60" && r.line === "Line 7"), J(after && after.rows));
    await open("broken-sketch.js", "js", "function setup() {\n  createCanvas(50, 50);\n  notAFunction();\n}\n");
    await run("p5-error", "#doc-code-run", 15000);
    await page.waitForTimeout(800);
    const bad3 = await output();
    ok("p5: an error in setup is a row on its line", bad3 && bad3.rows.some((r) => r.cls === "is-error" && r.line === "Line 3"), J(bad3 && bad3.rows));
  }

  //: Tests (D7): each test listed with its state and time, a failure on its
  //: line in the panel and as a diagnostic in the editor.
  const diagnostics = () => page.evaluate(() => {
    const out = [];
    window.CM6.lint.forEachDiagnostic(docCmView.state, (d) => out.push({ line: docCmView.state.doc.lineAt(d.from).number, message: d.message, source: d.source }));
    return out.filter((d) => d.source === "tests");
  });
  if (want("jstest")) {
    await open("math.test.js", "js", [
      "const add = (a, b) => a + b;",
      "describe('add', () => {",
      "  it('adds', () => {",
      "    expect(add(1, 2)).toBe(3);",
      "  });",
      "  it('compares lists', () => {",
      "    expect([add(1, 1), 3]).toEqual([2, 4]);",
      "  });",
      "  it.skip('later', () => {});",
      "});",
      "test('async', async () => {",
      "  await new Promise((r) => setTimeout(r, 20));",
      "  expect('abc').toMatch(/b/);",
      "});",
    ].join("\n"));
    const out = await run("jstest");
    await page.waitForTimeout(1500);
    const marks = await diagnostics();
    ok("js tests: Run on a test file lists each test", out && out.tests.length === 4, J(out && out.tests));
    ok("js tests: state and time per test", out && J(out.tests.map((t) => t.state)) === J(["pass", "fail", "skip", "pass"]) && out.tests.every((t) => /^\d+ ms$/.test(t.ms)), J(out && out.tests));
    ok("js tests: a failure is on its expect line", out && out.tests[1].line === "Line 7" && out.rows.some((r) => /Expected: \[2,4\]/.test(r.why)), J(out && out.tests[1]));
    ok("js tests: the totals end the run", out && /2 passed, 1 failed, 1 skipped\./.test(out.status), out && out.status);
    ok("js tests: the failure is a diagnostic on line 7", marks.some((d) => d.line === 7), J(marks));
  }
  if (want("tstest")) {
    await open("calc.test.ts", "ts", [
      "function mul(a: number, b: number): number { return a * b; }",
      "describe('mul', () => {",
      "  it('multiplies', () => { expect(mul(2, 3)).toBe(6); });",
      "  it('fails', () => { expect(mul(2, 2)).toBe(5); });",
      "});",
    ].join("\n"));
    const out = await run("tstest");
    ok("ts tests: run with types stripped", out && J(out.tests.map((t) => t.state)) === J(["pass", "fail"]) && out.tests[1].line === "Line 4", J(out && out.tests));
  }

  const pyReady = await page.evaluate(async () => docRunPythonReady());
  if (want("py") && pyReady) {
    await open("hello.py", "py", "name = 'world'\nprint(f'hello {name}')\nprint(1 / 0)\n");
    const out = await run("py", "#doc-code-run", 60000);
    ok("py: print arrives on its line", out && out.rows[0]?.text === "hello world" && out.rows[0]?.line === "Line 2", J(out && out.rows));
    ok("py: an exception on its line", out && out.rows[1]?.cls === "is-error" && /ZeroDivisionError/.test(out.rows[1].text) && out.rows[1].line === "Line 3", J(out && out.rows[1]));
  }
  if (want("pytest") && pyReady) {
    await open("test_math.py", "py", [
      "import unittest",
      "",
      "class TestMath(unittest.TestCase):",
      "    def test_add(self):",
      "        self.assertEqual(1 + 1, 2)",
      "",
      "    def test_list(self):",
      "        self.assertEqual([1, 2], [1, 3])",
      "",
      "def test_plain():",
      "    assert 2 + 2 == 4",
      "",
      "if __name__ == '__main__':",
      "    unittest.main()",
    ].join("\n"));
    const out = await run("pytest", "#doc-code-run", 60000);
    await page.waitForTimeout(1500);
    const marks = await diagnostics();
    ok("py tests: unittest and plain tests listed in order", out && J(out.tests.map((t) => [t.name, t.state])) === J([["TestMath.test_add", "pass"], ["TestMath.test_list", "fail"], ["test_plain", "pass"]]), J(out && out.tests));
    ok("py tests: the failure's diff is shown, on its line", out && out.tests[1].line === "Line 8" && out.rows.some((r) => /Lists differ/.test(r.why)), J(out && out.tests[1]));
    ok("py tests: totals", out && /2 passed, 1 failed\./.test(out.status), out && out.status);
    ok("py tests: a diagnostic on line 8", marks.some((d) => d.line === 8), J(marks));
  }
  if (want("pyinput") && pyReady) {
    await open("ask.py", "py", "name = input('Name? ')\nage = int(input('Age? '))\nprint(f'{name} is {age}')\n");
    await page.evaluate(() => { if (docRun) { docRun.stdin.value = ""; DOC_RUN_STDIN.clear(); } });
    //: Brief 70: with the box empty, input() asks in the log mid-run (D2's
    //: buffer) instead of failing; Enter answers, Escape is the end of input.
    const t0 = Date.now();
    await page.click("#doc-code-run");
    const asked = await page.waitForSelector(".cm-run-ask-field", { timeout: 60000 }).then(() => true).catch(() => false);
    times["pyinput-ask"] = { first: Date.now() - t0 };
    const box = await page.evaluate(() => !!docRun && !docRun.stdinWrap.classList.contains("hidden"));
    ok("py input: a file that calls input() opens the Input box", box);
    const prompt = asked ? await page.evaluate(() => document.querySelector(".cm-run-row.is-ask .cm-run-text").textContent) : null;
    ok("py input: with no lines, input() asks in the log mid-run", asked && prompt === "Name? ", J(prompt));
    if (asked) {
      await page.fill(".cm-run-ask-field", "Ada");
      await page.press(".cm-run-ask-field", "Enter");
      await page.waitForFunction(() => document.querySelector(".cm-run-row.is-ask .cm-run-text")?.textContent === "Age? ", null, { timeout: 5000 }).catch(() => {});
      await page.fill(".cm-run-ask-field", "36");
      await page.press(".cm-run-ask-field", "Enter");
      await page.waitForFunction(() => /^Finished/.test(document.querySelector(".cm-run-status")?.textContent || ""), null, { timeout: 10000 }).catch(() => {});
    }
    const asked2 = await output();
    ok("py input: answered mid-run, prompt and answer on one row", asked2 && J(asked2.rows.map((r) => r.text)) === J(["Name? Ada", "Age? 36", "Ada is 36"]), J(asked2 && asked2.rows));
    await page.fill(".cm-run-stdin", "Ada\n36");
    const out = await run("pyinput", "#doc-code-run", 60000);
    ok("py input: answered from the panel, prompt and answer on one row", out && J(out.rows.map((r) => r.text)) === J(["Name? Ada", "Age? 36", "Ada is 36"]), J(out && out.rows));
  }
  if (want("cell") && pyReady) {
    await open("cells.py", "py", "# %% first\nprint('one')\n# %% second\nx = 2\nprint('two', x)\n# %% third\nprint('three')\n");
    await page.evaluate(() => { const line = docCmView.state.doc.line(5); docCmView.dispatch({ selection: { anchor: line.from } }); });
    const out = await run("cell", "docRunCell", 60000);
    ok("py cell: runs only the cell at the caret, on its own lines", out && J(out.rows.map((r) => [r.text, r.line])) === J([["two 2", "Line 5"]]), J(out && out.rows));
    await page.evaluate(() => { const d = docCmView.state.doc; docCmView.dispatch({ selection: { anchor: d.line(7).from, head: d.line(7).to } }); });
    const sel = await run("selection", "docRunSelection", 60000);
    ok("py selection: runs the selected line", sel && J(sel.rows.map((r) => [r.text, r.line])) === J([["three", "Line 7"]]), J(sel && sel.rows));
  }
  if (want("jscell")) {
    await open("cells.js", "js", "// %% a\nconsole.log('a');\n// %% b\nfunction f() {\n    console.log('b');\n}\nf();\n");
    await page.evaluate(() => { const d = docCmView.state.doc; docCmView.dispatch({ selection: { anchor: d.line(5).from, head: d.line(5).to } }); });
    const sel = await run("jsselection", "docRunSelection");
    ok("js selection: an indented line runs dedented, on its own line", sel && J(sel.rows.map((r) => [r.text, r.line])) === J([["b", "Line 5"]]), J(sel && sel.rows));
  }
  if (!pyReady && want("nopy")) {
    //: DOCUMENTS_PLAN 25 row 2: Run disabled, one line, the Packages link.
    await open("nopy.py", "py", "print('hi')\n");
    const state = await page.evaluate(() => ({
      disabled: document.getElementById("doc-code-run").disabled,
      shown: !document.getElementById("doc-code-run").classList.contains("hidden"),
      why: document.getElementById("doc-code-run-why").classList.contains("hidden") ? null : document.getElementById("doc-code-run-why").textContent.trim(),
    }));
    ok("no python: Run shows, disabled, with one line", state.shown && state.disabled && state.why === "Install Python in Settings, Packages", J(state));
    await page.click("#doc-code-run-why");
    await page.waitForTimeout(2500);
    const reached = await page.evaluate(() => !!document.getElementById("extra-row-pyodide") && document.activeElement?.closest("#extra-row-pyodide") !== null);
    ok("no python: the line opens Settings, Packages, at Python", reached);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);
  }
  if (!pyReady) console.log("SKIP  python runs: the Pyodide extra is not installed in this data dir");

  if (want("activity")) {
    //: 25 row 9: a long run is a job in Activity, and Stop there stops it.
    await open("ticks.js", "js", "let n = 0;\nsetInterval(() => console.log('tick', ++n), 400);\n");
    await page.click("#doc-code-run");
    await page.waitForTimeout(3200);
    const listed = await page.evaluate(async () => (await apiJson("/activity")).jobs.filter((j) => j.kind === "code-run"));
    ok("activity: a run past two seconds is listed with Stop", listed.length === 1 && listed[0].stoppable && listed[0].label === "Running ticks.js", J(listed));
    const t0 = Date.now();
    if (listed[0]) await page.evaluate(async (id) => apiJson(`/activity/${encodeURIComponent(id)}/stop`, { method: "POST" }), listed[0].id);
    let status = "";
    for (let i = 0; i < 40 && status !== "Stopped from Activity."; i += 1) {
      await page.waitForTimeout(100);
      status = await page.evaluate(() => document.querySelector(".cm-run-status").textContent);
    }
    times["activity-stop"] = { end: Date.now() - t0 };
    ok("activity: Stop there stops the run here", status === "Stopped from Activity.", `${status} in ${times["activity-stop"].end} ms`);
    await page.waitForTimeout(800);
    const after = await page.evaluate(async () => (await apiJson("/activity")).jobs.filter((j) => j.kind === "code-run").length);
    ok("activity: and its row is gone", after === 0, String(after));
  }

  //: The panel's layout at this width: the head fits (no sideways
  //: overflow), the grip's hairline sits on the head's top edge whatever the
  //: grip's hit box is, and a tap 30 px above the line reaches the grip at a
  //: coarse pointer (its box grew upward, the line did not move).
  {
    await open("layout.js", "js", "console.log('layout');");
    await run("layout");
    const lay = await page.evaluate(() => {
      const panel = document.querySelector(".cm-run-panel");
      const head = panel.querySelector(".cm-run-head");
      const grip = panel.querySelector(".doc-run-resize");
      const g = grip.getBoundingClientRect();
      const h = head.getBoundingClientRect();
      const p = panel.getBoundingClientRect();
      const probe = document.elementFromPoint(Math.round(g.left + g.width / 2), Math.round(g.bottom - 30));
      return {
        headOverflow: head.scrollWidth - head.clientWidth,
        lineToHead: Math.round((g.bottom - h.top) * 10) / 10,
        gripH: Math.round(g.height * 10) / 10,
        panelTopToHead: Math.round((h.top - p.top) * 10) / 10,
        tapAbove: probe === grip,
      };
    });
    ok(`layout ${WIDTH}: the head fits its width`, lay.headOverflow <= 0, J(lay));
    ok(`layout ${WIDTH}: the hairline is on the head's top edge`, Math.abs(lay.lineToHead) <= 0.5 && lay.panelTopToHead <= 7.5, J(lay));
    if (phone) ok("layout 390: the grip takes a tap 30 px above its line", lay.tapAbove && lay.gripH >= 44, J(lay));
    //: The '?' opens the panel's help, inside the window.
    await page.click(".cm-run-help");
    await page.waitForTimeout(300);
    const help = await page.evaluate(() => {
      const body = document.getElementById("doc-run-help");
      const r = body.getBoundingClientRect();
      return { shown: !body.classList.contains("hidden") && r.height > 20, left: Math.round(r.left), right: Math.round(r.right), top: Math.round(r.top), bottom: Math.round(r.bottom), lines: body.querySelectorAll("p").length, w: innerWidth, h: innerHeight };
    });
    //: Five since Brief 70 added Debug's line and Brief 71 the tabs' and keys' lines.
    ok(`layout ${WIDTH}: the '?' opens five lines of help inside the window`, help.shown && help.lines === 5 && help.left >= 0 && help.right <= help.w && help.top >= 0 && help.bottom <= help.h, J(help));
    await page.click(".cm-run-help");
  }

  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`times ${WIDTH}: ${J(times)}`);
  console.log(`\n${good} passed, ${bad} failed`);
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
