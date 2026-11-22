// The owner: "atlas or the companion wont let me rest it on the start
// something buttons on the dashboard". Drags the companion (a real mouse
// drag) and lets go just above each Start something tile, a toolbar button
// and a chip where there are some, and reports where it lands: on the
// tile's top edge (its feet within 4px of it, over the tile) or not, why not
// (the edge list, the fit), and whether the tile still takes a click at its
// middle and top. Env: KIND, VW, VH, TAB (dashboard).
// Exits 1 when it does not land on a tile, or a tile it sits on cannot be
// clicked.
const { boot } = require('./lib.js');
const VW = Number(process.env.VW || 1440);
const VH = Number(process.env.VH || 900);

(async () => {
  const { browser, page } = await boot({ viewport: { width: VW, height: VH } });
  await page.evaluate((k) => { const b = $('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, process.env.KIND || 'atlas');
  await page.evaluate((t) => revealTab(t), process.env.TAB || 'dashboard');
  await page.waitForTimeout(6000);
  const targets = await page.evaluate(() => {
    const pick = (sel, n) => [...document.querySelectorAll(sel)].filter((el) => { const r = el.getBoundingClientRect(); return r.width > 20 && r.top > 60 && r.bottom < innerHeight - 40; }).slice(0, n)
      .map((el) => { const r = el.getBoundingClientRect(); return { sel, text: (el.textContent || '').trim().slice(0, 20), left: r.left, top: r.top, width: r.width, height: r.height }; });
    return [...pick('.launch-row-start button, .launch-row-start a', 3), ...pick('.chip, .dash-toolbar button', 2)];
  });
  const rows = [];
  for (const t of targets) {
    const face = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
    const aimX = t.left + t.width / 2;
    const aimY = t.top - 40;
    await page.mouse.move(face[0], face[1]);
    await page.mouse.down();
    await page.mouse.move(face[0] + 10, face[1] + 10, { steps: 3 });
    await page.mouse.move(aimX, aimY, { steps: 20 });
    await page.waitForTimeout(250);
    await page.mouse.up();
    await page.waitForTimeout(1600);
    const res = await page.evaluate((t) => {
      const feet = nmb.y + (nmb.pose === 'sit' ? NMB_SEAT : NMB_FEET - 1);
      const cx = nmb.x + NMB_W / 2;
      const on = Math.abs(feet - t.top) <= 4 && cx > t.left && cx < t.left + t.width;
      const hit = (x, y) => { const el = document.elementFromPoint(x, y); return !!el && !el.closest('#nm-buddy'); };
      return { on, pose: nmb.pose, perch: nmb.perch, feetOff: Math.round(feet - t.top), cxOff: Math.round(cx - (t.left + t.width / 2)), clickMiddle: hit(t.left + t.width / 2, t.top + t.height / 2), clickTop: hit(t.left + t.width / 2, t.top + 3) };
    }, t);
    rows.push({ target: `${t.sel} "${t.text}" ${Math.round(t.width)}x${Math.round(t.height)}`, ...res });
  }
  console.log(JSON.stringify(rows));
  await browser.close();
  // Every control it was dropped on still takes its click; the tiles are
  // stood on.
  process.exit(rows.some((r) => !r.clickMiddle || !r.clickTop) || rows.filter((r) => r.target.includes('launch')).some((r) => !r.on) ? 1 : 0);
})();
