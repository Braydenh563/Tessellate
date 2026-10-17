// Animation longhands of every element under every Atlas figure (the generated
// face, the layered companion, a clone inside a keyboard-focused list row) in
// each of the four gates the idle loops sit behind (08-consistency.css, "Atlas's
// life"), for a before/after of a selector rewrite. OLD=1 serves the stylesheets
// from OLD07 and OLD08 (files holding the previous text) so one checkout
// measures both sides.
//
//   OUT=/tmp/new.json BASE=... node atlasanimdump.js
//   OLD=1 OLD07=a.css OLD08=b.css OUT=/tmp/old.json BASE=... node atlasanimdump.js
//   node atlasanimdump.js --diff old.json new.json
const fs = require('fs');
if (process.argv[2] === '--diff') {
  const a = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  const b = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
  let n = 0;
  for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
    if (a[key] !== b[key]) {
      n++;
      const x = String(a[key]).split(';'), y = String(b[key]).split(';');
      const d = x.map((v, i) => [v, y[i]]).filter(([v, w]) => v !== w).slice(0, 3);
      if (n < 12) console.log(key, JSON.stringify(d));
    }
  }
  console.log(`${Object.keys(a).length} records, ${n} differences`);
  process.exit(0);
}
const { boot } = require('./lib.js');
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  if (process.env.OLD) {
    for (const [pat, file] of [['**/css/07-whiteboard-misc.css*', process.env.OLD07], ['**/css/08-consistency.css*', process.env.OLD08]]) {
      await ctx.route(pat, (route) => route.fulfill({ status: 200, contentType: 'text/css', body: fs.readFileSync(file, 'utf8') }));
    }
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    await page.fill('#lock-password', 'testpassword123').catch(() => {});
    await page.click('#lock-submit').catch(() => {});
  }
  await page.waitForTimeout(2500);
  await page.getByRole('button', { name: "Don't check" }).click({ timeout: 3000 }).catch(() => {});
  await page.evaluate(() => { const b = document.getElementById('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForTimeout(3000);
  const info = await page.evaluate(() => ({ atlas: document.querySelectorAll('.nm-atlas').length, layer: document.querySelectorAll('.nm-atlas.atl-layer').length, blink: document.querySelectorAll('.atl-blink.nm-blinks').length, css: [...document.styleSheets].some((s) => (s.href || '').includes('08-consistency')), universalChild: [...document.styleSheets].some((sh) => { try { return [...sh.cssRules].some((r) => r.cssText.includes('.atl-blink.nm-blinks > *')); } catch (e) { return false; } }) }));
  console.log(JSON.stringify(info));
  const out = {};
  const dump = async (label) => {
    const rec = await page.evaluate(() => {
      const res = {};
      const roots = [...document.querySelectorAll('.nm-atlas')];
      // One string per figure; figures are compared as a sorted set, because the
      // companion and the generated faces do not keep a stable DOM order.
      const list = roots.map((root) => [root, ...root.querySelectorAll('*')].map((el, i) => {
        const cs = getComputedStyle(el);
        return `${i}:${el.tagName}.${String(el.getAttribute('class') || '').slice(0, 40)}=${[cs.animationName, cs.animationDuration, cs.animationDelay, cs.animationIterationCount].join('|')}`;
      }).join(';'));
      list.sort();
      list.forEach((v, i) => { res[String(i)] = v; });
      return res;
    });
    for (const [k, v] of Object.entries(rec)) out[`${label} ${k}`] = v;
  };
  const root = (attrs) => page.evaluate((attrs) => { for (const [k, v] of Object.entries(attrs)) { if (v === null) delete document.documentElement.dataset[k]; else document.documentElement.dataset[k] = v; } }, attrs);
  // 1: always (the first gate), motion not reduced
  await root({ avatarMotion: 'always', motion: null, buddyMotion: null });
  await page.waitForTimeout(500);
  await dump('always');
  // 2: hover mode, a clone inside a list row that holds a keyboard focus, and one inside a hovered row
  await root({ avatarMotion: 'hover', motion: null });
  await page.evaluate(() => {
    const src = document.querySelector('.nm-atlas');
    const li = document.createElement('li');
    li.id = 'atlas-probe-li';
    li.tabIndex = 0;
    li.style.position = 'fixed'; li.style.left = '20px'; li.style.top = '20px'; li.style.width = '200px'; li.style.height = '200px'; li.style.zIndex = 99999;
    li.appendChild(src.cloneNode(true));
    document.body.appendChild(li);
    const lay = document.querySelector('#nm-buddy .nm-atlas.atl-layer');
    if (lay) { const li2 = document.createElement('li'); li2.id = 'atlas-probe-li2'; li2.tabIndex = 0; li2.style.position = 'fixed'; li2.style.left = '240px'; li2.style.top = '20px'; li2.style.width = '200px'; li2.style.height = '200px'; li2.style.zIndex = 99999; li2.appendChild(lay.cloneNode(true)); document.body.appendChild(li2); }
  });
  await page.keyboard.press('Shift');
  await page.evaluate(() => document.getElementById('atlas-probe-li').focus({ focusVisible: true }));
  await page.waitForTimeout(500);
  await dump('hover-focus-li');
  await page.evaluate(() => document.activeElement.blur());
  await page.mouse.move(100, 100);
  await page.waitForTimeout(500);
  await dump('hover-hovered-li');
  await page.mouse.move(1300, 800);
  const hasLi2 = await page.evaluate(() => !!document.getElementById('atlas-probe-li2'));
  if (hasLi2) {
    await page.evaluate(() => document.getElementById('atlas-probe-li2').focus({ focusVisible: true }));
    await page.waitForTimeout(500);
    await dump('hover-focus-layer-li');
    await page.evaluate(() => document.activeElement.blur());
  }
  // 3: the companion's own gate (.nm-live, full buddy motion)
  await root({ avatarMotion: 'always', buddyMotion: 'full' });
  await page.waitForTimeout(500);
  await dump('buddy-full');
  fs.writeFileSync(process.env.OUT, JSON.stringify(out));
  console.log(Object.keys(out).length, 'records');
  await browser.close();
})();
