// TIMELINE_PLAN audit 2026-10-18: the open rows of sections 10 and 11 as numbers.
//   BASE=http://127.0.0.1:8788 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers SCRATCH=/tmp/x node timeline1018.js
// Prints JSON per width: day-head overlap, small targets, rail dot offset,
// scrubber labels (when built), the reminders quick-add row at 390.
const { boot } = require('./lib.js');
const WIDTHS = [
  { w: 1440, h: 900, touch: false },
  { w: 390, h: 844, touch: true },
];
(async () => {
  const out = [];
  for (const { w, h, touch } of WIDTHS) {
    const opts = touch
      ? { viewport: { width: w, height: h }, hasTouch: true, isMobile: true }
      : { viewport: { width: w, height: h } };
    const { browser, page } = await boot(opts);
    await page.evaluate(() => window.switchTab('timeline'));
    await page.waitForTimeout(900);
    await page.evaluate(() => document.querySelector('#timeline-view-seg [data-timeline-view="feed"]')?.click());
    await page.waitForTimeout(600);
    await page.evaluate(() => {
      const sel = document.getElementById('timeline-scale');
      if (sel && sel.value !== 'day') {
        sel.value = 'day';
        sel.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
    await page.waitForTimeout(900);
    const r = await page.evaluate(() => {
      const rect = (el) => el.getBoundingClientRect();
      const heads = [...document.querySelectorAll('.timeline-bucket-head')].filter((e) => e.offsetParent);
      const overlap = (a, b) => {
        const x = rect(a), y = rect(b);
        return x.left < y.right - 0.5 && y.left < x.right - 0.5 && x.top < y.bottom - 0.5 && y.top < x.bottom - 0.5;
      };
      let headOverlaps = 0;
      const headButtons = [];
      for (const head of heads) {
        const kids = [...head.querySelectorAll('*')].filter((e) => e.offsetParent && rect(e).width > 0 && e.children.length === 0);
        for (let i = 0; i < kids.length; i++) for (let j = i + 1; j < kids.length; j++) {
          if (kids[i].contains(kids[j]) || kids[j].contains(kids[i])) continue;
          if (overlap(kids[i], kids[j])) headOverlaps++;
        }
        head.querySelectorAll('button').forEach((b) => headButtons.push({ cls: b.className, w: Math.round(rect(b).width), h: Math.round(rect(b).height) }));
      }
      const min = touch => (touch ? 44 : 24);
      const coarse = matchMedia('(pointer: coarse)').matches;
      const need = coarse ? 44 : 24;
      const targets = [...document.querySelectorAll('#tab-timeline button, #tab-timeline [role="button"], #tab-timeline select, #tab-timeline input')]
        .filter((e) => e.offsetParent && !e.closest('.hidden') && rect(e).width > 0);
      const small = targets.filter((e) => rect(e).height < need - 0.5 || rect(e).width < need - 0.5)
        .map((e) => `${e.id || e.className.toString().slice(0, 40)} ${Math.round(rect(e).width)}x${Math.round(rect(e).height)}`);
      // Rail dot against the first line's centre.
      const rows = [...document.querySelectorAll('.timeline-row')].filter((e) => e.offsetParent).slice(0, 12);
      const dots = rows.map((row) => {
        const dot = row.querySelector('.timeline-row-mark');
        const title = row.querySelector('.timeline-row-title');
        if (!dot || !title) return null;
        const lh = parseFloat(getComputedStyle(title).lineHeight) || rect(title).height;
        const d = rect(dot);
        return Math.round(((d.top + d.height / 2) - (rect(title).top + lh / 2)) * 10) / 10;
      });
      return { coarse, need, heads: heads.length, headOverlaps, headButtons: headButtons.slice(0, 3), small, dotOffsets: dots };
    });
    out.push({ w, ...r });
    await browser.close();
  }
  console.log(JSON.stringify(out, null, 1));
})();
