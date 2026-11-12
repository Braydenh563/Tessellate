// Every inline "working" indicator in the app, measured (INBOX 441 (2): "make
// sure all these loading spinners are consistent across the app").
//
// It drives the app's own builders and, where one can be held open, the real
// flow (a note's "Atlas is reading…" is `reevaluateEntry` with its API call
// held back, the way skeletons-style sweeps hold a response). For each
// indicator it reads the computed size (in em of the text beside it, because
// that is what has to agree), stroke, colour, animation name and duration,
// prints one signature per indicator, and then the DISTINCT signatures. One
// recipe means one signature (plus the filled-button colour override).
//
//   BASE=http://127.0.0.1:8784 node scratchpad/ui-sweeps/spinners.js
//   REDUCED=1 ...   the same under prefers-reduced-motion with progress
//                   motion set to "auto" (so the OS setting is honoured)
//
// Exits 1 if there is more than one rotating signature or any indicator
// stands still.
const { boot } = require('./lib.js');

const REDUCED = !!process.env.REDUCED;

(async () => {
  const { browser, page } = await boot({
    viewport: { width: 1440, height: 900 },
    ...(REDUCED ? { reducedMotion: 'reduce' } : {}),
  });
  if (REDUCED) {
    await page.evaluate(() => {
      localStorage.setItem('progress-motion', 'auto');
      document.documentElement.dataset.progressMotion = 'auto';
    });
  }
  const found = [];
  // `scope` is a selector for where to look; the indicators under it are the
  // ring (`.spinner`), the old glyph (`.ph-circle-notch`), the tension line's
  // pulsing text and the reply dots. A comma list built per scope, so one
  // scope never picks up another's.
  const take = async (where, scope) => {
    const selector = ['.spinner', '.ph-circle-notch', '.is-busy', '.typing-dots']
      .map((s) => `${scope} ${s}, ${scope}${s}`).join(', ');
    const rows = await page.evaluate(({ where, selector }) => {
      const out = [];
      const round = (n) => Math.round(n * 100) / 100;
      for (const el of document.querySelectorAll(selector)) {
        const r = el.getBoundingClientRect();
        if (!r.width && !r.height) continue;
        const dot = el.classList.contains('typing-dots') ? el.querySelector('.typing-dot') : null;
        const cs = getComputedStyle(dot || el);
        const host = el.parentElement ? parseFloat(getComputedStyle(el.parentElement).fontSize) : 16;
        const isRing = el.classList.contains('spinner');
        const isGlyph = el.classList.contains('ph-circle-notch');
        // The ring's visible arc is the right border; the glyph is its colour.
        const colour = isRing ? cs.borderRightColor : cs.color;
        const before = isRing ? getComputedStyle(el, '::before').content : '';
        out.push({
          where,
          kind: isRing ? 'ring' : isGlyph ? 'glyph' : el.classList.contains('typing-dots') ? 'reply-dots' : 'text-pulse',
          // A ring is as tall as its layout box (the computed height: offsetHeight rounds to whole pixels): the bounding
          // rect of a ring mid-turn is the rotated square, up to 1.41x bigger.
          // A glyph is as big as its font.
          em: round((isGlyph ? parseFloat(cs.fontSize) / host : parseFloat(cs.height) / parseFloat(cs.fontSize))),
          square: isRing ? Math.abs(el.offsetWidth - el.offsetHeight) < 0.5 : true,
          stroke: isRing ? cs.borderRightWidth : '-',
          colour,
          anim: cs.animationName,
          dur: cs.animationName === 'none' ? '-' : cs.animationDuration,
          ellipsisFallback: before && before !== 'none' && before !== 'normal' ? before : '',
        });
      }
      return out;
    }, { where, selector });
    for (const row of rows) found.push(row);
    return rows.length;
  };

  // A note to work on.
  const saved = await page.evaluate(async () => {
    const made = await apiJson('/entries', {
      method: 'POST',
      body: JSON.stringify({ content: 'spinner sweep note', defer_filing: true }),
    });
    return made;
  });

  // 1. "Atlas is reading…" on a card: the real handler, its API call held.
  let release;
  const held = new Promise((r) => (release = r));
  await page.route(/\/entries\/\d+\/reevaluate/, async (route) => {
    await held;
    await route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"held"}' });
  });
  await page.evaluate(() => switchTab('notes'));
  await page.waitForTimeout(800);
  await page.evaluate(async (id) => {
    await loadEntries();
    const entry = (typeof entriesCache !== 'undefined' ? entriesCache : []).find?.((e) => e.id === id);
    window.__sweepEntry = entry || { id };
  }, saved.id);
  await page.evaluate(() => { reevaluateEntry(window.__sweepEntry); });
  await page.waitForTimeout(600);
  const n1 = await take('card: Atlas is reading', `li[data-id="${saved.id}"]`);
  release();
  await page.waitForTimeout(500);

  // 2. "Filing…" on a card, the real card builder with a pending note.
  await page.evaluate((saved) => {
    const host = document.createElement('ul');
    host.className = 'entry-list';
    host.id = 'sweep-host';
    host.style.cssText = 'position:fixed;top:60px;left:40px;width:640px;z-index:99999;background:var(--bg)';
    host.appendChild(entryItem({ ...saved, filing_state: 'pending' }, { actions: true }));
    document.body.appendChild(host);
  }, saved);
  await page.waitForTimeout(400);
  await take('card: Filing', '#sweep-host');
  await page.evaluate(() => document.getElementById('sweep-host').remove());

  // 3. The agent palette: "Working…" and "Saving…".
  await page.evaluate(() => toggleAgentPalette());
  await page.waitForTimeout(500);
  await page.evaluate(() => cmdPaletteBusy(true));
  await page.waitForTimeout(300);
  await take('palette: Working', '#command-palette-status');
  await page.evaluate(() => cmdPaletteBusy(false));
  let releaseSave;
  const heldSave = new Promise((r) => (releaseSave = r));
  await page.route(/\/conversations$/, async (route) => {
    await heldSave;
    await route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"held"}' });
  });
  await page.evaluate(() => {
    cmdPaletteTurns.push({ question: 'q', answer: 'a' });
    cmdPaletteSaveAsChat();
  });
  await page.waitForTimeout(300);
  await take('palette: Saving', '#command-palette-status');
  releaseSave();
  await page.waitForTimeout(300);
  await page.evaluate(() => { cmdPaletteTurns.length = 0; toggleAgentPalette(); });
  await page.waitForTimeout(300);

  // 4. The activity panel's run state and a step group's summary, built by
  //    the same `setLabel` the real renderers call.
  await page.evaluate(() => {
    const host = document.createElement('div');
    host.id = 'sweep-labels';
    host.style.cssText = 'position:fixed;top:40px;left:40px;width:420px;z-index:99999;background:var(--bg);padding:8px;font-size:0.8rem';
    const a = document.createElement('div'); a.id = 'sweep-run';
    setLabel(a, 'ph:spin Running');
    host.appendChild(a);
    document.body.appendChild(host);
  });
  await take('activity: run state Running', '#sweep-run');
  await page.evaluate(() => document.getElementById('sweep-labels').remove());

  // 6. A long job's toast.
  await page.evaluate(() => { window.__toast = toastProgress('Reading text…'); });
  await page.waitForTimeout(300);
  await take('toast: Reading text', '.toast');
  await page.evaluate(() => window.__toast.done?.('Done'));

  // 7. A button that is busy, the way the app marks one.
  await page.evaluate(() => {
    const host = document.createElement('div');
    host.id = 'sweep-buttons';
    host.style.cssText = 'position:fixed;top:40px;left:40px;width:520px;z-index:99999;background:var(--bg);padding:8px;display:flex;gap:12px';
    for (const cls of ['ghost', 'accent', 'ghost danger']) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = cls;
      b.textContent = 'Apply';
      host.appendChild(b);
      if (typeof setBusy === 'function') setBusy(b, true, 'Working…');
      else { b.disabled = true; b.setAttribute('aria-busy', 'true'); }
    }
    document.body.appendChild(host);
  });
  await page.waitForTimeout(300);
  const buttons = await page.evaluate(() => [...document.querySelectorAll('#sweep-buttons button')].map((b) => ({
    cls: b.className, busy: b.getAttribute('aria-busy'), disabled: b.disabled,
    spinner: !!b.querySelector('.spinner'), text: b.textContent, cursor: getComputedStyle(b).cursor,
  })));
  await take('button: busy', '#sweep-buttons');

  // 8. The reply indicator in a chat bubble (a different, named recipe).
  const reply = await page.evaluate(() => {
    const host = document.createElement('div');
    host.id = 'sweep-reply';
    host.style.cssText = 'position:fixed;top:140px;left:40px;width:420px;z-index:99999;background:var(--bg);padding:8px';
    host.appendChild(typingDots('Thinking…'));
    document.body.appendChild(host);
    const dot = host.querySelector('.typing-dot');
    return dot ? getComputedStyle(dot).animationName : 'stepped word';
  });
  await page.evaluate(() => document.getElementById('sweep-reply')?.remove());

  // Report.
  const sig = (r) => `${r.kind} ${r.em}em ${r.square ? 'square' : 'NOT-SQUARE'} stroke=${r.stroke} colour=${r.colour} anim=${r.anim} ${r.dur}${r.ellipsisFallback ? ' fallback=' + r.ellipsisFallback : ''}`;
  console.log(`\n--- ${found.length} indicators found${REDUCED ? ' (reduced motion, progress motion auto)' : ''}`);
  for (const r of found) console.log(`${r.where.padEnd(32)} ${sig(r)}`);
  console.log('\nbuttons:', JSON.stringify(buttons));
  console.log('reply indicator dot animation (own recipe):', reply);
  const distinct = [...new Set(found.map(sig))];
  console.log(`\n=== ${distinct.length} distinct spinner signatures`);
  for (const s of distinct) console.log('  ' + s);
  const rotating = new Set(found.filter((r) => /turn|spin|notch/.test(r.anim)).map((r) => `${r.anim} ${r.dur}`));
  const still = found.filter((r) => r.anim === 'none');
  console.log(`motion (animation, duration) pairs: ${[...new Set(found.map((r) => `${r.anim} ${r.dur}`))].join(' | ')}`);
  if (still.length) console.log('STANDING STILL:', still.map((r) => r.where).join(', '));
  // The recipe: ONE ring shape, size, stroke, animation and duration. Colour
  // may differ in exactly the two documented ways (a filled button's text
  // colour, a danger button's red), so it is left out of the shape.
  const shapes = [...new Set(found.map((r) => `${r.kind} ${r.em}em ${r.square} ${r.stroke} ${r.anim} ${r.dur}`))];
  const colours = [...new Set(found.map((r) => r.colour))];
  console.log(`\n${shapes.length} distinct shape(s), ${colours.length} colour(s): ${shapes.join(' ; ')}`);
  await browser.close();
  const wantAnim = REDUCED ? 'spinner-pulse' : 'spinner-turn';
  const bad = shapes.length !== 1 || !found.every((r) => r.kind === 'ring' && r.anim === wantAnim) || still.length > 0 || colours.length > 3;
  console.log(bad ? 'FAIL: more than one recipe on screen' : 'PASS: one ring recipe');
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
