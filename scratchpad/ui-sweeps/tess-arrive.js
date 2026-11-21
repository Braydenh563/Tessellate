//: L-graph-10: a new note's cell arrives in the Tessellation view, and not under reduced motion.
//: BASE=http://localhost:PORT node scratchpad/ui-sweeps/tess-arrive.js (measured 2026-11-12: arrives about 1.4 s, none reduced).
const {boot} = require(process.cwd()+"/scratchpad/ui-sweeps/lib.js");
(async () => {
  const {browser, page} = await boot();
  const api = (path, body) => page.evaluate(([path, body]) => apiJson(path, body ? {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)} : {}), [path, body]);
  await page.evaluate(() => prefs.set("graph-layout", "tessellation"));
  await page.click("#tab-btn-graph");
  await page.waitForTimeout(3000);
  const state = () => page.evaluate(() => ({kind: gcTab.layoutKind, cells: gcTab.tree && gcTab.tree.tess ? gcTab.tree.tess.cells.length : null, arrive: gcTab.tessArrive ? [...gcTab.tessArrive.keys()] : []}));
  const before = await state();
  await page.click("#tab-btn-notes"); await page.waitForTimeout(1000);
  const made = await api("/entries", {content: "# A new one\nfresh"});
  await page.click("#tab-btn-graph"); await page.waitForTimeout(200);
  console.log("active", await page.evaluate(() => [...document.querySelectorAll("[id^=tab-btn-]")].filter((b) => b.classList.contains("active") || b.getAttribute("aria-selected") === "true").map((b) => b.id)));
  const samples = [];
  for (let i = 0; i < 8; i++) { await page.waitForTimeout(250); samples.push((await state()).arrive.join(",")); }
  await page.emulateMedia({reducedMotion: "reduce"});
  const made2 = await api("/entries", {content: "# Another\nfresh"});
  await page.evaluate(() => renderGraph());
  await page.waitForTimeout(600);
  const still = await state();
  console.log(JSON.stringify({before, id: made.id, samples, id2: made2.id, still}));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
