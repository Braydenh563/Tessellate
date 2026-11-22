// Open every opener we can call bare; for each visible popup head, last control right edge vs head content right and card content right.
const { boot } = require('/home/user/tessellate/scratchpad/ui-sweeps/lib.js');
const OPENERS = (process.env.OPENERS || '').split(',').filter(Boolean);
(async () => {
  const { browser, page } = await boot({ viewport: { width: +(process.env.W || 1440), height: 900 } });
  const names = OPENERS.length ? OPENERS : await page.evaluate(() => Object.keys(window).filter((k) => /^open[A-Z]/.test(k) && typeof window[k] === 'function' && window[k].length === 0));
  const bad = [], ok = [];
  for (const n of names) {
    await page.keyboard.press('Escape').catch(() => {});
    await page.evaluate(() => { for (const b of document.querySelectorAll('.sheet-close, .dialog-close, [data-close]')) { if (b.getBoundingClientRect().width) b.click(); } }).catch(() => {});
    await page.waitForTimeout(150);
    const r = await page.evaluate(async (n) => { try { await Promise.race([window[n](), new Promise((r) => setTimeout(r, 1500))]); } catch (e) { return 'err ' + e.message.slice(0, 60); } return 'ok'; }, n);
    await page.waitForTimeout(500);
    const m = await page.evaluate(() => {
      const out = [];
      for (const head of document.querySelectorAll('.dialog-head, .sheet-head, .panel-head, .modal-head')) {
        const hr = head.getBoundingClientRect(); if (!hr.width || hr.bottom < 0) continue;
        const card = head.closest('.card, .modal-card, .sheet-card, dialog, [role=dialog]') || head.parentElement;
        const cr = card.getBoundingClientRect(), cs = getComputedStyle(card), hs = getComputedStyle(head);
        const vis = [...head.children].filter((c) => c.getBoundingClientRect().width && getComputedStyle(c).visibility !== 'hidden');
        if (vis.length < 2) continue;
        const last = vis[vis.length - 1].getBoundingClientRect();
        const headIn = hr.right - parseFloat(hs.paddingRight);
        const cardIn = cr.right - parseFloat(cs.paddingRight) - parseFloat(cs.borderRightWidth);
        out.push({ card: (card.className || card.tagName).toString().slice(0, 60), name: card.dataset.sheet || card.id || '', gapHead: Math.round(headIn - last.right), gapCard: Math.round(cardIn - last.right) });
      }
      return out;
    });
    for (const x of m) (Math.abs(x.gapHead) > 2 || x.gapCard > 24 ? bad : ok).push(n + ' ' + JSON.stringify(x));
    if (!m.length) ok.push(n + ' (no head) ' + r);
  }
  console.log('BAD\n' + [...new Set(bad)].join('\n') + '\nOK ' + ok.length + '\n' + [...new Set(ok)].join('\n'));
  await browser.close();
})();
