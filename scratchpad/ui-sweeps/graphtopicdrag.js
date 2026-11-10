// **Topics are handled on the map** (the owner, 2026-10-10: "I cant rename a
// topic??", "I want to be able to drag whole topics around on the graph").
// On the notebook in the data dir, under Colour: Topic: the first topic's
// plate is hovered (title, cursor), dragged 140,70 px (every member moves by
// the same world delta and is pinned; one PUT /graph/pins), double-clicked
// (an inline field; a new name saved and shown on the plate and legend), then
// the old name restored. Pass: moved = members, spread < 1, pinned = members,
// pinsRequests 1, renamed true.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const puts = [];
  page.on("request", (r) => { if (r.method() === "PUT" && r.url().includes("/graph/pin")) puts.push(r.url().replace(/.*\/graph/, "/graph")); });
  await page.evaluate(() => { const c = document.getElementById("graph-colour"); localStorage.setItem("graph-colour", "topic"); });
  await page.evaluate(() => switchTab("graph"));
  await page.evaluate(() => { const c = document.getElementById("graph-colour"); if (c.value !== "topic") { c.value = "topic"; c.dispatchEvent(new Event("change", { bubbles: true })); } });
  await page.waitForTimeout(9000);
  const plate = await page.evaluate(() => {
    const s = gcTab, t = s.transform, p = s.topicPlates[0];
    if (!p) return null;
    const box = s.canvas.getBoundingClientRect();
    const topic = graphStructure.topics.find((x) => x.id === p.topic);
    return { x: box.left + t.applyX((p.left + p.right) / 2), y: box.top + t.applyY((p.top + p.bottom) / 2), id: p.topic, name: topic.name, size: topic.ids.length, plates: s.topicPlates.length };
  });
  if (!plate) { console.log(JSON.stringify({ error: "no plates" })); await browser.close(); return; }
  await page.mouse.move(plate.x, plate.y);
  await page.waitForTimeout(300);
  const hover = await page.evaluate(() => ({ title: gcTab.canvas.title, cursor: getComputedStyle(gcTab.canvas).cursor }));
  const before = await page.evaluate((id) => Object.fromEntries(gcTopicMembers(graphStructure.topics.find((t) => t.id === id)).map((n) => [n.id, [n.x, n.y]])), plate.id);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) { await page.mouse.move(plate.x + 14 * i, plate.y + 7 * i); await page.waitForTimeout(30); }
  await page.mouse.up();
  await page.waitForTimeout(1500);
  const after = await page.evaluate(({ id, before }) => {
    const k = gcTab.transform.k;
    const ms = gcTopicMembers(graphStructure.topics.find((t) => t.id === id));
    const deltas = ms.filter((n) => before[n.id]).map((n) => [n.x - before[n.id][0], n.y - before[n.id][1]]);
    const dx = deltas.map((d) => d[0]), dy = deltas.map((d) => d[1]);
    return { members: ms.length, moved: deltas.filter((d) => Math.hypot(d[0], d[1]) > 20 / k).length, spread: +(Math.max(...dx) - Math.min(...dx) + Math.max(...dy) - Math.min(...dy)).toFixed(2), meanScreen: [Math.round(dx.reduce((a, b) => a + b, 0) / dx.length * k), Math.round(dy.reduce((a, b) => a + b, 0) / dy.length * k)], pinned: ms.filter((n) => n.fx != null).length, card: !document.getElementById("graph-topic").classList.contains("hidden") };
  }, { id: plate.id, before });
  // Rename on the plate: where the plate is now.
  const moved = await page.evaluate((id) => {
    const s = gcTab, t = s.transform, p = s.topicPlates.find((q) => q.topic === id), box = s.canvas.getBoundingClientRect();
    return { x: box.left + t.applyX((p.left + p.right) / 2), y: box.top + t.applyY((p.top + p.bottom) / 2) };
  }, plate.id);
  await page.mouse.dblclick(moved.x, moved.y);
  await page.waitForTimeout(300);
  const field = await page.evaluate(() => { const f = document.querySelector(".graph-topic-rename"); if (!f) return null; const r = f.getBoundingClientRect(); return { value: f.value, focused: document.activeElement === f, w: Math.round(r.width), h: Math.round(r.height) }; });
  await page.keyboard.press("Control+A");
  await page.keyboard.type("Sweep topic");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(800);
  const renamed = await page.evaluate((id) => ({ legend: document.querySelector(`#graph-legend [data-topic="${id}"]`)?.textContent, name: graphStructure.topics.find((t) => t.id === id).name }), plate.id);
  const server = await page.evaluate(() => apiJson("/graph/structure?topics=1")).then((b) => b.topics.find((t) => t.id === plate.id)?.name);
  // Put the found name back.
  await page.evaluate((id) => gcSaveTopicName(graphStructure.topics.find((t) => t.id === id), ""), plate.id);
  await page.waitForTimeout(500);
  const restored = await page.evaluate(() => apiJson("/graph/structure?topics=1")).then((b) => b.topics.find((t) => t.id === plate.id)?.name);
  await page.evaluate(() => api("/graph/unpin-all", { method: "POST" }));
  console.log(JSON.stringify({ plate, hover, after, pinsRequests: puts.filter((u) => u === "/graph/pins").length, singlePins: puts.filter((u) => u !== "/graph/pins").length, field, renamed, server, restored }));
  await browser.close();
})();
