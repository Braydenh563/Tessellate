// Which code an inline-style CSP refusal comes from: the page's
// `securitypolicyviolation` events (file, line, sample) over TAB (chat), with
// Atlas as the companion. Env: BASE, TAB.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
  await page.evaluate(() => {
    window.__csp = [];
    document.addEventListener('securitypolicyviolation', (e) => window.__csp.push([e.violatedDirective, e.sourceFile, e.lineNumber, e.columnNumber, e.sample]));
    const b = document.getElementById('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await page.evaluate((t) => revealTab(t), process.env.TAB || 'chat');
  await page.waitForTimeout(4000);
  await page.setViewportSize({ width: 900, height: 700 });
  await page.waitForTimeout(2000);
  const seen = await page.evaluate(() => window.__csp);
  const by = {};
  for (const v of seen) { const k = v.slice(0, 4).join(' '); by[k] = (by[k] || 0) + 1; }
  console.log(JSON.stringify(by));
  await browser.close();
})();
