// Escape and Back on the image lightbox (WORLD_CLASS row 32 leftovers).
//   BASE=http://127.0.0.1:8797 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node esc-lightbox-1018.js
const { boot } = require('./lib.js');
const PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGP8z8DAwMDAxMDAwAAADwEBAAyEAvUAAAAASUVORK5CYII=';
(async () => {
  process.on('unhandledRejection', console.log);
  const { browser, page } = await boot();
  await page.evaluate(async (b64) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const fd = new FormData();
    fd.append('file', new File([bytes], 'p.png', { type: 'image/png' }));
    fd.append('direct', 'true');
    await fetch('/media/upload', { method: 'POST', body: fd, headers: { 'X-Auth-Token': authToken(), 'X-Workspace-ID': activeSpaceId() } });
  }, PNG);
  await page.evaluate(() => switchTab('library'));
  await page.waitForTimeout(1000);
  console.log(await page.evaluate(() => { const bs = [...document.querySelectorAll('#tab-library [role=tab], #tab-library button')].filter((e)=>/image|picture/i.test(e.textContent+e.id)); bs[0] && bs[0].click(); return bs.map((b)=>b.id+':'+b.textContent.trim()).join('|'); }));
  await page.waitForTimeout(2500);
  const count = () => page.evaluate(() => document.querySelectorAll('.lightbox').length);
  const open = async () => { console.log('tiles', await page.evaluate(()=>document.querySelectorAll('.library-image-tile').length)); await page.evaluate(() => document.querySelector('.library-image-tile img')?.click()); await page.waitForTimeout(2500); };
  await open();
  console.log('open', await count());
  await page.keyboard.press('Escape'); await page.waitForTimeout(300);
  console.log('after Escape (focus on body)', await count());
  await open();
  await page.evaluate(() => document.querySelector('.lightbox button')?.focus());
  await page.keyboard.press('Escape'); await page.waitForTimeout(300);
  console.log('after Escape (focus on button)', await count());
  // Back
  await page.evaluate(() => switchTab('notes')); await page.waitForTimeout(300);
  await page.evaluate(() => switchTab('library')); await page.waitForTimeout(800);
  await open();
  const tab0 = await page.evaluate(() => document.querySelector('[role=tab][aria-selected=true]')?.id);
  await page.goBack(); await page.waitForTimeout(800);
  const tab1 = await page.evaluate(() => document.querySelector('[role=tab][aria-selected=true]')?.id);
  console.log('Back: lightboxes', await count(), 'tab', tab0, '->', tab1);
  await browser.close();
})();
