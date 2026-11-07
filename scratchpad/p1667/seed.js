// Seed 48 titled notes (title line + body, so the dashboard list shows previews).
const { boot } = require('../ui-sweeps/lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const out = await page.evaluate(async () => {
    let made = 0;
    for (let i = 0; i < 48; i += 1) {
      const body = { content: `Seed ${i} heading\n\nThe preview line for note ${i} carries some words about gardens, plans and a few other things to read.`, category: ['Work', 'Ideas', 'Personal'][i % 3] };
      const r = await api('/entries', { method: 'POST', body: JSON.stringify(body) });
      if (r.ok) made += 1;
    }
    return made;
  });
  console.log('made', out);
  await browser.close();
})();
