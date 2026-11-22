// The Timeline calendar's head: one row, one centre line (the owner,
// 2026-11-12: "these two elements arent aligned in the timeline").
//   BASE=http://127.0.0.1:8781 THEME=dark node calheadalign.js
// At 1280, 1024 and 360, week span, with the Show: reminders chip on, every
// control on the head's first line (the steps, the title, Add, the chip, the
// span strip) has its centre within 1px of Add's, and Add, the chip and the
// strip share one height. Exits 1 on a miss. Before the fix, at 1280: Add
// 154.1 (32px), the strip 150.1 (36.4px).
const { boot } = require('./lib');

(async () => {
  const { browser, page } = await boot();
  let bad = 0;
  for (const width of [1280, 1024, 360]) {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(() => { localStorage.setItem('timeline-view', 'calendar'); localStorage.setItem('timeline-cal-span', 'week'); });
    await page.evaluate(() => switchTab('timeline'));
    await page.waitForTimeout(1500);
    await page.evaluate(() => { timelineCal.only = 'reminder'; paintTimeline(); });
    await page.waitForTimeout(800);
    const got = await page.evaluate(() => {
      const box = (sel) => { const el = document.querySelector(`.timeline-cal-head > ${sel}`); if (!el) return null; const b = el.getBoundingClientRect(); return { top: b.top, h: b.height, mid: b.top + b.height / 2 }; };
      return { add: box('.timeline-cal-add'), only: box('.timeline-cal-only'), seg: box('.timeline-cal-span'), title: box('.timeline-cal-title'), back: box('[data-cal-act="earlier"]') };
    });
    //: A row is what sits within half a control of a centre; a narrow head
    //: wraps (360: the steps and title, then Add and the chip), so each row
    //: is checked against its own first control.
    const add = got.add;
    const near = (a, b) => a && b && Math.abs(a.mid - b.mid) < Math.max(a.h, b.h) / 2;
    const line = Object.entries(got).filter(([, b]) => near(b, add));
    const off = [
      ...line.filter(([, b]) => Math.abs(b.mid - add.mid) > 1).map(([k, b]) => `${k} ${(b.mid - add.mid).toFixed(1)}px`),
      ...(got.back && got.title && near(got.back, got.title) && Math.abs(got.back.mid - got.title.mid) > 1 ? [`title ${(got.title.mid - got.back.mid).toFixed(1)}px from the steps`] : []),
    ];
    const tall = ['only', 'seg'].filter((k) => got[k] && Math.abs(got[k].h - add.h) > 1).map((k) => `${k} ${got[k].h.toFixed(1)} vs ${add.h.toFixed(1)}`);
    console.log(width, Object.fromEntries(line.map(([k, b]) => [k, `${b.mid.toFixed(1)} (${b.h.toFixed(1)})`])), off.length || tall.length ? `MISS ${[...off, ...tall].join(', ')}` : 'ok');
    if (!add || off.length || tall.length) bad += 1;
  }
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
