// INBOX 1402 (the owner, 2026-10-27): "atlas looks like a bored or grumpy
// gangster with its facial expressions and arm positioning half the time".
// Measured over the cycle, not one frame: the companion as Atlas on the
// dashboard, sampled every 100ms through a scripted session (idle, typing in
// the chat box, a long chat turn, idle reading), and each mood held still.
// Per sample, from what renders: the mouth's curve (the opacity-weighted
// sag of the drawn mouths, positive a smile), the left brow's rendered turn
// plus its drawn slant (positive: the inner end lower, a scowl) and drop,
// and the rig's arm joints (raise out from hanging, elbow bend).
// A sample is "grumpy" when the mouth curve is at or under 0.3 (flat or
// down), the brows are lowered (inner end down past 4 degrees, or dropped
// past 0.25px) or the arms are slack (both within 6 degrees of hanging
// with under 8 of elbow), a forearm folded across the body (60 degrees of
// elbow on an arm within 40 of hanging) or folded across the chest (both turned in 50 degrees or more).
// Env: BASE, LOOK1402 (masculine|feminine), MS (idle phase scale, default 1),
// CLOCK (the page's start time, default 2026-10-27T14:00:00; 03:00 dozes).
//   node scratchpad/ui-sweeps/atlasrest1402.js            the session
//   CASE=moods node scratchpad/ui-sweeps/atlasrest1402.js each mood held
const { boot } = require('./lib.js');
const LOOK = process.env.LOOK1402 || 'masculine';
const K = Number(process.env.MS || 1);

const SAMPLE = () => {
  const buddy = document.getElementById('nm-buddy');
  // Each drawn mouth's curve, read from its path: the mean sag of its Q
  // handles below its ends (positive smiles); an open mouth 2.5, an O 0.
  const curve = {};
  for (const g of buddy?.querySelectorAll('.atl-mouth .atl-m') || []) {
    const name = [...g.classList].find((c) => c.startsWith('atl-m-'))?.slice(6);
    const el = g.firstElementChild;
    if (!name || !el || name in curve) continue;
    const d = el.getAttribute('d') || '';
    if (el.tagName === 'ellipse' || !d) { curve[name] = 0; continue; }
    if (el.classList.contains('atl-ink')) { curve[name] = 2.5; continue; }
    const n = (d.match(/-?\d+(?:\.\d+)?/g) || []).map(Number);
    const sags = []; let y = n[1];
    for (let i = 2; i + 3 < n.length; i += 4) { sags.push(n[i + 1] - (y + n[i + 3]) / 2); y = n[i + 3]; }
    curve[name] = sags.length ? sags.reduce((a, b) => a + b, 0) / sags.length : 0;
  }
  const box = buddy?.querySelector('.atl-figure-box');
  const browL = buddy?.querySelector('.atl-brow-l');
  if (!box || !browL) return null;
  let w = 0, c = 0;
  for (const [name, k] of Object.entries(curve)) {
    const el = buddy.querySelector(`.atl-m-${name}`);
    const o = el ? +getComputedStyle(el).opacity : 0;
    w += o; c += o * k;
  }
  const m = /matrix\(([^)]+)\)/.exec(getComputedStyle(browL).transform);
  let rot = 0, ty = 0;
  if (m) { const v = m[1].split(',').map(Number); rot = Math.atan2(v[1], v[0]) * 180 / Math.PI; ty = v[5]; }
  // The drawn slant of the brow at rest: the chord from its outer to its
  // inner end, inner end down positive.
  const line = browL.querySelector('.atl-brow-line');
  let drawn = 0;
  if (line) {
    const L = line.getTotalLength(); const a = line.getPointAtLength(0); const b = line.getPointAtLength(L);
    drawn = Math.atan2(b.y - a.y, Math.abs(b.x - a.x)) * 180 / Math.PI * (b.x > a.x ? 1 : -1);
  }
  const arms = (box.atlasRig?.arms || []).map((a) => ({ side: a.side, raise: ((((-a.j.sh.x * a.sgn) + 180) % 360) + 360) % 360 - 180, el: a.j.el.x }));
  const acts = [...buddy.classList].filter((x) => /^nmb-(act-|pout|grumpy|groggy|sleep|think|drowsy)/.test(x));
  return {
    mood: typeof atlasMoodNow !== 'undefined' ? atlasMoodNow : '', acts, pose: buddy.dataset.pose || '', v: buddy.dataset.atlasVariant || '0',
    curve: w ? +(c / w).toFixed(2) : 0, brow: +(rot + drawn).toFixed(1), browRot: +rot.toFixed(1), drawn: +drawn.toFixed(1), browY: +ty.toFixed(2), arms,
  };
};
function grumpy(s) {
  const reasons = [];
  if (s.curve <= 0.3) reasons.push('mouth');
  if (s.brow > 4 || s.browY > 0.25) reasons.push('brows');
  if (s.arms.length === 2) {
    if (s.arms.every((a) => Math.abs(a.raise) < 6 && Math.abs(a.el) < 8)) reasons.push('slack');
    if (s.arms.every((a) => a.raise <= -50)) reasons.push('crossed');
    // A forearm folded across the body while the arm hangs (her winding elbow).
    if (s.arms.some((a) => a.el >= 60 && Math.abs(a.raise) <= 40)) reasons.push('forearm');
  }
  return reasons;
}
function summarise(samples, label) {
  const n = samples.length || 1;
  const count = (r) => samples.filter((s) => grumpy(s).includes(r)).length;
  const any = samples.filter((s) => grumpy(s).length).length;
  const moods = {};
  for (const s of samples) {
    const key = `${s.mood}/${s.pose}/v${s.v}${s.acts.length ? '+' + s.acts.join('+') : ''}${grumpy(s).length ? ' [' + grumpy(s).join(',') + ']' : ''}`;
    moods[key] = (moods[key] || 0) + 1;
  }
  return { label, n: samples.length, grumpyPct: +(100 * any / n).toFixed(1), mouthPct: +(100 * count('mouth') / n).toFixed(1), browsPct: +(100 * count('brows') / n).toFixed(1), slackPct: +(100 * count('slack') / n).toFixed(1), crossedPct: +(100 * count('crossed') / n).toFixed(1), forearmPct: +(100 * count('forearm') / n).toFixed(1), states: moods };
}

