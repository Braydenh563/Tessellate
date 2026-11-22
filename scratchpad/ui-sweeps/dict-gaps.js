const L = require('./lib.js');
(async () => {
  const { browser, page } = await L.boot();
  await page.setViewportSize({ width: Number(process.env.W || 1440), height: 900 });
  await page.evaluate(async () => { switchTab('documents'); await new Promise((r) => setTimeout(r, 1500)); for (let i = 0; i < 80; i++) docDictionary().add(`zzword${i}`); await openDocDictionary(); });
  await page.waitForTimeout(1000);
  console.log(JSON.stringify(await page.evaluate(() => {
    const d = document.getElementById('doc-dictionary-dialog'); const t = d.getBoundingClientRect().top;
    const o = { dialogH: Math.round(d.getBoundingClientRect().height), w: Math.round(d.getBoundingClientRect().width) };
    for (const s of ['.doc-dictionary-head', '.doc-dictionary-lead', '.doc-dictionary-field', '#doc-dictionary-list', '.doc-dictionary-section', '.doc-dictionary-setting']) { const r = d.querySelector(s).getBoundingClientRect(); o[s] = [Math.round(r.top - t), Math.round(r.left), Math.round(r.width)]; }
    return o;
  })));
  await browser.close();
})();
