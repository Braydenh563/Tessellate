// L-chat-58: the Ask tab as a smart browser. Slice 1 numbers: the thread chips, the filter, the "N of M" heading.
//   BASE=http://127.0.0.1:8795 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/askbrowser58.js  (W=390, THEME=dark)
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: Number(process.env.W || 1440), height: 900 } });
  await page.evaluate(() => { switchTab('notes'); showNotesSection('ask'); });
  await page.waitForTimeout(800);
  await page.evaluate((q) => askQuestion(q), process.env.Q || 'What have I saved about courses & study?').catch(() => {});
  await page.waitForTimeout(6000);
  const snap = () => page.evaluate(() => {
    const r = (el) => { if (!el) return null; const b = el.getBoundingClientRect(); return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) }; };
    const row = document.getElementById('ask-threads');
    const cards = [...document.querySelectorAll('#raw-results > li[data-id]')];
    return {
      row: r(row), rowOverflowX: row ? row.scrollWidth - row.clientWidth : null,
      chips: [...row.querySelectorAll('.chip')].map((c) => ({ t: c.textContent, pressed: c.getAttribute('aria-pressed'), ...r(c) })),
      cards: cards.length, visible: cards.filter((li) => li.getBoundingClientRect().height > 0).length,
      shown: document.getElementById('ask-records-shown')?.textContent, shownVisible: !document.getElementById('ask-records-shown')?.classList.contains('hidden'),
      fold: document.getElementById('ask-records-count')?.textContent,
      docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });
  console.log('before', JSON.stringify(await snap()));
  await page.locator('#ask-threads .chip').first().click();
  console.log('press1', JSON.stringify(await snap()));
  await page.locator('#ask-threads .chip').first().click();
  console.log('press2', JSON.stringify(await snap()));
  await browser.close();
})();
