// INBOX 1408: the document editor's two side panels are resizable in full
// screen (focus) mode, widths shared with the windowed editor.
//
//   BASE=http://127.0.0.1:8788 node scratchpad/ui-sweeps/docfocusresize.js
// Prints widths before and after each drag (getBoundingClientRect) and the
// remembered values; exit 1 when a check fails.
const { boot } = require('./lib.js');
const { openDoc } = require('./docopen.js');

const out = [];
const check = (name, ok, detail) => out.push({ name, ok: !!ok, detail });

const box = (page, sel) => page.evaluate((s) => {
  const el = document.querySelector(s);
  if (!el || !el.getClientRects().length) return null;
  const b = el.getBoundingClientRect();
  return { l: +b.left.toFixed(1), t: +b.top.toFixed(1), r: +b.right.toFixed(1), b: +b.bottom.toFixed(1), w: +b.width.toFixed(1), h: +b.height.toFixed(1) };
}, sel);

const drag = async (page, from, dx) => {
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  await page.mouse.move(from.x + dx / 2, from.y, { steps: 4 });
  await page.mouse.move(from.x + dx, from.y, { steps: 4 });
  await page.mouse.up();
  await page.waitForTimeout(250);
};

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await openDoc(page, { title: 'Resize sweep', content: '# Resize\n\n' + 'Their is a problem here. '.repeat(30) + '\n' });
  await page.evaluate(() => setDocView('live'));
  await page.waitForTimeout(600);

  // Windowed: the sidebar's own grip, the number to match.
  const windowedBefore = await box(page, '#doc-sidebar');
  const grip0 = await box(page, '#doc-sidebar > .sidebar-resize');
  await drag(page, { x: grip0.l + grip0.w / 2, y: grip0.t + grip0.h / 2 }, 60);
  const windowedAfter = await box(page, '#doc-sidebar');
  const stored = await page.evaluate(() => localStorage.getItem('sidebarWidth:doc-sidebar') || JSON.stringify(Object.entries(localStorage).filter(([k]) => /sidebarWidth/.test(k))));
  console.log('windowed', JSON.stringify({ before: windowedBefore.w, after: windowedAfter.w, stored }));
  check('windowed drag +60 widens the sidebar', windowedAfter.w > windowedBefore.w + 30, { windowedBefore, windowedAfter });

  await page.click('#doc-focus-toggle');
  await page.waitForTimeout(400);
  await page.click('#doc-focus-sidebar');
  await page.waitForTimeout(500);

  const before = await box(page, '#doc-sidebar');
  const grip = await box(page, '#doc-sidebar > .sidebar-resize');
  console.log('focus sidebar before', JSON.stringify({ side: before, grip }));
  check('focus: the sidebar has a visible grip', grip && grip.w > 0 && grip.h > 100, grip);
  if (grip) {
    const at = { x: grip.l + grip.w / 2, y: grip.t + grip.h / 2 };
    const hit = await page.evaluate(({ x, y }) => { const el = document.elementFromPoint(x, y); return el && (el.className || el.tagName); }, at);
    check('focus: the grip is what a press on it lands on', /sidebar-resize/.test(String(hit)), hit);
    await drag(page, at, 80);
    const after = await box(page, '#doc-sidebar');
    const line = await box(page, '#doc-editor .cm-content .cm-line, #doc-preview > *');
    console.log('focus sidebar after +80', JSON.stringify({ side: after, line }));
    check('focus: drag +80 widens the sidebar', after.w > before.w + 50, { before: before.w, after: after.w });
    check('focus: the page gave up the room', line && line.l >= after.r - 1, { line, after });
    const back = grip && (await box(page, '#doc-sidebar > .sidebar-resize'));
    await drag(page, { x: back.l + back.w / 2, y: back.t + back.h / 2 }, -400);
    const min = await box(page, '#doc-sidebar');
    console.log('focus sidebar after -400', min.w);
    check('focus: held at the floor', min.w >= 168 && min.w <= 172, min.w);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);
    await page.click('#doc-focus-sidebar');
    await page.waitForTimeout(400);
    const reopened = await box(page, '#doc-sidebar');
    check('focus: the width is remembered across close and open', Math.abs(reopened.w - min.w) < 1, { min: min.w, reopened: reopened.w });
  }

  // The suggestions panel.
  await page.evaluate(() => document.getElementById('doc-prose')?.click());
  await page.waitForTimeout(500);
  const p0 = await box(page, '#doc-prose-panel');
  const pg = await box(page, '.doc-prose-resize');
  console.log('focus prose before', JSON.stringify({ panel: p0, grip: pg }));
  check('focus: the suggestions panel has a visible grip', pg && pg.w > 0 && pg.h > 100, pg);
  if (pg && p0) {
    await drag(page, { x: pg.l + pg.w / 2, y: pg.t + pg.h / 2 }, -80);
    const p1 = await box(page, '#doc-prose-panel');
    console.log('focus prose after -80', JSON.stringify({ panel: p1 }));
    check('focus: dragging left widens the suggestions panel', p1.w > p0.w + 50, { before: p0.w, after: p1.w });
  }

  // Shared: leaving the mode, the windowed sidebar has the width set inside it.
  await page.evaluate(() => toggleDocFocus(false));
  await page.waitForTimeout(500);
  const shared = await box(page, '#doc-sidebar');
  console.log('windowed after leaving focus', shared && shared.w);
  check('the windowed sidebar takes the width set in focus mode', shared && Math.abs(shared.w - 170) < 2, shared);

  await page.screenshot({ path: `${process.env.SCRATCH || '.'}/docfocusresize.png` });
  for (const c of out) console.log(c.ok ? 'PASS' : 'FAIL', c.name, c.ok ? '' : JSON.stringify(c.detail));
  await browser.close();
  process.exit(out.every((c) => c.ok) ? 0 : 1);
})().catch((e) => { console.error(e); process.exit(2); });
