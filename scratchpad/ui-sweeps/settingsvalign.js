// Settings rows with a text value on the right: label name centre vs value first-line centre.
process.env.SCRATCH = process.env.SCRATCH || __dirname;
const { boot } = require('/home/user/Tessellate/.claude/worktrees/agent-a655c033671eade8e/scratchpad/ui-sweeps/lib.js');
(async () => {
  const W = Number(process.env.W || 1440);
  const { browser, page } = await boot({ viewport: { width: W, height: 900 } });
  await page.evaluate(() => openSettingsModal('models'));
  await page.waitForTimeout(1000);
  const sections = await page.evaluate(() => [...document.querySelectorAll('#settings-nav button[data-section]')].map((b) => b.dataset.section));
  let max = 0, n = 0; const bad = [];
  for (const s of sections) {
    await page.evaluate((x) => { showSettingsSection(x); for (const d of document.querySelectorAll(`#settings-${x} details`)) d.open = true; }, s);
    await page.waitForTimeout(400);
    const r = await page.evaluate((x) => {
      const sec = document.getElementById(`settings-${x}`);
      const line = (el) => {
        const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, { acceptNode: (t) => t.textContent.trim() && !t.parentElement.closest('button,[data-help-for]') ? 1 : 3 });
        const t = w.nextNode(); if (!t) return null;
        const rg = document.createRange(); rg.selectNodeContents(t);
        const rc = [...rg.getClientRects()].filter((q) => q.height);
        return rc.length ? rc[0] : null;
      };
      const out = [];
      for (const row of sec.querySelectorAll('.setting-row')) {
        if (!row.checkVisibility()) continue;
        const lab = row.querySelector(':scope > .setting-label'); if (!lab) continue;
        const vals = [...row.children].filter((k) => k !== lab && k.checkVisibility() && getComputedStyle(k).position !== 'absolute');
        if (vals.length !== 1) continue;
        const v = vals[0];
        if (v.querySelector('input,select,textarea,button,a[href],summary,canvas,svg,img,[role=switch],.select-shell,.switch')) continue;
        if (!v.textContent.trim()) continue;
        const nm = lab.querySelector(':scope > span') || lab;
        const a = line(nm), b = line(v); if (!a || !b) continue;
        const vr = v.getBoundingClientRect(), lr = lab.getBoundingClientRect();
        if (vr.top >= lr.bottom - 1) continue; // wrapped under the label: not side by side
        out.push({ id: v.id || (lab.textContent.trim().slice(0, 30)), d: (b.top + b.height / 2) - (a.top + a.height / 2), cls: v.className });
      }
      return out;
    }, s);
    for (const o of r) { n++; const d = Math.abs(o.d); if (d > max) max = d; if (d > 1) bad.push(`${s}: ${o.id} ${o.d.toFixed(1)}px (${o.cls})`); }
  }
  console.log(`W=${W} THEME=${process.env.THEME || 'light'} text-value rows ${n}, max offset ${max.toFixed(2)}px, over 1px: ${bad.length}`);
  bad.forEach((b) => console.log('  ' + b));
  await browser.close();
})();
