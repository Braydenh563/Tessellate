// Panels whose .dialog-head scrolls with the body: the head's nearest scrolling ancestor (by computed overflow) is
// inside the panel, and the head is not sticky. Reads computed styles of hidden panels too.
const L = require('./lib.js');
(async () => {
  const { browser, page } = await L.boot();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.evaluate(async () => { for (const t of ['documents', 'whiteboard', 'graph', 'library']) { try { switchTab(t); } catch {} await new Promise((r) => setTimeout(r, 1500)); } });
  console.log(JSON.stringify(await page.evaluate(() => {
    const out = [];
    for (const head of document.querySelectorAll('.dialog-head, .doc-prose-head')) {
      const cs = getComputedStyle(head); if (cs.position === 'sticky' || cs.position === 'fixed') continue;
      let el = head.parentElement, hit = null;
      for (let i = 0; el && i < 3; i++, el = el.parentElement) { if (/auto|scroll/.test(getComputedStyle(el).overflowY)) { hit = el; break; } }
      if (hit) out.push(`${hit.tagName.toLowerCase()}#${hit.id}.${[...hit.classList].slice(0, 2).join('.')} > head ${head.className.split(' ').slice(0, 3).join('.')}`);
    }
    return out;
  }), null, 1));
  await browser.close();
})();
