// INBOX 1547: in Live, a drag selection that crosses a rendered diagram or
// equation leaves it drawn (no toggle, nothing below moves); a caret placed in
// it still shows its source.
const { boot } = require("./lib.js");
(async () => {
  const { page, browser } = await boot({});
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e.message).slice(0, 200)));
  await page.waitForTimeout(3000);
  const id = await page.evaluate(async () => {
    const headers = { "X-Auth-Token": localStorage.getItem("token") || "", "Content-Type": "application/json" };
    const body = "Flicker probe\n\nFirst paragraph above.\n\n```mermaid\ngraph TD; A-->B\n```\n\nMiddle with $x^2+1$ inline.\n\n$$\\frac{a}{b}$$\n\nLast paragraph below.\n";
    return (await (await fetch("/documents", { method: "POST", headers, body: JSON.stringify({ title: "Flicker probe", content: body }) })).json()).id;
  });
  await page.evaluate(async (id) => {
    switchTab("documents"); await new Promise((r) => setTimeout(r, 500));
    await openDocument(id); await new Promise((r) => setTimeout(r, 1500));
    if (typeof setDocView === "function") setDocView("live");
    await new Promise((r) => setTimeout(r, 2500));
  }, id);
  const state = () => page.evaluate(() => {
    const last = [...document.querySelectorAll(".cm-line")].find((l) => l.textContent.includes("Last paragraph"));
    return { maths: document.querySelectorAll(".cm-content .cm-md-math").length, mermaid: document.querySelectorAll(".cm-content .cm-md-mermaid, .cm-content [class*=mermaid]").length, lastY: last ? Math.round(last.getBoundingClientRect().top) : null };
  });
  const lineBox = (needle) => page.evaluate((n) => { const l = [...document.querySelectorAll(".cm-line")].find((x) => x.textContent.includes(n)); const r = l.getBoundingClientRect(); return [r.left + 20, r.top + r.height / 2]; }, needle);
  const s0 = await state();
  const [x0, y0] = await lineBox("First paragraph");
  const [x1, y1] = await lineBox("Last paragraph");
  await page.mouse.move(x0, y0); await page.mouse.down();
  const seen = [];
  for (let i = 1; i <= 12; i++) { await page.mouse.move(x0 + 40, y0 + ((y1 - y0) * i) / 12, { steps: 2 }); await page.waitForTimeout(60); seen.push(await state()); }
  await page.mouse.up(); await page.waitForTimeout(200);
  const toggles = seen.filter((s) => s.maths !== s0.maths || s.mermaid !== s0.mermaid).length;
  const shift = Math.max(...seen.map((s) => Math.abs(s.lastY - s0.lastY)));
  console.log(toggles === 0 ? "ok  " : "FAIL", "drag across: widget toggles", toggles, "of 12 steps; start", JSON.stringify(s0));
  console.log(shift <= 1 ? "ok  " : "FAIL", "line below moved at most", shift, "px");
  // A caret placed in the inline maths shows its source.
  const pos = await page.evaluate(() => docCmView.state.doc.toString().indexOf("x^2"));
  await page.evaluate((p) => { docCmView.focus(); docCmView.dispatch({ selection: { anchor: p } }); }, pos);
  await page.waitForTimeout(300);
  const s2 = await state();
  console.log(s2.maths === s0.maths - 1 ? "ok  " : "FAIL", "caret in $x^2+1$ shows its source", JSON.stringify(s2));
  console.log(errors.length ? "FAIL errors " + JSON.stringify(errors) : "ok   no errors");
  await browser.close();
})();
