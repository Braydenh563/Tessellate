// L886: the breakpoint lane's tap size under a coarse pointer at 390 (touch emulation).
//   BASE=http://127.0.0.1:8817 node scratchpad/ui-sweeps/docsverify-lane.js
process.env.BASE ||= "http://127.0.0.1:8817";
process.env.SCRATCH ||= require("os").tmpdir();
const { boot } = require("./lib.js");
let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? "PASS" : "FAIL"}  ${n}  ${JSON.stringify(d)}`); };
(async () => {
  const { browser, page } = await boot({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);
  await page.evaluate(async () => {
    const text = "function f(n) {\n  return n * 2;\n}\nlet t = 0;\nfor (let i = 0; i < 3; i++) {\n  t += f(i);\n}\nconsole.log(t);\n";
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "lane " + Date.now(), content: text, file_type: "js" }) });
    await loadDocuments(d.id);
  });
  await page.waitForFunction(() => [...document.querySelectorAll(".cm-debug-gutter .cm-gutterElement")].some((e) => e.getBoundingClientRect().height > 0), null, { timeout: 20000 });
  await page.waitForTimeout(800);
  const m = await page.evaluate(() => {
    const coarse = matchMedia("(pointer: coarse)").matches;
    const els = [...document.querySelectorAll(".cm-debug-gutter .cm-gutterElement")].filter((e) => e.getBoundingClientRect().height > 0);
    const g = document.querySelector(".cm-debug-gutter");
    const r = (e) => { const b = e.getBoundingClientRect(); return { l: Math.round(b.left * 10) / 10, w: Math.round(b.width * 10) / 10, h: Math.round(b.height * 10) / 10 }; };
    return { coarse, n: els.length, lane: r(g), el: els.slice(0, 4).map(r), widthCss: getComputedStyle(els[0]).width, lineH: getComputedStyle(document.querySelector(".cm-line")).lineHeight };
  });
  console.log(JSON.stringify(m));
  ok("coarse pointer matches", m.coarse, m.coarse);
  ok("lane tap width >= 44", m.el[0].w >= 44, m.el[0].w);
  // A row is one line tall (the line pitch); the lane cannot be taller than the line without overlapping its neighbours.
  ok("lane row height is the line pitch", Math.abs(m.el[0].h - parseFloat(m.lineH)) < 1, [m.el[0].h, m.lineH]);
  const box = await page.evaluate(() => { const e = [...document.querySelectorAll(".cm-debug-gutter .cm-gutterElement")].filter((x) => x.getBoundingClientRect().height > 0)[3]; const b = e.getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; });
  await page.touchscreen.tap(box.x, box.y);
  await page.waitForTimeout(500);
  ok("tap on the lane sets a breakpoint", (await page.evaluate(() => docDebugBreaks().map((b) => b.line).join())) === "4", await page.evaluate(() => docDebugBreaks()));
  console.log(bad ? `${bad} FAILED` : "all passed");
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
