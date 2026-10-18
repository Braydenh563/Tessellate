// TIMELINE_PLAN 10 row 6: the density strip's labels, as numbers.
//   BASE=http://127.0.0.1:8788 node timelineticks1018.js
// Per width (1440, 1024, 390): strip visible, label count and step, label
// boxes inside the strip, pairwise overlaps, gaps, the d3 requests, the strip's
// width, a click on the strip still moving the feed.
const { boot } = require('./lib.js');
const WIDTHS = [{ w: 1440, h: 900 }, { w: 1024, h: 820 }, { w: 390, h: 844, touch: true }];
(async () => {
  const out = [];
  for (const { w, h, touch } of WIDTHS) {
    const opts = touch ? { viewport: { width: w, height: h }, hasTouch: true, isMobile: true } : { viewport: { width: w, height: h } };
    const { browser, page } = await boot(opts);
    const reqs = [];
    page.on('request', (r) => { const u = r.url(); if (/d3\.v7|timeline-ticks/.test(u)) reqs.push(u.split('/').pop().split('?')[0]); });
    await page.evaluate(() => window.switchTab('timeline'));
    await page.waitForTimeout(800);
    await page.evaluate(() => document.querySelector('#timeline-view-seg [data-timeline-view="feed"]')?.click());
    await page.waitForTimeout(1500);
    const r = await page.evaluate(async () => {
      const strip = document.getElementById('timeline-scrubber');
      const sb = strip.getBoundingClientRect();
      const shown = !strip.classList.contains('hidden') && sb.width > 0;
      const labels = [...strip.querySelectorAll('.timeline-tick')];
      const boxes = labels.map((l) => l.getBoundingClientRect());
      let overlaps = 0;
      let minGap = 1e9;
      for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i], b = boxes[j];
        if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom) overlaps++;
      }
      const tops = boxes.map((b) => b.top).sort((x, y) => x - y);
      for (let i = 1; i < tops.length; i++) minGap = Math.min(minGap, tops[i] - tops[i - 1]);
      const outside = boxes.map((b, i) => [labels[i].textContent, Math.round(b.left - sb.left), Math.round(b.right - sb.left), Math.round(b.top - sb.top), Math.round(sb.bottom - b.bottom)]).filter((o) => o[1] < 0 || o[2] > sb.width || o[3] < 0 || o[4] < 0);
      const scroller = document.getElementById('timeline-scroll');
      const before = scroller.scrollTop;
      let moved = null;
      if (shown) {
        const y = sb.top + sb.height * 0.8;
        strip.dispatchEvent(new PointerEvent('pointerdown', { clientX: sb.left + 10, clientY: y, pointerId: 1, bubbles: true }));
        await new Promise((res) => setTimeout(res, 500));
        moved = Math.round(scroller.scrollTop - before);
      }
      const first = labels[0];
      const fontPx = first ? getComputedStyle(first).fontSize : null;
      const color = first ? getComputedStyle(first).color : null;
      // Other spans through the same code: a week, a month, two months, two
      // years, a decade, drawn into this strip and measured the same way.
      const real = window.timelineDensitySpan;
      const spans = {};
      for (const days of [6, 30, 60, 700, 4000]) {
        window.timelineDensitySpan = () => ({ newest: Date.now(), oldest: Date.now() - days * 86400000, width: days * 86400000 });
        await timelineTicks();
        const ls = [...strip.querySelectorAll('.timeline-tick')];
        const bs = ls.map((l) => l.getBoundingClientRect());
        let ov = 0;
        for (let i = 0; i < bs.length; i++) for (let j = i + 1; j < bs.length; j++) {
          const a = bs[i], b = bs[j];
          if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom) ov++;
        }
        const sb2 = strip.getBoundingClientRect();
        const out2 = bs.filter((b) => b.left < sb2.left - 0.5 || b.right > sb2.right + 0.5 || b.top < sb2.top - 0.5 || b.bottom > sb2.bottom + 0.5).length;
        spans[days] = { n: ls.length, ov, out: out2, labels: ls.slice(0, 4).map((l) => l.textContent).join(',') };
      }
      window.timelineDensitySpan = real;
      return {
        spans,
        shown, stripW: Math.round(sb.width), stripH: Math.round(sb.height), feedW: Math.round(scroller.getBoundingClientRect().width),
        labels: labels.map((l) => l.textContent).join(','), count: labels.length, overlaps, minGap: Math.round(minGap * 10) / 10,
        outside, majors: labels.filter((l) => l.classList.contains('is-major')).length,
        fontPx, color, moved,
        hScroll: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });
    out.push({ w, reqs: [...new Set(reqs)].join(','), ...r });
    await browser.close();
  }
  console.log(JSON.stringify(out, null, 1));
})();
