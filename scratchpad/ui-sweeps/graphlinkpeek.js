// A line on the graph answers the pointer (the owner, 2026-10-04: "I cant
// click on links to see their reason in the graph??").
//
// Samples up to 20 drawn lines (link, thread, similar, map; at least 40px
// long on screen, midpoint clear of every dot), points at each one's middle
// with the real mouse and reads:
//
//   hover   the renderer's `hoverEdge` is that line, the canvas cursor is a
//           pointer
//   peek    a click there opens `#graph-link-peek`, naming the line's kind
//           and both notes; Escape closes it
//
//   BASE=http://127.0.0.1:8795 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/graphlinkpeek.js     (seed: graphlook.js)
const { boot, OUT } = require('./lib.js');

(async () => {
  const { browser, page } = await boot({ viewport: { width: Number(process.env.W || 1440), height: 900 } });
  try {
    await page.evaluate(() => switchTab('graph'));
    for (let i = 0; i < 60; i++) {
      await page.waitForTimeout(250);
      if (await page.evaluate(() => gcTab.nodes.length && gcTab.ticks > 5 && gcTab.alpha < 0.002)) break;
    }
    await page.waitForTimeout(1500);
    const picks = await page.evaluate(() => {
      const s = gcTab;
      const t = s.transform;
      const rect = s.canvas.getBoundingClientRect();
      const curved = gcRequestDraw.inspect.gcCurvedLinks(s) && !s.tree;
      const out = [];
      s.edges.forEach((e, i) => {
        const a = e.source, b = e.target;
        if (!GC_PEEK_KINDS.has(e.kind) || !a || !b || !Number.isFinite(a.x)) return;
        const c = curved ? gcRequestDraw.inspect.gcBowPoint(a, b) : { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
        const m = { x: 0.25 * a.x + 0.5 * c.x + 0.25 * b.x, y: 0.25 * a.y + 0.5 * c.y + 0.25 * b.y };
        const sx = rect.left + t.x + m.x * t.k;
        const sy = rect.top + t.y + m.y * t.k;
        if (Math.hypot(a.x - b.x, a.y - b.y) * t.k < 40) return;
        if (sx < rect.left + 20 || sx > rect.right - 20 || sy < rect.top + 60 || sy > rect.bottom - 20) return;
        if (gcRequestDraw.inspect.gcNodeAtWorld(m.x, m.y, s)) return;
        // Skip a middle another line crosses: there the nearer line is right.
        if (gcRequestDraw.inspect.gcEdgeAtWorld(m.x, m.y, s) !== e) return;
        out.push({ i, kind: e.kind, sx, sy });
      });
      return out.filter((_, j) => j % Math.max(1, Math.floor(out.length / 20)) === 0).slice(0, 20);
    });
    let hovered = 0;
    let peeked = 0;
    let cursor = 0;
    const misses = [];
    for (const p of picks) {
      await page.mouse.move(p.sx, p.sy);
      await page.waitForTimeout(60);
      const h = await page.evaluate((i) => ({ hit: gcTab.hoverEdge === gcTab.edges[i], cursor: getComputedStyle(gcTab.canvas).cursor }), p.i);
      if (h.hit) hovered += 1;
      if (h.cursor === 'pointer') cursor += 1;
      await page.mouse.click(p.sx, p.sy);
      await page.waitForTimeout(120);
      const peek = await page.evaluate(() => {
        const el = document.getElementById('graph-link-peek');
        return el ? { kind: el.querySelector('.graph-link-peek-kind')?.textContent, notes: el.querySelectorAll('.graph-link-peek-notes button').length } : null;
      });
      if (peek && peek.notes === 2 && peek.kind) peeked += 1;
      else misses.push({ ...p, h, peek });
      await page.keyboard.press('Escape');
      await page.waitForTimeout(60);
    }
    const closed = await page.evaluate(() => !document.getElementById('graph-link-peek'));
    console.log(JSON.stringify({ sampled: picks.length, kinds: [...new Set(picks.map((p) => p.kind))], hovered, cursorPointer: cursor, peeked, escapeCloses: closed, misses: misses.slice(0, 3) }));
    if (picks.length) {
      await page.mouse.click(picks[0].sx, picks[0].sy);
      await page.waitForTimeout(200);
      await page.screenshot({ path: `${OUT}/graphlinkpeek-${process.env.THEME || 'light'}.png`, clip: await page.evaluate(() => { const b = document.getElementById('graph-link-peek').getBoundingClientRect(); return { x: b.x - 20, y: b.y - 20, width: b.width + 40, height: b.height + 40 }; }) });
    }
  } finally {
    await browser.close();
  }
})().catch((e) => { console.log('ERR ' + e.stack); process.exit(1); });
