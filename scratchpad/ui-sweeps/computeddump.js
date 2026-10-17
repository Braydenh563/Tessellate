// Dump every computed style of every element under a root, for a before/after
// diff when CSS rules move between files (the boot budget's "move a surface
// into a lazy bundle"). Moving a rule after the later boot sheets can flip an
// equal-specificity tie, which no test sees.
//
//   SEL='#ocr-workspace' MODULE=libraryList OUT=/tmp/x.json BASE=... node computeddump.js
//   node computeddump.js --diff a.json b.json
const fs = require('fs');
if (process.argv[2] === '--diff') {
  const a = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  const b = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
  let n = 0;
  for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
    if (!(key in a) || !(key in b)) { console.log('MISSING', key); n++; continue; }
    for (const prop of new Set([...Object.keys(a[key]), ...Object.keys(b[key])])) {
      if (a[key][prop] !== b[key][prop]) { console.log(key, prop, a[key][prop], '->', b[key][prop]); n++; }
    }
  }
  console.log(`${Object.keys(a).length} elements, ${n} differences`);
  process.exit(0);
}
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: +(process.env.W || 1440), height: 900 } });
  const sel = process.env.SEL || '#ocr-workspace';
  if (process.env.MODULE) {
    await page.evaluate((m) => ensureModule(m), process.env.MODULE);
    await page.waitForTimeout(1500);
  }
  await page.evaluate((s) => {
    const root = document.querySelector(s);
    root.classList.remove('hidden');
    root.hidden = false;
    for (const el of root.querySelectorAll('[hidden]')) el.hidden = false;
  }, sel);
  await page.waitForTimeout(1500);
  const dump = await page.evaluate((s) => {
    const root = document.querySelector(s);
    const out = {};
    const els = [root, ...root.querySelectorAll('*')];
    els.forEach((el, i) => {
      const cs = getComputedStyle(el);
      const rec = {};
      for (let j = 0; j < cs.length; j++) rec[cs[j]] = cs.getPropertyValue(cs[j]);
      const r = el.getBoundingClientRect();
      rec.__rect = `${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.width)},${Math.round(r.height)}`;
      out[`${i}:${el.tagName}#${el.id}.${[...el.classList].join('.')}`] = rec;
    });
    return out;
  }, sel);
  fs.writeFileSync(process.env.OUT, JSON.stringify(dump));
  console.log(Object.keys(dump).length, 'elements');
  await browser.close();
})();
