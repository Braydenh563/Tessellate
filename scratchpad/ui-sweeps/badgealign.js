// INBOX 503: every badge, chip, pill and tag that holds an icon and words,
// measured by ink at 3x, never by box (a Phosphor glyph is drawn high in its
// own em square, and a flex row centres boxes). Per badge:
//   dy     icon ink centre minus the words' cap-height centre (+ is low): the
//          label recipe's target (DESIGN.md, INBOX 592; the x-height band
//          INBOX 503 measured against is retired), as iconalign.js reads it
//   gap    box gap between icon and words, and the ink gap beside it
//   padL/R ink-to-edge at each end (symmetry is read from what is painted)
// Also the Timeline rail (and any other icon-in-a-circle): the icon's ink
// centre against its circle's centre, x and y.
//   BASE=http://127.0.0.1:8883 W=1440 THEME=light node badgealign.js
//   OUTLIERS=1 prints only the badges past the limits; FAMILY=1 groups by
//   class set and prints min/max per family; VIEWS=timeline,notes narrows.
const { boot } = require('./lib.js');
const { execFileSync } = require('child_process');
const fs = require('fs');
const W = Number(process.env.W || 1440);
const THEME = process.env.THEME || 'light';
const phone = W < 600;
const PY = process.env.PY || require('path').resolve(__dirname, '..', '..', '.venv', 'bin', 'python');
const LIM = Number(process.env.LIM || 0.5);
const PHASES = (process.env.PHASES || '0').split(',').map(Number);

const TABS = ['dashboard', 'notes', 'chat', 'graph', 'reminders', 'timeline'];
const LIB = ['contents', 'docs', 'documents', 'links', 'media', 'skills', 'whiteboard'];
const SETTINGS = ['models', 'extras', 'websearch', 'tasks', 'skills', 'templates', 'personas', 'tools', 'learned',
  'about', 'account', 'appearance', 'preferences', 'privacy', 'data', 'memory', 'logs', 'searchindex', 'shortcuts', 'general'];
const VIEWS = [];
for (const t of TABS) VIEWS.push([t, [`closeSettingsModal&&closeSettingsModal()`, `switchTab('${t}')`]]);
for (const s of LIB) VIEWS.push([`library/${s}`, [`closeSettingsModal&&closeSettingsModal()`, `switchTab('library')`,
  `document.querySelector('#library-subtabs [data-target="library-view-${s}"]')?.click()`]]);
for (const s of SETTINGS) VIEWS.push([`settings/${s}`, [`openSettingsModal('${s}')`,
  `document.querySelectorAll('#settings-modal details').forEach((d)=>d.open=true)`]]);

// Runs in the page. Returns candidates (tagged data-ba) with a family key.
function collect(sel0) {
  const vis = (e) => e.checkVisibility && e.checkVisibility({ visibilityProperty: true, opacityProperty: true });
  const ICON = 'i.ph, i[class*="ph-"], svg, .spinner';
  const chipClass = /(^|\s)(chip|badge|pill|tag|item-label|extras-installed|dock-chip|status-key)(\s|$)|badge|pill/;
  const out = [];
  let n = 0;
  document.querySelectorAll('*').forEach((el) => {
    if (el.dataset.ba) { out.push(el); return; }
    const s = getComputedStyle(el);
    if (!/flex/.test(s.display) && !/inline-block|inline-grid/.test(s.display)) return;
    const r = el.getBoundingClientRect();
    if (r.height < 12 || r.height > 44 || r.width < 18 || r.width > 380) return;
    const named = chipClass.test(typeof el.className === 'string' ? el.className : '');
    const tag = el.tagName;
    if (!named) {
      // An unnamed inline-flex with an icon and words counts only when it
      // reads as a badge: not a button, link, input row or a menu item.
      if (/^(BUTTON|A|LABEL|SUMMARY|LI|INPUT|SELECT)$/.test(tag)) return;
      if (!/inline-flex/.test(s.display)) return;
      if (!(parseFloat(s.borderTopWidth) || s.backgroundColor !== 'rgba(0, 0, 0, 0)')) return;
    }
    const icons = [...el.children].filter((c) => c.matches(ICON));
    if (!icons.length) return;
    if (!vis(el)) return;
    const txt = (el.textContent || '').trim();
    if (!txt || txt.length > 48) return;
    // Innermost only: skip a wrapper whose child is itself a candidate.
    el.dataset.ba = String(++n);
    out.push(el);
  });
  return out.filter((el) => vis(el)).map((el) => {
    const ic = [...el.children].find((c) => c.matches(ICON));
    return {
      id: el.dataset.ba,
      key: (typeof el.className === 'string' ? el.className.replace(/\s+/g, '.') : '') + '|' + (ic.getAttribute('class') || ic.tagName).replace(/\s+/g, '.'),
      text: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 28),
    };
  });
}

