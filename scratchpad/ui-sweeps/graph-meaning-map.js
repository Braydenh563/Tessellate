// The Map of meaning reads as a map (owner, 2026-11-22), at 1440 and 1920, with 33 and then 500 notes.
//   BASE=http://127.0.0.1:8879 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/graph-meaning-map.js
// Seeds three topics (cooking, cycling, tax) from tests/fixtures/meaning_notes.json, a few [[links]], then more of the
// same topics up to 500 (1440 measures 33 then 500 notes; 1920 the 500 already seeded). Prints, per size: the mean drawn distance between same-topic pairs over
// different-topic pairs (ratio), cluster names, dot labels, overlaps (name plate vs dot label, plate
// vs plate), the faint lines drawn, the last frame's ms, and console errors. PASS needs ratio < 0.7.
const { boot } = require('./lib.js');
const fs = require('fs');
const NOTES = JSON.parse(fs.readFileSync(`${__dirname}/../../tests/fixtures/meaning_notes.json`, 'utf8'));
let failed = 0;
const say = (ok, name, detail) => { if (!ok) failed += 1; console.log(`${ok ? 'PASS' : 'FAIL'} ${name}: ${detail}`); };

async function seed(page, total, known) {
  return page.evaluate(async ({ notes, total, known }) => {
    const have = await apiJson('/entries');
    const topics = Object.keys(notes);
    const topicOf = { ...known };
    for (const e of have) for (const t of topics) if (notes[t].some((n) => e.content.startsWith(n.slice(0, 30)))) topicOf[e.id] = t;
    //: Past the written notes, each topic's notes are made of its own vocabulary (a fixed generator, so a
    //: run is repeatable) with two words of another topic's, as a real notebook's topics overlap a little.
    const vocab = {};
    for (const t of topics) vocab[t] = [...new Set(notes[t].join(' ').toLowerCase().match(/[a-z]{4,}/g))];
    let seed = 12345;
    const rnd = (n) => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed % n; };
    let i = have.length;
    while (i < total) {
      const t = topics[i % 3];
      const written = notes[t][Math.floor(i / 3)];
      let text = written;
      if (!text || i >= 33) {
        const words = [];
        for (let w = 0; w < 7; w++) words.push(vocab[t][rnd(vocab[t].length)]);
        const o = vocab[topics[(i + 1) % 3]];
        words.push(o[rnd(o.length)], o[rnd(o.length)]);
        text = words.join(' ');
      }
      const body = i === 3 ? `${text} [[${notes[t][0].slice(0, 20)}]]` : text;
      const r = await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: body }) });
      topicOf[r.id] = t;
      i += 1;
    }
    return topicOf;
  }, { notes: NOTES, total, known: known || {} });
}

async function measure(page, topicOf) {
  return page.evaluate((topicOf) => {
    const s = gcTab;
    const dots = s.nodes.filter((n) => !n.isGroup && Number.isFinite(n.x) && topicOf[n.id]);
    let same = 0, nSame = 0, other = 0, nOther = 0;
    for (let a = 0; a < dots.length; a++) for (let b = a + 1; b < dots.length; b++) {
      const d = Math.hypot(dots[a].x - dots[b].x, dots[a].y - dots[b].y);
      if (topicOf[dots[a].id] === topicOf[dots[b].id]) { same += d; nSame += 1; } else { other += d; nOther += 1; }
    }
    const hit = (p, q) => p.left < q.right && q.left < p.right && p.top < q.bottom && q.top < p.bottom;
    const plates = s.topicPlates || [];
    const labels = s.labelBoxes || [];
    let plateVsLabel = 0, plateVsPlate = 0;
    for (const p of plates) for (const l of labels) if (hit(p, l)) plateVsLabel += 1;
    for (let a = 0; a < plates.length; a++) for (let b = a + 1; b < plates.length; b++) if (hit(plates[a], plates[b])) plateVsPlate += 1;
    return {
      kind: s.layoutKind, notes: dots.length, ratio: (same / nSame) / (other / nOther),
      plates: plates.length, names: (s.tree?.clusters || []).map((c) => c.label), source: s.tree?.source,
      dotLabels: labels.length, plateVsLabel, plateVsPlate,
      lines: s.edges.length, ties: s.edges.filter((e) => e.kind === 'similar').length,
      frameMs: s.timing.lastFrame,
    };
  }, topicOf);
}

async function run(width, height, sizes, known, errs) {
  const { browser, page } = await boot({ viewport: { width, height } });
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  page.on('pageerror', (e) => errs.push(e.message));
  let topicOf = await seed(page, sizes[0], known);
  await page.evaluate(() => { prefs.set('graph-layout', 'map'); switchTab('graph'); });
  await page.waitForTimeout(3000);
  await page.evaluate(() => { const el = document.getElementById('graph-layout'); el.value = 'map'; el.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForTimeout(3500);
  const runs = [];
  for (const total of sizes) {
    if (total > sizes[0]) {
      await page.evaluate(() => switchTab('notes'));
      topicOf = await seed(page, total, topicOf);
      await page.evaluate(() => { switchTab('graph'); });
      await page.waitForTimeout(6000);
    }
    const m = await measure(page, topicOf);
    runs.push(m);
    say(m.kind === 'map' && m.notes >= total - 2, `${width} ${total}: placed`, `layout ${m.kind}, ${m.notes} notes, source ${m.source}`);
    say(m.ratio < 0.7, `${width} ${total}: same-topic over different-topic distance`, m.ratio.toFixed(3));
    say(m.plates >= 3, `${width} ${total}: cluster names`, `${m.plates} plates: ${m.names.join(' | ')}`);
    say(m.plateVsLabel === 0 && m.plateVsPlate === 0, `${width} ${total}: overlaps`, `plate vs dot label ${m.plateVsLabel}, plate vs plate ${m.plateVsPlate}, dot labels ${m.dotLabels}`);
    say(m.lines > 0, `${width} ${total}: faint lines`, `${m.lines} drawn, ${m.ties} by meaning`);
    say(m.frameMs < 50, `${width} ${total}: last frame`, `${Number(m.frameMs).toFixed(1)} ms`);
  }
  await page.screenshot({ path: `${process.env.OUT || '/tmp'}/graph-meaning-${width}.png` });
  await browser.close();
  return topicOf;
}

(async () => {
  const errs = [];
  const known = await run(1440, 900, [33, 500], {}, errs);
  await run(1920, 1080, [500], known, errs);
  say(errs.length === 0, 'console errors', errs.length ? errs.slice(0, 3).join(' / ') : '0');
  console.log(failed ? `FAIL: ${failed}` : 'PASS');
  process.exit(failed ? 1 : 0);
})();
