// Stray marks under the status bar (the owner, with a screenshot: "a column
// of four small Atlas heads" at the bottom left, outside any UI, and "I want
// the bottom bar icon to stay the animated memorymap logo"). After boot and
// a visit to each main tab, with the companion on: every drawn element that
// is a child of <body> in the page's flow (not fixed, not absolute, not
// hidden), every face or Atlas mark whose box lies under the status bar's top
// edge or below the window, and what #ai-mark holds.
//
//   BASE=http://127.0.0.1:8830 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/strayheads.js      (exits 1 on a stray)
const { boot } = require('./lib.js');
(async () => {
  const W = Number(process.env.W || 1440);
  const H = Number(process.env.H || 900);
  const { page, browser } = await boot({ viewport: { width: W, height: H } });
  let out;
  try {
    await page.evaluate(() => { const b = $('avatar-buddy'); if (b) { b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); } });
    for (const tab of (process.env.TABS || 'dashboard,notes,chat,library,timeline,dashboard').split(',')) {
      await page.evaluate((t) => (typeof revealTab === 'function' ? revealTab(t) : switchTab(t)), tab).catch(() => null);
      await page.waitForTimeout(1200);
    }
    //: And a change of look, which redraws every Atlas on the page
    //: (`atlasRepaint`): the owner had just asked what Auto follows.
    for (const look of (process.env.LOOKS || 'feminine,masculine,auto').split(',')) {
      await page.evaluate((l) => {
        const s = document.getElementById('atlas-look');
        s.value = l;
        s.dispatchEvent(new Event('change', { bubbles: true }));
      }, look);
      await page.waitForTimeout(600);
    }
    out = await page.evaluate(() => {
      const bar = document.getElementById('status-bar').getBoundingClientRect();
      const describe = (el) => {
        const path = [];
        for (let n = el; n && n !== document.body && path.length < 5; n = n.parentElement) {
          path.push(`${n.tagName.toLowerCase()}${n.id ? `#${n.id}` : ''}${n.classList.length ? `.${[...n.classList].slice(0, 3).join('.')}` : ''}`);
        }
        const r = el.getBoundingClientRect();
        return { path: path.join(' < '), box: [r.left, r.top, r.width, r.height].map(Math.round) };
      };
      const shown = (el) => {
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height) return false;
        for (let n = el; n; n = n.parentElement) {
          const cs = getComputedStyle(n);
          if (cs.visibility === 'hidden' || cs.opacity === '0' || cs.display === 'none') return false;
        }
        return true;
      };
      //: <body>'s own children laid out in the flow: nothing the app draws
      //: should be one (every surface is fixed, absolute or hidden).
      const inFlow = [...document.body.children].filter((el) => {
        const cs = getComputedStyle(el);
        return !['fixed', 'absolute'].includes(cs.position) && cs.display !== 'none' && !['SCRIPT', 'STYLE', 'LINK', 'TEMPLATE', 'MAIN', 'HEADER', 'FOOTER', 'NAV', 'ASIDE'].includes(el.tagName) && el.id !== 'app' && !el.classList.contains('tab-page') && shown(el);
      }).map(describe);
      //: Every face or Atlas mark drawn under the bar's top edge, or below
      //: the window, that is not inside the bar itself or the companion.
      const marks = [...document.querySelectorAll('svg.nm, svg[class*="nm-"], .nm-live, [data-atlas-avatar] svg, svg[data-atlas-layer], .atl-figure-box, .name-mark')]
        .filter((el) => shown(el) && !el.closest('#nm-buddy, #status-bar'))
        .filter((el) => el.getBoundingClientRect().bottom > bar.top + 1 || el.getBoundingClientRect().top > innerHeight)
        .map(describe);
      //: Every Atlas drawing outside the companion and the status bar, with
      //: where it is, for the report.
      const atlases = [...document.querySelectorAll('svg.nm-atlas')].filter((el) => shown(el) && !el.closest('#nm-buddy')).map(describe);
      const mark = document.getElementById('ai-mark');
      return {
        bar: [bar.left, bar.top, bar.width, bar.height].map(Math.round),
        scroll: [document.documentElement.scrollHeight, innerHeight],
        inFlow,
        marks,
        atlases,
        aiMark: mark ? { canvas: Boolean(mark.querySelector('canvas')), spins: Boolean(mark.querySelector('canvas.emblem-spin')), svg: Boolean(mark.querySelector('svg')), kids: [...mark.children].map((c) => c.tagName) } : null,
      };
    });
  } finally {
    console.log(JSON.stringify(out, null, 1));
    await browser.close();
  }
  const bad = !out || out.inFlow.length || out.marks.length || !out.aiMark?.canvas || out.aiMark?.svg;
  process.exit(bad ? 1 : 0);
})();