// Runs in the page: badges that sit on one row of one parent must share one
// height and one centre line (and one text baseline). Height and centre count
// only badges that are painted (a fill, an edge); an unpainted chip is words,
// and only its text line is compared. Every visible badge-like
// element counts, with or without an icon: a plain category chip sits beside a
// sparkle chip in the same row and is measured against it.
function rowStats() {
  const sel = '.chip, [class*="badge"], .pill, [class*="-pill"], .item-label, .extras-installed, .tag';
  const els = [...document.querySelectorAll(sel)].filter((e) => e.checkVisibility && e.checkVisibility({ visibilityProperty: true, opacityProperty: true }) && e.getBoundingClientRect().width > 8 && !/^(BUTTON|A|INPUT)$/.test(e.tagName) && !e.closest('button, a, summary'));
  const byParent = new Map();
  for (const e of els) { const p = e.parentElement; if (!byParent.has(p)) byParent.set(p, []); byParent.get(p).push(e); }
  const out = [];
  const textMid = (el) => { const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n; while ((n = w.nextNode())) { if (n.textContent.trim()) { const r = document.createRange(); r.selectNodeContents(n); const b = r.getBoundingClientRect(); if (b.width > 1) return (b.top + b.bottom) / 2; } } return null; };
  for (const [p, list] of byParent) {
    if (list.length < 2) continue;
    // Rows: clusters whose vertical spans overlap by more than half a height.
    const sorted = list.map((e) => ({ e, b: e.getBoundingClientRect() })).sort((a, b) => a.b.top - b.b.top);
    let row = [];
    const flush = () => {
      if (row.length >= 2) {
        const painted = row.filter((x) => { const c = getComputedStyle(x.e); return /rgba?\((?!0, 0, 0, 0\))/.test(c.backgroundColor) || parseFloat(c.borderTopWidth) > 0 || c.boxShadow !== 'none'; });
        const hs = (painted.length > 1 ? painted : row).map((x) => x.b.height), cs = (painted.length > 1 ? painted : row).map((x) => (x.b.top + x.b.bottom) / 2), ts = row.map((x) => textMid(x.e)).filter((v) => v !== null);
        const sp = (a) => Math.round((Math.max(...a) - Math.min(...a)) * 100) / 100;
        out.push({ parent: (typeof p.className === 'string' ? p.className.replace(/\s+/g, '.') : p.tagName).slice(0, 40), n: row.length, h: sp(hs), c: sp(cs), t: ts.length > 1 ? sp(ts) : 0, hs: [...new Set(hs.map((h) => Math.round(h * 10) / 10))], names: row.map((x) => (typeof x.e.className === 'string' ? x.e.className.replace(/\s+/g, '.') : '').slice(0, 30)).join(' ') });
      }
      row = [];
    };
    for (const x of sorted) {
      if (row.length && x.b.top > row[0].b.top + row[0].b.height / 2) flush();
      row.push(x);
    }
    flush();
  }
  return out;
}

