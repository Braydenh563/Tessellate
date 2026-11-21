// Shell measurement for L-world-class-106 (devibecode, first surface). Read-only.
// Per viewport (WxH@scale), THEME and REDUCED=1: top bar, utility cluster, tab bar,
// status bar, sidebar, horizontal scroll, shell text contrast, shell targets under 24px,
// running animations. Notes and Chat tabs. SHOTS=1 saves a shell shot per viewport.
//   BASE=http://127.0.0.1:8884 THEME=dark SCRATCH=<dir> VPS=1280x720@1 node shell-devibe-106.js
const { boot } = require('./lib.js');
const VPS = (process.env.VPS || '1093x614@1.25,1280x720@1,1366x768@1,1536x864@1.25,1920x1080@1,1024x768@1,820x1180@1').split(',');
const measure = () => {
  const R = (el) => { if (!el) return null; const r = el.getBoundingClientRect(); return { x: +r.x.toFixed(1), y: +r.y.toFixed(1), w: +r.width.toFixed(1), h: +r.height.toFixed(1) }; };
  const vis = (el) => el && el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) && el.getBoundingClientRect().width > 0;
  const cs = (el, p) => getComputedStyle(el)[p];
  const out = {};
  const de = document.documentElement;
  out.doc = { scrollW: de.scrollWidth, clientW: de.clientWidth, innerW: innerWidth, hscroll: de.scrollWidth > de.clientWidth };
  const tb = document.getElementById('top-bar'); out.top = R(tb); out.topPad = cs(tb, 'padding'); out.topBorderB = cs(tb, 'borderBottomWidth');
  out.wordmark = R(tb.querySelector('h1')); out.wordmarkText = tb.querySelector('h1').textContent; out.wordmarkDisplay = cs(tb.querySelector('h1'), 'display') + '/' + cs(tb.querySelector('h1'), 'fontSize');
  out.logo = R(document.getElementById('brand-logo'));
  out.spaceBtn = R(document.getElementById('space-switcher-btn'));
  const hc = tb.querySelector('.header-controls'); out.controls = R(hc);
  out.clusters = [...hc.querySelectorAll('.header-cluster')].map((c) => ({ box: R(c), bg: cs(c, 'backgroundColor'), border: cs(c, 'borderTopWidth') + ' ' + cs(c, 'borderTopColor'), radius: cs(c, 'borderRadius'), gap: cs(c, 'gap'), shadow: cs(c, 'boxShadow') }));
  const ids = ['privacy-chip', 'notif-btn', 'theme-btn', 'settings-btn', 'lock-btn', 'quit-btn'];
  out.buttons = ids.map((id) => { const el = document.getElementById(id); if (!el) return { id, missing: true };
    return { id, shown: !!vis(el), box: R(el), bg: cs(el, 'backgroundColor'), border: cs(el, 'borderTopWidth') + ' ' + cs(el, 'borderTopColor'), radius: cs(el, 'borderRadius'), shadow: cs(el, 'boxShadow'), icon: R(el.querySelector('i')) }; });
  const sh = out.buttons.filter((b) => b.shown); out.gaps = [];
  for (let i = 1; i < sh.length; i++) out.gaps.push(+(sh[i].box.x - (sh[i - 1].box.x + sh[i - 1].box.w)).toFixed(1));
  out.boxedButtons = sh.filter((b) => (parseFloat(b.border) > 0 && !/rgba\(0, 0, 0, 0\)/.test(b.border)) || !/rgba\(0, 0, 0, 0\)/.test(b.bg) || b.shadow !== 'none').map((b) => b.id);
  const bar = document.getElementById('tab-bar'); const tabs = [...bar.querySelectorAll('[role=tab]')];
  out.tabBar = { box: R(bar), scrollW: bar.scrollWidth, clientW: bar.clientWidth, overflow: bar.scrollWidth - bar.clientWidth, overflowX: cs(bar, 'overflowX') };
  out.tabs = tabs.map((t) => { const l = t.querySelector('.tab-label, span:not(.tab-icon)'); const lr = l ? l.getBoundingClientRect() : null;
    return { id: t.dataset.tab, shown: !!vis(t), box: R(t), labelShown: !!(l && vis(l)), labelW: lr ? +lr.width.toFixed(1) : null, labelFont: l ? cs(l, 'fontSize') : null, labelClip: l ? l.scrollWidth > l.clientWidth + 1 : null, btnClip: t.scrollWidth > t.clientWidth + 1 }; });
  const st = document.getElementById('status-bar'); out.status = R(st); out.statusDisplay = cs(st, 'display');
  out.statusClipped = [...st.querySelectorAll('*')].filter((e) => vis(e) && e.children.length === 0 && e.textContent.trim() && e.scrollWidth > e.clientWidth + 1 && !e.closest('.visually-hidden') && e.getBoundingClientRect().width > 2).map((e) => (e.id || e.className) + ' ' + e.scrollWidth + '>' + e.clientWidth);
  out.statusItems = [...st.querySelectorAll('.status-item,#ai-status')].filter(vis).map((e) => ({ id: e.id, box: R(e), fs: cs(e, 'fontSize'), text: e.textContent.trim().slice(0, 30) }));
  out.statusStatusOverflow = st.scrollWidth - st.clientWidth;
  const sb = document.getElementById('sidebar'); out.sidebar = sb ? { shown: !!vis(sb), box: R(sb), clipX: sb.scrollWidth - sb.clientWidth } : null;
  out.anim = document.getAnimations().filter((a) => { const t = a.effect && a.effect.target; return t && t.closest && t.closest('#top-bar,#tab-bar,#status-bar,#sidebar,.emblem') ; }).map((a) => (a.constructor.name + ':' + (a.animationName || a.transitionProperty) + ' on ' + (a.effect.target.id || a.effect.target.className)).slice(0, 90));
  // Contrast for shell text.
  const lum = (c) => { const v = c.map((x) => { x /= 255; return x <= .03928 ? x / 12.92 : Math.pow((x + .055) / 1.055, 2.4); }); return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; };
  const parse = (s) => { const m = s.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,\/]+/).map(Number); return { c: p.slice(0, 3), a: p.length > 3 ? p[3] : 1 }; };
  const bgOf = (el) => { let base = [255, 255, 255]; const chain = []; for (let e = el; e; e = e.parentElement) chain.push(e);
    let acc = null; for (const e of chain) { const p = parse(cs(e, 'backgroundColor')); if (p && p.a > 0) { if (p.a >= 1) { base = p.c; acc = acc ? [acc] : null; const layers = []; for (const e2 of chain.slice(0, chain.indexOf(e)).reverse()) { const q = parse(cs(e2, 'backgroundColor')); if (q && q.a > 0) layers.push(q); } let c = base; for (const q of layers) c = c.map((v, i) => v * (1 - q.a) + q.c[i] * q.a); return { c, translucent: layers.length > 0 }; } } }
    return { c: base, translucent: true }; };
  const fails = [];
  for (const root of ['#top-bar', '#tab-bar', '#status-bar']) for (const el of document.querySelectorAll(root + ' *')) {
    if (!vis(el)) continue; const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()); const isIcon = el.classList.contains('ph');
    if (!own && !isIcon) continue; const fg = parse(cs(el, 'color')); if (!fg) continue; const bg = bgOf(el);
    let op = 1; for (let e = el; e; e = e.parentElement) op *= parseFloat(cs(e, 'opacity'));
    const f = fg.c.map((v, i) => v * fg.a * op + bg.c[i] * (1 - fg.a * op)); const L1 = lum(f), L2 = lum(bg.c); const ratio = (Math.max(L1, L2) + .05) / (Math.min(L1, L2) + .05);
    const fs = parseFloat(cs(el, 'fontSize')); const bold = parseInt(cs(el, 'fontWeight')) >= 700; const need = isIcon ? 3 : (fs >= 18.66 || (bold && fs >= 14)) ? 3 : 4.5;
    if (ratio < need) fails.push({ sel: el.id ? '#' + el.id : (el.tagName.toLowerCase() + '.' + [...el.classList].join('.')), in: root, ratio: +ratio.toFixed(2), need, fs, text: el.textContent.trim().slice(0, 20), translucent: bg.translucent });
  }
  out.contrast = fails;
  out.small = [...document.querySelectorAll('#top-bar button,#top-bar [role=button],#tab-bar [role=tab],#status-bar button,#status-bar [tabindex]')].filter(vis).map((e) => ({ sel: e.id ? '#' + e.id : e.tagName.toLowerCase() + '.' + [...e.classList].join('.'), w: +e.getBoundingClientRect().width.toFixed(1), h: +e.getBoundingClientRect().height.toFixed(1) })).filter((x) => x.w < 24 || x.h < 24);
  out.minTarget = [...document.querySelectorAll('#top-bar button,#tab-bar [role=tab],#status-bar button')].filter(vis).map((e) => ({ sel: e.id || e.className, h: e.getBoundingClientRect().height })).sort((a, b) => a.h - b.h).slice(0, 3);
  return out;
};
(async () => {
  const all = {};
  for (const vp of VPS) {
    const [dim, sc] = vp.split('@'); const [w, h] = dim.split('x').map(Number);
    const { browser, page, OUT } = await boot({ viewport: { width: w, height: h }, scale: Number(sc || 1), reducedMotion: process.env.REDUCED ? 'reduce' : 'no-preference' });
    for (const tab of ['notes', 'chat']) {
      await page.evaluate((t) => switchTab(t), tab); await page.waitForTimeout(1200);
      const r = await page.evaluate(measure); r.tab = tab; all[vp + ':' + tab] = r;
      if (process.env.SHOTS && tab === 'notes') await page.screenshot({ path: `${OUT}/shell-before-${w}x${h}-${process.env.THEME || 'light'}.png` });
    }
    await browser.close();
  }
  require('fs').writeFileSync((process.env.SCRATCH || '.') + `/shell-${process.env.THEME || 'light'}${process.env.REDUCED ? '-reduced' : ''}.json`, JSON.stringify(all, null, 1));
  console.log('done', Object.keys(all).length);
})();
