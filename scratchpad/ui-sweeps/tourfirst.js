// INBOX 426 (y): "the guided tour breaks after Next to Notes" (image 87, the
// log: "tour-spot asked for 336,275 drew at 1128,4"), and the companion step's
// card covers its own control until Next then Back (images 95, 96).
//
// Walks a section's steps with Next, and on every step samples the card, the
// ring and the target every 50ms for 1.5s from the press: the card must not
// cover the target at ANY sample after the card first shows (not only once
// it settles), the ring must sit around the target, and no "asked for ...
// drew at" correction may fire. Then Back and Next again, which is the
// owner's workaround, must give the same placement as the first showing.
//
//   BASE=http://127.0.0.1:8793 SECTIONS=basics,settings VIEWPORTS=1440x900,1600x1000 node tourfirst.js
const { boot } = require('./lib.js');
const SECTIONS = (process.env.SECTIONS || 'basics,settings').split(',');
const VIEWPORTS = (process.env.VIEWPORTS || '1440x900,1600x1000').split(',').map((v) => v.split('x').map(Number));
let failures = 0;

function sample() {
  const card = document.getElementById('tour-card');
  const spot = document.getElementById('tour-spot');
  if (!card || card.classList.contains('hidden') || card.getAttribute('aria-busy') === 'true') return null;
  const el = openTour.inspect.run?.el;
  const t = el ? el.getBoundingClientRect() : null;
  const c = card.getBoundingClientRect();
  const s = spot && !spot.classList.contains('hidden') ? spot.getBoundingClientRect() : null;
  const inter = (a, b) => (a && b ? Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)) : 0);
  return {
    title: openTour.inspect.run?.step?.title,
    cover: t ? Math.round(inter(c, t) / Math.max(1, t.width * t.height) * 100) : 0,
    //: The ring pads 6px and is clamped at the window's top edge (a tab bar control sits at 4).
    ringOff: t && s ? Math.round(Math.max(Math.abs(s.left - (t.left - 6)), Math.abs(s.top - Math.max(0, t.top - 6)))) : null,
    card: [Math.round(c.left), Math.round(c.top)],
    target: t ? [Math.round(t.left), Math.round(t.top), Math.round(t.width), Math.round(t.height)] : null,
  };
}

async function watch(page, press) {
  await page.evaluate(() => { window.__tf = []; window.__tfw = []; });
  await press();
  const samples = [];
  for (let i = 0; i < 60; i++) {
    samples.push(await page.evaluate(sample));
    await page.waitForTimeout(50);
  }
  return samples.filter(Boolean);
}

(async () => {
  for (const [w, h] of VIEWPORTS) {
    const { browser, page } = await boot({ viewport: { width: w, height: h } });
    const warns = [];
    page.on('console', (m) => { if (/asked for/.test(m.text())) warns.push(m.text()); });
    for (const sec of SECTIONS) {
      warns.length = 0;
      let samples = await watch(page, () => page.evaluate((s) => openTour(s), sec));
      for (let step = 0; step < 12; step++) {
        if (!samples.length) { const st = await page.evaluate(() => ({ busy: document.getElementById("tour-card")?.getAttribute("aria-busy"), hidden: document.getElementById("tour-card")?.classList.contains("hidden"), step: openTour.inspect.run?.step?.title, idx: openTour.inspect.run?.index, n: openTour.inspect.run?.steps?.length })); console.log("   no card within 3s", JSON.stringify(st)); break; }
        const first = samples[0];
        const worst = samples.reduce((a, b) => (b.cover > a.cover ? b : a));
        const last = samples[samples.length - 1];
        const ringBad = samples.filter((x) => x.ringOff !== null && x.ringOff > 3).length;
        const bad = worst.cover > 0 || ringBad > 0;
        if (bad) failures++;
        console.log(`${bad ? 'FAIL' : 'ok  '} ${w}x${h} ${sec} "${last.title}": covers ${worst.cover}% at worst (first ${first.cover}%, last ${last.cover}%), ring off in ${ringBad}/${samples.length} samples, card ${JSON.stringify(first.card)} -> ${JSON.stringify(last.card)}`);
        const nextLabel = await page.evaluate(() => document.getElementById('tour-next')?.textContent || '');
        if (/^Done/.test(nextLabel)) break;
        // The owner's workaround, Next then Back, must not be needed: the
        // card the second time is where it was the first.
        if (step === 0 || /companion/i.test(last.title || '')) {
          await page.evaluate(() => openTour.inspect.next());
          await page.waitForTimeout(1200);
          const back = await watch(page, () => page.evaluate(() => openTour.inspect.back()));
          const b = back[back.length - 1];
          if (b && b.title === last.title && (Math.abs(b.card[0] - last.card[0]) > 2 || Math.abs(b.card[1] - last.card[1]) > 2)) {
            failures++;
            console.log(`FAIL   Next then Back moved "${b.title}"'s card ${JSON.stringify(last.card)} -> ${JSON.stringify(b.card)}`);
          }
        }
        if (/^Next: /.test(nextLabel) && !process.env.CHAIN) break;
        samples = await watch(page, () => page.evaluate(() => openTour.inspect.next()));
      }
      if (warns.length) { failures++; console.log(`FAIL   ${warns.length} placement corrections: ${warns.slice(0, 3).join(' | ')}`); }
      await page.evaluate(() => openTour.inspect.close(false)).catch(() => {});
      await page.waitForTimeout(400);
    }
    await browser.close();
  }
  console.log(failures ? `${failures} failing` : 'tour holds');
  process.exitCode = failures ? 1 : 0;
})();
