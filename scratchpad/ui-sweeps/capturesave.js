// Item 21 (dog1-1025): 30 lines in the capture box must scroll inside it and
// keep #save-btn inside the viewport, at 1280x800 and 700x800.
const { boot } = require('./lib.js');
(async () => {
  let bad = 0;
  for (const [w, h] of [[1280, 800], [700, 800]]) {
    const { page, browser } = await boot({ viewport: { width: w, height: h } });
    await page.waitForTimeout(2500);
    await page.evaluate(() => { switchTab('notes'); showNotesSection('browse'); });
    await page.waitForTimeout(500);
    await page.click('#notes-new-note');
    await page.waitForTimeout(800);
    await page.click('#capture .cm-content');
    await page.keyboard.type(Array.from({ length: 30 }, (_, i) => 'line ' + (i + 1)).join('\n'));
    await page.waitForTimeout(500);
    const m = await page.evaluate(() => {
      const s = document.getElementById('save-btn').getBoundingClientRect();
      const e = document.querySelector('#capture .cm-editor').getBoundingClientRect();
      return { saveBottom: Math.round(s.bottom), editorH: Math.round(e.height), vh: innerHeight };
    });
    console.log(w + 'x' + h, JSON.stringify(m));
    if (m.saveBottom > m.vh) bad++;
    await browser.close();
  }
  process.exit(bad ? 1 : 0);
})();
