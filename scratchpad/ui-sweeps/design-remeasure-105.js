// L-world-class-105: re-measure 22.3 (cards, Settings heads, icon weight, toast corner) at laptop widths.
const { boot } = require('./lib.js');
const W = (process.env.SIZES || '1093x614,1280x800,1440x900').split(',');
(async () => {
  const out = {};
  for (const s of W) {
    const [w, h] = s.split('x').map(Number);
    const { browser, page } = await boot({ viewport: { width: w, height: h } });
    const icons = () => page.evaluate(() => {
      const c = {};
      for (const i of document.querySelectorAll('i.ph, i[class*="ph-"]')) {
        const r = i.getBoundingClientRect();
        if (!r.width) continue;
        const cs = getComputedStyle(i);
        const k = `${cs.fontFamily.split(',')[0]}|${cs.fontWeight}|${cs.fontSynthesisWeight || cs.fontSynthesis}`;
        (c[k] ||= []).push((i.closest('[id]') || i).id || i.className);
      }
      return Object.fromEntries(Object.entries(c).map(([k, v]) => [k, v.length + ' ' + [...new Set(v)].slice(0, 6).join(' ')]));
    });
    const r = { shell: await icons() };
    await page.evaluate(() => document.querySelector('#tab-btn-notes, [data-tab="notes"]')?.click());
    await page.waitForTimeout(1500);
    r.cards = await page.evaluate(() => {
      const c = [...document.querySelectorAll('.entry-content')].find((e) => e.getBoundingClientRect().width > 100);
      if (!c) return null;
      let el = c.parentElement; while (el && parseFloat(getComputedStyle(el).paddingLeft) === 0) el = el.parentElement;
      const cs = getComputedStyle(el); const body = c;
      return { cls: el.className, w: Math.round(el.getBoundingClientRect().width), pad: cs.padding, body: getComputedStyle(body).fontSize, bodyCls: body.className, lh: getComputedStyle(body).lineHeight };
    });
    r.notesIcons = await icons();
    await page.evaluate(() => openSettingsModal());
    await page.waitForTimeout(1200);
    r.settings = await page.evaluate(() => {
      const pick = (sel) => [...document.querySelectorAll(sel)].filter((e) => e.getBoundingClientRect().width).slice(0, 3).map((e) => { const cs = getComputedStyle(e); return `${e.tagName}.${e.className} "${e.textContent.trim().slice(0, 24)}" ${cs.fontSize}/${cs.fontWeight}`; });
      return { h2: pick('#settings-modal h2'), h3: pick('#settings-modal h3'), h4: pick('#settings-modal h4'), summary: pick('#settings-modal summary'), legend: pick('#settings-modal legend'), label: pick('#settings-modal label, #settings-modal .stacked-label, #settings-modal .setting-label') };
    });
    r.settingsIcons = await icons();
    await page.keyboard.press('Escape');
    await page.evaluate(() => document.querySelector('#tab-btn-dashboard, [data-tab="dashboard"]')?.click());
    await page.waitForTimeout(1200);
    await page.evaluate(() => toast('Reminder: water the plants is due now'));
    await page.waitForTimeout(600);
    r.toast = await page.evaluate(() => {
      const t = [...document.querySelectorAll('.toast')].find((e) => e.getBoundingClientRect().width);
      const sb = document.querySelector('#status-bar, .status-bar');
      const head = [...document.querySelectorAll('.dash-head, .dash-hero')].find((e) => e.getBoundingClientRect().width);
      const R = (e) => e && (({ left, top, right, bottom }) => ({ l: Math.round(left), t: Math.round(top), r: Math.round(right), b: Math.round(bottom) }))(e.getBoundingClientRect());
      return { toast: R(t), statusBar: R(sb), head: R(head), headCls: head && head.className };
    });
    out[s] = r;
    await browser.close();
  }
  console.log(JSON.stringify(out, null, 1));
})();
