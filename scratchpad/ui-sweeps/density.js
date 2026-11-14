// The density sweep (INBOX 446 (5)): how much of each tab is chrome, how big
// the type and the controls are, how much padding sits around cards, bars
// and rows, and how many note rows fit above the fold. Measured against the
// native references the owner named (Apple Notes, Things, Linear, Obsidian):
// 13px UI text, 28-32px controls, 8-12px card padding, 32-44px list rows.
//
//   SEED=1 BASE=http://127.0.0.1:8790 node density.js   (once per data dir)
//   BASE=... W=1440 H=900 THEME=light node density.js
//   SHOTS=before BASE=... node density.js   (writes out/density-before-*.png)
//
// Every number is computed from the rendered DOM (getComputedStyle and
// getBoundingClientRect), not read off a screenshot.
const { boot } = require('./lib.js');
const fs = require('fs');
const W = +(process.env.W || 1440), H = +(process.env.H || 900);
const OUTDIR = __dirname + '/out';
fs.mkdirSync(OUTDIR, { recursive: true });

async function seed(page) {
  return page.evaluate(async () => {
    const post = async (p, b) => { try { const r = await api(p, { method: 'POST', body: JSON.stringify(b) }); return r.status; } catch (e) { return String(e).slice(0, 60); } };
    const cats = ['Work', 'Personal', 'Reading', 'Ideas', 'Health', 'Home'];
    const topics = ['Weekly review', 'Dentist call', 'Reading list', 'Mindmap idea', 'Meeting with Sam', 'Tomato soup',
      'Sprint retro', 'Passport renewal', 'Kitchen quotes', 'Quarterly numbers', 'Running plan', 'Gift ideas',
      'Book notes: Thinking in Systems', 'Garden layout', 'Tax documents', 'Conference talk outline', 'Bike repair',
      'Holiday plan', 'Podcast list', 'Onboarding checklist'];
    const out = [];
    for (let i = 0; i < 40; i++) {
      const t = topics[i % topics.length] + (i >= topics.length ? ' (follow-up)' : '');
      const content = `# ${t}\n\nA few lines about ${t.toLowerCase()}: what was agreed, what is next, and the one thing to remember before the end of the week.\n\n- first point\n- second point`;
      out.push(await post('/entries', { content, category: cats[i % cats.length], tags: [cats[i % cats.length].toLowerCase(), i % 3 ? 'followup' : 'done'] }));
    }
    out.push(await post('/reminders', { text: 'Send the weekly summary', due_at: new Date(Date.now() + 3600e3).toISOString() }));
    out.push(await post('/reminders', { text: 'Water the plants', due_at: new Date(Date.now() + 86400e3 * 2).toISOString() }));
    out.push(await post('/whiteboard/boards', { name: 'Launch plan', type: 'board' }));
    out.push(await post('/documents', { title: 'Design notes', content: '# Design notes\n\nSurface tiers and the button ramp.' }));
    return out;
  });
}