// Runs in the page: boxes for the ids currently inside the viewport.
function measure(ids) {
  const out = [];
  const box = (e) => { const q = e.getBoundingClientRect(); return { left: q.left, right: q.right, top: q.top, bottom: q.bottom }; };
  const ICON = 'i.ph, i[class*="ph-"], svg, .spinner';
  for (const id of ids) {
    const el = document.querySelector(`[data-ba="${id}"]`);
    if (!el || !el.isConnected) continue;
    const b = el.getBoundingClientRect();
    if (b.top < 4 || b.bottom > innerHeight - 4 || b.left < 2 || b.right > innerWidth - 2) continue;
    // Under a dialog or another surface, it is not what a person sees.
    const mid = document.elementFromPoint((b.left + b.right) / 2, (b.top + b.bottom) / 2);
    if (!mid || !(el.contains(mid) || mid.contains(el))) continue;
    const icons = [...el.children].filter((c) => c.matches(ICON));
    const icon = icons[0];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let r = null, n;
    while ((n = walker.nextNode())) {
      if (!n.textContent.trim() || icons.some((i) => i.contains(n))) continue;
      const range = document.createRange(); range.selectNodeContents(n);
      const rr = range.getBoundingClientRect();
      if (rr.width < 2) continue;
      r = r ? { left: Math.min(r.left, rr.left), right: Math.max(r.right, rr.right), top: Math.min(r.top, rr.top), bottom: Math.max(r.bottom, rr.bottom) } : { left: rr.left, right: rr.right, top: rr.top, bottom: rr.bottom };
    }
    if (!r) continue;
    const s = getComputedStyle(el), is = getComputedStyle(icon);
    const cv = document.createElement('canvas').getContext('2d');
    const tp = getComputedStyle(el.querySelector(':scope > :not(i):not(svg):not(.spinner)') || el);
    cv.font = `${tp.fontStyle} ${tp.fontWeight} ${tp.fontSize} ${tp.fontFamily}`;
    const cap = cv.measureText('H').actualBoundingBoxAscent;
    const lead = icon.getBoundingClientRect().left <= r.left;
    const gapBox = lead ? r.left - icon.getBoundingClientRect().right : icon.getBoundingClientRect().left - r.right;
    out.push({
      id, par: (() => { const p = el.parentElement; if (!p.dataset.bp) p.dataset.bp = String(++window.__bp || (window.__bp = 1)); return p.dataset.bp; })(), cap, box: box(el), icon: box(icon), text: r, extra: icons.slice(1).map(box),
      gapBox: Math.round(gapBox * 100) / 100,
      css: `gap ${s.columnGap} ml ${is.marginLeft} mr ${is.marginRight} pad ${s.paddingLeft}/${s.paddingRight} h ${Math.round(b.height * 10) / 10}`,
      lead,
    });
  }
  return out;
}


// Scrolling to a fractional offset moves text and icons by different
// roundings (each flex item paints on its own), which reads as jitter in the
// numbers that is not in the CSS. Whole-pixel scroll positions only.
function scrollTo(sel) {
  const el = document.querySelector(sel);
  if (!el) return;
  el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
  for (let p = el.parentElement; p; p = p.parentElement) {
    if (p.scrollTop % 1) p.scrollTop = Math.round(p.scrollTop);
    if (p.scrollLeft % 1) p.scrollLeft = Math.round(p.scrollLeft);
  }
  if (document.scrollingElement && document.scrollingElement.scrollTop % 1) document.scrollingElement.scrollTop = Math.round(document.scrollingElement.scrollTop);
}

