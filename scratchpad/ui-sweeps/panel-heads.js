// Panel heads stay put while the body scrolls; the Dictionary closes on an outside press and Escape,
// and a moved or docked panel drops the dim and the blur. BASE=http://127.0.0.1:8790 node panel-heads.js
const L = require('./lib.js');
(async () => {
  const { browser, page } = await L.boot();
  await page.setViewportSize({ width: 1440, height: 900 });
  const words = Array.from({ length: 160 }, (_, i) => `teh recieve definately wierd occured ${i}.`).join(' ');
  await page.evaluate(async (content) => {
    const r = await api('/documents', { method: 'POST', body: JSON.stringify({ title: 'Heads fixture', content }) });
    const d = await r.json(); switchTab('documents'); await openDocument(d.id);
  }, words);
  await page.waitForTimeout(2500);
  await page.click('#doc-prose').catch(() => {});
  await page.waitForTimeout(3000);
  const scrollTop = (sel, headSel) => page.evaluate(async ([s, h]) => {
    const box = document.querySelector(s); const head = box && box.querySelector(h);
    if (!box || !head) return { missing: !box ? s : h };
    let sc = head.parentElement; while (sc && !(sc.scrollHeight > sc.clientHeight + 1 && /auto|scroll/.test(getComputedStyle(sc).overflowY))) sc = sc.parentElement;
    const before = Math.round(head.getBoundingClientRect().top);
    if (sc) sc.scrollTop += 400;
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const after = Math.round(head.getBoundingClientRect().top);
    const bg = getComputedStyle(head).backgroundColor + ' stuck ' + getComputedStyle(head, '::before').backgroundColor;
    return { before, after, moved: sc ? sc.scrollTop : 'no scroller', bg };
  }, [sel, headSel]);
  console.log('suggestions head', JSON.stringify(await scrollTop('#doc-prose-panel', '.doc-prose-head')));
  // Dictionary: many words, so the dialog scrolls.
  await page.evaluate(async () => { for (let i = 0; i < 80; i++) docDictionary().add(`zzword${i}`); await openDocDictionary(); });
  await page.waitForTimeout(800);
  for (const h of ['.doc-dictionary-head', '.doc-dictionary-lead', '.doc-dictionary-field']) {
    console.log('dictionary', h, JSON.stringify(await page.evaluate((h) => {
      const d = document.getElementById('doc-dictionary-dialog'); const b = d.querySelector('.doc-dictionary-body'); const el = d.querySelector(h);
      const before = Math.round(el.getBoundingClientRect().top); b.scrollTop += 400; const after = Math.round(el.getBoundingClientRect().top);
      const out = { before, after, bodyScrolled: b.scrollTop, dialogScrolled: d.scrollTop }; b.scrollTop = 0; return out;
    }, h)));
  }
  console.log('before outside', JSON.stringify(await page.evaluate(() => { const d = document.getElementById('doc-dictionary-dialog'); const r = d.getBoundingClientRect(); return { modal: d.matches(':modal'), left: Math.round(r.left), hit: document.elementFromPoint(40, 450)?.id }; })));
  const open = () => page.evaluate(() => document.getElementById('doc-dictionary-dialog').open);
  await page.mouse.click(40, 450); await page.waitForTimeout(500);
  console.log('outside press closes', !(await open()));
  if (await open()) await page.evaluate(() => document.getElementById('doc-dictionary-dialog').close());
  await page.evaluate(() => openDocDictionary()); await page.waitForTimeout(500);
  await page.keyboard.press('Escape'); await page.waitForTimeout(500);
  console.log('escape closes', !(await open()));
  // Drag the head 200px right, then read the backdrop and whether the app behind takes a press.
  await page.evaluate(() => openDocDictionary()); await page.waitForTimeout(800);
  const hb = await page.locator('#doc-dictionary-dialog .doc-dictionary-head h2').boundingBox();
  await page.mouse.move(hb.x + 20, hb.y + 8); await page.mouse.down(); await page.mouse.move(hb.x + 120, hb.y + 40, { steps: 6 }); await page.mouse.move(hb.x + 220, hb.y + 60, { steps: 6 }); await page.mouse.up();
  await page.waitForTimeout(600);
  console.log('after drag', JSON.stringify(await page.evaluate(() => {
    const d = document.getElementById('doc-dictionary-dialog'); const b = getComputedStyle(d, '::backdrop');
    const app = document.querySelector('#app, main, .tab-page:not(.hidden)');
    return { glass: document.documentElement.dataset.glass, open: d.open, modal: d.matches(':modal'), moved: d.hasAttribute('data-panel-moved'), backdropBg: b.backgroundColor, backdropFilter: b.backdropFilter, appInert: app ? app.closest('[inert]') !== null || d.matches(':modal') : null };
  })));
  // Dock: drag the head to the left edge.
  const hb2 = await page.locator('#doc-dictionary-dialog .doc-dictionary-head h2').boundingBox();
  await page.mouse.move(hb2.x + 20, hb2.y + 8); await page.mouse.down(); await page.mouse.move(200, 300, { steps: 6 }); await page.mouse.move(1, 400, { steps: 8 }); await page.mouse.up();
  await page.waitForTimeout(800);
  console.log('after dock', JSON.stringify(await page.evaluate(() => {
    const d = document.getElementById('doc-dictionary-dialog'); const b = getComputedStyle(d, '::backdrop');
    const r = d.getBoundingClientRect();
    return { glass: document.documentElement.dataset.glass, left: Math.round(r.left), w: Math.round(r.width), modal: d.matches(':modal'), backdropBg: b.backgroundColor, backdropFilter: b.backdropFilter, hit: document.elementFromPoint(1000, 450)?.tagName };
  })));
  await page.focus('#doc-dictionary-search'); await page.keyboard.press('Escape'); await page.waitForTimeout(400);
  console.log('escape closes docked', !(await open()));
  // Back in the middle: modal again, with the dim.
  await page.evaluate(() => openDocDictionary()); await page.waitForTimeout(600);
  await page.evaluate(() => document.querySelector('#doc-dictionary-dialog .panel-reset')?.click()); await page.waitForTimeout(600);
  console.log('after reset', JSON.stringify(await page.evaluate(() => { const d = document.getElementById('doc-dictionary-dialog'); const b = getComputedStyle(d, '::backdrop'); return { open: d.open, modal: d.matches(':modal'), backdropBg: b.backgroundColor, backdropFilter: b.backdropFilter }; })));
  await browser.close();
})();
