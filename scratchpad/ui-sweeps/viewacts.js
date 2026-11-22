// Brief 88, the owner: "improve the actions and stuff for the expanded
// companion panel". Opens the companion's large view (double-click), reads
// its row of acts (`.nm-viewer-acts`), presses each chip in turn and reads
// that the companion took the act, and that the row sits inside the card
// with no chip clipped. KIND (atlas, me), PHONE=1 for 390 wide. PASS when
// every chip plays its act and the row fits.
const { boot } = require('./lib.js');
(async () => {
  const phone = !!process.env.PHONE;
  const { browser, page } = await boot({ viewport: phone ? { width: 390, height: 844 } : { width: 1440, height: 900 } });
  await page.evaluate((k) => { const b = $('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, process.env.KIND || 'atlas');
  await page.waitForTimeout(4000);
  await page.evaluate(() => { const b = document.getElementById('nm-buddy'); DOMTokenList.prototype.remove.call(b.classList, 'nmb-sleep', 'nmb-drowsy'); openNameMarkViewer(b.dataset.seed || '', { visit: true }); });
  await page.waitForTimeout(1500);
  const chips = await page.evaluate(() => [...document.querySelectorAll('.nm-viewer-acts .chip')].map((c) => c.textContent.trim()));
  let bad = chips.length >= 4 ? 0 : 1;
  console.log(`chips (${chips.length}): ${chips.join(', ')}`);
  const fit = await page.evaluate(() => { const card = document.querySelector('.nm-viewer-card').getBoundingClientRect(); const row = document.querySelector('.nm-viewer-acts'); const r = row.getBoundingClientRect(); const out = [...row.children].filter((c) => { const b = c.getBoundingClientRect(); return b.left < card.left || b.right > card.right || c.scrollWidth > c.clientWidth + 1; }).length; return { out, rowW: Math.round(r.width), cardW: Math.round(card.width), rows: new Set([...row.children].map((c) => Math.round(c.getBoundingClientRect().top))).size, pageX: document.documentElement.scrollWidth > innerWidth }; });
  if (fit.out || fit.pageX) bad += 1;
  console.log(`${fit.out || fit.pageX ? 'BAD ' : 'ok  '} row ${fit.rowW}px in card ${fit.cardW}px, ${fit.rows} line(s), ${fit.out} clipped, page scrolls sideways ${fit.pageX}`);
  for (let i = 0; i < chips.length; i += 1) {
    const r = await page.evaluate(async (i) => {
      const chip = document.querySelectorAll('.nm-viewer-acts .chip')[i];
      chip.click();
      await new Promise((r) => setTimeout(r, 150));
      return { act: nmb.act, cls: [...document.getElementById('nm-buddy').classList].filter((c) => c.startsWith('nmb-act-')).join(' ') };
    }, i);
    const ok = !!r.act;
    if (!ok) bad += 1;
    console.log(`${ok ? 'ok  ' : 'BAD '} ${chips[i]} -> ${r.act || '(none)'} ${r.cls}`);
    await page.waitForTimeout(900);
  }
  console.log(bad ? 'FAIL' : 'PASS');
  await browser.close();
})();
