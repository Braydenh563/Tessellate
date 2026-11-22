// The owner: "atlas companion just perched in the middle of the weekly
// digest and a position adjustment after appearing instantly made it blink
// to the new spot again". Boots, then visits each tab and comes back to the
// dashboard, and after each arrival settles, measures how much of the
// companion's drawn figure lies over words in a card (text nodes' rects
// inside .card, .dash-widget and .widget) and whether it moved after it
// appeared (a second place within 4s of arriving, and how: a poof or a
// walk). Env: KIND, VW, VH. Exits 1 when it rests over words (more than
// 30 square px) or makes a poof after arriving.
const { boot } = require('./lib.js');
const VW = Number(process.env.VW || 1440);
const VH = Number(process.env.VH || 900);
const TABS = (process.env.TABS || 'notes,dashboard,chat,dashboard,library,dashboard').split(',');

(async () => {
  const { browser, page } = await boot({ viewport: { width: VW, height: VH } });
  await page.evaluate((k) => { localStorage.removeItem('nm-buddy-spots'); const b = $('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, process.env.KIND || 'atlas');
  await page.evaluate(() => {
    window.__moves = [];
    const orig = window.nameMarkBuddyMoveTo;
    window.nameMarkBuddyMoveTo = function (buddy, spot, instant) {
      const r = orig.apply(this, arguments);
      window.__moves.push({ t: performance.now(), instant: !!instant, kind: spot.kind || '', poof: buddy.classList.contains('nmb-poofing') });
      return r;
    };
  });
  const measure = () => page.evaluate(() => {
    const buddy = document.getElementById('nm-buddy');
    const c = buddy.querySelector('.nm-buddy-char').getBoundingClientRect();
    // The figure, not its box's empty corners: the middle 70% of its width.
    // Down to what it rests on (its seat or its soles): below that its box
    // is empty unless its legs hang over, which the pose says.
    const rest = nmb.pose === 'sit' && nmb.legs === 'tuck' ? NMB_SEAT : nmb.pose === 'sit' ? NMB_FEET : nmb.pose === 'stand' ? NMB_FEET - 2 : NMB_H;
    const fig = { left: c.left + c.width * 0.15, right: c.right - c.width * 0.15, top: c.top + 4, bottom: Math.min(c.bottom - 6, nmb.y + rest) };
    let area = 0; const words = [];
    const tab = document.getElementById(`tab-${nameMarkBuddyTab()}`);
    const walker = document.createTreeWalker(tab, NodeFilter.SHOW_TEXT);
    const range = document.createRange();
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (!n.textContent.trim() || !n.parentElement.closest('.card, .dash-widget, .widget')) continue;
      range.selectNodeContents(n);
      for (const r of range.getClientRects()) {
        const w = Math.min(r.right, fig.right) - Math.max(r.left, fig.left);
        const h = Math.min(r.bottom, fig.bottom) - Math.max(r.top, fig.top);
        if (w > 0 && h > 0) { area += w * h; if (words.length < 3) words.push(n.textContent.trim().slice(0, 24)); }
      }
    }
    return { tab: nameMarkBuddyTab(), x: Math.round(nmb.x), y: Math.round(nmb.y), perch: nmb.perch, overWords: Math.round(area), words };
  });
  const rows = [];
  await page.waitForTimeout(6000);
  rows.push({ ...(await measure()), moves: await page.evaluate(() => window.__moves.splice(0).map((m) => (m.instant ? 'place' : m.poof ? 'poof' : 'go'))) });
  for (const tab of TABS) {
    await page.click(`#tab-btn-${tab}`);
    await page.waitForTimeout(7000);
    rows.push({ ...(await measure()), moves: await page.evaluate(() => window.__moves.splice(0).map((m) => (m.instant ? 'place' : m.poof ? 'poof' : 'go'))) });
  }
  console.log(JSON.stringify(rows));
  await browser.close();
  // One line the lane runners count (they read FAIL, not the exit code alone).
  console.log((rows.some((r) => r.overWords > 30 || r.moves.includes('poof'))) ? 'FAIL perchtext: a measure above is out of bounds' : 'PASS perchtext');
  process.exit(rows.some((r) => r.overWords > 30 || r.moves.includes('poof')) ? 1 : 0);
})();
