// Brief 88 (d), the owner: "more atlas variations for each gesture,
// movement, position, emotion and more". Plays each act ROUNDS times and
// walks between two perches as often, and records each play's drawn variant
// (`data-variant`), its manner (`data-manner`) and each walk's stride
// (`nmb.stride`). PASS when every act shows at least three different plays
// and no play is the same as the one before it, and the walks likewise.
// KIND (atlas, me, persona).
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate((k) => { const b = $('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, process.env.KIND || 'atlas');
  await page.waitForTimeout(4000);
  const top = await page.evaluate(() => document.getElementById('status-bar').getBoundingClientRect().top);
  const rounds = Number(process.env.ROUNDS || 6);
  const acts = (process.env.ACTS || 'wave,cheer,hop,nod,startle,stretch,shrug').split(',');
  const seen = {};
  let bad = 0;
  for (const act of acts) {
    seen[act] = [];
    for (let i = 0; i < rounds; i += 1) {
      const play = await page.evaluate((a) => { nameMarkBuddyAct(a); const b = document.getElementById('nm-buddy'); return `${b.dataset.variant ?? '-'}/${b.dataset.manner ?? '-'}`; }, act);
      seen[act].push(play);
      await page.waitForTimeout(400);
      await page.evaluate(() => nameMarkBuddyAct(''));
      await page.waitForTimeout(300);
    }
  }
  seen.walk = [];
  // A walk's length (a float's, for Atlas): a short step is a hop and a
  // long way a poof, which have no stride; one is counted when it took a
  // stride (its pick written to `nmb.stride`, watched for the write: the picker is the file's own).
  for (let i = 0; seen.walk.length < rounds && i < rounds * 3; i += 1) {
    const s = await page.evaluate(([x, t]) => { const b = document.getElementById('nm-buddy'); let took = null; let held = nmb.stride; Object.defineProperty(nmb, 'stride', { configurable: true, get: () => held, set: (v) => { held = v; took = String(v); } }); try { nameMarkBuddyMoveTo(b, { kind: 'yours', pose: 'stand', legs: '', x, y: Math.round(t - NMB_FEET + 1) }); } finally { delete nmb.stride; nmb.stride = held; } return took; }, [i % 2 ? 480 : 700, top]);
    if (s !== null) seen.walk.push(s);
    await page.waitForTimeout(2200);
  }
  for (const [k, plays] of Object.entries(seen)) {
    const distinct = new Set(plays).size;
    const repeats = plays.filter((p, i) => i && p === plays[i - 1]).length;
    const ok = distinct >= 3 && !repeats;
    if (!ok) bad += 1;
    console.log(`${ok ? 'ok  ' : 'BAD '} ${k}: ${distinct} different, ${repeats} repeats (${plays.join(' ')})`);
  }
  console.log(bad ? 'FAIL' : 'PASS');
  await browser.close();
})();
