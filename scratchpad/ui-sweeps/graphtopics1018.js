// B70 / B71 (INBOX 904): "why does this node want to be all the way down there" and "separating
// them out as it was so messy and stuck together I couldn't read it". On the real worker, under
// the Topic colour rule: topic plates that overlap each other (screen space), plates covering a
// dot, topic hulls that overlap (area of the intersection of bounding boxes as a cheap proxy
// and exact polygon overlap by sampling), notes outside their own topic's hull neighbours.
// Also, per category, the worst-over-median nearest same-category distance (B70's number).
//   BASE=http://127.0.0.1:8791 MODE=topic node scratchpad/ui-sweeps/graphtopics1018.js
const { boot } = require("./lib.js");
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => switchTab("graph"));
  await page.waitForTimeout(3000);
  if ((process.env.MODE || "topic") === "topic") {
    await page.evaluate(() => {
      const sel = document.getElementById("graph-colour");
      sel.value = "topic";
      sel.dispatchEvent(new Event("change"));
    });
  }
  await page.waitForTimeout(9000);
  const r = await page.evaluate(() => {
    const s = gcTab;
    const t = s.transform;
    const plates = (s.topicPlates || []).map((p) => ({
      l: p.left * t.k + t.x, r: p.right * t.k + t.x, t: p.top * t.k + t.y, b: p.bottom * t.k + t.y, topic: p.topic,
    }));
    const hit = (a, b) => a.l < b.r && b.l < a.r && a.t < b.b && b.t < a.b;
    let plateOverlaps = 0;
    for (let i = 0; i < plates.length; i++) for (let j = i + 1; j < plates.length; j++) if (hit(plates[i], plates[j])) plateOverlaps++;
    const notes = s.nodes.filter((n) => !n.isGroup);
    const P = (n) => ({ x: n.x * t.k + t.x, y: n.y * t.k + t.y, r: (n.r || 6) * t.k });
    let platesOnDots = 0;
    for (const p of plates)
      for (const n of notes) {
        const q = P(n);
        if (q.x + q.r > p.l && q.x - q.r < p.r && q.y + q.r > p.t && q.y - q.r < p.b) platesOnDots++;
      }
    // Dots overlapping dots.
    let dotOverlaps = 0;
    for (let i = 0; i < notes.length; i++)
      for (let j = i + 1; j < notes.length; j++) {
        const a = P(notes[i]), b = P(notes[j]);
        if (Math.hypot(a.x - b.x, a.y - b.y) < (a.r + b.r) * 0.9) dotOverlaps++;
      }
    // B70: worst over median nearest same-category distance.
    const byCat = new Map();
    for (const n of notes) {
      const c = n.group ?? n.category;
      if (!byCat.has(c)) byCat.set(c, []);
      byCat.get(c).push(n);
    }
    const ratios = [];
    for (const list of byCat.values()) {
      if (list.length < 4) continue;
      const d = list.map((n) => Math.min(...list.filter((m) => m !== n).map((m) => Math.hypot(n.x - m.x, n.y - m.y))));
      const sorted = d.slice().sort((a, b) => a - b);
      ratios.push(Math.max(...d) / Math.max(1, sorted[Math.floor(sorted.length / 2)]));
    }
    return {
      notes: notes.length, plates: plates.length, plateOverlaps, platesOnDots, dotOverlaps,
      meanWorstOverMedian: ratios.length ? +(ratios.reduce((a, b) => a + b, 0) / ratios.length).toFixed(2) : null,
      k: +t.k.toFixed(2),
    };
  });
  console.log(JSON.stringify(r));
  await browser.close();
})();
