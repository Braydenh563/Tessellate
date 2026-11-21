// L-world-class-177: every Settings section on a phone (W, H env; 360x740 and 320x568 measured 0 bad).
const { boot } = require('./lib.js');
(async () => {
  const W = +(process.env.W || 360), H = +(process.env.H || 740);
  const { browser, page } = await boot({ viewport: { width: W, height: H }, isMobile: true, hasTouch: true });
  await page.evaluate(() => openSettingsModal());
  await page.waitForTimeout(1500);
  const values = await page.evaluate(() => [...document.getElementById('settings-jump').options].map((o) => o.value));
  const out = [];
  for (const v of values) {
    await page.evaluate(() => document.querySelectorAll('.toast').forEach((t) => t.remove()));
    await page.selectOption('#settings-jump', v);
    await page.waitForTimeout(350);
    out.push(await page.evaluate(({ v, W, H }) => {
      const cur = document.querySelector("#settings-nav button.active")?.dataset.section;
      const panes = [...document.querySelectorAll('#settings-modal [data-section-pane], #settings-modal .settings-section, #settings-modal section')].filter((e) => e.checkVisibility() && e.getBoundingClientRect().height > 40);
      const pane = panes[0];
      if (!pane) return { v, cur, pane: false };
      const ctrls = [...pane.querySelectorAll('button, input, select, textarea, a[href], [tabindex="0"]')].filter((e) => e.checkVisibility());
      const wide = ctrls.filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > W + 1 || r.left < -1); }).map((e) => (e.id || e.className || e.tagName).toString().slice(0, 40) + ':' + Math.round(e.getBoundingClientRect().right));
      const last = ctrls[ctrls.length - 1];
      let lastOk = null;
      if (last) { last.scrollIntoView({ block: 'center' }); const r = last.getBoundingClientRect(); const hit = document.elementFromPoint(Math.min(W - 2, r.left + Math.min(r.width / 2, 20)), r.top + r.height / 2); lastOk = { inView: r.top >= 0 && r.bottom <= H, hit: !!hit && (hit === last || last.contains(hit) || hit.contains(last) || (hit.closest('label') && hit.closest('label').contains(last))), id: (last.id || last.textContent.trim().slice(0, 30) || last.tagName), by: hit && (hit.id || hit.className.toString().slice(0, 40)) }; }
      return { v, cur, n: ctrls.length, wide: wide.slice(0, 4), lastOk, sw: document.documentElement.scrollWidth };
    }, { v, W, H }));
  }
  const bad = out.filter((r) => r.pane === false || r.cur !== r.v || r.wide.length || !r.lastOk || !r.lastOk.inView || !r.lastOk.hit || r.sw > W);
  const ctrls = out.reduce((a, r) => a + (r.n || 0), 0);
  console.log(JSON.stringify({ W, n: out.length, ctrls, bad }));
  await browser.close();
})();