// A fractional shift of everything below the top of the nearest scrolling
// ancestor: its first child gains `ph` px of margin. (A fractional scrollTop is
// snapped to whole pixels, so it moves nothing.) The previous shift is undone.
function shiftScroll(sel, ph) {
  document.querySelectorAll('[data-ba-shift]').forEach((e) => { e.style.marginTop = e.dataset.baShift; delete e.dataset.baShift; });
  if (!ph) return;
  const el = document.querySelector(sel);
  for (let p = el && el.parentElement; p; p = p.parentElement) {
    if (p.scrollHeight > p.clientHeight + 1 && /auto|scroll/.test(getComputedStyle(p).overflowY) && p.firstElementChild) {
      const f = p.firstElementChild;
      f.dataset.baShift = f.style.marginTop;
      f.style.marginTop = `${(parseFloat(getComputedStyle(f).marginTop) || 0) + ph}px`;
      return;
    }
  }
}

// Icons in a circle: Timeline marks and any round icon holder. `ids` null
// lists and tags the candidates; a list of ids returns their boxes for the
// ones now inside the viewport.
function marksIn(ids) {
  const ICON = 'i.ph, i[class*="ph-"], svg';
  const q = (e) => { const b = e.getBoundingClientRect(); return { left: b.left, right: b.right, top: b.top, bottom: b.bottom }; };
  if (ids) {
    const out = [];
    for (const id of ids) {
      const el = document.querySelector(`[data-bm="${id}"]`);
      if (!el || !el.isConnected) continue;
      const r = el.getBoundingClientRect();
      if (r.top < 4 || r.bottom > innerHeight - 4 || r.left < 2 || r.right > innerWidth - 2) continue;
      const ic = [...el.children].find((c) => c.matches(ICON));
      out.push({ id: 'm' + id, box: q(el), icon: q(ic), text: null });
    }
    return out;
  }
  const list = [];
  document.querySelectorAll('span, div, a, button, i').forEach((el) => {
    if (!el.checkVisibility || !el.checkVisibility()) return;
    const r = el.getBoundingClientRect();
    if (r.width < 14 || r.width > 64 || Math.abs(r.width - r.height) > 1) return;
    if (el.textContent.trim() || el.children.length !== 1) return;
    const ic = el.children[0];
    if (!ic.matches(ICON)) return;
    const cs = getComputedStyle(el);
    const rad = parseFloat(cs.borderTopLeftRadius);
    if (!(rad >= r.width / 2 - 1 || cs.borderTopLeftRadius.includes('%'))) return;
    el.dataset.bm = String(list.length + 1);
    list.push({ id: el.dataset.bm, key: (typeof el.className === 'string' ? el.className.replace(/\s+/g, '.') : el.tagName) + '|' + (ic.getAttribute('class') || ic.tagName).replace(/\s+/g, '.'), size: Math.round(r.width) });
  });
  return list;
}

