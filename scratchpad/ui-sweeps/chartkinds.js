// L-chat-252: each chart kind the maker draws (bar, line, area, pie, scatter, histogram, table), drawn through
// `drawAskChart.maker.render`; measures what is on screen: the marks drawn, the SVG box, the table, the tooltip
// on a keyboard focus, and the contrast of a mark's fill against the card. THEME=dark for the dark sheet.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1200, height: 900 } });
  await page.evaluate(() => ensureModule('chartMaker'));
  const kinds = ['bar', 'line', 'area', 'pie', 'scatter', 'histogram', 'table'];
  const out = await page.evaluate(async (kinds) => {
    const lum = (c) => { const m = c.match(/[\d.]+/g).map(Number); const [r, g, b] = m.slice(0, 3).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
    const px = document.createElement('canvas').getContext('2d', { willReadFrequently: true });
    const rgbOf = (c) => { px.fillStyle = '#000'; px.fillStyle = c; px.clearRect(0, 0, 1, 1); px.fillRect(0, 0, 1, 1); const d = px.getImageData(0, 0, 1, 1).data; return `rgb(${d[0]},${d[1]},${d[2]})`; };
    const ratio = (a, b) => { const x = lum(a); const y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
    const rows = [];
    for (const kind of kinds) {
      const host = document.createElement('div');
      document.body.append(host);
      const text = kind === 'scatter' ? `title: ${kind}\nkind: ${kind}\n1, 3\n2, 5\n4, 4\n7, 9\n9, 2` : `title: ${kind}\nkind: ${kind}\nMon, 3\nTue, 5\nWed, 4\nThu, 8\nFri, 2\nSat, 6\nSun, 7\nMon2, 5\nTue2, 4`;
      const ok = drawAskChart.maker.render(host, text);
      const svg = host.querySelector('.ask-chart-svg');
      const box = svg && svg.getBoundingClientRect();
      const mark = host.querySelector('.ask-chart-slice, .ask-chart-bar, .ask-chart-dot, .ask-chart-area');
      const card = getComputedStyle(host.closest('body')).backgroundColor;
      const fill = mark ? rgbOf(getComputedStyle(mark).fill) : null;
      const slices = [...host.querySelectorAll('path.ask-chart-slice')].map((p) => rgbOf(getComputedStyle(p).fill));
      const distinct = new Set(slices).size;
      const table = host.querySelector('.ask-chart-numbers');
      rows.push({ kind, ok, svg: !!svg, w: box && Math.round(box.width), h: box && Math.round(box.height), marks: host.querySelectorAll('.ask-chart-pt').length, area: !!host.querySelector('polygon.ask-chart-area'), slicesDistinct: distinct, sliceMinContrast: slices.length ? +Math.min(...slices.map((c) => ratio(c, rgbOf(getComputedStyle(host.querySelector('.ask-chart-svg')).getPropertyValue('--card') || card)))).toFixed(2) : null, tableOpen: table && table.open, tableRows: host.querySelectorAll('.ask-chart-table tbody tr').length, contrast: fill && +ratio(fill, card).toFixed(2), saveSvg: [...host.querySelectorAll('button')].some((b) => /SVG/.test(b.textContent)) });
      host.remove();
    }
    return rows;
  }, kinds);
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