async function setup() {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, clock: process.env.CLOCK || '2026-10-27T14:00:00' });
  await page.evaluate((look) => {
    localStorage.removeItem('nm-buddy-spots');
    const sel = document.getElementById('atlas-look'); sel.value = look; sel.dispatchEvent(new Event('change', { bubbles: true }));
    const b = document.getElementById('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true }));
    revealTab('dashboard');
  }, LOOK);
  await page.waitForFunction(() => document.querySelector('#nm-buddy .atl-figure-box')?.atlasRig, null, { timeout: 20000 });
  await page.waitForTimeout(3000);
  const got = await page.evaluate(() => document.querySelector('#nm-buddy svg.atl-layer')?.dataset.atlasLook);
  if (got !== LOOK) throw new Error(`look ${got}, not ${LOOK}`);
  return { browser, page };
}

async function session() {
  const { browser, page } = await setup();
  await page.evaluate((fn) => {
    const sample = new Function(`return (${fn})()`);
    window.__s = [];
    const t0 = performance.now();
    window.__poll = setInterval(() => { const s = sample(); if (s) { s.t = Math.round(performance.now() - t0); window.__s.push(s); } }, 100);
  }, SAMPLE.toString());
  const phases = [];
  const mark = async (name) => phases.push([name, await page.evaluate(() => window.__s.length)]);
  await mark('idle');
  await page.waitForTimeout(90000 * K);
  await mark('typing');
  await page.evaluate(() => revealTab('chat'));
  await page.waitForTimeout(800);
  await page.focus('#chat-input').catch(() => {});
  const end = Date.now() + 30000 * K;
  while (Date.now() < end) { await page.keyboard.type('what did I plan for the week ', { delay: 140 }); await page.keyboard.press('Control+A'); await page.keyboard.press('Backspace'); }
  await page.evaluate(() => document.activeElement?.blur());
  await mark('chat turn');
  // A chat turn as chat-attach.js runs it: thinking, then its end state.
  await page.evaluate(() => setAtlasMood('thinking'));
  await page.waitForTimeout(30000 * K);
  await page.evaluate(() => setAtlasMood('happy', 5000));
  await mark('reading');
  await page.waitForTimeout(60000 * K);
  const samples = await page.evaluate(() => { clearInterval(window.__poll); return window.__s; });
  const out = { look: LOOK, total: summarise(samples, 'total'), phases: [] };
  phases.push(['end', samples.length]);
  for (let i = 0; i < phases.length - 1; i += 1) out.phases.push(summarise(samples.slice(phases[i][1], phases[i + 1][1]), phases[i][0]));
  console.log(JSON.stringify(out));
  await browser.close();
}

async function moods() {
  const { browser, page } = await setup();
  const rows = [];
  const list = await page.evaluate(() => Object.keys(ATLAS_MOODS));
  for (const mood of list) {
    for (const v of ['0', '1', '2']) {
      await page.evaluate(([m, vv]) => { const b = document.getElementById('nm-buddy'); b.dataset.pose = 'stand'; b.dataset.atlasVariant = vv; setAtlasMood(m, 0, { quiet: true }); }, [mood, v]);
      await page.waitForTimeout(1600);
      const s = await page.evaluate((fn) => new Function(`return (${fn})()`)(), SAMPLE.toString());
      rows.push(`${LOOK} ${s.pose} ${mood.padEnd(10)} v${v} curve ${s.curve} brow ${s.brow} (drawn ${s.drawn} turn ${s.browRot} y ${s.browY}) arms ${s.arms.map((a) => `${a.side} ${a.raise.toFixed(0)}/${a.el.toFixed(0)}`).join(' ')} ${grumpy(s).join(',')}`);
    }
  }
  console.log(rows.join('\n'));
  await browser.close();
}

(process.env.CASE === 'moods' ? moods : session)().catch((e) => { console.error(e); process.exit(1); });
