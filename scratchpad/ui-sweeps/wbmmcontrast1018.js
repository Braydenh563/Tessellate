// Contrast of the CONTENT of a board and a map (stickies, text cards, frames,
// shapes, topics), which contrast.js under-reads: it measures text nodes with
// an opaque ancestor background and skips gradients and SVG text. Here every
// element with its own text under #whiteboard-container is composited from the
// effective background (translucent layers over the first opaque one) and
// SVG <text> is read against the board ground. THEME=dark, WIDTH=390 as usual.
//   BASE=http://127.0.0.1:8797 THEME=dark node scratchpad/ui-sweeps/wbmmcontrast1018.js
const { boot, openBoardsTab, waitForBoardOpen } = require('./lib.js');
const WIDTH = Number(process.env.WIDTH || 1440);
const PHONE = WIDTH < 600;
(async () => {
  const { browser, page } = await boot({ viewport: { width: WIDTH, height: PHONE ? 844 : 900 }, hasTouch: PHONE, isMobile: PHONE });
  await openBoardsTab(page);
  let bad = 0;
  const targets = await page.evaluate(async () => (await apiJson('/whiteboard/boards')).filter((b) => /^Contrast/.test(b.title || b.name || '')).map((b) => [b.type === 'map' ? 'map ' + b.title : 'board', b.id]));
  for (const [kind, id] of targets) {
    await page.evaluate(async (i) => { await openWhiteboardBoard(i); }, id);
    await waitForBoardOpen(page, 0);
    await page.waitForTimeout(1500);
    console.log(JSON.stringify(await page.evaluate(() => ({ objs: document.querySelectorAll('.wb-object').length, state: (wbState.objects || []).length, sketches: (wbState.sketches || []).length, edges: document.querySelectorAll('.wb-map-edge').length, e0: (() => { const e = document.querySelector('.wb-map-edge'); if (!e) return null; const c = getComputedStyle(e); return [c.stroke, c.strokeWidth, c.opacity, e.checkVisibility()]; })() }))));
    for (const mode of ['rest', 'selected']) {
      if (mode === 'selected') { await page.evaluate(() => { try { wbSelectAllItems(); } catch (e) {} }); await page.waitForTimeout(500); }
      const r = await page.evaluate(() => {
        const cv = document.createElement('canvas'); cv.width = cv.height = 1; const cx = cv.getContext('2d', { willReadFrequently: true });
        const parse = (c) => { if (!c || c === 'transparent') return null; cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1); const d = cx.getImageData(0, 0, 1, 1).data; if (d[3] === 0) return null; return { r: d[0], g: d[1], b: d[2], a: d[3] / 255 }; };
        const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
        const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05); };
        const over = (t, b) => ({ r: t.r * t.a + b.r * (1 - t.a), g: t.g * t.a + b.g * (1 - t.a), b: t.b * t.a + b.b * (1 - t.a), a: 1 });
        const bgOf = (el) => { const layers = []; let base = null; let grad = false; for (let e = el; e; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.backgroundImage && cs.backgroundImage !== 'none') grad = true; const c = parse(cs.backgroundColor); if (c) { if (c.a >= 0.99) { base = c; break; } layers.push(c); } } if (!base) base = parse(getComputedStyle(document.body).backgroundColor) || { r: 255, g: 255, b: 255, a: 1 }; let c = base; for (let i = layers.length - 1; i >= 0; i--) c = over(layers[i], c); return { c, grad }; };
        const root = document.getElementById('whiteboard-container') || document.body;
        const out = []; let n = 0; window.__all = [];
        for (const el of root.querySelectorAll('*')) {
          if (!el.checkVisibility || !el.checkVisibility()) continue;
          const own = [...el.childNodes].filter((x) => x.nodeType === 3 && x.textContent.trim()).map((x) => x.textContent.trim()).join(' ');
          if (!own) continue;
          const cs = getComputedStyle(el);
          const svg = el instanceof SVGElement;
          const fg = parse(svg ? cs.fill : cs.color); if (!fg) continue;
          const { c: bg0, grad } = svg ? { c: parse(getComputedStyle(root).backgroundColor) || bgOf(root).c, grad: false } : bgOf(el);
          const bg = svg ? bgOf(el.closest('svg') || root).c : bg0;
          const f = fg.a < 1 ? over(fg, bg) : fg; n++;
          const r = ratio(f, bg); const size = parseFloat(cs.fontSize); const bold = parseInt(cs.fontWeight) >= 700;
          const need = size >= 18.66 || (bold && size >= 14) ? 3 : 4.5;
          if (window.__all) window.__all.push([r, own.slice(0,16), el.className.toString().slice(0,24)]); if (r < need) out.push(`${r.toFixed(2)}${grad ? 'g' : ''} <${el.tagName.toLowerCase()}.${[...el.classList].slice(0, 2).join('.')}> "${own.slice(0, 24)}" fg ${cs.color} on rgb(${Math.round(bg.r)},${Math.round(bg.g)},${Math.round(bg.b)}) ${size}px`);
        }
        // Non-text marks (3:1): a connector, a shape outline, a map edge, drawn
        // against the board ground. Strokes that carry a colour on purpose (a
        // branch colour) are still held to it: it is the line the eye follows.
        const ground = bgOf(root).c; const lines = []; window.__st = [];
        for (const el of root.querySelectorAll('path, line, polyline, rect, ellipse, circle')) {
          if (!el.checkVisibility || !el.checkVisibility()) continue;
          const cs = getComputedStyle(el); if (!cs.stroke || cs.stroke === 'none' || parseFloat(cs.strokeWidth) < 1) continue;
          const sc = parse(cs.stroke); if (!sc) continue; const op = parseFloat(cs.strokeOpacity) * parseFloat(cs.opacity) * sc.a;
          const f = over({ ...sc, a: op }, ground); const r = ratio(f, ground);
           window.__st.push([r, (el.getAttribute('class') || '').split(' ')[0], cs.stroke]); if (r < 3) lines.push(`${r.toFixed(2)} <${el.tagName}.${(el.getAttribute('class') || '').slice(0, 28)}> ${cs.stroke} op ${op.toFixed(2)} w ${cs.strokeWidth}`);
        }
        for (const el of root.querySelectorAll('[class*="handle"], [class*="grip"], [class*="port"], path.wb-map-edge, .wb-map-link')) {
          if (!el.checkVisibility || !el.checkVisibility()) continue;
          const cs = getComputedStyle(el); if (!(el instanceof SVGElement) || parseFloat(cs.opacity) < 0.5) continue;
          const fc = parse(cs.fill); if (!fc) continue; const r = ratio(over({ ...fc, a: fc.a * parseFloat(cs.fillOpacity) }, ground), ground);
          window.__st.push([r, (el.getAttribute('class') || '').split(' ')[0], cs.fill]); if (r < 3) lines.push(`${r.toFixed(2)} FILL <${el.tagName}.${(el.getAttribute('class') || '').slice(0, 28)}> ${cs.fill}`);
        }
        return { stmin: Object.entries(window.__st.reduce((m, x) => { m[x[1]] = Math.min(m[x[1]] ?? 99, x[0]); return m; }, {})).filter(([k]) => /edge|brace|boundary|link|spine|sketch(?!-hit)/.test(k)).map(([k, v]) => k + ' ' + v.toFixed(2)).join(' | '), lines: [...new Set(lines)].slice(0, 15), n, out: [...new Set(out)].slice(0, 25), low: window.__all.sort((a, b) => a[0] - b[0]).slice(0, 6).map((x) => x[0].toFixed(2) + ' ' + x[1] + ' ' + x[2]) };
      });
      console.log(`== ${kind}/${mode} ${process.env.THEME || 'light'} ${WIDTH}: ${r.out.length ? r.out.length + ' low' : 'ok'} (${r.n} text elements)`);
      r.out.forEach((l) => console.log('  ' + l)); console.log('  lowest: ' + r.low.join(' | '));
      console.log('  weakest strokes: ' + r.stmin);
      console.log(`  strokes under 3:1: ${r.lines.length}`); r.lines.forEach((l) => console.log('    ' + l));
      bad += r.out.length;
    }
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(300);
  }
  await browser.close();
  process.exitCode = bad ? 1 : 0;
})();
