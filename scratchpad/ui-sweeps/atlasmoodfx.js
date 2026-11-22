// What Atlas costs while a mood with small effects lasts (sparkles, thinking
// dots and pulses, drops, the wobble): those effects animate inside an
// `.atl-layer` svg, and the companion's pacer (`nameMarkBuddyTempo`,
// avatars.js) stepped them at 20Hz, a layout each time. Per mood, over MS ms
// of idle: paints, layouts and style recalcs a second (from a devtools trace
// and Performance metrics, no requestAnimationFrame loop of our own: that
// alone asks for a main frame every vsync, see atlaswalk.js), and how many
// animations run inside a layer svg and how many the pacer holds.
//
//   BASE=... node atlasmoodfx.js    MOODS=delighted,thinking,sad,confused,proud MS=4000
//
// Exits 1 when the median mood paints more than 1.5 times a second or lays
// out more than 2 times a second. The median, not the worst: the app's own
// poll lands in one 4s window in three or four (2 paints and a text change,
// about 40ms, whatever the mood; seen in calm as often as in sad), and a
// verdict on the worst window would be a verdict on the poll. INJECT runs
// print their numbers and give no verdict.
const fs = require('fs');
const os = require('os');
const { boot, OUT } = require('./lib.js');
const MOODS = (process.env.MOODS || 'calm,delighted,thinking,sad,confused,proud').split(',');
const MS = Number(process.env.MS || 4000);
const TAG = process.env.TAG || 'moodfx';

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Performance.enable');
  await page.evaluate(() => {
    const b = $('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true }));
    localStorage.removeItem('nm-buddy-spots');
  });
  await page.evaluate(() => revealTab('dashboard'));
  await page.waitForTimeout(5000);
  const out = {};
  let bad = false;
  for (const mood of MOODS) {
    // Held for longer than the measurement, so the mood's effects run
    // throughout; the tick's own acts are kept out of it.
    await page.evaluate((m) => { clearTimeout(nmb.timer); nmb.timer = 0; nameMarkBuddyExpress(m, 60000); }, mood);
    //: INJECT=1 puts one effect inside a layer svg, the shape the moods'
    //: effects had before Atlas round 5 moved them onto layer roots, so the
    //: pacer's handling of such an effect can still be measured.
    if (process.env.INJECT) {
      await page.waitForTimeout(300);
      await page.evaluate(() => {
        const dot = document.querySelector('#nm-buddy svg.atl-layer-body circle, #nm-buddy svg.atl-layer-body path');
        dot.animate([{ transform: 'scale(1)', opacity: 1 }, { transform: 'scale(1.3)', opacity: 0.4 }], { duration: 900, iterations: Infinity, direction: 'alternate' });
      });
    }
    await page.waitForTimeout(1500);
    const tp = `${os.tmpdir()}/moodfx-${process.pid}-${mood}.json`;
    const m0 = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
    await browser.startTracing(page, { path: tp, categories: ['devtools.timeline', 'disabled-by-default-devtools.timeline'] });
    const t0 = Date.now();
    await page.waitForTimeout(MS);
    const secs = (Date.now() - t0) / 1000;
    await browser.stopTracing();
    const m1 = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
    let paints = 0; let layouts = 0;
    for (const e of JSON.parse(fs.readFileSync(tp, 'utf8')).traceEvents) {
      if (e.name === 'Paint' && e.ph === 'X') paints += 1;
      if (e.name === 'Layout' && e.ph === 'X') layouts += 1;
    }
    fs.unlinkSync(tp);
    const anims = await page.evaluate(() => {
      const all = document.getElementById('nm-buddy').getAnimations({ subtree: true });
      const inLayer = all.filter((a) => a.effect?.target instanceof SVGElement && !(a.effect.target instanceof SVGSVGElement) && a.effect.target.closest('svg.atl-layer'));
      return { inLayer: inLayer.length, running: inLayer.filter((a) => a.playState === 'running').length, paced: nmbTempo.anims.length, names: [...new Set(inLayer.map((a) => a.animationName || 'waapi'))].join(' ') };
    });
    const r = {
      paintsPerSec: +(paints / secs).toFixed(2),
      layoutsPerSec: +(layouts / secs).toFixed(2),
      stylesPerSec: +((m1.RecalcStyleCount - m0.RecalcStyleCount) / secs).toFixed(1),
      taskMsPerSec: +((m1.TaskDuration - m0.TaskDuration) * 1000 / secs).toFixed(1),
      ...anims,
    };
    out[mood] = r;
    console.log(`${mood}: paints ${r.paintsPerSec}/s, layouts ${r.layoutsPerSec}/s, style ${r.stylesPerSec}/s, main ${r.taskMsPerSec} ms/s; in a layer ${r.inLayer} (${r.running} running, ${r.paced} paced) ${r.names}`);
  }
  fs.writeFileSync(`${OUT}/atlas-${TAG}.json`, JSON.stringify(out, null, 1));
  const median = (k) => { const v = Object.values(out).map((r) => r[k]).sort((a, b) => a - b); return v[Math.floor(v.length / 2)]; };
  console.log(`median: paints ${median('paintsPerSec')}/s, layouts ${median('layoutsPerSec')}/s`);
  if (!process.env.INJECT && (median('paintsPerSec') > 1.5 || median('layoutsPerSec') > 2)) bad = true;
  console.log(bad ? 'FAIL' : 'PASS');
  process.exitCode = bad ? 1 : 0;
  await browser.close();
})();
