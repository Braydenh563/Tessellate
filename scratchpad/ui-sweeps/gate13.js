// 13.0 gate recount for decisions 9 to 17 (UI_MODERNISATION_PLAN.md, 13.3), from the running app.
//
//   BASE=http://127.0.0.1:8823 SCRATCH=<dir> W=1440 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/gate13.js        (W=390 for the phone width)
//
// Two reads. CSS: every stylesheet the server serves under /css is fetched by the page and parsed by
// the browser's own CSSOM (tokens, colour literals outside the two colour files, literal z-index,
// outer drop shadows, literal durations, !important, border-radius 50% rules, hover rules without a
// focus-visible twin). Live: computed font size, z-index, box-shadow, transition duration and
// circular boxes over every visible element of seven tabs and Settings. Writes $SCRATCH/out-<W>.json.
const { boot } = require('./lib.js');
const fs = require('fs');
const OWN = ['00-tokens-shell', '05-sidebars-themes'];
const CSSOM = `(() => { const FILES = __FILES__;
  const OWN = ${JSON.stringify(OWN)};
  const out = { sheets: {}, props: new Set(), color: {inOwn:0, outside:0, byFile:{}}, fs: {}, z: {}, zLit: 0, shadow: new Set(), shadowLit:0, dur: {lit:0, tok:0, vals:{}}, imp: {total:0, byFile:{}}, circ50: 0, circFiles:{}, hover: 0, hoverNoFocus: 0, hoverSels: new Set(), focusSels: new Set(), noFocusList: [] };
  const COL = /#[0-9a-fA-F]{3,8}\\b|rgba?\\(|hsla?\\(/g;
  const splitTop = (t) => { const o=[]; let d=0, c=''; for (const ch of t) { if (ch==='(') d++; if (ch===')') d--; if (ch===',' && d===0) { o.push(c.trim()); c=''; } else c+=ch; } o.push(c.trim()); return o; };
  const norm = (x, re) => x.replace(':is(:focus-visible, :has(:focus-visible))', ':focus-visible').replace(re, '§').replace(/\\s+/g,' ');
  const walk = (rules, file) => { for (const r of rules) {
    if (r.cssRules && !r.style) walk(r.cssRules, file);
    if (r.style) { const st = r.style; const decls = []; { let d=0, q='', cur=''; for (const ch of st.cssText) { if (q) { if (ch===q) q=''; cur+=ch; continue; } if (ch==='"'||ch==="'") { q=ch; cur+=ch; continue; } if (ch==='(') d++; if (ch===')') d--; if (ch===';' && d===0) { decls.push(cur); cur=''; } else cur+=ch; } if (cur.trim()) decls.push(cur); }
    for (const dc of decls) { const ix = dc.indexOf(':'); if (ix<0) continue; const p = dc.slice(0,ix).trim(); let v = dc.slice(ix+1).trim(); const imp = /!\s*important\s*$/.test(v); v = v.replace(/!\s*important\s*$/,'').trim();
      if (p.startsWith('--')) out.props.add(p);
      if (imp) { out.imp.total++; out.imp.byFile[file] = (out.imp.byFile[file]||0)+1; }
      { const vv = v.replace(/url\([^)]*\)/g, '').replace(/var\([^)]*\)/g, (m)=>m); const m = vv.match(COL);
        if (m) { const own = OWN.some(o => file.includes(o)); if (own) out.color.inOwn += m.length; else { out.color.outside += m.length; out.color.byFile[file] = (out.color.byFile[file]||0)+m.length; } } }
      if (p === 'font-size' && !/var\\(/.test(v)) out.fs[v] = (out.fs[v]||0)+1;
      if (p === 'z-index') { out.z[v] = (out.z[v]||0)+1; if (!/var\\(/.test(v) && Math.abs(parseInt(v))>2) out.zLit++; }
      if (p === 'box-shadow' && v !== 'none') { out.shadow.add(v); if(!/var\\(/.test(v)) { out.shadowLit++; (out.shadowLits=out.shadowLits||[]).push(v.slice(0,60)); } }
      if (p === 'transition-duration' || p === 'transition' || p === 'animation' || p === 'animation-duration') {
        const lit = (v.replace(/var\\([^)]*\\)/g,'').match(/\\b\\d*\\.?\\d+m?s\\b/g)||[]);
        if (/var\\(--motion/.test(v)) out.dur.tok++;
        for (const d of lit) { out.dur.lit++; if (p.startsWith('transition') && d !== '0s' && d !== '0.001ms' && d !== '1ms') out.dur.transLit = (out.dur.transLit||0)+1; out.dur.vals[d] = (out.dur.vals[d]||0)+1; }
      }
      if ((p === 'border-radius') && /^50%$/.test(v)) { out.circ50++; out.circFiles[file] = (out.circFiles[file]||0)+1; (out.circSels = out.circSels||[]).push(r.selectorText||''); }
    }
    }
    if (r.selectorText) { const sels = splitTop(r.selectorText); const strip = (x)=>x.replace(/:not\\((?:[^()]|\\([^()]*\\))*\\)/g,'');
      const hov = sels.filter(x => /:hover/.test(strip(x)) && !/:not\\(:focus\\)|::-webkit-scrollbar|::file-selector-button/.test(x));
      for (const h of hov) { if (!/:focus-visible|:focus-within|:focus\\b/.test(strip(h))) out.noFocusList.push(h); out.hoverSels.add(h); }
      for (const x of sels) { if (/:focus-visible|:focus-within|:focus\\b/.test(strip(x))) out.focusSels.add(norm(x, /:focus-visible|:focus-within|:focus\\b/g)); } }
  } };
  for (const f of FILES) { const sh = new CSSStyleSheet(); sh.replaceSync(f.text); out.sheets[f.file] = sh.cssRules.length; walk(sh.cssRules, f.file); }
  out.lone = []; { const lone = out.noFocusList.filter(h => !out.focusSels.has(norm(h, /:hover/g))); out.hoverNoFocus = new Set(lone).size; out.lone = [...new Set(lone)]; }
  out.hover = out.hoverSels.size;
  return { sheets: out.sheets, props: out.props.size, color: out.color, fs: out.fs, z: out.z, zLit: out.zLit, shadowDistinct: out.shadow.size, shadowLit: out.shadowLit, dur: out.dur, imp: out.imp, circ50: out.circ50, circFiles: out.circFiles, hover: out.hover, hoverNoFocus: out.hoverNoFocus, lone: out.lone, circSels: out.circSels, shadowLits: out.shadowLits, impBy: out.imp.byFile };
})()`;
const LIVE = `(() => {
  const vis = (e) => e.checkVisibility && e.checkVisibility({visibilityProperty:true,opacityProperty:true}) && (r=>r.width>=2&&r.height>=2)(e.getBoundingClientRect());
  const res = { n: 0, fs: {}, z: {}, shadow: {}, dur: {}, circ: [], };
  for (const e of document.querySelectorAll('body *')) {
    if (!vis(e)) continue; res.n++;
    const cs = getComputedStyle(e);
    if (e.childNodes && [...e.childNodes].some(n => n.nodeType===3 && n.textContent.trim())) res.fs[cs.fontSize] = (res.fs[cs.fontSize]||0)+1;
    if (cs.position !== 'static' && cs.zIndex !== 'auto') res.z[cs.zIndex] = (res.z[cs.zIndex]||0)+1;
    if (cs.boxShadow !== 'none') res.shadow[cs.boxShadow] = (res.shadow[cs.boxShadow]||0)+1;
    const td = cs.transitionDuration; if (td && td !== '0s') res.dur[td] = (res.dur[td]||0)+1;
    const r = e.getBoundingClientRect(), br = parseFloat(cs.borderTopLeftRadius);
    if (r.width >= 4 && Math.abs(r.width - r.height) < 1.5 && br >= Math.min(r.width, r.height)/2 - 0.5 && cs.borderTopLeftRadius.indexOf('%')<0 || cs.borderTopLeftRadius === '50%') {
      res.circ.push((e.tagName.toLowerCase() + (e.id?'#'+e.id:'') + '.' + String(e.className&&e.className.baseVal!==undefined?e.className.baseVal:e.className).split(/\\s+/).filter(Boolean).slice(0,2).join('.')) + ' ' + Math.round(r.width)+'x'+Math.round(r.height));
    }
  }
  return res;
})()`;
(async () => {
  const W = Number(process.env.W || 1440);
  const { browser, page } = await boot({ viewport: { width: W, height: W > 800 ? 900 : 844 } });
  const merge = (a, b) => { for (const k in b) a[k] = (a[k]||0) + b[k]; };
  const agg = { n:0, fs:{}, z:{}, shadow:{}, dur:{}, circ:{} };
  const surf = {};
  const tabs = ['dashboard','notes','chat','graph','timeline','library','reminders'];
  for (const t of tabs) {
    await page.evaluate((t) => { try { switchTab(t); } catch (e) {} }, t);
    await page.waitForTimeout(2500);
    const l = await page.evaluate(LIVE);
    surf[t] = { n: l.n, circles: l.circ.length };
    agg.n += l.n; merge(agg.fs, l.fs); merge(agg.z, l.z); merge(agg.shadow, l.shadow); merge(agg.dur, l.dur);
    for (const c of l.circ) agg.circ[t + ': ' + c] = 1;
  }
  // Settings and the command palette load their own sheets.
  await page.evaluate(() => { try { document.querySelector('#settings-btn, [data-open-settings], #open-settings')?.click(); } catch (e) {} });
  await page.waitForTimeout(2500);
  { const l = await page.evaluate(LIVE); surf.settings = { n: l.n, circles: l.circ.length }; agg.n += l.n; merge(agg.fs, l.fs); merge(agg.z, l.z); merge(agg.shadow, l.shadow); merge(agg.dur, l.dur); for (const c of l.circ) agg.circ['settings: ' + c] = 1; }
  const names = fs.readdirSync(require('path').join(__dirname, '..', '..', 'frontend', 'css')).filter(n=>n.endsWith('.css'));
  const files = await page.evaluate(async (ns) => Promise.all(ns.map(async (n) => ({ file: n, text: await (await fetch('/css/' + n)).text() }))), names);
  const loaded = await page.evaluate(() => [...document.styleSheets].map(s => (s.href||'').split('/').pop().split('?')[0]).filter(Boolean));
  const css = await page.evaluate(CSSOM.replace('__FILES__', JSON.stringify(files)));
  css.served = names.length; css.loadedInPage = loaded.length;
  const out = { width: W, css, live: { visibleElements: agg.n, fontSizes: agg.fs, z: agg.z, shadowDistinct: Object.keys(agg.shadow).length, shadows: agg.shadow, durations: agg.dur, circles: Object.keys(agg.circ) }, surf };
  fs.writeFileSync(`${process.env.SCRATCH || '.'}/out-${W}.json`, JSON.stringify(out, null, 1));
  console.log(JSON.stringify({ props: css.props, color: { inOwn: css.color.inOwn, outside: css.color.outside }, imp: css.imp.total, circ50: css.circ50, hover: css.hover, hoverNoFocus: css.hoverNoFocus, zLit: css.zLit, shadowDistinct: css.shadowDistinct, shadowLit: css.shadowLit, durLit: css.dur.lit, durTransLit: css.dur.transLit||0, durTok: css.dur.tok, sheets: Object.keys(css.sheets).length, liveFs: Object.keys(agg.fs).length, liveShadow: Object.keys(agg.shadow).length, liveZ: Object.keys(agg.z).length, liveCirc: Object.keys(agg.circ).length, surf }));
  await browser.close();
})();
