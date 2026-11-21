// Brief 88 (a), the owner (screenshot of a faint glyph on Atlas): "what is
// this on the atlas companion?? sometimes when icons appear on atlas it is
// hard to see them or make them out." Shows each of Atlas's props in turn
// (every `.nmp-*` group in the companion's figure) and reads, per prop: its
// box on screen in px, and the contrast against Atlas's body colour of its
// best-seen edge: each shape's stroke (its keyline) or, with none, its fill,
// at the opacity it is drawn with. A halo (`*-glow`) does not count. PASS
// when every prop is at least 14px and has an edge at 3:1, and the
// companion's tooltip names a prop it has on. THEME=dark.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => { const b = $('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForTimeout(4000);
  const rows = await page.evaluate(() => {
    const lum = (c) => { const m = c.match(/[\d.]+/g); if (!m) return null; const [r, g, b] = m.slice(0, 3).map((v) => { v = v / 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
    const ratio = (a, b) => { const x = lum(a); const y = lum(b); if (x === null || y === null) return 0; return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
    const mix = (c, bg, a) => { const p = c.match(/[\d.]+/g).map(Number); const q = bg.match(/[\d.]+/g).map(Number); const alpha = a * (p.length > 3 ? p[3] : 1); return `rgb(${[0, 1, 2].map((i) => Math.round(p[i] * alpha + q[i] * (1 - alpha))).join(',')})`; };
    const buddy = document.getElementById('nm-buddy');
    const figure = buddy.querySelector('.nm-figure');
    const bodyEl = figure.querySelector('.atl-layer-body path, .atl-layer-body ellipse');
    const body = getComputedStyle(figure).getPropertyValue('--atl-md').trim() || '#9fb8ee';
    const probe = document.createElement('i'); probe.style.color = body; document.body.append(probe); const bodyRgb = getComputedStyle(probe).color; probe.remove();
    const out = [];
    const groups = [...figure.querySelectorAll('[class*="nmp-"]')].filter((g) => [...g.classList].some((c) => /^nmp-[a-z]+$/.test(c)) && !g.parentElement.closest('[class*="nmp-"]'));
    const seenNames = new Set();
    for (const g of groups) {
      const name = [...g.classList].find((c) => /^nmp-[a-z]+$/.test(c));
      // Not things it holds or wears: the coil is its own tail's band, and
      // the startle's bubble is a faint sheen round the whole figure.
      if (seenNames.has(name) || name === 'nmp-coil' || name === 'nmp-bubble') continue;
      seenNames.add(name);
      const was = g.style.opacity;
      // Shown at once: its fade would read as nothing shown.
      for (const el of [g, ...g.querySelectorAll('*')]) el.style.transition = 'none';
      g.style.opacity = '1';
      const r = g.getBoundingClientRect();
      let best = 0; let bestPart = '';
      for (const el of g.querySelectorAll('path, circle, ellipse, rect, line, polyline, polygon')) {
        if (/glow/.test(el.getAttribute('class') || '')) continue;
        const cs = getComputedStyle(el);
        let op = Number(cs.opacity); for (let p = el.parentElement; p && p !== g.parentElement; p = p.parentElement) op *= Number(getComputedStyle(p).opacity);
        for (const [paint, alpha] of [[cs.stroke, Number(cs.strokeOpacity)], [cs.fill, Number(cs.fillOpacity)]]) {
          if (!paint || paint === 'none' || !paint.startsWith('rgb')) continue;
          if (paint === cs.stroke && parseFloat(cs.strokeWidth) < 0.5) continue;
          const c = ratio(mix(paint, bodyRgb, alpha * op), bodyRgb);
          if (c > best) { best = c; bestPart = `${el.getAttribute('class')} ${paint === cs.stroke ? 'stroke' : 'fill'}`; }
        }
      }
      g.style.opacity = was;
      for (const el of [g, ...g.querySelectorAll('*')]) el.style.transition = '';
      out.push({ name, w: Math.round(r.width), h: Math.round(r.height), contrast: +best.toFixed(2), part: bestPart });
    }
    return { body: bodyRgb, out };
  });
  // And the tooltip names what it has on (headphones while a sound plays).
  const tip = await page.evaluate(() => { const b = document.getElementById('nm-buddy'); const face = b.querySelector('.nm-buddy-face'); b.classList.add('nmb-music'); face.dispatchEvent(new PointerEvent('pointerenter', { pointerType: 'touch' })); const on = face.title; b.classList.remove('nmb-music'); face.dispatchEvent(new PointerEvent('pointerenter', { pointerType: 'touch' })); return [on, face.title]; });
  let bad = tip[0].includes('headphones') && !tip[1].includes('headphones') ? 0 : 1;
  console.log(`${bad ? 'BAD ' : 'ok  '} tooltip with music "${tip[0]}", without "${tip[1]}"`);
  console.log(`body ${rows.body}`);
  for (const r of rows.out) {
    const ok = Math.max(r.w, r.h) >= 14 && r.contrast >= 3;
    if (!ok) bad += 1;
    console.log(`${ok ? 'ok  ' : 'BAD '} ${r.name} ${r.w}x${r.h}px edge ${r.contrast}:1 (${r.part})`);
  }
  console.log(bad ? `FAIL ${bad}` : 'PASS');
  await browser.close();
})();
