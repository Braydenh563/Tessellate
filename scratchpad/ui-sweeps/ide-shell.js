// Brief 71 (DOCUMENTS_PLAN 23 I3, D8): the panel tabs and their chords, Problems,
// the JavaScript and Python consoles, and the four tab heights across a reload.
// Usage: BASE=http://127.0.0.1:8827 [NOPY=1] node ide-shell.js (Python needs the
// Pyodide extra in the server data dir).
const { boot } = require("./lib.js");
const J = JSON.stringify;
let good = 0, bad = 0;
const ok = (n, c, d) => { c ? good++ : bad++; console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`); };
(async () => {
  const W = Number(process.env.WIDTH || 1440);
  const phone = W < 600;
  const { browser, page } = await boot(phone ? { viewport: { width: W, height: 844 }, hasTouch: true, isMobile: true } : { viewport: { width: W, height: 900 } });
  const errs = []; page.on("pageerror", (e) => { if (!/about:srcdoc|blob:null/.test(String(e.stack))) errs.push(e.message); });
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);
  const open = async (title, type, content) => {
    const id = await page.evaluate(async ([t, f, c]) => { const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: t, content: c, file_type: f }) }); await loadDocuments(d.id); return d.id; }, [title, type, content]);
    await page.waitForTimeout(2200);
    return id;
  };
  const focusEditor = async () => { await page.evaluate(() => docCmView.focus()); await page.waitForTimeout(150); };
  const panel = () => page.evaluate(() => {
    const p = document.querySelector(".cm-run-panel");
    if (!p) return null;
    const sel = p.querySelector('[role=tab][aria-selected="true"]');
    return { tabs: [...p.querySelectorAll("[role=tab]")].map((t) => t.textContent), tab: sel && sel.dataset.tab, h: Math.round(p.getBoundingClientRect().height), headH: Math.round(p.querySelector(".cm-run-head").getBoundingClientRect().height), status: p.querySelector(".cm-run-status").textContent };
  });
  const jsId = await open("shell.js", "js", "let total = 40;\nconst add = (a, b) => a + b;\nfunction twice(n) {\n  console.log('twice', n);\n  return n * 2;\n}\nconsole.log(add(total, 2));\nconst broken = ;\n");
  await focusEditor();
  await page.keyboard.press("Control+j");
  await page.waitForTimeout(500);
  let p = await panel();
  ok("Ctrl+J opens the panel with five tabs (Debug is Brief 70's)", p && p.tabs.length === 5, J(p));
  await page.keyboard.press("Control+Shift+M");
  await page.waitForTimeout(400);
  p = await panel();
  const probs = await page.evaluate(() => ({ rows: [...document.querySelectorAll("#doc-panel-problems .cm-run-row")].map((r) => r.textContent), count: document.querySelector("#doc-panel-tab-problems .cm-panel-count").textContent }));
  ok("Ctrl+Shift+M shows Problems", p && p.tab === "problems", J(p));
  ok("Problems lists the parse error with a line link and counts it", probs.rows.length >= 1 && /Line 8/.test(probs.rows.join()) && probs.count === String(probs.rows.length), J(probs));
  await page.keyboard.press("Control+Shift+M");
  await page.waitForTimeout(300);
  ok("Ctrl+Shift+M again hides the panel", (await panel()) === null);
  const companionBefore = await page.evaluate(() => document.body.className);
  await focusEditor();
  await page.keyboard.press("Control+Shift+Y");
  await page.waitForTimeout(400);
  p = await panel();
  const active = await page.evaluate(() => document.activeElement.className);
  ok("Ctrl+Shift+Y shows the Console, focus in its line", p && p.tab === "console" && /cm-console-input/.test(active), J([p, active]));
  ok("the companion did not toggle too", companionBefore === (await page.evaluate(() => document.body.className)));
  // Heights: one per tab, survive a reload
  const want = { output: 210, problems: 260, tests: 180, console: 300 };
  for (const [tab, h] of Object.entries(want)) {
    //: Dragged on the grip, as a person sets it: `docIdeRunApply` is the
    //: closure's own since documents-ide.js was wrapped (L529).
    const g = await page.evaluate((t) => { docRunShowTab(t); const r = docRun.dom.querySelector(".doc-run-resize").getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, h: docRun.dom.getBoundingClientRect().height }; }, tab);
    await page.mouse.move(g.x, g.y);
    await page.mouse.down();
    await page.mouse.move(g.x, g.y - (h - g.h), { steps: 4 });
    await page.mouse.up();
  }
  // Fix the edit so the run is clean, then run and use the console
  await page.evaluate(() => { const d = docCmView.state.doc; const l = d.line(8); docCmView.dispatch({ changes: { from: l.from, to: l.to, insert: "const fixed = 1;" } }); });
  await page.evaluate(() => docRunCode());
  await page.waitForTimeout(1500);
  p = await panel();
  ok("a run shows Output", p && p.tab === "output" && /Finished/.test(p.status), J(p));
  await page.evaluate(() => docPanelToggle("console"));
  await page.waitForTimeout(200);
  const consoleRun = async (line) => { await page.fill(".cm-console-input", line); await page.press(".cm-console-input", "Enter"); await page.waitForTimeout(700); };
  await consoleRun("total + 2");
  await consoleRun("twice(total)");
  await consoleRun("nope.x");
  const crow = await page.evaluate(() => [...document.querySelectorAll("#doc-panel-console .cm-run-row")].map((r) => r.className.replace("cm-run-row ", "") + ": " + r.textContent));
  ok("JS console sees the run's let/const and functions", crow.some((r) => /is-result: 42/.test(r)) && crow.some((r) => /is-result: 80/.test(r)) && crow.some((r) => /twice 40Line 4/.test(r)), J(crow));
  ok("JS console reports an error as an error row", crow.some((r) => /is-error: ReferenceError/.test(r)), J(crow));
  await page.press(".cm-console-input", "ArrowUp");
  await page.press(".cm-console-input", "ArrowUp");
  ok("Up walks the history", (await page.inputValue(".cm-console-input")) === "twice(total)");
  await page.evaluate(() => { docRunShowTab("console"); docRunClearTab(); });
  ok("Clear empties the console", (await page.evaluate(() => document.querySelectorAll("#doc-panel-console .cm-run-row").length)) === 0);
  // reload and check heights
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);
  await page.fill("#lock-password", "testpassword123").catch(() => {});
  await page.click("#lock-submit").catch(() => {});
  await page.waitForTimeout(2500);
  await page.evaluate(async (id) => { switchTab("documents"); await new Promise((r) => setTimeout(r, 1500)); await loadDocuments(id); }, jsId);
  await page.waitForTimeout(2500);
  await page.evaluate(() => docPanelToggle(null));
  await page.waitForTimeout(400);
  const got = {};
  for (const tab of Object.keys(want)) {
    got[tab] = await page.evaluate((t) => { docRunShowTab(t); return Math.round(docRun.dom.getBoundingClientRect().height); }, tab);
  }
  ok("the four heights survive a reload", Object.keys(want).every((t) => got[t] === want[t]), J({ want, got }));
  // Python console
  if (!process.env.NOPY) {
    await open("shell.py", "py", "n = 20\ndef double(v):\n    print('doubling', v)\n    return v * 2\n");
    await page.evaluate(() => docRunCode());
    for (let i = 0; i < 40; i++) { await page.waitForTimeout(1000); const s = (await panel())?.status || ""; if (/Finished|Stopped|Not run/.test(s)) break; }
    await page.evaluate(() => docPanelToggle("console"));
    await page.waitForTimeout(200);
    await consoleRun("double(n) + 1");
    await page.waitForTimeout(2000);
    await consoleRun("import math; math.sqrt(16)");
    await page.waitForTimeout(1500);
    await consoleRun("undefined_name");
    await page.waitForTimeout(1500);
    const prow = await page.evaluate(() => [...document.querySelectorAll("#doc-panel-console .cm-run-row")].map((r) => r.className.replace("cm-run-row ", "") + ": " + r.textContent));
    ok("Python console sees the run's namespace", prow.some((r) => /41/.test(r)) && prow.some((r) => /doubling 20Line 3/.test(r)) && prow.some((r) => /4\.0/.test(r)), J(prow));
    ok("Python console errors as rows", prow.some((r) => /is-error: NameError/.test(r)), J(prow));
  }
  //: Problems fed by each check: HTML's, CSS's and TypeScript's in the
  //: browser, Python's compiler on the server (before any run).
  for (const [title, type, text, line] of [
    ["p.html", "html", "<div>\n  <p>hi</span>\n</div>\n<b>open\n", 2],
    ["p.css", "css", "a {\n  color: red;\n  }}\n", 3],
    ["p.ts", "ts", "const n: number = ;\n", 1],
    ["p.py", "py", "def f(:\n    return 1\n", 1],
  ]) {
    await open(title, type, text);
    await page.waitForTimeout(1500);
    await page.evaluate(() => docPanelToggle("problems"));
    await page.waitForTimeout(500);
    const got = await page.evaluate(() => ({ rows: [...document.querySelectorAll("#doc-panel-problems .cm-run-row")].map((r) => r.textContent), count: document.querySelector("#doc-panel-tab-problems .cm-panel-count").textContent }));
    ok(`Problems on a .${type} file: a row on line ${line}, counted`, got.rows.some((r) => r.endsWith(`Line ${line}`)) && got.count === String(got.rows.length), J(got));
    await page.evaluate(() => docRunClose());
  }
  ok("no page errors", errs.length === 0, J(errs));
  console.log(`${good}/${good + bad}`);
  await browser.close();
})();
