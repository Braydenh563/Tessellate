// INBOX 1413: the graph note popup follows its node and its head drags it.
// Measures popup-to-node offset before/after a 200px pan and a zoom, the
// drag distance against the move, the overlap with its own node (0 wanted),
// and that a dragged popup stays put through a pan. One JSON line.
const { boot } = require("./lib.js");
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(async () => {
    for (let i = 0; i < 8; i++) {
      await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: `Follow probe ${i}\nsome words about harbour ${i}`, tags: ["probe"] }) }).catch(() => null);
    }
  });
  await page.evaluate(() => switchTab("graph"));
  await page.waitForTimeout(4000);
  const open = () => page.evaluate(async () => {
    const s = gcTab;
    const n = Array.from(s.byId.values()).find((x) => !x.isGroup && x.type !== "tag" && Number.isFinite(x.x));
    const t = s.transform;
    const c = s.canvas.getBoundingClientRect();
    await openGraphPopup({ stopPropagation() {}, clientX: c.left + n.x * t.k + t.x, clientY: c.top + n.y * t.k + t.y }, n);
    window.__n = n.id;
    return n.id;
  });
  const read = () => page.evaluate(() => {
    const s = gcTab, n = s.byId.get(window.__n), t = s.transform, c = s.canvas.getBoundingClientRect();
    const sx = c.left + n.x * t.k + t.x, sy = c.top + n.y * t.k + t.y, r = n.r * t.k;
    const p = document.getElementById("graph-popup").getBoundingClientRect();
    const ox = Math.max(0, Math.min(p.right, sx + r) - Math.max(p.left, sx - r));
    const oy = Math.max(0, Math.min(p.bottom, sy + r) - Math.max(p.top, sy - r));
    return { dx: Math.round(p.left - sx), dy: Math.round(p.top - sy), overlap: Math.round(ox * oy), away: document.getElementById("graph-popup").classList.contains("graph-popup-away"), k: +t.k.toFixed(2) };
  });
  const settle = () => page.waitForTimeout(700);
  const pan = (dx) => page.evaluate((dx) => { const s = gcTab; const t = s.transform; s.transform = Object.assign(Object.create(Object.getPrototypeOf(t)), t, { x: t.x + dx }); gcRequestDraw(s); }, dx);
  const zoom = () => page.evaluate(() => { const s = gcTab; const t = s.transform; const n = s.byId.get(window.__n); const k = t.k * 1.6; s.transform = Object.assign(Object.create(Object.getPrototypeOf(t)), t, { k, x: t.x + n.x * (t.k - k), y: t.y + n.y * (t.k - k) }); gcRequestDraw(s); });
  await open(); await settle();
  const before = await read();
  await pan(-200); await settle(); const panned = await read();
  await zoom(); await settle(); const zoomed = await read();
  const h = await page.evaluate(() => { const r = document.getElementById("graph-popup-title").getBoundingClientRect(); const p = document.getElementById("graph-popup").getBoundingClientRect(); return { x: r.left + 10, y: r.top + r.height / 2, pl: p.left, pt: p.top }; });
  await page.mouse.move(h.x, h.y); await page.mouse.down(); await page.mouse.move(h.x - 140, h.y + 90, { steps: 6 }); await page.mouse.up();
  await settle();
  const after = await page.evaluate(() => { const p = document.getElementById("graph-popup").getBoundingClientRect(); return { l: p.left, t: p.top }; });
  const drag = { moveX: Math.round(after.l - h.pl), moveY: Math.round(after.t - h.pt), asked: [-140, 90] };
  await pan(-200); await settle();
  const afterPan = await page.evaluate(() => { const p = document.getElementById("graph-popup").getBoundingClientRect(); return { l: p.left, t: p.top }; });
  const stay = Math.round(Math.hypot(afterPan.l - after.l, afterPan.t - after.t));
  const clamp = await page.evaluate(() => { const b = document.getElementById("graph-box").getBoundingClientRect(), p = document.getElementById("graph-popup").getBoundingClientRect(); return p.left >= b.left - 1 && p.right <= b.right + 1 && p.top >= b.top - 1; });
  await page.evaluate(() => document.getElementById("graph-popup-close").click());
  await open(); await settle();
  const reopened = await read();
  console.log(JSON.stringify({ before, panned, zoomed, drag, stayAfterPan: stay, clamped: clamp, reopened }));
  await browser.close();
})();