(async () => {
  const { browser, page, OUT } = await boot({ viewport: { width: W, height: 900 }, deviceScaleFactor: Number(process.env.SCALE || 3), ...(phone ? { hasTouch: true, isMobile: true } : {}) });
  // Another font, or a stylesheet tried before it is edited: the app's CSP
  // refuses an injected <style>, so `lib.js`'s OVERRIDE_CSS serves a copy of
  // 08-consistency.css with the candidate appended (try.sh builds it).
  const only = process.env.VIEWS ? process.env.VIEWS.split(',') : null;
  const rows = [];
  const marks = [];
  const rowsOut = [];
  for (const [name, steps] of VIEWS) {
    if (only && !only.some((o) => name.startsWith(o))) continue;
    for (const step of steps) { await page.evaluate((c) => { try { (0, eval)(c); } catch (e) {} }, step); await page.waitForTimeout(700); }
    await page.waitForTimeout(name.startsWith('settings') ? 2500 : 500);
    for (const rs of await page.evaluate(`(${rowStats.toString()})()`)) rowsOut.push({ view: name, ...rs });
    let cands = await page.evaluate(`(${collect.toString()})()`);
    if (!cands.length && !name.startsWith('graph') && !name.startsWith('chat')) {
      // A tab that was still drawing: look once more before calling it empty.
      await page.waitForTimeout(2000);
      cands = await page.evaluate(`(${collect.toString()})()`);
    }
    if (process.env.DEBUG) console.log(name, cands.length);
    // Up to 4 of each family, then scroll them into view in turn.
    const per = new Map();
    const pick = [];
    for (const c of cands) { const k = per.get(c.key) || 0; if (k < 4) { per.set(c.key, k + 1); pick.push(c); } }
    const done = new Set();
    let steps2 = 0;
    for (const c of pick) {
      if (done.has(c.id) || steps2++ > 30) continue;
      await page.evaluate(`(${scrollTo.toString()})('[data-ba="${c.id}"]')`);
      await page.waitForTimeout(250);
      const ids = pick.filter((p) => !done.has(p.id)).map((p) => p.id);
      let items = await page.evaluate(`(${measure.toString()})(${JSON.stringify(ids)})`);
      if (!items.length) { done.add(c.id); continue; }
      const got = items.map((i) => i.id);
      const mk = [];
      // PHASES="0,0.33,0.67": the same badges again at fractional scroll
      // offsets. Text paints on a whole CSS pixel and a box on the device's,
      // so one position can be up to 0.5px off either way and say nothing
      // about the CSS; the mean over the phases does (badgesum.js).
      for (const ph of PHASES) {
        if (ph) {
          await page.evaluate(`(${shiftScroll.toString()})('[data-ba="${c.id}"]', ${ph})`);
          await page.waitForTimeout(150);
          items = await page.evaluate(`(${measure.toString()})(${JSON.stringify(got)})`);
          if (!items.length) continue;
        }
        const shot = `${OUT}/ba-${W}-${THEME}.png`;
        await page.screenshot({ path: shot });
        const jf = `${OUT}/ba-items.json`;
        fs.writeFileSync(jf, JSON.stringify([...items, ...mk]));
        const res = JSON.parse(execFileSync(PY, [__dirname + '/badgealign.py', shot, jf], { maxBuffer: 1 << 26 }).toString());
        for (const it of items) {
          const m = res.find((r) => r.id === it.id) || {};
          const meta = pick.find((p) => p.id === it.id);
          rows.push({ view: name, id: it.id, phase: ph, key: meta.key, text: meta.text, css: it.css, gapBox: it.gapBox, lead: it.lead, par: name + ':' + it.par, top: it.box.top, bottom: it.box.bottom, ...m });
        }
      }
      for (const id of got) done.add(id);
      done.add(c.id);
    }
    // Icons in circles, the same way.
    const mc = await page.evaluate(`(${marksIn.toString()})(null)`);
    if (process.env.DEBUG) console.log(name, 'marks', mc.length);
    const mper = new Map();
    const mpick = [];
    for (const c of mc) { const k = mper.get(c.key) || 0; if (k < 3) { mper.set(c.key, k + 1); mpick.push(c); } }
    const mdone = new Set();
    for (const c of mpick) {
      if (mdone.has(c.id)) continue;
      await page.evaluate(`(${scrollTo.toString()})('[data-bm="${c.id}"]')`);
      await page.waitForTimeout(250);
      const ids = mpick.filter((p) => !mdone.has(p.id)).map((p) => p.id);
      const mk = await page.evaluate(`(${marksIn.toString()})(${JSON.stringify(ids)})`);
      mdone.add(c.id);
      if (!mk.length) continue;
      const shot = `${OUT}/ba-${W}-${THEME}.png`;
      await page.screenshot({ path: shot });
      const jf = `${OUT}/ba-items.json`;
      fs.writeFileSync(jf, JSON.stringify(mk));
      const res = JSON.parse(execFileSync(PY, [__dirname + '/badgealign.py', shot, jf], { maxBuffer: 1 << 26 }).toString());
      for (const it of mk) {
        const bare = it.id.slice(1);
        mdone.add(bare);
        const m = res.find((r) => r.id === it.id) || {};
        const meta = mpick.find((p) => p.id === bare);
        marks.push({ view: name, key: meta.key, size: meta.size, top: Math.round(it.box.top * 100) / 100, ...m });
      }
    }
  }
  await browser.close();
  // Print.
  const fam = new Map();
  for (const r of rows) { const k = r.key; if (!fam.has(k)) fam.set(k, []); fam.get(k).push(r); }
  const bad = (r) => (r.dy !== undefined && Math.abs(r.dy) > LIM) || (r.padL !== undefined && Math.abs(r.padL - r.padR) > 1) || (r.ic !== undefined && Math.abs(r.ic) > LIM) || (r.tc !== undefined && Math.abs(r.tc) > LIM);
  console.log(`${W}px ${THEME}: ${rows.length} badges, ${fam.size} families, ${rows.filter(bad).length} outliers (|dy| > ${LIM} or padding asymmetry > 1px)`);
  for (const [k, list] of [...fam].sort((a, b) => b[1].length - a[1].length)) {
    if (process.env.OUTLIERS && !list.some(bad)) continue;
    const dys = list.map((r) => r.dy).filter((v) => v !== undefined);
    const asym = list.map((r) => (r.padL !== undefined ? Math.round((r.padL - r.padR) * 100) / 100 : undefined)).filter((v) => v !== undefined);
    const gaps = [...new Set(list.map((r) => r.gapBox))].join('/');
    console.log(`\n${list.length}x ${k.split('|')[0] || '(no class)'} | icon ${k.split('|')[1]}`);
    const rg = (k) => { const v = list.map((r) => r[k]).filter((x) => x !== undefined); return v.length ? Math.min(...v) + '..' + Math.max(...v) : '-'; };
    console.log(`   icon-from-centre ${rg('ic')}  text-from-centre ${rg('tc')}`);
    console.log(`   dy ${dys.length ? Math.min(...dys) + '..' + Math.max(...dys) : '-'}  padL-padR ${asym.length ? Math.min(...asym) + '..' + Math.max(...asym) : '-'}  gapBox ${gaps}  ${list[0].css}`);
    const shown = new Set();
    for (const r of list) {
      if (process.env.OUTLIERS && !bad(r)) continue;
      const kk = r.view + r.text; if (shown.has(kk)) continue; shown.add(kk);
      if (shown.size > (process.env.FAMILY ? 2 : 6)) break;
      console.log(`   [${r.view}] "${r.text}" dy ${r.dy} padL ${r.padL} padR ${r.padR} gap ${r.gapBox} ink ${r.inkgap}`);
    }
  }
  const badRows = rowsOut.filter((r) => r.h > LIM || r.c > LIM || r.t > LIM);
  console.log(`\nrows of badges: ${rowsOut.length}, ${badRows.length} past ${LIM}px (height, centre line, text line)`);
  for (const r of badRows.slice(0, 40)) console.log(`   [${r.view}] .${r.parent} x${r.n} heights ${r.hs.join('/')} spread h ${r.h} centre ${r.c} text ${r.t}  ${r.names}`);
  if (marks.length) {
    console.log(`\nicons in circles: ${marks.length}`);
    const mf = new Map();
    for (const m of marks) { const k = `${m.key}|${m.size}`; if (!mf.has(k)) mf.set(k, []); mf.get(k).push(m); }
    for (const [k, list] of mf) { const dxs = list.map((m) => m.mdx).filter((v) => v !== undefined), dys = list.map((m) => m.mdy).filter((v) => v !== undefined); console.log(`  ${list.length}x ${k} [${[...new Set(list.map((m) => m.view))].join(',')}] dx ${Math.min(...dxs)}..${Math.max(...dxs)} dy ${Math.min(...dys)}..${Math.max(...dys)}`); }
  }
  fs.writeFileSync(`${OUT}/ba-${W}-${THEME}.json`, JSON.stringify({ rows, marks, rowsOut }));
})();
