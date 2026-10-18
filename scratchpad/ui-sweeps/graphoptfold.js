// The options panel against its own cap, plus the room the cap reserves.
//
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers NODE_PATH=/opt/node22/lib/node_modules \
//     BASE=http://127.0.0.1:8931 node scratchpad/ui-sweeps/graphoptfold.js
//
// The list's height was measured by a removed sweep; this says whether
// it fits, and what the panel is capped against. The cap subtracts a fixed
// band at the bottom for the zoom strip, so a panel that scrolls is either
// too tall or capped against a band bigger than the strip it protects, and
// the two are not the same fix.
const { boot } = require('./lib.js');
(async () => {
  const W = Number(process.env.W || 1440);
  const H = Number(process.env.H || 900);
  const { browser, page } = await boot({ viewport: { width: W, height: H } });
  await page.click('[data-tab="graph"]');
  await page.waitForTimeout(700);
  await page.click('#graph-options-toggle');
  await page.waitForTimeout(500);
  // Below 820 the graph dock folds its tail into a "More" menu and the gear
  // goes with it, so one press opens the menu rather than the panel.
  let presses = 1;
  while (presses < 3 && (await page.evaluate(() => document.getElementById('graph-options').classList.contains('hidden')))) {
    await page.click('#graph-options-toggle');
    await page.waitForTimeout(500);
    presses += 1;
  }
  console.log('presses to open the panel:', presses);
  const r = await page.evaluate(() => {
    const q = (s) => {
      const e = document.querySelector(s);
      if (!e) return null;
      const b = e.getBoundingClientRect();
      return { top: Math.round(b.top), bottom: Math.round(b.bottom), h: Math.round(b.height), w: Math.round(b.width) };
    };
    const panel = document.getElementById('graph-options');
    const toggle = document.getElementById('graph-options-toggle');
    const toggleState = { hidden: panel.classList.contains('hidden'), expanded: toggle.getAttribute('aria-expanded'), togglebox: Math.round(toggle.getBoundingClientRect().width) };
    const folds = [...panel.querySelectorAll('details.graph-options-fold')].map((d) => ({
      name: (d.querySelector('summary')?.textContent || '').trim(),
      open: d.open,
      h: Math.round(d.getBoundingClientRect().height),
      summaryH: Math.round(d.querySelector('summary').getBoundingClientRect().height),
    }));
    return {
      toggleState,
      panel: q('#graph-options'),
      scrollH: panel.scrollHeight,
      clientH: panel.clientHeight,
      scrolls: panel.scrollHeight > panel.clientHeight,
      overlay: q('.graph-overlay'),
      zoom: q('.graph-zoom'),
      legend: q('.graph-legend-row'),
      folds,
    };
  });
  console.log('closed:', JSON.stringify(r, null, 1));

  // Open all three and read the panel again: a fold that will not open is the
  // failure this shape can have that a closed measurement cannot see, and the
  // open panel has to stay inside its cap rather than run off the card.
  const opened = await page.evaluate(() => {
    const out = [];
    for (const d of document.querySelectorAll('#graph-options details.graph-options-fold')) {
      d.querySelector('summary').click();
      out.push({ name: (d.querySelector('summary').textContent || '').trim().split('\n')[0], open: d.open, h: Math.round(d.getBoundingClientRect().height) });
    }
    const panel = document.getElementById('graph-options');
    const vis = (id) => {
      const e = document.getElementById(id);
      if (!e) return 'missing';
      const b = e.getBoundingClientRect();
      return b.width > 0 && b.height > 0 ? 'shown' : 'hidden';
    };
    return {
      folds: out,
      scrollH: panel.scrollHeight,
      clientH: panel.clientHeight,
      bottom: Math.round(panel.getBoundingClientRect().bottom),
      gravity: vis('graph-gravity'),
      groupQuery: vis('graph-group-query'),
      minimapCorner: vis('graph-minimap-corner'),
    };
  });
  console.log('opened:', JSON.stringify(opened, null, 1));

  // "Unpin all" rides the Physics fold's summary, so the press that releases
  // the pins must not also open or close the fold under it.
  await page.click('#graph-unpin-all');
  await page.waitForTimeout(600);
  const afterUnpinOpen = await page.evaluate(() => document.getElementById('graph-physics').open);
  await page.click('#graph-physics > summary');
  await page.waitForTimeout(200);
  await page.click('#graph-unpin-all');
  await page.waitForTimeout(600);
  const afterUnpinClosed = await page.evaluate(() => document.getElementById('graph-physics').open);
  console.log('unpin keeps the fold as it was (open, then closed):', afterUnpinOpen, afterUnpinClosed);
  await page.evaluate(() => { const d = document.getElementById('graph-physics'); if (!d.open) d.querySelector('summary').click(); });

  // And the memory: a reload must bring back what was opened.
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  await page.click('[data-tab="graph"]');
  await page.waitForTimeout(700);
  const remembered = await page.evaluate(() => {
    const panel = document.getElementById('graph-options');
    if (panel.classList.contains('hidden')) document.getElementById('graph-options-toggle').click();
    return [...document.querySelectorAll('#graph-options details.graph-options-fold')].map((d) => ({
      id: d.id, open: d.open,
    }));
  });
  console.log('after reload:', JSON.stringify(remembered));
  await browser.close();
})();
