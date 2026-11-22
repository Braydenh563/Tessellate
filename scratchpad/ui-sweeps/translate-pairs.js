// Real Bergamot run per installed pair, in Chromium, against the app's own worker and files.
const { chromium } = require('playwright');
const B = process.argv[2];
const SAMPLES = {
  en: 'The meeting moved to Thursday because the report is not finished.',
  es: 'La reunión se trasladó al jueves porque el informe no está terminado.',
  fr: "La réunion a été déplacée à jeudi parce que le rapport n'est pas terminé.",
  de: 'Das Treffen wurde auf Donnerstag verschoben, weil der Bericht nicht fertig ist.',
  it: 'La riunione è stata spostata a giovedì perché il rapporto non è finito.',
  pt: 'A reunião foi transferida para quinta-feira porque o relatório não está pronto.',
};
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(B + '/', { waitUntil: 'domcontentloaded' });
  const status = await (await fetch(B + '/translate/status', { headers: { 'X-Auth-Token': process.argv[3] } })).json();
  const out = await page.evaluate(async ({ pairs, samples }) => {
    let w;
    let n = 0;
    const ask = (pair, text) => new Promise((res) => {
      const id = ++n;
      const on = (e) => { if (e.data.id === id) { w.removeEventListener('message', on); res(e.data); } };
      w.addEventListener('message', on);
      w.postMessage({ id, pair, text });
    });
    const rows = [];
    for (const pair of pairs) { if (!w) w = new Worker('/js/translate-worker.js?v=' + Date.now()); const r = await ask(pair, samples[pair.from]); rows.push({ pair: pair.from + '-' + pair.to, ...r }); }
    return rows;
  }, { pairs: status.pairs, samples: SAMPLES });
  for (const r of out) console.log(JSON.stringify(r));
  await browser.close();
})();
