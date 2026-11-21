// The owner (2026-10-11): "sometimes when I click on it, its arms which
// were hanging at its side with a bit of an inner bend, just start rising
// (or the one on its right does so its left arm) and it stays bent
// downwards, then falls again." Clicks Atlas (KIND, default atlas) awake
// N times and samples each arm every 60 ms for 2.4 s: the shoulder's turn,
// the elbow's bend, and where the hand is against the shoulder in the
// figure's own units (y grows down; the shoulders are at y 41). An arm
// raised out past 60 degrees whose elbow bends inward (the forearm
// turning down from it) is the report; before the fix a wave's bend was
// +40 and its hand at best y 47 (below the shoulder). LOOK=feminine for her.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(([k, look]) => { if (look) localStorage.setItem('atlas-look', look); const b = $('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, [process.env.KIND || 'atlas', process.env.LOOK || '']);
  await page.waitForTimeout(4000);
  const rows = [];
  const bad = [];
  const peak = [];
  for (let n = 0; n < Number(process.env.N || 6); n += 1) {
    // Standing on the bottom bar, awake, as in the report.
    await page.evaluate(() => { const bar = document.getElementById('status-bar').getBoundingClientRect(); const b = document.getElementById('nm-buddy'); b.classList.remove('nmb-sleep', 'nmb-drowsy'); nameMarkBuddyMoveTo(b, { kind: 'yours', pose: 'stand', legs: '', x: 700, y: Math.round(bar.top - NMB_FEET + 1) }, true); nmb.placedAt = Date.now(); nameMarkBuddyAct(''); });
    await page.waitForTimeout(1500);
    const f = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
    await page.mouse.click(f[0], f[1]);
    const trace = await page.evaluate(async () => {
      const out = [];
      const buddy = document.getElementById('nm-buddy');
      for (let i = 0; i < 40; i += 1) {
        await new Promise((r) => setTimeout(r, 60));
        const box = buddy.querySelector('.atl-figure-box');
        const rig = box && box.atlasRig;
        const row = { t: i * 60, act: nmb.act, cls: [...buddy.classList].filter((c) => c.startsWith('nmb-act-')).join(' ') };
        for (const side of ['l', 'r']) {
          const arm = rig && rig.arms.find((a) => a.side === side);
          const hand = buddy.querySelector(`.nmb-arm-${side}.atl-rigged > .atl-hand`);
          const svg = hand && hand.ownerSVGElement;
          let hy = null; let hx = null;
          if (hand && svg) { const m = svg.getScreenCTM(); const b = hand.getBoundingClientRect(); const p = new DOMPoint(b.left + b.width / 2, b.top + b.height / 2).matrixTransform(m.inverse()); hx = +p.x.toFixed(1); hy = +p.y.toFixed(1); }
          row[side] = arm ? { sh: Math.round(arm.j.sh.x), el: Math.round(arm.j.el.x), wr: Math.round(arm.j.wr.x), hx, hy } : { hx, hy };
        }
        out.push(row);
      }
      return out;
    });
    rows.push(trace);
    // Raised out past 60 degrees, the forearm must not turn back down
    // from the upper arm (a positive bend, inward, is towards the floor
    // once the arm is level): that is "stays bent downwards".
    for (const r of trace) for (const side of ['l', 'r']) {
      const a = r[side];
      const out = a && typeof a.sh === 'number' ? (side === 'r' ? -a.sh : a.sh) : 0;
      if (out > 60 && a.el > 2) bad.push({ n, t: r.t, side, ...a, act: r.act });
    }
    peak.push(Math.min(...trace.map((r) => Math.min(r.r.hy ?? 99, r.l.hy ?? 99))));
  }
  const acts = rows.map((tr) => [...new Set(tr.map((r) => r.act))].join('/'));
  console.log(JSON.stringify({ acts }));
  if (process.env.TRACE) for (const tr of rows) console.log(JSON.stringify(tr.filter((r, i) => i % 3 === 0).map((r) => [r.t, r.act, r.l, r.r])));
  console.log(JSON.stringify({ highestHandY: peak, bad: bad.length, first: bad.slice(0, 4) }));
  console.log(bad.length ? 'FAIL' : 'PASS');
  process.exitCode = bad.length ? 1 : 0;
  await browser.close();
})();