function measure(page, label, rootSel) {
  return page.evaluate(([label, rootSel]) => {
    const root = (rootSel && document.querySelector(rootSel)) || document.body;
    const vh = innerHeight, vw = innerWidth;
    const vis = (e) => { if (!e.checkVisibility || !e.checkVisibility({ opacityProperty: true, visibilityProperty: true })) return false; const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < vh && r.right > 0 && r.left < vw; };
    const hist = (arr) => { const m = {}; for (const v of arr) m[v] = (m[v] || 0) + 1; return Object.entries(m).sort((a, b) => b[1] - a[1]); };
    const px = (v) => Math.round(parseFloat(v) * 10) / 10;
    // Type: every visible element that owns a non-blank text node.
    const sizes = [];
    for (const e of root.querySelectorAll('*')) {
      if (!vis(e)) continue;
      if (![...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
      sizes.push(px(getComputedStyle(e).fontSize));
    }
    // Controls: buttons, selects, text inputs, tabs, summaries drawn as buttons.
    const ctl = [];
    for (const e of root.querySelectorAll('button, select, input[type=text], input[type=search], input:not([type]), summary.ghost, summary.small, [role=tab]')) {
      if (!vis(e) || e.closest('#nm-buddy')) continue;
      ctl.push(Math.round(e.getBoundingClientRect().height));
    }
    // Cards, bars, rows: padding and gap.
    const pad = (sel) => { const r = []; for (const e of root.querySelectorAll(sel)) { if (!vis(e)) continue; const c = getComputedStyle(e); r.push(`${px(c.paddingTop)}/${px(c.paddingLeft)} g${px(c.rowGap) || 0}`); } return hist(r).slice(0, 4); };
    const rowsH = []; for (const e of root.querySelectorAll('.entry-list > li, .reminder-list > li, .library-row, .timeline-item, .row-list > li, .settings-row, .setting-row')) { if (vis(e)) rowsH.push(Math.round(e.getBoundingClientRect().height)); }
    // Chrome: the top bar plus every visible dock / sub-tab strip at the top
    // of the active page, as a share of the viewport height.
    const tb = document.getElementById('top-bar');
    const tbH = tb && vis(tb) ? Math.round(tb.getBoundingClientRect().height) : 0;
    const page = document.querySelector('.tab-page:not(.hidden)');
    let chromeBottom = tbH;
    if (page) for (const e of page.querySelectorAll('.dock, [role=tablist], .seg.edge-fade, .library-toolbar, .graph-toolbar')) {
      if (!vis(e)) continue; const r = e.getBoundingClientRect();
      if (r.top < chromeBottom + 48 && r.bottom > chromeBottom) chromeBottom = Math.round(r.bottom);
    }
    // Note rows fully above the fold (the Notes list only).
    let rowsAbove = null;
    const list = document.getElementById('entry-list');
    if (list && vis(list)) rowsAbove = [...list.children].filter((li) => { const r = li.getBoundingClientRect(); return r.height > 0 && r.top >= 0 && r.bottom <= vh; }).length;
    // Radii and shadows across the visible page.
    const radii = new Set(), shadows = new Set();
    for (const e of root.querySelectorAll('*')) {
      if (!vis(e)) continue; const c = getComputedStyle(e);
      if (c.borderTopLeftRadius !== '0px') radii.add(c.borderTopLeftRadius);
      if (c.boxShadow !== 'none' && !e.matches(':focus')) shadows.add(c.boxShadow);
    }
    // Alignment (L-ui-modernisation-53, the owner's "very messy"): the distinct left edges, to the pixel, of
    // the blocks of text in the active page. Every type size and radius here is a token, so variety
    // alone did not say which surface looks messy; ragged starts do (CARP alignment).
    const edges = new Map();
    if (page) for (const e of page.querySelectorAll('*')) {
      if (!vis(e) || ![...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
      // Right-aligned text (the end of a space-between row, or text-align end) lines up on its right edge.
      const ps = e.parentElement && getComputedStyle(e.parentElement);
      if (/right|end/.test(getComputedStyle(e).textAlign) || (ps && /flex/.test(ps.display) && ps.justifyContent === 'space-between' && e === e.parentElement.lastElementChild && e !== e.parentElement.firstElementChild)) continue;
      const x = Math.round(e.getBoundingClientRect().left);
      edges.set(x, (edges.get(x) || 0) + 1);
    }
    const edgeList = [...edges].sort((a, b) => b[1] - a[1]);
    // Near misses: two starts 1 to 4px apart, which read as a mistake where a shared edge was meant.
    const xs = [...edges.keys()].sort((a, b) => a - b);
    const near = xs.filter((x, i) => i && x - xs[i - 1] <= 4).map((x, i) => `${xs[xs.indexOf(x) - 1]}/${x}`);
    const firstContent = page ? (() => { const r = page.getBoundingClientRect(); return Math.round(r.top + parseFloat(getComputedStyle(page).paddingTop)); })() : null;
    return {
      label, type: hist(sizes).slice(0, 8), typeDistinct: new Set(sizes).size,
      controls: hist(ctl).slice(0, 8), controlsN: ctl.length,
      cards: pad('.card, .tile, .surface-card, .dash-tile'),
      bars: pad('.dock, .library-toolbar, .graph-toolbar, .chat-dock-controls'),
      rows: hist(rowsH).slice(0, 5),
      topBar: tbH, chromeBottom, chromePct: Math.round((chromeBottom / vh) * 1000) / 10,
      firstContent, rowsAbove, radii: radii.size, shadows: shadows.size,
      edges: edges.size, near, edgeList: edgeList.slice(0, 12), radiiList: [...radii].slice(0, 14), shadowList: [...shadows].map((s) => s.slice(0, 70)).slice(0, 12),
    };
  }, [label, rootSel]);
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: H }, ...(W < 600 ? { hasTouch: true, isMobile: true } : {}) });
  if (process.env.SEED) { console.log('seed', JSON.stringify(await seed(page))); await browser.close(); return; }
  const tab = async (n) => { await page.evaluate((n) => switchTab(n), n); await page.waitForTimeout(1100); };
  const click = async (sel) => { await page.evaluate((s) => document.querySelector(s)?.click(), sel); await page.waitForTimeout(900); };
  const results = [];
  const shot = async (name) => { if (process.env.SHOTS) await page.screenshot({ path: `${OUTDIR}/density-${process.env.SHOTS}-${name}-${process.env.THEME || 'light'}-${W}.png` }); };
  await tab('dashboard'); results.push(await measure(page, 'dashboard')); await shot('dashboard');
  await tab('notes'); await click('#notes-subtabs [data-section="browse"]'); results.push(await measure(page, 'notes/browse')); await shot('notes');
  if (process.env.SHOTS) {
    await click('#notes-subtabs [data-section="capture"]'); await shot('capture');
    await click('#notes-subtabs [data-section="browse"]');
    for (const t of ['chat', 'graph', 'timeline']) { await tab(t); await shot(t); }
    await tab('library'); await shot('library');
    await tab('reminders'); await shot('reminders');
    await page.evaluate(() => document.getElementById('settings-btn')?.click()); await page.waitForTimeout(900); await shot('settings');
    return browser.close();
  }
  await click('#notes-subtabs [data-section="capture"]'); results.push(await measure(page, 'notes/capture'));
  await click('#notes-subtabs [data-section="ask"]'); results.push(await measure(page, 'notes/ask'));
  await click('#notes-subtabs [data-section="browse"]');
  await tab('chat'); results.push(await measure(page, 'chat'));
  await tab('graph'); await page.waitForTimeout(1200); results.push(await measure(page, 'graph'));
  await tab('library');
  for (const t of ['library-view-documents', 'library-view-docs', 'library-view-whiteboard']) { await click(`#tab-library [data-target="${t}"]`); results.push(await measure(page, 'library/' + t.replace('library-view-', ''))); }
  await click('#tab-library [data-media-kind="images"]'); results.push(await measure(page, 'library/images'));
  await click('#tab-library [data-target="library-view-documents"]');
  await tab('timeline'); results.push(await measure(page, 'timeline'));
  await tab('reminders'); results.push(await measure(page, 'reminders'));
  await page.evaluate(() => document.getElementById('settings-btn')?.click()); await page.waitForTimeout(900);
  results.push(await measure(page, 'settings', '#settings-modal'));
  if (process.env.JSON) fs.writeFileSync(process.env.JSON, JSON.stringify(results, null, 1));
  for (const r of results) {
    console.log(`\n== ${r.label} @${W}x${H}  topbar ${r.topBar}px  chrome ${r.chromeBottom}px (${r.chromePct}%)  first content y=${r.firstContent}  rows above fold ${r.rowsAbove}  radii ${r.radii}  shadows ${r.shadows}  type sizes ${r.typeDistinct}  left edges ${r.edges}  near misses ${r.near.length} ${r.near.join(' ')}`);
    console.log('  type    ', JSON.stringify(r.type));
    console.log('  controls', JSON.stringify(r.controls), 'n=' + r.controlsN);
    console.log('  cards   ', JSON.stringify(r.cards), ' bars', JSON.stringify(r.bars), ' rows', JSON.stringify(r.rows));
    if (process.env.VERBOSE) console.log('  edges', JSON.stringify(r.edgeList), '\n  radii', r.radiiList.join(' | '), '\n  shadows', r.shadowList.join(' | '));
  }
  await browser.close();
})().catch((e) => { console.error('SWEEP_ERROR', e.message); process.exit(1); });
