// L-chat-58 slice 2: Around this note. Opens the first card's neighbourhood and measures it.
//   BASE=http://127.0.0.1:8795 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/askbrowser58b.js  (W=390, THEME=dark)
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: Number(process.env.W || 1440), height: 900 } });
  await page.evaluate(() => { switchTab('notes'); showNotesSection('ask'); });
  await page.waitForTimeout(800);
  await page.evaluate((q) => askQuestion(q), process.env.Q || 'What have I saved about courses & study?').catch(() => {});
  await page.waitForTimeout(6000);
  if (Number(process.env.W || 1440) < 600) await page.locator('#ask-records-fold').click();
  const btn = page.locator('#raw-results > li[data-id] .record-around').first();
  const before = await page.evaluate(() => ({ cards: document.querySelectorAll('#raw-results > li[data-id]').length, answer: document.getElementById('ai-answer').textContent.length }));
  const t0 = Date.now();
  await btn.click();
  await page.waitForSelector('.ask-around .connection-row, .ask-around .ask-around-note:not(:only-child)', { timeout: 8000 }).catch(() => {});
  const ms = Date.now() - t0;
  console.log(JSON.stringify(await page.evaluate(([b, ms]) => {
    const r = (el) => { const x = el.getBoundingClientRect(); return { x: Math.round(x.x), y: Math.round(x.y), w: Math.round(x.width), h: Math.round(x.height) }; };
    const li = document.querySelector('#raw-results > li[data-id] .ask-around')?.closest('li');
    const box = li?.querySelector('.ask-around');
    return {
      ms, before: b,
      after: { cards: document.querySelectorAll('#raw-results > li[data-id]').length, answer: document.getElementById('ai-answer').textContent.length },
      card: li && r(li), box: box && r(box), indent: box && Math.round(box.getBoundingClientRect().x - li.getBoundingClientRect().x),
      rows: [...(box?.querySelectorAll('.connection-row') || [])].map((x) => ({ t: x.textContent.slice(0, 40), ...r(x) })),
      note: box?.textContent.slice(0, 60), insideCard: !!box && box.getBoundingClientRect().right <= li.getBoundingClientRect().right + 1,
      docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  }, [before, ms])));
  await btn.click();
  console.log('closed', await page.evaluate(() => document.querySelectorAll('.ask-around').length));
  await browser.close();
})();
