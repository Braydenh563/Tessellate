// Long Settings panes (L-ui-modernisation-52): Tools it can use and Appearance stay one pane each (the
// owner, L771: "keep one pane, add the row Skills has"), because every head is one press from the
// sidebar and lands under the pane's title. Measures each pane's height, its heads, the tallest stretch
// between heads, and where each index press lands. Exits 1 when a section head has no index link, a
// press lands off (more than 24px past the sticky title, unless the pane is scrolled to its end), or a
// stretch is over two screens without a filter that brings a match into the first screen.
//   BASE=http://127.0.0.1:8781 node scratchpad/ui-sweeps/settingslong.js
const { boot } = require('./lib.js');
let failed = 0;
const check = (name, ok, detail) => {
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${name}${detail !== undefined ? ' ' + JSON.stringify(detail) : ''}`);
  if (!ok) failed += 1;
};
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  for (const name of ['tools', 'appearance']) {
    await page.evaluate((n) => openSettingsModal(n), name);
    await page.waitForTimeout(1800);
    const m = await page.evaluate((n) => {
      const pane = document.getElementById(`settings-${n}`);
      const heads = [...pane.querySelectorAll('h3')].filter((h) => h.getClientRects().length && !h.closest('.settings-pane-title'));
      const top = pane.getBoundingClientRect().top;
      const ys = heads.map((h) => h.getBoundingClientRect().top - top);
      const height = pane.scrollHeight;
      const gaps = ys.map((y, i) => (ys[i + 1] ?? height) - y);
      const at = gaps.indexOf(Math.max(...gaps));
      const filter = heads[at]?.closest('.settings-group')?.querySelector('input[type=search]')?.id || null;
      const links = [...document.querySelectorAll('#settings-nav .settings-nav-group')];
      return { height: Math.round(height), heads: heads.length, links: links.length, tallest: Math.round(Math.max(...gaps)), filter, screen: innerHeight };
    }, name);
    console.log(name, JSON.stringify(m));
    check(`${name}: every head has an index link`, m.links >= m.heads, m);
    if (m.tallest <= 2 * m.screen || !m.filter) check(`${name}: no stretch between heads over two screens`, m.tallest <= 2 * m.screen, m.tallest);
    else {
      const f = await page.evaluate(async (id) => {
        const input = document.getElementById(id);
        input.value = 'web'; input.dispatchEvent(new Event('input', { bubbles: true }));
        await new Promise((r) => setTimeout(r, 500));
        const shown = [...document.querySelectorAll('#tool-list > li')].filter((li) => li.getClientRects().length);
        const h = Math.round(document.getElementById('tool-list').getBoundingClientRect().height);
        input.value = ''; input.dispatchEvent(new Event('input', { bubbles: true }));
        return { shown: shown.length, height: h };
      }, m.filter);
      check(`${name}: the long stretch has a filter that fits a match in one screen`, f.shown > 0 && f.height < m.screen, { tallest: m.tallest, ...f });
    }
    const off = [];
    for (let i = 0; i < m.links; i++) {
      const d = await page.evaluate(async (i) => {
        const link = document.querySelectorAll('#settings-nav .settings-nav-group')[i];
        link.click();
        await new Promise((r) => setTimeout(r, 1600)); // a 5,000px smooth scroll settles in about 1.5s
        let scroller = link._head.parentElement;
        while (scroller && !(/(auto|scroll)/.test(getComputedStyle(scroller).overflowY) && scroller.scrollHeight > scroller.clientHeight)) scroller = scroller.parentElement;
        scroller = scroller || document.scrollingElement;
        const st = scroller.getBoundingClientRect().top;
        const end = scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 2;
        return [Math.round(link._head.getBoundingClientRect().top - Math.max(0, st)), end];
      }, i);
      off.push(d);
    }
    const title = await page.evaluate((n) => Math.round(document.querySelector(`#settings-${n} .settings-pane-title`)?.getBoundingClientRect().height || 0), name);
    check(`${name}: each index press lands its head under the title`, off.every(([d, end]) => d >= title - 4 && (d <= title + 24 || end)), { title, off });
  }
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
